#!/usr/bin/env python3
"""数据中台备份守护进程（datacenter-backup 容器入口）。

职责：
1. 每日 02:30 自动备份，另支持前端“立即备份”触发（_datacenter/backup.trigger）。
2. 备份内容：user_data（排除邮件缓存等 D 级数据）+ config.json + 部署文件快照；
   SQLite（app.db）先做一致性快照再入包。密钥文件（.env）不入包。
3. 每次备份后完整性校验（重读归档比对条目数），结果写 _datacenter/backups.json。
4. 保留最近 KEEP 份，超出的删除；每日刷新一次资产扫描快照。
5. 每 30 秒写心跳，供数据中台页面显示备份服务是否在线。

只读挂载业务数据（除 _datacenter 状态目录外不写 user_data 任何内容）。
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/app")
from backend.datacenter_lib import (  # noqa: E402
    BACKUP_EXCLUDE_SHARED, BACKUP_EXCLUDE_USER_DIRS, classify_shared, datacenter_dir,
    read_json, save_scan_snapshot, scan_user_data, write_json_atomic, sqlite_consistent_snapshot,
)

APP = Path("/app")
USER_DATA = APP / "user_data"
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backup"))
DC = datacenter_dir(USER_DATA)
DAILY_AT = os.getenv("BACKUP_DAILY_AT", "02:30")
KEEP = int(os.getenv("BACKUP_KEEP", "14"))
MIN_FREE_BYTES = 5 * 1024 ** 3
EXTRA_FILES = [("config/config.json", APP / "config.json"),
               ("config/docker-compose.personal.yml", APP / "compose-snapshot.yml")]


def log(*args):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


def iter_backup_paths():
    """生成 (归档内路径, 实际路径)。跳过缓存目录、app.db（单独快照）与临时文件。"""
    for entry in sorted(USER_DATA.iterdir()):
        name = entry.name
        if name in BACKUP_EXCLUDE_SHARED or name in ("app.db", "app.db-wal", "app.db-shm", "app.db-journal") or name.endswith(".tmp"):
            continue
        if entry.is_file():
            yield f"user_data/{name}", entry
            continue
        if classify_shared(name):
            yield f"user_data/{name}", entry
            continue
        for child in sorted(entry.iterdir()):
            if child.name in BACKUP_EXCLUDE_USER_DIRS or child.name.endswith(".tmp"):
                continue
            yield f"user_data/{name}/{child.name}", child


def sqlite_snapshot(tmpdir):
    src = USER_DATA / "app.db"
    if not src.exists():
        return None
    dest = Path(tmpdir) / "app.db"
    sqlite_consistent_snapshot(src, dest)
    return dest


def run_backup(reason):
    started = datetime.now()
    run = {"id": started.strftime("%Y%m%d-%H%M%S"), "reason": reason,
           "started_at": started.isoformat(timespec="seconds"), "ok": False}
    archive = BACKUP_DIR / f"office-{run['id']}.tar.gz"
    log("backup start:", reason)
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(BACKUP_DIR).free
        if free < MIN_FREE_BYTES:
            raise RuntimeError(f"备份盘剩余空间不足（{free / 1024 ** 3:.1f} GB），已跳过本次备份")
        added = 0
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = sqlite_snapshot(tmpdir)
            with tarfile.open(archive, "w:gz", compresslevel=6) as tar:
                for arcname, path in iter_backup_paths():
                    tar.add(path, arcname=arcname)
                if snapshot:
                    tar.add(snapshot, arcname="user_data/app.db")
                for arcname, path in EXTRA_FILES:
                    if path.exists():
                        tar.add(path, arcname=arcname)
                added = len(tar.getnames())
        digest = hashlib.sha256()
        with open(archive, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        with tarfile.open(archive, "r:gz") as tar:  # 完整性校验：能完整重读且条目数一致
            verified = sum(1 for _ in tar)
        if verified != added:
            raise RuntimeError(f"校验失败：写入 {added} 项，读回 {verified} 项")
        run.update(ok=True, entries=added, bytes=archive.stat().st_size, sha256=digest.hexdigest(),
                   archive=archive.name, verified=True)
        prune()
    except Exception as exc:  # noqa: BLE001 —— 备份失败必须记录并继续守护
        run["error"] = str(exc)
        log("backup FAILED:", exc)
        traceback.print_exc()
        if archive.exists():
            archive.unlink(missing_ok=True)
    run["finished_at"] = datetime.now().isoformat(timespec="seconds")
    run["duration_seconds"] = round((datetime.now() - started).total_seconds(), 1)
    runs = read_json(DC / "backups.json", [])
    runs.append(run)
    write_json_atomic(DC / "backups.json", runs[-60:])
    write_status(last_run=run)
    log("backup done:", "ok" if run["ok"] else "failed", run.get("archive", ""),
        f"{run.get('bytes', 0) / 1024 ** 2:.0f} MB", f"{run['duration_seconds']}s")
    return run


def prune():
    archives = sorted(BACKUP_DIR.glob("office-*.tar.gz"))
    for old in archives[:-KEEP]:
        log("prune:", old.name)
        old.unlink(missing_ok=True)


def next_daily(now):
    hour, minute = (int(x) for x in DAILY_AT.split(":"))
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def write_status(last_run=None):
    status = read_json(DC / "backup_status.json", {})
    now = datetime.now()
    if last_run:
        status["last_run"] = {k: last_run.get(k) for k in
                              ("id", "ok", "reason", "finished_at", "bytes", "entries", "duration_seconds", "error", "archive")}
        if last_run.get("ok"):
            status["last_ok_at"] = last_run["finished_at"]
    try:
        usage = shutil.disk_usage(BACKUP_DIR)
        archives = sorted(BACKUP_DIR.glob("office-*.tar.gz"))
        status["backup_disk"] = {"total": usage.total, "free": usage.free, "mount": str(BACKUP_DIR),
                                 "archives": len(archives),
                                 "archives_bytes": sum(a.stat().st_size for a in archives)}
    except OSError:
        pass
    status.update(heartbeat_at=now.isoformat(timespec="seconds"),
                  next_scheduled=next_daily(now).isoformat(timespec="seconds"),
                  daily_at=DAILY_AT, keep=KEEP)
    write_json_atomic(DC / "backup_status.json", status)
    return status


def run_db_sync(reason):
    """全量入库 office-postgres；失败只记录，不影响备份守护。"""
    try:
        from backend.datacenter_db import sync_all
        roots = {"project": Path(os.environ["DATACENTER_PROJECT_ROOT"])} if os.getenv("DATACENTER_PROJECT_ROOT") else None
        status = sync_all(USER_DATA, APP / "config.json", reason=reason, archive_roots=roots, heartbeat=write_status)
        if status.get("busy"):
            log("db sync skipped: another sync is running")
            return
        if status.get("ok") and status.get("file_archive"):
            (DC / "pg_backup.trigger").write_text(status["file_archive"]["id"], encoding="ascii")
        log("db sync:", "ok" if status["ok"] else "MISMATCH", status["rows_total"], "rows,",
            f"{status['duration_seconds']}s", status.get("mismatches") or "")
    except Exception as exc:  # noqa: BLE001
        log("db sync FAILED:", type(exc).__name__, "see db_sync.json; source values omitted")


def refresh_scan():
    scan = scan_user_data(USER_DATA, extra_files=[("账号与平台配置（config.json）", "A", APP / "config.json")])
    save_scan_snapshot(USER_DATA, scan)
    log("scan refreshed:", scan["total_files"], "files,", f"{scan['total_bytes'] / 1024 ** 2:.0f} MB")


def main():
    DC.mkdir(parents=True, exist_ok=True)
    log("datacenter-backup started; daily at", DAILY_AT, "keep", KEEP)
    status = read_json(DC / "backup_status.json", {})
    # 首次部署（或超过 25 小时无成功备份）立即补一次全量。
    last_ok = status.get("last_ok_at", "")
    try:
        overdue = (datetime.now() - datetime.fromisoformat(last_ok)) > timedelta(hours=25)
    except (ValueError, TypeError):
        overdue = True
    if overdue:
        run_backup("startup")
        refresh_scan()
    run_db_sync("startup")
    scheduled = next_daily(datetime.now())
    trigger = DC / "backup.trigger"
    beat = 0.0
    while True:
        now = datetime.now()
        if trigger.exists():
            info = read_json(trigger, {})
            trigger.unlink(missing_ok=True)
            run_backup(f"manual:{info.get('requested_by', '')}")
        sync_trigger = DC / "sync.trigger"
        if sync_trigger.exists():
            info = read_json(sync_trigger, {})
            sync_trigger.unlink(missing_ok=True)
            run_db_sync(f"manual:{info.get('requested_by', '')}")
        if now >= scheduled:
            run_backup("daily")
            refresh_scan()
            run_db_sync("daily")
            scheduled = next_daily(datetime.now())
        if time.time() - beat >= 30:
            write_status()
            beat = time.time()
        time.sleep(5)


if __name__ == "__main__":
    main()
