"""Project cash-flow scenarios and regional receivable analysis."""

CASHFLOW_REGIONS = ("东区", "西区", "中区", "广东区", "未分区")
CASHFLOW_ENTRY_FIELDS = ("receivable", "received", "procurement", "special_procurement", "reimbursement", "personnel", "other", "guarantee")


def _cashflow_path(username):
    return user_root(safe_username(username)) / "cashflow_scenarios.json"


def _cashflow_items(username):
    items = office_doc_read("cashflow", _cashflow_path(username), [])
    return items if isinstance(items, list) else []


def _save_cashflow_items(username, items):
    office_doc_write("cashflow", _cashflow_path(username), items)


def _cashflow_history_path(username):
    return user_root(safe_username(username)) / "cashflow_history.json"


def _cashflow_history_data(username, ensure_ids=False):
    path = _cashflow_history_path(username)
    stored = office_doc_read("cashflow", path, {})
    if not isinstance(stored, dict):
        stored = {}
    records = stored.get("records") if isinstance(stored.get("records"), list) else []
    changed = False
    if ensure_ids:
        for record in records:
            if isinstance(record, dict) and not record.get("id"):
                record["id"] = "history-" + secrets.token_hex(8)
                changed = True
        if changed:
            office_doc_write("cashflow", path, stored)
    stored["records"] = records
    return stored


def _cashflow_region(value):
    name = str(value or "").strip()
    if name in {"广东", "广东代表处", "广东区"}:
        return "广东区"
    if name in CASHFLOW_REGIONS:
        return name
    return name if name and name not in {"0", "/", "未划分", "公司其他", "公司-其他"} else "未分区"


def _cash_number(value):
    try:
        return round(max(0, float(value or 0)), 2)
    except (TypeError, ValueError):
        return 0.0


def _cash_date(value):
    text = str(value or "").strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return ""


def _history_record(raw):
    if not isinstance(raw, dict):
        return None
    project_name = str(raw.get("project_name", "")).strip()
    customer = str(raw.get("customer", "")).strip()
    if not project_name and not customer:
        return None
    return {
        "id": str(raw.get("id", "")).strip()[:48],
        "region": _cashflow_region(raw.get("region")),
        "office": str(raw.get("office", "")).strip()[:80],
        "province": str(raw.get("province", "")).strip()[:50],
        "customer": customer[:120] or "未填写客户",
        "project_code": str(raw.get("project_code", "")).strip()[:80],
        "project_name": project_name[:160] or "未填写项目",
        "project_type": str(raw.get("project_type", "")).strip()[:60] or "其他回款",
        "contract_amount": _cash_number(raw.get("contract_amount")),
        "planned_amount": _cash_number(raw.get("planned_amount")),
        "received_amount": _cash_number(raw.get("received_amount")),
        "status": str(raw.get("status", "")).strip()[:40] or "未回款",
        "contract_date": _cash_date(raw.get("contract_date")),
        "planned_date": _cash_date(raw.get("planned_date")),
        "received_date": _cash_date(raw.get("received_date")),
        "is_difficult": bool(raw.get("is_difficult")),
        "is_long_term": bool(raw.get("is_long_term")),
    }


def _history_scale(amount):
    if amount < 1_000_000: return "100万以下"
    if amount < 5_000_000: return "100万–500万"
    if amount < 10_000_000: return "500万–1000万"
    return "1000万以上"


def cashflow_history_import(payload, username):
    raw_records = payload.get("records") or []
    if not isinstance(raw_records, list):
        raise ValueError("历史回款数据格式不正确")
    records = [record for record in (_history_record(item) for item in raw_records) if record]
    for record in records:
        record["id"] = record["id"] or "history-" + secrets.token_hex(8)
    if not records:
        raise ValueError("未识别到可导入的历史回款记录")
    data = {"source_name": str(payload.get("source_name", "历史回款数据")).strip()[:160],
            "imported_at": datetime.now().isoformat(timespec="seconds"), "records": records}
    office_doc_write("cashflow", _cashflow_history_path(username), data)
    return {"ok": True, "imported": len(records), "source_name": data["source_name"]}


def cashflow_history_list(username):
    stored = _cashflow_history_data(username, ensure_ids=True)
    records = [record for record in (_history_record(item) for item in (stored.get("records") or [])) if record]
    summary = {"records": len(records), "projects": len({x["project_code"] or x["project_name"] for x in records}), "planned_amount": 0, "received_amount": 0, "unpaid_amount": 0, "received_rate": 0, "average_collection_days": None}
    grouped = {"by_region": {}, "by_customer": {}, "by_project_type": {}, "by_scale": {}, "by_status": {}, "by_year": {}}
    project_risks = {}
    intervals = []
    for item in records:
        planned = item["planned_amount"]
        received = item["received_amount"]
        unpaid = max(0, planned - received)
        summary["planned_amount"] += planned; summary["received_amount"] += received; summary["unpaid_amount"] += unpaid
        project_key = item["project_code"] or item["project_name"]
        project = project_risks.setdefault(project_key, {"name": item["project_name"], "project_code": item["project_code"], "customer": item["customer"], "region": item["region"], "records": 0, "planned": 0, "received": 0, "unpaid": 0, "received_rate": 0, "difficult": 0, "long_term": 0})
        project["records"] += 1; project["planned"] += planned; project["received"] += received; project["unpaid"] += unpaid
        project["difficult"] += int(item["is_difficult"]); project["long_term"] += int(item["is_long_term"])
        if item["contract_date"] and item["received_date"] and received > 0:
            intervals.append((datetime.strptime(item["received_date"], "%Y-%m-%d").date() - datetime.strptime(item["contract_date"], "%Y-%m-%d").date()).days)
        year = (item["received_date"] or item["planned_date"] or item["contract_date"])[:4] or "未标注"
        for key, name in (("by_region", item["region"]), ("by_customer", item["customer"]), ("by_project_type", item["project_type"]), ("by_scale", _history_scale(item["contract_amount"])), ("by_status", item["status"]), ("by_year", year)):
            group = grouped[key].setdefault(name, {"name": name, "records": 0, "planned": 0, "received": 0, "unpaid": 0, "received_rate": 0, "difficult": 0, "long_term": 0, "collection_days_total": 0, "collection_days_count": 0, "collection_days_values": [], "schedule_variance_values": [], "scheduled_count": 0, "on_time_count": 0, "average_collection_days": None})
            group["records"] += 1; group["planned"] += planned; group["received"] += received; group["unpaid"] += unpaid
            group["difficult"] += int(item["is_difficult"]); group["long_term"] += int(item["is_long_term"])
            if key == "by_customer":
                type_amounts = group.setdefault("type_amounts", {})
                type_amounts[item["project_type"]] = round(type_amounts.get(item["project_type"], 0) + planned, 2)
            if item["contract_date"] and item["received_date"] and received > 0:
                days = (datetime.strptime(item["received_date"], "%Y-%m-%d").date() - datetime.strptime(item["contract_date"], "%Y-%m-%d").date()).days
                group["collection_days_total"] += days
                group["collection_days_count"] += 1
                if key == "by_customer": group["collection_days_values"].append(days)
            if item["planned_date"] and item["received_date"] and received > 0:
                variance_days = (datetime.strptime(item["received_date"], "%Y-%m-%d").date() - datetime.strptime(item["planned_date"], "%Y-%m-%d").date()).days
                group["scheduled_count"] += 1
                group["on_time_count"] += int(variance_days <= 0)
                if key == "by_customer": group["schedule_variance_values"].append(variance_days)
    summary["planned_amount"] = round(summary["planned_amount"], 2); summary["received_amount"] = round(summary["received_amount"], 2); summary["unpaid_amount"] = round(summary["unpaid_amount"], 2)
    summary["received_rate"] = round(summary["received_amount"] / summary["planned_amount"] * 100, 1) if summary["planned_amount"] else 0
    summary["average_collection_days"] = round(sum(intervals) / len(intervals)) if intervals else None
    for groups in grouped.values():
        for group in groups.values():
            group["planned"] = round(group["planned"], 2); group["received"] = round(group["received"], 2); group["unpaid"] = round(group["unpaid"], 2)
            group["received_rate"] = round(group["received"] / group["planned"] * 100, 1) if group["planned"] else 0
            group["average_collection_days"] = round(group["collection_days_total"] / group["collection_days_count"]) if group["collection_days_count"] else None
    for project in project_risks.values():
        project["planned"] = round(project["planned"], 2); project["received"] = round(project["received"], 2); project["unpaid"] = round(project["unpaid"], 2)
        project["received_rate"] = round(project["received"] / project["planned"] * 100, 1) if project["planned"] else 0
    order = lambda data: sorted(data.values(), key=lambda x: (x["unpaid"], -x["received_rate"]), reverse=True)
    def percentile(values, ratio):
        values = sorted(values)
        return values[round((len(values) - 1) * ratio)] if values else None

    def payment_bucket(name):
        text = str(name or "")
        if any(key in text for key in ("预付", "预付款", "首款", "定金")): return "前期款"
        if any(key in text for key in ("到货", "发货")): return "到货款"
        if any(key in text for key in ("验收", "试运行", "开通", "初验")): return "验收/开通款"
        if any(key in text for key in ("质保", "保修")): return "质保款"
        if any(key in text for key in ("结算", "终验", "尾款")): return "结算/尾款"
        return "其他节点"

    customer_profiles = []
    for customer in grouped["by_customer"].values():
        traits = []
        if customer["received_rate"] >= 90: traits.append("回款稳定")
        elif customer["received_rate"] < 70: traits.append("回款压力较高")
        else: traits.append("需持续跟踪")
        if customer["average_collection_days"] and customer["average_collection_days"] >= 180: traits.append("账期偏长")
        if customer["unpaid"] > customer["planned"] * 0.2: traits.append("待回款占比较高")
        if customer["difficult"] or customer["long_term"]: traits.append("含风险节点")
        if customer["received_rate"] < 70 or customer["unpaid"] > customer["planned"] * 0.2:
            recommendation = "测算采用保守回款节奏，回款节点宜后置，并为待回款预留资金缓冲。"
        elif customer["average_collection_days"] and customer["average_collection_days"] >= 120:
            recommendation = f"测算至少按约 {customer['average_collection_days']} 天的历史账期安排，验收及质保款不要提前计入可用现金。"
        else:
            recommendation = "可将历史回款节奏作为基准，但仍应把验收、质保等条件性回款独立列示。"
        patterns = sorted(customer.get("type_amounts", {}).items(), key=lambda item: item[1], reverse=True)
        cycles = customer.get("collection_days_values", [])
        stage_amounts = {}
        for name, amount in patterns:
            bucket = payment_bucket(name)
            stage_amounts[bucket] = stage_amounts.get(bucket, 0) + amount
        p75_days = percentile(cycles, .75)
        risk_score = min(100, round(
            max(0, 100 - customer["received_rate"]) * .35 +
            (customer["unpaid"] / customer["planned"] * 30 if customer["planned"] else 0) +
            (min(p75_days or 0, 720) / 720 * 25) +
            ((customer["difficult"] + customer["long_term"]) / customer["records"] * 10 if customer["records"] else 0)
        ))
        risk_level = "高" if risk_score >= 65 else "中" if risk_score >= 35 else "低"
        schedule_variances = customer.get("schedule_variance_values", [])
        on_time_rate = round(customer["on_time_count"] / customer["scheduled_count"] * 100, 1) if customer["scheduled_count"] else None
        cycle_reference = f"中位账期{percentile(cycles, .5)}天、P75账期{p75_days}天" if cycles else "暂无有效账期样本"
        schedule_reference = f"按期率{on_time_rate}%、计划偏差中位{percentile(schedule_variances, .5)}天" if schedule_variances else "暂无应收计划日期样本（可在历史表补录）"
        collection_factor = round(max(.4, min(.95, customer["received_rate"] / 100 * (1 - risk_score / 250))), 2)
        quantitative_guidance = f"量化基准：{cycle_reference}；{schedule_reference}；资金风险分{risk_score}/100（{risk_level}）；建议回款折算系数{round(collection_factor * 100)}%。"
        customer_profiles.append({**customer, "traits": traits,
                                  "median_collection_days": percentile(cycles, .5), "p75_collection_days": p75_days,
                                  "p90_collection_days": percentile(cycles, .9), "collection_sample_count": len(cycles),
                                  "on_time_collection_rate": on_time_rate, "median_schedule_variance_days": percentile(schedule_variances, .5), "schedule_sample_count": len(schedule_variances),
                                  "cashflow_risk_score": risk_score, "cashflow_risk_level": risk_level,
                                  "recommended_collection_factor": collection_factor,
                                  "recommendation": quantitative_guidance + recommendation,
                                  "payment_patterns": [{"name": name, "amount": amount, "share": round(amount / customer["planned"] * 100, 1) if customer["planned"] else 0} for name, amount in patterns[:5]],
                                  "stage_mix": [{"name": name, "share": round(amount / customer["planned"] * 100, 1) if customer["planned"] else 0} for name, amount in sorted(stage_amounts.items(), key=lambda item: item[1], reverse=True)]})
    customer_profiles.sort(key=lambda item: (item["planned"], item["records"]), reverse=True)
    return {"ok": True, "source_name": stored.get("source_name", ""), "imported_at": stored.get("imported_at", ""), "summary": summary,
            "insights": cashflow_history_insights(records),
            "by_region": order(grouped["by_region"]), "by_customer": order(grouped["by_customer"]),
            "by_project_type": order(grouped["by_project_type"]), "by_scale": order(grouped["by_scale"]),
            "by_status": sorted(grouped["by_status"].values(), key=lambda x: x["received"], reverse=True),
            "by_year": sorted(grouped["by_year"].values(), key=lambda x: x["name"]), "customer_profiles": customer_profiles,
            "project_risks": sorted(project_risks.values(), key=lambda item: (item["unpaid"], item["difficult"] + item["long_term"], -item["received_rate"]), reverse=True)}


def cashflow_history_records(username, keyword="", region="", page=1, page_size=50):
    stored = _cashflow_history_data(username, ensure_ids=True)
    records = [record for record in (_history_record(item) for item in stored["records"]) if record]
    keyword = str(keyword or "").strip().lower()
    region = _cashflow_region(region) if region else ""
    if keyword:
        records = [item for item in records if keyword in " ".join(str(item.get(key, "")).lower() for key in ("project_name", "customer", "project_code", "project_type"))]
    if region:
        records = [item for item in records if item["region"] == region]
    records.sort(key=lambda item: (item.get("received_date", ""), item.get("planned_date", ""), item["project_name"]), reverse=True)
    try: page = max(1, int(page))
    except (TypeError, ValueError): page = 1
    try: page_size = min(100, max(10, int(page_size)))
    except (TypeError, ValueError): page_size = 50
    start = (page - 1) * page_size
    return {"ok": True, "items": records[start:start + page_size], "total": len(records), "page": page, "page_size": page_size}


def cashflow_history_save(payload, username):
    record = _history_record(payload)
    if not record:
        raise ValueError("请至少填写项目名称或客户")
    stored = _cashflow_history_data(username, ensure_ids=True)
    record_id = str(payload.get("id", "")).strip()
    existing = next((item for item in stored["records"] if isinstance(item, dict) and item.get("id") == record_id), None)
    if existing is None:
        record["id"] = "history-" + secrets.token_hex(8)
        stored["records"].append(record)
    else:
        record["id"] = existing["id"]
        existing.clear()
        existing.update(record)
    office_doc_write("cashflow", _cashflow_history_path(username), stored)
    return {"ok": True, "item": record}


def cashflow_history_delete(record_id, username):
    stored = _cashflow_history_data(username, ensure_ids=True)
    remained = [item for item in stored["records"] if not isinstance(item, dict) or item.get("id") != str(record_id)]
    if len(remained) == len(stored["records"]):
        raise ValueError("历史回款记录不存在")
    stored["records"] = remained
    office_doc_write("cashflow", _cashflow_history_path(username), stored)
    return {"ok": True}


def _cashflow_entry(raw):
    if not isinstance(raw, dict):
        raise ValueError("资金节点格式不正确")
    date = str(raw.get("date", "")).strip()[:10]
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("请为每个资金节点填写 YYYY-MM-DD 日期")
    entry = {"id": str(raw.get("id", "")).strip()[:40] or "cash-" + secrets.token_hex(4),
             "date": date, "milestone": str(raw.get("milestone", "")).strip()[:120]}
    entry.update({name: _cash_number(raw.get(name)) for name in CASHFLOW_ENTRY_FIELDS})
    return entry


def _calculate_cashflow(entries, annual_rate):
    balance = 0.0
    funding_gap = 0.0
    funding_cost = 0.0
    calculated = []
    ordered = sorted(entries, key=lambda x: (x["date"], x["id"]))
    for index, item in enumerate(ordered):
        cost = sum(item[name] for name in CASHFLOW_ENTRY_FIELDS if name not in {"receivable", "received"})
        # 测算采用计划回款；实际已回款单独用于经营分析，不能覆盖计划节奏。
        net = round(item["receivable"] - cost, 2)
        balance = round(balance + net, 2)
        funding_gap = max(funding_gap, -balance)
        days = 0
        if index + 1 < len(ordered):
            days = max(0, (datetime.strptime(ordered[index + 1]["date"], "%Y-%m-%d") - datetime.strptime(item["date"], "%Y-%m-%d")).days)
        period_cost = round(max(0, -balance) * annual_rate * days / 365, 2)
        funding_cost += period_cost
        calculated.append({**item, "payment": round(cost, 2), "net_cashflow": net,
                           "cumulative_cashflow": balance, "funding_cost": period_cost})
    total_receivable = round(sum(x["receivable"] for x in ordered), 2)
    total_received = round(sum(x["received"] for x in ordered), 2)
    total_payment = round(sum(x["payment"] for x in calculated), 2)
    return calculated, {"total_receivable": total_receivable, "total_received": total_received,
                        "outstanding": max(0, round(total_receivable - total_received, 2)),
                        "total_payment": total_payment, "funding_gap": round(funding_gap, 2),
                        "funding_cost": round(funding_cost, 2), "ending_cashflow": round(balance, 2)}


def _cashflow_normalize(raw):
    if not isinstance(raw, dict):
        raise ValueError("测算数据格式不正确")
    project_name = str(raw.get("project_name", "")).strip()
    if not project_name:
        raise ValueError("请填写项目名称")
    region = str(raw.get("region", "未分区")).strip() or "未分区"
    if region not in CASHFLOW_REGIONS:
        region = "未分区"
    try:
        annual_rate = float(raw.get("annual_rate", 0.06) or 0.06)
    except (TypeError, ValueError):
        annual_rate = 0.06
    annual_rate = min(max(annual_rate, 0), 1)
    entries = [_cashflow_entry(x) for x in (raw.get("entries") or [])]
    calculated, summary = _calculate_cashflow(entries, annual_rate)
    return {"project_name": project_name[:120], "project_code": str(raw.get("project_code", "")).strip()[:80],
            "region": region, "customer": str(raw.get("customer", "")).strip()[:120],
            "owner": str(raw.get("owner", "")).strip()[:60], "annual_rate": annual_rate,
            "note": str(raw.get("note", "")).strip()[:1000], "entries": calculated, "summary": summary}


def cashflow_list(username):
    items = [_cashflow_normalize(item) | {"id": item.get("id", ""), "created_at": item.get("created_at", ""), "updated_at": item.get("updated_at", "")} for item in _cashflow_items(username)]
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    summary = {"total": len(items), "total_receivable": 0, "total_received": 0, "outstanding": 0, "funding_gap": 0, "funding_cost": 0}
    groups = {"by_region": {}, "by_customer": {}}
    for item in items:
        data = item["summary"]
        for key in summary:
            if key != "total": summary[key] = round(summary[key] + data.get(key, 0), 2)
        for group_key, name in (("by_region", item["region"]), ("by_customer", item["customer"] or "未填写客户")):
            group = groups[group_key].setdefault(name, {"name": name, "projects": 0, "receivable": 0, "received": 0, "outstanding": 0, "funding_gap": 0})
            group["projects"] += 1
            group["receivable"] = round(group["receivable"] + data["total_receivable"], 2)
            group["received"] = round(group["received"] + data["total_received"], 2)
            group["outstanding"] = round(group["outstanding"] + data["outstanding"], 2)
            group["funding_gap"] = max(group["funding_gap"], data["funding_gap"])
    return {"ok": True, "items": items, "summary": summary,
            "by_region": sorted(groups["by_region"].values(), key=lambda x: x["outstanding"], reverse=True),
            "by_customer": sorted(groups["by_customer"].values(), key=lambda x: x["outstanding"], reverse=True)}


def cashflow_save(payload, username):
    item = _cashflow_normalize(payload)
    now = datetime.now().isoformat(timespec="seconds")
    item_id = str(payload.get("id", "")).strip()
    items = _cashflow_items(username)
    existing = next((x for x in items if x.get("id") == item_id), None)
    if existing is None:
        item["id"] = "cashflow-" + secrets.token_hex(6)
        item["created_at"] = now
        item["updated_at"] = now
        items.append(item)
    else:
        item["id"] = existing["id"]
        item["created_at"] = existing.get("created_at", now)
        item["updated_at"] = now
        existing.clear()
        existing.update(item)
    _save_cashflow_items(username, items)
    return {"ok": True, "item": item}


def cashflow_delete(item_id, username):
    items = _cashflow_items(username)
    remained = [x for x in items if x.get("id") != str(item_id)]
    if len(items) == len(remained):
        raise ValueError("资金测算不存在")
    _save_cashflow_items(username, remained)
    return {"ok": True}
