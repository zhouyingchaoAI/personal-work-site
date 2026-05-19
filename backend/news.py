"""News source configuration, fetching, issue generation, and scheduler.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def news_dir():
    path = USER_DATA_DIR / "_news"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    sources = payload.get("sources", [])
    if isinstance(sources, str):
        sources = [{"name": "", "url": line.strip()} for line in sources.splitlines() if line.strip()]
    clean_sources = []
    for item in sources:
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
    config["news_sources"] = clean_sources
    config["news_search_query"] = str(payload.get("search_query", "") or "").strip()
    config["news_auto_search"] = bool(payload.get("auto_search", True))
    config["news_auto_push"] = bool(payload.get("auto_push", True))
    config["news_push_time"] = str(payload.get("push_time", "") or "08:30").strip()
    config["news_config_updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_config(config)
    return {"ok": True, "config": news_config_payload()}


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


def latest_news_issue():
    path = news_dir() / "latest.json"
    if not path.exists():
        return None
    try:
        return read_json_lenient(path)
    except Exception:
        return None


def save_news_issue(issue):
    issue_path = news_dir() / f"{issue['date']}.json"
    latest_path = news_dir() / "latest.json"
    raw = json.dumps(issue, ensure_ascii=False, indent=2)
    issue_path.write_text(raw, encoding="utf-8")
    latest_path.write_text(raw, encoding="utf-8")


def public_news_issue(issue, include_config_details=False):
    if not issue:
        return None
    item = dict(issue)
    if not include_config_details:
        for key in ("sources", "errors", "search_query", "auto_search"):
            item.pop(key, None)
    return item


def news_latest(include_config=False):
    result = {"ok": True, "issue": public_news_issue(latest_news_issue(), include_config)}
    if include_config:
        result["config"] = news_config_payload()
    return result


def local_news_issue(source_results, errors, search_query, auto_search, username):
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
    save_news_issue(issue)
    return {"ok": True, "issue": issue}


def generate_news_issue(payload=None, username="system"):
    payload = payload or {}
    config_payload = news_config_payload()
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
        return local_news_issue(source_results, errors, search_query, auto_search, username)

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
        "严格返回 JSON，不要 Markdown："
        "{\"title\":\"今日标题\",\"summary\":\"总览摘要\",\"items\":[{\"title\":\"资讯标题\",\"source\":\"来源\",\"url\":\"链接\",\"impact\":\"影响/价值\",\"action\":\"建议动作\"}],\"keywords\":[\"关键词\"]}"
    )
    user_content = (
        f"日期：{today}\n\n"
        f"自动搜索要求：\n{search_instruction}\n\n"
        f"已配置网页抓取内容：\n{source_text or '无'}"
    )
    try:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.35,
            },
            "POST",
            90,
        )
        result_text = data["choices"][0]["message"]["content"].strip()
        result_text = re.sub(r"^```(?:json)?|```$", "", result_text, flags=re.I).strip()
        parsed = json.loads(result_text)
    except Exception as exc:
        if source_results:
            fallback = local_news_issue(source_results, errors + [f"AI 生成失败：{exc}"], search_query, auto_search, username)
            fallback["issue"]["summary"] += " AI 生成失败，已使用本地抓取结果兜底。"
            save_news_issue(fallback["issue"])
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
    save_news_issue(issue)
    return {"ok": True, "issue": issue}


def news_auto_worker():
    while True:
        try:
            config = read_config()
            if config.get("news_auto_push", True):
                latest = latest_news_issue()
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                push_time = str(config.get("news_push_time", "08:30") or "08:30")
                if re.match(r"^\d{2}:\d{2}$", push_time) and now.strftime("%H:%M") < push_time:
                    time.sleep(1800)
                    continue
                config_updated_at = str(config.get("news_config_updated_at", "") or "")
                latest_generated_at = str((latest or {}).get("generated_at", "") or "")
                needs_retry = bool(latest and latest.get("date") == today and not latest.get("items"))
                config_changed = bool(config_updated_at and latest_generated_at and config_updated_at > latest_generated_at)
                if not latest or latest.get("date") != today or needs_retry or config_changed:
                    generate_news_issue({"auto_search": config.get("news_auto_search", True)}, "system")
        except Exception:
            pass
        time.sleep(1800)
