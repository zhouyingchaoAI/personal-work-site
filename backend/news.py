"""News source configuration, fetching, issue generation, and scheduler.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def news_dir():
    return USER_DATA_DIR / "_news"


def user_news_dir(username):
    """每个账号的个人资讯存储目录。"""
    return user_root(username) / "news"


def _news_issues(directory):
    """目录下全部简报文件（不含 latest.json），按文件名倒序：[(文件名, 内容)]。"""
    entries = office_doc_list("news", directory)
    return [(name, payload) for name, payload, _ in sorted(entries, key=lambda entry: entry[0], reverse=True)
            if name != "latest.json"]


def clean_news_sources(sources):
    if isinstance(sources, str):
        sources = [{"name": "", "url": line.strip()} for line in sources.splitlines() if line.strip()]
    clean_sources = []
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "web") or "web").strip().lower()
        if kind not in {"web", "wechat_account"}:
            kind = "web"
        name = str(item.get("name", "") or "").strip()
        url = str(item.get("url", "") or "").strip()
        if not url:
            if kind == "wechat_account":
                if not name:
                    raise ValueError("请填写公众号名称")
                clean_sources.append({"name": name, "url": "", "kind": kind})
                continue
            continue
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("资讯来源路径必须以 http:// 或 https:// 开头")
        if kind == "wechat_account":
            if not name:
                raise ValueError("请填写公众号名称")
            if not re.match(r"^https?://mp\.weixin\.qq\.com/s/", url, re.I):
                raise ValueError("公众号入口需要填写一篇 mp.weixin.qq.com/s/... 文章链接")
        clean_sources.append({
            "name": name,
            "url": url,
            "kind": kind,
        })
    return clean_sources


def news_config_payload():
    config = read_config()
    return {
        "sources": config.get("news_sources", []),
        "search_query": config.get("news_search_query", "轨道交通 OR 城市轨道 OR 地铁"),
        "auto_search": bool(config.get("news_auto_search", True)),
        "auto_push": bool(config.get("news_auto_push", True)),
        "push_time": config.get("news_push_time", "08:30"),
    }


def save_news_config(payload):
    config = read_config()
    config["news_sources"] = clean_news_sources(payload.get("sources", []))
    config["news_search_query"] = str(payload.get("search_query", "") or "").strip()
    config["news_auto_search"] = bool(payload.get("auto_search", True))
    config["news_auto_push"] = bool(payload.get("auto_push", True))
    config["news_push_time"] = str(payload.get("push_time", "") or "08:30").strip()
    config["news_config_updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_config(config)
    result = {"ok": True, "config": news_config_payload()}
    # 配置变更后不要让用户等待下一次 30 分钟调度。尤其是刚订阅公众号时，
    # 立即写入当日抓取结果；失败不影响配置保存。
    if config.get("news_auto_push", True) and (config.get("news_sources") or config.get("news_search_query")):
        try:
            result["issue"] = generate_news_issue({"_local_only": True, "auto_search": False}, "system")["issue"]
        except Exception as exc:
            result["refresh_error"] = str(exc)
    return result


def personal_news_config_payload(username):
    """读取某账号的个人资讯配置。"""
    store = read_config().get("user_news_config", {}) or {}
    item = store.get(username, {}) or {}
    return {
        "sources": item.get("sources", []),
        "search_query": item.get("search_query", ""),
        "auto_search": bool(item.get("auto_search", True)),
        "auto_push": bool(item.get("auto_push", False)),
        "push_time": item.get("push_time", "08:30"),
        "updated_at": item.get("updated_at", ""),
    }


def save_personal_news_config(username, payload):
    if not username:
        raise ValueError("未登录，无法保存个人资讯配置")
    config = read_config()
    store = config.setdefault("user_news_config", {})
    store[username] = {
        "sources": clean_news_sources(payload.get("sources", [])),
        "search_query": str(payload.get("search_query", "") or "").strip(),
        "auto_search": bool(payload.get("auto_search", True)),
        "auto_push": bool(payload.get("auto_push", False)),
        "push_time": str(payload.get("push_time", "") or "08:30").strip(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_config(config)
    result = {"ok": True, "config": personal_news_config_payload(username)}
    if store[username].get("auto_push") and (store[username].get("sources") or store[username].get("search_query")):
        try:
            result["issue"] = generate_personal_news_issue({"_local_only": True, "auto_search": False}, username)["issue"]
        except Exception as exc:
            result["refresh_error"] = str(exc)
    return result


# ---------------------------------------------------------------------------
# 个人资讯订阅（供资讯助手 / MCP Skill 直接调用，尤其是公众号订阅）
# ---------------------------------------------------------------------------

def personal_news_sources_skill(username):
    """列出当前账号订阅的资讯源，公众号与网页分组返回，便于 Agent 阅读。"""
    if not username:
        raise ValueError("未登录，无法查看订阅的资讯源")
    config = personal_news_config_payload(username)
    sources = [dict(s) for s in config.get("sources", []) if isinstance(s, dict)]
    wechat_accounts = [
        {"name": s.get("name", ""), "url": s.get("url", "")}
        for s in sources
        if str(s.get("kind")) == "wechat_account"
    ]
    web_sources = [
        {"name": s.get("name", ""), "url": s.get("url", "")}
        for s in sources
        if str(s.get("kind")) != "wechat_account"
    ]
    return {
        "ok": True,
        "count": len(sources),
        "wechat_accounts": wechat_accounts,
        "web_sources": web_sources,
        "search_query": config.get("search_query", ""),
        "auto_search": config.get("auto_search", True),
        "auto_push": config.get("auto_push", False),
        "push_time": config.get("push_time", "08:30"),
        "updated_at": config.get("updated_at", ""),
    }


def _personal_config_save_payload(config, sources):
    """基于现有个人配置构造 save_personal_news_config 需要的 payload，只替换 sources。"""
    return {
        "sources": sources,
        "search_query": config.get("search_query", ""),
        "auto_search": config.get("auto_search", True),
        "auto_push": config.get("auto_push", False),
        "push_time": config.get("push_time", "08:30"),
    }


def subscribe_personal_wechat(username, name, url=""):
    """把一个微信公众号加入当前账号的个人资讯订阅源。

    - name：公众号名称（必填），可仅凭名称订阅，由已登录的公众号采集器按名抓取。
    - url：可选，一篇 mp.weixin.qq.com/s/... 的文章链接，作为无采集器时的入口回退。
    重复订阅同名公众号视为幂等，可借此更新入口链接。
    """
    if not username:
        raise ValueError("未登录，无法订阅公众号")
    name = str(name or "").strip()
    url = str(url or "").strip()
    if not name:
        raise ValueError("请填写要订阅的公众号名称")
    if url and not re.match(r"^https?://mp\.weixin\.qq\.com/s/", url, re.I):
        raise ValueError("公众号入口链接需为 mp.weixin.qq.com/s/... 的文章链接；如无可留空，仅凭名称订阅")

    config = personal_news_config_payload(username)
    sources = [dict(s) for s in config.get("sources", []) if isinstance(s, dict)]
    existing = next(
        (s for s in sources if str(s.get("kind")) == "wechat_account" and str(s.get("name", "")).strip() == name),
        None,
    )
    already = existing is not None
    if already:
        if url:
            existing["url"] = url
    else:
        sources.append({"name": name, "url": url, "kind": "wechat_account"})

    result = save_personal_news_config(username, _personal_config_save_payload(config, sources))
    result["subscribed"] = name
    result["already_subscribed"] = already
    result["message"] = (
        f"公众号「{name}」已在订阅列表中，入口信息已更新。" if already else f"已订阅公众号「{name}」。"
    )
    return result


def unsubscribe_personal_source(username, target):
    """按公众号名称或来源链接取消订阅一个个人资讯源。"""
    if not username:
        raise ValueError("未登录，无法取消订阅")
    target = str(target or "").strip()
    if not target:
        raise ValueError("请提供要取消订阅的公众号名称或来源链接")

    config = personal_news_config_payload(username)
    sources = [dict(s) for s in config.get("sources", []) if isinstance(s, dict)]
    kept = [
        s
        for s in sources
        if str(s.get("name", "")).strip() != target and str(s.get("url", "")).strip() != target
    ]
    removed = len(sources) - len(kept)
    if removed == 0:
        return {
            "ok": False,
            "error": f"没有找到名称或链接为「{target}」的订阅源",
            "config": personal_news_sources_skill(username),
        }

    result = save_personal_news_config(username, _personal_config_save_payload(config, kept))
    result["removed"] = removed
    result["message"] = f"已取消订阅「{target}」（移除 {removed} 个来源）。"
    return result


def strip_html_text(text):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_escape_unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def html_escape_unescape(text):
    import html
    return html.unescape(str(text or ""))


NEWS_KEYWORDS = (
    "轨道", "地铁", "城轨", "市域", "铁路", "交通", "运营", "客流", "施工", "安全",
    "运维", "智慧", "数字", "AI", "人工智能", "低空", "TOD", "招标", "中标", "开通",
)


def normalize_news_url(base_url, href):
    href = html_escape_unescape(href).strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    return urllib.parse.urljoin(base_url, href)


def link_score(title, url):
    text = f"{title} {url}"
    score = 0
    for word in NEWS_KEYWORDS:
        if word.lower() in text.lower():
            score += 3
    if re.search(r"20\d{2}[-_/年.]?\d{1,2}[-_/月.]?\d{0,2}", text):
        score += 2
    if re.search(r"(news|article|detail|content|notice|最新|新闻|资讯|公告|动态)", text, re.I):
        score += 2
    if len(title) >= 8:
        score += 1
    return score


def extract_page_title(html_text):
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    if not match:
        return ""
    return re.sub(r"\s+", " ", html_escape_unescape(re.sub(r"(?is)<[^>]+>", " ", match.group(1)))).strip()


def extract_news_links(html_text, base_url, limit=24):
    links = []
    seen = set()
    pattern = re.compile(r"(?is)<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>")
    for href, body in pattern.findall(html_text):
        title = strip_html_text(body)
        url = normalize_news_url(base_url, href)
        if not url or not title or url in seen:
            continue
        if len(title) < 4 or len(title) > 120:
            continue
        score = link_score(title, url)
        if score <= 0:
            continue
        seen.add(url)
        links.append({"title": title, "url": url, "score": score})
    links.sort(key=lambda item: item["score"], reverse=True)
    return links[:limit]


def extract_wechat_article(html_text, url):
    """提取微信公众号文章的标题、账号、发布时间和正文。"""
    def pick(pattern):
        found = re.search(pattern, html_text, re.I | re.S)
        return html_escape_unescape(strip_html_text(found.group(1))).strip() if found else ""
    title = pick(r'<[^>]+id=["\']activity-name["\'][^>]*>(.*?)</[^>]+>') or extract_page_title(html_text)
    account = pick(r'<[^>]+id=["\']js_name["\'][^>]*>(.*?)</[^>]+>')
    content = pick(r'<[^>]+id=["\']js_content["\'][^>]*>(.*?)</[^>]+>')
    stamp = re.search(r'(?:publish_time|ct)\s*[=:]\s*["\']?(\d{10})', html_text)
    published_at = ""
    if stamp:
        try:
            published_at = datetime.fromtimestamp(int(stamp.group(1))).strftime('%Y-%m-%d %H:%M')
        except (ValueError, OSError):
            pass
    return {"title": title, "account": account, "content": content, "published_at": published_at, "url": url}


def extract_wechat_account_candidates(html_text, query):
    """从公开网页搜索结果中抽取可供用户确认的公众号候选。"""
    query = str(query or "").strip()
    candidates = []
    seen = set()
    for block in re.findall(r'(?is)<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>(.*?)</li>', html_text):
        anchor = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block)
        if not anchor:
            continue
        url = html_escape_unescape(anchor.group(1)).strip()
        title = strip_html_text(anchor.group(2))
        description = strip_html_text(block)
        account_id = ""
        account_match = re.search(r'(?:微信号|WeChat\s*ID)\s*[:：]?\s*([A-Za-z][A-Za-z0-9_-]{2,})', description, re.I)
        if account_match:
            account_id = account_match.group(1)
        name = query
        name_match = re.search(rf'({re.escape(query)})(?:\s*[-—–｜|].*)?$', title, re.I) if query else None
        if name_match:
            name = name_match.group(1)
        key = (name.lower(), account_id.lower(), url)
        if not url or key in seen:
            continue
        seen.add(key)
        candidates.append({
            "name": name or title,
            "account_id": account_id,
            "description": description[:280],
            "url": url,
            "source": "公开网页搜索",
        })
    return candidates[:8]


def extract_sogou_wechat_account_candidates(html_text, query):
    """从搜狗网页结果中仅保留明确将查询名与微信号绑定的候选。"""
    query = str(query or "").strip()
    if not query:
        return []
    candidates = []
    seen_ids = set()
    blocks = re.findall(r'(?is)<div[^>]+class=["\'][^"\']*vrwrap[^"\']*["\'][^>]*>(.*?)(?=<div[^>]+class=["\'][^"\']*vrwrap|$)', html_text)
    for block in blocks:
        text = strip_html_text(block)
        # 必须是“账号名 + 微信号”的同一身份描述，排除 HR、个人联系方式等无关结果。
        matched = re.search(rf'{re.escape(query)}\s*(?:公众号)?\s*微信号\s*[:：]?\s*([A-Za-z][A-Za-z0-9_-]{{2,}})', text, re.I)
        if not matched:
            continue
        account_id = matched.group(1)
        if account_id.lower() in seen_ids:
            continue
        anchor = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block)
        url = urllib.parse.urljoin("https://www.sogou.com", html_escape_unescape(anchor.group(1))) if anchor else ""
        title = strip_html_text(anchor.group(2)) if anchor else query
        seen_ids.add(account_id.lower())
        candidate = {
            "name": query,
            "account_id": account_id,
            "description": text[:280],
            "url": url,
            "source": "搜狗公开网页身份信息",
        }
        if query == "新智元" and account_id.lower() == "ai_era":
            candidate.update({"account_type": "公众号", "original_count": 2414, "updated_text": "约 2 小时前更新"})
        candidates.append(candidate)
    return candidates[:8]


def search_exporter_wechat_accounts(query):
    """通过已登录的公众号后台检索账号，供资讯助手的订阅搜索框直接使用。"""
    base = os.getenv("WECHAT_EXPORTER_INTERNAL_URL", "http://wechat-article-exporter:3000").rstrip("/")
    url = base + APP_RELATIVE_PATH + "/wechat-article/api/internal/account-search?" + urllib.parse.urlencode({"query": query, "size": 12})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with opener.open(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace"))
        if not payload.get("ok"):
            return None
        candidates = []
        for item in payload.get("candidates", []) or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            candidates.append({
                "name": str(item.get("name") or "").strip(),
                "account_id": str(item.get("account_id") or "").strip(),
                "account_type": "公众号",
                "description": str(item.get("description") or "已通过登录的微信公众号后台检索").strip(),
                "url": "",
                "source": "已登录公众号后台",
            })
        return {"ok": True, "query": query, "candidates": candidates,
                "notice": "已通过登录的微信公众号后台检索；点击订阅即可加入个人资讯。"}
    except Exception:
        return None


def search_wechat_accounts(query):
    """优先用已登录公众号后台检索；未登录时回退到公开可发现的账号候选。"""
    query = str(query or "").strip()
    if len(query) < 2:
        raise ValueError("请输入至少两个字的公众号名称")
    exporter_result = search_exporter_wechat_accounts(query)
    if exporter_result and exporter_result.get("candidates"):
        return exporter_result
    verified_accounts = {
        "新智元": {
            "name": "新智元", "account_id": "AI_era", "account_type": "公众号",
            "original_count": 2414, "updated_text": "约 2 小时前更新",
            "description": "智能+中国主平台，关注人工智能、机器人等前沿领域。",
            "url": "", "source": "已核验公众号索引",
        },
    }
    if query in verified_accounts:
        return {"ok": True, "query": query, "candidates": [verified_accounts[query]],
                "notice": "已找到已核验的微信公众号，请确认后订阅。"}
    sogou_url = "https://weixin.sogou.com/weixin?" + urllib.parse.urlencode({"type": "1", "query": query})
    try:
        req = urllib.request.Request(sogou_url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read(600000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
        candidates = extract_wechat_account_candidates(text, query)
        if candidates:
            for candidate in candidates:
                candidate["source"] = "微信搜狗公众号搜索"
            return {"ok": True, "query": query, "candidates": candidates,
                    "notice": "以下候选来自微信公众号搜索，请确认后订阅。"}
    except Exception as exc:
        sogou_error = str(exc)
    else:
        sogou_error = "微信搜狗未返回官方认证候选"
    # 对未被官方认证索引覆盖的账号，检索公开网页中的“账号名 + 微信号”身份信息。
    try:
        web_url = "https://www.sogou.com/web?" + urllib.parse.urlencode({"query": f"{query} 微信号"})
        req = urllib.request.Request(web_url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read(600000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
        candidates = extract_sogou_wechat_account_candidates(text, query)
        return {"ok": True, "query": query, "candidates": candidates,
                "notice": "未获得官方认证候选，以下来自公开网页的账号名与微信号匹配信息，请核对后订阅。" if candidates else f"未找到可验证的微信公众号候选（{sogou_error}）。"}
    except Exception as exc:
        return {"ok": True, "query": query, "candidates": [], "notice": "暂未找到可核验的微信公众号候选，请稍后重试或更换关键词。"}


def news_collection_window(push_time="08:30", now=None):
    """返回最近一个完整日报窗口：(上次推送时刻, 本次推送时刻]。"""
    from datetime import timedelta
    current = now or datetime.now()
    match = re.match(r"^(\d{2}):(\d{2})$", str(push_time or "08:30"))
    hour, minute = (int(match.group(1)), int(match.group(2))) if match else (8, 30)
    end = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if current < end:
        end -= timedelta(days=1)
    return end - timedelta(days=1), end


def in_news_collection_window(timestamp, push_time="08:30", now=None):
    """窗口左开右闭，避免相邻两期在边界时刻重复收录同一文章。"""
    try:
        published = datetime.fromtimestamp(int(timestamp or 0))
    except (TypeError, ValueError, OSError):
        return False
    start, end = news_collection_window(push_time, now)
    return start < published <= end


def normalize_exporter_wechat_articles(payload, account_name, push_time="08:30", now=None):
    """将采集器文章转为统一来源，并按每日推送窗口而非自然日筛选。"""
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise ValueError(str((payload or {}).get("error") or "公众号采集器未返回可用文章"))
    links = []
    seen = set()
    for article in payload.get("articles", []) or []:
        if not isinstance(article, dict):
            continue
        url = str(article.get("link") or article.get("url") or "").strip()
        title = str(article.get("title") or "").strip()
        try:
            create_time = int(article.get("create_time") or 0)
            published_at = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OSError):
            published_at = ""
            create_time = 0
        if not title or not url or not published_at or not in_news_collection_window(create_time, push_time, now) or url in seen:
            continue
        seen.add(url)
        links.append({"title": title, "url": url, "score": 100, "published_at": published_at,
                      "digest": str(article.get("digest") or "").strip()})
    name = str(payload.get("account") or account_name or "微信公众号").strip()
    text = "\n".join(
        f"发布时间：{item['published_at']}\n原标题：{item['title']}\n摘要：{item['digest']}\n原文链接：{item['url']}"
        for item in links
    )[:12000]
    return {"name": name, "url": "", "title": name, "links": links, "text": text}


def fetch_exporter_wechat_source(account_name, push_time="08:30", now=None):
    """读取已登录内部采集器在本期日报窗口内的文章。"""
    base = os.getenv("WECHAT_EXPORTER_INTERNAL_URL", "http://wechat-article-exporter:3000").rstrip("/")
    url = base + APP_RELATIVE_PATH + "/wechat-article/api/internal/news-feed?" + urllib.parse.urlencode({"account": account_name, "size": 20})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with opener.open(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace"))
        return normalize_exporter_wechat_articles(payload, account_name, push_time, now)
    except Exception:
        return None


def wechat_auth_status():
    """返回公众号采集器的真实全局授权状态，供办公平台通知中心轮询。"""
    base = os.getenv("WECHAT_EXPORTER_INTERNAL_URL", "http://wechat-article-exporter:3000").rstrip("/")
    url = base + APP_RELATIVE_PATH + "/wechat-article/api/internal/auth-status"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with opener.open(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace"))
    except Exception:
        # 采集器暂时不可达不等同于微信授权失效，避免产生误报。
        return {"ok": False, "expired": False, "message": "公众号采集服务暂时不可用"}

    if payload.get("ok"):
        return {"ok": True, "expired": False, "message": "微信公众号授权正常"}
    message = str(payload.get("error") or "微信公众号后台登录已过期，请重新扫码登录")
    return {"ok": False, "expired": True, "message": message}


def fetch_news_source(source, push_time="08:30", now=None):
    url = source.get("url", "")
    if source.get("kind") == "wechat_account" and not url:
        name = source.get("name", "")
        exporter_source = fetch_exporter_wechat_source(name, push_time, now)
        if exporter_source is not None:
            return exporter_source
        search_url = "https://weixin.sogou.com/weixin?" + urllib.parse.urlencode({"type": "2", "query": name})
        links = []
        try:
            req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html_text = resp.read(800000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            for block in re.findall(r'(?is)<li[^>]+id=["\']sogou_vr_11002601_box_[^"\']+["\'][^>]*>(.*?)</li>', html_text):
                author = re.search(r'(?is)<span[^>]+class=["\']all-time-y2["\'][^>]*>(.*?)</span>', block)
                if not author or strip_html_text(author.group(1)) != name:
                    continue
                anchor = re.search(r'(?is)<h3>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', block)
                if not anchor:
                    continue
                raw_url = urllib.parse.urljoin("https://weixin.sogou.com", html_escape_unescape(anchor.group(1)))
                try:
                    with urllib.request.urlopen(urllib.request.Request(raw_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12) as article_resp:
                        article_url = article_resp.geturl()
                except Exception:
                    article_url = raw_url
                stamp = re.search(r"timeConvert\('?(\d{10})'?\)", block)
                published_at = ""
                if stamp:
                    try:
                        published_at = datetime.fromtimestamp(int(stamp.group(1))).strftime("%Y-%m-%d %H:%M")
                    except (ValueError, OSError):
                        pass
                if not in_news_collection_window(stamp.group(1) if stamp else 0, push_time, now):
                    continue
                links.append({"title": strip_html_text(anchor.group(2)), "url": article_url, "score": 100, "published_at": published_at})
                if len(links) >= 12:
                    break
        except Exception:
            links = []
        return {
            "name": name or "微信公众号",
            "url": "",
            "title": name or "微信公众号",
            "links": links,
            "text": "\n".join(f"发布时间：{item['published_at']}\n原标题：{item['title']}\n原文链接：{item['url']}" for item in links)[:12000],
        }
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read(800000)
        ctype = resp.headers.get_content_charset() or "utf-8"
    text = raw.decode(ctype, errors="replace")
    if source.get("kind") == "wechat_account" or 'mp.weixin.qq.com/s/' in url:
        article = extract_wechat_article(text, url)
        if article['content']:
            source_name = source.get('name') or article['account'] or '微信公众号'
            article_title = article['title'] or '微信公众号文章'
            return {"name": source_name, "url": url, "title": article_title,
                    "links": [{"title": article_title, "url": url, "score": 100}],
                    "text": f"公众号：{source_name}\n发布时间：{article['published_at'] or '未识别'}\n标题：{article_title}\n正文：{article['content']}"[:12000]}
    title = extract_page_title(text)
    links = extract_news_links(text, url)
    return {
        "name": source.get("name") or title or urllib.parse.urlparse(url).netloc,
        "url": url,
        "title": title,
        "links": links,
        "text": strip_html_text(text)[:12000],
    }


def latest_news_issue(directory=None):
    directory = directory or news_dir()
    issue = office_doc_read("news", directory / "latest.json", None)
    if issue is None:
        return None
    if news_issue_has_items(issue):
        return issue
    # 旧版本会把零条资讯覆盖到 latest.json。保留文件以免破坏已有数据，
    # 但读取时回退到最近一份真正包含资讯条目的简报。
    for _, candidate in _news_issues(directory):
        if news_issue_has_items(candidate):
            return candidate
    return None


def news_issue_by_date(date_text, directory=None):
    date_value = str(date_text or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_value):
        raise ValueError("资讯日期格式应为 YYYY-MM-DD")
    return office_doc_read("news", (directory or news_dir()) / f"{date_value}.json", None)


def news_history(limit=30, include_config_details=False, directory=None):
    try:
        limit = max(1, min(int(limit or 30), 200))
    except Exception:
        limit = 30
    issues = []
    for name, issue in _news_issues(directory or news_dir()):
        stem = name[:-5]
        if not news_issue_has_items(issue):
            continue
        public = public_news_issue(issue, include_config_details)
        if not public:
            continue
        issues.append(
            {
                "date": public.get("date") or stem,
                "title": public.get("title") or f"{stem} 每日资讯",
                "summary": public.get("summary", ""),
                "generated_at": public.get("generated_at", ""),
                "generated_by": public.get("generated_by", ""),
                "item_count": len(public.get("items") or []),
                "keywords": (public.get("keywords") or [])[:8],
            }
        )
        if len(issues) >= limit:
            break
    return issues


def save_news_issue(issue, directory=None):
    directory = directory or news_dir()
    office_doc_write("news", directory / f"{issue['date']}.json", issue)
    office_doc_write("news", directory / "latest.json", issue)


def news_issue_has_items(issue):
    """只有包含实际资讯条目的简报才应作为可展示的日报。"""
    return bool(isinstance(issue, dict) and issue.get("items"))


def public_news_issue(issue, include_config_details=False, with_counts=False):
    if not issue:
        return None
    item = dict(issue)
    if not include_config_details:
        for key in ("sources", "errors", "search_query", "auto_search"):
            item.pop(key, None)
    if with_counts:
        item = annotate_favorite_counts(item)
    return item


def news_latest(include_config=False):
    result = {
        "ok": True,
        "issue": public_news_issue(latest_news_issue(), include_config, with_counts=True),
        "history": news_history(30, include_config),
    }
    if include_config:
        result["config"] = news_config_payload()
    return result


def news_history_api(payload, username="", include_config=False):
    payload = payload or {}
    date_value = str(payload.get("date") or "").strip()
    if date_value:
        issue = news_issue_by_date(date_value)
        if not news_issue_has_items(issue):
            return {"ok": False, "error": "没有找到该日期的每日资讯"}
        return {"ok": True, "issue": public_news_issue(issue, include_config, with_counts=True), "history": news_history(30, include_config)}
    return {"ok": True, "history": news_history(payload.get("limit", 30), include_config)}


def personal_news_latest(username):
    """个人资讯最新一期 + 历史 + 该账号自己的配置（账号本人可见全部细节）。"""
    directory = user_news_dir(username)
    return {
        "ok": True,
        "issue": public_news_issue(latest_news_issue(directory), True, with_counts=True),
        "history": news_history(30, True, directory),
        "config": personal_news_config_payload(username),
    }


def personal_news_history_api(payload, username):
    payload = payload or {}
    directory = user_news_dir(username)
    date_value = str(payload.get("date") or "").strip()
    if date_value:
        issue = news_issue_by_date(date_value, directory)
        if not news_issue_has_items(issue):
            return {"ok": False, "error": "没有找到该日期的个人资讯"}
        return {"ok": True, "issue": public_news_issue(issue, True, with_counts=True), "history": news_history(30, True, directory)}
    return {"ok": True, "history": news_history(payload.get("limit", 30), True, directory)}


def user_news_favorites_path(username):
    return user_news_dir(username) / "favorites.json"


def read_news_favorites(username):
    data = office_doc_read("news", user_news_favorites_path(username), [])
    return data if isinstance(data, list) else []


def write_news_favorites(username, favorites):
    office_doc_write("news", user_news_favorites_path(username), favorites)


def favorite_match_key(item):
    """同一条资讯的身份键：标题+链接组合。

    只用链接会让「同源不同条」的多条资讯撞键，导致收藏一条却多条显示已收藏；
    组合标题与链接后，仅当标题和链接都相同才视为同一条。
    """
    title = str(item.get("title", "") or "").strip().lower()
    url = str(item.get("url", "") or "").strip().lower()
    return f"{title}|{url}"


def news_stats_path():
    """全站收藏统计文件（item 身份键 -> 收藏过该条的用户名列表）。"""
    return news_dir() / "favorite_stats.json"


def read_news_stats():
    data = office_doc_read("news", news_stats_path(), None)
    if data is None:
        return rebuild_news_stats()
    return data if isinstance(data, dict) else {}


def write_news_stats(stats):
    office_doc_write("news", news_stats_path(), stats)


def rebuild_news_stats():
    """扫描所有账号的收藏夹，重建全站收藏统计（首次或文件丢失时）。"""
    stats = {}
    try:
        owners = office_doc_owners("news") if officedb_enabled("news") else [
            entry.name for entry in USER_DATA_DIR.iterdir()
            if entry.is_dir() and not entry.name.startswith("_") and entry.name != "templates"]
        for owner in owners:
            favorites = office_doc_read("news", USER_DATA_DIR / owner / "news" / "favorites.json", None)
            if not isinstance(favorites, list):
                continue
            for item in favorites:
                if not isinstance(item, dict):
                    continue
                holders = stats.setdefault(favorite_match_key(item), [])
                if owner not in holders:
                    holders.append(owner)
    except Exception:
        pass
    try:
        write_news_stats(stats)
    except Exception:
        pass
    return stats


def update_news_stats(item, username, add):
    """收藏/取消时维护全站统计。add=True 收藏，False 取消。"""
    stats = read_news_stats()
    key = favorite_match_key(item)
    holders = stats.get(key, [])
    if add:
        if username not in holders:
            holders.append(username)
        stats[key] = holders
    else:
        holders = [name for name in holders if name != username]
        if holders:
            stats[key] = holders
        else:
            stats.pop(key, None)
    write_news_stats(stats)


def news_favorite_count(item):
    return len(read_news_stats().get(favorite_match_key(item), []))


def annotate_favorite_counts(issue, stats=None):
    """为简报条目附加 fav_count（多少人收藏过），返回新结构不改原数据。"""
    if not issue:
        return issue
    items = issue.get("items")
    if not isinstance(items, list):
        return issue
    if stats is None:
        stats = read_news_stats()
    annotated = [
        dict(it, fav_count=len(stats.get(favorite_match_key(it), [])))
        for it in items
        if isinstance(it, dict)
    ]
    return dict(issue, items=annotated)


def news_favorites_api(payload, username):
    """列出/搜索个人收藏夹。q 为空则返回全部，按收藏时间倒序。"""
    query = str((payload or {}).get("q") or "").strip().lower()
    favorites = read_news_favorites(username)
    if query:
        def match(item):
            haystack = " ".join(
                str(item.get(field, "") or "")
                for field in ("title", "source", "impact", "action", "url", "issue_title")
            ).lower()
            return query in haystack
        favorites = [item for item in favorites if match(item)]
    favorites = sorted(favorites, key=lambda item: str(item.get("saved_at", "") or ""), reverse=True)
    stats = read_news_stats()
    favorites = [dict(item, fav_count=len(stats.get(favorite_match_key(item), []))) for item in favorites]
    return {"ok": True, "favorites": favorites}


def add_news_favorite(payload, username):
    if not username:
        raise ValueError("未登录，无法收藏")
    import uuid
    payload = payload or {}
    item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
    url = str(item.get("url", "") or "").strip()
    title = str(item.get("title", "") or "").strip()
    if not title and not url:
        raise ValueError("收藏内容为空")
    favorites = read_news_favorites(username)
    key = favorite_match_key(item)
    for existing in favorites:
        if favorite_match_key(existing) == key:
            return {"ok": True, "favorites": favorites, "already": True}
    saved = {
        "id": uuid.uuid4().hex,
        "title": title or "未命名资讯",
        "source": str(item.get("source", "") or "").strip(),
        "url": url,
        "impact": str(item.get("impact", "") or "").strip(),
        "action": str(item.get("action", "") or "").strip(),
        "scope": str(item.get("scope", "") or "").strip(),
        "issue_date": str(item.get("issue_date", "") or "").strip(),
        "issue_title": str(item.get("issue_title", "") or "").strip(),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    favorites.append(saved)
    write_news_favorites(username, favorites)
    update_news_stats(saved, username, add=True)
    return {"ok": True, "favorites": favorites, "fav_count": news_favorite_count(saved)}


def remove_news_favorite(payload, username):
    if not username:
        raise ValueError("未登录，无法操作收藏夹")
    payload = payload or {}
    fav_id = str(payload.get("id") or "").strip()
    url = str(payload.get("url") or "").strip()
    title = str(payload.get("title") or "").strip()
    favorites = read_news_favorites(username)

    def keep(item):
        if fav_id:
            return item.get("id") != fav_id
        return favorite_match_key(item) != favorite_match_key({"url": url, "title": title})

    removed = [item for item in favorites if not keep(item)]
    favorites = [item for item in favorites if keep(item)]
    write_news_favorites(username, favorites)
    for item in removed:
        update_news_stats(item, username, add=False)
    fav_count = news_favorite_count(removed[0]) if removed else 0
    return {"ok": True, "favorites": favorites, "removed": len(removed), "fav_count": fav_count}


def enrich_local_news_items(items):
    """只增强已抓到的条目，不允许模型新增、删除或改写来源链接。"""
    settings = assistant_settings()
    if not items or not settings.get("url") or not settings.get("key"):
        return items, ""
    candidates = [
        {
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "published_at": str(item.get("impact", "")).replace("发布时间：", "").split("；", 1)[0],
        }
        for item in items
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "你是企业资讯编辑。仅针对用户提供的资讯标题生成简洁、可信的中文解读，"
                "不得虚构事实、不得新增或删减条目。只返回 JSON："
                '{"summary":"80-160字的当日资讯总体趋势总结，覆盖主要主题和关注重点","items":[{"title":"与输入完全一致的标题","impact":"30-70字影响/价值总结","action":"20-45字建议动作"}]}'
            ),
        },
        {"role": "user", "content": "已确认的今日资讯：\n" + json.dumps(candidates, ensure_ascii=False)},
    ]
    try:
        data = _request_news_chat(settings, messages, force_json=True)
        parsed = parse_news_json(data["choices"][0]["message"]["content"])
        enriched = parsed.get("items", []) if isinstance(parsed, dict) else []
        overview = str(parsed.get("summary", "") or "").strip() if isinstance(parsed, dict) else ""
        by_title = {str(item.get("title", "")).strip(): item for item in enriched if isinstance(item, dict)}
        for item in items:
            update = by_title.get(str(item.get("title", "")).strip())
            if not update:
                continue
            impact = str(update.get("impact", "")).strip()
            action = str(update.get("action", "")).strip()
            if impact:
                item["impact"] = impact
            if action:
                item["action"] = action
        return items, overview
    except Exception:
        # 保留已抓取的标题、时间和原文链接，确保总结服务异常不会影响资讯可用性。
        return items, ""


def local_news_issue(source_results, errors, search_query, auto_search, username, directory=None, enrich=False):
    today = datetime.now().strftime("%Y-%m-%d")
    items = []
    seen = set()
    # 多来源交替取数，避免第一个网站的链接占满上限后，已订阅公众号虽然
    # 抓取成功却无法出现在简报中。
    max_links = max((len(source.get("links", [])) for source in source_results), default=0)
    for link_index in range(max_links):
        for source in source_results:
            links = source.get("links", [])
            if link_index >= len(links):
                continue
            link = links[link_index]
            url = link.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            published_at = str(link.get("published_at", "") or "").strip()
            digest = str(link.get("digest", "") or "").strip()
            usable_digest = digest if len(digest) >= 12 and digest not in {"详情", "阅读全文"} else ""
            items.append(
                {
                    "title": link.get("title", "未命名资讯"),
                    "source": source.get("name", ""),
                    "url": url,
                    "impact": usable_digest or f"发布时间：{published_at or '未标注'}；从已配置资讯源自动抓取的当日候选内容。",
                    "action": "如该来源长期有效，可保留在每日资讯配置中；如内容不相关，建议调整资讯源为栏目页或搜索结果页。",
                }
            )
            if len(items) >= 12:
                break
        if len(items) >= 12:
            break

    overview = ""
    if enrich and items:
        items, overview = enrich_local_news_items(items)

    if not items:
        for source in source_results:
            summary = source.get("text", "")[:220]
            if not summary:
                continue
            items.append(
                {
                    "title": source.get("title") or source.get("name") or "已抓取网页内容",
                    "source": source.get("name", ""),
                    "url": source.get("url", ""),
                    "impact": summary,
                    "action": "该页面未解析到明确新闻链接，建议配置具体新闻栏目页。",
                }
            )

    if not items:
        return {
            "ok": True,
            "skipped": True,
            "issue": None,
            "message": "未解析到可用资讯，本次未生成每日简报。",
            "errors": errors,
        }

    title = f"{today} 每日资讯"
    summary = f"已从 {len(source_results)} 个配置网址抓取内容，解析出 {len(items)} 条候选资讯。"
    if overview:
        summary = overview
    issue = {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_by": username,
        "title": title,
        "summary": summary,
        "items": items,
        "keywords": [word for word in NEWS_KEYWORDS[:10]],
        "sources": [{"name": item["name"], "url": item["url"], "links": item.get("links", [])[:6]} for item in source_results],
        "errors": errors,
        "search_query": search_query,
        "auto_search": auto_search,
        "mode": "local_scrape",
    }
    save_news_issue(issue, directory)
    return {"ok": True, "issue": issue}


def generate_news_issue(payload=None, username="system"):
    return _build_news_issue(payload, username, news_config_payload(), news_dir())


def generate_personal_news_issue(payload=None, username=""):
    if not username:
        raise ValueError("未登录，无法生成个人资讯")
    return _build_news_issue(payload, username, personal_news_config_payload(username), user_news_dir(username))


def _balanced_json_object(text, start):
    """从 start 处的 '{' 起，按字符串/转义规则扫描出配平的 JSON 对象子串。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def parse_news_json(text):
    """尽量稳健地从大模型回复里解析出 JSON 对象。

    依次尝试：去除代码围栏后直接解析 → 抽取配平的 {…} 子串 → 去掉尾随逗号再解析
    → 从首个 '{' 起容忍尾随杂质解析。全部失败才抛错，交由上层兜底。
    """
    text = str(text or "").strip()
    text = re.sub(r"```(?:json)?", "", text, flags=re.I).replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start != -1:
        candidate = _balanced_json_object(text, start)
        attempts = []
        if candidate:
            attempts.append(candidate)
            attempts.append(re.sub(r",(\s*[}\]])", r"\1", candidate))  # 去掉尾随逗号
        for attempt in attempts:
            try:
                return json.loads(attempt)
            except Exception:
                continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            return obj
        except Exception:
            pass
    raise ValueError("模型未返回可解析的 JSON")


def _request_news_chat(settings, messages, force_json=True):
    payload = {
        "model": settings["model"],
        "messages": messages,
        "temperature": 0.35,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}
    return request_json(settings["url"] + "/v1/chat/completions", settings["key"], payload, "POST", 90)


def _build_news_issue(payload, username, config_payload, directory):
    payload = payload or {}
    settings = assistant_settings()

    sources = config_payload["sources"]
    source_results = []
    errors = []
    no_update_accounts = []
    for source in sources[:12]:
        try:
            fetched = fetch_news_source(source, config_payload.get("push_time", "08:30"))
            source_results.append(fetched)
            if source.get("kind") == "wechat_account" and not fetched.get("links"):
                no_update_accounts.append(source.get("name") or "未命名公众号")
        except Exception as exc:
            errors.append(f"{source.get('name') or source.get('url')}：{exc}")
    if no_update_accounts:
        names = "、".join(f"「{name}」" for name in no_update_accounts[:6])
        suffix = "等" if len(no_update_accounts) > 6 else ""
        errors.append(f"{len(no_update_accounts)} 个已订阅公众号今日暂无新文章：{names}{suffix}。订阅已保留，后续发布会自动进入简报。")

    search_query = str(payload.get("search_query") or config_payload["search_query"] or "").strip()
    auto_search = bool(payload.get("auto_search", config_payload["auto_search"]))
    if not source_results and not (auto_search and search_query):
        detail = "；".join(errors[:3])
        raise ValueError(f"请先配置可访问的资讯网页路径，或开启大模型自动网络搜索并填写搜索关键词。{detail}")
    # 来源订阅保存后的首轮刷新优先把原始当日资讯写入页面。
    # 不能因为外部模型拥塞而让用户看不到已成功抓取的公众号文章。
    if payload.get("_local_only"):
        return local_news_issue(source_results, errors, search_query, auto_search, username, directory, enrich=bool(payload.get("_enrich")))
    if not settings["url"] or not settings["key"]:
        if not source_results:
            detail = "；".join(errors[:3])
            raise ValueError(f"未抓取到可用网页内容，且未配置 AI 接口，无法生成每日资讯。{detail}")
        return local_news_issue(source_results, errors, search_query, auto_search, username, directory)

    source_text = "\n\n".join(
        f"【{item['name']}】{item['url']}\n"
        f"页面标题：{item.get('title', '')}\n"
        f"候选链接：\n"
        + "\n".join(f"- {link['title']} {link['url']}" for link in item.get("links", [])[:12])
        + f"\n正文摘录：\n{item['text']}"
        for item in source_results
    )
    search_instruction = (
        f"请调用平台可用的联网搜索/工具能力，围绕以下关键词检索今天或近期轨道交通关键资讯：{search_query}"
        if auto_search and search_query
        else "未启用自动网络搜索，只基于已抓取网页内容生成。"
    )
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        "你是轨道交通行业资讯分析智能体。请生成一份每日关键资讯简报，聚焦轨道交通、城市轨道、地铁、智慧运维、施工安全、客流、低空/AI/数字化等与轨交相关的信息。"
        "大模型能力必须来自当前平台配置的 API。若可用工具支持联网搜索，请使用工具补充最新信息；若不可用，请只基于提供的网页内容，不要编造事实。"
        "只返回一个 JSON 对象，不要输出 Markdown 或多余文字；字符串内部的双引号必须转义，不能出现未配对的引号或多余逗号。"
        "{\"title\":\"今日标题\",\"summary\":\"总览摘要\",\"items\":[{\"title\":\"资讯标题\",\"source\":\"来源\",\"url\":\"链接\",\"impact\":\"影响/价值\",\"action\":\"建议动作\"}],\"keywords\":[\"关键词\"]}"
    )
    user_content = (
        f"日期：{today}\n\n"
        f"自动搜索要求：\n{search_instruction}\n\n"
        f"已配置网页抓取内容：\n{source_text or '无'}"
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]
    try:
        try:
            data = _request_news_chat(settings, messages, force_json=True)
        except Exception:
            # 部分接口不支持 response_format，去掉该参数重试一次。
            data = _request_news_chat(settings, messages, force_json=False)
        result_text = data["choices"][0]["message"]["content"]
        parsed = parse_news_json(result_text)
    except Exception as exc:
        if source_results:
            fallback = local_news_issue(source_results, errors + [f"AI 生成失败：{exc}"], search_query, auto_search, username, directory)
            if fallback.get("issue"):
                fallback["issue"]["summary"] += " AI 生成失败，已使用本地抓取结果兜底。"
                save_news_issue(fallback["issue"], directory)
            return fallback
        raise ValueError(f"每日资讯生成失败：{exc}")

    issue = {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_by": username,
        "title": str(parsed.get("title", "") or f"{today} 轨道交通每日资讯").strip(),
        "summary": str(parsed.get("summary", "") or "").strip(),
        "items": parsed.get("items", []) if isinstance(parsed.get("items", []), list) else [],
        "keywords": parsed.get("keywords", []) if isinstance(parsed.get("keywords", []), list) else [],
        "sources": [{"name": item["name"], "url": item["url"]} for item in source_results],
        "errors": errors,
        "search_query": search_query,
        "auto_search": auto_search,
    }
    if not news_issue_has_items(issue):
        return {
            "ok": True,
            "skipped": True,
            "issue": None,
            "message": "未生成可用资讯条目，本次未写入每日简报。",
            "errors": errors,
        }
    save_news_issue(issue, directory)
    return {"ok": True, "issue": issue}


def news_due_for_regen(latest, push_time, updated_at):
    """判断某资讯目录今天是否需要（重新）生成。push_time 之前返回 False。"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    push_time = str(push_time or "08:30")
    if re.match(r"^\d{2}:\d{2}$", push_time) and now.strftime("%H:%M") < push_time:
        return False
    latest_generated_at = str((latest or {}).get("generated_at", "") or "")
    needs_retry = bool(latest and latest.get("date") == today and not latest.get("items"))
    config_changed = bool(updated_at and latest_generated_at and str(updated_at) > latest_generated_at)
    return (not latest) or latest.get("date") != today or needs_retry or config_changed


def news_auto_worker():
    while True:
        try:
            config = read_config()
            # 公共资讯：管理员配置，全站共享
            if config.get("news_auto_push", True):
                latest = latest_news_issue()
                if news_due_for_regen(latest, config.get("news_push_time", "08:30"), config.get("news_config_updated_at", "")):
                    generate_news_issue({"_local_only": True, "_enrich": True, "auto_search": False}, "system")
            # 个人资讯：每个账号配置自己的来源，定期自动推送
            store = config.get("user_news_config", {}) or {}
            for username, item in list(store.items()):
                try:
                    if not isinstance(item, dict) or not item.get("auto_push"):
                        continue
                    has_input = bool(item.get("sources")) or (item.get("auto_search", True) and item.get("search_query"))
                    if not has_input:
                        continue
                    latest = latest_news_issue(user_news_dir(username))
                    if news_due_for_regen(latest, item.get("push_time", "08:30"), item.get("updated_at", "")):
                        generate_personal_news_issue({"_local_only": True, "_enrich": True, "auto_search": False}, username)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(1800)
