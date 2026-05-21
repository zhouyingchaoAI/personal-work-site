"""Workflow Engine: declarative task orchestration with variable interpolation.

Provides:
- Workflow definition (JSON) with step-by-step skill calls
- Variable interpolation: {{step_id.result.field}} → value
- State machine: pending → running → paused → completed / failed
- Resume from interruption, human confirmation gates
- Integration with Agent Runtime (workflows can be triggered by Agent)

Loaded by backend.runtime into the shared namespace.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _json_loads(value: str | None, fallback: Any = None) -> Any:
    if not value:
        return {} if fallback is None else fallback
    try:
        return json.loads(value)
    except Exception:
        return {} if fallback is None else fallback


def _db_connect():
    conn_fn = globals().get("connect")
    if conn_fn:
        return conn_fn()
    try:
        from backend import db as _db
        return _db.connect()
    except Exception:
        raise RuntimeError("Database connection not available") from None


def _init_db():
    init_fn = globals().get("init_db")
    if init_fn:
        return init_fn()
    try:
        from backend import db as _db
        return _db.init_db()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Workflow definitions (in-memory registry; can be extended to DB later)
# ---------------------------------------------------------------------------

_BUILTIN_WORKFLOWS: dict[str, dict] = {
    "weekly.from_diary": {
        "id": "weekly.from_diary",
        "name": "根据日记生成周报",
        "description": "自动获取本周日记，汇总后生成周报草稿和预览",
        "steps": [
            {"id": "get_date", "skill": "utils.get_date", "arguments": {}},
            {
                "id": "list_diary",
                "skill": "diary.list",
                "arguments": {
                    "start": "{{get_date.result.week_start}}",
                    "end": "{{get_date.result.week_end}}",
                },
            },
            {
                "id": "compose",
                "skill": "weekly.compose",
                "arguments": {
                    "raw_work": "{{list_diary.result.summary}}",
                },
            },
            {
                "id": "preview",
                "skill": "weekly.preview",
                "arguments": {
                    "period": "{{get_date.result.week_range}}",
                    "weekly_summary": "{{compose.result.weekly_summary}}",
                },
            },
        ],
        "on_error": "pause",
        "requires_confirmation_at": ["preview"],
    },
    "mail.summarize_and_reply": {
        "id": "mail.summarize_and_reply",
        "name": "总结邮件并生成回复草稿",
        "description": "获取邮件内容，生成摘要和回复建议",
        "steps": [
            {"id": "get_mail", "skill": "mail.get", "arguments": {"uid": "{{input.uid}}"}},
            {
                "id": "summarize",
                "skill": "text.summarize",
                "arguments": {"text": "{{get_mail.result.body}}", "max_length": 200},
            },
            {
                "id": "draft_reply",
                "skill": "mail.draft_reply",
                "arguments": {
                    "original": "{{get_mail.result.body}}",
                    "summary": "{{summarize.result.summary}}",
                    "tone": "{{input.tone|professional}}",
                },
            },
        ],
        "on_error": "pause",
        "requires_confirmation_at": ["draft_reply"],
    },
}


def list_workflows() -> list[dict]:
    """Return all available workflow definitions."""
    return [
        {
            "id": w["id"],
            "name": w["name"],
            "description": w.get("description", ""),
            "step_count": len(w.get("steps", [])),
            "requires_confirmation_at": w.get("requires_confirmation_at", []),
        }
        for w in _BUILTIN_WORKFLOWS.values()
    ]


def get_workflow(workflow_id: str) -> dict | None:
    """Get a workflow definition by ID."""
    return copy.deepcopy(_BUILTIN_WORKFLOWS.get(workflow_id))


# ---------------------------------------------------------------------------
# Workflow instance (stateful execution)
# ---------------------------------------------------------------------------

class WorkflowInstance:
    """Represents a running or completed workflow execution."""

    def __init__(
        self,
        workflow_id: str,
        user_id: str,
        inputs: dict | None = None,
        instance_id: str | None = None,
    ):
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.inputs = inputs or {}
        self.instance_id = instance_id or ("wf_" + uuid.uuid4().hex[:20])
        self.status = "pending"  # pending | running | paused | completed | failed
        self.current_step_index = 0
        self.step_results: dict[str, Any] = {}
        self.logs: list[dict] = []
        self.created_at = _utc_now()
        self.updated_at = self.created_at
        self.error_info: dict | None = None

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "status": self.status,
            "current_step_index": self.current_step_index,
            "step_results": self.step_results,
            "logs": self.logs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error_info": self.error_info,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowInstance":
        obj = cls(
            workflow_id=data["workflow_id"],
            user_id=data["user_id"],
            inputs=data.get("inputs", {}),
            instance_id=data.get("instance_id"),
        )
        obj.status = data.get("status", "pending")
        obj.current_step_index = data.get("current_step_index", 0)
        obj.step_results = data.get("step_results", {})
        obj.logs = data.get("logs", [])
        obj.created_at = data.get("created_at", _utc_now())
        obj.updated_at = data.get("updated_at", _utc_now())
        obj.error_info = data.get("error_info")
        return obj


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\|\s*([^}]+)\s*\}\}")
_VAR_SIMPLE_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _resolve_value(path: str, context: dict) -> Any:
    """Resolve a dotted path like 'step_id.result.field' from context."""
    parts = path.split(".")
    value = context
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
        if value is None:
            return None
    return value


def interpolate_arguments(arguments: dict, context: dict) -> dict:
    """Replace {{path}} and {{path|default}} placeholders in arguments."""
    result = {}
    for key, value in arguments.items():
        result[key] = _interpolate_value(value, context)
    return result


def _interpolate_value(value: Any, context: dict) -> Any:
    if isinstance(value, str):
        # Check for {{path|default}} pattern
        m = _VAR_RE.match(value)
        if m:
            path, default = m.group(1), m.group(2).strip()
            resolved = _resolve_value(path, context)
            return resolved if resolved is not None else default
        # Check for {{path}} pattern
        m = _VAR_SIMPLE_RE.match(value)
        if m:
            path = m.group(1)
            resolved = _resolve_value(path, context)
            if resolved is None:
                raise ValueError(f"变量未解析: {{{{{path}}}}}")
            return resolved
        # Mixed string interpolation (replace all occurrences)
        def replacer(match):
            path = match.group(1)
            resolved = _resolve_value(path, context)
            if resolved is None:
                raise ValueError(f"变量未解析: {{{{{path}}}}}")
            return str(resolved)
        value = _VAR_SIMPLE_RE.sub(replacer, value)
        return value
    if isinstance(value, dict):
        return {k: _interpolate_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_value(v, context) for v in value]
    return value


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------

def execute_workflow(
    workflow_id: str,
    user_id: str,
    inputs: dict | None = None,
    instance_id: str | None = None,
    resume: bool = False,
) -> dict:
    """Execute a workflow and return the final state.

    Args:
        workflow_id: The workflow definition ID.
        user_id: The user running the workflow.
        inputs: Initial input variables.
        instance_id: Existing instance ID (for resume).
        resume: If True, resume from a paused instance.

    Returns:
        dict with ok, instance, and any error info.
    """
    _init_db()
    definition = get_workflow(workflow_id)
    if not definition:
        return {"ok": False, "error": f"工作流不存在: {workflow_id}"}

    if resume and instance_id:
        instance = _load_instance(instance_id)
        if not instance:
            return {"ok": False, "error": f"工作流实例不存在: {instance_id}"}
        if instance.status not in ("paused", "pending"):
            return {"ok": False, "error": f"工作流状态不允许恢复: {instance.status}"}
    elif instance_id:
        # Continue from existing instance (e.g. after confirmation)
        instance = _load_instance(instance_id)
        if not instance:
            return {"ok": False, "error": f"工作流实例不存在: {instance_id}"}
    else:
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            user_id=user_id,
            inputs=inputs or {},
            instance_id=instance_id,
        )
        _save_instance(instance)

    instance.status = "running"
    instance.updated_at = _utc_now()
    _save_instance(instance)

    steps = definition.get("steps", [])
    on_error = definition.get("on_error", "pause")
    confirmation_steps = set(definition.get("requires_confirmation_at", []))

    try:
        for i in range(instance.current_step_index, len(steps)):
            step = steps[i]
            step_id = step["id"]
            skill_name = step["skill"]

            # Build context for interpolation
            context = {
                "input": instance.inputs,
                **instance.step_results,
            }

            # Interpolate arguments
            try:
                arguments = interpolate_arguments(step.get("arguments", {}), context)
            except ValueError as exc:
                instance.status = "failed"
                instance.error_info = {
                    "step_id": step_id,
                    "error": f"参数解析失败: {exc}",
                }
                instance.updated_at = _utc_now()
                _save_instance(instance)
                return {"ok": False, "error": str(exc), "instance": instance.to_dict()}

            # Check if this step requires confirmation
            if step_id in confirmation_steps:
                instance.status = "paused"
                instance.current_step_index = i
                instance.updated_at = _utc_now()
                _save_instance(instance)
                _log_step(instance, step_id, "paused_for_confirmation", arguments)
                return {
                    "ok": True,
                    "instance": instance.to_dict(),
                    "requires_confirmation": True,
                    "confirmation_context": {
                        "step_id": step_id,
                        "skill": skill_name,
                        "arguments": arguments,
                        "message": f"步骤 '{step_id}' 需要确认",
                    },
                }

            # Execute skill
            result = _execute_skill(skill_name, arguments, user_id)
            instance.step_results[step_id] = {"result": result}
            instance.current_step_index = i + 1
            instance.updated_at = _utc_now()
            _log_step(instance, step_id, "completed", arguments, result)
            _save_instance(instance)

        instance.status = "completed"
        instance.updated_at = _utc_now()
        _save_instance(instance)
        return {"ok": True, "instance": instance.to_dict()}

    except Exception as exc:
        failed_step_id = "unknown"
        try:
            failed_step_id = step.get("id", "unknown")
        except NameError:
            pass
        instance.status = "failed" if on_error == "fail" else "paused"
        instance.error_info = {
            "step_id": failed_step_id,
            "error": str(exc),
        }
        instance.updated_at = _utc_now()
        _save_instance(instance)
        return {
            "ok": False,
            "error": str(exc),
            "instance": instance.to_dict(),
        }


def confirm_and_resume(
    instance_id: str,
    user_id: str,
    confirmed: bool = True,
    override_arguments: dict | None = None,
) -> dict:
    """Resume a paused workflow after user confirmation.

    Args:
        instance_id: The workflow instance ID.
        user_id: The user confirming.
        confirmed: Whether the user confirmed (False = cancel).
        override_arguments: Optional argument overrides for the current step.

    Returns:
        dict with ok and instance state.
    """
    instance = _load_instance(instance_id)
    if not instance:
        return {"ok": False, "error": f"工作流实例不存在: {instance_id}"}
    if instance.user_id != user_id:
        return {"ok": False, "error": "无权操作此工作流实例"}
    if instance.status != "paused":
        return {"ok": False, "error": f"工作流状态不允许确认: {instance.status}"}

    if not confirmed:
        instance.status = "failed"
        instance.error_info = {"error": "用户取消"}
        instance.updated_at = _utc_now()
        _save_instance(instance)
        return {"ok": False, "error": "用户取消", "instance": instance.to_dict()}

    definition = get_workflow(instance.workflow_id)
    if not definition:
        return {"ok": False, "error": f"工作流定义不存在: {instance.workflow_id}"}

    steps = definition.get("steps", [])
    current_index = instance.current_step_index
    if current_index >= len(steps):
        instance.status = "completed"
        instance.updated_at = _utc_now()
        _save_instance(instance)
        return {"ok": True, "instance": instance.to_dict()}

    step = steps[current_index]
    step_id = step["id"]
    skill_name = step["skill"]

    # Build context and interpolate
    context = {
        "input": instance.inputs,
        **instance.step_results,
    }
    arguments = interpolate_arguments(step.get("arguments", {}), context)
    if override_arguments:
        arguments.update(override_arguments)

    # Execute the confirmed step
    try:
        result = _execute_skill(skill_name, arguments, user_id)
        instance.step_results[step_id] = {"result": result}
        instance.current_step_index = current_index + 1
        instance.status = "running"
        instance.updated_at = _utc_now()
        _log_step(instance, step_id, "confirmed_and_completed", arguments, result)
        _save_instance(instance)
    except Exception as exc:
        instance.status = "failed"
        instance.error_info = {"step_id": step_id, "error": str(exc)}
        instance.updated_at = _utc_now()
        _save_instance(instance)
        return {"ok": False, "error": str(exc), "instance": instance.to_dict()}

    # Continue with remaining steps
    return execute_workflow(
        instance.workflow_id,
        user_id,
        inputs=instance.inputs,
        instance_id=instance.instance_id,
        resume=False,  # Don't check status again, just continue from current index
    )


def _execute_skill(skill_name: str, arguments: dict, user_id: str) -> Any:
    """Execute a skill via the Skill Runtime."""
    execute_fn = globals().get("execute_skill")
    if execute_fn:
        return execute_fn(skill_name, arguments, user_id)
    # Fallback: try to import from skills_agent
    try:
        from backend import skills_agent as sa
        return sa.execute_skill(skill_name, arguments, user_id)
    except Exception as exc:
        raise RuntimeError(f"Skill 执行失败: {skill_name}: {exc}") from exc


def _log_step(
    instance: WorkflowInstance,
    step_id: str,
    status: str,
    arguments: dict | None = None,
    result: Any = None,
) -> None:
    instance.logs.append({
        "step_id": step_id,
        "status": status,
        "timestamp": _utc_now(),
        "arguments": arguments,
        "result": result,
    })


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_instance(instance: WorkflowInstance) -> None:
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO workflow_instances (
                id, workflow_id, user_id, status, current_step_index,
                step_results_json, logs_json, inputs_json, error_info_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                current_step_index = excluded.current_step_index,
                step_results_json = excluded.step_results_json,
                logs_json = excluded.logs_json,
                inputs_json = excluded.inputs_json,
                error_info_json = excluded.error_info_json,
                updated_at = excluded.updated_at
            """,
            (
                instance.instance_id,
                instance.workflow_id,
                instance.user_id,
                instance.status,
                instance.current_step_index,
                _json_dumps(instance.step_results),
                _json_dumps(instance.logs),
                _json_dumps(instance.inputs),
                _json_dumps(instance.error_info),
                instance.created_at,
                instance.updated_at,
            ),
        )


def _load_instance(instance_id: str) -> WorkflowInstance | None:
    with _db_connect() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    return WorkflowInstance.from_dict({
        "instance_id": data["id"],
        "workflow_id": data["workflow_id"],
        "user_id": data["user_id"],
        "status": data["status"],
        "current_step_index": data["current_step_index"],
        "step_results": _json_loads(data.get("step_results_json"), {}),
        "logs": _json_loads(data.get("logs_json"), []),
        "inputs": _json_loads(data.get("inputs_json"), {}),
        "error_info": _json_loads(data.get("error_info_json"), None),
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
    })


def list_user_workflows(user_id: str, limit: int = 20) -> list[dict]:
    """List workflow instances for a user."""
    _init_db()
    limit = max(1, min(int(limit), 100))
    with _db_connect() as conn:
        rows = conn.execute(
            """
            SELECT id, workflow_id, status, current_step_index, created_at, updated_at
            FROM workflow_instances
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Workflow Skills (callable by Agent / API)
# ---------------------------------------------------------------------------

def workflow_list_skill(arguments: dict, username: str) -> dict:
    """Skill: workflow.list — List available workflows."""
    return {"ok": True, "workflows": list_workflows()}


def workflow_run_skill(arguments: dict, username: str) -> dict:
    """Skill: workflow.run — Start a workflow instance."""
    args = arguments or {}
    workflow_id = str(args.get("workflow_id", "")).strip()
    if not workflow_id:
        raise ValueError("请提供 workflow_id")
    inputs = args.get("inputs") or {}
    result = execute_workflow(workflow_id, username, inputs=inputs)
    return result


def workflow_status_skill(arguments: dict, username: str) -> dict:
    """Skill: workflow.status — Get workflow instance status."""
    args = arguments or {}
    instance_id = str(args.get("instance_id", "")).strip()
    if not instance_id:
        raise ValueError("请提供 instance_id")
    instance = _load_instance(instance_id)
    if not instance:
        return {"ok": False, "error": f"工作流实例不存在: {instance_id}"}
    if instance.user_id != username:
        return {"ok": False, "error": "无权查看此工作流实例"}
    return {"ok": True, "instance": instance.to_dict()}


def workflow_confirm_skill(arguments: dict, username: str) -> dict:
    """Skill: workflow.confirm — Confirm and resume a paused workflow."""
    args = arguments or {}
    instance_id = str(args.get("instance_id", "")).strip()
    confirmed = bool(args.get("confirmed", True))
    override = args.get("override_arguments") or {}
    if not instance_id:
        raise ValueError("请提供 instance_id")
    return confirm_and_resume(instance_id, username, confirmed, override)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def workflows_api(payload: dict, username: str) -> dict:
    """Unified API handler for workflow operations."""
    action = str(payload.get("action", "")).strip()
    if action == "list":
        return {"ok": True, "workflows": list_workflows()}
    if action == "run":
        return workflow_run_skill(payload, username)
    if action == "status":
        return workflow_status_skill(payload, username)
    if action == "confirm":
        return workflow_confirm_skill(payload, username)
    if action == "instances":
        limit = int(payload.get("limit", 20))
        return {"ok": True, "instances": list_user_workflows(username, limit)}
    return {"ok": False, "error": f"未知操作: {action}"}
