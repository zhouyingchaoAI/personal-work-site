"""Public, email-based password reset helpers.

Tokens are deliberately kept in memory: they are short lived, single use, and
automatically invalidated on a service restart.
"""

PASSWORD_RESET_TOKENS = {}
PASSWORD_RESET_LOCK = threading.Lock()
PASSWORD_RESET_CAPTCHAS = {}
PASSWORD_RESET_TTL_SECONDS = 10 * 60
PASSWORD_RESET_RESEND_SECONDS = 60
PASSWORD_RESET_MAX_ATTEMPTS = 5
PASSWORD_RESET_CAPTCHA_TTL_SECONDS = 3 * 60
DEFAULT_COMPANY_EMAIL_DOMAIN = os.getenv("COMPANY_EMAIL_DOMAIN", "chencytech.com").strip().lower().lstrip("@")


def _normalized_email(value):
    return str(value or "").strip().lower()


def _valid_email(value):
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", _normalized_email(value)))


def default_company_email(username):
    """Company mail is the safe, predictable default until an admin overrides it."""
    local_part = str(username or "").strip().lower()
    if "@" in local_part:
        return local_part if _valid_email(local_part) else ""
    candidate = f"{local_part}@{DEFAULT_COMPANY_EMAIL_DOMAIN}" if local_part and DEFAULT_COMPANY_EMAIL_DOMAIN else ""
    return candidate if _valid_email(candidate) else ""


def _password_reset_user(identifier):
    key = _normalized_email(identifier)
    if not key:
        return None, ""
    for user in read_config().get("users", []):
        username = _normalized_email(user.get("username"))
        bound_email = _normalized_email(user.get("email"))
        configured_email = _normalized_email(user_mail_config(user.get("username")).get("user_email"))
        company_email = configured_email if _valid_email(configured_email) else default_company_email(user.get("username"))
        if key == username or (bound_email and key == bound_email) or key == company_email:
            destination = bound_email if _valid_email(bound_email) else company_email
            return user, destination
    return None, ""


def _password_reset_digest(username, code):
    return hmac.new(_master_secret(), f"password-reset:{username}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def create_password_reset_captcha():
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = "".join(secrets.choice(alphabet) for _ in range(5))
    captcha_id = secrets.token_urlsafe(18)
    with PASSWORD_RESET_LOCK:
        PASSWORD_RESET_CAPTCHAS[captcha_id] = {
            "digest": _password_reset_digest(captcha_id, code),
            "expires_at": time.time() + PASSWORD_RESET_CAPTCHA_TTL_SECONDS,
        }
    # The text is intentionally rendered as SVG rather than returned as data.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="132" height="42" viewBox="0 0 132 42">'
        '<rect width="132" height="42" rx="7" fill="#eef4ff"/>'
        '<path d="M5 31L37 8M50 35L81 5M91 34L124 12" stroke="#9bb5e8" stroke-width="1.5"/>'
        f'<text x="66" y="29" text-anchor="middle" fill="#174ea6" font-family="Arial,sans-serif" font-size="22" font-weight="700" letter-spacing="4">{code}</text>'
        '</svg>'
    )
    return {"ok": True, "captcha_id": captcha_id, "svg": svg}


def _verify_password_reset_captcha(payload):
    captcha_id = str((payload or {}).get("captcha_id", "") or "")
    answer = str((payload or {}).get("captcha", "") or "").strip().upper()
    with PASSWORD_RESET_LOCK:
        captcha = PASSWORD_RESET_CAPTCHAS.pop(captcha_id, None)
    if not captcha or time.time() > captcha.get("expires_at", 0):
        raise ValueError("动态验证码已失效，请刷新后重试")
    if not secrets.compare_digest(captcha["digest"], _password_reset_digest(captcha_id, answer)):
        raise ValueError("动态验证码错误，请刷新后重试")


def password_reset_smtp_settings():
    """Use the first configured company mailbox as the shared reset sender."""
    config = read_config()
    for username in (config.get("user_mail_settings") or {}):
        settings = smtp_settings(username)
        if settings.get("host") and settings.get("user") and settings.get("password"):
            return settings
    return smtp_settings()


def send_password_reset_email(destination, code):
    settings = password_reset_smtp_settings()
    validate_smtp_ready(settings)
    message = EmailMessage()
    message["Subject"] = "承希智能办公助手 · 密码重置验证码"
    message["From"] = settings.get("from_addr") or settings["user"]
    message["To"] = destination
    message.set_content(
        f"您正在重置承希智能办公助手的登录密码。\n\n验证码：{code}\n\n"
        "验证码 10 分钟内有效，请勿向任何人泄露。若非本人操作，请忽略此邮件。"
    )
    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(settings["user"], settings["password"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings["user"], settings["password"])
            smtp.send_message(message)


def request_password_reset(payload):
    """Issue a code without revealing whether an account/email exists."""
    _verify_password_reset_captcha(payload)
    identifier = str((payload or {}).get("identifier", "") or "").strip()[:254]
    generic = {"ok": True, "message": "如账号已绑定邮箱，验证码已发送，请查收。"}
    user, destination = _password_reset_user(identifier)
    if not user or not destination:
        return generic
    username = user.get("username", "")
    now = time.time()
    with PASSWORD_RESET_LOCK:
        current = PASSWORD_RESET_TOKENS.get(username)
        if current and now - current.get("sent_at", 0) < PASSWORD_RESET_RESEND_SECONDS:
            return generic
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        send_password_reset_email(destination, code)
    except Exception as exc:
        # Keep the external response generic; server logs retain actionable detail.
        print(f"[password-reset] failed to send reset email for {username}: {exc}")
        return generic
    with PASSWORD_RESET_LOCK:
        PASSWORD_RESET_TOKENS[username] = {
            "digest": _password_reset_digest(username, code),
            "expires_at": now + PASSWORD_RESET_TTL_SECONDS,
            "sent_at": now,
            "attempts": 0,
        }
    return generic


def confirm_password_reset(payload):
    payload = payload or {}
    identifier = str(payload.get("identifier", "") or "").strip()[:254]
    code = str(payload.get("code", "") or "").strip()
    new_password = str(payload.get("new_password", "") or "")
    if len(new_password) < 8:
        raise ValueError("新密码至少 8 位")
    user, _destination = _password_reset_user(identifier)
    username = (user or {}).get("username", "")
    now = time.time()
    with PASSWORD_RESET_LOCK:
        token = PASSWORD_RESET_TOKENS.get(username)
        valid = bool(token and now <= token.get("expires_at", 0) and token.get("attempts", 0) < PASSWORD_RESET_MAX_ATTEMPTS)
        valid = valid and secrets.compare_digest(token["digest"], _password_reset_digest(username, code))
        if not valid:
            if token:
                token["attempts"] = token.get("attempts", 0) + 1
                if token["attempts"] >= PASSWORD_RESET_MAX_ATTEMPTS or now > token.get("expires_at", 0):
                    PASSWORD_RESET_TOKENS.pop(username, None)
            raise ValueError("验证码无效或已过期")
        PASSWORD_RESET_TOKENS.pop(username, None)
    config = read_config()
    for account in config.get("users", []):
        if account.get("username") == username:
            account["password"] = hash_password(new_password)
            break
    write_config(config)
    for session_token, session_username in list(SESSIONS.items()):
        if session_username == username:
            del SESSIONS[session_token]
    return {"ok": True, "message": "密码已重置，请使用新密码登录。"}
