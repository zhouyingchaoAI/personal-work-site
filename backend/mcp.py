"""MCP (Model Context Protocol) server.

Exposes all platform Skill capabilities as MCP tools, compatible with
Claude Desktop, OpenClaw and any standard MCP client.

Transport : MCP Streamable HTTP (2025-03-26 spec), stateless POST-only mode.
Endpoint  : POST /mcp
Auth      : Authorization: Bearer <mcp_secret>  (set in admin → 服务器配置)
User ctx  : X-MCP-Username: <username>          (which user's data context)
Discovery : GET  /mcp                           (no auth, returns server info)

Configure mcp_secret via POST /api/mcp-config?generate=1 or from admin panel.
Leave mcp_secret empty to disable the MCP endpoint.
"""
from __future__ import annotations

MCP_PROTOCOL_VERSION = "2024-11-05"
_MCP_SERVER_INFO: dict = {"name": "personal-office-assistant", "version": "1.0.0"}
_MCP_CAPABILITIES: dict = {"tools": {}}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _mcp_secret() -> str:
    return str(read_config().get("mcp_secret", "") or "")


def mcp_enabled() -> bool:
    return bool(_mcp_secret())


def _check_auth(authorization: str) -> bool:
    secret = _mcp_secret()
    if not secret:
        return False
    return bool(authorization) and authorization.startswith("Bearer ") and authorization[7:].strip() == secret


# ---------------------------------------------------------------------------
# Skill → MCP tool conversion
# ---------------------------------------------------------------------------

def _params_to_json_schema(params) -> dict:
    """Convert a skill parameters dict to a JSON Schema properties object."""
    if not params or not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    properties: dict = {}
    for key, desc in params.items():
        if isinstance(desc, list):
            prop: dict = {"type": "array", "description": str(desc), "items": {}}
        elif isinstance(desc, dict):
            prop = {"type": "object", "description": str(desc)}
        else:
            d = str(desc)
            if any(kw in d for kw in ("数组", "array", "列表", "[]")):
                prop = {"type": "array", "description": d, "items": {}}
            elif any(kw in d for kw in ("对象", "object", "{}")):
                prop = {"type": "object", "description": d}
            elif any(kw in d for kw in ("整数", "integer", "int")):
                prop = {"type": "integer", "description": d}
            elif any(kw in d for kw in ("布尔", "boolean", "是否")):
                prop = {"type": "boolean", "description": d}
            else:
                prop = {"type": "string", "description": d}
        properties[key] = prop
    return {"type": "object", "properties": properties}


def _skill_to_mcp_tool(skill: dict) -> dict:
    module = skill.get("module", "")
    title = skill.get("title", "")
    desc = skill.get("description", "")
    safe = skill.get("safe", True)

    label = f"[{module} · {title}] " if module and title else (f"[{module or title}] " if module or title else "")
    warning = "（写入/生成/发送，请谨慎）" if not safe else ""
    return {
        "name": skill["name"],
        "description": f"{label}{desc}{warning}",
        "inputSchema": _params_to_json_schema(skill.get("parameters")),
    }


def _mcp_tools_list() -> list:
    return [_skill_to_mcp_tool(s) for s in skill_defs()]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def _mcp_call_tool(name: str, arguments: dict, username: str) -> dict:
    try:
        result = execute_skill(name, arguments, username, source="mcp")
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
    except Exception as exc:
        error_body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
        return {"content": [{"type": "text", "text": error_body}], "isError": True}


# ---------------------------------------------------------------------------
# JSON-RPC handling
# ---------------------------------------------------------------------------

def _handle_single_request(req: dict, username: str) -> dict | None:
    """Handle one JSON-RPC object. Returns None for pure notifications (no id field)."""
    method = req.get("method", "")
    params = req.get("params") or {}
    is_notification = "id" not in req
    req_id = req.get("id")

    def ok(result: dict) -> dict:
        r: dict = {"jsonrpc": "2.0", "result": result}
        if not is_notification:
            r["id"] = req_id
        return r

    def err(code: int, message: str) -> dict:
        r: dict = {"jsonrpc": "2.0", "error": {"code": code, "message": message}}
        if not is_notification:
            r["id"] = req_id
        return r

    if method == "initialize":
        return ok({
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": _MCP_CAPABILITIES,
            "serverInfo": _MCP_SERVER_INFO,
        })

    if method == "ping":
        return ok({})

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "tools/list":
        return ok({"tools": _mcp_tools_list()})

    if method == "tools/call":
        name = str(params.get("name", "") or "").strip()
        arguments = params.get("arguments") or {}
        if not name:
            return err(-32602, "name is required")
        if not isinstance(arguments, dict):
            return err(-32602, "arguments must be an object")
        return ok(_mcp_call_tool(name, arguments, username))

    return err(-32601, f"Method not found: {method}")


def mcp_handle_post(authorization: str, mcp_username: str, body_bytes: bytes) -> tuple[int, dict | list | None]:
    """
    Handle POST /mcp. Returns (http_status, response_body).
    Returns (204, None) for pure-notification messages.
    """
    if not mcp_enabled():
        return 501, {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "MCP server not enabled. Set mcp_secret in admin → 服务器配置."},
        }
    if not _check_auth(authorization):
        return 401, {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Unauthorized: invalid or missing Bearer token"},
        }

    username = (mcp_username or "").strip()

    try:
        body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return 400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: invalid JSON"}}

    if isinstance(body, list):
        responses = [_handle_single_request(r, username) for r in body if isinstance(r, dict)]
        responses = [r for r in responses if r is not None]
        return (204, None) if not responses else (200, responses)

    if not isinstance(body, dict):
        return 400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

    resp = _handle_single_request(body, username)
    return (204, None) if resp is None else (200, resp)


# ---------------------------------------------------------------------------
# Discovery and admin API
# ---------------------------------------------------------------------------

def mcp_info() -> dict:
    """Public server info for GET /mcp (no auth required)."""
    enabled = mcp_enabled()
    return {
        "server": _MCP_SERVER_INFO["name"],
        "version": _MCP_SERVER_INFO["version"],
        "protocol": f"MCP/{MCP_PROTOCOL_VERSION}",
        "transport": "Streamable HTTP",
        "endpoint": "POST /mcp",
        "enabled": enabled,
        "auth": "Authorization: Bearer <mcp_secret>",
        "user_context": "X-MCP-Username: <username>",
        "skill_count": len(skill_defs()) if enabled else 0,
    }


def mcp_config_api() -> dict:
    """Admin GET /api/mcp-config: return MCP configuration status."""
    config = read_config()
    secret = config.get("mcp_secret", "")
    return {
        "ok": True,
        "enabled": bool(secret),
        "mcp_secret_masked": "已配置" if secret else "未配置",
        "protocol_version": MCP_PROTOCOL_VERSION,
        "server_name": _MCP_SERVER_INFO["name"],
        "server_version": _MCP_SERVER_INFO["version"],
        "skill_count": len(skill_defs()),
        "endpoint_hint": "POST /mcp  |  Authorization: Bearer <mcp_secret>  |  X-MCP-Username: <username>",
    }


def save_mcp_config(payload: dict) -> dict:
    """Admin POST /api/mcp-config: save or generate MCP secret."""
    config = read_config()

    if payload.get("generate"):
        config["mcp_secret"] = secrets.token_urlsafe(32)
        write_config(config)
        return {
            "ok": True,
            "mcp_secret": config["mcp_secret"],
            "message": "新密钥已生成，请立即复制保存，此后不再明文显示",
        }

    if payload.get("clear"):
        config.pop("mcp_secret", None)
        write_config(config)
        return {"ok": True, "message": "MCP 密钥已清除，MCP 服务已禁用"}

    secret = str(payload.get("mcp_secret", "") or "").strip()
    if secret:
        if len(secret) < 16:
            raise ValueError("MCP 密钥至少 16 字符")
        config["mcp_secret"] = secret
        write_config(config)

    return mcp_config_api()
