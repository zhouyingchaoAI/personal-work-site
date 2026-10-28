"""数据中台共用库：数据资产分级扫描与元数据文件读写。

仅依赖标准库，可被 runtime 模块（backend/data_center.py）和独立备份守护进程
（scripts/datacenter_backup.py）同时导入。所有写入都走"临时文件 + 原子替换"。
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

# 数据分级：A 核心业务（每日备份+归档）、B 用户文件（每日增量）、C 可重建（不备份）、D 缓存（不备份）。
LEVELS = {"A": "核心业务数据", "B": "用户文件", "C": "可重建数据", "D": "缓存"}

# 每用户目录下的子目录 → (模块名, 级别)
USER_DIR_MAP = {
    "crm": ("联指经营助手", "A"),
    "diary": ("工作日记", "A"),
    "profile": ("用户资料", "A"),
    "contract_documents": ("合同单据", "A"),
    "meetings": ("会议记录", "A"),
    "reports": ("周报与出差报告", "B"),
    "reimbursement": ("报销材料", "B"),
    "pdf_markdown": ("PDF 转 Markdown", "B"),
    "writing": ("智能写作素材", "B"),
    "drafts": ("草稿", "B"),
    "generated": ("生成文件", "B"),
    "cashflow_exports": ("资金测算导出", "B"),
    "knowledge": ("知识库文件", "B"),
    "news": ("资讯缓存", "D"),
    "mail_cache": ("邮件缓存", "D"),
}
# 每用户目录下的单文件 → (模块名, 级别)
USER_FILE_MAP = {
    "operating_ledger.json": ("项目管理台账", "A"),
    "cashflow_history.json": ("资金测算", "A"),
    "cashflow_scenarios.json": ("资金测算", "A"),
    "cashflow_workbook_state.json": ("资金测算", "A"),
}
# user_data 顶层共享条目 → (模块名, 级别)
SHARED_MAP = {
    "projects": ("项目资料", "B"),
    "knowledge": ("知识库文件", "A"),
    ".auth": ("平台登录会话（SQLite）", "A"),
    ".crm-region-settings.json": ("联指经营助手", "A"),
    ".crm-quality-settings.json": ("联指经营助手", "A"),
    ".crm-amap-settings.json": ("联指经营助手", "A"),
    "app.db": ("智能体记录（SQLite）", "A"),
    "_forum": ("金点子论坛", "A"),
    "_tickets": ("平台工单", "A"),
    ".crm-security": ("操作留痕与安全策略", "A"),
    ".crm-import-completion": ("联指经营助手", "A"),
    "_crm_business_analysis.json": ("经营分析数据", "A"),
    "_crm_staff_directory.json": ("员工目录", "A"),
    "_datacenter": ("数据中台元数据", "A"),
    "_cashflow": ("资金测算模板", "B"),
    "kb_migration_backup": ("历史归档", "B"),
    "_news": ("资讯缓存", "D"),
    "_mcp_mail_attachment_links": ("邮件附件链接", "D"),
    "wechat-article-exporter": ("公众号导出缓存", "D"),
}
# 备份时排除的内容（缓存与可重建，避免备份被 2GB 邮件缓存撑大）。
BACKUP_EXCLUDE_USER_DIRS = {"mail_cache"}
BACKUP_EXCLUDE_SHARED = {"wechat-article-exporter", "_news", "_mcp_mail_attachment_links"}


def datacenter_dir(user_data_dir):
    return Path(user_data_dir) / "_datacenter"


def write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    temp.replace(path)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _tree_stats(root):
    files = 0
    size = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                size += os.lstat(os.path.join(dirpath, name)).st_size
                files += 1
            except OSError:
                continue
    return files, size


def classify_shared(name):
    if name in SHARED_MAP:
        return SHARED_MAP[name]
    if name.startswith((".", "_")) or "backup" in name.lower() or ".bak" in name.lower():
        return ("其他共享数据", "B")
    return None  # 认为是用户目录


def scan_user_data(user_data_dir, extra_files=()):
    """遍历 user_data，按（模块, 级别）聚合大小与文件数。extra_files 追加统计 config.json 等。"""
    start = time.time()
    root = Path(user_data_dir)
    agg = {}
    users = {}

    def add(module, level, files, size, user=None):
        key = (module, level)
        entry = agg.setdefault(key, {"module": module, "level": level, "files": 0, "bytes": 0})
        entry["files"] += files
        entry["bytes"] += size
        if user:
            u = users.setdefault(user, {"user": user, "files": 0, "bytes": 0})
            u["files"] += files
            u["bytes"] += size

    for entry in sorted(root.iterdir() if root.exists() else []):
        name = entry.name
        shared = classify_shared(name)
        if entry.is_file():
            module, level = shared or ("其他共享数据", "B")
            try:
                add(module, level, 1, entry.lstat().st_size)
            except OSError:
                pass
            continue
        if shared:
            files, size = _tree_stats(entry)
            add(shared[0], shared[1], files, size)
            continue
        # 用户目录
        for child in sorted(entry.iterdir()):
            if child.is_file():
                module, level = USER_FILE_MAP.get(child.name, ("其他用户数据", "B"))
                try:
                    add(module, level, 1, child.lstat().st_size, user=name)
                except OSError:
                    pass
            else:
                module, level = USER_DIR_MAP.get(child.name, ("其他用户数据", "B"))
                files, size = _tree_stats(child)
                add(module, level, files, size, user=name)

    for label, level, path in extra_files:
        try:
            add(label, level, 1, Path(path).lstat().st_size)
        except OSError:
            pass

    modules = sorted(agg.values(), key=lambda x: -x["bytes"])
    levels = {k: {"name": v, "files": 0, "bytes": 0, "modules": 0} for k, v in LEVELS.items()}
    for item in modules:
        bucket = levels[item["level"]]
        bucket["files"] += item["files"]
        bucket["bytes"] += item["bytes"]
        bucket["modules"] += 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(time.time() - start, 2),
        "total_files": sum(m["files"] for m in modules),
        "total_bytes": sum(m["bytes"] for m in modules),
        "levels": levels,
        "modules": modules,
        "users_top": sorted(users.values(), key=lambda x: -x["bytes"])[:12],
        "user_count": len(users),
    }


def save_scan_snapshot(user_data_dir, scan, extra_history=None):
    """写 scan.json，并维护逐日容量历史（用于增长趋势）。"""
    path = datacenter_dir(user_data_dir) / "scan.json"
    previous = read_json(path, {})
    history = previous.get("history") or []
    today = scan["generated_at"][:10]
    point = {"date": today,
             "total_bytes": scan["total_bytes"],
             **{lv: scan["levels"][lv]["bytes"] for lv in LEVELS}}
    if extra_history:
        point.update(extra_history)
    if history and history[-1].get("date") == today:
        history[-1] = point
    else:
        history.append(point)
    scan = dict(scan, history=history[-120:])
    write_json_atomic(path, scan)
    return scan


def sqlite_consistent_snapshot(source, destination):
    """Snapshot a read-only mount, including WAL commits, without creating source SHM.

    Copy a stable DB/sidecar set into a private writable directory, then use the
    SQLite backup API. A changing source is retried instead of ignoring its WAL.
    """
    import shutil
    import sqlite3
    import tempfile
    source, destination = Path(source), Path(destination)
    paths = [source, Path(str(source)+'-wal'), Path(str(source)+'-journal')]
    def signature():
        result=[]
        for path in paths:
            try:
                info=path.stat()
                result.append((info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns))
            except FileNotFoundError:result.append(None)
        return result
    for _ in range(3):
        with tempfile.TemporaryDirectory(prefix='dc-sqlite-source-') as tmp:
            before=signature()
            if before[0] is None:raise FileNotFoundError(source)
            copied=Path(tmp)/'source.db'
            try:
                for index,path in enumerate(paths):
                    if before[index] is not None:
                        suffix='' if index==0 else '-wal' if index==1 else '-journal'
                        shutil.copyfile(path,Path(str(copied)+suffix))
            except FileNotFoundError:
                continue
            if before!=signature():continue
            with sqlite3.connect(copied) as src, sqlite3.connect(destination) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('SQLite snapshot integrity check failed')
            return destination
    raise RuntimeError('SQLite source changed during all snapshot attempts; retry later')
