"""报销助手：扫描邮件发票附件/链接、合并生成报销 PDF。"""

import io
import re
import imaplib
import uuid
import base64
import zipfile
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

_INVOICE_EXTENSIONS = {'.pdf', '.ofd', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}
_PDF_EXTENSIONS   = {'.pdf'}
_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif'}
_IMAP_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_NETEASE_IMAP_HOSTS = {'imap.163.com', 'imap.126.com', 'imap.yeah.net', 'imap.188.com'}

_TYPE_KEYWORDS = {
    '火车': ['火车', '高铁', '动车', '铁路', 'train'],
    '机票': ['机票', '航班', '航空', '飞机', '行程单', 'flight', 'airline'],
    '住宿': ['住宿', '酒店', '宾馆', '旅馆', '民宿', 'hotel'],
    '餐饮': ['餐', '饭', '餐厅', '餐饮', 'restaurant'],
    '出租车': ['出租', '滴滴', '打车', '网约', 'taxi'],
    '通讯费': ['话费', '通讯', '通信', '流量', '宽带', '移动', '电信', '联通',
              '中国移动', '中国电信', '中国联通', '手机费', '电话费', '10086', '10000'],
}
# 邮件主题/正文中判断是否为发票的关键词
_INVOICE_KEYWORDS = ['发票', 'invoice', '增值税', 'fapiao', 'receipt', '报销', '收据', '电子票', '行程单', '开票']

# 已知电子发票交付平台域名 —— URL 含这些域名时直接尝试下载
_INVOICE_PLATFORM_DOMAINS = [
    'nnfp.jss.com.cn', 'jss.com.cn', 'nuonuo.com',
    'baiwang.com', 'aisino.com',
    'fpdk.ntax.com.cn', 'ntax.com.cn', 'chinatax',
    'ele-invoice', 'dingtax.com',
    'tax.gov.cn', 'etax', 'efp.',
    'fapiao.jd', 'fp.alipay', 'invoice.meituan',
    'yunpiao', 'yunzhangfang', 'kp.shui5',
]

# 发送发票通知的平台邮箱域名
_INVOICE_SENDER_DOMAINS = [
    'nuonuo.com', 'info.nuonuo.com',
    'baiwang.com', 'aisino.com',
    'ntax.com.cn', 'jss.com.cn',
    'dingtax.com', 'tax.gov.cn',
    'yunzhangfang.com', 'kp.shui5.com',
    '139.com',          # 中国移动
    '10086.com',        # 中国移动
    'chinamobile.com',  # 中国移动
    '189.cn',           # 中国电信
    '10000.gd.cn',      # 中国电信
    'chinaunicom.cn',   # 中国联通
]

# 链接文字关键词
_LINK_TEXT_KW = [
    '下载发票', '查看发票', '电子发票', '发票下载', '下载PDF', '下载OFD',
    '发票链接', '点击下载', '下载凭证', '行程单下载', '报销凭证', '领取发票',
    '查看详情', '点击查看', '点击领取',
]
# URL 关键词（不含平台域名，平台域名已在 _INVOICE_PLATFORM_DOMAINS 中）
_LINK_URL_KW = [
    'fapiao', 'invoice', 'einvoice', 'e-invoice', 'efapiao',
    'eticket', 'itinerary', 'receipt', 'fpdown', 'fpview',
]


# ── IMAP 连接 ─────────────────────────────────────────────────

def _to_imap_date(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return f"{dt.day:02d}-{_IMAP_MONTHS[dt.month - 1]}-{dt.year}"


def _imap_connect_safe(settings):
    """建立 IMAP 连接，网易系服务器自动发送 ID 命令。"""
    validate_imap_ready(settings)
    if settings["use_ssl"]:
        box = imaplib.IMAP4_SSL(settings["host"], settings["port"])
    else:
        box = imaplib.IMAP4(settings["host"], settings["port"])
    box.login(settings["user"], settings["password"])
    if settings["host"].lower() in _NETEASE_IMAP_HOSTS:
        imaplib.Commands['ID'] = ('AUTH',)
        box._simple_command('ID', '("name" "imaplib" "version" "1.0" "vendor" "python")')
    return box


# ── 文件缓存 ──────────────────────────────────────────────────

def _reimbursement_dir(username, sub):
    path = user_root(username) / "reimbursement" / sub
    path.mkdir(parents=True, exist_ok=True)
    return path

def reimbursement_cache_dir(username):
    return _reimbursement_dir(username, "cache")

def reimbursement_output_dir(username):
    return _reimbursement_dir(username, "output")

def _cache_path_for_key(username, key):
    for p in reimbursement_cache_dir(username).glob(f"{key}__*"):
        return p
    return None

def _save_cache(username, key, filename, data):
    safe = re.sub(r'[^\w.-]+', '_', filename) or 'attachment'
    path = reimbursement_cache_dir(username) / f"{key}__{safe}"
    path.write_bytes(data)
    return path


# ── 文件内容提取 ──────────────────────────────────────────────

def _extract_pdf_text(path, max_chars=800):
    if path.suffix.lower() != '.pdf':
        return ''
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        text = ''
        for page in reader.pages:
            text += (page.extract_text() or '') + '\n'
            if len(text) >= max_chars:
                break
        return text[:max_chars].strip()
    except Exception:
        return ''


def _extract_ofd_text(path, max_chars=800):
    if path.suffix.lower() != '.ofd':
        return ''
    try:
        with zipfile.ZipFile(str(path), 'r') as z:
            parts = []
            for name in z.namelist():
                if not name.lower().endswith('.xml'):
                    continue
                raw = z.read(name).decode('utf-8', errors='replace')
                text = re.sub(r'<[^>]+>', ' ', raw)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    parts.append(text)
                if sum(len(t) for t in parts) >= max_chars:
                    break
            return (' '.join(parts))[:max_chars]
    except Exception:
        return ''


def _extract_file_text(path, max_chars=800):
    ext = path.suffix.lower()
    if ext == '.pdf':
        return _extract_pdf_text(path, max_chars)
    if ext == '.ofd':
        return _extract_ofd_text(path, max_chars)
    return ''


# ── zip 压缩包发票提取 ────────────────────────────────────────
# 部分平台（如中国移动 DZFP_*.zip）把电子发票打包成 zip 投递，
# 内部才是真正的 PDF/OFD/图片，需要解压后才能识别。

def _zip_namelist(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.namelist()
    except Exception:
        return None


def _is_ofd_container(names):
    """OFD 文件本身就是 zip（根目录含 OFD.xml），不应被当作普通压缩包拆开。"""
    return any(n.split('/')[-1].lower() == 'ofd.xml' for n in (names or []))


def _extract_zip_invoices(data, max_files=20):
    """从 zip 字节中提取发票文件（pdf/ofd/图片），返回 [(filename, bytes), ...]。
    若压缩包本身是 OFD 容器则返回空（交由调用方按 OFD 处理）；
    同一压缩包内 PDF 与 OFD 并存时只保留 PDF。"""
    names = _zip_namelist(data)
    if names is None or _is_ofd_container(names):
        return []
    out = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in names:
                if name.endswith('/'):
                    continue
                inner_ext = Path(name).suffix.lower()
                if inner_ext not in _INVOICE_EXTENSIONS:
                    continue
                try:
                    payload = z.read(name)
                except Exception:
                    continue
                if payload:
                    out.append((Path(name).name, payload))
                if len(out) >= max_files:
                    break
    except Exception:
        return []
    if any(Path(n).suffix.lower() == '.pdf' for n, _ in out):
        out = [(n, d) for n, d in out if Path(n).suffix.lower() != '.ofd']
    return out


# ── 链接提取与下载 ────────────────────────────────────────────

def _is_invoice_email(subject, from_addr):
    """
    判断这封邮件是否是发票通知邮件。
    只要主题含发票关键词，或发件人来自已知发票平台，就认定为发票邮件。
    发票邮件中的所有 http 链接都应当被尝试下载。
    """
    subj = (subject or '').lower()
    frm  = (from_addr or '').lower()
    return (
        any(kw in subj for kw in _INVOICE_KEYWORDS) or
        any(d in frm for d in _INVOICE_SENDER_DOMAINS) or
        'invoice' in frm or 'fapiao' in frm
    )


def _looks_like_invoice_url(url, text=''):
    """URL 或链接文字本身是否暗示这是发票下载链接。"""
    u = url.lower()
    t = (text or '').lower()
    return (
        u.endswith('.pdf') or u.endswith('.ofd') or
        any(d in u for d in _INVOICE_PLATFORM_DOMAINS) or
        any(kw in u for kw in _LINK_URL_KW) or
        any(kw in t for kw in _LINK_TEXT_KW)
    )


def _extract_invoice_links(msg, subject='', from_addr=''):
    """
    从邮件提取需要下载的链接。
    - 如果是发票通知邮件：提取所有 http 链接（不过滤）
    - 否则：只提取明确像发票下载的链接
    """
    force_all = _is_invoice_email(subject, from_addr)
    found = []
    seen  = set()

    def add(url, text):
        url = (url or '').strip().rstrip('.,;)>"\'')
        if not url.startswith('http') or url in seen or len(url) > 800:
            return
        # 过滤掉明显不是文件下载的 URL（图片、跟踪像素、退订链接等）
        skip_patterns = ['unsubscribe', 'unsub', 'mailto:', 'tel:', 'javascript:',
                         '.gif', '.jpg', '.png', '.jpeg', 'track.', 'click.', 'open.']
        if any(p in url.lower() for p in skip_patterns):
            return
        if force_all or _looks_like_invoice_url(url, text):
            seen.add(url)
            found.append((url, text))

    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == 'attachment':
            continue
        ctype   = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or 'utf-8'
        content = payload.decode(charset, errors='replace')

        if ctype == 'text/html':
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                                 content, re.IGNORECASE | re.DOTALL):
                add(m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip())
        elif ctype == 'text/plain':
            for m in re.finditer(r'https?://[^\s<>"\']+', content):
                add(m.group(0), '')

    return found


_DL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/pdf,application/octet-stream,text/html,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def _filename_from_headers_or_url(headers, final_url, default_ext):
    cd = headers.get('Content-Disposition') or ''
    m  = re.search(r"filename\*?=['\"]?(?:UTF-8'')?([^'\";\r\n]+)", cd, re.IGNORECASE)
    if m:
        name = urllib.parse.unquote(m.group(1).strip().strip('"\''))
        if name:
            return Path(name).name or f'invoice{default_ext}'
    url_path = final_url.split('?')[0].split('/')[-1]
    if url_path and '.' in url_path:
        return url_path
    return f'invoice{default_ext}'


def _base_origin(url):
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _resolve_url(url, base_url):
    """把相对 URL 解析为绝对 URL。"""
    url = url.strip()
    if url.startswith('http'):
        return url
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return _base_origin(base_url) + url
    return url


def _extract_download_candidates(html_text, page_url):
    """
    从 HTML/JS 源码中提取候选下载 URL，按与"发票 PDF"的相关度打分排序。
    覆盖：href/src/action, data-* 属性, JS 字符串字面量, JS 变量赋值, window.open/location.href。
    """
    base = _base_origin(page_url)
    seen = set()
    scored = []

    def consider(raw_url):
        if not raw_url:
            return
        resolved = _resolve_url(raw_url.strip().rstrip('.,;)\'"'), page_url)
        if not resolved.startswith('http') or resolved in seen or len(resolved) > 600:
            return
        # 跳过明显无关 URL
        skip = ['logout', 'login', 'signup', 'register', 'css', '.js?', '.png', '.jpg',
                '.gif', '.ico', 'tracker', 'analytics', 'googletagmanager', 'baidu.com/s',
                'weibo.com', 'qq.com/cgi', 'alipay.com/i', '#']
        if any(s in resolved.lower() for s in skip):
            return
        seen.add(resolved)
        ul = resolved.lower()
        score = 0
        if ul.endswith('.pdf'):            score = 10
        elif ul.endswith('.ofd'):          score = 9
        elif 'download' in ul and 'pdf' in ul: score = 8
        elif '/download' in ul:            score = 7
        elif 'getpdf' in ul or 'exportpdf' in ul: score = 7
        elif 'pdf' in ul:                  score = 6
        elif 'ofd' in ul:                  score = 6
        elif any(d in ul for d in _INVOICE_PLATFORM_DOMAINS): score = 5
        elif any(kw in ul for kw in _LINK_URL_KW): score = 4
        elif 'file' in ul or 'attach' in ul: score = 2
        if score > 0:
            scored.append((score, resolved))

    # HTML 属性
    for pat in [
        r'(?:href|src|action)\s*=\s*["\']([^"\']+)["\']',
        r'data-(?:url|href|link|src|download|file|pdf|invoice)\s*=\s*["\']([^"\']+)["\']',
        r'(?:onclick|onload)\s*=\s*["\'][^"\']*?["\']([^"\']+\.(?:pdf|ofd))["\']',
    ]:
        for m in re.finditer(pat, html_text, re.IGNORECASE):
            consider(m.group(1))

    # JS 变量 / 对象属性（含常见命名）
    for pat in [
        r'(?:pdfUrl|downloadUrl|fileUrl|invoiceUrl|attachUrl|'
        r'url|href|src|link|path|filePath|downloadPath)\s*[=:]\s*["\']([^"\']+)["\']',
        r'window\.(?:open|location\.href)\s*\(\s*["\']([^"\']+)["\']',
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
    ]:
        for m in re.finditer(pat, html_text, re.IGNORECASE):
            consider(m.group(1))

    # 所有 https:// 字符串（兜底）
    for m in re.finditer(r'https?://[^\s"\'<>\\]{8,}', html_text):
        consider(m.group(0).rstrip('.,;)\'"'))

    return sorted(scored, key=lambda x: x[0], reverse=True)


def _is_spa_html(data):
    """判断 HTML 内容是否是 SPA（内容由 JS 渲染，无法静态提取）。"""
    text = data[:2000].lower()
    return (b'<div id="app">' in text or b"<div id='app'>" in text) and b'<script' in text


def _try_download_url(url, timeout=15, _depth=0):
    """
    递归下载 URL，返回以下之一：
    - ('file', filename, data)      成功拿到文件
    - ('spa', final_url, html_data) 拿到 SPA 页面（内容由 JS 渲染，需人工下载）
    - None                          失败
    """
    if _depth > 2:
        return None
    try:
        req = urllib.request.Request(url, headers=_DL_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            ctype     = (resp.headers.get('Content-Type') or '').lower()
            headers   = resp.headers
            data      = resp.read()
        if not data:
            return None

        # magic bytes 优先
        if data[:4] == b'%PDF':
            return 'file', _filename_from_headers_or_url(headers, final_url, '.pdf'), data
        if data[:2] == b'PK':
            names = _zip_namelist(data)
            if names is not None:
                # OFD 文件本身是 zip（含 OFD.xml），整包即为发票
                if _is_ofd_container(names):
                    return 'file', _filename_from_headers_or_url(headers, final_url, '.ofd'), data
                # 否则尝试解压出内部发票文件（如中国移动 DZFP_*.zip 内的 PDF）
                inner = _extract_zip_invoices(data)
                if inner:
                    return 'file', inner[0][0], inner[0][1]
        if 'pdf' in ctype and 'html' not in ctype:
            return 'file', _filename_from_headers_or_url(headers, final_url, '.pdf'), data
        if 'ofd' in ctype:
            return 'file', _filename_from_headers_or_url(headers, final_url, '.ofd'), data

        # HTML 页面
        is_html = (b'<html' in data[:1000].lower() or b'<!doctype' in data[:200].lower()
                   or 'html' in ctype)
        if not is_html:
            return None

        # SPA 页面（内容由 JS 渲染）
        if _is_spa_html(data):
            if _depth == 0:
                return 'spa', final_url, data
            return None

        # 普通 HTML：提取候选下载 URL 再尝试
        if _depth < 2:
            html_text  = data.decode('utf-8', errors='replace')
            candidates = _extract_download_candidates(html_text, final_url)
            tried = set()
            for score, inner_url in candidates[:8]:
                if inner_url in tried or inner_url in (url, final_url):
                    continue
                tried.add(inner_url)
                result = _try_download_url(inner_url, timeout=timeout, _depth=_depth + 1)
                if result:
                    return result

        return None
    except Exception:
        return None


# ── 关键词兜底分析 ────────────────────────────────────────────

def _keyword_type(text):
    for t, kws in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return t
    return '其他'


def _keyword_analyze(candidates):
    result = {}
    for c in candidates:
        name    = (c.get('filename') or '').lower()
        subject = (c.get('email_subject') or '').lower()
        content = (c.get('_content') or '').lower()
        ext = Path(name).suffix
        # 占位行（无附件，仅邮件信息）始终保留，供手动上传
        if c.get('is_stub'):
            result[c['key']] = {
                'is_invoice': True,
                'invoice_type': _keyword_type(subject + ' ' + (c.get('_email_body') or '').lower()),
                'invoice_date': '', 'invoice_amount': '', 'invoice_location': '',
                'invoice_from': '', 'invoice_to': '',
            }
            continue
        if ext not in _INVOICE_EXTENSIONS:
            continue
        text = name + ' ' + subject + ' ' + content
        is_invoice = ext in ('.pdf', '.ofd') or any(kw in text for kw in _INVOICE_KEYWORDS)
        if not is_invoice:
            continue
        result[c['key']] = {
            'is_invoice': True,
            'invoice_type': _keyword_type(text),
            'invoice_date': '',
            'invoice_amount': '',
            'invoice_location': '',
            'invoice_from': '',
            'invoice_to': '',
        }
    return result


# ── LLM 分析 ──────────────────────────────────────────────────

def _llm_analyze(candidates):
    """
    用平台 LLM 一次性完成：判断是否为发票 + 提取类型/日期/金额/出发地/目的地。
    综合 PDF/OFD 文件内容 + 邮件正文，识别不出的字段留空。
    """
    cfg = merged_assistant_config()
    if not cfg.get("url") or not cfg.get("key"):
        return _keyword_analyze(candidates)

    lines = []
    # 用 key 的前 8 位作为唯一标识传给 LLM，避免序号乱序导致数据错配
    key_index = {c['key'][:8]: c['key'] for c in candidates}

    for i, c in enumerate(candidates):
        short_key = c['key'][:8]
        entry = (
            f"[{short_key}] {i + 1}. 附件名：{c['filename']}  "
            f"邮件主题：{c['email_subject']}  "
            f"发件人：{c['email_from']}"
        )
        file_text  = (c.get('_content') or '').strip()
        email_body = (c.get('_email_body') or '').strip()
        if file_text:
            entry += f"\n   【附件内容】{file_text[:400]}"
        if email_body and not file_text:
            entry += f"\n   【邮件正文】{email_body[:500]}"
        elif email_body:
            entry += f"\n   【邮件正文（补充）】{email_body[:200]}"
        lines.append(entry)

    system_prompt = (
        "你是财务报销助手，从邮件附件和正文中识别发票并提取关键字段。\n\n"
        "判断规则：\n"
        "- 是发票/收据/行程单等报销凭证则 is_invoice=true\n"
        "- 附件内容或邮件正文出现金额、购买方/销售方、发票号、税率等字段即为发票\n"
        "- 不确定时 is_invoice=true（宁多勿漏）\n\n"
        "提取字段：\n"
        "  id: 每条前方括号里的 8 位标识，原样返回，不得修改\n"
        "  is_invoice: bool\n"
        "  type: 住宿 | 火车 | 机票 | 餐饮 | 出租车 | 通讯费 | 其他\n"
        "       （话费/宽带/流量/移动·电信·联通运营商发票 = 通讯费）\n"
        "  date: 票据日期 YYYY-MM-DD（住宿填入住日期；不确定留空）\n"
        "  amount: 发票金额，带货币符号如 ¥285.00（不确定留空）\n"
        "  location: 地点（住宿必填，格式【城市·酒店名】如【杭州·欧诺酒店】；"
        "餐饮可填餐厅名；其他类型留空）\n"
        "  from: 出发地（仅火车/机票填写，其他留空）\n"
        "  to: 目的地（仅火车/机票填写，其他留空）\n\n"
        "字段提取重点：\n"
        "- 住宿发票：location=销售方名称（酒店全称），date=入住日期，amount=含税合计\n"
        "- 火车/机票：from=出发站/城市，to=到达站/城市，date=乘车/乘机日期\n"
        "- 餐饮：location=餐厅名称（可选），date=消费日期，amount=合计金额\n\n"
        "以 JSON 数组返回，id 字段必须原样返回，不要修改。只返回 JSON，不要其他文字。\n"
        "示例：[{\"id\":\"a1b2c3d4\",\"is_invoice\":true,\"type\":\"住宿\","
        "\"date\":\"2026-05-15\",\"amount\":\"¥285.00\","
        "\"location\":\"杭州·欧诺酒店\",\"from\":\"\",\"to\":\"\"}]"
    )

    try:
        import json as _json
        data = request_json(
            cfg["url"] + "/v1/chat/completions",
            cfg["key"],
            {
                "model": cfg["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "附件列表：\n" + "\n".join(lines)},
                ],
                "temperature": 0,
                "max_tokens": 1500,
            },
            "POST",
            60,
        )
        content = data["choices"][0]["message"]["content"].strip()
        try:
            items = _json.loads(content)
        except Exception:
            m = re.search(r'\[.+\]', content, re.DOTALL)
            items = _json.loads(m.group()) if m else []

        if not isinstance(items, list):
            raise ValueError("非列表")

        result = {}
        for item in items:
            # 优先用 id 匹配（key 前 8 位），避免序号乱序造成错配
            short_id = str(item.get('id') or '').strip()
            full_key = key_index.get(short_id)
            if not full_key:
                # 降级：用 index 序号
                idx = int(item.get('index', 0)) - 1
                if 0 <= idx < len(candidates):
                    full_key = candidates[idx]['key']
            if not full_key:
                continue
            result[full_key] = {
                'is_invoice':       bool(item.get('is_invoice', True)),
                'invoice_type':     str(item.get('type') or '其他').strip(),
                'invoice_date':     str(item.get('date') or '').strip(),
                'invoice_amount':   str(item.get('amount') or '').strip(),
                'invoice_location': str(item.get('location') or '').strip(),
                'invoice_from':     str(item.get('from') or '').strip(),
                'invoice_to':       str(item.get('to') or '').strip(),
            }
        # LLM 漏掉的条目：默认保留
        for c in candidates:
            if c['key'] not in result:
                text = (c.get('filename', '') + c.get('email_subject', '') + c.get('_content', '')).lower()
                result[c['key']] = {
                    'is_invoice': True,
                    'invoice_type': _keyword_type(text),
                    'invoice_date': '',
                    'invoice_amount': '',
                    'invoice_from': '',
                    'invoice_to': '',
                }
        return result
    except Exception:
        return _keyword_analyze(candidates)


# ── 主扫描函数 ─────────────────────────────────────────────────

def scan_invoice_attachments(username, start_date, end_date, account="company"):
    try:
        since = _to_imap_date(start_date)
        before_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        before = f"{before_dt.day:02d}-{_IMAP_MONTHS[before_dt.month - 1]}-{before_dt.year}"
    except ValueError as e:
        raise ValueError(f"日期格式错误，请使用 YYYY-MM-DD：{e}")

    settings = imap_settings_for_account(username, account)
    box      = _imap_connect_safe(settings)
    all_candidates = []
    total_scanned  = 0
    downloaded_urls = set()

    def _make_candidate(key, cached_path, filename, subject, from_addr, date_str, uid, email_body):
        ext = Path(filename.lower()).suffix
        return {
            "key": key,
            "email_uid": uid,
            "email_subject": subject,
            "email_date": date_str,
            "email_from": from_addr,
            "filename": filename,
            "size": cached_path.stat().st_size,
            "content_type": "",
            "is_pdf":   ext in _PDF_EXTENSIONS,
            "is_image": ext in _IMAGE_EXTENSIONS,
            "is_ofd":   ext == ".ofd",
            "invoice_type": "其他",
            "invoice_date": "",
            "invoice_amount": "",
            "invoice_location": "",
            "invoice_from": "",
            "invoice_to": "",
            "_content":    _extract_file_text(cached_path),
            "_email_body": email_body,
        }

    try:
        status, _ = box.select("INBOX")
        if status != "OK":
            raise ValueError("无法打开收件箱，请检查邮箱配置")

        status, data = box.uid("search", None, f'SINCE {since} BEFORE {before}')
        if status != "OK":
            raise ValueError("搜索邮件失败")
        uids = data[0].split()
        total_scanned = len(uids)
        if not uids:
            return {"ok": True, "items": [], "total_scanned": 0}

        # ══ 阶段 1：只拉头部，快速筛出发票候选邮件 ══════════════════
        # 大多数邮件不是发票，仅对发票邮件才下载全文，大幅减少数据量和耗时
        HEADER_FIELDS = "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])"
        invoice_uids = []   # 确认是发票邮件的 UID
        header_info  = {}   # uid -> (subject, from_addr, date_str)

        BATCH_H = 50
        for i in range(0, len(uids), BATCH_H):
            batch   = uids[i:i + BATCH_H]
            uid_set = b",".join(batch)
            st, fetched = box.uid("fetch", uid_set, HEADER_FIELDS)
            if st != "OK" or not fetched:
                continue
            for raw_item in fetched:
                if not isinstance(raw_item, tuple) or not raw_item[1]:
                    continue
                meta_str = raw_item[0].decode("utf-8", errors="ignore")
                m = re.search(r"UID\s+(\d+)", meta_str)
                uid = m.group(1) if m else ""
                if not uid:
                    continue
                hdr = email.message_from_bytes(raw_item[1])
                subject   = decode_mime_value(hdr.get("Subject", "")) or ""
                from_addr = decode_mime_value(hdr.get("From", "")) or ""
                date_str  = normalize_mail_date(hdr.get("Date", ""))
                header_info[uid] = (subject, from_addr, date_str)
                if _is_invoice_email(subject, from_addr):
                    invoice_uids.append(uid.encode() if isinstance(uid, str) else uid)

        # ══ 阶段 2：只对发票候选邮件下载全文并提取附件/链接 ═══════════
        import time as _time
        MAX_LINKS_PER_EMAIL = 3   # 每封邮件最多尝试 3 个链接
        LINK_TIMEOUT = 5          # 每个链接最多等 5 秒
        # 链接下载是扫描里最慢的部分；给整个阶段一个总预算，避免前置代理 504 超时
        LINK_BUDGET_SEC = 25
        link_deadline = _time.time() + LINK_BUDGET_SEC

        BATCH = 20
        for i in range(0, len(invoice_uids), BATCH):
            batch   = invoice_uids[i:i + BATCH]
            uid_set = b",".join(batch)
            status, fetched = box.uid("fetch", uid_set, "(BODY.PEEK[])")
            if status != "OK" or not fetched:
                continue

            for raw_item in fetched:
                if not isinstance(raw_item, tuple) or not raw_item[1]:
                    continue
                meta  = raw_item[0].decode("utf-8", errors="ignore")
                match = re.search(r"UID\s+(\d+)", meta)
                uid   = match.group(1) if match else ""
                if not uid:
                    continue

                subject, from_addr, date_str = header_info.get(uid, ("", "", ""))
                msg        = email.message_from_bytes(raw_item[1])
                email_body = extract_mail_text(msg, 800)

                email_candidates = []

                # ── 1. 附件 ──────────────────────────────────
                for part in (msg.walk() if msg.is_multipart() else [msg]):
                    if part.is_multipart():
                        continue
                    fname = part.get_filename()
                    if not fname:
                        continue
                    fname = decode_mime_value(fname)
                    ext   = Path(fname.lower()).suffix
                    if ext not in _INVOICE_EXTENSIONS and ext != '.zip':
                        continue
                    payload = part.get_payload(decode=True) or b""
                    if not payload:
                        continue
                    # zip 附件（如中国移动 DZFP_*.zip）：解压出内部发票文件
                    if ext == '.zip':
                        inner = _extract_zip_invoices(payload)
                        if inner:
                            for inner_name, inner_data in inner:
                                key  = uuid.uuid4().hex
                                path = _save_cache(username, key, inner_name, inner_data)
                                email_candidates.append(_make_candidate(
                                    key, path, inner_name, subject, from_addr, date_str, uid, email_body))
                        else:
                            # 解不出内部文件：若整包本身是 OFD 容器，整包当作一张 OFD 收录
                            names = _zip_namelist(payload)
                            if names is not None and _is_ofd_container(names):
                                ofd_name = (Path(fname).stem or 'invoice') + '.ofd'
                                key  = uuid.uuid4().hex
                                path = _save_cache(username, key, ofd_name, payload)
                                email_candidates.append(_make_candidate(
                                    key, path, ofd_name, subject, from_addr, date_str, uid, email_body))
                        continue
                    key  = uuid.uuid4().hex
                    path = _save_cache(username, key, fname, payload)
                    email_candidates.append(_make_candidate(
                        key, path, fname, subject, from_addr, date_str, uid, email_body))

                # ── 2. 正文链接下载 ───────────────────────────
                # 仅当邮件没有附件时才尝试下载正文链接（有附件就不必再去试链接，
                # 大幅提速）；并受全局时间预算约束，避免整体扫描超时。
                spa_urls   = []
                link_tried = 0
                links = [] if email_candidates else _extract_invoice_links(msg, subject, from_addr)
                for url, link_text in links:
                    if link_tried >= MAX_LINKS_PER_EMAIL or _time.time() >= link_deadline:
                        break
                    if url in downloaded_urls:
                        continue
                    downloaded_urls.add(url)
                    link_tried += 1
                    dl = _try_download_url(url, timeout=LINK_TIMEOUT)
                    if not dl:
                        continue
                    kind = dl[0]
                    if kind == 'file':
                        _, fname, file_data = dl
                        existing_names = {c['filename'] for c in email_candidates}
                        if fname in existing_names:
                            continue
                        key  = uuid.uuid4().hex
                        path = _save_cache(username, key, fname, file_data)
                        email_candidates.append(_make_candidate(
                            key, path, fname, subject, from_addr, date_str, uid, email_body))
                    elif kind == 'spa':
                        _, spa_final_url, _ = dl
                        spa_urls.append(spa_final_url or url)

                # ── 3. 占位行 ─────────────────────────────────
                # 发票邮件但没拿到任何文件（SPA 页面 / zip 解不开 / 仅正文有金额）：
                # 仍建占位行，保证"明显是发票邮件"始终出现在列表，可在该行手动上传 PDF
                if not email_candidates:
                    key = uuid.uuid4().hex
                    email_candidates.append({
                        "key": key,
                        "email_uid": uid,
                        "email_subject": subject,
                        "email_date": date_str,
                        "email_from": from_addr,
                        "filename": "",
                        "size": 0,
                        "content_type": "",
                        "is_pdf":   False,
                        "is_image": False,
                        "is_ofd":   False,
                        "is_stub":  True,
                        "source_url": spa_urls[0] if spa_urls else "",
                        "invoice_type": "其他",
                        "invoice_date": "",
                        "invoice_amount": "",
                        "invoice_location": "",
                        "invoice_from": "",
                        "invoice_to": "",
                        "_content":    "",
                        "_email_body": email_body,
                    })

                # ── 4. PDF 优先：有 PDF 则丢弃同邮件的 OFD ───
                real = [c for c in email_candidates if not c.get('is_stub')]
                has_pdf = any(Path(c['filename'].lower()).suffix == '.pdf' for c in real)
                if has_pdf:
                    email_candidates = [
                        c for c in email_candidates
                        if c.get('is_stub') or Path(c['filename'].lower()).suffix != '.ofd'
                    ]

                all_candidates.extend(email_candidates)

    finally:
        try:
            box.logout()
        except Exception:
            pass

    if all_candidates:
        analysis = _llm_analyze(all_candidates)
        results  = []
        for c in all_candidates:
            meta = analysis.get(c["key"], {})
            if meta.get("is_invoice", True):
                c.update({
                    "invoice_type":     meta.get("invoice_type", "其他"),
                    "invoice_date":     meta.get("invoice_date", ""),
                    "invoice_amount":   meta.get("invoice_amount", ""),
                    "invoice_location": meta.get("invoice_location", ""),
                    "invoice_from":     meta.get("invoice_from", ""),
                    "invoice_to":       meta.get("invoice_to", ""),
                })
                c.pop("_content", None)
                # 所有邮件来源条目都保留正文，供前端"邮件内容"弹框查看原始邮件
                c["email_body"] = c.pop("_email_body", "")
                results.append(c)
    else:
        results = []

    results.sort(key=lambda x: x["email_date"], reverse=True)
    return {"ok": True, "items": results, "total_scanned": total_scanned}


# ── 手动上传 ───────────────────────────────────────────────────

def get_reimbursement_attachment(username, key):
    return _cache_path_for_key(username, key)


# ── OFD 预览（渲染成图片）──────────────────────────────────────
# easyofd 把 OFD 渲染成图片：① 对签名缺失容错（否则部分发票解析崩溃）
# ② 用 /opt/ofdfonts 下的中文字体顶替内嵌字体名，否则文字渲染为空白

_OFD_FONT_DIR = "/opt/ofdfonts"
_ofd_ready = False

def _ensure_ofd_runtime():
    global _ofd_ready
    if _ofd_ready:
        return True
    import reportlab.rl_config as rc
    if _OFD_FONT_DIR not in rc.TTFSearchPath:
        rc.TTFSearchPath = list(rc.TTFSearchPath) + [_OFD_FONT_DIR]
    import easyofd.parser_ofd.ofd_parser as _P
    _orig = _P.OFDParser.get_xml_obj
    def _safe(self, label):
        if not label:
            return None
        try:
            return _orig(self, label)
        except Exception:
            return None
    _P.OFDParser.get_xml_obj = _safe
    # 字体文件此时已在搜索路径上，重新注册一遍 font_map
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import easyofd.parser_ofd as _PP
    for font, names in _PP.font_map.items():
        for name in names:
            try:
                pdfmetrics.registerFont(TTFont(name, font))
            except Exception:
                pass
    _ofd_ready = True
    return True


def _ofd_preview_path(username, key):
    return _reimbursement_dir(username, "ofd_preview") / f"{key}.png"


def render_ofd_preview(username, key):
    """把缓存的 OFD 渲染为 PNG（多页纵向拼接），带磁盘缓存。失败返回 None。"""
    path = _cache_path_for_key(username, key)
    if not path or not path.exists() or path.suffix.lower() != '.ofd':
        return None
    cache_png = _ofd_preview_path(username, key)
    if cache_png.exists():
        return cache_png.read_bytes()
    try:
        _ensure_ofd_runtime()
        import sys, os
        from easyofd import OFD
        from PIL import Image as PILImage
        data = path.read_bytes()
        _stdout = sys.stdout
        try:
            sys.stdout = open(os.devnull, 'w')   # 屏蔽 easyofd 的 print 噪音
            ofd = OFD()
            ofd.read(data, fmt='binary')
            imgs = ofd.to_jpg()
        finally:
            sys.stdout = _stdout
        if not imgs:
            return None
        pages = [im.convert('RGB') for im in imgs]
        if len(pages) == 1:
            canvas = pages[0]
        else:
            w = max(p.width for p in pages)
            canvas = PILImage.new('RGB', (w, sum(p.height for p in pages)), 'white')
            y = 0
            for p in pages:
                canvas.paste(p, (0, y))
                y += p.height
        buf = io.BytesIO()
        canvas.save(buf, format='PNG')
        cache_png.write_bytes(buf.getvalue())
        return buf.getvalue()
    except Exception:
        return None


# ── 原始邮件 HTML（含内嵌图片）────────────────────────────────

def _email_html_with_inline_images(msg):
    """提取邮件 HTML 正文，把 cid: 内嵌图片转成 data URI 以便直接渲染。
    无 HTML 时退化为纯文本；同时收集附件名列表。返回 (html, attachments)。"""
    html = ''
    plain = ''
    cid_map = {}
    attachments = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or '').lower()
        disp  = part.get_content_disposition()
        cid   = part.get('Content-ID')
        fname = part.get_filename()
        if fname:
            fname = decode_mime_value(fname)

        if ctype == 'text/html' and disp != 'attachment' and not html:
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            html = payload.decode(charset, errors='replace')
        elif ctype == 'text/plain' and disp != 'attachment' and not fname and not plain:
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            plain = payload.decode(charset, errors='replace')
        elif ctype.startswith('image/') and cid:
            payload = part.get_payload(decode=True) or b''
            if payload and len(payload) <= 5 * 1024 * 1024:
                b64 = base64.b64encode(payload).decode('ascii')
                cid_map[cid.strip().strip('<>')] = f'data:{ctype};base64,{b64}'

        if fname and (disp == 'attachment' or (not cid and ctype not in ('text/html', 'text/plain'))):
            attachments.append(fname)

    if html and cid_map:
        def _sub_cid(m):
            ref = m.group(2).strip().strip('<>')
            return f'{m.group(1)}="{cid_map[ref]}"' if ref in cid_map else m.group(0)
        html = re.sub(r'(src)\s*=\s*["\']cid:([^"\']+)["\']', _sub_cid, html, flags=re.IGNORECASE)

    if not html and plain:
        esc = plain.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html = f'<pre style="white-space:pre-wrap;word-break:break-word;font-family:inherit;margin:0;">{esc}</pre>'

    return html, attachments


def get_reimbursement_email_html(username, account, uid):
    """按 UID 重新拉取整封邮件，返回可直接渲染的原始 HTML（含内嵌图片）。"""
    if not uid:
        return {"ok": False, "error": "缺少邮件标识"}
    settings = imap_settings_for_account(username, account)
    box = _imap_connect_safe(settings)
    try:
        status, _ = box.select("INBOX")
        if status != "OK":
            return {"ok": False, "error": "无法打开收件箱"}
        st, fetched = box.uid("fetch", str(uid), "(BODY.PEEK[])")
        if st != "OK" or not fetched or not fetched[0]:
            return {"ok": False, "error": "未找到该邮件（可能已被删除或不在收件箱）"}
        raw = fetched[0][1] if isinstance(fetched[0], tuple) else None
        if not raw:
            return {"ok": False, "error": "邮件内容为空"}
        msg = email.message_from_bytes(raw)
        html, attachments = _email_html_with_inline_images(msg)
        return {
            "ok": True,
            "subject": decode_mime_value(msg.get("Subject", "")) or "",
            "from":    decode_mime_value(msg.get("From", "")) or "",
            "date":    normalize_mail_date(msg.get("Date", "")),
            "html":    html,
            "attachments": attachments,
        }
    finally:
        try:
            box.logout()
        except Exception:
            pass


def save_reimbursement_upload(username, filename, data_b64):
    try:
        data = base64.b64decode(data_b64)
    except Exception:
        raise ValueError("文件 base64 解码失败")
    # zip 压缩包（如中国移动 DZFP_*.zip）：解出内部发票文件后再入库
    if Path(filename.lower()).suffix == '.zip':
        inner = _extract_zip_invoices(data)
        if inner:
            filename, data = inner[0]
        else:
            names = _zip_namelist(data)
            if names is not None and _is_ofd_container(names):
                filename = (Path(filename).stem or 'invoice') + '.ofd'
            else:
                raise ValueError("压缩包内未找到发票文件（PDF/OFD/图片）")
    key  = uuid.uuid4().hex
    path = _save_cache(username, key, filename, data)
    ext  = Path(filename.lower()).suffix
    file_text = _extract_file_text(path)
    candidate = {
        "key": key, "email_subject": "", "email_from": "",
        "filename": filename, "_content": file_text, "_email_body": "",
    }
    meta = _llm_analyze([candidate]).get(key, {})
    return {
        "key": key,
        "filename": filename,
        "size": len(data),
        "is_pdf":   ext in _PDF_EXTENSIONS,
        "is_image": ext in _IMAGE_EXTENSIONS,
        "is_ofd":   ext == ".ofd",
        "source": "upload",
        "invoice_type":     meta.get("invoice_type", "其他"),
        "invoice_date":     meta.get("invoice_date", ""),
        "invoice_amount":   meta.get("invoice_amount", ""),
        "invoice_location": meta.get("invoice_location", ""),
        "invoice_from":     meta.get("invoice_from", ""),
        "invoice_to":       meta.get("invoice_to", ""),
    }


def fetch_and_save_url(username, url, hint_subject="", hint_body=""):
    """
    尝试从 URL 直接下载发票文件，保存并返回条目信息。
    如果 URL 指向 SPA 页面无法自动下载，返回 {ok: False, spa: True}。
    如果下载失败，返回 {ok: False, error: ...}。
    """
    result = _try_download_url(url)
    if result is None:
        return {"ok": False, "error": "无法下载该链接，请手动获取文件后上传"}
    if result[0] == 'spa':
        return {"ok": False, "spa": True, "error": "该链接为 SPA 页面，需要浏览器渲染，请手动下载后上传"}
    _, filename, file_data = result
    key  = uuid.uuid4().hex
    path = _save_cache(username, key, filename, file_data)
    ext  = Path(filename.lower()).suffix
    file_text = _extract_file_text(path)
    candidate = {
        "key": key,
        "email_subject": hint_subject,
        "email_from": "",
        "filename": filename,
        "_content": file_text,
        "_email_body": hint_body,
    }
    meta = _llm_analyze([candidate]).get(key, {})
    return {
        "ok": True,
        "key": key,
        "filename": filename,
        "size": len(file_data),
        "is_pdf":   ext in _PDF_EXTENSIONS,
        "is_image": ext in _IMAGE_EXTENSIONS,
        "is_ofd":   ext == ".ofd",
        "source": "upload",
        "invoice_type":     meta.get("invoice_type", "其他"),
        "invoice_date":     meta.get("invoice_date", ""),
        "invoice_amount":   meta.get("invoice_amount", ""),
        "invoice_location": meta.get("invoice_location", ""),
        "invoice_from":     meta.get("invoice_from", ""),
        "invoice_to":       meta.get("invoice_to", ""),
    }


# ── 合并 PDF ───────────────────────────────────────────────────

def merge_reimbursement_pdf(username, items, output_name):
    import pypdf
    from PIL import Image as PILImage

    if not items:
        raise ValueError("没有选中任何发票")

    writer      = pypdf.PdfWriter()
    skipped_ofd = []

    for item in items:
        key  = str(item.get("key", "")).strip()
        path = _cache_path_for_key(username, key)
        if not path or not path.exists():
            continue
        ext = path.suffix.lower()
        if ext == ".pdf":
            try:
                reader = pypdf.PdfReader(str(path))
                for page in reader.pages:
                    writer.add_page(page)
            except Exception:
                pass
        elif ext in _IMAGE_EXTENSIONS:
            try:
                img = PILImage.open(str(path)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PDF")
                buf.seek(0)
                reader = pypdf.PdfReader(buf)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception:
                pass
        elif ext == ".ofd":
            dname = path.name.split("__", 1)[-1] if "__" in path.name else path.name
            skipped_ofd.append(dname)

    if len(writer.pages) == 0 and not skipped_ofd:
        raise ValueError("没有可用的页面，请确认选中的文件有效")

    safe_name = re.sub(r'[^\w一-鿿.-]+', '_', output_name or "报销附件")
    if not safe_name.lower().endswith('.pdf'):
        safe_name += '.pdf'
    output_path = reimbursement_output_dir(username) / safe_name

    result: dict = {"ok": True, "filename": safe_name, "pages": len(writer.pages)}
    if skipped_ofd:
        result["warning"] = f"以下 OFD 文件暂不支持合并，请手动处理：{', '.join(skipped_ofd)}"

    if len(writer.pages) > 0:
        with open(str(output_path), 'wb') as f:
            writer.write(f)
    else:
        result["ok"]    = False
        result["error"] = result.pop("warning", "没有可合并的文件")

    return result


def list_reimbursement_outputs(username):
    out_dir = reimbursement_output_dir(username)
    files   = []
    for p in sorted(out_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({"filename": p.name, "size": p.stat().st_size})
    return files
