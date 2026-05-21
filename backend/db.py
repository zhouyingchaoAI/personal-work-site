"""SQLite foundation for AI-native history, Skill audit, and memory.

This module is intentionally dependency-free so the local office assistant can keep
running as a lightweight single-process app while gaining durable Agent history.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
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


def default_db_path() -> Path:
    """Return the default app database path.

    When loaded through ``backend.runtime``, ``USER_DATA_DIR`` exists in globals.
    When imported as ``backend.db`` in tests, fall back to the repository-local
    ``user_data/app.db`` path.
    """
    user_data_dir = globals().get("USER_DATA_DIR")
    if user_data_dir:
        return Path(user_data_dir) / "app.db"
    return Path(__file__).resolve().parent.parent / "user_data" / "app.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path | None = None) -> Path:
    """Create AI-native tables if they do not already exist."""
    path = Path(db_path) if db_path else default_db_path()
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skill_invocations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                skill_name TEXT NOT NULL,
                skill_version TEXT NOT NULL DEFAULT '1.0.0',
                source TEXT NOT NULL,
                arguments_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,
                status TEXT NOT NULL,
                safety_level TEXT NOT NULL DEFAULT 'safe',
                confirmed INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_skill_invocations_user_time
                ON skill_invocations(user_id, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_skill_invocations_skill_time
                ON skill_invocations(skill_name, started_at DESC);

            CREATE TABLE IF NOT EXISTS agent_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'system',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_agent_events_user_time
                ON agent_events(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_agent_events_session_time
                ON agent_events(session_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                source TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memory_items_user_type_time
                ON memory_items(user_id, type, updated_at DESC);

            CREATE TABLE IF NOT EXISTS workflow_instances (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                current_step_index INTEGER NOT NULL DEFAULT 0,
                step_results_json TEXT NOT NULL DEFAULT '{}',
                logs_json TEXT NOT NULL DEFAULT '[]',
                inputs_json TEXT NOT NULL DEFAULT '{}',
                error_info_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workflow_instances_user_time
                ON workflow_instances(user_id, updated_at DESC);
            """
        )
    return path


def record_skill_invocation(
    db_path: str | Path | None = None,
    *,
    user_id: str,
    session_id: str | None = None,
    skill_name: str,
    source: str,
    arguments: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    status: str,
    safety_level: str = "safe",
    confirmed: bool = False,
    error: str | None = None,
    skill_version: str = "1.0.0",
    started_at: str | None = None,
    finished_at: str | None = None,
) -> str:
    path = init_db(db_path)
    invocation_id = "inv_" + uuid.uuid4().hex[:20]
    now = utc_now()
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO skill_invocations (
                id, user_id, session_id, skill_name, skill_version, source,
                arguments_json, result_json, status, safety_level, confirmed,
                error, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invocation_id,
                user_id or "anonymous",
                session_id,
                skill_name,
                skill_version or "1.0.0",
                source or "unknown",
                _json_dumps(arguments or {}),
                _json_dumps(result) if result is not None else None,
                status,
                safety_level or "safe",
                1 if confirmed else 0,
                error,
                started_at or now,
                finished_at or now,
            ),
        )
    return invocation_id


def list_recent_skill_invocations(
    db_path: str | Path | None = None,
    *,
    user_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    path = init_db(db_path)
    limit = max(1, min(int(limit or 20), 100))
    sql = "SELECT * FROM skill_invocations"
    params: list[Any] = []
    if user_id:
        sql += " WHERE user_id = ?"
        params.append(user_id)
    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["arguments"] = _json_loads(item.pop("arguments_json"), {})
        item["result"] = _json_loads(item.pop("result_json"), {})
        item["confirmed"] = bool(item.get("confirmed"))
        result.append(item)
    return result


def record_agent_event(
    db_path: str | Path | None = None,
    *,
    user_id: str,
    session_id: str | None = None,
    event_type: str,
    source: str = "system",
    payload: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> str:
    """Persist an AI-native event for session timeline/audit views."""
    path = init_db(db_path)
    event_id = "evt_" + uuid.uuid4().hex[:20]
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO agent_events (id, user_id, session_id, event_type, source, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_id or "anonymous",
                session_id,
                event_type or "agent.event",
                source or "system",
                _json_dumps(payload or {}),
                created_at or utc_now(),
            ),
        )
    return event_id


def list_agent_events(
    db_path: str | Path | None = None,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent AI-native events, optionally scoped to a session."""
    path = init_db(db_path)
    limit = max(1, min(int(limit or 50), 200))
    sql = "SELECT * FROM agent_events"
    params: list[Any] = []
    clauses = []
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["payload"] = _json_loads(item.pop("payload_json"), {})
        result.append(item)
    return result


def remember(
    db_path: str | Path | None = None,
    *,
    user_id: str,
    memory_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    confidence: float = 1.0,
) -> str:
    path = init_db(db_path)
    memory_id = "mem_" + uuid.uuid4().hex[:20]
    now = utc_now()
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO memory_items (
                id, user_id, type, content, metadata_json, source,
                confidence, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                user_id or "anonymous",
                memory_type or "note",
                content,
                _json_dumps(metadata or {}),
                source,
                float(confidence),
                now,
                now,
            ),
        )
    return memory_id


def list_memory_items(
    db_path: str | Path | None = None,
    *,
    user_id: str,
    memory_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    path = init_db(db_path)
    limit = max(1, min(int(limit or 50), 200))
    sql = "SELECT * FROM memory_items WHERE user_id = ?"
    params: list[Any] = [user_id or "anonymous"]
    if memory_type:
        sql += " AND type = ?"
        params.append(memory_type)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_loads(item.pop("metadata_json"), {})
        result.append(item)
    return result
