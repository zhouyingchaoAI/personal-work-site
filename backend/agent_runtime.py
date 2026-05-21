"""Agent Runtime: session management, message history, context assembly, unified response protocol.

This module provides a clean runtime surface for AI-native agent interactions:
- Session CRUD with SQLite persistence
- Message history per session
- Automatic memory/context injection before LLM calls
- Unified response protocol: {reply, actions, ui_patches, memory_updates, requires_confirmation}
- Skill call parsing and execution through the existing Skill Runtime

Loaded by backend.runtime into the shared namespace.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

# These will be available after backend.runtime loads all modules
def _db_connect():
    conn_fn = globals().get("connect")
    if conn_fn:
        return conn_fn()
    # Fallback direct import for tests
    try:
        from backend import db as _db
        return _db.connect()
    except Exception:
        raise RuntimeError("Database connection not available") from None


def _default_db_path():
    path_fn = globals().get("default_db_path")
    if path_fn:
        return path_fn()
    try:
        from backend import db as _db
        return _db.default_db_path()
    except Exception:
        return None


def _init_db():
    init_fn = globals().get("init_db")
    if init_fn:
        return init_fn()
    try:
        from backend import db as _db
        return _db.init_db()
    except Exception:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: str | None, fallback: Any = None) -> Any:
    if not value:
        return {} if fallback is None else fallback
    try:
        return json.loads(value)
    except Exception:
        return {} if fallback is None else fallback


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def create_session(user_id: str, kind: str = "chat", title: str | None = None, metadata: dict | None = None) -> dict:
    """Create a new agent session."""
    _init_db()
    session_id = "sess_" + uuid.uuid4().hex[:20]
    now = _utc_now()
    meta = metadata or {}
    meta.setdefault("created_by", user_id)
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_sessions (id, user_id, kind, title, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id or "anonymous", kind or "chat", title or "", "active", _json_dumps(meta), now, now),
        )
    return {"id": session_id, "user_id": user_id, "kind": kind, "title": title or "", "status": "active", "created_at": now}


def get_session(session_id: str) -> dict | None:
    """Fetch a session by ID."""
    with _db_connect() as conn:
        row = conn.execute("SELECT * FROM agent_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["metadata"] = _json_loads(item.pop("metadata_json", None), {})
    return item


def list_sessions(user_id: str, limit: int = 20) -> list[dict]:
    """List recent sessions for a user."""
    limit = max(1, min(int(limit or 20), 100))
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id or "anonymous", limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_loads(item.pop("metadata_json", None), {})
        result.append(item)
    return result


def update_session(session_id: str, **fields) -> dict:
    """Update session fields (title, status, metadata)."""
    allowed = {"title", "status", "metadata"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_session(session_id) or {}
    params = []
    sets = []
    for k, v in updates.items():
        if k == "metadata":
            sets.append("metadata_json = ?")
            params.append(_json_dumps(v))
        else:
            sets.append(f"{k} = ?")
            params.append(v)
    params.append(_utc_now())
    params.append(session_id)
    with _db_connect() as conn:
        conn.execute(
            f"UPDATE agent_sessions SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
            params,
        )
    return get_session(session_id) or {}


# ---------------------------------------------------------------------------
# Message history
# ---------------------------------------------------------------------------

def add_message(session_id: str, role: str, content: str, metadata: dict | None = None) -> dict:
    """Append a message to a session."""
    now = _utc_now()
    with _db_connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO agent_messages (session_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, _json_dumps(metadata or {}), now),
        )
        msg_id = cur.lastrowid
        # Update session updated_at
        conn.execute("UPDATE agent_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "created_at": now}


def get_messages(session_id: str, limit: int = 100) -> list[dict]:
    """Fetch messages for a session, oldest first."""
    limit = max(1, min(int(limit or 100), 500))
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_loads(item.pop("metadata_json", None), {})
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Agent event timeline
# ---------------------------------------------------------------------------

def record_agent_event(
    user_id: str,
    session_id: str | None,
    event_type: str,
    *,
    source: str = "agent-runtime",
    payload: dict | None = None,
) -> str:
    """Persist a structured event for timeline/audit views."""
    _init_db()
    event_id = "evt_" + uuid.uuid4().hex[:20]
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_events (id, user_id, session_id, event_type, source, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_id or "anonymous",
                session_id,
                event_type or "agent.event",
                source or "agent-runtime",
                _json_dumps(payload or {}),
                _utc_now(),
            ),
        )
    return event_id


def list_agent_events(user_id: str, session_id: str | None = None, limit: int = 50) -> list[dict]:
    """List structured events for the current user/session."""
    _init_db()
    limit = max(1, min(int(limit or 50), 200))
    sql = "SELECT * FROM agent_events WHERE user_id = ?"
    params: list[Any] = [user_id or "anonymous"]
    if session_id:
        sql += " AND session_id = ?"
        params.append(session_id)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with _db_connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["payload"] = _json_loads(item.pop("payload_json", None), {})
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Memory integration helpers
# ---------------------------------------------------------------------------

def _fetch_memory_for_context(user_id: str, query: str | None = None, limit: int = 5) -> list[dict]:
    """Retrieve relevant memory items to inject into agent context."""
    memory_fn = globals().get("search_memory_items")
    if memory_fn:
        try:
            return memory_fn(user_id=user_id, query=query or "", limit=limit)
        except Exception:
            pass
    # Fallback to list_memory_items from db
    try:
        from backend import db as _db
        return _db.list_memory_items(user_id=user_id, limit=limit)
    except Exception:
        return []


def _build_system_prompt(kind: str, user_id: str, skill_docs: str) -> str:
    """Build the system prompt with agent persona + memory + skill docs."""
    # Fetch existing agent system prompt
    prompts = globals().get("AGENT_SYSTEM_PROMPTS", {})
    base = prompts.get(kind) or prompts.get("weekly") or prompts.get("dashboard", "")

    # Inject memory
    memories = _fetch_memory_for_context(user_id, limit=5)
    memory_section = ""
    if memories:
        memory_section = "\n\n[用户记忆]\n"
        for m in memories:
            t = m.get("type", "note")
            c = m.get("content", "")
            memory_section += f"- [{t}] {c}\n"

    skill_section = (
        "\n\n你现在运行在「智能办公助手 Skill 模式」。"
        "\n如果用户要求你操作软件功能，请从下面 Skill 中选择一个调用。"
        '\n调用时只输出严格 JSON：{"reply":"说明","skill_call":{"name":"skill.name","arguments":{}}}'
        "\n如果不需要操作软件功能，直接自然语言回复。"
        "\n如需当前日期、本周起止日期等时间信息，可调用 utils.get_date。"
        "\n可用 Skill：\n" + skill_docs
    )

    return base + memory_section + skill_section


# ---------------------------------------------------------------------------
# Skill call parsing (reuse existing parsers)
# ---------------------------------------------------------------------------

def _parse_skill_call(text: str) -> dict | None:
    """Delegate to the existing parse_skill_call if available."""
    parser = globals().get("parse_skill_call_skill")
    if parser and parser is not _parse_skill_call:
        call = parser(text)
        if not isinstance(call, dict):
            return None
        name = str(call.get("name") or "").strip()
        arguments = call.get("arguments") or {}
        if not name or not isinstance(arguments, dict):
            return None
        return {"name": name, "arguments": arguments, "reply": call.get("reply", "")}
    return None


def _clean_agent_reply(text: str) -> str:
    """Delegate to existing _clean_agent_reply."""
    # Avoid recursion: look up the function from skills_agent module, not self
    skills_cleaner = globals().get("_clean_agent_reply_skill")
    if skills_cleaner and skills_cleaner is not _clean_agent_reply:
        return skills_cleaner(text)
    # Fallback minimal implementation
    if not text:
        return text
    import re
    cleaned = re.sub(r"\[TOOL_CALL\].*?\[/TOOL_CALL\]", "", text, flags=re.S).strip()
    cleaned = re.sub(r"<minimax:tool_call>.*?</minimax:tool_call>", "", cleaned, flags=re.S).strip()
    cleaned = re.sub(r"<invoke[^>]*>.*?</invoke>", "", cleaned, flags=re.S).strip()
    cleaned = re.sub(r"\n?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?", "\n", cleaned).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Unified agent response builder
# ---------------------------------------------------------------------------

def build_agent_response(
    session_id: str,
    reply: str,
    *,
    actions: list[dict] | None = None,
    ui_patches: list[dict] | None = None,
    memory_updates: list[dict] | None = None,
    requires_confirmation: bool = False,
    confirmation_context: dict | None = None,
    skill_calls: list[dict] | None = None,
) -> dict:
    """Build the standardized agent response envelope."""
    return {
        "ok": True,
        "protocol_version": "ai-native.v1",
        "trace_id": "trace_" + uuid.uuid4().hex[:16],
        "session_id": session_id,
        "reply": reply,
        "actions": actions or [],
        "ui_patches": ui_patches or [],
        "memory_updates": memory_updates or [],
        "requires_confirmation": requires_confirmation,
        "confirmation_context": confirmation_context,
        "skill_calls": skill_calls or [],
    }


# ---------------------------------------------------------------------------
# Core agent chat helpers
# ---------------------------------------------------------------------------

def _ui_patches_from_skill_calls(executed_calls: list[dict]) -> list[dict]:
    patches: list[dict] = []
    if executed_calls:
        patches.append({
            "op": "show_timeline",
            "steps": [
                {"name": "理解意图", "status": "completed"},
                {"name": "执行 Skill", "status": "completed"},
                {"name": "更新界面", "status": "completed"},
            ],
        })
    for call in executed_calls:
        name = call["name"]
        result = call.get("result", {}) or {}
        if name == "weekly.preview" and result.get("preview_image_url"):
            patches.append({"op": "show_card", "card_type": "preview", "data": result})
        elif name == "weekly.compose" and result.get("draft"):
            patches.append({"op": "set_field", "selector": "#weeklyDraft", "value": result["draft"]})
        elif name == "diary.save":
            diary = result.get("diary") or result
            patches.append({
                "op": "show_card",
                "card_type": "success",
                "title": "工作日记已保存",
                "content": f"{diary.get('date', '今天')} 的日记已写入，可在工作日记列表中查看。",
            })
    return patches


def _memory_updates_from_skill_calls(executed_calls: list[dict]) -> list[dict]:
    updates: list[dict] = []
    for call in executed_calls:
        if call["name"] == "weekly.compose" and call.get("result", {}).get("ok"):
            draft = call["result"].get("draft", {})
            summary_text = " ".join(r.get("content", "") for r in draft.get("weekly_summary", []))
            if summary_text:
                updates.append({
                    "action": "remember",
                    "type": "event",
                    "content": f"生成周报草稿：{summary_text[:120]}",
                })
    return updates


def _skill_result_reply(skill_name: str, result: dict, model_reply: str = "") -> str:
    """Build a deterministic reply immediately after Skill execution.

    This avoids a second LLM round just to summarize simple/system Skill results,
    which was the main cause of floating-agent calls appearing slow or stuck.
    """
    result = result or {}
    if skill_name == "diary.save":
        diary = result.get("diary") or result
        date = diary.get("date") or "今天"
        parts = []
        if diary.get("today_work"):
            parts.append("今日工作：" + str(diary.get("today_work"))[:120])
        if diary.get("tomorrow_plan"):
            parts.append("明日计划：" + str(diary.get("tomorrow_plan"))[:120])
        if diary.get("thoughts"):
            parts.append("想法心得：" + str(diary.get("thoughts"))[:120])
        detail = "；".join(parts)
        return f"已保存 {date} 的工作日记" + (f"：{detail}" if detail else "。")
    if skill_name == "utils.get_date":
        parts = []
        for key in ("today", "weekday", "week_range", "month_range", "quarter_range", "year", "iso_week"):
            if result.get(key):
                labels = {
                    "today": "今天",
                    "weekday": "星期",
                    "week_range": "本周",
                    "month_range": "本月",
                    "quarter_range": "本季度",
                    "year": "年度",
                    "iso_week": "ISO 周",
                }
                parts.append(f"{labels[key]}：{result[key]}")
        return "已获取日期信息：" + "；".join(parts) if parts else "已获取日期信息。"
    if skill_name == "reports.list":
        reports = result.get("reports") or []
        weekly = len([r for r in reports if r.get("kind") == "weekly"])
        trip = len([r for r in reports if r.get("kind") == "trip"])
        sample = "、".join(str(r.get("name") or r.get("file") or "未命名") for r in reports[:5])
        suffix = f"，最近包括：{sample}" if sample else ""
        return f"已查询到 {len(reports)} 条报告记录（周报 {weekly} 条，出差报告 {trip} 条）{suffix}。"
    if skill_name in ("weekly.prefill", "trip.prefill"):
        if result.get("ok") is False and result.get("error"):
            return str(result["error"])
        return "已读取最新历史报告预填信息，页面可继续编辑。"
    if skill_name == "diary.list":
        items = result.get("items") or result.get("diaries") or result.get("records") or []
        if not items:
            return "暂未查询到工作日记记录。你可以先在工作日记页面保存一篇，或直接告诉我‘帮我记录今天的工作日记：……’。"
        lines = [f"已查询到 {len(items)} 条工作日记记录，最近记录如下："]
        for idx, item in enumerate(items[:10], 1):
            date = item.get("date") or item.get("created_at") or "未标日期"
            preview = item.get("today_work_preview") or item.get("today_work") or item.get("summary") or "无内容预览"
            lines.append(f"{idx}. {date}：{str(preview)[:120]}")
        return "\n".join(lines)
    if skill_name == "forum.list":
        topics = result.get("topics") or result.get("items") or []
        return f"已查询到 {len(topics)} 条金点子话题。"
    if skill_name == "news.latest":
        title = result.get("title") or result.get("headline") or "最新每日资讯"
        return f"已获取{title}。"
    if skill_name == "workflow.list":
        workflows = result.get("workflows") or result.get("items") or []
        return f"已查询到 {len(workflows)} 个可用工作流。"
    if result.get("message"):
        return str(result["message"])
    if result.get("file"):
        return f"{skill_name} 已完成，生成文件：{result['file']}。"
    if model_reply:
        return _clean_agent_reply(model_reply) or f"{skill_name} 已执行完成。"
    return f"{skill_name} 已执行完成。"


def _clean_diary_segment(segment: str) -> str:
    segment = str(segment or "").strip(" ，,。；;\n\t")
    segment = re.sub(r"^(今天|今日|我今天|今天我|今日我)?(完成了?|做了?|处理了?|工作内容是?|工作是?|工作[:：]?|主要工作是?)", "", segment).strip(" ，,。；;\n\t")
    segment = re.sub(r"^(明天|明日|明天我|明日我)?(继续|计划|要做|准备|工作计划是?|计划是?)", "", segment).strip(" ，,。；;\n\t")
    segment = re.sub(r"^(想法是?|心得是?|思路是?|备注是?)", "", segment).strip(" ，,。；;\n\t")
    return segment


def _direct_diary_save_call(raw_text: str) -> dict | None:
    """Parse explicit diary-save utterances into diary.save arguments.

    This keeps common diary assistant turns complete even without an LLM round, and
    prevents words like “今天” inside diary content from being misrouted to date lookup.
    """
    text = (raw_text or "").split("[系统提示", 1)[0].strip()
    normalized = text.lower()
    if "日记" not in normalized:
        return None
    diary_list_tokens = (
        "日记列表", "工作日记列表", "查询日记", "查看日记", "看看日记", "看下日记", "看一下日记",
        "查下日记", "查一下日记", "最近日记", "列出日记", "浏览日记", "历史日记", "日记记录",
        "看看我的日记", "看日记", "我的日记", "查日记", "日记在哪", "日记内容",
    )
    if any(token in normalized for token in diary_list_tokens):
        return None
    if not any(token in normalized for token in ("记录", "保存", "写", "新增", "创建", "帮我记", "记一下")):
        return None

    date_match = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})", text)
    if date_match:
        date = re.sub(r"[/.年/月]", "-", date_match.group(1)).rstrip("日")
        parts = date.split("-")
        if len(parts) == 3:
            date = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    content = re.split(r"[:：]", text, maxsplit=1)[1] if re.search(r"[:：]", text) else text
    content = re.sub(r"^(帮我|请)?(记录|保存|写|新增|创建)?(今天|今日|一篇)?(的)?(工作)?日记", "", content).strip(" ，,。；;\n\t")
    today_parts: list[str] = []
    tomorrow_parts: list[str] = []
    thought_parts: list[str] = []
    for segment in re.split(r"[；;\n]+", content):
        seg = segment.strip()
        if not seg:
            continue
        if re.search(r"明天|明日|计划|待办", seg):
            tomorrow_parts.append(_clean_diary_segment(seg))
        elif re.search(r"想法|心得|思路|感受|备注", seg):
            thought_parts.append(_clean_diary_segment(seg))
        else:
            today_parts.append(_clean_diary_segment(seg))

    if not today_parts and content:
        today_parts.append(_clean_diary_segment(content))

    payload = {
        "date": date,
        "today_work": "；".join(p for p in today_parts if p),
        "tomorrow_plan": "；".join(p for p in tomorrow_parts if p),
        "thoughts": "；".join(p for p in thought_parts if p),
    }
    if not any(payload.get(k) for k in ("today_work", "tomorrow_plan", "thoughts")):
        return None
    return {"name": "diary.save", "arguments": payload}


def _direct_system_skill_call(text: str, kind: str = "") -> dict | None:
    """Return a deterministic local Skill call for cheap safe utilities.

    Safe query Skills should not require an LLM round-trip when the user's intent
    is explicit. The model is still used for fuzzy planning and content creation;
    this router only handles low-risk lookups with stable arguments.
    """
    raw = text or ""
    # Frontend may append page context after this marker. Direct intent routing
    # should only inspect the user's actual utterance, otherwise terms like
    # "本周工作总结" in page context can incorrectly trigger date lookup.
    raw = raw.split("[系统提示", 1)[0]
    normalized = raw.lower().strip()
    if not normalized:
        return None

    def has_any(*tokens: str) -> bool:
        return any(token in normalized for token in tokens)

    if has_any("日记列表", "工作日记列表", "查询日记", "查看日记", "看看日记", "看下日记", "看一下日记", "查下日记", "查一下日记", "最近日记", "列出日记", "浏览日记", "历史日记", "日记记录", "看看我的日记", "看日记", "我的日记", "查日记", "日记在哪", "日记内容"):
        return {"name": "diary.list", "arguments": {"limit": 20}}

    diary_save = _direct_diary_save_call(raw)
    if diary_save:
        return diary_save

    # 对话上下文中用户追问"列表呢""我需要看列表"等，如果当前 kind 是 diary 且没有保存意图，
    # 也视为日记列表查询意图
    if kind == "diary" and has_any("列表", "看列表", "看记录", "记录在哪"):
        return {"name": "diary.list", "arguments": {"limit": 20}}

    wants_date = has_any("日期", "几号", "星期", "周几", "date", "today", "今天几号", "今天日期", "当前日期", "现在日期")
    mentions_week = has_any("本周", "本月", "本季度", "年度")
    mentions_skill = has_any("skill", "工具", "系统", "调用", "tool")
    explicit_date_question = has_any("今天几号", "今天日期", "当前日期", "现在日期", "几号", "周几", "星期几", "date", "today")
    if (explicit_date_question or (wants_date and mentions_skill) or (mentions_week and mentions_skill)) and (mentions_skill or len(normalized) <= 80):
        return {"name": "utils.get_date", "arguments": {}}

    if (
        has_any("报告列表", "历史报告", "报告记录", "查询报告", "列出报告", "最近报告", "历史周报", "周报历史", "看看历史周报", "历史出差", "出差历史", "看看历史出差")
        and not has_any("预填", "读取")
    ):
        report_kind = "all"
        if has_any("周报") and not has_any("出差"):
            report_kind = "weekly"
        elif has_any("出差") and not has_any("周报"):
            report_kind = "trip"
        return {"name": "reports.list", "arguments": {"kind": report_kind}}

    if kind == "weekly" and has_any("历史", "历史周报", "周报历史") and has_any("看", "看看", "查看", "查询", "列表"):
        return {"name": "reports.list", "arguments": {"kind": "weekly"}}

    if kind == "trip" and has_any("历史", "历史出差", "出差历史") and has_any("看", "看看", "查看", "查询", "列表"):
        return {"name": "reports.list", "arguments": {"kind": "trip"}}

    if has_any("最新周报", "周报预填", "历史周报预填", "读取周报") and has_any("预填", "最新", "历史", "迁移"):
        return {"name": "weekly.prefill", "arguments": {}}

    if has_any("最新出差", "出差预填", "历史出差", "读取出差") and has_any("预填", "最新", "历史"):
        return {"name": "trip.prefill", "arguments": {}}

    if has_any("金点子", "论坛话题", "论坛列表") and has_any("查看", "查询", "列表", "最新", "话题"):
        return {"name": "forum.list", "arguments": {}}

    if has_any("每日资讯", "最新资讯", "新闻", "资讯") and has_any("查看", "获取", "最新", "今天"):
        return {"name": "news.latest", "arguments": {}}

    if has_any("工作流列表", "可用工作流", "workflow") and has_any("查看", "查询", "列出", "列表"):
        return {"name": "workflow.list", "arguments": {}}

    return None


def _split_user_text_and_page_context(text: str) -> tuple[str, dict]:
    """Return the user's visible utterance plus optional frontend context JSON."""
    raw = text or ""
    user_text, marker, tail = raw.partition("[系统提示")
    if not marker:
        return raw.strip(), {}
    json_start = tail.find("{")
    if json_start < 0:
        return user_text.strip(), {}
    context = _json_loads(tail[json_start:].strip(), {})
    return user_text.strip(), context if isinstance(context, dict) else {}


def _is_greeting(text: str) -> bool:
    clean = re.sub(r"[\s,，。.!！?？~～]+", "", (text or "").strip().lower())
    return clean in {"在吗", "在不在", "hello", "hi", "嗨", "你好", "您好", "有人吗"}


def _weekly_intent(text: str, kind: str) -> bool:
    if kind != "weekly":
        return False
    if re.search(r"报告列表|历史报告|报告记录|查询.*报告|列出.*报告|最近报告|历史周报|周报历史", text or ""):
        return False
    return bool(re.search(r"周报|工作总结|草稿|预览|看看|显示|生成|整理|输出", text or ""))


def _trip_intent(text: str, kind: str) -> bool:
    if kind != "trip":
        return False
    if re.search(r"报告列表|历史报告|报告记录|查询.*报告|列出.*报告|最近报告|历史出差|出差历史", text or ""):
        return False
    return bool(re.search(r"出差|差旅|行程|报告|草稿|预览|看看|显示|生成|整理|输出", text or ""))


def _weekly_preview_intent(text: str) -> bool:
    return bool(re.search(r"预览|看看草稿|显示草稿|看草稿|看看|显示|生成文件|生成周报", text or ""))


def _weekly_compose_intent(text: str) -> bool:
    return bool(re.search(r"写|生成|整理|输出|编写|草稿|周报|工作总结", text or ""))


def _rows_have_content(rows: Any) -> bool:
    if not isinstance(rows, list):
        return False
    for row in rows:
        if isinstance(row, dict) and any(str(v or "").strip() for v in row.values()):
            return True
    return False


def _weekly_context_rows(context: dict) -> dict:
    return {
        "weekly_summary": context.get("weekly_summary") if isinstance(context.get("weekly_summary"), list) else [],
        "weekly_follow": context.get("weekly_follow") if isinstance(context.get("weekly_follow"), list) else [],
        "weekly_next": context.get("weekly_next") if isinstance(context.get("weekly_next"), list) else [],
    }


def _period_from_date_result(date_result: dict, context: dict | None = None) -> str:
    context = context or {}
    period = str(context.get("period") or context.get("weekly_period") or "").strip()
    if period:
        return period
    week_start = date_result.get("week_start")
    week_end = date_result.get("week_end")
    if week_start and week_end:
        return f"{week_start}-{week_end}"
    return str(date_result.get("week_range") or "").strip()


def _weekly_material_from_user_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^(帮我|请|麻烦)?(根据|用)?", "", text).strip()
    return text


def _trip_preview_intent(text: str) -> bool:
    return bool(re.search(r"预览|看看|显示|生成文件|生成报告|生成出差报告", text or ""))


def _trip_context_payload(context: dict) -> dict:
    keys = (
        "reporter", "department", "location", "trip_start", "trip_end",
        "purpose", "itinerary", "details", "issues", "suggestions",
    )
    return {key: str(context.get(key) or "").strip() for key in keys}


def _trip_payload_has_content(payload: dict) -> bool:
    return any(str(payload.get(k) or "").strip() for k in ("location", "purpose", "itinerary", "details", "issues", "suggestions"))


def _trip_material_from_user_text(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^(帮我|请|麻烦)?(根据|用)?", "", text).strip()
    return text


def _trip_date_text(payload: dict, date_result: dict) -> str:
    start = str(payload.get("trip_start") or "").strip()
    end = str(payload.get("trip_end") or "").strip()
    if start and end:
        return f"{start} 至 {end}"
    if start:
        return start
    return str(date_result.get("today") or "").strip()


def _has_weekly_material(text: str, context: dict) -> bool:
    if len(_weekly_material_from_user_text(text)) >= 18 and re.search(r"完成|重构|设计|开发|优化|修复|推进|联调|总结|本周|下周", text or ""):
        return True
    return any(_rows_have_content(v) for v in _weekly_context_rows(context).values())


def _direct_weekly_response(latest_user_content: str, kind: str, username: str, session_id: str) -> dict | None:
    """Handle common weekly turns in one deterministic backend pass.

    This avoids splitting one user request into "get date now, compose later,
    preview after another prompt" and always surfaces the period used.
    """
    user_text, context = _split_user_text_and_page_context(latest_user_content)
    if not _weekly_intent(user_text, kind):
        return None

    exec_fn = globals().get("execute_skill")
    if not exec_fn:
        return _agent_error(session_id, username, "内部错误：缺少 execute_skill", kind=kind)

    if _weekly_preview_intent(user_text):
        rows = _weekly_context_rows(context)
        if any(_rows_have_content(v) for v in rows.values()):
            date_result = exec_fn("utils.get_date", {}, username)
            period = _period_from_date_result(date_result, context)
            preview_args = {"period": period, **rows}
            preview_result = exec_fn("weekly.preview", preview_args, username)
            executed_calls = [
                {"name": "utils.get_date", "arguments": {}, "result": date_result},
                {"name": "weekly.preview", "arguments": preview_args, "result": preview_result},
            ]
            reply = f"已按周报时段 {period} 生成预览。请先确认这个时间范围和内容是否正确，确认无误后我再发送。"
            add_message(session_id, "assistant", reply, metadata={"kind": kind, "direct_weekly": True})
            return build_agent_response(
                session_id=session_id,
                reply=reply,
                actions=[{"type": "skill_call", "name": c["name"], "arguments": c["arguments"]} for c in executed_calls],
                ui_patches=_ui_patches_from_skill_calls(executed_calls),
                memory_updates=_memory_updates_from_skill_calls(executed_calls),
                skill_calls=executed_calls,
            )

    if _weekly_compose_intent(user_text):
        if not _has_weekly_material(user_text, context):
            date_result = exec_fn("utils.get_date", {}, username)
            period = _period_from_date_result(date_result, context)
            executed_calls = [{"name": "utils.get_date", "arguments": {}, "result": date_result}]
            reply = (
                f"在的。我先确认一下周报时间范围：本次是否按 {period} 来写？"
                "你可以直接把本周工作、重点跟进和下周计划发给我，我会一次生成草稿并填入表单。"
            )
            add_message(session_id, "assistant", reply, metadata={"kind": kind, "direct_weekly": True})
            return build_agent_response(
                session_id=session_id,
                reply=reply,
                actions=[{"type": "skill_call", "name": "utils.get_date", "arguments": {}}],
                ui_patches=_ui_patches_from_skill_calls(executed_calls),
                skill_calls=executed_calls,
            )

        date_result = exec_fn("utils.get_date", {}, username)
        period = _period_from_date_result(date_result, context)
        compose_args = {"period": period, "raw_work": _weekly_material_from_user_text(user_text)}
        compose_result = exec_fn("weekly.compose", compose_args, username)
        executed_calls = [
            {"name": "utils.get_date", "arguments": {}, "result": date_result},
            {"name": "weekly.compose", "arguments": compose_args, "result": compose_result},
        ]
        draft = compose_result.get("draft") or {}
        if _weekly_preview_intent(user_text):
            preview_args = {"period": period, **draft}
            preview_result = exec_fn("weekly.preview", preview_args, username)
            executed_calls.append({"name": "weekly.preview", "arguments": preview_args, "result": preview_result})
            reply = f"收到。我已按周报时段 {period} 生成草稿并生成预览，请确认时间范围、内容和格式。"
        else:
            reply = f"收到。我已按周报时段 {period} 生成草稿并填入表单，请先确认这个时间范围是否正确；需要预览时告诉我“生成预览”。"
        add_message(session_id, "assistant", reply, metadata={"kind": kind, "direct_weekly": True})
        return build_agent_response(
            session_id=session_id,
            reply=reply,
            actions=[{"type": "skill_call", "name": c["name"], "arguments": c["arguments"]} for c in executed_calls],
            ui_patches=_ui_patches_from_skill_calls(executed_calls),
            memory_updates=_memory_updates_from_skill_calls(executed_calls),
            skill_calls=executed_calls,
        )

    return None


def _direct_trip_response(latest_user_content: str, kind: str, username: str, session_id: str) -> dict | None:
    """Handle common trip-report turns without leaving completion to another prompt."""
    user_text, context = _split_user_text_and_page_context(latest_user_content)
    if not _trip_intent(user_text, kind):
        return None

    exec_fn = globals().get("execute_skill")
    if not exec_fn:
        return _agent_error(session_id, username, "内部错误：缺少 execute_skill", kind=kind)

    payload = _trip_context_payload(context)
    raw_material = _trip_material_from_user_text(user_text)
    if not _trip_payload_has_content(payload) and len(raw_material) >= 12:
        payload["details"] = raw_material
    if not _trip_payload_has_content(payload):
        date_result = exec_fn("utils.get_date", {}, username)
        date_text = _trip_date_text(payload, date_result)
        executed_calls = [{"name": "utils.get_date", "arguments": {}, "result": date_result}]
        reply = (
            f"在的。出差报告我需要先确认出差时间和地点。当前可按 {date_text} 起草，"
            "请补充出差地点、目的、行程和工作详情；补齐后我会一次生成报告文件和邮件草稿。"
        )
        add_message(session_id, "assistant", reply, metadata={"kind": kind, "direct_trip": True})
        return build_agent_response(
            session_id=session_id,
            reply=reply,
            actions=[{"type": "skill_call", "name": "utils.get_date", "arguments": {}}],
            ui_patches=_ui_patches_from_skill_calls(executed_calls),
            skill_calls=executed_calls,
        )

    date_result = exec_fn("utils.get_date", {}, username)
    if not payload.get("trip_start"):
        payload["trip_start"] = str(date_result.get("today") or "").replace(".", "-")
    if not payload.get("trip_end"):
        payload["trip_end"] = payload.get("trip_start", "")
    args = {"kind": "trip", **payload}
    result = exec_fn("document.generate", args, username)
    executed_calls = [
        {"name": "utils.get_date", "arguments": {}, "result": date_result},
        {"name": "document.generate", "arguments": args, "result": result},
    ]
    date_text = _trip_date_text(payload, date_result)
    reply = f"收到。我已按出差时间 {date_text} 生成出差报告文件和邮件草稿，请确认时间、地点和正文内容。"
    add_message(session_id, "assistant", reply, metadata={"kind": kind, "direct_trip": True})
    return build_agent_response(
        session_id=session_id,
        reply=reply,
        actions=[{"type": "skill_call", "name": c["name"], "arguments": c["arguments"]} for c in executed_calls],
        ui_patches=_ui_patches_from_skill_calls(executed_calls),
        skill_calls=executed_calls,
    )


def _agent_error(session_id: str, username: str, message: str, *, kind: str = "", source: str = "agent-runtime") -> dict:
    if session_id:
        try:
            record_agent_event(
                username,
                session_id,
                "agent.error",
                source=source,
                payload={"kind": kind, "error": message},
            )
        except Exception:
            pass
    return {
        "ok": False,
        "protocol_version": "ai-native.v1",
        "trace_id": "trace_" + uuid.uuid4().hex[:16],
        "session_id": session_id,
        "error": message,
    }


# ---------------------------------------------------------------------------
# Core agent chat
# ---------------------------------------------------------------------------

def agent_chat(payload: dict, username: str = "") -> dict:
    """AI-native agent chat with session persistence, memory injection, and unified response protocol.

    Payload fields:
    - session_id: optional; if omitted, a new session is created
    - kind: agent kind (weekly/trip/diary/mailassistant/news/forum/dashboard)
    - messages: list of {role, content} for this turn (typically just the latest user message)
    - create_if_missing: bool, default True
    """
    _init_db()
    payload = payload or {}
    kind = str(payload.get("kind", "weekly")).strip()
    session_id = str(payload.get("session_id", "") or "").strip()
    create_if_missing = bool(payload.get("create_if_missing", True))

    # Resolve or create session
    if session_id:
        session = get_session(session_id)
        if not session and not create_if_missing:
            return {"ok": False, "error": "会话不存在"}
        if not session:
            session = create_session(username, kind=kind)
            session_id = session["id"]
    else:
        session = create_session(username, kind=kind)
        session_id = session["id"]

    record_agent_event(
        username,
        session_id,
        "agent.turn.started",
        payload={"kind": kind, "message_count": len(payload.get("messages", []) or [])},
    )

    # Persist incoming user messages
    incoming = payload.get("messages", [])
    if isinstance(incoming, dict):
        incoming = [incoming]
    for m in incoming:
        if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
            add_message(session_id, "user", str(m["content"]), metadata={"kind": kind})

    latest_user_content = next(
        (str(m.get("content", "") or "").strip() for m in reversed(incoming) if isinstance(m, dict) and m.get("role") == "user" and str(m.get("content", "") or "").strip()),
        "",
    )
    user_text_only, _page_context = _split_user_text_and_page_context(latest_user_content)
    if _is_greeting(user_text_only):
        final_reply = "在的。我可以帮你写周报、生成预览、整理日记或处理邮件。你把要处理的内容发给我就行。"
        add_message(session_id, "assistant", final_reply, metadata={"kind": kind, "direct_greeting": True})
        response = build_agent_response(session_id=session_id, reply=final_reply)
        record_agent_event(
            username,
            session_id,
            "agent.turn.completed",
            payload={"kind": kind, "reply_chars": len(final_reply), "direct": True, "intent": "greeting"},
        )
        return response

    weekly_response = _direct_weekly_response(latest_user_content, kind, username, session_id)
    if weekly_response:
        record_agent_event(
            username,
            session_id,
            "agent.turn.completed",
            payload={
                "kind": kind,
                "reply_chars": len(weekly_response.get("reply") or ""),
                "skill_calls": len(weekly_response.get("skill_calls") or []),
                "direct": True,
                "intent": "weekly",
            },
        )
        return weekly_response

    trip_response = _direct_trip_response(latest_user_content, kind, username, session_id)
    if trip_response:
        record_agent_event(
            username,
            session_id,
            "agent.turn.completed",
            payload={
                "kind": kind,
                "reply_chars": len(trip_response.get("reply") or ""),
                "skill_calls": len(trip_response.get("skill_calls") or []),
                "direct": True,
                "intent": "trip",
            },
        )
        return trip_response

    direct_call = _direct_system_skill_call(latest_user_content, kind)
    if direct_call:
        exec_fn = globals().get("execute_skill")
        if not exec_fn:
            return _agent_error(session_id, username, "内部错误：缺少 execute_skill", kind=kind)
        try:
            result = exec_fn(direct_call["name"], direct_call.get("arguments") or {}, username)
            executed_calls = [{"name": direct_call["name"], "arguments": direct_call.get("arguments") or {}, "result": result}]
            final_reply = _skill_result_reply(direct_call["name"], result)
            add_message(session_id, "assistant", final_reply, metadata={"kind": kind, "direct_skill": True, "skill_call": direct_call})
            ui_patches = _ui_patches_from_skill_calls(executed_calls)
            memory_updates = _memory_updates_from_skill_calls(executed_calls)
            response = build_agent_response(
                session_id=session_id,
                reply=final_reply,
                ui_patches=ui_patches,
                memory_updates=memory_updates,
                skill_calls=executed_calls,
            )
            record_agent_event(
                username,
                session_id,
                "skill.completed",
                payload={"kind": kind, "skill": direct_call["name"], "direct": True},
            )
            record_agent_event(
                username,
                session_id,
                "agent.turn.completed",
                payload={"kind": kind, "reply_chars": len(final_reply), "skill_calls": 1, "direct": True},
            )
            return response
        except Exception as exc:
            return _agent_error(session_id, username, str(exc), kind=kind)

    # Fetch history
    history = get_messages(session_id, limit=100)

    # Build skill docs
    skill_defs_fn = globals().get("skill_defs")
    skill_docs = ""
    if skill_defs_fn:
        try:
            skill_docs = json.dumps(skill_defs_fn(), ensure_ascii=False)
        except Exception:
            pass

    # Build system prompt with memory
    system = _build_system_prompt(kind, username, skill_docs)

    # Build API messages
    api_messages = [{"role": "system", "content": system}]
    for msg in history:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    # Get assistant settings
    settings_fn = globals().get("assistant_settings")
    settings = settings_fn() if settings_fn else {}
    if not settings.get("url") or not settings.get("key"):
        return _agent_error(session_id, username, "未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key", kind=kind)

    # Request LLM
    request_json_fn = globals().get("request_json")
    if not request_json_fn:
        return _agent_error(session_id, username, "内部错误：缺少 request_json", kind=kind)

    try:
        executed_calls: list[dict] = []
        max_rounds = 3
        final_reply = ""
        content = ""
        continue_after_skill = bool(payload.get("continue_after_skill", False))
        for _round in range(max_rounds):
            data = request_json_fn(
                settings["url"] + "/v1/chat/completions",
                settings["key"],
                {
                    "model": settings["model"],
                    "messages": api_messages,
                    "temperature": 0.6 if _round == 0 else 0.4,
                },
                "POST",
                45,
            )
            content = data["choices"][0]["message"]["content"].strip()
            skill_call = _parse_skill_call(content)

            if not skill_call:
                final_reply = _clean_agent_reply(content)
                add_message(session_id, "assistant", final_reply, metadata={"kind": kind, "round": _round})
                break

            # Execute skill through the audited runtime
            exec_fn = globals().get("execute_skill")
            if not exec_fn:
                return _agent_error(session_id, username, "内部错误：缺少 execute_skill", kind=kind)

            result = exec_fn(skill_call["name"], skill_call["arguments"], username)
            executed_calls.append({
                "name": skill_call["name"],
                "arguments": skill_call["arguments"],
                "result": result,
            })
            record_agent_event(
                username,
                session_id,
                "skill.completed",
                payload={"kind": kind, "skill": skill_call["name"], "round": _round},
            )

            # Persist assistant skill-call message
            add_message(session_id, "assistant", content, metadata={"kind": kind, "round": _round, "skill_call": skill_call})

            # Default to execute-and-return. This keeps system Skill calls fast and
            # prevents the UI from waiting for a second LLM summarization round.
            should_continue = continue_after_skill or (
                kind == "weekly"
                and _weekly_intent(user_text_only, kind)
                and skill_call["name"] in ("utils.get_date", "weekly.compose")
            )
            if not should_continue:
                final_reply = _skill_result_reply(skill_call["name"], result, skill_call.get("reply") or content)
                add_message(session_id, "assistant", final_reply, metadata={"kind": kind, "round": _round, "skill_result_reply": True})
                break

            # Optional legacy loop: feed result back to LLM for multi-step planning.
            feedback = (
                "[系统通知：你刚才调用了 Skill '" + skill_call["name"] + "'，执行结果如下。"
                "如果任务已完成，请用自然语言回复用户。"
                "如果还需要继续操作，可以继续调用下一个 Skill。]\\n"
                + json.dumps(result, ensure_ascii=False)
            )
            add_message(session_id, "user", feedback, metadata={"kind": kind, "round": _round, "system_feedback": True})
            api_messages.append({"role": "assistant", "content": content})
            api_messages.append({"role": "user", "content": feedback})

        if not final_reply:
            final_reply = _clean_agent_reply(content) or "我这次没有拿到有效的可执行结果。请再说一次你要查看历史周报、生成草稿还是生成预览，我会直接执行对应操作。"
            add_message(session_id, "assistant", final_reply, metadata={"kind": kind, "round": max_rounds - 1, "max_rounds": True})
    except Exception as exc:
        return _agent_error(session_id, username, str(exc), kind=kind)

    # Build unified response
    ui_patches = _ui_patches_from_skill_calls(executed_calls)
    memory_updates = _memory_updates_from_skill_calls(executed_calls)

    response = build_agent_response(
        session_id=session_id,
        reply=final_reply,
        actions=[{"type": "skill_call", "name": c["name"], "arguments": c["arguments"]} for c in executed_calls],
        ui_patches=ui_patches,
        memory_updates=memory_updates,
        skill_calls=executed_calls,
    )
    record_agent_event(
        username,
        session_id,
        "agent.turn.completed",
        payload={
            "kind": kind,
            "reply_chars": len(final_reply or ""),
            "skill_calls": len(executed_calls),
            "ui_patches": len(ui_patches),
        },
    )
    return response


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def agent_sessions_api(payload: dict, username: str) -> dict:
    """Handler for /api/agent/sessions."""
    action = str(payload.get("action", "list")).strip()
    if action == "list":
        return {"ok": True, "sessions": list_sessions(username, limit=payload.get("limit", 20))}
    if action == "create":
        kind = str(payload.get("kind", "chat")).strip()
        title = str(payload.get("title", "") or "").strip()
        session = create_session(username, kind=kind, title=title)
        return {"ok": True, "session": session}
    if action == "get":
        sid = str(payload.get("session_id", "") or "").strip()
        session = get_session(sid)
        if not session:
            return {"ok": False, "error": "会话不存在"}
        messages = get_messages(sid, limit=payload.get("limit", 100))
        events = list_agent_events(username, session_id=sid, limit=payload.get("event_limit", 50))
        return {"ok": True, "session": session, "messages": messages, "events": events}
    if action == "events":
        sid = str(payload.get("session_id", "") or "").strip()
        events = list_agent_events(username, session_id=sid or None, limit=payload.get("limit", 50))
        return {"ok": True, "events": events}
    if action == "update":
        sid = str(payload.get("session_id", "") or "").strip()
        updates = {}
        if "title" in payload:
            updates["title"] = str(payload["title"])
        if "status" in payload:
            updates["status"] = str(payload["status"])
        session = update_session(sid, **updates)
        return {"ok": True, "session": session}
    return {"ok": False, "error": "未知 action"}
