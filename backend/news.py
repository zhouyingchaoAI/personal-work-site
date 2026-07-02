"""News source configuration, fetching, issue generation, and scheduler.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def news_dir():
    path = USER_DATA_DIR / "_news"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_news_dir(username):
    """每个账号的个人资讯存储目录。"""
    path = user_root(username) / "news"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_news_sources(sources):
    if isinstance(sources, str):
        sources = [{"name": "", "url": line.strip()} for line in sources.splitlines() if line.strip()]
    clean_sources = []
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "") or "").strip()
        if not url:
            continue
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("资讯网页路径必须以 http:// 或 https:// 开头")
        clean_sources.append({
            "name": str(item.get("name", "") or "").strip(),
            "url": url,
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
    return {"ok": True, "config": news_config_payload()}


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
    return {"ok": True, "config": personal_news_config_payload(username)}


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


def fetch_news_source(source):
    url = source.get("url", "")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read(800000)
        ctype = resp.headers.get_content_charset() or "utf-8"
    text = raw.decode(ctype, errors="replace")
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
    path = (directory or news_dir()) / "latest.json"
    if not path.exists():
        return None
    try:
        return read_json_lenient(path)
    except Exception:
        return None


def news_issue_by_date(date_text, directory=None):
    date_value = str(date_text or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_value):
        raise ValueError("资讯日期格式应为 YYYY-MM-DD")
    path = (directory or news_dir()) / f"{date_value}.json"
    if not path.exists():
        return None
    try:
        return read_json_lenient(path)
    except Exception:
        return None


def news_history(limit=30, include_config_details=False, directory=None):
    try:
        limit = max(1, min(int(limit or 30), 200))
    except Exception:
        limit = 30
    issues = []
    for path in sorted((directory or news_dir()).glob("*.json"), reverse=True):
        if path.name == "latest.json":
            continue
        try:
            issue = read_json_lenient(path)
        except Exception:
            continue
        public = public_news_issue(issue, include_config_details)
        if not public:
            continue
        issues.append(
            {
                "date": public.get("date") or path.stem,
                "title": public.get("title") or f"{path.stem} 每日资讯",
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
    issue_path = directory / f"{issue['date']}.json"
    latest_path = directory / "latest.json"
    raw = json.dumps(issue, ensure_ascii=False, indent=2)
    issue_path.write_text(raw, encoding="utf-8")
    latest_path.write_text(raw, encoding="utf-8")


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
        if not issue:
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
        if not issue:
            return {"ok": False, "error": "没有找到该日期的个人资讯"}
        return {"ok": True, "issue": public_news_issue(issue, True, with_counts=True), "history": news_history(30, True, directory)}
    return {"ok": True, "history": news_history(payload.get("limit", 30), True, directory)}


def user_news_favorites_path(username):
    return user_news_dir(username) / "favorites.json"


def read_news_favorites(username):
    path = user_news_favorites_path(username)
    if not path.exists():
        return []
    try:
        data = read_json_lenient(path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_news_favorites(username, favorites):
    user_news_favorites_path(username).write_text(
        json.dumps(favorites, ensure_ascii=False, indent=2), encoding="utf-8"
    )


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
    path = news_stats_path()
    if not path.exists():
        return rebuild_news_stats()
    try:
        data = read_json_lenient(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_news_stats(stats):
    news_stats_path().write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def rebuild_news_stats():
    """扫描所有账号的收藏夹，重建全站收藏统计（首次或文件丢失时）。"""
    stats = {}
    try:
        for entry in USER_DATA_DIR.iterdir():
            if not entry.is_dir() or entry.name.startswith("_") or entry.name == "templates":
                continue
            fav_path = entry / "news" / "favorites.json"
            if not fav_path.exists():
                continue
            try:
                favorites = read_json_lenient(fav_path)
            except Exception:
                continue
            if not isinstance(favorites, list):
                continue
            for item in favorites:
                if not isinstance(item, dict):
                    continue
                holders = stats.setdefault(favorite_match_key(item), [])
                if entry.name not in holders:
                    holders.append(entry.name)
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


def local_news_issue(source_results, errors, search_query, auto_search, username, directory=None):
    today = datetime.now().strftime("%Y-%m-%d")
    items = []
    seen = set()
    for source in source_results:
        for link in source.get("links", []):
            url = link.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            items.append(
                {
                    "title": link.get("title", "未命名资讯"),
                    "source": source.get("name", ""),
                    "url": url,
                    "impact": "从已配置资讯源自动抓取到的候选内容，请打开来源链接确认详情和时效。",
                    "action": "如该来源长期有效，可保留在每日资讯配置中；如内容不相关，建议调整资讯源为栏目页或搜索结果页。",
                }
            )
            if len(items) >= 12:
                break
        if len(items) >= 12:
            break

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

    title = f"{today} 每日资讯"
    summary = (
        f"已从 {len(source_results)} 个配置网址抓取内容，解析出 {len(items)} 条候选资讯。"
        if items
        else "已尝试抓取配置网址，但没有解析到可用资讯条目。请检查网址是否为公开新闻栏目页。"
    )
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
    for source in sources[:12]:
        try:
            source_results.append(fetch_news_source(source))
        except Exception as exc:
            errors.append(f"{source.get('name') or source.get('url')}：{exc}")

    search_query = str(payload.get("search_query") or config_payload["search_query"] or "").strip()
    auto_search = bool(payload.get("auto_search", config_payload["auto_search"]))
    if not source_results and not (auto_search and search_query):
        detail = "；".join(errors[:3])
        raise ValueError(f"请先配置可访问的资讯网页路径，或开启大模型自动网络搜索并填写搜索关键词。{detail}")
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
                    generate_news_issue({"auto_search": config.get("news_auto_search", True)}, "system")
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
                        generate_personal_news_issue({"auto_search": item.get("auto_search", True)}, username)
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(1800)
