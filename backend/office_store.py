"""办公平台统一存储层：各助手的 JSON 记录 / 二进制文件 / 追加事件走同一接口。

存储模式由 user_data/_datacenter/office_db.json 决定：`modules` 里为 true 的助手
走 office-postgres 的 app.documents / app.blobs / app.events；未开启的助手仍读写
user_data 下的原文件（路径即逻辑键，相对 USER_DATA_DIR 的 posix 路径）。

设计要点：
- 调用方只传原来的文件路径：文件模式按原路径读写，数据库模式把该路径当键。
  迁移即“按原路径把文件逐个写入数据库”，数据中台按键前缀就能说明数据位置。
- JSON 用 json 列（保留键序，与文件时代一致）；二进制用 bytea + sha256；
  追加型日志用 app.events（seq 自增）。
- 列表接口返回 (键名, 内容, 更新时间)：文件模式取 mtime，数据库模式取 updated_at，
  调用方排序口径不变。
- 少数第三方库只接受真实路径（OFD 渲染等）：office_blob_local() 在数据库模式下
  临时落盘，退出即删。
"""
import contextlib
import hashlib
import json
import os
import queue as _officedb_queue
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor/pgdeps"))
import pg8000.native  # noqa: E402

OFFICE_STORE_MODULES = ("ledger", "cashflow", "project", "diary", "workorder", "forum", "meeting", "writing",
                        "news", "reports", "reimbursement", "mailassistant", "knowledge", "datacenter",
                        "platform")
# 助手 id → 存储模块：周报与出差报告共用 reports/、generated/、drafts/ 目录，按同一开关切换。
OFFICE_STORE_ASSISTANT_MODULE = {"weekly": "reports", "trip": "reports"}


def office_store_module(assistant):
    return OFFICE_STORE_ASSISTANT_MODULE.get(assistant, assistant)
OFFICE_SHARED_ROOTS = {"projects", "knowledge", "templates"}
# 各助手的原文件布局：user 项相对每个用户目录，shared 项相对 user_data；以 / 结尾为目录。
# 迁移脚本与数据中台“存储对应”都以此为准。
OFFICE_STORE_LAYOUT = {
    "ledger": {"user": ["operating_ledger.json", "contract_documents/"], "shared": []},
    "cashflow": {"user": ["cashflow_history.json", "cashflow_scenarios.json", "cashflow_workbook_state.json",
                          "cashflow_exports/"], "shared": []},
    "project": {"user": [], "shared": ["projects/"]},
    "diary": {"user": ["diary/"], "shared": []},
    "workorder": {"user": [], "shared": ["_tickets/"]},
    "forum": {"user": [], "shared": ["_forum/"]},
    "meeting": {"user": ["meetings/"], "shared": []},
    "writing": {"user": ["writing/"], "shared": []},
    "news": {"user": ["news/"], "shared": ["_news/"]},
    "reports": {"user": ["reports/", "generated/", "drafts/"], "shared": ["templates/"]},
    "reimbursement": {"user": ["reimbursement/"], "shared": []},
    # mail_cache/ 里除 sent.json 外都是可重建的 IMAP 缓存（进 cache 表，不入备份）。
    "mailassistant": {"user": ["mail_cache/"], "shared": ["_mcp_mail_attachment_links/"],
                      "cache": lambda path: path.name != "sent.json" and "mail_cache" in path.parts},
    "knowledge": {"user": [], "shared": ["knowledge/"]},
    "datacenter": {"user": [], "shared": ["_datacenter/access_log.jsonl", "_datacenter/db_alerts.jsonl"]},
    "platform": {"user": ["profile/", "nav_prefs.json"], "shared": []},
}


def office_store_user_dirs():
    root = Path(USER_DATA_DIR)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")) and p.name not in OFFICE_SHARED_ROOTS)


def office_store_layout_paths(module):
    """该助手全部原文件根：[(Path, is_dir)]，只返回当前存在的。"""
    layout = OFFICE_STORE_LAYOUT.get(module) or {"user": [], "shared": []}
    result = []
    roots = [(Path(USER_DATA_DIR), layout["shared"])] + [(d, layout["user"]) for d in office_store_user_dirs()]
    for base, entries in roots:
        for entry in entries:
            path = base / entry.rstrip("/")
            if path.exists():
                result.append((path, entry.endswith("/")))
    return result
_officedb_lock = threading.RLock()
_officedb_state = {"config": None, "config_mtime": None, "config_path": None}
_officedb_pool = _officedb_queue.LifoQueue(maxsize=6)
_officedb_slots = threading.BoundedSemaphore(6)


def _officedb_config_path():
    return Path(USER_DATA_DIR) / "_datacenter" / "office_db.json"


def officedb_config():
    path = _officedb_config_path()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    with _officedb_lock:
        if _officedb_state["config_mtime"] != mtime or _officedb_state["config_path"] != str(path):
            try:
                _officedb_state["config"] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _officedb_state["config"] = None
            _officedb_state["config_mtime"] = mtime
            _officedb_state["config_path"] = str(path)
            _officedb_drain_pool()
        return _officedb_state["config"]


def _officedb_drain_pool():
    while True:
        try:
            conn = _officedb_pool.get_nowait()
        except _officedb_queue.Empty:
            return
        try:
            conn.close()
        except Exception:
            pass


def officedb_enabled(module):
    """该助手是否已切换到数据库模式（配置 modules.<module> 为 true，或 modules.all）。"""
    config = officedb_config()
    if not config or not config.get("enabled", True):
        return False
    modules = config.get("modules") or {}
    return modules.get(module) is True or modules.get("all") is True


def officedb_enabled_modules():
    config = officedb_config() or {}
    modules = config.get("modules") or {}
    if modules.get("all") is True:
        return list(OFFICE_STORE_MODULES)
    return [name for name in OFFICE_STORE_MODULES if modules.get(name) is True]


class _officedb_conn:
    """池化连接；异常时丢弃连接而不是放回。"""

    def __enter__(self):
        if not _officedb_slots.acquire(timeout=8):
            raise RuntimeError("办公数据库繁忙，请稍后重试")
        self.conn = None
        try:
            try:
                self.conn = _officedb_pool.get_nowait()
            except _officedb_queue.Empty:
                config = officedb_config() or {}
                self.conn = pg8000.native.Connection(
                    user=config.get("user", "office_app"), password=config["password"],
                    host=config.get("host", "office-postgres"), port=int(config.get("port", 5432)),
                    database=config.get("database", "office"), timeout=10)
            return self.conn
        except Exception:
            _officedb_slots.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                _officedb_pool.put_nowait(self.conn)
            except _officedb_queue.Full:
                self.conn.close()
        else:
            try:
                self.conn.close()
            except Exception:
                pass
        _officedb_slots.release()


OFFICE_STORE_DDL = """
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.documents (module text NOT NULL, owner text NOT NULL DEFAULT '', key text NOT NULL,
  payload json NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (module, key));
CREATE INDEX IF NOT EXISTS documents_owner ON app.documents (module, owner);
CREATE TABLE IF NOT EXISTS app.blobs (module text NOT NULL, owner text NOT NULL DEFAULT '', key text NOT NULL,
  content bytea NOT NULL, size bigint NOT NULL, sha256 text NOT NULL, content_type text,
  updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (module, key));
CREATE INDEX IF NOT EXISTS blobs_owner ON app.blobs (module, owner);
CREATE TABLE IF NOT EXISTS app.events (seq bigserial PRIMARY KEY, module text NOT NULL, stream text NOT NULL,
  owner text NOT NULL DEFAULT '', payload jsonb NOT NULL, at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS events_stream ON app.events (module, stream, seq DESC);
-- 可重建缓存（邮件 IMAP 快照与附件）：与业务数据分表，备份时排除其数据。
CREATE TABLE IF NOT EXISTS app.cache_documents (LIKE app.documents INCLUDING ALL);
CREATE TABLE IF NOT EXISTS app.cache_blobs (LIKE app.blobs INCLUDING ALL);
"""
OFFICE_CACHE_TABLES = ("app.cache_documents", "app.cache_blobs")


def _office_docs_table(cache):
    return "app.cache_documents" if cache else "app.documents"


def _office_blobs_table(cache):
    return "app.cache_blobs" if cache else "app.blobs"


def officedb_ensure_schema(conn):
    for statement in OFFICE_STORE_DDL.strip().split(";\n"):
        if statement.strip():
            conn.run(statement)


# ---------- 键与路径 ----------

def office_store_key(path):
    """把 user_data 下的路径转成逻辑键（posix 相对路径）；user_data 之外的路径拒绝。"""
    root = Path(USER_DATA_DIR)
    path = Path(path)
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"路径不在 user_data 内：{path}") from exc
    key = relative.as_posix()
    if key in ("", ".") or ".." in relative.parts:
        raise ValueError(f"无效存储键：{path}")
    return key


def _office_use_db(module, path):
    """数据库模式且路径在 user_data 内才走数据库；旧的共享目录（代码目录旁的
    周报/generated/drafts）不属于用户数据，始终按文件处理。"""
    if not officedb_enabled(module):
        return False
    root = Path(USER_DATA_DIR)
    path = Path(path)
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


def office_store_owner(key):
    first = PurePosixPath(key).parts[0]
    if first.startswith("_") or first.startswith(".") or first in OFFICE_SHARED_ROOTS or "/" not in key:
        return ""
    return first


def _office_now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _office_ts(value):
    if value is None:
        return 0.0
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    return float(value)


# ---------- JSON 文档 ----------

def office_doc_read(module, path, default=None, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT payload FROM {_office_docs_table(cache)} WHERE module=:module AND key=:key",
                            module=module, key=key)
        return rows[0][0] if rows else default
    path = Path(path)
    if not path.exists():
        return default
    try:
        return _office_parse_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _office_parse_json(text):
    """与旧 read_json_lenient 一致：允许 JSON 之后有残留字符（历史上的追加写入）。"""
    try:
        return json.loads(text)
    except ValueError:
        data, _ = json.JSONDecoder().raw_decode(text.lstrip("\ufeff"))
        return data


def office_doc_write(module, path, value, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            conn.run(f"INSERT INTO {_office_docs_table(cache)} (module, owner, key, payload) VALUES (:module, :owner, :key, :payload::json) "
                     f"ON CONFLICT (module, key) DO UPDATE SET payload=EXCLUDED.payload, owner=EXCLUDED.owner, updated_at=now()",
                     module=module, owner=office_store_owner(key), key=key,
                     payload=json.dumps(value, ensure_ascii=False))
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def office_doc_delete(module, path, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"DELETE FROM {_office_docs_table(cache)} WHERE module=:module AND key=:key RETURNING key",
                            module=module, key=key)
        return bool(rows)
    path = Path(path)
    if not path.exists():
        return False
    path.unlink()
    return True


def office_doc_exists(module, path, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT 1 FROM {_office_docs_table(cache)} WHERE module=:module AND key=:key", module=module, key=key)
        return bool(rows)
    return Path(path).is_file()


def office_doc_list(module, directory, suffix=".json", recursive=False, cache=False):
    """返回目录下的 JSON 文档：[(键名/文件名, 内容, 更新时间戳)]，无序。"""
    if _office_use_db(module, directory):
        prefix = office_store_key(directory) + "/"
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT key, payload, updated_at FROM {_office_docs_table(cache)} WHERE module=:module AND key LIKE :pattern",
                            module=module, pattern=_office_like(prefix) + "%")
        result = []
        for key, payload, updated_at in rows:
            rest = key[len(prefix):]
            if (not recursive and "/" in rest) or (suffix and not rest.endswith(suffix)):
                continue
            result.append((rest, payload, _office_ts(updated_at)))
        return result
    directory = Path(directory)
    if not directory.exists():
        return []
    result = []
    for path in (directory.rglob("*") if recursive else directory.iterdir()):
        if not path.is_file() or (suffix and not path.name.endswith(suffix)):
            continue
        try:
            payload = _office_parse_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        result.append((path.relative_to(directory).as_posix(), payload, path.stat().st_mtime))
    return result


def office_doc_owners(module):
    """数据库模式下有数据的用户列表（用于跨用户统计）。文件模式由调用方自行遍历目录。"""
    with _officedb_conn() as conn:
        rows = conn.run("SELECT DISTINCT owner FROM app.documents WHERE module=:module AND owner<>''", module=module)
    return [row[0] for row in rows]


def _office_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------- 二进制文件 ----------

def office_blob_write(module, path, content, content_type=None, cache=False):
    if not isinstance(content, (bytes, bytearray)):
        raise TypeError("二进制内容必须是 bytes")
    content = bytes(content)
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            conn.run(f"INSERT INTO {_office_blobs_table(cache)} (module, owner, key, content, size, sha256, content_type) "
                     "VALUES (:module, :owner, :key, :content, :size, :sha256, :content_type) "
                     "ON CONFLICT (module, key) DO UPDATE SET content=EXCLUDED.content, size=EXCLUDED.size, "
                     "sha256=EXCLUDED.sha256, content_type=EXCLUDED.content_type, owner=EXCLUDED.owner, updated_at=now()",
                     module=module, owner=office_store_owner(key), key=key, content=content, size=len(content),
                     sha256=hashlib.sha256(content).hexdigest(), content_type=content_type)
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def office_blob_read(module, path, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT content FROM {_office_blobs_table(cache)} WHERE module=:module AND key=:key", module=module, key=key)
        return bytes(rows[0][0]) if rows else None
    path = Path(path)
    if not path.is_file():
        return None
    return path.read_bytes()


def office_blob_exists(module, path, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT 1 FROM {_office_blobs_table(cache)} WHERE module=:module AND key=:key", module=module, key=key)
        return bool(rows)
    return Path(path).is_file()


def office_blob_stat(module, path, cache=False):
    """返回 {size, mtime, sha256}；不存在返回 None。"""
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT size, updated_at, sha256 FROM {_office_blobs_table(cache)} WHERE module=:module AND key=:key",
                            module=module, key=key)
        if not rows:
            return None
        return {"size": rows[0][0], "mtime": _office_ts(rows[0][1]), "sha256": rows[0][2]}
    path = Path(path)
    if not path.is_file():
        return None
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime, "sha256": None}


def office_blob_delete(module, path, cache=False):
    if _office_use_db(module, path):
        key = office_store_key(path)
        with _officedb_conn() as conn:
            rows = conn.run(f"DELETE FROM {_office_blobs_table(cache)} WHERE module=:module AND key=:key RETURNING key", module=module, key=key)
        return bool(rows)
    path = Path(path)
    if not path.is_file():
        return False
    path.unlink()
    return True


def office_blob_list(module, directory, prefix="", recursive=False, cache=False):
    """目录下的文件：[(相对名, size, mtime)]。prefix 按文件名开头过滤。"""
    if _office_use_db(module, directory):
        base = office_store_key(directory) + "/"
        with _officedb_conn() as conn:
            rows = conn.run(f"SELECT key, size, updated_at FROM {_office_blobs_table(cache)} WHERE module=:module AND key LIKE :pattern",
                            module=module, pattern=_office_like(base + prefix) + "%")
        result = []
        for key, size, updated_at in rows:
            rest = key[len(base):]
            if not recursive and "/" in rest:
                continue
            result.append((rest, size, _office_ts(updated_at)))
        return result
    directory = Path(directory)
    if not directory.exists():
        return []
    result = []
    for path in (directory.rglob("*") if recursive else directory.iterdir()):
        if not path.is_file():
            continue
        rest = path.relative_to(directory).as_posix()
        if prefix and not rest.startswith(prefix):
            continue
        stat = path.stat()
        result.append((rest, stat.st_size, stat.st_mtime))
    return result


def office_blob_delete_tree(module, directory, cache=False):
    """删除目录下全部文件（数据库模式按键前缀删除）。返回删除数量。"""
    if _office_use_db(module, directory):
        base = office_store_key(directory) + "/"
        with _officedb_conn() as conn:
            rows = conn.run(f"DELETE FROM {_office_blobs_table(cache)} WHERE module=:module AND key LIKE :pattern RETURNING key",
                            module=module, pattern=_office_like(base) + "%")
            docs = conn.run(f"DELETE FROM {_office_docs_table(cache)} WHERE module=:module AND key LIKE :pattern RETURNING key",
                            module=module, pattern=_office_like(base) + "%")
        return len(rows) + len(docs)
    directory = Path(directory)
    if not directory.exists():
        return 0
    count = 0
    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
            count += 1
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        directory.rmdir()
    except OSError:
        pass
    return count


@contextlib.contextmanager
def office_blob_local(module, path, suffix=None, cache=False):
    """给只接受真实路径的库用：数据库模式临时落盘，退出删除；文件模式直接给原路径。"""
    path = Path(path)
    if not _office_use_db(module, path):
        yield path if path.is_file() else None
        return
    content = office_blob_read(module, path, cache=cache)
    if content is None:
        yield None
        return
    handle = tempfile.NamedTemporaryFile(prefix="office-blob-", suffix=suffix or path.suffix, delete=False)
    try:
        handle.write(content)
        handle.close()
        yield Path(handle.name)
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


# ---------- 追加事件 ----------

def office_event_append(module, stream, payload, owner=""):
    """数据库模式写 app.events；文件模式由调用方按原 JSONL 路径追加（返回 False）。"""
    if not officedb_enabled(module):
        return False
    with _officedb_conn() as conn:
        conn.run("INSERT INTO app.events (module, stream, owner, payload) VALUES (:module, :stream_name, :owner, :payload::jsonb)",
                 module=module, stream_name=stream, owner=owner or "", payload=json.dumps(payload, ensure_ascii=False))
    return True


def office_event_recent(module, stream, limit=200, since_seq=None):
    with _officedb_conn() as conn:
        rows = conn.run("SELECT seq, payload FROM app.events WHERE module=:module AND stream=:stream_name "
                        "AND (:since::bigint IS NULL OR seq > :since::bigint) ORDER BY seq DESC LIMIT :limit",
                        module=module, stream_name=stream, since=since_seq, limit=int(limit))
    return [{"seq": seq, **(payload if isinstance(payload, dict) else {"value": payload})} for seq, payload in rows]


def office_event_count(module, stream):
    with _officedb_conn() as conn:
        rows = conn.run("SELECT count(*) FROM app.events WHERE module=:module AND stream=:stream_name", module=module, stream_name=stream)
    return int(rows[0][0])


# ---------- 迁移 ----------

def office_store_import_tree(module, directory, json_suffixes=(".json",), skip=None, dry_run=False, cache=False,
                             incremental=True):
    """把目录下现有文件按原路径导入数据库：JSON 进 documents，其余进 blobs。
    incremental=True 时内容未变（blob 按 sha256、JSON 按内容）的文件不重复写。
    返回 {"documents": n, "blobs": n, "skipped": [...], "unchanged": n}。仅在数据库模式下调用。"""
    directory = Path(directory)
    summary = {"documents": 0, "blobs": 0, "skipped": [], "bytes": 0, "unchanged": 0}
    if not directory.exists():
        return summary
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        if skip and skip(path):
            summary["skipped"].append(str(path))
            continue
        raw = path.read_bytes()
        summary["bytes"] += len(raw)
        if path.suffix.lower() in json_suffixes:
            try:
                payload = _office_parse_json(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                summary["skipped"].append(str(path))
                continue
            if not dry_run:
                if incremental and office_doc_read(module, path, None, cache=cache) == payload:
                    summary["unchanged"] += 1
                    continue
                office_doc_write(module, path, payload, cache=cache)
            summary["documents"] += 1
        else:
            if not dry_run:
                stat = office_blob_stat(module, path, cache=cache) if incremental else None
                if stat and stat["sha256"] == hashlib.sha256(raw).hexdigest():
                    summary["unchanged"] += 1
                    continue
                office_blob_write(module, path, raw, cache=cache)
            summary["blobs"] += 1
    return summary


def office_store_verify_tree(module, directory, json_suffixes=(".json",), skip=None, cache=False):
    """逐文件核对数据库内容与原文件一致；返回 {"checked": n, "mismatch": [...]}。"""
    directory = Path(directory)
    result = {"checked": 0, "mismatch": []}
    if not directory.exists():
        return result
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.endswith(".tmp") or (skip and skip(path)):
            continue
        raw = path.read_bytes()
        if path.suffix.lower() in json_suffixes:
            try:
                expected = _office_parse_json(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            actual = office_doc_read(module, path, None, cache=cache)
            same = json.dumps(actual, ensure_ascii=False, sort_keys=True) == json.dumps(expected, ensure_ascii=False, sort_keys=True)
        else:
            actual = office_blob_read(module, path, cache=cache)
            same = actual == raw
        result["checked"] += 1
        if not same:
            result["mismatch"].append(str(path))
    return result


def office_store_counts(module):
    """数据库模式下该助手的记录数、文件数、字节数。"""
    with _officedb_conn() as conn:
        docs = conn.run("SELECT count(*) FROM app.documents WHERE module=:module", module=module)[0][0]
        blobs = conn.run("SELECT count(*), coalesce(sum(size),0) FROM app.blobs WHERE module=:module", module=module)[0]
        events = conn.run("SELECT count(*) FROM app.events WHERE module=:module", module=module)[0][0]
        cache_docs = conn.run("SELECT count(*) FROM app.cache_documents WHERE module=:module", module=module)[0][0]
        cache_blobs = conn.run("SELECT count(*), coalesce(sum(size),0) FROM app.cache_blobs WHERE module=:module", module=module)[0]
    return {"documents": int(docs), "blobs": int(blobs[0]), "bytes": int(blobs[1]), "events": int(events),
            "cache_documents": int(cache_docs), "cache_blobs": int(cache_blobs[0]), "cache_bytes": int(cache_blobs[1])}


def office_store_export_tree(module, directory, target_root):
    """把数据库内该目录键前缀下的全部内容还原到 target_root（用于回退/导出）。"""
    base = office_store_key(directory) + "/"
    target_root = Path(target_root)
    count = 0
    with _officedb_conn() as conn:
        docs = conn.run("SELECT key, payload FROM app.documents WHERE module=:module AND key LIKE :pattern",
                        module=module, pattern=_office_like(base) + "%")
        blobs = conn.run("SELECT key, content FROM app.blobs WHERE module=:module AND key LIKE :pattern",
                         module=module, pattern=_office_like(base) + "%")
    for key, payload in docs:
        destination = target_root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
    for key, content in blobs:
        destination = target_root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(bytes(content))
        count += 1
    return count
