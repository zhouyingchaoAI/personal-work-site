"""Runtime loader for the modularized personal office assistant backend.

The original application grew as one script. During modularization we load the
feature modules below into a shared namespace so existing cross-feature calls keep
working while each domain now lives in a readable file. New code should prefer
adding focused helpers to the relevant module and, over time, moving shared
contracts into explicit imports.
"""
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
APP_ENTRY = APP_ROOT / "app.py"
MODULE_DIR = Path(__file__).resolve().parent
MODULES = [
    "core.py",
    "login_sessions.py",
    "db.py",
    "office_store.py",
    "assistant_permissions.py",
    "organization_excel.py",
    "internal_organization.py",
    "crm_security.py",
    "reports.py",
    "mail.py",
    "password_reset.py",
    "text_tools.py",
    "skills_agent.py",
    "diary.py",
    "project.py",
    "ledger.py",
    "cashflow.py",
    "cashflow_insights.py",
    "cashflow_workbook.py",
    "data_center.py",
    "data_center_browse.py",
    "data_center_api.py",
    "data_center_databases.py",
    "data_center_dataflow.py",
    "data_center_ownership.py",
    "data_center_storage.py",
    "contract_documents.py",
    "crm_store.py",
    "crm_configuration.py",
    "crm_graph.py",
    "crm.py",
    "crm_rail.py",
    "crm_excel.py",
    "crm_monthly_battle.py",
    "forum.py",
    "tickets.py",
    "news.py",
    "documents.py",
    "skill_runtime.py",
    "agent_runtime.py",
    "memory.py",
    "workflows.py",
    "mcp.py",
    "fastgpt.py",
    "reimbursement.py",
    "digital_human.py",
    "meeting.py",
    "knowledge.py",
    "pdf_markdown.py",
    "writing.py",
    "server.py",
]

# Preserve the old script semantics for path calculations such as BASE_DIR.
globals()["__file__"] = str(APP_ENTRY)

for module_name in MODULES:
    module_path = MODULE_DIR / module_name
    source = module_path.read_text(encoding="utf-8")
    exec(compile(source, str(module_path), "exec"), globals())

__all__ = [name for name in globals() if not name.startswith("_")]
