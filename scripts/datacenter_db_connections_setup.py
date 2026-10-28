#!/usr/bin/env python3
"""生成数据中台「数据库直连」的连接注册文件（在宿主机上运行）。

凭据从各数据库容器的运行环境读取，写入 user_data/_datacenter/db_connections.json
（权限 600），不写入代码仓库。凭据轮换或新增数据库后重新运行本脚本即可。

统一业务库 office-postgres 不落密文：主服务容器已有只读角色环境变量
OFFICE_QUERY_PASSWORD，注册项里只记 password_env。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def container_env(name):
    try:
        out = subprocess.run(["docker", "inspect", name, "--format",
                              "{{json .Config.Env}}"], capture_output=True, text=True, check=True).stdout
        return dict(item.split("=", 1) for item in json.loads(out) if "=" in item)
    except subprocess.CalledProcessError:
        print(f"[跳过] 容器 {name} 不存在或未运行", file=sys.stderr)
        return None


def container_cmd(name):
    try:
        out = subprocess.run(["docker", "inspect", name, "--format", "{{json .Config.Cmd}}"],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out) or []
    except subprocess.CalledProcessError:
        return []


def redis_password_from_cmd(name):
    cmd = container_cmd(name)
    for i, part in enumerate(cmd):
        if part == "--requirepass" and i + 1 < len(cmd):
            return cmd[i + 1]
    return ""


# 数据库类别（分色展示）：kind 默认映射 + 个别实例覆盖（pgvector 属向量库）。
CATEGORY_BY_KIND = {"postgres": "relational", "mysql": "relational", "sqlite": "relational",
                    "mongodb": "document", "redis": "kv", "elasticsearch": "fulltext",
                    "qdrant": "vector", "neo4j": "graph", "minio": "object"}
CATEGORY_OVERRIDES = {"fastgpt-pg": "vector"}


def build():
    instances = [
        {"id": "office-postgres", "kind": "postgres", "label": "统一业务数据库", "system": "办公平台",
         "level": "A", "host": "office-postgres", "port": 5432, "database": "office",
         "user": "datacenter_reader", "password_env": "OFFICE_QUERY_PASSWORD",
         "note": "只读角色 datacenter_reader（已授 pg_read_all_data）"},
        {"id": "sqlite-app", "kind": "sqlite", "label": "平台 SQLite（app.db）", "system": "办公平台",
         "level": "A", "path": "user_data/app.db", "note": "智能体会话 / 工作流 / 技能调用"},
    ]

    env = container_env("fastgpt-pg")
    if env:
        instances.append({"id": "fastgpt-pg", "kind": "postgres", "label": "工作流中心向量库", "system": "FastGPT",
                          "level": "C", "host": "fastgpt-pg", "port": 5432,
                          "database": env.get("POSTGRES_DB", "fastgpt"),
                          "user": env.get("POSTGRES_USER", "fastgpt"), "password": env.get("POSTGRES_PASSWORD", "")})
    env = container_env("fastgpt-aiproxy-pg")
    if env:
        instances.append({"id": "fastgpt-aiproxy-pg", "kind": "postgres", "label": "模型网关库", "system": "FastGPT",
                          "level": "C", "host": "fastgpt-aiproxy-pg", "port": 5432,
                          "database": env.get("POSTGRES_DB", "aiproxy"),
                          "user": env.get("POSTGRES_USER", "postgres"), "password": env.get("POSTGRES_PASSWORD", "")})
    env = container_env("docker-db-1")
    if env:
        instances.append({"id": "dify-postgres", "kind": "postgres", "label": "Dify 平台库", "system": "Dify",
                          "level": "B", "host": "docker-db-1", "port": 5432,
                          "database": env.get("POSTGRES_DB", "dify"),
                          "user": env.get("PGUSER", "postgres"), "password": env.get("POSTGRES_PASSWORD", ""),
                          "note": "主容器需在 docker_default 网络（docker network connect docker_default personal-work-site）"})
    env = container_env("foundry-platform-postgres-1")
    if env:
        instances.append({"id": "foundry-postgres", "kind": "postgres", "label": "Foundry 平台库", "system": "Foundry",
                          "level": "B", "host": "foundry-platform-postgres-1", "port": 5432,
                          "database": env.get("POSTGRES_DB", "foundry"),
                          "user": env.get("POSTGRES_USER", "foundry"), "password": env.get("POSTGRES_PASSWORD", ""),
                          "note": "主容器需在 foundry-platform_default 网络"})
    env = container_env("ragflow-mysql")
    if env:
        instances.append({"id": "ragflow-mysql", "kind": "mysql", "label": "知识库主库（RAGFlow）", "system": "RAGFlow",
                          "level": "A", "host": "host.docker.internal", "port": 5455,
                          "database": "rag_flow", "user": "root",
                          "password": env.get("MYSQL_ROOT_PASSWORD", "")})
    env = container_env("fastgpt-mongo")
    if env:
        instances.append({"id": "fastgpt-mongo", "kind": "mongodb", "label": "工作流中心主库", "system": "FastGPT",
                          "level": "A", "host": "fastgpt-mongo", "port": 27017,
                          "user": env.get("MONGO_INITDB_ROOT_USERNAME", ""),
                          "password": env.get("MONGO_INITDB_ROOT_PASSWORD", ""),
                          "note": "副本集 rs0，直连模式"})

    for cid, container, host, port, label, system, level in [
            ("crm-redis", "crm-redis", "crm-redis", 6379, "联指经营助手缓存", "办公平台", "D"),
            ("fastgpt-redis", "fastgpt-redis", "fastgpt-redis", 6379, "工作流中心缓存", "FastGPT", "D"),
            ("dify-redis", "docker-redis-1", "docker-redis-1", 6379, "Dify 缓存", "Dify", "D"),
            ("ragflow-redis", "ragflow-redis", "host.docker.internal", 16379, "知识库缓存（RAGFlow）", "RAGFlow", "D")]:
        if container_env(container) is None:
            continue
        instances.append({"id": cid, "kind": "redis", "label": label, "system": system, "level": level,
                          "host": host, "port": port, "password": redis_password_from_cmd(container)})

    env = container_env("ragflow-es-01")
    if env:
        instances.append({"id": "ragflow-es", "kind": "elasticsearch", "label": "知识库全文索引（RAGFlow）",
                          "system": "RAGFlow", "level": "B", "url": "http://host.docker.internal:1200",
                          "user": "elastic", "password": env.get("ELASTIC_PASSWORD", "")})
    if container_env("personal-work-qdrant") is not None:
        instances.append({"id": "qdrant", "kind": "qdrant", "label": "知识库向量库", "system": "办公平台",
                          "level": "C", "url": "http://personal-work-qdrant:6333"})
    env = container_env("crm-neo4j")
    if env:
        auth = env.get("NEO4J_AUTH", "neo4j/")
        user, _, password = auth.partition("/")
        instances.append({"id": "crm-neo4j", "kind": "neo4j", "label": "联指经营助手关系图谱", "system": "办公平台",
                          "level": "C", "url": "http://crm-neo4j:7474", "user": user, "password": password})
    if container_env("fastgpt-minio") is not None:
        instances.append({"id": "fastgpt-minio", "kind": "minio", "label": "工作流中心文件存储", "system": "FastGPT",
                          "level": "B", "host": "fastgpt-minio", "port": 9000,
                          "note": "对象存储：仅状态与健康探测，不提供内容浏览"})
    if container_env("ragflow-minio") is not None:
        instances.append({"id": "ragflow-minio", "kind": "minio", "label": "知识库文件存储（RAGFlow）",
                          "system": "RAGFlow", "level": "B", "host": "host.docker.internal", "port": 19000,
                          "note": "对象存储：仅状态与健康探测，不提供内容浏览"})

    for inst in instances:
        inst["category"] = CATEGORY_OVERRIDES.get(inst["id"], CATEGORY_BY_KIND.get(inst["kind"], "relational"))

    return {"generated_at": subprocess.run(["date", "+%Y-%m-%dT%H:%M:%S"], capture_output=True,
                                           text=True).stdout.strip(),
            "instances": instances,
            "client_map": build_client_map()}


# 数据流向页用：把数据库端看到的客户端 IP 反查成"哪个容器/哪个助手"。
# 容器重启 IP 会变，重跑本脚本刷新映射；未命中的 IP 前端显示原始地址。
CLIENT_LABELS = [
    ("personal-work-site", "办公平台主服务"),
    ("personal-work-celery", "联指经营助手 · 后台任务"),
    ("datacenter-backup", "数据中台 · 同步/备份"),
    ("datacenter-pg-backup", "数据中台 · 数据库备份"),
    ("fastgpt-app", "工作流中心（FastGPT）"),
    ("fastgpt-sso", "工作流中心 · SSO"),
    ("fastgpt-plugin", "工作流中心 · 插件"),
    ("fastgpt-aiproxy", "模型网关（AI Proxy）"),
    ("ragflow-server", "知识库文档解析（RAGFlow）"),
    ("docker-api-1", "Dify 平台 API"),
    ("docker-worker-1", "Dify 平台 Worker"),
    ("docker-web-1", "Dify 平台 Web"),
    ("docker-plugin_daemon-1", "Dify 插件守护"),
    ("foundry-platform-api-1", "Foundry 平台 API"),
]


def build_client_map():
    mapping = {}
    for container, label in CLIENT_LABELS:
        try:
            out = subprocess.run(["docker", "inspect", container, "--format",
                                  "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}"],
                                 capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            continue
        for ip in out.split():
            if ip:
                mapping[ip] = label
    return mapping


def main():
    target = ROOT / "user_data" / "_datacenter" / "db_connections.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    registry = build()
    target.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    target.chmod(0o600)
    print(f"已写入 {target}（{len(registry['instances'])} 个实例，权限 600）")


if __name__ == "__main__":
    main()
