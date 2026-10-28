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
            "name": "trip.compose",
            "module": "出差报告",
            "title": "编写/整理出差报告草稿",
            "description": "调用配置的大模型，把出差原始描述整理成出差报告结构：目的、行程、工作内容与成果、思路、问题、建议。",
            "parameters": {
                "location": "出差地点，可选",
                "trip_date_text": "出差日期文本，可选",
                "purpose": "出差目的，可选",
                "raw_work": "出差原始工作内容",
                "itinerary": "行程安排，可选",
                "details": "工作内容，可选",
                "issues": "问题与不足，可选",
                "suggestions": "建议，可选",
                "style": "输出风格，可选",
            },
            "safe": True,
        },
        {
            "name": "trip.preview",
            "module": "出差报告",
            "title": "生成出差报告预览",
            "description": "根据已整理的出差报告字段生成正式 Word 文件与邮件草稿，供用户确认后发送。",
            "parameters": {
                "department": "部门，可选",
                "location": "出差地点，可选",
                "trip_start": "出差开始日期，可选",
                "trip_end": "出差结束日期，可选",
                "trip_date_text": "出差日期文本，可选",
                "purpose": "出差目的",
                "itinerary": "行程安排",
                "details": "工作内容与成果",
                "work_approach": "工作思路/方法，可选",
                "issues": "问题与不足，可选",
                "suggestions": "建议与下一步，可选",
            },
            "safe": False,
        },
        {
            "name": "trip.send_confirmed",
            "module": "出差报告",
            "title": "确认后发送出差报告邮件",
            "description": "仅在用户确认出差报告预览无误后，使用当前账号邮件配置发送出差报告邮件。",
            "parameters": {
                "attachment": "出差报告文件名，通常来自 trip.preview",
                "to": "收件人，可选",
                "cc": "抄送，可选",
                "subject": "主题，可选",
                "body": "正文，可选",
            },
            "safe": False,
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
            "description": "保存或补充当前用户指定日期的工作日记；只提交本次要更新的字段，其他已记录内容会保留。",
            "parameters": {
                "date": "YYYY-MM-DD",
                "today_work": "今日工作（可选）",
                "tomorrow_plan": "明日计划（可选）",
                "thoughts": "想法心得（可选）",
                "clear_fields": "明确清空的字段数组，可选：today_work/tomorrow_plan/thoughts",
            },
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
            "description": "通过当前用户 IMAP 配置按固定查询快照读取邮件；支持按文件夹、日期范围（since/before）和主题关键词筛选。返回 total、has_more 和 next_cursor：涉及全部邮件、批量下载附件或合规检索时，只要 has_more=true，就必须携带上一页的 next_cursor 与完全相同的 folder、keyword、since、before 继续查询，直到 next_cursor=null。不要使用 page/offset；每页最大 200 条。注意：约1个月前的历史邮件多在“已归档”，发出的邮件在“已发送”——查半年请用对应 folder 或 folder=all。",
            "parameters": {
                "limit": "每页返回条数，默认20，最大200，可选",
                "since": "起始日期 YYYY-MM-DD（含当天），可选",
                "before": "截止日期 YYYY-MM-DD（不含当天），可选",
                "keyword": "主题关键词，可选",
                "folder": "文件夹，可选：inbox(默认)/archive(已归档)/sent(已发送)/drafts/trash/spam，或 all(收件箱+已归档合并)",
                "cursor": "上一页返回的 next_cursor；续页时须保留相同的 folder、keyword、since、before 条件，可选",
            },
            "safe": True,
        },
        {
            "name": "mailbox.detail",
            "module": "邮件",
            "title": "查看邮件详情",
            "description": "通过邮件 UID 读取邮件正文、HTML 预览和附件信息。若邮件来自非收件箱（如 mailbox.list 返回的 folder=已归档/已发送），需带上同样的 folder。",
            "parameters": {"uid": "邮件 UID", "folder": "邮件所在文件夹，来自 mailbox.list 返回项的 folder 字段，可选，默认 inbox"},
            "safe": True,
        },
        {
            "name": "mailbox.attachment",
            "module": "邮件",
            "title": "下载邮件附件",
            "description": "通过邮件 UID 与附件 part（来自 mailbox.detail 附件项的 part 字段，如 part2）获取免 Cookie 临时下载链接；默认不内联 base64，避免大附件截断。",
            "parameters": {"uid": "邮件 UID", "part": "附件 part_key，如 part2，来自 mailbox.detail", "include_base64": "是否同时返回 base64，默认 false", "max_bytes": "include_base64=true 时允许内联的最大字节数，默认 1048576"},
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
            "name": "tickets.list",
            "module": "工单系统", "title": "查询最新工单",
            "description": "实时读取工单列表，支持助手、提交人账号、状态、关键词和更新时间筛选。分页读取；updated_since 包含边界时间，轮询时按工单ID和updated_at去重。共享范围与平台工单系统一致。",
            "parameters": {"module": "助手名称，精确匹配，可选；可与status组合，例如联指经营助手", "author_username": "提交人账号，可选；历史工单可能没有账号", "author": "提交人署名，精确匹配，可选", "status": "all/unresolved/open/accepted/resolved/rejected，默认all；unresolved仅未结案（待处理和受理中），排除已解决和不采纳", "keyword": "关键词，可选", "updated_since": "原样使用上次返回的updated_at，ISO时间，可选", "offset": "非负整数，默认0", "limit": "整数1至100，默认30"},
            "safe": True,
        },
        {
            "name": "tickets.get",
            "module": "工单系统", "title": "查看实时工单详情",
            "description": "读取完整工单、截图附件元数据和全部回复。每次直接读取最新记录，不增加浏览量。附件URL仍需平台登录权限，不是公开下载链接。",
            "parameters": {"id": "必填，工单ID"}, "safe": True,
        },
        {
            "name": "tickets.image",
            "module": "工单系统", "title": "读取工单附件图片",
            "description": "根据工单ID和附件ID读取截图，MCP直接返回image内容，供视觉模型查看。支持工单正文和回复中的PNG/JPEG/GIF/WebP图片，最大10MB；先调用tickets.get取得附件ID。不接受任意URL或文件路径。",
            "parameters": {"id": "必填，工单ID", "attachment_id": "必填，该工单或回复中的图片附件ID"}, "safe": True,
        },
        {
            "name": "tickets.reply",
            "module": "工单系统", "title": "回复工单",
            "description": "向工单写入处理回复，以认证账号署名。必须提供confirm=true。status默认空表示仅回复；accepted/resolved/rejected改变状态，仅管理员可用。回复前先查看工单，不要将建议误报为已完成。",
            "parameters": {"id": "必填，工单ID", "content": "必填，回复内容", "status": "空/accepted/resolved/rejected，默认空", "confirm": "布尔值，必须为true确认写入"}, "safe": False,
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
            "description": "查看系统生成的最新每日资讯（全站公共简报）。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "news.personal",
            "module": "资讯",
            "title": "查看我的个人资讯",
            "description": "查看当前用户个人资讯的最新一期简报、历史列表与订阅配置（含公众号订阅）。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "news.sources",
            "module": "资讯",
            "title": "查看我订阅的资讯源",
            "description": "列出当前用户订阅的资讯源，按微信公众号与网页来源分组返回。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "news.search_wechat",
            "module": "资讯",
            "title": "搜索微信公众号",
            "description": "按名称搜索可订阅的微信公众号候选，优先使用已登录的公众号后台，返回候选供确认后订阅。",
            "parameters": {"query": "公众号名称关键词，至少两个字"},
            "safe": True,
        },
        {
            "name": "news.subscribe_wechat",
            "module": "资讯",
            "title": "订阅微信公众号",
            "description": "把一个微信公众号加入当前用户的个人资讯订阅源；可仅凭名称订阅，也可附一篇 mp.weixin.qq.com/s/... 文章链接作为入口。建议先用 news.search_wechat 确认名称。",
            "parameters": {
                "name": "公众号名称，必填",
                "url": "可选，一篇 mp.weixin.qq.com/s/... 的文章链接作为入口回退",
            },
            "safe": False,
        },
        {
            "name": "news.unsubscribe",
            "module": "资讯",
            "title": "取消订阅资讯源",
            "description": "按公众号名称或来源链接，从当前用户的个人资讯订阅中移除一个来源。",
            "parameters": {"target": "要取消订阅的公众号名称或来源链接"},
            "safe": False,
        },
        {
            "name": "news.generate",
            "module": "资讯",
            "title": "立即生成我的个人资讯",
            "description": "按当前用户的订阅源（含公众号）立即抓取并重新生成一期个人资讯简报。",
            "parameters": {"auto_search": "是否附加联网关键词检索，布尔，可选，默认按个人配置"},
            "safe": False,
        },
        {
            "name": "writing.uploads",
            "module": "智能写作",
            "title": "查看写作素材",
            "description": "列出当前用户已上传、可供写作引用的素材文件。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "writing.templates",
            "module": "智能写作",
            "title": "查看写作模板",
            "description": "列出当前用户可用的写作模板。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "writing.outline",
            "module": "智能写作",
            "title": "生成写作提纲",
            "description": "根据主题、要求与素材（可选引用知识库）生成 Markdown 大纲，仅返回文本不落库。",
            "parameters": {
                "title": "文稿标题，可选",
                "writing_type": "文体类型，如 通用文章/工作汇报，可选",
                "requirements": "写作要求，可选",
                "file_ids": "引用的素材文件 id 数组，可选",
                "use_knowledge": "是否引用知识库，布尔，可选",
                "kb_ids": "指定知识库 id 数组，可选",
            },
            "safe": True,
        },
        {
            "name": "writing.generate",
            "module": "智能写作",
            "title": "生成文稿",
            "description": "结合素材、提纲与知识库生成完整中文文稿，并保存为写作历史。",
            "parameters": {
                "title": "文稿标题，可选",
                "writing_type": "文体类型，可选",
                "requirements": "写作要求，可选",
                "outline": "提纲，可选",
                "audience": "目标读者，可选",
                "length": "篇幅要求，可选",
                "file_ids": "引用的素材文件 id 数组，可选",
                "use_knowledge": "是否引用知识库，布尔，可选",
                "kb_ids": "指定知识库 id 数组，可选",
            },
            "safe": False,
        },
        {
            "name": "writing.rewrite",
            "module": "智能写作",
            "title": "改写文稿",
            "description": "按要求对给定正文进行润色、扩写、缩写或语气调整，并保存为写作历史。",
            "parameters": {
                "content": "待改写正文，必填",
                "rewrite_instruction": "改写要求，可选",
                "title": "标题，可选",
            },
            "safe": False,
        },
        {
            "name": "writing.history",
            "module": "智能写作",
            "title": "查看写作历史",
            "description": "列出当前用户的写作历史（带正文摘要）。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "writing.get",
            "module": "智能写作",
            "title": "读取写作历史详情",
            "description": "按 id 读取一条写作历史的完整正文与元数据。",
            "parameters": {"id": "写作历史 id"},
            "safe": True,
        },
        {
            "name": "writing.export",
            "module": "智能写作",
            "title": "导出文稿",
            "description": "把写作正文导出为 Markdown 或 Word 文件，返回下载信息。",
            "parameters": {
                "id": "写作历史 id，可选（与 content 二选一）",
                "content": "直接导出的正文，可选（与 id 二选一）",
                "title": "文件标题，可选",
                "format": "导出格式：md 或 docx，默认 md",
            },
            "safe": False,
        },
        {
            "name": "meeting.list",
            "module": "会议",
            "title": "查看会议列表",
            "description": "列出当前用户已保存的会议记录（含时长、段落数、是否有纪要）。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "meeting.get",
            "module": "会议",
            "title": "查看会议详情",
            "description": "按 id 读取一场会议的转写段落、翻译与纪要。",
            "parameters": {"id": "会议 id"},
            "safe": True,
        },
        {
            "name": "meeting.summarize",
            "module": "会议",
            "title": "生成会议纪要",
            "description": "根据提供的会议转写文本生成结构化会议纪要，仅返回文本不落库。",
            "parameters": {"transcript": "会议转写全文，必填", "title": "会议标题，可选"},
            "safe": True,
        },
        {
            "name": "meeting.translate",
            "module": "会议",
            "title": "翻译会议文本",
            "description": "把一段会议文本翻译为目标语言。",
            "parameters": {"text": "待翻译文本，必填", "target": "目标语言代码，如 en/zh，默认 en"},
            "safe": True,
        },
        {
            "name": "meeting.save",
            "module": "会议",
            "title": "保存会议记录",
            "description": "新建或更新一场会议记录（标题、段落、纪要等）。",
            "parameters": {
                "id": "会议 id，可选；不传则新建",
                "title": "会议标题，可选",
                "segments": "转写段落数组，可选",
                "summary": "会议纪要，可选",
            },
            "safe": False,
        },
        {
            "name": "meeting.delete",
            "module": "会议",
            "title": "删除会议记录",
            "description": "按 id 删除一场会议记录。",
            "parameters": {"id": "会议 id"},
            "safe": False,
        },
        {
            "name": "knowledge.datasets",
            "module": "知识库",
            "title": "查看知识库列表",
            "description": "列出当前用户可用的知识库（含文档数、切片数）。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "knowledge.docs",
            "module": "知识库",
            "title": "查看知识库文档",
            "description": "按范围列出知识库中的文档。",
            "parameters": {"scope": "范围：mine(默认)/shared/all，可选"},
            "safe": True,
        },
        {
            "name": "knowledge.search",
            "module": "知识库",
            "title": "检索知识库",
            "description": "在知识库中做语义检索，返回命中片段与来源，用于引用溯源。",
            "parameters": {
                "query": "检索关键词，必填",
                "top_k": "返回片段数，默认 5，可选",
                "kb_ids": "限定知识库 id 数组，可选",
            },
            "safe": True,
        },
        {
            "name": "knowledge.ask",
            "module": "知识库",
            "title": "知识库问答",
            "description": "基于知识库检索结果回答问题，返回答案与引用来源。",
            "parameters": {
                "question": "问题，必填",
                "top_k": "检索片段数，默认 5，可选",
                "kb_ids": "限定知识库 id 数组，可选",
            },
            "safe": True,
        },
        {
            "name": "knowledge.delete",
            "module": "知识库",
            "title": "删除知识库文档",
            "description": "按 id 删除一篇知识库文档（共享库需管理员）。",
            "parameters": {"id": "文档 id", "scope": "范围，可选"},
            "safe": False,
        },
        {
            "name": "reimbursement.searches",
            "module": "报销",
            "title": "查看报销搜索记录",
            "description": "列出当前用户保存的报销发票扫描记录。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "reimbursement.search_detail",
            "module": "报销",
            "title": "查看报销记录详情",
            "description": "按记录 id 读取一次报销扫描的发票明细与切片状态。",
            "parameters": {"id": "报销搜索记录 id"},
            "safe": True,
        },
        {
            "name": "reimbursement.outputs",
            "module": "报销",
            "title": "查看报销输出文件",
            "description": "列出当前用户已生成的报销合并/打包文件。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "reimbursement.scan",
            "module": "报销",
            "title": "扫描邮箱发票",
            "description": "在指定日期范围内扫描邮箱附件，识别并归集发票（联网 IMAP，耗时较长）。",
            "parameters": {
                "start": "起始日期 YYYY-MM-DD，必填",
                "end": "截止日期 YYYY-MM-DD，必填",
                "account": "邮箱账号：company(默认)/personal，可选",
            },
            "safe": False,
        },
        {
            "name": "reimbursement.merge",
            "module": "报销",
            "title": "合并报销 PDF",
            "description": "把选中的发票合并为一个 PDF 报销材料，返回生成文件信息。",
            "parameters": {
                "items": "选中的发票项数组，必填",
                "output_name": "输出文件名，可选",
                "merge_train_tickets": "是否将火车票拼版合并，布尔，可选",
            },
            "safe": False,
        },
        {
            "name": "reimbursement.download_zip",
            "module": "报销",
            "title": "打包下载发票",
            "description": "把选中的发票打包为 ZIP，返回下载文件信息。",
            "parameters": {"items": "选中的发票项数组，必填", "output_name": "输出文件名，可选"},
            "safe": False,
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

    buffer = io.BytesIO()
    image.crop((0, 0, width, min(total_height, y + 36))).save(buffer, format="PNG")
    office_blob_write("reports", output_path, buffer.getvalue(), content_type="image/png")
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
        try:
            rows = normalize_weekly_rows(parse_json_object(content))
            if any(rows.values()):
                return {"ok": True, "mode": "api", "model": settings["model"], "draft": rows}
            raise ValueError("模型返回的周报 JSON 没有有效条目")
        except Exception as exc:
            # 模型偶尔会在长中文内容中漏掉转义，不能让一次格式问题中断整个
            # 审核流程。保留原始工作项并降级为规则草稿，用户仍可在审核卡完善。
            optimized = local_optimize_text(source_text)
            summary = [
                {"category": "工作推进", "content": line, "status": "已推进", "plan": ""}
                for line in optimized.splitlines()
                if line.strip()
            ]
            return {
                "ok": True,
                "mode": "local_fallback",
                "warning": f"模型返回格式异常，已保留原始工作内容生成基础草稿：{str(exc)[:120]}",
                "draft": {"weekly_summary": summary, "weekly_follow": [], "weekly_next": []},
            }

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


def compose_trip_skill(arguments):
    """把出差原始材料整理成系统可写入的出差报告 JSON 字段（与周报 compose 同构）。"""
    args = arguments or {}
    source_text = "\n".join(
        str(args.get(key, "") or "").strip()
        for key in ("raw_work", "itinerary", "details", "purpose", "issues", "suggestions", "work_approach")
        if str(args.get(key, "") or "").strip()
    )
    if not source_text:
        raise ValueError("请提供 raw_work / purpose / itinerary 等至少一项出差内容")

    settings = assistant_settings()
    prompt = (
        "你是企业出差报告 Skill，负责把出差原始描述整理成系统可写入的出差报告 JSON。"
        "要求：1、如实反映行程与工作成果，不编造未提供事项；2、语言简洁、书面、条理清晰；"
        "3、修正错别字；4、输出严格 JSON，不要 Markdown。"
        "JSON 格式："
        "{\"purpose\":\"出差目的\",\"itinerary\":\"行程安排\",\"details\":\"工作内容与成果\","
        "\"work_approach\":\"工作思路/方法\",\"issues\":\"问题与不足\",\"suggestions\":\"建议与下一步\"}"
    )
    user_content = json.dumps(
        {
            "location": args.get("location", ""),
            "date_text": args.get("trip_date_text", ""),
            "purpose": args.get("purpose", ""),
            "raw_work": args.get("raw_work", ""),
            "itinerary": args.get("itinerary", ""),
            "details": args.get("details", ""),
            "issues": args.get("issues", ""),
            "suggestions": args.get("suggestions", ""),
            "style": args.get("style", "简洁、具体、体现出差成果"),
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
        draft = parse_json_object(content)
        return {"ok": True, "mode": "api", "model": settings["model"], "draft": draft}

    optimized = local_optimize_text(source_text)
    return {
        "ok": True,
        "mode": "local_fallback",
        "warning": "未配置大模型 API，已使用本地规则生成基础出差报告草稿。",
        "draft": {
            "purpose": str(args.get("purpose", "") or ""),
            "itinerary": str(args.get("itinerary", "") or ""),
            "details": optimized,
            "work_approach": str(args.get("work_approach", "") or ""),
            "issues": str(args.get("issues", "") or ""),
            "suggestions": str(args.get("suggestions", "") or ""),
        },
    }


def trip_preview_skill(arguments, username):
    """按已整理的出差报告字段生成正式 Word 文件与邮件草稿，供确认后发送。"""
    args = arguments or {}
    payload = {
        "department": args.get("department", ""),
        "location": args.get("location", ""),
        "trip_start": args.get("trip_start", ""),
        "trip_end": args.get("trip_end", ""),
        "trip_date_text": args.get("trip_date_text", ""),
        "purpose": args.get("purpose", ""),
        "itinerary": args.get("itinerary", ""),
        "details": args.get("details", ""),
        "work_approach": args.get("work_approach", ""),
        "issues": args.get("issues", ""),
        "suggestions": args.get("suggestions", ""),
    }
    path = generate_trip(payload, username)
    draft = compose_draft("trip", path.name, username)
    return {
        "ok": True,
        "file": path.name,
        "download_url": "/download?file=" + urllib.parse.quote(path.name),
        "mail_draft": draft,
        "message": "出差报告已生成，请确认 Word 文件与邮件草稿；确认无误后再调用 trip.send_confirmed。",
    }


def trip_send_confirmed_skill(arguments, username):
    """确认无误后，用当前账号邮件配置发送出差报告邮件（与 weekly.send_confirmed 同构）。"""
    args = arguments or {}
    attachment = str(args.get("attachment", "") or "").strip()
    if not attachment:
        raise ValueError("请提供 trip.preview 生成的 attachment 文件名")
    draft = compose_draft("trip", attachment, username)
    payload = {
        "to": args.get("to") or draft.get("to", ""),
        "cc": args.get("cc") or draft.get("cc", ""),
        "subject": args.get("subject") or draft.get("subject", ""),
        "body": args.get("body") or draft.get("body", ""),
        "body_html": args.get("body_html") or draft.get("body_html", ""),
        "attachment": attachment,
    }
    return send_mail(payload, username)


def weekly_reporting_range(reference):
    """Return the workweek a newly created weekly report should cover.

    A Monday submission normally covers the workweek that just ended. On the
    other days, the calendar week's Monday–Friday range remains the default.
    """
    from datetime import timedelta

    monday = reference - timedelta(days=reference.weekday())
    if reference.weekday() == 0:
        monday -= timedelta(days=7)
    return monday, monday + timedelta(days=4)


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

    # 工作周起止（周一到周五），与周报页面默认时段保持一致；周一默认上个完整工作周。
    monday, friday = weekly_reporting_range(today)
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


def mailbox_attachment_skill(args, username):
    """返回邮件附件的 MCP 专用下载信息，无需浏览器 cookie 登录。

    默认只返回临时 download_url，避免大段 base64 被 Agent 写入 shell heredoc 时截断。
    调用方只有明确传 include_base64=true 时才会得到 content_base64。
    """
    args = args or {}
    uid = str(args.get("uid", "") or "").strip()
    part = str(args.get("part", "") or args.get("part_key", "") or "").strip()
    if not uid or not part:
        raise ValueError("请提供 uid 和 part（来自 mailbox.detail 附件项的 part 字段，如 part2）")
    include_base64 = bool(args.get("include_base64") or args.get("return_base64"))
    max_bytes = int(args.get("max_bytes", 1024 * 1024) or 1024 * 1024)
    path, data = get_mail_part_content(username, uid, part)  # 未缓存会自动从 IMAP 拉取
    name_only = path.name.split("__", 1)[-1] if "__" in path.name else path.name
    mime = mail_part_content_type_from_name(name_only, data)
    download_url = create_mcp_mail_attachment_link(username, uid, part)
    download_url_absolute = absolute_personal_work_url(download_url)
    result = {
        "ok": True,
        "uid": uid,
        "part": part,
        "name": name_only,
        "mime": mime or "application/octet-stream",
        "size": len(data),
        "download_url": download_url,
        "download_url_absolute": download_url_absolute,
        "download_url_expires_in_seconds": 3600,
        "download_note": "微信端/OpenClaw 请直接用 download_url_absolute 下载附件；不要把大附件 base64 写入 shell heredoc。此链接由 MCP 专用临时 token 授权，不依赖浏览器 cookie。",
        "base64_included": False,
    }
    if not include_base64:
        result["content_omitted"] = True
        result["omit_reason"] = "默认不内联返回 base64，避免大附件在 Agent/shell 中被截断；如确需 base64，请传 include_base64=true。"
        return result
    if len(data) > max_bytes:
        result["content_omitted"] = True
        result["omit_reason"] = f"附件 {len(data)} 字节超过 {max_bytes} 字节上限，未内联返回 base64；请使用 download_url 下载，或提高 max_bytes。"
        return result
    result["encoding"] = "base64"
    result["base64_included"] = True
    result["content_base64"] = base64.b64encode(data).decode("ascii")
    return result


def execute_skill(name, arguments, username):
    args = arguments or {}
    if name in ("tickets.list", "tickets.get", "tickets.reply", "tickets.image"):
        return ticket_mcp_tool(name, args, username)
    if name == "utils.get_date":
        return get_date_skill(args)
    if name == "reports.list":
        kind = str(args.get("kind", "all") or "all")
        permissions = assistant_permissions(find_user(username) or {})
        reports = [item for item in all_files(username) if permissions.get(item.get("kind"), False)]
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
    if name == "trip.compose":
        return compose_trip_skill(args)
    if name == "trip.preview":
        return trip_preview_skill(args, username)
    if name == "trip.send_confirmed":
        return trip_send_confirmed_skill(args, username)
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
        return list_mailbox_mcp(username, args)
    if name == "mailbox.detail":
        return get_inbox_message(
            username,
            str(args.get("uid", "") or ""),
            bool(args.get("refresh", False)),
            folder=args.get("folder"),
        )
    if name == "mailbox.attachment":
        return mailbox_attachment_skill(args, username)
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
    if name == "news.personal":
        return personal_news_latest(username)
    if name == "news.sources":
        return personal_news_sources_skill(username)
    if name == "news.search_wechat":
        return search_wechat_accounts(str(args.get("query", "") or ""))
    if name == "news.subscribe_wechat":
        return subscribe_personal_wechat(username, args.get("name", ""), args.get("url", ""))
    if name == "news.unsubscribe":
        return unsubscribe_personal_source(username, args.get("target", ""))
    if name == "news.generate":
        gen_payload = {}
        if "auto_search" in args:
            gen_payload["auto_search"] = bool(args.get("auto_search"))
        return generate_personal_news_issue(gen_payload, username)
    if name == "writing.uploads":
        return writing_uploads(username)
    if name == "writing.templates":
        return writing_templates(username)
    if name == "writing.outline":
        return writing_generate_outline(args, username)
    if name == "writing.generate":
        return writing_generate(args, username)
    if name == "writing.rewrite":
        return writing_rewrite(args, username)
    if name == "writing.history":
        return writing_history(username)
    if name == "writing.get":
        return writing_get_history(str(args.get("id", "") or ""), username)
    if name == "writing.export":
        return writing_export(args, username)
    if name == "meeting.list":
        return meeting_list(username)
    if name == "meeting.get":
        return meeting_get(str(args.get("id", "") or ""), username)
    if name == "meeting.summarize":
        return meeting_summarize(args, username)
    if name == "meeting.translate":
        return meeting_translate(args)
    if name == "meeting.save":
        return meeting_save(args, username)
    if name == "meeting.delete":
        return meeting_delete(args, username)
    if name == "knowledge.datasets":
        return kb_datasets(username)
    if name == "knowledge.docs":
        return kb_list(str(args.get("scope", "mine") or "mine"), username)
    if name == "knowledge.search":
        return kb_search(args, username)
    if name == "knowledge.ask":
        return kb_ask(args, username)
    if name == "knowledge.delete":
        return kb_delete(args, username)
    if name == "reimbursement.searches":
        return {"ok": True, "records": list_reimbursement_searches(username)}
    if name == "reimbursement.search_detail":
        return get_reimbursement_search(username, str(args.get("id", "") or ""))
    if name == "reimbursement.outputs":
        return {"ok": True, "outputs": list_reimbursement_outputs(username)}
    if name == "reimbursement.scan":
        return scan_invoice_attachments(
            username,
            str(args.get("start", "") or ""),
            str(args.get("end", "") or ""),
            str(args.get("account", "company") or "company"),
        )
    if name == "reimbursement.merge":
        return merge_reimbursement_pdf(
            username,
            args.get("items") or [],
            str(args.get("output_name", "合并发票") or "合并发票"),
            bool(args.get("merge_train_tickets", False)),
        )
    if name == "reimbursement.download_zip":
        return download_reimbursement_invoices_zip(
            username,
            args.get("items") or [],
            str(args.get("output_name", "发票批量下载") or "发票批量下载"),
        )
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
