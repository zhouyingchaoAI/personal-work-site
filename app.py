#!/usr/bin/env python3
import json
import base64
import mimetypes
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
import urllib.request
import zipfile
import shutil
import secrets
from copy import deepcopy
from datetime import datetime
from email.message import EmailMessage
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
    return {
        "username": user.get("username", ""),
        "role": user.get("role", "member"),
        "name": user.get("name") or user.get("username", ""),
        "is_admin": user.get("role") == "admin",
    }


def ensure_user_space(username):
    for path in (user_report_dir(username), user_generated_dir(username), user_draft_dir(username)):
        path.mkdir(parents=True, exist_ok=True)


def find_user(username, password=None):
    for user in read_config().get("users", []):
        if user.get("username") != username:
            continue
        if password is None or str(user.get("password", "")) == str(password):
            return user
    return None


def user_mail_config(username):
    """返回指定用户的邮件配置，含本人邮箱、周报/出差报告各自的收件人和抄送"""
    config = read_config()
    settings = config.get("user_mail_settings", {}).get(username or "", {})
    return {
        "user_email": settings.get("user_email", ""),
        "weekly_to": settings.get("weekly_to", ""),
        "weekly_cc": settings.get("weekly_cc", ""),
        "trip_to": settings.get("trip_to", ""),
        "trip_cc": settings.get("trip_cc", ""),
        "smtp_host": settings.get("smtp_host", ""),
        "smtp_port": int(settings.get("smtp_port", 587) or 587),
        "smtp_user": settings.get("smtp_user", ""),
        "smtp_password": settings.get("smtp_password", ""),
        "smtp_from": settings.get("smtp_from", "") or settings.get("user_email", ""),
        "smtp_tls": str(settings.get("smtp_tls", "true")).lower() != "false",
        "smtp_ssl": str(settings.get("smtp_ssl", "false")).lower() == "true",
    }


def save_user_mail_config(username, payload):
    if not username:
        raise ValueError("请先登录")
    config = read_config()
    settings = config.setdefault("user_mail_settings", {}).setdefault(username, {})
    fields = ["user_email", "weekly_to", "weekly_cc", "trip_to", "trip_cc", "smtp_host", "smtp_user", "smtp_from"]
    for field in fields:
        settings[field] = str(payload.get(field, "") or "").strip()
    if payload.get("smtp_password"):
        settings["smtp_password"] = str(payload.get("smtp_password") or "").strip()
    settings["smtp_port"] = int(payload.get("smtp_port", settings.get("smtp_port", 587)) or 587)
    settings["smtp_tls"] = bool(payload.get("smtp_tls", True))
    settings["smtp_ssl"] = bool(payload.get("smtp_ssl", False))
    write_config(config)
    result = user_mail_config(username)
    result["smtp_password_masked"] = "已配置" if result.get("smtp_password") else "未配置"
    result.pop("smtp_password", None)
    return {"ok": True, "mail_config": result}


def admin_config_payload():
    config = read_config()
    return {
        "assistant_api_url": config.get("assistant_api_url", ""),
        "assistant_model": config.get("assistant_model", "MiniMax-M2.7"),
        "assistant_prompt": config.get("assistant_prompt", DEFAULT_ASSISTANT_PROMPT),
        "assistant_api_key_masked": "已配置" if config.get("assistant_api_key") else "未配置",
        "email_signature": config.get("email_signature", DEFAULT_EMAIL_SIGNATURE),
        "users": [public_user(user) for user in config.get("users", [])],
    }


def save_admin_config(payload):
    config = read_config()
    config["assistant_api_url"] = str(payload.get("assistant_api_url", "") or "").strip()
    config["assistant_model"] = str(payload.get("assistant_model", "") or "MiniMax-M2.7").strip()
    config["assistant_prompt"] = str(payload.get("assistant_prompt", "") or DEFAULT_ASSISTANT_PROMPT).strip()
    email_signature = payload.get("email_signature")
    if email_signature is not None:
        config["email_signature"] = str(email_signature).strip()
    api_key = str(payload.get("assistant_api_key", "") or "").strip()
    if api_key:
        config["assistant_api_key"] = api_key
    write_config(config)
    return {"ok": True, "config": admin_config_payload()}


def add_member_user(payload):
    username = str(payload.get("username", "") or "").strip()
    password = str(payload.get("password", "") or "").strip()
    name = str(payload.get("name", "") or "").strip() or username
    if not re.match(r"^[A-Za-z0-9_@.-]{2,40}$", username):
        raise ValueError("用户名只能包含字母、数字、下划线、点、@ 或横线，长度 2-40 位")
    if len(password) < 4:
        raise ValueError("密码至少 4 位")
    config = read_config()
    users = config.setdefault("users", [])
    if any(user.get("username") == username for user in users):
        raise ValueError("该用户名已存在")
    users.append({"username": username, "password": password, "role": "member", "name": name})
    write_config(config)
    ensure_user_space(username)
    return {"ok": True, "users": [public_user(user) for user in users]}


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
    return generated_files(username) + report_files(username)


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
    signature = config.get("email_signature", DEFAULT_EMAIL_SIGNATURE) or ""
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

    # 记住数据区域原始的合并结构
    data_area_merges = []
    for mc in list(ws.merged_cells.ranges):
        if not (mc.max_row < 5 or mc.min_row > 20):
            data_area_merges.append((mc.min_row, mc.min_col, mc.max_row, mc.max_col))

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

    def write_and_style(row_idx, col_idx, value, halign="left"):
        cell = ws.cell(row_idx, col_idx)
        cell.value = normalize_numbered_text(value)
        cell.border = thin_border
        style_xlsx_cell(cell, horizontal=halign, vertical="center")

    # 清空数据区域（包括所有列）
    for r in range(5, 9):
        for c in range(2, 7):
            write_and_style(r, c, "")
    for r in range(11, 16):
        for c in range(2, 7):
            write_and_style(r, c, "")
    for r in range(18, 21):
        for c in range(2, 7):
            write_and_style(r, c, "")

    # 本周工作总结 (行5-8): B=工作分类 C=工作内容 E=完成情况 F=后续计划
    for idx, row in enumerate(summary_rows[:4], start=5):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 5, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 5, 6))

    # 重点工作跟进 (行11-15): B=工作分类 C=工作内容 D=当前进展 F=困难与求助
    for idx, row in enumerate(follow_rows[:5], start=11):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 4, row[2])
        write_and_style(idx, 6, row[3])
        adjust_row_height(ws, idx, (2, 3, 4, 6))

    # 下周工作计划 (行18-20): B=工作分类 C=工作内容 F=困难与求助
    for idx, row in enumerate(next_rows[:3], start=18):
        write_and_style(idx, 2, row[0], halign="center")
        write_and_style(idx, 3, row[1])
        write_and_style(idx, 6, row[2])
        adjust_row_height(ws, idx, (2, 3, 6))

    # 恢复原始合并结构
    for min_r, min_c, max_r, max_c in data_area_merges:
        try:
            ws.merge_cells(start_row=min_r, start_column=min_c, end_row=max_r, end_column=max_c)
        except Exception:
            pass

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
  <title>办公助手</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #1d2430;
      --muted: #657184;
      --line: #d9dee7;
      --accent: #17736a;
      --accent-2: #9a5b13;
      --danger: #b42318;
      --shadow: 0 12px 30px rgba(26, 34, 47, .08);
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
  </style>
</head>
<body>
  <header>
    <div class="header-row">
      <div>
        <h1>办公助手</h1>
        <div class="sub">周报、出差报告、历史资料和邮件发送的一体化办公工作台。</div>
      </div>
      <div class="userbar" id="userbar">
        <span id="userInfo"></span>
        <button class="mini" type="button" id="logoutButton">退出</button>
      </div>
    </div>
  </header>
  <section class="auth-panel" id="authPanel">
    <h2>登录</h2>
    <label>用户名</label>
    <input id="loginUser" value="admin" />
    <label>密码</label>
    <input id="loginPass" type="password" value="admin123" />
    <div class="toolbar">
      <button id="loginButton" type="button">登录</button>
    </div>
    <div class="hint">默认管理员：admin / admin123；普通成员：member / member123。管理员可修改大模型 API 配置，成员不可修改系统配置。</div>
    <div id="loginStatus" class="status"></div>
  </section>
  <main id="appMain" class="hidden">
    <section class="task-board">
      <h2>导航</h2>
      <div class="task-grid">
        <button class="task-card active" type="button" data-task="weekly">
          <span class="task-name">周报助手</span>
          <span class="task-desc">填写周报、发送邮件、管理历史周报。</span>
        </button>
        <button class="task-card" type="button" data-task="trip">
          <span class="task-name">出差报告助手</span>
          <span class="task-desc">填写出差报告、发送邮件、管理历史出差报告。</span>
        </button>
        <button class="task-card" type="button" data-task="mailconfig">
          <span class="task-name">邮件配置</span>
          <span class="task-desc">配置自己的发件邮箱、周报/出差报告收件人和抄送人。</span>
        </button>
        <button class="task-card admin-only hidden" type="button" data-task="config">
          <span class="task-name">系统配置</span>
          <span class="task-desc">管理员配置 NewAPI 地址、Key、模型和默认优化提示词。</span>
        </button>
      </div>
    </section>
    <section class="composer">
      <h2 id="taskTitle">填写周报</h2>
      <input id="kind" type="hidden" value="weekly" />
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
        <label>邮件签名模板</label>
        <textarea id="configEmailSignature" placeholder="留空则使用默认签名"></textarea>
        <div class="toolbar">
          <button class="secondary" id="loadModels" type="button">获取模型列表</button>
          <button class="warn" id="testModel" type="button">测试 API Key</button>
          <button id="saveConfig" type="button">保存系统配置</button>
        </div>
        <div id="configTestStatus" class="status"></div>
        <h2 style="margin-top:18px">普通用户管理</h2>
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
        <label>初始密码</label>
        <input id="newUserPassword" type="password" placeholder="至少 4 位" />
        <div class="toolbar">
          <button id="addUser" type="button">新增普通用户</button>
        </div>
        <div class="user-list" id="userList"></div>
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
            <label>SMTP 服务器</label>
            <input id="mailSmtpHost" placeholder="smtp.example.com" />
          </div>
          <div>
            <label>SMTP 端口</label>
            <input id="mailSmtpPort" type="number" placeholder="587" />
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
        <div class="row">
          <label><input id="mailSmtpTls" type="checkbox" style="width:auto" /> 使用 TLS</label>
          <label><input id="mailSmtpSsl" type="checkbox" style="width:auto" /> 使用 SSL</label>
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
        <div class="toolbar" style="margin-top:16px">
          <button id="saveMailConfig" type="button">保存我的邮件配置</button>
          <button class="warn" id="testMailConfig" type="button">测试我的邮箱配置</button>
        </div>
        <div id="mailConfigStatus" class="status"></div>
      </div>
      </div>
      <div class="toolbar" id="generateToolbar">
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
    let state = { reports: [], selected: null, task: 'weekly', user: null, weeklyPrefilled: false, tripPrefilled: false, modalSave: null, restoringDraft: false };
    const FORM_DRAFT_PREFIX = 'personalWorkSite.formDraft.v2';
    const el = id => document.getElementById(id);

    async function api(path, options) {
      const res = await fetch(path, options);
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
      if (authed) {
        el('userInfo').textContent = `${user.name || user.username} · ${user.role === 'admin' ? '管理员' : '成员'}`;
      }
      document.querySelectorAll('.admin-only').forEach(node => {
        node.classList.toggle('hidden', !user?.is_admin);
      });
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
        reader.onerror = () => reject(reader.error || new Error('读取文件失败'));
        reader.readAsDataURL(file);
      });
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

    function setTask(task) {
      state.task = task;
      document.querySelectorAll('.task-card').forEach(card => {
        card.classList.toggle('active', card.dataset.task === task);
      });
      const isAssistant = task === 'weekly' || task === 'trip';
      el('weeklyPanel').classList.toggle('hidden', task !== 'weekly');
      el('tripPanel').classList.toggle('hidden', task !== 'trip');
      el('mailPanel').classList.toggle('hidden', !isAssistant);
      el('uploadPanel').classList.toggle('hidden', !isAssistant);
      el('configPanel').classList.toggle('hidden', task !== 'config');
      el('mailConfigPanel').classList.toggle('hidden', task !== 'mailconfig');
      el('generateToolbar').classList.toggle('hidden', !isAssistant);
      const titles = { weekly: '周报助手', trip: '出差报告助手', config: '系统配置', mailconfig: '邮件配置' };
      el('taskTitle').textContent = titles[task] || '内容填写';
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
        renderReports();
        renderHistoryReports();
      }
      if (task === 'mailconfig') {
        loadMailConfig();
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
      el('configEmailSignature').value = data.email_signature || '';
      el('configApiKey').value = '';
      el('configKeyHint').textContent = 'API Key 状态：' + (data.assistant_api_key_masked || '未配置');
      renderUsers(data.users || []);
    }

    async function loadMailConfig() {
      const data = await api('/api/mail-config');
      el('mailUserEmail').value = data.user_email || '';
      el('mailSmtpFrom').value = data.smtp_from || '';
      el('mailSmtpHost').value = data.smtp_host || '';
      el('mailSmtpPort').value = data.smtp_port || 587;
      el('mailSmtpUser').value = data.smtp_user || '';
      el('mailSmtpPassword').value = '';
      el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (data.smtp_password_masked || '未配置');
      el('mailSmtpTls').checked = data.smtp_tls !== false;
      el('mailSmtpSsl').checked = data.smtp_ssl === true;
      el('mailWeeklyTo').value = data.weekly_to || '';
      el('mailWeeklyCc').value = data.weekly_cc || '';
      el('mailTripTo').value = data.trip_to || '';
      el('mailTripCc').value = data.trip_cc || '';
    }

    function mailConfigPayload() {
      return {
        user_email: el('mailUserEmail').value,
        smtp_from: el('mailSmtpFrom').value,
        smtp_host: el('mailSmtpHost').value,
        smtp_port: el('mailSmtpPort').value,
        smtp_user: el('mailSmtpUser').value,
        smtp_password: el('mailSmtpPassword').value,
        smtp_tls: el('mailSmtpTls').checked,
        smtp_ssl: el('mailSmtpSsl').checked,
        weekly_to: el('mailWeeklyTo').value,
        weekly_cc: el('mailWeeklyCc').value,
        trip_to: el('mailTripTo').value,
        trip_cc: el('mailTripCc').value
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
      el('userList').innerHTML = (users || []).map(user => `
        <div class="user-item">
          <div>
            <strong>${escapeHtml(user.name || user.username)}</strong>
            <div class="history-meta">${escapeHtml(user.username)} · ${user.role === 'admin' ? '管理员' : '普通成员'}</div>
          </div>
          <div class="history-meta">${user.is_admin ? '系统配置权限' : '业务使用权限'}</div>
        </div>
      `).join('') || '<div class="upload-item">暂无用户。</div>';
    }

    function adminConfigPayload() {
      return {
        assistant_api_url: el('configApiUrl').value,
        assistant_api_key: el('configApiKey').value,
        assistant_model: el('configModel').value || el('configModelSelect').value,
        assistant_prompt: el('configPrompt').value,
        email_signature: el('configEmailSignature').value
      };
    }

    async function boot() {
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

    el('generate').addEventListener('click', async () => {
      const kind = el('kind').value;
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
        } else if (task === 'config') {
          await loadAdminConfig();
        }
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
        el('mailPasswordHint').textContent = 'SMTP 密码/授权码状态：' + (result.mail_config.smtp_password_masked || '未配置');
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
      el('configTestStatus').textContent = '正在新增普通用户...';
      el('configTestStatus').className = 'status';
      try {
        const result = await api('/api/admin-users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: el('newUserName').value,
            password: el('newUserPassword').value,
            name: el('newDisplayName').value
          })
        });
        renderUsers(result.users || []);
        el('newUserName').value = '';
        el('newDisplayName').value = '';
        el('newUserPassword').value = '';
        el('configTestStatus').textContent = '普通用户已新增。';
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
    el('weeklyStart').addEventListener('change', syncWeeklyPeriod);
    el('weeklyEnd').addEventListener('change', syncWeeklyPeriod);
    window.addEventListener('beforeunload', () => {
      saveCurrentModal();
      saveFormDraft();
    });
    el('historyKind').addEventListener('change', renderHistoryReports);

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

    boot();
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
        if user.get("role") != "admin":
            self.send_json({"ok": False, "error": "只有管理员可以修改系统配置"}, status=403)
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
        if parsed.path.startswith("/api/") and not self.require_user():
            return
        if parsed.path == "/api/mail-config":
            username = self.current_user().get("username", "")
            data = user_mail_config(username)
            data["smtp_password_masked"] = "已配置" if data.get("smtp_password") else "未配置"
            data.pop("smtp_password", None)
            self.send_json(data)
            return
        if parsed.path == "/api/reports":
            username = self.current_user().get("username", "")
            files = sorted(all_files(username), key=lambda item: (item["generated"] if "generated" in item else False, item["kind"], item["sort_key"], item["mtime"]), reverse=True)
            self.send_json(
                {
                    "reports": files,
                    "latest_weekly": (newest("weekly", username) or {}).get("name", ""),
                    "latest_trip": (newest("trip", username) or {}).get("name", ""),
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
            elif parsed.path == "/api/generate":
                result = generate_document(payload, username)
            elif parsed.path == "/api/optimize":
                result = optimize_text(payload)
            elif parsed.path == "/api/upload-history":
                result = upload_history_reports(payload, username)
            elif parsed.path == "/api/delete-history":
                result = delete_history_report(payload, username)
            elif parsed.path == "/api/mail-config":
                result = save_user_mail_config(username, payload)
            elif parsed.path == "/api/test-mail-config":
                result = test_user_mail_config(username)
            elif parsed.path == "/api/admin-config":
                if not self.require_admin():
                    return
                result = save_admin_config(payload)
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
                result = add_member_user(payload)
            else:
                self.send_json({"error": "Not found"}, status=404)
                return
            self.send_json(result)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)


def main():
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"个人工作报告邮件助手已启动：http://127.0.0.1:{port}")
    print(f"用户数据目录：{USER_DATA_DIR}")
    print(f"共享模板目录：{REPORT_DIR}")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
