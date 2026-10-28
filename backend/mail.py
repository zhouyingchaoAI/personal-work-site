"""SMTP/IMAP settings, mailbox reading, and message building.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

from html import unescape as html_unescape

def smtp_settings(username=None):
    config = read_config()
    if username:
        mail = user_mail_config(username)
        return {
            "host": mail.get("smtp_host", ""),
            "port": int(mail.get("smtp_port") or 587),
            "user": mail.get("smtp_user", ""),
            "password": mail.get("smtp_password", ""),
            "from_addr": mail.get("smtp_from", "") or mail.get("user_email", ""),
            "use_ssl": bool(mail.get("smtp_ssl", False)),
            "use_tls": bool(mail.get("smtp_tls", True)),
        }
    return {
        "host": os.getenv("SMTP_HOST", config.get("smtp_host", "")),
        "port": int(os.getenv("SMTP_PORT", config.get("smtp_port", "587") or 587)),
        "user": os.getenv("SMTP_USER", config.get("smtp_user", "")),
        "password": os.getenv("SMTP_PASSWORD", config.get("smtp_password", "")),
        "from_addr": os.getenv("SMTP_FROM", config.get("smtp_from", "")),
        "use_ssl": str(os.getenv("SMTP_SSL", config.get("smtp_ssl", "false"))).lower() == "true",
        "use_tls": str(os.getenv("SMTP_TLS", config.get("smtp_tls", "true"))).lower() != "false",
    }


def smtp_settings_personal(username):
    mail = user_mail_config(username)
    return {
        "host": mail.get("personal_smtp_host", ""),
        "port": int(mail.get("personal_smtp_port") or 587),
        "user": mail.get("personal_smtp_user", ""),
        "password": mail.get("personal_smtp_password", ""),
        "from_addr": mail.get("personal_email", ""),
        "use_ssl": bool(mail.get("personal_smtp_ssl", False)),
        "use_tls": bool(mail.get("personal_smtp_tls", True)),
    }


def smtp_settings_for_account(username, account="company"):
    if account == "personal":
        return smtp_settings_personal(username)
    return smtp_settings(username)


def imap_settings(username=None):
    mail = user_mail_config(username)
    return {
        "host": mail.get("imap_host", ""),
        "port": int(mail.get("imap_port") or 993),
        "user": mail.get("imap_user", "") or mail.get("smtp_user", ""),
        "password": mail.get("imap_password", "") or mail.get("smtp_password", ""),
        "use_ssl": bool(mail.get("imap_ssl", True)),
    }


def imap_settings_personal(username):
    mail = user_mail_config(username)
    return {
        "host": mail.get("personal_imap_host", ""),
        "port": int(mail.get("personal_imap_port") or 993),
        "user": mail.get("personal_imap_user", "") or mail.get("personal_smtp_user", ""),
        "password": mail.get("personal_imap_password", ""),
        "use_ssl": bool(mail.get("personal_imap_ssl", True)),
    }


def imap_settings_for_account(username, account="company"):
    if account == "personal":
        return imap_settings_personal(username)
    return imap_settings(username)


def validate_smtp_ready(settings):
    missing = []
    if not settings.get("host"):
        missing.append("SMTP 服务器")
    if not settings.get("user"):
        missing.append("SMTP 用户名")
    if not settings.get("password"):
        missing.append("SMTP 授权码/密码")
    if missing:
        raise ValueError("当前账号邮件未配置完整，缺少：" + "、".join(missing) + "。请到左侧“邮件配置”补充后再发送。")


def validate_imap_ready(settings):
    missing = []
    if not settings.get("host"):
        missing.append("IMAP 服务器")
    if not settings.get("user"):
        missing.append("IMAP 用户名")
    if not settings.get("password"):
        missing.append("IMAP 授权码/密码")
    if missing:
        raise ValueError("当前账号收件箱未配置完整，缺少：" + "、".join(missing) + "。请到左侧“邮件配置”补充后再查看邮件。")


def _test_smtp_login(settings):
    validate_smtp_ready(settings)
    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(settings["user"], settings["password"])
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings["user"], settings["password"])


def _open_imap_box(settings, timeout=20):
    import socket
    original_getaddrinfo = socket.getaddrinfo

    def _ipv4_first_getaddrinfo(*args, **kwargs):
        infos = original_getaddrinfo(*args, **kwargs)
        return sorted(infos, key=lambda item: 0 if item[0] == socket.AF_INET else 1)

    socket.getaddrinfo = _ipv4_first_getaddrinfo
    try:
        if settings["use_ssl"]:
            return imaplib.IMAP4_SSL(settings["host"], settings["port"], timeout=timeout)
        return imaplib.IMAP4(settings["host"], settings["port"], timeout=timeout)
    finally:
        socket.getaddrinfo = original_getaddrinfo


def _test_imap_login(settings):
    validate_imap_ready(settings)
    box = _open_imap_box(settings, timeout=20)
    try:
        box.login(settings["user"], settings["password"])
    finally:
        try:
            box.logout()
        except Exception:
            pass


def test_user_mail_config(username, account="company"):
    smtp_settings_value = smtp_settings_for_account(username, account)
    _test_smtp_login(smtp_settings_value)
    imap_settings_value = imap_settings_for_account(username, account)
    _test_imap_login(imap_settings_value)
    label = "个人邮箱" if account == "personal" else "公司邮箱"
    return {"ok": True, "message": f"{label}配置测试成功，可以正常登录 SMTP 和 IMAP。"}


def imap_connect(username):
    settings = imap_settings(username)
    validate_imap_ready(settings)
    box = _open_imap_box(settings, timeout=20)
    box.login(settings["user"], settings["password"])
    return box


def imap_connect_for_account(username, account="company"):
    settings = imap_settings_for_account(username, account)
    validate_imap_ready(settings)
    box = _open_imap_box(settings, timeout=20)
    box.login(settings["user"], settings["password"])
    return box


def user_mail_cache_dir(username):
    path = user_root(username) / "mail_cache"
    if not officedb_enabled("mailassistant"):
        path.mkdir(parents=True, exist_ok=True)
    return path


def _mail_is_cache_name(name):
    """sent.json 是本地发送历史（业务数据）；其余都是可重建的 IMAP 缓存。"""
    return str(name or "") != "sent"


def mail_cache_path(username, name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "cache"))
    return user_mail_cache_dir(username) / f"{safe}.json"


def safe_mail_uid(uid):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(uid or "")) or "message"


def safe_mail_part_key(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")) or "part"


def mail_part_dir(username, uid):
    path = user_mail_cache_dir(username) / "parts" / safe_mail_uid(uid)
    if not officedb_enabled("mailassistant"):
        path.mkdir(parents=True, exist_ok=True)
    return path


def clear_mail_part_dir(username, uid):
    directory = mail_part_dir(username, uid)
    for name, _, _ in office_blob_list("mailassistant", directory, cache=True):
        try:
            office_blob_delete("mailassistant", directory / name, cache=True)
        except Exception:
            pass


def mail_part_path(username, uid, part_key):
    key = safe_mail_part_key(part_key)
    directory = mail_part_dir(username, uid)
    matches = sorted(name for name, _, _ in office_blob_list("mailassistant", directory, prefix=key + "__", cache=True)
                     if "/" not in name)
    return directory / matches[0] if matches else None


def mailbox_part_url(uid, part_key, download=False):
    query = APP_RELATIVE_PATH + "/api/mailbox-part?uid=" + urllib.parse.quote(str(uid or "")) + "&part=" + urllib.parse.quote(str(part_key or ""))
    if download:
        query += "&download=1"
    return query


def mcp_mail_attachment_link_dir():
    return USER_DATA_DIR / "_mcp_mail_attachment_links"


def mcp_mail_attachment_token_path(token):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(token or ""))
    return mcp_mail_attachment_link_dir() / (safe + ".json")


def create_mcp_mail_attachment_link(username, uid, part_key, expires_seconds=3600):
    token = secrets.token_urlsafe(24)
    payload = {
        "username": str(username or ""),
        "uid": str(uid or ""),
        "part": str(part_key or ""),
        "expires_at": time.time() + max(60, int(expires_seconds or 3600)),
    }
    office_doc_write("mailassistant", mcp_mail_attachment_token_path(token), payload)
    return APP_RELATIVE_PATH + "/mcp-mail-attachment?token=" + urllib.parse.quote(token)


def absolute_personal_work_url(path):
    value = str(path or "")
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return PERSONAL_WORK_SITE_PUBLIC_URL + value


def resolve_mcp_mail_attachment_link(token):
    token = str(token or "").strip()
    if not token:
        raise ValueError("缺少下载 token")
    path = mcp_mail_attachment_token_path(token)
    data = office_doc_read("mailassistant", path, None)
    if not isinstance(data, dict):
        raise ValueError("下载链接不存在或已过期")
    if time.time() > float(data.get("expires_at", 0) or 0):
        try:
            office_doc_delete("mailassistant", path)
        except Exception:
            pass
        raise ValueError("下载链接已过期，请重新调用 mailbox.attachment")
    username = str(data.get("username", "") or "")
    uid = str(data.get("uid", "") or "")
    part_key = str(data.get("part", "") or "")
    attachment_path = get_mail_part(username, uid, part_key)
    return {"path": attachment_path, "username": username, "uid": uid, "part": part_key}


def mail_part_content_type_from_name(name, raw=None):
    ctype, _ = mimetypes.guess_type(str(name or ""))
    if ctype:
        return ctype
    lower = str(name or "").lower()
    for marker, value in (
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".gif", "image/gif"),
        (".webp", "image/webp"),
        (".pdf", "application/pdf"),
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ):
        if marker in lower:
            return value
    head = bytes(raw or b"")[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    return "application/octet-stream"


def normalize_content_id(value):
    return str(value or "").strip().strip("<>")


def replace_cid_sources(html, cid_urls):
    if not html or not cid_urls:
        return html
    pattern = r"src\s*=\s*(['\"]?)cid:([^'\"\s>]+)\1"
    def repl(match):
        quote = match.group(1) or ''
        cid = urllib.parse.unquote(match.group(2) or "")
        url = cid_urls.get(normalize_content_id(cid))
        return "src=" + quote + url + quote if url else match.group(0)
    return re.sub(pattern, repl, html, flags=re.I)


def save_mail_part(username, uid, part_key, filename, payload):
    safe_name = Path(decode_mime_value(filename or "attachment")).name or "attachment"
    safe_name = re.sub(r"[\\/]+", "_", safe_name)
    path = mail_part_dir(username, uid) / (safe_mail_part_key(part_key) + "__" + safe_name)
    office_blob_write("mailassistant", path, payload or b"", content_type=mimetypes.guess_type(safe_name)[0], cache=True)
    return path


def get_mail_part(username, uid, part_key):
    path = mail_part_path(username, uid, part_key)
    if path is None:
        get_inbox_message(username, uid, refresh=True)
        path = mail_part_path(username, uid, part_key)
    if path is None:
        raise ValueError("邮件附件不存在或已过期，请刷新邮件后重试")
    return path


def get_mail_part_content(username, uid, part_key):
    """附件逻辑路径与内容：(Path, bytes)。"""
    path = get_mail_part(username, uid, part_key)
    raw = office_blob_read("mailassistant", path, cache=True)
    if raw is None:
        raise ValueError("邮件附件不存在或已过期，请刷新邮件后重试")
    return path, raw


def mail_detail_cache_is_stale(data):
    msg = (data or {}).get("message") or {}
    body_html = str(msg.get("body_html", ""))
    if "cid:" in body_html.lower():
        return True
    for item in msg.get("attachments", []) or []:
        if item.get("name") and not item.get("download_url"):
            return True
    return False


def read_mail_cache(username, name, max_age_seconds=600):
    data = office_doc_read("mailassistant", mail_cache_path(username, name), None, cache=_mail_is_cache_name(name))
    if not isinstance(data, dict):
        return None
    try:
        fetched_at = float(data.get("fetched_at", 0) or 0)
        if max_age_seconds and time.time() - fetched_at > max_age_seconds:
            return None
        return data
    except Exception:
        return None


def write_mail_cache(username, name, data):
    payload = dict(data or {})
    payload["fetched_at"] = time.time()
    office_doc_write("mailassistant", mail_cache_path(username, name), payload, cache=_mail_is_cache_name(name))
    return payload


def sent_mail_store_path(username):
    return mail_cache_path(username, "sent")


def load_sent_mail_store(username):
    data = office_doc_read("mailassistant", sent_mail_store_path(username), None)
    if data is None:
        return []
    try:
        if isinstance(data, dict):
            messages = data.get("messages", [])
            return messages if isinstance(messages, list) else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_sent_mail_store(username, messages):
    path = sent_mail_store_path(username)
    payload = {"messages": list(messages or [])[:200], "updated_at": datetime.now().isoformat(timespec="seconds")}
    office_doc_write("mailassistant", path, payload)


def sent_mail_preview(body, body_html):
    text = str(body or "").strip()
    if not text and body_html:
        text = re.sub(r"<[^>]+>", " ", str(body_html or ""))
    return re.sub(r"\s+", " ", text).strip()[:180]


def sent_mail_body_html(body, body_html):
    if body_html:
        return str(body_html)[:120000]
    text = html_escape(str(body or "")).replace("\n", "<br>")
    return f'<div style="white-space:pre-wrap;">{text}</div>' if text else ""


def sent_mail_attachment_summaries(payload):
    items = []
    if payload.get("attachment"):
        name = Path(str(payload.get("attachment") or "")).name
        if name:
            items.append({"name": name})
    for idx, item in enumerate(payload.get("attachments", []) or []):
        if not isinstance(item, dict):
            continue
        name = Path(str(item.get("name", "") or f"附件{idx + 1}")).name
        size = 0
        content = item.get("content", "") or ""
        if content:
            try:
                size = len(base64.b64decode(content))
            except Exception:
                size = 0
        items.append({"index": idx, "name": name, "size": size, "type": item.get("type", "") or "application/octet-stream"})
    return items


def record_sent_mail(payload, username=None, account="company"):
    if not username:
        return None
    now = datetime.now()
    uid = "sent-" + now.strftime("%Y%m%d%H%M%S") + "-" + secrets.token_urlsafe(5)
    settings = smtp_settings_for_account(username, account)
    body = append_email_signature(payload.get("body", ""), username)
    body_html = email_body_html_with_signature(payload, username)
    message = {
        "uid": uid,
        "mailbox": "sent",
        "subject": str(payload.get("subject", "") or "无主题"),
        "from": settings.get("from_addr") or settings.get("user", ""),
        "to": str(payload.get("to", "") or ""),
        "cc": str(payload.get("cc", "") or ""),
        "date": now.strftime("%Y-%m-%d %H:%M"),
        "created_at": now.isoformat(timespec="seconds"),
        "preview": sent_mail_preview(body, body_html),
        "body": body[:6000],
        "body_html": sent_mail_body_html(body, body_html),
        "has_html": bool(body_html or body),
        "attachments": sent_mail_attachment_summaries(payload),
    }
    messages = [item for item in load_sent_mail_store(username) if item.get("uid") != uid]
    messages.insert(0, message)
    save_sent_mail_store(username, messages)
    return message


def sent_mail_public_summary(message):
    return {
        "uid": message.get("uid", ""),
        "subject": message.get("subject", "无主题"),
        "from": message.get("from", ""),
        "to": message.get("to", ""),
        "cc": message.get("cc", ""),
        "date": message.get("date", ""),
        "preview": message.get("preview", ""),
        "attachments": message.get("attachments", []) or [],
        "mailbox": "sent",
        "source": message.get("source", "local"),
    }


def platform_sent_report_messages(username):
    """Build read-only sent-mail rows from reports promoted after platform send.

    Earlier platform versions promoted successful weekly/trip reports but did not
    create ``sent.json``.  Those promoted files are therefore the durable proof
    of historical sends and must be visible alongside newer local mail records.
    """
    settings = smtp_settings(username)
    messages = []
    for report in report_files(username):
        kind = str(report.get("kind") or "")
        name = str(report.get("name") or "")
        if kind not in ("weekly", "trip") or not name:
            continue
        digest = hashlib.sha1(f"{kind}:{name}".encode("utf-8")).hexdigest()[:16]
        is_weekly = kind == "weekly"
        title = "周报" if is_weekly else "出差报告"
        to_value = settings.get("from_addr") or settings.get("user", "")
        messages.append({
            "uid": "report-sent-" + digest,
            "mailbox": "sent",
            "source": "platform_report",
            "report_name": name,
            "report_kind": kind,
            "subject": f"【{title}】{name}",
            "from": settings.get("from_addr") or settings.get("user", ""),
            "to": to_value,
            "cc": "",
            "date": datetime.fromtimestamp(float(report.get("mtime") or 0)).strftime("%Y-%m-%d %H:%M"),
            "created_at": datetime.fromtimestamp(float(report.get("mtime") or 0)).isoformat(timespec="seconds"),
            "preview": f"平台已发送的{title}附件：{name}",
            "body": f"平台已发送的{title}附件：{name}",
            "body_html": "",
            "has_html": False,
            "attachments": [{"name": name}],
        })
    return messages


def merged_sent_messages(username):
    local = load_sent_mail_store(username)
    local_attachment_names = {
        str(item.get("name") or "")
        for message in local
        for item in (message.get("attachments") or [])
        if isinstance(item, dict)
    }
    historical = [
        message for message in platform_sent_report_messages(username)
        if message.get("report_name") not in local_attachment_names
    ]
    return sorted(local + historical, key=lambda item: str(item.get("created_at") or item.get("date") or ""), reverse=True)


def list_sent_messages(username, limit=20):
    limit = max(1, min(int(limit or 20), 50))
    messages = merged_sent_messages(username)[:limit]
    return {"ok": True, "messages": [sent_mail_public_summary(item) for item in messages], "cached": False}


def get_sent_message(username, uid):
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少已发邮件 UID")
    for message in merged_sent_messages(username):
        if message.get("uid") == uid:
            item = dict(message)
            item["attachments"] = item.get("attachments", []) or []
            # 历史平台发送记录来自归档报告。用现有报告解析器还原当时邮件的
            # 正文/表格预览，而不是只展示“附件已发送”的占位文本。
            if item.get("source") == "platform_report":
                try:
                    draft = compose_draft(item.get("report_kind"), item.get("report_name"), username)
                    if not draft.get("error"):
                        item["body"] = str(draft.get("body") or item.get("body") or "")
                        item["body_html"] = str(draft.get("body_html") or item.get("body_html") or "")
                        item["has_html"] = bool(item["body_html"])
                        item["to"] = str(draft.get("to") or item.get("to") or "")
                        item["cc"] = str(draft.get("cc") or item.get("cc") or "")
                except Exception:
                    # 个别旧文件无法解析时仍保留附件占位详情，不能让整封邮件打不开。
                    pass
            return {"ok": True, "message": item, "cached": False}
    raise ValueError("已发邮件不存在")


def clear_mail_cache(username):
    directory = user_mail_cache_dir(username)
    for name, _, _ in office_doc_list("mailassistant", directory, cache=True):
        # 已发邮件是本地发送成功后的持久历史，不属于可失效的 IMAP 缓存。
        # 保存邮箱配置时会刷新收件箱缓存，但不能抹掉用户的已发记录。
        if name == "sent.json":
            continue
        try:
            office_doc_delete("mailassistant", directory / name, cache=True)
        except Exception:
            pass


def decode_mime_value(value):
    chunks = decode_header(value or "")
    output = []
    for chunk, charset in chunks:
        if isinstance(chunk, bytes):
            output.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            output.append(chunk)
    return "".join(output).strip()


def normalize_mail_date(value):
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value or ""


def html_mail_text(value):
    """Convert an HTML mail body to the concise text used by mailbox previews."""
    css_selector = r"(?:[A-Za-z][\w-]*|[.#][\w-]+)(?:[.#][\w-]+)*(?:\s+(?:[A-Za-z][\w-]*|[.#][\w-]+)(?:[.#][\w-]+)*)*"
    css_rule = rf"(?is){css_selector}(?:\s*,\s*{css_selector})*\s*\{{[^{{}}]{{0,4000}}\}}"
    without_css = re.sub(css_rule, " ", str(value or ""))
    return re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", " ", without_css))).strip()


def extract_mail_text(msg, max_chars=800):
    parts = []
    html_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() not in ("text/plain", "text/html"):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if part.get_content_type() == "text/plain":
                parts.append(content)
            else:
                html_parts.append(content)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            content = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_parts.append(content)
            else:
                parts.append(content)
    if not parts and html_parts:
        # Some webmail clients place editor CSS before the first HTML element
        # instead of wrapping it in a <style> tag.  Stripping tags alone leaves
        # that stylesheet as the first line of the inbox preview.
        parts = [html_mail_text(text) for text in html_parts]
    text = re.sub(r"\s+", " ", "\n".join(parts)).strip()
    return text[:max_chars]


def extract_mail_html(msg, max_chars=120000):
    html_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment" or part.get_content_type() != "text/html":
                continue
            payload = part.get_payload(decode=True)
            if payload:
                html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    elif msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True)
        if payload:
            html_parts.append(payload.decode(msg.get_content_charset() or "utf-8", errors="replace"))
    html = "\n".join(html_parts).strip()
    html = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", "", html)
    html = re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", html)
    html = re.sub(r"(?i)javascript:", "", html)
    return html[:max_chars]


def mail_summary_from_message(uid, msg, username=None):
    attachments = []
    cid_urls = {}
    if username:
        clear_mail_part_dir(username, uid)
    for idx, part in enumerate(msg.walk() if msg.is_multipart() else [msg]):
        if part.is_multipart():
            continue
        name = part.get_filename()
        cid = normalize_content_id(part.get("Content-ID", ""))
        disposition = (part.get_content_disposition() or "").lower()
        if not name and not cid:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = decode_mime_value(name) if name else ((cid or f"part-{idx}") + (mimetypes.guess_extension(part.get_content_type()) or ""))
        part_key = f"part{idx}"
        if username and payload:
            save_mail_part(username, uid, part_key, filename, payload)
        if cid:
            cid_urls[cid] = mailbox_part_url(uid, part_key)
        if name and (disposition == "attachment" or not cid):
            item = {
                "name": decode_mime_value(name),
                "size": len(payload),
                "type": part.get_content_type(),
                "part": part_key,
            }
            if username and payload:
                item["download_url"] = mailbox_part_url(uid, part_key, True)
                item["mcp_tool"] = "mailbox.attachment"
                item["mcp_arguments"] = {"uid": str(uid), "part": part_key}
                item["mcp_hint"] = "龙虾/MCP 下载附件请调用 mailbox.attachment，并传入这里的 uid 与 part。"
            attachments.append(item)
    body_html = replace_cid_sources(extract_mail_html(msg), cid_urls)
    return {
        "uid": str(uid),
        "subject": decode_mime_value(msg.get("Subject", "")) or "无主题",
        "from": decode_mime_value(msg.get("From", "")),
        "to": decode_mime_value(msg.get("To", "")),
        "date": normalize_mail_date(msg.get("Date", "")),
        "preview": extract_mail_text(msg, 180),
        "body": extract_mail_text(msg, 6000),
        "body_html": body_html,
        "has_html": bool(body_html),
        "attachments": attachments,
    }


def mail_header_summary(uid, msg):
    return {
        "uid": str(uid),
        "subject": decode_mime_value(msg.get("Subject", "")) or "无主题",
        "from": decode_mime_value(msg.get("From", "")),
        "to": decode_mime_value(msg.get("To", "")),
        "date": normalize_mail_date(msg.get("Date", "")),
        "preview": "点击邮件查看正文",
        "attachments": [],
    }


_IMAP_SEARCH_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# 友好名 -> 可能的中英文文件夹名（小写匹配）。不同邮箱服务器命名各异，按解码后的中文/英文名匹配。
_FOLDER_ALIASES = {
    'inbox': ['inbox', '收件箱'],
    'archive': ['已归档', '归档', 'archive', 'archives'],
    'sent': ['已发送', '发件箱', 'sent', 'sent messages', 'sent items'],
    'drafts': ['草稿箱', '草稿', 'drafts', 'draft'],
    'trash': ['已删除', '废件箱', 'trash', 'deleted', 'deleted messages'],
    'spam': ['垃圾邮件', 'spam', 'junk'],
}
MAILBOX_RECENT_MONTH_CACHE = "inbox_recent_month_v2"
MAILBOX_RECENT_MONTH_DAYS = 31
MAILBOX_RECENT_MONTH_LIMIT = 200
# 页面最大可见范围为 50 封；这些正文均来自本地缓存，随列表返回可避免点击后再发详情请求。
MAILBOX_INLINE_DETAIL_LIMIT = 50
MAILBOX_PREFETCH_CONCURRENCY = 3
MAILBOX_MCP_CURSOR_MAX_AGE = 7200
_mailbox_prefetch_active_users = set()
_mailbox_prefetch_lock = threading.Lock()
_mailbox_prefetch_slots = threading.BoundedSemaphore(MAILBOX_PREFETCH_CONCURRENCY)


def _mailbox_recent_month_since():
    return datetime.fromtimestamp(time.time() - MAILBOX_RECENT_MONTH_DAYS * 86400).strftime("%Y-%m-%d")


def prefetch_user_inbox_recent_month(username, force=False):
    """后台同步个人收件箱近一个月摘要及详情，供页面直接读取本地缓存。"""
    username = str(username or "").strip()
    if not username:
        return {"ok": False, "skipped": True}
    settings = imap_settings(username)
    if not settings.get("host") or not settings.get("user") or not settings.get("password"):
        return {"ok": False, "skipped": True}
    snapshot = read_mail_cache(username, MAILBOX_RECENT_MONTH_CACHE, 1800) if not force else None
    if not snapshot:
        since = _mailbox_recent_month_since()
        result = list_inbox_messages(username, MAILBOX_RECENT_MONTH_LIMIT, refresh=True, since=since, folder="inbox")
        snapshot = {
            "ok": True,
            "messages": result.get("messages") or [],
            "period_start": since,
            "background_sync": True,
            "total": result.get("total", len(result.get("messages") or [])),
            "counts": result.get("counts") or {
                "all": result.get("total", len(result.get("messages") or [])),
                "unread": sum(1 for item in (result.get("messages") or []) if item.get("is_read") is False),
                "read": sum(1 for item in (result.get("messages") or []) if item.get("is_read") is True),
            },
        }
        write_mail_cache(username, MAILBOX_RECENT_MONTH_CACHE, snapshot)
    snapshot["detail_count"] = prefetch_inbox_message_details(username, snapshot["messages"])
    return snapshot


def schedule_user_inbox_prefetch(username, force=False):
    """为单个用户安排独立的邮件预取，不让其他账号阻塞其正文缓存。"""
    username = str(username or "").strip()
    if not username:
        return False
    with _mailbox_prefetch_lock:
        if username in _mailbox_prefetch_active_users:
            return False
        _mailbox_prefetch_active_users.add(username)

    def _run():
        try:
            with _mailbox_prefetch_slots:
                prefetch_user_inbox_recent_month(username, force=force)
        except Exception:
            # 单个邮箱不可用不应影响 HTTP 服务或其他账号的预取。
            pass
        finally:
            with _mailbox_prefetch_lock:
                _mailbox_prefetch_active_users.discard(username)

    threading.Thread(target=_run, daemon=True, name=f"mail-prefetch-{username}").start()
    return True


def mail_inbox_auto_worker():
    """启动后及每 30 分钟为所有已配置 IMAP 的账号预取最近一个月邮件。"""
    while True:
        try:
            users = (read_config().get("users") or [])
            for user in users:
                schedule_user_inbox_prefetch(str((user or {}).get("username") or ""), force=True)
        except Exception:
            pass
        time.sleep(1800)


def _imap_utf7_decode(name):
    """解码 IMAP modified UTF-7 文件夹名（如 &XfJfUmhj- -> 已归档）。"""
    import binascii
    res = []
    i = 0
    while i < len(name):
        ch = name[i]
        if ch == '&':
            j = name.find('-', i)
            if j == -1:
                res.append(name[i:])
                break
            chunk = name[i + 1:j]
            if chunk == '':
                res.append('&')
            else:
                try:
                    res.append(binascii.a2b_base64(chunk.replace(',', '/') + '=' * (-len(chunk) % 4)).decode('utf-16-be'))
                except Exception:
                    res.append(name[i:j + 1])
            i = j + 1
        else:
            res.append(ch)
            i += 1
    return ''.join(res)


def _resolve_imap_folder(box, wanted):
    """把用户传入的文件夹名（inbox/已归档/archive/原始 IMAP 名）解析成实际可 select 的 IMAP 名。"""
    w = str(wanted or '').strip()
    if not w or w.lower() in ('inbox', '收件箱'):
        return 'INBOX'
    wl = w.lower()
    wanted_set = {wl}
    for canon, names in _FOLDER_ALIASES.items():
        if wl == canon or wl in [n.lower() for n in names]:
            wanted_set.add(canon)
            wanted_set.update(n.lower() for n in names)
    try:
        typ, data = box.list()
    except Exception:
        return w
    for f in data or []:
        if not f:
            continue
        line = f.decode('utf-8', 'ignore') if isinstance(f, (bytes, bytearray)) else str(f)
        m = re.search(r'\(([^)]*)\)\s+"([^"]*)"\s+(.+)$', line)
        raw = (m.group(3).strip().strip('"') if m else line.strip().split()[-1].strip('"'))
        decoded = _imap_utf7_decode(raw)
        if raw == w or decoded == w or raw.lower() in wanted_set or decoded.lower() in wanted_set:
            return raw
    return w


def mail_fetch_meta_is_read(meta):
    """Return whether an IMAP FETCH response contains the standard \\Seen flag."""
    return bool(re.search(r"FLAGS\s*\([^)]*\\Seen", str(meta or ""), re.IGNORECASE))


def _fetch_folder_summaries(box, raw_folder, since_imap, before_imap, window, folder_label, offset=0, read_status="all"):
    """在已连接的 box 上选中某文件夹并按日期范围抓取邮件头摘要（带 folder 标签便于详情回查）。"""
    box.select(raw_folder, readonly=True)
    criteria = []
    if since_imap:
        criteria += ["SINCE", since_imap]
    if before_imap:
        criteria += ["BEFORE", before_imap]
    if read_status == "unread":
        criteria.append("UNSEEN")
    elif read_status == "read":
        criteria.append("SEEN")
    if not criteria:
        criteria = ["ALL"]
    status, data = box.uid("search", None, *criteria)
    if status != "OK":
        raise ValueError("读取邮件失败")
    all_uids = data[0].split()
    total = len(all_uids)
    uids = all_uids[::-1][offset:offset + window]
    messages = []
    if uids:
        uid_set = b",".join(uids)
        status, fetched = box.uid("fetch", uid_set, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE)])")
        if status != "OK" or not fetched:
            raise ValueError("读取邮件失败")
        for item in fetched:
            if not isinstance(item, tuple) or not item[1]:
                continue
            meta = item[0].decode("utf-8", errors="ignore")
            match = re.search(r"UID\s+(\d+)", meta)
            uid = match.group(1) if match else ""
            if not uid:
                continue
            summary = mail_header_summary(uid, email.message_from_bytes(item[1]))
            # Search criteria is authoritative for a status-filtered query. Some
            # providers return stale FLAGS in the subsequent header FETCH.
            if read_status == "unread":
                summary["is_read"] = False
            elif read_status == "read":
                summary["is_read"] = True
            else:
                summary["is_read"] = mail_fetch_meta_is_read(meta)
            summary["folder"] = folder_label
            messages.append(summary)
        order = {uid.decode("ascii", errors="ignore"): idx for idx, uid in enumerate(uids)}
        messages.sort(key=lambda it: order.get(str(it.get("uid", "")), 999))
    return messages, total


def _inbox_read_counts(box):
    """Return whole-inbox counters for folder labels, independent from the visible page/filter."""
    box.select(_resolve_imap_folder(box, "inbox"), readonly=True)
    status, all_data = box.uid("search", None, "ALL")
    if status != "OK":
        raise ValueError("读取邮件数量失败")
    status, unread_data = box.uid("search", None, "UNSEEN")
    if status != "OK":
        raise ValueError("读取未读邮件数量失败")
    total = len((all_data or [b""])[0].split())
    unread = len((unread_data or [b""])[0].split())
    return {"all": total, "unread": unread, "read": max(0, total - unread)}


def _mailbox_mcp_query(args):
    """Normalize the stable filtering portion of the mailbox MCP query."""
    args = args or {}
    try:
        limit = int(args.get("limit", 20) or 20)
    except (TypeError, ValueError):
        raise ValueError("limit 必须是整数")
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    return {
        "folder": str(args.get("folder", "inbox") or "inbox").strip().lower(),
        "keyword": str(args.get("keyword", "") or "").strip(),
        "since": str(args.get("since", "") or "").strip(),
        "before": str(args.get("before", "") or "").strip(),
        "limit": min(limit, 200),
    }


def _mailbox_mcp_filter(query):
    return {key: query[key] for key in ("folder", "keyword", "since", "before")}


def _mailbox_mcp_cursor(snapshot_id, offset):
    offset = int(offset)
    signature = hmac.new(_master_secret(), f"mailbox-mcp:{snapshot_id}:{offset}".encode("utf-8"), hashlib.sha256).hexdigest()[:20]
    return f"{snapshot_id}.{offset}.{signature}"


def _parse_mailbox_mcp_cursor(cursor):
    try:
        snapshot_id, offset_text, signature = str(cursor or "").rsplit(".", 2)
        offset = int(offset_text)
    except (ValueError, TypeError):
        raise ValueError("cursor 无效")
    expected = _mailbox_mcp_cursor(snapshot_id, offset).rsplit(".", 1)[-1]
    if not snapshot_id or offset < 0 or not hmac.compare_digest(signature, expected):
        raise ValueError("cursor 无效")
    return snapshot_id, offset


def _mailbox_mcp_snapshot_messages(username, query):
    """Read every matching message header once, then page an immutable local snapshot."""
    since_imap = _imap_search_date(query["since"]) if query["since"] else None
    before_imap = _imap_search_date(query["before"]) if query["before"] else None
    keyword = query["keyword"].lower()
    box = imap_connect(username)
    try:
        folder = query["folder"]
        if folder in ("all", "全部", "inbox+archive"):
            targets = [("INBOX", "收件箱"), (_resolve_imap_folder(box, "archive"), "已归档")]
        else:
            raw = _resolve_imap_folder(box, folder)
            targets = [(raw, "收件箱" if raw == "INBOX" else _imap_utf7_decode(raw))]
        messages = []
        for raw_folder, label in targets:
            box.select(raw_folder, readonly=True)
            criteria = []
            if since_imap:
                criteria += ["SINCE", since_imap]
            if before_imap:
                criteria += ["BEFORE", before_imap]
            status, data = box.uid("search", None, *(criteria or ["ALL"]))
            if status != "OK":
                raise ValueError("读取邮件失败")
            all_uids = list(reversed((data[0] or b"").split()))
            for start in range(0, len(all_uids), 100):
                uids = all_uids[start:start + 100]
                if not uids:
                    continue
                status, fetched = box.uid("fetch", b",".join(uids), "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE)])")
                if status != "OK":
                    raise ValueError("读取邮件失败")
                order = {uid.decode("ascii", errors="ignore"): index for index, uid in enumerate(uids)}
                batch = []
                for item in fetched or []:
                    if not isinstance(item, tuple) or not item[1]:
                        continue
                    match = re.search(r"UID\s+(\d+)", item[0].decode("utf-8", errors="ignore"))
                    if not match:
                        continue
                    summary = mail_header_summary(match.group(1), email.message_from_bytes(item[1]))
                    if keyword and keyword not in str(summary.get("subject", "")).lower():
                        continue
                    summary["folder"] = label
                    batch.append(summary)
                batch.sort(key=lambda row: order.get(str(row.get("uid", "")), 999))
                messages.extend(batch)
        messages.sort(key=lambda row: (str(row.get("date", "")), f"{int(str(row.get('uid', '0')) or 0):020d}"), reverse=True)
        return messages
    finally:
        try:
            box.logout()
        except Exception:
            pass


def list_mailbox_mcp(username, args=None):
    """Cursor-paginated, query-consistent mailbox API for MCP callers."""
    args = args or {}
    query = _mailbox_mcp_query(args)
    cursor = str(args.get("cursor", "") or "").strip()
    if cursor:
        snapshot_id, offset = _parse_mailbox_mcp_cursor(cursor)
        snapshot = read_mail_cache(username, f"mcp_mail_snapshot_{snapshot_id}", MAILBOX_MCP_CURSOR_MAX_AGE)
        if not snapshot:
            raise ValueError("cursor 已过期，请从第一页重新查询")
        if _mailbox_mcp_filter(snapshot.get("query") or {}) != _mailbox_mcp_filter(query):
            raise ValueError("cursor 与当前查询条件不一致，请从第一页重新查询")
    else:
        snapshot_id = secrets.token_urlsafe(18)
        offset = 0
        snapshot = {
            "query": query,
            "messages": _mailbox_mcp_snapshot_messages(username, query),
        }
        write_mail_cache(username, f"mcp_mail_snapshot_{snapshot_id}", snapshot)
    messages = snapshot.get("messages") or []
    total = len(messages)
    page = messages[offset:offset + query["limit"]]
    next_offset = offset + len(page)
    has_more = next_offset < total
    return {
        "ok": True,
        "messages": page,
        "total": total,
        "has_more": has_more,
        "next_cursor": _mailbox_mcp_cursor(snapshot_id, next_offset) if has_more else None,
        "limit": query["limit"],
    }


def _imap_search_date(value):
    """把 YYYY-MM-DD（或 / . 分隔）转成 IMAP 需要的 DD-Mon-YYYY。"""
    text = str(value or "").strip()
    if not text:
        return None
    for sep in ("-", "/", "."):
        parts = text.split(sep)
        if len(parts) == 3:
            try:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                return f"{day:02d}-{_IMAP_SEARCH_MONTHS[month - 1]}-{year}"
            except (ValueError, IndexError):
                break
    raise ValueError(f"日期格式应为 YYYY-MM-DD：{text}")


def _recent_month_inbox_result(username, snapshot, limit, offset=0, read_status="all"):
    """Return a fast, locally cached inbox page, optionally filtered by read state."""
    all_messages = snapshot.get("messages") or []
    if read_status == "unread":
        filtered_messages = [item for item in all_messages if item.get("is_read") is False]
    elif read_status == "read":
        filtered_messages = [item for item in all_messages if item.get("is_read") is True]
    else:
        filtered_messages = all_messages
    page = filtered_messages[offset:offset + limit]
    raw_counts = snapshot.get("counts") or {}
    all_count = int(raw_counts.get("all") or snapshot.get("total") or len(all_messages))
    unread_count = int(raw_counts.get("unread") if raw_counts.get("unread") is not None else sum(
        1 for item in all_messages if item.get("is_read") is False
    ))
    read_count = int(raw_counts.get("read") if raw_counts.get("read") is not None else max(0, all_count - unread_count))
    counts = {"all": all_count, "unread": unread_count, "read": read_count}
    return {
        "ok": True,
        "messages": inbox_messages_with_ready_details(username, page),
        "cached": True,
        "background_sync": True,
        "period_start": snapshot.get("period_start") or "",
        "total": len(filtered_messages),
        "has_more": offset + len(page) < len(filtered_messages),
        "counts": counts,
        "unread_count": unread_count,
        "read_count": read_count,
    }


def _mail_rows_match_read_status(messages, read_status):
    if read_status == "unread":
        return all(item.get("is_read") is False for item in (messages or []))
    if read_status == "read":
        return all(item.get("is_read") is True for item in (messages or []))
    return True


def list_inbox_messages(username, limit=20, refresh=False, since=None, before=None, keyword=None, folder=None, offset=0, read_status="all"):
    since_imap = _imap_search_date(since) if since else None
    before_imap = _imap_search_date(before) if before else None
    keyword = str(keyword or "").strip() or None
    folder = str(folder or "inbox").strip() or "inbox"
    read_status = str(read_status or "all").strip().lower()
    if read_status not in ("all", "unread", "read"):
        raise ValueError("read_status 仅支持 all、unread 或 read")
    offset = max(0, int(offset or 0))
    has_filter = bool(since_imap or before_imap or keyword or read_status != "all")
    # 带日期/关键词筛选时放宽到 200 封，便于翻查半年内邮件；无筛选保持最近 50 封。
    cap = 200 if has_filter else 50
    limit = max(1, min(int(limit or 20), cap))
    cache_key = re.sub(r"[^A-Za-z0-9]+", "_", f"v2_{folder}_{read_status}_{limit}_{offset}_{since_imap or ''}_{before_imap or ''}_{keyword or ''}")
    cache_name = f"inbox_{cache_key}"
    if not refresh:
        # 用户进入收件箱时立即独立安排正文预取；列表仍优先直接返回缓存，
        # 不再等待全量账号轮询任务依次完成。
        is_inbox_first_page = not offset and folder.lower() in ("inbox", "收件箱")
        if is_inbox_first_page:
            schedule_user_inbox_prefetch(username)
        month_cache = read_mail_cache(username, MAILBOX_RECENT_MONTH_CACHE, 0) if is_inbox_first_page else None
        cached = read_mail_cache(username, cache_name, 1800)
        if cached and not _mail_rows_match_read_status(cached.get("messages") or [], read_status):
            # A user may have opened a message after this status-specific page was
            # cached. Do not show that now-read row inside the unread directory.
            cached = None
        if cached:
            # IMAP 的 SEEN/UNSEEN 检索偶发返回空页。不能让该临时空结果覆盖已经
            # 完成预取的近一个月快照，否则未读页会在半小时内错误显示为 0 封。
            if read_status != "all" and month_cache:
                fallback = _recent_month_inbox_result(username, month_cache, limit, offset, read_status)
                if not cached.get("messages") and fallback.get("messages"):
                    return fallback
            cached["ok"] = True
            cached["cached"] = True
            cached["messages"] = inbox_messages_with_ready_details(username, cached.get("messages") or [])
            return cached
        # 页面默认只显示 10/20/50 封，但后台已提前同步近一个月（最多 200 封）。
        # 即使这份快照略旧，也优先返回它，避免用户每次进入收件箱都等待 IMAP。
        if not has_filter and month_cache:
            return _recent_month_inbox_result(username, month_cache, limit, offset, read_status)
    # 关键词过滤时每个文件夹先取较大候选集（最新 cap 封）再过滤，避免漏掉 limit 窗口外的命中。
    window = cap if keyword else limit
    box = imap_connect(username)
    try:
        # folder=all/全部：合并 收件箱 + 已归档（半年前的历史邮件多在已归档）。
        if folder.lower() in ("all", "全部", "inbox+archive"):
            targets = [("INBOX", "收件箱"), (_resolve_imap_folder(box, "archive"), "已归档")]
        else:
            raw = _resolve_imap_folder(box, folder)
            label = "收件箱" if raw == "INBOX" else _imap_utf7_decode(raw)
            targets = [(raw, label)]
        messages = []
        total = 0
        for raw_folder, label in targets:
            try:
                folder_messages, folder_total = _fetch_folder_summaries(
                    box, raw_folder, since_imap, before_imap, window, label, offset, read_status=read_status
                )
                messages += folder_messages
                total += folder_total
            except Exception:
                continue
        if len(targets) > 1:
            messages.sort(key=lambda it: str(it.get("date", "")), reverse=True)
        if keyword:
            kw = keyword.lower()
            messages = [
                m for m in messages
                if kw in str(m.get("subject", "")).lower() or kw in str(m.get("from", "")).lower()
            ]
        messages = messages[:limit]
        counts = None
        if folder.lower() in ("inbox", "收件箱"):
            try:
                counts = _inbox_read_counts(box)
            except Exception:
                # 计数读取失败时仍可正常展示邮件列表，并给出当前页可推导的统计。
                unread = sum(1 for item in messages if item.get("is_read") is False)
                counts = {"all": total, "unread": unread, "read": max(0, total - unread)}
        # A valid monthly snapshot is more trustworthy than a transient empty
        # SEEN/UNSEEN query. Serve it instead of persisting a false empty cache.
        if read_status != "all" and not messages and not total:
            month_cache = read_mail_cache(username, MAILBOX_RECENT_MONTH_CACHE, 0)
            if month_cache:
                fallback = _recent_month_inbox_result(username, month_cache, limit, offset, read_status)
                if fallback.get("messages"):
                    return fallback
        result = write_mail_cache(username, cache_name, {
            "ok": True,
            "messages": messages,
            "cached": False,
            "total": total,
            "has_more": offset + len(messages) < total,
            "counts": counts or {"all": total, "unread": 0, "read": total},
            "unread_count": int((counts or {}).get("unread") or 0),
            "read_count": int((counts or {}).get("read") or 0),
        })
        result["ok"] = True
        result["messages"] = inbox_messages_with_ready_details(username, result.get("messages") or [])
        return result
    finally:
        try:
            box.logout()
        except Exception:
            pass


def _inbox_detail_cache_name(folder, uid):
    return f"detail_{re.sub(r'[^A-Za-z0-9]+', '_', str(folder or 'inbox'))}_{uid}"


def inbox_messages_with_ready_details(username, messages, limit=MAILBOX_INLINE_DETAIL_LIMIT):
    """将列表顶部已缓存的正文直接附在响应中，首批点击无需第二次 HTTP 请求。"""
    hydrated = []
    for index, item in enumerate(messages or []):
        row = dict(item or {})
        if index < limit:
            uid = str(row.get("uid") or "").strip()
            cached = read_mail_cache(username, _inbox_detail_cache_name("inbox", uid), 0) if uid else None
            if cached and not mail_detail_cache_is_stale(cached):
                row.update((cached.get("message") or {}))
                if row.get("body_html"):
                    row["preview"] = html_mail_text(row["body_html"])[:180] or row.get("preview", "")
        hydrated.append(row)
    return hydrated


def prefetch_inbox_message_details(username, messages):
    """复用一个 IMAP 连接预加载收件箱详情，避免用户逐封打开时再等待网络。"""
    missing_uids = []
    for item in messages or []:
        uid = str((item or {}).get("uid") or "").strip()
        if not uid:
            continue
        cached = read_mail_cache(username, _inbox_detail_cache_name("inbox", uid), 0)
        if not cached or mail_detail_cache_is_stale(cached):
            missing_uids.append(uid)
    if not missing_uids:
        return 0
    box = imap_connect(username)
    loaded = 0
    try:
        box.select(_resolve_imap_folder(box, "inbox"), readonly=True)
        for uid in missing_uids:
            try:
                status, fetched = box.uid("fetch", uid, "(BODY.PEEK[])")
                raw = next((item[1] for item in fetched or [] if isinstance(item, tuple)), None) if status == "OK" else None
                if not raw:
                    continue
                write_mail_cache(username, _inbox_detail_cache_name("inbox", uid), {
                    "ok": True,
                    "message": mail_summary_from_message(uid, email.message_from_bytes(raw), username),
                    "cached": False,
                    "background_sync": True,
                })
                loaded += 1
            except Exception:
                # 单封异常不影响其余近一个月邮件的预取。
                continue
    finally:
        try:
            box.logout()
        except Exception:
            pass
    return loaded


def get_inbox_message(username, uid, refresh=False, folder=None):
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少邮件 UID")
    # IMAP UID 是按文件夹独立的；列表来自哪个文件夹，详情就得选中同一个文件夹。
    folder = str(folder or "inbox").strip() or "inbox"
    cache_name = _inbox_detail_cache_name(folder, uid)
    if not refresh:
        cached = read_mail_cache(username, cache_name, 7200)
        if cached and not mail_detail_cache_is_stale(cached):
            cached["ok"] = True
            cached["cached"] = True
            return cached
    box = imap_connect(username)
    try:
        box.select(_resolve_imap_folder(box, folder), readonly=True)
        status, fetched = box.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK" or not fetched:
            raise ValueError("邮件不存在或读取失败")
        raw = next((item[1] for item in fetched if isinstance(item, tuple)), None)
        if not raw:
            raise ValueError("邮件内容为空")
        result = write_mail_cache(username, cache_name, {"ok": True, "message": mail_summary_from_message(uid, email.message_from_bytes(raw), username), "cached": False})
        result["ok"] = True
        return result
    finally:
        try:
            box.logout()
        except Exception:
            pass


def _update_cached_mail_read_state(username, uid):
    """Update every local mailbox snapshot containing uid after IMAP marks it read."""
    uid = str(uid or "").strip()
    if not uid:
        return
    directory = user_mail_cache_dir(username)
    for name, cached, _ in office_doc_list("mailassistant", directory, cache=True):
        try:
            if not isinstance(cached, dict):
                continue
            changed = False
            was_unread = False
            for item in cached.get("messages") or []:
                if str(item.get("uid") or "") != uid:
                    continue
                was_unread = item.get("is_read") is False
                item["is_read"] = True
                changed = True
            message = cached.get("message")
            if isinstance(message, dict) and str(message.get("uid") or "") == uid:
                message["is_read"] = True
                changed = True
            if not changed:
                continue
            if was_unread and isinstance(cached.get("unread_count"), int):
                cached["unread_count"] = max(0, cached["unread_count"] - 1)
                if isinstance(cached.get("total"), int):
                    cached["read_count"] = max(0, cached["total"] - cached["unread_count"])
            if was_unread and isinstance(cached.get("counts"), dict):
                counts = cached["counts"]
                unread = max(0, int(counts.get("unread") or 0) - 1)
                all_count = int(counts.get("all") or cached.get("total") or 0)
                counts["unread"] = unread
                counts["read"] = max(0, all_count - unread)
            cached["fetched_at"] = time.time()
            office_doc_write("mailassistant", directory / name, cached, cache=True)
        except Exception:
            # 缓存文件损坏或单文件更新失败时，不影响 IMAP 已读状态。
            continue


def mark_inbox_message_read(username, uid):
    """Persist an explicit user read action to IMAP and immediately update local caches."""
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少邮件 UID")
    box = imap_connect(username)
    try:
        box.select(_resolve_imap_folder(box, "inbox"), readonly=False)
        status, _ = box.uid("store", uid, "+FLAGS.SILENT", "(\\Seen)")
        if status != "OK":
            raise ValueError("邮件已读状态更新失败")
    finally:
        try:
            box.logout()
        except Exception:
            pass
    _update_cached_mail_read_state(username, uid)
    return {"ok": True, "uid": uid, "is_read": True}


def split_addresses(value):
    return [item.strip() for item in re.split(r"[;,]", value or "") if item.strip()]


def email_signature_for_user(username=None):
    mail_cfg = user_mail_config(username)
    return mail_cfg.get("email_signature") or default_email_signature_for_user(username) or ""


def normalize_email_signature_html(signature):
    """Replace authenticated 263 image links with the bundled company logo."""
    text = str(signature or "")
    logo_path = BASE_DIR / 'backend' / 'assets' / 'company-logo.png'
    logo = ''
    if logo_path.is_file():
        logo = '<img alt="CHENCY" width="180" style="display:block;width:180px;height:auto;border:0;" src="data:image/png;base64,' + base64.b64encode(logo_path.read_bytes()).decode('ascii') + '">'
    banner = (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="width:654px;max-width:100%;border-collapse:collapse;background:#1753a6;margin:8px 0;">'
        '<tr><td style="padding:9px 22px;border:0;color:#ffffff;font-family:Arial,sans-serif;font-size:19px;font-weight:700;white-space:nowrap;">◈ CHENCY</td>'
        '<td style="padding:9px 22px;border:0;color:#dceaff;font-family:Arial,Microsoft YaHei,sans-serif;font-size:14px;font-weight:600;text-align:right;white-space:nowrap;">承客户之心 · 拓希望之路</td>'
        '</tr></table>'
    )
    if logo:
        banner = banner.replace('◈ CHENCY', logo).replace('background:#1753a6', 'background:#ffffff').replace('color:#dceaff', 'color:#1753a6')
    original_path = BASE_DIR / 'backend' / 'assets' / 'company-signature-original.png'
    if original_path.is_file():
        banner = '<img alt="CHENCY · 承客户之心 · 拓希望之路" width="654" style="display:block;width:654px;max-width:100%;height:auto;border:0;margin:8px 0;" src="data:image/png;base64,' + base64.b64encode(original_path.read_bytes()).decode('ascii') + '">'
    return re.sub(
        r'<img\b[^>]*\bsrc=["\'][^"\']*mail\.263\.net/[^"\']*mailInnerFileDownloadImg[^"\']*["\'][^>]*>',
        banner,
        text,
        flags=re.I,
    )


def append_email_signature(body, username=None):
    text = str(body or "")
    signature = email_signature_for_user(username)
    if not signature:
        return text
    # Rich signatures are persisted as HTML.  Plain-text MIME parts receive a
    # readable text equivalent while HTML MIME parts keep the original format.
    signature_text = re.sub(r"<br\s*/?>", "\n", signature, flags=re.I)
    signature_text = re.sub(r"</p\s*>", "\n", signature_text, flags=re.I)
    signature_text = re.sub(r"<[^>]+>", "", signature_text).strip()
    if text.rstrip().endswith(signature_text):
        return text
    return text.rstrip() + "\n\n" + signature_text


def append_email_signature_html(body_html, username=None):
    html = str(body_html or "")
    signature = normalize_email_signature_html(email_signature_for_user(username))
    if not signature:
        return html
    sig_html = signature.strip() if re.search(r"<[^>]+>", signature) else html_escape(signature.strip()).replace("\n", "<br>")
    marker = '<div class="email-signature">'
    if marker in html:
        return html
    return html.rstrip() + f'<div class="email-signature">{sig_html}</div>'


def email_body_html_with_signature(payload, username=None):
    """Return an HTML mail part whenever a rich signature is configured.

    Reports already provide HTML bodies.  This also makes the configured
    formatting effective for normal plain-text emails sent through the mailbox
    or an MCP tool, instead of silently downgrading the signature to text.
    """
    body_html = str(payload.get("body_html", "") or "")
    if body_html:
        return append_email_signature_html(body_html, username)
    signature = email_signature_for_user(username)
    if not signature or not re.search(r"<[^>]+>", signature):
        return ""
    body = html_escape(str(payload.get("body", "") or "")).replace("\n", "<br>")
    return append_email_signature_html(f'<div style="white-space:pre-wrap;">{body}</div>', username)


def build_message(payload, username=None, account="company"):
    settings = smtp_settings_for_account(username, account)
    mail_cfg = user_mail_config(username)
    if account == "personal":
        user_email = mail_cfg.get("personal_email", "")
    else:
        user_email = mail_cfg.get("user_email", "")
    from_addr = payload.get("from") or user_email or settings["from_addr"] or settings["user"]
    if not from_addr:
        from_addr = "no-reply@local"

    body = append_email_signature(payload.get("body", "") or "", username)
    body_html = email_body_html_with_signature(payload, username)
    inline_images = []
    def embed_image(match):
        subtype, encoded = match.group(2).lower(), match.group(3)
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return match.group(0)
        if not raw or len(raw) > 10 * 1024 * 1024:
            return match.group(0)
        cid = 'signature-' + secrets.token_hex(12) + '@office.local'
        inline_images.append((cid, subtype, raw))
        return 'src=' + match.group(1) + 'cid:' + cid + match.group(1)
    body_html = re.sub(r'''src\s*=\s*(["'])data:image/(png|jpeg|gif|webp);base64,([^"']+)\1''', embed_image, body_html, flags=re.I)

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(split_addresses(payload.get("to", "")))
    if split_addresses(payload.get("cc", "")):
        msg["Cc"] = ", ".join(split_addresses(payload.get("cc", "")))
    msg["Subject"] = payload.get("subject", "")

    if body_html:
        # multipart/alternative: text/plain + text/html
        msg.set_content(body, subtype="plain", charset="utf-8")
        msg.add_alternative(body_html, subtype="html")
        for cid, subtype, raw in inline_images:
            msg.get_payload()[-1].add_related(raw, maintype='image', subtype=subtype, cid=f'<{cid}>', disposition='inline')
    else:
        msg.set_content(body, subtype="plain", charset="utf-8")

    attachment_name = payload.get("attachment", "")
    path = attachment_path_by_name(attachment_name, username) if attachment_name else None
    raw = office_blob_read("reports", path) if attachment_name and path else None
    if raw is not None:
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=path.name)
    for item in payload.get("attachments", []) or []:
        filename = Path(str(item.get("name", "attachment"))).name or "attachment"
        raw = base64.b64decode(item.get("content", "") or "")
        ctype = item.get("type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1) if "/" in ctype else ("application", "octet-stream")
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def attachment_path_by_name(file_name, username=None):
    safe_name = Path(file_name or "").name
    kind = report_kind_from_name(safe_name) if "report_kind_from_name" in globals() else "other"
    if username:
        bases = (
            user_generated_kind_dir(username, kind),
            user_report_kind_dir(username, kind),
            user_generated_dir(username),
            user_report_dir(username),
        )
    else:
        bases = (
            GENERATED_DIR / safe_report_kind(kind),
            REPORT_DIR / safe_report_kind(kind),
            GENERATED_DIR,
            REPORT_DIR,
        )
    for base in bases:
        path = base / safe_name
        if safe_name and office_blob_exists("reports", path):
            return path
    return None


def history_path_by_name(file_name, username=None):
    safe_name = Path(file_name or "").name
    kind = report_kind_from_name(safe_name) if "report_kind_from_name" in globals() else "other"
    bases = (user_report_kind_dir(username, kind), user_report_dir(username)) if username else (REPORT_DIR / safe_report_kind(kind), REPORT_DIR)
    for base in bases:
        path = base / safe_name
        if safe_name and office_blob_exists("reports", path):
            return path
    return None
