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


def ticket_store_path():
    ticket_dir = USER_DATA_DIR / "_tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    return ticket_dir / "tickets.json"


def _ticket_forum_topics_path():
    # The legacy forum store is shared (not per-user); mirror forum_store_path().
    return USER_DATA_DIR / "_forum" / "topics.json"


def ensure_tickets_migrated():
    """Move legacy platform_ticket topics from the forum store into the ticket store.

    Idempotent: once the ticket store file exists this is a no-op, so it is safe to
    call on every load. Backs up the forum store before rewriting it.
    """
    store = ticket_store_path()
    if store.exists():
        return
    tickets = []
    forum_path = _ticket_forum_topics_path()
    if forum_path.exists():
        try:
            data = read_json_lenient(forum_path)
        except Exception:
            data = []
        if isinstance(data, list):
            tickets = [dict(topic) for topic in data if topic.get("preset") == "platform_ticket"]
            if tickets:
                remaining = [topic for topic in data if topic.get("preset") != "platform_ticket"]
                backup = forum_path.with_name(
                    "topics.json.bak-before-ticket-split-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                )
                try:
                    backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except OSError:
                    pass
                forum_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
    # Drop the now-meaningless "preset" marker on migrated records.
    for ticket in tickets:
        ticket.pop("preset", None)
        ticket.pop("manual_pinned", None)
    store.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tickets():
    ensure_tickets_migrated()
    path = ticket_store_path()
    if not path.exists():
        return []
    try:
        data = read_json_lenient(path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_tickets(tickets):
    ticket_store_path().write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")


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
