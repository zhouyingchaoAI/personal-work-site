"""Structured text parsing and assistant text optimization.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def clean_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def parse_table_lines(value, columns):
    if isinstance(value, list):
        rows = []
        for row in value:
            if isinstance(row, dict):
                keys = ["category", "content", "status", "plan", "progress", "difficulty"]
                values = [str(row.get(key, "") or "").strip() for key in keys]
                if columns == 4:
                    rows.append([values[0], values[1], values[2] or values[4], values[3] or values[5]])
                else:
                    rows.append([values[0], values[1], values[5] or values[3]])
            elif isinstance(row, list):
                rows.append(([str(item or "").strip() for item in row] + [""] * columns)[:columns])
        return [row for row in rows if any(row)]

    rows = []
    for line in clean_lines(value):
        parts = [part.strip() for part in re.split(r"\s*[|｜]\s*", line)]
        parts = (parts + [""] * columns)[:columns]
        rows.append(parts)
    return rows


def style_xlsx_cell(cell, horizontal="left", vertical="top"):
    cell.alignment = cell.alignment.copy(
        wrap_text=True,
        horizontal=horizontal,
        vertical=vertical,
    )


def cell_value(ws, row, col):
    value = ws.cell(row, col).value
    return "" if value is None else str(value).strip()


def xlsx_row_text(values):
    return " | ".join(values).strip()


def normalize_numbered_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[；;]\s*(?=\d+[、.．])", "\n", text)
    text = re.sub(r"(?<!^)(?<!\n)\s*(?=\d+[、.．])", "\n", text)
    text = re.sub(r"[；;]\s*(?=[*＊·-]\s*)", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def local_optimize_text(text):
    text = normalize_numbered_text(text)
    if not text:
        return ""
    replacements = {
        "后段": "后端",
        "滑框": "滑动窗口",
        "扒取": "抓取",
        "api": "API",
        "Api": "API",
        "roi": "ROI",
        "mns": "MNS",
        "ui": "UI",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    parts = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:\d+[、.．]|[-*＊·])\s*", "", line).strip(" 。；;")
        if line:
            split_parts = [p.strip(" 。；;") for p in re.split(r"[；;]\s*", line) if p.strip(" 。；;")]
            parts.extend(split_parts)
    if len(parts) <= 1:
        parts = [p.strip(" 。；;") for p in re.split(r"，(?=(?:实现|完成|推动|优化|设计|增加|完善|梳理|分析|开展|补充))", parts[0]) if p.strip(" 。；;")]
    return "\n".join(f"{idx}、{part}。" for idx, part in enumerate(parts, start=1))


def normalize_assistant_output(text):
    text = normalize_numbered_text(text)
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = []
    for idx, line in enumerate(lines, start=1):
        line = re.sub(r"^\s*\d+\s*[、.．]\s*", f"{idx}、", line)
        if not re.match(r"^\d+、", line):
            line = f"{idx}、{line.strip(' 。；;')}。"
        normalized.append(line)
    return "\n".join(normalized)


def assistant_settings():
    config = read_config()
    return {
        "url": os.getenv("ASSISTANT_API_URL", config.get("assistant_api_url", "")).rstrip("/"),
        "key": os.getenv("ASSISTANT_API_KEY", config.get("assistant_api_key", "")),
        "model": os.getenv("ASSISTANT_MODEL", config.get("assistant_model", "MiniMax-M2.7")),
        "prompt": os.getenv("ASSISTANT_PROMPT", config.get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT)),
    }


def optimize_text(payload):
    text = str(payload.get("text", "") or "").strip()
    prompt = str(payload.get("prompt", "") or "").strip() or assistant_settings()["prompt"]
    if not text:
        return {"ok": True, "mode": "empty", "text": ""}

    settings = assistant_settings()
    if settings["url"] and settings["key"]:
        try:
            body = json.dumps(
                {
                    "model": settings["model"],
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是中文工作周报写作助手。只输出优化后的正文，不要解释，"
                                "不要使用Markdown标题，不要添加用户未提供的事项。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"{prompt}\n\n待优化内容：\n{text}",
                        },
                    ],
                    "temperature": 0.2,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                settings["url"] + "/v1/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + settings["key"],
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return {"ok": True, "mode": "api", "model": settings["model"], "text": normalize_assistant_output(content)}
        except Exception as exc:
            return {
                "ok": True,
                "mode": "local_fallback",
                "warning": f"智能接口调用失败，已使用本地规则优化：{exc}",
                "text": local_optimize_text(text),
            }

    return {"ok": True, "mode": "local", "text": local_optimize_text(text)}


WEEKLY_AGENT_SYSTEM = (
    "你是\"周报助手\"犇犇，通过对话帮用户填写和发送周报。\\n\\n"
    "工作流（必须按顺序执行）：\\n"
    "1. 获取日期：如需要当前日期或本周周期，调用 utils.get_date 获取。\\n"
    "2. 生成草稿：用户一旦提供了本周工作内容（哪怕只有几条），立即调用 weekly.compose 整理成周报结构。不要过度追问。\\n"
    "3. 生成预览：用户说\"预览/生成附件/确认\"后，调用 weekly.preview 生成 Excel、预览图和邮件草稿。\\n"
    "4. 发送邮件：用户明确说\"确认发送/可以发/发吧\"后，调用 weekly.send_confirmed 发送邮件。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息；没有的信息留空即可。\\n"
    "- 用户只要说了工作内容，哪怕很简短，也立即调用 weekly.compose，不要反复追问。\\n"
    "- 每一步先向用户说明你在做什么，再调用 Skill。\\n"
    "- 调用 weekly.preview 时，period 字段格式为 YYYY.MM.DD-YYYY.MM.DD。\\n"
    "- 如果用户只说了\"帮我写周报\"但完全没提工作内容，才需要询问。"
)

TRIP_AGENT_SYSTEM = (
    "你是\"出差报告助手\"犇犇，通过对话帮用户填写和发送出差报告。\\n\\n"
    "工作流（必须按顺序执行）：\\n"
    "1. 收集信息：引导用户提供出差时间、地点、目的、行程等。如需要当前日期，先调用 utils.get_date。\\n"
    "2. 生成报告：信息完整后，调用 document.generate 生成正式出差报告 Word 文件。\\n"
    "3. 发送邮件：用户确认后，发送邮件（如系统支持）。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息。\\n"
    "- 每一步都要先向用户说明你在做什么，再调用 Skill。"
)

DIARY_AGENT_SYSTEM = (
    "你是\"工作日记助手\"犇犇，通过对话帮用户记录每天的工作日记。\\n\\n"
    "工作流：\\n"
    "1. 收集信息：通过自然对话了解用户今天的工作内容、明日计划和想法。\\n"
    "2. 保存日记：信息完整后，调用 diary.save 保存到系统。\\n"
    "3. 查看历史：用户想查看时，调用 diary.get 或 diary.list。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息。\\n"
    "- 日记内容保持自然语言，不要过度结构化。"
)

MAIL_AGENT_SYSTEM = (
    "你是\"智能邮件助手\"，帮助用户阅读邮件、提炼重点、起草普通邮件、优化邮件正文。\\n"
    "你会收到当前邮件助手页面上的收件箱、选中邮件或写信表单上下文。\\n"
    "你的任务不是写周报或出差报告；除非用户明确要求，否则不要输出报告表单 JSON。\\n"
    "请用中文直接回答，必要时给出可复制的邮件主题和正文。不要编造未提供的邮件内容。"
)

NEWS_AGENT_SYSTEM = (
    "你是\"每日资讯助手\"，帮助用户理解轨道交通每日资讯、提炼重点、总结影响和建议行动。\\n"
    "你会收到当前资讯页面内容。普通用户不能配置资讯源；只有超级管理员能配置和生成。\\n"
    "你的任务不是写周报或出差报告；不要输出报告表单 JSON。\\n"
    "请基于已提供资讯回答，不要编造最新新闻。"
)

FORUM_AGENT_SYSTEM = (
    "你是\"金点子论坛助手\"，帮助用户围绕当前话题提炼观点、生成评论、总结讨论热度和下一步行动。\\n"
    "你会收到当前论坛话题、评论输入框或话题创建草稿。\\n"
    "你的任务不是写周报或出差报告；不要输出报告表单 JSON。\\n"
    "请用中文给出适合论坛讨论的内容；如果用户要评论，优先给出一段可直接发布的评论。"
)

GENERAL_AGENT_SYSTEM = (
    "你是\"AI 办公总助手\"，根据用户当前所在页面提供工作建议。\\n"
    "可协助周报、出差报告、工作日记、邮件、论坛和每日资讯相关问题。\\n"
    "如果当前页面不是周报或出差报告，不要输出报告表单 JSON。\\n"
    "回答要简洁、可执行，不要编造不存在的信息。"
)

DEFAULT_AGENT_WORKFLOWS = {
    "weekly": "1) weekly.compose 规范化并填入周报结构 → 2) weekly.preview 生成周报文件、预览图片和邮件草稿 → 3) 用户确认后 weekly.send_confirmed 发送邮件",
    "trip": "1) trip.prefill 获取历史出差报告预填 → 2) 用户补充信息后 document.generate 生成正式报告 → 3) 发送邮件",
    "diary": "1) diary.save 保存工作日记 → 可随时 diary.get / diary.list 查看",
    "mailassistant": "1) mailbox.list 查看邮件 → 2) text.optimize 优化正文或起草回复",
    "forum": "1) forum.list 查看话题 → 2) forum.add_comment 发表评论或 forum.create 发起话题",
    "news": "1) news.list 查看每日资讯 → 2) text.optimize 提炼重点和影响",
}

AGENT_SYSTEM_PROMPTS = {
    "weekly": WEEKLY_AGENT_SYSTEM,
    "trip": TRIP_AGENT_SYSTEM,
    "diary": DIARY_AGENT_SYSTEM,
    "mailassistant": MAIL_AGENT_SYSTEM,
    "news": NEWS_AGENT_SYSTEM,
    "forum": FORUM_AGENT_SYSTEM,
    "dashboard": GENERAL_AGENT_SYSTEM,
}

AGENT_WORKFLOWS = dict(DEFAULT_AGENT_WORKFLOWS)

