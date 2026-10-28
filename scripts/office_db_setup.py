#!/usr/bin/env python3
"""办公平台统一存储层准备（宿主机运行，可重复执行）。

- 在 office 库创建 app schema（documents / blobs / events）与 office_app 写角色；
- 生成 user_data/_datacenter/office_db.json（600 权限）：modules 里逐个助手开关，
  首次生成为空（全部仍走文件），由迁移脚本核对通过后逐个翻开关。
- --test-db <名称>：另建一个一次性测试库（同样的表），供单测 OFFICE_STORE_TEST_CONFIG 使用。
"""
import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "user_data" / "_datacenter" / "office_db.json"
sys.path.insert(0, str(ROOT / "vendor" / "pgdeps"))


def load_ddl():
    namespace = {}
    source = (ROOT / "backend" / "office_store.py").read_text(encoding="utf-8")
    start = source.index("OFFICE_STORE_DDL = ")
    end = source.index('"""\n', source.index('"""', start) + 3) + 4
    exec(source[start:end], namespace)
    return namespace["OFFICE_STORE_DDL"]


def psql(sql, database="office"):
    return subprocess.run(["docker", "exec", "-i", "office-postgres", "psql", "-U", "office", "-d", database,
                           "-v", "ON_ERROR_STOP=1"], input=sql, text=True, capture_output=True, check=True).stdout


def grant_sql(password):
    return "\n".join([
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='office_app') THEN "
        "CREATE ROLE office_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE; END IF; END $$;",
        f"ALTER ROLE office_app PASSWORD '{password}';",
        "ALTER ROLE office_app SET statement_timeout='30s';",
        "GRANT USAGE ON SCHEMA app TO office_app;",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO office_app;",
        "GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO office_app;",
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-db", help="另建一次性测试库并输出其配置路径")
    args = parser.parse_args()
    ddl = load_ddl()

    existing = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    password = existing.get("password") or secrets.token_urlsafe(36)
    psql(ddl)
    psql(grant_sql(password) + "\nGRANT CONNECT ON DATABASE office TO office_app;")
    config = {**existing, "enabled": True, "host": "office-postgres", "port": 5432, "database": "office",
              "user": "office_app", "password": password, "modules": existing.get("modules") or {}}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    TARGET.chmod(0o600)
    print(f"已写入 {TARGET}，已开启助手：{[k for k, v in config['modules'].items() if v]}")

    if args.test_db:
        name = args.test_db
        assert name != "office", "测试库不能是生产库"
        exists = psql(f"SELECT 1 FROM pg_database WHERE datname='{name}'").strip().splitlines()
        if not any(line.strip() == "1" for line in exists):
            psql(f'CREATE DATABASE "{name}"')
        psql(ddl, database=name)
        psql(grant_sql(password) + f'\nGRANT CONNECT ON DATABASE "{name}" TO office_app;', database=name)
        ip = subprocess.run(["docker", "inspect", "office-postgres", "--format",
                             "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"],
                            capture_output=True, text=True, check=True).stdout.split()[0]
        test_config = {**config, "host": ip, "database": name, "modules": {"all": True}}
        test_path = Path("/tmp") / f"office_store_test_{name}.json"
        test_path.write_text(json.dumps(test_config, ensure_ascii=False, indent=2), encoding="utf-8")
        test_path.chmod(0o600)
        print(f"测试库 {name} 就绪，配置：{test_path}（export OFFICE_STORE_TEST_CONFIG={test_path}）")


if __name__ == "__main__":
    main()
