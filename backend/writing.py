"""智能写作助手：素材上传、知识库参考、模板、历史、生成、改写与导出。

This module is loaded by backend.runtime into one shared application namespace.
"""

WRITING_TYPES = [
    "通用文章", "通知公告", "汇报材料", "方案文档", "制度文件", "会议纪要", "邮件草稿",
    "新闻稿", "工作总结", "调研报告", "标书/投标响应", "合同条款说明",
]
WRITING_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
WRITING_MAX_MATERIAL_CHARS = 12000
WRITING_MAX_MATERIAL_TOTAL_CHARS = 30000
WRITING_MAX_KB_CHARS = 8000


def _writing_dir(username):
    base = user_root(username) / "writing"
    for child in ("uploads", "history", "templates", "exports"):
        (base / child).mkdir(parents=True, exist_ok=True)
    return base


def _writing_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _writing_id(prefix="wr"):
    return f"{prefix}_{int(time.time() * 1000)}_{secrets.token_hex(4)}"


def _writing_safe_name(name):
    safe = Path(name or "upload.txt").name.strip() or "upload.txt"
    safe = re.sub(r"[\\/:*?\"<>|]+", "_", safe)
    return safe[:120]


def _writing_json_read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _writing_json_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _writing_decode_file(file_item):
    name = _writing_safe_name(file_item.get("name") or "upload.txt")
    data = str(file_item.get("data") or "")
    if "," in data:
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data)
    if not raw:
        raise ValueError(f"{name} 文件内容为空")
    if len(raw) > WRITING_MAX_UPLOAD_BYTES:
        raise ValueError(f"{name} 超过 20MB 上限")
    return name, raw


def _writing_extract_text(name, raw):
    try:
        return _kb_extract_text(name, raw).strip()
    except Exception as exc:
        suffix = Path(name).suffix.lower()
        if suffix in (".txt", ".md", ".csv", ".log", ".json"):
            return raw.decode("utf-8", "ignore").strip()
        raise ValueError(f"{name} 文本提取失败：{exc}") from exc


def _writing_upload_record(username, upload_id):
    path = _writing_dir(username) / "uploads" / f"{upload_id}.json"
    record = _writing_json_read(path, None)
    if not record:
        raise ValueError("写作素材不存在")
    return record


def _writing_history_path(username, item_id):
    return _writing_dir(username) / "history" / f"{Path(item_id or '').name}.json"


def _writing_template_path(username, template_id):
    return _writing_dir(username) / "templates" / f"{Path(template_id or '').name}.json"


def writing_upload(payload, username):
    files = (payload or {}).get("files") or []
    if not files:
        raise ValueError("请选择需要上传的写作素材")
    uploaded = []
    for item in files:
        name, raw = _writing_decode_file(item)
        text = _writing_extract_text(name, raw)
        upload_id = _writing_id("mat")
        raw_path = _writing_dir(username) / "uploads" / f"{upload_id}_{name}"
        raw_path.write_bytes(raw)
        record = {
            "id": upload_id,
            "name": name,
            "size": len(raw),
            "path": str(raw_path),
            "text": text,
            "text_preview": text[:300],
            "created_at": _writing_now(),
        }
        _writing_json_write(_writing_dir(username) / "uploads" / f"{upload_id}.json", record)
        public_record = dict(record)
        public_record.pop("text", None)
        uploaded.append(public_record)
    return {"ok": True, "files": uploaded}


def writing_uploads(username):
    """列出该用户已上传并持久化的写作素材，供页面刷新后继续使用。"""
    base = _writing_dir(username) / "uploads"
    items = []
    for path in sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        rec = _writing_json_read(path, None)
        if rec and rec.get("id"):
            items.append({
                "id": rec["id"],
                "name": rec.get("name", ""),
                "size": rec.get("size", 0),
                "text_preview": rec.get("text_preview", ""),
                "created_at": rec.get("created_at", ""),
            })
    return {"ok": True, "files": items}


def writing_delete_upload(payload, username):
    upload_id = str((payload or {}).get("id") or "").strip()
    base = _writing_dir(username) / "uploads"
    rec_path = base / f"{Path(upload_id).name}.json"
    if not rec_path.exists():
        raise ValueError("素材不存在")
    rec = _writing_json_read(rec_path, {}) or {}
    rec_path.unlink()
    raw = rec.get("path")
    try:
        if raw and Path(raw).exists():
            Path(raw).unlink()
    except Exception:
        pass
    return {"ok": True, "deleted": upload_id}


def writing_templates(username):
    base = _writing_dir(username) / "templates"
    templates = []
    for path in sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = _writing_json_read(path, None)
        if item:
            templates.append(item)
    if not templates:
        templates = [
            {"id": "builtin_plan", "name": "方案文档", "writing_type": "方案文档", "prompt": "按背景、目标、架构、实施计划、风险控制、验收指标组织。", "builtin": True},
            {"id": "builtin_report", "name": "汇报材料", "writing_type": "汇报材料", "prompt": "先讲结论，再列进展、问题、下一步计划，语气正式。", "builtin": True},
            {"id": "builtin_notice", "name": "通知公告", "writing_type": "通知公告", "prompt": "标题明确，正文包含事项、时间、对象、要求和联系方式。", "builtin": True},
        ]
    return {"ok": True, "templates": templates, "types": WRITING_TYPES}


def writing_save_template(payload, username):
    payload = payload or {}
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("模板名称不能为空")
    template_id = str(payload.get("id") or "").strip()
    if not template_id or template_id.startswith("builtin_"):
        template_id = _writing_id("tpl")
    item = {
        "id": template_id,
        "name": name[:80],
        "writing_type": str(payload.get("writing_type") or "通用文章")[:40],
        "prompt": str(payload.get("prompt") or "")[:4000],
        "updated_at": _writing_now(),
        "builtin": False,
    }
    _writing_json_write(_writing_template_path(username, template_id), item)
    return {"ok": True, "template": item}


def _writing_collect_materials(payload, username):
    materials = []
    for upload_id in payload.get("file_ids") or []:
        record = _writing_upload_record(username, upload_id)
        materials.append({"id": record["id"], "name": record["name"], "text": record.get("text", "")})
    for file_item in payload.get("files") or []:
        upload = writing_upload({"files": [file_item]}, username)["files"][0]
        record = _writing_upload_record(username, upload["id"])
        materials.append({"id": record["id"], "name": record["name"], "text": record.get("text", "")})
    # 历史周报/出差报告不复制到上传素材库，只按当前账号和当前选择即时解析，
    # 既能用于参考，也避免通过文件名访问其他账号的报告。
    report_refs = payload.get("report_refs") or []
    report_index = {
        (str(item.get("kind") or ""), str(item.get("name") or "")): item
        for item in all_files(username)
    }
    for reference in report_refs[:8]:
        kind = str((reference or {}).get("kind") or "").strip()
        name = Path(str((reference or {}).get("name") or "")).name
        report = report_index.get((kind, name))
        if not report:
            continue
        path = Path(str(report.get("path") or ""))
        if not path.exists() or not path.is_file():
            continue
        try:
            text = _kb_extract_text(path.name, path.read_bytes()).strip()
        except Exception:
            continue
        if text:
            materials.append({"id": f"report:{kind}:{name}", "name": f"参考{('周报' if kind == 'weekly' else '出差报告')}：{name}", "text": text})
    return materials


def writing_agent_attachment_context(file_ids, username):
    """Return a bounded, labelled text context for files attached to an agent turn.

    The files are resolved from the current user's writing uploads, so an agent
    request can never read another user's material merely by guessing an id.
    """
    items = []
    for upload_id in list(file_ids or [])[:6]:
        record = _writing_upload_record(username, str(upload_id or ""))
        text = str(record.get("text") or "").strip()
        if text:
            items.append(f"【附件：{record.get('name') or '未命名文件'}】\n{text[:WRITING_MAX_MATERIAL_CHARS]}")
    if not items:
        return ""
    return "\n\n以下是用户本轮上传的附件内容，请结合它们回答：\n" + "\n\n".join(items)


def _writing_knowledge_sources(payload, username):
    if not payload.get("use_knowledge"):
        return []
    query = " ".join([
        str(payload.get("title") or ""),
        str(payload.get("requirements") or ""),
        str(payload.get("outline") or ""),
    ]).strip()
    if not query:
        query = str(payload.get("writing_type") or "写作")
    result = kb_search({"query": query, "top_k": int(payload.get("knowledge_top_k") or 6), "kb_ids": payload.get("kb_ids") or []}, username)
    return result.get("results") or []


def _writing_prompt(payload, materials, sources, mode="generate"):
    title = str(payload.get("title") or "未命名文稿").strip()
    writing_type = str(payload.get("writing_type") or "通用文章").strip()
    audience = str(payload.get("audience") or "").strip()
    tone = str(payload.get("tone") or "正式、清晰、可执行").strip()
    length = str(payload.get("length") or "").strip()
    requirements = str(payload.get("requirements") or "").strip()
    rewrite_instruction = str(payload.get("rewrite_instruction") or "").strip()
    if rewrite_instruction:
        requirements = "\n\n".join(part for part in (requirements, f"本轮改写要求：{rewrite_instruction}") if part)
    outline = str(payload.get("outline") or "").strip()
    # 多文件总结需要读取每份材料，但总上下文必须受控，避免 Excel / Word 合并后超出模型窗口。
    material_parts = []
    material_count = max(1, len(materials))
    per_material_limit = min(WRITING_MAX_MATERIAL_CHARS, WRITING_MAX_MATERIAL_TOTAL_CHARS // material_count)
    for item in materials:
        excerpt = str(item.get("text") or "")[:per_material_limit]
        if excerpt:
            material_parts.append(f"【素材：{item['name']}】\n{excerpt}")
    material_text = "\n\n".join(material_parts)
    kb_text = "\n\n".join(
        f"【知识库 {index}：{item.get('doc_name') or item.get('dataset_name') or '资料'}】\n{str(item.get('text') or '')[:1200]}"
        for index, item in enumerate(sources, start=1)
    )[:WRITING_MAX_KB_CHARS]
    action = "生成完整正文" if mode == "generate" else "生成可编辑大纲" if mode == "outline" else "改写当前正文"
    current = str(payload.get("content") or "").strip()
    return f"""请作为企业智能写作助手，{action}。

写作类型：{writing_type}
标题/主题：{title}
目标读者：{audience or '未指定'}
语气风格：{tone}
篇幅要求：{length or '按内容需要'}
补充要求：{requirements or '无'}

用户大纲：
{outline or '未提供'}

当前正文（改写时使用）：
{current or '无'}

上传素材：
{material_text or '无'}

知识库参考：
{kb_text or '无'}

输出要求：
- 使用规范的中文 Markdown：标题用 #/##/###，列表用 - 或 1. ，重点用 **加粗**。
- 严禁在每行开头添加「1、2、3、」这类行号前缀；不要在标题或分隔线后加句号。
- 直接输出正文本身，不要额外解释；内容结构完整、可直接复制使用。
- 若使用知识库资料，在相关段落保留 [知识库1] 这样的引用标记。
- 不要编造上传素材和知识库里没有的具体数字、日期、人名。
""".strip()


def _writing_strip_references(text):
    """去掉正文里已有的「参考资料」小节，避免改写时重复叠加。"""
    return re.split(r"\n#{1,6}\s*参考资料\s*\n", str(text or ""), maxsplit=1)[0].rstrip()


def _writing_append_references(content, sources):
    """把本次命中的知识库文档以「参考资料」小节追加到正文末尾，便于阅读与导出。"""
    content = _writing_strip_references(content)
    names = []
    for src in sources or []:
        name = str((src or {}).get("doc_name") or (src or {}).get("dataset_name") or "").strip()
        if name and name not in names:
            names.append(name)
    if not names:
        return content
    refs = "\n".join(f"{index}. {name}" for index, name in enumerate(names, start=1))
    return f"{content}\n\n## 参考资料\n\n{refs}\n"


def _writing_clean_markdown(text):
    """清洗模型输出：去掉非标准的「数字、」行号前缀，修复分隔线后多余的句号。

    标准 Markdown 有序列表用「1. 」（点+空格），这里只移除中文顿号「数字、」这种
    模型误加的行号，不会误伤正常有序列表。
    """
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    cleaned = []
    for line in lines:
        s = re.sub(r"^(\s*)\d+[、]\s*", r"\1", line)
        # 丢弃只剩 # 号的空标题行（如 "###" / "###。"）
        if re.match(r"^\s*#{1,6}[。.\s]*$", s):
            continue
        # 分隔线后误加的句号：---。/ ***。
        s = re.sub(r"^(\s*[-*_]{3,})[。.\s]*$", r"\1", s) if re.match(r"^\s*[-*_]{3,}[。.\s]*$", s) else s
        # 标题行末尾多余的句号
        s = re.sub(r"^(\s*#{1,6}\s+.*?)[。]\s*$", r"\1", s)
        cleaned.append(s)
    return "\n".join(cleaned).strip()


def _writing_call_ai(prompt, system):
    settings = assistant_settings()
    if not settings.get("url") or not settings.get("key"):
        return ""
    body = json.dumps(
        assistant_generation_payload(settings, {
            "model": settings["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.35,
        }),
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        settings["url"].rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["key"]},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return normalize_assistant_output(data["choices"][0]["message"]["content"].strip())


def _writing_local_draft(payload, materials, sources, mode="generate"):
    title = str(payload.get("title") or "未命名文稿").strip()
    writing_type = str(payload.get("writing_type") or "通用文章").strip()
    requirements = str(payload.get("requirements") or "").strip()
    if mode == "outline":
        return f"# {title}\n\n## 一、背景与目标\n## 二、核心内容\n## 三、实施安排\n## 四、风险与保障\n## 五、结论与下一步"
    parts = [f"# {title}", "", f"> 类型：{writing_type}"]
    if requirements:
        parts.extend(["", f"> 写作要求：{requirements}"])
    if payload.get("outline"):
        parts.extend(["", "## 大纲", str(payload.get("outline"))])
    parts.extend(["", "## 正文", f"围绕“{title}”，本文从背景、重点内容、执行建议和后续安排展开说明。"])
    if materials:
        parts.extend(["", "## 上传素材整理"])
        for item in materials:
            parts.append(f"### {item['name']}\n{item['text'][:1200]}")
    if sources:
        parts.extend(["", "## 知识库参考"])
        for index, item in enumerate(sources, start=1):
            parts.append(f"### [知识库{index}] {item.get('doc_name') or '参考资料'}\n{str(item.get('text') or '')[:800]}")
    parts.extend(["", "## 下一步建议", "- 根据实际业务口径补充关键数据。", "- 审核涉及日期、金额、责任人等敏感信息。"])
    return "\n".join(parts)


def _writing_save_history(payload, content, materials, sources, action="generate"):
    username = payload["_username"]
    item_id = payload.get("id") or _writing_id("doc")
    now = _writing_now()
    item = {
        "id": item_id,
        "title": str(payload.get("title") or "未命名文稿")[:120],
        "writing_type": str(payload.get("writing_type") or "通用文章")[:40],
        "requirements": str(payload.get("requirements") or "")[:4000],
        "outline": str(payload.get("outline") or "")[:12000],
        "content": content,
        "materials": [{"id": m["id"], "name": m["name"], "text_preview": m["text"][:300]} for m in materials],
        "sources": sources,
        "action": action,
        "created_at": now,
        "updated_at": now,
    }
    old = _writing_json_read(_writing_history_path(username, item_id), None)
    if old and old.get("created_at"):
        item["created_at"] = old["created_at"]
    _writing_json_write(_writing_history_path(username, item_id), item)
    return item


def writing_generate_outline(payload, username):
    payload = dict(payload or {})
    materials = _writing_collect_materials(payload, username)
    sources = _writing_knowledge_sources(payload, username)
    prompt = _writing_prompt(payload, materials, sources, "outline")
    try:
        content = _writing_call_ai(prompt, "你是企业写作大纲规划助手，只输出 Markdown 大纲。") or _writing_local_draft(payload, materials, sources, "outline")
        mode = "api" if content and assistant_settings().get("url") and assistant_settings().get("key") else "local"
    except Exception as exc:
        content = _writing_local_draft(payload, materials, sources, "outline") + f"\n\n> AI 生成失败，已使用本地大纲兜底：{exc}"
        mode = "local_fallback"
    return {"ok": True, "outline": _writing_clean_markdown(content), "mode": mode, "sources": sources}


def writing_generate(payload, username):
    payload = dict(payload or {})
    payload["_username"] = username
    materials = _writing_collect_materials(payload, username)
    sources = _writing_knowledge_sources(payload, username)
    prompt = _writing_prompt(payload, materials, sources, "generate")
    try:
        content = _writing_call_ai(prompt, "你是企业智能写作助手，擅长结合文件素材和知识库生成可直接使用的中文文稿。")
        mode = "api"
    except Exception as exc:
        content = ""
        mode = f"local_fallback: {exc}"
    if not content:
        content = _writing_local_draft(payload, materials, sources, "generate")
        if mode == "api":
            mode = "local"
    content = _writing_append_references(_writing_clean_markdown(content), sources)
    item = _writing_save_history(payload, content, materials, sources, "generate")
    return {"ok": True, "mode": mode, "item": item}


def writing_rewrite(payload, username):
    payload = dict(payload or {})
    payload["_username"] = username
    materials = _writing_collect_materials(payload, username)
    sources = _writing_knowledge_sources(payload, username)
    prompt = _writing_prompt(payload, materials, sources, "rewrite")
    try:
        content = _writing_call_ai(prompt, "你是企业文稿改写助手，按用户要求润色、扩写、缩写或调整语气。")
        mode = "api"
    except Exception as exc:
        content = ""
        mode = f"local_fallback: {exc}"
    if not content:
        base = str(payload.get("content") or "").strip()
        instruction = str(payload.get("rewrite_instruction") or payload.get("requirements") or "润色优化").strip()
        content = f"# {payload.get('title') or '改写文稿'}\n\n> 改写要求：{instruction}\n\n{base}"
        if not base:
            content = _writing_local_draft(payload, materials, sources, "generate")
    content = _writing_append_references(_writing_clean_markdown(content), sources)
    item = _writing_save_history(payload, content, materials, sources, "rewrite")
    return {"ok": True, "mode": mode, "item": item}


def writing_history(username):
    items = []
    for path in sorted((_writing_dir(username) / "history").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = _writing_json_read(path, None)
        if item:
            summary = dict(item)
            summary["content_preview"] = str(summary.get("content") or "")[:240]
            summary.pop("content", None)
            items.append(summary)
    return {"ok": True, "items": items}


def writing_get_history(item_id, username):
    item = _writing_json_read(_writing_history_path(username, item_id), None)
    if not item:
        raise ValueError("写作历史不存在")
    return {"ok": True, "item": item}


def writing_delete_history(payload, username):
    item_id = str((payload or {}).get("id") or "").strip()
    path = _writing_history_path(username, item_id)
    if not path.exists():
        raise ValueError("写作历史不存在")
    path.unlink()
    return {"ok": True, "deleted": item_id}


def _writing_content_from_payload(payload, username):
    content = str((payload or {}).get("content") or "")
    item_id = str((payload or {}).get("id") or "").strip()
    item = None
    if item_id:
        item = _writing_json_read(_writing_history_path(username, item_id), None)
        if item and not content:
            content = str(item.get("content") or "")
    if not content.strip():
        raise ValueError("没有可导出的正文")
    title = str((payload or {}).get("title") or (item or {}).get("title") or "智能写作文稿").strip()
    return title, content, item


WRITING_DOCX_CHINESE_FONT = "微软雅黑"
WRITING_DOCX_LATIN_FONT = "Arial"
WRITING_DOCX_BODY_FONT_SIZE = 10.5


def _writing_set_docx_run_font(run, latin_font=WRITING_DOCX_LATIN_FONT, chinese_font=WRITING_DOCX_CHINESE_FONT):
    """明确写入中西文字体，避免 Word 根据本机主题字体替换中文。"""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run.font.name = latin_font
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    r_fonts.set(qn("w:ascii"), latin_font)
    r_fonts.set(qn("w:hAnsi"), latin_font)
    r_fonts.set(qn("w:eastAsia"), chinese_font)
    r_fonts.set(qn("w:cs"), latin_font)


def _writing_configure_docx_styles(doc):
    """配置导出文档的基础样式，让正文、标题、列表和表格字体一致。"""
    from docx.shared import Pt

    style_sizes = {
        "Normal": WRITING_DOCX_BODY_FONT_SIZE,
        "List Bullet": WRITING_DOCX_BODY_FONT_SIZE,
        "List Number": WRITING_DOCX_BODY_FONT_SIZE,
        "Intense Quote": WRITING_DOCX_BODY_FONT_SIZE,
        "Heading 1": 16,
        "Heading 2": 14,
        "Heading 3": 12,
        "Heading 4": 11,
    }
    for style_name, size in style_sizes.items():
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        style.font.name = WRITING_DOCX_LATIN_FONT
        style.font.size = Pt(size)
        r_pr = style._element.get_or_add_rPr()
        # 复用 run 的设置逻辑所需的 XML 属性，样式与直接写入的 run 保持一致。
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        r_fonts = r_pr.rFonts
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.insert(0, r_fonts)
        r_fonts.set(qn("w:ascii"), WRITING_DOCX_LATIN_FONT)
        r_fonts.set(qn("w:hAnsi"), WRITING_DOCX_LATIN_FONT)
        r_fonts.set(qn("w:eastAsia"), WRITING_DOCX_CHINESE_FONT)
        r_fonts.set(qn("w:cs"), WRITING_DOCX_LATIN_FONT)


def _writing_docx_runs(paragraph, text):
    """把行内 Markdown（**加粗**、*斜体*、`代码`）转成 Word run。"""
    def add_run(value, latin_font=WRITING_DOCX_LATIN_FONT):
        run = paragraph.add_run(value)
        _writing_set_docx_run_font(run, latin_font=latin_font)
        return run

    pos = 0
    for m in re.finditer(r"\*\*(.+?)\*\*|__(.+?)__|(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|`(.+?)`", text):
        if m.start() > pos:
            add_run(text[pos:m.start()])
        bold = m.group(1) if m.group(1) is not None else m.group(2)
        italic = m.group(3)
        code = m.group(4)
        if bold is not None:
            add_run(bold).bold = True
        elif italic is not None:
            add_run(italic).italic = True
        elif code is not None:
            add_run(code, latin_font="Consolas")
        pos = m.end()
    if pos < len(text):
        add_run(text[pos:])


def _writing_markdown_table_cells(line):
    """解析一行 GFM 表格；兼容模型在行末误加的中文句号。"""
    value = str(line or "").strip()
    value = re.sub(r"\|\s*[。．]\s*$", "|", value)
    if not (value.startswith("|") and value.endswith("|")):
        return None
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", value)[1:-1]]


def _writing_markdown_table_separator(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _writing_markdown_tables(content):
    """提取 Markdown 正文中的 GFM 表格，兼容模型在行尾误加的中文句号。"""
    lines = str(content or "").splitlines()
    tables = []
    index = 0
    while index < len(lines):
        headers = _writing_markdown_table_cells(lines[index])
        separator = _writing_markdown_table_cells(lines[index + 1]) if index + 1 < len(lines) else None
        if not (headers and separator and len(headers) == len(separator) and _writing_markdown_table_separator(separator)):
            index += 1
            continue
        rows = []
        index += 2
        while index < len(lines):
            row = _writing_markdown_table_cells(lines[index])
            if not row:
                break
            rows.append(row)
            index += 1
        tables.append((headers, rows))
    return tables


def _writing_add_docx_table(doc, headers, rows):
    columns = len(headers)
    table = doc.add_table(rows=1, cols=columns)
    table.style = "Table Grid"
    for index, text in enumerate(headers):
        paragraph = table.cell(0, index).paragraphs[0]
        _writing_docx_runs(paragraph, text)
        for run in paragraph.runs:
            run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for index in range(columns):
            _writing_docx_runs(cells[index].paragraphs[0], row[index] if index < len(row) else "")


def _writing_markdown_to_docx(doc, content):
    """把 Markdown 正文转换成结构化 Word 文档（含原生表格）。"""
    _writing_configure_docx_styles(doc)
    lines = str(content or "").splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        # GFM 表格：首行 + 分隔行 + 任意数量的数据行。表格逐单元格写入 Word，
        # 不再把 | ... | 导出为普通段落。
        headers = _writing_markdown_table_cells(stripped)
        separator = _writing_markdown_table_cells(lines[index + 1]) if index + 1 < len(lines) else None
        if headers and separator and len(headers) == len(separator) and _writing_markdown_table_separator(separator):
            rows = []
            index += 2
            while index < len(lines):
                row = _writing_markdown_table_cells(lines[index])
                if not row:
                    break
                rows.append(row)
                index += 1
            _writing_add_docx_table(doc, headers, rows)
            continue
        # 水平分隔线，Word 里忽略
        if re.fullmatch(r"[-*_]{3,}", stripped):
            index += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level = min(len(heading.group(1)), 4)
            doc.add_heading(heading.group(2).strip().strip("#").strip(), level=level)
            index += 1
            continue
        # 无序列表
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        if bullet:
            _writing_docx_runs(doc.add_paragraph(style="List Bullet"), bullet.group(1))
            index += 1
            continue
        # 有序列表
        ordered = re.match(r"^\d+[.、)]\s+(.*)$", stripped)
        if ordered:
            _writing_docx_runs(doc.add_paragraph(style="List Number"), ordered.group(1))
            index += 1
            continue
        # 引用
        quote = re.match(r"^>\s?(.*)$", stripped)
        if quote:
            p = doc.add_paragraph(style="Intense Quote")
            _writing_docx_runs(p, quote.group(1))
            index += 1
            continue
        _writing_docx_runs(doc.add_paragraph(), stripped)
        index += 1


def _writing_export_xlsx(path, content):
    """将正文中的 Markdown 表格导出为原生 Excel 工作表。"""
    tables = _writing_markdown_tables(content)
    if not tables:
        raise ValueError("正文中未识别到可导出的表格，请先使用 Markdown 表格格式编写内容")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ValueError("Excel 导出组件不可用，请联系管理员安装 openpyxl") from exc

    workbook = Workbook()
    workbook.remove(workbook.active)
    border = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    header_fill = PatternFill("solid", fgColor="1F5AA6")
    for table_index, (headers, rows) in enumerate(tables, start=1):
        sheet = workbook.create_sheet(f"表格{table_index}")
        for column, value in enumerate(headers, start=1):
            cell = sheet.cell(row=1, column=column, value=value)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        for row_index, row in enumerate(rows, start=2):
            for column in range(1, len(headers) + 1):
                cell = sheet.cell(row=row_index, column=column, value=row[column - 1] if column <= len(row) else "")
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = border
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(rows) + 1)}"
        for column in range(1, len(headers) + 1):
            values = [str(headers[column - 1])] + [str(row[column - 1]) if column <= len(row) else "" for row in rows]
            sheet.column_dimensions[get_column_letter(column)].width = min(42, max(10, max(len(value) for value in values) + 2))
    workbook.save(path)


def writing_export(payload, username):
    payload = payload or {}
    title, content, item = _writing_content_from_payload(payload, username)
    content = _writing_clean_markdown(content)
    fmt = str(payload.get("format") or "md").lower()
    if fmt not in {"md", "txt", "docx", "xlsx"}:
        raise ValueError("导出格式只支持 md/txt/docx/xlsx")
    export_id = _writing_id("export")
    safe_title = re.sub(r"[^0-9A-Za-z.\-\u4e00-\u9fff]+", "_", title)[:80] or "智能写作文稿"
    path = _writing_dir(username) / "exports" / f"{safe_title}-{export_id}.{fmt}"
    if fmt in {"md", "txt"}:
        path.write_text(content, encoding="utf-8")
    elif fmt == "xlsx":
        _writing_export_xlsx(path, content)
    else:
        try:
            from docx import Document

            doc = Document()
            _writing_markdown_to_docx(doc, content)
            doc.save(path)
        except Exception:
            path = path.with_suffix(".md")
            path.write_text(content, encoding="utf-8")
            fmt = "md"
    return {"ok": True, "format": fmt, "name": path.name, "path": str(path), "download_url": f"/api/writing/download?file={urllib.parse.quote(path.name)}"}
