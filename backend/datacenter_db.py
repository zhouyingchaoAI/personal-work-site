"""数据中台：全量入库同步（office-postgres 镜像层）。

把系统权限、账号配置、各业务模块用户数据、审计留痕和文件索引**全部**同步进
统一数据库 office-postgres。定位是“导入”阶段的镜像：
- 业务读写仍在原 JSON / SQLite（唯一数据源不变），本层每日 + 手动全量重建；
- 表结构统一为「自然键列 + payload JSONB」，先完整入库、后续再逐模块规范化；
- 每张表在单事务内 TRUNCATE + INSERT，失败整表回滚，不会留下半份数据；
- 同步结果（行数、耗时、与源对账）写 _datacenter/db_sync.json 供页面展示。

驱动用纯 Python 的 pg8000（vendor/pgdeps，跨解释器版本），仅在备份容器内使用；
主服务进程不连数据库，只读状态文件。
"""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "pgdeps"))
import pg8000.native  # noqa: E402

from backend.datacenter_lib import (  # noqa: E402
    USER_DIR_MAP, USER_FILE_MAP, classify_shared, datacenter_dir, read_json, write_json_atomic, sqlite_consistent_snapshot,
)

SCHEMAS = ("auth", "settings", "crm", "cashflow", "ledger", "collab", "agentic", "audit", "files", "meta", "raw")
DDL = """
CREATE TABLE IF NOT EXISTS raw.documents (path text PRIMARY KEY, content bytea NOT NULL, sha256 text NOT NULL, payload jsonb, parse_error boolean NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS raw.sqlite_schema (name text PRIMARY KEY, ddl text, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS raw.sqlite_rows (table_name text, row_no bigint, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(table_name, row_no));
CREATE TABLE IF NOT EXISTS auth.users (username text PRIMARY KEY, role text, name text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS auth.user_permissions (username text, assistant text, allowed boolean, payload jsonb, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (username, assistant));
CREATE TABLE IF NOT EXISTS settings.platform (key text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS settings.user_mail (username text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS crm.units (owner text, id text, name text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.people (owner text, id text, name text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.relations (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.actions (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.opportunities (owner text, id text, name text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.sales_contracts (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), pos integer, PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.staff (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.staff_directory (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS cashflow.history_records (owner text, idx integer, customer text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, idx));
CREATE TABLE IF NOT EXISTS cashflow.scenarios (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS cashflow.workbook_state (owner text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ledger.items (owner text, id text, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS collab.tickets (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS collab.forum_topics (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS agentic.sessions (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS agentic.messages (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS agentic.events (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS agentic.skill_invocations (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS agentic.memory_items (id text PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS audit.crm_events (line_no integer PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS audit.datacenter_access (line_no integer PRIMARY KEY, payload jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS files.catalog (path text PRIMARY KEY, owner text, module text, level text, size bigint, mtime timestamptz, synced_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS meta.sync_runs (id serial PRIMARY KEY, started_at timestamptz, finished_at timestamptz, ok boolean, reason text, tables_synced integer, rows_total bigint, error text);
"""


def db_connect():
    return pg8000.native.Connection(
        user=os.getenv("OFFICE_PG_USER", "office"),
        password=os.environ["OFFICE_PG_PASSWORD"],
        host=os.getenv("OFFICE_PG_HOST", "office-postgres"),
        port=int(os.getenv("OFFICE_PG_PORT", "5432")),
        database=os.getenv("OFFICE_PG_DB", "office"),
        timeout=20,
    )


def ensure_schema(conn):
    for schema in SCHEMAS:
        conn.run(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for stmt in DDL.strip().split(";\n"):
        if stmt.strip():
            conn.run(stmt)
    conn.run("ALTER TABLE files.catalog ADD COLUMN IF NOT EXISTS sha256 text")
    # 兼容早期建表：agent 事件类 id 实为文本（如 evt_…），统一为 text（幂等）。
    for table in ("agentic.messages", "agentic.events", "agentic.skill_invocations", "agentic.memory_items"):
        conn.run(f"ALTER TABLE {table} ALTER COLUMN id TYPE text USING id::text")

    from backend.datacenter_sql import ensure_structured_schema, ensure_query_role
    ensure_structured_schema(conn)
    ensure_query_role(conn)


def _office_store_ns(root):
    """加载统一存储层（office_store.py）到独立命名空间：备份容器与主服务共用同一份布局定义。"""
    module_dir = Path(__file__).resolve().parent
    ns = {"USER_DATA_DIR": Path(root), "__file__": str(module_dir.parent / "app.py")}
    exec(compile((module_dir / "office_store.py").read_text(encoding="utf-8"), "office_store.py", "exec"), ns)
    return ns


def office_live_state(root):
    """返回 (已切库助手集合, 存储层命名空间, 需从文件镜像中排除的相对路径)。"""
    ns = _office_store_ns(root)
    live = set(ns["officedb_enabled_modules"]())
    excluded_dirs, excluded_files = [], set()
    for module in live:
        for path, is_dir in ns["office_store_layout_paths"](module):
            relative = str(path.relative_to(Path(root)))
            (excluded_dirs.append(relative + os.sep) if is_dir else excluded_files.add(relative))
    return live, ns, (tuple(excluded_dirs), excluded_files)


def office_path_is_live(relative, excluded):
    dirs, files = excluded
    return relative in files or relative.startswith(dirs)


def read_source_json(path, default):
    """Missing optional source is empty; damaged/unreadable source must fail safely."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _source_files(root):
    root = Path(root)
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if not path.is_symlink() and path.is_file():
                yield path


def build_document_rows(root):
    """All JSON/JSONL, including unknown modules and caches; preserve original bytes."""
    root = Path(root)
    for path in _source_files(root):
        if path.suffix.lower() not in (".json", ".jsonl"):
            continue
        content = path.read_bytes()
        payload, error = None, False
        try:
            text = content.decode("utf-8-sig")
            data = ([json.loads(line) for line in text.splitlines() if line.strip()]
                    if path.suffix.lower() == ".jsonl" else json.loads(text))
            payload = json.dumps(data, ensure_ascii=True, allow_nan=False)
            # PostgreSQL JSONB cannot store a NUL character. Exact bytes remain available.
            if "\\u0000" in payload:
                payload, error = None, True
        except (UnicodeError, ValueError):
            error = True
        yield [str(path.relative_to(root)), content, hashlib.sha256(content).hexdigest(), payload, error]


def build_sqlite_rows(path):
    """Consistent read transaction, all tables including workflows/FTS metadata."""
    schema, rows = [], []
    if not Path(path).exists():
        return schema, rows
    def encode(value):
        if isinstance(value, bytes):
            return {"__bytes_hex__": value.hex()}
        raise TypeError(type(value).__name__)
    with tempfile.TemporaryDirectory(prefix="dc-sqlite-rows-") as tmp:
        snapshot = sqlite_consistent_snapshot(path, Path(tmp) / "snapshot.db")
        return _sqlite_rows_from_snapshot(snapshot, encode)


def _sqlite_rows_from_snapshot(path, encode):
    schema, rows = [], []
    with sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True) as sq:
        sq.row_factory = sqlite3.Row
        sq.execute("BEGIN")
        tables = sq.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        for table in tables:
            name = table["name"]
            schema.append([name, table["sql"]])
            quoted = name.replace('"', '""')
            for index, row in enumerate(sq.execute(f'SELECT * FROM "{quoted}"'), 1):
                rows.append([name, index, json.dumps(dict(row), ensure_ascii=True, default=encode)])
    return schema, rows


# ==================== 行构造（纯函数，便于测试） ====================
def rows_from_keyed_json(data, owner=None, name_key=None):
    """dict(id→obj) 或 list(obj 含 id) → [(owner?, id, name?, payload)]。"""
    items = list(data.items()) if isinstance(data, dict) else list(enumerate(data or []))
    rows = []
    for idx, (key, item) in enumerate(items):
        if not isinstance(item, dict):
            item = {"value": item}
        rid = str(item.get("id") or item.get("username") or (key if isinstance(data, dict) else f"row-{idx}"))
        row = [rid]
        if name_key is not None:
            row.append(str(item.get(name_key, ""))[:300])
        row.append(json.dumps(item, ensure_ascii=False))
        rows.append(([owner] if owner is not None else []) + row)
    return rows


def build_config_rows(config):
    users, perms, mails, platform = [], [], [], []
    for u in config.get("users") or []:
        username = str(u.get("username", ""))
        users.append([username, str(u.get("role", "")), str(u.get("name", "")), json.dumps(u, ensure_ascii=False)])
        overrides = u.get("assistant_permissions") or {}
        if isinstance(overrides, dict):
            for assistant, allowed in overrides.items():
                perms.append([username, str(assistant), bool(allowed), json.dumps({"override": allowed})])
    for username, payload in (config.get("user_mail_settings") or {}).items():
        mails.append([str(username), json.dumps(payload, ensure_ascii=False)])
    for key, value in config.items():
        if key in ("users", "user_mail_settings"):
            continue
        platform.append([str(key), json.dumps(value, ensure_ascii=False)])
    return users, perms, mails, platform


def iter_user_dirs(user_data_dir):
    for entry in sorted(Path(user_data_dir).iterdir()):
        if entry.is_dir() and not classify_shared(entry.name):
            yield entry


def build_files_catalog(user_data_dir):
    rows = []
    root = Path(user_data_dir)
    for path in _source_files(root):
        relative = path.relative_to(root)
        parts = relative.parts
        shared = classify_shared(parts[0])
        owner = ""
        if shared or len(parts) == 1:
            module, level = shared or ("其他共享数据", "B")
        else:
            owner = parts[0]
            mapping = USER_FILE_MAP if len(parts) == 2 else USER_DIR_MAP
            module, level = mapping.get(parts[1], ("其他用户数据", "B"))
        stat = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        rows.append([str(relative), owner, module, level, stat.st_size,
                     datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(), digest.hexdigest()])
    return rows


# ==================== 同步执行 ====================
def _replace(conn, table, columns, rows, casts=None):
    """单事务全量重建一张表；返回入库行数。"""
    conn.run("BEGIN")
    try:
        from backend.datacenter_sql import MODELS
        # MVCC-preserving replacement for tables serving reads; readers keep the last committed rows.
        command = "DELETE FROM" if table in {m["table"] for m in MODELS.values()} else "TRUNCATE"
        conn.run(f"{command} {table}")
        if rows:
            placeholders = ", ".join(
                f":p{i}{casts.get(col, '') if casts else ''}" for i, col in enumerate(columns))
            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            for row in rows:
                conn.run(sql, **{f"p{i}": v for i, v in enumerate(row)})
        conn.run("COMMIT")
    except Exception:
        conn.run("ROLLBACK")
        raise
    return len(rows)


def _jsonl_rows(path):
    rows = []
    if Path(path).exists():
        for no, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            try:
                rows.append([no, json.dumps(json.loads(line), ensure_ascii=False)])
            except json.JSONDecodeError:
                rows.append([no, json.dumps({"raw": line[:2000]})])
    return rows


def sync_all(user_data_dir, config_path, reason="manual", archive_roots=None, heartbeat=None):
    started = datetime.now()
    status = {"started_at": started.isoformat(timespec="seconds"), "reason": reason, "ok": False, "tables": []}
    conn = None
    locked = False
    J = {"payload": "::jsonb"}
    try:
        conn = db_connect()
        locked = conn.run("SELECT pg_try_advisory_lock(720260929)")[0][0]
        if not locked:
            return {"ok": False, "busy": True}
        ensure_schema(conn)
        root = Path(user_data_dir)

        def record(table, rows, source_count=None):
            source_count = rows if source_count is None else source_count
            rows = conn.run(f"SELECT count(*) FROM {table}")[0][0]
            status["tables"].append({"table": table, "rows": rows,
                                     "source": source_count if source_count is not None else rows,
                                     "match": source_count is None or source_count == rows})

        live, store_ns, excluded = office_live_state(root)
        status["office_live_modules"] = sorted(live)

        def src(module, path, default):
            """已切库助手从 app.documents 取，其余读原文件。"""
            if module not in live:
                return read_source_json(path, default)
            rows = conn.run("SELECT payload FROM app.documents WHERE module=:module AND key=:key",
                            module=module, key=store_ns["office_store_key"](path))
            return rows[0][0] if rows else default

        # 已切库助手的原文件是切换前快照，不再镜像；改镜像 app.documents 里的在线记录。
        documents = [row for row in build_document_rows(root) if not office_path_is_live(row[0], excluded)]
        if live:
            for key, text in conn.run("SELECT key, payload::text FROM app.documents WHERE module = ANY(:modules)",
                                      modules=sorted(live)):
                content = text.encode("utf-8")
                payload, error = None, False
                try:
                    payload = json.dumps(json.loads(text), ensure_ascii=True, allow_nan=False)
                    if "\\u0000" in payload:
                        payload, error = None, True
                except ValueError:
                    error = True
                documents.append([key, content, hashlib.sha256(content).hexdigest(), payload, error])
        cfg_bytes = Path(config_path).read_bytes()
        documents.append(["@config/config.json", cfg_bytes, hashlib.sha256(cfg_bytes).hexdigest(),
                          None, False])
        record("raw.documents", _replace(conn, "raw.documents",
               ["path", "content", "sha256", "payload", "parse_error"], documents, J), len(documents))
        status["document_parse_errors"] = sum(bool(r[4]) for r in documents)
        schema, sqlite_rows = build_sqlite_rows(root / "app.db")
        record("raw.sqlite_schema", _replace(conn, "raw.sqlite_schema", ["name", "ddl"], schema), len(schema))
        record("raw.sqlite_rows", _replace(conn, "raw.sqlite_rows",
               ["table_name", "row_no", "payload"], sqlite_rows, J), len(sqlite_rows))

        config = read_source_json(config_path, None)
        if not isinstance(config, dict) or not isinstance(config.get("users"), list):
            raise ValueError("Invalid account configuration")
        users, perms, mails, platform = build_config_rows(config)
        record("auth.users", _replace(conn, "auth.users", ["username", "role", "name", "payload"], users, J),
               len(config.get("users") or []))
        record("auth.user_permissions", _replace(conn, "auth.user_permissions",
               ["username", "assistant", "allowed", "payload"], perms, J))
        record("settings.user_mail", _replace(conn, "settings.user_mail", ["username", "payload"], mails, J))
        record("settings.platform", _replace(conn, "settings.platform", ["key", "payload"], platform, J))

        # 联指经营助手切库后（crm_db.json enabled），crm.* 业务表由应用直接读写，
        # 属于线上数据而非镜像，同步跳过以免旧文件覆盖；未切换时保持原镜像行为。
        crm_live = bool((read_json(datacenter_dir(root) / "crm_db.json", {}) or {}).get("enabled"))
        status["crm_live_mode"] = crm_live
        crm_tables = {"units": "name", "people": "name", "opportunities": "name", "relations": None,
                      "actions": None, "staff": None}
        if not crm_live:
            for name, name_key in crm_tables.items():
                rows, source = [], 0
                for udir in iter_user_dirs(root):
                    data = read_source_json(udir / "crm" / f"{name}.json", None)
                    if data is None:
                        continue
                    source += len(data) if isinstance(data, (dict, list)) else 0
                    rows.extend(rows_from_keyed_json(data, owner=udir.name, name_key=name_key))
                cols = ["owner", "id"] + (["name"] if name_key else []) + ["payload"]
                record(f"crm.{name}", _replace(conn, f"crm.{name}", cols, rows, J), source)

        hist_rows, hist_src, scen_rows, wb_rows, ledger_rows, ledger_src = [], 0, [], [], [], 0
        for udir in iter_user_dirs(root):
            records = (src("cashflow", udir / "cashflow_history.json", {}) or {}).get("records") or []
            hist_src += len(records)
            hist_rows.extend([udir.name, i, str(r.get("customer", ""))[:300], json.dumps(r, ensure_ascii=False)]
                             for i, r in enumerate(records))
            for s in src("cashflow", udir / "cashflow_scenarios.json", []) or []:
                scen_rows.append([udir.name, str(s.get("id", "")), json.dumps(s, ensure_ascii=False)])
            wb = src("cashflow", udir / "cashflow_workbook_state.json", None)
            if wb is not None:
                wb_rows.append([udir.name, json.dumps(wb, ensure_ascii=False)])
            items = src("ledger", udir / "operating_ledger.json", []) or []
            ledger_src += len(items)
            ledger_rows.extend(([udir.name] + r) for r in rows_from_keyed_json(items))
        record("cashflow.history_records", _replace(conn, "cashflow.history_records",
               ["owner", "idx", "customer", "payload"], hist_rows, J), hist_src)
        record("cashflow.scenarios", _replace(conn, "cashflow.scenarios", ["owner", "id", "payload"], scen_rows, J))
        record("cashflow.workbook_state", _replace(conn, "cashflow.workbook_state", ["owner", "payload"], wb_rows, J))
        record("ledger.items", _replace(conn, "ledger.items", ["owner", "id", "payload"], ledger_rows, J), ledger_src)

        tickets = src("workorder", root / "_tickets" / "tickets.json", {})
        tickets = tickets.get("tickets") if isinstance(tickets, dict) else tickets
        record("collab.tickets", _replace(conn, "collab.tickets", ["id", "payload"],
               rows_from_keyed_json(tickets or []), J), len(tickets or []))
        topics = src("forum", root / "_forum" / "topics.json", {})
        topics = topics.get("topics") if isinstance(topics, dict) else topics
        record("collab.forum_topics", _replace(conn, "collab.forum_topics", ["id", "payload"],
               rows_from_keyed_json(topics or []), J), len(topics or []))
        if not crm_live:
            record("crm.staff_directory", _replace(conn, "crm.staff_directory", ["id", "payload"],
                   rows_from_keyed_json(read_source_json(root / "_crm_staff_directory.json", {})), J))

        if (root / "app.db").exists():
            for src_table, dest in [("agent_sessions", "agentic.sessions"), ("agent_messages", "agentic.messages"),
                                    ("agent_events", "agentic.events"), ("skill_invocations", "agentic.skill_invocations"),
                                    ("memory_items", "agentic.memory_items")]:
                if src_table not in {name for name, ddl in schema}:
                    raise ValueError("Required SQLite source table missing")
                data = [json.loads(payload) for table, _, payload in sqlite_rows if table == src_table]
                rows = [[str(r.get("id", i)), json.dumps(r, ensure_ascii=False, default=str)]
                        for i, r in enumerate(data, 1)]
                record(dest, _replace(conn, dest, ["id", "payload"], rows, J), len(data))

        configuration_live = crm_live and (read_json(datacenter_dir(root) / "crm_db.json", {}) or {}).get('configuration_enabled') is True
        audit_rows = ([[seq, json.dumps(payload, ensure_ascii=False)] for seq, payload in
                       conn.run('SELECT seq,payload FROM crm.security_events ORDER BY seq')]
                      if configuration_live else _jsonl_rows(root / ".crm-security" / "audit.jsonl"))
        record("audit.crm_events", _replace(conn, "audit.crm_events", ["line_no", "payload"], audit_rows, J))
        access_rows = ([[seq, json.dumps(payload, ensure_ascii=False)] for seq, payload in
                        conn.run("SELECT seq, payload FROM app.events WHERE module='datacenter' AND stream='access_log' ORDER BY seq")]
                       if "datacenter" in live else _jsonl_rows(datacenter_dir(root) / "access_log.jsonl"))
        record("audit.datacenter_access", _replace(conn, "audit.datacenter_access", ["line_no", "payload"], access_rows, J))

        catalog = [row for row in build_files_catalog(root) if not office_path_is_live(row[0], excluded)]
        if live:
            for key, owner, size, updated_at, sha256 in conn.run(
                    "SELECT key, owner, size, updated_at, sha256 FROM app.blobs WHERE module = ANY(:modules)", modules=sorted(live)):
                parts = key.split("/")
                shared = classify_shared(parts[0])
                if shared or len(parts) == 1:
                    module, level = shared or ("其他共享数据", "B")
                else:
                    module, level = (USER_FILE_MAP if len(parts) == 2 else USER_DIR_MAP).get(parts[1], ("其他用户数据", "B"))
                catalog.append([key, owner, module, level, size, updated_at.isoformat(), sha256])
        record("files.catalog", _replace(conn, "files.catalog",
               ["path", "owner", "module", "level", "size", "mtime", "sha256"], catalog,
               {"mtime": "::timestamptz"}), len(catalog))

        from backend.datacenter_sql import refresh_query_stats
        refresh_query_stats(conn)

        if archive_roots:
            from backend.datacenter_archive import snapshot_project
            status["file_archive"] = snapshot_project(conn, archive_roots, heartbeat=heartbeat)
        status["ok"] = all(t["match"] for t in status["tables"])
        status["mismatches"] = [t["table"] for t in status["tables"] if not t["match"]]
    except Exception as exc:  # noqa: BLE001 —— 同步失败要落到状态文件
        status["error"] = f"{type(exc).__name__}: 同步失败，已保留失败表上次成功镜像，请管理员检查服务日志"
        raise
    finally:
        status["finished_at"] = datetime.now().isoformat(timespec="seconds")
        status["duration_seconds"] = round((datetime.now() - started).total_seconds(), 1)
        status["rows_total"] = sum(t["rows"] for t in status.get("tables", []))
        try:
            if not locked:
                raise RuntimeError("No sync lock")
            conn.run("INSERT INTO meta.sync_runs (started_at, finished_at, ok, reason, tables_synced, rows_total, error) "
                     "VALUES (:a::timestamptz, :b::timestamptz, :c, :d, :e, :f, :g)",
                     a=status["started_at"], b=status["finished_at"], c=status["ok"], d=reason,
                     e=len(status["tables"]), f=status["rows_total"], g=status.get("error", ""))
        except Exception:
            pass
        if conn is not None:
            conn.close()
        if conn is None or locked:
            history = read_json(datacenter_dir(user_data_dir) / "db_sync.json", {}).get("history") or []
            history.append({k: status.get(k) for k in ("started_at", "finished_at", "ok", "reason",
                                                   "rows_total", "duration_seconds", "error")})
            write_json_atomic(datacenter_dir(user_data_dir) / "db_sync.json",
                          {"last": status, "history": history[-30:]})
    return status
