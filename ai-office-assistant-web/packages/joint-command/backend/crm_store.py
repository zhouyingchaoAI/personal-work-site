"""联指经营助手的 PostgreSQL 存储后端（数据中台 office-postgres）。

存储模式由 user_data/_datacenter/crm_db.json 决定：enabled=true 走本模块，
否则 crm.py 走原本地 JSON 文件。设计要点：

- 表复用数据中台镜像表 crm.<collection>（payload jsonb + 生成列），写入后
  数据接口的结构化查询即时可见；历史入 crm.live_history；共享 JSON
  （员工目录之外的经营分析、导入完善任务）入 crm.live_blobs。
- 读走进程内整表缓存，用 crm.live_state 全局版本号失效（写后本进程立即
  可见；其他进程如 celery 的写入 ≤0.8 秒内可见），替代原先每次快照
  近千次文件 stat。
- 写为差量 upsert/delete + 版本号自增，单事务提交；变更历史与文件模式
  语义一致（记录被修改/删除前的旧值）。
"""
import json
import queue as _crmdb_queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor/pgdeps"))
import pg8000.native  # noqa: E402

CRMDB_COLLECTIONS = ("units", "people", "relations", "actions", "links", "staff", "opportunities", "sales_contracts")
CRMDB_NAME_COLS = {"units", "people", "opportunities"}
_crmdb_lock = threading.RLock()
_crmdb_state = {"config": None, "config_mtime": None, "version": 0, "version_at": 0.0,
                "tables": {}, "staff_directory": None}
_crmdb_pool = _crmdb_queue.LifoQueue(maxsize=4)
_crmdb_slots = threading.BoundedSemaphore(4)
CRMDB_VERSION_TTL = 0.8  # 秒；跨进程写入的最大可见延迟


def _crmdb_config_path():
    return Path(USER_DATA_DIR) / "_datacenter" / "crm_db.json"


def crmdb_config():
    path = _crmdb_config_path()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    with _crmdb_lock:
        if _crmdb_state["config_mtime"] != mtime:
            try:
                _crmdb_state["config"] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _crmdb_state["config"] = None
            _crmdb_state["config_mtime"] = mtime
        return _crmdb_state["config"]


def crmdb_enabled():
    config = crmdb_config()
    return bool(config and config.get("enabled"))


class _crmdb_conn:
    """池化连接；异常时丢弃连接而不是放回。"""

    def __enter__(self):
        if not _crmdb_slots.acquire(timeout=8):
            raise RuntimeError("客户经营数据库繁忙，请稍后重试")
        self.conn = None
        try:
            try:
                self.conn = _crmdb_pool.get_nowait()
            except _crmdb_queue.Empty:
                config = crmdb_config() or {}
                self.conn = pg8000.native.Connection(
                    user=config.get("user", "crm_app"), password=config["password"],
                    host=config.get("host", "office-postgres"), port=int(config.get("port", 5432)),
                    database=config.get("database", "office"), timeout=10)
            return self.conn
        except Exception:
            _crmdb_slots.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            _crmdb_pool.put_nowait(self.conn)
        else:
            try:
                self.conn.close()
            except Exception:
                pass
        _crmdb_slots.release()


def crmdb_version(force=False):
    """全局数据版本；缓存 CRMDB_VERSION_TTL 秒内的检查结果。"""
    now = time.monotonic()
    with _crmdb_lock:
        if not force and _crmdb_state["version"] and now - _crmdb_state["version_at"] < CRMDB_VERSION_TTL:
            return _crmdb_state["version"]
    with _crmdb_conn() as conn:
        version = conn.run("SELECT version FROM crm.live_state WHERE key='global'")[0][0]
    with _crmdb_lock:
        if version != _crmdb_state["version"]:
            _crmdb_state["tables"] = {}
            _crmdb_state["staff_directory"] = None
        _crmdb_state["version"] = version
        _crmdb_state["version_at"] = now
        return version


def _crmdb_set_version(version):
    with _crmdb_lock:
        _crmdb_state["version"] = version
        _crmdb_state["version_at"] = time.monotonic()


def _crmdb_table(collection):
    if collection not in CRMDB_COLLECTIONS:
        raise ValueError("未知数据集")
    return f"crm.{collection}"


def _crmdb_load_table(collection, version):
    """整表缓存按 owner 存 JSON 串：读方 json.loads 拿独立副本，
    比 deepcopy 快且与文件模式的解析成本持平（省掉文件 IO 与 stat）。"""
    with _crmdb_lock:
        entry = _crmdb_state["tables"].get(collection)
        if entry and entry["version"] == version:
            return entry["data"]
    with _crmdb_conn() as conn:
        # pos 保留文件时代的插入顺序，列表类页面的展示顺序与切换前一致。
        rows = conn.run(f"SELECT owner, id, payload FROM {_crmdb_table(collection)} "
                        f"ORDER BY pos NULLS LAST, id")
    grouped = {}
    for owner, record_id, payload in rows:
        grouped.setdefault(owner, {})[record_id] = payload
    data = {owner: json.dumps(records, ensure_ascii=False) for owner, records in grouped.items()}
    with _crmdb_lock:
        _crmdb_state["tables"][collection] = {"version": version, "data": data}
    return data


def crmdb_load(owner, collection):
    version = crmdb_version()
    raw = _crmdb_load_table(collection, version).get(owner)
    return json.loads(raw) if raw else {}


def crmdb_staff_directory():
    version = crmdb_version()
    with _crmdb_lock:
        entry = _crmdb_state["staff_directory"]
        if entry and entry["version"] == version:
            return json.loads(entry["data"])
    with _crmdb_conn() as conn:
        rows = conn.run("SELECT id, payload FROM crm.staff_directory ORDER BY pos NULLS LAST, id")
    data = json.dumps({record_id: payload for record_id, payload in rows}, ensure_ascii=False)
    with _crmdb_lock:
        _crmdb_state["staff_directory"] = {"version": version, "data": data}
    return json.loads(data)


def _crmdb_bump(conn):
    return conn.run("UPDATE crm.live_state SET version=version+1 WHERE key='global' RETURNING version")[0][0]


def _crmdb_apply(conn, table, owner, records, current, name_col, current_pos=None):
    positions = {rid: i for i, rid in enumerate(records)}
    current_pos = current_pos or {}
    upserts = [{"id": rid, "name": str((rec or {}).get("name", ""))[:300], "payload": rec,
                "pos": positions[rid]}
               for rid, rec in records.items() if current.get(rid) != rec]
    touched = {item["id"] for item in upserts}
    moved = [{"id": rid, "pos": positions[rid]} for rid in records
             if rid not in touched and current_pos.get(rid) != positions[rid]]
    removed = [rid for rid in current if rid not in records]
    if upserts:
        cols, vals = ("owner, id, name, payload, pos", "e->>'id', e->>'name', e->'payload', (e->>'pos')::integer") \
            if name_col else ("owner, id, payload, pos", "e->>'id', e->'payload', (e->>'pos')::integer")
        sets = "payload=EXCLUDED.payload, pos=EXCLUDED.pos, synced_at=now()" + \
            (", name=EXCLUDED.name" if name_col else "")
        conn.run(f"INSERT INTO {table} ({cols}) SELECT :owner, {vals} "
                 f"FROM jsonb_array_elements(:data::jsonb) e ON CONFLICT (owner, id) DO UPDATE SET {sets}",
                 owner=owner, data=json.dumps(upserts, ensure_ascii=False))
    if moved:
        conn.run(f"UPDATE {table} t SET pos=(e->>'pos')::integer FROM jsonb_array_elements(:data::jsonb) e "
                 f"WHERE t.owner=:owner AND t.id=e->>'id'",
                 owner=owner, data=json.dumps(moved))
    if removed:
        conn.run(f"DELETE FROM {table} WHERE owner=:owner AND id IN "
                 f"(SELECT jsonb_array_elements_text(:ids::jsonb))",
                 owner=owner, ids=json.dumps(removed))
    return len(upserts), len(removed)


def crmdb_store(owner, collection, records, previous=None):
    """整集合替换语义（与文件模式一致）：差量写 + 历史 + 版本自增。"""
    table = _crmdb_table(collection)
    name_col = collection in CRMDB_NAME_COLS
    with _crmdb_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run(f"SELECT id, payload, pos FROM {table} WHERE owner=:owner", owner=owner)
            current = {rid: payload for rid, payload, _pos in rows}
            current_pos = {rid: pos for rid, _payload, pos in rows}
            base = current if previous is None else previous
            history = [{"record_id": rid, "at": crm_now(), "entry": old}
                       for rid, old in base.items() if records.get(rid) != old]
            _crmdb_apply(conn, table, owner, records, current, name_col, current_pos)
            if history:
                conn.run("INSERT INTO crm.live_history (owner, collection, record_id, at, entry) "
                         "SELECT :owner::text, :collection::text, e->>'record_id', e->>'at', "
                         "jsonb_build_object('at', e->>'at', 'collection', :collection::text, "
                         "'record_id', e->>'record_id', 'record', e->'entry') "
                         "FROM jsonb_array_elements(:data::jsonb) e",
                         owner=owner, collection=collection, data=json.dumps(history, ensure_ascii=False))
            version = _crmdb_bump(conn)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    with _crmdb_lock:
        entry = _crmdb_state["tables"].get(collection)
        if entry:
            entry["data"][owner] = json.dumps(records, ensure_ascii=False)
            entry["version"] = version
    _crmdb_set_version(version)


def crmdb_store_staff_directory(records):
    with _crmdb_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT id, payload, pos FROM crm.staff_directory")
            current = {rid: payload for rid, payload, _pos in rows}
            current_pos = {rid: pos for rid, _payload, pos in rows}
            positions = {rid: i for i, rid in enumerate(records)}
            upserts = [{"id": rid, "payload": rec, "pos": positions[rid]}
                       for rid, rec in records.items() if current.get(rid) != rec]
            touched = {item["id"] for item in upserts}
            moved = [{"id": rid, "pos": positions[rid]} for rid in records
                     if rid not in touched and current_pos.get(rid) != positions[rid]]
            removed = [rid for rid in current if rid not in records]
            if upserts:
                conn.run("INSERT INTO crm.staff_directory (id, payload, pos) "
                         "SELECT e->>'id', e->'payload', (e->>'pos')::integer "
                         "FROM jsonb_array_elements(:data::jsonb) e "
                         "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, pos=EXCLUDED.pos, synced_at=now()",
                         data=json.dumps(upserts, ensure_ascii=False))
            if moved:
                conn.run("UPDATE crm.staff_directory t SET pos=(e->>'pos')::integer "
                         "FROM jsonb_array_elements(:data::jsonb) e WHERE t.id=e->>'id'",
                         data=json.dumps(moved))
            if removed:
                conn.run("DELETE FROM crm.staff_directory WHERE id IN "
                         "(SELECT jsonb_array_elements_text(:ids::jsonb))", ids=json.dumps(removed))
            version = _crmdb_bump(conn)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    with _crmdb_lock:
        _crmdb_state["staff_directory"] = {"version": version,
                                           "data": json.dumps(records, ensure_ascii=False)}
    _crmdb_set_version(version)


def crmdb_record_versions(owner, collection, record_id, limit=50):
    with _crmdb_conn() as conn:
        rows = conn.run("SELECT entry FROM crm.live_history WHERE owner=:owner AND collection=:collection "
                        "AND record_id=:rid ORDER BY seq DESC LIMIT :n",
                        owner=owner, collection=collection, rid=record_id, n=limit)
    return [row[0] for row in rows]


# ---------- 共享 JSON（经营分析快照 / 导入完善任务） ----------

_crmdb_blob_cache = {}


def crmdb_blob_get(key):
    """大 JSON（经营分析快照/任务队列）带 updated_at 校验缓存：
    命中时只有一次毫秒级小查询，不重复搬运几百 KB。"""
    with _crmdb_conn() as conn:
        rows = conn.run("SELECT updated_at FROM crm.live_blobs WHERE key=:key", key=key)
        if not rows:
            with _crmdb_lock:
                _crmdb_blob_cache.pop(key, None)
            return None
        stamp = rows[0][0]
        with _crmdb_lock:
            cached = _crmdb_blob_cache.get(key)
        if cached and cached[0] == stamp:
            return json.loads(cached[1])
        payload = conn.run("SELECT payload FROM crm.live_blobs WHERE key=:key", key=key)[0][0]
    raw = json.dumps(payload, ensure_ascii=False)
    with _crmdb_lock:
        _crmdb_blob_cache[key] = (stamp, raw)
        while len(_crmdb_blob_cache) > 8:
            _crmdb_blob_cache.pop(next(iter(_crmdb_blob_cache)))
    return payload


def crmdb_blob_put(key, payload):
    with _crmdb_conn() as conn:
        # json 而非 jsonb：保留键序，任务/快照的展示顺序与文件时代一致。
        conn.run("INSERT INTO crm.live_blobs (key, payload) VALUES (:key, :payload::json) "
                 "ON CONFLICT (key) DO UPDATE SET payload=EXCLUDED.payload, updated_at=now()",
                 key=key, payload=json.dumps(payload, ensure_ascii=False))


_crmdb_versions_cache = {"stamp": None, "rows": None}


def crmdb_business_versions():
    """经营分析快照版本列表。json 列的 ->> 每次都会重新解析几百 KB 文本，
    因此结果按 (count, max(updated_at)) 校验缓存，只有导入后才重算。"""
    with _crmdb_conn() as conn:
        stamp = tuple(conn.run("SELECT count(*), max(updated_at) FROM crm.live_blobs "
                               "WHERE key LIKE 'business!_analysis:%' ESCAPE '!'")[0])
        with _crmdb_lock:
            if _crmdb_versions_cache["stamp"] == stamp:
                return json.loads(_crmdb_versions_cache["rows"])
        rows = conn.run("SELECT key, payload->>'imported_at', payload->>'imported_by', "
                        "payload->>'filename', coalesce(json_array_length(payload->'sheets'), 0) "
                        "FROM crm.live_blobs WHERE key LIKE 'business!_analysis:%' ESCAPE '!'")
    result = [{"version": key.split(":", 1)[1], "imported_at": imported_at or "",
               "imported_by": imported_by or "", "filename": filename or "", "sheets": sheets}
              for key, imported_at, imported_by, filename, sheets in rows]
    with _crmdb_lock:
        _crmdb_versions_cache["stamp"] = stamp
        _crmdb_versions_cache["rows"] = json.dumps(result, ensure_ascii=False)
    return result


def crmdb_blob_keys(prefix):
    with _crmdb_conn() as conn:
        rows = conn.run("SELECT key FROM crm.live_blobs WHERE key LIKE :p ESCAPE '!' ORDER BY key",
                        p=prefix.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%")
    return [row[0] for row in rows]


# ---------- 一次性迁移与回滚导出 ----------

def crmdb_import_from_files(root=None):
    """本地文件 → 数据库，整表替换并逐集合核对行数；返回核对报告。"""
    root = Path(root or USER_DATA_DIR)
    report = {"collections": [], "history": [], "blobs": [], "ok": True}

    def read_json_file(path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    owners = sorted(p.parent.name for p in root.glob("*/crm") if p.is_dir())
    with _crmdb_conn() as conn:
        conn.run("BEGIN")
        try:
            for collection in CRMDB_COLLECTIONS:
                table = _crmdb_table(collection)
                conn.run(f"DELETE FROM {table}")
                source_total = 0
                for owner in owners:
                    records = read_json_file(root / owner / "crm" / f"{collection}.json")
                    source_total += len(records)
                    _crmdb_apply(conn, table, owner, records, {}, collection in CRMDB_NAME_COLS)
                stored = conn.run(f"SELECT count(*) FROM {table}")[0][0]
                report["collections"].append({"collection": collection, "source": source_total,
                                              "stored": stored, "match": stored == source_total})
            directory = read_json_file(root / "_crm_staff_directory.json")
            conn.run("DELETE FROM crm.staff_directory")
            if directory:
                conn.run("INSERT INTO crm.staff_directory (id, payload, pos) "
                         "SELECT e->>'id', e->'payload', (e->>'pos')::integer "
                         "FROM jsonb_array_elements(:data::jsonb) e",
                         data=json.dumps([{"id": k, "payload": v, "pos": i}
                                          for i, (k, v) in enumerate(directory.items())],
                                         ensure_ascii=False))
            stored = conn.run("SELECT count(*) FROM crm.staff_directory")[0][0]
            report["collections"].append({"collection": "staff_directory", "source": len(directory),
                                          "stored": stored, "match": stored == len(directory)})

            conn.run("DELETE FROM crm.live_history")
            for owner in owners:
                for path in sorted((root / owner / "crm" / "history").glob("*.jsonl")):
                    collection = path.stem
                    entries = []
                    for line in path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except ValueError:
                            continue
                        entries.append({"record_id": str(item.get("record_id", "")),
                                        "at": str(item.get("at", "")), "entry": item})
                    for start in range(0, len(entries), 2000):
                        chunk = entries[start:start + 2000]
                        conn.run("INSERT INTO crm.live_history (owner, collection, record_id, at, entry) "
                                 "SELECT :owner, :collection, e->>'record_id', e->>'at', e->'entry' "
                                 "FROM jsonb_array_elements(:data::jsonb) e",
                                 owner=owner, collection=collection,
                                 data=json.dumps(chunk, ensure_ascii=False))
                    stored = conn.run("SELECT count(*) FROM crm.live_history WHERE owner=:o AND collection=:c",
                                      o=owner, c=collection)[0][0]
                    report["history"].append({"owner": owner, "collection": collection,
                                              "source": len(entries), "stored": stored,
                                              "match": stored == len(entries)})

            blobs = {"import_tasks": root / ".crm-import-completion" / "tasks.json",
                     "business_analysis:legacy": root / "_crm_business_analysis.json"}
            analysis_dir = root / "_crm_business_analysis"
            if analysis_dir.is_dir():
                for path in sorted(analysis_dir.glob("*.json")):
                    blobs[f"business_analysis:{path.stem}"] = path
            conn.run("DELETE FROM crm.live_blobs")
            for key, path in blobs.items():
                if not path.exists():
                    continue
                payload = read_json_file(path)
                conn.run("INSERT INTO crm.live_blobs (key, payload) VALUES (:key, :payload::json)",
                         key=key, payload=json.dumps(payload, ensure_ascii=False))
                report["blobs"].append({"key": key, "keys": len(payload)})
            version = _crmdb_bump(conn)
            report["ok"] = all(item["match"] for item in report["collections"] + report["history"])
            if not report["ok"]:
                raise RuntimeError("迁移核对不一致，已回滚")
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    with _crmdb_lock:
        _crmdb_state["tables"] = {}
        _crmdb_state["staff_directory"] = None
    _crmdb_set_version(version)
    return report


def crmdb_export_to_files(out_dir):
    """数据库 → 目录（回滚工具）：还原集合 / 员工目录 / 历史 / 共享 JSON。"""
    out = Path(out_dir)
    exported = []
    with _crmdb_conn() as conn:
        for collection in CRMDB_COLLECTIONS:
            rows = conn.run(f"SELECT owner, id, payload FROM {_crmdb_table(collection)} ORDER BY owner, id")
            per_owner = {}
            for owner, rid, payload in rows:
                per_owner.setdefault(owner, {})[rid] = payload
            for owner, records in per_owner.items():
                path = out / owner / "crm" / f"{collection}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
                exported.append(str(path))
        directory = {rid: payload for rid, payload in conn.run("SELECT id, payload FROM crm.staff_directory")}
        (out / "_crm_staff_directory.json").write_text(
            json.dumps(directory, ensure_ascii=False, indent=2), encoding="utf-8")
        history = conn.run("SELECT owner, collection, entry FROM crm.live_history ORDER BY seq")
        streams = {}
        for owner, collection, entry in history:
            path = out / owner / "crm" / "history" / f"{collection}.jsonl"
            if path not in streams:
                path.parent.mkdir(parents=True, exist_ok=True)
                streams[path] = path.open("w", encoding="utf-8")
            streams[path].write(json.dumps(entry, ensure_ascii=False) + "\n")
        for stream in streams.values():
            stream.close()
        for key, payload in conn.run("SELECT key, payload FROM crm.live_blobs"):
            if key == "import_tasks":
                path = out / ".crm-import-completion" / "tasks.json"
            elif key == "business_analysis:legacy":
                path = out / "_crm_business_analysis.json"
            elif key.startswith("business_analysis:"):
                path = out / "_crm_business_analysis" / (key.split(":", 1)[1] + ".json")
            else:
                path = out / "_crm_blobs" / (key.replace(":", "_") + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            exported.append(str(path))
    configuration_files = crm_configuration_export(out) if (crmdb_config() or {}).get('configuration_enabled') else 0
    return {"ok": True, "files": len(exported) + 1 + configuration_files}
