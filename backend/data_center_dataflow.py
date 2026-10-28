"""数据中台「数据流向」：数据库 ↔ 助手 的实时连接拓扑、交互速率与异常。

- 拓扑是架构事实（哪个助手用哪些库），叠加实时证据：各库的活动计数器两次
  采样差分成速率；客户端连接地址经注册文件 client_map 反查是哪个容器在连。
- 异常（不可达 / 认证失败 / 死锁增长 / 回滚异常 / 拒绝连接 / ES red / 同步或
  备份失败）写入 _datacenter/db_alerts.jsonl（同实例同类型 10 分钟去重）。
- 复用 data_center_databases 的连接助手（共享命名空间，加载顺序在其后）。
"""

def _dc_store_enabled(module):
    """统一存储层开关（独立命名空间加载本模块时可能没有 office_store，按未切库处理）。"""
    fn = globals().get("officedb_enabled")
    return bool(fn and fn(module))


def _dc_store_module(ident):
    fn = globals().get("office_store_module")
    return fn(ident) if fn else ident

import json
import threading as _dcflow_threading
import time as _dcflow_time
from datetime import datetime as _dcflow_datetime

DCFLOW_MIN_INTERVAL = 2.5     # 秒；更频繁的请求直接复用上次结果
DCFLOW_ALERT_DEDUP = 600      # 秒；同实例同类型告警的落盘去重窗口
_dcflow_lock = _dcflow_threading.Lock()
_dcflow_cache = {"at": 0.0, "result": None}
_dcflow_last = {}             # instance_id -> (monotonic, counters)
_dcflow_alert_seen = {}       # (instance, code) -> monotonic

# 助手 → 数据库实例（架构事实；实例缺失时自动忽略该边）。client_hints 用于把
# 数据库端看到的客户端标签归属到助手，作为"这条连接正在交互"的实时证据。
DCFLOW_TOPOLOGY = [
    {"id": "crm", "label": "联指经营助手", "instances": ["office-postgres", "crm-redis", "crm-neo4j"],
     "client_hints": ["联指经营助手"]},
    {"id": "datacenter", "label": "数据中台（同步/接口/备份）", "instances": ["office-postgres"],
     "client_hints": ["数据中台"]},
    {"id": "agent", "label": "智能体 · 工作流 · 技能", "instances": ["sqlite-app"], "client_hints": []},
    {"id": "workflow", "label": "工作流中心（FastGPT）",
     "instances": ["fastgpt-mongo", "fastgpt-pg", "fastgpt-redis", "fastgpt-minio"],
     "client_hints": ["工作流中心"]},
    {"id": "gateway", "label": "模型网关（AI Proxy）", "instances": ["fastgpt-aiproxy-pg"],
     "client_hints": ["模型网关"]},
    {"id": "knowledge", "label": "知识库（Qdrant / RAGFlow）",
     "instances": ["qdrant", "ragflow-mysql", "ragflow-es", "ragflow-redis", "ragflow-minio"],
     "client_hints": ["知识库"]},
    {"id": "dify", "label": "Dify 平台", "instances": ["dify-postgres", "dify-redis"],
     "client_hints": ["Dify"]},
    {"id": "foundry", "label": "Foundry 平台", "instances": ["foundry-postgres"],
     "client_hints": ["Foundry"]},
]

DCFLOW_FILE_ASSISTANTS = {
    "writing": ("智能写作", "用户目录 writing/：素材、历史、模板与导出"),
    "weekly": ("周报助手", "用户目录 reports/weekly、drafts、generated；工作日记提供素材"),
    "trip": ("出差报告助手", "用户目录 reports/trip、drafts、generated"),
    "diary": ("工作日记", "用户目录 diary/*.json"),
    "forum": ("金点子论坛", "共享目录 _forum/"),
    "news": ("每日资讯", "共享 _news/ 与用户 news/ 缓存"),
    "mailassistant": ("邮件助手", "邮件服务器、用户 mail_cache/ 与账号邮件配置"),
    "meeting": ("会议助手", "用户目录 meetings/：录音、转写、纪要"),
    "project": ("项目助手", "共享 projects/projects.json 与项目附件"),
    "ledger": ("项目管理台账", "用户 operating_ledger.json 与 contract_documents/"),
    "cashflow": ("资金测算助手", "用户 cashflow_*.json、cashflow_exports/ 与共享模板"),
    "reimbursement": ("报销助手", "用户目录 reimbursement/：发票与报销附件"),
}


def _dcflow_topology():
    groups = {group["id"]: dict(group, node_type="system", mirror_instances=[],
                                     storage_note="数据库主存储；连接状态以实例采样为准")
              for group in DCFLOW_TOPOLOGY}
    for ident, (label, source) in DCFLOW_FILE_ASSISTANTS.items():
        if _dc_store_enabled(_dc_store_module(ident)):
            groups[ident] = {"id": ident, "label": label, "instances": ["office-postgres"],
                             "client_hints": [], "mirror_instances": [],
                             "storage_note": f"主存储：office-postgres · app.documents / app.blobs（原 {source.split('：')[0]} 已切库，目录保留为切换前快照）。"}
        else:
            groups[ident] = {"id": ident, "label": label, "instances": ["office-postgres"],
                             "client_hints": [], "mirror_instances": ["office-postgres"],
                             "storage_note": f"主存储：{source}。统一库保存定时同步镜像或文件索引，非实时业务读写。"}
    groups["lobsterbase"] = {"id": "lobsterbase", "label": "龙虾基地", "instances": [],
                              "client_hints": [], "mirror_instances": [],
                              "storage_note": "外部 OpenClaw 平台：platform.db、智能体工作目录及对象存储；尚未接入中台数据库监测。"}
    groups["workorder"] = {"id": "workorder", "label": "工单系统", "instances": ["office-postgres"],
                            "client_hints": [], "mirror_instances": [] if _dc_store_enabled("workorder") else ["office-postgres"],
                            "node_type": "system",
                            "storage_note": ("主存储：office-postgres · app.documents（工单记录已切库；collab.tickets 由其同步）。"
                                             if _dc_store_enabled("workorder") else "主存储：共享 _tickets/；统一库 collab.tickets 为定时同步镜像。")}
    groups["agent"]["instances"].append("office-postgres")
    groups["agent"]["mirror_instances"] = ["office-postgres"]
    groups["agent"]["storage_note"] = "SQLite 保存会话、消息、技能、记忆和工作流；统一库保存定时同步镜像。"
    groups["workflow"]["instances"] = [*groups["workflow"]["instances"], "sqlite-app"]
    groups["workflow"]["storage_note"] = "FastGPT 数据库保存编排与知识数据；平台 SQLite 的 workflow_instances 保存本地工作流实例。"
    if _dc_store_enabled("knowledge"):
        groups["knowledge"]["storage_note"] = "Qdrant / RAGFlow 保存检索数据，本地文档记录与 RAGFlow 映射已切库到 office-postgres · app.documents；平台问答会话在 SQLite。"
        groups["knowledge"]["instances"].append("office-postgres")
    else:
        groups["knowledge"]["storage_note"] = "Qdrant / RAGFlow 保存检索数据，共享 knowledge/ 保存本地文档记录和映射；平台问答会话在 SQLite。"
    groups["knowledge"]["instances"].append("sqlite-app")
    ordered = []
    for ident in ASSISTANT_IDS:
        group = groups.pop(ident, {"id": ident, "label": ident, "instances": [],
                                  "client_hints": [], "mirror_instances": [],
                                  "storage_note": "存储对应关系待核实，尚未接入数据库监测。"})
        ordered.append(dict(group, node_type="assistant"))
    return ordered + list(groups.values())


def _dcflow_client_label(addr):
    ip = str(addr or "").split(":")[0].split("/")[0]
    mapping = (read_json(datacenter_dir(USER_DATA_DIR) / "db_connections.json", {}) or {}).get("client_map") or {}
    return mapping.get(ip, "")


def _dcflow_pg(inst):
    conn = _dcdb_pg_connect(inst)
    try:
        row = conn.run("SELECT numbackends, xact_commit, xact_rollback, tup_returned + tup_fetched, "
                       "tup_inserted + tup_updated + tup_deleted, deadlocks "
                       "FROM pg_stat_database WHERE datname = current_database()")[0]
        clients = conn.run("SELECT coalesce(client_addr::text, '容器内'), count(*) FROM pg_stat_activity "
                           "WHERE datname = current_database() AND pid <> pg_backend_pid() GROUP BY 1")
        counters = {"事务提交": row[1], "事务回滚": row[2], "行读取": row[3], "行写入": row[4], "死锁": row[5]}
        return counters, {"连接数": row[0]}, [{"addr": a, "count": c} for a, c in clients]
    finally:
        conn.close()


def _dcflow_mysql(inst):
    (status_rows, _), (proc_rows, _) = _dcdb_mysql_run(inst, None, [
        ("SHOW GLOBAL STATUS WHERE Variable_name IN "
         "('Questions','Innodb_rows_read','Innodb_rows_inserted','Innodb_rows_updated',"
         "'Innodb_rows_deleted','Threads_connected','Aborted_connects')", None),
        ("SELECT host, count(*) AS c FROM information_schema.processlist "
         "WHERE user NOT IN ('event_scheduler') GROUP BY host", None)])
    status = {row["Variable_name"]: int(row["Value"]) for row in status_rows}
    counters = {"查询数": status.get("Questions", 0),
                "行读取": status.get("Innodb_rows_read", 0),
                "行写入": status.get("Innodb_rows_inserted", 0) + status.get("Innodb_rows_updated", 0)
                          + status.get("Innodb_rows_deleted", 0),
                "连接失败": status.get("Aborted_connects", 0)}
    clients = [{"addr": row["host"], "count": int(row["c"])} for row in proc_rows]
    return counters, {"连接数": status.get("Threads_connected", 0)}, clients


def _dcflow_redis(inst):
    client = _DcdbRedis(inst)
    try:
        info = dict(line.partition(":")[::2] for line in (client.cmd("INFO") or "").splitlines()
                    if ":" in line and not line.startswith("#"))
        counters = {"命令数": int(info.get("total_commands_processed", 0)),
                    "拒绝连接": int(info.get("rejected_connections", 0))}
        gauges = {"连接数": int(info.get("connected_clients", 0)),
                  "每秒操作": int(info.get("instantaneous_ops_per_sec", 0))}
        clients = {}
        for line in (client.cmd("CLIENT", "LIST") or "").splitlines():
            fields = dict(part.split("=", 1) for part in line.split(" ") if "=" in part)
            if fields.get("cmd", "").startswith("client"):
                continue  # 排除本次采样自身
            addr = fields.get("addr", "")
            clients[addr] = clients.get(addr, 0) + 1
        return counters, gauges, [{"addr": a, "count": c} for a, c in sorted(clients.items())]
    finally:
        client.close()


def _dcflow_mongo(inst):
    client = _dcdb_mongo_client(inst)
    try:
        status = client.admin.command("serverStatus")
        ops = status.get("opcounters", {})
        counters = {"读操作": int(ops.get("query", 0)) + int(ops.get("getmore", 0)),
                    "写操作": int(ops.get("insert", 0)) + int(ops.get("update", 0)) + int(ops.get("delete", 0)),
                    "命令数": int(ops.get("command", 0))}
        return counters, {"连接数": int(status.get("connections", {}).get("current", 0))}, []
    finally:
        client.close()


def _dcflow_es(inst):
    stats = _dcdb_http(inst, "GET", "/_stats?filter_path=_all.total.search.query_total,"
                                    "_all.total.indexing.index_total")
    total = (stats.get("_all") or {}).get("total") or {}
    health = _dcdb_http(inst, "GET", "/_cluster/health")
    counters = {"检索次数": int((total.get("search") or {}).get("query_total", 0)),
                "写入文档": int((total.get("indexing") or {}).get("index_total", 0))}
    return counters, {"集群状态": health.get("status", ""), "节点数": health.get("number_of_nodes", 0)}, []


def _dcflow_qdrant(inst):
    collections = (_dcdb_http(inst, "GET", "/collections").get("result") or {}).get("collections") or []
    points = 0
    for c in collections:
        detail = (_dcdb_http(inst, "GET", f"/collections/{c['name']}").get("result") or {})
        points += int(detail.get("points_count") or 0)
    return {"向量点": points}, {"集合数": len(collections)}, []


def _dcflow_neo4j(inst):
    result = _dcdb_neo4j_run(inst, [("MATCH (n) RETURN count(n)", None),
                                    ("MATCH ()-[r]->() RETURN count(r)", None)])
    nodes = result[0]["data"][0]["row"][0]
    rels = result[1]["data"][0]["row"][0]
    return {"节点+关系": int(nodes) + int(rels)}, {"节点": nodes, "关系": rels}, []


def _dcflow_sqlite(inst):
    path = BASE_DIR / inst["path"]
    stat = path.stat()
    return {"文件写入": stat.st_mtime_ns // 1_000_000_000}, \
        {"大小": f"{stat.st_size / 1048576:.1f} MB"}, []


def _dcflow_minio(inst):
    import urllib.request as _rq
    with _rq.urlopen(f"http://{inst['host']}:{inst['port']}/minio/health/live", timeout=5) as resp:
        ok = resp.status == 200
    return {}, {"健康检查": "通过" if ok else "失败"}, []


_DCFLOW_SAMPLERS = {"postgres": _dcflow_pg, "mysql": _dcflow_mysql, "redis": _dcflow_redis,
                    "mongodb": _dcflow_mongo, "elasticsearch": _dcflow_es, "qdrant": _dcflow_qdrant,
                    "neo4j": _dcflow_neo4j, "sqlite": _dcflow_sqlite, "minio": _dcflow_minio}

# 速率字段：counters 里这些键换算为"每秒"；其余（死锁/拒绝等）给增量。
_DCFLOW_RATE_KEYS = {"事务提交", "事务回滚", "行读取", "行写入", "查询数", "命令数",
                     "读操作", "写操作", "检索次数", "写入文档"}


def _dcflow_alert(alerts, instance, level, code, message):
    alerts.append({"at": _dcflow_datetime.now().isoformat(timespec="seconds"),
                   "instance": instance, "level": level, "code": code, "message": message})


def _dcflow_persist_alerts(alerts):
    if not alerts:
        return
    now = _dcflow_time.monotonic()
    path = datacenter_dir(USER_DATA_DIR) / "db_alerts.jsonl"
    lines = []
    for alert in alerts:
        key = (alert["instance"], alert["code"])
        if now - _dcflow_alert_seen.get(key, -DCFLOW_ALERT_DEDUP) >= DCFLOW_ALERT_DEDUP:
            _dcflow_alert_seen[key] = now
            lines.append(json.dumps(alert, ensure_ascii=False))
    if not lines:
        return
    try:
        if _dc_store_enabled("datacenter"):
            for line in lines:
                office_event_append("datacenter", "db_alerts", json.loads(line))
            return
    except Exception:
        pass  # 告警库不可用时落回文件，避免监控本身中断
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _dcflow_recent_alerts(limit=30):
    if _dc_store_enabled("datacenter"):
        try:
            return [{k: v for k, v in row.items() if k != "seq"} for row in office_event_recent("datacenter", "db_alerts", limit=limit)]
        except Exception:
            return []
    path = datacenter_dir(USER_DATA_DIR) / "db_alerts.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines[-500:]):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


def _dcflow_sample_instance(inst, alerts):
    item = {"id": inst["id"], "label": inst.get("label", inst["id"]), "kind": inst["kind"],
            "system": inst.get("system", ""), "category": inst.get("category", "relational"),
            "status": "up", "gauges": {}, "rates": {}, "deltas": {}, "clients": [], "active": False}
    if inst["kind"] != "mysql" and not _dcdb_probe_host(inst):
        item["status"] = "down"
        _dcflow_alert(alerts, inst["id"], "critical", "down", f"{inst.get('label', inst['id'])} 探测不可达")
        return item
    try:
        counters, gauges, clients = _DCFLOW_SAMPLERS[inst["kind"]](inst)
    except Exception as exc:
        item["status"] = "auth-error"
        _dcflow_alert(alerts, inst["id"], "critical", "sample-error",
                      f"{inst.get('label', inst['id'])} 采样失败：{type(exc).__name__}")
        return item
    item["gauges"] = gauges
    grouped = {}
    for entry in clients:
        label = _dcflow_client_label(entry["addr"]) or entry["addr"]
        grouped[label] = grouped.get(label, 0) + int(entry.get("count", 1))
    item["clients"] = [{"label": label, "count": count}
                       for label, count in sorted(grouped.items(), key=lambda kv: -kv[1])]
    now = _dcflow_time.monotonic()
    previous = _dcflow_last.get(inst["id"])
    if previous:
        dt = max(now - previous[0], 0.5)
        for key, value in counters.items():
            delta = value - previous[1].get(key, value)
            if key in _DCFLOW_RATE_KEYS:
                item["rates"][key] = round(max(delta, 0) / dt, 1)
            else:
                item["deltas"][key] = max(delta, 0)
    _dcflow_last[inst["id"]] = (now, counters)
    if inst["kind"] == "sqlite":
        # mtime 作写入信号：只表达"采样间隔内有没有写入"，不展示原始时间戳差值。
        item["deltas"] = {"期间有写入": 1} if any(v > 0 for v in item["deltas"].values()) else {}
    item["active"] = bool(item["clients"]) or any(v > 0 for v in item["rates"].values()) \
        or any(v > 0 for v in item["deltas"].values())

    if item["deltas"].get("死锁"):
        _dcflow_alert(alerts, inst["id"], "warning", "deadlock", f"检测到 {item['deltas']['死锁']} 次新死锁")
    if item["deltas"].get("拒绝连接"):
        _dcflow_alert(alerts, inst["id"], "warning", "rejected", "Redis 拒绝了新连接（连接数达上限）")
    if item["deltas"].get("连接失败"):
        _dcflow_alert(alerts, inst["id"], "warning", "aborted-connect",
                      f"MySQL 连接失败 {item['deltas']['连接失败']} 次")
    rollback, commit = item["rates"].get("事务回滚", 0), item["rates"].get("事务提交", 0)
    if rollback > commit and rollback + commit > 5:
        _dcflow_alert(alerts, inst["id"], "warning", "rollback", f"事务回滚率异常（{rollback}/s > 提交 {commit}/s）")
    if item["gauges"].get("集群状态") == "red":
        _dcflow_alert(alerts, inst["id"], "critical", "es-red", "Elasticsearch 集群状态 red")
    return item


def _dcflow_platform_alerts(alerts):
    sync = (read_json(datacenter_dir(USER_DATA_DIR) / "db_sync.json", {}) or {}).get("last") or {}
    if sync and sync.get("ok") is False:
        _dcflow_alert(alerts, "office-postgres", "critical", "sync-failed",
                      f"数据入库同步失败（{sync.get('finished_at', '')}）")
    backup = (read_json(datacenter_dir(USER_DATA_DIR) / "backup_status.json", {}) or {}).get("last_run") or {}
    if backup and backup.get("ok") is False:
        _dcflow_alert(alerts, "office-postgres", "critical", "backup-failed",
                      f"备份失败（{backup.get('finished_at', '')}）")


# 助手 × 实例 → 相关数据对象的归属规则；未列出的边表示"整库都属于该系统"。
# office-postgres 内：crm schema 归联指经营助手，其余 schema 是数据中台的镜像/治理数据。
DCFLOW_EDGE_TABLES = {
    ("crm", "office-postgres"): {"include": ["crm."]},
    ("datacenter", "office-postgres"): {"exclude": ["crm."]},
    ("ledger", "office-postgres"): {"include": ["ledger."]},
    ("cashflow", "office-postgres"): {"include": ["cashflow."]},
    ("forum", "office-postgres"): {"exact": ["collab.forum_topics"]},
    ("workorder", "office-postgres"): {"exact": ["collab.tickets"]},
    ("agent", "office-postgres"): {"include": ["agentic."]},
    ("agent", "sqlite-app"): {"exact": ["agent_sessions", "agent_messages", "agent_events", "skill_invocations", "memory_items", "workflow_instances"]},
    ("workflow", "sqlite-app"): {"exact": ["workflow_instances"]},
    ("knowledge", "sqlite-app"): {"exact": ["agent_sessions", "agent_messages"], "shared": True},
    ("platform", "office-postgres"): {"include": ["auth.", "settings.", "agentic.", "collab.tickets"]},
    ("platform", "sqlite-app"): {"exact": ["agent_sessions", "agent_messages", "agent_events", "skill_invocations", "memory_items", "workflow_instances"]},
}
for _dcflow_ident in DCFLOW_FILE_ASSISTANTS:
    DCFLOW_EDGE_TABLES.setdefault((_dcflow_ident, "office-postgres"),
                                 {"exact": ["raw.documents", "files.catalog"], "shared": True})


DCFLOW_LIVE_TABLES = {
    "mailassistant": ["app.documents", "app.blobs", "app.cache_documents", "app.cache_blobs"],
    "datacenter": ["app.events", "app.documents", "app.blobs"],
}


def _dcflow_edge_rule(assistant_id, instance_id):
    """已切库助手在 office-postgres 额外关联在线业务表 app.*（按 module 列区分，多助手共享）；
    静态规则里的镜像 / 归属表照旧保留。"""
    rule = DCFLOW_EDGE_TABLES.get((assistant_id, instance_id))
    module = _dc_store_module(assistant_id)
    if instance_id == "office-postgres" and module in globals().get("OFFICE_STORE_MODULES", ()) and _dc_store_enabled(module):
        return dict(rule or {}, live=DCFLOW_LIVE_TABLES.get(module, ["app.documents", "app.blobs"]))
    return rule


def dcflow_tables(assistant_id, instance_id, username):
    """选中助手后点击关联库：返回该助手在这个库里的相关数据表/集合/键。"""
    group = next((g for g in _dcflow_topology() if g["id"] == str(assistant_id or "")), None)
    if assistant_id == "platform":
        members = [entry for entry in _dcflow_topology() if entry["node_type"] != "assistant"]
        group = {"id": "platform", "label": "平台本身", "instances": sorted({ident for member in members for ident in member["instances"]}),
                 "mirror_instances": ["office-postgres"], "storage_note": "平台共享表可能包含多个助手的数据；行数与容量为全表值，非单助手统计。"}
    if not group or str(instance_id or "") not in group["instances"]:
        raise ValueError("该助手与此数据库没有关联")
    inst = _dcdb_inst(instance_id)
    if inst["kind"] == "minio":
        return {"ok": True, "assistant": group["label"], "instance": inst.get("label", inst["id"]),
                "kind": "minio", "objects": [], "rows_label": "",
                "note": "对象存储保存附件等文件本体，不提供表清单；文件索引见「原始数据」页签"}
    result = dcdb_objects(instance_id, inst.get("database", ""), username)
    rule = _dcflow_edge_rule(group["id"], inst["id"])
    all_objects = result.get("objects") or []
    objects = list(all_objects)
    live = list((rule or {}).get("live") or [])
    note = f"{inst.get('label', inst['id'])} 整库服务于「{group['label']}」"
    if rule and live and not (rule.get("exact") or rule.get("include") or rule.get("exclude")):
        objects = []
        note = "按数据对象归属过滤。"
    if rule:
        include, exclude = rule.get("include"), rule.get("exclude")
        if rule.get("exact"):
            objects = [o for o in objects if o["name"] in rule["exact"]]
            note = "按数据对象归属过滤。"
        elif include:
            objects = [o for o in objects if any(o["name"].startswith(p) for p in include)]
            note = f"按归属过滤：{'、'.join(include)} 前缀的数据表属于「{group['label']}」"
        elif exclude:
            objects = [o for o in objects if not any(o["name"].startswith(p) for p in exclude)]
            note = f"按归属过滤：除 {'、'.join(exclude)} 外的镜像/治理数据表属于「{group['label']}」"
        if rule.get("shared"):
            objects = [dict(obj, rows=None, size=None, kind_label="共享镜像 / 索引") for obj in objects]
            note = "共享原始文档 / 文件索引表，包含多个助手的数据；未按助手统计行数与容量，请在原始数据页按来源路径查看。"
    if live:
        live_objects = [dict(obj, kind_label="在线业务表（统一存储层，多助手共享，行数为全表）")
                        for obj in all_objects if obj["name"] in live]
        objects = live_objects + [obj for obj in objects if obj["name"] not in live]
        note = ("在线业务表 app.* 按 module 列区分助手，行数与容量为全表值；其余为镜像 / 归属表。 " + note)
    if instance_id in group.get("mirror_instances", []):
        note = "定时同步镜像，非助手实时直连。" + note
    note += " " + group["storage_note"]
    return {"ok": True, "assistant": group["label"], "instance": inst.get("label", inst["id"]),
            "kind": inst["kind"], "objects": objects, "rows_label": result.get("rows_label", ""),
            "note": note}


def dcflow_snapshot():
    now = _dcflow_time.monotonic()
    with _dcflow_lock:
        if _dcflow_cache["result"] and now - _dcflow_cache["at"] < DCFLOW_MIN_INTERVAL:
            return _dcflow_cache["result"]
    instances = list(_dcdb_registry().values())
    alerts = []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        items = list(pool.map(lambda inst: _dcflow_sample_instance(inst, alerts), instances))
    _dcflow_platform_alerts(alerts)
    _dcflow_persist_alerts(alerts)
    known = {item["id"] for item in items}
    topology = [{**group, "instances": [i for i in group["instances"] if i in known],
                 "unregistered_instances": [i for i in group["instances"] if i not in known]}
                for group in _dcflow_topology()]
    result = {"ok": True, "sampled_at": _dcflow_datetime.now().isoformat(timespec="seconds"),
              "assistants": topology, "instances": items,
              "alerts_active": alerts, "alerts_recent": _dcflow_recent_alerts()}
    with _dcflow_lock:
        _dcflow_cache["at"] = now
        _dcflow_cache["result"] = result
    return result
