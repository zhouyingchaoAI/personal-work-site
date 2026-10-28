"""FastGPT provisioning bridge for the office assistant.

FastGPT treats an MCP Tools collection as a first-class node source.  This
module keeps that collection and FastGPT's OpenAI-compatible model entry in
sync with the single configuration screen of the office assistant.
"""
from __future__ import annotations


FASTGPT_INTERNAL_URL = os.getenv("FASTGPT_INTERNAL_URL", "http://fastgpt-app:3000").rstrip("/")
FASTGPT_SSO_URL = os.getenv("FASTGPT_SSO_URL", "http://fastgpt-sso:3100").rstrip("/")
FASTGPT_SSO_SECRET = os.getenv("FASTGPT_SSO_SECRET", "office_fastgpt_sso_9Rm4Kv7Lx2Np8Qw")
FASTGPT_MCP_HOST = os.getenv("FASTGPT_MCP_HOST", "http://personal-work-site:8765").rstrip("/")
FASTGPT_EMBEDDING_URL = os.getenv("FASTGPT_EMBEDDING_URL", "http://xinference-gpu:9997/v1").rstrip("/")
FASTGPT_AIPROXY_URL = os.getenv("FASTGPT_AIPROXY_URL", "http://fastgpt-aiproxy:3000").rstrip("/")
FASTGPT_AIPROXY_TOKEN = os.getenv("FASTGPT_AIPROXY_TOKEN", "")


def _fastgpt_request(path, payload, token, timeout=45):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        FASTGPT_INTERNAL_URL + path,
        data=data,
        headers={"Content-Type": "application/json", "Cookie": "fastgpt_token=" + token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if int(result.get("code", 200) or 200) >= 400:
        raise RuntimeError(result.get("message") or "FastGPT 请求失败")
    return result.get("data")


def _fastgpt_get(path, token, timeout=45):
    """Call a FastGPT read API using the same authenticated session."""
    request = urllib.request.Request(
        FASTGPT_INTERNAL_URL + path,
        headers={"Cookie": "fastgpt_token=" + token},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if int(result.get("code", 200) or 200) >= 400:
        raise RuntimeError(result.get("message") or "FastGPT 请求失败")
    return result.get("data")


def _aiproxy_request(path, method="GET", payload=None, timeout=45):
    """Call FastGPT v4.15's active AIProxy configuration API."""
    if not FASTGPT_AIPROXY_TOKEN:
        raise RuntimeError("未配置 FASTGPT_AIPROXY_TOKEN，无法同步 FastGPT 模型提供商")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        FASTGPT_AIPROXY_URL + "/api/" + path.lstrip("/"), data=data,
        headers={"Content-Type": "application/json", "Authorization": FASTGPT_AIPROXY_TOKEN},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("success", False):
        raise RuntimeError(result.get("message") or "AIProxy 请求失败")
    return result.get("data")


def _fastgpt_token(username="admin", system=False):
    path = "/system-token" if system else "/login"
    payload = {"username": username, "name": "办公助手", "role": "superadmin"}
    request = urllib.request.Request(
        FASTGPT_SSO_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Office-SSO-Secret": FASTGPT_SSO_SECRET},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        token = str(json.loads(response.read().decode("utf-8")).get("token") or "")
    if not token:
        raise RuntimeError("FastGPT 单点登录未返回令牌")
    return token


def fastgpt_mcp_url(username="admin"):
    secret = str(read_config().get("mcp_secret", "") or "")
    if not secret:
        raise ValueError("MCP 服务未启用，请先生成 MCP 密钥")
    return FASTGPT_MCP_HOST + "/mcp?" + urllib.parse.urlencode({"access_token": secret, "username": username})


def _model_metadata(settings):
    """The minimal, version-stable FastGPT system model metadata contract."""
    return {
        "type": "llm",
        "model": settings["model"],
        "name": "办公助手 · " + settings["model"],
        "provider": "Office OpenAI API",
        # FastGPT v4.15 only exposes records with this flag in
        # `activeModelList`; an otherwise valid custom record remains hidden.
        "isActive": True,
        "isDefault": True,
        "contextToken": 128000,
        "maxResponse": 8192,
        "toolChoice": True,
        "defaultConfig": {
            "baseUrl": settings["url"].rstrip("/") + "/v1",
            "apiKey": settings["key"],
        },
    }


def sync_fastgpt_model():
    """Upsert the configured OpenAI-compatible model without replacing others."""
    settings = merged_assistant_config()
    if not settings.get("url") or not settings.get("key") or not settings.get("model"):
        return {"ok": False, "skipped": True, "message": "办公助手大模型配置不完整，已跳过 FastGPT 模型同步"}
    token = _fastgpt_token(system=True)
    raw = _fastgpt_request("/api/core/ai/model/getConfigJson", {}, token)
    entries = json.loads(raw or "[]") if isinstance(raw, str) else list(raw or [])
    entry = {"model": settings["model"], "metadata": _model_metadata(settings)}
    entries = [item for item in entries if str(item.get("model") or "") != settings["model"]]
    entries.append(entry)
    _fastgpt_request("/api/core/ai/model/updateWithJson", {"config": json.dumps(entries, ensure_ascii=False)}, token)
    return {"ok": True, "model": settings["model"], "base_url": settings["url"]}


def _openai_v1_url(url):
    """Normalize platform OpenAI-compatible service URLs for FastGPT."""
    base = str(url or "").strip().rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def _fastgpt_embedding_metadata(settings):
    return {
        "type": "embedding",
        "model": settings["model"],
        "name": "办公助手 · 嵌入 · " + settings["model"],
        "provider": "Office Embedding API",
        "isActive": True,
        "isDefault": True,
        "contextToken": 32768,
        # FastGPT 用 defaultToken 计算知识库切块大小；缺失会导致训练报
        # "Chunk size must be a positive finite number"，知识库（含 API 文件库）无法入库。
        "defaultToken": 512,
        "maxToken": 3000,
        "weight": 0,
        # FastGPT requires a non-empty key in model metadata even for a local,
        # unauthenticated OpenAI-compatible service. Xinference ignores it.
        "defaultConfig": {
            "baseUrl": _openai_v1_url(settings["api_url"]),
            "apiKey": settings.get("api_key") or "local-no-auth",
        },
    }


def _fastgpt_rerank_metadata(settings):
    return {
        "type": "rerank",
        "model": settings["rerank_model"],
        "name": "办公助手 · 重排 · " + settings["rerank_model"],
        "provider": "Office Rerank API",
        "isActive": True,
        "contextToken": 32768,
        "defaultConfig": {
            "baseUrl": _openai_v1_url(settings["api_url"]),
            "apiKey": settings.get("api_key") or "local-no-auth",
        },
    }


def _fastgpt_tool_intro(tool):
    """Build a usable FastGPT picker description from an MCP tool schema."""
    name = str(tool.get("name") or "工具")
    description = str(tool.get("description") or "执行办公助手能力。")
    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields = []
    for key, value in properties.items():
        value = value or {}
        kind = str(value.get("type") or "参数")
        label = str(value.get("description") or key)
        fields.append(f"{key}（{kind}{'，必填' if key in required else '，可选'}）：{label}")
    parameter_text = "；".join(fields) if fields else "无参数。"
    safety = "\n注意：该工具会产生写入、发送或外部调用，请由 Agent 在确认信息完整后调用。" if any(
        word in (name + " " + description).lower()
        for word in ("create", "send", "delete", "subscribe", "unsubscribe", "generate", "写入", "发送", "删除", "订阅")
    ) else ""
    return (
        f"用途：{description}\n"
        "使用：从“我的工具”拖入工作流，并连接到 Agent 节点的“工具”输入；由 Agent 按任务自动调用。\n"
        f"参数：{parameter_text}" + safety
    )


def sync_fastgpt_embedding_model():
    """Upsert the platform-configured embedding and optional rerank models.

    This deliberately reads the same knowledge-base settings used by the
    platform, instead of assuming a container name or a particular model.
    """
    settings = kb_embedding_settings()
    if not settings.get("api_url") or not settings.get("model"):
        return {"ok": False, "skipped": True, "message": "平台嵌入模型配置不完整，已跳过 FastGPT 同步"}
    token = _fastgpt_token(system=True)
    raw = _fastgpt_request("/api/core/ai/model/getConfigJson", {}, token)
    entries = json.loads(raw or "[]") if isinstance(raw, str) else list(raw or [])
    managed = {str(settings["model"])}
    if settings.get("rerank_model"):
        managed.add(str(settings["rerank_model"]))
    # Retire the former hard-coded fallback only when it is not the configured
    # platform model, avoiding a stale choice in FastGPT's knowledge-base UI.
    if settings["model"] != "bge-m3":
        managed.add("bge-m3")
    entries = [item for item in entries if str(item.get("model") or "") not in managed]
    entries.append({"model": settings["model"], "metadata": _fastgpt_embedding_metadata(settings)})
    if settings.get("rerank_model"):
        entries.append({"model": settings["rerank_model"], "metadata": _fastgpt_rerank_metadata(settings)})
    _fastgpt_request("/api/core/ai/model/updateWithJson", {"config": json.dumps(entries, ensure_ascii=False)}, token)
    return {
        "ok": True,
        "model": settings["model"],
        "base_url": _openai_v1_url(settings["api_url"]),
        "rerank_model": settings.get("rerank_model") or "",
    }


def _aiproxy_upsert_channel(name, key, base_url, models):
    """Create/update an OpenAI-compatible provider channel idempotently."""
    channels = _aiproxy_request("channels/all") or []
    existing = next((item for item in channels if item.get("name") == name), None)
    payload = {
        # AIProxy provider type 1 is OpenAI-compatible, covering chat,
        # embeddings and rerank endpoints.
        "type": 1, "name": name, "key": key or "local-no-auth",
        "base_url": _openai_v1_url(base_url), "proxy_url": "",
        "models": list(dict.fromkeys(item for item in models if item)),
        # Empty sets is AIProxy's default/public model set. A named set would
        # hide the provider from FastGPT accounts that have not been assigned
        # that exact set, which is why the model page appeared empty.
        "model_mapping": {}, "sets": [], "priority": 10,
        "skip_tls_verify": False, "enabled_no_permission_ban": False,
        "max_error_rate": 0,
    }
    if existing:
        _aiproxy_request(f"channel/{existing['id']}", "PUT", payload)
        return str(existing["id"])
    _aiproxy_request("channel/", "POST", payload)
    channels = _aiproxy_request("channels/all") or []
    created = next((item for item in channels if item.get("name") == name), None)
    if not created:
        raise RuntimeError("AIProxy 模型提供商创建后未找到：" + name)
    return str(created["id"])


def _aiproxy_upsert_model(model, model_type, config):
    """Upsert a model visible in FastGPT's 模型提供商 page."""
    payload = {
        "model": model, "type": model_type, "owner": "办公助手平台",
        "config": config, "retry_times": 1, "timeout": 120,
        "stream_timeout": 180, "exclude_from_tests": False,
    }
    # AIProxy's POST endpoint is intentionally an upsert for a model name.
    _aiproxy_request("model_config/" + urllib.parse.quote(model, safe=""), "POST", payload)


def sync_fastgpt_aiproxy_models():
    """Sync platform model services to the FastGPT v4.15 UI/runtime source."""
    llm = merged_assistant_config()
    embedding = kb_embedding_settings()
    if not (llm.get("url") and llm.get("key") and llm.get("model")):
        return {"ok": False, "skipped": True, "message": "平台大模型配置不完整，已跳过 AIProxy 同步"}
    if not (embedding.get("api_url") and embedding.get("model")):
        return {"ok": False, "skipped": True, "message": "平台嵌入模型配置不完整，已跳过 AIProxy 同步"}

    llm_channel = _aiproxy_upsert_channel(
        "办公助手平台 · 大模型", llm["key"], llm["url"], [llm["model"]],
    )
    embedding_models = [embedding["model"]]
    if embedding.get("rerank_model"):
        embedding_models.append(embedding["rerank_model"])
    embedding_channel = _aiproxy_upsert_channel(
        "办公助手平台 · 嵌入与重排", embedding.get("api_key") or "", embedding["api_url"], embedding_models,
    )
    _aiproxy_upsert_model(llm["model"], 1, {
        "max_input_tokens": 128000, "max_output_tokens": 8192,
        "max_context_tokens": 128000, "tool_choice": True,
    })
    # AIProxy mode 3 is /embeddings; mode 10 is /rerank.
    _aiproxy_upsert_model(embedding["model"], 3, {"max_input_tokens": 32768, "max_context_tokens": 32768})
    if embedding.get("rerank_model"):
        _aiproxy_upsert_model(embedding["rerank_model"], 10, {"max_input_tokens": 32768, "max_context_tokens": 32768})
    return {
        "ok": True, "llm": llm["model"], "embedding": embedding["model"],
        "rerank": embedding.get("rerank_model") or "", "channels": [llm_channel, embedding_channel],
    }


def sync_fastgpt_mcp(username="admin"):
    """Parse all office MCP tools in FastGPT and create/update one collection."""
    url = fastgpt_mcp_url(username)
    token = _fastgpt_token(username)
    tools = _fastgpt_request("/api/core/app/mcpTools/getTools", {"url": url}, token)
    if not isinstance(tools, list) or not tools:
        raise RuntimeError("FastGPT 未能从办公助手 MCP 发现任何工具")
    config = read_config()
    payload = {"name": "办公助手 MCP 工具", "url": url, "toolList": tools}
    app_id = str(config.get("fastgpt_mcp_app_id", "") or "")
    # FastGPT v4.15's create endpoint intentionally returns an empty body.  On
    # first provisioning locate the collection through its supported list API,
    # so all later config saves update the same node collection instead of
    # producing duplicates.
    if not app_id:
        apps = _fastgpt_request("/api/core/app/list", {}, token)
        found = next((app for app in (apps or []) if app.get("name") == payload["name"] and app.get("type") == "toolSet"), None)
        app_id = str((found or {}).get("_id") or "")
    if app_id:
        try:
            data = _fastgpt_request("/api/core/app/mcpTools/update", {**payload, "appId": app_id}, token)
        except Exception:
            data = _fastgpt_request("/api/core/app/mcpTools/create", payload, token)
    else:
        data = _fastgpt_request("/api/core/app/mcpTools/create", payload, token)
    if isinstance(data, dict):
        app_id = str(data.get("appId") or data.get("_id") or app_id)
    if app_id:
        config["fastgpt_mcp_app_id"] = app_id
        config["fastgpt_mcp_username"] = username
        write_config(config)
    return {"ok": True, "tool_count": len(tools), "app_id": app_id, "username": username}


def sync_fastgpt_mcp_server():
    """Publish every collection child as a FastGPT outward MCP tool.

    A tool-set app is only a *collection node* in FastGPT.  Associating that
    node with an outward MCP service exposes one opaque wrapper, rather than
    the tools inside it.  ``getChildren`` supplies FastGPT's virtual child app
    IDs; those are the IDs an MCP service must associate individually.
    """
    config = read_config()
    app_id = str(config.get("fastgpt_mcp_app_id") or "")
    if not app_id:
        raise RuntimeError("办公助手 MCP 工具集合尚未创建")
    token = _fastgpt_token("admin")
    # A virtual child ID cannot be associated with a service (FastGPT validates
    # appId as a Mongo ObjectId).  Materialize a one-tool tool-set per Skill;
    # they remain backed by the same platform MCP endpoint and give the outward
    # service a real app ID for each independent callable tool.
    source_url = fastgpt_mcp_url("admin")
    tools = _fastgpt_request("/api/core/app/mcpTools/getTools", {"url": source_url}, token)
    if not isinstance(tools, list) or not tools:
        raise RuntimeError("办公助手 MCP 工具集合中没有可发布的工具")

    all_apps = _fastgpt_request("/api/core/app/list", {}, token)
    apps = []
    materialized_ids = {}
    for tool in tools:
        tool_name = str(tool.get("name") or "").strip()
        if not tool_name:
            continue
        node_name = "办公助手 MCP · " + tool_name
        node = next((item for item in (all_apps or []) if item.get("name") == node_name and item.get("type") == "toolSet"), None)
        payload = {"name": node_name, "url": source_url, "toolList": [tool]}
        if node:
            node_id = str(node["_id"])
            _fastgpt_request("/api/core/app/mcpTools/update", {**payload, "appId": node_id}, token)
        else:
            _fastgpt_request("/api/core/app/mcpTools/create", payload, token)
            all_apps = _fastgpt_request("/api/core/app/list", {}, token)
            node = next((item for item in (all_apps or []) if item.get("name") == node_name and item.get("type") == "toolSet"), None)
            if not node:
                raise RuntimeError("FastGPT 单工具节点创建后未找到：" + tool_name)
            node_id = str(node["_id"])
        # ``mcpTools/create/update`` preserves an empty app intro. The
        # workflow picker displays this field in its detail popover, so fill
        # it explicitly with the MCP tool's human-readable description.
        _fastgpt_request(
            "/api/core/app/update?appId=" + urllib.parse.quote(node_id, safe=""),
            {"intro": _fastgpt_tool_intro(tool)}, token,
        )
        materialized_ids[tool_name] = node_id
        apps.append({
            "appId": node_id,
            "toolName": tool_name,
            "description": str(tool.get("description") or tool_name),
        })

    # FastGPT limits one outward MCP service to 50 linked applications. Keep
    # the split deterministic so a later sync updates the same services.
    service_specs = [
        ("办公助手平台 MCP 服务", apps[:50]),
        ("办公助手平台 MCP 服务（续）", apps[50:]),
    ]
    servers = _fastgpt_request("/api/support/mcp/list", {}, token)
    server_ids = []
    for name, linked_apps in service_specs:
        if not linked_apps:
            continue
        existing = next((item for item in (servers or []) if item.get("name") == name), None)
        if existing:
            _fastgpt_request("/api/support/mcp/update", {
                "id": str(existing["_id"]), "apps": linked_apps,
            }, token)
            server_ids.append(str(existing["_id"]))
        else:
            _fastgpt_request("/api/support/mcp/create", {"name": name, "apps": linked_apps}, token)
            refreshed = _fastgpt_request("/api/support/mcp/list", {}, token)
            created = next((item for item in (refreshed or []) if item.get("name") == name), None)
            if not created:
                raise RuntimeError("FastGPT MCP 服务创建后未找到")
            server_ids.append(str(created["_id"]))
            servers = refreshed
    config["fastgpt_mcp_server_id"] = server_ids[0] if server_ids else ""
    config["fastgpt_mcp_server_ids"] = server_ids
    config["fastgpt_mcp_tool_app_ids"] = materialized_ids
    write_config(config)
    return {
        "ok": True,
        "server_id": config["fastgpt_mcp_server_id"],
        "server_ids": server_ids,
        "tool_count": len(apps),
        "service_count": len(server_ids),
    }


def sync_fastgpt(username="admin"):
    """Synchronize nodes first, then model settings; return per-part outcomes."""
    result = {"ok": True, "mcp": None, "mcp_server": None, "model": None, "embedding": None, "aiproxy": None}
    try:
        result["mcp"] = sync_fastgpt_mcp(username)
    except Exception as exc:
        result["ok"] = False
        result["mcp"] = {"ok": False, "error": str(exc)}
    try:
        result["mcp_server"] = sync_fastgpt_mcp_server()
    except Exception as exc:
        result["ok"] = False
        result["mcp_server"] = {"ok": False, "error": str(exc)}
    try:
        result["model"] = sync_fastgpt_model()
        result["ok"] = bool(result["ok"] and result["model"].get("ok", False))
    except Exception as exc:
        result["ok"] = False
        result["model"] = {"ok": False, "error": str(exc)}
    try:
        result["embedding"] = sync_fastgpt_embedding_model()
        result["ok"] = bool(result["ok"] and result["embedding"].get("ok", False))
    except Exception as exc:
        result["ok"] = False
        result["embedding"] = {"ok": False, "error": str(exc)}
    try:
        result["aiproxy"] = sync_fastgpt_aiproxy_models()
        result["ok"] = bool(result["ok"] and result["aiproxy"].get("ok", False))
    except Exception as exc:
        result["ok"] = False
        result["aiproxy"] = {"ok": False, "error": str(exc)}
    return result


def sync_fastgpt_user_collections():
    """Eagerly provision each account's private, identity-bound MCP nodes."""
    users = [str(item.get("username") or "").strip() for item in read_config().get("users", [])]
    results = []
    for username in (item for item in users if item):
        try:
            _fastgpt_token(username)
            results.append({"username": username, "ok": True})
        except Exception as exc:
            results.append({"username": username, "ok": False, "error": str(exc)})
    return {"ok": all(item["ok"] for item in results), "users": results}


def fastgpt_config_api():
    config = read_config()
    return {
        "ok": True,
        "mcp_enabled": mcp_enabled(),
        "mcp_tool_count": len(skill_defs()),
        "collection_app_id": config.get("fastgpt_mcp_app_id", ""),
        "server_id": config.get("fastgpt_mcp_server_id", ""),
        "collection_username": config.get("fastgpt_mcp_username", "admin"),
        "model": merged_assistant_config().get("model", ""),
        "model_configured": bool(merged_assistant_config().get("url") and merged_assistant_config().get("key")),
        "embedding_model": kb_embedding_settings().get("model", ""),
        "embedding_configured": bool(kb_embedding_settings().get("api_url") and kb_embedding_settings().get("model")),
        "message": "保存办公助手的大模型配置后会自动同步；也可在此手动重新同步。",
    }
