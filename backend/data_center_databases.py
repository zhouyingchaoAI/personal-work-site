"""数据中台「数据库直连」：平台内全部数据库实例的只读浏览。

安全约束：
- 全部接口在 server.py 层要求超级管理员；连接注册文件 _datacenter/db_connections.json
  由宿主机脚本 scripts/datacenter_db_connections_setup.py 生成（600 权限），密文不进代码。
- 只读强制：SQL 库走 READ ONLY 事务 + 语句白名单；Redis/ES/Qdrant/Neo4j 只发只读命令。
- 行数据经 dc_mask 脱敏（密码 / 密钥字段），每次浏览与查询写入 access_log.jsonl。
"""
import base64
import decimal
import json
import os
import re
import socket
import sqlite3 as _dcdb_sqlite3
import sys
import time
import urllib.parse
import urllib.request
import uuid as _dcdb_uuid
from concurrent.futures import ThreadPoolExecutor as _DcdbPool
from datetime import date as _dcdb_date, datetime as _dcdb_datetime
from pathlib import Path

# 共享命名空间下 __file__ 指向 app.py；vendor 依赖目录以应用根目录为准。
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor/pgdeps"))
import pg8000.native  # noqa: E402

DCDB_ROW_LIMIT = 200
DCDB_PAGE_SIZE = 50
DCDB_SQL_ALLOWED = re.compile(r"^\s*(select|with|show|explain|describe|desc|values|table)\b", re.I)
DCDB_IDENT = re.compile(r"^[A-Za-z0-9_$一-鿿.-]+$")
DCDB_KINDS_SQL = ("postgres", "mysql", "sqlite")


def _dcdb_registry():
    data = read_json(datacenter_dir(USER_DATA_DIR) / "db_connections.json", {})
    instances = data.get("instances") or []
    if not instances:
        raise RuntimeError("连接注册文件缺失，请在宿主机运行 scripts/datacenter_db_connections_setup.py")
    return {inst["id"]: inst for inst in instances}


def _dcdb_inst(instance_id):
    inst = _dcdb_registry().get(str(instance_id or ""))
    if not inst:
        raise ValueError("未知的数据库实例")
    return inst


def _dcdb_password(inst):
    if inst.get("password_env"):
        value = os.environ.get(inst["password_env"], "")
        if not value:
            raise RuntimeError(f"环境变量 {inst['password_env']} 未配置")
        return value
    return inst.get("password", "")


def _dcdb_safe(value):
    """转成可 JSON 序列化并截断超长内容。"""
    if isinstance(value, dict):
        return {str(k): _dcdb_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_dcdb_safe(v) for v in list(value)[:200]]
    if isinstance(value, (bytes, memoryview)):
        raw = bytes(value)
        return f"<二进制 {len(raw)} 字节> " + base64.b64encode(raw[:48]).decode()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (_dcdb_datetime, _dcdb_date)):
        return value.isoformat()
    if isinstance(value, _dcdb_uuid.UUID):
        return str(value)
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + f"……（共 {len(value)} 字符）"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _dcdb_rows_payload(columns, rows, **extra):
    safe = [dc_mask(_dcdb_safe(dict(zip(columns, row)) if not isinstance(row, dict) else row)) for row in rows]
    return {"ok": True, "columns": list(columns), "rows": safe, **extra}


def _dcdb_ident(name, what="对象名"):
    name = str(name or "").strip()
    if not name or not DCDB_IDENT.match(name):
        raise ValueError(f"{what}非法")
    return name


# ---------- PostgreSQL ----------

def _dcdb_pg_connect(inst, db=None):
    return pg8000.native.Connection(
        user=inst["user"], password=_dcdb_password(inst), host=inst["host"],
        port=int(inst["port"]), database=db or inst.get("database", "postgres"), timeout=6)


def _dcdb_pg_readonly(conn):
    conn.run("BEGIN READ ONLY")
    conn.run("SET LOCAL statement_timeout='8000ms'")


def _dcdb_pg_objects(inst, db):
    conn = _dcdb_pg_connect(inst, db)
    try:
        _dcdb_pg_readonly(conn)
        dbs = [r[0] for r in conn.run("SELECT datname FROM pg_database WHERE NOT datistemplate ORDER BY 1")]
        objects = [{"name": f"{r[0]}.{r[1]}", "rows": max(int(r[2]), 0), "size": int(r[3]), "kind_label": r[4]}
                   for r in conn.run(
                       "SELECT n.nspname, c.relname, c.reltuples::bigint, pg_total_relation_size(c.oid), "
                       "CASE c.relkind WHEN 'm' THEN '物化视图' ELSE '表' END "
                       "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                       "WHERE c.relkind IN ('r','p','m') AND n.nspname NOT IN "
                       "('pg_catalog','information_schema','pg_toast') ORDER BY 1, 2")]
        conn.run("COMMIT")
        return {"databases": dbs, "objects": objects, "rows_label": "行（估算）"}
    finally:
        conn.close()


def _dcdb_pg_rows(inst, db, obj, page, size):
    schema, _, table = obj.partition(".")
    from pg8000.native import identifier
    target = identifier(_dcdb_ident(schema, "schema")) + "." + identifier(_dcdb_ident(table, "表名"))
    conn = _dcdb_pg_connect(inst, db)
    try:
        _dcdb_pg_readonly(conn)
        try:
            total = conn.run("SELECT count(*) FROM " + target)[0][0]
        except Exception:
            conn.run("ROLLBACK"); _dcdb_pg_readonly(conn)
            total = None
        rows = conn.run(f"SELECT * FROM {target} LIMIT {int(size)} OFFSET {int(page) * int(size)}")
        columns = [c["name"] for c in (conn.columns or [])]
        conn.run("COMMIT")
        return _dcdb_rows_payload(columns, rows, total=total)
    finally:
        conn.close()


def _dcdb_pg_query(inst, db, sql):
    conn = _dcdb_pg_connect(inst, db)
    try:
        _dcdb_pg_readonly(conn)
        rows = conn.run(sql)
        columns = [c["name"] for c in (conn.columns or [])]
        conn.run("COMMIT")
        truncated = rows is not None and len(rows) > DCDB_ROW_LIMIT
        return _dcdb_rows_payload(columns, (rows or [])[:DCDB_ROW_LIMIT], truncated=truncated)
    finally:
        conn.close()


# ---------- MySQL ----------

def _dcdb_mysql_connect(inst, db=None):
    import pymysql
    return pymysql.connect(host=inst["host"], port=int(inst["port"]), user=inst["user"],
                           password=_dcdb_password(inst), database=db or inst.get("database"),
                           connect_timeout=6, read_timeout=10, charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)


def _dcdb_mysql_run(inst, db, statements):
    conn = _dcdb_mysql_connect(inst, db)
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute("SET SESSION MAX_EXECUTION_TIME=8000")
            cur.execute("START TRANSACTION READ ONLY")
            result = []
            for stmt, args in statements:
                cur.execute(stmt, args)
                result.append((list(cur.fetchall()), [d[0] for d in cur.description or []]))
            conn.rollback()
            return result
    finally:
        conn.close()


def _dcdb_mysql_objects(inst, db):
    db = db or inst.get("database")
    (dbs, _), (tables, _) = _dcdb_mysql_run(inst, None, [
        ("SHOW DATABASES", None),
        ("SELECT table_name AS name, table_rows AS rows_est, data_length + index_length AS size, "
         "table_type AS ttype FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name", (db,))])
    names = [list(d.values())[0] for d in dbs]
    names = [n for n in names if n not in ("information_schema", "performance_schema", "mysql", "sys")]
    objects = [{"name": t["name"], "rows": int(t["rows_est"] or 0), "size": int(t["size"] or 0),
                "kind_label": "视图" if t["ttype"] == "VIEW" else "表"} for t in tables]
    return {"databases": names, "objects": objects, "rows_label": "行（估算）"}


def _dcdb_mysql_rows(inst, db, obj, page, size):
    table = _dcdb_ident(obj, "表名").replace("`", "")
    (rows, columns), = _dcdb_mysql_run(inst, db or inst.get("database"), [
        (f"SELECT * FROM `{table}` LIMIT %s OFFSET %s", (int(size), int(page) * int(size)))])
    (count_rows, _), = _dcdb_mysql_run(inst, db or inst.get("database"), [(f"SELECT count(*) AS c FROM `{table}`", None)])
    return _dcdb_rows_payload(columns, rows, total=int(count_rows[0]["c"]))


def _dcdb_mysql_query(inst, db, sql):
    (rows, columns), = _dcdb_mysql_run(inst, db or inst.get("database"), [(sql, None)])
    return _dcdb_rows_payload(columns, rows[:DCDB_ROW_LIMIT], truncated=len(rows) > DCDB_ROW_LIMIT)


# ---------- SQLite ----------

def _dcdb_sqlite_connect(inst):
    path = (BASE_DIR / inst["path"]).resolve()
    conn = _dcdb_sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = _dcdb_sqlite3.Row
    return conn


def _dcdb_sqlite_objects(inst, _db):
    with _dcdb_sqlite_connect(inst) as conn:
        objects = []
        for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                  "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            try:
                count = conn.execute(f'SELECT count(*) FROM "{name}"' if '"' not in name else "SELECT 0").fetchone()[0]
            except Exception:
                count = None
            objects.append({"name": name, "rows": count, "size": None, "kind_label": "表"})
        return {"databases": [], "objects": objects, "rows_label": "行"}


def _dcdb_sqlite_rows(inst, _db, obj, page, size):
    table = _dcdb_ident(obj, "表名").replace('"', "")
    with _dcdb_sqlite_connect(inst) as conn:
        total = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}" LIMIT ? OFFSET ?',
                                              (int(size), int(page) * int(size)))]
        columns = list(rows[0].keys()) if rows else [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        return _dcdb_rows_payload(columns, rows, total=total)


def _dcdb_sqlite_query(inst, _db, sql):
    with _dcdb_sqlite_connect(inst) as conn:
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchmany(DCDB_ROW_LIMIT + 1)]
        columns = [d[0] for d in cur.description or []]
        return _dcdb_rows_payload(columns, rows[:DCDB_ROW_LIMIT], truncated=len(rows) > DCDB_ROW_LIMIT)


# ---------- MongoDB ----------

def _dcdb_mongo_client(inst):
    from pymongo import MongoClient
    return MongoClient(host=inst["host"], port=int(inst["port"]), username=inst["user"],
                       password=_dcdb_password(inst), authSource="admin", directConnection=True,
                       serverSelectionTimeoutMS=4000, socketTimeoutMS=8000, connectTimeoutMS=4000)


def _dcdb_mongo_objects(inst, db):
    client = _dcdb_mongo_client(inst)
    try:
        dbs = [n for n in client.list_database_names() if n not in ("local", "config")]
        db = db or ("fastgpt" if "fastgpt" in dbs else (dbs[0] if dbs else "admin"))
        objects = [{"name": name, "rows": client[db][name].estimated_document_count(), "size": None,
                    "kind_label": "集合"} for name in sorted(client[db].list_collection_names())]
        return {"databases": dbs, "objects": objects, "current_db": db, "rows_label": "文档（估算）"}
    finally:
        client.close()


def _dcdb_mongo_rows(inst, db, obj, page, size, filter_text=""):
    query = {}
    if str(filter_text or "").strip():
        if "$where" in filter_text:
            raise ValueError("不支持 $where 过滤")
        query = json.loads(filter_text)
        if not isinstance(query, dict):
            raise ValueError("过滤条件需是 JSON 对象")
    client = _dcdb_mongo_client(inst)
    try:
        coll = client[db or "fastgpt"][str(obj)]
        total = coll.count_documents(query, maxTimeMS=5000) if query else coll.estimated_document_count()
        docs = [{k: _dcdb_safe(v) for k, v in d.items()} for d in
                coll.find(query).skip(int(page) * int(size)).limit(int(size)).max_time_ms(8000)]
        columns = sorted({k for d in docs for k in d}) or ["_id"]
        return _dcdb_rows_payload(columns, docs, total=total)
    finally:
        client.close()


# ---------- Redis（内置最小 RESP 客户端，只发白名单里的只读命令） ----------

class _DcdbRedis:
    def __init__(self, inst):
        self.sock = socket.create_connection((inst["host"], int(inst["port"])), timeout=5)
        self.fh = self.sock.makefile("rb")
        if inst.get("password"):
            self.cmd("AUTH", inst["password"])

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def cmd(self, *args):
        payload = b"*" + str(len(args)).encode() + b"\r\n"
        for arg in args:
            data = arg if isinstance(arg, bytes) else str(arg).encode()
            payload += b"$" + str(len(data)).encode() + b"\r\n" + data + b"\r\n"
        self.sock.sendall(payload)
        return self._read()

    def _read(self):
        line = self.fh.readline().rstrip(b"\r\n")
        kind, body = line[:1], line[1:]
        if kind == b"+":
            return body.decode("utf-8", "replace")
        if kind == b"-":
            raise RuntimeError("Redis: " + body.decode("utf-8", "replace"))
        if kind == b":":
            return int(body)
        if kind == b"$":
            length = int(body)
            if length == -1:
                return None
            data = self.fh.read(length + 2)[:length]
            return data.decode("utf-8", "replace")
        if kind == b"*":
            count = int(body)
            return None if count == -1 else [self._read() for _ in range(count)]
        raise RuntimeError("Redis 响应无法解析")


def _dcdb_redis_objects(inst, _db, pattern="*"):
    client = _DcdbRedis(inst)
    try:
        info = {}
        for line in (client.cmd("INFO") or "").splitlines():
            if ":" in line and not line.startswith("#"):
                key, _, value = line.partition(":")
                info[key] = value
        cursor, keys = "0", []
        for _ in range(40):
            cursor, batch = client.cmd("SCAN", cursor, "MATCH", pattern or "*", "COUNT", "200")
            keys.extend(batch or [])
            if cursor == "0" or len(keys) >= DCDB_ROW_LIMIT:
                break
        objects = []
        for key in keys[:DCDB_ROW_LIMIT]:
            objects.append({"name": key, "rows": None, "size": None, "kind_label": client.cmd("TYPE", key)})
        summary = {"redis_version": info.get("redis_version", ""), "used_memory_human": info.get("used_memory_human", ""),
                   "total_keys": client.cmd("DBSIZE")}
        return {"databases": [], "objects": objects, "rows_label": "", "summary": summary,
                "truncated": len(keys) > DCDB_ROW_LIMIT}
    finally:
        client.close()


def _dcdb_redis_rows(inst, _db, key, _page, _size):
    client = _DcdbRedis(inst)
    try:
        kind = client.cmd("TYPE", key)
        ttl = client.cmd("TTL", key)
        if kind == "string":
            value = client.cmd("GET", key)
        elif kind == "list":
            value = client.cmd("LRANGE", key, 0, 99)
        elif kind == "hash":
            flat = client.cmd("HSCAN", key, "0", "COUNT", "100")[1] or []
            value = dict(zip(flat[::2], flat[1::2]))
        elif kind == "set":
            value = (client.cmd("SSCAN", key, "0", "COUNT", "100") or [None, []])[1]
        elif kind == "zset":
            flat = client.cmd("ZRANGE", key, 0, 99, "WITHSCORES") or []
            value = [{"member": m, "score": s} for m, s in zip(flat[::2], flat[1::2])]
        else:
            value = f"<类型 {kind}，未提供预览>"
        row = {"key": key, "type": kind, "ttl_seconds": ttl, "value": _dcdb_safe(value)}
        return _dcdb_rows_payload(["key", "type", "ttl_seconds", "value"], [row], total=1)
    finally:
        client.close()


# ---------- HTTP 类（Elasticsearch / Qdrant / Neo4j） ----------

def _dcdb_http(inst, method, path, body=None):
    req = urllib.request.Request(inst["url"].rstrip("/") + path, method=method,
                                 headers={"Content-Type": "application/json"})
    if inst.get("user"):
        token = base64.b64encode(f"{inst['user']}:{_dcdb_password(inst)}".encode()).decode()
        req.add_header("Authorization", "Basic " + token)
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def _dcdb_es_objects(inst, _db):
    indices = _dcdb_http(inst, "GET", "/_cat/indices?format=json&bytes=b")
    objects = [{"name": i.get("index", ""), "rows": int(i.get("docs.count") or 0),
                "size": int(i.get("store.size") or 0), "kind_label": i.get("health", "")}
               for i in sorted(indices, key=lambda x: x.get("index", ""))]
    return {"databases": [], "objects": objects, "rows_label": "文档"}


def _dcdb_es_rows(inst, _db, obj, page, size):
    index = _dcdb_ident(obj, "索引名")
    result = _dcdb_http(inst, "POST", f"/{index}/_search",
                        {"size": int(size), "from": int(page) * int(size)})
    hits = result.get("hits", {})
    docs = [{"_id": h.get("_id"), **(h.get("_source") or {})} for h in hits.get("hits", [])]
    columns = sorted({k for d in docs for k in d}) or ["_id"]
    total = (hits.get("total") or {}).get("value") if isinstance(hits.get("total"), dict) else hits.get("total")
    return _dcdb_rows_payload(columns, docs, total=total)


def _dcdb_qdrant_objects(inst, _db):
    collections = (_dcdb_http(inst, "GET", "/collections").get("result") or {}).get("collections") or []
    objects = []
    for c in collections:
        detail = (_dcdb_http(inst, "GET", f"/collections/{c['name']}").get("result") or {})
        objects.append({"name": c["name"], "rows": detail.get("points_count"),
                        "size": None, "kind_label": detail.get("status", "")})
    return {"databases": [], "objects": objects, "rows_label": "向量点"}


def _dcdb_qdrant_rows(inst, _db, obj, page, size):
    name = _dcdb_ident(obj, "集合名")
    result = _dcdb_http(inst, "POST", f"/collections/{name}/points/scroll",
                        {"limit": int(size), "with_payload": True, "with_vector": False}).get("result") or {}
    docs = [{"id": p.get("id"), **{f"payload.{k}": _dcdb_safe(v) for k, v in (p.get("payload") or {}).items()}}
            for p in result.get("points") or []]
    columns = sorted({k for d in docs for k in d}) or ["id"]
    return _dcdb_rows_payload(columns, docs, total=None,
                              note="向量点仅展示 payload，向量值不传输" if docs else "")


def _dcdb_neo4j_run(inst, statements):
    body = {"statements": [{"statement": s, "parameters": p or {}} for s, p in statements]}
    result = _dcdb_http(inst, "POST", "/db/neo4j/tx/commit", body)
    if result.get("errors"):
        raise RuntimeError("Neo4j: " + str(result["errors"][0].get("message", ""))[:300])
    return result.get("results") or []


def _dcdb_neo4j_objects(inst, _db):
    labels = [r["row"][0] for r in _dcdb_neo4j_run(inst, [("CALL db.labels()", None)])[0]["data"]]
    objects = []
    for label in labels[:80]:
        if "`" in label:
            continue
        count = _dcdb_neo4j_run(inst, [(f"MATCH (n:`{label}`) RETURN count(n)", None)])[0]["data"][0]["row"][0]
        objects.append({"name": label, "rows": count, "size": None, "kind_label": "节点标签"})
    rels = _dcdb_neo4j_run(inst, [("MATCH ()-[r]->() RETURN type(r), count(*) ORDER BY 1", None)])[0]["data"]
    for row in rels:
        objects.append({"name": row["row"][0], "rows": row["row"][1], "size": None, "kind_label": "关系类型"})
    return {"databases": [], "objects": objects, "rows_label": "数量"}


def _dcdb_neo4j_rows(inst, _db, obj, page, size, kind_label=""):
    if "`" in str(obj):
        raise ValueError("标签名非法")
    data = _dcdb_neo4j_run(inst, [
        (f"MATCH (n:`{obj}`) RETURN n SKIP $skip LIMIT $limit",
         {"skip": int(page) * int(size), "limit": int(size)})])[0]["data"]
    docs = [d["row"][0] if isinstance(d["row"][0], dict) else {"value": d["row"][0]} for d in data]
    if not docs:
        data = _dcdb_neo4j_run(inst, [
            (f"MATCH (a)-[r:`{obj}`]->(b) RETURN a, type(r), b SKIP $skip LIMIT $limit",
             {"skip": int(page) * int(size), "limit": int(size)})])[0]["data"]
        docs = [{"起点": d["row"][0], "关系": d["row"][1], "终点": d["row"][2]} for d in data]
    columns = sorted({k for d in docs for k in d}) or ["value"]
    return _dcdb_rows_payload(columns, docs, total=None)


# ---------- 汇总入口 ----------

def _dcdb_probe_host(inst):
    if inst["kind"] == "sqlite":
        return (BASE_DIR / inst["path"]).exists()
    if inst["kind"] == "mysql":
        try:
            _dcdb_mysql_run(inst, None, [("SELECT 1", None)])
            return True
        except Exception:
            return False
    if inst.get("url"):
        part = urllib.parse.urlparse(inst["url"])
        host, port = part.hostname, part.port or (443 if part.scheme == "https" else 80)
    else:
        host, port = inst["host"], int(inst["port"])
    try:
        with socket.create_connection((host, port), timeout=1.2):
            return True
    except OSError:
        return False


def _dcdb_brief(inst):
    """每个实例的轻量摘要（版本 / 规模），失败不影响清单。"""
    kind = inst["kind"]
    if kind == "sqlite":
        path = BASE_DIR / inst["path"]
        return {"version": "SQLite", "detail": f"{path.stat().st_size / 1048576:.1f} MB"}
    if kind == "postgres":
        conn = _dcdb_pg_connect(inst)
        try:
            version = conn.run("SHOW server_version")[0][0]
            size = conn.run("SELECT pg_size_pretty(pg_database_size(current_database()))")[0][0]
            return {"version": "PostgreSQL " + version, "detail": size}
        finally:
            conn.close()
    if kind == "mysql":
        (rows, _), = _dcdb_mysql_run(inst, None, [("SELECT version() AS v", None)])
        return {"version": "MySQL " + rows[0]["v"], "detail": ""}
    if kind == "mongodb":
        client = _dcdb_mongo_client(inst)
        try:
            info = client.server_info()
            return {"version": "MongoDB " + info.get("version", ""), "detail": f"{len(client.list_database_names())} 库"}
        finally:
            client.close()
    if kind == "redis":
        client = _DcdbRedis(inst)
        try:
            info = dict(line.partition(":")[::2] for line in (client.cmd("INFO", "server") or "").splitlines()
                        if ":" in line and not line.startswith("#"))
            return {"version": "Redis " + info.get("redis_version", ""), "detail": f"{client.cmd('DBSIZE')} 键"}
        finally:
            client.close()
    if kind == "elasticsearch":
        info = _dcdb_http(inst, "GET", "/")
        return {"version": "Elasticsearch " + (info.get("version") or {}).get("number", ""), "detail": ""}
    if kind == "qdrant":
        collections = (_dcdb_http(inst, "GET", "/collections").get("result") or {}).get("collections") or []
        return {"version": "Qdrant", "detail": f"{len(collections)} 集合"}
    if kind == "neo4j":
        info = _dcdb_http(inst, "GET", "/")
        return {"version": "Neo4j " + str(info.get("neo4j_version", "")), "detail": ""}
    if kind == "minio":
        import urllib.request as _rq
        with _rq.urlopen(f"http://{inst['host']}:{inst['port']}/minio/health/live", timeout=5) as resp:
            healthy = resp.status == 200
        return {"version": "MinIO", "detail": "健康检查通过" if healthy else "健康检查失败"}
    return {"version": "", "detail": ""}


def dcdb_instances():
    instances = list(_dcdb_registry().values())
    def enrich(inst):
        item = {k: inst.get(k) for k in ("id", "kind", "label", "system", "level", "note", "category")}
        item["location"] = inst.get("url") or (f"{inst.get('host')}:{inst.get('port')}" if inst.get("host")
                                               else inst.get("path", ""))
        up = _dcdb_probe_host(inst)
        item["status"] = "up" if up else "down"
        if up:
            try:
                item.update(_dcdb_brief(inst))
            except Exception as exc:
                item["status"] = "auth-error"
                item["detail"] = f"{type(exc).__name__}"
        item["queryable"] = inst["kind"] in DCDB_KINDS_SQL
        return item
    with _DcdbPool(max_workers=8) as pool:
        items = list(pool.map(enrich, instances))
    return {"ok": True, "instances": items}


_DCDB_OBJECTS = {"postgres": _dcdb_pg_objects, "mysql": _dcdb_mysql_objects, "sqlite": _dcdb_sqlite_objects,
                 "mongodb": _dcdb_mongo_objects, "elasticsearch": _dcdb_es_objects,
                 "qdrant": _dcdb_qdrant_objects, "neo4j": _dcdb_neo4j_objects}
_DCDB_ROWS = {"postgres": _dcdb_pg_rows, "mysql": _dcdb_mysql_rows, "sqlite": _dcdb_sqlite_rows,
              "elasticsearch": _dcdb_es_rows, "qdrant": _dcdb_qdrant_rows, "neo4j": _dcdb_neo4j_rows}


def dcdb_objects(instance_id, db, username, pattern="*"):
    inst = _dcdb_inst(instance_id)
    dc_audit(username, "db-objects", f"{inst['id']}/{db or ''}", inst["kind"])
    if inst["kind"] == "redis":
        return {"ok": True, **_dcdb_redis_objects(inst, db, pattern)}
    handler = _DCDB_OBJECTS.get(inst["kind"])
    if not handler:
        raise ValueError("该实例类型不支持对象浏览")
    return {"ok": True, **handler(inst, db or None)}


def dcdb_rows(instance_id, db, obj, page, size, username, filter_text=""):
    inst = _dcdb_inst(instance_id)
    page = max(int(page or 0), 0)
    size = min(max(int(size or DCDB_PAGE_SIZE), 1), DCDB_ROW_LIMIT)
    if not str(obj or "").strip():
        raise ValueError("缺少对象名")
    dc_audit(username, "db-rows", f"{inst['id']}/{db or ''}/{obj}", f"page={page}")
    if inst["kind"] == "mongodb":
        return _dcdb_mongo_rows(inst, db, obj, page, size, filter_text)
    if inst["kind"] == "redis":
        return _dcdb_redis_rows(inst, db, obj, page, size)
    handler = _DCDB_ROWS.get(inst["kind"])
    if not handler:
        raise ValueError("该实例类型不支持数据浏览")
    return handler(inst, db, str(obj), page, size)


def dcdb_query(instance_id, db, sql, username):
    inst = _dcdb_inst(instance_id)
    if inst["kind"] not in DCDB_KINDS_SQL:
        raise ValueError("SQL 查询仅支持 PostgreSQL / MySQL / SQLite 实例")
    sql = str(sql or "").strip().rstrip(";").strip()
    if not sql:
        raise ValueError("请输入 SQL")
    if ";" in sql:
        raise ValueError("仅支持单条语句")
    if not DCDB_SQL_ALLOWED.match(sql):
        raise ValueError("仅支持只读查询（SELECT / WITH / SHOW / EXPLAIN / DESCRIBE）")
    dc_audit(username, "db-query", f"{inst['id']}/{db or ''}", sql[:500])
    started = time.time()
    handler = {"postgres": _dcdb_pg_query, "mysql": _dcdb_mysql_query, "sqlite": _dcdb_sqlite_query}[inst["kind"]]
    result = handler(inst, db, sql)
    result["duration_ms"] = round((time.time() - started) * 1000, 1)
    return result
