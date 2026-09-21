"""Assistant entitlements. Missing overrides inherit defaults, including future assistants."""
ASSISTANT_IDS = ("writing", "weekly", "trip", "diary", "forum", "news", "mailassistant",
                 "meeting", "knowledge", "project", "crm", "ledger", "cashflow", "workflow",
                 "reimbursement", "lobsterbase")
# 资金测算涉及项目回款与垫资数据，和客户经营、经营台账一样默认仅超级管理员可用。
ASSISTANT_DEFAULT_DENIED = {"crm", "ledger", "cashflow"}


def assistant_permissions(user):
    overrides = user.get("assistant_permissions", {})
    if not isinstance(overrides, dict):
        overrides = {}
    result = {key: user.get("role") == "superadmin" or
            overrides.get(key, key not in ASSISTANT_DEFAULT_DENIED) is True
            for key in ASSISTANT_IDS}
    result["crm"] = crm_capabilities(user)["read"]
    return result


def require_assistant_access(username, assistant):
    user = find_user(username)
    if not user or not assistant_permissions(user).get(assistant, False):
        raise PermissionError("没有该助手的使用权限，请联系超级管理员授权")


def validate_assistant_permissions(value):
    if not isinstance(value, dict) or any(k not in ASSISTANT_IDS or type(v) is not bool for k, v in value.items()):
        raise ValueError("助手权限必须是有效助手与布尔值的映射")
    return dict(value)


def assistant_for_path(path):
    for prefix, assistant in (
        ("/api/crm", "crm"), ("/api/ledger", "ledger"), ("/api/cashflow", "cashflow"), ("/api/contracts", "ledger"),
        ("/api/projects", "project"), ("/api/writing", "writing"),
        ("/api/diary", "diary"), ("/api/forum", "forum"), ("/api/news", "news"),
        ("/api/meeting", "meeting"), ("/api/knowledge", "knowledge"),
        ("/api/ragflow", "knowledge"), ("/api/reimbursement", "reimbursement"),
        ("/api/workflows", "workflow"), ("/api/weekly", "weekly"), ("/api/trip", "trip"),
        ("/api/mailbox", "mailassistant"), ("/api/mail-send", "mailassistant"),
        ("/api/sent-mail", "mailassistant"), ("/api/lobster", "lobsterbase"),
        ("/api/openclaw-sso", "lobsterbase"), ("/api/my-lobsters", "lobsterbase"),
    ):
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "-"):
            return assistant
    return None
