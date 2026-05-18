#!/usr/bin/env python3
import json
import base64
import email
import imaplib
import io
import mimetypes
import os
import re
import smtplib
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
import shutil
import secrets
from copy import deepcopy
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = BASE_DIR.parent
REPORT_DIR = WORKSPACE / "周报"
DRAFT_DIR = BASE_DIR / "drafts"
GENERATED_DIR = BASE_DIR / "generated"
FRONTEND_DIR = BASE_DIR / "frontend"
USER_DATA_DIR = BASE_DIR / "user_data"
CONFIG_PATH = BASE_DIR / "config.json"
AGENT_CONFIG_PATH = BASE_DIR / "agent_config.json"
APP_RELATIVE_PATH = "/personal-office-assistant"
SESSIONS = {}
DEFAULT_ASSISTANT_PROMPT = (
    "请帮我优化下面的工作内容，要求：\n"
    "1、拆分成1、2、3、4这样的编号要点，每点单独换行。\n"
    "2、语言简洁明了，体现实际工作量和推进成果。\n"
    "3、修正错别字、病句和不通顺表达。\n"
    "4、不要编造不存在的事项，不要写空话套话。"
)

DEFAULT_EMAIL_SIGNATURE = """\n
周颖超

--------------------------------------------------------------------------------------
湖南承希科技有限公司  | Hunan Chency Technology Co.,Ltd.
--------------------------------------------------------------------------------------
Mobile: 185-2961-2716
E-mail: zhouyingchao@chencytech.com
Add: 湖南省长沙市岳麓区军民融合产业园1栋B座15A层
------------------------------------------------------------------------

本邮件及其附件含有保密信息，仅限于发送给上面地址中列出的个人或群组。禁止任何其他人以任何形式使用（包括但不限全部或部分地泄露、复制、或散发）本邮件中的信息。如果您错收了本邮件，请您立即电话或邮件通知发件人并删除本邮件！
This e-mail and its attachments contain confidential information and are intended only for the individual or group of individuals listed at the address above. Any other pere this email!"""


def safe_username(username):
    return re.sub(r"[^A-Za-z0-9_@.-]+", "_", str(username or "default")).strip("._") or "default"


def user_root(username):
    return USER_DATA_DIR / safe_username(username)


def user_report_dir(username):
    return user_root(username) / "reports"


def user_generated_dir(username):
    return user_root(username) / "generated"


def user_draft_dir(username):
    return user_root(username) / "drafts"


def user_profile_dir(username):
    return user_root(username) / "profile"


def user_diary_dir(username):
    return user_root(username) / "diary"


def user_forum_dir(username):
    return user_root(username) / "forum"


def read_config():
    config = {
        "leader_email": "",
        "cc": "",
        "sender_name": "周颖超",
        "weekly_greeting": "领导您好：",
        "trip_greeting": "领导您好：",
        "signature": "周颖超",
        "email_signature": DEFAULT_EMAIL_SIGNATURE,
        "assistant_prompt": DEFAULT_ASSISTANT_PROMPT,
        "assistant_api_url": "",
        "assistant_api_key": "",
        "assistant_model": "MiniMax-M2.7",
        "smtp_host": "smtp.263.net",
        "imap_host": "imap.263.net",
        "news_sources": [],
        "news_search_query": "轨道交通 OR 城市轨道 OR 地铁 OR 智慧轨交 OR 轨道交通安全",
        "news_auto_search": True,
        "news_auto_push": True,
        "news_push_time": "08:30",
        "users": [
            {"username": "admin", "password": "admin123", "role": "admin", "name": "管理员"},
            {"username": "member", "password": "member123", "role": "member", "name": "成员"},
        ],
        "user_mail_settings": {},
    }
    if CONFIG_PATH.exists():
        try:
            config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    return config


def write_config(config):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def read_agent_config():
    if not AGENT_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_agent_config(cfg):
    AGENT_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def public_user(user):
    role = user.get("role", "member")
    username = user.get("username", "")
    avatar_url = user.get("avatar_url", "")
    if not avatar_url and username and (user_profile_dir(username) / "avatar.png").exists():
        avatar_url = f"/user-avatar/{urllib.parse.quote(username)}.png?v={int((user_profile_dir(username) / 'avatar.png').stat().st_mtime)}"
    return {
        "username": username,
        "role": role,
        "name": user.get("name") or username,
        "avatar_url": avatar_url,
        "bio": user.get("bio", ""),
        "hobbies": user.get("hobbies", ""),
        "is_admin": role in ("admin", "superadmin"),
        "is_superadmin": role == "superadmin",
    }


def ensure_user_space(username):
    for path in (user_report_dir(username), user_generated_dir(username), user_draft_dir(username), user_profile_dir(username)):
        path.mkdir(parents=True, exist_ok=True)


def find_user(username, password=None):
    for user in read_config().get("users", []):
        if user.get("username") != username:
            continue
        if password is None or str(user.get("password", "")) == str(password):
            return user
    return None


def default_email_signature_for_user(username):
    user = find_user(username)
    name = user.get("name") or username if user else username
    mail_cfg = read_config().get("user_mail_settings", {}).get(username or "", {})
    email = mail_cfg.get("user_email") or mail_cfg.get("smtp_user") or ""
    parts = [f"\n{name}"]
    if email:
        parts.append(f"E-mail: {email}")
    parts.append("")
    return "\n".join(parts)


def _reference_mail_config():
    """以 zhouyingchao 的邮件配置作为参考示例（去掉密码）"""
    config = read_config()
    ref = config.get("user_mail_settings", {}).get("zhouyingchao", {})
    return {
        "user_email": ref.get("user_email", "yourname@company.com"),
        "weekly_to": ref.get("weekly_to", ""),
        "weekly_cc": ref.get("weekly_cc", ""),
        "trip_to": ref.get("trip_to", ""),
        "trip_cc": ref.get("trip_cc", ""),
        "smtp_user": ref.get("smtp_user", "yourname@company.com"),
        "smtp_from": ref.get("smtp_from", "yourname@company.com"),
    }


def user_mail_config(username):
    """返回指定用户的邮件配置，含本人邮箱、周报/出差报告各自的收件人和抄送"""
    config = read_config()
    settings = config.get("user_mail_settings", {}).get(username or "", {})
    reference = _reference_mail_config()
    return {
        "user_email": settings.get("user_email", ""),
        "weekly_to": settings.get("weekly_to", ""),
        "weekly_cc": settings.get("weekly_cc", ""),
        "trip_to": settings.get("trip_to", ""),
        "trip_cc": settings.get("trip_cc", ""),
        "smtp_host": config.get("smtp_host", "smtp.263.net"),
        "smtp_port": int(config.get("smtp_port", 465) or 465),
        "smtp_user": settings.get("smtp_user", ""),
        "smtp_password": settings.get("smtp_password", ""),
        "smtp_from": settings.get("smtp_from", "") or settings.get("user_email", ""),
        "smtp_tls": bool(config.get("smtp_tls", False)),
        "smtp_ssl": bool(config.get("smtp_ssl", True)),
        "imap_host": config.get("imap_host", "imap.263.net"),
        "imap_port": int(config.get("imap_port", 993) or 993),
        "imap_user": settings.get("imap_user", "") or settings.get("smtp_user", ""),
        "imap_password": settings.get("imap_password", "") or settings.get("smtp_password", ""),
        "imap_ssl": bool(config.get("imap_ssl", True)),
        "email_signature": settings.get("email_signature", default_email_signature_for_user(username)),
        "reference": reference,
    }


def save_user_mail_config(username, payload):
    if not username:
        raise ValueError("请先登录")
    config = read_config()
    settings = config.setdefault("user_mail_settings", {}).setdefault(username, {})
    fields = ["user_email", "weekly_to", "weekly_cc", "trip_to", "trip_cc", "smtp_user", "smtp_from", "imap_user"]
    for field in fields:
        if field in payload:
            settings[field] = str(payload.get(field, "") or "").strip()
    if payload.get("smtp_password"):
        settings["smtp_password"] = str(payload.get("smtp_password") or "").strip()
    if payload.get("imap_password"):
        settings["imap_password"] = str(payload.get("imap_password") or "").strip()
    if payload.get("email_signature") is not None:
        settings["email_signature"] = str(payload.get("email_signature") or "").strip()
    if settings.get("user_email"):
        settings["smtp_from"] = settings.get("smtp_from") or settings["user_email"]
        settings["smtp_user"] = settings.get("smtp_user") or settings["user_email"]
    if settings.get("smtp_user"):
        settings["imap_user"] = settings.get("imap_user") or settings["smtp_user"]
    write_config(config)
    clear_mail_cache(username)
    result = user_mail_config(username)
    result["smtp_password_masked"] = "已配置" if result.get("smtp_password") else "未配置"
    result["imap_password_masked"] = "已配置" if result.get("imap_password") else "未配置"
    result.pop("smtp_password", None)
    result.pop("imap_password", None)
    return {"ok": True, "mail_config": result}


def admin_config_payload():
    config = read_config()
    return {
        "assistant_api_url": config.get("assistant_api_url", ""),
        "assistant_model": config.get("assistant_model", "MiniMax-M2.7"),
        "assistant_prompt": config.get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT),
        "assistant_api_key_masked": "已配置" if config.get("assistant_api_key") else "未配置",
        "smtp_host": config.get("smtp_host", "smtp.263.net"),
        "smtp_port": int(config.get("smtp_port", 465) or 465),
        "smtp_tls": bool(config.get("smtp_tls", False)),
        "smtp_ssl": bool(config.get("smtp_ssl", True)),
        "imap_host": config.get("imap_host", "imap.263.net"),
        "imap_port": int(config.get("imap_port", 993) or 993),
        "imap_ssl": bool(config.get("imap_ssl", True)),
        "users": [public_user(user) for user in config.get("users", [])],
    }


def save_admin_config(payload):
    config = read_config()
    config["assistant_api_url"] = str(payload.get("assistant_api_url", "") or "").strip()
    config["assistant_model"] = str(payload.get("assistant_model", "") or "MiniMax-M2.7").strip()
    config["assistant_prompt"] = str(payload.get("assistant_prompt", "") or DEFAULT_ASSISTANT_PROMPT).strip()
    api_key = str(payload.get("assistant_api_key", "") or "").strip()
    if api_key:
        config["assistant_api_key"] = api_key
    write_config(config)
    return {"ok": True, "config": admin_config_payload()}


def save_server_config(payload):
    config = read_config()
    if payload.get("smtp_host") is not None:
        config["smtp_host"] = str(payload.get("smtp_host", "") or "smtp.263.net").strip()
    if payload.get("smtp_port") is not None:
        config["smtp_port"] = int(payload.get("smtp_port", 465) or 465)
    if payload.get("smtp_tls") is not None:
        config["smtp_tls"] = bool(payload.get("smtp_tls", False))
    if payload.get("smtp_ssl") is not None:
        config["smtp_ssl"] = bool(payload.get("smtp_ssl", True))
    if payload.get("imap_host") is not None:
        config["imap_host"] = str(payload.get("imap_host", "") or "imap.263.net").strip()
    if payload.get("imap_port") is not None:
        config["imap_port"] = int(payload.get("imap_port", 993) or 993)
    if payload.get("imap_ssl") is not None:
        config["imap_ssl"] = bool(payload.get("imap_ssl", True))
    write_config(config)
    return {"ok": True, "config": admin_config_payload()}


def _caller_role(caller_username):
    caller = find_user(caller_username)
    return caller.get("role", "member") if caller else "member"


def user_list(caller_username):
    config = read_config()
    caller_role = _caller_role(caller_username)
    users = config.get("users", [])
    if caller_role in ("superadmin", "admin"):
        return [public_user(u) for u in users]
    return []


def add_user(payload, caller_username):
    caller_role = _caller_role(caller_username)
    new_username = str(payload.get("username", "") or "").strip()
    password = str(payload.get("password", "") or "").strip()
    name = str(payload.get("name", "") or "").strip() or new_username
    role = str(payload.get("role", "") or "member").strip()
    if caller_role == "admin" and role != "member":
        raise ValueError("管理员只能添加普通成员")
    if not re.match(r"^[A-Za-z0-9_@.-]{2,40}$", new_username):
        raise ValueError("用户名只能包含字母、数字、下划线、点、@ 或横线，长度 2-40 位")
    if len(password) < 4:
        raise ValueError("密码至少 4 位")
    config = read_config()
    users = config.setdefault("users", [])
    if any(u.get("username") == new_username for u in users):
        raise ValueError("该用户名已存在")
    users.append({"username": new_username, "password": password, "role": role, "name": name})
    write_config(config)
    ensure_user_space(new_username)
    return {"ok": True, "users": user_list(caller_username)}


def delete_user(payload, caller_username):
    caller_role = _caller_role(caller_username)
    target_username = str(payload.get("username", "") or "").strip()
    config = read_config()
    users = config.get("users", [])
    target = next((u for u in users if u.get("username") == target_username), None)
    if not target:
        raise ValueError("用户不存在")
    target_role = target.get("role", "member")
    if caller_role == "admin" and target_role != "member":
        raise ValueError("管理员只能删除普通成员")
    if caller_role == "superadmin" and target_role == "superadmin":
        raise ValueError("不能删除超级管理员")
    config["users"] = [u for u in users if u.get("username") != target_username]
    write_config(config)
    return {"ok": True, "users": user_list(caller_username)}


def change_password(payload, username):
    old_password = str(payload.get("old_password", "") or "").strip()
    new_password = str(payload.get("new_password", "") or "").strip()
    if len(new_password) < 4:
        raise ValueError("新密码至少 4 位")
    user = find_user(username, old_password)
    if not user:
        raise ValueError("原密码错误")
    config = read_config()
    for u in config.get("users", []):
        if u.get("username") == username:
            u["password"] = new_password
            break
    write_config(config)
    return {"ok": True}


def update_user(payload, caller_username):
    caller_role = _caller_role(caller_username)
    target_username = str(payload.get("username", "") or "").strip()
    config = read_config()
    users = config.get("users", [])
    target = next((u for u in users if u.get("username") == target_username), None)
    if not target:
        raise ValueError("用户不存在")
    target_role = target.get("role", "member")
    new_role = payload.get("role")
    new_name = str(payload.get("name", "") or "").strip()
    new_password = str(payload.get("password", "") or "").strip()
    if caller_role == "admin":
        if target_role != "member":
            raise ValueError("管理员只能修改普通成员")
        if new_role is not None and new_role != target_role:
            raise ValueError("管理员不能修改用户权限")
    if caller_role == "superadmin" and target_role == "superadmin" and new_role is not None and new_role != "superadmin":
        # 防止超级管理员降级自己后系统没有超级管理员？暂不限制
        pass
    if new_name:
        target["name"] = new_name
    if new_password:
        target["password"] = new_password
    if new_role is not None and caller_role == "superadmin":
        target["role"] = new_role
    write_config(config)
    return {"ok": True, "users": user_list(caller_username)}


def save_user_profile(payload, username):
    if not username:
        raise ValueError("请先登录")
    config = read_config()
    target = None
    for user in config.get("users", []):
        if user.get("username") == username:
            target = user
            break
    if not target:
        raise ValueError("用户不存在")
    name = str(payload.get("name", "") or "").strip()
    bio = str(payload.get("bio", "") or "").strip()
    hobbies = str(payload.get("hobbies", "") or "").strip()
    if name:
        target["name"] = name[:40]
    target["bio"] = bio[:500]
    target["hobbies"] = hobbies[:300]
    avatar_preset = str(payload.get("avatar_preset", "") or "").strip()
    avatar_data = str(payload.get("avatar_data", "") or "").strip()
    profile_dir = user_profile_dir(username)
    profile_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = profile_dir / "avatar.png"
    if avatar_preset == "assistant":
        src = BASE_DIR / "assets" / "ai-assistant-avatar.png"
        if src.exists():
            avatar_path.write_bytes(src.read_bytes())
    elif avatar_data:
        if "," in avatar_data:
            avatar_data = avatar_data.split(",", 1)[1]
        raw = base64.b64decode(avatar_data)
        if len(raw) > 3 * 1024 * 1024:
            raise ValueError("头像文件不能超过 3MB")
        avatar_path.write_bytes(raw)
    if avatar_path.exists():
        target["avatar_url"] = f"/user-avatar/{urllib.parse.quote(username)}.png?v={int(avatar_path.stat().st_mtime)}"
    write_config(config)
    return {"ok": True, "user": public_user(target)}


def merged_assistant_config(payload=None):
    config = read_config()
    payload = payload or {}
    api_key = str(payload.get("assistant_api_key", "") or "").strip() or config.get("assistant_api_key", "")
    return {
        "url": str(payload.get("assistant_api_url", "") or config.get("assistant_api_url", "")).strip().rstrip("/"),
        "key": api_key,
        "model": str(payload.get("assistant_model", "") or config.get("assistant_model", "MiniMax-M2.7")).strip(),
    }


def request_json(url, api_key, body=None, method="GET", timeout=20):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_admin_models(payload):
    settings = merged_assistant_config(payload)
    if not settings["url"] or not settings["key"]:
        raise ValueError("请先填写 NewAPI 地址和 API Key")
    try:
        data = request_json(settings["url"] + "/v1/models", settings["key"], method="GET", timeout=15)
        models = []
        for item in data.get("data", []):
            model_id = item.get("id") if isinstance(item, dict) else str(item)
            if model_id:
                models.append(model_id)
        models = sorted(set(models))
        if models:
            return {"ok": True, "mode": "api", "models": models}
    except Exception as exc:
        fallback = ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M1", "minimax-m2.7", "minimax-m2.5"]
        return {"ok": True, "mode": "fallback", "warning": f"模型列表获取失败，已使用常用 MiniMax 选项：{exc}", "models": fallback}
    return {"ok": True, "mode": "fallback", "models": ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M1"]}


def test_admin_model(payload):
    settings = merged_assistant_config(payload)
    if not settings["url"] or not settings["key"] or not settings["model"]:
        raise ValueError("请填写 NewAPI 地址、API Key 和模型名称")
    data = request_json(
        settings["url"] + "/v1/chat/completions",
        settings["key"],
        body={
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": "你只需要回复 OK。"},
                {"role": "user", "content": "请回复 OK，用于测试 API Key 和模型是否可用。"},
            ],
            "temperature": 0,
            "max_tokens": 16,
        },
        method="POST",
        timeout=30,
    )
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return {"ok": True, "model": settings["model"], "message": content or "测试请求已成功返回"}


def parse_weekly_date(name):
    match = re.search(r"(?:([0-9]{2})年)?([0-9]{1,2})月([0-9]{1,2})日-([0-9]{1,2})月([0-9]{1,2})日", name)
    if not match:
        return (0, 0, 0, 0)
    year = 2000 + int(match.group(1) or "25")
    month1 = int(match.group(2))
    day1 = int(match.group(3))
    month2 = int(match.group(4))
    day2 = int(match.group(5))
    return (year, month2, day2, month1 * 100 + day1)


def parse_trip_date(name):
    match = re.search(r"出差报告-([0-9]{8})-([0-9]{4})", name)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def report_files(username=None):
    files = []
    base = user_report_dir(username) if username else REPORT_DIR
    if not base.exists():
        return files
    for path in base.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        lower = path.suffix.lower()
        if "工作周报" in path.name and lower in {".xlsx", ".xls"}:
            files.append(
                {
                    "kind": "weekly",
                    "name": path.name,
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                    "sort_key": parse_weekly_date(path.name),
                    "deletable": bool(username),
                }
            )
        elif path.name.startswith("出差报告") and lower in {".docx", ".md"}:
            files.append(
                {
                    "kind": "trip",
                    "name": path.name,
                    "path": str(path),
                    "mtime": path.stat().st_mtime,
                    "sort_key": parse_trip_date(path.name),
                    "deletable": bool(username),
                }
            )
    return files


def generated_files(username=None):
    files = []
    base = user_generated_dir(username) if username else GENERATED_DIR
    if not base.exists():
        return files
    for path in base.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        lower = path.suffix.lower()
        if "工作周报" in path.name and lower in {".xlsx", ".xls"}:
            kind = "weekly"
        elif "出差报告" in path.name and lower in {".docx", ".md"}:
            kind = "trip"
        else:
            continue
        files.append(
            {
                "kind": kind,
                "name": path.name,
                "path": str(path),
                "mtime": path.stat().st_mtime,
                "sort_key": (9999, int(path.stat().st_mtime)),
                "generated": True,
                "deletable": bool(username),
            }
        )
    return files


def all_files(username=None):
    user_files = generated_files(username) + report_files(username)
    if username and not any(not f.get("generated") for f in user_files):
        user_files = user_files + report_files(None)
    return user_files


def newest(kind, username=None, fallback_shared=False):
    items = [item for item in report_files(username) if item["kind"] == kind]
    if not items and fallback_shared and username:
        items = [item for item in report_files(None) if item["kind"] == kind]
    if not items:
        return None
    return sorted(items, key=lambda item: (item["sort_key"], item["mtime"]), reverse=True)[0]


def newest_any(kind, username=None, fallback_shared=False):
    items = [item for item in all_files(username) if item["kind"] == kind]
    if not items and fallback_shared and username:
        items = [item for item in all_files(None) if item["kind"] == kind]
    if not items and kind == "weekly":
        for fallback_user in ("zhouyingchao", "admin"):
            items = [item for item in all_files(fallback_user) if item["kind"] == kind]
            if items:
                break
    if not items:
        return None
    return sorted(items, key=lambda item: (item["sort_key"], item["mtime"]), reverse=True)[0]


def xml_text(node):
    if node is None:
        return ""
    return "".join(node.itertext())


def preview_docx(path, max_chars=900):
    try:
        with zipfile.ZipFile(path) as docx:
            xml = docx.read("word/document.xml")
        root = ET.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = [xml_text(p).strip() for p in root.findall(".//w:p", ns)]
        text = "\n".join(p for p in paragraphs if p)
        return text[:max_chars]
    except Exception:
        return ""


def preview_xlsx(path, max_chars=900):
    try:
        with zipfile.ZipFile(path) as book:
            shared = []
            if "xl/sharedStrings.xml" in book.namelist():
                root = ET.fromstring(book.read("xl/sharedStrings.xml"))
                ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                shared = [xml_text(si).strip() for si in root.findall(".//a:si", ns)]
            sheet_names = [n for n in book.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            texts = []
            for sheet in sheet_names[:2]:
                root = ET.fromstring(book.read(sheet))
                for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    value = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    if value is None or value.text is None:
                        continue
                    if cell.attrib.get("t") == "s":
                        idx = int(value.text)
                        if idx < len(shared):
                            texts.append(shared[idx])
                    else:
                        texts.append(value.text)
            return "\n".join(t for t in texts if t)[:max_chars]
    except Exception:
        return ""


def table_style_html():
    return (
        "width:100%;border-collapse:collapse;margin:8px 0 14px 0;"
        "table-layout:fixed;"
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif;"
        "font-size:13px;background:#fff;"
    )


def xlsx_original_table_html(path):
    try:
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter

        wb = load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        min_row, max_row = 1, ws.max_row
        min_col, max_col = 1, ws.max_column

        while max_row > 1 and not any(ws.cell(max_row, col).value not in (None, "") for col in range(min_col, max_col + 1)):
            max_row -= 1
        while max_col > 1 and not any(ws.cell(row, max_col).value not in (None, "") for row in range(min_row, max_row + 1)):
            max_col -= 1

        merged_starts = {}
        merged_covered = set()
        for area in ws.merged_cells.ranges:
            if area.max_row < min_row or area.min_row > max_row or area.max_col < min_col or area.min_col > max_col:
                continue
            row_span = area.max_row - area.min_row + 1
            col_span = area.max_col - area.min_col + 1
            merged_starts[(area.min_row, area.min_col)] = (row_span, col_span)
            for r in range(area.min_row, area.max_row + 1):
                for c in range(area.min_col, area.max_col + 1):
                    if (r, c) != (area.min_row, area.min_col):
                        merged_covered.add((r, c))

        parts = [f'<table class="raw-table" style="{table_style_html()}">']
        colgroup = ["<colgroup>"]
        for col in range(min_col, max_col + 1):
            letter = get_column_letter(col)
            width = ws.column_dimensions[letter].width or 12
            colgroup.append(f'<col style="width:{min(max(width * 8, 72), 220)}px">')
        colgroup.append("</colgroup>")
        parts.extend(colgroup)

        for row in range(min_row, max_row + 1):
            parts.append("<tr>")
            for col in range(min_col, max_col + 1):
                if (row, col) in merged_covered:
                    continue
                cell = ws.cell(row, col)
                value = "" if cell.value is None else str(cell.value)
                row_span, col_span = merged_starts.get((row, col), (1, 1))
                attrs = []
                if row_span > 1:
                    attrs.append(f'rowspan="{row_span}"')
                if col_span > 1:
                    attrs.append(f'colspan="{col_span}"')
                align = cell.alignment.horizontal or "left"
                valign = cell.alignment.vertical or "middle"
                weight = "font-weight:700;" if cell.font and cell.font.bold else ""
                fill = ""
                fg = getattr(cell.fill, "fgColor", None)
                if fg and fg.type == "rgb" and fg.rgb and fg.rgb not in {"00000000", "FFFFFFFF"}:
                    fill = f"background:#{fg.rgb[-6:]};"
                style = (
                    "border:1px solid #cfd6df;padding:7px 9px;white-space:pre-wrap;word-break:break-word;"
                    f"text-align:{align};vertical-align:{valign};{weight}{fill}"
                )
                parts.append(f'<td {" ".join(attrs)} style="{style}">{html_escape(value)}</td>')
            parts.append("</tr>")
        parts.append("</table>")
        return "".join(parts)
    except Exception:
        return ""


def docx_original_table_html(path):
    try:
        ns = {"w": W_NS}
        parts = []
        with zipfile.ZipFile(path) as docx:
            root = ET.fromstring(docx.read("word/document.xml"))
        for table in root.findall(".//w:tbl", ns):
            parts.append(f'<table class="raw-table" style="{table_style_html()}">')
            grid_cols = []
            for grid_col in table.findall("w:tblGrid/w:gridCol", ns):
                try:
                    grid_cols.append(int(grid_col.attrib.get(w_tag("w"), "0") or 0))
                except ValueError:
                    grid_cols.append(0)
            if grid_cols and sum(grid_cols) > 0:
                total = sum(grid_cols)
                parts.append("<colgroup>")
                for width in grid_cols:
                    parts.append(f'<col style="width:{width / total * 100:.3f}%">')
                parts.append("</colgroup>")
            for row in table.findall("w:tr", ns):
                parts.append("<tr>")
                for cell in row.findall("w:tc", ns):
                    grid_span = cell.find("w:tcPr/w:gridSpan", ns)
                    colspan = grid_span.attrib.get(w_tag("val"), "1") if grid_span is not None else "1"
                    paragraphs = []
                    for paragraph in cell.findall("w:p", ns):
                        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
                        if text:
                            paragraphs.append(text)
                    text = html_escape("\n".join(paragraphs)).replace("\n", "<br>")
                    span_attr = f' colspan="{html_escape(colspan)}"' if colspan and colspan != "1" else ""
                    cell_style = (
                        "border:1px solid #cfd6df;padding:7px 9px;vertical-align:top;"
                        "white-space:pre-wrap;word-break:break-word;"
                    )
                    parts.append(
                        f'<td{span_attr} style="{cell_style}">'
                        f"{text}</td>"
                    )
                parts.append("</tr>")
            parts.append("</table>")
        if parts:
            return "".join(parts)
        paragraphs = []
        for paragraph in root.findall(".//w:p", ns):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
            if text:
                paragraphs.append(html_escape(text))
        return "".join(f"<p>{text}</p>" for text in paragraphs)
    except Exception:
        return ""


def preview_file_html(path):
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return xlsx_original_table_html(path)
    if suffix == ".docx":
        return docx_original_table_html(path)
    if suffix == ".md":
        text = path.read_text(encoding="utf-8", errors="ignore")
        return f'<div style="white-space:pre-wrap;">{html_escape(text)}</div>'
    return ""


def preview_file(path):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return preview_docx(path)
    if suffix == ".xlsx":
        return preview_xlsx(path)
    if suffix == ".md":
        return path.read_text(encoding="utf-8", errors="ignore")[:900]
    return ""


def html_escape(text):
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_weekly_body(path):
    """从 xlsx 周报提取结构化摘要，返回 (纯文本, HTML)"""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]

        def get(r, c):
            v = ws.cell(r, c).value
            return str(v).strip() if v else ""

        def find_row(label, fallback):
            for r in range(1, ws.max_row + 1):
                if label in get(r, 2):
                    return r
            return fallback

        def valid_data_row(cat, content):
            if not cat and not content:
                return False
            invalid = {"工作分类", "工作内容", "一、本周工作总结", "二、重点工作跟进", "三、下周工作计划"}
            return cat not in invalid and content not in invalid

        summary_title_row = find_row("一、本周工作总结", 3)
        follow_title_row = find_row("二、重点工作跟进", 9)
        next_title_row = find_row("三、下周工作计划", 16)
        summary_range = range(summary_title_row + 2, follow_title_row)
        follow_range = range(follow_title_row + 2, next_title_row)
        next_range = range(next_title_row + 2, ws.max_row + 1)

        # ===== 纯文本版本 =====
        lines = []
        title = get(2, 2)
        if title:
            lines.append(title)
            lines.append("")

        # 一、本周工作总结: B=工作分类 C=工作内容 E=完成情况 F=后续计划
        lines.append("一、本周工作总结")
        for row in summary_range:
            cat = get(row, 2)
            content = get(row, 3)
            status = get(row, 5)
            plan = get(row, 6)
            if not valid_data_row(cat, content):
                continue
            if cat:
                lines.append(f"【{cat}】")
            if content:
                for ln in content.split("\n"):
                    ln = ln.strip()
                    if ln:
                        lines.append(f"  {ln}")
            if status:
                lines.append(f"  完成情况：{status}")
            if plan:
                lines.append(f"  后续计划：{plan}")
            lines.append("")

        # 二、重点工作跟进: B=工作分类 C=工作内容 D=当前进展 F=困难与求助
        lines.append("二、重点工作跟进")
        for row in follow_range:
            cat = get(row, 2)
            content = get(row, 3)
            progress = get(row, 4)
            difficulty = get(row, 6)
            if not valid_data_row(cat, content):
                continue
            if cat:
                lines.append(f"【{cat}】")
            if content:
                for ln in content.split("\n"):
                    ln = ln.strip()
                    if ln:
                        lines.append(f"  {ln}")
            if progress:
                lines.append(f"  当前进展：{progress}")
            if difficulty:
                lines.append(f"  困难与求助：{difficulty}")
            lines.append("")

        # 三、下周工作计划: B=工作分类 C=工作内容 F=困难与求助
        lines.append("三、下周工作计划")
        for row in next_range:
            cat = get(row, 2)
            content = get(row, 3)
            difficulty = get(row, 6)
            if not valid_data_row(cat, content):
                continue
            if cat:
                lines.append(f"【{cat}】")
            if content:
                for ln in content.split("\n"):
                    ln = ln.strip()
                    if ln:
                        lines.append(f"  {ln}")
            if difficulty:
                lines.append(f"  困难与求助：{difficulty}")
            lines.append("")

        text_body = "\n".join(lines).strip()

        # ===== HTML 表格版本 =====
        h = []
        if title:
            h.append(f'<h3 style="margin:0 0 12px 0;font-size:16px;">{html_escape(title)}</h3>')

        th_style = "border:1px solid #ccc;padding:6px 8px;text-align:left;background:#f5f5f5;font-size:13px;"
        td_style = "border:1px solid #ccc;padding:6px 8px;text-align:left;font-size:13px;vertical-align:top;"
        table_style = "width:100%;border-collapse:collapse;margin-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif;"

        def make_table(headers, rows):
            parts = ['<table style="' + table_style + '">']
            parts.append('<tr>')
            for hd in headers:
                parts.append(f'<th style="{th_style}">{html_escape(hd)}</th>')
            parts.append('</tr>')
            for row in rows:
                if not any(row):
                    continue
                parts.append('<tr>')
                for cell in row:
                    cell_html = html_escape(cell).replace("\n", "<br>")
                    parts.append(f'<td style="{td_style}">{cell_html}</td>')
                parts.append('</tr>')
            parts.append('</table>')
            return "".join(parts)

        # 本周工作总结
        h.append('<p style="font-size:14px;font-weight:bold;margin:12px 0 6px 0;">一、本周工作总结</p>')
        summary_rows = []
        for row in summary_range:
            cat = get(row, 2)
            content = get(row, 3)
            status = get(row, 5)
            plan = get(row, 6)
            if valid_data_row(cat, content):
                summary_rows.append([cat, content, status, plan])
        h.append(make_table(["工作分类", "工作内容", "完成情况", "后续计划"], summary_rows))

        # 重点工作跟进
        h.append('<p style="font-size:14px;font-weight:bold;margin:12px 0 6px 0;">二、重点工作跟进</p>')
        follow_rows = []
        for row in follow_range:
            cat = get(row, 2)
            content = get(row, 3)
            progress = get(row, 4)
            difficulty = get(row, 6)
            if valid_data_row(cat, content):
                follow_rows.append([cat, content, progress, difficulty])
        h.append(make_table(["工作分类", "工作内容", "当前进展", "困难与求助"], follow_rows))

        # 下周工作计划
        h.append('<p style="font-size:14px;font-weight:bold;margin:12px 0 6px 0;">三、下周工作计划</p>')
        next_rows = []
        for row in next_range:
            cat = get(row, 2)
            content = get(row, 3)
            difficulty = get(row, 6)
            if valid_data_row(cat, content):
                next_rows.append([cat, content, difficulty])
        h.append(make_table(["工作分类", "工作内容", "困难与求助"], next_rows))

        html_body = "".join(h)
        return text_body, html_body
    except Exception:
        return "", ""


def format_trip_body(path):
    """从 docx 出差报告提取结构化摘要，返回 (纯文本, HTML)"""
    try:
        from docx import Document
        doc = Document(path)
        if not doc.tables:
            return "", ""
        table = doc.tables[0]

        def cell_text(r, c):
            try:
                return table.cell(r, c).text.strip()
            except Exception:
                return ""

        reporter = cell_text(0, 1)
        department = cell_text(0, 3)
        location = cell_text(0, 5)
        date_text = cell_text(1, 1)
        purpose = cell_text(2, 1)
        itinerary = cell_text(3, 1)
        details = cell_text(4, 1)
        issues = cell_text(5, 1)
        suggestions = cell_text(6, 1)

        # ===== 纯文本版本 =====
        lines = []
        if reporter:
            lines.append(f"报告人：{reporter}")
        if department:
            lines.append(f"部门：{department}")
        if location:
            lines.append(f"出差地点：{location}")
        if date_text:
            lines.append(f"出差时间：{date_text}")
        lines.append("")

        if purpose:
            lines.append("【出差目的】")
            lines.append(purpose)
            lines.append("")
        if itinerary:
            lines.append("【行程概览】")
            lines.append(itinerary)
            lines.append("")
        if details:
            lines.append("【工作详情】")
            lines.append(details)
            lines.append("")
        if issues:
            lines.append("【问题与困难】")
            lines.append(issues)
            lines.append("")
        if suggestions:
            lines.append("【改进建议】")
            lines.append(suggestions)
            lines.append("")

        text_body = "\n".join(lines).strip()

        # ===== HTML 表格版本 =====
        h = []
        h.append('<table style="width:100%;border-collapse:collapse;margin-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Microsoft YaHei,sans-serif;font-size:13px;">')

        info_rows = [
            ["报告人", reporter, "部门", department, "出差地点", location],
            ["出差时间", date_text, "", "", "", ""],
        ]
        td_label = "border:1px solid #ccc;padding:6px 8px;background:#f5f5f5;font-weight:bold;width:12%;"
        td_value = "border:1px solid #ccc;padding:6px 8px;"

        for row in info_rows:
            h.append('<tr>')
            h.append(f'<td style="{td_label}">{html_escape(row[0])}</td>')
            h.append(f'<td style="{td_value}" colspan="5">{html_escape(row[1])}</td>')
            h.append('</tr>')
        h.append('</table>')

        section_style = "font-size:14px;font-weight:bold;margin:12px 0 6px 0;"
        content_style = "font-size:13px;line-height:1.6;margin:0 0 12px 0;"

        if purpose:
            h.append(f'<p style="{section_style}">【出差目的】</p>')
            h.append(f'<p style="{content_style}">{html_escape(purpose).replace(chr(10), "<br>")}</p>')
        if itinerary:
            h.append(f'<p style="{section_style}">【行程概览】</p>')
            h.append(f'<p style="{content_style}">{html_escape(itinerary).replace(chr(10), "<br>")}</p>')
        if details:
            h.append(f'<p style="{section_style}">【工作详情】</p>')
            h.append(f'<p style="{content_style}">{html_escape(details).replace(chr(10), "<br>")}</p>')
        if issues:
            h.append(f'<p style="{section_style}">【问题与困难】</p>')
            h.append(f'<p style="{content_style}">{html_escape(issues).replace(chr(10), "<br>")}</p>')
        if suggestions:
            h.append(f'<p style="{section_style}">【改进建议】</p>')
            h.append(f'<p style="{content_style}">{html_escape(suggestions).replace(chr(10), "<br>")}</p>')

        html_body = "".join(h)
        return text_body, html_body
    except Exception:
        return "", ""


def compose_draft(kind, file_name=None, username=None):
    config = read_config()
    mail = user_mail_config(username)
    report = None
    if file_name:
        for item in all_files(username):
            if item["name"] == file_name:
                report = item
                break
    if report is None:
        report = newest(kind, username, fallback_shared=True)
    if report is None:
        return {"error": "没有找到对应报告"}

    path = Path(report["path"])
    preview = preview_file(path)
    preview_html = preview_file_html(path)
    sender = config.get("sender_name", "周颖超")
    if kind == "weekly":
        subject = f"【周报】{path.stem}"
        summary_text, summary_html = format_weekly_body(path)
        body = (
            f"{config.get('weekly_greeting', '领导您好：')}\n\n"
            f"附件为我的本周工作周报《{path.name}》，请查收。\n\n"
        )
        if summary_text:
            body += summary_text + "\n\n"
        body += (
            "本周主要工作内容已在附件中汇总，如有需要补充或调整的地方，我会及时完善。\n\n"
            f"{sender}\n"
            f"{datetime.now().strftime('%Y年%m月%d日')}"
        )
        body_html = f'<p>{html_escape(config.get("weekly_greeting", "领导您好："))}</p><p>附件为我的本周工作周报《{html_escape(path.name)}》，请查收。</p>'
        if summary_html:
            body_html += summary_html
        body_html += f'<p>本周主要工作内容已在附件中汇总，如有需要补充或调整的地方，我会及时完善。</p><p>{html_escape(sender)}<br>{datetime.now().strftime("%Y年%m月%d日")}</p>'
        to_addr = mail.get("weekly_to", "")
        cc_addr = mail.get("weekly_cc", "")
    else:
        subject = f"【出差报告】{path.stem}"
        summary_text, summary_html = format_trip_body(path)
        trip_table_html = preview_html or summary_html
        body = (
            f"{config.get('trip_greeting', '领导您好：')}\n\n"
            f"附件为我的出差报告《{path.name}》，请查收。\n\n"
        )
        if summary_text:
            body += summary_text + "\n\n"
        body += (
            "出差事项、过程记录和相关结论已在附件中说明，如需进一步补充材料，我会及时整理。\n\n"
            f"{sender}\n"
            f"{datetime.now().strftime('%Y年%m月%d日')}"
        )
        body_html = f'<p>{html_escape(config.get("trip_greeting", "领导您好："))}</p><p>附件为我的出差报告《{html_escape(path.name)}》，请查收。</p>'
        if trip_table_html:
            body_html += trip_table_html
        body_html += f'<p>出差事项、过程记录和相关结论已在附件中说明，如需进一步补充材料，我会及时整理。</p><p>{html_escape(sender)}<br>{datetime.now().strftime("%Y年%m月%d日")}</p>'
        to_addr = mail.get("trip_to", "")
        cc_addr = mail.get("trip_cc", "")

    return {
        "kind": kind,
        "subject": subject,
        "body": body,
        "body_html": body_html,
        "to": to_addr,
        "cc": cc_addr,
        "attachment": report["name"],
        "attachment_path": report["path"],
        "download_url": "/download?file=" + urllib.parse.quote(report["name"]),
        "preview": preview,
        "preview_html": preview_html,
    }

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


def imap_settings(username=None):
    mail = user_mail_config(username)
    return {
        "host": mail.get("imap_host", ""),
        "port": int(mail.get("imap_port") or 993),
        "user": mail.get("imap_user", "") or mail.get("smtp_user", ""),
        "password": mail.get("imap_password", "") or mail.get("smtp_password", ""),
        "use_ssl": bool(mail.get("imap_ssl", True)),
    }


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


def test_user_mail_config(username):
    settings = smtp_settings(username)
    validate_smtp_ready(settings)
    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(settings["user"], settings["password"])
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings["user"], settings["password"])
    return {"ok": True, "message": "邮箱配置测试成功，可以正常登录 SMTP。"}


def imap_connect(username):
    settings = imap_settings(username)
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


def mail_summary_from_message(uid, msg):
    attachments = []
    for part in msg.walk() if msg.is_multipart() else []:
        name = part.get_filename()
        if name:
            payload = part.get_payload(decode=True) or b""
            attachments.append({
                "name": decode_mime_value(name),
                "size": len(payload),
                "type": part.get_content_type(),
            })
    body_html = extract_mail_html(msg)
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


def list_inbox_messages(username, limit=20, refresh=False):
    limit = max(1, min(int(limit or 20), 50))
    cache_name = f"inbox_{limit}"
    if not refresh:
        cached = read_mail_cache(username, cache_name, 1800)
        if cached:
            cached["ok"] = True
            cached["cached"] = True
            return cached
    box = imap_connect(username)
    try:
        box.select("INBOX", readonly=True)
        status, data = box.uid("search", None, "ALL")
        if status != "OK":
            raise ValueError("读取收件箱失败")
        uids = data[0].split()[-limit:][::-1]
        messages = []
        if uids:
            uid_set = b",".join(uids)
            status, fetched = box.uid("fetch", uid_set, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE)])")
            if status != "OK" or not fetched:
                raise ValueError("读取收件箱失败")
            for item in fetched:
                if not isinstance(item, tuple) or not item[1]:
                    continue
                meta = item[0].decode("utf-8", errors="ignore")
                match = re.search(r"UID\s+(\d+)", meta)
                uid = match.group(1) if match else ""
                if not uid:
                    continue
                messages.append(mail_header_summary(uid, email.message_from_bytes(item[1])))
        uid_order = {uid.decode("ascii", errors="ignore"): idx for idx, uid in enumerate(uids)}
        messages.sort(key=lambda item: uid_order.get(str(item.get("uid", "")), 999))
        result = write_mail_cache(username, cache_name, {"ok": True, "messages": messages, "cached": False})
        result["ok"] = True
        return result
    finally:
        try:
            box.logout()
        except Exception:
            pass


def get_inbox_message(username, uid, refresh=False):
    uid = str(uid or "").strip()
    if not uid:
        raise ValueError("缺少邮件 UID")
    cache_name = f"detail_{uid}"
    if not refresh:
        cached = read_mail_cache(username, cache_name, 7200)
        if cached:
            cached["ok"] = True
            cached["cached"] = True
            return cached
    box = imap_connect(username)
    try:
        box.select("INBOX", readonly=True)
        status, fetched = box.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK" or not fetched:
            raise ValueError("邮件不存在或读取失败")
        raw = next((item[1] for item in fetched if isinstance(item, tuple)), None)
        if not raw:
            raise ValueError("邮件内容为空")
        result = write_mail_cache(username, cache_name, {"ok": True, "message": mail_summary_from_message(uid, email.message_from_bytes(raw)), "cached": False})
        result["ok"] = True
        return result
    finally:
        try:
            box.logout()
        except Exception:
            pass


def split_addresses(value):
    return [item.strip() for item in re.split(r"[;,]", value or "") if item.strip()]


def build_message(payload, username=None):
    settings = smtp_settings(username)
    mail_cfg = user_mail_config(username)
    user_email = mail_cfg.get("user_email", "")
    from_addr = payload.get("from") or user_email or settings["from_addr"] or settings["user"]
    if not from_addr:
        from_addr = "no-reply@local"

    config = read_config()
    user_mail = config.get("user_mail_settings", {}).get(username or "", {})
    signature = user_mail.get("email_signature", default_email_signature_for_user(username)) or ""
    body = payload.get("body", "") or ""
    if signature:
        if not body.endswith(signature):
            body = body + signature

    body_html = payload.get("body_html", "") or ""
    if signature and body_html:
        sig_html = html_escape(signature).replace("\n", "<br>")
        if sig_html not in body_html:
            body_html = body_html + "<br>" + sig_html

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
    path = user_generated_dir(username) / attachment_name if username else GENERATED_DIR / attachment_name
    if not path.exists():
        path = user_report_dir(username) / attachment_name if username else REPORT_DIR / attachment_name
    if attachment_name and path.exists():
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
    bases = (user_generated_dir(username), user_report_dir(username)) if username else (GENERATED_DIR, REPORT_DIR)
    for base in bases:
        path = base / safe_name
        if path.exists() and path.is_file():
            return path
    return None


def history_path_by_name(file_name, username=None):
    safe_name = Path(file_name or "").name
    path = (user_report_dir(username) if username else REPORT_DIR) / safe_name
    if path.exists() and path.is_file():
        return path
    return None


def clean_lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def parse_table_lines(value, columns):
    if isinstance(value, list):
        rows = []
        for row in value:
            if isinstance(row, dict):
                keys = ["category", "content", "status", "plan", "progress", "difficulty"]
                values = [str(row.get(key, "") or "").strip() for key in keys]
                if columns == 4:
                    rows.append([values[0], values[1], values[2] or values[4], values[3] or values[5]])
                else:
                    rows.append([values[0], values[1], values[5] or values[3]])
            elif isinstance(row, list):
                rows.append(([str(item or "").strip() for item in row] + [""] * columns)[:columns])
        return [row for row in rows if any(row)]

    rows = []
    for line in clean_lines(value):
        parts = [part.strip() for part in re.split(r"\s*[|｜]\s*", line)]
        parts = (parts + [""] * columns)[:columns]
        rows.append(parts)
    return rows


def style_xlsx_cell(cell, horizontal="left", vertical="top"):
    cell.alignment = cell.alignment.copy(
        wrap_text=True,
        horizontal=horizontal,
        vertical=vertical,
    )


def cell_value(ws, row, col):
    value = ws.cell(row, col).value
    return "" if value is None else str(value).strip()


def xlsx_row_text(values):
    return " | ".join(values).strip()


def normalize_numbered_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[；;]\s*(?=\d+[、.．])", "\n", text)
    text = re.sub(r"(?<!^)(?<!\n)\s*(?=\d+[、.．])", "\n", text)
    text = re.sub(r"[；;]\s*(?=[*＊·-]\s*)", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def local_optimize_text(text):
    text = normalize_numbered_text(text)
    if not text:
        return ""
    replacements = {
        "后段": "后端",
        "滑框": "滑动窗口",
        "扒取": "抓取",
        "api": "API",
        "Api": "API",
        "roi": "ROI",
        "mns": "MNS",
        "ui": "UI",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    parts = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:\d+[、.．]|[-*＊·])\s*", "", line).strip(" 。；;")
        if line:
            split_parts = [p.strip(" 。；;") for p in re.split(r"[；;]\s*", line) if p.strip(" 。；;")]
            parts.extend(split_parts)
    if len(parts) <= 1:
        parts = [p.strip(" 。；;") for p in re.split(r"，(?=(?:实现|完成|推动|优化|设计|增加|完善|梳理|分析|开展|补充))", parts[0]) if p.strip(" 。；;")]
    return "\n".join(f"{idx}、{part}。" for idx, part in enumerate(parts, start=1))


def normalize_assistant_output(text):
    text = normalize_numbered_text(text)
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = []
    for idx, line in enumerate(lines, start=1):
        line = re.sub(r"^\s*\d+\s*[、.．]\s*", f"{idx}、", line)
        if not re.match(r"^\d+、", line):
            line = f"{idx}、{line.strip(' 。；;')}。"
        normalized.append(line)
    return "\n".join(normalized)


def assistant_settings():
    config = read_config()
    return {
        "url": os.getenv("ASSISTANT_API_URL", config.get("assistant_api_url", "")).rstrip("/"),
        "key": os.getenv("ASSISTANT_API_KEY", config.get("assistant_api_key", "")),
        "model": os.getenv("ASSISTANT_MODEL", config.get("assistant_model", "MiniMax-M2.7")),
        "prompt": os.getenv("ASSISTANT_PROMPT", config.get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT)),
    }


def optimize_text(payload):
    text = str(payload.get("text", "") or "").strip()
    prompt = str(payload.get("prompt", "") or "").strip() or assistant_settings()["prompt"]
    if not text:
        return {"ok": True, "mode": "empty", "text": ""}

    settings = assistant_settings()
    if settings["url"] and settings["key"]:
        try:
            body = json.dumps(
                {
                    "model": settings["model"],
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是中文工作周报写作助手。只输出优化后的正文，不要解释，"
                                "不要使用Markdown标题，不要添加用户未提供的事项。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"{prompt}\n\n待优化内容：\n{text}",
                        },
                    ],
                    "temperature": 0.2,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                settings["url"] + "/v1/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + settings["key"],
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return {"ok": True, "mode": "api", "model": settings["model"], "text": normalize_assistant_output(content)}
        except Exception as exc:
            return {
                "ok": True,
                "mode": "local_fallback",
                "warning": f"智能接口调用失败，已使用本地规则优化：{exc}",
                "text": local_optimize_text(text),
            }

    return {"ok": True, "mode": "local", "text": local_optimize_text(text)}


WEEKLY_AGENT_SYSTEM = (
    "你是\"周报助手\"犇犇，通过对话帮用户填写和发送周报。\\n\\n"
    "工作流（必须按顺序执行）：\\n"
    "1. 获取日期：如需要当前日期或本周周期，调用 utils.get_date 获取。\\n"
    "2. 生成草稿：用户一旦提供了本周工作内容（哪怕只有几条），立即调用 weekly.compose 整理成周报结构。不要过度追问。\\n"
    "3. 生成预览：用户说\"预览/生成附件/确认\"后，调用 weekly.preview 生成 Excel、预览图和邮件草稿。\\n"
    "4. 发送邮件：用户明确说\"确认发送/可以发/发吧\"后，调用 weekly.send_confirmed 发送邮件。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息；没有的信息留空即可。\\n"
    "- 用户只要说了工作内容，哪怕很简短，也立即调用 weekly.compose，不要反复追问。\\n"
    "- 每一步先向用户说明你在做什么，再调用 Skill。\\n"
    "- 调用 weekly.preview 时，period 字段格式为 YYYY.MM.DD-YYYY.MM.DD。\\n"
    "- 如果用户只说了\"帮我写周报\"但完全没提工作内容，才需要询问。"
)

TRIP_AGENT_SYSTEM = (
    "你是\"出差报告助手\"犇犇，通过对话帮用户填写和发送出差报告。\\n\\n"
    "工作流（必须按顺序执行）：\\n"
    "1. 收集信息：引导用户提供出差时间、地点、目的、行程等。如需要当前日期，先调用 utils.get_date。\\n"
    "2. 生成报告：信息完整后，调用 document.generate 生成正式出差报告 Word 文件。\\n"
    "3. 发送邮件：用户确认后，发送邮件（如系统支持）。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息。\\n"
    "- 每一步都要先向用户说明你在做什么，再调用 Skill。"
)

DIARY_AGENT_SYSTEM = (
    "你是\"工作日记助手\"犇犇，通过对话帮用户记录每天的工作日记。\\n\\n"
    "工作流：\\n"
    "1. 收集信息：通过自然对话了解用户今天的工作内容、明日计划和想法。\\n"
    "2. 保存日记：信息完整后，调用 diary.save 保存到系统。\\n"
    "3. 查看历史：用户想查看时，调用 diary.get 或 diary.list。\\n\\n"
    "注意事项：\\n"
    "- 不要编造用户没有提供的信息。\\n"
    "- 日记内容保持自然语言，不要过度结构化。"
)

MAIL_AGENT_SYSTEM = (
    "你是\"智能邮件助手\"，帮助用户阅读邮件、提炼重点、起草普通邮件、优化邮件正文。\\n"
    "你会收到当前邮件助手页面上的收件箱、选中邮件或写信表单上下文。\\n"
    "你的任务不是写周报或出差报告；除非用户明确要求，否则不要输出报告表单 JSON。\\n"
    "请用中文直接回答，必要时给出可复制的邮件主题和正文。不要编造未提供的邮件内容。"
)

NEWS_AGENT_SYSTEM = (
    "你是\"每日资讯助手\"，帮助用户理解轨道交通每日资讯、提炼重点、总结影响和建议行动。\\n"
    "你会收到当前资讯页面内容。普通用户不能配置资讯源；只有超级管理员能配置和生成。\\n"
    "你的任务不是写周报或出差报告；不要输出报告表单 JSON。\\n"
    "请基于已提供资讯回答，不要编造最新新闻。"
)

FORUM_AGENT_SYSTEM = (
    "你是\"金点子论坛助手\"，帮助用户围绕当前话题提炼观点、生成评论、总结讨论热度和下一步行动。\\n"
    "你会收到当前论坛话题、评论输入框或话题创建草稿。\\n"
    "你的任务不是写周报或出差报告；不要输出报告表单 JSON。\\n"
    "请用中文给出适合论坛讨论的内容；如果用户要评论，优先给出一段可直接发布的评论。"
)

GENERAL_AGENT_SYSTEM = (
    "你是\"AI 办公总助手\"，根据用户当前所在页面提供工作建议。\\n"
    "可协助周报、出差报告、工作日记、邮件、论坛和每日资讯相关问题。\\n"
    "如果当前页面不是周报或出差报告，不要输出报告表单 JSON。\\n"
    "回答要简洁、可执行，不要编造不存在的信息。"
)

DEFAULT_AGENT_WORKFLOWS = {
    "weekly": "1) weekly.compose 规范化并填入周报结构 → 2) weekly.preview 生成周报文件、预览图片和邮件草稿 → 3) 用户确认后 weekly.send_confirmed 发送邮件",
    "trip": "1) trip.prefill 获取历史出差报告预填 → 2) 用户补充信息后 document.generate 生成正式报告 → 3) 发送邮件",
    "diary": "1) diary.save 保存工作日记 → 可随时 diary.get / diary.list 查看",
    "mailassistant": "1) mailbox.list 查看邮件 → 2) text.optimize 优化正文或起草回复",
    "forum": "1) forum.list 查看话题 → 2) forum.add_comment 发表评论或 forum.create 发起话题",
    "news": "1) news.list 查看每日资讯 → 2) text.optimize 提炼重点和影响",
}

AGENT_SYSTEM_PROMPTS = {
    "weekly": WEEKLY_AGENT_SYSTEM,
    "trip": TRIP_AGENT_SYSTEM,
    "diary": DIARY_AGENT_SYSTEM,
    "mailassistant": MAIL_AGENT_SYSTEM,
    "news": NEWS_AGENT_SYSTEM,
    "forum": FORUM_AGENT_SYSTEM,
    "dashboard": GENERAL_AGENT_SYSTEM,
}

AGENT_WORKFLOWS = dict(DEFAULT_AGENT_WORKFLOWS)


def load_agent_config():
    """启动时加载 agent_config.json 并覆盖默认提示词和工作流。"""
    global WEEKLY_AGENT_SYSTEM, TRIP_AGENT_SYSTEM, DIARY_AGENT_SYSTEM
    global MAIL_AGENT_SYSTEM, NEWS_AGENT_SYSTEM, FORUM_AGENT_SYSTEM
    global GENERAL_AGENT_SYSTEM, AGENT_SYSTEM_PROMPTS, AGENT_WORKFLOWS
    cfg = read_agent_config()
    prompts = cfg.get("prompts", {})
    if prompts.get("weekly"):
        WEEKLY_AGENT_SYSTEM = prompts["weekly"]
    if prompts.get("trip"):
        TRIP_AGENT_SYSTEM = prompts["trip"]
    if prompts.get("diary"):
        DIARY_AGENT_SYSTEM = prompts["diary"]
    if prompts.get("mailassistant"):
        MAIL_AGENT_SYSTEM = prompts["mailassistant"]
    if prompts.get("news"):
        NEWS_AGENT_SYSTEM = prompts["news"]
    if prompts.get("forum"):
        FORUM_AGENT_SYSTEM = prompts["forum"]
    if prompts.get("dashboard"):
        GENERAL_AGENT_SYSTEM = prompts["dashboard"]
    AGENT_SYSTEM_PROMPTS = {
        "weekly": WEEKLY_AGENT_SYSTEM,
        "trip": TRIP_AGENT_SYSTEM,
        "diary": DIARY_AGENT_SYSTEM,
        "mailassistant": MAIL_AGENT_SYSTEM,
        "news": NEWS_AGENT_SYSTEM,
        "forum": FORUM_AGENT_SYSTEM,
        "dashboard": GENERAL_AGENT_SYSTEM,
    }
    workflows = cfg.get("workflows", {})
    for key, val in workflows.items():
        if key in AGENT_WORKFLOWS and val:
            AGENT_WORKFLOWS[key] = val


def weekly_compose_skill_detail():
    return {
        "purpose": "把用户自然语言描述的工作内容整理成系统周报表单结构，支持从历史周报迁移、补全分类、优化表达、生成下周计划。",
        "when_to_use": [
            "用户说“帮我写周报、整理本周工作、根据这些内容生成周报”。",
            "用户粘贴零散工作内容，需要拆分成 1、2、3、4 点。",
            "用户要求把上周计划转成本周工作内容，或生成下一周计划。",
            "用户希望体现工作量很多、语言简洁、无错别字。"
        ],
        "input_schema": {
            "period": "周报周期，例如 2026.05.11-2026.05.15，可选",
            "raw_work": "本周原始工作内容，自然语言或多行文本",
            "last_week_plan": "上次周报的下周计划，可选，用于迁移到本周工作",
            "key_work": "重点工作/关键项目，可选",
            "next_plan": "下周计划原始描述，可选",
            "difficulties": "困难、风险、需要协调事项，可选",
            "style": "输出风格，可选，默认：简洁、具体、体现工作量"
        },
        "output_schema": {
            "weekly_summary": [{"category": "工作分类", "content": "工作内容", "status": "完成情况", "plan": "后续计划"}],
            "weekly_follow": [{"category": "重点工作", "content": "工作内容", "progress": "当前进展", "difficulty": "困难与求助"}],
            "weekly_next": [{"category": "工作分类", "content": "下周计划", "difficulty": "困难与求助"}]
        },
        "call_example": {
            "reply": "我来根据这些内容生成周报草稿。",
            "skill_call": {
                "name": "weekly.compose",
                "arguments": {
                    "period": "2026.05.11-2026.05.15",
                    "raw_work": "实现平台复杂页面层次拆解；实现多模型部署管理；训练安全帽反光衣手套检测模型；完善API授权；增加权限管理；优化UI。",
                    "key_work": "算法平台、模型服务、数据治理、多模型部署",
                    "next_plan": "推进业务与算法服务后端联调；实现ROI滑动窗口切片和结果去重；拆分微服务架构。",
                    "style": "体现工作量多，编号清晰，简洁明了"
                }
            }
        }
    }


def weekly_preview_skill_detail():
    return {
        "purpose": "根据已规范化的周报结构生成正式周报文件、邮件草稿和周报预览图片，供用户确认。",
        "when_to_use": [
            "用户已提供或确认周报结构化内容，需要生成预览。",
            "用户说“生成周报预览、让我先看看、预览没问题再发”。",
            "大模型已经通过 weekly.compose 得到 weekly_summary、weekly_follow、weekly_next。"
        ],
        "input_schema": {
            "period": "周报周期，例如 2026.05.11-2026.05.15",
            "weekly_summary": [{"category": "工作分类", "content": "工作内容", "status": "完成情况", "plan": "后续计划"}],
            "weekly_follow": [{"category": "重点工作", "content": "工作内容", "progress": "当前进展", "difficulty": "困难与求助"}],
            "weekly_next": [{"category": "工作分类", "content": "下周计划", "difficulty": "困难与求助"}]
        },
        "output_schema": {
            "file": "生成的周报 Excel 文件名",
            "download_url": "周报文件下载地址",
            "preview_image_url": "周报预览图片地址",
            "mail_draft": "待确认的邮件草稿"
        },
        "call_example": {
            "reply": "我先生成周报预览，请你确认内容和格式。",
            "skill_call": {
                "name": "weekly.preview",
                "arguments": {
                    "period": "2026.05.11-2026.05.15",
                    "weekly_summary": [{"category": "算法平台", "content": "完成平台复杂页面层次拆解。", "status": "已完成", "plan": "持续优化交互"}],
                    "weekly_follow": [],
                    "weekly_next": [{"category": "联调", "content": "推进业务与算法服务后端联调。", "difficulty": ""}]
                }
            }
        }
    }


def weekly_send_skill_detail():
    return {
        "purpose": "在用户明确确认周报预览无误后，发送周报邮件。",
        "when_to_use": [
            "用户已经查看周报预览图片并明确说“确认发送、没问题发送、可以发”。",
            "不得在未生成预览、未确认时调用。",
            "发送前需要已有 weekly.preview 返回的 file，或 arguments 中提供 attachment。"
        ],
        "input_schema": {
            "attachment": "weekly.preview 生成的周报文件名",
            "to": "收件人，可选；为空使用邮件配置中的周报收件人",
            "cc": "抄送，可选；为空使用邮件配置中的周报抄送",
            "subject": "主题，可选",
            "body": "正文，可选"
        },
        "output_schema": {
            "mode": "sent|draft",
            "message": "发送结果"
        },
        "call_example": {
            "reply": "已确认预览无误，我现在发送周报邮件。",
            "skill_call": {
                "name": "weekly.send_confirmed",
                "arguments": {"attachment": "周颖超工作周报2026.05.11-2026.05.15.xlsx"}
            }
        }
    }


def skill_defs():
    return [
        {
            "name": "reports.list",
            "module": "报告",
            "title": "查询报告列表",
            "description": "查询当前用户的周报、出差报告、生成文件和历史报告。",
            "parameters": {"kind": "all|weekly|trip，可选"},
            "safe": True,
        },
        {
            "name": "weekly.prefill",
            "module": "周报",
            "title": "获取最新周报预填",
            "description": "读取最新历史周报，将上次下周计划迁移到本次工作内容。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "weekly.compose",
            "module": "周报",
            "title": "编写/设计周报草稿",
            "description": "调用配置的大模型 API，将原始工作内容整理成周报三段式结构：本周工作总结、重点工作跟进、下周工作计划。",
            "parameters": {
                "period": "周报周期，可选",
                "raw_work": "本周原始工作内容",
                "last_week_plan": "上次周报下周计划，可选",
                "key_work": "重点工作，可选",
                "next_plan": "下周计划，可选",
                "difficulties": "困难与求助，可选",
                "style": "输出风格，可选"
            },
            "safe": True,
            "detail": weekly_compose_skill_detail(),
        },
        {
            "name": "weekly.preview",
            "module": "周报",
            "title": "生成周报预览",
            "description": "根据已整理的周报结构生成正式周报 Excel、邮件草稿和周报预览图片，供用户确认。",
            "parameters": {
                "period": "周报周期",
                "weekly_summary": "本周工作总结数组",
                "weekly_follow": "重点工作跟进数组",
                "weekly_next": "下周工作计划数组"
            },
            "safe": False,
            "detail": weekly_preview_skill_detail(),
        },
        {
            "name": "weekly.send_confirmed",
            "module": "周报",
            "title": "确认后发送周报邮件",
            "description": "仅在用户确认周报预览无误后，使用当前账号邮件配置发送周报邮件。",
            "parameters": {
                "attachment": "周报文件名，通常来自 weekly.preview",
                "to": "收件人，可选",
                "cc": "抄送，可选",
                "subject": "主题，可选",
                "body": "正文，可选"
            },
            "safe": False,
            "detail": weekly_send_skill_detail(),
        },
        {
            "name": "trip.prefill",
            "module": "出差报告",
            "title": "获取最新出差报告预填",
            "description": "读取最新历史出差报告并填充当前出差报告草稿。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "document.generate",
            "module": "报告",
            "title": "生成正式报告文件",
            "description": "按模板生成周报 Excel 或出差报告 Word。",
            "parameters": {"kind": "weekly|trip", "weekly_summary": "数组", "weekly_follow": "数组", "weekly_next": "数组", "trip fields": "出差报告字段"},
            "safe": False,
        },
        {
            "name": "text.optimize",
            "module": "通用",
            "title": "优化文本",
            "description": "用配置的大模型 API 优化工作内容、邮件正文、论坛内容等文本。",
            "parameters": {"text": "待优化文本", "prompt": "优化要求，可选"},
            "safe": True,
        },
        {
            "name": "diary.save",
            "module": "工作日记",
            "title": "保存工作日记",
            "description": "保存当前用户指定日期的工作日记。",
            "parameters": {"date": "YYYY-MM-DD", "today_work": "今日工作", "tomorrow_plan": "明日计划", "thoughts": "想法心得"},
            "safe": False,
        },
        {
            "name": "diary.get",
            "module": "工作日记",
            "title": "读取工作日记",
            "description": "读取当前用户指定日期的工作日记。",
            "parameters": {"date": "YYYY-MM-DD"},
            "safe": True,
        },
        {
            "name": "diary.list",
            "module": "工作日记",
            "title": "查询工作日记列表",
            "description": "查询当前用户的工作日记列表。",
            "parameters": {"start": "开始日期，可选", "end": "结束日期，可选"},
            "safe": True,
        },
        {
            "name": "mailbox.list",
            "module": "邮件",
            "title": "查看收件箱",
            "description": "通过当前用户 IMAP 配置读取最近邮件。",
            "parameters": {"limit": "10/20/50，可选"},
            "safe": True,
        },
        {
            "name": "mailbox.detail",
            "module": "邮件",
            "title": "查看邮件详情",
            "description": "通过邮件 UID 读取邮件正文、HTML 预览和附件信息。",
            "parameters": {"uid": "邮件 UID"},
            "safe": True,
        },
        {
            "name": "mail.send",
            "module": "邮件",
            "title": "发送普通邮件",
            "description": "使用当前用户 SMTP 配置发送普通邮件。",
            "parameters": {"to": "收件人", "cc": "抄送，可选", "subject": "主题", "body": "正文"},
            "safe": False,
        },
        {
            "name": "forum.list",
            "module": "金点子论坛",
            "title": "查看金点子话题",
            "description": "查看当前用户可见的金点子论坛话题。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "forum.create",
            "module": "金点子论坛",
            "title": "发布金点子话题",
            "description": "创建新的金点子论坛话题。",
            "parameters": {"title": "标题", "body": "内容", "tags": "标签数组，可选"},
            "safe": False,
        },
        {
            "name": "forum.comment",
            "module": "金点子论坛",
            "title": "发布论坛评论",
            "description": "给指定金点子话题添加评论。",
            "parameters": {"id": "话题 ID", "body": "评论内容"},
            "safe": False,
        },
        {
            "name": "news.latest",
            "module": "资讯",
            "title": "查看每日资讯",
            "description": "查看系统生成的最新每日资讯。",
            "parameters": {},
            "safe": True,
        },
        {
            "name": "utils.get_date",
            "module": "通用",
            "title": "获取日期信息",
            "description": "获取当前日期、今天星期几、本周起止日期、本月起止日期、本季度起止日期、当前年度等日期信息，用于填写周报周期、出差时间等。",
            "parameters": {"format": "日期格式，可选，如 YYYY.MM.DD 或 YYYY-MM-DD，默认 YYYY.MM.DD"},
            "safe": True,
        },
    ]


def skill_doc_markdown():
    lines = [
        "# 智能办公助手 Skill 文档",
        "",
        "本系统把周报、出差报告、工作日记、邮件、论坛、每日资讯等业务能力封装为可由大模型调用的 Skill。",
        "",
        "## 调用协议",
        "",
        "大模型需要调用功能时，请返回严格 JSON，不要包裹 Markdown 代码块：",
        "",
        '{"reply":"给用户看的说明","skill_call":{"name":"skill.name","arguments":{}}}',
        "",
        "如果只是普通问答，不需要调用 Skill，则直接自然语言回复即可。",
        "",
        "## 安全约束",
        "",
        "- safe=true 的 Skill 为查询、预览、优化类能力，可直接执行。",
        "- safe=false 的 Skill 会产生写入、生成文件、发邮件或发布内容等动作；前端应在关键场景增加确认。",
        "- 所有 Skill 默认在当前登录用户空间内执行，不能跨用户读取数据。",
        "",
        "## Skill 列表",
        "",
    ]
    for item in skill_defs():
        lines.extend([
            f"### {item['name']} - {item['title']}",
            "",
            item["description"],
            "",
            f"- 安全级别：{'查询/预览' if item['safe'] else '会产生写入或外部动作'}",
            f"- 参数：`{json.dumps(item['parameters'], ensure_ascii=False)}`",
            "",
        ])
        if item.get("detail"):
            detail = item["detail"]
            lines.extend([
                "#### 详细设计",
                "",
                f"- 用途：{detail.get('purpose', '')}",
                "",
                "适用场景：",
            ])
            lines.extend([f"- {line}" for line in detail.get("when_to_use", [])])
            lines.extend([
                "",
                "输入 Schema：",
                "",
                "```json",
                json.dumps(detail.get("input_schema", {}), ensure_ascii=False, indent=2),
                "```",
                "",
                "输出 Schema：",
                "",
                "```json",
                json.dumps(detail.get("output_schema", {}), ensure_ascii=False, indent=2),
                "```",
                "",
                "调用示例：",
                "",
                "```json",
                json.dumps(detail.get("call_example", {}), ensure_ascii=False, indent=2),
                "```",
                "",
            ])
    return "\n".join(lines)


def public_skill_docs():
    return {"ok": True, "skills": skill_defs(), "markdown": skill_doc_markdown()}


def skill_by_name(name):
    return next((item for item in skill_defs() if item.get("name") == name), None)


def parse_json_object(text):
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_weekly_rows(data):
    def clean_rows(rows, keys):
        result = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = {key: str(row.get(key, "") or "").strip() for key in keys}
            if any(item.values()):
                result.append(item)
        return result

    return {
        "weekly_summary": clean_rows(data.get("weekly_summary", []), ["category", "content", "status", "plan"]),
        "weekly_follow": clean_rows(data.get("weekly_follow", []), ["category", "content", "progress", "difficulty"]),
        "weekly_next": clean_rows(data.get("weekly_next", []), ["category", "content", "difficulty"]),
    }


def weekly_payload_from_draft(args):
    draft = args.get("draft") if isinstance(args.get("draft"), dict) else args
    rows = normalize_weekly_rows(draft)
    return {
        "kind": "weekly",
        "period": str(args.get("period") or draft.get("period") or datetime.now().strftime("%Y.%m.%d-%Y.%m.%d")).strip(),
        "weekly_summary": rows["weekly_summary"],
        "weekly_follow": rows["weekly_follow"],
        "weekly_next": rows["weekly_next"],
    }


def text_wrap_units(text, max_units):
    lines = []
    current = ""
    units = 0
    for ch in str(text or ""):
        if ch == "\n":
            lines.append(current)
            current = ""
            units = 0
            continue
        weight = 2 if ord(ch) > 127 else 1
        if units + weight > max_units and current:
            lines.append(current)
            current = ch
            units = weight
        else:
            current += ch
            units += weight
    if current or not lines:
        lines.append(current)
    return lines


def load_preview_font(size=18, bold=False):
    try:
        from PIL import ImageFont
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size=size)
        return ImageFont.load_default()
    except Exception:
        return None


def create_weekly_preview_image(payload, output_path):
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        raise ValueError("缺少 Pillow，无法生成周报预览图片") from exc

    rows = normalize_weekly_rows(payload)
    title_font = load_preview_font(30, True)
    section_font = load_preview_font(22, True)
    text_font = load_preview_font(17)
    small_font = load_preview_font(14)
    width = 1400
    margin = 44
    y = 36

    def estimate_section_height(title, data, keys):
        height = 54
        for row in data or [{"category": "", "content": "暂无内容"}]:
            text = " | ".join(str(row.get(k, "") or "") for k in keys)
            height += max(72, len(text_wrap_units(text, 88)) * 23 + 34)
        return height

    total_height = 110
    total_height += estimate_section_height("本周工作总结", rows["weekly_summary"], ["category", "content", "status", "plan"])
    total_height += estimate_section_height("重点工作跟进", rows["weekly_follow"], ["category", "content", "progress", "difficulty"])
    total_height += estimate_section_height("下周工作计划", rows["weekly_next"], ["category", "content", "difficulty"])
    total_height = max(900, total_height + 80)

    image = Image.new("RGB", (width, total_height), "#f4f7fb")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, width - 24, total_height - 24), radius=18, fill="#ffffff", outline="#dbe5f1", width=2)
    title = f"工作周报（{payload.get('period') or ''}）"
    draw.text((margin, y), title, fill="#172033", font=title_font)
    y += 58
    draw.text((margin, y), "预览图用于确认内容，正式格式以生成的 Excel 附件为准。", fill="#64748b", font=small_font)
    y += 38

    def section(title, data, columns):
        nonlocal y
        draw.rounded_rectangle((margin, y, width - margin, y + 38), radius=8, fill="#eff6ff", outline="#bfdbfe")
        draw.text((margin + 16, y + 8), title, fill="#1d4ed8", font=section_font)
        y += 50
        data = data or [{}]
        for index, row in enumerate(data, 1):
            line_parts = [f"{label}：{row.get(key, '')}" for key, label in columns if row.get(key, "")]
            if not line_parts:
                line_parts = ["暂无内容"]
            wrapped = []
            for part in line_parts:
                wrapped.extend(text_wrap_units(part, 92))
            card_h = max(70, len(wrapped) * 24 + 34)
            draw.rounded_rectangle((margin, y, width - margin, y + card_h), radius=8, fill="#ffffff", outline="#dbe5f1")
            draw.text((margin + 16, y + 14), f"{index}.", fill="#2563eb", font=text_font)
            text_y = y + 14
            for line in wrapped:
                draw.text((margin + 54, text_y), line, fill="#172033", font=text_font)
                text_y += 24
            y += card_h + 12
        y += 12

    section("一、本周工作总结", rows["weekly_summary"], [("category", "分类"), ("content", "内容"), ("status", "完成情况"), ("plan", "后续计划")])
    section("二、重点工作跟进", rows["weekly_follow"], [("category", "分类"), ("content", "内容"), ("progress", "进展"), ("difficulty", "困难")])
    section("三、下周工作计划", rows["weekly_next"], [("category", "分类"), ("content", "内容"), ("difficulty", "困难")])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop((0, 0, width, min(total_height, y + 36))).save(output_path)
    return output_path


def compose_weekly_skill(arguments):
    args = arguments or {}
    source_text = "\n".join(
        str(args.get(key, "") or "").strip()
        for key in ("last_week_plan", "raw_work", "key_work", "next_plan", "difficulties")
        if str(args.get(key, "") or "").strip()
    )
    if not source_text:
        raise ValueError("请提供 raw_work、last_week_plan、key_work 或 next_plan 中至少一项内容")

    settings = assistant_settings()
    prompt = (
        "你是企业周报 Skill，负责把原始工作描述整理成系统可写入的周报 JSON。"
        "要求：1、体现工作量和推进成果；2、语言简洁明了；3、修正错别字；4、不编造未提供事项；"
        "5、分类尽量贴近软件/算法/数据治理/联调/架构/UI/管理等实际工作；"
        "6、输出严格 JSON，不要 Markdown。"
        "JSON 格式："
        "{\"weekly_summary\":[{\"category\":\"\",\"content\":\"\",\"status\":\"\",\"plan\":\"\"}],"
        "\"weekly_follow\":[{\"category\":\"\",\"content\":\"\",\"progress\":\"\",\"difficulty\":\"\"}],"
        "\"weekly_next\":[{\"category\":\"\",\"content\":\"\",\"difficulty\":\"\"}]}"
    )
    user_content = json.dumps(
        {
            "period": args.get("period", ""),
            "raw_work": args.get("raw_work", ""),
            "last_week_plan": args.get("last_week_plan", ""),
            "key_work": args.get("key_work", ""),
            "next_plan": args.get("next_plan", ""),
            "difficulties": args.get("difficulties", ""),
            "style": args.get("style", "简洁、具体、体现工作量"),
        },
        ensure_ascii=False,
        indent=2,
    )

    if settings["url"] and settings["key"]:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.25,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        rows = normalize_weekly_rows(parse_json_object(content))
        return {"ok": True, "mode": "api", "model": settings["model"], "draft": rows}

    optimized = local_optimize_text(source_text)
    summary = [
        {"category": "工作推进", "content": line, "status": "已推进", "plan": ""}
        for line in optimized.splitlines()
        if line.strip()
    ]
    return {
        "ok": True,
        "mode": "local_fallback",
        "warning": "未配置大模型 API，已使用本地规则生成基础周报草稿。",
        "draft": {"weekly_summary": summary, "weekly_follow": [], "weekly_next": []},
    }


def weekly_preview_skill(arguments, username):
    payload = weekly_payload_from_draft(arguments or {})
    path = generate_weekly(payload, username)
    draft = compose_draft("weekly", path.name, username)
    preview_name = path.with_suffix(".png").name
    preview_path = user_generated_dir(username) / preview_name
    create_weekly_preview_image(payload, preview_path)
    return {
        "ok": True,
        "file": path.name,
        "download_url": "/download?file=" + urllib.parse.quote(path.name),
        "preview_image": preview_name,
        "preview_image_url": "/preview-image?file=" + urllib.parse.quote(preview_name),
        "mail_draft": draft,
        "message": "周报预览已生成，请确认预览图片和邮件草稿；确认无误后再调用 weekly.send_confirmed。",
    }


def weekly_send_confirmed_skill(arguments, username):
    args = arguments or {}
    attachment = str(args.get("attachment", "") or "").strip()
    if not attachment:
        raise ValueError("请提供 weekly.preview 生成的 attachment 文件名")
    draft = compose_draft("weekly", attachment, username)
    payload = {
        "to": args.get("to") or draft.get("to", ""),
        "cc": args.get("cc") or draft.get("cc", ""),
        "subject": args.get("subject") or draft.get("subject", ""),
        "body": args.get("body") or draft.get("body", ""),
        "body_html": args.get("body_html") or draft.get("body_html", ""),
        "attachment": attachment,
    }
    return send_mail(payload, username)


def get_date_skill(args):
    from datetime import datetime, timedelta

    fmt = str(args.get("format") or "YYYY.MM.DD").strip()
    if fmt == "YYYY-MM-DD":
        date_fmt = "%Y-%m-%d"
    elif fmt == "YYYY/MM/DD":
        date_fmt = "%Y/%m/%d"
    else:
        date_fmt = "%Y.%m.%d"

    today = datetime.now()
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[today.weekday()]

    # 本周起止（周一到周日）
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_start = monday.strftime(date_fmt)
    week_end = sunday.strftime(date_fmt)

    # 本月起止
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    # 本季度起止
    quarter = (today.month - 1) // 3 + 1
    quarter_start_month = (quarter - 1) * 3 + 1
    quarter_start = today.replace(month=quarter_start_month, day=1)
    if quarter == 4:
        next_q_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_q_start = today.replace(month=quarter_start_month + 3, day=1)
    quarter_end = next_q_start - timedelta(days=1)

    # 第几周（ISO week）
    iso_year, iso_week, _ = today.isocalendar()

    return {
        "ok": True,
        "today": today.strftime(date_fmt),
        "weekday": weekday,
        "week_range": f"{week_start}-{week_end}",
        "week_start": week_start,
        "week_end": week_end,
        "month_range": f"{month_start.strftime(date_fmt)}-{month_end.strftime(date_fmt)}",
        "quarter": f"Q{quarter}",
        "quarter_range": f"{quarter_start.strftime(date_fmt)}-{quarter_end.strftime(date_fmt)}",
        "year": str(today.year),
        "iso_week": f"{iso_year} 年第 {iso_week} 周",
    }


def execute_skill(name, arguments, username):
    args = arguments or {}
    if name == "utils.get_date":
        return get_date_skill(args)
    if name == "reports.list":
        kind = str(args.get("kind", "all") or "all")
        reports = all_files(username)
        if kind in ("weekly", "trip"):
            reports = [item for item in reports if item.get("kind") == kind]
        return {"ok": True, "reports": reports[:50]}
    if name == "weekly.prefill":
        return weekly_prefill(username)
    if name == "weekly.compose":
        return compose_weekly_skill(args)
    if name == "weekly.preview":
        return weekly_preview_skill(args, username)
    if name == "weekly.send_confirmed":
        return weekly_send_confirmed_skill(args, username)
    if name == "trip.prefill":
        return trip_prefill(username)
    if name == "document.generate":
        return generate_document(args, username)
    if name == "text.optimize":
        return optimize_text(args)
    if name == "diary.save":
        return save_diary(args, username)
    if name == "diary.get":
        return get_diary(str(args.get("date", "") or ""), username)
    if name == "diary.list":
        return list_diaries(args, username)
    if name == "mailbox.list":
        return list_inbox_messages(username, args.get("limit", 20), bool(args.get("refresh", False)))
    if name == "mailbox.detail":
        return get_inbox_message(username, str(args.get("uid", "") or ""), bool(args.get("refresh", False)))
    if name == "mail.send":
        args["body_html"] = ""
        return send_mail(args, username)
    if name == "forum.list":
        return forum_list_topics(username)
    if name == "forum.create":
        return forum_create_topic(args, username)
    if name == "forum.comment":
        return forum_add_comment(args, username)
    if name == "news.latest":
        return news_latest(False)
    raise ValueError("未知 Skill：" + str(name))


def skill_test(payload, username):
    name = str(payload.get("name", "") or "").strip()
    skill = skill_by_name(name)
    if not skill:
        raise ValueError("未知 Skill：" + name)
    if not skill.get("safe") and not payload.get("confirm_unsafe"):
        raise ValueError("该 Skill 会产生写入、生成文件、发邮件或发布内容，请勾选确认后再测试")

    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("调用参数必须是 JSON 对象")

    instruction = str(payload.get("instruction", "") or "").strip()
    model_used = ""
    if instruction:
        settings = assistant_settings()
        if not settings["url"] or not settings["key"]:
            raise ValueError("未配置 AI 接口，请先在系统配置中设置 NewAPI 地址和 Key")
        system = (
            "你是智能办公助手的 Skill 测试器。"
            "请根据用户的自然语言测试要求，为指定 Skill 生成 arguments JSON 对象。"
            "只能返回 JSON 对象本身，不要返回 Markdown，不要调用其他 Skill。"
            "必须严格贴合 Skill 参数说明，不要编造用户没有提供的业务事实。"
        )
        user_prompt = (
            "待测试 Skill：\n"
            + json.dumps(skill, ensure_ascii=False, indent=2)
            + "\n\n已有参数草稿：\n"
            + json.dumps(arguments, ensure_ascii=False, indent=2)
            + "\n\n自然语言测试要求：\n"
            + instruction
        )
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        generated = parse_json_object(content)
        if not isinstance(generated, dict):
            raise ValueError("大模型未返回有效的 arguments JSON 对象")
        arguments = generated
        model_used = settings["model"]

    result = execute_skill(name, arguments, username)
    return {
        "ok": True,
        "skill": name,
        "model": model_used,
        "arguments": arguments,
        "result": result,
    }


def _extract_balanced_json(text):
    start = text.find("{")
    if start == -1:
        return None
    count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            count += 1
        elif text[i] == "}":
            count -= 1
            if count == 0:
                return text[start : i + 1]
    return None


def _parse_xml_tool_call(text):
    """解析 <invoke name=\"...\">...<parameter>..</parameter></invoke> 格式的 tool call。"""
    invoke_match = re.search(r"<invoke\s+name=\"([^\"]+)\"[^>]*>(.*?)</invoke>", text, flags=re.S)
    if not invoke_match:
        # 也尝试 <minimax:tool_call>...<invoke>...</invoke>...</minimax:tool_call>
        invoke_match = re.search(r"<invoke\s+name=[\"']([^\"']+)[\"'][^>]*>(.*?)</invoke>", text, flags=re.S)
    if not invoke_match:
        return None
    name = invoke_match.group(1).strip()
    inner = invoke_match.group(2)
    arguments = {}
    for param_match in re.finditer(r"<parameter\s+name=\"([^\"]+)\">(.*?)</parameter>", inner, flags=re.S):
        key = param_match.group(1).strip()
        val = param_match.group(2).strip()
        try:
            arguments[key] = json.loads(val)
        except Exception:
            arguments[key] = val
    return {"name": name, "arguments": arguments}


def parse_skill_call(text):
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    # Try direct parse first
    data = None
    try:
        data = parse_json_object(raw)
    except Exception:
        pass
    # Try extracting [TOOL_CALL] ... [/TOOL_CALL] format
    if not data:
        tool_match = re.search(r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]", raw, flags=re.S)
        if tool_match:
            try:
                data = parse_json_object(tool_match.group(1))
            except Exception:
                pass
    # Try extracting JSON object from mixed text and fix unescaped control chars
    if not data:
        json_str = _extract_balanced_json(raw)
        if json_str:
            try:
                data = json.loads(json_str)
            except Exception:
                try:
                    fixed = json_str.replace("\n", "\\n").replace("\r", "\\r")
                    data = json.loads(fixed)
                except Exception:
                    pass
    if isinstance(data, dict):
        call = data.get("skill_call")
        if isinstance(call, dict) and call.get("name"):
            return {
                "reply": data.get("reply", ""),
                "name": str(call.get("name", "")).strip(),
                "arguments": call.get("arguments") or {},
            }
    # Try XML format (MiniMax etc.)
    xml_call = _parse_xml_tool_call(raw)
    if xml_call:
        return {
            "reply": "",
            "name": xml_call["name"],
            "arguments": xml_call["arguments"],
        }
    return None


def _clean_agent_reply(text):
    """从大模型回复中提取自然语言，去掉嵌入的 JSON/Skill 调用标记。"""
    if not text:
        return text
    # 去掉 [TOOL_CALL] ... [/TOOL_CALL]
    cleaned = re.sub(r"\[TOOL_CALL\].*?\[/TOOL_CALL\]", "", text, flags=re.S).strip()
    # 去掉 <minimax:tool_call> ... </minimax:tool_call>
    cleaned = re.sub(r"<minimax:tool_call>.*?</minimax:tool_call>", "", cleaned, flags=re.S).strip()
    # 去掉 <invoke>...</invoke>
    cleaned = re.sub(r"<invoke[^>]*>.*?</invoke>", "", cleaned, flags=re.S).strip()
    # 去掉独立的大括号 JSON 块（如果它占了多行或紧跟在文字后面）
    cleaned = re.sub(r"\n?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?", "\n", cleaned).strip()
    # 去掉 Markdown 代码块
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S).strip()
    return cleaned


def agent_chat(payload, username=""):
    kind = payload.get("kind", "weekly")
    messages = payload.get("messages", [])
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key"}

    system = AGENT_SYSTEM_PROMPTS.get(kind) or AGENT_SYSTEM_PROMPTS.get("weekly")
    system = (
        system
        + "\\n\\n你现在运行在“智能办公助手 Skill 模式”。"
        + "\\n如果用户要求你操作软件功能，请从下面 Skill 中选择一个调用。"
        + "\\n周报工作流必须按顺序执行：1) weekly.compose 规范化并填入周报结构；2) weekly.preview 生成周报文件、预览图片和邮件草稿；3) 只有用户明确确认预览无误后，才能调用 weekly.send_confirmed 发送邮件。"
        + "\\n调用时必须且只能输出严格 JSON（禁止 Markdown、XML、\[TOOL_CALL\]）：{\"reply\":\"说明\",\"skill_call\":{\"name\":\"skill.name\",\"arguments\":{}}}"
        + "\\n如果不需要操作软件功能，直接自然语言回复。"
        + "\\n如需当前日期、本周起止日期、今天是星期几等时间信息，可调用 utils.get_date。"
        + "\\n可用 Skill：\\n"
        + json.dumps(skill_defs(), ensure_ascii=False)
    )
    api_messages = [{"role": "system", "content": system}]
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = str(m.get("content", "") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        api_messages.append({"role": role, "content": content})

    try:
        executed_calls = []
        max_rounds = 3
        for _round in range(max_rounds):
            data = request_json(
                settings["url"] + "/v1/chat/completions",
                settings["key"],
                {
                    "model": settings["model"],
                    "messages": api_messages,
                    "temperature": 0.6 if _round == 0 else 0.4,
                },
                "POST",
                60,
            )
            content = data["choices"][0]["message"]["content"].strip()
            skill_call = parse_skill_call(content)
            if not skill_call:
                # 没有新的 Skill 调用，直接返回最终回复
                final_reply = _clean_agent_reply(content)
                if executed_calls:
                    return {
                        "ok": True,
                        "reply": final_reply,
                        "skill_calls": executed_calls,
                    }
                return {"ok": True, "reply": final_reply}
            # 执行 Skill
            result = execute_skill(skill_call["name"], skill_call["arguments"], username)
            executed_calls.append({
                "name": skill_call["name"],
                "arguments": skill_call["arguments"],
                "result": result,
            })
            # 将结果反馈给大模型，继续下一轮
            api_messages.append({"role": "assistant", "content": content})
            api_messages.append({
                "role": "user",
                "content": (
                    "[系统通知：你刚才调用了 Skill '" + skill_call["name"] + "'，执行结果如下。"
                    "如果任务已完成，请用自然语言回复用户。"
                    "如果还需要继续操作（如先生成草稿再生成预览），可以继续调用下一个 Skill。]\n"
                    + json.dumps(result, ensure_ascii=False)
                ),
            })
        # 达到最大轮次，返回最后一次回复
        return {
            "ok": True,
            "reply": content,
            "skill_calls": executed_calls,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def save_agent_config(payload):
    cfg = read_agent_config()
    if "prompts" in payload:
        cfg["prompts"] = payload["prompts"]
    if "workflows" in payload:
        cfg["workflows"] = payload["workflows"]
    write_agent_config(cfg)
    load_agent_config()
    return {"ok": True, "message": "犇犇配置已保存并生效"}


def agent_orchestration():
    return {
        "ok": True,
        "agents": AGENT_SYSTEM_PROMPTS,
        "skill_mode_suffix": (
            "\\n\\n你现在运行在「智能办公助手 Skill 模式」。"
            "\\n如果用户要求你操作软件功能，请从下面 Skill 中选择一个调用。"
            '\\n调用时只输出严格 JSON：{\\"reply\\":\\"说明\\",\\"skill_call\\":{\\"name\\":\\"skill.name\\",\\"arguments\\":{}}}'
            "\\n如果不需要操作软件功能，直接自然语言回复。"
        ),
        "workflows": AGENT_WORKFLOWS,
        "skills": skill_defs(),
    }


# ===== 工作日记 =====

def read_json_lenient(path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        data, _ = json.JSONDecoder().raw_decode(text)
        return data


def save_diary(payload, username):
    date_str = str(payload.get("date", "") or "").strip()
    if not date_str:
        raise ValueError("请选择日记日期")
    diary_dir = user_diary_dir(username)
    diary_dir.mkdir(parents=True, exist_ok=True)
    path = diary_dir / f"{date_str}.json"
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "date": date_str,
        "today_work": str(payload.get("today_work", "") or "").strip(),
        "tomorrow_plan": str(payload.get("tomorrow_plan", "") or "").strip(),
        "thoughts": str(payload.get("thoughts", "") or "").strip(),
        "updated_at": now,
    }
    if path.exists():
        old = read_json_lenient(path)
        data["created_at"] = old.get("created_at", now)
    else:
        data["created_at"] = now
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "diary": data}


def get_diary(date_str, username):
    if not date_str:
        return {"ok": True, "diary": None}
    path = user_diary_dir(username) / f"{date_str}.json"
    if not path.exists():
        return {"ok": True, "diary": None}
    return {"ok": True, "diary": read_json_lenient(path)}


def list_diaries(payload, username):
    diary_dir = user_diary_dir(username)
    if not diary_dir.exists():
        return {"ok": True, "diaries": []}
    items = []
    for p in sorted(diary_dir.glob("*.json"), reverse=True):
        try:
            d = read_json_lenient(p)
            items.append({
                "date": d.get("date", p.stem),
                "today_work_preview": d.get("today_work", "")[:80],
                "created_at": d.get("created_at", ""),
                "updated_at": d.get("updated_at", ""),
            })
        except Exception:
            continue
    limit = int(payload.get("limit", 0) or 0)
    if limit > 0:
        items = items[:limit]
    return {"ok": True, "diaries": items}


def delete_diary(date_str, username):
    if not date_str:
        raise ValueError("请选择要删除的日记日期")
    path = user_diary_dir(username) / f"{date_str}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}


def summarize_diaries_for_weekly(payload, username):
    start_date = str(payload.get("start_date", "") or "").strip()
    end_date = str(payload.get("end_date", "") or "").strip()
    if not start_date or not end_date:
        raise ValueError("请选择日记日期范围")
    diary_dir = user_diary_dir(username)
    contents = []
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while cur <= end:
        date_str = cur.strftime("%Y-%m-%d")
        path = diary_dir / f"{date_str}.json"
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                parts = [f"【{date_str}】"]
                if d.get("today_work"):
                    parts.append(f"今日工作：{d['today_work']}")
                if d.get("tomorrow_plan"):
                    parts.append(f"明日计划：{d['tomorrow_plan']}")
                if d.get("thoughts"):
                    parts.append(f"思路想法：{d['thoughts']}")
                contents.append("\n".join(parts))
            except Exception:
                pass
        cur += __import__("datetime").timedelta(days=1)
    if not contents:
        return {"ok": True, "mode": "empty", "summary": "", "warning": "该日期范围内没有工作日记"}
    full_text = "\n\n".join(contents)
    settings = assistant_settings()
    prompt = (
        "请根据下面的工作日记内容，总结生成周报的三个部分。"
        "要求：1. 本周工作总结：概括已完成的主要工作，按要点列出；"
        "2. 重点工作跟进：提炼需要持续跟进的重大事项和当前进展；"
        "3. 下周工作计划：基于日记中的明日计划和思路，整理出下周工作安排。"
        "输出格式：\n本周工作总结：\n1. ...\n2. ...\n\n重点工作跟进：\n1. ...\n2. ...\n\n下周工作计划：\n1. ...\n2. ..."
    )
    if settings["url"] and settings["key"]:
        try:
            body = json.dumps(
                {
                    "model": settings["model"],
                    "messages": [
                        {"role": "system", "content": "你是中文工作周报写作助手。只输出总结内容，不要解释。"},
                        {"role": "user", "content": f"{prompt}\n\n工作日记内容：\n{full_text}"},
                    ],
                    "temperature": 0.3,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            req = urllib.request.Request(
                settings["url"] + "/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["key"]},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            return {"ok": True, "mode": "api", "summary": content}
        except Exception as exc:
            return {"ok": False, "error": f"AI 总结失败：{exc}"}
    return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 API 地址和 Key"}


# ===== 金点子论坛 =====

def forum_store_path(username):
    forum_dir = USER_DATA_DIR / "_forum"
    forum_dir.mkdir(parents=True, exist_ok=True)
    return forum_dir / "topics.json"


def load_forum_topics(username):
    path = forum_store_path(username)
    if not path.exists():
        return []
    try:
        data = read_json_lenient(path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_forum_topics(username, topics):
    forum_store_path(username).write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")


def forum_public_topic(topic, with_comments=False):
    item = dict(topic)
    comments = item.get("comments", [])
    likes = item.get("likes", [])
    item["comment_count"] = len(comments)
    item["like_count"] = len(likes)
    item["view_count"] = int(item.get("view_count", 0) or 0)
    item["heat"] = item["view_count"] + item["like_count"] * 5 + item["comment_count"] * 3
    if not with_comments:
        item.pop("comments", None)
    item.pop("likes", None)
    return item


def forum_list_topics(username):
    topics = sorted(load_forum_topics(username), key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"ok": True, "topics": [forum_public_topic(topic) for topic in topics]}


def forum_get_topic(payload, username):
    topic_id = str(payload.get("id", "") or "").strip()
    topics = load_forum_topics(username)
    for topic in topics:
        if topic.get("id") == topic_id:
            topic["view_count"] = int(topic.get("view_count", 0) or 0) + 1
            save_forum_topics(username, topics)
            return {"ok": True, "topic": forum_public_topic(topic, with_comments=True)}
    raise ValueError("话题不存在")


def forum_create_topic(payload, username):
    title = str(payload.get("title", "") or "").strip()
    body = str(payload.get("body", "") or "").strip()
    source = str(payload.get("source", "") or "user").strip() or "user"
    if not title:
        raise ValueError("请填写话题标题")
    if not body:
        raise ValueError("请填写话题内容")
    now = datetime.now().isoformat(timespec="seconds")
    user = find_user(username) or {}
    topic = {
        "id": secrets.token_urlsafe(10),
        "title": title,
        "body": body,
        "source": source,
        "author": user.get("name") or username,
        "created_at": now,
        "updated_at": now,
        "view_count": 0,
        "likes": [],
        "comments": [],
    }
    topics = load_forum_topics(username)
    topics.append(topic)
    save_forum_topics(username, topics)
    return {"ok": True, "topic": forum_public_topic(topic, with_comments=True)}


def forum_add_comment(payload, username):
    topic_id = str(payload.get("topic_id", "") or "").strip()
    content = str(payload.get("content", "") or "").strip()
    parent_id = str(payload.get("parent_id", "") or "").strip()
    if not topic_id:
        raise ValueError("请选择话题")
    if not content:
        raise ValueError("请填写讨论内容")
    topics = load_forum_topics(username)
    user = find_user(username) or {}
    now = datetime.now().isoformat(timespec="seconds")
    for topic in topics:
        if topic.get("id") == topic_id:
            topic.setdefault("comments", []).append({
                "id": secrets.token_urlsafe(8),
                "parent_id": parent_id,
                "author": user.get("name") or username,
                "content": content,
                "created_at": now,
            })
            topic["updated_at"] = now
            save_forum_topics(username, topics)
            return {"ok": True, "topic": forum_public_topic(topic, with_comments=True)}
    raise ValueError("话题不存在")


def forum_toggle_like(payload, username):
    topic_id = str(payload.get("topic_id", "") or "").strip()
    if not topic_id:
        raise ValueError("请选择话题")
    topics = load_forum_topics(username)
    now = datetime.now().isoformat(timespec="seconds")
    for topic in topics:
        if topic.get("id") == topic_id:
            likes = topic.setdefault("likes", [])
            if username in likes:
                likes.remove(username)
                liked = False
            else:
                likes.append(username)
                liked = True
            topic["updated_at"] = now
            save_forum_topics(username, topics)
            item = forum_public_topic(topic, with_comments=True)
            item["liked"] = liked
            return {"ok": True, "topic": item}
    raise ValueError("话题不存在")


def extract_uploaded_text(file_item):
    name = Path(file_item.get("name", "") or "upload.txt").name
    raw = base64.b64decode(file_item.get("data", "") or "")
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return raw.decode("utf-8", errors="ignore")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as docx:
                root = ET.fromstring(docx.read("word/document.xml"))
            ns = {"w": W_NS}
            parts = []
            for paragraph in root.findall(".//w:p", ns):
                text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
                if text:
                    parts.append(text)
            return "\n".join(parts)
        except Exception:
            return ""
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            parts = []
            for ws in wb.worksheets[:3]:
                for row in ws.iter_rows(values_only=True):
                    values = [str(value).strip() for value in row if value not in (None, "")]
                    if values:
                        parts.append(" | ".join(values))
            return "\n".join(parts)
        except Exception:
            return ""
    return raw.decode("utf-8", errors="ignore")


def forum_ai_topic(payload, username):
    seed = str(payload.get("seed", "") or "").strip()
    chat = str(payload.get("chat", "") or "").strip()
    files = payload.get("files", []) or []
    document_texts = []
    for item in files[:5]:
        text = extract_uploaded_text(item)
        if text:
            document_texts.append(f"【{Path(item.get('name', '')).name}】\n{text[:6000]}")
    if not seed and not chat and not document_texts:
        raise ValueError("请输入灵感信息、聊天内容，或上传文档")

    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        raise ValueError("未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key 后再使用智能生成话题")

    content = "\n\n".join([
        f"输入信息：\n{seed}" if seed else "",
        f"聊天内容：\n{chat}" if chat else "",
        f"文档内容：\n{chr(10).join(document_texts)}" if document_texts else "",
    ]).strip()
    try:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "请根据输入信息，为团队金点子论坛生成一个适合当天讨论的话题。"
                            "话题要具体、有讨论价值，能启发大家围绕工作改进、产品创新、效率提升或项目机会发表观点。"
                            "严格返回 JSON：{\"title\":\"话题标题\",\"body\":\"话题介绍和讨论引导\"}，不要返回 Markdown。"
                        ),
                    },
                    {"role": "user", "content": content},
                ],
                "temperature": 0.7,
            },
            "POST",
            60,
        )
        result_text = data["choices"][0]["message"]["content"].strip()
        result_text = re.sub(r"^```(?:json)?|```$", "", result_text, flags=re.I).strip()
        result = json.loads(result_text)
        title = str(result.get("title", "") or "").strip()
        body = str(result.get("body", "") or "").strip()
    except Exception as exc:
        raise ValueError(f"智能生成话题调用失败：{exc}")

    if not title or not body:
        raise ValueError("智能生成话题没有返回完整标题和内容，请检查模型配置")
    return forum_create_topic({"title": title, "body": body, "source": "ai"}, username)


def forum_ai_comment(payload, username):
    topic_id = str(payload.get("topic_id", "") or "").strip()
    if not topic_id:
        raise ValueError("请选择话题")

    topics = load_forum_topics(username)
    topic = next((item for item in topics if item.get("id") == topic_id), None)
    if not topic:
        raise ValueError("话题不存在")

    comments = topic.get("comments", [])
    discussion = "\n".join(
        f"- {comment.get('author', '成员')}：{comment.get('content', '')}"
        for comment in comments[-20:]
    ) or "暂无评论"
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        raise ValueError("未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key 后再使用 AI 潜水评论")

    user = find_user(username) or {}
    display_name = user.get("name") or username or "成员"
    try:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"你是{display_name}的 AI 潜水员，正在金点子论坛里协助他阅读话题和已有讨论，"
                            "然后以他的助手身份发表一条简短、有启发的评论。"
                            "评论要像团队讨论里的自然发言：可以总结共识、补充一个角度、提出一个可落地追问或下一步建议。"
                            "不要居高临下，不要写长文，不要使用 Markdown 标题，控制在 120-220 字。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"话题：{topic.get('title', '')}\n\n"
                            f"话题说明：\n{topic.get('body', '')}\n\n"
                            f"已有讨论：\n{discussion}"
                        ),
                    },
                ],
                "temperature": 0.65,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise ValueError(f"AI 潜水评论调用失败：{exc}")

    if not content:
        raise ValueError("AI 潜水评论没有返回内容，请检查模型配置")

    return forum_add_comment({"topic_id": topic_id, "content": content}, f"{display_name}的 AI 潜水员")


# ===== 每日资讯 =====

def news_dir():
    path = USER_DATA_DIR / "_news"
    path.mkdir(parents=True, exist_ok=True)
    return path


def news_config_payload():
    config = read_config()
    return {
        "sources": config.get("news_sources", []),
        "search_query": config.get("news_search_query", "轨道交通 OR 城市轨道 OR 地铁"),
        "auto_search": bool(config.get("news_auto_search", True)),
        "auto_push": bool(config.get("news_auto_push", True)),
        "push_time": config.get("news_push_time", "08:30"),
    }


def save_news_config(payload):
    config = read_config()
    sources = payload.get("sources", [])
    if isinstance(sources, str):
        sources = [{"name": "", "url": line.strip()} for line in sources.splitlines() if line.strip()]
    clean_sources = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "") or "").strip()
        if not url:
            continue
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("资讯网页路径必须以 http:// 或 https:// 开头")
        clean_sources.append({
            "name": str(item.get("name", "") or "").strip(),
            "url": url,
        })
    config["news_sources"] = clean_sources
    config["news_search_query"] = str(payload.get("search_query", "") or "").strip()
    config["news_auto_search"] = bool(payload.get("auto_search", True))
    config["news_auto_push"] = bool(payload.get("auto_push", True))
    config["news_push_time"] = str(payload.get("push_time", "") or "08:30").strip()
    write_config(config)
    return {"ok": True, "config": news_config_payload()}


def strip_html_text(text):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_escape_unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def html_escape_unescape(text):
    import html
    return html.unescape(str(text or ""))


def fetch_news_source(source):
    url = source.get("url", "")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PersonalWorkSite/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read(800000)
        ctype = resp.headers.get_content_charset() or "utf-8"
    text = raw.decode(ctype, errors="replace")
    return {
        "name": source.get("name") or urllib.parse.urlparse(url).netloc,
        "url": url,
        "text": strip_html_text(text)[:12000],
    }


def latest_news_issue():
    path = news_dir() / "latest.json"
    if not path.exists():
        return None
    try:
        return read_json_lenient(path)
    except Exception:
        return None


def save_news_issue(issue):
    issue_path = news_dir() / f"{issue['date']}.json"
    latest_path = news_dir() / "latest.json"
    raw = json.dumps(issue, ensure_ascii=False, indent=2)
    issue_path.write_text(raw, encoding="utf-8")
    latest_path.write_text(raw, encoding="utf-8")


def public_news_issue(issue, include_config_details=False):
    if not issue:
        return None
    item = dict(issue)
    if not include_config_details:
        for key in ("sources", "errors", "search_query", "auto_search"):
            item.pop(key, None)
    return item


def news_latest(include_config=False):
    result = {"ok": True, "issue": public_news_issue(latest_news_issue(), include_config)}
    if include_config:
        result["config"] = news_config_payload()
    return result


def generate_news_issue(payload=None, username="system"):
    payload = payload or {}
    config_payload = news_config_payload()
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        raise ValueError("未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key 后再生成每日资讯")

    sources = config_payload["sources"]
    source_results = []
    errors = []
    for source in sources[:12]:
        try:
            source_results.append(fetch_news_source(source))
        except Exception as exc:
            errors.append(f"{source.get('name') or source.get('url')}：{exc}")

    search_query = str(payload.get("search_query") or config_payload["search_query"] or "").strip()
    auto_search = bool(payload.get("auto_search", config_payload["auto_search"]))
    if not source_results and not (auto_search and search_query):
        raise ValueError("请先配置资讯网页路径，或开启大模型自动网络搜索并填写搜索关键词")

    source_text = "\n\n".join(
        f"【{item['name']}】{item['url']}\n{item['text']}"
        for item in source_results
    )
    search_instruction = (
        f"请调用平台可用的联网搜索/工具能力，围绕以下关键词检索今天或近期轨道交通关键资讯：{search_query}"
        if auto_search and search_query
        else "未启用自动网络搜索，只基于已抓取网页内容生成。"
    )
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        "你是轨道交通行业资讯分析智能体。请生成一份每日关键资讯简报，聚焦轨道交通、城市轨道、地铁、智慧运维、施工安全、客流、低空/AI/数字化等与轨交相关的信息。"
        "大模型能力必须来自当前平台配置的 API。若可用工具支持联网搜索，请使用工具补充最新信息；若不可用，请只基于提供的网页内容，不要编造事实。"
        "严格返回 JSON，不要 Markdown："
        "{\"title\":\"今日标题\",\"summary\":\"总览摘要\",\"items\":[{\"title\":\"资讯标题\",\"source\":\"来源\",\"url\":\"链接\",\"impact\":\"影响/价值\",\"action\":\"建议动作\"}],\"keywords\":[\"关键词\"]}"
    )
    user_content = (
        f"日期：{today}\n\n"
        f"自动搜索要求：\n{search_instruction}\n\n"
        f"已配置网页抓取内容：\n{source_text or '无'}"
    )
    try:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.35,
            },
            "POST",
            90,
        )
        result_text = data["choices"][0]["message"]["content"].strip()
        result_text = re.sub(r"^```(?:json)?|```$", "", result_text, flags=re.I).strip()
        parsed = json.loads(result_text)
    except Exception as exc:
        raise ValueError(f"每日资讯生成失败：{exc}")

    issue = {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generated_by": username,
        "title": str(parsed.get("title", "") or f"{today} 轨道交通每日资讯").strip(),
        "summary": str(parsed.get("summary", "") or "").strip(),
        "items": parsed.get("items", []) if isinstance(parsed.get("items", []), list) else [],
        "keywords": parsed.get("keywords", []) if isinstance(parsed.get("keywords", []), list) else [],
        "sources": [{"name": item["name"], "url": item["url"]} for item in source_results],
        "errors": errors,
        "search_query": search_query,
        "auto_search": auto_search,
    }
    save_news_issue(issue)
    return {"ok": True, "issue": issue}


def news_auto_worker():
    while True:
        try:
            config = read_config()
            if config.get("news_auto_push", True):
                latest = latest_news_issue()
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                push_time = str(config.get("news_push_time", "08:30") or "08:30")
                if re.match(r"^\d{2}:\d{2}$", push_time) and now.strftime("%H:%M") < push_time:
                    time.sleep(1800)
                    continue
                if not latest or latest.get("date") != today:
                    generate_news_issue({"auto_search": config.get("news_auto_search", True)}, "system")
        except Exception:
            pass
        time.sleep(1800)


def safe_uploaded_name(name, kind):
    name = Path(name or "").name.strip()
    if not name:
        raise ValueError("上传文件缺少文件名")
    suffix = Path(name).suffix.lower()
    if kind == "weekly":
        if suffix not in {".xlsx", ".xls"}:
            raise ValueError("周报只支持 .xlsx 或 .xls 文件")
        if "工作周报" not in name:
            name = "工作周报-" + name
    elif kind == "trip":
        if suffix not in {".docx", ".md"}:
            raise ValueError("出差报告只支持 .docx 或 .md 文件")
        if not name.startswith("出差报告"):
            name = "出差报告-" + name
    else:
        raise ValueError("请选择上传类型")
    return re.sub(r"[/:\\\\]+", "_", name)


def unique_report_path(name, username=None):
    base = user_report_dir(username) if username else REPORT_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(1, 1000):
        candidate = base / f"{stem}-上传{idx}{suffix}"
        if not candidate.exists():
            return candidate
    raise ValueError("同名文件过多，请修改文件名后再上传")


def upload_history_reports(payload, username=None):
    kind = payload.get("kind")
    files = payload.get("files") or []
    if not files:
        raise ValueError("请选择需要上传的文件")
    uploaded = []
    for item in files:
        name = safe_uploaded_name(item.get("name", ""), kind)
        data = item.get("data", "")
        if "," in data:
            data = data.split(",", 1)[1]
        raw = base64.b64decode(data)
        if not raw:
            raise ValueError(f"{name} 文件内容为空")
        path = unique_report_path(name, username)
        path.write_bytes(raw)
        uploaded.append({"name": path.name, "path": str(path), "size": len(raw)})
    return {"ok": True, "uploaded": uploaded}


def delete_history_report(payload, username=None):
    path = history_path_by_name(payload.get("name", ""), username)
    if path is None:
        raise ValueError("历史报告文件不存在")
    name = path.name
    path.unlink()
    return {"ok": True, "deleted": name}


def delete_report_file(payload, username=None):
    path = attachment_path_by_name(payload.get("name", ""), username)
    if path is None:
        raise ValueError("报告文件不存在，或不是当前账号的可删除文件")
    name = path.name
    path.unlink()
    return {"ok": True, "deleted": name}


def estimated_text_lines(text, width_chars):
    lines = 0
    for part in str(text or "").splitlines() or [""]:
        visual_len = sum(2 if ord(ch) > 127 else 1 for ch in part)
        lines += max(1, (visual_len + width_chars - 1) // width_chars)
    return lines


def adjust_row_height(ws, row_idx, columns):
    width_chars = {
        2: 40,
        3: 30,
        4: 72,
        5: 24,
        6: 72,
        (3, 4): 68,
        (4, 5): 92,
        (3, 4, 5): 112,
    }
    max_lines = 1
    for col in columns:
        width = width_chars.get(col, 32)
        for merged in ws.merged_cells.ranges:
            if merged.min_row == row_idx and merged.max_row == row_idx and merged.min_col == col:
                key = tuple(range(merged.min_col, merged.max_col + 1))
                width = width_chars.get(key, width)
                break
        max_lines = max(max_lines, estimated_text_lines(ws.cell(row_idx, col).value, width))
    ws.row_dimensions[row_idx].height = min(320, max(34, max_lines * 16 + 8))


def weekly_prefill(username=None):
    from openpyxl import load_workbook

    template = Path((newest_any("weekly", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists():
        return {"weekly_summary": "", "weekly_follow": "", "weekly_next": ""}

    wb = load_workbook(template, data_only=True)
    ws = wb[wb.sheetnames[0]]

    summary = []
    summary_rows = []
    for row in range(18, min(ws.max_row, 26) + 1):
        category = cell_value(ws, row, 2)
        content = normalize_numbered_text(cell_value(ws, row, 3))
        if category or content:
            # 本周总结继承上周计划：工作分类 | 工作内容 | 完成情况 | 后续计划
            summary.append(xlsx_row_text([category, content, "", ""]))
            summary_rows.append({"category": category, "content": content, "status": "", "plan": ""})

    follow = []
    follow_rows = []
    for row in range(11, min(ws.max_row, 15) + 1):
        category = cell_value(ws, row, 2)
        content = normalize_numbered_text(cell_value(ws, row, 3))
        progress = normalize_numbered_text(cell_value(ws, row, 4))
        difficulty = normalize_numbered_text(cell_value(ws, row, 6))
        if category or content or progress or difficulty:
            follow.append(xlsx_row_text([category, content, progress, difficulty]))
            follow_rows.append(
                {
                    "category": category,
                    "content": content,
                    "progress": progress,
                    "difficulty": difficulty,
                }
            )

    return {
        "weekly_summary": "\n".join(summary),
        "weekly_follow": "\n".join(follow),
        "weekly_next": "",
        "summary_rows": summary_rows,
        "follow_rows": follow_rows,
        "next_rows": [],
        "source": template.name,
    }


def table_cell_text(table, row, col):
    try:
        return normalize_numbered_text(table.cell(row, col).text.strip())
    except Exception:
        return ""


def split_trip_date(date_text):
    text = date_text or ""
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*至\s*(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if match:
        start = f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        end = f"{int(match.group(4)):04d}-{int(match.group(5)):02d}-{int(match.group(6)):02d}"
        return start, end
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2}).*?(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if match:
        start = f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        end = f"{int(match.group(4)):04d}-{int(match.group(5)):02d}-{int(match.group(6)):02d}"
        return start, end
    return "", ""


def format_trip_date_text(start, end):
    def fmt(value):
        value = str(value or "").strip()
        match = re.match(r"(\d{4})[-/.]?(\d{1,2})[-/.]?(\d{1,2})$", value)
        if not match:
            return value
        return f"{int(match.group(1)):04d}年{int(match.group(2)):02d}月{int(match.group(3)):02d}日"
    start_text = fmt(start)
    end_text = fmt(end)
    if start_text and end_text:
        return f"{start_text}至{end_text}"
    return start_text or end_text


def trip_prefill(username=None):
    from docx import Document

    template = Path((newest("trip", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists() or template.suffix.lower() != ".docx":
        return {"source": ""}

    doc = Document(template)
    if not doc.tables:
        return {"source": template.name}
    table = doc.tables[0]
    date_text = table_cell_text(table, 1, 1)
    start, end = split_trip_date(date_text)
    return {
        "source": template.name,
        "reporter": table_cell_text(table, 0, 1) or "周颖超",
        "department": table_cell_text(table, 0, 3) or "场景研究院",
        "location": table_cell_text(table, 0, 5),
        "trip_start": start,
        "trip_end": end,
        "trip_date_text": date_text,
        "purpose": table_cell_text(table, 2, 1),
        "itinerary": table_cell_text(table, 3, 1),
        "details": table_cell_text(table, 4, 1),
        "issues": table_cell_text(table, 5, 1),
        "suggestions": table_cell_text(table, 6, 1),
    }


def generate_weekly(payload, username=None):
    from openpyxl import load_workbook
    from openpyxl.styles import Border, Side

    template = Path((newest_any("weekly", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists() or not template.is_file():
        raise ValueError("没有找到周报模板")

    output_dir = user_generated_dir(username) if username else GENERATED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    period = (payload.get("period") or datetime.now().strftime("%Y.%m.%d-%Y.%m.%d")).strip()
    safe_period = re.sub(r"[^0-9A-Za-z.\-\u4e00-\u9fff]+", "", period)
    output = output_dir / f"周颖超工作周报{safe_period}.xlsx"
    if template.resolve() == output.resolve():
        fallback = newest("weekly", username, fallback_shared=True)
        if fallback and Path(fallback.get("path", "")).resolve() != output.resolve():
            template = Path(fallback["path"])
    shutil.copy2(template, output)

    wb = load_workbook(output)
    ws = wb[wb.sheetnames[0]]

    # 取消数据区域的合并单元格，方便写入
    for mc in list(ws.merged_cells.ranges):
        if not (mc.max_row < 5 or mc.min_row > 20):
            ws.unmerge_cells(str(mc))

    ws["B2"] = f"工作周报（{period}）"

    summary_rows = parse_table_lines(payload.get("weekly_summary", ""), 4) or [
        ["", "", "", ""]
    ]
    follow_rows = parse_table_lines(payload.get("weekly_follow", ""), 4) or [
        ["", "", "", ""]
    ]
    next_rows = parse_table_lines(payload.get("weekly_next", ""), 3) or [
        ["", "", ""]
    ]

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    def merge_safe(min_r, min_c, max_r, max_c):
        try:
            ws.merge_cells(start_row=min_r, start_column=min_c, end_row=max_r, end_column=max_c)
        except Exception:
            pass

    def write_and_style(row_idx, col_idx, value, halign="left"):
        cell = ws.cell(row_idx, col_idx)
        cell.value = normalize_numbered_text(value)
        cell.border = thin_border
        style_xlsx_cell(cell, horizontal=halign, vertical="center")

    def write_section_title(row_idx, title):
        write_and_style(row_idx, 2, title, halign="center")
        merge_safe(row_idx, 2, row_idx, 6)

    def write_header(row_idx, labels, merges=None):
        for col_idx in range(2, 7):
            write_and_style(row_idx, col_idx, "")
        for col_idx, label in labels:
            write_and_style(row_idx, col_idx, label, halign="center")
        for merge in merges or []:
            merge_safe(row_idx, merge[0], row_idx, merge[1])

    max_row = max(ws.max_row, 24)
    if max_row >= 3:
        ws.delete_rows(3, max_row - 2)

    summary_title = 3
    summary_header = 4
    summary_start = 5
    write_section_title(summary_title, "一、本周工作总结")
    write_header(summary_header, [(2, "工作分类"), (3, "工作内容"), (5, "上周内容完成情况"), (6, "后续计划")], [(3, 4)])

    # 本周工作总结: B=工作分类 C=工作内容 E=完成情况 F=后续计划
    for idx, row in enumerate(summary_rows, start=summary_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 5, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 5, 6))
        merge_safe(idx, 3, idx, 4)

    follow_title = summary_start + len(summary_rows)
    follow_header = follow_title + 1
    follow_start = follow_header + 1
    write_section_title(follow_title, "二、重点工作跟进")
    write_header(follow_header, [(2, "工作分类"), (3, "工作内容"), (4, "当前进展"), (6, "困难与求助")], [(4, 5)])

    # 重点工作跟进: B=工作分类 C=工作内容 D=当前进展 F=困难与求助
    for idx, row in enumerate(follow_rows, start=follow_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 4, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 4, 6))
        merge_safe(idx, 4, idx, 5)

    next_title = follow_start + len(follow_rows)
    next_header = next_title + 1
    next_start = next_header + 1
    write_section_title(next_title, "三、下周工作计划")
    write_header(next_header, [(2, "工作分类"), (3, "工作内容"), (6, "困难与求助")], [(3, 5)])

    # 下周工作计划: B=工作分类 C=工作内容 F=困难与求助
    for idx, row in enumerate(next_rows, start=next_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 6, row[2])
        adjust_row_height(ws, idx, (2, 3, 6))
        merge_safe(idx, 3, idx, 5)

    merge_safe(2, 2, 2, 6)

    wb.save(output)
    return output


def clear_docx_row_height(row):
    from docx.oxml.ns import qn

    tr_pr = row._tr.get_or_add_trPr()
    for height in list(tr_pr.findall(qn("w:trHeight"))):
        tr_pr.remove(height)


def set_cell_text(cell, text, bold=False, compact=True):
    from docx.shared import Pt
    from docx.oxml.ns import qn

    text = normalize_numbered_text(text)
    parts = text.splitlines() or [""]
    while len(cell.paragraphs) < len(parts):
        cell.add_paragraph()
    for index, part in enumerate(parts):
        paragraph = cell.paragraphs[index]
        for run in list(paragraph.runs):
            paragraph._p.remove(run._r)
        run = paragraph.add_run(part)
        run.bold = bold
        run.font.name = "宋体"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(11)
        paragraph.paragraph_format.line_spacing = 1.08 if compact else 1.2
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(2 if compact else 4)
    for paragraph in cell.paragraphs[len(parts):]:
        paragraph._element.getparent().remove(paragraph._element)


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("w", W_NS)


def w_tag(name):
    return f"{{{W_NS}}}{name}"


def set_docx_xml_cell_text(cell, text):
    text = normalize_numbered_text(text)
    lines = text.splitlines() or [""]
    paragraphs = cell.findall(w_tag("p"))
    paragraph_template = deepcopy(paragraphs[0]) if paragraphs else ET.Element(w_tag("p"))
    paragraph_props = paragraph_template.find(w_tag("pPr"))
    run_template = paragraph_template.find(".//" + w_tag("r"))
    run_props = deepcopy(run_template.find(w_tag("rPr"))) if run_template is not None and run_template.find(w_tag("rPr")) is not None else None

    for paragraph in paragraphs:
        cell.remove(paragraph)

    for line in lines:
        paragraph = ET.Element(w_tag("p"))
        if paragraph_props is not None:
            paragraph.append(deepcopy(paragraph_props))
        run = ET.SubElement(paragraph, w_tag("r"))
        if run_props is not None:
            run.append(deepcopy(run_props))
        text_node = ET.SubElement(run, w_tag("t"))
        text_node.set(f"{{{XML_NS}}}space", "preserve")
        text_node.text = line
        cell.append(paragraph)


def generate_trip_from_docx_template(template, output, values):
    with zipfile.ZipFile(template, "r") as source:
        document_xml = source.read("word/document.xml")
        root = ET.fromstring(document_xml)
        table = root.find(".//" + w_tag("tbl"))
        if table is None:
            raise ValueError("出差报告模板中没有找到表格")
        rows = table.findall(w_tag("tr"))

        def cell(row_idx, actual_col_idx):
            return rows[row_idx].findall(w_tag("tc"))[actual_col_idx]

        cell_map = {
            (0, 1): values.get("reporter", "周颖超"),
            (0, 3): values.get("department", "场景研究院"),
            (0, 5): values.get("location", ""),
            (1, 1): values.get("date_text", ""),
            (2, 1): values.get("purpose", ""),
            (3, 1): values.get("itinerary", ""),
            (4, 1): values.get("details", ""),
            (5, 1): values.get("issues", ""),
            (6, 1): values.get("suggestions", ""),
        }
        for (row_idx, col_idx), value in cell_map.items():
            set_docx_xml_cell_text(cell(row_idx, col_idx), value)

        output.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output.with_suffix(output.suffix + ".tmp")
        with zipfile.ZipFile(temp_output, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True) if item.filename == "word/document.xml" else source.read(item.filename)
                target.writestr(item, data)
        temp_output.replace(output)


def generate_trip(payload, username=None):
    template = Path((newest("trip", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists() or template.suffix.lower() != ".docx":
        raise ValueError("没有找到 Word 出差报告模板")

    output_dir = user_generated_dir(username) if username else GENERATED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    start = (payload.get("trip_start") or datetime.now().strftime("%Y%m%d")).replace("-", "")
    end = (payload.get("trip_end") or start).replace("-", "")[-4:]
    output = output_dir / f"出差报告-{start}-{end}-周颖超.docx"
    date_text = payload.get("trip_date_text") or format_trip_date_text(payload.get("trip_start", ""), payload.get("trip_end", ""))
    values = {
        "reporter": payload.get("reporter", "周颖超"),
        "department": payload.get("department", "场景研究院"),
        "location": payload.get("location", ""),
        "date_text": date_text,
        "purpose": payload.get("purpose", ""),
        "itinerary": payload.get("itinerary", ""),
        "details": payload.get("details", ""),
        "issues": payload.get("issues", ""),
        "suggestions": payload.get("suggestions", ""),
    }
    generate_trip_from_docx_template(template, output, values)
    return output


def generate_document(payload, username=None):
    kind = payload.get("kind")
    if kind == "weekly":
        path = generate_weekly(payload, username)
    elif kind == "trip":
        path = generate_trip(payload, username)
    else:
        raise ValueError("未知生成类型")
    draft = compose_draft(kind, path.name, username)
    return {
        "ok": True,
        "file": path.name,
        "path": str(path),
        "draft": draft,
    }


def save_draft(payload, username=None):
    draft_dir = user_draft_dir(username) if username else DRAFT_DIR
    draft_dir.mkdir(parents=True, exist_ok=True)
    msg = build_message(payload, username)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_subject = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", payload.get("subject", "draft"))[:40]
    path = draft_dir / f"{stamp}-{safe_subject}.eml"
    path.write_bytes(bytes(msg))
    return path


def send_mail(payload, username=None):
    settings = smtp_settings(username)
    if not settings["host"]:
        draft = save_draft(payload, username)
        return {"ok": True, "mode": "draft", "message": f"邮件未发出：当前账号未配置 SMTP 服务器，已生成邮件草稿：{draft}"}
    validate_smtp_ready(settings)

    msg = build_message(payload, username)
    recipients = split_addresses(payload.get("to", "")) + split_addresses(payload.get("cc", ""))
    if not recipients:
        raise ValueError("请填写收件人邮箱")

    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["host"], settings["port"], context=ssl.create_default_context(), timeout=20) as smtp:
            if settings["user"]:
                smtp.login(settings["user"], settings["password"])
            smtp.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
            if settings["use_tls"]:
                smtp.starttls(context=ssl.create_default_context())
            if settings["user"]:
                smtp.login(settings["user"], settings["password"])
            smtp.send_message(msg, to_addrs=recipients)
    return {"ok": True, "mode": "sent", "message": "邮件已发送"}


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
            self.send_json(weekly_prefill(self.current_user().get("username", "")))
            return
        if parsed.path == "/api/trip-prefill":
            self.send_json(trip_prefill(self.current_user().get("username", "")))
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
    load_agent_config()
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=news_auto_worker, daemon=True).start()
    print(f"个人工作报告邮件助手已启动：http://127.0.0.1:{port}")
    print(f"英文相对访问地址：{APP_RELATIVE_PATH}")
    print(f"完整访问地址：http://127.0.0.1:{port}{APP_RELATIVE_PATH}")
    print(f"用户数据目录：{USER_DATA_DIR}")
    print(f"共享模板目录：{REPORT_DIR}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
