"""数据中台助手：数据资产总览、备份中心、存储与服务状态。

只读管理入口（仅超级管理员）：本模块不修改任何业务数据。备份由独立容器
datacenter-backup 执行，双方通过 user_data/_datacenter 下的 JSON 交换状态。
"""
import shutil
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.datacenter_lib import (
    LEVELS, datacenter_dir, read_json, save_scan_snapshot, scan_user_data, write_json_atomic,
)

DATACENTER_SCAN_TTL = 600  # 秒；期间复用上次扫描结果，避免每次请求都遍历 1.4 万个文件。
_datacenter_lock = threading.Lock()
_datacenter_cache = {"scan": None, "at": 0.0, "infra": None, "infra_at": 0.0}

# 平台数据服务清单：(标识, 主机, 端口, 说明, 数据级别)。主机名走 Docker 内网，
# 不在内网网络上的通过 host.docker.internal 探测宿主机端口。
DATACENTER_SERVICES = [
    ("office-postgres", "office-postgres", 5432, "统一业务数据库（新增，迁移目标）", "A"),
    ("datacenter-backup", None, 0, "备份服务（每日 02:30 自动运行）", "A"),
    ("crm-neo4j", "crm-neo4j", 7687, "联指经营助手关系图谱", "C"),
    ("crm-redis", "crm-redis", 6379, "联指经营助手缓存与队列", "D"),
    ("fastgpt-mongo", "fastgpt-mongo", 27017, "工作流中心主库", "A"),
    ("fastgpt-pg", "fastgpt-pg", 5432, "工作流中心向量库", "C"),
    ("fastgpt-minio", "fastgpt-minio", 9000, "工作流中心文件存储", "B"),
    ("fastgpt-redis", "fastgpt-redis", 6379, "工作流中心缓存", "D"),
    ("qdrant", "host.docker.internal", 6333, "知识库向量库", "C"),
    ("ragflow-mysql", "host.docker.internal", 5455, "知识库主库（RAGFlow）", "A"),
    ("ragflow-minio", "host.docker.internal", 19000, "知识库文件存储（RAGFlow）", "B"),
]


def _datacenter_probe(host, port, service_key=None):
    if service_key == "ragflow-mysql":
        try:
            return "up" if _dcdb_probe_host(_dcdb_inst(service_key)) else "down"
        except Exception:
            return "down"
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return "up"
    except OSError:
        return "down"


def _datacenter_infra():
    now = time.time()
    if _datacenter_cache["infra"] and now - _datacenter_cache["infra_at"] < 60:
        return _datacenter_cache["infra"]
    status_path = datacenter_dir(USER_DATA_DIR) / "backup_status.json"
    backup_status = read_json(status_path, {})
    heartbeat = backup_status.get("heartbeat_at") or ""
    try:
        registered = dcdb_instances()["instances"]
    except (ValueError, RuntimeError, OSError):
        registered = []
    if registered:
        results = [{"key": item["id"], "label": item["label"], "level": item["level"],
                    "status": "up" if item["status"] == "up" else "down"} for item in registered]
        results.append({"key": "datacenter-backup", "label": "平台统一备份服务", "level": "A",
                        "status": "up" if _datacenter_recent(heartbeat, 300) else "down"})
        _datacenter_cache["infra"], _datacenter_cache["infra_at"] = results, now
        return results
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for key, host, port, label, level in DATACENTER_SERVICES:
            if host:
                futures[key] = pool.submit(_datacenter_probe, host, port, key)
        for key, host, port, label, level in DATACENTER_SERVICES:
            if host:
                state = futures[key].result()
            else:  # 备份服务按心跳判断（5 分钟内有心跳算在线）
                state = "up" if _datacenter_recent(heartbeat, 300) else "down"
            results.append({"key": key, "label": label, "level": level, "status": state})
    _datacenter_cache["infra"], _datacenter_cache["infra_at"] = results, now
    return results


def _datacenter_recent(iso_text, seconds):
    try:
        return time.time() - datetime.fromisoformat(iso_text).timestamp() < seconds
    except (ValueError, TypeError):
        return False


def _datacenter_scan(force=False):
    now = time.time()
    with _datacenter_lock:
        if not force and _datacenter_cache["scan"] and now - _datacenter_cache["at"] < DATACENTER_SCAN_TTL:
            return _datacenter_cache["scan"]
        disk_snapshot = read_json(datacenter_dir(USER_DATA_DIR) / "scan.json", {})
        if not force and disk_snapshot and _datacenter_recent(disk_snapshot.get("generated_at", ""), DATACENTER_SCAN_TTL):
            scan = disk_snapshot
        else:
            scan = scan_user_data(USER_DATA_DIR, extra_files=[("账号与平台配置（config.json）", "A", CONFIG_PATH)])
            scan = save_scan_snapshot(USER_DATA_DIR, scan)
        _datacenter_cache["scan"], _datacenter_cache["at"] = scan, now
        return scan


def datacenter_overview(force=False):
    scan = _datacenter_scan(force=force)
    usage = shutil.disk_usage(USER_DATA_DIR)
    backup_status = read_json(datacenter_dir(USER_DATA_DIR) / "backup_status.json", {})
    db_sync = read_json(datacenter_dir(USER_DATA_DIR) / "db_sync.json", {})
    return {
        "ok": True,
        "scan": scan,
        "db_sync": db_sync,
        "level_names": LEVELS,
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free,
                 "mount": "业务数据盘（/home）"},
        "backup_disk": backup_status.get("backup_disk") or None,
        "services": _datacenter_infra(),
        "migration": DATACENTER_MIGRATION,
    }


# 迁移路线（展示用，进度手工维护；切换动作不在本助手内执行）。
DATACENTER_MIGRATION = [
    {"step": "统一数据库容器（office-postgres）", "status": "done", "note": "已启动，独立命名卷，仅 Docker 内网可达"},
    {"step": "每日自动备份（核心数据 + 用户文件）", "status": "done", "note": "备份到系统盘 /srv/office-backups，排除邮件缓存"},
    {"step": "全量入库（权限、账号、业务数据、审计、文件索引）", "status": "done", "note": "已登记镜像每日与备份一同同步并对账；不代表所有助手均已切换主存储，具体见各助手存储对应"},
    {"step": "业务模块逐个切换（双写→切换→归档）", "status": "done", "note": "联指经营助手走 crm.* 表；其余 15 个助手与平台资料经统一存储层（app.documents / app.blobs / app.events，开关 _datacenter/office_db.json）切换至 office-postgres，原文件冻结为切换前快照"},
    {"step": "用户文件迁入对象存储", "status": "done", "note": "附件、报告、发票等二进制文件已以 bytea 存入 app.blobs（sha256 校验）；邮件 IMAP 缓存单独放 app.cache_* 并排除在备份之外"},
    {"step": "第二、三份备份副本", "status": "todo", "note": "内网另一台机器 + 异地加密，待确定存放位置"},
]


def datacenter_backups():
    dc = datacenter_dir(USER_DATA_DIR)
    runs = read_json(dc / "backups.json", [])
    status = read_json(dc / "backup_status.json", {})
    trigger = dc / "backup.trigger"
    return {
        "ok": True,
        "runs": runs[-30:][::-1],
        "status": status,
        "pending_trigger": trigger.exists(),
        "copies": [
            {"name": "副本 1 · 本机系统盘", "target": "/srv/office-backups", "state": "enabled",
             "note": "与业务数据不同磁盘，每日 02:30 自动备份，保留最近 14 份"},
            {"name": "副本 2 · 内网另一台机器", "target": "", "state": "todo", "note": "待确定 NAS 或服务器后接入"},
            {"name": "副本 3 · 异地（加密）", "target": "", "state": "todo", "note": "上传前加密，密钥单独保管"},
        ],
    }


def datacenter_trigger_backup(username):
    dc = datacenter_dir(USER_DATA_DIR)
    write_json_atomic(dc / "backup.trigger", {"requested_by": username,
                                              "requested_at": datetime.now().isoformat(timespec="seconds")})
    return {"ok": True, "message": "已发出备份指令，备份服务将在 1 分钟内开始执行"}


def datacenter_trigger_db_sync(username):
    dc = datacenter_dir(USER_DATA_DIR)
    write_json_atomic(dc / "sync.trigger", {"requested_by": username,
                                            "requested_at": datetime.now().isoformat(timespec="seconds")})
    return {"ok": True, "message": "已发出入库同步指令，1 分钟内开始全量同步"}


def datacenter_refresh(username):
    scan = _datacenter_scan(force=True)
    return {"ok": True, "generated_at": scan["generated_at"], "duration_seconds": scan["duration_seconds"]}
