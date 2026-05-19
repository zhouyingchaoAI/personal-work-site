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
    diary_dir.mkdir(parents=True, exist_ok=True)
    path = diary_dir / f"{date_str}.json"
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "date": date_str,
        "today_work": str(payload.get("today_work", "") or "").strip(),
        "tomorrow_plan": str(payload.get("tomorrow_plan", "") or "").strip(),
        "thoughts": str(payload.get("thoughts", "") or "").strip(),
        "updated_at": now,
    }
    if path.exists():
        old = read_json_lenient(path)
        data["created_at"] = old.get("created_at", now)
    else:
        data["created_at"] = now
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "diary": data}


def get_diary(date_str, username):
    if not date_str:
        return {"ok": True, "diary": None}
    path = user_diary_dir(username) / f"{date_str}.json"
    if not path.exists():
        return {"ok": True, "diary": None}
    return {"ok": True, "diary": read_json_lenient(path)}


def list_diaries(payload, username):
    diary_dir = user_diary_dir(username)
    if not diary_dir.exists():
        return {"ok": True, "diaries": []}
    items = []
    for p in sorted(diary_dir.glob("*.json"), reverse=True):
        try:
            d = read_json_lenient(p)
            items.append({
                "date": d.get("date", p.stem),
                "today_work_preview": d.get("today_work", "")[:80],
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
    path = user_diary_dir(username) / f"{date_str}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}


def summarize_diaries_for_weekly(payload, username):
    start_date = str(payload.get("start_date", "") or "").strip()
    end_date = str(payload.get("end_date", "") or "").strip()
    if not start_date or not end_date:
        raise ValueError("请选择日记日期范围")
    diary_dir = user_diary_dir(username)
    contents = []
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while cur <= end:
        date_str = cur.strftime("%Y-%m-%d")
        path = diary_dir / f"{date_str}.json"
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                parts = [f"【{date_str}】"]
                if d.get("today_work"):
                    parts.append(f"今日工作：{d['today_work']}")
                if d.get("tomorrow_plan"):
                    parts.append(f"明日计划：{d['tomorrow_plan']}")
                if d.get("thoughts"):
                    parts.append(f"思路想法：{d['thoughts']}")
                contents.append("\n".join(parts))
            except Exception:
                pass
        cur += __import__("datetime").timedelta(days=1)
    if not contents:
        return {"ok": True, "mode": "empty", "summary": "", "warning": "该日期范围内没有工作日记"}
    full_text = "\n\n".join(contents)
    settings = assistant_settings()
    prompt = (
        "请根据下面的工作日记内容，总结生成周报的三个部分。"
        "要求：1. 本周工作总结：概括已完成的主要工作，按要点列出；"
        "2. 重点工作跟进：提炼需要持续跟进的重大事项和当前进展；"
        "3. 下周工作计划：基于日记中的明日计划和思路，整理出下周工作安排。"
        "输出格式：\n本周工作总结：\n1. ...\n2. ...\n\n重点工作跟进：\n1. ...\n2. ...\n\n下周工作计划：\n1. ...\n2. ..."
    )
    if settings["url"] and settings["key"]:
        try:
            body = json.dumps(
                {
                    "model": settings["model"],
                    "messages": [
                        {"role": "system", "content": "你是中文工作周报写作助手。只输出总结内容，不要解释。"},
                        {"role": "user", "content": f"{prompt}\n\n工作日记内容：\n{full_text}"},
                    ],
                    "temperature": 0.3,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                settings["url"] + "/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["key"]},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return {"ok": True, "mode": "api", "summary": content}
        except Exception as exc:
            return {"ok": False, "error": f"AI 总结失败：{exc}"}
    return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 API 地址和 Key"}


# ===== 金点子论坛 =====
