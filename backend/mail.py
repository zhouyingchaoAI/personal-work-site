"""SMTP/IMAP settings, mailbox reading, and message building.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

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


def test_user_mail_config(username, account="company"):
    settings = smtp_settings_for_account(username, account)
    validate_smtp_ready(settings)
    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(settings["user"], settings["password"])
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings["user"], settings["password"])
    label = "个人邮箱" if account == "personal" else "公司邮箱"
    return {"ok": True, "message": f"{label}配置测试成功，可以正常登录 SMTP。"}


def imap_connect(username):
    settings = imap_settings(username)
    validate_imap_ready(settings)
    if settings["use_ssl"]:
        box = imaplib.IMAP4_SSL(settings["host"], settings["port"], timeout=20)
    else:
        box = imaplib.IMAP4(settings["host"], settings["port"], timeout=20)
    box.login(settings["user"], settings["password"])
    return box


def imap_connect_for_account(username, account="company"):
    settings = imap_settings_for_account(username, account)
    validate_imap_ready(settings)
    if settings["use_ssl"]:
        box = imaplib.IMAP4_SSL(settings["host"], settings["port"], timeout=20)
    else:
        box = imaplib.IMAP4(settings["host"], settings["port"], timeout=20)
    box.login(settings["user"], settings["password"])
    return box


def user_mail_cache_dir(username):
    path = user_root(username) / "mail_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def mail_cache_path(username, name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "cache"))
    return user_mail_cache_dir(username) / f"{safe}.json"


def safe_mail_uid(uid):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(uid or "")) or "message"


def safe_mail_part_key(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")) or "part"


def mail_part_dir(username, uid):
    path = user_mail_cache_dir(username) / "parts" / safe_mail_uid(uid)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_mail_part_dir(username, uid):
    path = mail_part_dir(username, uid)
    for item in path.glob("*"):
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            pass


def mail_part_path(username, uid, part_key):
    key = safe_mail_part_key(part_key)
    matches = sorted(mail_part_dir(username, uid).glob(key + "__*"))
    return matches[0] if matches else None


def mailbox_part_url(uid, part_key, download=False):
    query = APP_RELATIVE_PATH + "/api/mailbox-part?uid=" + urllib.parse.quote(str(uid or "")) + "&part=" + urllib.parse.quote(str(part_key or ""))
    if download:
        query += "&download=1"
    return query


def mcp_mail_attachment_link_dir():
    path = USER_DATA_DIR / "_mcp_mail_attachment_links"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    mcp_mail_attachment_token_path(token).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
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
    if not path.exists() or not path.is_file():
        raise ValueError("下载链接不存在或已过期")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("下载链接无效")
    if time.time() > float(data.get("expires_at", 0) or 0):
        try:
            path.unlink()
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
    path.write_bytes(payload or b"")
    return path


def get_mail_part(username, uid, part_key):
    path = mail_part_path(username, uid, part_key)
    if path is None or not path.exists():
        get_inbox_message(username, uid, refresh=True)
        path = mail_part_path(username, uid, part_key)
    if path is None or not path.exists() or not path.is_file():
        raise ValueError("邮件附件不存在或已过期，请刷新邮件后重试")
    return path


def mail_detail_cache_is_stale(data):
    msg = (data or {}).get("message") or {}
    body_html = str(msg.get("body_html", ""))
    if "cid:" in body_html.lower():
        return True
    if 'src="/api/mailbox-part' in body_html or "src='/api/mailbox-part" in body_html:
        return True
    for item in msg.get("attachments", []) or []:
        if item.get("name") and not item.get("download_url"):
            return True
    return False


def read_mail_cache(username, name, max_age_seconds=600):
    path = mail_cache_path(username, name)
    if not path.exists():
        return None
    try:
        data = read_json_lenient(path)
        fetched_at = float(data.get("fetched_at", 0) or 0)
        if max_age_seconds and time.time() - fetched_at > max_age_seconds:
            return None
        return data
    except Exception:
        return None


def write_mail_cache(username, name, data):
    payload = dict(data or {})
    payload["fetched_at"] = time.time()
    mail_cache_path(username, name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def sent_mail_store_path(username):
    return mail_cache_path(username, "sent")


def load_sent_mail_store(username):
    path = sent_mail_store_path(username)
    if not path.exists():
        return []
    try:
        data = read_json_lenient(path)
        if isinstance(data, dict):
            messages = data.get("messages", [])
            return messages if isinstance(messages, list) else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_sent_mail_store(username, messages):
    path = sent_mail_store_path(username)
    payload = {"messages": list(messages or [])[:200], "updated_at": datetime.now().isoformat(timespec="seconds")}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
    body_html = payload.get("body_html", "") or ""
    if body_html:
        body_html = append_email_signature_html(body_html, username)
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
    }


def list_sent_messages(username, limit=20):
    limit = max(1, min(int(limit or 20), 50))
    messages = load_sent_mail_store(username)[:limit]
    return {"ok": True, "messages": [sent_mail_public_summary(item) for item in messages], "cached": False}


def get_sent_message(username, uid):
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少已发邮件 UID")
    for message in load_sent_mail_store(username):
        if message.get("uid") == uid:
            item = dict(message)
            item["attachments"] = item.get("attachments", []) or []
            return {"ok": True, "message": item, "cached": False}
    raise ValueError("已发邮件不存在")


def clear_mail_cache(username):
    path = user_mail_cache_dir(username)
    for item in path.glob("*.json"):
        try:
            item.unlink()
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
        parts = [re.sub(r"<[^>]+>", " ", text) for text in html_parts]
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


def _fetch_folder_summaries(box, raw_folder, since_imap, before_imap, window, folder_label):
    """在已连接的 box 上选中某文件夹并按日期范围抓取邮件头摘要（带 folder 标签便于详情回查）。"""
    box.select(raw_folder, readonly=True)
    criteria = []
    if since_imap:
        criteria += ["SINCE", since_imap]
    if before_imap:
        criteria += ["BEFORE", before_imap]
    if not criteria:
        criteria = ["ALL"]
    status, data = box.uid("search", None, *criteria)
    if status != "OK":
        raise ValueError("读取邮件失败")
    all_uids = data[0].split()
    uids = all_uids[-window:][::-1]
    messages = []
    if uids:
        uid_set = b",".join(uids)
        status, fetched = box.uid("fetch", uid_set, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE)])")
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
            summary["folder"] = folder_label
            messages.append(summary)
        order = {uid.decode("ascii", errors="ignore"): idx for idx, uid in enumerate(uids)}
        messages.sort(key=lambda it: order.get(str(it.get("uid", "")), 999))
    return messages


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


def list_inbox_messages(username, limit=20, refresh=False, since=None, before=None, keyword=None, folder=None):
    since_imap = _imap_search_date(since) if since else None
    before_imap = _imap_search_date(before) if before else None
    keyword = str(keyword or "").strip() or None
    folder = str(folder or "inbox").strip() or "inbox"
    has_filter = bool(since_imap or before_imap or keyword)
    # 带日期/关键词筛选时放宽到 200 封，便于翻查半年内邮件；无筛选保持最近 50 封。
    cap = 200 if has_filter else 50
    limit = max(1, min(int(limit or 20), cap))
    cache_key = re.sub(r"[^A-Za-z0-9]+", "_", f"{folder}_{limit}_{since_imap or ''}_{before_imap or ''}_{keyword or ''}")
    cache_name = f"inbox_{cache_key}"
    if not refresh:
        cached = read_mail_cache(username, cache_name, 1800)
        if cached:
            cached["ok"] = True
            cached["cached"] = True
            return cached
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
        for raw_folder, label in targets:
            try:
                messages += _fetch_folder_summaries(box, raw_folder, since_imap, before_imap, window, label)
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
        result = write_mail_cache(username, cache_name, {"ok": True, "messages": messages, "cached": False})
        result["ok"] = True
        return result
    finally:
        try:
            box.logout()
        except Exception:
            pass


def get_inbox_message(username, uid, refresh=False, folder=None):
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少邮件 UID")
    # IMAP UID 是按文件夹独立的；列表来自哪个文件夹，详情就得选中同一个文件夹。
    folder = str(folder or "inbox").strip() or "inbox"
    cache_name = f"detail_{re.sub(r'[^A-Za-z0-9]+', '_', folder)}_{uid}"
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


def split_addresses(value):
    return [item.strip() for item in re.split(r"[;,]", value or "") if item.strip()]


def email_signature_for_user(username=None):
    mail_cfg = user_mail_config(username)
    return mail_cfg.get("email_signature") or default_email_signature_for_user(username) or ""


def append_email_signature(body, username=None):
    text = str(body or "")
    signature = email_signature_for_user(username)
    if not signature:
        return text
    if text.rstrip().endswith(signature.strip()):
        return text
    return text.rstrip() + "\n\n" + signature.strip()


def append_email_signature_html(body_html, username=None):
    html = str(body_html or "")
    signature = email_signature_for_user(username)
    if not signature:
        return html
    sig_html = html_escape(signature.strip()).replace("\n", "<br>")
    if html.rstrip().endswith(f"<p>{sig_html}</p>"):
        return html
    return html.rstrip() + f'<p>{sig_html}</p>'


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
    body_html = payload.get("body_html", "") or ""
    if body_html:
        body_html = append_email_signature_html(body_html, username)

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
    else:
        msg.set_content(body, subtype="plain", charset="utf-8")

    attachment_name = payload.get("attachment", "")
    path = attachment_path_by_name(attachment_name, username) if attachment_name else None
    if attachment_name and path and path.exists():
        ctype, encoding = mimetypes.guess_type(str(path))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
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
        if path.exists() and path.is_file():
            return path
    return None


def history_path_by_name(file_name, username=None):
    safe_name = Path(file_name or "").name
    kind = report_kind_from_name(safe_name) if "report_kind_from_name" in globals() else "other"
    bases = (user_report_kind_dir(username, kind), user_report_dir(username)) if username else (REPORT_DIR / safe_report_kind(kind), REPORT_DIR)
    for base in bases:
        path = base / safe_name
        if path.exists() and path.is_file():
            return path
    return None
