"""Core paths, configuration, user management, and shared HTTP helpers.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

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


def safe_report_kind(kind):
    kind = str(kind or "").strip().lower()
    if kind in {"weekly", "trip"}:
        return kind
    return "other"


def user_root(username):
    return USER_DATA_DIR / safe_username(username)


def user_report_dir(username):
    return user_root(username) / "reports"


def user_report_kind_dir(username, kind):
    return user_report_dir(username) / safe_report_kind(kind)


def user_generated_dir(username):
    return user_root(username) / "generated"


def user_generated_kind_dir(username, kind):
    return user_generated_dir(username) / safe_report_kind(kind)


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


def display_name_for_user(username):
    user = find_user(username)
    return (user or {}).get("name") or username or read_config().get("sender_name", "周颖超")


def safe_display_name(username):
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff@._-]+", "", display_name_for_user(username)) or safe_username(username)


def ensure_user_space(username):
    for path in (
        user_report_kind_dir(username, "weekly"),
        user_report_kind_dir(username, "trip"),
        user_generated_kind_dir(username, "weekly"),
        user_generated_kind_dir(username, "trip"),
        user_draft_dir(username),
        user_profile_dir(username),
    ):
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
