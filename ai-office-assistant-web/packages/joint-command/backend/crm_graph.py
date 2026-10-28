"""联指经营助手的图谱/缓存/异步基础设施接入层。

三件套按"可选增强 + 优雅降级"接入，任一服务不可用都不阻断主流程：
  - Redis：``crm_overview`` 结果缓存 + Celery broker/backend。
  - Neo4j：关系图谱投影，支撑二度引荐最短路径与度中心度（JSON 仍是可靠数据源，
    图谱按用户子图整体重建，可随时从 JSON 重放）。
  - Celery：写操作后异步同步图谱、每日衰减扫描（见 backend/celery_app.py）。

本模块被 runtime 载入共享命名空间，crm.py 可直接调用其函数。所有外部依赖在
导入期以 try/except 保护：即便旧镜像尚未安装 redis/neo4j/celery，runtime 仍能加载。
"""

import os

try:  # 驱动缺失（旧镜像）时降级为纯内存，不影响 runtime 载入
    import redis as _redis_lib
except Exception:  # pragma: no cover - 依赖缺失路径
    _redis_lib = None

try:
    from neo4j import GraphDatabase as _Neo4jDriver
except Exception:  # pragma: no cover
    _Neo4jDriver = None

CRM_CACHE_TTL = 300  # 秒
_CRM_REDIS_CLIENT = None
_CRM_REDIS_READY = False
_CRM_NEO4J_DRIVER = None
_CRM_NEO4J_READY = False


def crm_redis():
    """惰性连接 Redis；不可用返回 None，调用方自行降级。"""
    global _CRM_REDIS_CLIENT, _CRM_REDIS_READY
    if _CRM_REDIS_READY:
        return _CRM_REDIS_CLIENT
    _CRM_REDIS_READY = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url or _redis_lib is None:
        _CRM_REDIS_CLIENT = None
        return None
    try:
        client = _redis_lib.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
        client.ping()
        _CRM_REDIS_CLIENT = client
    except Exception:
        _CRM_REDIS_CLIENT = None
    return _CRM_REDIS_CLIENT


def crm_neo4j():
    """惰性连接 Neo4j；不可用返回 None，调用方回退内存图算法。"""
    global _CRM_NEO4J_DRIVER, _CRM_NEO4J_READY
    if _CRM_NEO4J_READY:
        return _CRM_NEO4J_DRIVER
    _CRM_NEO4J_READY = True
    uri = os.getenv("NEO4J_URI", "").strip()
    if not uri or _Neo4jDriver is None:
        _CRM_NEO4J_DRIVER = None
        return None
    try:
        driver = _Neo4jDriver.driver(
            uri,
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "neo4j")),
            connection_timeout=2, max_connection_lifetime=600,
        )
        driver.verify_connectivity()
        _CRM_NEO4J_DRIVER = driver
    except Exception:
        _CRM_NEO4J_DRIVER = None
    return _CRM_NEO4J_DRIVER


# ---------------------------------------------------------------------------
# Redis 缓存
# ---------------------------------------------------------------------------

def crm_cache_key(username):
    return f"crm:overview:{safe_username(username)}"


def crm_cache_get(username):
    client = crm_redis()
    if not client:
        return None
    try:
        raw = client.get(crm_cache_key(username))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def crm_cache_set(username, data):
    client = crm_redis()
    if not client:
        return
    try:
        client.setex(crm_cache_key(username), CRM_CACHE_TTL, json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


def crm_cache_invalidate(username):
    client = crm_redis()
    if not client:
        return
    try:
        client.delete(crm_cache_key(username))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Neo4j 图谱投影：按用户子图整体重建（owner 命名空间隔离）
# ---------------------------------------------------------------------------

def crm_graph_sync_user(username):
    """从 JSON 重建该用户的关系子图。返回是否成功写入 Neo4j。"""
    driver = crm_neo4j()
    if not driver:
        return False
    owner = safe_username(username)
    units = crm_load(username, "units")
    people = crm_load(username, "people")
    relations = crm_load(username, "relations")
    # 组织按单位分组，用于生成同事边（二度引荐路径的桥）
    by_unit = {}
    for p in people.values():
        if p.get("unit_id"):
            by_unit.setdefault(p["unit_id"], []).append(p["id"])
    try:
        with driver.session() as session:
            session.execute_write(_crm_graph_rebuild_tx, owner, units, people, relations, by_unit)
        return True
    except Exception:
        return False


def _crm_graph_rebuild_tx(tx, owner, units, people, relations, by_unit):
    tx.run("MATCH (n {owner:$owner}) DETACH DELETE n", owner=owner)
    tx.run("MERGE (s:CrmSelf {owner:$owner})", owner=owner)
    for u in units.values():
        tx.run(
            "MERGE (x:CrmUnit {owner:$owner, uid:$uid}) SET x.name=$name, x.type=$type",
            owner=owner, uid=u["id"], name=u.get("name", ""), type=u.get("type", ""),
        )
    for p in people.values():
        tx.run(
            "MERGE (x:CrmPerson {owner:$owner, pid:$pid}) SET x.name=$name, x.influence=$inf",
            owner=owner, pid=p["id"], name=p.get("name", ""), inf=int(p.get("influence", 0) or 0),
        )
        if p.get("unit_id"):
            tx.run(
                "MATCH (a:CrmPerson {owner:$owner, pid:$pid}),(b:CrmUnit {owner:$owner, uid:$uid}) "
                "MERGE (a)-[:WORKS_AT {owner:$owner}]->(b)",
                owner=owner, pid=p["id"], uid=p["unit_id"],
            )
    for r in relations.values():
        if not r.get("person_id") or not r.get("our_member"):
            continue
        tx.run(
            "MATCH (s:CrmSelf {owner:$owner}),(t:CrmPerson {owner:$owner, pid:$pid}) "
            "MERGE (s)-[k:KNOWS {owner:$owner}]->(t) SET k.strength=$st, k.score=$sc",
            owner=owner, pid=r["person_id"], st=int(r.get("strength", 0) or 0), sc=int(r.get("score", 0) or 0),
        )
    # 同事边：同单位两两相连，作为引荐路径的中转
    for members in by_unit.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                tx.run(
                    "MATCH (a:CrmPerson {owner:$owner, pid:$p1}),(b:CrmPerson {owner:$owner, pid:$p2}) "
                    "MERGE (a)-[:COLLEAGUE {owner:$owner}]-(b)",
                    owner=owner, p1=members[i], p2=members[j],
                )


def crm_graph_shortest_path(username, target_person_id):
    """Neo4j 最短引荐路径：我方→目标客户人。返回节点名序列或 None。"""
    driver = crm_neo4j()
    if not driver:
        return None
    owner = safe_username(username)
    try:
        with driver.session() as session:
            record = session.run(
                "MATCH (s:CrmSelf {owner:$owner}),(t:CrmPerson {owner:$owner, pid:$pid}) "
                "MATCH p=shortestPath((s)-[:KNOWS|COLLEAGUE*..6]-(t)) "
                "RETURN [n IN nodes(p) | coalesce(n.name,'我方')] AS names, "
                "[n IN nodes(p) | CASE WHEN n:CrmSelf THEN 'self' ELSE n.pid END] AS ids, "
                "length(p) AS hops",
                owner=owner, pid=target_person_id,
            ).single()
        if not record:
            return None
        return {"names": record["names"], "ids": record["ids"], "hops": record["hops"], "source": "neo4j"}
    except Exception:
        return None


def crm_graph_centrality(username):
    """度中心度：每位客户人的连边数（KNOWS+COLLEAGUE），降序。"""
    driver = crm_neo4j()
    if not driver:
        return None
    owner = safe_username(username)
    try:
        with driver.session() as session:
            rows = session.run(
                "MATCH (p:CrmPerson {owner:$owner}) "
                "OPTIONAL MATCH (p)-[r {owner:$owner}]-() "
                "RETURN p.pid AS pid, p.name AS name, count(r) AS degree ORDER BY degree DESC",
                owner=owner,
            ).data()
        return rows
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 写操作后统一处理：失效缓存 + 异步同步图谱（Celery 不可用则内联同步）
# ---------------------------------------------------------------------------

def crm_on_change(username):
    if getattr(globals().get("CRM_IMPORT_CONTEXT"), "active", False):
        return
    crm_cache_invalidate(username)
    try:
        from backend.celery_app import crm_sync_graph_task
        crm_sync_graph_task.delay(username)
        return
    except Exception:
        pass
    # Celery/broker 不可用：尽力内联同步，失败静默（Neo4j 也可能未起）
    try:
        crm_graph_sync_user(username)
    except Exception:
        pass


def crm_infra_status():
    return {
        "redis": bool(crm_redis()),
        "neo4j": bool(crm_neo4j()),
        "redis_configured": bool(os.getenv("REDIS_URL", "").strip()),
        "neo4j_configured": bool(os.getenv("NEO4J_URI", "").strip()),
    }
