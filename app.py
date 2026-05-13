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
USER_DATA_DIR = BASE_DIR / "user_data"
CONFIG_PATH = BASE_DIR / "config.json"
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
        settings[field] = str(payload.get(field, "") or "").strip()
    if payload.get("smtp_password"):
        settings["smtp_password"] = str(payload.get("smtp_password") or "").strip()
    if payload.get("imap_password"):
        settings["imap_password"] = str(payload.get("imap_password") or "").strip()
    if payload.get("email_signature") is not None:
        settings["email_signature"] = str(payload.get("email_signature") or "").strip()
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
    if caller_role == "superadmin":
        return [public_user(u) for u in users]
    elif caller_role == "admin":
        return [public_user(u) for u in users if u.get("role") == "member"]
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

        # ===== 纯文本版本 =====
        lines = []
        title = get(2, 2)
        if title:
            lines.append(title)
            lines.append("")

        # 一、本周工作总结 (行5-8): B=工作分类 C=工作内容 E=完成情况 F=后续计划
        lines.append("一、本周工作总结")
        for row in range(5, 9):
            cat = get(row, 2)
            content = get(row, 3)
            status = get(row, 5)
            plan = get(row, 6)
            if not cat and not content:
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

        # 二、重点工作跟进 (行11-15): B=工作分类 C=工作内容 D=当前进展 F=困难与求助
        lines.append("二、重点工作跟进")
        for row in range(11, 16):
            cat = get(row, 2)
            content = get(row, 3)
            progress = get(row, 4)
            difficulty = get(row, 6)
            if not cat and not content:
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

        # 三、下周工作计划 (行18-20): B=工作分类 C=工作内容 F=困难与求助
        lines.append("三、下周工作计划")
        for row in range(18, 21):
            cat = get(row, 2)
            content = get(row, 3)
            difficulty = get(row, 6)
            if not cat and not content:
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
        for row in range(5, 9):
            cat = get(row, 2)
            content = get(row, 3)
            status = get(row, 5)
            plan = get(row, 6)
            if cat or content:
                summary_rows.append([cat, content, status, plan])
        h.append(make_table(["工作分类", "工作内容", "完成情况", "后续计划"], summary_rows))

        # 重点工作跟进
        h.append('<p style="font-size:14px;font-weight:bold;margin:12px 0 6px 0;">二、重点工作跟进</p>')
        follow_rows = []
        for row in range(11, 16):
            cat = get(row, 2)
            content = get(row, 3)
            progress = get(row, 4)
            difficulty = get(row, 6)
            if cat or content:
                follow_rows.append([cat, content, progress, difficulty])
        h.append(make_table(["工作分类", "工作内容", "当前进展", "困难与求助"], follow_rows))

        # 下周工作计划
        h.append('<p style="font-size:14px;font-weight:bold;margin:12px 0 6px 0;">三、下周工作计划</p>')
        next_rows = []
        for row in range(18, 21):
            cat = get(row, 2)
            content = get(row, 3)
            difficulty = get(row, 6)
            if cat or content:
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
    "你是\"周报协同助手\"，像一位贴身秘书一样通过对话帮用户直接操作周报表单。\\n\\n"
    "工作模式：\\n"
    "- 你不是在\"采访\"用户，而是在\"协同编辑\"表单。\\n"
    "- 每次对话都会把当前表单的完整数据发给你，你必须返回操作后的完整数据。\\n"
    "- 用户说\"新增/添加/来一条\"，你就往对应数组末尾追加一条（内容从用户描述提取）。\\n"
    "- 用户说\"修改/更新/把第X条\"，你就修改对应索引的数据（用户说的第1条对应数组索引0）。\\n"
    "- 用户说\"删除/去掉/移除第X条\"，你就从数组中删掉对应索引。\\n"
    "- 用户提供了具体值，直接写入对应字段。\\n"
    "- 如果用户没有明确操作意图，友好地列出当前记录并询问：\"要新增、修改还是删除？\"\\n"
    "- 不要编造用户没有提供的信息；未提及的字段保持原值。\\n\\n"
    "数据格式（每次返回都必须包含完整数组）：\\n"
    "- weekly_summary: [{category, content, status}]\\n"
    "- weekly_follow: [{category, content, progress}]\\n"
    "- weekly_next: [{category, content, difficulty}]\\n\\n"
    "返回格式（严格的JSON，不要markdown代码块，不要额外文字）：\\n"
    '{"done":false,"reply":"你的回复","weekly_summary":[],"weekly_follow":[],"weekly_next":[]}'
)

TRIP_AGENT_SYSTEM = (
    "你是\"出差报告协同助手\"，像一位贴身秘书一样通过对话帮用户直接操作出差报告表单。\\n\\n"
    "工作模式：\\n"
    "- 你不是在\"采访\"用户，而是在\"协同编辑\"表单。\\n"
    "- 每次对话都会把当前表单的完整数据发给你，你必须返回操作后的完整数据。\\n"
    "- 用户说\"地点改为青岛\"，你就把 location 改为\"青岛\"。\\n"
    "- 用户说\"补充行程\"，你就引导并更新 itinerary。\\n"
    "- 用户提供了具体值，直接写入对应字段。\\n"
    "- 如果用户没有明确操作意图，列出当前已填字段并询问想补充什么。\\n"
    "- 不要编造用户没有提供的信息；未提及的字段保持原值。\\n\\n"
    "字段（每次返回都必须包含完整字段）：\\n"
    "reporter, department, location, trip_start, trip_end, purpose, itinerary, details, issues, suggestions\\n\\n"
    "返回格式（严格的JSON，不要markdown代码块，不要额外文字）：\\n"
    '{"done":false,"reply":"你的回复","reporter":"","department":"","location":"","trip_start":"","trip_end":"","purpose":"","itinerary":"","details":"","issues":"","suggestions":""}'
)

DIARY_AGENT_SYSTEM = (
    "你是\"工作日记智能助手\"，像一位贴心的工作秘书，通过对话帮用户记录每天的工作日记。\\n\\n"
    "工作模式：\\n"
    "- 你可以通过自然对话了解用户今天的工作情况。\\n"
    "- 每次对话都要返回结构化数据。\\n"
    "- 当用户提供了足够完整的信息时，设置 done: true，并给出总结。\\n"
    "- 如果用户只提供了部分信息，友好地追问剩余部分。\\n"
    "- 不要编造用户没有提供的信息；未提及的字段保持原值。\\n"
    "- 字段内容保持自然语言，不要过度结构化。\\n\\n"
    "字段（每次返回都必须包含完整字段）：\\n"
    "today_work: 今日完成的主要工作内容\\n"
    "tomorrow_plan: 明天的工作计划\\n"
    "thoughts: 工作中的思路、想法、心得、建议\\n\\n"
    "返回格式（严格的JSON，不要markdown代码块，不要额外文字）：\\n"
    '{"done":false,"reply":"你的回复","today_work":"","tomorrow_plan":"","thoughts":""}'
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


def agent_chat(payload):
    kind = payload.get("kind", "weekly")
    messages = payload.get("messages", [])
    settings = assistant_settings()
    if not settings["url"] or not settings["key"]:
        return {"ok": False, "error": "未配置 AI 接口，请在系统配置中设置 NewAPI 地址和 Key"}

    if kind == "diary":
        system = DIARY_AGENT_SYSTEM
    elif kind == "trip":
        system = TRIP_AGENT_SYSTEM
    elif kind == "mailassistant":
        system = MAIL_AGENT_SYSTEM
    elif kind == "news":
        system = NEWS_AGENT_SYSTEM
    elif kind == "forum":
        system = FORUM_AGENT_SYSTEM
    elif kind == "dashboard":
        system = GENERAL_AGENT_SYSTEM
    else:
        system = WEEKLY_AGENT_SYSTEM
    api_messages = [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in messages
    ]

    try:
        data = request_json(
            settings["url"] + "/v1/chat/completions",
            settings["key"],
            {
                "model": settings["model"],
                "messages": api_messages,
                "temperature": 0.6,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        return {"ok": True, "reply": content}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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

    template = Path((newest("weekly", username, fallback_shared=True) or {}).get("path", ""))
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

    template = Path((newest("weekly", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists():
        raise ValueError("没有找到周报模板")

    output_dir = user_generated_dir(username) if username else GENERATED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    period = (payload.get("period") or datetime.now().strftime("%Y.%m.%d-%Y.%m.%d")).strip()
    safe_period = re.sub(r"[^0-9A-Za-z.\-\u4e00-\u9fff]+", "", period)
    output = output_dir / f"周颖超工作周报{safe_period}.xlsx"
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

    summary_extra = max(0, len(summary_rows) - 4)
    follow_extra = max(0, len(follow_rows) - 5)
    next_extra = max(0, len(next_rows) - 3)
    if next_extra:
        ws.insert_rows(21, next_extra)
    if follow_extra:
        ws.insert_rows(16, follow_extra)
    if summary_extra:
        ws.insert_rows(9, summary_extra)

    summary_start = 5
    follow_start = 11 + summary_extra
    next_start = 18 + summary_extra + follow_extra

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    def write_and_style(row_idx, col_idx, value, halign="left"):
        cell = ws.cell(row_idx, col_idx)
        cell.value = normalize_numbered_text(value)
        cell.border = thin_border
        style_xlsx_cell(cell, horizontal=halign, vertical="center")

    # 清空数据区域（包括所有列）
    for r in range(summary_start, summary_start + len(summary_rows)):
        for c in range(2, 7):
            write_and_style(r, c, "")
    for r in range(follow_start, follow_start + len(follow_rows)):
        for c in range(2, 7):
            write_and_style(r, c, "")
    for r in range(next_start, next_start + len(next_rows)):
        for c in range(2, 7):
            write_and_style(r, c, "")

    # 本周工作总结: B=工作分类 C=工作内容 E=完成情况 F=后续计划
    for idx, row in enumerate(summary_rows, start=summary_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 5, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 5, 6))

    # 重点工作跟进: B=工作分类 C=工作内容 D=当前进展 F=困难与求助
    for idx, row in enumerate(follow_rows, start=follow_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 4, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 4, 6))

    # 下周工作计划: B=工作分类 C=工作内容 F=困难与求助
    for idx, row in enumerate(next_rows, start=next_start):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 6, row[2])
        adjust_row_height(ws, idx, (2, 3, 6))

    def merge_safe(min_r, min_c, max_r, max_c):
        try:
            ws.merge_cells(start_row=min_r, start_column=min_c, end_row=max_r, end_column=max_c)
        except Exception:
            pass

    merge_safe(2, 2, 2, 6)
    merge_safe(3, 2, 3, 6)
    merge_safe(4, 3, 4, 4)
    for idx in range(summary_start, summary_start + len(summary_rows)):
        merge_safe(idx, 3, idx, 4)

    follow_title = 9 + summary_extra
    follow_header = 10 + summary_extra
    merge_safe(follow_title, 2, follow_title, 6)
    merge_safe(follow_header, 4, follow_header, 5)
    for idx in range(follow_start, follow_start + len(follow_rows)):
        merge_safe(idx, 4, idx, 5)

    next_title = 16 + summary_extra + follow_extra
    next_header = 17 + summary_extra + follow_extra
    merge_safe(next_title, 2, next_title, 6)
    merge_safe(next_header, 3, next_header, 5)
    for idx in range(next_start, next_start + len(next_rows)):
        merge_safe(idx, 3, idx, 5)

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
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI 办公助手 | 智能办公平台</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1120;
      --surface: #111827;
      --panel: #1e293b;
      --elevated: #243447;
      --ink: #f1f5f9;
      --muted: #94a3b8;
      --line: #334155;
      --accent: #3b82f6;
      --accent-2: #8b5cf6;
      --accent-gradient: linear-gradient(135deg, #3b82f6, #8b5cf6);
      --danger: #ef4444;
      --success: #10b981;
      --warning: #f59e0b;
      --shadow: 0 8px 32px rgba(2, 8, 20, .45);
      --glow: 0 0 20px rgba(59, 130, 246, .15);
      --radius: 12px;
      --radius-sm: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      background: #123c3b;
      color: #fff;
      padding: 22px 28px;
      border-bottom: 4px solid #d69839;
    }
    .header-row {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
    }
    .userbar {
      display: none;
      align-items: center;
      gap: 10px;
      color: #d7e5e3;
      font-size: 13px;
    }
    .user-avatar {
      width: 30px; height: 30px; border-radius: 50%;
      object-fit: cover; background: #eaf1fb; border: 1px solid var(--line);
    }
    .userbar button { background: rgba(255,255,255,.16); }
    h1 { margin: 0; font-size: 24px; font-weight: 720; letter-spacing: 0; }
    .sub { margin-top: 6px; color: #d7e5e3; font-size: 14px; }
    main {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      gap: 16px;
      padding: 20px;
      max-width: 1320px;
      margin: 0 auto;
      align-items: start;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .task-board {
      padding: 14px;
      position: sticky;
      top: 14px;
    }
    .task-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    .task-card {
      width: 100%;
      min-height: 64px;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
      color: var(--ink);
      box-shadow: none;
      cursor: pointer;
    }
    .task-card.active {
      border-color: var(--accent);
      background: #eef8f6;
      box-shadow: inset 0 0 0 1px #b9ded8;
    }
    .task-card .task-name {
      display: block;
      font-size: 15px;
      font-weight: 760;
      margin-bottom: 4px;
    }
    .task-card .task-desc {
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      font-weight: 520;
    }
    .task-panel.hidden { display: none; }
    .auth-panel {
      max-width: 460px;
      margin: 34px auto 0;
      padding: 18px;
    }
    .auth-panel.hidden { display: none; }
    .mail-layout {
      display: grid;
      grid-template-columns: minmax(250px, 340px) minmax(0, 1fr);
      gap: 16px;
    }
    .side {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }
    .composer { padding: 18px; }
    .sub-tabs {
      display: flex;
      gap: 8px;
      margin: 0 0 18px;
      padding: 4px;
      background: #eef1f5;
      border-radius: 10px;
      width: fit-content;
    }
    .sub-tab {
      padding: 8px 18px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 680;
      background: transparent;
      color: var(--muted);
      border: 0;
      cursor: pointer;
      transition: all .15s ease;
    }
    .sub-tab.active {
      background: #fff;
      color: var(--accent);
      box-shadow: 0 2px 8px rgba(26,34,47,.08);
    }
    .sub-tab:hover:not(.active) {
      color: var(--ink);
      background: rgba(255,255,255,.5);
    }
    h2 { margin: 0 0 14px; font-size: 17px; }
    label { display: block; margin: 12px 0 6px; font-size: 13px; color: var(--muted); }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 11px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }
    textarea { min-height: 260px; resize: vertical; line-height: 1.55; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 14px; }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      font-weight: 680;
      cursor: pointer;
      background: var(--accent);
      color: #fff;
    }
    button.secondary { background: #2f3a4a; }
    button.warn { background: var(--accent-2); }
    button.action-button {
      padding: 10px 14px;
      font-size: 14px;
      background: var(--accent);
      color: #fff;
      border: 0;
      white-space: nowrap;
    }
    .download-link {
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      padding: 8px 12px;
      border-radius: 6px;
      background: #eef8f6;
      color: var(--accent);
      border: 1px solid #b9ded8;
      text-decoration: none;
      font-weight: 680;
      font-size: 14px;
    }
    .report {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 10px;
      cursor: pointer;
      background: #fff;
    }
    .report.active { border-color: var(--accent); background: #eef8f6; }
    .report .name { font-weight: 680; word-break: break-all; }
    .report .meta { color: var(--muted); font-size: 12px; margin-top: 5px; }
    .preview {
      white-space: pre-wrap;
      background: #f8fafb;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      min-height: 130px;
      max-height: 260px;
      overflow: auto;
      color: #354052;
      font-size: 13px;
      line-height: 1.55;
    }
    .rich-preview {
      white-space: normal;
      background: #f8fafb;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      min-height: 130px;
      max-height: 360px;
      overflow: auto;
      color: #354052;
      font-size: 13px;
      line-height: 1.55;
    }
    .rich-preview table {
      min-width: 760px;
    }
    .rich-preview td,
    .rich-preview th {
      box-sizing: border-box;
    }
    .rich-preview p {
      margin: 8px 0;
    }
    .status { margin-top: 12px; font-size: 14px; color: var(--muted); }
    .status.ok { color: var(--accent); }
    .status.err { color: var(--danger); }
    .upload-list {
      margin-top: 12px;
      display: grid;
      gap: 8px;
    }
    .config-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .upload-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
      color: #354052;
      font-size: 13px;
      word-break: break-all;
    }
    .history-tools {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    .history-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .history-item {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
    }
    .history-name { font-weight: 680; word-break: break-all; }
    .history-meta { margin-top: 4px; color: var(--muted); font-size: 12px; }
    .history-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .user-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .user-item {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: #fff;
    }
    .guide {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 16px;
      background: #fbfcfd;
    }
    .guide textarea { min-height: 94px; }
    .guide .hint { color: var(--muted); font-size: 12px; margin-top: 5px; line-height: 1.45; }
    .guide-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .hidden { display: none; }
    .weekly-workspace {
      display: grid;
      gap: 12px;
    }
    .weekly-period-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }
    .weekly-period-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .weekly-period-title {
      font-weight: 760;
      color: #263142;
    }
    .weekly-period-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .weekly-section-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      align-items: start;
    }
    .weekly-section-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      min-height: 430px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .weekly-section-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .weekly-section-title {
      font-weight: 760;
      color: #263142;
      line-height: 1.3;
    }
    .weekly-section-meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    .weekly-rows {
      padding: 10px;
      overflow: auto;
      max-height: 370px;
      flex: 1;
    }
    .edit-card-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }
    .work-block {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      margin: 0 0 8px 0;
      padding: 10px;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease;
    }
    .work-block:hover, .edit-card:hover {
      border-color: var(--accent);
      background: #f5fbfa;
    }
    .work-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 6px;
    }
    .work-title { font-weight: 700; color: #263142; }
    .work-summary {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.42;
      white-space: pre-wrap;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .edit-card {
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
      cursor: pointer;
    }
    .edit-card-title {
      font-weight: 720;
      color: #263142;
      margin-bottom: 7px;
    }
    .edit-card-preview {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .mini {
      padding: 6px 9px;
      font-size: 12px;
      background: #e8edf3;
      color: #263142;
    }
    .danger {
      background: #fff0ed;
      color: var(--danger);
      border: 1px solid #f3bbb2;
    }
    .field-grid {
      display: grid;
      grid-template-columns: minmax(130px, .75fr) minmax(260px, 1.7fr) minmax(150px, 1fr) minmax(150px, 1fr);
      gap: 10px;
    }
    .field-grid.three {
      grid-template-columns: minmax(150px, .85fr) minmax(320px, 2fr) minmax(170px, 1fr);
    }
    .field-grid textarea {
      min-height: 78px;
      line-height: 1.55;
      white-space: pre-wrap;
    }
    .field-store, .trip-store { display: none; }
    .field-grid label { margin-top: 0; }
    .section-actions { margin-top: 8px; }
    .modal {
      position: fixed;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 22px;
      background: rgba(15, 23, 42, .42);
      z-index: 20;
    }
    .modal.hidden { display: none; }
    .modal-box {
      width: min(960px, 96vw);
      max-height: 90vh;
      overflow: auto;
      background: #fff;
      border-radius: 8px;
      border: 1px solid var(--line);
      box-shadow: 0 22px 60px rgba(15, 23, 42, .24);
      padding: 18px;
    }
    .modal-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .modal-title { font-size: 18px; font-weight: 760; }
    .modal-fields {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .modal-fields .wide { grid-column: 1 / -1; }
    .modal-fields textarea { min-height: 190px; }
    .field-assist {
      margin: 7px 0 4px;
      padding: 9px;
      border: 1px solid #c8d8d5;
      border-radius: 8px;
      background: #f4fbfa;
    }
    .field-assist-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }
    .field-assist details {
      flex: 1;
      min-width: 220px;
    }
    .field-assist summary {
      cursor: pointer;
      color: #174541;
      font-size: 13px;
      font-weight: 700;
    }
    .field-assist textarea {
      min-height: 104px;
      margin-top: 8px;
      font-size: 13px;
    }
    .assist-status {
      min-height: 18px;
      margin-top: 7px;
      color: var(--muted);
      font-size: 13px;
    }
    .assist-status.ok { color: var(--accent); }
    .assist-status.err { color: var(--danger); }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 14px;
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; padding: 12px; }
      .task-board { position: static; }
      .row { grid-template-columns: 1fr; }
      .task-grid, .mail-layout, .edit-card-grid, .modal-fields, .config-grid, .weekly-section-grid, .weekly-period-grid { grid-template-columns: 1fr; }
      .guide-grid, .field-grid, .field-grid.three { grid-template-columns: 1fr; }
      .weekly-section-card { min-height: auto; }
      .weekly-rows { max-height: none; }
      .modal-fields .wide { grid-column: auto; }
      header { padding: 18px; }
    }
    .agent-float { position: fixed; bottom: 24px; right: 24px; z-index: 1000; }
    .agent-toggle {
      width: 112px; height: 112px; border-radius: 0;
      background: transparent;
      color: #fff; font-size: 24px; border: 0;
      box-shadow: none;
      cursor: pointer; transition: transform .2s;
      display: grid; place-items: center; padding: 0;
      touch-action: none;
    }
    .agent-avatar {
      width: 96px; height: 96px; object-fit: contain;
      filter: drop-shadow(0 4px 10px rgba(15, 23, 42, .22));
      pointer-events: none;
    }
    .agent-header .agent-avatar { width: 30px; height: 30px; margin-right: 8px; }
    .agent-toggle:hover { transform: scale(1.08); }
    .agent-window {
      position: absolute; bottom: 70px; right: 0;
      width: 420px; max-height: 640px;
      background: #fff; border-radius: 14px;
      box-shadow: 0 20px 50px rgba(26,34,47,.18);
      display: flex; flex-direction: column;
      overflow: hidden; border: 1px solid var(--line);
      resize: both;
    }
    .agent-window.hidden { display: none; }
    .agent-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 14px 16px; background: #123c3b; color: #fff;
      cursor: move; user-select: none;
    }
    .agent-header span { font-weight: 720; font-size: 15px; }
    .agent-close { background: rgba(255,255,255,.18); color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 13px; }
    .agent-body { display: flex; flex-direction: column; flex: 1; min-height: 0; }
    .agent-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
    .agent-msg { max-width: 88%; padding: 10px 12px; border-radius: 12px; font-size: 13.5px; line-height: 1.55; }
    .agent-msg.user { align-self: flex-end; background: #17736a; color: #fff; border-bottom-right-radius: 4px; }
    .agent-msg.assistant { align-self: flex-start; background: #f1f5f9; color: var(--ink); border-bottom-left-radius: 4px; }
    .agent-actions { display: flex; gap: 8px; padding: 0 14px 10px; }
    .agent-action { flex: 1; padding: 8px; font-size: 13px; background: #eef8f6; color: var(--accent); border: 1px solid #b9ded8; border-radius: 8px; cursor: pointer; font-weight: 680; }
    .agent-action:hover { background: #dcefea; }
    .agent-input-wrap { display: flex; gap: 8px; padding: 10px 14px 14px; border-top: 1px solid var(--line); align-items: flex-end; }
    .agent-input-wrap textarea { flex: 1; border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; font-size: 14px; min-height: 56px; max-height: 140px; resize: vertical; line-height: 1.5; }
    .agent-input-wrap button { padding: 9px 16px; background: var(--accent); color: #fff; border-radius: 8px; font-size: 14px; border: 0; font-weight: 680; height: fit-content; }

    /* ===== 工作日记 ===== */
    .diary-tabs {
      display: flex; gap: 6px; margin: 0 0 20px;
      padding: 4px; background: var(--surface);
      border-radius: var(--radius); width: fit-content;
      border: 1px solid var(--line);
    }
    .diary-tab {
      padding: 8px 18px; border-radius: var(--radius-sm);
      font-size: 13px; font-weight: 700;
      background: transparent; color: var(--muted); border: 0;
      cursor: pointer; transition: all .15s ease;
      display: inline-flex; align-items: center; gap: 7px;
    }
    .diary-tab.active {
      background: var(--accent-gradient); color: #fff;
      box-shadow: 0 4px 12px rgba(59, 130, 246, .25);
    }
    .diary-tab:hover:not(.active) { color: var(--ink); background: var(--elevated); }
    .diary-view.hidden { display: none; }
    .diary-card {
      background: var(--panel); border: 1px solid var(--line);
      border-radius: var(--radius); padding: 24px;
    }
    .diary-card textarea { min-height: 120px; }
    .diary-field { cursor: pointer; background: var(--surface); transition: border-color .2s; }
    .diary-field:hover { border-color: var(--accent); }
    .diary-two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 4px;
    }
    .diary-list-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 14px;
    }
    .diary-list { display: grid; gap: 10px; }
    .diary-item {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      gap: 14px; align-items: center;
      padding: 14px 16px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all .15s ease;
    }
    .diary-item:hover {
      border-color: var(--accent);
      background: rgba(59, 130, 246, .06);
    }
    .diary-item-date {
      font-weight: 800; font-size: 13px;
      color: var(--accent); white-space: nowrap;
      background: rgba(59, 130, 246, .1);
      padding: 4px 10px; border-radius: 6px;
    }
    .diary-item-preview {
      color: var(--muted); font-size: 13px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .diary-empty {
      text-align: center; padding: 40px 20px;
      color: var(--muted); font-size: 14px;
    }
    .diary-detail-body { display: grid; gap: 16px; }
    .diary-detail-section {
      background: var(--surface); border: 1px solid var(--line);
      border-radius: var(--radius-sm); padding: 14px;
    }
    .diary-detail-label {
      font-size: 12px; font-weight: 700; color: var(--muted);
      text-transform: uppercase; letter-spacing: .06em;
      margin-bottom: 8px;
    }
    .diary-detail-content {
      font-size: 14px; line-height: 1.65; color: var(--ink);
      white-space: pre-wrap;
    }
    .diary-summarize-box {
      background: rgba(59, 130, 246, .08);
      border: 1px dashed rgba(59, 130, 246, .35);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
      margin-bottom: 16px;
      display: flex; align-items: center; gap: 14px;
      flex-wrap: wrap;
    }
    .diary-summarize-box label { margin: 0; font-size: 12px; }
    .diary-summarize-box input {
      width: auto; min-width: 140px; padding: 8px 12px; font-size: 13px;
    }
    .diary-summarize-box button { padding: 8px 16px; font-size: 13px; }

    @media (max-width: 520px) {
      .agent-window { width: calc(100vw - 32px); right: -8px; }
    }

    /* ===== Modern AI Office Design System Overrides ===== */
    body {
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    header {
      background: rgba(17, 24, 39, .85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 14px 24px;
    }
    .header-row { display: flex; justify-content: space-between; align-items: center; gap: 20px; }
    .brand { display: flex; align-items: center; gap: 12px; font-size: 18px; font-weight: 700; letter-spacing: .3px; }
    .brand-icon {
      width: 36px; height: 36px; border-radius: 10px;
      background: var(--accent-gradient); display: grid; place-items: center; color: #fff; font-size: 18px;
      box-shadow: var(--glow);
    }
    .icon, .nav-icon, .card-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .icon svg, .nav-icon svg, .card-icon svg {
      width: 1.15em;
      height: 1.15em;
      stroke-width: 2;
    }
    .global-search {
      flex: 1; max-width: 420px; position: relative;
    }
    .global-search input {
      width: 100%; background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
      padding: 10px 16px 10px 38px; color: var(--ink); font-size: 14px;
      transition: all .2s;
    }
    .global-search input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,.2); }
    .global-search .search-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: var(--muted); }
    .global-search .search-icon svg { width: 16px; height: 16px; }
    .userbar { display: none; align-items: center; gap: 12px; }
    .user-avatar {
      width: 32px; height: 32px; border-radius: 50%;
      object-fit: cover; background: #eaf1fb; border: 1px solid var(--line);
    }
    .userbar button {
      background: var(--elevated); color: var(--muted); border: 1px solid var(--line);
      padding: 8px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600;
      transition: all .2s;
    }
    .userbar button:hover { background: var(--panel); color: var(--ink); border-color: var(--accent); }

    main {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 0;
      padding: 0;
      max-width: none;
      margin: 0;
      align-items: start;
      min-height: calc(100vh - 70px);
    }
    .sidebar {
      background: var(--surface);
      border-right: 1px solid var(--line);
      padding: 20px 14px;
      position: sticky;
      top: 70px;
      height: calc(100vh - 70px);
      overflow-y: auto;
    }
    .sidebar-title {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .08em; color: var(--muted); margin: 0 10px 14px;
    }
    .nav-group { margin-bottom: 20px; }
    .nav-group + .nav-group { border-top: 1px solid var(--line); padding-top: 20px; }
    .task-grid { display: flex; flex-direction: column; gap: 6px; }
    .task-card {
      width: 100%; text-align: left; border: 1px solid transparent;
      border-radius: var(--radius-sm); padding: 10px 12px;
      background: transparent; color: var(--muted); box-shadow: none;
      cursor: pointer; transition: all .15s; font-size: 13px;
      display: flex; align-items: center; gap: 10px;
    }
    .task-card:hover {
      background: var(--panel); color: var(--ink); border-color: var(--line);
    }
    .task-card.active {
      background: rgba(59, 130, 246, .12); color: var(--accent); border-color: rgba(59, 130, 246, .35);
      box-shadow: inset 0 0 0 1px rgba(59, 130, 246, .15);
    }
    .task-card .task-name { font-weight: 700; font-size: 13.5px; margin: 0; }
    .task-card .task-desc { display: none; }
    .task-card .nav-icon { width: 20px; height: 20px; display: grid; place-items: center; font-size: 15px; flex-shrink: 0; }

    .composer { padding: 28px; background: var(--bg); }
    .page-header { margin-bottom: 24px; }
    .page-header h2 { font-size: 22px; font-weight: 800; margin: 0 0 6px; letter-spacing: -.3px; }
    .page-header p { color: var(--muted); font-size: 14px; margin: 0; }

    .sub-tabs {
      display: flex; gap: 6px; margin: 0 0 24px;
      padding: 4px; background: var(--surface);
      border-radius: var(--radius); width: fit-content;
      border: 1px solid var(--line);
    }
    .sub-tabs.hidden { display: none; }
    .sub-tab {
      padding: 8px 18px; border-radius: var(--radius-sm);
      font-size: 13px; font-weight: 700;
      background: transparent; color: var(--muted); border: 0;
      cursor: pointer; transition: all .15s ease;
      display: inline-flex; align-items: center; gap: 7px;
    }
    .sub-tab.active {
      background: var(--accent-gradient); color: #fff;
      box-shadow: 0 4px 12px rgba(59, 130, 246, .25);
    }
    .sub-tab:hover:not(.active) { color: var(--ink); background: var(--elevated); }

    section, .task-panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .task-panel { overflow: hidden; }

    h2 { margin: 0 0 14px; font-size: 17px; color: var(--ink); }
    label { display: block; margin: 12px 0 6px; font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
    input, select, textarea {
      width: 100%; background: var(--surface); border: 1px solid var(--line);
      border-radius: var(--radius-sm); padding: 10px 12px;
      font: inherit; color: var(--ink); transition: all .2s;
    }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,.12); }
    textarea { min-height: 120px; resize: vertical; line-height: 1.6; background: var(--surface); }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 18px; }
    #generateToolbar.hidden { display: none !important; }
    button {
      border: 0; border-radius: var(--radius-sm); padding: 10px 18px;
      font-weight: 700; cursor: pointer; background: var(--accent-gradient);
      color: #fff; font-size: 13px; transition: all .2s; letter-spacing: .2px;
      box-shadow: 0 4px 14px rgba(59, 130, 246, .25);
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(59, 130, 246, .35); }
    button:active { transform: translateY(0); }
    button.secondary { background: var(--elevated); color: var(--ink); box-shadow: none; border: 1px solid var(--line); }
    button.secondary:hover { background: var(--panel); border-color: var(--accent); }
    button.warn { background: linear-gradient(135deg, #f59e0b, #ef4444); }
    button.action-button { padding: 10px 16px; font-size: 13px; background: var(--accent-gradient); color: #fff; border: 0; white-space: nowrap; }
    .download-link {
      display: inline-flex; align-items: center; min-height: 36px;
      padding: 8px 14px; border-radius: var(--radius-sm);
      background: rgba(59, 130, 246, .1); color: var(--accent);
      border: 1px solid rgba(59, 130, 246, .25); text-decoration: none;
      font-weight: 700; font-size: 13px; transition: all .2s;
    }
    .download-link:hover { background: rgba(59, 130, 246, .18); }

    .report {
      border: 1px solid var(--line); border-radius: var(--radius-sm);
      padding: 14px; margin-bottom: 10px; cursor: pointer;
      background: var(--surface); transition: all .15s;
    }
    .report:hover { border-color: var(--accent); background: rgba(59, 130, 246, .06); }
    .report.active { border-color: var(--accent); background: rgba(59, 130, 246, .1); box-shadow: 0 0 0 1px rgba(59, 130, 246, .15); }

    .weekly-period-card, .weekly-section-card {
      background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
      padding: 18px; margin-bottom: 16px;
    }
    .weekly-period-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
    .weekly-period-title { font-size: 15px; font-weight: 800; color: var(--ink); }
    .weekly-section-title { font-size: 14px; font-weight: 700; color: var(--ink); margin-bottom: 4px; }
    .weekly-section-meta { font-size: 12px; color: var(--muted); }
    .work-block {
      background: var(--elevated); border: 1px solid var(--line);
      border-radius: var(--radius-sm); padding: 14px; margin-bottom: 10px;
      cursor: pointer; transition: all .15s;
    }
    .work-block:hover { border-color: var(--accent); }

    .trip-store input, .trip-store textarea {
      background: var(--surface); margin-bottom: 10px;
    }

    .auth-panel {
      max-width: 420px; margin: 80px auto;
      background: var(--panel); border: 1px solid var(--line);
      border-radius: var(--radius); padding: 36px;
      box-shadow: var(--shadow);
    }
    .auth-panel h2 { font-size: 20px; margin-bottom: 20px; text-align: center; }

    /* Dashboard */
    .dashboard-grid { display: grid; gap: 24px; }
    .welcome-card {
      background: var(--panel); border: 1px solid var(--line);
      border-radius: var(--radius); padding: 28px;
      position: relative; overflow: hidden;
    }
    .welcome-card::before {
      content: ""; position: absolute; top: -40%; right: -10%;
      width: 300px; height: 300px; border-radius: 50%;
      background: radial-gradient(circle, rgba(59,130,246,.15), transparent 70%);
      pointer-events: none;
    }
    .welcome-card h1 { font-size: 24px; font-weight: 800; margin: 0 0 8px; position: relative; z-index: 1; }
    .welcome-card p { color: var(--muted); margin: 0 0 20px; position: relative; z-index: 1; }
    .quick-actions { display: flex; gap: 10px; flex-wrap: wrap; position: relative; z-index: 1; }
    .quick-actions button { padding: 10px 20px; font-size: 13px; }

    .shortcut-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .shortcut-card {
      background: var(--panel); border: 1px solid var(--line);
      border-radius: var(--radius); padding: 20px; cursor: pointer;
      transition: all .2s; position: relative; overflow: hidden;
      display: flex; align-items: center; gap: 16px;
    }
    .shortcut-card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
      box-shadow: 0 8px 24px rgba(2, 8, 20, .5);
    }
    .shortcut-card .icon {
      width: 52px; height: 52px; border-radius: 14px;
      background: var(--accent-gradient); display: grid; place-items: center;
      color: #fff; font-size: 22px; flex-shrink: 0;
      box-shadow: var(--glow);
    }
    .shortcut-card .title { font-weight: 800; font-size: 16px; margin-bottom: 6px; }
    .shortcut-card .desc { font-size: 13px; color: var(--muted); line-height: 1.55; }
    @media (max-width: 1180px) {
      .shortcut-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    .recent-docs { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 20px; }
    .recent-docs h3 { font-size: 14px; font-weight: 800; margin: 0 0 14px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
    .doc-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--line); }
    .doc-item:last-child { border-bottom: 0; }
    .doc-name { font-size: 13px; font-weight: 600; }
    .doc-meta { font-size: 11px; color: var(--muted); }
    .ai-command {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      position: relative;
      z-index: 1;
      max-width: 760px;
    }
    .ai-command input {
      min-height: 46px;
      border-radius: 999px;
      padding: 12px 18px;
      background: #fff;
      color: var(--ink);
      border-color: #cbd8e8;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .8);
    }
    .ai-command input:focus {
      background: #fff;
      border-color: var(--accent);
      box-shadow: 0 0 0 4px rgba(37, 99, 235, .12);
    }
    .ai-command button { border-radius: 999px; }
    .module-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    .recommend-list { display: grid; gap: 10px; }
    .recommend-item {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      padding: 12px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
    }
    .recommend-item .card-icon { color: var(--accent); margin-top: 2px; }
    .recommend-item strong { display: block; font-size: 13px; margin-bottom: 2px; }
    .recommend-item span { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .forum-layout {
      display: grid;
      grid-template-columns: minmax(320px, .9fr) minmax(520px, 1.5fr);
      gap: 16px;
    }
    .forum-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 16px;
      box-shadow: var(--shadow);
    }
    .forum-card h3 { margin: 0 0 12px; font-size: 15px; }
    .forum-create-panel.hidden { display: none; }
    .forum-topic-list { display: grid; gap: 10px; margin-top: 12px; max-height: 660px; overflow: auto; }
    .forum-topic-item {
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 12px;
      background: #f8fbff;
      cursor: pointer;
      transition: all .16s ease;
    }
    .forum-topic-item:hover,
    .forum-topic-item.active {
      border-color: #93c5fd;
      background: #eff6ff;
    }
    .forum-topic-title { font-weight: 760; font-size: 14px; line-height: 1.45; }
    .forum-topic-meta { margin-top: 6px; color: var(--muted); font-size: 12px; }
    .forum-topic-stats {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .forum-stat {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: 999px;
      background: #eef6ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 680;
    }
    .forum-topic-body,
    .forum-comment-body {
      white-space: pre-wrap;
      color: var(--ink);
      line-height: 1.65;
      font-size: 14px;
    }
    .forum-comments { display: grid; gap: 10px; margin-top: 12px; }
    .forum-comment {
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 12px;
      background: #f8fafc;
    }
    .forum-comment.reply {
      margin-left: 28px;
      border-left: 3px solid #93c5fd;
    }
    .forum-comment-meta { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .forum-comment-actions { margin-top: 8px; display: flex; gap: 8px; }
    .forum-pagination {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
    }
    .forum-empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: var(--radius-sm);
      padding: 18px;
      text-align: center;
      background: #fbfdff;
    }
    .news-layout {
      display: grid;
      grid-template-columns: minmax(320px, .85fr) minmax(480px, 1.4fr);
      gap: 16px;
    }
    .news-layout.reader { grid-template-columns: 1fr; }
    .news-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 16px;
      box-shadow: var(--shadow);
    }
    .news-card h3 { margin: 0 0 12px; font-size: 15px; }
    .news-source-row {
      display: grid;
      grid-template-columns: minmax(100px, .45fr) minmax(160px, 1fr) auto;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
    }
    .news-issue-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .news-issue-title { font-size: 20px; font-weight: 820; color: var(--ink); }
    .news-issue-meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .news-summary {
      white-space: pre-wrap;
      line-height: 1.65;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: #f8fbff;
      margin-bottom: 12px;
    }
    .news-list { display: grid; gap: 10px; }
    .news-item {
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 12px;
      background: #fff;
    }
    .news-item-title { font-weight: 760; margin-bottom: 6px; }
    .news-item-meta { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .news-item p { margin: 6px 0; line-height: 1.6; }
    .news-keywords { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
    .news-keyword {
      padding: 4px 8px;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 680;
    }
    @media (max-width: 1100px) {
      .forum-layout { grid-template-columns: 1fr; }
      .news-layout { grid-template-columns: 1fr; }
    }

    /* Agent */
    .agent-float { position: fixed; bottom: 28px; right: 28px; z-index: 3000; touch-action: none; }
    .agent-toggle {
      width: 112px; height: 112px; border-radius: 0;
      background: transparent; color: #fff; font-size: 24px;
      border: 0; box-shadow: none;
      cursor: grab; transition: all .2s;
      display: grid; place-items: center; padding: 0;
      touch-action: none;
    }
    .agent-toggle:hover { transform: scale(1.04); box-shadow: none; }
    .agent-toggle:active { cursor: grabbing; }
    .agent-window {
      position: absolute; bottom: 72px; right: 0;
      width: 420px; max-height: 640px; min-height: 400px;
      background: var(--panel); border-radius: var(--radius);
      box-shadow: 0 24px 60px rgba(2, 8, 20, .55);
      display: flex; flex-direction: column; overflow: hidden;
      border: 1px solid var(--line); resize: both;
    }
    .agent-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 14px 18px; background: var(--accent-gradient); color: #fff;
      cursor: move; user-select: none;
    }
    .agent-close { background: rgba(255,255,255,.2); color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 13px; border: 0; cursor: pointer; }
    .agent-close:hover { background: rgba(255,255,255,.3); }
    .agent-msg { max-width: 88%; padding: 10px 14px; border-radius: 14px; font-size: 13.5px; line-height: 1.55; }
    .agent-msg.user { align-self: flex-end; background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
    .agent-msg.assistant { align-self: flex-start; background: var(--surface); color: var(--ink); border-bottom-left-radius: 4px; border: 1px solid var(--line); }
    .agent-action { flex: 1; padding: 8px; font-size: 12px; background: var(--surface); color: var(--accent); border: 1px solid var(--line); border-radius: var(--radius-sm); cursor: pointer; font-weight: 700; }
    .agent-action:hover { background: rgba(59, 130, 246, .1); border-color: var(--accent); }
    .agent-input-wrap textarea { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px 12px; font-size: 14px; min-height: 56px; max-height: 140px; resize: vertical; line-height: 1.5; flex: 1; color: var(--ink); }
    .agent-input-wrap textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(59,130,246,.12); }
    .agent-input-wrap button { padding: 10px 18px; font-size: 13px; }

    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .sidebar { display: none; }
      .module-grid { grid-template-columns: 1fr; }
      .ai-command { grid-template-columns: 1fr; }
    }

    /* ===== Comfortable Light AI Office Theme ===== */
    :root {
      color-scheme: light;
      --bg: #f4f7fb;
      --surface: #f8fafc;
      --panel: #ffffff;
      --elevated: #eef4ff;
      --ink: #172033;
      --muted: #64748b;
      --line: #dbe5f1;
      --accent: #2563eb;
      --accent-2: #0ea5e9;
      --accent-gradient: linear-gradient(135deg, #2563eb, #0ea5e9);
      --danger: #dc2626;
      --success: #059669;
      --warning: #d97706;
      --shadow: 0 12px 34px rgba(15, 23, 42, .08);
      --glow: 0 12px 28px rgba(37, 99, 235, .18);
    }
    body {
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, .08), transparent 30%),
        linear-gradient(180deg, #f7fbff 0%, #eef4fb 100%);
      color: var(--ink);
    }
    header {
      background: rgba(255, 255, 255, .92);
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      box-shadow: 0 8px 24px rgba(15, 23, 42, .05);
    }
    .global-search input,
    input,
    select,
    textarea,
    .agent-input-wrap textarea {
      background: #ffffff;
      color: var(--ink);
      border-color: #cbd8e8;
    }
    input::placeholder,
    textarea::placeholder { color: #94a3b8; }
    input:focus,
    select:focus,
    textarea:focus,
    .agent-input-wrap textarea:focus {
      background: #fff;
      border-color: var(--accent);
      box-shadow: 0 0 0 4px rgba(37, 99, 235, .12);
    }
    .sidebar {
      background: rgba(255, 255, 255, .82);
      backdrop-filter: blur(14px);
      border-right: 1px solid var(--line);
    }
    .task-card {
      color: #526174;
    }
    .task-card:hover {
      background: #eef5ff;
      color: var(--ink);
      border-color: #bfdbfe;
    }
    .task-card.active {
      background: linear-gradient(135deg, rgba(37, 99, 235, .12), rgba(14, 165, 233, .1));
      color: #1d4ed8;
      border-color: #93c5fd;
      box-shadow: inset 3px 0 0 #2563eb;
    }
    .composer { background: transparent; }
    section,
    .task-panel,
    .welcome-card,
    .shortcut-card,
    .insight-card,
    .recent-docs,
    .weekly-period-card,
    .weekly-section-card,
    .guide,
    .side,
    .auth-panel,
    .modal-box,
    .agent-window {
      background: rgba(255, 255, 255, .96);
      border-color: var(--line);
      color: var(--ink);
      box-shadow: var(--shadow);
    }
    .sub-tabs {
      background: #eaf1fb;
      border-color: #d4e2f3;
    }
    .sub-tab { color: #5f7189; }
    .sub-tab:hover:not(.active) {
      background: #f7fbff;
      color: var(--ink);
    }
    .work-block,
    .edit-card,
    .report,
    .history-item,
    .upload-item,
    .user-item,
    .recommend-item,
    .rich-preview,
    .preview {
      background: #ffffff;
      color: var(--ink);
      border-color: var(--line);
    }
    .weekly-section-head {
      background: #f7fbff;
      border-bottom-color: var(--line);
    }
    .work-title,
    .edit-card-title,
    .weekly-period-title,
    .weekly-section-title,
    .doc-name,
    .history-name { color: var(--ink); }
    .work-summary,
    .edit-card-preview,
    .history-meta,
    .doc-meta,
    .insight-desc,
    .shortcut-card .desc,
    .recommend-item span,
    .page-header p,
    label,
    .sidebar-title { color: var(--muted); }
    button.secondary {
      background: #ffffff;
      color: #1e3a8a;
      border: 1px solid #bfdbfe;
    }
    button.secondary:hover {
      background: #eff6ff;
      border-color: #60a5fa;
    }
    .agent-header {
      background: var(--accent-gradient);
      color: #fff;
    }
    .agent-msg.assistant {
      background: #f8fafc;
      color: var(--ink);
      border: 1px solid var(--line);
    }
    .agent-action {
      background: #eff6ff;
      color: #1d4ed8;
      border-color: #bfdbfe;
    }
    .mail-assistant-grid {
      display: grid;
      grid-template-columns: minmax(340px, .9fr) minmax(480px, 1.4fr);
      gap: 16px;
      margin-bottom: 16px;
    }
    .mailbox-card,
    .mail-detail-card,
    .mail-compose-card {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      overflow: hidden;
      box-shadow: var(--shadow);
    }
    .mailbox-list {
      max-height: 520px;
      overflow: auto;
      padding: 12px;
      display: grid;
      gap: 10px;
    }
    .mailbox-item {
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
      background: #f8fbff;
      cursor: pointer;
      transition: all .16s ease;
    }
    .mailbox-item:hover,
    .mailbox-item.active {
      background: #eff6ff;
      border-color: #93c5fd;
      transform: translateY(-1px);
    }
    .mailbox-subject {
      color: var(--ink);
      font-weight: 760;
      font-size: 13.5px;
      margin-bottom: 4px;
    }
    .mailbox-meta,
    .mailbox-preview {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .mail-section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      background: #f7fbff;
      border-bottom: 1px solid var(--line);
    }
    .mail-section-title {
      color: var(--ink);
      font-size: 15px;
      font-weight: 800;
      margin-bottom: 3px;
    }
    .mail-section-meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .mail-detail {
      min-height: 520px;
      padding: 0;
      background: #f8fbff;
      color: var(--ink);
      line-height: 1.65;
    }
    .mail-detail-head {
      border-bottom: 1px solid var(--line);
      padding: 16px 18px;
      background: #fff;
    }
    .mail-detail-body {
      margin: 16px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: #fff;
      min-height: 260px;
      overflow: auto;
      white-space: normal;
    }
    .mail-detail-body.plain {
      white-space: pre-wrap;
    }
    .mail-attachment-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .mail-attachment {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border: 1px solid #bfdbfe;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 700;
    }
    .mail-compose-card {
      padding-bottom: 16px;
    }
    .mail-compose-layout {
      display: grid;
      grid-template-columns: minmax(420px, 1fr) minmax(320px, .85fr);
      gap: 16px;
      padding: 16px;
      align-items: start;
    }
    .mail-compose-form,
    .mail-compose-preview {
      display: grid;
      gap: 12px;
    }
    .mail-compose-form textarea {
      min-height: 220px;
    }
    .mail-compose-preview .rich-preview {
      min-height: 300px;
      max-height: 460px;
      overflow: auto;
      background: #fff;
    }
    .mail-file-list {
      display: grid;
      gap: 8px;
    }
    .mail-file-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: #f8fbff;
      font-size: 12px;
      color: var(--muted);
    }
    .profile-grid { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 16px; align-items: start; }
    .profile-avatar-large {
      width: 86px; height: 86px; border-radius: 50%; object-fit: cover;
      background: #eaf1fb; border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }
    .profile-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    @media (max-width: 1100px) {
      .mail-assistant-grid { grid-template-columns: 1fr; }
      .mail-detail { min-height: 280px; }
      .mail-compose-layout { grid-template-columns: 1fr; }
    }

  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div class="brand">
        <div class="brand-icon"><span class="icon" data-icon="sparkles"></span></div>
        <div>智能办公助手 / AI 办公平台</div>
      </div>
      <div class="global-search">
        <span class="search-icon icon" data-icon="search"></span>
        <input type="text" placeholder="搜索文档、邮件、知识..." />
      </div>
      <div class="userbar" id="userbar">
        <img class="user-avatar" id="userAvatar" src="/assets/ai-assistant-avatar.png" alt="" />
        <span id="userInfo"></span>
        <button type="button" id="profileButton" class="mini">个人资料</button>
        <button type="button" id="changePassButton" class="mini">修改密码</button>
        <button type="button" id="logoutButton">退出</button>
      </div>
    </div>
  </header>
  <section class="auth-panel" id="authPanel">
    <h2>登录</h2>
    <label>用户名</label>
    <input id="loginUser" />
    <label>密码</label>
    <input id="loginPass" type="password" />
    <div class="toolbar">
      <button id="loginButton" type="button">登录</button>
    </div>
    <div id="loginStatus" class="status"></div>
  </section>
  <main id="appMain" class="hidden">
    <aside class="sidebar">
      <div class="nav-group">
        <div class="sidebar-title">工作台</div>
        <div class="task-grid">
          <button class="task-card active" type="button" data-task="dashboard">
            <span class="nav-icon" data-icon="layout-dashboard"></span>
            <span class="task-name">首页</span>
          </button>
        </div>
      </div>
      <div class="nav-group">
        <div class="sidebar-title">智能助手</div>
        <div class="task-grid">
          <button class="task-card" type="button" data-task="weekly">
            <span class="nav-icon" data-icon="file-spreadsheet"></span>
            <span class="task-name">周报助手</span>
          </button>
          <button class="task-card" type="button" data-task="trip">
            <span class="nav-icon" data-icon="briefcase-business"></span>
            <span class="task-name">出差报告助手</span>
          </button>
          <button class="task-card" type="button" data-task="diary">
            <span class="nav-icon" data-icon="book-open"></span>
            <span class="task-name">工作日记</span>
          </button>
          <button class="task-card" type="button" data-task="forum">
            <span class="nav-icon" data-icon="messages-square"></span>
            <span class="task-name">金点子论坛</span>
          </button>
          <button class="task-card" type="button" data-task="news">
            <span class="nav-icon" data-icon="newspaper"></span>
            <span class="task-name">每日资讯</span>
          </button>
          <button class="task-card" type="button" data-task="mailassistant">
            <span class="nav-icon" data-icon="inbox"></span>
            <span class="task-name">邮件助手</span>
          </button>
        </div>
      </div>
      <div class="nav-group">
        <div class="sidebar-title">系统</div>
        <div class="task-grid">
          <button class="task-card" type="button" data-task="mailconfig">
            <span class="nav-icon" data-icon="mail-check"></span>
            <span class="task-name">邮件配置</span>
          </button>
          <button class="task-card admin-only hidden" type="button" data-task="config">
            <span class="nav-icon" data-icon="settings"></span>
            <span class="task-name">系统配置</span>
          </button>
        </div>
      </div>
    </aside>
    <section class="composer">
      <div class="task-panel" id="dashboardPanel">
        <div class="dashboard-grid">
          <div class="welcome-card">
            <h1>欢迎回来，<span id="dashUserName"></span></h1>
            <p>围绕日常办公闭环工作：记录工作、生成报告、处理邮件、共创金点子、查看每日轨交资讯。</p>
            <div class="ai-command">
              <input id="dashboardAsk" type="text" placeholder="输入问题，例如：根据本周日记生成周报、整理出差报告、提炼邮件重点..." />
              <button type="button" id="dashboardAskButton"><span class="icon" data-icon="send"></span> 提问助手</button>
            </div>
          </div>
          <div class="shortcut-grid">
            <div class="shortcut-card" onclick="navigateTo('weekly','edit')">
              <div class="icon" data-icon="file-spreadsheet"></div>
              <div>
                <div class="title">填写周报</div>
                <div class="desc">按模板快速生成本周工作总结、重点跟进和下周计划</div>
              </div>
            </div>
            <div class="shortcut-card" onclick="navigateTo('diary')">
              <div class="icon" data-icon="book-open"></div>
              <div>
                <div class="title">记录工作日记</div>
                <div class="desc">沉淀每日工作、明日计划和想法，周报可直接智能总结</div>
              </div>
            </div>
            <div class="shortcut-card" onclick="navigateTo('trip','edit')">
              <div class="icon" data-icon="briefcase-business"></div>
              <div>
                <div class="title">填写出差报告</div>
                <div class="desc">录入出差地点、时间、目的、行程和总结内容</div>
              </div>
            </div>
            <div class="shortcut-card" onclick="navigateTo('forum')">
              <div class="icon" data-icon="messages-square"></div>
              <div>
                <div class="title">金点子论坛</div>
                <div class="desc">浏览历史话题、查看热度点赞评论，围绕话题分级讨论</div>
              </div>
            </div>
            <div class="shortcut-card" onclick="navigateTo('news')">
              <div class="icon" data-icon="newspaper"></div>
              <div>
                <div class="title">每日资讯</div>
                <div class="desc">查看轨道交通关键资讯，配置和生成由超级管理员维护</div>
              </div>
            </div>
            <div class="shortcut-card" onclick="navigateTo('mailassistant')">
              <div class="icon" data-icon="inbox"></div>
              <div>
                <div class="title">邮件助手</div>
                <div class="desc">读取收件箱、查看邮件详情、普通发信；收件箱已支持缓存加速</div>
              </div>
            </div>
          </div>
          <div class="module-grid">
            <div class="recent-docs">
              <h3>最近文档</h3>
              <div id="recentDocsList"><div class="doc-item"><span class="doc-name">暂无最近文档</span></div></div>
            </div>
            <div class="recent-docs">
              <h3>当前能力</h3>
              <div class="recommend-list">
                <div class="recommend-item">
                  <span class="card-icon" data-icon="calendar-check"></span>
                  <div><strong>报告只在专属模块生成</strong><span>“按标准模板生成文件”仅在周报助手和出差报告助手中出现。</span></div>
                </div>
                <div class="recommend-item">
                  <span class="card-icon" data-icon="messages-square"></span>
                  <div><strong>论坛以浏览评论为主</strong><span>发起话题默认收起，历史话题展示热度、点赞、评论和浏览。</span></div>
                </div>
                <div class="recommend-item">
                  <span class="card-icon" data-icon="newspaper"></span>
                  <div><strong>资讯配置受权限保护</strong><span>普通用户只看每日资讯，只有超级管理员能配置来源和立即生成。</span></div>
                </div>
                <div class="recommend-item">
                  <span class="card-icon" data-icon="inbox"></span>
                  <div><strong>邮件读取已缓存</strong><span>收件箱列表优先读缓存，点击刷新才强制重新拉取最新邮件。</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="page-header hidden" id="pageHeader">
        <h2 id="taskTitle"></h2>
        <p id="taskDesc"></p>
      </div>
      <div class="sub-tabs hidden" id="subTabs">
        <button class="sub-tab active" type="button" data-sub="edit"><span class="icon" data-icon="clipboard-pen"></span> 填写报告</button>
        <button class="sub-tab" type="button" data-sub="mail"><span class="icon" data-icon="mail"></span> 发送邮件</button>
        <button class="sub-tab" type="button" data-sub="history"><span class="icon" data-icon="folder-clock"></span> 历史管理</button>
      </div>
      <input id="kind" type="hidden" value="weekly" />
      <div class="task-panel hidden" id="diaryPanel">
        <div class="diary-tabs">
          <button class="diary-tab active" type="button" data-diarytab="write"><span class="icon" data-icon="pen-line"></span> 记录日记</button>
          <button class="diary-tab" type="button" data-diarytab="browse"><span class="icon" data-icon="library"></span> 浏览日记</button>
        </div>
        <div class="diary-view" id="diaryWriteView">
          <div class="diary-card">
            <div class="row">
              <div>
                <label>日期</label>
                <input id="diaryDate" type="date" />
              </div>
              <div style="display:flex;align-items:flex-end;">
                <button type="button" class="secondary" id="diaryLoadToday">载入今天</button>
              </div>
            </div>
            <div class="diary-two-col">
              <div>
                <label>今日工作内容</label>
                <textarea id="diaryTodayWork" class="diary-field" readonly placeholder="记录今天完成的主要工作、遇到的问题、解决方案..."></textarea>
              </div>
              <div>
                <label>明日工作计划</label>
                <textarea id="diaryTomorrowPlan" class="diary-field" readonly placeholder="计划明天要做的事项..."></textarea>
              </div>
            </div>
            <label>思路与想法</label>
            <textarea id="diaryThoughts" class="diary-field" readonly placeholder="灵光一闪的想法、改进建议、学习心得..."></textarea>
            <div class="toolbar">
              <button type="button" id="diarySaveButton">保存日记</button>
              <button type="button" class="secondary" id="diaryClearButton">清空</button>
              <button type="button" id="diaryAgentButton"><span class="icon" data-icon="sparkles"></span> AI 智能记录</button>
              <span id="diaryStatus" class="status"></span>
            </div>
          </div>
        </div>
        <div class="diary-view hidden" id="diaryBrowseView">
          <div class="diary-card">
            <div class="diary-list-header">
              <h3 style="margin:0;font-size:15px;">日记列表</h3>
              <button type="button" class="mini" id="diaryRefreshList">刷新</button>
            </div>
            <div id="diaryList" class="diary-list"><div class="diary-empty">暂无日记，去记录第一篇吧～</div></div>
          </div>
        </div>
        <div class="modal hidden" id="diaryDetailModal">
          <div class="modal-box" style="width:min(720px,96vw)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
              <h3 style="margin:0" id="diaryDetailDate">日记详情</h3>
              <button type="button" class="secondary" onclick="el('diaryDetailModal').classList.add('hidden')">关闭</button>
            </div>
            <div class="diary-detail-body">
              <div class="diary-detail-section">
                <div class="diary-detail-label">今日工作内容</div>
                <div class="diary-detail-content" id="diaryDetailToday"></div>
              </div>
              <div class="diary-detail-section">
                <div class="diary-detail-label">明日工作计划</div>
                <div class="diary-detail-content" id="diaryDetailTomorrow"></div>
              </div>
              <div class="diary-detail-section">
                <div class="diary-detail-label">思路与想法</div>
                <div class="diary-detail-content" id="diaryDetailThoughts"></div>
              </div>
            </div>
            <div class="toolbar" style="justify-content:flex-end;margin-top:16px;">
              <button type="button" class="secondary" id="diaryDetailEdit">编辑</button>
              <button type="button" class="danger" id="diaryDetailDelete">删除</button>
            </div>
          </div>
        </div>
      </div>
      <div class="task-panel hidden" id="forumPanel">
        <div class="forum-layout">
          <div class="forum-card">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;">
              <h3 style="margin:0;">全部历史话题</h3>
              <span class="history-meta" id="forumTopicCount">0 个话题</span>
            </div>
            <div class="toolbar" style="margin-top:12px;">
              <button type="button" class="secondary" id="forumToggleCreate">发起话题</button>
              <button type="button" class="secondary" id="forumRefreshButton">刷新</button>
            </div>
            <div class="forum-create-panel hidden" id="forumCreatePanel">
              <h3 style="margin-top:18px;">发起金点子话题</h3>
              <label>话题标题</label>
              <input id="forumTitle" placeholder="例如：如何让工作日记自动沉淀成项目经验？" />
              <label>话题内容</label>
              <textarea id="forumBody" placeholder="写下背景、想讨论的问题、希望大家从哪些角度给建议..."></textarea>
              <div class="toolbar">
                <button type="button" id="forumCreateButton">发布话题</button>
              </div>
              <div id="forumCreateStatus" class="status"></div>
              <h3 style="margin-top:24px;">智能体每日起题</h3>
              <label>输入信息</label>
              <textarea id="forumAiSeed" placeholder="输入今天的工作背景、灵感、项目机会或想让大家讨论的方向..."></textarea>
              <label>聊天内容</label>
              <textarea id="forumAiChat" placeholder="可粘贴群聊、会议纪要、用户反馈等内容..."></textarea>
              <label>传入文档</label>
              <input id="forumAiFiles" type="file" multiple accept=".txt,.md,.csv,.docx,.xlsx" />
              <div class="toolbar">
                <button type="button" class="warn" id="forumAiButton"><span class="icon" data-icon="sparkles"></span> 智能生成话题</button>
              </div>
              <div id="forumAiStatus" class="status"></div>
            </div>
            <div class="forum-topic-list" id="forumTopicList">
              <div class="forum-empty">暂无话题，先发起一个金点子吧。</div>
            </div>
          </div>
          <div class="forum-card">
            <div id="forumTopicDetail" style="margin-top:16px;">
              <div class="forum-empty">选择一个话题查看详情和讨论。</div>
            </div>
          </div>
        </div>
      </div>
      <div class="task-panel hidden" id="newsPanel">
        <div class="news-layout" id="newsLayout">
          <div class="news-card superadmin-only hidden" id="newsConfigCard">
            <h3>资讯收集配置</h3>
            <label>网页路径</label>
            <div id="newsSources"></div>
            <div class="toolbar">
              <button type="button" class="secondary" id="newsAddSource">新增网页</button>
            </div>
            <label>大模型自动搜索关键词</label>
            <textarea id="newsSearchQuery" placeholder="轨道交通 OR 城市轨道 OR 地铁 OR 智慧轨交"></textarea>
            <div class="row">
              <label><input id="newsAutoSearch" type="checkbox" style="width:auto" /> 允许大模型自动网络搜索</label>
              <label><input id="newsAutoPush" type="checkbox" style="width:auto" /> 每日自动更新推送</label>
            </div>
            <label>推送时间</label>
            <input id="newsPushTime" type="time" value="08:30" />
            <div class="toolbar">
              <button type="button" id="newsSaveConfig">保存配置</button>
              <button type="button" class="warn" id="newsGenerateNow"><span class="icon" data-icon="sparkles"></span> 立即生成今日资讯</button>
            </div>
            <div id="newsConfigStatus" class="status"></div>
            <div class="hint">自动搜索会通过平台配置的大模型 API 发起；若模型平台不支持联网工具，将主要基于配置网页内容生成。</div>
          </div>
          <div class="news-card">
            <div class="news-issue-head">
              <div>
                <div class="news-issue-title" id="newsTitle">暂无每日资讯</div>
                <div class="news-issue-meta" id="newsMeta">配置资讯源后生成今日简报。</div>
              </div>
              <button type="button" class="secondary" id="newsRefresh">刷新</button>
            </div>
            <div class="news-summary" id="newsSummary">暂无摘要。</div>
            <div class="news-list" id="newsItems"></div>
            <div class="news-keywords" id="newsKeywords"></div>
          </div>
        </div>
      </div>
      <div class="task-panel" id="weeklyPanel">
      <div class="guide" id="weeklyGuide">
        <div class="weekly-workspace">
          <div class="weekly-period-card">
            <div class="weekly-period-head">
              <div>
                <div class="weekly-period-title">周报时段</div>
                <div class="weekly-section-meta">默认上周一至上周五，可用日历快速调整。</div>
              </div>
              <div class="toolbar" style="margin-top:0">
                <span class="history-meta" id="weeklyPeriodText"></span>
                <button class="action-button" id="loadLatestWeekly" type="button">获取最新历史报告</button>
              </div>
            </div>
            <div class="weekly-period-grid">
              <div>
                <label>开始日期</label>
                <input id="weeklyStart" type="date" />
              </div>
              <div>
                <label>结束日期</label>
                <input id="weeklyEnd" type="date" />
              </div>
            </div>
          </div>
          <input id="weeklyPeriod" type="hidden" />
          <div class="diary-summarize-box" id="diarySummarizeBox">
            <span class="icon" data-icon="sparkles" style="color:var(--accent);font-size:18px;"></span>
            <div style="flex:1;min-width:200px;">
              <div style="font-weight:700;font-size:13px;margin-bottom:4px;">从工作日记智能总结</div>
              <div style="font-size:12px;color:var(--muted);">选择日期范围，AI 自动总结日记内容填充周报</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
              <input id="diarySumStart" type="date" style="width:auto;min-width:130px;" />
              <span style="color:var(--muted);font-size:13px;">至</span>
              <input id="diarySumEnd" type="date" style="width:auto;min-width:130px;" />
              <button type="button" id="diarySummarizeBtn">智能总结</button>
            </div>
          </div>
          <div class="weekly-section-grid">
            <section class="weekly-section-card">
              <div class="weekly-section-head">
                <div>
                  <div class="weekly-section-title">一、本周工作总结</div>
                  <div class="weekly-section-meta"><span id="summaryCount">0</span> 项，点击卡片填写详情</div>
                </div>
                <button class="mini" id="addSummary" type="button">新增</button>
              </div>
              <div class="weekly-rows" id="summaryRows"></div>
            </section>
            <section class="weekly-section-card">
              <div class="weekly-section-head">
                <div>
                  <div class="weekly-section-title">二、重点工作跟进</div>
                  <div class="weekly-section-meta"><span id="followCount">0</span> 项，记录进展和困难</div>
                </div>
                <button class="mini" id="addFollow" type="button">新增</button>
              </div>
              <div class="weekly-rows" id="followRows"></div>
            </section>
            <section class="weekly-section-card">
              <div class="weekly-section-head">
                <div>
                  <div class="weekly-section-title">三、下周工作计划</div>
                  <div class="weekly-section-meta"><span id="nextCount">0</span> 项，安排后续计划</div>
                </div>
                <button class="mini" id="addNext" type="button">新增</button>
              </div>
              <div class="weekly-rows" id="nextRows"></div>
            </section>
          </div>
        </div>
      </div>
      </div>
      <div class="task-panel hidden" id="tripPanel">
      <div class="guide" id="tripGuide">
        <div class="toolbar" style="margin-top:0;margin-bottom:12px">
          <button class="action-button" id="loadLatestTrip" type="button">获取最新历史报告</button>
          <span class="history-meta">使用最近一份出差报告自动填充当前模板。</span>
        </div>
        <div class="trip-store">
          <input id="tripReporter" value="周颖超" />
          <input id="tripDepartment" value="场景研究院" />
          <input id="tripLocation" placeholder="青岛" />
          <input id="tripStart" placeholder="2026-05-06" />
          <input id="tripEnd" placeholder="2026-05-08" />
          <textarea id="tripPurpose"></textarea>
          <textarea id="tripItinerary"></textarea>
          <textarea id="tripDetails"></textarea>
          <textarea id="tripIssues"></textarea>
          <textarea id="tripSuggestions"></textarea>
        </div>
        <div class="edit-card-grid" id="tripCards"></div>
      </div>
      </div>
      <div class="task-panel hidden" id="configPanel">
      <div class="guide">
        <div class="superadmin-only hidden">
        <h2 style="margin:0 0 14px">大模型 API 配置</h2>
        <div class="config-grid">
          <div>
            <label>NewAPI 地址</label>
            <input id="configApiUrl" placeholder="http://host:port" />
          </div>
          <div>
            <label>模型名称</label>
            <select id="configModelSelect"></select>
          </div>
        </div>
        <label>手动模型名称</label>
        <input id="configModel" placeholder="MiniMax-M2.7" />
        <label>API Key</label>
        <input id="configApiKey" type="password" placeholder="留空则保持原 Key 不变" />
        <div class="hint" id="configKeyHint"></div>
        <label>默认优化提示词</label>
        <textarea id="configPrompt"></textarea>
        <div class="toolbar">
          <button class="secondary" id="loadModels" type="button">获取模型列表</button>
          <button class="warn" id="testModel" type="button">测试 API Key</button>
          <button id="saveConfig" type="button">保存系统配置</button>
        </div>
        <div id="configTestStatus" class="status"></div>
        </div>
        <div class="superadmin-only hidden">
        <h2 style="margin-top:18px">邮件服务器（全局）</h2>
        <div class="config-grid">
          <div>
            <label>SMTP 服务器</label>
            <input id="configSmtpHost" placeholder="smtp.263.net" />
          </div>
          <div>
            <label>SMTP 端口</label>
            <input id="configSmtpPort" type="number" placeholder="465" />
          </div>
        </div>
        <div class="row">
          <label><input id="configSmtpTls" type="checkbox" style="width:auto" /> 使用 TLS</label>
          <label><input id="configSmtpSsl" type="checkbox" style="width:auto" /> 使用 SSL</label>
        </div>
        <div class="config-grid">
          <div>
            <label>IMAP 服务器</label>
            <input id="configImapHost" placeholder="imap.263.net" />
          </div>
          <div>
            <label>IMAP 端口</label>
            <input id="configImapPort" type="number" placeholder="993" />
          </div>
        </div>
        <div class="row">
          <label><input id="configImapSsl" type="checkbox" style="width:auto" /> 使用 SSL 连接 IMAP</label>
        </div>
        <div class="toolbar">
          <button id="saveServerConfig" type="button">保存邮件服务器配置</button>
        </div>
        <div id="configServerStatus" class="status"></div>
        </div>
        <div class="admin-only hidden">
        <h2 style="margin-top:18px">用户管理</h2>
        <div class="config-grid">
          <div>
            <label>用户名</label>
            <input id="newUserName" placeholder="zhangsan" />
          </div>
          <div>
            <label>显示名称</label>
            <input id="newDisplayName" placeholder="张三" />
          </div>
        </div>
        <div class="config-grid" id="newUserRoleBox" style="display:none;">
          <div>
            <label>角色权限</label>
            <select id="newUserRole">
              <option value="member">普通成员</option>
              <option value="admin">管理员</option>
              <option value="superadmin">超级管理员</option>
            </select>
          </div>
        </div>
        <label>初始密码</label>
        <input id="newUserPassword" type="password" placeholder="至少 4 位" />
        <div class="toolbar">
          <button id="addUser" type="button">新增用户</button>
        </div>
        <div class="user-list" id="userList"></div>
        </div>
      </div>
      </div></div>
      <div class="task-panel hidden" id="mailConfigPanel">
      <div class="guide">
        <h2>我的邮箱账户</h2>
        <div class="config-grid">
          <div>
            <label>本人邮箱</label>
            <input id="mailUserEmail" placeholder="your-email@example.com" />
          </div>
          <div>
            <label>SMTP 发件地址</label>
            <input id="mailSmtpFrom" placeholder="默认使用本人邮箱" />
          </div>
        </div>
        <div class="config-grid">
          <div>
            <label>SMTP 用户名</label>
            <input id="mailSmtpUser" placeholder="通常为邮箱账号" />
          </div>
          <div>
            <label>SMTP 授权码/密码</label>
            <input id="mailSmtpPassword" type="password" placeholder="留空则保持原密码不变" />
            <div class="hint" id="mailPasswordHint"></div>
          </div>
        </div>
        <div class="config-grid" style="margin-top:8px;">
          <div style="background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;">
            <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">SMTP 服务器（全局）</div>
            <div id="mailSmtpHostDisplay" style="font-weight:700;font-size:14px;">smtp.263.net</div>
          </div>
          <div style="background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;">
            <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">SMTP 端口 / SSL</div>
            <div id="mailSmtpPortDisplay" style="font-weight:700;font-size:14px;">465 / SSL</div>
          </div>
        </div>
        <h2 style="margin-top:18px">收件箱 IMAP</h2>
        <div class="config-grid">
          <div>
            <label>IMAP 用户名</label>
            <input id="mailImapUser" placeholder="默认使用 SMTP 用户名" />
          </div>
          <div>
            <label>IMAP 授权码/密码</label>
            <input id="mailImapPassword" type="password" placeholder="留空则保持原密码不变" />
            <div class="hint" id="mailImapPasswordHint"></div>
          </div>
        </div>
        <div class="config-grid" style="margin-top:8px;">
          <div style="background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;">
            <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">IMAP 服务器（全局）</div>
            <div id="mailImapHostDisplay" style="font-weight:700;font-size:14px;">imap.263.net</div>
          </div>
          <div style="background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px;">
            <div style="font-size:12px;color:var(--muted);margin-bottom:2px;">IMAP 端口 / SSL</div>
            <div id="mailImapPortDisplay" style="font-weight:700;font-size:14px;">993 / SSL</div>
          </div>
        </div>
        <h2 style="margin-top:18px">周报邮件</h2>
        <div class="config-grid">
          <div>
            <label>周报收件人</label>
            <input id="mailWeeklyTo" placeholder="leader@example.com" />
          </div>
          <div>
            <label>周报抄送</label>
            <input id="mailWeeklyCc" placeholder="可选，多个用分号分隔" />
          </div>
        </div>
        <h2 style="margin-top:18px">出差报告邮件</h2>
        <div class="config-grid">
          <div>
            <label>出差报告收件人</label>
            <input id="mailTripTo" placeholder="leader@example.com" />
          </div>
          <div>
            <label>出差报告抄送</label>
            <input id="mailTripCc" placeholder="可选，多个用分号分隔" />
          </div>
        </div>
        <label>邮件签名模板</label>
        <textarea id="mailEmailSignature" placeholder="留空则使用默认签名"></textarea>
        <div class="toolbar" style="margin-top:16px">
          <button id="saveMailConfig" type="button">保存我的邮件配置</button>
          <button class="warn" id="testMailConfig" type="button">测试我的邮箱配置</button>
        </div>
        <div id="mailConfigStatus" class="status"></div>
      </div>
      </div>
      <div class="task-panel hidden" id="mailAssistantPanel">
      <div class="guide">
        <div class="mail-assistant-grid">
          <div class="mailbox-card">
            <div class="mail-section-head">
              <div>
                <div class="mail-section-title">收件箱</div>
                <div class="mail-section-meta">查看当前账号最近邮件，支持正文和附件信息预览。</div>
              </div>
              <div class="toolbar" style="margin-top:0">
                <select id="mailboxLimit" style="width:110px">
                  <option value="10">最近 10 封</option>
                  <option value="20" selected>最近 20 封</option>
                  <option value="50">最近 50 封</option>
                </select>
                <button class="secondary" id="refreshMailbox" type="button"><span class="icon" data-icon="refresh-cw"></span> 刷新</button>
              </div>
            </div>
            <div class="mailbox-list" id="mailboxList"></div>
          </div>
          <div class="mail-detail-card">
            <div class="mail-section-head">
              <div>
                <div class="mail-section-title">邮件详情</div>
                <div class="mail-section-meta">按邮件原始版式预览正文，附件在头部集中展示。</div>
              </div>
            </div>
            <div class="mail-detail" id="mailDetail">暂无选中邮件。</div>
          </div>
        </div>
        <div class="mail-compose-card">
          <div class="mail-section-head">
            <div>
              <div class="mail-section-title">发送邮件</div>
              <div class="mail-section-meta">使用当前账号 SMTP 发送普通邮件，可添加附件并实时预览正文。</div>
            </div>
          </div>
          <div class="mail-compose-layout">
            <div class="mail-compose-form">
              <div class="row">
                <div>
                  <label>收件人</label>
                  <input id="assistantMailTo" placeholder="recipient@example.com" />
                </div>
                <div>
                  <label>抄送</label>
                  <input id="assistantMailCc" placeholder="可选，多个邮箱用分号分隔" />
                </div>
              </div>
              <label>主题</label>
              <input id="assistantMailSubject" placeholder="请输入邮件主题" />
              <label>正文</label>
              <textarea id="assistantMailBody" placeholder="请输入邮件正文"></textarea>
              <label>附件</label>
              <input id="assistantMailFiles" type="file" multiple />
              <div class="mail-file-list" id="assistantMailFileList"></div>
              <div class="toolbar">
                <button class="secondary" id="clearAssistantMail" type="button">清空</button>
                <button class="warn" id="sendAssistantMail" type="button"><span class="icon" data-icon="send"></span> 发送邮件</button>
              </div>
              <div id="assistantMailStatus" class="status"></div>
            </div>
            <div class="mail-compose-preview">
              <label>正文预览</label>
              <div class="rich-preview" id="assistantMailPreview">暂无正文内容</div>
            </div>
          </div>
        </div>
      </div>
      </div>
      <div class="toolbar hidden" id="generateToolbar">
        <button id="generate">按标准模板生成文件</button>
      </div>
      <div class="task-panel hidden" id="mailPanel">
      <div class="mail-layout">
      <div class="side">
        <h2>报告文件</h2>
        <label>类型</label>
        <select id="mailKind">
          <option value="weekly">周报</option>
          <option value="trip">出差报告</option>
        </select>
        <div id="reports"></div>
      </div>
      <div>
      <h2>邮件内容</h2>
      <div class="row">
        <div>
          <label>收件人</label>
          <input id="to" placeholder="leader@example.com" />
        </div>
        <div>
          <label>抄送</label>
          <input id="cc" placeholder="可选，多个邮箱用分号分隔" />
        </div>
      </div>
      <label>主题</label>
      <input id="subject" />
      <label>正文</label>
      <textarea id="body"></textarea>
      <label>发送邮件正文预览</label>
      <div class="rich-preview" id="bodyPreview"></div>
      <label>附件</label>
      <input id="attachment" readonly />
      <div class="toolbar" style="margin-top:8px">
        <a id="downloadLink" class="download-link hidden" href="#" target="_blank">下载查看当前附件</a>
      </div>
      <label>模板内容预览</label>
      <div class="rich-preview" id="preview"></div>
      <div class="toolbar">
        <button id="refresh">重新生成正文</button>
        <button class="secondary" id="copy">复制正文</button>
        <button class="warn" id="send">发送/生成草稿</button>
      </div>
      </div>
      </div>
      </div>
      <div class="task-panel hidden" id="uploadPanel">
      <div class="guide">
        <div class="row">
          <div>
            <label>上传类型</label>
            <select id="uploadKind">
              <option value="weekly">历史周报（.xlsx / .xls）</option>
              <option value="trip">历史出差报告（.docx / .md）</option>
            </select>
          </div>
          <div>
            <label>选择文件</label>
            <input id="uploadFiles" type="file" multiple accept=".xlsx,.xls,.docx,.md" />
          </div>
        </div>
        <div class="toolbar">
          <button id="uploadButton" type="button">上传到历史报告库</button>
        </div>
        <div class="hint">上传后的文件会保存到当前用户的个人历史报告空间，并自动出现在“发送报告邮件”的报告列表中。</div>
        <div class="upload-list" id="uploadList"></div>
        <div class="history-tools">
          <h2 style="margin:0">历史报告管理</h2>
          <select id="historyKind">
            <option value="all">全部</option>
            <option value="weekly">周报</option>
            <option value="trip">出差报告</option>
          </select>
        </div>
        <div class="history-list" id="historyList"></div>
      </div>
      </div>
      <div id="status" class="status"></div>
    </section>
  </main>
  <div class="modal hidden" id="passModal" role="dialog" aria-modal="true">
    <div class="modal-box" style="width:min(420px,96vw)">
      <div class="modal-head">
        <div class="modal-title">修改密码</div>
        <button class="mini secondary" type="button" onclick="el('passModal').classList.add('hidden')">取消</button>
      </div>
      <div class="modal-fields">
        <label>原密码</label>
        <input id="passOld" type="password" placeholder="输入当前密码" />
        <label>新密码</label>
        <input id="passNew" type="password" placeholder="至少 4 位" />
        <label>确认新密码</label>
        <input id="passConfirm" type="password" placeholder="再次输入新密码" />
        <div id="passStatus" class="status"></div>
      </div>
      <div class="modal-actions">
        <button class="secondary" type="button" onclick="el('passModal').classList.add('hidden')">取消</button>
        <button type="button" id="passSave">确认修改</button>
      </div>
    </div>
  </div>
  <div class="modal hidden" id="editModal" role="dialog" aria-modal="true">
    <div class="modal-box">
      <div class="modal-head">
        <div class="modal-title" id="modalTitle">编辑内容</div>
        <button class="mini secondary" type="button" id="modalClose">退出并保存</button>
      </div>
      <div class="modal-fields" id="modalFields"></div>
      <div class="modal-actions">
        <button class="secondary" type="button" id="modalCancel">退出并保存</button>
        <button type="button" id="modalSave">保存</button>
      </div>
    </div>
  </div>
  <script>
    let defaultAssistantPrompt = `请帮我优化下面的工作内容，要求：
1、拆分成1、2、3、4这样的编号要点，每点单独换行。
2、语言简洁明了，体现实际工作量和推进成果。
3、修正错别字、病句和不通顺表达。
4、不要编造不存在的事项，不要写空话套话。`;
    let state = { reports: [], selected: null, task: 'weekly', subTab: 'edit', user: null, weeklyPrefilled: false, tripPrefilled: false, modalSave: null, restoringDraft: false, assistantMailFiles: [], forumSelected: null, forumCommentPage: 1 };
    const FORM_DRAFT_PREFIX = 'personalWorkSite.formDraft.v2';
    const el = id => document.getElementById(id);
    const lucideIcons = {
      sparkles: '<path d="M9.94 14.5 8.5 18.06 7.06 14.5 3.5 13.06 7.06 11.62 8.5 8.06l1.44 3.56 3.56 1.44-3.56 1.44Z"/><path d="M18 8.5 17.2 10.7 15 11.5l2.2.8L18 14.5l.8-2.2 2.2-.8-2.2-.8L18 8.5Z"/><path d="M15 2l-.9 2.1L12 5l2.1.9L15 8l.9-2.1L18 5l-2.1-.9L15 2Z"/>',
      search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
      'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
      'file-spreadsheet': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M10 9v8"/><path d="M14 9v8"/>',
      'briefcase-business': '<path d="M12 12h.01"/><path d="M16 6V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><path d="M22 13a18.15 18.15 0 0 1-20 0"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
      'mail-check': '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/><path d="M22 12.5V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h8"/><path d="m16 19 2 2 4-4"/>',
      inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>',
      paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
      'refresh-cw': '<path d="M3 12a9 9 0 0 1 15.1-6.6L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.1 6.6L3 16"/><path d="M3 21v-5h5"/>',
      settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.51a2 2 0 0 1 1-1.72l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/>',
      send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
      'file-plus-2': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M12 18v-6"/><path d="M9 15h6"/>',
      bot: '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
      'bell-ring': '<path d="M10.27 21a2 2 0 0 0 3.46 0"/><path d="M4 8a8 8 0 0 1 16 0c0 7 3 7 3 9H1c0-2 3-2 3-9"/><path d="M18.75 3.2A10 10 0 0 1 22 8"/><path d="M1.99 8a10 10 0 0 1 3.26-4.8"/>',
      'file-text': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
      'messages-square': '<path d="M14 9a2 2 0 0 1-2 2H6l-4 4V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2Z"/><path d="M18 9h2a2 2 0 0 1 2 2v10l-4-4h-6a2 2 0 0 1-2-2v-1"/>',
      'thumbs-up': '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3.28a2 2 0 0 0 1.7-.94L13 2a2.3 2.3 0 0 1 2 3.88Z"/>',
      newspaper: '<path d="M4 22h14a2 2 0 0 0 2-2V4H6a2 2 0 0 0-2 2v16Z"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h6v4h-6z"/><path d="M4 8H2v12a2 2 0 0 0 2 2"/>',
      mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
      'folder-clock': '<path d="M10 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2v1.5"/><circle cx="16" cy="16" r="5"/><path d="M16 13v3l2 1"/>',
      archive: '<rect width="20" height="5" x="2" y="3" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
      'calendar-check': '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
      'wand-sparkles': '<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.21 1.21 0 0 0 1.72 0L21.64 5.36a1.21 1.21 0 0 0 0-1.72Z"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/>',
      database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/>',
      'clipboard-pen': '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v9"/><path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7"/><path d="M17.5 22 22 17.5 20.5 16 16 20.5V22Z"/>',
      'book-open': '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
      'pen-line': '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
      'library': '<path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/><path d="M4 4v16"/>',
      'chevron-right': '<path d="m9 18 6-6-6-6"/>'
    };

    function renderIcons(root = document) {
      root.querySelectorAll('[data-icon]').forEach(node => {
        const name = node.dataset.icon;
        if (!lucideIcons[name] || node.dataset.iconRendered === 'true') return;
        node.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${lucideIcons[name]}</svg>`;
        node.dataset.iconRendered = 'true';
      });
    }

    async function api(path, options) {
      const res = await fetch(path, options);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '请求失败');
      return data;
    }
    async function apiPost(path, body) {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || '请求失败');
      return data;
    }

    function applyUser(user) {
      state.user = user;
      const authed = !!user;
      el('authPanel').classList.toggle('hidden', authed);
      el('appMain').classList.toggle('hidden', !authed);
      el('userbar').style.display = authed ? 'flex' : 'none';
      el('agentFloat').classList.toggle('hidden', !authed);
      if (authed) {
        const roleText = user.role === 'superadmin' ? '超级管理员' : user.role === 'admin' ? '管理员' : '成员';
        el('userInfo').textContent = `${user.name || user.username} · ${roleText}`;
        el('userAvatar').src = user.avatar_url || '/assets/ai-assistant-avatar.png';
      }
      document.querySelectorAll('.admin-only').forEach(node => {
        node.classList.toggle('hidden', !user?.is_admin);
      });
      document.querySelectorAll('.superadmin-only').forEach(node => {
        node.classList.toggle('hidden', !user?.is_superadmin);
      });
      el('newsLayout')?.classList.toggle('reader', !user?.is_superadmin);
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
        reader.onerror = () => reject(reader.error || new Error('读取文件失败'));
        reader.readAsDataURL(file);
      });
    }

    function openProfileModal() {
      const user = state.user || {};
      el('profileName').value = user.name || user.username || '';
      el('profileBio').value = user.bio || '';
      el('profileHobbies').value = user.hobbies || '';
      el('profileAvatarPreview').src = user.avatar_url || '/assets/ai-assistant-avatar.png';
      el('profileAvatarFile').value = '';
      el('profileStatus').textContent = '';
      el('profileStatus').className = 'status';
      el('profileModal').classList.remove('hidden');
    }

    function closeProfileModal() {
      el('profileModal').classList.add('hidden');
    }

    async function saveProfile(avatarPreset = '') {
      try {
        el('profileStatus').textContent = '保存中...';
        el('profileStatus').className = 'status';
        const file = el('profileAvatarFile').files[0];
        const avatarData = file ? await readFileAsBase64(file) : '';
        const result = await apiPost('/api/profile', {
          name: el('profileName').value,
          bio: el('profileBio').value,
          hobbies: el('profileHobbies').value,
          avatar_data: avatarData,
          avatar_preset: avatarPreset
        });
        applyUser(result.user);
        el('profileAvatarPreview').src = result.user.avatar_url || '/assets/ai-assistant-avatar.png';
        el('profileAvatarFile').value = '';
        el('profileStatus').textContent = '个人资料已保存';
        el('profileStatus').className = 'status ok';
      } catch (err) {
        el('profileStatus').textContent = err.message;
        el('profileStatus').className = 'status err';
      }
    }

    function renderReports() {
      const kind = el('mailKind').value;
      const list = state.reports.filter(r => r.kind === kind);
      el('reports').innerHTML = list.map(r => `
        <div class="report ${state.selected === r.name ? 'active' : ''}" data-name="${encodeURIComponent(r.name)}">
          <div class="name">${r.name}</div>
          <div class="meta">${r.generated ? '新生成' : (r.kind === 'weekly' ? '周报模板' : '出差报告模板')} · ${new Date(r.mtime * 1000).toLocaleString()}</div>
        </div>
      `).join('');
      document.querySelectorAll('.report').forEach(node => {
        node.addEventListener('click', () => loadDraft(kind, decodeURIComponent(node.dataset.name)));
      });
    }

    function reportKindName(kind) {
      return kind === 'weekly' ? '周报' : '出差报告';
    }

    function renderRecentDocs() {
      const list = state.reports.slice(0, 6);
      const box = el('recentDocsList');
      if (!box) return;
      box.innerHTML = list.length ? list.map(r => `
        <div class="doc-item">
          <div>
            <div class="doc-name">${escapeHtml(r.name)}</div>
            <div class="doc-meta">${r.kind === 'weekly' ? '周报' : '出差报告'} · ${new Date(r.mtime * 1000).toLocaleDateString()}</div>
          </div>
          <a class="download-link" style="padding:6px 12px;font-size:12px;" href="/download?file=${encodeURIComponent(r.name)}" target="_blank">查看</a>
        </div>
      `).join('') : '<div class="doc-item"><span class="doc-name">暂无最近文档</span></div>';
    }

    function renderHistoryReports() {
      const kind = el('historyKind')?.value || 'all';
      const list = state.reports.filter(r => !r.generated && (kind === 'all' || r.kind === kind));
      el('historyList').innerHTML = list.length ? list.map(r => `
        <div class="history-item" data-name="${encodeURIComponent(r.name)}">
          <div>
            <div class="history-name">${escapeHtml(r.name)}</div>
            <div class="history-meta">${reportKindName(r.kind)} · ${new Date(r.mtime * 1000).toLocaleString()}</div>
          </div>
          <div class="history-actions">
            <a class="download-link" href="/download?file=${encodeURIComponent(r.name)}" target="_blank">下载</a>
            <button class="mini danger delete-history" type="button">删除</button>
          </div>
        </div>
      `).join('') : '<div class="upload-item">暂无历史报告。</div>';
      el('historyList').querySelectorAll('.delete-history').forEach(button => {
        button.addEventListener('click', async () => {
          const name = decodeURIComponent(button.closest('.history-item').dataset.name);
          if (!confirm('确定删除这个历史报告吗？\\n' + name)) return;
          try {
            const result = await api('/api/delete-history', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ name })
            });
            el('status').textContent = '已删除历史报告：' + result.deleted;
            el('status').className = 'status ok';
            await loadReports({ preserveSelection: true });
          } catch (err) {
            el('status').textContent = err.message;
            el('status').className = 'status err';
          }
        });
      });
    }

    function setSubTab(sub) {
      state.subTab = sub;
      document.querySelectorAll('.sub-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.sub === sub);
      });
      const task = state.task;
      const isAssistant = task === 'weekly' || task === 'trip';
      const isWeekly = task === 'weekly';
      const isEdit = sub === 'edit';
      const isMail = sub === 'mail';
      const isHistory = sub === 'history';
      el('weeklyPanel').classList.toggle('hidden', !isAssistant || !isWeekly || !isEdit);
      el('tripPanel').classList.toggle('hidden', !isAssistant || isWeekly || !isEdit);
      el('generateToolbar').classList.toggle('hidden', !isAssistant || !isEdit);
      el('mailPanel').classList.toggle('hidden', !isAssistant || !isMail);
      el('uploadPanel').classList.toggle('hidden', !isAssistant || !isHistory);
      if (isMail) renderReports();
      if (isHistory) renderHistoryReports();
      el('status').textContent = '';
      el('status').className = 'status';
    }

    function navigateTo(task, sub) {
      state.subTab = sub || 'edit';
      setTask(task);
    }

    function setTask(task) {
      state.task = task;
      document.querySelectorAll('.task-card').forEach(card => {
        card.classList.toggle('active', card.dataset.task === task);
      });
      const isDashboard = task === 'dashboard';
      const isAssistant = task === 'weekly' || task === 'trip';
      el('dashboardPanel').classList.toggle('hidden', !isDashboard);
      el('pageHeader').classList.toggle('hidden', isDashboard);
      el('subTabs').classList.toggle('hidden', !isAssistant);
      el('weeklyPanel').classList.add('hidden');
      el('tripPanel').classList.add('hidden');
      el('mailPanel').classList.add('hidden');
      el('uploadPanel').classList.add('hidden');
      el('mailAssistantPanel').classList.toggle('hidden', task !== 'mailassistant');
      el('diaryPanel').classList.toggle('hidden', task !== 'diary');
      el('forumPanel').classList.toggle('hidden', task !== 'forum');
      el('newsPanel').classList.toggle('hidden', task !== 'news');
      el('generateToolbar').classList.add('hidden');
      el('configPanel').classList.toggle('hidden', task !== 'config');
      el('mailConfigPanel').classList.toggle('hidden', task !== 'mailconfig');
      if (!isAssistant) {
        state.subTab = 'edit';
        document.querySelectorAll('.sub-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.sub === 'edit'));
      }
      const titles = { dashboard: '工作台', weekly: '周报助手', trip: '出差报告助手', diary: '工作日记', forum: '金点子论坛', news: '每日资讯', mailassistant: '邮件助手', config: '系统配置', mailconfig: '邮件配置' };
      const descs = {
        dashboard: '智能办公一站式工作台',
        weekly: '填写周报、发送邮件、管理历史周报',
        trip: '填写出差报告、发送邮件、管理历史出差报告',
        diary: '记录每日工作、查看历史日记，写周报时可智能总结',
        forum: '智能体或成员发起每日话题，大家围绕创意、改进和机会展开讨论',
        news: '收集轨道交通关键资讯，调用平台大模型生成每日简报',
        mailassistant: '查看收件箱、阅读邮件、发送普通邮件',
        config: '管理员配置 AI 接口和系统参数',
        mailconfig: '配置发件邮箱、收件人和抄送地址'
      };
      el('taskTitle').textContent = titles[task] || '';
      el('taskDesc').textContent = descs[task] || '';
      syncAgentToTask(task);
      if (isDashboard) {
        renderRecentDocs();
        const u = state.user;
        el('dashUserName').textContent = u ? (u.name || u.username) : '';
      }
      if (isAssistant) {
        el('kind').value = task;
        el('mailKind').value = task;
        el('uploadKind').value = task;
        el('historyKind').value = task;
        const hideEl = (sel) => { if (sel) sel.style.display = 'none'; };
        const hidePrevLabel = (sel) => { const lab = sel?.previousElementSibling; if (lab && lab.tagName === 'LABEL') lab.style.display = 'none'; };
        hideEl(el('mailKind')); hidePrevLabel(el('mailKind'));
        hideEl(el('uploadKind')); hidePrevLabel(el('uploadKind'));
        const historyTools = el('historyKind')?.closest('.history-tools');
        if (historyTools) historyTools.style.display = 'none';
        setSubTab(state.subTab || 'edit');
      }
      if (task === 'mailconfig') {
        loadMailConfig();
      }
      if (task === 'mailassistant') {
        loadMailbox();
      }
      if (task === 'diary') {
        initDiaryPanel();
      }
      if (task === 'forum') {
        loadForumTopics();
      }
      if (task === 'news') {
        loadNews();
      }
    }

    function workFields(section) {
      const isNext = section === 'next';
      return isNext
        ? [
            ['category', '工作分类'],
            ['content', '工作内容'],
            ['difficulty', '困难与求助']
          ]
        : [
            ['category', '工作分类'],
            ['content', '工作内容'],
            [section === 'summary' ? 'status' : 'progress', section === 'summary' ? '完成情况' : '当前进展'],
            [section === 'summary' ? 'plan' : 'difficulty', section === 'summary' ? '后续计划' : '困难与求助']
          ];
    }

    function sectionName(section) {
      return { summary: '本周工作总结', follow: '重点工作跟进', next: '下周工作计划' }[section] || '工作内容';
    }

    function sectionTarget(section) {
      return section === 'summary' ? el('summaryRows') : section === 'follow' ? el('followRows') : el('nextRows');
    }

    function updateWeeklyCounts() {
      [['summary', 'summaryCount'], ['follow', 'followCount'], ['next', 'nextCount']].forEach(([section, id]) => {
        const count = collectWorkRows(section).length;
        if (el(id)) el(id).textContent = count;
      });
    }

    function rowPreview(row) {
      const parts = [row.category, row.content, row.status, row.progress, row.plan, row.difficulty]
        .map(value => String(value || '').trim())
        .filter(Boolean);
      return parts.join('\\n') || '点击填写任务内容';
    }

    function rowTemplate(section, row, index) {
      const fields = workFields(section);
      const title = row.category || `${sectionName(section)} ${index + 1}`;
      return `
        <div class="work-block" data-section="${section}" data-index="${index}">
          <div class="work-head">
            <div class="work-title">${escapeHtml(title)}</div>
            <button class="mini danger remove-row" type="button">删除</button>
          </div>
          <div class="work-summary">${escapeHtml(rowPreview(row))}</div>
          <div class="field-store">
            ${fields.map(([key, label]) => `
              <textarea data-key="${key}" data-label="${label}">${escapeHtml(row[key] || '')}</textarea>
            `).join('')}
          </div>
        </div>`;
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    function renderWorkRows(section, rows) {
      const target = sectionTarget(section);
      target.innerHTML = (rows && rows.length ? rows : [{}]).map((row, index) => rowTemplate(section, row, index)).join('');
      attachWorkEvents(target);
      updateWeeklyCounts();
    }

    function attachWorkEvents(target) {
      target.querySelectorAll('.remove-row').forEach(button => {
        button.addEventListener('click', event => {
          event.stopPropagation();
          button.closest('.work-block').remove();
          renumberRows(target);
          updateWeeklyCounts();
        });
      });
      target.querySelectorAll('.work-block').forEach(block => {
        block.addEventListener('click', () => openWorkModal(block));
      });
    }

    function renumberRows(container) {
      container.querySelectorAll('.work-block').forEach((block, index) => {
        block.dataset.index = index;
        refreshWorkCard(block);
      });
    }

    function addWorkRow(section, row = {}) {
      const target = sectionTarget(section);
      if (target.children.length === 1 && !target.querySelector('textarea')?.value.trim()) {
        target.innerHTML = '';
      }
      const wrapper = document.createElement('div');
      wrapper.innerHTML = rowTemplate(section, row, target.children.length).trim();
      const block = wrapper.firstElementChild;
      target.appendChild(block);
      attachWorkEvents(target);
      updateWeeklyCounts();
      openWorkModal(block);
    }

    function collectWorkRows(section) {
      const target = sectionTarget(section);
      return [...target.querySelectorAll('.work-block')].map(block => {
        const row = {};
        block.querySelectorAll('textarea[data-key]').forEach(input => {
          row[input.dataset.key] = input.value.trim();
        });
        return row;
      }).filter(row => Object.values(row).some(Boolean));
    }

    function refreshWorkCard(block) {
      const row = {};
      block.querySelectorAll('textarea[data-key]').forEach(input => {
        row[input.dataset.key] = input.value.trim();
      });
      const section = block.dataset.section;
      const index = Number(block.dataset.index || 0);
      block.querySelector('.work-title').textContent = row.category || `${sectionName(section)} ${index + 1}`;
      block.querySelector('.work-summary').textContent = rowPreview(row);
      updateWeeklyCounts();
      saveFormDraft();
    }

    function openModal(title, fields, onSave) {
      el('modalTitle').textContent = title;
      el('modalFields').innerHTML = fields.map(field => {
        const wide = field.multiline ? ' wide' : '';
        const control = field.multiline
          ? `<textarea data-modal-key="${field.key}" placeholder="${field.label}">${escapeHtml(field.value || '')}</textarea>`
          : `<input data-modal-key="${field.key}" type="${field.type || 'text'}" placeholder="${field.label}" value="${escapeHtml(field.value || '')}" />`;
        const assist = field.multiline ? `
          <div class="field-assist">
            <div class="field-assist-head">
              <details>
                <summary>展开/修改提示词</summary>
                <textarea class="field-assist-prompt">${escapeHtml(defaultAssistantPrompt)}</textarea>
              </details>
              <button class="warn assist-optimize" type="button">辅助优化</button>
            </div>
            <div class="assist-status">待优化</div>
          </div>` : '';
        return `
          <div class="${wide}">
            <label>${field.label}</label>
            ${assist}
            ${control}
          </div>`;
      }).join('');
      state.modalSave = onSave;
      el('editModal').classList.remove('hidden');
      const first = el('modalFields').querySelector('input, textarea');
      if (first) first.focus();
    }

    function closeModal() {
      el('editModal').classList.add('hidden');
      state.modalSave = null;
    }

    function saveAndCloseModal() {
      saveCurrentModal();
      closeModal();
    }

    function modalValues() {
      const values = {};
      el('modalFields').querySelectorAll('[data-modal-key]').forEach(input => {
        values[input.dataset.modalKey] = input.value.trim();
      });
      return values;
    }

    function draftStorageKey() {
      return state.user?.username ? `${FORM_DRAFT_PREFIX}:${state.user.username}` : '';
    }

    function tripFormPayload() {
      return {
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
    }

    function saveFormDraft() {
      const key = draftStorageKey();
      if (!key || state.restoringDraft) return;
      try {
        const draft = {
          updatedAt: Date.now(),
          weekly: {
            start: el('weeklyStart').value,
            end: el('weeklyEnd').value,
            period: el('weeklyPeriod').value,
            summary: collectWorkRows('summary'),
            follow: collectWorkRows('follow'),
            next: collectWorkRows('next')
          },
          trip: tripFormPayload()
        };
        localStorage.setItem(key, JSON.stringify(draft));
      } catch (err) {
        console.warn('保存本地草稿失败', err);
      }
    }

    function restoreSavedFormDraft(kind) {
      const key = draftStorageKey();
      if (!key) return false;
      let draft = null;
      try {
        draft = JSON.parse(localStorage.getItem(key) || 'null');
      } catch (err) {
        return false;
      }
      if (!draft) return false;
      state.restoringDraft = true;
      try {
        if (kind === 'weekly' && draft.weekly) {
          if (draft.weekly.start) el('weeklyStart').value = draft.weekly.start;
          if (draft.weekly.end) el('weeklyEnd').value = draft.weekly.end;
          syncWeeklyPeriod();
          if ((draft.weekly.summary || []).length || (draft.weekly.follow || []).length || (draft.weekly.next || []).length) {
            renderWorkRows('summary', draft.weekly.summary || []);
            renderWorkRows('follow', draft.weekly.follow || []);
            renderWorkRows('next', draft.weekly.next || []);
            state.weeklyPrefilled = true;
            return true;
          }
        }
        if (kind === 'trip' && draft.trip) {
          Object.entries({
            tripReporter: draft.trip.reporter,
            tripDepartment: draft.trip.department,
            tripLocation: draft.trip.location,
            tripStart: draft.trip.trip_start,
            tripEnd: draft.trip.trip_end,
            tripPurpose: draft.trip.purpose,
            tripItinerary: draft.trip.itinerary,
            tripDetails: draft.trip.details,
            tripIssues: draft.trip.issues,
            tripSuggestions: draft.trip.suggestions
          }).forEach(([id, value]) => {
            if (value !== undefined && value !== null) el(id).value = value;
          });
          renderTripCards();
          state.tripPrefilled = true;
          return true;
        }
      } finally {
        state.restoringDraft = false;
      }
      return false;
    }

    function clearSavedFormDraft(kind) {
      const key = draftStorageKey();
      if (!key) return;
      try {
        const draft = JSON.parse(localStorage.getItem(key) || '{}');
        if (kind === 'weekly') delete draft.weekly;
        if (kind === 'trip') delete draft.trip;
        localStorage.setItem(key, JSON.stringify({ ...draft, updatedAt: Date.now() }));
      } catch (err) {
        localStorage.removeItem(key);
      }
    }

    function saveCurrentModal() {
      if (state.modalSave) {
        state.modalSave(modalValues());
        saveFormDraft();
      }
    }

    function openWorkModal(block) {
      const section = block.dataset.section;
      const index = Number(block.dataset.index || 0) + 1;
      const fields = workFields(section).map(([key, label]) => {
        const input = block.querySelector(`[data-key="${key}"]`);
        return { key, label, value: input?.value || '', multiline: key !== 'category' };
      });
      openModal(`${sectionName(section)} ${index}`, fields, values => {
        fields.forEach(field => {
          const input = block.querySelector(`[data-key="${field.key}"]`);
          if (input) input.value = values[field.key] || '';
        });
        refreshWorkCard(block);
      });
    }

    const tripGroups = [
      {
        key: 'base',
        title: '基础信息',
        fields: [
          ['tripReporter', '报告人', false],
          ['tripDepartment', '部门', false],
          ['tripLocation', '出差地点', false],
          ['tripStart', '开始日期', false, 'date'],
          ['tripEnd', '结束日期', false, 'date']
        ]
      },
      { key: 'purpose', title: '出差目的', fields: [['tripPurpose', '出差目的', true]] },
      { key: 'itinerary', title: '行程概览', fields: [['tripItinerary', '行程概览', true]] },
      { key: 'details', title: '工作详情', fields: [['tripDetails', '工作详情', true]] },
      { key: 'issues', title: '问题与反馈', fields: [['tripIssues', '问题与反馈', true]] },
      { key: 'suggestions', title: '总结与建议', fields: [['tripSuggestions', '总结与建议', true]] }
    ];

    function tripPreview(group) {
      const values = group.fields.map(([id, label]) => {
        const value = el(id).value.trim();
        return value ? (group.key === 'base' ? `${label}：${value}` : value) : '';
      }).filter(Boolean);
      return values.join('\\n') || '点击填写内容';
    }

    function formatPeriodDate(value) {
      if (!value) return '';
      const [year, month, day] = value.split('-').map(Number);
      if (!year || !month || !day) return value;
      return `${year}.${month}.${day}`;
    }

    function toDateInputValue(date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    function setDefaultWeeklyDates(force = false) {
      if (!force && (el('weeklyStart').value || el('weeklyEnd').value)) {
        syncWeeklyPeriod();
        return;
      }
      const today = new Date();
      const day = today.getDay() || 7;
      const thisMonday = new Date(today);
      thisMonday.setHours(0, 0, 0, 0);
      thisMonday.setDate(today.getDate() - day + 1);
      const lastMonday = new Date(thisMonday);
      lastMonday.setDate(thisMonday.getDate() - 7);
      const lastFriday = new Date(lastMonday);
      lastFriday.setDate(lastMonday.getDate() + 4);
      el('weeklyStart').value = toDateInputValue(lastMonday);
      el('weeklyEnd').value = toDateInputValue(lastFriday);
      el('diarySumStart').value = toDateInputValue(lastMonday);
      el('diarySumEnd').value = toDateInputValue(lastFriday);
      syncWeeklyPeriod();
    }

    function syncWeeklyPeriod() {
      const start = formatPeriodDate(el('weeklyStart').value);
      const end = formatPeriodDate(el('weeklyEnd').value);
      el('weeklyPeriod').value = start && end ? `${start}-${end}` : (start || end);
      if (el('weeklyPeriodText')) {
        el('weeklyPeriodText').textContent = el('weeklyPeriod').value || '未选择时段';
      }
      saveFormDraft();
    }

    function renderTripCards() {
      el('tripCards').innerHTML = tripGroups.map(group => `
        <div class="edit-card" data-trip-group="${group.key}">
          <div class="edit-card-title">${group.title}</div>
          <div class="edit-card-preview">${escapeHtml(tripPreview(group))}</div>
        </div>
      `).join('');
      el('tripCards').querySelectorAll('.edit-card').forEach(card => {
        card.addEventListener('click', () => openTripModal(card.dataset.tripGroup));
      });
    }

    function openTripModal(groupKey) {
      const group = tripGroups.find(item => item.key === groupKey);
      if (!group) return;
      const fields = group.fields.map(([id, label, multiline, type]) => ({
        key: id,
        label,
        multiline,
        type,
        value: el(id).value
      }));
      openModal(group.title, fields, values => {
        fields.forEach(field => {
          el(field.key).value = values[field.key] || '';
        });
        renderTripCards();
        saveFormDraft();
      });
    }

    async function loadReports(options = {}) {
      const data = await api('/api/reports');
      state.reports = data.reports;
      window.latestWeekly = data.latest_weekly;
      window.latestTrip = data.latest_trip;
      const task = state.task || 'weekly';
      if (!options.preserveSelection) {
        state.selected = task === 'weekly' ? data.latest_weekly : data.latest_trip;
        el('mailKind').value = task;
      }
      setTask(task);
      renderReports();
      renderHistoryReports();
      if (!options.preserveSelection && state.selected) {
        await loadDraft(task, state.selected);
      }
    }

    async function loadAdminConfig() {
      if (!state.user?.is_admin) return;
      const data = await api('/api/admin-config');
      el('configApiUrl').value = data.assistant_api_url || '';
      el('configModel').value = data.assistant_model || 'MiniMax-M2.7';
      renderModelOptions([data.assistant_model || 'MiniMax-M2.7'], data.assistant_model || 'MiniMax-M2.7');
      el('configPrompt').value = data.assistant_prompt || defaultAssistantPrompt;
      el('configApiKey').value = '';
      el('configKeyHint').textContent = 'API Key 状态：' + (data.assistant_api_key_masked || '未配置');
      el('configSmtpHost').value = data.smtp_host || 'smtp.263.net';
      el('configSmtpPort').value = data.smtp_port || 465;
      el('configSmtpTls').checked = !!data.smtp_tls;
      el('configSmtpSsl').checked = !!data.smtp_ssl;
      el('configImapHost').value = data.imap_host || 'imap.263.net';
      el('configImapPort').value = data.imap_port || 993;
      el('configImapSsl').checked = !!data.imap_ssl;
      el('newUserRoleBox').style.display = state.user?.is_superadmin ? 'grid' : 'none';
      await loadUserList();
    }
    async function loadUserList() {
      if (!state.user?.is_admin) return;
      try {
        const data = await api('/api/admin-users-list');
        renderUsers(data.users || []);
      } catch (err) {
        el('userList').innerHTML = '<div class="upload-item">加载用户列表失败</div>';
      }
    }

    async function loadMailConfig() {
      const data = await api('/api/mail-config');
      const ref = data.reference || {};
      const setVal = (id, val, refVal) => {
        const node = el(id);
        node.value = val || '';
        node.placeholder = refVal || '';
      };
      setVal('mailUserEmail', data.user_email, ref.user_email);
      setVal('mailSmtpFrom', data.smtp_from, ref.smtp_from);
      setVal('mailSmtpHost', data.smtp_host, ref.smtp_host);
      setVal('mailSmtpPort', data.smtp_port, ref.smtp_port);
      setVal('mailSmtpUser', data.smtp_user, ref.smtp_user);
      el('mailSmtpPassword').value = '';
      el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (data.smtp_password_masked || '未配置');
      el('mailSmtpTls').checked = data.smtp_tls !== false;
      el('mailSmtpSsl').checked = data.smtp_ssl === true;
      setVal('mailImapHost', data.imap_host, ref.imap_host);
      setVal('mailImapUser', data.imap_user, ref.imap_user);
      el('mailImapPassword').value = '';
      el('mailImapPasswordHint').textContent = 'IMAP 密码/授权码状态：' + (data.imap_password_masked || '未配置');
      setVal('mailWeeklyTo', data.weekly_to, ref.weekly_to);
      setVal('mailWeeklyCc', data.weekly_cc, ref.weekly_cc);
      setVal('mailTripTo', data.trip_to, ref.trip_to);
      setVal('mailTripCc', data.trip_cc, ref.trip_cc);
      el('mailEmailSignature').value = data.email_signature || '';
      // 显示全局服务器配置
      el('mailSmtpHostDisplay').textContent = data.smtp_host || 'smtp.263.net';
      el('mailSmtpPortDisplay').textContent = (data.smtp_port || 465) + ' / ' + (data.smtp_ssl ? 'SSL' : 'TLS');
      el('mailImapHostDisplay').textContent = data.imap_host || 'imap.263.net';
      el('mailImapPortDisplay').textContent = (data.imap_port || 993) + ' / ' + (data.imap_ssl ? 'SSL' : 'TLS');
    }

    function mailConfigPayload() {
      return {
        user_email: el('mailUserEmail').value,
        smtp_from: el('mailSmtpFrom').value,
        smtp_user: el('mailSmtpUser').value,
        smtp_password: el('mailSmtpPassword').value,
        imap_user: el('mailImapUser').value,
        imap_password: el('mailImapPassword').value,
        weekly_to: el('mailWeeklyTo').value,
        weekly_cc: el('mailWeeklyCc').value,
        trip_to: el('mailTripTo').value,
        trip_cc: el('mailTripCc').value,
        email_signature: el('mailEmailSignature').value
      };
    }

    function textToHtml(text) {
      return escapeHtml(text || '').split('\\n').join('<br>');
    }

    function renderBodyPreview() {
      if (state.bodyHtml) {
        el('bodyPreview').innerHTML = state.bodyHtml;
      } else {
        el('bodyPreview').innerHTML = textToHtml(el('body').value || '暂无正文内容');
      }
    }

    function renderModelOptions(models, selected) {
      const unique = [...new Set((models || []).filter(Boolean))];
      if (!unique.includes(selected) && selected) unique.unshift(selected);
      el('configModelSelect').innerHTML = unique.map(model => `
        <option value="${escapeHtml(model)}" ${model === selected ? 'selected' : ''}>${escapeHtml(model)}</option>
      `).join('');
    }

    function renderUsers(users) {
      const roleLabel = (role) => {
        if (role === 'superadmin') return '超级管理员';
        if (role === 'admin') return '管理员';
        return '普通成员';
      };
      const isSuper = state.user?.is_superadmin;
      el('userList').innerHTML = (users || []).map(user => {
        const showActions = isSuper || user.role === 'member';
        const roleSelect = isSuper
          ? `<select class="user-role-select mini" data-user="${escapeHtml(user.username)}" style="margin-right:8px;">
              <option value="member" ${user.role === 'member' ? 'selected' : ''}>普通成员</option>
              <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>管理员</option>
              <option value="superadmin" ${user.role === 'superadmin' ? 'selected' : ''}>超级管理员</option>
            </select>`
          : `<span class="mini" style="margin-right:8px;color:var(--muted);">${roleLabel(user.role)}</span>`;
        const deleteBtn = showActions && user.username !== state.user?.username
          ? `<button class="mini danger delete-user" data-user="${escapeHtml(user.username)}" type="button">删除</button>`
          : '';
        return `
        <div class="user-item" style="grid-template-columns:minmax(0,1fr) auto auto;">
          <div>
            <strong>${escapeHtml(user.name || user.username)}</strong>
            <div class="history-meta">${escapeHtml(user.username)} · ${roleLabel(user.role)}</div>
          </div>
          <div>${roleSelect}</div>
          <div>${deleteBtn}</div>
        </div>
      `}).join('') || '<div class="upload-item">暂无用户。</div>';
      // 绑定删除按钮
      el('userList').querySelectorAll('.delete-user').forEach(btn => {
        btn.addEventListener('click', async () => {
          const username = btn.dataset.user;
          if (!confirm(`确定删除用户 ${username} 吗？`)) return;
          try {
            const result = await apiPost('/api/admin-users-delete', { username });
            renderUsers(result.users || []);
            el('configTestStatus').textContent = '用户已删除';
            el('configTestStatus').className = 'status ok';
          } catch (err) {
            el('configTestStatus').textContent = err.message;
            el('configTestStatus').className = 'status err';
          }
        });
      });
      // 绑定角色修改
      if (isSuper) {
        el('userList').querySelectorAll('.user-role-select').forEach(sel => {
          sel.addEventListener('change', async () => {
            const username = sel.dataset.user;
            const newRole = sel.value;
            try {
              const result = await apiPost('/api/admin-users-update', { username, role: newRole });
              renderUsers(result.users || []);
              el('configTestStatus').textContent = '权限已更新';
              el('configTestStatus').className = 'status ok';
            } catch (err) {
              el('configTestStatus').textContent = err.message;
              el('configTestStatus').className = 'status err';
              await loadUserList();
            }
          });
        });
      }
    }

    function renderMailbox(messages) {
      const box = el('mailboxList');
      box.innerHTML = (messages || []).length ? messages.map(item => `
        <div class="mailbox-item" data-uid="${escapeHtml(item.uid)}">
          <div class="mailbox-subject">${escapeHtml(item.subject || '无主题')}</div>
          <div class="mailbox-meta">${escapeHtml(item.from || '未知发件人')}</div>
          <div class="mailbox-meta">${escapeHtml(item.date || '')}</div>
          ${(item.attachments || []).length ? `<div class="mailbox-meta">${(item.attachments || []).length} 个附件</div>` : ''}
          <div class="mailbox-preview">${escapeHtml(item.preview || '暂无正文预览')}</div>
        </div>
      `).join('') : '<div class="upload-item">暂无邮件，或当前邮箱没有可读取的收件箱邮件。</div>';
      box.querySelectorAll('.mailbox-item').forEach(item => {
        item.addEventListener('click', () => loadMailDetail(item.dataset.uid));
      });
    }

    async function loadMailbox(forceRefresh = false) {
      if (!el('mailboxList')) return;
      el('mailboxList').innerHTML = `<div class="upload-item">${forceRefresh ? '正在刷新收件箱...' : '正在读取收件箱缓存...'}</div>`;
      el('mailDetail').textContent = '请选择左侧邮件查看详情。';
      try {
        const query = new URLSearchParams({ limit: el('mailboxLimit').value || '20' });
        if (forceRefresh) query.set('refresh', '1');
        const data = await api('/api/mailbox?' + query.toString());
        renderMailbox(data.messages || []);
        if (data.cached) {
          el('mailDetail').textContent = '已从本地缓存加载。需要最新邮件时点击“刷新”。';
        }
      } catch (err) {
        el('mailboxList').innerHTML = `<div class="upload-item">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadMailDetail(uid) {
      if (!uid) return;
      document.querySelectorAll('.mailbox-item').forEach(item => item.classList.toggle('active', item.dataset.uid === uid));
      el('mailDetail').textContent = '正在读取邮件详情...';
      try {
        const query = new URLSearchParams({ uid });
        const data = await api('/api/mailbox-detail?' + query.toString());
        const msg = data.message || {};
        const attachments = msg.attachments || [];
        const bodyHtml = msg.body_html
          ? `<div class="mail-detail-body">${msg.body_html}</div>`
          : `<div class="mail-detail-body plain">${escapeHtml(msg.body || msg.preview || '暂无可读取的文本正文')}</div>`;
        el('mailDetail').innerHTML = `
          <div class="mail-detail-head">
            <div class="mailbox-subject">${escapeHtml(msg.subject || '无主题')}</div>
            <div class="mailbox-meta">发件人：${escapeHtml(msg.from || '')}</div>
            <div class="mailbox-meta">收件人：${escapeHtml(msg.to || '')}</div>
            <div class="mailbox-meta">时间：${escapeHtml(msg.date || '')}</div>
            <div class="mail-attachment-list">
              ${attachments.length ? attachments.map(file => `
                <span class="mail-attachment">
                  <span class="icon" data-icon="paperclip"></span>
                  ${escapeHtml(file.name || '附件')}
                  ${file.size ? ` · ${formatFileSize(file.size)}` : ''}
                </span>
              `).join('') : '<span class="mailbox-meta">无附件</span>'}
            </div>
          </div>
          ${bodyHtml}
        `;
        renderIcons(el('mailDetail'));
      } catch (err) {
        el('mailDetail').textContent = err.message;
      }
    }

    function formatFileSize(bytes) {
      const size = Number(bytes || 0);
      if (size < 1024) return size + ' B';
      if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB';
      return (size / 1024 / 1024).toFixed(1) + ' MB';
    }

    function renderAssistantMailFiles() {
      const box = el('assistantMailFileList');
      box.innerHTML = state.assistantMailFiles.length ? state.assistantMailFiles.map((file, index) => `
        <div class="mail-file-item">
          <span>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</span>
          <button class="mini secondary remove-assistant-file" type="button" data-index="${index}">移除</button>
        </div>
      `).join('') : '<div class="mailbox-meta">未添加附件</div>';
      box.querySelectorAll('.remove-assistant-file').forEach(button => {
        button.addEventListener('click', () => {
          state.assistantMailFiles.splice(Number(button.dataset.index), 1);
          renderAssistantMailFiles();
        });
      });
    }

    function renderAssistantMailPreview() {
      el('assistantMailPreview').innerHTML = textToHtml(el('assistantMailBody').value || '暂无正文内容');
    }

    function clearAssistantMail() {
      el('assistantMailTo').value = '';
      el('assistantMailCc').value = '';
      el('assistantMailSubject').value = '';
      el('assistantMailBody').value = '';
      el('assistantMailFiles').value = '';
      state.assistantMailFiles = [];
      renderAssistantMailFiles();
      renderAssistantMailPreview();
      el('assistantMailStatus').textContent = '';
      el('assistantMailStatus').className = 'status';
    }

    function adminConfigPayload() {
      return {
        assistant_api_url: el('configApiUrl').value,
        assistant_api_key: el('configApiKey').value,
        assistant_model: el('configModel').value || el('configModelSelect').value,
        assistant_prompt: el('configPrompt').value,
      };
    }

    async function boot() {
      renderIcons();
      try {
        const session = await api('/api/session');
        defaultAssistantPrompt = session.assistant_prompt || defaultAssistantPrompt;
        if (session.authenticated) {
          applyUser(session.user);
          await loadReports();
        } else {
          applyUser(null);
        }
      } catch (err) {
        applyUser(null);
        el('loginStatus').textContent = err.message;
        el('loginStatus').className = 'status err';
      }
    }

    async function loadDraft(kind, name) {
      state.selected = name;
      renderReports();
      const query = new URLSearchParams({ kind, file: name || '' });
      const draft = await api('/api/draft?' + query.toString());
      el('to').value = draft.to || '';
      el('cc').value = draft.cc || '';
      el('subject').value = draft.subject || '';
      el('body').value = draft.body || '';
      state.bodyHtml = draft.body_html || '';
      renderBodyPreview();
      el('attachment').value = draft.attachment || '';
      if (draft.download_url) {
        el('downloadLink').href = draft.download_url;
        el('downloadLink').classList.remove('hidden');
      } else {
        el('downloadLink').classList.add('hidden');
      }
      el('preview').innerHTML = draft.preview_html || textToHtml(draft.preview || '暂无可预览内容');
      el('status').textContent = '';
      el('status').className = 'status';
      if (kind === 'weekly' && !state.weeklyPrefilled) {
        await loadWeeklyPrefill();
      }
      if (kind === 'trip' && !state.tripPrefilled) {
        await loadTripPrefill();
      }
    }

    async function loadWeeklyPrefill(force = false) {
      if (!force && state.weeklyPrefilled) return;
      if (force) clearSavedFormDraft('weekly');
      setDefaultWeeklyDates();
      const prefill = await api('/api/weekly-prefill');
      renderWorkRows('summary', prefill.summary_rows || []);
      renderWorkRows('follow', prefill.follow_rows || []);
      renderWorkRows('next', prefill.next_rows || []);
      state.weeklyPrefilled = true;
      const restored = force ? false : restoreSavedFormDraft('weekly');
      if (prefill.source) {
        el('status').textContent = restored ? '已恢复上次未生成的周报草稿。' : `已获取最新历史周报：${prefill.source}。上次“下周计划”已写入本次“本周工作内容”，重点工作已复制，下周计划保持为空。`;
        el('status').className = 'status ok';
      } else {
        el('status').textContent = '没有找到可用于预填的历史周报。';
        el('status').className = 'status err';
      }
      saveFormDraft();
    }

    async function loadTripPrefill(force = false) {
      if (!force && state.tripPrefilled) return;
      if (force) clearSavedFormDraft('trip');
      const prefill = await api('/api/trip-prefill');
      el('tripReporter').value = prefill.reporter || '周颖超';
      el('tripDepartment').value = prefill.department || '场景研究院';
      el('tripLocation').value = prefill.location || '';
      el('tripStart').value = prefill.trip_start || '';
      el('tripEnd').value = prefill.trip_end || '';
      el('tripPurpose').value = prefill.purpose || '';
      el('tripItinerary').value = prefill.itinerary || '';
      el('tripDetails').value = prefill.details || '';
      el('tripIssues').value = prefill.issues || '';
      el('tripSuggestions').value = prefill.suggestions || '';
      renderTripCards();
      state.tripPrefilled = true;
      const restored = force ? false : restoreSavedFormDraft('trip');
      if (prefill.source) {
        el('status').textContent = restored ? '已恢复上次未生成的出差报告草稿。' : `已获取最新历史出差报告：${prefill.source}，并自动填入当前模板。`;
        el('status').className = 'status ok';
      } else {
        el('status').textContent = '没有找到可用于预填的历史出差报告。';
        el('status').className = 'status err';
      }
      saveFormDraft();
    }

    el('mailKind').addEventListener('change', async () => {
      const kind = el('mailKind').value;
      const generated = state.reports.find(r => r.kind === kind && r.generated);
      const latest = generated?.name || (kind === 'weekly' ? window.latestWeekly : window.latestTrip);
      await loadDraft(kind, latest || '');
    });

    el('refreshMailbox').addEventListener('click', () => loadMailbox(true));
    el('mailboxLimit').addEventListener('change', loadMailbox);
    el('assistantMailBody').addEventListener('input', renderAssistantMailPreview);
    el('assistantMailFiles').addEventListener('change', () => {
      state.assistantMailFiles = [...el('assistantMailFiles').files].map(file => ({
        file,
        name: file.name,
        size: file.size,
        type: file.type || 'application/octet-stream'
      }));
      renderAssistantMailFiles();
    });
    el('clearAssistantMail').addEventListener('click', clearAssistantMail);
    el('sendAssistantMail').addEventListener('click', async () => {
      el('assistantMailStatus').textContent = '正在发送邮件...';
      el('assistantMailStatus').className = 'status';
      try {
        const attachments = [];
        for (const item of state.assistantMailFiles) {
          attachments.push({
            name: item.name,
            type: item.type,
            content: await readFileAsBase64(item.file)
          });
        }
        const result = await api('/api/mail-send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            to: el('assistantMailTo').value,
            cc: el('assistantMailCc').value,
            subject: el('assistantMailSubject').value,
            body: el('assistantMailBody').value,
            attachments
          })
        });
        el('assistantMailStatus').textContent = result.message || '邮件已发送。';
        el('assistantMailStatus').className = 'status ok';
      } catch (err) {
        el('assistantMailStatus').textContent = err.message;
        el('assistantMailStatus').className = 'status err';
      }
    });

    el('generate').addEventListener('click', async () => {
      const kind = el('kind').value;
      if (!['weekly', 'trip'].includes(kind) || !['weekly', 'trip'].includes(state.task)) {
        el('generateToolbar').classList.add('hidden');
        return;
      }
      syncWeeklyPeriod();
      el('status').textContent = '正在按模板生成文件...';
      el('status').className = 'status';
      const payload = kind === 'weekly' ? {
        kind,
        period: el('weeklyPeriod').value,
        weekly_summary: collectWorkRows('summary'),
        weekly_follow: collectWorkRows('follow'),
        weekly_next: collectWorkRows('next')
      } : {
        kind,
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
      try {
        const result = await api('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        clearSavedFormDraft(kind);
        await loadReports();
        el('kind').value = kind;
        await loadDraft(kind, result.file);
        el('status').textContent = '已生成标准文件，并设为当前邮件附件：' + result.file;
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    });

    document.querySelectorAll('.task-card').forEach(card => {
      card.addEventListener('click', async () => {
        const task = card.dataset.task;
        state.subTab = 'edit';
        setTask(task);
        if (task === 'weekly') {
          await loadWeeklyPrefill();
          const generated = state.reports.find(r => r.kind === 'weekly' && r.generated);
          const latest = generated?.name || window.latestWeekly;
          await loadDraft('weekly', latest || '');
        } else if (task === 'trip') {
          await loadTripPrefill();
          const generated = state.reports.find(r => r.kind === 'trip' && r.generated);
          const latest = generated?.name || window.latestTrip;
          await loadDraft('trip', latest || '');
        } else if (task === 'mailconfig') {
          loadMailConfig();
        } else if (task === 'mailassistant') {
          loadMailbox();
        } else if (task === 'config') {
          await loadAdminConfig();
        }
      });
    });

    document.querySelectorAll('.sub-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        setSubTab(tab.dataset.sub);
      });
    });

    el('loginButton').addEventListener('click', async () => {
      el('loginStatus').textContent = '正在登录...';
      el('loginStatus').className = 'status';
      try {
        const result = await api('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: el('loginUser').value, password: el('loginPass').value })
        });
        defaultAssistantPrompt = result.assistant_prompt || defaultAssistantPrompt;
        applyUser(result.user);
        await loadReports();
      } catch (err) {
        el('loginStatus').textContent = err.message;
        el('loginStatus').className = 'status err';
      }
    });

    el('changePassButton').addEventListener('click', () => {
      el('passOld').value = '';
      el('passNew').value = '';
      el('passConfirm').value = '';
      el('passStatus').textContent = '';
      el('passModal').classList.remove('hidden');
    });
    el('passSave').addEventListener('click', async () => {
      const oldPass = el('passOld').value;
      const newPass = el('passNew').value;
      const confirm = el('passConfirm').value;
      if (!oldPass || !newPass) {
        el('passStatus').textContent = '请填写原密码和新密码';
        el('passStatus').className = 'status err';
        return;
      }
      if (newPass.length < 4) {
        el('passStatus').textContent = '新密码至少 4 位';
        el('passStatus').className = 'status err';
        return;
      }
      if (newPass !== confirm) {
        el('passStatus').textContent = '两次输入的新密码不一致';
        el('passStatus').className = 'status err';
        return;
      }
      try {
        await apiPost('/api/change-password', { old_password: oldPass, new_password: newPass });
        el('passStatus').textContent = '密码修改成功，请重新登录';
        el('passStatus').className = 'status ok';
        setTimeout(() => { el('passModal').classList.add('hidden'); }, 1500);
      } catch (err) {
        el('passStatus').textContent = err.message;
        el('passStatus').className = 'status err';
      }
    });
    el('logoutButton').addEventListener('click', async () => {
      await api('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      applyUser(null);
    });

    el('saveConfig').addEventListener('click', async () => {
      el('status').textContent = '正在保存系统配置...';
      el('status').className = 'status';
      try {
        const result = await api('/api/admin-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        defaultAssistantPrompt = result.config.assistant_prompt || defaultAssistantPrompt;
        el('configApiKey').value = '';
        el('configKeyHint').textContent = 'API Key 状态：' + (result.config.assistant_api_key_masked || '未配置');
        el('status').textContent = '系统配置已保存。';
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    });

    el('saveServerConfig').addEventListener('click', async () => {
      el('configServerStatus').textContent = '正在保存邮件服务器配置...';
      el('configServerStatus').className = 'status';
      try {
        await apiPost('/api/server-config', {
          smtp_host: el('configSmtpHost').value,
          smtp_port: el('configSmtpPort').value,
          smtp_tls: el('configSmtpTls').checked,
          smtp_ssl: el('configSmtpSsl').checked,
          imap_host: el('configImapHost').value,
          imap_port: el('configImapPort').value,
          imap_ssl: el('configImapSsl').checked,
        });
        el('configServerStatus').textContent = '邮件服务器配置已保存（对所有用户生效）。';
        el('configServerStatus').className = 'status ok';
      } catch (err) {
        el('configServerStatus').textContent = err.message;
        el('configServerStatus').className = 'status err';
      }
    });

    el('saveMailConfig').addEventListener('click', async () => {
      el('mailConfigStatus').textContent = '正在保存邮件配置...';
      el('mailConfigStatus').className = 'status';
      try {
        const result = await api('/api/mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mailConfigPayload())
        });
        el('mailSmtpPassword').value = '';
        el('mailImapPassword').value = '';
        el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (result.mail_config.smtp_password_masked || '未配置');
        el('mailImapPasswordHint').textContent = 'IMAP 密码/授权码状态：' + (result.mail_config.imap_password_masked || '未配置');
        el('mailConfigStatus').textContent = '邮件配置已保存。';
        el('mailConfigStatus').className = 'status ok';
      } catch (err) {
        el('mailConfigStatus').textContent = err.message;
        el('mailConfigStatus').className = 'status err';
      }
    });

    el('testMailConfig').addEventListener('click', async () => {
      el('mailConfigStatus').textContent = '正在测试邮箱配置...';
      el('mailConfigStatus').className = 'status';
      try {
        await api('/api/mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mailConfigPayload())
        });
        const result = await api('/api/test-mail-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        el('mailSmtpPassword').value = '';
        el('mailImapPassword').value = '';
        el('mailConfigStatus').textContent = result.message || '邮箱配置测试成功。';
        el('mailConfigStatus').className = 'status ok';
        await loadMailConfig();
      } catch (err) {
        el('mailConfigStatus').textContent = err.message;
        el('mailConfigStatus').className = 'status err';
      }
    });

    el('configModelSelect').addEventListener('change', () => {
      el('configModel').value = el('configModelSelect').value;
    });

    el('loadModels').addEventListener('click', async () => {
      el('configTestStatus').textContent = '正在获取模型列表...';
      el('configTestStatus').className = 'status';
      try {
        const result = await api('/api/admin-models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        renderModelOptions(result.models, el('configModel').value || result.models[0]);
        el('configModel').value = el('configModelSelect').value;
        el('configTestStatus').textContent = result.warning || `已获取 ${result.models.length} 个模型。`;
        el('configTestStatus').className = result.warning ? 'status err' : 'status ok';
      } catch (err) {
        el('configTestStatus').textContent = err.message;
        el('configTestStatus').className = 'status err';
      }
    });

    el('testModel').addEventListener('click', async () => {
      el('configTestStatus').textContent = '正在测试 API Key 和模型...';
      el('configTestStatus').className = 'status';
      try {
        const result = await api('/api/admin-test-model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(adminConfigPayload())
        });
        el('configTestStatus').textContent = `测试成功：${result.model} 返回 ${result.message}`;
        el('configTestStatus').className = 'status ok';
      } catch (err) {
        el('configTestStatus').textContent = '测试失败：' + err.message;
        el('configTestStatus').className = 'status err';
      }
    });

    el('addUser').addEventListener('click', async () => {
      const isSuper = state.user?.is_superadmin;
      el('configTestStatus').textContent = '正在新增用户...';
      el('configTestStatus').className = 'status';
      try {
        const payload = {
          username: el('newUserName').value,
          password: el('newUserPassword').value,
          name: el('newDisplayName').value
        };
        if (isSuper) payload.role = el('newUserRole').value;
        const result = await apiPost('/api/admin-users', payload);
        renderUsers(result.users || []);
        el('newUserName').value = '';
        el('newDisplayName').value = '';
        el('newUserPassword').value = '';
        el('configTestStatus').textContent = '用户已新增。';
        el('configTestStatus').className = 'status ok';
      } catch (err) {
        el('configTestStatus').textContent = err.message;
        el('configTestStatus').className = 'status err';
      }
    });

    el('addSummary').addEventListener('click', () => addWorkRow('summary'));
    el('addFollow').addEventListener('click', () => addWorkRow('follow'));
    el('addNext').addEventListener('click', () => addWorkRow('next'));
    el('loadLatestWeekly').addEventListener('click', () => loadWeeklyPrefill(true));
    el('loadLatestTrip').addEventListener('click', () => loadTripPrefill(true));
    el('weeklyStart').addEventListener('change', () => {
      syncWeeklyPeriod();
      el('diarySumStart').value = el('weeklyStart').value;
    });
    el('weeklyEnd').addEventListener('change', () => {
      syncWeeklyPeriod();
      el('diarySumEnd').value = el('weeklyEnd').value;
    });
    window.addEventListener('beforeunload', () => {
      saveCurrentModal();
      saveFormDraft();
    });
    el('historyKind').addEventListener('change', renderHistoryReports);
    el('profileButton').addEventListener('click', openProfileModal);
    el('profileClose').addEventListener('click', closeProfileModal);
    el('profileModal').addEventListener('click', event => {
      if (event.target === el('profileModal')) closeProfileModal();
    });
    el('profileAvatarFile').addEventListener('change', () => {
      const file = el('profileAvatarFile').files[0];
      if (file) el('profileAvatarPreview').src = URL.createObjectURL(file);
    });
    el('profileUseAssistantAvatar').addEventListener('click', () => saveProfile('assistant'));
    el('profileSave').addEventListener('click', () => saveProfile());

    el('uploadButton').addEventListener('click', async () => {
      const selected = [...el('uploadFiles').files];
      if (!selected.length) {
        el('status').textContent = '请先选择要上传的历史报告文件。';
        el('status').className = 'status err';
        return;
      }
      el('uploadButton').disabled = true;
      el('uploadButton').textContent = '上传中...';
      el('status').textContent = '正在读取并上传文件...';
      el('status').className = 'status';
      try {
        const files = [];
        for (const file of selected) {
          files.push({ name: file.name, data: await readFileAsBase64(file) });
        }
        const result = await api('/api/upload-history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: el('uploadKind').value, files })
        });
        el('uploadList').innerHTML = result.uploaded.map(item => `
          <div class="upload-item">已上传：${escapeHtml(item.name)}</div>
        `).join('');
        el('status').textContent = `上传完成，共 ${result.uploaded.length} 个文件。`;
        el('status').className = 'status ok';
        el('uploadFiles').value = '';
        await loadReports({ preserveSelection: true });
        if (state.task === 'weekly' || state.task === 'trip') {
          renderHistoryReports();
          renderReports();
        } else {
          setTask('weekly');
        }
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      } finally {
        el('uploadButton').disabled = false;
        el('uploadButton').textContent = '上传到历史报告库';
      }
    });

    // ===== 工作日记 =====
    function initDiaryPanel() {
      const today = new Date().toISOString().split('T')[0];
      el('diaryDate').value = today;
      loadDiaryToForm(today);
      renderDiaryList();
    }
    function setDiaryTab(tab) {
      document.querySelectorAll('.diary-tab').forEach(t => t.classList.toggle('active', t.dataset.diarytab === tab));
      el('diaryWriteView').classList.toggle('hidden', tab !== 'write');
      el('diaryBrowseView').classList.toggle('hidden', tab !== 'browse');
      if (tab === 'browse') renderDiaryList();
    }
    async function loadDiaryToForm(dateStr) {
      try {
        const data = await api('/api/diary/get?date=' + encodeURIComponent(dateStr));
        const d = data.diary || {};
        el('diaryTodayWork').value = d.today_work || '';
        el('diaryTomorrowPlan').value = d.tomorrow_plan || '';
        el('diaryThoughts').value = d.thoughts || '';
      } catch (err) {
        el('diaryTodayWork').value = '';
        el('diaryTomorrowPlan').value = '';
        el('diaryThoughts').value = '';
      }
    }
    async function saveDiary() {
      const payload = {
        date: el('diaryDate').value,
        today_work: el('diaryTodayWork').value,
        tomorrow_plan: el('diaryTomorrowPlan').value,
        thoughts: el('diaryThoughts').value,
      };
      if (!payload.date) {
        el('diaryStatus').textContent = '请选择日期';
        el('diaryStatus').className = 'status err';
        return;
      }
      try {
        el('diaryStatus').textContent = '保存中...';
        el('diaryStatus').className = 'status';
        await apiPost('/api/diary/save', payload);
        el('diaryStatus').textContent = '保存成功';
        el('diaryStatus').className = 'status ok';
        setTimeout(() => { el('diaryStatus').textContent = ''; }, 2000);
      } catch (err) {
        el('diaryStatus').textContent = err.message;
        el('diaryStatus').className = 'status err';
      }
    }
    async function renderDiaryList() {
      const list = el('diaryList');
      list.innerHTML = '<div class="diary-empty">加载中...</div>';
      try {
        const data = await api('/api/diary/list?limit=100');
        const items = data.diaries || [];
        if (!items.length) {
          list.innerHTML = '<div class="diary-empty">暂无日记，去记录第一篇吧～</div>';
          return;
        }
        list.innerHTML = items.map(item => `
          <div class="diary-item" data-date="${escapeHtml(item.date)}">
            <div class="diary-item-date">${escapeHtml(item.date)}</div>
            <div class="diary-item-preview">${escapeHtml(item.today_work_preview || '无内容')}</div>
            <span class="icon" data-icon="chevron-right"></span>
          </div>
        `).join('');
        renderIcons(list);
        list.querySelectorAll('.diary-item').forEach(item => {
          item.addEventListener('click', () => openDiaryDetail(item.dataset.date));
        });
      } catch (err) {
        list.innerHTML = `<div class="diary-empty">加载失败：${escapeHtml(err.message)}</div>`;
      }
    }
    async function openDiaryDetail(dateStr) {
      try {
        const data = await api('/api/diary/get?date=' + encodeURIComponent(dateStr));
        const d = data.diary || {};
        el('diaryDetailDate').textContent = (d.date || dateStr) + ' 日记详情';
        el('diaryDetailToday').textContent = d.today_work || '（无内容）';
        el('diaryDetailTomorrow').textContent = d.tomorrow_plan || '（无内容）';
        el('diaryDetailThoughts').textContent = d.thoughts || '（无内容）';
        el('diaryDetailEdit').onclick = () => {
          el('diaryDetailModal').classList.add('hidden');
          setDiaryTab('write');
          el('diaryDate').value = dateStr;
          loadDiaryToForm(dateStr);
        };
        el('diaryDetailDelete').onclick = async () => {
          if (!confirm('确定删除 ' + dateStr + ' 的日记吗？')) return;
          try {
            await apiPost('/api/diary/delete', { date: dateStr });
            el('diaryDetailModal').classList.add('hidden');
            renderDiaryList();
          } catch (err) {
            alert('删除失败：' + err.message);
          }
        };
        el('diaryDetailModal').classList.remove('hidden');
      } catch (err) {
        alert('读取日记失败：' + err.message);
      }
    }

    // 日记事件绑定
    document.querySelectorAll('.diary-tab').forEach(tab => {
      tab.addEventListener('click', () => setDiaryTab(tab.dataset.diarytab));
    });
    el('diaryLoadToday').addEventListener('click', () => {
      const today = new Date().toISOString().split('T')[0];
      el('diaryDate').value = today;
      loadDiaryToForm(today);
    });
    el('diaryDate').addEventListener('change', () => loadDiaryToForm(el('diaryDate').value));
    el('diarySaveButton').addEventListener('click', saveDiary);
    el('diaryClearButton').addEventListener('click', () => {
      el('diaryTodayWork').value = '';
      el('diaryTomorrowPlan').value = '';
      el('diaryThoughts').value = '';
      el('diaryStatus').textContent = '';
    });
    function openDiaryEditor(fieldId, title) {
      const value = el(fieldId).value;
      openModal(title, [
        { key: 'content', label: title, multiline: true, value: value }
      ], (values) => {
        el(fieldId).value = values.content || '';
        saveDiary();
      });
    }
    el('diaryTodayWork').addEventListener('click', () => openDiaryEditor('diaryTodayWork', '今日工作内容'));
    el('diaryTomorrowPlan').addEventListener('click', () => openDiaryEditor('diaryTomorrowPlan', '明日工作计划'));
    el('diaryThoughts').addEventListener('click', () => openDiaryEditor('diaryThoughts', '思路与想法'));
    el('diaryAgentButton').addEventListener('click', () => startAgent('diary'));
    el('diaryRefreshList').addEventListener('click', renderDiaryList);

    // 工作日记智能总结 → 周报
    async function summarizeDiariesForWeekly() {
      const start = el('diarySumStart').value;
      const end = el('diarySumEnd').value;
      if (!start || !end) {
        el('status').textContent = '请选择日记日期范围';
        el('status').className = 'status err';
        return;
      }
      if (start > end) {
        el('status').textContent = '开始日期不能晚于结束日期';
        el('status').className = 'status err';
        return;
      }
      el('status').textContent = '正在总结工作日记，请稍候...';
      el('status').className = 'status';
      try {
        const data = await apiPost('/api/diary/summarize', { start_date: start, end_date: end });
        if (!data.ok) {
          el('status').textContent = data.error || '总结失败';
          el('status').className = 'status err';
          return;
        }
        if (data.mode === 'empty') {
          el('status').textContent = data.warning || '该范围内无日记';
          el('status').className = 'status err';
          return;
        }
        parseAndApplyDiarySummary(data.summary || '');
        el('status').textContent = '日记总结已应用到周报，请检查并调整';
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    }
    function parseAndApplyDiarySummary(summary) {
      // 解析 AI 返回的总结文本，按三个部分填充
      const sections = { '本周工作总结': [], '重点工作跟进': [], '下周工作计划': [] };
      let current = null;
      summary.split('\\n').forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) return;
        if (trimmed.includes('本周工作总结') || trimmed.includes('本周工作')) {
          current = '本周工作总结';
        } else if (trimmed.includes('重点工作跟进') || trimmed.includes('重点工作')) {
          current = '重点工作跟进';
        } else if (trimmed.includes('下周工作计划') || trimmed.includes('下周工作')) {
          current = '下周工作计划';
        } else if (current && /^[\d一二三四五六七八九十]+[.、.．\s]/.test(trimmed)) {
          const content = trimmed.replace(/^[\d一二三四五六七八九十]+[.、.．\s]+/, '').trim();
          if (content) sections[current].push(content);
        } else if (current && trimmed.startsWith('- ')) {
          const content = trimmed.replace(/^- /, '').trim();
          if (content) sections[current].push(content);
        } else if (current && trimmed.startsWith('* ')) {
          const content = trimmed.replace(/^\* /, '').trim();
          if (content) sections[current].push(content);
        }
      });
      // 填充到周报表单
      const map = {
        '本周工作总结': 'summary',
        '重点工作跟进': 'follow',
        '下周工作计划': 'next'
      };
      Object.entries(map).forEach(([title, key]) => {
        const items = sections[title] || [];
        // 清空现有
        state[`weekly_${key}`] = [];
        items.forEach(content => {
          state[`weekly_${key}`].push({
            category: '',
            content: content,
            ...(key === 'summary' ? { status: '已完成' } : key === 'follow' ? { progress: '推进中' } : { difficulty: '正常' })
          });
        });
        renderWeeklyRows(key);
      });
      saveFormDraft();
    }
    el('diarySummarizeBtn').addEventListener('click', summarizeDiariesForWeekly);

    // ===== 金点子论坛 =====
    function forumSourceName(source) {
      if (source === 'ai') return '智能体';
      return '成员发起';
    }
    async function loadForumTopics(selectFirst = false) {
      const list = el('forumTopicList');
      list.innerHTML = '<div class="forum-empty">加载话题中...</div>';
      try {
        const data = await api('/api/forum/topics');
        const topics = data.topics || [];
        el('forumTopicCount').textContent = `${topics.length} 个话题`;
        if (!topics.length) {
          list.innerHTML = '<div class="forum-empty">暂无话题，先发起一个金点子吧。</div>';
          el('forumTopicDetail').innerHTML = '<div class="forum-empty">选择一个话题查看详情和讨论。</div>';
          return;
        }
        list.innerHTML = topics.map(topic => `
          <div class="forum-topic-item ${state.forumSelected === topic.id ? 'active' : ''}" data-id="${escapeHtml(topic.id)}">
            <div class="forum-topic-title">${escapeHtml(topic.title)}</div>
            <div class="forum-topic-meta">${escapeHtml(forumSourceName(topic.source))} · ${escapeHtml(topic.author || '')} · ${escapeHtml(topic.created_at || '')}</div>
            <div class="forum-topic-stats">
              <span class="forum-stat">热度 ${topic.heat || 0}</span>
              <span class="forum-stat">赞 ${topic.like_count || 0}</span>
              <span class="forum-stat">评 ${topic.comment_count || 0}</span>
              <span class="forum-stat">看 ${topic.view_count || 0}</span>
            </div>
          </div>
        `).join('');
        list.querySelectorAll('.forum-topic-item').forEach(item => {
          item.addEventListener('click', () => openForumTopic(item.dataset.id));
        });
        if (selectFirst || !state.forumSelected) {
          openForumTopic(topics[0].id);
        }
      } catch (err) {
        list.innerHTML = `<div class="forum-empty">加载失败：${escapeHtml(err.message)}</div>`;
      }
    }
    async function openForumTopic(topicId) {
      state.forumSelected = topicId;
      state.forumCommentPage = 1;
      document.querySelectorAll('.forum-topic-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id === topicId);
      });
      const detail = el('forumTopicDetail');
      detail.innerHTML = '<div class="forum-empty">读取话题中...</div>';
      try {
        const data = await api('/api/forum/topic?id=' + encodeURIComponent(topicId));
        renderForumTopic(data.topic);
      } catch (err) {
        detail.innerHTML = `<div class="forum-empty">读取失败：${escapeHtml(err.message)}</div>`;
      }
    }
    function forumCommentTree(comments) {
      const byParent = {};
      comments.forEach(comment => {
        const key = comment.parent_id || '';
        (byParent[key] ||= []).push(comment);
      });
      return byParent;
    }
    function forumCommentHtml(comment, children = []) {
      return `
        <div class="forum-comment ${comment.parent_id ? 'reply' : ''}" data-comment-id="${escapeHtml(comment.id || '')}" data-author="${escapeHtml(comment.author || '')}">
          <div class="forum-comment-meta">${escapeHtml(comment.author || '')} · ${escapeHtml(comment.created_at || '')}</div>
          <div class="forum-comment-body">${escapeHtml(comment.content || '')}</div>
          <div class="forum-comment-actions">
            <button class="mini secondary forum-reply-button" type="button">回复</button>
          </div>
        </div>
        ${children.map(child => forumCommentHtml(child, [])).join('')}`;
    }
    function renderForumTopic(topic) {
      const comments = topic.comments || [];
      const pageSize = 10;
      const tree = forumCommentTree(comments);
      const topComments = tree[''] || [];
      const totalPages = Math.max(1, Math.ceil(topComments.length / pageSize));
      state.forumCommentPage = Math.min(Math.max(1, state.forumCommentPage || 1), totalPages);
      const pageTopComments = topComments.slice((state.forumCommentPage - 1) * pageSize, state.forumCommentPage * pageSize);
      el('forumTopicDetail').innerHTML = `
        <div class="forum-topic-title" style="font-size:18px;">${escapeHtml(topic.title)}</div>
        <div class="forum-topic-meta">${escapeHtml(forumSourceName(topic.source))} · ${escapeHtml(topic.author || '')} · ${escapeHtml(topic.created_at || '')}</div>
        <div class="forum-topic-stats">
          <span class="forum-stat">热度 ${topic.heat || 0}</span>
          <span class="forum-stat">点赞 ${topic.like_count || 0}</span>
          <span class="forum-stat">评论 ${topic.comment_count || 0}</span>
          <span class="forum-stat">浏览 ${topic.view_count || 0}</span>
        </div>
        <div class="forum-topic-body" style="margin-top:12px;">${escapeHtml(topic.body)}</div>
        <div class="toolbar">
          <button type="button" id="forumLikeButton" class="secondary"><span class="icon" data-icon="thumbs-up"></span> 点赞</button>
        </div>
        <div class="forum-comments">
          ${pageTopComments.length ? pageTopComments.map(comment => forumCommentHtml(comment, tree[comment.id] || [])).join('') : '<div class="forum-empty">还没有讨论，来写第一条观点。</div>'}
        </div>
        <div class="forum-pagination">
          <button type="button" class="mini secondary" id="forumPrevPage" ${state.forumCommentPage <= 1 ? 'disabled' : ''}>上一页</button>
          <span>第 ${state.forumCommentPage} / ${totalPages} 页 · 共 ${comments.length} 条评论</span>
          <button type="button" class="mini secondary" id="forumNextPage" ${state.forumCommentPage >= totalPages ? 'disabled' : ''}>下一页</button>
        </div>
        <label>参与讨论</label>
        <textarea id="forumCommentInput" placeholder="写下你的观点、建议、风险提醒或下一步行动..."></textarea>
        <input id="forumCommentParent" type="hidden" value="" />
        <div class="toolbar">
          <button type="button" id="forumCommentButton">发布讨论</button>
          <button type="button" class="secondary" id="forumAiCommentButton"><span class="icon" data-icon="bot"></span> AI 潜水评论</button>
          <span id="forumCommentStatus" class="status"></span>
        </div>
      `;
      renderIcons(el('forumTopicDetail'));
      el('forumLikeButton').addEventListener('click', async () => {
        try {
          const result = await apiPost('/api/forum/like', { topic_id: topic.id });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
      el('forumPrevPage').addEventListener('click', () => {
        state.forumCommentPage -= 1;
        renderForumTopic(topic);
      });
      el('forumNextPage').addEventListener('click', () => {
        state.forumCommentPage += 1;
        renderForumTopic(topic);
      });
      document.querySelectorAll('.forum-reply-button').forEach(button => {
        button.addEventListener('click', () => {
          const item = button.closest('.forum-comment');
          el('forumCommentParent').value = item.dataset.commentId || '';
          el('forumCommentInput').value = `回复 ${item.dataset.author || '成员'}：`;
          el('forumCommentInput').focus();
        });
      });
      el('forumCommentButton').addEventListener('click', async () => {
        const content = el('forumCommentInput').value.trim();
        if (!content) {
          el('forumCommentStatus').textContent = '请先填写讨论内容';
          el('forumCommentStatus').className = 'status err';
          return;
        }
        try {
          el('forumCommentStatus').textContent = '发布中...';
          el('forumCommentStatus').className = 'status';
          const result = await apiPost('/api/forum/comment', { topic_id: topic.id, content, parent_id: el('forumCommentParent').value });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
      el('forumAiCommentButton').addEventListener('click', async () => {
        try {
          el('forumCommentStatus').textContent = 'AI 潜水员正在读帖...';
          el('forumCommentStatus').className = 'status';
          const result = await apiPost('/api/forum/ai-comment', { topic_id: topic.id });
          renderForumTopic(result.topic);
          loadForumTopics();
        } catch (err) {
          el('forumCommentStatus').textContent = err.message;
          el('forumCommentStatus').className = 'status err';
        }
      });
    }
    el('forumCreateButton').addEventListener('click', async () => {
      const payload = { title: el('forumTitle').value, body: el('forumBody').value };
      try {
        el('forumCreateStatus').textContent = '发布中...';
        el('forumCreateStatus').className = 'status';
        const result = await apiPost('/api/forum/create', payload);
        el('forumTitle').value = '';
        el('forumBody').value = '';
        el('forumCreateStatus').textContent = '话题已发布';
        el('forumCreateStatus').className = 'status ok';
        state.forumSelected = result.topic.id;
        await loadForumTopics();
        openForumTopic(result.topic.id);
      } catch (err) {
        el('forumCreateStatus').textContent = err.message;
        el('forumCreateStatus').className = 'status err';
      }
    });
    el('forumRefreshButton').addEventListener('click', () => loadForumTopics());
    el('forumToggleCreate').addEventListener('click', () => {
      const panel = el('forumCreatePanel');
      const hidden = panel.classList.toggle('hidden');
      el('forumToggleCreate').textContent = hidden ? '发起话题' : '收起发起';
    });
    el('forumAiButton').addEventListener('click', async () => {
      try {
        el('forumAiStatus').textContent = '智能体正在起题...';
        el('forumAiStatus').className = 'status';
        const files = [];
        for (const file of [...el('forumAiFiles').files]) {
          files.push({ name: file.name, data: await readFileAsBase64(file) });
        }
        const result = await apiPost('/api/forum/ai-topic', {
          seed: el('forumAiSeed').value,
          chat: el('forumAiChat').value,
          files
        });
        el('forumAiSeed').value = '';
        el('forumAiChat').value = '';
        el('forumAiFiles').value = '';
        el('forumAiStatus').textContent = '智能话题已发布';
        el('forumAiStatus').className = 'status ok';
        state.forumSelected = result.topic.id;
        await loadForumTopics();
        openForumTopic(result.topic.id);
      } catch (err) {
        el('forumAiStatus').textContent = err.message;
        el('forumAiStatus').className = 'status err';
      }
    });

    // ===== 每日资讯 =====
    function renderNewsSources(sources = []) {
      const box = el('newsSources');
      const rows = sources.length ? sources : [{ name: '', url: '' }];
      box.innerHTML = rows.map((source, index) => `
        <div class="news-source-row" data-index="${index}">
          <input class="news-source-name" placeholder="名称" value="${escapeHtml(source.name || '')}" />
          <input class="news-source-url" placeholder="https://example.com/news" value="${escapeHtml(source.url || '')}" />
          <button class="mini danger news-remove-source" type="button">删除</button>
        </div>
      `).join('');
      box.querySelectorAll('.news-remove-source').forEach(button => {
        button.addEventListener('click', () => {
          button.closest('.news-source-row').remove();
          if (!box.querySelector('.news-source-row')) renderNewsSources();
        });
      });
    }
    function collectNewsSources() {
      return [...document.querySelectorAll('.news-source-row')].map(row => ({
        name: row.querySelector('.news-source-name').value.trim(),
        url: row.querySelector('.news-source-url').value.trim()
      })).filter(item => item.url);
    }
    function renderNewsIssue(issue) {
      if (!issue) {
        el('newsTitle').textContent = '暂无每日资讯';
        el('newsMeta').textContent = state.user?.is_superadmin ? '配置资讯源后生成今日简报。' : '暂无今日简报，请稍后刷新。';
        el('newsSummary').textContent = '暂无摘要。';
        el('newsItems').innerHTML = '<div class="forum-empty">暂无资讯内容。</div>';
        el('newsKeywords').innerHTML = '';
        return;
      }
      el('newsTitle').textContent = issue.title || `${issue.date || ''} 轨道交通每日资讯`;
      el('newsMeta').textContent = `${issue.date || ''} · ${issue.generated_at || ''} · ${issue.generated_by || ''}`;
      el('newsSummary').textContent = issue.summary || '暂无摘要。';
      const items = issue.items || [];
      el('newsItems').innerHTML = items.length ? items.map(item => `
        <div class="news-item">
          <div class="news-item-title">${escapeHtml(item.title || '未命名资讯')}</div>
          <div class="news-item-meta">${escapeHtml(item.source || '')}${item.url ? ` · <a href="${escapeHtml(item.url)}" target="_blank">来源链接</a>` : ''}</div>
          <p><strong>影响/价值：</strong>${escapeHtml(item.impact || '')}</p>
          <p><strong>建议动作：</strong>${escapeHtml(item.action || '')}</p>
        </div>
      `).join('') : '<div class="forum-empty">暂无资讯条目。</div>';
      el('newsKeywords').innerHTML = (issue.keywords || []).map(k => `<span class="news-keyword">${escapeHtml(k)}</span>`).join('');
    }
    async function loadNews() {
      try {
        const data = await api('/api/news/latest');
        if (state.user?.is_superadmin) {
          const cfg = data.config || {};
          renderNewsSources(cfg.sources || []);
          el('newsSearchQuery').value = cfg.search_query || '';
          el('newsAutoSearch').checked = !!cfg.auto_search;
          el('newsAutoPush').checked = !!cfg.auto_push;
          el('newsPushTime').value = cfg.push_time || '08:30';
        }
        renderNewsIssue(data.issue);
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    }
    el('newsAddSource').addEventListener('click', () => {
      const current = collectNewsSources();
      current.push({ name: '', url: '' });
      renderNewsSources(current);
    });
    el('newsRefresh').addEventListener('click', loadNews);
    el('newsSaveConfig').addEventListener('click', async () => {
      try {
        el('newsConfigStatus').textContent = '保存中...';
        el('newsConfigStatus').className = 'status';
        await apiPost('/api/news/config', {
          sources: collectNewsSources(),
          search_query: el('newsSearchQuery').value,
          auto_search: el('newsAutoSearch').checked,
          auto_push: el('newsAutoPush').checked,
          push_time: el('newsPushTime').value
        });
        el('newsConfigStatus').textContent = '资讯配置已保存';
        el('newsConfigStatus').className = 'status ok';
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    });
    el('newsGenerateNow').addEventListener('click', async () => {
      try {
        el('newsConfigStatus').textContent = '正在抓取网页并调用大模型生成资讯...';
        el('newsConfigStatus').className = 'status';
        const result = await apiPost('/api/news/generate', {
          search_query: el('newsSearchQuery').value,
          auto_search: el('newsAutoSearch').checked
        });
        renderNewsIssue(result.issue);
        el('newsConfigStatus').textContent = '今日资讯已生成';
        el('newsConfigStatus').className = 'status ok';
      } catch (err) {
        el('newsConfigStatus').textContent = err.message;
        el('newsConfigStatus').className = 'status err';
      }
    });

    el('modalSave').addEventListener('click', saveAndCloseModal);
    el('modalCancel').addEventListener('click', saveAndCloseModal);
    el('modalClose').addEventListener('click', saveAndCloseModal);
    el('modalFields').addEventListener('input', event => {
      if (event.target.closest('[data-modal-key]')) {
        saveCurrentModal();
      }
    });
    el('editModal').addEventListener('click', event => {
      if (event.target === el('editModal')) saveAndCloseModal();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !el('editModal').classList.contains('hidden')) {
        saveAndCloseModal();
      }
    });
    el('dashboardAskButton').addEventListener('click', () => {
      const text = el('dashboardAsk').value.trim();
      agentKind = agentKindForTask();
      updateAgentChrome(agentKind);
      toggleAgent(true);
      if (!agentMessages.length) {
        agentMessages.push({ role: 'assistant', content: `你好，我是${agentTitle(agentKind)}。你可以直接把当前页面相关的问题交给我。` });
      }
      renderAgentMessages();
      if (text) sendAgentMessage(text);
    });
    el('dashboardAsk').addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        el('dashboardAskButton').click();
      }
    });
    async function optimizeField(button) {
      const fieldWrap = button.closest('.wide');
      const input = fieldWrap?.querySelector('textarea[data-modal-key]');
      const promptInput = fieldWrap?.querySelector('.field-assist-prompt');
      const fieldStatus = fieldWrap?.querySelector('.assist-status');
      if (!input || !promptInput || !fieldStatus) return;
      const original = input.value.trim();
      if (!original) {
        fieldStatus.textContent = '请先填写需要优化的内容。';
        fieldStatus.className = 'assist-status err';
        return;
      }
      button.disabled = true;
      button.textContent = '优化中...';
      fieldStatus.textContent = '正在调用 MiniMax-M2.7 优化，请稍等...';
      fieldStatus.className = 'assist-status';
      try {
        const result = await api('/api/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: original,
            prompt: promptInput.value
          })
        });
        input.value = result.text || original;
        fieldStatus.textContent = result.warning || '优化完成，已写入当前输入框。';
        fieldStatus.className = result.warning ? 'assist-status err' : 'assist-status ok';
      } catch (err) {
        fieldStatus.textContent = '优化失败：' + err.message;
        fieldStatus.className = 'assist-status err';
      } finally {
        button.disabled = false;
        button.textContent = '辅助优化';
      }
    }

    el('modalFields').addEventListener('click', event => {
      const button = event.target.closest('.assist-optimize');
      if (button) optimizeField(button);
    });

    el('refresh').addEventListener('click', () => {
      const kind = state.task === 'mail' ? el('mailKind').value : el('kind').value;
      loadDraft(kind, state.selected);
    });
    el('copy').addEventListener('click', async () => {
      await navigator.clipboard.writeText(el('body').value);
      el('status').textContent = '正文已复制';
      el('status').className = 'status ok';
    });
    el('body').addEventListener('input', () => {
      state.bodyHtml = '';
      renderBodyPreview();
    });
    el('send').addEventListener('click', async () => {
      el('status').textContent = '处理中...';
      el('status').className = 'status';
      try {
        const result = await api('/api/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            to: el('to').value,
            cc: el('cc').value,
            subject: el('subject').value,
            body: el('body').value,
            body_html: state.bodyHtml || '',
            attachment: el('attachment').value
          })
        });
        el('status').textContent = result.message;
        el('status').className = 'status ok';
      } catch (err) {
        el('status').textContent = err.message;
        el('status').className = 'status err';
      }
    });

    let agentMessages = [];
    let agentKind = null;

    function agentKindForTask(task = state.task) {
      if (['weekly', 'trip', 'diary', 'forum', 'news', 'mailassistant'].includes(task)) return task;
      if (task === 'calendar') return 'diary';
      return 'dashboard';
    }

    function agentTitle(kind) {
      return {
        weekly: '周报助手',
        trip: '出差报告助手',
        diary: '日记助手',
        forum: '论坛助手',
        news: '资讯助手',
        mailassistant: '智能邮件助手',
        dashboard: 'AI 办公总助手'
      }[kind] || 'AI 办公助手';
    }

    function agentIcon(kind) {
      return {
        weekly: 'file-spreadsheet',
        trip: 'briefcase-business',
        diary: 'book-open',
        forum: 'messages-square',
        news: 'newspaper',
        mailassistant: 'inbox',
        dashboard: 'layout-dashboard'
      }[kind] || 'bot';
    }

    function updateAgentChrome(kind = agentKindForTask()) {
      const title = agentTitle(kind);
      const header = document.querySelector('#agentWindow .agent-header span');
      if (header) {
        header.innerHTML = `<img class="agent-avatar" src="/assets/ai-assistant-avatar.png" alt="" /> ${title}`;
      }
      el('agentToggle').title = title;
      el('agentActions').innerHTML = `
        <button class="agent-action" type="button" data-agent-kind="${kind}"><span class="icon" data-icon="${agentIcon(kind)}"></span> ${title}</button>
        <button class="agent-action" type="button" data-agent-kind="weekly"><span class="icon" data-icon="file-spreadsheet"></span> 周报</button>
        <button class="agent-action" type="button" data-agent-kind="trip"><span class="icon" data-icon="briefcase-business"></span> 出差</button>
      `;
      el('agentActions').querySelectorAll('.agent-action').forEach(btn => {
        btn.addEventListener('click', () => startAgent(btn.dataset.agentKind, true));
      });
      renderIcons(el('agentWindow'));
    }

    function syncAgentToTask(task = state.task) {
      const nextKind = agentKindForTask(task);
      const changed = agentKind !== nextKind;
      agentKind = nextKind;
      updateAgentChrome(nextKind);
      if (changed) {
        agentMessages = [];
        renderAgentMessages();
      }
      const win = el('agentWindow');
      if (changed && win && !win.classList.contains('hidden')) {
        startAgent(nextKind, true);
      }
    }

    function toggleAgent(show) {
      const win = el('agentWindow');
      const shouldOpen = show === true || (show === undefined && win.classList.contains('hidden'));
      if (show === true) win.classList.remove('hidden');
      else if (show === false) win.classList.add('hidden');
      else if (shouldOpen) win.classList.remove('hidden');
      bringAgentToFront();
    }

    function bringAgentToFront() {
      const agent = el('agentFloat');
      if (!agent) return;
      agent.style.zIndex = '3000';
    }

    function renderAgentMessages() {
      const box = el('agentMessages');
      box.innerHTML = agentMessages.map(m =>
        `<div class="agent-msg ${m.role}">${escapeHtml(m.content)}</div>`
      ).join('');
      box.scrollTop = box.scrollHeight;
    }

    async function sendAgentContext(contextData) {
      const btn = el('agentSend');
      btn.disabled = true;
      btn.textContent = '分析中...';
      try {
        const payloadMessages = agentMessages.filter(m => m.role !== 'system').map(m => ({...m}));
        payloadMessages.push({
          role: 'user',
          content: `[系统提示：当前智能体类型为 ${agentTitle(agentKind)}，以下是当前页面上下文。请严格按这个智能体的职责处理，不要沿用其他模块逻辑。]\\n` + JSON.stringify(contextData, null, 2)
        });
        const result = await api('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: agentKind, messages: payloadMessages })
        });
        agentMessages.push({ role: 'assistant', content: result.reply });
        renderAgentMessages();
        try {
          const json = JSON.parse(result.reply);
          applyAgentResult(json);
          if (json.done) {
            const doneMsg = agentKind === 'diary' ? '日记已根据对话内容自动填充并保存，你可以在页面上查看和修改。' : '已根据对话内容自动生成并填充到表单中，你可以切换到"填写报告"查看和修改。';
            agentMessages.push({ role: 'assistant', content: doneMsg });
            renderAgentMessages();
          }
        } catch (e) { /* 继续对话 */ }
      } catch (err) {
        agentMessages.push({ role: 'assistant', content: '出错：' + err.message });
        renderAgentMessages();
      } finally {
        btn.disabled = false;
        btn.textContent = '发送';
      }
    }

    function startCurrentAgent() {
      startAgent(agentKindForTask(), true);
    }

    function openAgentFromAvatar() {
      el('agentWindow')?.classList.remove('hidden');
      bringAgentToFront();
      startCurrentAgent();
    }

    function startAgent(kind, reset = true) {
      const previousKind = agentKind;
      agentKind = kind;
      updateAgentChrome(kind);
      if (reset || !agentMessages.length || previousKind !== kind) agentMessages = [];
      toggleAgent(true);
      const currentData = getCurrentFormData(kind);
      const hasContent = kind === 'weekly'
        ? [currentData.weekly_summary, currentData.weekly_follow, currentData.weekly_next].some(hasRowContent)
        : kind === 'forum'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : kind === 'news'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : kind === 'mailassistant'
        ? Object.values(currentData).some(v => typeof v === 'string' && v.trim())
        : Object.values(currentData).some(v => v && String(v).trim());
      if (hasContent) {
        const greeting = kind === 'weekly'
          ? '你好，我是周报智能助手。我检测到你已经在表单中填写了一些内容，让我分析一下还需要补充什么。'
          : kind === 'diary'
          ? '你好，我是工作日记智能助手。我检测到你已经在日记中填写了一些内容，让我分析一下还可以补充什么。'
          : kind === 'forum'
          ? '你好，我是论坛助手。我会基于当前话题、评论和草稿，帮你提炼观点或生成讨论回复。'
          : kind === 'news'
          ? '你好，我是资讯助手。我会基于当前每日资讯，帮你提炼重点、影响和建议行动。'
          : kind === 'mailassistant'
          ? '你好，我是智能邮件助手。我会根据当前邮件或写信内容，帮你总结、回复或优化正文。'
          : '你好，我是出差报告智能助手。我检测到你已经在表单中填写了一些内容，让我分析一下还需要补充什么。';
        agentMessages.push({ role: 'assistant', content: greeting });
        renderAgentMessages();
        sendAgentContext(currentData);
      } else {
        const greeting = kind === 'weekly'
          ? '你好，我是周报智能助手。\\n\\n我会通过几轮对话了解你本周的工作情况，然后自动生成周报。\\n\\n请先告诉我：本周你主要做了哪些工作？可以按项目或任务分类描述。'
          : kind === 'diary'
          ? '你好，我是工作日记智能助手。\\n\\n我会通过对话帮你记录今天的工作日记。\\n\\n你可以一次性描述今天的工作、明天的计划和想法，我会自动分类整理。\\n\\n请告诉我：今天做了什么工作？'
          : kind === 'forum'
          ? '你好，我是论坛助手。\\n\\n我可以帮你发起金点子话题、润色评论、总结历史话题讨论热度。\\n\\n你想讨论哪个点子？'
          : kind === 'news'
          ? '你好，我是资讯助手。\\n\\n我可以帮你解读每日轨交资讯、提炼影响和行动建议。\\n\\n请告诉我你想重点看哪类资讯？'
          : kind === 'mailassistant'
          ? '你好，我是智能邮件助手。\\n\\n我可以帮你总结邮件、起草回复、优化普通邮件正文。\\n\\n请把要处理的邮件内容或写信要求告诉我。'
          : kind === 'dashboard'
          ? '你好，我是 AI 办公总助手。\\n\\n我可以帮你在周报、出差报告、工作日记、邮件、论坛和资讯之间梳理工作。你现在想处理什么？'
          : '你好，我是出差报告智能助手。\\n\\n我会通过几轮对话了解你的出差情况，然后自动生成出差报告。\\n\\n请先告诉我：这次出差的地点和时间？';
        agentMessages.push({ role: 'assistant', content: greeting });
        renderAgentMessages();
      }
    }

    async function sendAgentMessage(text) {
      if (!text.trim()) return;
      agentMessages.push({ role: 'user', content: text.trim() });
      renderAgentMessages();
      el('agentInput').value = '';
      const btn = el('agentSend');
      btn.disabled = true;
      btn.textContent = '思考中...';
      try {
        const currentData = getCurrentFormData(agentKind);
        const payloadMessages = agentMessages.filter(m => m.role !== 'system').map(m => ({...m}));
        if (Object.values(currentData).some(v => Array.isArray(v) ? v.length : v)) {
          payloadMessages.push({
            role: 'user',
            content: `[系统提示：当前智能体类型为 ${agentTitle(agentKind)}，以下是当前页面上下文。请严格按这个智能体的职责处理，不要沿用其他模块逻辑。]\\n` + JSON.stringify(currentData, null, 2)
          });
        }
        const result = await api('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: agentKind, messages: payloadMessages })
        });
        agentMessages.push({ role: 'assistant', content: result.reply });
        renderAgentMessages();
        try {
          const json = JSON.parse(result.reply);
          applyAgentResult(json);
          if (json.done) {
            const doneMsg = agentKind === 'diary' ? '日记已根据对话内容自动填充并保存，你可以在页面上查看和修改。' : '已根据对话内容自动生成并填充到表单中，你可以切换到"填写报告"查看和修改。';
            agentMessages.push({ role: 'assistant', content: doneMsg });
            renderAgentMessages();
          }
        } catch (e) { /* 继续对话 */ }
      } catch (err) {
        agentMessages.push({ role: 'assistant', content: '出错：' + err.message });
        renderAgentMessages();
      } finally {
        btn.disabled = false;
        btn.textContent = '发送';
      }
    }

    function getCurrentFormData(kind) {
      if (kind === 'weekly') {
        return {
          weekly_summary: collectWorkRows('summary'),
          weekly_follow: collectWorkRows('follow'),
          weekly_next: collectWorkRows('next')
        };
      }
      if (kind === 'diary') {
        return {
          today_work: el('diaryTodayWork').value,
          tomorrow_plan: el('diaryTomorrowPlan').value,
          thoughts: el('diaryThoughts').value
        };
      }
      if (kind === 'forum') {
        return {
          selected_topic_id: state.forumSelected || '',
          topic_title: document.querySelector('#forumTopicDetail .forum-topic-title')?.textContent || '',
          topic_detail: el('forumTopicDetail')?.innerText || '',
          comment_draft: el('forumCommentInput')?.value || '',
          create_title: el('forumTitle')?.value || '',
          create_body: el('forumBody')?.value || ''
        };
      }
      if (kind === 'news') {
        return {
          title: el('newsTitle')?.textContent || '',
          meta: el('newsMeta')?.textContent || '',
          summary: el('newsSummary')?.textContent || '',
          items: el('newsItems')?.innerText || '',
          keywords: el('newsKeywords')?.innerText || ''
        };
      }
      if (kind === 'mailassistant') {
        return {
          selected_mail: el('mailDetail')?.innerText || '',
          compose_to: el('assistantMailTo')?.value || '',
          compose_cc: el('assistantMailCc')?.value || '',
          compose_subject: el('assistantMailSubject')?.value || '',
          compose_body: el('assistantMailBody')?.value || ''
        };
      }
      if (kind === 'dashboard') {
        return {
          current_task: state.task || 'dashboard',
          current_page: el('taskTitle')?.textContent || '工作台',
          user: state.user?.name || state.user?.username || ''
        };
      }
      return {
        reporter: el('tripReporter').value,
        department: el('tripDepartment').value,
        location: el('tripLocation').value,
        trip_start: el('tripStart').value,
        trip_end: el('tripEnd').value,
        purpose: el('tripPurpose').value,
        itinerary: el('tripItinerary').value,
        details: el('tripDetails').value,
        issues: el('tripIssues').value,
        suggestions: el('tripSuggestions').value
      };
    }

    function hasRowContent(arr) {
      return Array.isArray(arr) && arr.some(r => Object.values(r).some(v => v && String(v).trim()));
    }

    function applyAgentResult(data) {
      if (agentKind === 'weekly') {
        if (hasRowContent(data.weekly_summary)) renderWorkRows('summary', data.weekly_summary);
        if (hasRowContent(data.weekly_follow)) renderWorkRows('follow', data.weekly_follow);
        if (hasRowContent(data.weekly_next)) renderWorkRows('next', data.weekly_next);
      } else if (agentKind === 'trip') {
        if (data.reporter !== undefined) el('tripReporter').value = data.reporter;
        if (data.department !== undefined) el('tripDepartment').value = data.department;
        if (data.location !== undefined) el('tripLocation').value = data.location;
        if (data.trip_start !== undefined) el('tripStart').value = data.trip_start;
        if (data.trip_end !== undefined) el('tripEnd').value = data.trip_end;
        if (data.purpose !== undefined) el('tripPurpose').value = data.purpose;
        if (data.itinerary !== undefined) el('tripItinerary').value = data.itinerary;
        if (data.details !== undefined) el('tripDetails').value = data.details;
        if (data.issues !== undefined) el('tripIssues').value = data.issues;
        if (data.suggestions !== undefined) el('tripSuggestions').value = data.suggestions;
        renderTripCards();
      } else if (agentKind === 'diary') {
        if (data.today_work !== undefined) el('diaryTodayWork').value = data.today_work;
        if (data.tomorrow_plan !== undefined) el('diaryTomorrowPlan').value = data.tomorrow_plan;
        if (data.thoughts !== undefined) el('diaryThoughts').value = data.thoughts;
        if (data.done) saveDiary();
      }
      highlightUpdatedFields();
    }

    function highlightUpdatedFields() {
      document.querySelectorAll('input, textarea, .work-block').forEach(el => {
        el.style.transition = 'box-shadow .4s ease';
        el.style.boxShadow = '0 0 0 2px #17736a40';
        setTimeout(() => { el.style.boxShadow = ''; }, 800);
      });
    }

    boot();
  </script>
  <div class="modal hidden" id="profileModal">
    <div class="modal-box" style="max-width:720px;">
      <div class="modal-head">
        <div class="modal-title">个人资料</div>
        <button class="mini secondary" id="profileClose" type="button">关闭</button>
      </div>
      <div class="profile-grid">
        <div>
          <img class="profile-avatar-large" id="profileAvatarPreview" src="/assets/ai-assistant-avatar.png" alt="" />
          <div class="profile-actions">
            <button class="mini secondary" id="profileUseAssistantAvatar" type="button">使用助手头像</button>
          </div>
        </div>
        <div>
          <label>对外显示名称</label>
          <input id="profileName" placeholder="你的姓名或昵称" />
          <label>上传头像</label>
          <input id="profileAvatarFile" type="file" accept="image/png,image/jpeg,image/webp" />
          <label>对外介绍</label>
          <textarea id="profileBio" placeholder="例如：负责项目、擅长方向、工作职责等" style="min-height:96px;"></textarea>
          <label>个人爱好</label>
          <textarea id="profileHobbies" placeholder="例如：轨道交通、AI 工具、阅读、跑步..." style="min-height:80px;"></textarea>
          <div class="toolbar">
            <button id="profileSave" type="button">保存资料</button>
            <span id="profileStatus" class="status"></span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="agent-float hidden" id="agentFloat">
    <button class="agent-toggle" id="agentToggle" type="button" title="AI 智能助手" onclick="openAgentFromAvatar()"><img class="agent-avatar" src="/assets/ai-assistant-avatar.png" alt="AI 智能助手" /></button>
    <div class="agent-window hidden" id="agentWindow">
      <div class="agent-header">
        <span><img class="agent-avatar" src="/assets/ai-assistant-avatar.png" alt="" /> AI 智能助手</span>
        <button class="agent-close" id="agentClose" type="button">✕</button>
      </div>
      <div class="agent-body">
        <div class="agent-messages" id="agentMessages">
          <div class="agent-msg assistant">你好！我是你的 AI 智能助手。点击下方的快捷按钮，我可以帮你自动生成周报或出差报告。</div>
        </div>
        <div class="agent-actions" id="agentActions">
          <button class="agent-action" type="button" data-agent-kind="weekly"><span class="icon" data-icon="file-spreadsheet"></span> 生成周报</button>
          <button class="agent-action" type="button" data-agent-kind="trip"><span class="icon" data-icon="briefcase-business"></span> 生成出差报告</button>
          <button class="agent-action" type="button" data-agent-kind="diary"><span class="icon" data-icon="book-open"></span> 记录日记</button>
        </div>
        <div class="agent-input-wrap">
          <textarea id="agentInput" placeholder="输入消息...（Ctrl+Enter 发送）"></textarea>
          <button id="agentSend" type="button">发送</button>
        </div>
      </div>
    </div>
  </div>
  <script>
    (function() {
      const el = id => document.getElementById(id);
      const agentFloat = el('agentFloat');
      const agentToggle = el('agentToggle');
      const agentWindow = el('agentWindow');
      const agentHeader = agentWindow.querySelector('.agent-header');
      let suppressClickUntil = 0;

      agentToggle.addEventListener('click', event => {
        event.stopPropagation();
        if (Date.now() < suppressClickUntil) return;
        openAgentFromAvatar();
      });
      el('agentClose').addEventListener('click', () => toggleAgent(false));
      el('agentSend').addEventListener('click', () => sendAgentMessage(el('agentInput').value));
      el('agentInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          sendAgentMessage(el('agentInput').value);
        }
      });
      if (typeof updateAgentChrome === 'function') updateAgentChrome(typeof agentKindForTask === 'function' ? agentKindForTask() : 'dashboard');
      if (typeof renderIcons === 'function') renderIcons(document);

      // 拖拽逻辑：拖按钮或标题栏都会移动整个 AI 助手，点击按钮只负责唤醒。
      (function() {
        let dragging = false;
        let moved = false;
        let startX = 0;
        let startY = 0;
        let initLeft = 0;
        let initTop = 0;
        let activePointerId = null;
        let pointerStartedOnToggle = false;

        function pointerDown(e) {
          if (e.target.closest('.agent-close') || e.target.closest('textarea') || e.target.closest('.agent-action') || e.target.closest('#agentSend')) return;
          bringAgentToFront();
          dragging = true;
          moved = false;
          activePointerId = e.pointerId;
          pointerStartedOnToggle = !!e.target.closest('#agentToggle');
          startX = e.clientX; startY = e.clientY;
          const rect = agentFloat.getBoundingClientRect();
          initLeft = rect.left; initTop = rect.top;
          agentFloat.style.right = 'auto';
          agentFloat.style.bottom = 'auto';
          agentFloat.style.left = initLeft + 'px';
          agentFloat.style.top = initTop + 'px';
          agentToggle.style.cursor = 'grabbing';
          agentHeader.style.cursor = 'grabbing';
          if (e.currentTarget.setPointerCapture) e.currentTarget.setPointerCapture(e.pointerId);
        }

        agentToggle.addEventListener('pointerdown', pointerDown);
        agentHeader.addEventListener('pointerdown', pointerDown);

        document.addEventListener('pointermove', e => {
          if (!dragging) return;
          if (activePointerId !== null && e.pointerId !== activePointerId) return;
          const dx = e.clientX - startX;
          const dy = e.clientY - startY;
          if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
            moved = true;
          }
          const rect = agentFloat.getBoundingClientRect();
          const maxLeft = window.innerWidth - Math.max(80, rect.width);
          const maxTop = window.innerHeight - Math.max(80, rect.height);
          const nextLeft = Math.max(8, Math.min(initLeft + dx, maxLeft));
          const nextTop = Math.max(8, Math.min(initTop + dy, maxTop));
          agentFloat.style.left = nextLeft + 'px';
          agentFloat.style.top = nextTop + 'px';
        });

        document.addEventListener('pointerup', e => {
          if (!dragging) return;
          if (activePointerId !== null && e.pointerId !== activePointerId) return;
          dragging = false;
          activePointerId = null;
          agentToggle.style.cursor = 'grab';
          agentHeader.style.cursor = 'move';
          if (moved) {
            suppressClickUntil = Date.now() + 250;
          } else if (pointerStartedOnToggle) {
            openAgentFromAvatar();
          }
          pointerStartedOnToggle = false;
        });
      })();
    })();
  </script>
</body>
</html>"""


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
        if parsed.path == "/":
            raw = app_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
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
        if parsed.path.startswith("/api/") and not self.require_user():
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
        self.send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
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
                result = agent_chat(payload)
            elif parsed.path == "/api/upload-history":
                result = upload_history_reports(payload, username)
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
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=news_auto_worker, daemon=True).start()
    print(f"个人工作报告邮件助手已启动：http://127.0.0.1:{port}")
    print(f"用户数据目录：{USER_DATA_DIR}")
    print(f"共享模板目录：{REPORT_DIR}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
