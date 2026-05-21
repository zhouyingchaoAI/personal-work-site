"""HTTP request handler and application startup.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

def app_html():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, data, status=200, headers=None):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
        username = SESSIONS.get(token)
        return find_user(username) if username else None

    def require_user(self):
        user = self.current_user()
        if not user:
            self.send_json({"ok": False, "error": "请先登录"}, status=401)
            return None
        return user

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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith(APP_RELATIVE_PATH + "/"):
            parsed = parsed._replace(path=parsed.path[len(APP_RELATIVE_PATH):] or "/")
        if parsed.path in ("/", APP_RELATIVE_PATH, APP_RELATIVE_PATH + "/"):
            raw = app_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
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
            asset_name = Path(urllib.parse.unquote(parsed.path)).name
            path = BASE_DIR / "assets" / asset_name
            if not path.exists() or not path.is_file():
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "public, max-age=86400")
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
            path = user_profile_dir(name) / "avatar.png"
            if not path.exists():
                self.send_json({"error": "Not found"}, status=404)
                return
            raw = path.read_bytes()
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
        if parsed.path == "/api/admin-config":
            if not self.require_admin():
                return
            self.send_json(admin_config_payload())
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
        if parsed.path.startswith("/api/") and not self.require_user():
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
            data.pop("smtp_password", None)
            data.pop("imap_password", None)
            self.send_json(data)
            return
        if parsed.path == "/api/mailbox":
            qs = urllib.parse.parse_qs(parsed.query)
            limit = qs.get("limit", ["20"])[0]
            refresh = qs.get("refresh", ["0"])[0] == "1"
            try:
                self.send_json(list_inbox_messages(self.current_user().get("username", ""), limit, refresh))
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
        if parsed.path == "/api/reports":
            username = self.current_user().get("username", "")
            files = sorted(all_files(username), key=lambda item: (item["generated"] if "generated" in item else False, item["kind"], item["sort_key"], item["mtime"]), reverse=True)
            self.send_json(
                {
                    "reports": files,
                    "latest_weekly": (newest("weekly", username, fallback_shared=True) or {}).get("name", ""),
                    "latest_trip": (newest("trip", username, fallback_shared=True) or {}).get("name", ""),
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
        if parsed.path == "/api/forum/topics":
            self.send_json(forum_list_topics(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/forum/topic":
            qs = urllib.parse.parse_qs(parsed.query)
            self.send_json(forum_get_topic({"id": qs.get("id", [""])[0]}, self.current_user().get("username", "")))
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
        if parsed.path == "/download":
            qs = urllib.parse.parse_qs(parsed.query)
            file_name = qs.get("file", [""])[0]
            path = attachment_path_by_name(file_name, self.current_user().get("username", ""))
            if path is None:
                self.send_json({"error": "文件不存在"}, status=404)
                return
            raw = path.read_bytes()
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
            if path is None:
                self.send_json({"error": "平台还没有保存自定义模板，请先上传模板。"}, status=404)
                return
            raw = path.read_bytes()
            ctype, _ = mimetypes.guess_type(str(path))
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            encoded_name = urllib.parse.quote(path.name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/preview-image":
            if not self.require_user():
                return
            qs = urllib.parse.parse_qs(parsed.query)
            file_name = Path(qs.get("file", [""])[0]).name
            path = user_generated_dir(self.current_user().get("username", "")) / file_name
            if path.suffix.lower() != ".png" or not path.exists() or not path.is_file():
                self.send_json({"error": "预览图片不存在"}, status=404)
                return
            raw = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith(APP_RELATIVE_PATH + "/"):
            parsed = parsed._replace(path=parsed.path[len(APP_RELATIVE_PATH):] or "/")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if parsed.path == "/api/login":
                user = find_user(payload.get("username", ""), payload.get("password", ""))
                if not user:
                    self.send_json({"ok": False, "error": "用户名或密码错误"}, status=401)
                    return
                ensure_user_space(user.get("username", ""))
                token = secrets.token_urlsafe(24)
                SESSIONS[token] = user.get("username", "")
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
                if token in SESSIONS:
                    del SESSIONS[token]
                self.send_json({"ok": True}, headers={"Set-Cookie": "pws_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
                return
            if parsed.path.startswith("/api/") and not self.require_user():
                return
            username = self.current_user().get("username", "")
            if parsed.path == "/api/send":
                result = send_mail(payload, username)
            elif parsed.path == "/api/mail-send":
                payload["body_html"] = ""
                result = send_mail(payload, username)
            elif parsed.path == "/api/generate":
                result = generate_document(payload, username)
            elif parsed.path == "/api/optimize":
                result = optimize_text(payload)
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
            elif parsed.path == "/api/mail-config":
                result = save_user_mail_config(username, payload)
            elif parsed.path == "/api/test-mail-config":
                result = test_user_mail_config(username)
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
                if not self.require_admin():
                    return
                result = add_user(payload, username)
            elif parsed.path == "/api/admin-users-delete":
                if not self.require_admin():
                    return
                result = delete_user(payload, username)
            elif parsed.path == "/api/admin-users-update":
                if not self.require_admin():
                    return
                result = update_user(payload, username)
            elif parsed.path == "/api/diary/save":
                result = save_diary(payload, username)
            elif parsed.path == "/api/diary/delete":
                result = delete_diary(payload.get("date", ""), username)
            elif parsed.path == "/api/diary/summarize":
                result = summarize_diaries_for_weekly(payload, username)
            elif parsed.path == "/api/forum/create":
                result = forum_create_topic(payload, username)
            elif parsed.path == "/api/forum/comment":
                result = forum_add_comment(payload, username)
            elif parsed.path == "/api/forum/like":
                result = forum_toggle_like(payload, username)
            elif parsed.path == "/api/forum/ai-topic":
                result = forum_ai_topic(payload, username)
            elif parsed.path == "/api/forum/ai-comment":
                result = forum_ai_comment(payload, username)
            elif parsed.path == "/api/news/config":
                if not self.require_superadmin():
                    return
                result = save_news_config(payload)
            elif parsed.path == "/api/news/generate":
                if not self.require_superadmin():
                    return
                result = generate_news_issue(payload, username)
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
    print(f"个人工作报告邮件助手已启动：http://{host}:{port}")
    print(f"英文相对访问地址：{APP_RELATIVE_PATH}")
    print(f"完整访问地址：http://{host}:{port}{APP_RELATIVE_PATH}")
    print(f"用户数据目录：{USER_DATA_DIR}")
    print(f"共享模板目录：{REPORT_DIR}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()
