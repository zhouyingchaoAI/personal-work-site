"""Assistant storage guide: live sources, synchronized tables and file archives."""

def _dc_store_enabled(module):
    """统一存储层开关（独立命名空间加载本模块时可能没有 office_store，按未切库处理）。"""
    fn = globals().get("officedb_enabled")
    return bool(fn and fn(module))


def _dc_store_module(ident):
    fn = globals().get("office_store_module")
    return fn(ident) if fn else ident



def _dcstorage_item(data, mode, primary, tables=(), note=""):
    return {"data": data, "mode": mode, "primary": primary,
            "mirror_tables": list(tables), "note": note}


def _dcstorage_live(module, data, file_primary, tables=(), note="", kind="documents", key_hint=""):
    """按统一存储层开关决定条目：已切库显示 office-postgres · app.*，否则显示原文件位置。
    kind：documents / blobs / mixed / cache / events。"""
    if not _dc_store_enabled(module):
        return _dcstorage_item(data, "file", file_primary, tables, note)
    table = {"documents": "app.documents", "blobs": "app.blobs", "mixed": "app.documents / app.blobs",
             "cache": "app.cache_documents / app.cache_blobs", "events": "app.events"}[kind]
    hint = key_hint or file_primary
    live_note = f"已切库，业务直接读写数据库（module={module}）；原文件 {file_primary} 保留为切换前快照，不再参与读写。"
    if kind == "cache":
        live_note = f"可重建缓存，单独放在 cache 表并排除在备份之外；原目录 {file_primary} 保留为切换前快照。"
    return _dcstorage_item(data, "database", f"office-postgres · {table}（键前缀 {hint}）", tables,
                           (note + " " if note else "") + live_note)


def dcstorage_overview():
    item = _dcstorage_item
    raw = ("raw.documents", "files.catalog")
    files = ("files.catalog",)
    details = {
        "platform": [
            item("平台账号、助手授权与公共配置", "file", "项目根目录 config.json", ("auth.users", "settings.user_mail"), "平台共享配置，不归属于某个业务助手；凭据仅脱敏展示。"),
            item("平台登录会话", "database", ".auth/sessions.sqlite3 · login_sessions", (), "保存令牌摘要与有效期。"),
            _dcstorage_live("platform", "用户头像与导航偏好", "<用户>/profile/", raw, kind="mixed"),
        ],
        "writing": [
            _dcstorage_live("writing", "写作历史、模板与素材记录", "<用户>/writing/（JSON）", raw),
            _dcstorage_live("writing", "上传素材、导出文档", "<用户>/writing/uploads、exports", files, kind="blobs"),
        ],
        "weekly": [
            _dcstorage_live("reports", "周报原稿、草稿、生成文件、预览图", "<用户>/reports/weekly、drafts、generated（含旧版报告目录）", raw,
                            "周报与出差报告共用 reports 模块。", kind="blobs"),
            _dcstorage_live("diary", "引用的工作日记", "<用户>/diary/*.json", raw, "与工作日记助手共享素材。"),
        ],
        "trip": [_dcstorage_live("reports", "出差报告、草稿、生成文档", "<用户>/reports/trip、drafts、generated（含旧版报告目录）", raw,
                                 "周报与出差报告共用 reports 模块；共享模板 templates/ 同样入库。", kind="blobs")],
        "diary": [_dcstorage_live("diary", "每日工作记录与总结", "<用户>/diary/*.json", raw)],
        "forum": [
            _dcstorage_live("forum", "主题、回复等主题记录", "_forum/topics.json", ("collab.forum_topics",)),
            _dcstorage_live("forum", "论坛附件", "_forum/attachments/", raw, kind="blobs"),
        ],
        "news": [_dcstorage_live("news", "资讯简报、个人订阅结果、收藏与收藏统计", "_news/、<用户>/news/", raw)],
        "mailassistant": [
            item("邮箱服务端邮件", "external", "配置的 IMAP / SMTP 邮件服务器", (), "中台未核验外部邮件服务器存储，不能视为全量已入库。"),
            _dcstorage_live("mailassistant", "已发送记录与 MCP 附件下载链接", "<用户>/mail_cache/sent.json、_mcp_mail_attachment_links/", raw),
            _dcstorage_live("mailassistant", "收件箱快照与附件分片缓存（可重建）", "<用户>/mail_cache/（parts/ 与各快照 JSON）", raw, kind="cache"),
            item("邮件账号配置", "file", "项目根目录 config.json", ("settings.user_mail",), "中台只展示存储说明，不展示凭据。"),
        ],
        "meeting": [
            _dcstorage_live("meeting", "会议记录、转写与纪要", "<用户>/meetings/*.json", raw),
        ],
        "knowledge": [
            item("内置知识检索向量", "database", "Qdrant · 知识库集合", (), "按配置的知识库引擎使用；向量可重建。"),
            item("RAGFlow 元数据、全文索引与缓存", "database", "RAGFlow MySQL / Elasticsearch / Redis", (), "按配置的知识库引擎使用，属于外部服务数据库。"),
            item("RAGFlow 上传文件本体", "object", "RAGFlow MinIO 对象存储"),
            _dcstorage_live("knowledge", "本地文档记录与 RAGFlow 账号、会话映射", "knowledge/*.json（共享目录）", raw),
            item("平台问答会话与消息", "database", "app.db · agent_sessions / agent_messages", ("agentic.sessions", "agentic.messages"), "SQLite 是本地数据库，不是普通 JSON 文件；该表由多个功能共享。"),
        ],
        "project": [
            _dcstorage_live("project", "项目、成员与项目记录", "projects/projects.json", raw),
            _dcstorage_live("project", "项目资料与附件", "projects/<项目ID>/files/", files, kind="blobs"),
        ],
        "ledger": [
            _dcstorage_live("ledger", "项目合同、交付、验收回款等台账记录", "<用户>/operating_ledger.json", ("ledger.items",)),
            _dcstorage_live("ledger", "合同记录、原件及生成单据", "<用户>/contract_documents/", raw, kind="mixed"),
        ],
        "cashflow": [
            _dcstorage_live("cashflow", "历史回款与测算记录", "<用户>/cashflow_history.json", ("cashflow.history_records",)),
            _dcstorage_live("cashflow", "测算方案", "<用户>/cashflow_scenarios.json", ("cashflow.scenarios",)),
            _dcstorage_live("cashflow", "测算工作簿状态", "<用户>/cashflow_workbook_state.json", ("cashflow.workbook_state",)),
            _dcstorage_live("cashflow", "导出的测算工作簿", "<用户>/cashflow_exports/", files,
                            "测算模板 _cashflow/*.xlsx 随部署提供、只读，不属于业务数据。", kind="blobs"),
        ],
        "workflow": [
            item("FastGPT 应用编排、会话与知识数据", "database", "FastGPT MongoDB / pgvector / Redis"),
            item("FastGPT 附件本体", "object", "FastGPT MinIO 对象存储"),
            item("平台本地工作流实例", "database", "app.db · workflow_instances", ("raw.sqlite_rows",), "SQLite 原始行镜像与其他本地表共享。"),
        ],
        "reimbursement": [
            _dcstorage_live("reimbursement", "发票搜索与处理记录", "<用户>/reimbursement/searches/*.json", raw),
            _dcstorage_live("reimbursement", "发票文件、OFD 预览与报销输出附件", "<用户>/reimbursement/cache、ofd_preview、output", files, kind="blobs"),
        ],
        "lobsterbase": [
            item("平台账号与智能体管理记录", "external", "OpenClaw · platform.db（SQLite）", (), "部署配置显示使用 SQLite；尚未接入中台，未核验其表与数据。"),
            item("智能体工作目录与文件", "external", "OpenClaw 工作目录 / 对象存储", (), "不在办公平台入库范围内，待接入核验。"),
        ],
        "datacenter": [
            item("业务镜像、账号权限与文件索引", "database", "office-postgres · raw / auth / settings / cashflow / ledger / collab / agentic / files", (), "作为中台查询副本；不代表上游助手已切换主存储。"),
            item("可还原的文件归档", "database", "office-postgres · archive.entries / archive.chunks / archive.runs", (), "保存文件本体分块；归档后业务仍使用原目录。"),
            item("扫描、同步、备份状态、连接注册与切库开关", "file", "_datacenter/*.json", raw,
                 "备份进程与主服务之间的状态文件和数据库连接引导配置，必须留在文件里（数据库连接信息不能存在数据库中）。"),
            _dcstorage_live("datacenter", "数据库告警记录", "_datacenter/db_alerts.jsonl", (), kind="events"),
            _dcstorage_live("datacenter", "中台访问审计", "_datacenter/access_log.jsonl", ("audit.datacenter_access",), kind="events"),
            _dcstorage_live("datacenter", "切库迁移记录", "（无文件，直接入库）", (), kind="events", key_hint="store_migration"),
        ],
        "agent": [item("智能体会话、消息、事件、技能调用与记忆", "database", "app.db · agent_sessions / agent_messages / agent_events / skill_invocations / memory_items",
                       ("agentic.sessions", "agentic.messages", "agentic.events", "agentic.skill_invocations", "agentic.memory_items"))],
        "workorder": [_dcstorage_live("workorder", "工单记录", "_tickets/tickets.json", ("collab.tickets",)),
                      _dcstorage_live("forum", "工单附件（复用论坛附件目录）", "_forum/attachments/", (), kind="blobs")],
        "gateway": [item("模型网关管理数据", "database", "FastGPT AI Proxy PostgreSQL")],
        "dify": [item("Dify 平台数据与缓存", "database", "Dify PostgreSQL / Redis", (), "本项覆盖已注册数据库，不表示已盘点 Dify 全部附件存储。")],
        "foundry": [item("Foundry 平台数据", "database", "Foundry PostgreSQL", (), "本项覆盖已注册数据库，不表示已盘点全部外部文件。")],
    }
    crm_live = crmdb_enabled()
    crm_rows = [
        ("单位、联系人、关系、动作、商机、员工与关联", "crm.units / people / relations / actions / opportunities / staff / links", "<用户>/crm/*.json"),
        ("员工目录", "crm.staff_directory", "_crm_staff_directory.json"),
        ("业务变更历史", "crm.live_history", "<用户>/crm/history/*.jsonl"),
        ("经营分析快照与导入完善任务", "crm.live_blobs", "_crm_business_analysis.json、.crm-import-completion/"),
    ]
    details["crm"] = [item(name, "database" if crm_live else "file",
                           "office-postgres · " + table if crm_live else source, (),
                           "数据库开关已开启；原 JSON 保留为切换前快照，不再作为业务主数据。" if crm_live else "数据库开关未开启，业务仍读写文件。")
                      for name, table, source in crm_rows]
    configuration_live = crm_configuration_in_db()
    details["crm"] += [
        item("关系图谱与缓存", "database", "Neo4j / Redis", (), "派生图谱与缓存，不替代业务主数据。"),
        item("权限策略与人员区域归属", "database" if configuration_live else "file",
             "office-postgres · crm.configuration（policies / liaison_regions）" if configuration_live else ".crm-security/policies.json、liaison-regions.json"),
        item("操作审计", "database" if configuration_live else "file",
             "office-postgres · crm.security_events（时间、操作者、操作、状态、对象索引）" if configuration_live else ".crm-security/audit.jsonl",
             ("audit.crm_events",), "audit.crm_events 是中台定时同步副本；业务审计以左侧主存储为准。"),
        item("区域与质量规则", "database" if configuration_live else "file",
             "office-postgres · crm.configuration（regions / quality）" if configuration_live else ".crm-region-settings.json、.crm-quality-settings.json"),
        item("高德地图配置", "database" if configuration_live else "file",
             "office-postgres · crm.configuration（amap）" if configuration_live else ".crm-amap-settings.json", (), "地图安全密钥仅在服务端使用，对外浏览脱敏。"),
    ]
    sync = (read_json(datacenter_dir(USER_DATA_DIR) / "db_sync.json", {}) or {}).get("last") or {}
    checks = {entry["table"]: entry for entry in sync.get("tables", [])}
    groups = []
    for group in _dcflow_topology():
        rows = details.get(group["id"], [item("数据对应待核实", "unknown", "尚未登记")])
        for row in rows:
            row["mirror_evidence"] = [{"table": table, "verified": sync.get("ok") is True and checks.get(table, {}).get("match") is True,
                                        "rows": checks.get(table, {}).get("rows")}
                                       for table in row["mirror_tables"]]
        groups.append({"id": group["id"], "label": group["label"], "node_type": group["node_type"], "items": rows})
    platform = {"id": "platform", "label": "平台本身", "node_type": "system", "items": details["platform"]}
    for row in platform["items"]:
        row["mirror_evidence"] = [{"table": table, "verified": sync.get("ok") is True and checks.get(table, {}).get("match") is True,
                                  "rows": checks.get(table, {}).get("rows")} for table in row["mirror_tables"]]
    return {"ok": True, "assistants": groups, "subjects": dc_owner_subjects(groups + [platform]), "crm_live": crm_live,
            "sync": {"ok": sync.get("ok"), "finished_at": sync.get("finished_at"),
                     "archive_ok": (sync.get("file_archive") or {}).get("ok")},
            "office_store_modules": (globals().get("officedb_enabled_modules") or (lambda: []))(),
            "scope_note": "路径未注明时相对 user_data；<用户> 表示各用户目录。映射依据当前读写代码、CRM 开关与统一存储层开关（_datacenter/office_db.json）；已切库助手的原目录保留为切换前快照。镜像依据最近一次同步记录，非逐文件实时核验。共享表行数是全表记录数，不是该助手的数据量。"}
