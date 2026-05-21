"""Skill definitions, skill execution, and agent orchestration.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

# Import memory skills so they are available in the shared namespace
# (backend.runtime loads memory.py before skills_agent.py)
try:
    from backend.memory import (
        memory_remember_skill,
        memory_search_skill,
        memory_forget_skill,
        memory_summarize_skill,
    )
except Exception:
    # Fallback: will be available via globals after runtime exec
    pass

def load_agent_config():
    """启动时加载 agent_config.json 并覆盖默认提示词和工作流。"""
    global WEEKLY_AGENT_SYSTEM, TRIP_AGENT_SYSTEM, DIARY_AGENT_SYSTEM
    global MAIL_AGENT_SYSTEM, NEWS_AGENT_SYSTEM, FORUM_AGENT_SYSTEM
    global GENERAL_AGENT_SYSTEM, AGENT_SYSTEM_PROMPTS, AGENT_WORKFLOWS
    cfg = read_agent_config()
    prompts = cfg.get("prompts", {})
    if prompts.get("weekly"):
        WEEKLY_AGENT_SYSTEM = prompts["weekly"]
    if prompts.get("trip"):
        TRIP_AGENT_SYSTEM = prompts["trip"]
    if prompts.get("diary"):
        DIARY_AGENT_SYSTEM = prompts["diary"]
    if prompts.get("mailassistant"):
        MAIL_AGENT_SYSTEM = prompts["mailassistant"]
    if prompts.get("news"):
        NEWS_AGENT_SYSTEM = prompts["news"]
    if prompts.get("forum"):
        FORUM_AGENT_SYSTEM = prompts["forum"]
    if prompts.get("dashboard"):
        GENERAL_AGENT_SYSTEM = prompts["dashboard"]
    AGENT_SYSTEM_PROMPTS = {
        "weekly": WEEKLY_AGENT_SYSTEM,
        "trip": TRIP_AGENT_SYSTEM,
        "diary": DIARY_AGENT_SYSTEM,
        "mailassistant": MAIL_AGENT_SYSTEM,
        "news": NEWS_AGENT_SYSTEM,
        "forum": FORUM_AGENT_SYSTEM,
        "dashboard": GENERAL_AGENT_SYSTEM,
    }
    workflows = cfg.get("workflows", {})
    for key, val in workflows.items():
        if key in AGENT_WORKFLOWS and val:
            AGENT_WORKFLOWS[key] = val


def weekly_compose_skill_detail():
    return {
        "purpose": "把用户自然语言描述的工作内容整理成系统周报表单结构，支持从历史周报迁移、补全分类、优化表达、生成下周计划。",
        "when_to_use": [
            "用户说“帮我写周报、整理本周工作、根据这些内容生成周报”。",
            "用户粘贴零散工作内容，需要拆分成 1、2、3、4 点。",
            "用户要求把上周计划转成本周工作内容，或生成下一周计划。",
            "用户希望体现工作量很多、语言简洁、无错别字。"
        ],
        "input_schema": {
            "period": "周报周期，例如 2026.05.11-2026.05.15，可选",
            "raw_work": "本周原始工作内容，自然语言或多行文本",
            "last_week_plan": "上次周报的下周计划，可选，用于迁移到本周工作",
            "key_work": "重点工作/关键项目，可选",
            "next_plan": "下周计划原始描述，可选",
            "difficulties": "困难、风险、需要协调事项，可选",
            "style": "输出风格，可选，默认：简洁、具体、体现工作量"
        },
        "output_schema": {
            "weekly_summary": [{"category": "工作分类", "content": "工作内容", "status": "完成情况", "plan": "后续计划"}],
            "weekly_follow": [{"category": "重点工作", "content": "工作内容", "progress": "当前进展", "difficulty": "困难与求助"}],
            "weekly_next": [{"category": "工作分类", "content": "下周计划", "difficulty": "困难与求助"}]
        },
        "call_example": {
            "reply": "我来根据这些内容生成周报草稿。",
            "skill_call": {
                "name": "weekly.compose",
                "arguments": {
                    "period": "2026.05.11-2026.05.15",
                    "raw_work": "实现平台复杂页面层次拆解；实现多模型部署管理；训练安全帽反光衣手套检测模型；完善API授权；增加权限管理；优化UI。",
                    "key_work": "算法平台、模型服务、数据治理、多模型部署",
                    "next_plan": "推进业务与算法服务后端联调；实现ROI滑动窗口切片和结果去重；拆分微服务架构。",
                    "style": "体现工作量多，编号清晰，简洁明了"
                }
            }
        }
    }


def weekly_preview_skill_detail():
    return {
        "purpose": "根据已规范化的周报结构生成正式周报文件、邮件草稿和周报预览图片，供用户确认。",
        "when_to_use": [
            "用户已提供或确认周报结构化内容，需要生成预览。",
            "用户说“生成周报预览、让我先看看、预览没问题再发”。",
            "大模型已经通过 weekly.compose 得到 weekly_summary、weekly_follow、weekly_next。"
        ],
        "input_schema": {
            "period": "周报周期，例如 2026.05.11-2026.05.15",
            "weekly_summary": [{"category": "工作分类", "content": "工作内容", "status": "完成情况", "plan": "后续计划"}],
            "weekly_follow": [{"category": "重点工作", "content": "工作内容", "progress": "当前进展", "difficulty": "困难与求助"}],
            "weekly_next": [{"category": "工作分类", "content": "下周计划", "difficulty": "困难与求助"}]
        },
        "output_schema": {
            "file": "生成的周报 Excel 文件名",
            "download_url": "周报文件下载地址",
            "preview_image_url": "周报预览图片地址",
            "mail_draft": "待确认的邮件草稿"
        },
        "call_example": {
            "reply": "我先生成周报预览，请你确认内容和格式。",
            "skill_call": {
                "name": "weekly.preview",
                "arguments": {
                    "period": "2026.05.11-2026.05.15",
                    "weekly_summary": [{"category": "算法平台", "content": "完成平台复杂页面层次拆解。", "status": "已完成", "plan": "持续优化交互"}],
                    "weekly_follow": [],
                    "weekly_next": [{"category": "联调", "content": "推进业务与算法服务后端联调。", "difficulty": ""}]
                }
            }
        }
    }


def weekly_send_skill_detail():
    return {
        "purpose": "在用户明确确认周报预览无误后，发送周报邮件。",
        "when_to_use": [
            "用户已经查看周报预览图片并明确说“确认发送、没问题发送、可以发”。",
            "不得在未生成预览、未确认时调用。",
            "发送前需要已有 weekly.preview 返回的 file，或 arguments 中提供 attachment。"
        ],
        "input_schema": {
            "attachment": "weekly.preview 生成的周报文件名",
            "to": "收件人，可选；为空使用邮件配置中的周报收件人",
            "cc": "抄送，可选；为空使用邮件配置中的周报抄送",
            "subject": "主题，可选",
            "body": "正文，可选"
        },
        "output_schema": {
            "mode": "sent|draft",
            "message": "发送结果"
        },
        "call_example": {
            "reply": "已确认预览无误，我现在发送周报邮件。",
            "skill_call": {
                "name": "weekly.send_confirmed",
                "arguments": {"attachment": "周颖超工作周报2026.05.11-2026.05.15.xlsx"}
            }
        }
    }


def skill_defs():
    base = [
        {
            "name": "reports.list",
            "module": "报告",
            "title": "查询报告列表",
            "description": "查询当前用户的周报、出差报告、生成文件和历史报告。",
            "parameters": {"kind": "all|weekly|trip，可选"},
            "safe": True,
        },
        {
            "name": "weekly.prefill",
            "module": "周报",
            "title": "获取最新周报预填",
            "description": "读取最新历史周报，将上次下周计划迁移到本次工作内容。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "weekly.compose",
            "module": "周报",
            "title": "编写/设计周报草稿",
            "description": "调用配置的大模型 API，将原始工作内容整理成周报三段式结构：本周工作总结、重点工作跟进、下周工作计划。",
            "parameters": {
                "period": "周报周期，可选",
                "raw_work": "本周原始工作内容",
                "last_week_plan": "上次周报下周计划，可选",
                "key_work": "重点工作，可选",
                "next_plan": "下周计划，可选",
                "difficulties": "困难与求助，可选",
                "style": "输出风格，可选"
            },
            "safe": True,
            "detail": weekly_compose_skill_detail(),
        },
        {
            "name": "weekly.preview",
            "module": "周报",
            "title": "生成周报预览",
            "description": "根据已整理的周报结构生成正式周报 Excel、邮件草稿和周报预览图片，供用户确认。",
            "parameters": {
                "period": "周报周期",
                "weekly_summary": "本周工作总结数组",
                "weekly_follow": "重点工作跟进数组",
                "weekly_next": "下周工作计划数组"
            },
            "safe": False,
            "detail": weekly_preview_skill_detail(),
        },
        {
            "name": "weekly.send_confirmed",
            "module": "周报",
            "title": "确认后发送周报邮件",
            "description": "仅在用户确认周报预览无误后，使用当前账号邮件配置发送周报邮件。",
            "parameters": {
                "attachment": "周报文件名，通常来自 weekly.preview",
                "to": "收件人，可选",
                "cc": "抄送，可选",
                "subject": "主题，可选",
                "body": "正文，可选"
            },
            "safe": False,
            "detail": weekly_send_skill_detail(),
        },
        {
            "name": "trip.prefill",
            "module": "出差报告",
            "title": "获取最新出差报告预填",
            "description": "读取最新历史出差报告并填充当前出差报告草稿。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "document.generate",
            "module": "报告",
            "title": "生成正式报告文件",
            "description": "按模板生成周报 Excel 或出差报告 Word。",
            "parameters": {"kind": "weekly|trip", "weekly_summary": "数组", "weekly_follow": "数组", "weekly_next": "数组", "trip fields": "出差报告字段"},
            "safe": False,
        },
        {
            "name": "text.optimize",
            "module": "通用",
            "title": "优化文本",
            "description": "用配置的大模型 API 优化工作内容、邮件正文、论坛内容等文本。",
            "parameters": {"text": "待优化文本", "prompt": "优化要求，可选"},
            "safe": True,
        },
        {
            "name": "diary.save",
            "module": "工作日记",
            "title": "保存工作日记",
            "description": "保存当前用户指定日期的工作日记。",
            "parameters": {"date": "YYYY-MM-DD", "today_work": "今日工作", "tomorrow_plan": "明日计划", "thoughts": "想法心得"},
            "safe": False,
        },
        {
            "name": "diary.get",
            "module": "工作日记",
            "title": "读取工作日记",
            "description": "读取当前用户指定日期的工作日记。",
            "parameters": {"date": "YYYY-MM-DD"},
            "safe": True,
        },
        {
            "name": "diary.list",
            "module": "工作日记",
            "title": "查询工作日记列表",
            "description": "查询当前用户的工作日记列表。",
            "parameters": {"start": "开始日期，可选", "end": "结束日期，可选"},
            "safe": True,
        },
        {
            "name": "mailbox.list",
            "module": "邮件",
            "title": "查看收件箱",
            "description": "通过当前用户 IMAP 配置读取最近邮件。",
            "parameters": {"limit": "10/20/50，可选"},
            "safe": True,
        },
        {
            "name": "mailbox.detail",
            "module": "邮件",
            "title": "查看邮件详情",
            "description": "通过邮件 UID 读取邮件正文、HTML 预览和附件信息。",
            "parameters": {"uid": "邮件 UID"},
            "safe": True,
        },
        {
            "name": "mail.send",
            "module": "邮件",
            "title": "发送普通邮件",
            "description": "使用当前用户 SMTP 配置发送普通邮件。",
            "parameters": {"to": "收件人", "cc": "抄送，可选", "subject": "主题", "body": "正文"},
            "safe": False,
        },
        {
            "name": "forum.list",
            "module": "金点子论坛",
            "title": "查看金点子话题",
            "description": "查看当前用户可见的金点子论坛话题。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "forum.create",
            "module": "金点子论坛",
            "title": "发布金点子话题",
            "description": "创建新的金点子论坛话题。",
            "parameters": {"title": "标题", "body": "内容", "tags": "标签数组，可选"},
            "safe": False,
        },
        {
            "name": "forum.comment",
            "module": "金点子论坛",
            "title": "发布论坛评论",
            "description": "给指定金点子话题添加评论。",
            "parameters": {"id": "话题 ID", "body": "评论内容"},
            "safe": False,
        },
        {
            "name": "news.latest",
            "module": "资讯",
            "title": "查看每日资讯",
            "description": "查看系统生成的最新每日资讯。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "memory.remember",
            "module": "记忆",
            "title": "保存记忆",
            "description": "保存用户偏好、事件、事实等记忆条目，供后续 Agent 调用时检索。",
            "parameters": {
                "content": "记忆内容，必填",
                "type": "记忆类型：preference/event/fact/note/context，默认 note",
                "metadata": "额外元数据对象，可选",
                "source": "来源，可选",
                "confidence": "置信度 0-1，默认 1.0"
            },
            "safe": False,
        },
        {
            "name": "memory.search",
            "module": "记忆",
            "title": "搜索记忆",
            "description": "通过关键词全文搜索用户的记忆条目。",
            "parameters": {
                "query": "搜索关键词，可选",
                "type": "按类型过滤，可选",
                "limit": "返回数量，默认 10"
            },
            "safe": True,
        },
        {
            "name": "memory.forget",
            "module": "记忆",
            "title": "删除记忆",
            "description": "删除指定 ID 的记忆条目。",
            "parameters": {"id": "记忆 ID"},
            "safe": False,
        },
        {
            "name": "memory.summarize",
            "module": "记忆",
            "title": "总结记忆",
            "description": "总结用户近期的记忆条目。",
            "parameters": {"type": "按类型过滤，可选", "days": "最近多少天，默认 30"},
            "safe": True,
        },
        {
            "name": "workflow.list",
            "module": "工作流",
            "title": "列出工作流",
            "description": "列出所有可用的工作流定义。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "workflow.run",
            "module": "工作流",
            "title": "运行工作流",
            "description": "启动一个工作流实例，按步骤执行 Skill 调用。",
            "parameters": {
                "workflow_id": "工作流 ID",
                "inputs": "初始输入变量对象，可选"
            },
            "safe": False,
        },
        {
            "name": "workflow.status",
            "module": "工作流",
            "title": "查看工作流状态",
            "description": "获取工作流实例的当前状态和步骤结果。",
            "parameters": {"instance_id": "工作流实例 ID"},
            "safe": True,
        },
        {
            "name": "workflow.confirm",
            "module": "工作流",
            "title": "确认并继续工作流",
            "description": "对暂停中的工作流步骤进行确认，然后继续执行。",
            "parameters": {
                "instance_id": "工作流实例 ID",
                "confirmed": "是否确认，默认 true",
                "override_arguments": "参数覆盖对象，可选"
            },
            "safe": False,
        },
        {
            "name": "utils.get_date",
            "module": "通用",
            "title": "获取日期信息",
            "description": "获取当前日期、今天星期几、本周起止日期、本月起止日期、本季度起止日期、当前年度等日期信息，用于填写周报周期、出差时间等。",
            "parameters": {"format": "日期格式，可选，如 YYYY.MM.DD 或 YYYY-MM-DD，默认 YYYY.MM.DD"},
            "safe": True,
        },
    ]
    return base


def skill_doc_markdown():
    lines = [
        "# 智能办公助手 Skill 文档",
        "",
        "本系统把周报、出差报告、工作日记、邮件、论坛、每日资讯等业务能力封装为可由大模型调用的 Skill。",
        "",
        "## 调用协议",
        "",
        "大模型需要调用功能时，请返回严格 JSON，不要包裹 Markdown 代码块：",
        "",
        '{"reply":"给用户看的说明","skill_call":{"name":"skill.name","arguments":{}}}',
        "",
        "如果只是普通问答，不需要调用 Skill，则直接自然语言回复即可。",
        "",
        "## 安全约束",
        "",
        "- safe=true 的 Skill 为查询、预览、优化类能力，可直接执行。",
        "- safe=false 的 Skill 会产生写入、生成文件、发邮件或发布内容等动作；前端应在关键场景增加确认。",
        "- 所有 Skill 默认在当前登录用户空间内执行，不能跨用户读取数据。",
        "",
        "## Skill 列表",
        "",
    ]
    for item in skill_defs():
        lines.extend([
            f"### {item['name']} - {item['title']}",
            "",
            item["description"],
            "",
            f"- 安全级别：{'查询/预览' if item['safe'] else '会产生写入或外部动作'}",
            f"- 参数：`{json.dumps(item['parameters'], ensure_ascii=False)}`",
            "",
        ])
        if item.get("detail"):
            detail = item["detail"]
            lines.extend([
                "#### 详细设计",
                "",
                f"- 用途：{detail.get('purpose', '')}",
                "",
                "适用场景：",
            ])
            lines.extend([f"- {line}" for line in detail.get("when_to_use", [])])
            lines.extend([
                "",
                "输入 Schema：",
                "",
                "```json",
                json.dumps(detail.get("input_schema", {}), ensure_ascii=False, indent=2),
                "```",
                "",
                "输出 Schema：",
                "",
                "```json",
                json.dumps(detail.get("output_schema", {}), ensure_ascii=False, indent=2),
                "```",
                "",
                "调用示例：",
                "",
                "```json",
                json.dumps(detail.get("call_example", {}), ensure_ascii=False, indent=2),
                "```",
                "",
            ])
    return "\n".join(lines)


def public_skill_docs():
    return {"ok": True, "skills": skill_defs(), "markdown": skill_doc_markdown()}


def skill_by_name(name):
    return next((item for item in skill_defs() if item.get("name") == name), None)


def parse_json_object(text):
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_weekly_rows(data):
    def clean_rows(rows, keys):
        result = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = {key: str(row.get(key, "") or "").strip() for key in keys}
            if any(item.values()):
                result.append(item)
        return result

    return {
        "weekly_summary": clean_rows(data.get("weekly_summary", []), ["category", "content", "status", "plan"]),
        "weekly_follow": clean_rows(data.get("weekly_follow", []), ["category", "content", "progress", "difficulty"]),
        "weekly_next": clean_rows(data.get("weekly_next", []), ["category", "content", "difficulty"]),
    }


def weekly_payload_from_draft(args):
    draft = args.get("draft") if isinstance(args.get("draft"), dict) else args
    rows = normalize_weekly_rows(draft)
    return {
        "kind": "weekly",
        "period": str(args.get("period") or draft.get("period") or datetime.now().strftime("%Y.%m.%d-%Y.%m.%d")).strip(),
        "weekly_summary": rows["weekly_summary"],
        "weekly_follow": rows["weekly_follow"],
        "weekly_next": rows["weekly_next"],
    }


def text_wrap_units(text, max_units):
    lines = []
    current = ""
    units = 0
    for ch in str(text or ""):
        if ch == "\n":
            lines.append(current)
            current = ""
            units = 0
            continue
        weight = 2 if ord(ch) > 127 else 1
        if units + weight > max_units and current:
            lines.append(current)
            current = ch
            units = weight
        else:
            current += ch
            units += weight
    if current or not lines:
        lines.append(current)
    return lines


def load_preview_font(size=18, bold=False):
    try:
        from PIL import ImageFont
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()
    except Exception:
        return None


def create_weekly_preview_image(payload, output_path):
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        raise ValueError("缺少 Pillow，无法生成周报预览图片") from exc

    rows = normalize_weekly_rows(payload)
    title_font = load_preview_font(30, True)
    section_font = load_preview_font(22, True)
    text_font = load_preview_font(17)
    small_font = load_preview_font(14)
    width = 1400
    margin = 44
    y = 36

    def estimate_section_height(title, data, keys):
        height = 54
        for row in data or [{"category": "", "content": "暂无内容"}]:
            text = " | ".join(str(row.get(k, "") or "") for k in keys)
            height += max(72, len(text_wrap_units(text, 88)) * 23 + 34)
        return height

    total_height = 110
    total_height += estimate_section_height("本周工作总结", rows["weekly_summary"], ["category", "content", "status", "plan"])
    total_height += estimate_section_height("重点工作跟进", rows["weekly_follow"], ["category", "content", "progress", "difficulty"])
    total_height += estimate_section_height("下周工作计划", rows["weekly_next"], ["category", "content", "difficulty"])
    total_height = max(900, total_height + 80)

    image = Image.new("RGB", (width, total_height), "#f4f7fb")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, width - 24, total_height - 24), radius=18, fill="#ffffff", outline="#dbe5f1", width=2)
    title = f"工作周报（{payload.get('period') or ''}）"
    draw.text((margin, y), title, fill="#172033", font=title_font)
    y += 58
    draw.text((margin, y), "预览图用于确认内容，正式格式以生成的 Excel 附件为准。", fill="#64748b", font=small_font)
    y += 38

    def section(title, data, columns):
        nonlocal y
        draw.rounded_rectangle((margin, y, width - margin, y + 38), radius=8, fill="#eff6ff", outline="#bfdbfe")
        draw.text((margin + 16, y + 8), title, fill="#1d4ed8", font=section_font)
        y += 50
        data = data or [{}]
        for index, row in enumerate(data, 1):
            line_parts = [f"{label}：{row.get(key, '')}" for key, label in columns if row.get(key, "")]
            if not line_parts:
                line_parts = ["暂无内容"]
            wrapped = []
            for part in line_parts:
                wrapped.extend(text_wrap_units(part, 92))
            card_h = max(70, len(wrapped) * 24 + 34)
            draw.rounded_rectangle((margin, y, width - margin, y + card_h), radius=8, fill="#ffffff", outline="#dbe5f1")
            draw.text((margin + 16, y + 14), f"{index}.", fill="#2563eb", font=text_font)
            text_y = y + 14
            for line in wrapped:
                draw.text((margin + 54, text_y), line, fill="#172033", font=text_font)
                text_y += 24
            y += card_h + 12
        y += 12

    section("一、本周工作总结", rows["weekly_summary"], [("category", "分类"), ("content", "内容"), ("status", "完成情况"), ("plan", "后续计划")])
    section("二、重点工作跟进", rows["weekly_follow"], [("category", "分类"), ("content", "内容"), ("progress", "进展"), ("difficulty", "困难")])
    section("三、下周工作计划", rows["weekly_next"], [("category", "分类"), ("content", "内容"), ("difficulty", "困难")])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop((0, 0, width, min(total_height, y + 36))).save(output_path)
    return output_path


def compose_weekly_skill(arguments):
    args = arguments or {}
    source_text = "\n".join(
        str(args.get(key, "") or "").strip()
        for key in ("last_week_plan", "raw_work", "key_work", "next_plan", "difficulties")
        if str(args.get(key, "") or "").strip()
    )
    if not source_text:
        raise ValueError("请提供 raw_work、last_week_plan、key_work 或 next_plan 中至少一项内容")

    settings = assistant_settings()
    prompt = (
        "你是企业周报 Skill，负责把原始工作描述整理成系统可写入的周报 JSON。"
        "要求：1、体现工作量和推进成果；2、语言简洁明了；3、修正错别字；4、不编造未提供事项；"
        "5、分类尽量贴近软件/算法/数据治理/联调/架构/UI/管理等实际工作；"
        "6、输出严格 JSON，不要 Markdown。"
        "JSON 格式："
        "{\"weekly_summary\":[{\"category\":\"\",\"content\":\"\",\"status\":\"\",\"plan\":\"\"}],"
        "\"weekly_follow\":[{\"category\":\"\",\"content\":\"\",\"progress\":\"\",\"difficulty\":\"\"}],"
        "\"weekly_next\":[{\"category\":\"\",\"content\":\"\",\"difficulty\":\"\"}]}"
    )
    user_content = json.dumps(
        {
            "period": args.get("period", ""),
            "raw_work": args.get("raw_work", ""),
            "last_week_plan": args.get("last_week_plan", ""),
            "key_work": args.get("key_work", ""),
            "next_plan": args.get("next_plan", ""),
            "difficulties": args.get("difficulties", ""),
            "style": args.get("style", "简洁、具体、体现工作量"),
        },
        ensure_ascii=False,
        indent=2,
    )

    if settings["url"] and settings["key"]:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.25,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        rows = normalize_weekly_rows(parse_json_object(content))
        return {"ok": True, "mode": "api", "model": settings["model"], "draft": rows}

    optimized = local_optimize_text(source_text)
    summary = [
        {"category": "工作推进", "content": line, "status": "已推进", "plan": ""}
        for line in optimized.splitlines()
        if line.strip()
    ]
    return {
        "ok": True,
        "mode": "local_fallback",
        "warning": "未配置大模型 API，已使用本地规则生成基础周报草稿。",
        "draft": {"weekly_summary": summary, "weekly_follow": [], "weekly_next": []},
    }


def weekly_preview_skill(arguments, username):
    payload = weekly_payload_from_draft(arguments or {})
    path = generate_weekly(payload, username)
    draft = compose_draft("weekly", path.name, username)
    preview_name = path.with_suffix(".png").name
    preview_path = user_generated_dir(username) / preview_name
    create_weekly_preview_image(payload, preview_path)
    return {
        "ok": True,
        "file": path.name,
        "download_url": "/download?file=" + urllib.parse.quote(path.name),
        "preview_image": preview_name,
        "preview_image_url": "/preview-image?file=" + urllib.parse.quote(preview_name),
        "mail_draft": draft,
        "message": "周报预览已生成，请确认预览图片和邮件草稿；确认无误后再调用 weekly.send_confirmed。",
    }


def weekly_send_confirmed_skill(arguments, username):
    args = arguments or {}
    attachment = str(args.get("attachment", "") or "").strip()
    if not attachment:
        raise ValueError("请提供 weekly.preview 生成的 attachment 文件名")
    draft = compose_draft("weekly", attachment, username)
    payload = {
        "to": args.get("to") or draft.get("to", ""),
        "cc": args.get("cc") or draft.get("cc", ""),
        "subject": args.get("subject") or draft.get("subject", ""),
        "body": args.get("body") or draft.get("body", ""),
        "body_html": args.get("body_html") or draft.get("body_html", ""),
        "attachment": attachment,
    }
    return send_mail(payload, username)


def get_date_skill(args):
    from datetime import datetime, timedelta

    fmt = str(args.get("format") or "YYYY.MM.DD").strip()
    if fmt == "YYYY-MM-DD":
        date_fmt = "%Y-%m-%d"
    elif fmt == "YYYY/MM/DD":
        date_fmt = "%Y/%m/%d"
    else:
        date_fmt = "%Y.%m.%d"

    today = datetime.now()
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[today.weekday()]

    # 工作周起止（周一到周五），与周报页面默认时段保持一致。
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    week_start = monday.strftime(date_fmt)
    week_end = friday.strftime(date_fmt)

    # 本月起止
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    # 本季度起止
    quarter = (today.month - 1) // 3 + 1
    quarter_start_month = (quarter - 1) * 3 + 1
    quarter_start = today.replace(month=quarter_start_month, day=1)
    if quarter == 4:
        next_q_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_q_start = today.replace(month=quarter_start_month + 3, day=1)
    quarter_end = next_q_start - timedelta(days=1)

    # 第几周（ISO week）
    iso_year, iso_week, _ = today.isocalendar()

    return {
        "ok": True,
        "today": today.strftime(date_fmt),
        "weekday": weekday,
        "week_range": f"{week_start}-{week_end}",
        "week_start": week_start,
        "week_end": week_end,
        "month_range": f"{month_start.strftime(date_fmt)}-{month_end.strftime(date_fmt)}",
        "quarter": f"Q{quarter}",
        "quarter_range": f"{quarter_start.strftime(date_fmt)}-{quarter_end.strftime(date_fmt)}",
        "year": str(today.year),
        "iso_week": f"{iso_year} 年第 {iso_week} 周",
    }


def execute_skill(name, arguments, username):
    args = arguments or {}
    if name == "utils.get_date":
        return get_date_skill(args)
    if name == "reports.list":
        kind = str(args.get("kind", "all") or "all")
        reports = all_files(username)
        if kind in ("weekly", "trip"):
            reports = [item for item in reports if item.get("kind") == kind]
        return {"ok": True, "reports": reports[:50]}
    if name == "weekly.prefill":
        return weekly_prefill(username)
    if name == "weekly.compose":
        return compose_weekly_skill(args)
    if name == "weekly.preview":
        return weekly_preview_skill(args, username)
    if name == "weekly.send_confirmed":
        return weekly_send_confirmed_skill(args, username)
    if name == "trip.prefill":
        return trip_prefill(username)
    if name == "document.generate":
        return generate_document(args, username)
    if name == "text.optimize":
        return optimize_text(args)
    if name == "diary.save":
        return save_diary(args, username)
    if name == "diary.get":
        return get_diary(str(args.get("date", "") or ""), username)
    if name == "diary.list":
        return list_diaries(args, username)
    if name == "mailbox.list":
        return list_inbox_messages(username, args.get("limit", 20), bool(args.get("refresh", False)))
    if name == "mailbox.detail":
        return get_inbox_message(username, str(args.get("uid", "") or ""), bool(args.get("refresh", False)))
    if name == "mail.send":
        args["body_html"] = ""
        return send_mail(args, username)
    if name == "forum.list":
        return forum_list_topics(username)
    if name == "forum.create":
        return forum_create_topic(args, username)
    if name == "forum.comment":
        return forum_add_comment(args, username)
    if name == "news.latest":
        return news_latest(False)
    if name == "memory.remember":
        return globals().get("memory_remember_skill", lambda a, u: {"ok": False, "error": "memory 模块未加载"})(args, username)
    if name == "memory.search":
        return globals().get("memory_search_skill", lambda a, u: {"ok": False, "error": "memory 模块未加载"})(args, username)
    if name == "memory.forget":
        return globals().get("memory_forget_skill", lambda a, u: {"ok": False, "error": "memory 模块未加载"})(args, username)
    if name == "memory.summarize":
        return globals().get("memory_summarize_skill", lambda a, u: {"ok": False, "error": "memory 模块未加载"})(args, username)
    if name == "workflow.list":
        return globals().get("workflow_list_skill", lambda a, u: {"ok": False, "error": "workflow 模块未加载"})(args, username)
    if name == "workflow.run":
        return globals().get("workflow_run_skill", lambda a, u: {"ok": False, "error": "workflow 模块未加载"})(args, username)
    if name == "workflow.status":
        return globals().get("workflow_status_skill", lambda a, u: {"ok": False, "error": "workflow 模块未加载"})(args, username)
    if name == "workflow.confirm":
        return globals().get("workflow_confirm_skill", lambda a, u: {"ok": False, "error": "workflow 模块未加载"})(args, username)
    raise ValueError("未知 Skill：" + str(name))


def skill_test(payload, username):
    name = str(payload.get("name", "") or "").strip()
    skill = skill_by_name(name)
    if not skill:
        raise ValueError("未知 Skill：" + name)
    if not skill.get("safe") and not payload.get("confirm_unsafe"):
        raise ValueError("该 Skill 会产生写入、生成文件、发邮件或发布内容，请勾选确认后再测试")

    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("调用参数必须是 JSON 对象")

    instruction = str(payload.get("instruction", "") or "").strip()
    model_used = ""
    if instruction:
        settings = assistant_settings()
        if not settings["url"] or not settings["key"]:
            raise ValueError("未配置 AI 接口，请先在系统配置中设置 NewAPI 地址和 Key")
        system = (
            "你是智能办公助手的 Skill 测试器。"
            "请根据用户的自然语言测试要求，为指定 Skill 生成 arguments JSON 对象。"
            "只能返回 JSON 对象本身，不要返回 Markdown，不要调用其他 Skill。"
            "必须严格贴合 Skill 参数说明，不要编造用户没有提供的业务事实。"
        )
        user_prompt = (
            "待测试 Skill：\n"
            + json.dumps(skill, ensure_ascii=False, indent=2)
            + "\n\n已有参数草稿：\n"
            + json.dumps(arguments, ensure_ascii=False, indent=2)
            + "\n\n自然语言测试要求：\n"
            + instruction
        )
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        generated = parse_json_object(content)
        if not isinstance(generated, dict):
            raise ValueError("大模型未返回有效的 arguments JSON 对象")
        arguments = generated
        model_used = settings["model"]

    result = execute_skill(name, arguments, username)
    return {
        "ok": True,
        "skill": name,
        "model": model_used,
        "arguments": arguments,
        "result": result,
    }


def _extract_balanced_json(text):
    start = text.find("{")
    if start == -1:
        return None
    count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            count += 1
        elif text[i] == "}":
            count -= 1
            if count == 0:
                return text[start : i + 1]
    return None


def _parse_xml_tool_call(text):
    """解析 <invoke name=\"...\">...<parameter>..</parameter></invoke> 格式的 tool call。"""
    invoke_match = re.search(r"<invoke\s+name=\"([^\"]+)\"[^>]*>(.*?)</invoke>", text, flags=re.S)
    if not invoke_match:
        # 也尝试 <minimax:tool_call>...<invoke>...</invoke>...</minimax:tool_call>
        invoke_match = re.search(r"<invoke\s+name=[\"']([^\"']+)[\"'][^>]*>(.*?)</invoke>", text, flags=re.S)
    if not invoke_match:
        return None
    name = invoke_match.group(1).strip()
    inner = invoke_match.group(2)
    arguments = {}
    for param_match in re.finditer(r"<parameter\s+name=\"([^\"]+)\">(.*?)</parameter>", inner, flags=re.S):
        key = param_match.group(1).strip()
        val = param_match.group(2).strip()
        try:
            arguments[key] = json.loads(val)
        except Exception:
            arguments[key] = val
    return {"name": name, "arguments": arguments}


def parse_skill_call(text):
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    # Try direct parse first
    data = None
    try:
        data = parse_json_object(raw)
    except Exception:
        pass
    # Try extracting [TOOL_CALL] ... [/TOOL_CALL] format
    if not data:
        tool_match = re.search(r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]", raw, flags=re.S)
        if tool_match:
            try:
                data = parse_json_object(tool_match.group(1))
            except Exception:
                pass
    # Try extracting JSON object from mixed text and fix unescaped control chars
    if not data:
        json_str = _extract_balanced_json(raw)
        if json_str:
            try:
                data = json.loads(json_str)
            except Exception:
                try:
                    fixed = json_str.replace("\n", "\\n").replace("\r", "\\r")
                    data = json.loads(fixed)
                except Exception:
                    pass
    if isinstance(data, dict):
        call = data.get("skill_call")
        if isinstance(call, dict) and call.get("name"):
            return {
                "reply": data.get("reply", ""),
                "name": str(call.get("name", "")).strip(),
                "arguments": call.get("arguments") or {},
            }
    # Try XML format (MiniMax etc.)
    xml_call = _parse_xml_tool_call(raw)
    if xml_call:
        return {
            "reply": "",
            "name": xml_call["name"],
            "arguments": xml_call["arguments"],
        }
    return None


def _clean_agent_reply(text):
    """从大模型回复中提取自然语言，去掉嵌入的 JSON/Skill 调用标记。"""
    if not text:
        return text
    # 去掉 [TOOL_CALL] ... [/TOOL_CALL]
    cleaned = re.sub(r"\[TOOL_CALL\].*?\[/TOOL_CALL\]", "", text, flags=re.S).strip()
    # 去掉 <minimax:tool_call> ... </minimax:tool_call>
    cleaned = re.sub(r"<minimax:tool_call>.*?</minimax:tool_call>", "", cleaned, flags=re.S).strip()
    # 去掉 <invoke>...</invoke>
    cleaned = re.sub(r"<invoke[^>]*>.*?</invoke>", "", cleaned, flags=re.S).strip()
    # 去掉独立的大括号 JSON 块（如果它占了多行或紧跟在文字后面）
    cleaned = re.sub(r"\n?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?", "\n", cleaned).strip()
    # 去掉 Markdown 代码块
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S).strip()
    return cleaned


def agent_chat(payload, username=""):
    """Delegate to the new AI-native Agent Runtime if available.

    Falls back to legacy inline implementation if agent_runtime module
    is not loaded (e.g. during partial imports in tests).
    """
    # Check if agent_runtime's agent_chat is available and different from this function
    runtime_chat = globals().get("agent_chat")
    if runtime_chat is not None and runtime_chat is not agent_chat:
        return runtime_chat(payload, username)

    # Legacy implementation kept for compatibility during transition
    return _legacy_agent_chat(payload, username)


def _build_ui_patches_from_skill_calls(executed_calls):
    """Auto-generate ui_patches from executed skill call results for AI-native frontend."""
    patches = []
    for call in executed_calls:
        name = call.get("name", "")
        result = call.get("result", {}) or {}
        if name == "weekly.compose" and result.get("draft"):
            patches.append({"op": "set_field", "selector": "#weeklyDraft", "value": result["draft"]})
            patches.append({
                "op": "show_card",
                "card_type": "success",
                "data": {
                    "title": "周报草稿已生成",
                    "message": f"工作总结 {len(result['draft'].get('weekly_summary') or [])} 项 · 重点跟进 {len(result['draft'].get('weekly_follow') or [])} 项 · 下周计划 {len(result['draft'].get('weekly_next') or [])} 项",
                },
            })
        elif name == "weekly.preview" and result.get("preview_image_url"):
            patches.append({
                "op": "show_card",
                "card_type": "preview",
                "data": result,
            })
        elif name == "weekly.send_confirmed" and result.get("ok"):
            patches.append({
                "op": "show_card",
                "card_type": "success",
                "data": {"title": "周报已发送", "message": result.get("message", "")},
            })
        elif name == "diary.save" and result.get("ok"):
            patches.append({
                "op": "show_card",
                "card_type": "success",
                "data": {"title": "日记已保存", "message": result.get("message", "")},
            })
        elif name == "mail.send" and result.get("ok"):
            patches.append({
                "op": "show_card",
                "card_type": "success",
                "data": {"title": "邮件已发送", "message": result.get("message", "")},
            })
        elif name == "document.generate" and result.get("ok"):
            patches.append({
                "op": "show_card",
                "card_type": "preview",
                "data": result,
            })
    return patches


def _legacy_agent_chat(payload, username=""):
    kind = payload.get("kind", "weekly")
    messages = payload.get("messages", [])
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key"}

    system = AGENT_SYSTEM_PROMPTS.get(kind) or AGENT_SYSTEM_PROMPTS.get("weekly")
    system = (
        system
        + "\n\n你现在运行在「智能办公助手 Skill 模式」。"
        + "\n如果用户要求你操作软件功能，请从下面 Skill 中选择一个调用。"
        + "\n周报工作流必须按顺序执行：1) weekly.compose 规范化并填入周报结构；2) weekly.preview 生成周报文件、预览图片和邮件草稿；3) 只有用户明确确认预览无误后，才能调用 weekly.send_confirmed 发送邮件。"
        + '\n调用时必须且只能输出严格 JSON（禁止 Markdown、XML、[TOOL_CALL]）：{"reply":"说明","skill_call":{"name":"skill.name","arguments":{}}}'
        + "\n如果不需要操作软件功能，直接自然语言回复。"
        + "\n如需当前日期、本周起止日期、今天是星期几等时间信息，可调用 utils.get_date。"
        + "\n可用 Skill：\n"
        + json.dumps(skill_defs(), ensure_ascii=False)
    )
    api_messages = [{"role": "system", "content": system}]
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = str(m.get("content", "") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        api_messages.append({"role": role, "content": content})

    try:
        executed_calls = []
        max_rounds = 3
        for _round in range(max_rounds):
            data = request_json(
                settings["url"] + "/v1/chat/completions",
                settings["key"],
                {
                    "model": settings["model"],
                    "messages": api_messages,
                    "temperature": 0.6 if _round == 0 else 0.4,
                },
                "POST",
                60,
            )
            content = data["choices"][0]["message"]["content"].strip()
            skill_call = parse_skill_call(content)
            if not skill_call:
                # 没有新的 Skill 调用，直接返回最终回复
                final_reply = _clean_agent_reply(content)
                ui_patches = _build_ui_patches_from_skill_calls(executed_calls)
                if executed_calls:
                    return {
                        "ok": True,
                        "reply": final_reply,
                        "skill_calls": executed_calls,
                        "ui_patches": ui_patches,
                    }
                return {"ok": True, "reply": final_reply, "ui_patches": ui_patches}
            # 执行 Skill
            result = execute_skill(skill_call["name"], skill_call["arguments"], username)
            executed_calls.append({
                "name": skill_call["name"],
                "arguments": skill_call["arguments"],
                "result": result,
            })
            # 将结果反馈给大模型，继续下一轮
            api_messages.append({"role": "assistant", "content": content})
            api_messages.append({
                "role": "user",
                "content": (
                    "[系统通知：你刚才调用了 Skill '" + skill_call["name"] + "'，执行结果如下。"
                    "如果任务已完成，请用自然语言回复用户。"
                    "如果还需要继续操作（如先生成草稿再生成预览），可以继续调用下一个 Skill。]\n"
                    + json.dumps(result, ensure_ascii=False)
                ),
            })
        # 达到最大轮次，返回最后一次回复
        ui_patches = _build_ui_patches_from_skill_calls(executed_calls)
        return {
            "ok": True,
            "reply": content,
            "skill_calls": executed_calls,
            "ui_patches": ui_patches,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def save_agent_config(payload):
    cfg = read_agent_config()
    if "prompts" in payload:
        cfg["prompts"] = payload["prompts"]
    if "workflows" in payload:
        cfg["workflows"] = payload["workflows"]
    write_agent_config(cfg)
    load_agent_config()
    return {"ok": True, "message": "犇犇配置已保存并生效"}


def agent_orchestration():
    return {
        "ok": True,
        "agents": AGENT_SYSTEM_PROMPTS,
        "skill_mode_suffix": (
            "\\n\\n你现在运行在「智能办公助手 Skill 模式」。"
            "\\n如果用户要求你操作软件功能，请从下面 Skill 中选择一个调用。"
            '\\n调用时只输出严格 JSON：{\\"reply\\":\\"说明\\",\\"skill_call\\":{\\"name\\":\\"skill.name\\",\\"arguments\\":{}}}'
            "\\n如果不需要操作软件功能，直接自然语言回复。"
        ),
        "workflows": AGENT_WORKFLOWS,
        "skills": skill_defs(),
    }


# ===== 工作日记 =====
