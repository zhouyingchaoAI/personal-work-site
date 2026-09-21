#!/usr/bin/env python3
"""Create platform accounts from the CRM staff directory without altering access roles."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core import hash_password  # noqa: E402


DEFAULT_PASSWORD = "123456"


def _text(value):
    return str(value or "").strip()


def _username(name, employee_id, claimed, transliterate):
    base = re.sub(r"[^a-z0-9]", "", _text(transliterate(name)).lower())
    if not base:
        base = "staff"
    candidate = base
    if candidate in claimed:
        candidate = f"{base}_{employee_id}"
    suffix = 2
    while candidate in claimed:
        candidate = f"{base}_{employee_id}_{suffix}"
        suffix += 1
    return candidate


def provision(config_path, directory_path, transliterate):
    """Synchronize identity and organization fields; return a change summary.

    Existing accounts are matched by employee ID, then by a unique personnel name.
    Their username, password, role and permissions are deliberately retained.
    """
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    directory = json.loads(Path(directory_path).read_text(encoding="utf-8"))
    users = config.setdefault("users", [])
    records = sorted((item for item in directory.values() if _text(item.get("name"))), key=lambda item: _text(item.get("member_key")))
    name_counts = Counter(_text(item.get("name")) for item in records)
    by_employee = {_text(item.get("employee_id")): item for item in users if _text(item.get("employee_id"))}
    by_unique_name = {item.get("name"): item for item in users if _text(item.get("name"))}
    claimed = {_text(item.get("username")) for item in users}
    summary = {"created": 0, "enriched": 0, "unchanged": 0}

    for record in records:
        employee_id = _text(record.get("member_key"))
        name = _text(record.get("name"))
        account = by_employee.get(employee_id)
        if not account and name_counts[name] == 1:
            account = by_unique_name.get(name)
        fields = {
            "employee_id": employee_id,
            "company": _text(record.get("company")),
            "department": _text(record.get("department")),
            "position": _text(record.get("title")),
            "organization_source": "crm_staff_directory",
        }
        if account:
            changed = any(_text(account.get(key)) != value for key, value in fields.items())
            account.update(fields)
            summary["enriched" if changed else "unchanged"] += 1
            continue

        username = _username(name, employee_id, claimed, transliterate)
        account = {
            "username": username,
            "password": hash_password(DEFAULT_PASSWORD),
            "role": "member",
            "name": name,
            **fields,
        }
        users.append(account)
        claimed.add(username)
        by_employee[employee_id] = account
        if name_counts[name] == 1:
            by_unique_name[name] = account
        summary["created"] += 1

    # Keep the inode intact: production binds config.json into the running
    # container, and replacing the file would leave that mount on old data.
    Path(config_path).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Provision personal-work-site accounts from CRM staff data.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        from pypinyin import lazy_pinyin
    except ImportError as exc:
        raise SystemExit("需要 pypinyin：python3 -m pip install pypinyin") from exc
    result = provision(args.config, args.directory, lambda name: "".join(lazy_pinyin(name)))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
