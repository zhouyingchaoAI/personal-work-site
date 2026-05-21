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
    "db.py",
    "reports.py",
    "mail.py",
    "text_tools.py",
    "skills_agent.py",
    "diary.py",
    "forum.py",
    "news.py",
    "documents.py",
    "skill_runtime.py",
    "agent_runtime.py",
    "memory.py",
    "workflows.py",
    "server.py",
]

# Preserve the old script semantics for path calculations such as BASE_DIR.
globals()["__file__"] = str(APP_ENTRY)

for module_name in MODULES:
    module_path = MODULE_DIR / module_name
    source = module_path.read_text(encoding="utf-8")
    exec(compile(source, str(module_path), "exec"), globals())

__all__ = [name for name in globals() if not name.startswith("_")]
