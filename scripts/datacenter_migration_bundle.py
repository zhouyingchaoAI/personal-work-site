#!/usr/bin/env python3
"""Create one portable, checksummed migration bundle for the whole office stack.

This is deliberately a *host-side* tool: Docker is the authority for the
external products' data.  It makes native, application-consistent exports for
SQL/Mongo services and records the persistent volumes needed by object stores
and caches.  A final cut-over should run with writers paused; this tool never
stops a service on its own.

The output is a new directory below /srv/office-backups/migrations by default.
It never overwrites an existing bundle and never prints credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DESTINATION = Path("/home/chency/zyc/workspace/chency-site/data/backups/migrations")

# Native exports are portable across hosts.  Caches are intentionally not
# exported as authoritative data; their owning services can rebuild them.
EXPORTS = (
    ("office-postgres", "postgres", "office-postgres", "office", "office"),
    ("fastgpt-vector", "postgres", "fastgpt-pg", "fastgpt", "fastgpt"),
    ("fastgpt-aiproxy", "postgres", "fastgpt-aiproxy-pg", "postgres", "aiproxy"),
    ("dify", "postgres", "docker-db-1", "postgres", "dify"),
    ("foundry", "postgres", "foundry-platform-postgres-1", "foundry", "foundry"),
    ("ragflow", "mysql", "ragflow-mysql", "root", "rag_flow"),
    ("fastgpt", "mongo", "fastgpt-mongo", "fastgpt", "fastgpt"),
)

# Object stores hold user-owned files, so retain their volume bytes.  The
# manifest identifies the exact Docker volume; a final migration should pause
# writers before this final snapshot.  Redis/Qdrant/Neo4j are derived/cache or
# service-specific and are reported rather than falsely labelled complete.
VOLUMES = (
    ("fastgpt-minio", "/home/chency/zyc/workspace/chency-site/data/office/fastgpt-minio/data", "object-store"),
    ("ragflow-minio", "/home/chency/zyc/workspace/chency-site/data/ragflow/ragflow-minio/data", "object-store"),
    ("openclaw-minio", "/home/chency/zyc/workspace/chency-site/data/openclaw-platform/minio", "object-store"),
)


def run(*args: str, stdout=None) -> None:
    subprocess.run(args, check=True, stdout=stdout, stderr=subprocess.PIPE)


def docker_container_exists(name: str) -> bool:
    return subprocess.run(["docker", "inspect", name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def docker_volume_exists(name: str) -> bool:
    if Path(name).is_absolute():
        return Path(name).is_dir()
    return subprocess.run(["docker", "volume", "inspect", name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def export_database(kind: str, container: str, user: str, database: str, target: Path) -> None:
    with target.open("wb") as output:
        if kind == "postgres":
            run("docker", "exec", container, "pg_dump", "--format=custom", "--no-owner", "--no-acl",
                "--username", user, "--dbname", database, stdout=output)
        elif kind == "mysql":
            # Password stays in the container environment rather than argv/logs.
            run("docker", "exec", container, "sh", "-lc",
                f'exec mysqldump --single-transaction --routines --events --user={user} --password="$MYSQL_ROOT_PASSWORD" --databases {database}',
                stdout=output)
        elif kind == "mongo":
            run("docker", "exec", container, "sh", "-lc",
                f'exec mongodump --archive --gzip --authenticationDatabase admin --username {user} --password "$MONGO_INITDB_ROOT_PASSWORD" --db {database}',
                stdout=output)
        else:  # pragma: no cover - table above is closed
            raise ValueError(f"unsupported exporter: {kind}")


def export_volume(volume: str, target: Path) -> None:
    # Use an ephemeral read-only mount; no host path or container filesystem is
    # assumed. Alpine is already part of the normal Docker toolchain here.
    with target.open("wb") as output:
        mount_type = "bind" if Path(volume).is_absolute() else "volume"
        run("docker", "run", "--rm", "--mount", f"type={mount_type},src={volume},dst=/source,readonly",
            "alpine:3.20", "tar", "-C", "/source", "-czf", "-", ".", stdout=output)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(destination: Path, dry_run: bool = False) -> dict:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle = destination / f"platform-{stamp}"
    plan = {"created_at": datetime.now().isoformat(timespec="seconds"), "state": "running",
            "format": 1, "exports": [], "volumes": [],
            "cutover_note": "For a final migration, pause writers, run this command again, then validate SHA256SUMS."}
    if dry_run:
        for label, kind, container, _user, database in EXPORTS:
            plan["exports"].append({"system": label, "kind": kind, "container": container,
                                    "database": database, "state": "planned"})
        for label, volume, purpose in VOLUMES:
            plan["volumes"].append({"system": label, "volume": volume, "purpose": purpose, "state": "planned"})
        return plan
    if bundle.exists():
        raise FileExistsError(bundle)
    bundle.mkdir(parents=True, mode=0o700)
    try:
        for label, kind, container, user, database in EXPORTS:
            suffix = {"postgres": "dump", "mysql": "sql", "mongo": "archive.gz"}[kind]
            filename = f"databases/{label}.{suffix}"
            target = bundle / filename
            target.parent.mkdir(exist_ok=True)
            item = {"system": label, "kind": kind, "container": container, "database": database,
                    "file": filename, "state": "missing"}
            if docker_container_exists(container):
                export_database(kind, container, user, database, target)
                item.update(state="complete", bytes=target.stat().st_size, sha256=sha256(target))
            plan["exports"].append(item)
        for label, volume, purpose in VOLUMES:
            filename = f"volumes/{label}.tar.gz"
            target = bundle / filename
            target.parent.mkdir(exist_ok=True)
            item = {"system": label, "volume": volume, "purpose": purpose, "file": filename,
                    "consistency": "crash-consistent; use a paused-writer final run for cut-over", "state": "missing"}
            if docker_volume_exists(volume):
                export_volume(volume, target)
                item.update(state="complete", bytes=target.stat().st_size, sha256=sha256(target))
            plan["volumes"].append(item)
        plan["not_exported"] = [
            {"system": "Redis", "reason": "cache/queue; rebuild or use service-specific export if it contains irreplaceable jobs"},
            {"system": "Qdrant / Neo4j", "reason": "derived indexes/graph; rebuild from authoritative source or add a service-specific export"},
        ]
        plan["state"] = "complete" if all(x["state"] == "complete" for x in plan["exports"] + plan["volumes"]) else "partial"
        (bundle / "manifest.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checksum_lines = []
        for item in plan["exports"] + plan["volumes"]:
            if item["state"] == "complete":
                checksum_lines.append(f"{item['sha256']}  {item['file']}")
        (bundle / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="ascii")
        os.chmod(bundle / "manifest.json", 0o600)
        os.chmod(bundle / "SHA256SUMS", 0o600)
        return {**plan, "path": str(bundle)}
    except Exception as exc:
        plan.update(state="failed", error=type(exc).__name__)
        (bundle / "manifest.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = build(args.destination, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
