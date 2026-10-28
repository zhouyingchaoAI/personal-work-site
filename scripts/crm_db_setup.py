#!/usr/bin/env python3
"""联指经营助手切库准备（宿主机运行，可重复执行）。

- 在 office 库创建 crm_app 写角色（仅限 crm schema 的业务表）与 live 辅助表；
- 生成 user_data/_datacenter/crm_db.json（600 权限）：主服务/celery/备份容器
  由它判断存储模式（enabled=true 走 PostgreSQL，false/缺失走本地文件）。

首次生成 enabled=false，由迁移流程校验通过后翻开关。
"""
import json
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "user_data" / "_datacenter" / "crm_db.json"

DDL = """
CREATE TABLE IF NOT EXISTS crm.configuration (key text PRIMARY KEY, payload jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS crm.security_events (seq bigserial PRIMARY KEY, source_line bigint UNIQUE,
  payload jsonb NOT NULL,
  at text GENERATED ALWAYS AS (payload->>'at') STORED,
  actor text GENERATED ALWAYS AS (payload->>'actor') STORED,
  operation text GENERATED ALWAYS AS (payload->>'operation') STORED,
  status integer GENERATED ALWAYS AS ((payload->>'status')::integer) STORED,
  target text GENERATED ALWAYS AS (payload->>'target') STORED);
CREATE INDEX IF NOT EXISTS security_events_actor ON crm.security_events (actor, seq DESC);
CREATE TABLE IF NOT EXISTS crm.links (owner text, id text, payload jsonb NOT NULL,
  synced_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (owner, id));
CREATE TABLE IF NOT EXISTS crm.live_state (key text PRIMARY KEY, version bigint NOT NULL);
INSERT INTO crm.live_state (key, version) VALUES ('global', 1) ON CONFLICT (key) DO NOTHING;
CREATE TABLE IF NOT EXISTS crm.live_history (seq bigserial PRIMARY KEY, owner text NOT NULL,
  collection text NOT NULL, record_id text NOT NULL, at text NOT NULL DEFAULT '', entry jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS live_history_record ON crm.live_history (owner, collection, record_id, seq DESC);
-- payload 用 json（非 jsonb）：保留键序，任务队列/快照展示顺序与文件时代一致。
CREATE TABLE IF NOT EXISTS crm.live_blobs (key text PRIMARY KEY, payload json NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now());
-- pos 保留集合内插入顺序（文件时代由 JSON 键序承载）。
ALTER TABLE crm.units ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.people ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.relations ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.actions ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.links ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.staff ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.opportunities ADD COLUMN IF NOT EXISTS pos integer;
ALTER TABLE crm.staff_directory ADD COLUMN IF NOT EXISTS pos integer;
"""

TABLES = ("units", "people", "relations", "actions", "opportunities", "staff", "links",
          "staff_directory", "live_history", "live_blobs", "live_state", "configuration", "security_events")


def psql(sql):
    return subprocess.run(["docker", "exec", "-i", "office-postgres", "psql", "-U", "office",
                           "-d", "office", "-v", "ON_ERROR_STOP=1"], input=sql, text=True,
                          capture_output=True, check=True).stdout


def main():
    existing = {}
    if TARGET.exists():
        existing = json.loads(TARGET.read_text(encoding="utf-8"))
    password = existing.get("password") or secrets.token_urlsafe(36)

    psql(DDL)
    role_sql = [
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_app') THEN "
        "CREATE ROLE crm_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE; END IF; END $$;",
        f"ALTER ROLE crm_app PASSWORD '{password}';",
        "ALTER ROLE crm_app SET statement_timeout='15s';",
        "GRANT CONNECT ON DATABASE office TO crm_app;",
        "GRANT USAGE ON SCHEMA crm TO crm_app;",
    ]
    role_sql += [f"GRANT SELECT, INSERT, UPDATE, DELETE ON crm.{t} TO crm_app;" for t in TABLES]
    role_sql.append("GRANT USAGE ON ALL SEQUENCES IN SCHEMA crm TO crm_app;")
    psql("\n".join(role_sql))

    config = {**existing, "enabled": bool(existing.get("enabled", False)), "host": "office-postgres",
              "port": 5432, "database": "office", "user": "crm_app", "password": password}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    TARGET.chmod(0o600)
    print(f"已写入 {TARGET}（enabled={config['enabled']}），角色与表已就绪")


if __name__ == "__main__":
    main()
