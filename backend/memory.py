"""Memory Layer: user preferences, event history, context retrieval.

Provides:
- FTS5-powered memory search (SQLite built-in, zero dependencies)
- Memory Skills: memory.remember, memory.search, memory.forget, memory.summarize
- Automatic context injection for Agent Runtime

Loaded by backend.runtime into the shared namespace.
"""
from __future__ import annotations

import json
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
# FTS5 virtual table for memory search
# ---------------------------------------------------------------------------

def _ensure_fts5() -> None:
    """Create FTS5 virtual table on memory_items if not exists."""
    with _db_connect() as conn:
        # Check if FTS5 table exists
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_items_fts'"
        ).fetchone()
        if row:
            return
        # Create FTS5 virtual table
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
                content,
                content_rowid=rowid,
                content='memory_items'
            )
            """
        )
        # Populate with existing data
        conn.execute(
            """
            INSERT INTO memory_items_fts(rowid, content)
            SELECT rowid, content FROM memory_items
            """
        )
        # Create triggers to keep FTS5 in sync
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memory_items_fts_insert AFTER INSERT ON memory_items BEGIN
                INSERT INTO memory_items_fts(rowid, content) VALUES (new.rowid, new.content);
            END
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memory_items_fts_delete AFTER DELETE ON memory_items BEGIN
                INSERT INTO memory_items_fts(memory_items_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
            END
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memory_items_fts_update AFTER UPDATE ON memory_items BEGIN
                INSERT INTO memory_items_fts(memory_items_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                INSERT INTO memory_items_fts(rowid, content) VALUES (new.rowid, new.content);
            END
            """
        )


# ---------------------------------------------------------------------------
# Memory CRUD
# ---------------------------------------------------------------------------

def remember_memory(
    user_id: str,
    memory_type: str,
    content: str,
    metadata: dict | None = None,
    source: str | None = None,
    confidence: float = 1.0,
) -> dict:
    """Save a memory item. Returns the created memory."""
    _init_db()
    _ensure_fts5()
    memory_id = "mem_" + uuid.uuid4().hex[:20]
    now = _utc_now()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO memory_items (id, user_id, type, content, metadata_json, source, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    return {
        "id": memory_id,
        "user_id": user_id,
        "type": memory_type,
        "content": content,
        "metadata": metadata or {},
        "source": source,
        "confidence": confidence,
        "created_at": now,
    }


def forget_memory(user_id: str, memory_id: str) -> dict:
    """Delete a memory item. Only the owner can delete."""
    with _db_connect() as conn:
        cur = conn.execute(
            "DELETE FROM memory_items WHERE id = ? AND user_id = ?",
            (memory_id, user_id or "anonymous"),
        )
        if cur.rowcount == 0:
            raise ValueError("记忆不存在或无权限删除")
    return {"ok": True, "deleted_id": memory_id}


def list_memories(
    user_id: str,
    memory_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List memory items for a user."""
    _init_db()
    limit = max(1, min(int(limit or 50), 200))
    sql = "SELECT * FROM memory_items WHERE user_id = ?"
    params: list[Any] = [user_id or "anonymous"]
    if memory_type:
        sql += " AND type = ?"
        params.append(memory_type)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _db_connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_loads(item.pop("metadata_json", None), {})
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# FTS5 Search
# ---------------------------------------------------------------------------

def search_memory_items(
    user_id: str,
    query: str,
    memory_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Full-text search memory items using SQLite FTS5."""
    _init_db()
    _ensure_fts5()
    if not query or not query.strip():
        return list_memories(user_id, memory_type=memory_type, limit=limit)

    limit = max(1, min(int(limit or 10), 100))
    # Escape FTS5 special chars - wrap in double quotes for phrase matching
    safe_query = '"' + query.strip().replace('"', '""') + '"'
    # Build query: search in FTS5 then join back to memory_items
    sql = """
        SELECT m.* FROM memory_items m
        JOIN memory_items_fts fts ON m.rowid = fts.rowid
        WHERE m.user_id = ? AND memory_items_fts MATCH ?
    """
    params: list[Any] = [user_id or "anonymous", safe_query]
    if memory_type:
        sql += " AND m.type = ?"
        params.append(memory_type)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    with _db_connect() as conn:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS5 might not be available in some builds, fallback to LIKE
            like_sql = "SELECT * FROM memory_items WHERE user_id = ? AND content LIKE ?"
            like_params: list[Any] = [user_id or "anonymous", f"%{safe_query}%"]
            if memory_type:
                like_sql += " AND type = ?"
                like_params.append(memory_type)
            like_sql += " ORDER BY updated_at DESC LIMIT ?"
            like_params.append(limit)
            rows = conn.execute(like_sql, like_params).fetchall()
        # If FTS5 returned no results, try LIKE fallback for Chinese substring matching
        if not rows:
            like_sql = "SELECT * FROM memory_items WHERE user_id = ? AND content LIKE ?"
            like_params: list[Any] = [user_id or "anonymous", f"%{query.strip()}%"]
            if memory_type:
                like_sql += " AND type = ?"
                like_params.append(memory_type)
            like_sql += " ORDER BY updated_at DESC LIMIT ?"
            like_params.append(limit)
            rows = conn.execute(like_sql, like_params).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _json_loads(item.pop("metadata_json", None), {})
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Memory Skills (callable by Agent / API)
# ---------------------------------------------------------------------------

def memory_remember_skill(arguments: dict, username: str) -> dict:
    """Skill: memory.remember — Save a memory item."""
    args = arguments or {}
    content = str(args.get("content", "") or "").strip()
    if not content:
        raise ValueError("请提供 content（记忆内容）")
    result = remember_memory(
        user_id=username,
        memory_type=str(args.get("type", "note")).strip() or "note",
        content=content,
        metadata=args.get("metadata") or {},
        source=args.get("source") or "skill",
        confidence=float(args.get("confidence", 1.0)),
    )
    return {"ok": True, "memory": result}


def memory_search_skill(arguments: dict, username: str) -> dict:
    """Skill: memory.search — Search memory items."""
    args = arguments or {}
    results = search_memory_items(
        user_id=username,
        query=str(args.get("query", "") or "").strip(),
        memory_type=str(args.get("type", "") or "").strip() or None,
        limit=int(args.get("limit", 10)),
    )
    return {"ok": True, "memories": results, "count": len(results)}


def memory_forget_skill(arguments: dict, username: str) -> dict:
    """Skill: memory.forget — Delete a memory item."""
    args = arguments or {}
    memory_id = str(args.get("id", "") or "").strip()
    if not memory_id:
        raise ValueError("请提供 id（记忆 ID）")
    return forget_memory(username, memory_id)


def memory_summarize_skill(arguments: dict, username: str) -> dict:
    """Skill: memory.summarize — Summarize recent memories."""
    args = arguments or {}
    memory_type = str(args.get("type", "") or "").strip() or None
    days = int(args.get("days", 30))
    items = list_memories(username, memory_type=memory_type, limit=50)
    # Simple summary: group by type and list contents
    summary_lines = []
    for item in items:
        t = item.get("type", "note")
        c = item.get("content", "")
        summary_lines.append(f"[{t}] {c}")
    summary = "\n".join(summary_lines[:20])
    return {
        "ok": True,
        "summary": summary,
        "count": len(items),
        "types": list(set(i.get("type", "note") for i in items)),
    }


# ---------------------------------------------------------------------------
# Integration with Agent Runtime
# ---------------------------------------------------------------------------

def get_memory_context(user_id: str, query: str | None = None, limit: int = 5) -> str:
    """Build a memory context string for Agent system prompt injection."""
    items = search_memory_items(user_id, query or "", limit=limit)
    if not items:
        return ""
    lines = ["\n[用户记忆]"]
    for item in items:
        t = item.get("type", "note")
        c = item.get("content", "")
        lines.append(f"- [{t}] {c}")
    return "\n".join(lines)
