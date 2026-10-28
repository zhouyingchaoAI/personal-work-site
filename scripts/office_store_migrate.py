#!/usr/bin/env python3
"""把某个助手的本地文件迁入 office-postgres（宿主机运行）。

流程：导入（按原路径写 app.documents / app.blobs）→ 逐文件核对 → 翻开关
（office_db.json modules.<助手>=true，运行中的服务按 mtime 即时感知）→ 再核对一次，
补写切换窗口内的改动。原文件保留不动，作为切换前快照。

用法：python3 scripts/office_store_migrate.py ledger [cashflow ...] [--switch] [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "user_data" / "_datacenter" / "office_db.json"
sys.path.insert(0, str(ROOT / "vendor" / "pgdeps"))


def container_ip():
    out = subprocess.run(["docker", "inspect", "office-postgres", "--format",
                          "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"],
                         capture_output=True, text=True, check=True).stdout
    return out.split()[0]


def load_store(force_modules):
    ns = {"USER_DATA_DIR": ROOT / "user_data", "__file__": str(ROOT / "app.py")}
    exec(compile((ROOT / "backend" / "office_store.py").read_text(encoding="utf-8"), "office_store.py", "exec"), ns)
    base = json.loads(CONFIG.read_text(encoding="utf-8"))
    config = {**base, "host": container_ip(), "modules": {name: True for name in force_modules}}
    ns["officedb_config"] = lambda: config
    return ns


def jsonl_events(ns, module, stream, path):
    count = 0
    if not path.exists():
        return 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        ns["office_event_append"](module, stream, payload, owner=str(payload.get("user") or payload.get("actor") or ""))
        count += 1
    return count


def _split_cache(ns, module):
    """布局里的 cache 谓词：命中的文件进 cache 表（可重建缓存），其余进业务表。"""
    predicate = (ns["OFFICE_STORE_LAYOUT"].get(module) or {}).get("cache")
    return predicate or (lambda path: False)


def migrate(ns, module, dry_run, skip_events=False):
    layout = ns["office_store_layout_paths"](module)
    is_cache = _split_cache(ns, module)
    totals = {"documents": 0, "blobs": 0, "events": 0, "skipped": [], "bytes": 0, "roots": len(layout),
              "cache_files": 0}
    for path, is_dir in layout:
        if path.suffix == ".jsonl":
            # 追加型日志只导入一次：切换后的补写不再重复导入。
            if not dry_run and not skip_events:
                totals["events"] += jsonl_events(ns, module, path.stem, path)
            continue
        root = path if is_dir else path.parent
        for cache in (False, True):
            def skip(p, target=path, want_cache=cache, single=not is_dir):
                if single and p != target:
                    return True
                return bool(is_cache(p)) != want_cache
            summary = ns["office_store_import_tree"](module, root, dry_run=dry_run, skip=skip, cache=cache)
            for key in ("documents", "blobs", "bytes"):
                totals[key] += summary[key]
            if cache:
                totals["cache_files"] += summary["documents"] + summary["blobs"]
            if is_dir and not cache:
                totals["skipped"] += [item for item in summary["skipped"] if not is_cache(Path(item))]
    return totals


def verify(ns, module):
    """业务文件必须逐项一致；可重建缓存（cache 谓词命中）在校验窗口内可能被在线服务刷新，
    不一致的缓存文件重新导入一次后按“已刷新”计，不阻断切换。"""
    result = {"checked": 0, "mismatch": [], "cache_refreshed": 0}
    is_cache = _split_cache(ns, module)
    for path, is_dir in ns["office_store_layout_paths"](module):
        if path.suffix == ".jsonl":
            continue
        root = path if is_dir else path.parent
        for cache in (False, True):
            def skip(p, target=path, want_cache=cache, single=not is_dir):
                if single and p != target:
                    return True
                return bool(is_cache(p)) != want_cache
            part = ns["office_store_verify_tree"](module, root, skip=skip, cache=cache)
            result["checked"] += part["checked"]
            if cache and part["mismatch"]:
                for item in part["mismatch"]:
                    target = Path(item)
                    ns["office_store_import_tree"](module, target.parent, skip=lambda p, t=target: p != t, cache=True)
                result["cache_refreshed"] += len(part["mismatch"])
            else:
                result["mismatch"] += part["mismatch"]
    return result


def switch_on(module):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config.setdefault("modules", {})[module] = True
    temporary = CONFIG.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(CONFIG)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("modules", nargs="+")
    parser.add_argument("--switch", action="store_true", help="核对通过后翻开关")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ns = load_store(list(args.modules) + ["datacenter"])
    for module in args.modules:
        if module not in ns["OFFICE_STORE_LAYOUT"]:
            raise SystemExit(f"未知助手：{module}")
        started = datetime.now().isoformat(timespec="seconds")
        totals = migrate(ns, module, args.dry_run)
        print(f"[{module}] 导入：{totals}")
        if args.dry_run:
            continue
        check = verify(ns, module)
        print(f"[{module}] 核对：{check['checked']} 项，不一致 {len(check['mismatch'])}，缓存已刷新 {check['cache_refreshed']}")
        if check["mismatch"]:
            for item in check["mismatch"][:20]:
                print("   ", item)
            raise SystemExit(f"[{module}] 核对未通过，未翻开关")
        if args.switch:
            switch_on(module)
            again = migrate(ns, module, False, skip_events=True)
            check = verify(ns, module)
            print(f"[{module}] 已开启数据库模式；切换窗口补写后核对 {check['checked']} 项，不一致 {len(check['mismatch'])}，缓存已刷新 {check['cache_refreshed']}")
        counts = ns["office_store_counts"](module)
        ns["office_event_append"]("datacenter", "store_migration", {
            "module": module, "started_at": started, "finished_at": datetime.now().isoformat(timespec="seconds"),
            "imported": {k: totals[k] for k in ("documents", "blobs", "events", "bytes", "cache_files")},
            "skipped": len(totals["skipped"]), "verified": check["checked"], "switched": bool(args.switch),
            "counts": counts})
        print(f"[{module}] 库内现有：{counts}")


if __name__ == "__main__":
    main()
