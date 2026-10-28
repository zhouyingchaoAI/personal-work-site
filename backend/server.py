"""HTTP request handler and application startup.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

import gzip as _gzip


def app_html():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


# ---- Response compression -------------------------------------------------
# The app is reached through reverse proxies that do not compress, so JSON and
# hashed static assets are gzipped here. CRM snapshots alone are ~3 MB per load.
GZIP_MIN_BYTES = 1024
GZIP_TYPES = ("text/", "application/json", "application/javascript", "text/javascript",
              "application/wasm", "image/svg+xml", "application/xml")
_ASSET_GZIP_CACHE = {}
_ASSET_GZIP_CACHE_LOCK = threading.Lock()
_ASSET_GZIP_CACHE_LIMIT = 48 * 1024 * 1024  # compressed bytes kept in memory


def _client_accepts_gzip(handler):
    return "gzip" in (handler.headers.get("Accept-Encoding") or "").lower()


def _gzip_asset(path, raw):
    """Compress a static asset once; later hits reuse the cached bytes."""
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _ASSET_GZIP_CACHE_LOCK:
        hit = _ASSET_GZIP_CACHE.get(key)
    if hit is not None:
        return hit
    packed = _gzip.compress(raw, compresslevel=6)
    with _ASSET_GZIP_CACHE_LOCK:
        total = sum(len(v) for v in _ASSET_GZIP_CACHE.values()) + len(packed)
        if total > _ASSET_GZIP_CACHE_LIMIT:
            _ASSET_GZIP_CACHE.clear()
        _ASSET_GZIP_CACHE[key] = packed
    return packed


def _openclaw_sso_token(user_info: dict) -> str:
    """Obtain an openclaw token for the given user via the office-SSO exchange."""
    target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
    secret = os.getenv("OPENCLAW_OFFICE_SSO_SECRET", "openclaw-office-sso-dev")
    sso_payload = {
        "username": user_info.get("username", ""),
        "display_name": user_info.get("name") or user_info.get("username", ""),
        "role": user_info.get("role", "member"),
        "name": user_info.get("name", ""),
        "avatar_url": user_info.get("avatar_url", ""),
        "bio": user_info.get("bio", ""),
        "hobbies": user_info.get("hobbies", ""),
        "is_admin": bool(user_info.get("is_admin")),
        "is_superadmin": bool(user_info.get("is_superadmin")),
    }
    parsed_target = urllib.parse.urlparse(target)
    urls = [target + "/api/auth/office-sso"]
    if parsed_target.path.rstrip("/").endswith("/openclaw"):
        origin = urllib.parse.urlunparse((parsed_target.scheme, parsed_target.netloc, "", "", "", ""))
        urls.append(origin.rstrip("/") + "/api/auth/office-sso")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_err = None
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(sso_payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-OpenClaw-Office-SSO-Secret": secret},
                method="POST",
            )
            with opener.open(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("token", "")
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code != 404:
                raise
    raise last_err or RuntimeError("龙虾平台未返回登录凭据")


def _self_mcp_endpoint(headers) -> str:
    """Derive this server's public MCP endpoint URL from incoming request headers."""
    forwarded_proto = headers.get("X-Forwarded-Proto", "")
    forwarded_host = headers.get("X-Forwarded-Host", "") or headers.get("Host", "127.0.0.1:8765")
    scheme = forwarded_proto if forwarded_proto in ("http", "https") else "http"
    return f"{scheme}://{forwarded_host}{APP_RELATIVE_PATH}/mcp"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, data, status=200, headers=None):
        event = getattr(self, '_crm_audit_event', None)
        if event:
            self._crm_audit_event = None
            try:
                crm_audit(event['actor'], event['operation'], event['path'], status, outcome='失败' if isinstance(data, dict) and data.get('ok') is False else None)
            except OSError:
                sys.stderr.write("CRM audit write failed\n")
            headers = {**(headers or {}), 'Cache-Control': 'no-store', 'Pragma': 'no-cache'}
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if len(raw) >= GZIP_MIN_BYTES and _client_accepts_gzip(self):
            raw = _gzip.compress(raw, compresslevel=5)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def cookie_value(self, name):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == name:
                return value
        return ""

    def current_user(self):
        token = self.cookie_value("pws_session")
        user = login_session_user(token)
        set_request_username(user.get("username", "") if user else "")
        return user

    def require_user(self):
        user = self.current_user()
        if not user:
            self.send_json({"ok": False, "error": "请先登录"}, status=401)
            return None
        return user

    def check_assistant_permission(self, payload=None):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        # 数据中台取数接口：业务系统携带 API Key（无平台会话）调用，
        # 密钥有效性由 /api/datacenter/data 路由自行校验。
        if path.startswith("/api/datacenter/data") and self.headers.get("X-Data-Api-Key"):
            return True
        if path.startswith(APP_RELATIVE_PATH + "/"):
            path = path[len(APP_RELATIVE_PATH):]
        assistant = assistant_for_path(path)
        if path in ("/api/generate", "/api/send", "/download-template", "/api/draft", "/api/delete-report", "/api/upload-history", "/api/delete-history", "/api/report-template", "/api/report-templates", "/api/report-template-delete"):
            if self.command == "POST" and payload is None:
                return True
            kind = (payload or {}).get("kind") or urllib.parse.parse_qs(parsed.query).get("kind", ["weekly"])[0]
            assistant = "trip" if kind == "trip" else "weekly"
        if path.startswith("/forum-attachment/"):
            assistant = "forum"
        if path.startswith("/wechat-article/"):
            assistant = "news"
        if not assistant:
            return True
        user = self.require_user()
        if not user:
            return False
        if assistant == "crm":
            operation = crm_security_operation(path, self.command)
            self._crm_audit_event = {'actor':user['username'], 'operation':operation, 'path':path}
            security_admin = user.get('role') == 'superadmin' and path.startswith('/api/crm/security/')
            if not (crm_capabilities(user).get(operation, False) or security_admin):
                self.send_json({"ok":False,"error":"没有该客户数据操作权限，请联系客户经营管理员授权", "assistant":"crm"}, status=403)
                return False
        if not assistant_permissions(user).get(assistant, False):
            self.send_json({"ok": False, "error": "没有该助手的使用权限，请联系超级管理员授权", "assistant": assistant}, status=403)
            return False
        return True

    def require_admin(self):
        user = self.require_user()
        if not user:
            return None
        if user.get("role") not in ("admin", "superadmin"):
            self.send_json({"ok": False, "error": "只有管理员可以修改系统配置"}, status=403)
            return None
        return user

    def require_superadmin(self):
        user = self.require_user()
        if not user:
            return None
        if user.get("role") != "superadmin":
            self.send_json({"ok": False, "error": "只有超级管理员可以进行该操作"}, status=403)
            return None
        return user

    def _proxy_gateway(self):
        """把 /gateway 前缀的请求透传给 AI 安全网关（控制台+API），支持流式响应。"""
        target = os.getenv("SECURITY_GATEWAY_INTERNAL_URL", "http://host.docker.internal:3011").rstrip("/")
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        forward_headers = {}
        for key in ("Authorization", "X-Admin-Token", "Content-Type", "Accept", "X-Request-Id"):
            value = self.headers.get(key)
            if value:
                forward_headers[key] = value
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(target + self.path, data=body, headers=forward_headers, method=self.command)
        try:
            response = opener.open(request, timeout=300)
        except urllib.error.HTTPError as exc:
            response = exc
        except Exception as exc:
            self.send_json({"ok": False, "error": f"安全网关不可达: {exc}"}, status=502)
            return
        try:
            self.send_response(response.status)
            skipped = {"connection", "keep-alive", "transfer-encoding", "content-encoding"}
            has_length = False
            for key, value in response.getheaders():
                if key.lower() in skipped:
                    continue
                if key.lower() == "content-length":
                    has_length = True
                self.send_header(key, value)
            if not has_length:
                # 流式（chunked）响应转为按连接关闭界定长度
                self.close_connection = True
                self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            response.close()

    def _proxy_records_collector(self):
        """Expose the announcement collector through this public HTTPS entry.

        The edge forwards office.chencytech.com directly to this service, so
        proxying here (rather than a second local nginx) keeps /records
        reachable from the public domain.  Collector responses use absolute
        internal paths; rewrite those paths to stay below /records.
        """
        prefix = "/records"
        suffix = self.path[len(prefix):] or "/"
        target = os.getenv("RECORDS_COLLECTOR_URL", "http://172.24.0.1:18000").rstrip("/") + suffix
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        forwarded = {}
        for key in ("Content-Type", "Accept", "Authorization", "Cookie"):
            value = self.headers.get(key)
            if value:
                forwarded[key] = value
        forwarded.update({
            "Host": self.headers.get("Host", "office.chencytech.com"),
            "X-Forwarded-Host": self.headers.get("Host", "office.chencytech.com"),
            "X-Forwarded-Proto": self.headers.get("X-Forwarded-Proto", "https"),
            "X-Forwarded-Prefix": prefix,
        })
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(urllib.request.Request(target, data=body, headers=forwarded, method=self.command), timeout=300)
        except urllib.error.HTTPError as exc:
            response = exc
        except Exception as exc:
            self.send_json({"ok": False, "error": f"公告采集器不可达: {exc}"}, status=502)
            return
        try:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith(("text/html", "application/javascript", "application/json")):
                # Use placeholders so rewriting /api/vendors/ cannot be
                # rewritten a second time as /records/api/records/vendors/.
                raw = (raw.replace(b"/api/", b"__records_api__")
                          .replace(b"/vendors/", b"__records_vendors__")
                          .replace(b"__records_api__", b"/records/api/")
                          .replace(b"__records_vendors__", b"/records/vendors/")
                          .replace(b'"/settings"', b'"/records/settings"')
                          .replace(b"'/settings'", b"'/records/settings'")
                          .replace(b'"/review"', b'"/records/review"')
                          .replace(b"'/review'", b"'/records/review'"))
            self.send_response(response.status)
            skipped = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"}
            for key, value in response.getheaders():
                if key.lower() in skipped:
                    continue
                if key.lower() == "location" and value.startswith("/"):
                    value = prefix + value
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        finally:
            response.close()

    # FastGPT 以「根路径」构建，直接占用办公助手域名的根级路由命名空间。下面这些
    # 前缀 / 顶层页面均为 FastGPT 独有，与办公助手自身的 /personal-office-assistant/*
    # 以及有限的根 /api/xxx 接口互不冲突。
    FASTGPT_ROOT_PREFIXES = (
        "/_next/", "/imgs/", "/icon/", "/js/", "/fonts/", "/pwa/", "/model/",
        "/api/common/", "/api/core/", "/api/support/", "/api/proApi/",
        "/api/system/", "/api/plugin/", "/api/aiproxy/", "/api/invoke/",
        "/api/marketplace/", "/api/apidoc/", "/api/mcp/", "/api/admin/",
        "/api/v1/", "/api/v2/",
    )
    FASTGPT_ROOT_PAGES = (
        "account", "apidoc", "app", "chat", "config", "dashboard",
        "dataset", "price", "skill", "zh-CN", "zh-Hant",
    )
    # AIProxy's browser bundle calls its APIs at absolute /api/* paths.  The
    # workflow center is mounted on the office domain, so route those calls to
    # the internal AIProxy service instead of letting them fall through to the
    # office assistant API (which made the model-provider table appear empty).
    AIPROXY_API_PREFIXES = (
        "/api/model_config", "/api/model_configs", "/api/models/",
        "/api/channel", "/api/channels", "/api/group", "/api/groups",
        "/api/dashboard", "/api/token", "/api/tokens/",
    )

    def _is_aiproxy_api_request(self):
        path_only = self.path.split("?", 1)[0]
        return any(path_only.startswith(prefix) for prefix in self.AIPROXY_API_PREFIXES)

    def _proxy_aiproxy_api(self, api_path=None):
        """Serve the embedded AIProxy UI's absolute API calls on this domain."""
        user = self.require_user()
        if not user:
            return
        if self.command not in ("GET", "HEAD") and user.get("role") not in ("admin", "superadmin"):
            self.send_json({"ok": False, "error": "只有管理员可以修改 FastGPT 模型提供商"}, status=403)
            return
        request_path = api_path or self.path
        target = os.getenv("FASTGPT_AIPROXY_URL", "http://fastgpt-aiproxy:3000").rstrip("/") + request_path
        token = os.getenv("FASTGPT_AIPROXY_TOKEN", "")
        if not token:
            self.send_json({"ok": False, "error": "AIProxy 管理令牌未配置"}, status=502)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        headers = {"Authorization": token}
        for key in ("Content-Type", "Accept"):
            if self.headers.get(key):
                headers[key] = self.headers[key]
        try:
            response = urllib.request.urlopen(urllib.request.Request(target, data=body, headers=headers, method=self.command), timeout=120)
        except urllib.error.HTTPError as exc:
            response = exc
        except Exception as exc:
            self.send_json({"ok": False, "error": f"AIProxy 暂不可用：{exc}"}, status=502)
            return
        try:
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() in {"connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length"}:
                    continue
                self.send_header(key, value)
            raw = response.read()
            # AIProxy v0.6.5's “可用模型” view only receives a static
            # provider catalogue from models/builtin/channel.  Custom platform
            # models are correctly stored in model_configs but omitted from
            # that catalogue, leaving the UI blank. Merge the configured
            # models into the OpenAI-compatible catalogue the view consumes.
            if request_path.split("?", 1)[0] == "/api/models/builtin/channel":
                try:
                    catalog = json.loads(raw.decode("utf-8"))
                    cfg_req = urllib.request.Request(
                        target.rsplit("/api/", 1)[0] + "/api/model_configs/all",
                        headers={"Authorization": token}, method="GET",
                    )
                    with urllib.request.urlopen(cfg_req, timeout=30) as cfg_response:
                        configured = json.loads(cfg_response.read().decode("utf-8")).get("data") or []
                    rows = catalog.setdefault("data", {}).setdefault("1", [])
                    known = {str(item.get("model") or "") for item in rows}
                    rows.extend(item for item in configured if str(item.get("model") or "") not in known)
                    raw = json.dumps(catalog, ensure_ascii=False).encode("utf-8")
                except Exception:
                    pass
            if request_path.split("?", 1)[0] == "/api/models/default":
                try:
                    defaults = json.loads(raw.decode("utf-8"))
                    data = defaults.setdefault("data", {})
                    if not (data.get("models") or {}):
                        cfg_req = urllib.request.Request(
                            target.rsplit("/api/", 1)[0] + "/api/model_configs/all",
                            headers={"Authorization": token}, method="GET",
                        )
                        with urllib.request.urlopen(cfg_req, timeout=30) as cfg_response:
                            configured = json.loads(cfg_response.read().decode("utf-8")).get("data") or []
                        grouped = {}
                        for item in configured:
                            name = str(item.get("model") or "")
                            kind = str(item.get("type") or "")
                            if name and kind:
                                grouped.setdefault(kind, []).append(name)
                        data["models"] = grouped
                        data.setdefault("mapping", {})
                        raw = json.dumps(defaults, ensure_ascii=False).encode("utf-8")
                except Exception:
                    pass
            if request_path.split("?", 1)[0].startswith("/api/models/default/"):
                try:
                    model_type = request_path.split("?", 1)[0].rsplit("/", 1)[-1]
                    cfg_req = urllib.request.Request(
                        target.rsplit("/api/", 1)[0] + "/api/model_configs/all",
                        headers={"Authorization": token}, method="GET",
                    )
                    with urllib.request.urlopen(cfg_req, timeout=30) as cfg_response:
                        configured = json.loads(cfg_response.read().decode("utf-8")).get("data") or []
                    names = [str(item.get("model")) for item in configured if str(item.get("type")) == model_type and item.get("model")]
                    raw = json.dumps({"data": {"mapping": {}, "models": names}, "success": True}, ensure_ascii=False).encode("utf-8")
                except Exception:
                    pass
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        finally:
            response.close()

    def _is_fastgpt_request(self) -> bool:
        base = APP_RELATIVE_PATH
        # 历史子路径入口，保留以便 302 回跳到根级地址。
        if self.path.startswith(base + "/fastgpt"):
            return True
        path_only = self.path.split("?", 1)[0]
        if path_only.startswith(base + "/") or path_only == base:
            return False
        if any(path_only.startswith(pfx) for pfx in self.FASTGPT_ROOT_PREFIXES):
            return True
        top = path_only.strip("/").split("/", 1)[0]
        return top in self.FASTGPT_ROOT_PAGES

    def do_DELETE(self):
        set_request_username("")
        if not self.check_assistant_permission():
            return
        if self.path.startswith("/api/aiproxy/api/"):
            self._proxy_aiproxy_api("/api/" + self.path[len("/api/aiproxy/api/"):])
            return
        if self._is_aiproxy_api_request():
            self._proxy_aiproxy_api()
            return
        if self._is_fastgpt_request():
            self._proxy_fastgpt()
            return
        if self.path == "/gateway" or self.path.startswith("/gateway/"):
            self._proxy_gateway()
            return
        self.send_json({"ok": False, "error": "接口不存在"}, status=404)

    def do_PUT(self):
        set_request_username("")
        if not self.check_assistant_permission():
            return
        if self.path.startswith("/api/aiproxy/api/"):
            self._proxy_aiproxy_api("/api/" + self.path[len("/api/aiproxy/api/"):])
            return
        if self._is_aiproxy_api_request():
            self._proxy_aiproxy_api()
            return
        if self._is_fastgpt_request():
            self._proxy_fastgpt()
            return
        if self.path == "/gateway" or self.path.startswith("/gateway/"):
            self._proxy_gateway()
            return
        self.send_json({"ok": False, "error": "接口不存在"}, status=404)

    def _proxy_wechat_exporter(self):
        """同域代理公众号采集器，避免对外暴露独立端口。"""
        prefix = APP_RELATIVE_PATH + "/wechat-article"
        suffix = self.path[len(prefix):] or "/"
        # 内部采集桥只允许办公助手容器直连，禁止通过公开反向代理访问。
        if suffix.startswith("/api/internal/"):
            self.send_json({"ok": False, "error": "内部采集接口不可公开访问"}, status=403)
            return
        # Nuxt 设置 baseURL 后，服务端 API 也位于该子路径；静态资源仍由
        # 采集器根目录提供。分别处理才能同时支持页面资源与登录 POST 请求。
        if suffix.startswith("/api/"):
            target = "http://wechat-article-exporter:3000" + prefix + suffix
        else:
            target = "http://wechat-article-exporter:3000" + suffix
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items() if key.lower() in {"content-type", "cookie", "accept"}}
        try:
            req = urllib.request.Request(target, data=body, headers=headers, method=self.command)
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    base = APP_RELATIVE_PATH + "/wechat-article"
                    page = raw.decode("utf-8", errors="replace")
                    page = page.replace('href="/_nuxt/', f'href="{base}/_nuxt/')
                    page = page.replace('src="/_nuxt/', f'src="{base}/_nuxt/')
                    page = page.replace('src="/vendors/', f'src="{base}/vendors/')
                    page = page.replace('baseURL:"/"', f'baseURL:"{base}/"')
                    page = page.replace('buildAssetsDir:"/_nuxt/"', 'buildAssetsDir:"_nuxt/"')
                    raw = page.encode("utf-8")
                self.send_response(resp.status)
                for key in ("Content-Type", "Set-Cookie", "Cache-Control"):
                    if resp.headers.get(key):
                        self.send_header(key, resp.headers.get(key))
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        except Exception as exc:
            self.send_json({"ok": False, "error": f"公众号采集服务不可用：{exc}"}, status=502)

    def _proxy_fastgpt(self):
        """同域代理 FastGPT 工作流中心，不暴露独立服务端口。

        FastGPT 官方镜像按「根路径」构建（Next.js basePath 无法在预构建镜像里
        运行时生效）。若挂到子路径下代理，客户端路由 / query 参数（如 appId）会
        在 hydration 时被 FastGPT 重置——因为浏览器地址栏带着 Next 路由表里不存在
        的前缀。因此这里让 FastGPT 直接占用办公助手域名的「根级」路由命名空间
        （/chat、/_next、/api/core 等，与办公助手自身的 /personal-office-assistant/*
        及有限的根 /api/xxx 不冲突），原样透传、不改写内容，路由与 query 全部保真。
        """
        user = self.require_user()
        if not user:
            return
        if not assistant_permissions(user)["workflow"]:
            self.send_json({"ok": False, "error": "没有工作流中心权限，请联系客户经营管理员授权"}, status=403)
            return
        base_prefix = APP_RELATIVE_PATH
        legacy_prefix = next(
            (base_prefix + v for v in ("/fastgpt-v3", "/fastgpt-v2", "/fastgpt")
             if self.path.startswith(base_prefix + v)),
            "",
        )
        if legacy_prefix:
            # 兼容历史入口：旧的子路径地址一律 302 到根级等价地址。
            target_path = self.path[len(legacy_prefix):] or "/"
            self.send_response(302)
            self.send_header("Location", target_path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # 根级模式：原样转发，不做内容改写。
        suffix = self.path
        prefix = ""
        target = "http://fastgpt-app:3000" + suffix
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        forwarded = {
            "X-Forwarded-Proto": self.headers.get("X-Forwarded-Proto", "https"),
            "X-Forwarded-Host": self.headers.get("X-Forwarded-Host", self.headers.get("Host", "")),
            "X-Forwarded-Prefix": prefix,
            "X-Forwarded-For": self.client_address[0],
            "X-Office-Username": user.get("username", ""),
        }
        try:
            sso_request = urllib.request.Request(
                "http://fastgpt-sso:3100/login",
                data=json.dumps(user, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Office-SSO-Secret": "office_fastgpt_sso_9Rm4Kv7Lx2Np8Qw"},
                method="POST",
            )
            with urllib.request.urlopen(sso_request, timeout=10) as sso_response:
                fastgpt_token = json.loads(sso_response.read().decode("utf-8")).get("token", "")
            if not fastgpt_token:
                raise RuntimeError("登录桥未返回会话")
            # 默认简体中文：若浏览器尚未保存 NEXT_LOCALE（用户没手动切过语言），
            # 则为 FastGPT 注入 zh-CN，并在响应里补一枚同名 Cookie，保证首屏即中文；
            # 用户一旦在「语言与时区」里改过，就尊重其选择、不再强制覆盖。
            incoming_cookie = self.headers.get("Cookie", "") or ""
            existing_locale = ""
            for part in incoming_cookie.split(";"):
                part = part.strip()
                if part.startswith("NEXT_LOCALE="):
                    existing_locale = part[len("NEXT_LOCALE="):]
                    break
            self._fastgpt_default_locale = existing_locale or "zh-CN"
            self._fastgpt_set_locale = not existing_locale
            forwarded["Cookie"] = f"fastgpt_token={fastgpt_token}; NEXT_LOCALE={self._fastgpt_default_locale}"
        except Exception as exc:
            self.send_json({"ok": False, "error": f"工作流单点登录失败：{exc}"}, status=502)
            return
        for key in ("Content-Type", "Cookie", "Accept", "Accept-Language", "Origin", "Referer", "User-Agent"):
            value = self.headers.get(key)
            if value and key != "Cookie":
                forwarded[key] = value
        try:
            req = urllib.request.Request(target, data=body, headers=forwarded, method=self.command)
            response = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as exc:
            response = exc
        except Exception as exc:
            self.send_json({"ok": False, "error": f"工作流中心暂不可用：{exc}"}, status=502)
            return
        try:
            # FastGPT（Next.js）默认使用根路径 /_next/ 输出资源。工作流中心被
            # 同域挂载在 /personal-office-assistant/fastgpt 下时，浏览器会把这些
            # 资源错误地请求到办公助手根目录并得到 404。将 HTML/JS/CSS 中的资源
            # 路径改写为代理前缀，避免要求用户额外暴露 FastGPT 端口或域名。
            content_type = response.headers.get("Content-Type", "").lower()
            # 根级模式（prefix 为空）原样透传，无需改写内容。
            rewrite_content = bool(prefix) and any(kind in content_type for kind in (
                "text/html", "javascript", "text/css", "application/json",
            ))
            raw = None
            if rewrite_content:
                raw = response.read()
                try:
                    text = raw.decode("utf-8")
                    text = text.replace("/_next/", f"{prefix}/_next/")
                    text = text.replace("/imgs/", f"{prefix}/imgs/")
                    text = text.replace("/icon/", f"{prefix}/icon/")
                    # FastGPT 客户端把后端接口写成绝对 /api/...；若不改写，
                    # 会命中办公助手自己的 API 而不是 FastGPT 服务。
                    for quote in ('"', "'", "`"):
                        text = text.replace(f"{quote}/api/", f"{quote}{prefix}/api/")
                        text = text.replace(f"{quote}/api{quote}", f"{quote}{prefix}/api{quote}")
                    raw = text.encode("utf-8")
                except UnicodeDecodeError:
                    # 非 UTF-8 资源维持原样，确保代理不会影响文件下载。
                    pass

            self.send_response(response.status)
            # FastGPT 默认对所有页面下发 X-Frame-Options: DENY，会阻止办公助手同源
            # 内嵌工作流中心。这里统一降为 SAMEORIGIN，仅允许本域内嵌。
            skipped = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "x-frame-options"}
            for key, value in response.getheaders():
                lower = key.lower()
                if lower in skipped:
                    continue
                if lower == "location" and value.startswith("/"):
                    value = prefix + value
                if lower == "content-length":
                    if raw is not None:
                        continue
                self.send_header(key, value)
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            if getattr(self, "_fastgpt_set_locale", False):
                self.send_header("Set-Cookie", "NEXT_LOCALE=zh-CN; Path=/; Max-Age=315360000")
            if raw is not None:
                self.send_header("Content-Length", str(len(raw)))
            else:
                self.close_connection = True
                self.send_header("Connection", "close")
            self.end_headers()
            if raw is not None:
                self.wfile.write(raw)
                return
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            response.close()

    def _handle_fastgpt_kb_bridge(self) -> bool:
        """FastGPT ⇄ RAGFlow 打通：内网服务端点，凭共享密钥检索 RAGFlow 知识库。

        供 FastGPT 工作流的 HTTP 节点调用（内网 http://personal-work-site:8765），
        不依赖办公助手登录态，仅校验共享密钥。
        """
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith(APP_RELATIVE_PATH + "/"):
            path = path[len(APP_RELATIVE_PATH):]
        is_apidataset = path.startswith("/api/fastgpt/apidataset/")
        if not path.startswith("/api/fastgpt/kb") and not is_apidataset:
            return False
        secret = self.headers.get("X-FastGPT-KB-Secret", "") or self.headers.get("Authorization", "").replace("Bearer ", "")
        personal_username = ""
        personal_match = re.match(r"^/api/fastgpt/apidataset/personal/([^/]+)(?:/|$)", path)
        if personal_match:
            personal_username = urllib.parse.unquote(personal_match.group(1)).strip()
            authorized = bool(personal_username) and hmac.compare_digest(secret, fastgpt_apidataset_personal_token(personal_username))
        else:
            authorized = hmac.compare_digest(secret, FASTGPT_KB_BRIDGE_SECRET)
        if not authorized:
            if is_apidataset:
                self.send_json({"success": False, "message": "unauthorized"}, status=401)
            else:
                self.send_json({"ok": False, "error": "unauthorized"}, status=401)
            return True
        try:
            # FastGPT「API 文件库」原生连接器（baseURL=.../api/fastgpt/apidataset）
            if is_apidataset:
                sub = path[len("/api/fastgpt/apidataset"):]
                if personal_username:
                    # The match includes the slash following <username>; leave
                    # the endpoint suffix in exactly the API-file-library form.
                    sub = "/" + path[personal_match.end():]
                query = urllib.parse.parse_qs(parsed.query)
                file_id = (query.get("id", [""])[0]) or ""
                if sub == "/v1/file/list" and self.command == "POST":
                    length = int(self.headers.get("Content-Length", "0") or 0)
                    body = self.rfile.read(length) if length else b"{}"
                    payload = json.loads(body.decode("utf-8") or "{}")
                    self.send_json(fastgpt_apidataset_list(payload.get("parentId", ""), payload.get("searchKey", ""), personal_username))
                    return True
                if sub == "/v1/file/content" and self.command == "GET":
                    self.send_json(fastgpt_apidataset_content(file_id, personal_username))
                    return True
                if sub == "/v1/file/detail" and self.command == "GET":
                    self.send_json(fastgpt_apidataset_detail(file_id, personal_username))
                    return True
                if sub == "/v1/file/read" and self.command == "GET":
                    self.send_json(fastgpt_apidataset_read(file_id, personal_username))
                    return True
                self.send_json({"success": False, "message": "not found"}, status=404)
                return True
            if path == "/api/fastgpt/kb-list" and self.command == "GET":
                self.send_json(fastgpt_kb_list())
                return True
            if path == "/api/fastgpt/kb-retrieval" and self.command == "POST":
                length = int(self.headers.get("Content-Length", "0") or 0)
                body = self.rfile.read(length) if length else b"{}"
                payload = json.loads(body.decode("utf-8") or "{}")
                self.send_json(fastgpt_kb_retrieval(payload))
                return True
        except Exception as exc:
            if is_apidataset:
                self.send_json({"success": False, "message": str(exc)}, status=500)
            else:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return True
        self.send_json({"ok": False, "error": "not found"}, status=404)
        return True

    def do_GET(self):
        set_request_username("")
        if not self.check_assistant_permission():
            return
        if self.path == "/records" or self.path.startswith("/records/"):
            self._proxy_records_collector()
            return
        if self._handle_fastgpt_kb_bridge():
            return
        if self.path.startswith("/api/aiproxy/api/"):
            self._proxy_aiproxy_api("/api/" + self.path[len("/api/aiproxy/api/"):])
            return
        if self._is_aiproxy_api_request():
            self._proxy_aiproxy_api()
            return
        if self._is_fastgpt_request():
            self._proxy_fastgpt()
            return
        if self.path.startswith(APP_RELATIVE_PATH + "/wechat-article"):
            self._proxy_wechat_exporter()
            return
        if self.path == "/gateway" or self.path.startswith("/gateway/"):
            self._proxy_gateway()
            return
        if self.path.startswith(APP_RELATIVE_PATH + "/gateway"):
            # 习惯性输成 /personal-office-assistant/gateway 时跳到规范地址
            self.send_response(302)
            self.send_header("Location", self.path[len(APP_RELATIVE_PATH):])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith(APP_RELATIVE_PATH + "/"):
            parsed = parsed._replace(path=parsed.path[len(APP_RELATIVE_PATH):] or "/")
        if parsed.path in ("/", APP_RELATIVE_PATH, APP_RELATIVE_PATH + "/"):
            raw = app_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/mcp-mail-attachment":
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get("token", [""])[0]
            try:
                info = resolve_mcp_mail_attachment_link(token)
                path, raw = get_mail_part_content(info["username"], info["uid"], info["part"])
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
                return
            display_name = path.name.split("__", 1)[1] if "__" in path.name else path.name
            encoded_name = urllib.parse.quote(display_name)
            self.send_response(200)
            self.send_header("Content-Type", mail_part_content_type_from_name(display_name, raw))
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/digital-human":
            # 数字人页面用相对路径加载模型资源，统一补成带斜杠的目录地址。
            self.send_response(302)
            self.send_header("Location", self.path.split("?", 1)[0] + "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path == "/digital-human/":
            raw = digital_human_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/digital-human/"):
            if parsed.path.startswith("/digital-human/exports/"):
                path = digital_human_asset(parsed.path[len("/digital-human/exports/"):])
            else:
                path = digital_human_static(parsed.path[len("/digital-human/"):])
            if path is None:
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            if path.suffix.lower() == ".glb":
                ctype = "model/gltf-binary"
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/frontend/"):
            relative = Path(urllib.parse.unquote(parsed.path[len("/frontend/"):]))
            if relative.is_absolute() or ".." in relative.parts:
                self.send_json({"error": "Not found"}, status=404)
                return
            path = FRONTEND_DIR / relative
            if not path.exists() or not path.is_file():
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/assets/"):
            rel = Path(urllib.parse.unquote(parsed.path[len("/assets/"):])).name
            path = FRONTEND_DIR / "assets" / rel
            if not path.exists() or not path.is_file():
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            ctype = ctype or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            if len(raw) >= GZIP_MIN_BYTES and ctype.startswith(GZIP_TYPES) and _client_accepts_gzip(self):
                raw = _gzip_asset(path, raw)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(raw)))
            # Everything under /assets/ is emitted by Vite with a content hash in the
            # file name, so a changed file always gets a new URL and can be cached forever.
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/user-avatar/"):
            user = self.require_user()
            if not user:
                return
            name = Path(urllib.parse.unquote(parsed.path)).stem
            target = find_user(name)
            if not target:
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = office_blob_read("platform", user_profile_dir(name) / "avatar.png")
            if raw is None:
                self.send_json({"error": "Not found"}, status=404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/session":
            user = self.current_user()
            self.send_json(
                {
                    "authenticated": bool(user),
                    "user": public_user(user) if user else None,
                    "assistant_prompt": read_config().get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT),
                }
            )
            return
        if parsed.path == "/api/openclaw-sso":
            user = self.require_user()
            if not user:
                return
            target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
            public_url = os.getenv("OPENCLAW_PLATFORM_PUBLIC_URL", "/openclaw").rstrip("/")
            secret = os.getenv("OPENCLAW_OFFICE_SSO_SECRET", "openclaw-office-sso-dev")
            current_user_info = public_user(user)
            payload = {
                "username": current_user_info.get("username", ""),
                "display_name": current_user_info.get("name") or current_user_info.get("username", ""),
                "role": current_user_info.get("role", "member"),
                "name": current_user_info.get("name", ""),
                "avatar_url": current_user_info.get("avatar_url", ""),
                "bio": current_user_info.get("bio", ""),
                "hobbies": current_user_info.get("hobbies", ""),
                "is_admin": bool(current_user_info.get("is_admin")),
                "is_superadmin": bool(current_user_info.get("is_superadmin")),
            }
            try:
                parsed_target = urllib.parse.urlparse(target)
                targets = [target + "/api/auth/office-sso"]
                if parsed_target.path.rstrip("/").endswith("/openclaw"):
                    origin = urllib.parse.urlunparse((parsed_target.scheme, parsed_target.netloc, "", "", "", ""))
                    targets.append(origin.rstrip("/") + "/api/auth/office-sso")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                last_error = None
                data = None
                for sso_url in targets:
                    try:
                        req = urllib.request.Request(
                            sso_url,
                            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            headers={
                                "Content-Type": "application/json",
                                "X-OpenClaw-Office-SSO-Secret": secret,
                            },
                            method="POST",
                        )
                        with opener.open(req, timeout=15) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                        break
                    except urllib.error.HTTPError as exc:
                        last_error = exc
                        if exc.code != 404:
                            raise
                if data is None:
                    raise last_error or RuntimeError("龙虾平台未返回登录凭据")
                self.send_json({"ok": True, "token": data.get("token", ""), "user": data.get("user"), "url": public_url + "/"})
            except Exception as exc:
                self.send_json({"ok": False, "error": f"龙虾平台单点登录失败：{exc}"}, status=502)
            return
        if parsed.path == "/api/my-lobsters":
            user = self.require_user()
            if not user:
                return
            try:
                token = _openclaw_sso_token(public_user(user))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(
                    target + "/api/agents",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with opener.open(req, timeout=15) as resp:
                    agents_data = json.loads(resp.read().decode("utf-8"))
                self.send_json({"ok": True, "agents": agents_data if isinstance(agents_data, list) else []})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=502)
            return
        if parsed.path == "/api/assistant-lobster":
            user = self.require_user()
            if not user:
                return
            self.send_json({"ok": True, "lobster": get_assistant_lobster(user.get("username", ""))})
            return
        if parsed.path == "/api/nav-prefs":
            user = self.require_user()
            if not user:
                return
            self.send_json(load_nav_prefs(user.get("username", "")))
            return
        if parsed.path == "/api/admin-config":
            if not self.require_admin():
                return
            self.send_json(admin_config_payload())
            return
        if parsed.path == "/api/tts-config":
            if not self.require_admin():
                return
            self.send_json(digital_human_tts_config_api())
            return
        if parsed.path == "/api/meeting-config":
            if not self.require_admin():
                return
            self.send_json(meeting_config_api())
            return
        if parsed.path == "/api/knowledge-config":
            if not self.require_admin():
                return
            self.send_json(kb_config_api())
            return
        if parsed.path == "/api/writing/templates":
            user = self.require_user()
            if not user:
                return
            self.send_json(writing_templates(user.get("username", "")))
            return
        if parsed.path == "/api/writing/history":
            user = self.require_user()
            if not user:
                return
            self.send_json(writing_history(user.get("username", "")))
            return
        if parsed.path == "/api/writing/uploads":
            user = self.require_user()
            if not user:
                return
            self.send_json(writing_uploads(user.get("username", "")))
            return
        if parsed.path == "/api/writing/history-item":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(writing_get_history(qs.get("id", [""])[0], user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
            return
        if parsed.path == "/api/writing/download":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            file_name = Path(urllib.parse.unquote(qs.get("file", [""])[0])).name
            path = user_root(user.get("username", "")) / "writing" / "exports" / file_name
            raw = office_blob_read("writing", path) if file_name else None
            if raw is None:
                self.send_json({"ok": False, "error": "导出文件不存在"}, status=404)
                return
            ctype, _ = mimetypes.guess_type(str(path))
            encoded_name = urllib.parse.quote(path.name)
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/xinference-config":
            if not self.require_admin():
                return
            self.send_json(xinference_unified_config())
            return
        if parsed.path == "/api/ragflow/status":
            if not self.require_admin():
                return
            self.send_json(kb_ragflow_status())
            return
        if parsed.path == "/api/ragflow/sso":
            # 多租户：每个用户登录自己的 RAGFlow 租户，普通用户也可用。
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(kb_ragflow_sso(user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/mcp-config":
            if not self.require_admin():
                return
            self.send_json(mcp_config_api())
            return
        if parsed.path == "/api/fastgpt-config":
            if not self.require_admin():
                return
            self.send_json(fastgpt_config_api())
            return
        if parsed.path == "/api/admin-users-list":
            if not self.require_admin():
                return
            self.send_json({"ok": True, "users": user_list(self.current_user().get("username", ""))})
            return
        if parsed.path == "/skill-docs":
            raw = (
                "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
                "<title>智能办公助手 Skill 文档</title>"
                "<style>body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;max-width:980px;margin:0 auto;padding:32px;line-height:1.7;color:#172033;background:#f4f7fb}"
                "pre{white-space:pre-wrap;background:#fff;border:1px solid #dbe5f1;border-radius:10px;padding:18px;box-shadow:0 8px 24px rgba(15,23,42,.06)}"
                "a{display:inline-block;margin-bottom:18px;color:#2563eb;font-weight:700}</style></head><body>"
                "<a href='/download-skill-doc'>下载 Markdown 文档</a>"
                "<pre>"
                + escape(skill_doc_markdown())
                + "</pre></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/download-skill-doc":
            raw = skill_doc_markdown().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''ai-office-skills.md")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/mcp":
            self.send_json(mcp_info())
            return
        if parsed.path == "/api/datacenter/data" and self.headers.get("X-Data-Api-Key"):
            pass  # 业务系统 API Key 取数：无平台会话，密钥在 /api/datacenter/data 路由内校验
        elif parsed.path.startswith("/api/") and not self.require_user():
            return
        if parsed.path == "/api/skills":
            if not self.require_superadmin():
                return
            self.send_json(public_skill_docs())
            return
        if parsed.path == "/api/skill-invocations":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = qs.get("limit", ["20"])[0]
            self.send_json(skill_invocation_history({"limit": limit}, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/agent-orchestration":
            if not self.require_superadmin():
                return
            self.send_json(agent_orchestration())
            return
        if parsed.path == "/api/agent-config":
            if not self.require_superadmin():
                return
            self.send_json({"ok": True, "config": read_agent_config()})
            return
        if parsed.path == "/api/agent/sessions":
            qs = urllib.parse.parse_qs(parsed.query)
            payload = {k: v[0] for k, v in qs.items()}
            self.send_json(agent_sessions_api(payload, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/mail-config":
            username = self.current_user().get("username", "")
            data = user_mail_config(username)
            data["smtp_password_masked"] = "已配置" if data.get("smtp_password") else "未配置"
            data["imap_password_masked"] = "已配置" if data.get("imap_password") else "未配置"
            data["personal_smtp_password_masked"] = "已配置" if data.get("personal_smtp_password") else "未配置"
            data["personal_imap_password_masked"] = "已配置" if data.get("personal_imap_password") else "未配置"
            data.pop("smtp_password", None)
            data.pop("imap_password", None)
            data.pop("personal_smtp_password", None)
            data.pop("personal_imap_password", None)
            self.send_json(data)
            return
        if parsed.path == "/api/mailbox":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = qs.get("limit", ["20"])[0]
            offset = qs.get("offset", ["0"])[0]
            read_status = qs.get("read_status", ["all"])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            try:
                self.send_json(list_inbox_messages(
                    self.current_user().get("username", ""), limit, refresh, offset=offset, read_status=read_status
                ))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/mailbox-detail":
            qs = urllib.parse.parse_qs(parsed.query)
            uid = qs.get("uid", [""])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            try:
                self.send_json(get_inbox_message(self.current_user().get("username", ""), uid, refresh))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/sent-mail":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = qs.get("limit", ["20"])[0]
            try:
                self.send_json(list_sent_messages(self.current_user().get("username", ""), limit))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/sent-mail-detail":
            qs = urllib.parse.parse_qs(parsed.query)
            uid = qs.get("uid", [""])[0]
            try:
                self.send_json(get_sent_message(self.current_user().get("username", ""), uid))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/mailbox-part":
            qs = urllib.parse.parse_qs(parsed.query)
            uid = qs.get("uid", [""])[0]
            part_key = qs.get("part", [""])[0]
            download = qs.get("download", ["0"])[0] == "1"
            try:
                path, raw = get_mail_part_content(self.current_user().get("username", ""), uid, part_key)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
                return
            display_name = path.name.split("__", 1)[1] if "__" in path.name else path.name
            self.send_response(200)
            self.send_header("Content-Type", mail_part_content_type_from_name(display_name, raw))
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=1800")
            if download:
                encoded_name = urllib.parse.quote(display_name)
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/reimbursement/scan":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            start = qs.get("start", [""])[0]
            end = qs.get("end", [""])[0]
            account = qs.get("account", ["company"])[0]
            last_exc = None
            for attempt in range(2):
                try:
                    self.send_json(scan_invoice_attachments(username, start, end, account))
                    return
                except Exception as exc:
                    last_exc = exc
                    if attempt == 0:
                        __import__("time").sleep(1)
            self.send_json({"ok": False, "error": str(last_exc)}, status=400)
            return
        if parsed.path == "/api/reimbursement/searches":
            username = self.current_user().get("username", "")
            try:
                self.send_json(list_reimbursement_searches(username))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/reimbursement/search":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            try:
                self.send_json(get_reimbursement_search(username, qs.get("id", [""])[0]))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
            return
        if parsed.path == "/api/reimbursement/email":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            uid = qs.get("uid", [""])[0]
            account = qs.get("account", ["company"])[0]
            try:
                self.send_json(get_reimbursement_email_html(username, account, uid))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/reimbursement/attachment":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            key = qs.get("key", [""])[0]
            try:
                path = get_reimbursement_attachment(username, key)
                if not path or not path.exists():
                    self.send_json({"ok": False, "error": "附件不存在"}, status=404)
                    return
                raw = path.read_bytes()
                display_name = path.name.split("__", 1)[1] if "__" in path.name else path.name
                download = qs.get("download", ["0"])[0] == "1"
                self.send_response(200)
                self.send_header("Content-Type", mail_part_content_type_from_name(display_name, raw))
                self.send_header("Content-Length", str(len(raw)))
                if download:
                    encoded_name = urllib.parse.quote(display_name)
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/reimbursement/ofd-preview":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            key = qs.get("key", [""])[0]
            try:
                png = render_ofd_preview(username, key)
                if not png:
                    self.send_json({"ok": False, "error": "OFD 渲染失败或不支持"}, status=404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/reimbursement/output":
            qs = urllib.parse.parse_qs(parsed.query)
            username = self.current_user().get("username", "")
            filename = qs.get("name", [""])[0]
            try:
                found = get_reimbursement_output(username, filename)
                if found is None:
                    self.send_json({"ok": False, "error": "文件不存在"}, status=404)
                    return
                path, raw = found
                encoded_name = urllib.parse.quote(path.name)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/reports":
            username = self.current_user().get("username", "")
            files = sorted(all_files(username), key=lambda item: (item["generated"] if "generated" in item else False, item["kind"], item["sort_key"], item["mtime"]), reverse=True)
            permissions = assistant_permissions(self.current_user())
            files = [item for item in files if permissions.get(item.get("kind"), False)]
            self.send_json(
                {
                    "reports": files,
                    "latest_weekly": (newest("weekly", username) or {}).get("name", "") if permissions["weekly"] else "",
                    "latest_trip": (newest("trip", username) or {}).get("name", "") if permissions["trip"] else "",
                }
            )
            return
        if parsed.path == "/api/draft":
            qs = urllib.parse.parse_qs(parsed.query)
            kind = qs.get("kind", ["weekly"])[0]
            file_name = qs.get("file", [""])[0]
            draft = compose_draft(kind, file_name, self.current_user().get("username", ""))
            status = 400 if "error" in draft else 200
            self.send_json(draft, status=status)
            return
        if parsed.path == "/api/weekly-prefill":
            try:
                self.send_json(weekly_prefill(self.current_user().get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/trip-prefill":
            try:
                self.send_json(trip_prefill(self.current_user().get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/list":
            qs = urllib.parse.parse_qs(parsed.query)
            scope = qs.get("scope", ["mine"])[0]
            try:
                self.send_json(kb_list(scope, self.current_user().get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            return
        if parsed.path == "/api/knowledge/kbs":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(kb_datasets(user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/digital-human/kb-config":
            user = self.require_user()
            if not user:
                return
            self.send_json({"ok": True, **get_digital_human_kb(user.get("username", ""))})
            return
        if parsed.path == "/api/knowledge/chat-history":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(kb_chat_history(user.get("username", ""), qs.get("session_id", [""])[0]))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/chat-embed":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(kb_chat_embed(user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/external-info":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(kb_external_api_info(user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/doc-file":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                name, raw = kb_doc_file(qs.get("dataset_id", [""])[0], qs.get("doc_id", [""])[0], user.get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", mail_part_content_type_from_name(name, raw))
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(name)}")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/doc-chunks":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(kb_doc_chunks(qs.get("dataset_id", [""])[0], qs.get("doc_id", [""])[0], user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/pdf-md/list":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(pdf_md_list(user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/pdf-md/get":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(pdf_md_get(qs.get("job_id", [""])[0], user.get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/pdf-md/page":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                name, raw = pdf_md_page_image(qs.get("job_id", [""])[0], qs.get("page", ["1"])[0], user.get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(name)}")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/knowledge/pdf-md/asset":
            user = self.require_user()
            if not user:
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                name, content_type, raw = pdf_md_asset(qs.get("job_id", [""])[0], qs.get("name", [""])[0], user.get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(name)}")
                self.end_headers()
                self.wfile.write(raw)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/meeting/list":
            self.send_json(meeting_list(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/meeting/get":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(meeting_get(qs.get("id", [""])[0], self.current_user().get("username", "")))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=404)
            return
        if parsed.path == "/api/diary/list":
            qs = urllib.parse.parse_qs(parsed.query)
            payload = {k: v[0] for k, v in qs.items()}
            self.send_json(list_diaries(payload, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/diary/get":
            qs = urllib.parse.parse_qs(parsed.query)
            date_str = qs.get("date", [""])[0]
            self.send_json(get_diary(date_str, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/projects":
            self.send_json(project_list(self.current_user().get("username", "")))
            return
        if parsed.path in {"/api/contracts", "/api/contracts/get", "/api/contracts/download", "/api/contracts/original"}:
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if parsed.path == "/api/contracts":
                    self.send_json(contract_list(user["username"]), headers={"Cache-Control": "no-store"})
                elif parsed.path == "/api/contracts/get":
                    self.send_json({"ok": True, "contract": contract_read(user["username"], query.get("id", [""])[0])}, headers={"Cache-Control": "no-store"})
                else:
                    if parsed.path == "/api/contracts/original":
                        name, raw = contract_original(user["username"], query.get("id", [""])[0])
                    else:
                        name, raw = contract_download(user["username"], query.get("id", [""])[0], query.get("document_id", [""])[0])
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf" if name.lower().endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            except Exception:
                self.send_json({"ok": False, "error": "合同读取失败，请稍后重试"}, status=500)
            return
        if parsed.path == "/api/ledger":
            user = self.require_user()
            if not user:
                return
            self.send_json(ledger_list(user.get("username", "")))
            return
        if parsed.path.startswith("/api/datacenter/"):
            query = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/datacenter/datasets":
            if not self.require_superadmin():
                return
            self.send_json(dapi_catalog())
            return
        if parsed.path == "/api/datacenter/apikeys":
            if not self.require_superadmin():
                return
            self.send_json(dapi_list_keys())
            return
        if parsed.path == "/api/datacenter/data":
            token = self.headers.get("X-Data-Api-Key", "")
            caller = ""
            if token:
                key_name = dapi_auth_key(token)
                if not key_name:
                    self.send_json({"ok": False, "error": "API Key 无效或已吊销"}, status=401)
                    return
                caller = f"apikey:{key_name}"
            else:
                user = self.require_superadmin()
                if not user:
                    return
                caller = user.get("username", "")
            params = {k: v[0] for k, v in query.items()}
            try:
                self.send_json(dapi_query(params.pop("dataset", ""), params, caller))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except RuntimeError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=503)
            except Exception:
                self.send_json({"ok": False, "error": "取数失败，请稍后重试"}, status=500)
            return
        if parsed.path == "/api/datacenter/databases":
            if not self.require_superadmin():
                return
            self.send_json(dcdb_instances())
            return
        if parsed.path == "/api/datacenter/storage-map":
            if not self.require_superadmin():
                return
            self.send_json(dcstorage_overview())
            return
        if parsed.path == "/api/datacenter/databases/flow":
            if not self.require_superadmin():
                return
            try:
                self.send_json(dcflow_snapshot())
            except Exception as exc:
                self.send_json({"ok": False, "error": f"采样失败：{type(exc).__name__}: {exc}"[:300]}, status=502)
            return
        if parsed.path == "/api/datacenter/databases/flow/tables":
            user = self.require_superadmin()
            if not user:
                return
            try:
                self.send_json(dcflow_tables(query.get("assistant", [""])[0], query.get("instance", [""])[0],
                                             user.get("username", "")))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": f"读取失败：{type(exc).__name__}: {exc}"[:300]}, status=502)
            return
        if parsed.path == "/api/datacenter/databases/objects":
            user = self.require_superadmin()
            if not user:
                return
            try:
                self.send_json(dcdb_objects(query.get("instance", [""])[0], query.get("db", [""])[0],
                                            user.get("username", ""), query.get("pattern", ["*"])[0]))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": f"访问失败：{type(exc).__name__}: {exc}"[:400]}, status=502)
            return
        if parsed.path == "/api/datacenter/databases/rows":
            user = self.require_superadmin()
            if not user:
                return
            try:
                self.send_json(dcdb_rows(query.get("instance", [""])[0], query.get("db", [""])[0],
                                         query.get("object", [""])[0], query.get("page", ["0"])[0],
                                         query.get("size", ["50"])[0], user.get("username", ""),
                                         query.get("filter", [""])[0]))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": f"访问失败：{type(exc).__name__}: {exc}"[:400]}, status=502)
            return
        if parsed.path == "/api/datacenter/browse":
            if not self.require_superadmin():
                return
            try:
                self.send_json(datacenter_browse(query.get("path", [""])[0], query.get("subject", [""])[0]))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/datacenter/file":
            user = self.require_superadmin()
            if not user:
                return
            try:
                self.send_json(datacenter_preview(query.get("path", [""])[0], user.get("username", ""),
                                                  query.get("table", [""])[0], query.get("offset", [0])[0]))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/datacenter/download":
            user = self.require_superadmin()
            if not user:
                return
            try:
                target = datacenter_download(query.get("path", [""])[0], user.get("username", ""))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(target.name))
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/datacenter/dashboard":
            if not self.require_superadmin():
                return
            self.send_json(datacenter_dashboard())
            return
        if parsed.path == "/api/datacenter/access-log":
            if not self.require_superadmin():
                return
            self.send_json(datacenter_access_log())
            return
        if parsed.path == "/api/datacenter/overview":
            if not self.require_superadmin():
                return
            self.send_json(datacenter_overview())
            return
        if parsed.path == "/api/datacenter/backups":
            if not self.require_superadmin():
                return
            self.send_json(datacenter_backups())
            return
        if parsed.path == "/api/cashflow":
            user = self.require_user()
            if not user:
                return
            self.send_json(cashflow_list(user.get("username", "")))
            return
        if parsed.path == "/api/cashflow/workbook":
            user = self.require_user()
            if not user:
                return
            self.send_json(cashflow_workbook_get(user.get("username", "")))
            return
        if parsed.path == "/api/cashflow/workbook/export":
            user = self.require_user()
            if not user:
                return
            try:
                output_name, raw = cashflow_workbook_export(user.get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(output_name))
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (ValueError, OSError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/cashflow/history":
            user = self.require_user()
            if not user:
                return
            self.send_json(cashflow_history_list(user.get("username", "")))
            return
        if parsed.path == "/api/cashflow/history/records":
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            self.send_json(cashflow_history_records(user.get("username", ""), query.get("keyword", [""])[0], query.get("region", [""])[0], query.get("page", [1])[0], query.get("page_size", [50])[0]))
            return
        if parsed.path.startswith('/api/crm/amap-proxy/_AMapService/'):
            if not self.require_user(): return
            try:
                raw, content_type = crm_amap.fetch_proxy(USER_DATA_DIR, parsed.path.removeprefix('/api/crm/amap-proxy/_AMapService'), parsed.query, crm_configuration_amap_storage())
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'private, no-store')
                self.end_headers()
                self.wfile.write(raw)
            except Exception:
                self.send_json({'ok': False, 'error': '高德服务暂不可用，请检查地图凭据、配额和网络'}, status=502)
            return
        if parsed.path.startswith("/api/crm/security/"):
            user = self.require_user()
            if not user: return
            try:
                if parsed.path == "/api/crm/security/me": result = {"ok":True,"capabilities":crm_capabilities(user)}
                elif parsed.path == "/api/crm/security/users": result = crm_security_users(user)
                elif parsed.path == "/api/crm/security/battle-roster": result = crm_battle_roster()
                elif parsed.path == "/api/crm/security/audit": result = crm_security_audit(user)
                elif parsed.path == "/api/crm/security/region-settings": result = crm_region_settings()
                elif parsed.path == "/api/crm/security/quality-settings": result = crm_quality_settings(user)
                elif parsed.path == "/api/crm/security/amap-settings": result = crm_amap_settings()
                else: result = {"ok":False,"error":"接口不存在"}
                self.send_json(result)
            except (ValueError, PermissionError, OSError) as exc:
                self.send_json({"ok":False,"error":str(exc)}, status=403)
            return
        if parsed.path == "/api/crm/excel/template":
            if not self.require_user():
                return
            raw = crm_business_template()
            raw = crm_trace_export(raw, self.current_user(), parsed.path, 'crm-collection-template.xlsx')
            self._crm_audit_event = None
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename=crm-collection-template.xlsx")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/business-analysis/dashboard":
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            html = crm_business_dashboard_html(user, query.get("version", [""])[0] or None)
            if html is None:
                self.send_json({"ok": False, "error": "看板不可用或无数据"}, status=404)
                return
            raw = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/opportunities/template":
            if not self.require_user():
                return
            raw = crm_opportunity_template()
            filename = "机会点导入模板.xlsx"
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/business-analysis/template":
            user = self.require_user()
            if not user:
                return
            caps = crm_capabilities(user)
            if not caps.get('read') or caps.get('data_scope') != 'all':
                self.send_json({"ok": False, "error": "含公司真实样例的模板仅限管理级下载"}, status=403)
                return
            try:
                query = urllib.parse.parse_qs(parsed.query)
                blocks = [item for item in query.get('blocks', [''])[0].split(',') if item]
                raw, filename, content_type = crm_analysis_template_export(user, query.get('version', [None])[0], blocks)
            except ValueError as error:
                self.send_json({"ok": False, "error": str(error)}, status=400)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/business-analysis/task-order-template":
            if not self.require_user():
                return
            raw = crm_task_order_template()
            filename = "联指经营助手_任务令数据导入模板.xlsx"
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/excel/export":
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            level = query.get("level", ["all"])[0]
            target = query.get("target", [""])[0]
            region = query.get("region", [""])[0]
            try:
                raw, filename = crm_relationship_export(user, level, target, region)
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            raw = crm_trace_export(raw, user, parsed.path, filename, {'level': level, 'target': target, 'region': region})
            self._crm_audit_event = None
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/organization/export":
            user = self.require_user()
            if not user:
                return
            try:
                raw, filename = crm_customer_organization_export(user)
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            raw = crm_trace_export(raw, user, parsed.path, filename)
            self._crm_audit_event = None
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/assignment-directory":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(crm_assignment_directory(user))
            except PermissionError as exc:
                self.send_json({'ok': False, 'error': str(exc)}, status=403)
            return
        if parsed.path == "/api/crm/opportunities/export":
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            state = query.get('state', ['all'])[0]
            stage = query.get('stage', [''])[0]
            keyword = query.get('keyword', [''])[0]
            try:
                raw, filename = crm_opportunity_export(user, state, stage, keyword, query.get('region', [''])[0], query.get('sales_stage', [''])[0])
            except (ValueError, PermissionError) as exc:
                self.send_json({'ok': False, 'error': str(exc)}, status=403)
                return
            raw = crm_trace_export(raw, user, parsed.path, filename, {'state': state, 'stage': stage, 'keyword': keyword})
            self._crm_audit_event = None
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/crm/import-completion/excel":
            user = self.require_user()
            if not user:
                return
            query = urllib.parse.parse_qs(parsed.query)
            try:
                raw, filename = crm_import_completion_excel_export(
                    user, query.get('region', [''])[0], query.get('manager', [''])[0],
                )
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            raw = crm_trace_export(raw, user, parsed.path, filename, {'region': query.get('region', [''])[0], 'manager': query.get('manager', [''])[0]})
            self._crm_audit_event = None
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(filename))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/admin-organization/canvas":
            if not self.require_superadmin():
                return
            self.send_json(internal_organization_get(self.current_user()['username']))
            return
        if parsed.path == "/api/admin-organization/excel":
            if not self.require_superadmin():
                return
            raw = organization_excel_export()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote('公司组织架构表.xlsx'))
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path in {"/api/crm/monthly-battle", "/api/crm/manager-directory", "/api/crm/staff", "/api/crm/playbook", "/api/crm/overview", "/api/crm/units", "/api/crm/people", "/api/crm/relations", "/api/crm/opportunities", "/api/crm/sales-contracts", "/api/crm/history", "/api/crm/project-map", "/api/crm/graph/centrality", "/api/crm/graph/path", "/api/crm/infra", "/api/crm/import-completion/tasks", "/api/crm/business-analysis"}:
            user = self.require_user()
            if not user:
                return
            username = user["username"]
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if parsed.path == "/api/crm/monthly-battle":
                    result = monthly_battle_template(user) if query.get('template') == ['1'] else monthly_battle_read(user, query.get('view', [''])[0], query.get('region', [''])[0], query.get('manager', [''])[0])
                elif parsed.path == "/api/crm/business-analysis":
                    result = crm_business_analysis(user, query.get("version", [""])[0] or None,
                                                   query.get("view", [""])[0], query.get("region", [""])[0],
                                                   query.get("manager", [""])[0])
                elif parsed.path == "/api/crm/playbook":
                    result = crm_read_playbook(user)
                elif parsed.path == "/api/crm/manager-directory":
                    result = crm_manager_directory(user)
                elif parsed.path == "/api/crm/overview":
                    result = crm_read_overview(user)
                elif parsed.path == "/api/crm/staff":
                    result = {"ok": True, "staff": crm_read_snapshot(user, ('staff',))['staff']}
                elif parsed.path == "/api/crm/units":
                    result = crm_read_units(user)
                elif parsed.path == "/api/crm/people":
                    result = crm_read_people(user)
                elif parsed.path == "/api/crm/relations":
                    result = crm_read_relations(user)
                elif parsed.path == "/api/crm/opportunities":
                    result = crm_read_opportunities(user)
                elif parsed.path == "/api/crm/sales-contracts":
                    result = crm_read_sales_contracts(user)
                elif parsed.path == "/api/crm/history":
                    result = {"ok": True, "versions": crm_record_versions(username, query.get('collection', [''])[0], query.get('record_id', [''])[0])}
                elif parsed.path == "/api/crm/graph/centrality":
                    result = {"ok": True, "centrality": crm_graph_centrality(username), "source": "neo4j" if crm_neo4j() else "unavailable"}
                elif parsed.path == "/api/crm/graph/path":
                    result = crm_path_to_person(username, query.get("target", [""])[0])
                elif parsed.path == "/api/crm/infra":
                    result = {"ok": True, "infra": crm_infra_status()}
                elif parsed.path == "/api/crm/import-completion/tasks":
                    result = crm_import_completion_tasks(user)
                else:
                    result = crm_project_map(username, query.get("project_id", [""])[0])
                self.send_json(result, headers={"Cache-Control": "no-store"})
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            except Exception:
                self.send_json({"ok": False, "error": "客户经营数据读取失败，请稍后重试"}, status=500)
            return
        if parsed.path == "/api/projects/get":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(project_get(qs.get("id", [""])[0], self.current_user().get("username", "")))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            return
        if parsed.path == "/api/projects/timeline":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(project_timeline(qs.get("id", [""])[0], self.current_user().get("username", "")))
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            return
        if parsed.path == "/api/projects/admins":
            try:
                self.send_json(project_admins_payload(self.current_user().get("username", "")))
            except PermissionError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            return
        if parsed.path == "/api/projects/file":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                name, raw = project_file(qs.get("id", [""])[0], qs.get("file_id", [""])[0], self.current_user().get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", mail_part_content_type_from_name(name, raw))
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(name)}")
                self.end_headers()
                self.wfile.write(raw)
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            return
        if parsed.path == "/api/projects/report-file":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                name, raw = project_report_file(qs.get("id", [""])[0], qs.get("report_id", [""])[0], self.current_user().get("username", ""))
                self.send_response(200)
                self.send_header("Content-Type", mail_part_content_type_from_name(name, raw))
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(name)}")
                self.end_headers()
                self.wfile.write(raw)
            except (ValueError, PermissionError) as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=403)
            return
        if parsed.path == "/api/forum/topics":
            self.send_json(forum_list_topics(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/forum/topic":
            qs = urllib.parse.parse_qs(parsed.query)
            self.send_json(forum_get_topic({"id": qs.get("id", [""])[0]}, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/tickets":
            self.send_json(ticket_list(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/tickets/get":
            qs = urllib.parse.parse_qs(parsed.query)
            self.send_json(ticket_get({"id": qs.get("id", [""])[0]}, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/news/latest":
            user = self.current_user() or {}
            self.send_json(news_latest(user.get("role") == "superadmin"))
            return
        if parsed.path == "/api/news/history":
            user = self.current_user() or {}
            qs = urllib.parse.parse_qs(parsed.query)
            payload = {k: v[0] for k, v in qs.items()}
            self.send_json(news_history_api(payload, self.current_user().get("username", ""), user.get("role") == "superadmin"))
            return
        if parsed.path == "/api/news/config":
            if not self.require_superadmin():
                return
            self.send_json({"ok": True, "config": news_config_payload()})
            return
        if parsed.path == "/api/news/wechat-accounts":
            if not self.require_user():
                return
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                self.send_json(search_wechat_accounts(qs.get("query", [""])[0]))
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path == "/api/news/wechat-auth-status":
            if not self.require_user():
                return
            self.send_json(wechat_auth_status())
            return
        if parsed.path == "/api/news/personal/latest":
            self.send_json(personal_news_latest(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/news/personal/history":
            qs = urllib.parse.parse_qs(parsed.query)
            payload = {k: v[0] for k, v in qs.items()}
            self.send_json(personal_news_history_api(payload, self.current_user().get("username", "")))
            return
        if parsed.path == "/api/news/personal/config":
            self.send_json({"ok": True, "config": personal_news_config_payload(self.current_user().get("username", ""))})
            return
        if parsed.path == "/api/news/favorites":
            qs = urllib.parse.parse_qs(parsed.query)
            payload = {k: v[0] for k, v in qs.items()}
            self.send_json(news_favorites_api(payload, self.current_user().get("username", "")))
            return
        if parsed.path == "/download":
            qs = urllib.parse.parse_qs(parsed.query)
            file_name = qs.get("file", [""])[0]
            path = attachment_path_by_name(file_name, self.current_user().get("username", ""))
            raw = office_blob_read("reports", path) if path is not None else None
            if raw is None:
                self.send_json({"error": "文件不存在"}, status=404)
                return
            ctype, encoding = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            encoded_name = urllib.parse.quote(path.name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/download-template":
            qs = urllib.parse.parse_qs(parsed.query)
            kind = safe_report_kind(qs.get("kind", ["weekly"])[0])
            path = configured_template_path(kind, self.current_user().get("username", ""))
            raw = office_blob_read("reports", path) if path is not None else None
            if raw is None:
                self.send_json({"error": "平台还没有保存自定义模板，请先上传模板。"}, status=404)
                return
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            encoded_name = urllib.parse.quote(path.name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path.startswith("/forum-attachment/"):
            if not self.require_user():
                return
            parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
            attachment_id = parts[1] if len(parts) >= 2 else ""
            found = forum_attachment_content(attachment_id)
            if found is None:
                self.send_json({"error": "附件不存在"}, status=404)
                return
            path, raw = found
            ctype, _ = mimetypes.guess_type(str(path))
            ctype = ctype or "application/octet-stream"
            display_name = parts[2] if len(parts) >= 3 else path.name
            disposition = "inline" if ctype.startswith("image/") else "attachment"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.send_header("Content-Disposition", f"{disposition}; filename*=UTF-8''{urllib.parse.quote(display_name)}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/preview-image":
            if not self.require_user():
                return
            qs = urllib.parse.parse_qs(parsed.query)
            file_name = Path(qs.get("file", [""])[0]).name
            path = user_generated_dir(self.current_user().get("username", "")) / file_name
            raw = office_blob_read("reports", path) if file_name and path.suffix.lower() == ".png" else None
            if raw is None:
                self.send_json({"error": "预览图片不存在"}, status=404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.end_headers()
            self.wfile.write(raw)
            return
        # Serve static root files from FRONTEND_DIR (e.g. /logo.ico, /favicon.svg)
        static_path = FRONTEND_DIR / Path(urllib.parse.unquote(parsed.path)).name
        if parsed.path.count("/") == 1 and static_path.exists() and static_path.is_file() and not parsed.path.startswith("/api"):
            raw = static_path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(static_path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(raw)
            return
        # SPA fallback: serve index.html for non-API, non-file paths
        if not parsed.path.startswith("/api") and not parsed.path.startswith("/mcp") and "." not in Path(parsed.path).name:
            raw = app_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_PUT(self):
        set_request_username("")
        if not self.check_assistant_permission():
            return
        if self.path == "/records" or self.path.startswith("/records/"):
            self._proxy_records_collector()
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        set_request_username("")
        if not self.check_assistant_permission():
            return
        if self.path == "/records" or self.path.startswith("/records/"):
            self._proxy_records_collector()
            return
        if self._handle_fastgpt_kb_bridge():
            return
        if self.path.startswith("/api/aiproxy/api/"):
            self._proxy_aiproxy_api("/api/" + self.path[len("/api/aiproxy/api/"):])
            return
        if self._is_aiproxy_api_request():
            self._proxy_aiproxy_api()
            return
        if self._is_fastgpt_request():
            self._proxy_fastgpt()
            return
        if self.path.startswith(APP_RELATIVE_PATH + "/wechat-article"):
            self._proxy_wechat_exporter()
            return
        if self.path == "/gateway" or self.path.startswith("/gateway/"):
            self._proxy_gateway()
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith(APP_RELATIVE_PATH + "/"):
            parsed = parsed._replace(path=parsed.path[len(APP_RELATIVE_PATH):] or "/")
        if parsed.path == "/mcp":
            auth = self.headers.get("Authorization", "")
            query = urllib.parse.parse_qs(parsed.query)
            # FastGPT MCP collections are configured by URL and do not provide
            # custom headers.  The query values are accepted solely for its
            # private Docker-network endpoint; ordinary clients keep using
            # Bearer + X-MCP-Username.
            mcp_user = self.headers.get("X-MCP-Username", "") or query.get("username", [""])[0]
            access_token = query.get("access_token", [""])[0]
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body_raw = self.rfile.read(length)
            except Exception:
                body_raw = b"{}"
            status, resp = mcp_handle_post(auth, mcp_user, body_raw, access_token)
            if resp is None:
                self.send_response(204)
                self.end_headers()
            else:
                raw = json.dumps(resp, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            return
        if parsed.path == "/api/knowledge/ask-stream":
            user = self.require_user()
            if not user:
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except Exception:
                payload = {}
            kb_ask_stream(self, payload, user.get("username", ""))
            return
        if parsed.path in {"/api/crm/excel/import", "/api/crm/opportunities/import", "/api/crm/sales-contracts/import", "/api/crm/business-analysis/import", "/api/crm/business-analysis/task-order-import"} and int(self.headers.get("Content-Length", "0") or 0) > 8 * 1024 * 1024:
            self.send_json({"ok": False, "error": "文件不能超过5MB"}, status=413)
            return
        try:
            if parsed.path == "/api/forum/attachment" and self.headers.get("Content-Type", "").lower().startswith("multipart/form-data"):
                if not self.require_user():
                    return
                import cgi
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                        "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                    },
                )
                file_item = form["file"] if "file" in form else None
                if file_item is None or not getattr(file_item, "filename", ""):
                    raise ValueError("请选择要上传的附件")
                raw = file_item.file.read()
                result = forum_upload_attachment_file(
                    file_item.filename,
                    getattr(file_item, "type", "") or self.headers.get("Content-Type", ""),
                    raw,
                    self.current_user().get("username", ""),
                )
                self.send_json(result)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if parsed.path == "/api/login":
                user = find_user(payload.get("username", ""), payload.get("password", ""))
                if not user:
                    self.send_json({"ok": False, "error": "用户名或密码错误"}, status=401)
                    return
                ensure_user_space(user.get("username", ""))
                token = create_login_session(user)
                self.send_json(
                    {
                        "ok": True,
                        "user": public_user(user),
                        "assistant_prompt": read_config().get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT),
                    },
                    headers={"Set-Cookie": f"pws_session={token}; Path=/; HttpOnly; SameSite=Lax"},
                )
                return
            if parsed.path == "/api/logout":
                token = self.cookie_value("pws_session")
                delete_login_session(token)
                self.send_json({"ok": True}, headers={"Set-Cookie": "pws_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
                return
            if parsed.path == "/api/password-reset/captcha":
                self.send_json(create_password_reset_captcha())
                return
            if parsed.path == "/api/password-reset/request":
                try:
                    self.send_json(request_password_reset(payload))
                except ValueError as exc:
                    self.send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/password-reset/confirm":
                try:
                    self.send_json(confirm_password_reset(payload))
                except ValueError as exc:
                    self.send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path.startswith("/api/") and not self.require_user():
                return
            username = self.current_user().get("username", "")
            if not self.check_assistant_permission(payload):
                return
            if parsed.path == "/api/send":
                result = send_mail(payload, username)
            elif parsed.path == "/api/mail-send":
                payload["body_html"] = ""
                result = send_mail(payload, username)
            elif parsed.path == "/api/mailbox-mark-read":
                result = mark_inbox_message_read(username, payload.get("uid", ""))
            elif parsed.path == "/api/generate":
                result = generate_document(payload, username)
            elif parsed.path == "/api/optimize":
                result = optimize_text(payload)
            elif parsed.path == "/api/chat":
                result = digital_human_chat(payload, username)
            elif parsed.path == "/api/tts":
                result = digital_human_tts(payload)
            elif parsed.path == "/api/tts-config":
                if not self.require_admin():
                    return
                result = save_digital_human_tts_config(payload)
            elif parsed.path == "/api/tts-voices":
                if not self.require_admin():
                    return
                result = probe_tts_api_voices(payload)
            elif parsed.path == "/api/meeting-config":
                if not self.require_admin():
                    return
                result = save_meeting_config(payload)
            elif parsed.path == "/api/meeting-test":
                if not self.require_admin():
                    return
                result = meeting_test_asr(payload)
            elif parsed.path == "/api/knowledge-config":
                if not self.require_admin():
                    return
                result = save_kb_config(payload)
            elif parsed.path == "/api/knowledge-test":
                if not self.require_admin():
                    return
                result = kb_test_embedding(payload)
            elif parsed.path == "/api/xinference-probe":
                if not self.require_admin():
                    return
                result = xinference_probe(payload)
            elif parsed.path == "/api/xinference-apply":
                if not self.require_admin():
                    return
                result = xinference_apply(payload)
            elif parsed.path == "/api/writing/upload":
                result = writing_upload(payload, username)
            elif parsed.path == "/api/writing/templates":
                result = writing_save_template(payload, username)
            elif parsed.path == "/api/writing/outline":
                result = writing_generate_outline(payload, username)
            elif parsed.path == "/api/writing/generate":
                result = writing_generate(payload, username)
            elif parsed.path == "/api/writing/rewrite":
                result = writing_rewrite(payload, username)
            elif parsed.path == "/api/writing/export":
                result = writing_export(payload, username)
            elif parsed.path == "/api/writing/delete":
                result = writing_delete_history(payload, username)
            elif parsed.path == "/api/writing/upload-delete":
                result = writing_delete_upload(payload, username)
            elif parsed.path == "/api/knowledge/upload":
                result = kb_upload(payload, username)
            elif parsed.path == "/api/knowledge/delete":
                result = kb_delete(payload, username)
            elif parsed.path == "/api/knowledge/search":
                result = kb_search(payload, username)
            elif parsed.path == "/api/knowledge/ask":
                result = kb_ask(payload, username)
            elif parsed.path == "/api/knowledge/reparse":
                result = kb_reparse(payload, username)
            elif parsed.path == "/api/knowledge/kbs":
                result = kb_dataset_manage(payload, username)
            elif parsed.path == "/api/digital-human/kb-config":
                result = save_digital_human_kb(payload, username)
            elif parsed.path == "/api/knowledge/chat-sessions":
                result = kb_chat_sessions(payload, username)
            elif parsed.path == "/api/knowledge/chat-clear":
                result = kb_chat_clear(username, payload.get("session_id", ""))
            elif parsed.path == "/api/knowledge/pdf-md/create":
                result = pdf_md_create(payload, username)
            elif parsed.path == "/api/knowledge/pdf-md/parse":
                result = pdf_md_parse(payload, username)
            elif parsed.path == "/api/knowledge/pdf-md/region":
                result = pdf_md_region(payload, username)
            elif parsed.path == "/api/knowledge/pdf-md/save":
                result = pdf_md_save(payload, username)
            elif parsed.path == "/api/knowledge/pdf-md/delete":
                result = pdf_md_delete(payload, username)
            elif parsed.path == "/api/knowledge/pdf-md/to-kb":
                result = pdf_md_to_kb(payload, username)
            elif parsed.path == "/api/ragflow/bootstrap":
                if not self.require_admin():
                    return
                result = kb_ragflow_bootstrap(payload)
            elif parsed.path == "/api/ragflow/chunk-config":
                if not self.require_admin():
                    return
                result = kb_ragflow_save_chunk_config(payload)
            elif parsed.path == "/api/meeting/transcribe":
                result = meeting_transcribe(payload, username)
            elif parsed.path == "/api/meeting/translate":
                result = meeting_translate(payload)
            elif parsed.path == "/api/meeting/summarize":
                result = meeting_summarize(payload, username)
            elif parsed.path == "/api/meeting/save":
                result = meeting_save(payload, username)
            elif parsed.path == "/api/meeting/delete":
                result = meeting_delete(payload, username)
            elif parsed.path == "/api/agent":
                result = agent_chat(payload, username)
            elif parsed.path == "/api/agent/chat":
                result = agent_chat(payload, username)
            elif parsed.path == "/api/agent/sessions":
                result = agent_sessions_api(payload, username)
            elif parsed.path == "/api/workflows":
                result = workflows_api(payload, username)
            elif parsed.path == "/api/skills/execute":
                result = execute_skill_request(payload, username)
            elif parsed.path == "/api/skill-invocations":
                result = skill_invocation_history(payload, username)
            elif parsed.path == "/api/skill-test":
                if not self.require_superadmin():
                    return
                result = skill_test(payload, username)
            elif parsed.path == "/api/agent-config":
                if not self.require_superadmin():
                    return
                result = save_agent_config(payload)
            elif parsed.path == "/api/upload-history":
                result = upload_history_reports(payload, username)
            elif parsed.path == "/api/report-template":
                result = save_report_template(payload, username)
            elif parsed.path == "/api/report-template-delete":
                result = delete_report_template(payload, username)
            elif parsed.path == "/api/report-templates":
                result = report_template_info(username)
            elif parsed.path == "/api/delete-report":
                result = delete_report_file(payload, username)
            elif parsed.path == "/api/delete-history":
                result = delete_history_report(payload, username)
            elif parsed.path == "/api/change-password":
                result = change_password(payload, username)
            elif parsed.path == "/api/profile":
                result = save_user_profile(payload, username)
            elif parsed.path == "/api/nav-prefs":
                result = save_nav_prefs(payload, username)
            elif parsed.path == "/api/reimbursement/upload":
                result = save_reimbursement_upload(username, payload.get("filename", "attachment"), payload.get("data", ""))
            elif parsed.path == "/api/reimbursement/fetch-url":
                result = fetch_and_save_url(
                    username,
                    payload.get("url", ""),
                    payload.get("hint_subject", ""),
                    payload.get("hint_body", ""),
                )
            elif parsed.path == "/api/reimbursement/merge":
                result = merge_reimbursement_pdf(username, payload.get("items", []), payload.get("output_name", "报销附件"), bool(payload.get("merge_train_tickets")))
            elif parsed.path == "/api/reimbursement/download-zip":
                result = download_reimbursement_invoices_zip(username, payload.get("items", []), payload.get("output_name", "发票批量下载"))
            elif parsed.path == "/api/reimbursement/search":
                result = save_reimbursement_search(username, payload)
            elif parsed.path == "/api/mail-config":
                result = save_user_mail_config(username, payload)
            elif parsed.path == "/api/test-mail-config":
                account = str(payload.get("account") or "company").strip()
                result = test_user_mail_config(username, account)
            elif parsed.path == "/api/admin-config":
                if not self.require_admin():
                    return
                result = save_admin_config(payload)
            elif parsed.path == "/api/server-config":
                if not self.require_superadmin():
                    return
                result = save_server_config(payload)
            elif parsed.path == "/api/admin-models":
                if not self.require_admin():
                    return
                result = list_admin_models(payload)
            elif parsed.path == "/api/admin-test-model":
                if not self.require_admin():
                    return
                result = test_admin_model(payload)
            elif parsed.path == "/api/admin-users":
                if not self.require_superadmin():
                    return
                result = add_user(payload, username)
            elif parsed.path == "/api/admin-users-delete":
                if not self.require_superadmin():
                    return
                result = delete_user(payload, username)
            elif parsed.path == "/api/admin-users-update":
                if not self.require_superadmin():
                    return
                result = update_user(payload, username)
            elif parsed.path == "/api/admin-users-batch-permissions":
                if not self.require_superadmin():
                    return
                result = batch_update_assistant_permissions(payload, username)
            elif parsed.path == "/api/admin-users-assistant-batch":
                result = batch_update_assistant_users(payload, username)
            elif parsed.path == "/api/admin-organization/canvas":
                if not self.require_superadmin():
                    return
                result = internal_organization_save(payload, username)
            elif parsed.path == "/api/admin-organization/import":
                if not self.require_superadmin():
                    return
                result = organization_excel_import(payload, username)
            elif parsed.path == "/api/diary/save":
                result = save_diary(payload, username)
            elif parsed.path == "/api/diary/delete":
                result = delete_diary(payload.get("date", ""), username)
            elif parsed.path == "/api/diary/summarize":
                result = summarize_diaries_for_weekly(payload, username)
            elif parsed.path == "/api/projects/create":
                result = project_create(payload, username)
            elif parsed.path == "/api/ledger/save":
                result = ledger_save(payload, username)
            elif parsed.path == "/api/datacenter/apikeys/create":
                if not self.require_superadmin():
                    return
                result = dapi_create_key(payload, username)
            elif parsed.path == "/api/datacenter/apikeys/revoke":
                if not self.require_superadmin():
                    return
                result = dapi_revoke_key(payload, username)
            elif parsed.path == "/api/datacenter/sync/run":
                if not self.require_superadmin():
                    return
                result = datacenter_trigger_db_sync(username)
            elif parsed.path == "/api/datacenter/backup/run":
                if not self.require_superadmin():
                    return
                result = datacenter_trigger_backup(username)
            elif parsed.path == "/api/datacenter/refresh":
                if not self.require_superadmin():
                    return
                result = datacenter_refresh(username)
            elif parsed.path == "/api/datacenter/databases/query":
                if not self.require_superadmin():
                    return
                result = dcdb_query(payload.get("instance", ""), payload.get("db", ""),
                                    payload.get("sql", ""), username)
            elif parsed.path == "/api/cashflow/save":
                result = cashflow_save(payload, username)
            elif parsed.path == "/api/cashflow/workbook/save":
                result = cashflow_workbook_save(payload, username)
            elif parsed.path == "/api/cashflow/history/import":
                result = cashflow_history_import(payload, username)
            elif parsed.path == "/api/cashflow/history/save":
                result = cashflow_history_save(payload, username)
            elif parsed.path == "/api/cashflow/history/delete":
                result = cashflow_history_delete(payload.get("id", ""), username)
            elif parsed.path == "/api/contracts/upload":
                result = contract_upload(payload, username)
            elif parsed.path == "/api/contracts/archive":
                result = contract_archive(payload, username)
            elif parsed.path == "/api/contracts/extract":
                result = contract_extract_preview(payload, username)
            elif parsed.path == "/api/contracts/save":
                result = contract_save(payload, username)
            elif parsed.path == "/api/contracts/generate":
                result = contract_generate(payload, username)
            elif parsed.path == "/api/crm/staff/save":
                result = crm_staff_save(payload, username)
            elif parsed.path == "/api/crm/unit/save":
                result = crm_unit_save(payload, username)
            elif parsed.path == "/api/crm/unit/delete":
                result = crm_unit_delete(payload.get("id", ""), username)
            elif parsed.path == "/api/crm/department/node":
                result = crm_department_node(payload, username)
            elif parsed.path == "/api/crm/person/save":
                result = crm_person_save(payload, username)
            elif parsed.path == "/api/crm/relation/save":
                result = crm_relation_save_authorized(payload, self.current_user())
            elif parsed.path == "/api/crm/bulk-update":
                result = crm_bulk_update(payload, username)
            elif parsed.path == "/api/crm/relations/batch-assign":
                result = crm_relation_batch_assign(payload, self.current_user())
            elif parsed.path == "/api/crm/security/appoint":
                result = crm_security_grant(payload, self.current_user(), mode="appoint")
            elif parsed.path == "/api/crm/security/region-settings":
                result = crm_region_settings_save(payload, self.current_user())
            elif parsed.path == "/api/crm/security/battle-roster":
                result = crm_battle_roster_save(payload, self.current_user())
            elif parsed.path == "/api/crm/security/quality-settings":
                result = crm_quality_settings_save(payload, self.current_user())
            elif parsed.path == "/api/crm/security/amap-settings":
                result = crm_amap_settings_save(payload, self.current_user())
            elif parsed.path == "/api/crm/security/grant":
                result = crm_security_grant(payload, self.current_user())
            elif parsed.path == "/api/crm/security/batch-grant":
                result = crm_security_batch_grant(payload, self.current_user())
            elif parsed.path == "/api/crm/security/liaison-region":
                result = crm_liaison_region_save(payload, self.current_user())
            elif parsed.path == "/api/crm/quick-create":
                result = crm_quick_create(payload, username)
            elif parsed.path == "/api/crm/excel/import":
                result = crm_excel_import(payload, username)
            elif parsed.path == "/api/crm/opportunities/import":
                result = crm_opportunity_import(payload, username)
            elif parsed.path == "/api/crm/sales-contracts/import":
                result = crm_sales_contract_import(payload, username)
            elif parsed.path == "/api/crm/business-analysis/import":
                result = crm_business_import(payload, username)
            elif parsed.path == "/api/crm/business-analysis/task-order-import":
                result = crm_task_order_import(payload, username)
            elif parsed.path == "/api/crm/monthly-battle/import":
                result = monthly_battle_import(payload, self.current_user())
            elif parsed.path == "/api/crm/monthly-battle/progress":
                result = monthly_battle_progress(payload, self.current_user())
            elif parsed.path == "/api/crm/monthly-battle/comment":
                result = monthly_battle_comment(payload, self.current_user())
            elif parsed.path == "/api/crm/opportunity/save":
                result = crm_opportunity_save(payload, username)
            elif parsed.path == "/api/crm/opportunity/stage-save":
                result = crm_opportunity_stage_update(payload, username)
            elif parsed.path == "/api/crm/excel/retry-rows":
                result = crm_excel_retry_rows(payload, username)
            elif parsed.path == "/api/crm/import-completion/complete":
                result = crm_import_completion_complete(payload, self.current_user())
            elif parsed.path == "/api/crm/import-completion/excel":
                result = crm_import_completion_excel_import(payload, self.current_user())
            elif parsed.path == "/api/crm/followup/complete":
                result = crm_followup_complete_authorized(payload, self.current_user())
            elif parsed.path == "/api/crm/action/add":
                result = crm_action_add_authorized(payload, self.current_user())
            elif parsed.path == "/api/crm/link/save":
                result = crm_link_save(payload, username)
            elif parsed.path == "/api/crm/battle-map/generate":
                result = crm_battle_map_generate(payload, username)
            elif parsed.path == "/api/crm/import-from-contract":
                result = crm_import_from_contract(payload, username)
            elif parsed.path == "/api/ledger/delete":
                result = ledger_delete(payload.get("id", ""), username)
            elif parsed.path == "/api/cashflow/delete":
                result = cashflow_delete(payload.get("id", ""), username)
            elif parsed.path == "/api/projects/update":
                result = project_update(payload, username)
            elif parsed.path == "/api/projects/delete":
                result = project_delete(payload, username)
            elif parsed.path == "/api/projects/members":
                result = project_save_members(payload, username)
            elif parsed.path == "/api/projects/upload":
                result = project_upload_file(payload, username)
            elif parsed.path == "/api/projects/admins":
                result = project_save_admins(payload, username)
            elif parsed.path == "/api/forum/attachment":
                result = forum_upload_attachment(payload, username)
            elif parsed.path == "/api/forum/create":
                result = forum_create_topic(payload, username)
            elif parsed.path == "/api/forum/comment":
                result = forum_add_comment(payload, username)
            elif parsed.path == "/api/forum/like":
                result = forum_toggle_like(payload, username)
            elif parsed.path == "/api/forum/pin":
                if not self.require_superadmin():
                    return
                result = forum_set_topic_pinned(payload, username)
            elif parsed.path == "/api/forum/ai-topic":
                result = forum_ai_topic(payload, username)
            elif parsed.path == "/api/forum/ai-comment":
                result = forum_ai_comment(payload, username)
            elif parsed.path == "/api/tickets/create":
                result = ticket_create(payload, username)
            elif parsed.path == "/api/tickets/comment":
                result = ticket_add_comment(payload, username)
            elif parsed.path == "/api/news/config":
                if not self.require_superadmin():
                    return
                result = save_news_config(payload)
            elif parsed.path == "/api/news/generate":
                if not self.require_superadmin():
                    return
                payload["_local_only"] = True
                payload["auto_search"] = False
                payload["_enrich"] = True
                result = generate_news_issue(payload, username)
            elif parsed.path == "/api/news/personal/config":
                result = save_personal_news_config(username, payload)
            elif parsed.path == "/api/news/personal/generate":
                payload["_local_only"] = True
                payload["auto_search"] = False
                payload["_enrich"] = True
                result = generate_personal_news_issue(payload, username)
            elif parsed.path == "/api/news/favorites":
                result = add_news_favorite(payload, username)
            elif parsed.path == "/api/news/favorites/delete":
                result = remove_news_favorite(payload, username)
            elif parsed.path == "/api/mcp-config":
                if not self.require_admin():
                    return
                result = save_mcp_config(payload)
            elif parsed.path == "/api/fastgpt-sync":
                if not self.require_admin():
                    return
                result = sync_fastgpt(self.current_user().get("username", "admin"))
            elif parsed.path == "/api/install-mcp-to-lobster":
                if not self.require_admin():
                    return
                agent_id = int(payload.get("agent_id", 0))
                if not agent_id:
                    raise ValueError("agent_id is required")
                mcp_cfg = mcp_config_api()
                if not mcp_cfg.get("enabled"):
                    raise ValueError("MCP 服务未启用，请先在 MCP 管理页生成密钥后再安装")
                mcp_secret = str(read_config().get("mcp_secret", "") or "")
                mcp_endpoint = _self_mcp_endpoint(self.headers)
                token = _openclaw_sso_token(public_user(self.current_user()))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                install_payload = json.dumps({
                    "name": "personal-office-assistant",
                    "endpoint": mcp_endpoint,
                    "auth_token": mcp_secret,
                    "permission_level": "read",
                    "username": self.current_user().get("username", ""),
                }, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    f"{target}/api/agents/{agent_id}/mcp-install",
                    data=install_payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with opener.open(req, timeout=15) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                if not result.get("ok"):
                    raise ValueError(result.get("detail") or "安装失败")
            elif parsed.path == "/api/lobster-model-options":
                user = self.require_user()
                if not user:
                    return
                agent_id = int(payload.get("agent_id", 0))
                if not agent_id:
                    raise ValueError("agent_id is required")
                token = _openclaw_sso_token(public_user(user))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(
                    f"{target}/api/agents/{agent_id}/model-options",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with opener.open(req, timeout=15) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            elif parsed.path == "/api/update-lobster-model":
                user = self.require_user()
                if not user:
                    return
                agent_id = int(payload.get("agent_id", 0))
                model_name = str(payload.get("model_name") or payload.get("model") or "").strip()
                if not agent_id:
                    raise ValueError("agent_id is required")
                if not model_name:
                    raise ValueError("model_name is required")
                token = _openclaw_sso_token(public_user(user))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(
                    f"{target}/api/agents/{agent_id}/model",
                    data=json.dumps({"model_name": model_name}, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with opener.open(req, timeout=15) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            elif parsed.path == "/api/restart-lobster":
                if not self.require_admin():
                    return
                agent_id = int(payload.get("agent_id", 0))
                if not agent_id:
                    raise ValueError("agent_id is required")
                token = _openclaw_sso_token(public_user(self.current_user()))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(
                    f"{target}/api/agents/{agent_id}/restart",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with opener.open(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            elif parsed.path == "/api/assistant-lobster":
                # 保存/清除悬浮助手绑定的龙虾（agent_id 为空=解绑）。
                agent_id = payload.get("agent_id")
                lobster = save_assistant_lobster(username, agent_id, payload.get("agent_name", ""))
                result = {"ok": True, "lobster": lobster}
            elif parsed.path == "/api/lobster-chat":
                # 悬浮助手对话桥接到绑定的龙虾：经 SSO 调平台 chat 端点。
                message = str(payload.get("message", "") or "").strip()
                if not message:
                    raise ValueError("message is required")
                bound = get_assistant_lobster(username)
                agent_id = int(payload.get("agent_id") or (bound or {}).get("agent_id") or 0)
                if not agent_id:
                    raise ValueError("尚未绑定龙虾，请先在设置页绑定")
                session_id = str(payload.get("session_id") or "").strip() or f"office-assistant-{username}"
                token = _openclaw_sso_token(public_user(self.current_user()))
                target = os.getenv("OPENCLAW_PLATFORM_INTERNAL_URL", "http://127.0.0.1:18080/openclaw").rstrip("/")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(
                    f"{target}/api/agents/{agent_id}/chat",
                    data=json.dumps({"message": message, "session_id": session_id}, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                    method="POST",
                )
                with opener.open(req, timeout=185) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            else:
                self.send_json({"error": "Not found"}, status=404)
                return
            self.send_json(result)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)


def main():
    init_db()
    load_agent_config()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=news_auto_worker, daemon=True).start()
    threading.Thread(target=mail_inbox_auto_worker, daemon=True).start()
    print(f"个人工作报告邮件助手已启动：http://{host}:{port}")
    print(f"英文相对访问地址：{APP_RELATIVE_PATH}")
    print(f"完整访问地址：http://{host}:{port}{APP_RELATIVE_PATH}")
    print(f"用户数据目录：{USER_DATA_DIR}")
    print(f"共享模板目录：{REPORT_DIR}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()
