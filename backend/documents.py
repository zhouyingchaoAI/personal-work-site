"""Uploads, prefill logic, weekly/trip document generation, drafts, and sending.

This module is loaded by backend.runtime into one shared application namespace.
Keep feature code here grouped by responsibility; cross-feature functions remain available
through the runtime during this incremental modularization.
"""

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


def generated_report_path(name, username=None):
    base = user_report_dir(username) if username else REPORT_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(1, 1000):
        candidate = base / f"{stem}-生成{idx}{suffix}"
        if not candidate.exists():
            return candidate
    raise ValueError("同名生成文件过多，请调整日期或文件名后再生成")


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

    def find_section_row(keyword):
        for row in range(1, ws.max_row + 1):
            text = "".join(str(ws.cell(row, col).value or "") for col in range(1, min(ws.max_column, 8) + 1))
            if keyword in text:
                return row
        return 0

    def next_section_row(after_row):
        candidates = [
            row
            for row in (find_section_row("重点工作跟进"), find_section_row("下周工作计划"))
            if row > after_row
        ]
        return min(candidates) if candidates else ws.max_row + 1

    follow_section = find_section_row("重点工作跟进")
    next_section = find_section_row("下周工作计划")

    summary = []
    summary_rows = []
    next_start = next_section + 2 if next_section else 18
    next_end = next_section_row(next_section) - 1 if next_section else min(ws.max_row, 26)
    for row in range(next_start, min(ws.max_row, next_end) + 1):
        category = cell_value(ws, row, 2)
        content = normalize_numbered_text(cell_value(ws, row, 3))
        if category in {"工作分类", "三、下周工作计划"} or content == "工作内容":
            continue
        if category or content:
            # 本周总结继承上周计划：工作分类 | 工作内容 | 完成情况 | 后续计划
            summary.append(xlsx_row_text([category, content, "", ""]))
            summary_rows.append({"category": category, "content": content, "status": "", "plan": ""})

    follow = []
    follow_rows = []
    follow_start = follow_section + 2 if follow_section else 11
    follow_end = next_section - 1 if next_section else min(ws.max_row, 15)
    for row in range(follow_start, min(ws.max_row, follow_end) + 1):
        category = cell_value(ws, row, 2)
        content = normalize_numbered_text(cell_value(ws, row, 3))
        progress = normalize_numbered_text(cell_value(ws, row, 4))
        difficulty = normalize_numbered_text(cell_value(ws, row, 6))
        if category in {"工作分类", "二、重点工作跟进", "三、下周工作计划"} or content == "工作内容":
            continue
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
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    template = Path((newest_any("weekly", username, fallback_shared=True) or {}).get("path", ""))
    if not template.exists() or not template.is_file():
        raise ValueError("没有找到周报模板")

    period = (payload.get("period") or datetime.now().strftime("%Y.%m.%d-%Y.%m.%d")).strip()
    safe_period = re.sub(r"[^0-9A-Za-z.\-\u4e00-\u9fff]+", "", period)
    output = generated_report_path(f"周颖超工作周报{safe_period}.xlsx", username)
    if template.resolve() == output.resolve():
        fallback = newest("weekly", username, fallback_shared=True)
        if fallback and Path(fallback.get("path", "")).resolve() != output.resolve():
            template = Path(fallback["path"])
    shutil.copy2(template, output)

    wb = load_workbook(output)
    ws = wb[wb.sheetnames[0]]

    for mc in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(mc))
    ws.delete_rows(1, max(ws.max_row, 1))

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = None
    widths = {"A": 3, "B": 30, "C": 34, "D": 34, "E": 25, "F": 32}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

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
    title_fill = PatternFill("solid", fgColor="00A9D6")
    white_fill = PatternFill("solid", fgColor="FFFFFF")
    header_font = Font(name="宋体", size=12, bold=True)
    body_font = Font(name="宋体", size=11, bold=True)
    title_font = Font(name="宋体", size=20, bold=True, color="000000")

    def merge_safe(min_r, min_c, max_r, max_c):
        try:
            ws.merge_cells(start_row=min_r, start_column=min_c, end_row=max_r, end_column=max_c)
        except Exception:
            pass

    def write_and_style(row_idx, col_idx, value, halign="left", valign="center", font=None, fill=None, normalize=True):
        cell = ws.cell(row_idx, col_idx)
        cell.value = normalize_numbered_text(value) if normalize else value
        cell.border = thin_border
        cell.font = font or body_font
        if fill:
            cell.fill = fill
        cell.alignment = Alignment(wrap_text=True, horizontal=halign, vertical=valign)

    def write_section_title(row_idx, title):
        for col_idx in range(2, 7):
            write_and_style(row_idx, col_idx, "", halign="left", font=header_font, fill=white_fill)
        write_and_style(row_idx, 2, title, halign="left", font=header_font, fill=white_fill)
        merge_safe(row_idx, 2, row_idx, 6)
        ws.row_dimensions[row_idx].height = 32

    def write_header(row_idx, labels, merges=None):
        for col_idx in range(2, 7):
            write_and_style(row_idx, col_idx, "", halign="center", font=header_font, fill=white_fill, normalize=False)
        for col_idx, label in labels:
            write_and_style(row_idx, col_idx, label, halign="center", font=header_font, fill=white_fill, normalize=False)
        for merge in merges or []:
            merge_safe(row_idx, merge[0], row_idx, merge[1])
        ws.row_dimensions[row_idx].height = 28

    def write_title(row_idx):
        for col_idx in range(2, 7):
            write_and_style(row_idx, col_idx, "", halign="center", font=title_font, fill=title_fill, normalize=False)
        write_and_style(row_idx, 2, f"工作周报（{period}）", halign="center", font=title_font, fill=title_fill, normalize=False)
        merge_safe(row_idx, 2, row_idx, 6)
        ws.row_dimensions[row_idx].height = 44

    write_title(1)

    summary_title = 2
    summary_header = 3
    summary_start = 4
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

    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = f"B1:F{next_start + len(next_rows) - 1}"

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

    start = (payload.get("trip_start") or datetime.now().strftime("%Y%m%d")).replace("-", "")
    end = (payload.get("trip_end") or start).replace("-", "")[-4:]
    output = generated_report_path(f"出差报告-{start}-{end}-周颖超.docx", username)
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
