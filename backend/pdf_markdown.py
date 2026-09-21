"""PDF 解析成 Markdown 工具（知识库助手）。

流程：
1. 上传 PDF -> 服务端用 PyMuPDF 渲染每页为图片（供 review 对照/绘图框取），
   并生成一份"快速文本层" Markdown 作为初稿。
2. 调 RAGFlow 的 DeepDoc OCR（/v1/document/parse）把整份 PDF 解析成 Markdown，
   与页面图片左右对照 review。
3. 对图文错配的部分，前端用绘图工具在页面上框取一块区域，服务端把该区域裁剪成
   单页 PDF 再交给 RAGFlow OCR，得到"子 Markdown"，插入回完整 Markdown。

所有能力（整份/区域 OCR）都走 RAGFlow，网关只负责渲染、裁剪、存储与身份隔离。

依赖 backend.runtime 注入的共享运行时：USER_DATA_DIR、safe_username、
kb_embedding_settings、_ragflow_ready、_ragflow_user_settings、_ragflow_named_dataset、
_ragflow_upload、_ragflow_request、_ragflow_doc_status、kb_upload 等。
"""

import threading
import time

PDFMD_STAGING_NAME = "PDF解析暂存"  # 每用户一个隐藏数据集，OCR 完读走分块后即删文档。
# 生成的 Markdown 里图片引用的公网 API 前缀（同源，nginx 反代到后端，带 cookie 鉴权）。
# 不用前端开发代理 /personal-work-api：导出的 Markdown 在生产页面预览时必须直达
# /personal-office-assistant 下的真实后端路由。
PDFMD_ASSET_PREFIX = "/personal-office-assistant/api/knowledge/pdf-md/asset"
PDFMD_MIN_FIGURE_FRAC = 0.012  # 小于页面面积此比例的图忽略（图标/线条噪点）。
PDFMD_MAX_FIGURE_FRAC = 0.9    # 大于页面面积此比例的图忽略（多为扫描整页背景）。
PDFMD_ZOOM = 2.0  # 页面预览渲染倍率（约 144 DPI）。
PDFMD_REGION_ZOOM = 3.0  # 区域裁剪送 OCR 的倍率（约 216 DPI，保证清晰度）。
PDFMD_MAX_FILE_BYTES = 60 * 1024 * 1024
PDFMD_MAX_PAGES = 400


def _pdfmd_root(username: str):
    path = USER_DATA_DIR / safe_username(username) / "pdf_markdown"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pdfmd_safe_job(job_id: str) -> str:
    safe = Path(str(job_id or "")).name
    if not safe or not re.match(r"^[0-9A-Za-z_-]+$", safe):
        raise ValueError("任务 ID 无效")
    return safe


def _pdfmd_job_dir(username: str, job_id: str, create: bool = False):
    path = _pdfmd_root(username) / _pdfmd_safe_job(job_id)
    if create:
        (path / "pages").mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        raise ValueError("任务不存在或已删除")
    return path


def _pdfmd_meta_path(job_dir):
    return job_dir / "meta.json"


def _pdfmd_load_meta(job_dir) -> dict:
    try:
        return json.loads(_pdfmd_meta_path(job_dir).read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("任务数据已损坏")


def _pdfmd_save_meta(job_dir, meta: dict):
    _pdfmd_meta_path(job_dir).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _pdfmd_open(job_dir):
    import fitz

    return fitz.open(str(job_dir / "source.pdf"))


def _pdfmd_decode_upload(payload: dict) -> tuple:
    filename = Path(str(payload.get("filename", "") or "document.pdf")).name
    if not filename.lower().endswith(".pdf"):
        raise ValueError("仅支持 PDF 文件")
    data = str(payload.get("data", "") or "")
    if "," in data and data.strip().lower().startswith("data:"):
        data = data.split(",", 1)[1]
    raw = base64.b64decode(data) if data else b""
    if not raw:
        raise ValueError("文件内容为空")
    if len(raw) > PDFMD_MAX_FILE_BYTES:
        raise ValueError(f"文件超过 {PDFMD_MAX_FILE_BYTES // (1024 * 1024)}MB 限制")
    return filename, raw


def _pdfmd_render_pages(job_dir, doc) -> list:
    """渲染每页为 PNG，返回页面尺寸信息（像素）。"""
    import fitz

    pages_dir = job_dir / "pages"
    pages = []
    mat = fitz.Matrix(PDFMD_ZOOM, PDFMD_ZOOM)
    for index in range(doc.page_count):
        page = doc[index]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        (pages_dir / f"{index + 1}.png").write_bytes(pix.tobytes("png"))
        pages.append({"page": index + 1, "width": pix.width, "height": pix.height})
    return pages


def _pdfmd_fitz_markdown(doc, job_dir=None, job_id: str = "") -> str:
    """PDF 文本层初稿，带真实页标题和已抽取的图片 URL（无需等待 OCR）。"""
    parts = []
    for index in range(doc.page_count):
        page = doc[index]
        figures = _pdfmd_extract_figures(doc, job_dir, index) if job_dir and job_id else []
        body = _pdfmd_page_layout_markdown(page, figures, job_id, index + 1) if figures else None
        if body is None:
            text = (page.get_text("text") or "").strip()
            page_parts = [text] if text else ["_（此页无文本层，请使用 OCR 解析）_"]
            page_parts.extend(_pdfmd_asset_md(job_id, fig["name"], f"第{index + 1}页 图{fig['order']}") for fig in figures)
            body = "\n\n".join(page_parts)
        parts.append(f"## 第 {index + 1} 页\n\n{body}")
    return "\n\n".join(parts).strip()


# ---- RAGFlow DeepDoc OCR 调用 ----
# /v1/document/parse 只抽文本层、不做真正 OCR；扫描件与栅格化区域会返回空。
# 因此走数据集解析管线（chunk_method=naive + layout_recognize=DeepDOC）拿真实 OCR，
# 每用户一个隐藏暂存数据集，读完分块后立即删除该文档，保持干净。

def _pdfmd_staging_dataset(username: str):
    settings = kb_embedding_settings()
    if settings["provider"] != "ragflow":
        raise ValueError("请先在设置中把知识库引擎切换为 RAGFlow")
    _ragflow_ready(settings)
    user_settings = _ragflow_user_settings(settings, username)
    safe = str(username or "anonymous")
    dataset_id = _ragflow_named_dataset(user_settings, PDFMD_STAGING_NAME, f"pdfmd::{safe}")
    return user_settings, dataset_id


def _pdfmd_deepdoc_ocr(user_settings: dict, dataset_id: str, filename: str, raw: bytes, timeout: int = 300) -> str:
    """上传 PDF 到暂存数据集 -> DeepDoc 解析 -> 轮询完成 -> 读分块拼 Markdown -> 删文档。"""
    doc = _ragflow_upload(filename, raw, user_settings, dataset_id, "")
    doc_id = doc.get("id", "")
    if not doc_id:
        raise ValueError("RAGFlow 上传失败，未返回文档 ID")
    try:
        deadline = time.time() + timeout
        status = "parsing"
        while time.time() < deadline:
            data = _ragflow_request(
                user_settings, "GET",
                f"/api/v1/datasets/{dataset_id}/documents?id={doc_id}&page=1&page_size=1",
            ) or {}
            docs = data.get("docs", []) or []
            item = next((d for d in docs if d.get("id") == doc_id), docs[0] if docs else {})
            status = _ragflow_doc_status(item)
            if status == "":
                break
            if status == "failed":
                raise ValueError("RAGFlow 解析失败：" + str(item.get("progress_msg", "") or "")[-120:])
            time.sleep(2)
        else:
            raise ValueError("RAGFlow 解析超时，请稍后重试或缩小框选范围")
        return _pdfmd_read_chunks(user_settings, dataset_id, doc_id)
    finally:
        try:
            _ragflow_request(user_settings, "DELETE", f"/api/v1/datasets/{dataset_id}/documents", {"ids": [doc_id]})
        except Exception:
            pass


def _pdfmd_single_page_pdf(doc, page_index: int) -> bytes:
    """从源文档抽取一页为独立 PDF（保留文本层/矢量，供逐页 OCR）。"""
    import fitz

    out = fitz.open()
    out.insert_pdf(doc, from_page=page_index, to_page=page_index)
    return out.tobytes()


def _pdfmd_extract_figures(doc, job_dir, page_index: int) -> list:
    """用 PyMuPDF 抽取某页内嵌的位图图片（按从上到下、从左到右排序），保存到 images/。

    返回 [{name, order}]，name 为文件名（供 asset 路由与 Markdown 引用）。
    忽略过小（噪点）与几乎铺满整页（扫描背景）的图片。
    """
    page = doc[page_index]
    page_area = max(1.0, page.rect.width * page.rect.height)
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    seen_xrefs = set()
    candidates = []
    for info in page.get_image_info(xrefs=True):
        xref = info.get("xref", 0)
        bbox = info.get("bbox") or (0, 0, 0, 0)
        area = max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        frac = area / page_area
        if frac < PDFMD_MIN_FIGURE_FRAC or frac > PDFMD_MAX_FIGURE_FRAC:
            continue
        if not xref or xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        candidates.append((round(bbox[1], 1), round(bbox[0], 1), xref))

    candidates.sort()
    figures = []
    for order, (top, left, xref) in enumerate(candidates, start=1):
        try:
            extracted = doc.extract_image(xref)
        except Exception:
            continue
        ext = (extracted.get("ext") or "png").lower()
        if ext not in ("png", "jpg", "jpeg", "webp", "gif", "bmp"):
            ext = "png"
        name = f"p{page_index + 1}_{order}.{ext}"
        (images_dir / name).write_bytes(extracted.get("image", b""))
        # bbox 记录用于按版面把图片插回文字之间（图文并茂）。
        bbox = next((i.get("bbox") for i in page.get_image_info(xrefs=True) if i.get("xref") == xref), (left, top, left, top))
        figures.append({"name": name, "order": order, "bbox": list(bbox)})
    return figures


def _pdfmd_page_layout_markdown(page, figures: list, job_id: str, page_no: int) -> str:
    """有文本层时，按版面阅读顺序把文字块与图片交错排布（保留图-文对应关系）。

    适合"图片+说明"的卡片式排版（如缺陷照片配图号/部位）。返回 None 表示文本层不足，
    应回退到 DeepDoc OCR。
    """
    blocks = page.get_text("blocks", sort=True) or []
    text_items = [b for b in blocks if len(b) >= 7 and b[6] == 0 and str(b[4]).strip()]
    total_chars = sum(len(str(b[4]).strip()) for b in text_items)
    if total_chars < 20:
        return None

    figures = sorted(figures, key=lambda fig: ((fig.get("bbox") or [0, 0, 0, 0])[1], (fig.get("bbox") or [0, 0, 0, 0])[0]))
    captions = [[] for _ in figures]
    standalone = []
    # 卡片常见排版是照片左、字段右（或字段在照片下）。将该区域的文本绑定到照片，
    # 让线性的 Markdown 也保持「图 URL → 本图说明」的可读顺序。
    side_gap = max(36.0, page.rect.width * 0.18)
    below_gap = max(30.0, page.rect.height * 0.10)
    for block in text_items:
        x0, y0, x1, y1 = block[:4]
        best = None
        for index, fig in enumerate(figures):
            fx0, fy0, fx1, fy1 = fig.get("bbox") or [0, 0, 0, 0]
            vertically_aligned = y1 >= fy0 and y0 <= fy1
            if vertically_aligned and x0 >= fx1 and x0 - fx1 <= side_gap:
                score = (0, x0 - fx1, abs((y0 + y1) - (fy0 + fy1)))
            elif y0 >= fy1 and y0 - fy1 <= below_gap and x1 >= fx0 and x0 <= fx1:
                score = (1, y0 - fy1, abs((x0 + x1) - (fx0 + fx1)))
            else:
                continue
            if best is None or score < best[0]:
                best = (score, index)
        if best is None:
            standalone.append((y0, x0, str(block[4]).strip()))
        else:
            captions[best[1]].append((y0, x0, str(block[4]).strip()))

    out = [text for _y, _x, text in sorted(standalone)]
    for index, fig in enumerate(figures):
        out.append(_pdfmd_asset_md(job_id, fig["name"], f"第{page_no}页 图{fig['order']}"))
        caption_lines = []
        for _y, _x, text in sorted(captions[index]):
            caption_lines.extend(line.strip() for line in text.splitlines() if line.strip())
        if caption_lines:
            out.append("- " + caption_lines[0] + "\n" + "\n".join("  - " + line for line in caption_lines[1:]))
    return "\n\n".join(out).strip()


def _pdfmd_asset_md(job_id: str, name: str, alt: str) -> str:
    return f"![{alt}]({PDFMD_ASSET_PREFIX}?job_id={job_id}&name={name})"


def _pdfmd_read_chunks(user_settings: dict, dataset_id: str, doc_id: str) -> str:
    parts = []
    page = 1
    while True:
        data = _ragflow_request(
            user_settings, "GET",
            f"/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks?page={page}&page_size=100",
        ) or {}
        chunks = data.get("chunks") or []
        for chunk in chunks:
            text = str(chunk.get("content", "") or chunk.get("content_with_weight", "") or "").strip()
            if text:
                parts.append(text)
        total = int(data.get("total", 0) or 0)
        if len(chunks) < 100 or (total and page * 100 >= total):
            break
        page += 1
    return "\n\n".join(parts).strip()


def _pdfmd_region_pdf(job_dir, page: int, rect: dict) -> bytes:
    """把页面上一块矩形区域（比例坐标 0~1）裁剪并渲染成单页 PDF，供 OCR。"""
    import fitz

    x0 = max(0.0, min(1.0, float(rect.get("x0", 0))))
    y0 = max(0.0, min(1.0, float(rect.get("y0", 0))))
    x1 = max(0.0, min(1.0, float(rect.get("x1", 1))))
    y1 = max(0.0, min(1.0, float(rect.get("y1", 1))))
    if x1 - x0 < 0.005 or y1 - y0 < 0.005:
        raise ValueError("框选区域太小，请重新框选")
    doc = _pdfmd_open(job_dir)
    try:
        if page < 1 or page > doc.page_count:
            raise ValueError("页码超出范围")
        src = doc[page - 1]
        r = src.rect
        clip = fitz.Rect(
            r.x0 + x0 * r.width,
            r.y0 + y0 * r.height,
            r.x0 + x1 * r.width,
            r.y0 + y1 * r.height,
        )
        pix = src.get_pixmap(matrix=fitz.Matrix(PDFMD_REGION_ZOOM, PDFMD_REGION_ZOOM), clip=clip, alpha=False)
        png = pix.tobytes("png")
        out = fitz.open()
        out_page = out.new_page(width=pix.width, height=pix.height)
        out_page.insert_image(fitz.Rect(0, 0, pix.width, pix.height), stream=png)
        return out.tobytes()
    finally:
        doc.close()


def _pdfmd_region_figures(job_dir, page: int, rect: dict) -> list:
    """提取与比例框选区域相交的原始图片，供区域 OCR 结果内联引用。"""
    import fitz

    x0 = max(0.0, min(1.0, float(rect.get("x0", 0))))
    y0 = max(0.0, min(1.0, float(rect.get("y0", 0))))
    x1 = max(0.0, min(1.0, float(rect.get("x1", 1))))
    y1 = max(0.0, min(1.0, float(rect.get("y1", 1))))
    doc = _pdfmd_open(job_dir)
    try:
        if page < 1 or page > doc.page_count:
            raise ValueError("页码超出范围")
        src = doc[page - 1]
        bounds = src.rect
        clip = fitz.Rect(
            bounds.x0 + x0 * bounds.width,
            bounds.y0 + y0 * bounds.height,
            bounds.x0 + x1 * bounds.width,
            bounds.y0 + y1 * bounds.height,
        )
        figures = _pdfmd_extract_figures(doc, job_dir, page - 1)
        return [fig for fig in figures if fitz.Rect(fig.get("bbox") or ()).intersects(clip)]
    finally:
        doc.close()


# ---- 对外接口 ----

def pdf_md_list(username: str = "") -> dict:
    root = _pdfmd_root(username)
    jobs = []
    for entry in sorted(root.glob("*"), key=lambda p: p.name, reverse=True):
        if not entry.is_dir():
            continue
        try:
            meta = _pdfmd_load_meta(entry)
        except Exception:
            continue
        jobs.append({
            "id": meta.get("id", entry.name),
            "filename": meta.get("filename", ""),
            "created_at": meta.get("created_at", ""),
            "page_count": meta.get("page_count", 0),
            "ocr_engine": meta.get("ocr_engine", ""),
            "ocr_done": bool(meta.get("ocr_done")),
        })
    return {"ok": True, "jobs": jobs}


def pdf_md_create(payload: dict, username: str = "") -> dict:
    """上传 PDF：保存、渲染页面、生成文本层初稿。OCR 解析走单独接口。"""
    filename, raw = _pdfmd_decode_upload(payload or {})
    job_id = "pm" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
    job_dir = _pdfmd_job_dir(username, job_id, create=True)
    (job_dir / "source.pdf").write_bytes(raw)

    doc = _pdfmd_open(job_dir)
    try:
        if doc.page_count > PDFMD_MAX_PAGES:
            raise ValueError(f"PDF 页数超过 {PDFMD_MAX_PAGES} 页限制")
        pages = _pdfmd_render_pages(job_dir, doc)
        markdown = _pdfmd_fitz_markdown(doc, job_dir, job_id)
        page_count = doc.page_count
    finally:
        doc.close()

    meta = {
        "id": job_id,
        "filename": filename,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "page_count": page_count,
        "pages": pages,
        "zoom": PDFMD_ZOOM,
        "ocr_engine": "fitz-text",
        "ocr_done": False,
        "markdown": markdown,
        "parse_status": "idle",
        "parse_progress": 0,
        "parse_page": 0,
        "parse_error": "",
    }
    _pdfmd_save_meta(job_dir, meta)
    return {"ok": True, "job": _pdfmd_meta_public(meta)}


def _pdfmd_meta_public(meta: dict) -> dict:
    return {
        "id": meta.get("id", ""),
        "filename": meta.get("filename", ""),
        "created_at": meta.get("created_at", ""),
        "page_count": meta.get("page_count", 0),
        "pages": meta.get("pages", []),
        "zoom": meta.get("zoom", PDFMD_ZOOM),
        "ocr_engine": meta.get("ocr_engine", ""),
        "ocr_done": bool(meta.get("ocr_done")),
        "markdown": meta.get("markdown", ""),
        "parse_status": meta.get("parse_status", "idle"),
        "parse_progress": int(meta.get("parse_progress", 0) or 0),
        "parse_page": int(meta.get("parse_page", 0) or 0),
        "parse_error": meta.get("parse_error", ""),
    }


def pdf_md_get(job_id: str, username: str = "") -> dict:
    job_dir = _pdfmd_job_dir(username, job_id)
    meta = _pdfmd_load_meta(job_dir)
    return {"ok": True, "job": _pdfmd_meta_public(meta)}


def pdf_md_page_image(job_id: str, page: str, username: str = "") -> tuple:
    """返回某页 PNG（name, bytes），供二进制路由输出。"""
    job_dir = _pdfmd_job_dir(username, job_id)
    try:
        page_no = int(page)
    except (TypeError, ValueError):
        raise ValueError("页码无效")
    path = job_dir / "pages" / f"{page_no}.png"
    if not path.exists():
        raise ValueError("页面不存在")
    return f"{job_id}-{page_no}.png", path.read_bytes()


def pdf_md_asset(job_id: str, name: str, username: str = "") -> tuple:
    """返回抽取出的图片资源（name, content_type, bytes），供 Markdown 内联展示。"""
    job_dir = _pdfmd_job_dir(username, job_id)
    safe = Path(str(name or "")).name
    if not safe or not re.match(r"^[0-9A-Za-z_.-]+$", safe):
        raise ValueError("资源名无效")
    path = job_dir / "images" / safe
    if not path.exists():
        raise ValueError("资源不存在")
    ext = safe.rsplit(".", 1)[-1].lower()
    content_type = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
    }.get(ext, "application/octet-stream")
    return safe, content_type, path.read_bytes()


_PDFMD_PARSE_LOCK = threading.Lock()
_PDFMD_PARSING = set()  # 正在解析的 job_id，避免重复启动。


def pdf_md_parse(payload: dict, username: str = "") -> dict:
    """启动后台逐页 DeepDoc OCR，生成图文并茂的 Markdown。前端轮询 pdf-md/get 取进度。"""
    payload = payload or {}
    job_dir = _pdfmd_job_dir(username, payload.get("job_id"))
    meta = _pdfmd_load_meta(job_dir)
    job_id = meta.get("id", "")
    # 提前校验引擎，避免后台线程里静默失败。
    _pdfmd_staging_dataset(username)

    with _PDFMD_PARSE_LOCK:
        if job_id in _PDFMD_PARSING or meta.get("parse_status") == "running":
            return {"ok": True, "status": "running", "job": _pdfmd_meta_public(meta)}
        _PDFMD_PARSING.add(job_id)

    meta["parse_status"] = "running"
    meta["parse_progress"] = 0
    meta["parse_page"] = 0
    meta["parse_error"] = ""
    _pdfmd_save_meta(job_dir, meta)

    thread = threading.Thread(target=_pdfmd_parse_worker, args=(username, job_dir, job_id), daemon=True)
    thread.start()
    return {"ok": True, "status": "running", "job": _pdfmd_meta_public(meta)}


def _pdfmd_parse_worker(username: str, job_dir, job_id: str):
    """后台逐页解析：每页 DeepDoc OCR 文本 + PyMuPDF 抽图，拼成图文并茂 Markdown。"""
    import fitz

    try:
        user_settings, dataset_id = _pdfmd_staging_dataset(username)
        doc = fitz.open(str(job_dir / "source.pdf"))
        try:
            page_count = doc.page_count
            meta = _pdfmd_load_meta(job_dir)
            filename = meta.get("filename", "document.pdf")
            sections = []
            for index in range(page_count):
                figures = _pdfmd_extract_figures(doc, job_dir, index)
                page = doc[index]
                body = None
                # 多图卡片式排版且有文本层：按版面交错图文，保留图-文对应（不必逐页 OCR）。
                if len(figures) >= 2:
                    body = _pdfmd_page_layout_markdown(page, figures, job_id, index + 1)
                if body is None:
                    # 表格/纯文本/扫描页：走 DeepDoc OCR（表格会输出 HTML），OCR 空则回退文本层。
                    page_pdf = _pdfmd_single_page_pdf(doc, index)
                    try:
                        text = _pdfmd_deepdoc_ocr(user_settings, dataset_id, f"{filename}-p{index + 1}.pdf", page_pdf, timeout=240)
                    except Exception as exc:
                        text = f"_（第 {index + 1} 页 OCR 失败：{exc}）_"
                    if not text.strip():
                        text = (page.get_text("text") or "").strip()
                    parts = [text.strip()] if text.strip() else []
                    for fig in figures:
                        parts.append(_pdfmd_asset_md(job_id, fig["name"], f"第{index + 1}页 图{fig['order']}"))
                    body = "\n\n".join(parts).strip()
                sections.append((f"## 第 {index + 1} 页\n\n" + body).strip())
                # 逐页写回，前端轮询即可看到增量结果与进度。
                meta = _pdfmd_load_meta(job_dir)
                meta["markdown"] = "\n\n".join(sections).strip()
                meta["parse_page"] = index + 1
                meta["parse_progress"] = int((index + 1) * 100 / max(1, page_count))
                meta["parse_status"] = "running"
                meta["ocr_engine"] = "ragflow-deepdoc"
                _pdfmd_save_meta(job_dir, meta)
        finally:
            doc.close()

        meta = _pdfmd_load_meta(job_dir)
        meta["parse_status"] = "done"
        meta["parse_progress"] = 100
        meta["ocr_done"] = True
        meta["ocr_engine"] = "ragflow-deepdoc"
        _pdfmd_save_meta(job_dir, meta)
    except Exception as exc:
        try:
            meta = _pdfmd_load_meta(job_dir)
            meta["parse_status"] = "failed"
            meta["parse_error"] = str(exc)
            _pdfmd_save_meta(job_dir, meta)
        except Exception:
            pass
    finally:
        with _PDFMD_PARSE_LOCK:
            _PDFMD_PARSING.discard(job_id)


def pdf_md_region(payload: dict, username: str = "") -> dict:
    """框选一块区域 -> RAGFlow OCR -> 返回子 Markdown。"""
    payload = payload or {}
    job_dir = _pdfmd_job_dir(username, payload.get("job_id"))
    meta = _pdfmd_load_meta(job_dir)
    try:
        page = int(payload.get("page", 1))
    except (TypeError, ValueError):
        raise ValueError("页码无效")
    rect = payload.get("rect") or {}
    if not isinstance(rect, dict):
        raise ValueError("框选区域参数无效")
    user_settings, dataset_id = _pdfmd_staging_dataset(username)
    region_pdf = _pdfmd_region_pdf(job_dir, page, rect)
    text = _pdfmd_deepdoc_ocr(user_settings, dataset_id, f"region-p{page}.pdf", region_pdf, timeout=240)
    figures = _pdfmd_region_figures(job_dir, page, rect)
    parts = [text.strip()] if text.strip() else []
    parts.extend(_pdfmd_asset_md(meta.get("id", ""), fig["name"], f"第{page}页 区域图{fig['order']}") for fig in figures)
    return {"ok": True, "markdown": "\n\n".join(parts), "page": page}


def pdf_md_save(payload: dict, username: str = "") -> dict:
    """保存 review 后的完整 Markdown。"""
    payload = payload or {}
    job_dir = _pdfmd_job_dir(username, payload.get("job_id"))
    meta = _pdfmd_load_meta(job_dir)
    if "markdown" not in payload:
        raise ValueError("缺少 markdown 内容")
    meta["markdown"] = str(payload.get("markdown", "") or "")
    meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _pdfmd_save_meta(job_dir, meta)
    return {"ok": True}


def pdf_md_delete(payload: dict, username: str = "") -> dict:
    import shutil

    payload = payload or {}
    job_dir = _pdfmd_job_dir(username, payload.get("job_id"))
    shutil.rmtree(job_dir, ignore_errors=True)
    return {"ok": True}


def pdf_md_to_kb(payload: dict, username: str = "") -> dict:
    """把校对好的 Markdown 作为 .md 文档存入知识库。"""
    payload = payload or {}
    job_dir = _pdfmd_job_dir(username, payload.get("job_id"))
    meta = _pdfmd_load_meta(job_dir)
    markdown = str(payload.get("markdown", meta.get("markdown", "")) or "").strip()
    if not markdown:
        raise ValueError("Markdown 内容为空，无法入库")
    base = Path(meta.get("filename", "document.pdf")).stem or "document"
    name = f"{base}.md"
    data = base64.b64encode(markdown.encode("utf-8")).decode("ascii")
    return kb_upload({"filename": name, "data": data, "scope": payload.get("scope", "mine")}, username)
