"""AI-native Skill runtime and audit bridge.

This file is loaded after legacy business modules by ``backend.runtime``. It wraps
the existing hard-coded Skill implementation with a stable runtime surface:

- normalized Skill metadata for UI/Agent discovery
- safe/unsafe confirmation gate for the unified Skill API
- durable Skill invocation audit records

The old ``execute_skill(name, arguments, username)`` contract remains compatible:
callers still receive the raw Skill result.
"""
from __future__ import annotations

import traceback
from typing import Any

try:  # Normal import path when this file is imported as a module.
    from backend import db as _db_module
except Exception:  # Runtime exec path already loaded db helpers into globals.
    _db_module = None

_LEGACY_SKILL_DEFS = globals().get("skill_defs")
_LEGACY_EXECUTE_SKILL = globals().get("execute_skill")
_LEGACY_SKILL_BY_NAME = globals().get("skill_by_name")


def _init_db():
    init = globals().get("init_db") or (_db_module.init_db if _db_module else None)
    if init:
        return init()
    return None


def _record_skill_invocation(**kwargs):
    recorder = globals().get("record_skill_invocation") or (_db_module.record_skill_invocation if _db_module else None)
    if not recorder:
        return ""
    return recorder(**kwargs)


def _list_recent_skill_invocations(**kwargs):
    reader = globals().get("list_recent_skill_invocations") or (_db_module.list_recent_skill_invocations if _db_module else None)
    if not reader:
        return []
    return reader(**kwargs)


def _legacy_skill_defs() -> list[dict[str, Any]]:
    if not callable(_LEGACY_SKILL_DEFS):
        return []
    result = _LEGACY_SKILL_DEFS()
    return list(result) if isinstance(result, list) else []


def _safety_level(skill: dict[str, Any] | None) -> str:
    if not skill:
        return "unknown"
    if skill.get("safe"):
        return "safe"
    name = str(skill.get("name", ""))
    if "send" in name:
        return "external_action"
    if any(token in name for token in ("save", "create", "comment")):
        return "write_data"
    if any(token in name for token in ("preview", "generate")):
        return "write_file"
    return "unsafe"


def _confirmation_required(skill: dict[str, Any] | None) -> bool:
    return not bool((skill or {}).get("safe"))


def normalize_skill_definition(skill: dict[str, Any]) -> dict[str, Any]:
    """Return a backward-compatible but richer Skill definition."""
    item = dict(skill)
    item.setdefault("version", "1.0.0")
    item.setdefault("parameters", {})
    item.setdefault("safe", True)
    item.setdefault("safety", _safety_level(item))
    item.setdefault("confirmation", "required" if _confirmation_required(item) else "none")
    item.setdefault("input_schema", {"type": "object", "properties": item.get("parameters", {})})
    item.setdefault("output_schema", item.get("detail", {}).get("output_schema", {}) if isinstance(item.get("detail"), dict) else {})
    item.setdefault("roles", ["member", "admin", "superadmin"])
    item.setdefault("enabled", True)
    return item


def skill_defs():
    return [normalize_skill_definition(item) for item in _legacy_skill_defs()]


def skill_by_name(name):
    target = str(name or "").strip()
    for item in skill_defs():
        if item.get("name") == target:
            return item
    return None


def execute_skill_raw(name, arguments, username):
    """Execute the legacy Skill handler without audit side effects."""
    if not callable(_LEGACY_EXECUTE_SKILL):
        raise ValueError("Skill Runtime 未找到旧版 Skill 执行器")
    return _LEGACY_EXECUTE_SKILL(name, arguments or {}, username)


def execute_skill_with_audit(
    name,
    arguments,
    username,
    *,
    source="agent",
    session_id=None,
    confirmed=None,
):
    """Execute a Skill and persist an invocation audit record."""
    _init_db()
    skill_name = str(name or "").strip()
    skill = skill_by_name(skill_name)
    if not skill:
        raise ValueError("未知 Skill：" + skill_name)
    args = arguments or {}
    if not isinstance(args, dict):
        raise ValueError("调用参数必须是 JSON 对象")

    safety = _safety_level(skill)
    was_confirmed = bool(confirmed) if confirmed is not None else bool(skill.get("safe"))
    try:
        result = execute_skill_raw(skill_name, args, username)
        invocation_id = _record_skill_invocation(
            user_id=username or "anonymous",
            session_id=session_id,
            skill_name=skill_name,
            skill_version=str(skill.get("version", "1.0.0")),
            source=source or "agent",
            arguments=args,
            result=result if isinstance(result, dict) else {"value": result},
            status="success",
            safety_level=safety,
            confirmed=was_confirmed,
        )
        return {"invocation_id": invocation_id, "result": result}
    except Exception as exc:
        _record_skill_invocation(
            user_id=username or "anonymous",
            session_id=session_id,
            skill_name=skill_name,
            skill_version=str(skill.get("version", "1.0.0")),
            source=source or "agent",
            arguments=args,
            result=None,
            status="failed",
            safety_level=safety,
            confirmed=was_confirmed,
            error="{}\n{}".format(exc, traceback.format_exc(limit=4)),
        )
        raise


def execute_skill(name, arguments, username, source="agent", session_id=None, confirmed=None):
    """Backward-compatible Skill executor returning the raw Skill result."""
    return execute_skill_with_audit(
        name,
        arguments,
        username,
        source=source,
        session_id=session_id,
        confirmed=confirmed,
    )["result"]


def execute_skill_request(payload, username):
    """Unified /api/skills/execute request handler."""
    payload = payload or {}
    name = str(payload.get("skill") or payload.get("name") or "").strip()
    arguments = payload.get("arguments") or {}
    source = str(payload.get("source") or "ui").strip() or "ui"
    session_id = payload.get("session_id") or None
    confirmed = bool(payload.get("confirm_unsafe") or payload.get("confirmed"))

    skill = skill_by_name(name)
    if not skill:
        raise ValueError("未知 Skill：" + name)
    if not isinstance(arguments, dict):
        raise ValueError("调用参数必须是 JSON 对象")
    if _confirmation_required(skill) and not confirmed:
        return {
            "ok": False,
            "skill": name,
            "requires_confirmation": True,
            "safety": _safety_level(skill),
            "message": "该 Skill 会产生写入、生成文件、发邮件或发布内容，请确认后再执行。",
        }

    audited = execute_skill_with_audit(
        name,
        arguments,
        username,
        source=source,
        session_id=session_id,
        confirmed=confirmed or bool(skill.get("safe")),
    )
    return {
        "ok": True,
        "skill": name,
        "invocation_id": audited.get("invocation_id", ""),
        "safety": _safety_level(skill),
        "requires_confirmation": False,
        "result": audited.get("result"),
    }


def skill_invocation_history(payload, username):
    payload = payload or {}
    limit = payload.get("limit", 20)
    return {
        "ok": True,
        "invocations": _list_recent_skill_invocations(user_id=username or "anonymous", limit=limit),
    }
