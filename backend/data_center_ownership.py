"""Shared ownership metadata for the data center's assistant-first navigation."""

DC_OWNER_MODULES = {
    "crm": ["联指经营助手", "经营分析数据", "员工目录", "操作留痕与安全策略"],
    "writing": ["智能写作素材"], "weekly": ["周报与出差报告", "草稿", "生成文件", "工作日记"],
    "trip": ["周报与出差报告", "草稿", "生成文件"], "diary": ["工作日记"],
    "forum": ["金点子论坛"], "news": ["资讯缓存"],
    "mailassistant": ["邮件缓存", "邮件附件链接"], "meeting": ["会议记录"],
    "knowledge": ["知识库文件", "PDF 转 Markdown"], "project": ["项目资料"],
    "ledger": ["项目管理台账", "合同单据"], "cashflow": ["资金测算", "资金测算模板", "资金测算导出"],
    "workflow": ["智能体记录（SQLite）"], "reimbursement": ["报销材料"],
    "datacenter": ["数据中台元数据"],
}
DC_OWNER_DATASETS = {
    "crm": ["crm.units", "crm.people", "crm.relations", "crm.actions", "crm.opportunities", "org.staff"],
    "cashflow": ["cashflow.history", "cashflow.insights"], "ledger": ["ledger.items"],
    "forum": ["forum.topics"], "datacenter": ["meta.assets", "meta.backups"],
    "platform": ["tickets.list", "agent.skill_invocations", "org.staff"],
}
DC_OWNER_METRICS = {
    "crm": ["客户单位", "客户联系人", "客户关系", "跟进动作", "商机"],
    "cashflow": ["历史回款节点"], "ledger": ["台账项目"], "forum": ["论坛主题"],
    "platform": ["平台账号", "工单", "智能体会话", "智能体消息", "技能调用"],
}
DC_OWNER_PATHS = {
    "crm": ["*/crm", ".crm-security", ".crm-import-completion", "_crm*", ".crm-*.json"],
    "writing": ["*/writing"], "weekly": ["*/reports/weekly", "*/reports/*工作周报*", "*/drafts", "*/generated/weekly", "*/generated/*工作周报*", "*/diary"],
    "trip": ["*/reports/trip", "*/reports/出差报告*", "*/drafts", "*/generated/trip", "*/generated/*出差报告*"], "diary": ["*/diary"],
    "forum": ["_forum"], "news": ["_news", "*/news"],
    "mailassistant": ["*/mail_cache", "_mcp_mail_attachment_links"], "meeting": ["*/meetings"],
    "knowledge": ["knowledge", "*/knowledge", "*/pdf_markdown"], "project": ["projects"],
    "ledger": ["*/operating_ledger.json", "*/contract_documents"],
    "cashflow": ["*/cashflow_*.json", "*/cashflow_exports", "_cashflow"],
    "workflow": ["app.db"], "reimbursement": ["*/reimbursement"], "datacenter": ["_datacenter"],
    "platform": ["config.json", ".auth", "app.db", "_tickets", "*/profile"],
}


def dc_owner_subjects(groups):
    topology = _dcflow_topology()
    subjects = []
    platform_groups = [group for group in topology if group["node_type"] != "assistant"]
    for group in [group for group in topology if group["node_type"] == "assistant"] + [
            {"id": "platform", "label": "平台本身", "instances": [], "mirror_instances": []}]:
        ident = group["id"]
        members = platform_groups + [group] if ident == "platform" else [group]
        member_ids = [member["id"] for member in members]
        subjects.append({
            "id": ident, "label": group["label"], "group_ids": member_ids,
            "instances": sorted({instance for member in members for instance in member["instances"]}),
            "mirror_instances": sorted({instance for member in members for instance in member.get("mirror_instances", [])}),
            "modules": DC_OWNER_MODULES.get(ident, []) if ident != "platform" else
                ["用户资料", "平台工单", "智能体记录（SQLite）", "平台登录会话（SQLite）", "账号与平台配置", "账号与平台配置（config.json）"],
            "datasets": DC_OWNER_DATASETS.get(ident, []), "metrics": DC_OWNER_METRICS.get(ident, []),
            "items": [dict(item, owner_label=source["label"]) for source in groups
                      if source["id"] in member_ids for item in source["items"]],
        })
    return subjects


def dc_owner_path_matches(subject, rel, directory=False):
    from fnmatch import fnmatchcase
    if not subject or subject == "all":
        return True
    if subject not in ASSISTANT_IDS and subject != "platform":
        raise ValueError("未知助手或平台")
    parts = str(rel).strip("/").split("/")
    for pattern in DC_OWNER_PATHS.get(subject, []):
        pattern_parts = pattern.split("/")
        overlap = min(len(parts), len(pattern_parts))
        if all(fnmatchcase(parts[index], pattern_parts[index]) for index in range(overlap)):
            if len(parts) >= len(pattern_parts) or directory:
                return True
    return False


def dc_owner_file_roots(root, subject):
    if subject not in ASSISTANT_IDS and subject != "platform":
        raise ValueError("未知助手或平台")
    return [path for pattern in DC_OWNER_PATHS.get(subject, []) for path in root.glob(pattern)
            if path.resolve() == root or root in path.resolve().parents]
