"""Collection-pattern insights over imported historical receivables.

Four conclusions, each computed from the history records rather than asserted:
1. amount tiers: larger integration projects close their collection loop later;
2. general-contractor behaviour: some customers pay slower and tie up our working capital;
3. customer credit rating that feeds contract negotiation terms;
4. standard collection models: payment-split patterns with probability and per-node timing.
Only project-level facts are used; a project's cycle runs from its contract date to its last
recorded receipt, and open projects are reported separately instead of being treated as closed.
"""

INSIGHT_TIERS = (("100万以下", 0, 1_000_000), ("100万–500万", 1_000_000, 5_000_000), ("500万以上", 5_000_000, float("inf")))
INSIGHT_BUCKETS = ("前期款", "进度款", "到货款", "验收/开通款", "结算/尾款", "质保款", "服务期款", "其他节点")
INSIGHT_PLACEHOLDER_CUSTOMERS = ("年度订货", "未填写客户")
INSIGHT_FUNDING_RATE = 0.04  # 仅用于估算资金占用成本，页面明示口径


def _insight_bucket(name):
    text = str(name or "")
    if any(key in text for key in ("预付", "首款", "定金")): return "前期款"
    if any(key in text for key in ("维保", "运维", "服务费", "驻场", "年费", "季度", "半年")): return "服务期款"
    if "进度" in text: return "进度款"
    if any(key in text for key in ("到货", "发货")): return "到货款"
    if any(key in text for key in ("验收", "试运行", "开通", "初验")): return "验收/开通款"
    if any(key in text for key in ("结算", "终验", "尾款")): return "结算/尾款"
    if any(key in text for key in ("质保", "保修")): return "质保款"
    return "其他节点"


def _insight_pct(values, ratio):
    values = sorted(v for v in values if v is not None)
    return values[round((len(values) - 1) * ratio)] if values else None


def _insight_days(start, end):
    try:
        return (datetime.strptime(end, "%Y-%m-%d").date() - datetime.strptime(start, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return None


def _insight_projects(records, today):
    projects = {}
    for item in records:
        key = (item["customer"], item["project_code"] or item["project_name"])
        p = projects.setdefault(key, {"name": item["project_name"], "customer": item["customer"], "region": item["region"],
                                      "contract_amount": 0, "contract_date": "", "planned": 0, "received": 0, "nodes": []})
        p["contract_amount"] = max(p["contract_amount"], item["contract_amount"])
        if item["contract_date"] and (not p["contract_date"] or item["contract_date"] < p["contract_date"]):
            p["contract_date"] = item["contract_date"]
        p["planned"] += item["planned_amount"]; p["received"] += item["received_amount"]
        p["nodes"].append(item)
    for p in projects.values():
        received_dates = [n["received_date"] for n in p["nodes"] if n["received_date"] and n["received_amount"] > 0]
        p["closed"] = p["planned"] > 0 and p["received"] >= p["planned"] * 0.98
        p["last_received"] = max(received_dates) if received_dates else ""
        p["cycle_days"] = _insight_days(p["contract_date"], p["last_received"]) if p["closed"] and p["contract_date"] and p["last_received"] else None
        if p["cycle_days"] is not None and p["cycle_days"] < 0: p["cycle_days"] = None
        p["open_days"] = _insight_days(p["contract_date"], today) if not p["closed"] and p["contract_date"] else None
        first = min(received_dates) if received_dates else ""
        p["first_days"] = _insight_days(p["contract_date"], first) if first and p["contract_date"] else None
        # 资金占用（元·年）：已回部分按实际回款时长，未回部分按合同日至今计。
        occupied = 0.0
        for n in p["nodes"]:
            if n["received_amount"] > 0 and n["received_date"] and p["contract_date"]:
                d = _insight_days(p["contract_date"], n["received_date"]) or 0
                occupied += n["received_amount"] * max(0, d) / 365
            unpaid = max(0, n["planned_amount"] - n["received_amount"])
            if unpaid and p["contract_date"]:
                occupied += unpaid * max(0, _insight_days(p["contract_date"], today) or 0) / 365
        p["occupied_year"] = occupied
    return list(projects.values())


def _insight_tiers(projects):
    rows = []
    for name, low, high in INSIGHT_TIERS:
        group = [p for p in projects if low <= p["contract_amount"] < high and p["contract_amount"] > 0]
        cycles = [p["cycle_days"] for p in group if p["cycle_days"] is not None]
        firsts = [p["first_days"] for p in group if p["first_days"] is not None]
        planned = sum(p["planned"] for p in group); received = sum(p["received"] for p in group)
        rows.append({"name": name, "projects": len(group), "closed_projects": len(cycles),
                     "median_cycle_days": _insight_pct(cycles, .5), "p75_cycle_days": _insight_pct(cycles, .75),
                     "median_first_days": _insight_pct(firsts, .5),
                     "avg_nodes": round(sum(len(p["nodes"]) for p in group) / len(group), 1) if group else None,
                     "received_rate": round(received / planned * 100, 1) if planned else 0,
                     "open_projects": sum(1 for p in group if not p["closed"])})
    return rows


def _insight_bucket_medians(projects):
    days = {}
    for p in projects:
        for n in p["nodes"]:
            if n["received_amount"] > 0 and n["received_date"] and p["contract_date"]:
                d = _insight_days(p["contract_date"], n["received_date"])
                if d is not None and d >= 0: days.setdefault(_insight_bucket(n["project_type"]), []).append(d)
    return {b: _insight_pct(v, .5) for b, v in days.items() if len(v) >= 5}


def _insight_customers(projects, bucket_medians, today):
    grouped = {}
    for p in projects:
        grouped.setdefault(p["customer"], []).append(p)
    rows = []
    for name, items in grouped.items():
        planned = sum(p["planned"] for p in items)
        if len(items) < 2 or planned <= 0: continue
        nodes = [(p, n) for p in items for n in p["nodes"]]
        node_days, weighted, weight = [], 0.0, 0.0
        for p, n in nodes:
            if n["received_amount"] > 0 and n["received_date"] and p["contract_date"]:
                d = _insight_days(p["contract_date"], n["received_date"])
                if d is None or d < 0: continue
                node_days.append(d)
                base = bucket_medians.get(_insight_bucket(n["project_type"]))
                if base:  # 与全公司同类回款节点的中位账期相比，按金额加权
                    weighted += n["received_amount"] * d / base; weight += n["received_amount"]
        received = sum(p["received"] for p in items)
        # 逾期未回：签约满一年仍未回的金额占比，避免把刚签约、尚未到期的款项算成“回款差”。
        overdue = sum(max(0, p["planned"] - p["received"]) for p in items if p["contract_date"] and (_insight_days(p["contract_date"], today) or 0) >= 365)
        prepay = sum(n["planned_amount"] for _, n in nodes if _insight_bucket(n["project_type"]) == "前期款")
        occupied = sum(p["occupied_year"] for p in items)
        rows.append({"name": name, "projects": len(items), "nodes": len(nodes), "planned": round(planned, 2), "received": round(received, 2),
                     "unpaid": round(max(0, planned - received), 2), "received_rate": round(received / planned * 100, 1),
                     "overdue_share": round(overdue / planned * 100, 1),
                     "median_node_days": _insight_pct(node_days, .5), "p75_node_days": _insight_pct(node_days, .75),
                     "cycle_index": round(weighted / weight, 2) if weight else None,
                     "occupancy_years": round(occupied / planned, 2),
                     "median_cycle_days": _insight_pct([p["cycle_days"] for p in items if p["cycle_days"] is not None], .5),
                     "prepay_share": round(prepay / planned * 100, 1),
                     "occupied_year": round(occupied, 2), "funding_cost": round(occupied * INSIGHT_FUNDING_RATE, 2),
                     "_enough": len(items) >= 3 and weight > 0 and planned >= 1_000_000})
    rated = [r for r in rows if r["_enough"]]
    base_index = _insight_pct([r["cycle_index"] for r in rated], .5) or 1
    base_occ = _insight_pct([r["occupancy_years"] for r in rated], .5) or 1
    for r in rows:
        r["cycle_vs_company"] = round(r["cycle_index"] / base_index, 2) if r["cycle_index"] else None
        r["occupancy_vs_company"] = round(r["occupancy_years"] / base_occ, 2)
        if r.pop("_enough"):
            # 信用分（满分 100）：同类节点账期相对公司水平、每元回款资金占用时长相对公司水平、逾期未回占比、预付比例。
            score = 100 - min(40, max(0, r["cycle_vs_company"] - 1) * 45) - min(30, max(0, r["occupancy_vs_company"] - 1) * 25) \
                    - min(25, r["overdue_share"] * 0.6) - max(0, 20 - r["prepay_share"]) * 0.4
            r["credit_score"] = round(max(0, min(100, score)))
            r["credit_grade"] = "A" if r["credit_score"] >= 90 else "B" if r["credit_score"] >= 75 else "C" if r["credit_score"] >= 60 else "D"
            r["terms"] = _insight_terms(r["credit_grade"], r["prepay_share"], r["cycle_vs_company"])
        else:
            r["credit_score"], r["credit_grade"] = None, "样本不足"
            r["terms"] = "历史项目少于 3 个或累计金额不足 100 万，暂不评级，参考同金额档位基线。"
    rank = {"D": 0, "C": 1, "B": 2, "A": 3, "样本不足": 4}
    rows.sort(key=lambda r: (rank[r["credit_grade"]], -r["funding_cost"]))
    return rows, base_index, base_occ


def _insight_terms(grade, prepay_share, index):
    if grade == "A":
        return "可按公司标准条款签约，维持现有回款节奏。"
    if grade == "B":
        extra = f"同类节点比公司平均慢约 {round((index - 1) * 100)}%，" if index and index > 1.1 else ""
        return extra + "签约时明确各节点回款时限，验收款约定到期付款日，避免无限期挂账。"
    lines = []
    if prepay_share < 20: lines.append(f"历史预付仅约 {prepay_share:.0f}%，谈判争取预付不低于 20%–30%")
    if index and index > 1.1: lines.append(f"同类回款节点比公司平均慢约 {round((index - 1) * 100)}%，约定验收后付款时限并设逾期违约金")
    lines.append("减少背靠背条款，质保金可用保函替代")
    if grade == "D": lines.append("新项目立项前做垫资测算，超出资金预算需审批")
    return "；".join(lines) + "。"


def _insight_patterns(projects):
    order = {name: i for i, name in enumerate(INSIGHT_BUCKETS)}
    sample = [p for p in projects if p["planned"] > 0 and p["contract_date"] and p["contract_amount"] > 0 and 0.9 <= p["planned"] / p["contract_amount"] <= 1.1]
    counter = {}
    for p in sample:
        shares = {}
        for n in p["nodes"]:
            b = _insight_bucket(n["project_type"])
            shares[b] = shares.get(b, 0) + n["planned_amount"]
        parts = []
        for b in sorted(shares, key=lambda x: order[x]):
            pct = round(shares[b] / p["planned"] * 20) * 5  # 取整到 5%
            if pct > 0: parts.append((b, pct))
        if len(parts) == 1 and parts[0][0] == "其他节点": continue
        if not parts: continue
        signature = " → ".join(f"{b} {pct}%" for b, pct in parts)
        entry = counter.setdefault(signature, {"signature": signature, "stages": [b for b, _ in parts], "shares": [pct for _, pct in parts],
                                               "projects": 0, "cycles": [], "stage_days": {b: [] for b, _ in parts}, "amounts": []})
        entry["projects"] += 1
        entry["amounts"].append(p["contract_amount"])
        if p["cycle_days"] is not None: entry["cycles"].append(p["cycle_days"])
        for n in p["nodes"]:
            b = _insight_bucket(n["project_type"])
            if b in entry["stage_days"] and n["received_amount"] > 0 and n["received_date"]:
                d = _insight_days(p["contract_date"], n["received_date"])
                if d is not None and d >= 0: entry["stage_days"][b].append(d)
    total = len(sample) or 1
    rows = []
    for e in sorted(counter.values(), key=lambda x: x["projects"], reverse=True)[:8]:
        rows.append({"signature": e["signature"], "projects": e["projects"], "probability": round(e["projects"] / total * 100, 1),
                     "nodes": [{"stage": b, "share": s, "median_days": _insight_pct(e["stage_days"][b], .5), "samples": len(e["stage_days"][b])}
                               for b, s in zip(e["stages"], e["shares"])],
                     "median_cycle_days": _insight_pct(e["cycles"], .5), "closed_projects": len(e["cycles"]),
                     "median_contract_amount": _insight_pct(e["amounts"], .5)})
    return rows, len(sample)


def cashflow_history_insights(records):
    today = datetime.now().date().isoformat()
    records = [r for r in records if not any(mark in r["customer"] for mark in INSIGHT_PLACEHOLDER_CUSTOMERS)]
    projects = _insight_projects(records, today)
    bucket_medians = _insight_bucket_medians(projects)
    tiers = _insight_tiers(projects)
    customers, base_index, base_occ = _insight_customers(projects, bucket_medians, today)
    patterns, pattern_sample = _insight_patterns(projects)
    conclusions = []
    small, large = tiers[0], tiers[-1]
    if small["median_cycle_days"] is not None and large["median_cycle_days"] is not None:
        conclusions.append({"key": "amount", "title": "项目金额与回款周期强相关",
                            "text": f"500万以上项目回款闭环中位 {large['median_cycle_days']} 天，100万以下项目 {small['median_cycle_days']} 天；按金额档位设定回款基线。"})
    rated = [c for c in customers if c["credit_score"] is not None]
    slow = [c for c in rated if c["credit_grade"] in ("C", "D")]
    laggards = sorted([c for c in rated if (c["cycle_vs_company"] or 0) > 1.1 or c["occupancy_vs_company"] > 1.3], key=lambda c: c["funding_cost"], reverse=True)[:3]
    if laggards:
        conclusions.append({"key": "customer", "title": "总包客户属性决定回款质量",
                            "text": "资金占用最多的慢回款客户：" + "、".join(f"{c['name']}（同类节点慢 {round(((c['cycle_vs_company'] or 1) - 1) * 100)}%，每元回款占用 {c['occupancy_years']} 年）" for c in laggards) + "。长期合作需持续垫资。"})
    if slow:
        conclusions.append({"key": "credit", "title": "结论反哺合同谈判与客户评级",
                            "text": f"已按同类节点账期、资金占用时长、逾期未回占比、预付比例为 {len(rated)} 个客户评级，C/D 级 {len(slow)} 个；签约前按评级调整预付比例与账期条款。"})
    if patterns:
        p0 = patterns[0]
        multi = next((p for p in patterns if len(p["nodes"]) > 1), None)
        text = f"一次性结清以“{p0['signature']}”最常见（{p0['probability']}%）"
        if multi:
            text += f"；分期模式以“{multi['signature']}”最常见（{multi['probability']}%），闭环中位 {multi['median_cycle_days'] or '—'} 天"
        conclusions.append({"key": "model", "title": "沉淀标准化回款模型", "text": text + "。新项目测算可直接套用对应模式的节点比例与时长。"})
    return {"bucket_medians": bucket_medians, "funding_rate": INSIGHT_FUNDING_RATE, "company_cycle_index": base_index, "company_occupancy_years": base_occ,
            "project_count": len(projects), "closed_projects": sum(1 for p in projects if p["closed"]),
            "tiers": tiers, "customers": customers, "patterns": patterns, "pattern_sample": pattern_sample, "conclusions": conclusions}
