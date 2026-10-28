"""Work-order (工单) system, split out from the golden-idea forum.

Tickets used to live inside the forum store as topics with preset "platform_ticket".
They now have their own store (_tickets/tickets.json) and dedicated CRUD, while the
forum keeps only ordinary idea topics. A one-time, idempotent migration moves any
legacy platform_ticket topics out of the forum store (with a backup) so no data is
lost. Attachments continue to use the shared forum attachment storage/route, so
existing attachment URLs keep working without moving any files.

Loaded by backend.runtime into the shared application namespace.
"""

TICKET_COMMENT_STATUSES = {"", "accepted", "resolved", "rejected"}


def ticket_mcp_tool(name, args, username):
    user = find_user(username) if username else None
    if not user:
        raise PermissionError("工单工具要求 X-MCP-Username 为有效的平台账号")
    if not isinstance(args, dict):
        raise ValueError("参数必须是对象")
    if name == "tickets.image":
        ticket_id = str(args.get("id", "") or "").strip()
        attachment_id = str(args.get("attachment_id", "") or "").strip()
        if not ticket_id or not re.fullmatch(r"[A-Za-z0-9_-]+", attachment_id):
            raise ValueError("请提供有效工单ID及附件ID")
        ticket = next((item for item in load_tickets() if item.get("id") == ticket_id), None)
        if ticket is None:
            raise ValueError("工单不存在")
        attachments = list(ticket.get("attachments", []))
        for comment in ticket.get("comments", []):
            attachments.extend(comment.get("attachments", []))
        attachment = next((item for item in attachments if item.get("id") == attachment_id), None)
        if attachment is None:
            raise PermissionError("该附件不属于指定工单或其回复")
        entry = forum_attachment_entry(attachment_id)
        if entry is None:
            raise ValueError("附件文件不存在")
        if entry[1] > 10 * 1024 * 1024:
            raise ValueError("图片超过10MB，请在平台查看或上传压缩图片")
        return {"ok": True, "ticket_id": ticket_id, "attachment_id": attachment_id,
                "name": forum_public_attachment(attachment)["name"], "size": entry[1]}
    if name == "tickets.reply":
        if args.get("confirm") is not True:
            raise ValueError("回复将写入工单，请设置 confirm=true")
        status = str(args.get("status", "") or "")
        if status not in TICKET_COMMENT_STATUSES:
            raise ValueError("无效工单状态")
        if status and user.get("role") not in ("admin", "superadmin"):
            raise PermissionError("仅管理员可通过MCP改变工单状态；普通用户可回复")
        content = str(args.get("content", "") or "").strip()
        if not content or len(content) > 10000:
            raise ValueError("回复内容须为1至10000字")
        return ticket_add_comment({"ticket_id": args.get("id"), "content": content, "status": status}, username)
    if name == "tickets.get":
        ticket_id = str(args.get("id", "") or "").strip()
        if not ticket_id:
            raise ValueError("请提供工单ID")
        ticket = next((item for item in load_tickets() if item.get("id") == ticket_id), None)
        if ticket is None:
            raise ValueError("工单不存在")
        return {"ok": True, "ticket": ticket_public(ticket, with_comments=True)}
    if name != "tickets.list":
        raise ValueError("未知工单工具")
    limit, offset = args.get("limit", 30), args.get("offset", 0)
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError("limit须为1至100整数，offset须为非负整数")
    status = args.get("status", "all") or "all"
    if status not in ("all", "unresolved", "open", "accepted", "resolved", "rejected"):
        raise ValueError("无效工单状态")
    since = str(args.get("updated_since", "") or "").strip()
    if since:
        try:
            since_timestamp = datetime.fromisoformat(since).timestamp()
        except ValueError:
            raise ValueError("updated_since须为ISO时间，建议原样使用工单updated_at")
    keyword = str(args.get("keyword", "") or "").strip().lower()
    selected = []
    for ticket in load_tickets():
        if any(args.get(key) and ticket.get(key, "") != args[key] for key in ("module", "author", "author_username")):
            continue
        if status == "unresolved" and ticket_is_closed(ticket):
            continue
        if status not in ("all", "unresolved") and ticket_status(ticket) != status:
            continue
        if since and (not ticket.get("updated_at") or datetime.fromisoformat(ticket["updated_at"]).timestamp() < since_timestamp):
            continue
        if keyword and keyword not in " ".join(str(ticket.get(key, "")) for key in ("title", "body", "author", "module")).lower():
            continue
        selected.append(ticket)
    selected.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("id", ""))))
    page = selected[offset:offset + limit]
    return {"ok": True, "tickets": [ticket_public(item) for item in page], "total": len(selected),
            "offset": offset, "limit": limit, "has_more": offset + len(page) < len(selected),
            "next_offset": offset + len(page) if offset + len(page) < len(selected) else None,
            "latest_updated_at": max((str(item.get("updated_at", "")) for item in selected), default=None)}


def ticket_mcp_image_content(metadata):
    found = forum_attachment_content(metadata["attachment_id"])
    if found is None:
        raise ValueError("附件文件不存在")
    raw = found[1]
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise ValueError("图片为空或超过10MB")
    mime = None
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif raw.startswith((b"GIF87a", b"GIF89a")):
        mime = "image/gif"
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        mime = "image/webp"
    if mime is None:
        raise ValueError("该附件不是支持的PNG/JPEG/GIF/WebP图片")
    return {"type": "image", "mimeType": mime, "data": base64.b64encode(raw).decode("ascii")}


def ticket_store_path():
    return USER_DATA_DIR / "_tickets" / "tickets.json"


def _ticket_forum_topics_path():
    # The legacy forum store is shared (not per-user); mirror forum_store_path().
    return USER_DATA_DIR / "_forum" / "topics.json"


def ensure_tickets_migrated():
    """Move legacy platform_ticket topics from the forum store into the ticket store.

    Idempotent: once the ticket store file exists this is a no-op, so it is safe to
    call on every load. Backs up the forum store before rewriting it.
    """
    store = ticket_store_path()
    if office_doc_exists("workorder", store):
        return
    tickets = []
    forum_path = _ticket_forum_topics_path()
    data = office_doc_read("forum", forum_path, [])
    if isinstance(data, list):
        tickets = [dict(topic) for topic in data if topic.get("preset") == "platform_ticket"]
        if tickets:
            remaining = [topic for topic in data if topic.get("preset") != "platform_ticket"]
            backup = forum_path.with_name(
                "topics.json.bak-before-ticket-split-" + datetime.now().strftime("%Y%m%d-%H%M%S")
            )
            try:
                office_doc_write("forum", backup, data)
            except OSError:
                pass
            office_doc_write("forum", forum_path, remaining)
    # Drop the now-meaningless "preset" marker on migrated records.
    for ticket in tickets:
        ticket.pop("preset", None)
        ticket.pop("manual_pinned", None)
    office_doc_write("workorder", store, tickets)


def load_tickets():
    ensure_tickets_migrated()
    data = office_doc_read("workorder", ticket_store_path(), [])
    return data if isinstance(data, list) else []


def save_tickets(tickets):
    office_doc_write("workorder", ticket_store_path(), tickets)


def ticket_is_resolved(ticket):
    return any(str(comment.get("status", "") or "") == "resolved" for comment in ticket.get("comments", []))


def ticket_is_closed(ticket):
    """A work order is closed once it is resolved or explicitly not accepted."""
    return any(str(comment.get("status", "") or "") in {"resolved", "rejected"} for comment in ticket.get("comments", []))


def ticket_status(ticket):
    """Overall lifecycle: resolved / rejected (terminal) > accepted (受理中) > open (待处理)."""
    statuses = [str(comment.get("status", "") or "") for comment in ticket.get("comments", [])]
    if "resolved" in statuses:
        return "resolved"
    if "rejected" in statuses:
        return "rejected"
    if "accepted" in statuses:
        return "accepted"
    return "open"


def ticket_is_pinned(ticket):
    """Unfinished work orders float to the top; a ticket stops pinning once closed."""
    return not ticket_is_closed(ticket)


def ticket_sort_key(ticket):
    return (1 if ticket_is_pinned(ticket) else 0, str(ticket.get("updated_at", "")))


def ticket_public(ticket, with_comments=False):
    item = dict(ticket)
    comments = item.get("comments", [])
    item["attachments"] = [forum_public_attachment(att) for att in item.get("attachments", []) if att.get("id")]
    item["comment_count"] = len(comments)
    item["view_count"] = int(item.get("view_count", 0) or 0)
    item["module"] = str(ticket.get("module", "") or "")
    item["pinned"] = ticket_is_pinned(ticket)
    item["resolved"] = ticket_is_resolved(ticket)
    item["closed"] = ticket_is_closed(ticket)
    item["status"] = ticket_status(ticket)
    item.pop("preset", None)
    item.pop("manual_pinned", None)
    item.pop("likes", None)
    if with_comments:
        item["comments"] = [forum_public_comment(comment) for comment in comments]
    else:
        item.pop("comments", None)
    return item


def ticket_list(username):
    tickets = sorted(load_tickets(), key=ticket_sort_key, reverse=True)
    open_count = sum(1 for ticket in tickets if not ticket_is_closed(ticket))
    return {
        "ok": True,
        "tickets": [ticket_public(ticket) for ticket in tickets],
        "summary": {"total": len(tickets), "open": open_count, "closed": len(tickets) - open_count},
    }


def ticket_get(payload, username):
    ticket_id = str(payload.get("id", "") or "").strip()
    tickets = load_tickets()
    for ticket in tickets:
        if ticket.get("id") == ticket_id:
            ticket["view_count"] = int(ticket.get("view_count", 0) or 0) + 1
            save_tickets(tickets)
            return {"ok": True, "ticket": ticket_public(ticket, with_comments=True)}
    raise ValueError("工单不存在")


def ticket_create(payload, username):
    title = str(payload.get("title", "") or "").strip()
    body = str(payload.get("body", "") or "").strip()
    module = str(payload.get("module", "") or "").strip()[:40]
    source = str(payload.get("source", "") or "user").strip() or "user"
    if not module:
        raise ValueError("请选择该问题所属的助手 / 模块")
    if not title:
        raise ValueError("请填写工单标题")
    if not body:
        raise ValueError("请填写工单内容")
    now = datetime.now().isoformat(timespec="seconds")
    user = find_user(username) or {}
    ticket = {
        "id": secrets.token_urlsafe(10),
        "title": title,
        "body": body,
        "module": module,
        "source": source,
        "author": user.get("name") or username,
        "author_username": username,
        "created_at": now,
        "updated_at": now,
        "view_count": 0,
        "attachments": forum_save_attachments(payload.get("attachments", []) or []),
        "comments": [],
    }
    tickets = load_tickets()
    tickets.append(ticket)
    save_tickets(tickets)
    return {"ok": True, "ticket": ticket_public(ticket, with_comments=True)}


def ticket_add_comment(payload, username):
    ticket_id = str(payload.get("topic_id", "") or payload.get("ticket_id", "") or "").strip()
    content = str(payload.get("content", "") or "").strip()
    parent_id = str(payload.get("parent_id", "") or "").strip()
    status = str(payload.get("status", "") or "").strip()
    if status not in TICKET_COMMENT_STATUSES:
        status = ""
    if not ticket_id:
        raise ValueError("请选择工单")
    if not content:
        raise ValueError("请填写处理内容")
    tickets = load_tickets()
    user = find_user(username) or {}
    now = datetime.now().isoformat(timespec="seconds")
    for ticket in tickets:
        if ticket.get("id") == ticket_id:
            ticket.setdefault("comments", []).append({
                "id": secrets.token_urlsafe(8),
                "parent_id": parent_id,
                "author": user.get("name") or username,
                "content": content,
                "status": status,
                "attachments": forum_save_attachments(payload.get("attachments", []) or []),
                "created_at": now,
            })
            ticket["updated_at"] = now
            save_tickets(tickets)
            return {"ok": True, "ticket": ticket_public(ticket, with_comments=True)}
    raise ValueError("工单不存在")
