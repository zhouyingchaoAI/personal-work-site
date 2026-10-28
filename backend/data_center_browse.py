"""数据中台第二批：原始数据浏览（只读、脱敏、留痕）与数据看板。

安全约束：
- 全部接口在 server.py 层要求超级管理员；本模块不提供任何写业务数据的能力。
- 路径一律解析后限定在 user_data 内，另外仅放行 config.json（只允许脱敏预览，禁止下载）。
- 密码、密钥类字段值统一脱敏；每次预览 / 下载写入 _datacenter/access_log.jsonl。
"""
import json
import re
import sqlite3
import threading
from pathlib import Path

from backend.datacenter_lib import LEVELS, USER_DIR_MAP, USER_FILE_MAP, classify_shared, datacenter_dir, read_json

DC_SENSITIVE_KEY = re.compile(r"password|passwd|pwd|secret|token|api_?key|private_key|access_key|credential|security_code", re.I)
DC_MASK = "••• 已脱敏"
DC_PREVIEW_MAX_BYTES = 24 * 1024 * 1024
DC_LIST_LIMIT = 400
_dc_access_lock = threading.Lock()


def _dc_root():
    return Path(USER_DATA_DIR).resolve()


def dc_resolve(rel):
    """把请求路径限定在 user_data 内；'config.json' 特殊放行（仅预览）。"""
    rel = str(rel or "").strip().lstrip("/")
    if rel == "config.json":
        return Path(CONFIG_PATH).resolve(), True
    root = _dc_root()
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise PermissionError("路径越界")
    return target, False


def dc_mask(value, key=""):
    if isinstance(value, dict):
        return {k: (DC_MASK if DC_SENSITIVE_KEY.search(str(k)) and isinstance(v, (str, int, float)) and v not in ("", None)
                    else dc_mask(v, k)) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 200:
            return [dc_mask(v, key) for v in value[:200]] + [f"……共 {len(value)} 项，仅显示前 200 项"]
        return [dc_mask(v, key) for v in value]
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000] + f"……（共 {len(value)} 字符）"
    return value


def dc_audit(username, action, path, detail=""):
    entry = {"at": datetime.now().isoformat(timespec="seconds"), "user": username,
             "action": action, "path": str(path), "detail": detail}
    try:
        if office_event_append("datacenter", "access_log", entry, owner=str(username or "")):
            return
    except Exception:
        pass  # 数据库暂不可用时留痕落回文件，不阻断浏览
    log_path = datacenter_dir(USER_DATA_DIR) / "access_log.jsonl"
    with _dc_access_lock:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _dc_entry(path, rel, module="", level=""):
    stat = path.stat()
    return {"name": path.name, "path": rel, "dir": path.is_dir(),
            "size": stat.st_size if path.is_file() else None,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "module": module, "level": level}


def datacenter_browse(rel, subject=""):
    """目录清单。根目录分“共享数据 / 用户目录”两组并标注模块与级别。"""
    target, is_config = dc_resolve(rel)
    if is_config:
        raise ValueError("config.json 请直接预览")
    if not target.exists():
        raise ValueError("路径不存在")
    if target.is_file():
        raise ValueError("这是文件，请用预览接口")
    root = _dc_root()
    entries = []
    truncated = False
    owner_roots = dc_owner_file_roots(root, subject) if subject and subject != "all" else None
    children = sorted((child for child in target.iterdir()
                       if owner_roots is None or any(child == owned or child in owned.parents or owned in child.parents for owned in owner_roots)),
                      key=lambda p: (p.is_file(), p.name))
    for child in children[:DC_LIST_LIMIT]:
        crel = str(child.relative_to(root))
        module = level = ""
        if target == root:
            shared = classify_shared(child.name)
            if shared:
                module, level = shared
            else:
                module, level = ("用户目录", "") if child.is_dir() else ("其他共享数据", "B")
        else:
            parts = child.relative_to(root).parts
            if len(parts) == 2 and not classify_shared(parts[0]):
                mapping = USER_DIR_MAP.get(child.name) if child.is_dir() else USER_FILE_MAP.get(child.name)
                if mapping:
                    module, level = mapping
        try:
            entries.append(_dc_entry(child, crel, module, level))
        except OSError:
            continue
    truncated = len(children) > DC_LIST_LIMIT
    extra = []
    if target == root and dc_owner_path_matches(subject, "config.json"):
        extra = [{"name": "config.json", "path": "config.json", "dir": False,
                  "size": Path(CONFIG_PATH).stat().st_size,
                  "mtime": datetime.fromtimestamp(Path(CONFIG_PATH).stat().st_mtime).isoformat(timespec="seconds"),
                  "module": "账号与平台配置（仅脱敏预览）", "level": "A"}]
    return {"ok": True, "path": rel or "", "entries": extra + entries, "truncated": truncated,
            "level_names": LEVELS}


def _dc_forbid_secret_file(target):
    if DC_SENSITIVE_KEY.search(target.name) or target.name == ".env":
        raise PermissionError("密钥文件不提供查看和下载")


def datacenter_preview(rel, username, table="", offset=0):
    target, is_config = dc_resolve(rel)
    if not is_config:
        _dc_forbid_secret_file(target)
    if not target.exists() or not target.is_file():
        raise ValueError("文件不存在")
    size = target.stat().st_size
    meta = {"path": rel, "size": size,
            "mtime": datetime.fromtimestamp(target.stat().st_mtime).isoformat(timespec="seconds")}
    dc_audit(username, "preview", rel, table)
    suffix = target.suffix.lower()
    if suffix == ".db":
        return {"ok": True, "kind": "sqlite", **meta, **_dc_sqlite(target, table, offset)}
    if size > DC_PREVIEW_MAX_BYTES:
        return {"ok": True, "kind": "binary", **meta, "note": "文件过大，仅提供下载"}
    if suffix in (".json", ".bak") or is_config or ".json" in target.name:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": True, "kind": "binary", **meta, "note": "不是有效的 JSON 文件"}
        summary = {"type": "array", "items": len(data)} if isinstance(data, list) else \
                  {"type": "object", "keys": len(data)} if isinstance(data, dict) else {"type": type(data).__name__}
        return {"ok": True, "kind": "json", **meta, "summary": summary, "data": dc_mask(data),
                "downloadable": not is_config}
    if suffix == ".jsonl":
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        rows = []
        for line in lines[-200:]:
            try:
                rows.append(dc_mask(json.loads(line)))
            except json.JSONDecodeError:
                rows.append(line[:500])
        return {"ok": True, "kind": "jsonl", **meta, "total_lines": len(lines), "rows": rows}
    if suffix in (".md", ".txt", ".log", ".csv", ".yaml", ".yml", ".py", ".html"):
        text = target.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "kind": "text", **meta, "text": text[:60000],
                "truncated": len(text) > 60000}
    return {"ok": True, "kind": "binary", **meta,
            "note": "二进制文件（可下载后用对应软件打开）"}


def _dc_sqlite(path, table, offset):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = []
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            try:
                count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            except sqlite3.DatabaseError:
                count = None
            tables.append({"name": name, "rows": count})
        result = {"tables": tables}
        if table:
            if not re.fullmatch(r"[A-Za-z0-9_]+", table) or table not in {t["name"] for t in tables}:
                raise ValueError("表不存在")
            offset = max(0, int(offset or 0))
            rows = conn.execute(f'SELECT * FROM "{table}" LIMIT 50 OFFSET ?', (offset,)).fetchall()
            result["table"] = table
            result["offset"] = offset
            result["columns"] = [d[0] for d in conn.execute(f'SELECT * FROM "{table}" LIMIT 0').description or []] \
                or (list(rows[0].keys()) if rows else [])
            result["rows"] = [[dc_mask(row[c], c) if isinstance(row[c], (str, int, float)) or row[c] is None else str(row[c])[:500]
                               for c in row.keys()] for row in rows]
            if rows:
                result["columns"] = list(rows[0].keys())
        return result


def datacenter_download(rel, username):
    target, is_config = dc_resolve(rel)
    if is_config:
        raise PermissionError("config.json 含密钥，只允许脱敏预览")
    _dc_forbid_secret_file(target)
    if not target.exists() or not target.is_file():
        raise ValueError("文件不存在")
    dc_audit(username, "download", rel, f"{target.stat().st_size}B")
    return target


def datacenter_access_log():
    if officedb_enabled("datacenter"):
        rows = [{k: v for k, v in row.items() if k != "seq"} for row in office_event_recent("datacenter", "access_log", limit=200)]
        return {"ok": True, "rows": rows}
    path = datacenter_dir(USER_DATA_DIR) / "access_log.jsonl"
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {"ok": True, "rows": rows[::-1]}


# ==================== 数据看板 ====================
_dc_dash_cache = {"data": None, "at": 0.0}


def _dc_count_json(path, key=None):
    data = read_json(path, None)
    if data is None:
        return 0
    if key is not None and isinstance(data, dict):
        data = data.get(key) or []
    return len(data) if isinstance(data, (list, dict)) else 0


def datacenter_dashboard(force=False):
    import time as _time
    now = _time.time()
    if not force and _dc_dash_cache["data"] and now - _dc_dash_cache["at"] < 600:
        return _dc_dash_cache["data"]
    root = _dc_root()
    crm = {"units": 0, "people": 0, "relations": 0, "actions": 0, "opportunities": 0}
    cashflow_records = ledger_items = 0
    ext_counter = {}
    user_dirs = []
    for entry in root.iterdir():
        if entry.is_dir() and not classify_shared(entry.name):
            user_dirs.append(entry)
    for u in user_dirs:
        if not crmdb_enabled():
            for name in crm:
                crm[name] += _dc_count_json(u / "crm" / f"{name}.json")
        cashflow_records += _dc_count_json(u / "cashflow_history.json", "records")
        ledger_items += _dc_count_json(u / "operating_ledger.json")
    if crmdb_enabled():
        with _crmdb_conn() as conn:
            for name in crm:
                crm[name] = conn.run(f'SELECT count(*) FROM crm.{name}')[0][0]
    agent = {"agent_sessions": 0, "agent_messages": 0, "skill_invocations": 0}
    db = root / "app.db"
    if db.exists():
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                for t in agent:
                    agent[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.DatabaseError:
            pass
    tickets = _dc_count_json(root / "_tickets" / "tickets.json", "tickets") or _dc_count_json(root / "_tickets" / "tickets.json")
    topics = _dc_count_json(root / "_forum" / "topics.json", "topics") or _dc_count_json(root / "_forum" / "topics.json")
    users = len((read_config() or {}).get("users", []))
    # 文件类型分布（复用扫描；这里独立轻量统计后缀）
    for p in root.rglob("*"):
        if p.is_file():
            ext = p.suffix.lower().lstrip(".")[:12] or "无后缀"
            ext_counter[ext] = ext_counter.get(ext, 0) + 1
    exts = sorted(ext_counter.items(), key=lambda kv: -kv[1])
    scan = read_json(datacenter_dir(USER_DATA_DIR) / "scan.json", {})
    runs = read_json(datacenter_dir(USER_DATA_DIR) / "backups.json", [])
    recent = runs[-30:]
    data = {
        "ok": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "records": {
            "平台账号": users,
            "客户单位": crm["units"], "客户联系人": crm["people"], "客户关系": crm["relations"],
            "跟进动作": crm["actions"], "商机": crm["opportunities"],
            "历史回款节点": cashflow_records, "台账项目": ledger_items,
            "工单": tickets, "论坛主题": topics,
            "智能体会话": agent["agent_sessions"], "智能体消息": agent["agent_messages"],
            "技能调用": agent["skill_invocations"],
        },
        "records_note": "按当前业务主存储统计，含管理员为同事复制的数据副本；共享 SQLite 指标属于平台，不按助手重复分摊",
        "history": (scan.get("history") or [])[-60:],
        "levels": scan.get("levels") or {},
        "top_modules": (scan.get("modules") or [])[:10],
        "extensions": [{"ext": k, "count": v} for k, v in exts[:10]],
        "extensions_other": sum(v for _, v in exts[10:]),
        "backup": {
            "total": len(recent),
            "ok": sum(1 for r in recent if r.get("ok")),
            "recent": [{"id": r.get("id"), "ok": bool(r.get("ok")), "bytes": r.get("bytes") or 0,
                        "finished_at": r.get("finished_at", "")} for r in recent],
        },
    }
    _dc_dash_cache["data"], _dc_dash_cache["at"] = data, now
    return data
