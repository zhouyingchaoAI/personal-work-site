"""数据中台第三批：面向业务系统的标准数据访问接口（Data API）。

定位：业务系统统一从这里取数（只读）。默认保持现有 JSON / SQLite；source=database 使用结构化 PostgreSQL 镜像；
后续核心数据迁入 office-postgres 时只换本层实现，调用方不感知——因此
现有智能办公平台的业务读写逻辑保持不变，不做切换。

鉴权两种方式，二选一：
1. 平台内超级管理员会话（数据中台“数据接口”页签的在线测试用）。
2. 业务系统用 API Key：请求头 `X-Data-Api-Key`。密钥由超管在页面创建，
   仅保存 SHA-256 哈希（明文只在创建时展示一次），可吊销，记录最近使用。

每次取数写入访问留痕（access_log.jsonl，action=api）。所有数据集只读，
敏感字段沿用 dc_mask 脱敏，单次最多 500 条。
"""
import hashlib
import json
import secrets as _secrets
import sqlite3
import threading
from pathlib import Path

from backend.datacenter_lib import datacenter_dir, read_json, write_json_atomic

DAPI_MAX_LIMIT = 500
_dapi_key_lock = threading.Lock()


# ==================== 数据集注册表（同时就是接口文档） ====================
def _doc(key, group, name, desc, params, fields, source, note=""):
    return {"key": key, "group": group, "name": name, "desc": desc, "params": params,
            "fields": fields, "source": source, "note": note}

_P_OWNER = {"name": "owner", "required": True, "desc": "数据属主用户名（如 zhouyingchao）"}
_P_KW = {"name": "keyword", "required": False, "desc": "关键字过滤（名称类字段包含匹配）"}
_P_PAGE = [{"name": "limit", "required": False, "desc": "返回条数，默认 100，最大 500"},
           {"name": "offset", "required": False, "desc": "起始位置，默认 0"}]

DAPI_DATASETS = [
    _doc("crm.units", "联指经营助手", "客户单位", "五位一体客户单位档案", [_P_OWNER, _P_KW, *_P_PAGE],
         [("id", "单位 ID"), ("name", "单位名称"), ("type", "单位类型（主管/业主/总包/设计/厂商）"),
          ("region", "城市"), ("business_region", "经营区域"), ("updated_at", "更新时间")],
         "user_data/<owner>/crm/units.json"),
    _doc("crm.people", "联指经营助手", "客户联系人", "客户单位下的联系人档案", [_P_OWNER, _P_KW, *_P_PAGE],
         [("id", "联系人 ID"), ("name", "姓名"), ("unit_id", "所属单位 ID"), ("position", "职务"),
          ("importance", "重要程度"), ("support", "支持程度")],
         "user_data/<owner>/crm/people.json", "联系方式字段已脱敏"),
    _doc("crm.relations", "联指经营助手", "客户关系", "我方人员与客户联系人的对接关系", [_P_OWNER, *_P_PAGE],
         [("id", "关系 ID"), ("person_id", "联系人 ID"), ("our_staff", "我方对接人"),
          ("strength", "关系强度 L0–L5"), ("last_interaction_at", "最近互动")],
         "user_data/<owner>/crm/relations.json"),
    _doc("crm.actions", "联指经营助手", "跟进动作", "拜访、沟通等跟进记录", [_P_OWNER, *_P_PAGE],
         [("id", "动作 ID"), ("person_id", "联系人 ID"), ("kind", "动作类型"), ("occurred_at", "发生时间"),
          ("summary", "摘要")], "user_data/<owner>/crm/actions.json"),
    _doc("crm.opportunities", "联指经营助手", "商机", "在谈商机与阶段", [_P_OWNER, _P_KW, *_P_PAGE],
         [("id", "商机 ID"), ("name", "商机名称"), ("stage", "阶段"), ("owner_name", "负责人"),
          ("amount", "可参与份额")], "user_data/<owner>/crm/opportunities.json"),
    _doc("cashflow.history", "资金测算", "历史回款节点", "历史回款台账逐节点记录", [_P_OWNER, _P_KW, *_P_PAGE],
         [("project_name", "项目名称"), ("customer", "客户"), ("region", "区域"), ("project_type", "回款性质"),
          ("planned_amount", "计划回款"), ("received_amount", "实际回款"), ("received_date", "回款日期")],
         "user_data/<owner>/cashflow_history.json 的 records"),
    _doc("cashflow.insights", "资金测算", "回款规律洞察", "金额档位基线、客户信用评级、标准回款模型（整包返回）",
         [_P_OWNER], [("tiers", "金额档位基线"), ("customers", "客户评级明细"), ("patterns", "标准回款模型"),
                      ("conclusions", "四条结论")], "由历史回款实时计算", "计算耗时约 1–2 秒，建议调用方缓存"),
    _doc("ledger.items", "项目管理台账", "台账项目", "项目合同、交付、验收、回款台账", [_P_OWNER, _P_KW, *_P_PAGE],
         [("id", "台账 ID"), ("project_name", "项目名称"), ("stage", "阶段"), ("status", "状态"),
          ("contract_amount", "合同金额"), ("received_amount", "已回款")],
         "user_data/<owner>/operating_ledger.json"),
    _doc("org.staff", "组织与协作", "员工目录", "全平台员工目录（含区域与岗位）", [_P_KW, *_P_PAGE],
         [("username", "账号"), ("name", "姓名"), ("employee_id", "工号"), ("region", "区域"), ("position", "岗位")],
         "user_data/_crm_staff_directory.json"),
    _doc("tickets.list", "组织与协作", "平台工单", "各助手的问题与需求工单", [_P_KW, *_P_PAGE],
         [("id", "工单 ID"), ("module", "所属助手"), ("title", "标题"), ("status", "状态"), ("created_by", "提交人")],
         "user_data/_tickets/tickets.json"),
    _doc("forum.topics", "组织与协作", "论坛主题", "金点子论坛主题列表", [_P_KW, *_P_PAGE],
         [("id", "主题 ID"), ("title", "标题"), ("author", "作者"), ("created_at", "创建时间")],
         "user_data/_forum/topics.json"),
    _doc("agent.skill_invocations", "智能体", "技能调用记录", "平台技能被调用的历史", [*_P_PAGE],
         [("id", "记录 ID"), ("username", "调用人"), ("skill", "技能"), ("status", "状态"), ("created_at", "时间")],
         "user_data/app.db 表 skill_invocations"),
    _doc("meta.assets", "数据中台", "数据资产快照", "分级容量与模块清单（与资产总览一致）", [],
         [("levels", "A/B/C/D 汇总"), ("modules", "模块明细"), ("history", "逐日容量")], "_datacenter/scan.json"),
    _doc("meta.backups", "数据中台", "备份记录", "最近备份运行记录与状态", [],
         [("runs", "最近 30 次"), ("status", "心跳与下次计划")], "_datacenter/backups.json"),
]
DAPI_INDEX = {d["key"]: d for d in DAPI_DATASETS}


# ==================== API Key 管理 ====================
def _dapi_keys_path():
    return datacenter_dir(USER_DATA_DIR) / "api_keys.json"


def dapi_list_keys():
    keys = read_json(_dapi_keys_path(), [])
    return {"ok": True, "keys": [{k: v for k, v in item.items() if k != "hash"} for item in keys]}


def dapi_create_key(payload, username):
    name = str(payload.get("name", "")).strip()[:60]
    if not name:
        raise ValueError("请为密钥取一个名字（如：经营分析看板）")
    token = "dck_" + _secrets.token_urlsafe(30)
    with _dapi_key_lock:
        keys = read_json(_dapi_keys_path(), [])
        if any(k.get("name") == name and not k.get("revoked_at") for k in keys):
            raise ValueError("已存在同名密钥，请换一个名字或先吊销旧密钥")
        keys.append({"id": "key-" + _secrets.token_hex(5), "name": name, "prefix": token[:10] + "…",
                     "hash": hashlib.sha256(token.encode()).hexdigest(),
                     "created_by": username, "created_at": datetime.now().isoformat(timespec="seconds"),
                     "last_used_at": "", "calls": 0, "revoked_at": ""})
        write_json_atomic(_dapi_keys_path(), keys)
    dc_audit(username, "apikey-create", name)
    return {"ok": True, "token": token, "note": "密钥只显示这一次，请立即保存；服务端仅保存哈希"}


def dapi_revoke_key(payload, username):
    key_id = str(payload.get("id", ""))
    with _dapi_key_lock:
        keys = read_json(_dapi_keys_path(), [])
        target = next((k for k in keys if k.get("id") == key_id), None)
        if not target:
            raise ValueError("密钥不存在")
        target["revoked_at"] = datetime.now().isoformat(timespec="seconds")
        write_json_atomic(_dapi_keys_path(), keys)
    dc_audit(username, "apikey-revoke", target.get("name", key_id))
    return {"ok": True}


def dapi_auth_key(token):
    """校验 API Key，返回密钥名；无效返回 None。"""
    if not token or not token.startswith("dck_"):
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _dapi_key_lock:
        keys = read_json(_dapi_keys_path(), [])
        for k in keys:
            if k.get("hash") == digest and not k.get("revoked_at"):
                k["last_used_at"] = datetime.now().isoformat(timespec="seconds")
                k["calls"] = int(k.get("calls") or 0) + 1
                write_json_atomic(_dapi_keys_path(), keys)
                return k.get("name") or "api-key"
    return None


# ==================== 取数实现 ====================
def _dapi_owner_root(owner):
    owner = safe_username(owner)
    root = Path(USER_DATA_DIR) / owner
    if not root.is_dir():
        raise ValueError(f"数据属主 {owner} 不存在")
    return root


def _dapi_page(items, params):
    try:
        limit = min(DAPI_MAX_LIMIT, max(1, int(params.get("limit") or 100)))
        offset = max(0, int(params.get("offset") or 0))
    except ValueError:
        raise ValueError("limit / offset 必须是数字")
    return items[offset:offset + limit], {"total": len(items), "limit": limit, "offset": offset}


def _dapi_kw(items, params, keys=("name", "title", "project_name", "customer", "summary")):
    kw = str(params.get("keyword") or "").strip()
    if not kw:
        return items
    return [it for it in items if any(kw in str(it.get(k, "")) for k in keys)]


def _dapi_crm(owner, filename):
    root = _dapi_owner_root(owner)
    data = crmdb_load(owner, filename.removesuffix(".json")) if crmdb_enabled() else read_json(root / "crm" / filename, {})
    items = list(data.values()) if isinstance(data, dict) else (data or [])
    return sorted(items, key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)


def dapi_query(dataset, params, caller):
    doc = DAPI_INDEX.get(dataset)
    if not doc:
        raise ValueError(f"数据集不存在：{dataset}（可用：GET /api/datacenter/datasets）")
    for p in doc["params"]:
        if p.get("required") and not str(params.get(p["name"]) or "").strip():
            raise ValueError(f"缺少必填参数 {p['name']}：{p['desc']}")
    owner = str(params.get("owner") or "").strip()
    start = datetime.now()
    source = str(params.get("source") or "live")
    if source not in ("live", "database"):
        raise ValueError("source 只能为 live 或 database")
    from backend.datacenter_sql import MODELS as sql_models, query_structured
    if source == "database":
        if dataset not in sql_models:
            raise ValueError("该数据集仍使用实时原存储，暂不支持数据库查询")
        try:
            result = query_structured(dataset, params)
        except ValueError:
            raise
        except Exception:
            dc_audit(caller, "api-failed", dataset, "source=database")
            raise RuntimeError("数据库镜像查询暂不可用，请稍后重试或明确选择实时原存储") from None
        result["items"] = [dc_mask(item) for item in result["items"]]
        if crmdb_enabled() and (dataset.startswith("crm.") or dataset == "org.staff"):
            result["storage_role"] = "primary"
            result["synced_at"] = None
        dc_audit(caller, "api", dataset, json.dumps({k:v for k,v in params.items() if v}, ensure_ascii=False)[:200])
        return {"ok": True, "dataset": dataset, "took_ms": round((datetime.now()-start).total_seconds()*1000), **result}
    if any(value not in (None, "") and key not in {"owner", "keyword", "limit", "offset", "source"} for key,value in params.items()):
        raise ValueError("扩展筛选参数仅用于 source=database，请选择数据库镜像")
    if dataset.startswith("crm."):
        items = _dapi_crm(owner, dataset.split(".")[1] + ".json")
        items, page = _dapi_page(_dapi_kw(items, params), params)
        result = {"items": dc_mask(items), **page}
    elif dataset == "cashflow.history":
        records = (read_json(_dapi_owner_root(owner) / "cashflow_history.json", {}) or {}).get("records") or []
        items, page = _dapi_page(_dapi_kw(records, params), params)
        result = {"items": items, **page}
    elif dataset == "cashflow.insights":
        records = (read_json(_dapi_owner_root(owner) / "cashflow_history.json", {}) or {}).get("records") or []
        if not records:
            raise ValueError(f"{owner} 没有历史回款数据")
        result = {"insights": cashflow_history_insights(records)}
    elif dataset == "ledger.items":
        items = read_json(_dapi_owner_root(owner) / "operating_ledger.json", [])
        items, page = _dapi_page(_dapi_kw(items, params), params)
        result = {"items": items, **page}
    elif dataset == "org.staff":
        data = crmdb_staff_directory() if crmdb_enabled() else read_json(Path(USER_DATA_DIR) / "_crm_staff_directory.json", {})
        items = list(data.values()) if isinstance(data, dict) else (data or [])
        items, page = _dapi_page(_dapi_kw(items, params, ("name", "username", "region", "position")), params)
        result = {"items": dc_mask(items), **page}
    elif dataset == "tickets.list":
        data = read_json(Path(USER_DATA_DIR) / "_tickets" / "tickets.json", {})
        items = data.get("tickets") if isinstance(data, dict) else data
        items, page = _dapi_page(_dapi_kw(items or [], params, ("title", "module", "status")), params)
        result = {"items": dc_mask(items), **page}
    elif dataset == "forum.topics":
        data = read_json(Path(USER_DATA_DIR) / "_forum" / "topics.json", {})
        items = data.get("topics") if isinstance(data, dict) else data
        items, page = _dapi_page(_dapi_kw(items or [], params, ("title", "author")), params)
        result = {"items": dc_mask(items), **page}
    elif dataset == "agent.skill_invocations":
        with sqlite3.connect(f"file:{Path(USER_DATA_DIR) / 'app.db'}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM skill_invocations").fetchone()[0]
            limit = min(DAPI_MAX_LIMIT, max(1, int(params.get("limit") or 100)))
            offset = max(0, int(params.get("offset") or 0))
            rows = conn.execute("SELECT * FROM skill_invocations ORDER BY id DESC LIMIT ? OFFSET ?",
                                (limit, offset)).fetchall()
            result = {"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}
    elif dataset == "meta.assets":
        scan = read_json(datacenter_dir(USER_DATA_DIR) / "scan.json", {})
        result = {"levels": scan.get("levels"), "modules": scan.get("modules"),
                  "history": scan.get("history"), "generated_at": scan.get("generated_at")}
    elif dataset == "meta.backups":
        result = {"runs": read_json(datacenter_dir(USER_DATA_DIR) / "backups.json", [])[-30:],
                  "status": read_json(datacenter_dir(USER_DATA_DIR) / "backup_status.json", {})}
    else:  # pragma: no cover —— 注册表与实现不同步时显式报错
        raise ValueError(f"数据集 {dataset} 未实现")
    took = round((datetime.now() - start).total_seconds() * 1000)
    dc_audit(caller, "api", dataset, json.dumps({k: v for k, v in params.items() if v}, ensure_ascii=False)[:200])
    return {"ok": True, "dataset": dataset, "took_ms": took, "source": "live", **result}


def dapi_catalog():
    from backend.datacenter_sql import MODELS as sql_models
    datasets = []
    for doc in DAPI_DATASETS:
        entry = {**doc, "params": list(doc["params"])}
        primary = crmdb_enabled() and (doc["key"].startswith("crm.") or doc["key"] == "org.staff")
        if primary:
            entry["source"] = "office-postgres · " + ("crm.staff_directory" if doc["key"] == "org.staff" else doc["key"])
        model = sql_models.get(doc["key"])
        if model:
            entry["database_table"] = model["table"]
            entry["typed_fields"] = [{"name": name, "type": kind, "source_field": field} for name,(kind,field) in model["fields"].items()]
            entry["params"].append({"name":"source", "required":False, "desc": "live：业务主存储；database：PostgreSQL 主库结构化查询（已切库）" if primary else "live：实时原存储（默认）；database：PostgreSQL 镜像，非实时，响应 synced_at 标明同步时间"})
            entry["params"].extend({"name":field,"required":False,"desc":"仅 database：精确匹配 "+field} for field in model["filters"])
            if model.get("date"):
                entry["params"].extend({"name":p,"required":False,"desc":"仅 database："+model["date"]+" 的闭区间，YYYY-MM-DD"} for p in ("date_from","date_to"))
            if model.get("amount"):
                entry["params"].extend({"name":p,"required":False,"desc":"仅 database："+model["amount"]+" 的闭区间，单位沿用业务原数据"} for p in ("min_amount","max_amount"))
                entry["params"].append({"name":"summary","required":False,"desc":"仅 database：1 返回筛选结果全部金额汇总，金额为十进制字符串；0 不汇总"})
            entry["note"] += "；数据库按索引筛选、排序、分页；保留原文返回格式。新增 summary/synced_at/source 元数据；非法日期/金额保留原文，类型列为 NULL 并计数。"
        datasets.append(entry)
    return {"ok": True, "datasets": datasets, "base_url": "/api/datacenter/data",
            "auth": {"header": "X-Data-Api-Key",
                     "note": "业务系统用 API Key 调用；平台内超级管理员会话可直接调用（在线测试）"},
            "readonly": True, "max_limit": DAPI_MAX_LIMIT}
