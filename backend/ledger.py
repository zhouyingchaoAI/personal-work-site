"""Operating ledger assistant: project, contract, delivery and payment tracking."""

LEDGER_STAGES = {"机会", "合同", "采购", "交付", "验收", "回款", "关闭"}
LEDGER_STATUSES = {"正常", "关注", "逾期", "已完成"}

def _ledger_path(username):
    username = safe_username(username)
    return user_root(username) / "operating_ledger.json"

def _ledger_items(username):
    data = office_doc_read("ledger", _ledger_path(username), [])
    return data if isinstance(data, list) else []

def _save_ledger(username, items):
    office_doc_write("ledger", _ledger_path(username), items)

def ledger_list(username):
    items = _ledger_items(username)
    items.sort(key=lambda x: (x.get("status") == "逾期", x.get("updated_at", "")), reverse=True)
    summary = {"total": len(items), "normal": 0, "attention": 0, "overdue": 0, "contract_amount": 0, "received_amount": 0, "remaining_amount": 0, "pending_documents": 0, "follow_up_due": 0}
    today = datetime.now().date().isoformat()
    for item in items:
        item.setdefault("document_checklist", [])
        item.setdefault("payment_progress", "")
        item.setdefault("last_follow_up", "")
        item.setdefault("customer_contact", "")
        item["remaining_amount"] = max(0, float(item.get("contract_amount") or 0) - float(item.get("received_amount") or 0))
        item["pending_document_count"] = sum(1 for doc in item["document_checklist"] if not doc.get("completed"))
        deadlines = [item.get(k, "") for k in ("delivery_due", "acceptance_due", "payment_due")]
        if item.get("status") not in {"已完成", "逾期"} and any(day and day < today for day in deadlines): item["status"] = "逾期"
        status = item.get("status", "正常")
        summary[{"正常":"normal", "关注":"attention", "逾期":"overdue"}.get(status, "normal")] += 1
        summary["contract_amount"] += float(item.get("contract_amount") or 0)
        summary["received_amount"] += float(item.get("received_amount") or 0)
        summary["remaining_amount"] += item["remaining_amount"]
        summary["pending_documents"] += item["pending_document_count"]
        if item.get("last_follow_up") and item["last_follow_up"] < today: summary["follow_up_due"] += 1
    return {"ok": True, "items": items, "summary": summary}

def ledger_save(payload, username):
    title = str(payload.get("project_name", "")).strip()
    if not title: raise ValueError("请填写项目名称")
    now = datetime.now().isoformat(timespec="seconds")
    item_id = str(payload.get("id", "")).strip()
    items = _ledger_items(username)
    item = next((x for x in items if x.get("id") == item_id), None)
    if item is None:
        item = {"id": "ledger-" + secrets.token_hex(6), "created_at": now}
        items.append(item)
    item.update({
        "project_name": title[:120], "project_code": str(payload.get("project_code", "")).strip()[:80],
        "customer": str(payload.get("customer", "")).strip()[:120],
        "owner": str(payload.get("owner", "")).strip()[:60],
        "stage": str(payload.get("stage", "机会")) if str(payload.get("stage", "机会")) in LEDGER_STAGES else "机会",
        "status": str(payload.get("status", "正常")) if str(payload.get("status", "正常")) in LEDGER_STATUSES else "正常",
        "contract_amount": float(payload.get("contract_amount") or 0), "received_amount": float(payload.get("received_amount") or 0),
        "contract_date": str(payload.get("contract_date", ""))[:20], "delivery_due": str(payload.get("delivery_due", ""))[:20],
        "acceptance_due": str(payload.get("acceptance_due", ""))[:20], "payment_due": str(payload.get("payment_due", ""))[:20],
        "next_action": str(payload.get("next_action", "")).strip()[:1000], "risk_note": str(payload.get("risk_note", "")).strip()[:1000], "updated_at": now,
        "payment_progress": str(payload.get("payment_progress", "")).strip()[:1000], "last_follow_up": str(payload.get("last_follow_up", ""))[:20],
        "customer_contact": str(payload.get("customer_contact", "")).strip()[:500],
        "document_checklist": [
            {"name": str(doc.get("name", ""))[:80], "completed": bool(doc.get("completed"))}
            for doc in (payload.get("document_checklist") or []) if isinstance(doc, dict) and str(doc.get("name", "")).strip()
        ],
    })
    _save_ledger(username, items)
    return {"ok": True, "item": item}

def ledger_delete(item_id, username):
    items = _ledger_items(username)
    remained = [x for x in items if x.get("id") != str(item_id)]
    if len(remained) == len(items): raise ValueError("台账记录不存在")
    _save_ledger(username, remained)
    return {"ok": True}
