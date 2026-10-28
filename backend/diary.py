"""Work diary persistence and weekly summarization.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def read_json_lenient(path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        data, _ = json.JSONDecoder().raw_decode(text)
        return data


def save_diary(payload, username):
    date_str = str(payload.get("date", "") or "").strip()
    if not date_str:
        raise ValueError("请选择日记日期")
    diary_dir = user_diary_dir(username)
    path = diary_dir / f"{date_str}.json"
    now = datetime.now().isoformat(timespec="seconds")
    # Skills (especially OpenClaw / WeChat) often save one part of a diary per
    # message.  Treat these writes as patches: omitted or blank placeholder
    # fields must not erase an earlier part of the same day's entry.  The web
    # form sends replace=true because it edits the complete record and needs to
    # retain the ability to intentionally clear a field.
    old = office_doc_read("diary", path, None)
    existed = isinstance(old, dict)
    old = old if existed else {}
    replace = bool(payload.get("replace"))
    clear_fields = {
        str(field).strip()
        for field in (payload.get("clear_fields") or [])
        if str(field).strip() in {"today_work", "tomorrow_plan", "thoughts"}
    }

    data = {"date": date_str, "updated_at": now}
    for field in ("today_work", "tomorrow_plan", "thoughts"):
        incoming = str(payload.get(field, "") or "").strip()
        if replace or field in clear_fields or incoming:
            data[field] = incoming
        else:
            data[field] = str(old.get(field, "") or "").strip()
    # 日报可同时关联多个项目，供每个项目的成员时间线汇总同一条日报。
    # 保留 project_id 首项以兼容旧客户端和既有数据。
    project_source = payload.get("project_ids") if (replace or "project_ids" in payload) else old.get("project_ids")
    if project_source is None:
        project_source = [payload.get("project_id", "")] if (replace or "project_id" in payload) else [old.get("project_id", "")]
    project_ids = []
    for project_id in project_source if isinstance(project_source, list) else [project_source]:
        project_id = str(project_id or "").strip()
        if project_id and project_id not in project_ids:
            project_ids.append(project_id)
    data["project_ids"] = project_ids
    data["project_id"] = project_ids[0] if project_ids else ""
    # 项目日记以项目 ID 为键保存，避免同一天参与多个项目时内容混在日常工作里。
    note_source = payload.get("project_notes") if (replace or "project_notes" in payload) else old.get("project_notes", {})
    note_source = note_source if isinstance(note_source, dict) else {}
    data["project_notes"] = {
        project_id: str(note_source.get(project_id, "") or "").strip()
        for project_id in project_ids
        if str(note_source.get(project_id, "") or "").strip()
    }
    data["created_at"] = old.get("created_at", now) if existed else now
    office_doc_write("diary", path, data)
    return {"ok": True, "diary": data}


def get_diary(date_str, username):
    if not date_str:
        return {"ok": True, "diary": None}
    diary = office_doc_read("diary", user_diary_dir(username) / f"{date_str}.json", None)
    if not isinstance(diary, dict):
        return {"ok": True, "diary": None}
    if "project_ids" not in diary:
        diary["project_ids"] = [diary["project_id"]] if diary.get("project_id") else []
    diary["project_notes"] = diary.get("project_notes") if isinstance(diary.get("project_notes"), dict) else {}
    return {"ok": True, "diary": diary}


def list_diaries(payload, username):
    payload = payload or {}
    diary_dir = user_diary_dir(username)
    start = str(payload.get("start", "") or payload.get("start_date", "") or "").strip()
    end = str(payload.get("end", "") or payload.get("end_date", "") or "").strip()
    keyword = str(payload.get("keyword", "") or payload.get("q", "") or "").strip().lower()
    items = []
    for name, d, _ in sorted(office_doc_list("diary", diary_dir), key=lambda entry: entry[0], reverse=True):
        try:
            stem = name[:-5]
            if not isinstance(d, dict):
                continue
            date = str(d.get("date", stem) or stem)
            if start and date < start:
                continue
            if end and date > end:
                continue
            project_notes = d.get("project_notes") if isinstance(d.get("project_notes"), dict) else {}
            full_text = "\n".join([*(str(d.get(k, "") or "") for k in ("today_work", "tomorrow_plan", "thoughts")), *(str(value or "") for value in project_notes.values())])
            if keyword and keyword not in full_text.lower() and keyword not in date.lower():
                continue
            items.append({
                "date": date,
                "today_work": d.get("today_work", ""),
                "tomorrow_plan": d.get("tomorrow_plan", ""),
                "thoughts": d.get("thoughts", ""),
                "project_id": d.get("project_id", ""),
                "project_ids": d.get("project_ids") or ([d.get("project_id")] if d.get("project_id") else []),
                "project_notes": project_notes,
                "today_work_preview": d.get("today_work", "")[:120],
                "created_at": d.get("created_at", ""),
                "updated_at": d.get("updated_at", ""),
            })
        except Exception:
            continue
    limit = int(payload.get("limit", 0) or 0)
    if limit > 0:
        items = items[:limit]
    return {"ok": True, "diaries": items}


def delete_diary(date_str, username):
    if not date_str:
        raise ValueError("请选择要删除的日记日期")
    office_doc_delete("diary", user_diary_dir(username) / f"{date_str}.json")
    return {"ok": True}


# 日记总结拼接给 LLM 的最大字符数，超出时保留最近日期，避免超出模型上下文。
DIARY_SUMMARY_MAX_CHARS = 24000


def _diary_chat_completion(settings, messages, temperature=0.3, timeout=60, retries=1):
    """调用 OpenAI 兼容 /v1/chat/completions，失败重试 retries 次。返回 message 文本。"""
    body = json.dumps(
        assistant_generation_payload(settings, {"model": settings["model"], "messages": messages, "temperature": temperature}),
        ensure_ascii=False,
    ).encode("utf-8")
    last_exc = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(
                settings["url"] + "/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["key"]},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001 — 收集后统一抛出
            last_exc = exc
    raise last_exc


def _collect_weekly_categories(username):
    """取上一份历史周报的工作分类，作为 AI 归类锚点。失败返回空清单。"""
    cats = {"summary": [], "follow": []}
    try:
        prefill = weekly_prefill(username)
    except Exception:
        return cats
    for key, rows_key in (("summary", "summary_rows"), ("follow", "follow_rows")):
        seen = set()
        for row in (prefill.get(rows_key) or []):
            category = str(row.get("category", "") or "").strip()
            if category and category not in seen:
                seen.add(category)
                cats[key].append(category)
    return cats


def _strip_json_fence(text):
    import re
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _parse_summary_json(raw):
    """把 LLM 返回解析为结构化 rows；无法解析返回 None。"""
    text = _strip_json_fence(raw)
    obj = None
    try:
        obj = json.loads(text)
    except Exception:
        try:
            obj = json.loads(text[text.index("{"): text.rindex("}") + 1])
        except Exception:
            return None
    if not isinstance(obj, dict):
        return None

    def norm(items, fields):
        out = []
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            row = {f: str(it.get(f, "") or "").strip() for f in fields}
            if row.get("content") or row.get("category") or row.get("progress"):
                out.append(row)
        return out

    summary = norm(obj.get("summary"), ["category", "content", "status", "plan"])
    for row in summary:
        if not row.get("status"):
            row["status"] = "已完成"
    return {
        "summary": summary,
        "follow": norm(obj.get("follow"), ["category", "content", "progress", "difficulty"]),
        "next": norm(obj.get("next"), ["category", "content", "difficulty"]),
    }


def _diary_text_to_rows(text):
    """LLM 未按 JSON 返回时的回退：把三段纯文本解析为 rows。"""
    import re
    rows = {"summary": [], "follow": [], "next": []}
    current = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "本周工作" in line and "总结" in line:
            current = "summary"; continue
        if "重点工作" in line:
            current = "follow"; continue
        if "下周工作" in line:
            current = "next"; continue
        content = re.sub(r"^[\d一二三四五六七八九十]+[.、．\s]+", "", line)
        content = re.sub(r"^[-*•]\s*", "", content).strip()
        if not (current and content):
            continue
        if current == "summary":
            rows["summary"].append({"category": "", "content": content, "status": "已完成"})
        elif current == "follow":
            rows["follow"].append({"category": "", "content": content, "progress": "", "difficulty": ""})
        else:
            rows["next"].append({"category": "", "content": content, "difficulty": ""})
    return rows


def _rows_to_text(rows):
    """把结构化 rows 渲染成三段文本，供展示与旧前端兼容。"""
    def line(idx, row):
        cat = f"[{row['category']}] " if row.get("category") else ""
        extra = ""
        if row.get("progress"):
            extra = f"（进展：{row['progress']}）"
        return f"{idx}. {cat}{row.get('content', '')}{extra}"

    parts = ["本周工作总结："]
    parts += [line(i, r) for i, r in enumerate(rows.get("summary", []), 1)]
    parts += ["", "重点工作跟进："]
    parts += [line(i, r) for i, r in enumerate(rows.get("follow", []), 1)]
    parts += ["", "下周工作计划："]
    parts += [line(i, r) for i, r in enumerate(rows.get("next", []), 1)]
    return "\n".join(parts)


def _merge_rows_by_category(rows, list_fields, keep_fields):
    """同一工作分类合并成一行：多条工作内容用「1、2、3」编号合并，贴合周报表格。"""
    import re
    order = []
    groups = {}
    for r in rows:
        cat = str(r.get("category") or "").strip()
        if not any(str(r.get(f) or "").strip() for f in list_fields):
            continue
        if cat not in groups:
            groups[cat] = {"_lists": {f: [] for f in list_fields},
                           "_keep": {k: str(r.get(k) or "").strip() for k in keep_fields}}
            order.append(cat)
        for f in list_fields:
            v = str(r.get(f) or "").strip()
            if v:
                groups[cat]["_lists"][f].append(v)
    out = []
    for cat in order:
        row = {"category": cat}
        row.update(groups[cat]["_keep"])
        for f in list_fields:
            items = groups[cat]["_lists"][f]
            if len(items) <= 1:
                row[f] = items[0] if items else ""
            else:
                cleaned = [re.sub(r"^\s*(?:\d+[、.．]|[-*•])\s*", "", it).strip() for it in items]
                row[f] = "\n".join(f"{i}、{c}" for i, c in enumerate(cleaned, 1))
        out.append(row)
    return out


def summarize_diaries_for_weekly(payload, username):
    # 优先用前端「勾选日记」传来的具体日期列表；否则退回连续日期范围。
    explicit_dates = [str(d).strip() for d in (payload.get("dates") or []) if str(d).strip()]
    start_date = str(payload.get("start_date", "") or "").strip()
    end_date = str(payload.get("end_date", "") or "").strip()
    if explicit_dates:
        date_list = sorted(set(explicit_dates))
    else:
        if not start_date or not end_date:
            raise ValueError("请选择日记日期范围")
        date_list = []
        cur = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        while cur <= end:
            date_list.append(cur.strftime("%Y-%m-%d"))
            cur += __import__("datetime").timedelta(days=1)
    diary_dir = user_diary_dir(username)
    daily = []  # [(date_str, block_text)]，按日期升序
    for date_str in date_list:
        d = office_doc_read("diary", diary_dir / f"{date_str}.json", None)
        if d is not None:
            if isinstance(d, dict):
                parts = [f"【{date_str}】"]
                if d.get("today_work"):
                    parts.append(f"今日工作：{d['today_work']}")
                if d.get("tomorrow_plan"):
                    parts.append(f"明日计划：{d['tomorrow_plan']}")
                if d.get("thoughts"):
                    parts.append(f"思路想法：{d['thoughts']}")
                if len(parts) > 1:
                    daily.append((date_str, "\n".join(parts)))

    empty_rows = {"summary": [], "follow": [], "next": []}
    if not daily:
        return {"ok": True, "mode": "empty", "summary": "", "rows": empty_rows, "warning": "该日期范围内没有工作日记"}

    # 截断保护：超长时优先保留最近日期的日记。
    full_text = "\n\n".join(block for _, block in daily)
    if len(full_text) > DIARY_SUMMARY_MAX_CHARS:
        kept, total = [], 0
        for _, block in reversed(daily):
            if kept and total + len(block) > DIARY_SUMMARY_MAX_CHARS:
                break
            kept.append(block)
            total += len(block)
        full_text = "\n\n".join(reversed(kept))

    settings = assistant_settings()
    if not (settings["url"] and settings["key"]):
        return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 API 地址和 Key"}

    # 「重点工作跟进」沿用历史周报、不由日记总结更新，故这里只让 AI 产出 summary 和 next。
    # 用户在日记页弹框里指定的分类优先；否则回退到历史周报分类作锚点。
    user_cats = [str(c).strip() for c in (payload.get("categories") or []) if str(c).strip()]
    if user_cats:
        cat_hint = (
            "\n\n【指定工作分类】请把每条内容归入下列用户指定的分类之一，尽量不要新建其它分类：\n"
            f"- {'、'.join(user_cats)}"
        )
    else:
        cats = _collect_weekly_categories(username)
        if cats["summary"]:
            cat_hint = (
                "\n\n【已有工作分类】请优先把内容归入下列既有分类，确有全新主题时才新建分类，保持与历史周报一致：\n"
                f"- 可用分类：{'、'.join(cats['summary'])}"
            )
        else:
            cat_hint = "\n\n请为每条内容自拟简洁的工作分类（如某项目或事务名）。"

    prompt = (
        "请阅读下面的工作日记，整理成周报数据，并严格只输出 JSON（不要任何解释或多余文字）。"
        "JSON 结构如下：\n"
        '{"summary":[{"category":"工作分类","content":"本周已完成的具体工作","status":"已完成","plan":"后续计划，可留空"}],'
        '"next":[{"category":"工作分类","content":"下周计划做的事","difficulty":""}]}\n'
        "要求：summary 概括本周已完成主要工作；next 基于明日计划与思路整理下周安排。"
        "每条 content 简洁具体、避免空话套话，category 必填。"
        + cat_hint
    )
    messages = [
        {"role": "system", "content": "你是中文工作周报写作助手，只输出符合要求的 JSON。"},
        {"role": "user", "content": f"{prompt}\n\n工作日记内容：\n{full_text}"},
    ]
    try:
        raw = _diary_chat_completion(settings, messages, temperature=0.3, timeout=60, retries=1)
    except Exception as exc:
        return {"ok": False, "error": f"AI 总结失败：{exc}"}

    parsed = _parse_summary_json(raw)
    mode = "api"
    if parsed is None:
        # 兜底：模型未按 JSON 返回时，按三段文本解析，保证不崩。
        parsed = _diary_text_to_rows(raw)
        mode = "api-text"
    # 同一工作分类合并为一行，工作内容用「1、2、3」编号。
    rows = {
        "summary": _merge_rows_by_category(parsed.get("summary", []), ["content", "plan"], ["status"]),
        "follow": parsed.get("follow", []),
        "next": _merge_rows_by_category(parsed.get("next", []), ["content", "difficulty"], []),
    }
    return {"ok": True, "mode": mode, "rows": rows, "summary": _rows_to_text(rows)}


# ===== 金点子论坛 =====
