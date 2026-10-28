"""联指经营助手领导汇报 PPT：按 v5 蓝白高端视觉规范逐页渲染为 1920×1080 PNG。
用法：python3 deck.py [页码 ...]   不带参数渲染全部 24 页。"""
import base64, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1790581168448_irx25x')
SHOTS = OUT / '截图素材'
TOTAL = 24
_cache = {}
def data_url(f):
    if f not in _cache:
        _cache[f] = 'data:image/png;base64,' + base64.b64encode((SHOTS / f).read_bytes()).decode()
    return _cache[f]

COL = dict(cyan=('#0EA5E9', '#38BDF8'), blue=('#15499C', '#2F7BEA'), orange=('#F97316', '#FDBA74'),
           green=('#16A34A', '#4ADE80'), gold=('#D97706', '#FBBF24'), red=('#DC2626', '#F87171'))

ICON = {
 'doc': '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>',
 'ruler': '<path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2m1-5 2 2m1-5 2 2"/>',
 'gauge': '<path d="M4 16a8 8 0 1 1 16 0"/><path d="m12 16 4-5"/><circle cx="12" cy="16" r="1.4"/>',
 'shield': '<path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
 'scan': '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M8 12h8"/>',
 'radar': '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12 18 6"/>',
 'chart': '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
 'flag': '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
 'bell': '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
 'loop': '<path d="M20 12a8 8 0 1 1-3-6.2"/><path d="M20 4v5h-5"/>',
 'lock': '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
 'link': '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
 'hourglass': '<path d="M6 3h12M6 21h12M7 3c0 5 10 5 10 9s-10 4-10 9M17 3c0 5-10 5-10 9"/>',
 'users': '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="10" r="2.5"/><path d="M3 20a6 6 0 0 1 12 0M14 20a4 4 0 0 1 7 0"/>',
 'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
 'meeting': '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
 'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
 'notice': '<path d="M4 10v4h3l6 4V6L7 10z"/><path d="M17 9a4 4 0 0 1 0 6"/>',
 'badge': '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="12" cy="10" r="2.5"/><path d="M8 17a4 4 0 0 1 8 0"/>',
 'file': '<path d="M6 3h9l3 3v15H6z"/><path d="M9 11h6M9 15h6M9 7h3"/>',
 'sun': '<circle cx="12" cy="14" r="4"/><path d="M3 18h18M12 4v3M5 8l2 2M19 8l-2 2"/>',
 'box': '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
 'eye': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 'check': '<path d="m5 12 5 5 9-10"/>',
 'key': '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3"/>',
 'stamp': '<path d="M9 3h6v6l3 4H6l3-4z"/><path d="M5 17h14v4H5z"/>',
 'scale': '<path d="M12 3v18M5 21h14M6 7h12"/><path d="m6 7-3 7h6zM18 7l-3 7h6z"/>',
 'chat': '<path d="M4 5h16v11H9l-5 4z"/>',
 'share': '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="m8 11 8-4M8 13l8 4"/>',
 'pin': '<path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
 'trophy': '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4a3 3 0 0 0 4 4M16 6h4a3 3 0 0 1-4 4M12 13v4M8 21h8"/>',
 'click': '<path d="M9 9v10l3-3 2 5 2-1-2-5h4z"/><path d="M5 5l2 2M12 2v3M2 12h3"/>',
 'book': '<path d="M4 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H4zM20 4h-6"/><path d="M20 4v15h-6"/>',
 'steps': '<path d="M4 20h5v-5h5v-5h5V4"/>',
 'network': '<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="18" r="2.5"/><circle cx="19" cy="18" r="2.5"/><path d="M11 7 6 16M13 7l5 9M7 18h10"/>',
 'warn': '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/>',
 'target': '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
 'chip': '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
 'pentagon': '<path d="m12 3 9 6.5-3.5 10.5h-11L3 9.5z"/><circle cx="12" cy="12" r="2"/>',
 'q': '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
 'grid': '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
 'calendar': '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
 'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
}

def ic(name, color='blue', size=52):
    c1, c2 = COL[color]
    return (f"<span class=ib style='width:{size}px;height:{size}px;border-radius:{size*0.28:.0f}px;background:linear-gradient(135deg,{c1},{c2});box-shadow:0 10px 20px -8px {c1}99'>"
            f"<svg viewBox='0 0 24 24' width='{size*0.52:.0f}' height='{size*0.52:.0f}' fill='none' stroke='#fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>{ICON[name]}</svg></span>")

def line_icon(name, color='#15499C', size=22, sw=2):
    return f"<svg viewBox='0 0 24 24' width='{size}' height='{size}' fill='none' stroke='{color}' stroke-width='{sw}' stroke-linecap='round' stroke-linejoin='round'>{ICON[name]}</svg>"

def shot(file, crop, w, h, bar=True, label=''):
    """带窗口栏的截图框；crop=(x,y,cw,ch) 为原图 1920×1080 中的裁切区域，按宽度等比缩放。"""
    x, y, cw, ch = crop
    bh = 26 if bar else 0
    ih = h - bh
    s = w / cw
    img = (f"<div style='height:{ih}px;background:url({data_url(file)}) no-repeat;background-size:{1920*s:.1f}px {1080*s:.1f}px;"
           f"background-position:{-x*s:.1f}px {-y*s:.1f}px'></div>")
    tb = f"<div class=tb><i></i><i></i><i></i><span>{label}</span></div>" if bar else ''
    return f"<div class=win style='width:{w}px;height:{h}px'>{tb}{img}</div>"

BASE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;position:relative;overflow:hidden;font-family:'Droid Sans Fallback',sans-serif;color:#1E293B;background:linear-gradient(155deg,#FFFFFF 0%,#F5F9FF 50%,#EEF4FF 100%)}
.blob{position:absolute;border-radius:50%;filter:blur(60px);z-index:0}
.wave{position:absolute;right:-40px;bottom:-40px;width:900px;height:420px;opacity:.5;z-index:0}
.dots{position:absolute;left:30px;top:210px;width:240px;height:190px;background-image:radial-gradient(#15499C2e 1.5px,transparent 1.5px);background-size:18px 18px;z-index:0}
.ribbon{position:absolute;right:-260px;top:-300px;width:760px;height:520px;border-radius:50%;background:linear-gradient(130deg,#15499C,#2F7BEA 60%,#7FB2FF);transform:rotate(-18deg);box-shadow:0 30px 80px rgba(47,123,234,.25);z-index:0}
.ribbon2{position:absolute;right:-170px;top:-330px;width:700px;height:500px;border-radius:50%;border:1.5px solid #A9C6F2;transform:rotate(-10deg);z-index:0}
.hd{position:absolute;left:96px;top:56px;display:flex;gap:24px;align-items:flex-start;z-index:2}
.no{width:72px;height:72px;border-radius:18px;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff;font-size:32px;font-weight:800;display:flex;align-items:center;justify-content:center;box-shadow:0 12px 26px rgba(21,73,156,.3);margin-top:6px}
.eb{font-size:16px;letter-spacing:5px;color:#2F7BEA;font-weight:700}
h1{font-size:48px;color:#0B2458;letter-spacing:1px;line-height:1.22;font-weight:800}
.sub{font-size:22px;color:#64748B;margin-top:4px}
.rule{position:absolute;left:96px;top:196px;width:1728px;height:2px;background:linear-gradient(90deg,#15499C,#2F7BEA55 40%,transparent);z-index:2}
.part{position:absolute;right:340px;top:70px;padding:7px 18px;border-radius:99px;background:#EAF2FFee;color:#15499C;font-size:17px;border:1px solid #D3E3FB;font-weight:600;z-index:2}
.ft{position:absolute;left:96px;right:96px;bottom:22px;display:flex;justify-content:space-between;color:#94A3B8;font-size:16px;z-index:2}
.bar{position:absolute;left:0;right:0;bottom:0;height:5px;background:#E2EBF8;z-index:2}.bar i{display:block;height:100%;background:linear-gradient(90deg,#15499C,#2F7BEA)}
.stage{position:absolute;left:96px;right:96px;top:222px;bottom:62px;z-index:1}
.card{background:linear-gradient(180deg,#FFFFFF,#FBFDFF);border:1px solid #DDE8F8;border-radius:18px;box-shadow:0 18px 40px -18px rgba(21,73,156,.28),0 2px 6px rgba(21,73,156,.05);position:relative}
.glass{background:linear-gradient(145deg,rgba(255,255,255,.8),rgba(214,230,255,.55));border:1px solid rgba(255,255,255,.95);box-shadow:inset 0 1px 0 #fff,0 24px 50px -20px rgba(21,73,156,.35);border-radius:24px}
.ib{display:inline-flex;align-items:center;justify-content:center;flex:none}
.win{border-radius:14px;overflow:hidden;background:#fff;border:1px solid #D6E3F7;box-shadow:0 26px 50px -22px rgba(21,73,156,.45);flex:none}
.win .tb{height:26px;background:#EEF3FB;display:flex;gap:6px;align-items:center;padding-left:10px;border-bottom:1px solid #DFE8F6}
.win .tb i{width:8px;height:8px;border-radius:50%;background:#C5D3E8}.win .tb span{margin-left:8px;font-size:13px;color:#64748B}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:17px;padding:5px 13px;border-radius:99px;border:1px solid;font-weight:600;white-space:nowrap}
.t-title{font-size:26px;font-weight:800;color:#0B2458}.t-body{font-size:19px;color:#64748B}
.dia{width:8px;height:8px;transform:rotate(45deg);flex:none;display:inline-block}
.grad{background:linear-gradient(90deg,#15499C,#2F7BEA);-webkit-background-clip:text;color:transparent}
.cap{font-size:15px;color:#94A3B8}
"""

def wave_svg():
    return ('<svg class=wave viewBox="0 0 900 420" fill="none" stroke="#9DBDEB" stroke-width="1">'
            + ''.join(f'<path d="M0 {300+i*9} C 220 {200+i*12}, 480 {420-i*6}, 900 {170+i*11}"/>' for i in range(12)) + '</svg>')

BG = ('<div class=blob style="left:-160px;top:-120px;width:620px;height:420px;background:#DCEAFF"></div>'
      '<div class=blob style="left:780px;top:560px;width:720px;height:420px;background:#E6F0FF"></div>'
      + wave_svg() + '<div class=dots></div><div class=ribbon></div><div class=ribbon2></div>')

PARTS = {**{i: ('PART 01 · 为什么做', 'WHY IT MATTERS') for i in range(2, 6)},
         **{i: ('PART 02 · AI 原生架构', 'AI-NATIVE ARCHITECTURE') for i in range(6, 14)},
         **{i: ('PART 03 · 组织与机制', 'ORGANIZATION & GOVERNANCE') for i in range(14, 20)},
         **{i: ('APPENDIX · 备用', 'APPENDIX') for i in range(21, 25)}}

def page(n, title, sub, body, css='', header=True):
    head = ''
    if header:
        tag, en = PARTS[n]
        head = (f"<div class=hd><div class=no>{n:02d}</div><div><div class=eb>{en}</div><h1>{title}</h1><div class=sub>{sub}</div></div></div>"
                f"<div class=rule></div><div class=part>{tag}</div>")
    foot = (f"<div class=ft><span>联指经营助手 · AI 原生客户经营</span><span>{n:02d} / {TOTAL}</span></div>"
            f"<div class=bar><i style='width:{round(n/TOTAL*100)}%'></i></div>")
    return f"<meta charset=utf-8><style>{BASE_CSS}{css}</style>{BG}{head}{body}{foot}"

def glass_cube(x, y, s, rot=0, op=1):
    return (f"<div style='position:absolute;left:{x}px;top:{y}px;width:{s}px;height:{s}px;border-radius:{s*0.22:.0f}px;"
            f"transform:rotate({rot}deg);opacity:{op};background:linear-gradient(145deg,rgba(255,255,255,.95),rgba(173,205,255,.55));"
            f"border:1px solid #fff;box-shadow:inset 0 1px 0 #fff,0 18px 30px -12px rgba(21,73,156,.45);z-index:1'></div>")

PAGES = {}
def reg(n):
    def deco(f):
        PAGES[n] = f
        return f
    return deco

# ============ 01 封面 ============
@reg(1)
def p01():
    chips = ''.join(f"<span class=pill style='color:{COL[c][0]};border-color:{COL[c][0]}66;background:#fff'>{t}</span>" + ("<i class=dash></i>" if i < 3 else '')
                    for i, (t, c) in enumerate([('感知', 'cyan'), ('研判', 'blue'), ('行动', 'orange'), ('学习', 'green')]))
    css = """.l{position:absolute;left:150px;top:250px;width:760px;z-index:2}
.l .eb2{font-size:18px;letter-spacing:6px;color:#2F7BEA;font-weight:700}
.l h0{display:block;font-size:112px;font-weight:900;color:#0B2458;letter-spacing:6px;margin-top:18px;line-height:1.1}
.l h2{font-size:46px;margin-top:18px;font-weight:800}
.l .ln{width:84px;height:5px;border-radius:3px;background:linear-gradient(90deg,#15499C,#2F7BEA);margin:34px 0 26px}
.l .tag{font-size:26px;color:#475569;letter-spacing:2px}
.l .chips{display:flex;align-items:center;margin-top:40px}.l .chips .pill{font-size:21px;padding:8px 20px}
.dash{width:34px;height:0;border-top:2px dashed #93B4E6;display:inline-block}
.l .date{margin-top:120px;font-size:22px;color:#94A3B8;letter-spacing:2px}
.arc{position:absolute;border-radius:50%;border:1px solid #BFD4F5;z-index:0}
.hero{position:absolute;left:960px;top:230px;z-index:2}
.hero .win{transform:perspective(2200px) rotateY(-9deg) rotateX(2deg);transform-origin:left center}
.band{position:absolute;right:-200px;top:120px;width:1300px;height:900px;border-radius:50%;border:70px solid transparent;
 border-top-color:#2F7BEA22;border-right-color:#15499C18;transform:rotate(12deg);z-index:0}
.node{position:absolute;width:14px;height:14px;border-radius:50%;background:#fff;border:3px solid #2F7BEA;box-shadow:0 0 0 6px #2F7BEA22;z-index:3}
"""
    body = ("<div class=arc style='left:-260px;top:250px;width:820px;height:820px'></div><div class=arc style='left:-180px;top:330px;width:660px;height:660px'></div>"
            "<div class=band></div>"
            "<div class=l><div class=eb2>AI-NATIVE CUSTOMER OPERATIONS</div><h0>联指经营助手</h0><h2 class=grad>走向 AI 原生的客户经营组织</h2>"
            "<div class=ln></div><div class=tag>看得清 · 接得住 · 打得准 · 越用越聪明</div>"
            f"<div class=chips>{chips}</div><div class=date>2026 年 9 月</div></div>"
            f"<div class=hero>{shot('01-总体信息.png', (0, 0, 1920, 1080), 1000, 588, label='联合指挥驾驶舱 · 总体信息')}</div>"
            + glass_cube(900, 190, 70, 18) + glass_cube(1800, 170, 54, -12) + glass_cube(1840, 780, 82, 24) + glass_cube(920, 820, 46, -20, .9)
            + "<svg style='position:absolute;left:0;top:0;z-index:1' width=1920 height=1080 fill=none stroke='#8FB3EA' stroke-width=1.2 stroke-dasharray='5 6'>"
              "<path d='M935 225 L1000 260'/><path d='M1827 197 L1760 240'/><path d='M1860 800 L1800 760'/><path d='M943 843 L1000 800'/></svg>"
            "<div class=node style='left:1540px;top:880px'></div><div class=node style='left:1700px;top:140px'></div>")
    return page(1, '', '', body, css, header=False)

# ============ 02 三句话汇报 ============
def hero_nodes():
    return """<svg width=260 height=170 viewBox="0 0 260 170" fill="none">
<ellipse cx=130 cy=140 rx=110 ry=22 fill="#CFE0FB" opacity=".6"/>
<g stroke="#9CC2F0" stroke-width="2" stroke-dasharray="4 6"><path d="M60 90 L110 60"/><path d="M150 50 L200 85"/><path d="M95 120 L160 115"/></g>
""" + ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#g1)" stroke="#fff" stroke-width="2"/>' for x, y, r in [(60, 92, 18), (115, 58, 22), (200, 88, 16), (160, 118, 14), (92, 124, 12)]) + """
<defs><radialGradient id="g1" cx=".35" cy=".3"><stop offset="0" stop-color="#E0F2FE"/><stop offset="1" stop-color="#38BDF8"/></radialGradient></defs></svg>"""

def hero_screen():
    return """<div style="position:relative;width:260px;height:170px">
<div style="position:absolute;left:30px;top:6px;width:200px;height:126px;border-radius:14px;transform:perspective(600px) rotateY(-14deg);
 background:linear-gradient(145deg,rgba(255,255,255,.95),rgba(170,200,250,.6));border:1px solid #fff;box-shadow:0 20px 30px -12px rgba(21,73,156,.5);padding:16px 18px">
 <svg width=164 height=90 viewBox="0 0 164 90" fill="none"><path d="M4 70 L40 48 L70 58 L104 24 L150 14" stroke="#2F7BEA" stroke-width="3" stroke-linecap="round"/>
 <g fill="#15499C" opacity=".85"><rect x="8" y="76" width="16" height="12" rx="2"/><rect x="34" y="68" width="16" height="20" rx="2"/><rect x="60" y="72" width="16" height="16" rx="2"/><rect x="86" y="60" width="16" height="28" rx="2"/><rect x="112" y="52" width="16" height="36" rx="2"/></g></svg></div>
<div style="position:absolute;left:104px;top:132px;width:52px;height:18px;background:linear-gradient(180deg,#C9DCF8,#E8F0FC);border-radius:0 0 6px 6px"></div>
<div style="position:absolute;left:70px;top:148px;width:120px;height:10px;border-radius:6px;background:#C9DCF8"></div></div>"""

def hero_stairs(color='green'):
    c1, c2 = COL[color]
    steps = ''.join(f"<div style='position:absolute;left:{20+i*72}px;bottom:14px;width:78px;height:{40+i*38}px;border-radius:10px;"
                    f"background:linear-gradient(160deg,rgba(255,255,255,.95),{c2}66);border:1px solid #fff;box-shadow:0 16px 24px -12px {c1}88'></div>" for i in range(3))
    return (f"<div style='position:relative;width:260px;height:170px'>{steps}"
            f"<svg style='position:absolute;left:190px;top:4px' width=40 height=60 fill=none stroke='{c1}' stroke-width=3 stroke-linecap=round><path d='M6 56V6'/><path d='M6 6h26l-7 9 7 9H6' fill='{c2}'/></svg></div>")

PTS2 = [['决策链长、触点少', '周期长、人员流动', '经验在个人、难复用'], ['统一档案与口径', '一张驾驶舱 + 四大板块', '分级权限与全程留痕'], ['一个底座 · 四个闭环', '六个数字助手分工', '四条底线保安全']]
@reg(2)
def p02():
    cards = [('01', '解决组织问题', '关系和经验沉淀不下来、传不下去', hero_nodes(), 'cyan'),
             ('02', '底座已经建成', '能“记”能“算”，还不会“想”', hero_screen(), 'blue'),
             ('03', '下一步：AI 原生', '分四步走，需拍板六件事', hero_stairs(), 'green')]
    css = """.row{display:grid;grid-template-columns:repeat(3,1fr);gap:40px;height:100%;align-items:stretch}
.c{padding:34px 36px;display:flex;flex-direction:column;overflow:hidden}.c .hero{height:250px;border-radius:18px;display:flex;align-items:center;justify-content:center;margin-bottom:26px}
.c .num{font-size:76px;font-weight:900;line-height:1}.c h3{font-size:40px;color:#0B2458;margin-top:10px;font-weight:800}.c p{font-size:25px;color:#475569;margin-top:16px;line-height:1.55}
.c .pts{list-style:none;margin-top:22px;border-top:1px dashed #DCE7F7;padding-top:16px}.c .pts li{display:flex;gap:12px;align-items:center;font-size:22px;color:#334155;padding:7px 0}
.c .foot{margin-top:auto;display:flex;align-items:center;gap:10px;font-size:17px;color:#94A3B8}
.arrow{position:absolute;top:50%;width:40px;height:40px;margin-top:-20px;border-radius:50%;background:#fff;border:1px solid #DDE8F8;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 16px -8px rgba(21,73,156,.4);z-index:3}"""
    body = "<div class=stage><div class=row>"
    for num, t, d, hero, c in cards:
        c1, c2 = COL[c]
        body += (f"<div class='card c' style='border-top:5px solid {c1}'><div class=hero style='background:linear-gradient(160deg,{c2}1f,#F4F8FF)'>{hero}</div>"
                 f"<div class=num style='background:linear-gradient(135deg,{c1},{c2});-webkit-background-clip:text;color:transparent'>{num}</div>"
                 f"<h3>{t}</h3><p>{d}</p><ul class=pts>" + ''.join(f"<li><i class=dia style='background:{c1}'></i>{x}</li>" for x in PTS2[int(num)-1]) + "</ul>"
                 f"<div class=foot><i class=dia style='background:{c1}'></i>{['现状判断', '第一阶段', '本次汇报重点'][int(num)-1]}</div></div>")
    body += "</div>" + ''.join(f"<div class=arrow style='left:{x}px'>{line_icon('arrow', '#2F7BEA', 20)}</div>" for x in (556, 1152)) + "</div>"
    return page(2, '三句话汇报', '先给结论，后面每一部分都在展开这三句话', body, css)

# ============ 03 问题的本质 ============
@reg(3)
def p03():
    rows = [('link', '决策链长，触点少', '定标、定技术、签验收、批付款分属不同人', '没人说得上话'),
            ('hourglass', '周期长，人员流动', '项目以“年”计，双方人员都会轮岗', '关系断在交接'),
            ('users', '经验在个人', '关系与打法在微信、通讯录、个人记忆里', '组织难以复用')]
    css = """.left{position:absolute;left:0;top:0;width:1000px;bottom:0;display:flex;flex-direction:column;gap:16px}
.r{display:flex;align-items:center;gap:18px;padding:16px 20px}.r .nm{width:250px}.r .nm b{display:block;font-size:26px;color:#0B2458;font-weight:800}
.r .ds{flex:1;font-size:18px;color:#64748B;line-height:1.5}.r .res{padding:10px 16px;border-radius:12px;background:#FEF2F2;border:1px solid #FBCACA;color:#B91C1C;font-size:20px;font-weight:700;white-space:nowrap}
.low{flex:1;display:flex;gap:22px;margin-top:6px}
.ringbox{flex:1;padding:14px;position:relative}
.key{width:330px;padding:28px;border-radius:20px;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff;display:flex;flex-direction:column;justify-content:center;box-shadow:0 24px 40px -18px rgba(21,73,156,.7)}
.key small{font-size:17px;opacity:.8;letter-spacing:3px}.key b{font-size:34px;margin-top:10px;line-height:1.35}.key span{font-size:18px;opacity:.85;margin-top:14px;line-height:1.5}
.right{position:absolute;left:1040px;right:0;top:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
.right .glassbg{position:absolute;inset:40px 0 30px;z-index:-1}"""
    ring = """<svg width="600" height="330" viewBox="0 0 600 330" fill="none">
<defs><linearGradient id="rg" x1="0" x2="1"><stop offset="0" stop-color="#FCA5A5"/><stop offset="1" stop-color="#F87171"/></linearGradient>
<marker id="ah" markerWidth="10" markerHeight="10" refX="5" refY="5" orient="auto"><path d="M0 0 10 5 0 10z" fill="#EF4444"/></marker></defs>
<ellipse cx="300" cy="170" rx="210" ry="118" fill="#FEF2F2" stroke="url(#rg)" stroke-width="10" opacity=".9"/>
<ellipse cx="300" cy="170" rx="210" ry="118" stroke="#fff" stroke-width="2" opacity=".8"/>
<path d="M430 78 Q500 110 505 150" stroke="#EF4444" stroke-width="2.5" marker-end="url(#ah)"/><path d="M470 250 Q420 285 340 290" stroke="#EF4444" stroke-width="2.5" marker-end="url(#ah)"/>
<path d="M170 262 Q100 230 95 190" stroke="#EF4444" stroke-width="2.5" marker-end="url(#ah)"/><path d="M130 88 Q190 52 260 50" stroke="#EF4444" stroke-width="2.5" marker-end="url(#ah)"/>
<text x="300" y="164" text-anchor="middle" font-size="34" font-weight="800" fill="#DC2626">填报死循环</text>
<text x="300" y="198" text-anchor="middle" font-size="17" fill="#94A3B8">靠行政推动，数据随检查起落</text></svg>"""
    chips = [(300, 22, '填表是负担'), (520, 170, '数据不更新'), (300, 318, '系统没人用'), (80, 170, '更没人填')]
    chip_html = ''.join(f"<span class=pill style='position:absolute;left:{x}px;top:{y}px;transform:translate(-50%,-50%);color:#B91C1C;border-color:#FCA5A5;background:#fff;font-size:19px'>{t}</span>" for x, y, t in chips)
    body = "<div class=stage><div class=left>"
    for icn, nm, ds, res in rows:
        body += f"<div class='card r'>{ic(icn, 'red', 54)}<div class=nm><b>{nm}</b></div><div class=ds>{ds}</div>{line_icon('arrow', '#94A3B8', 22)}<div class=res>{res}</div></div>"
    body += (f"<div class=low><div class='card ringbox'><div style='position:relative;width:600px;height:330px;margin:0 auto'>{ring}{chip_html}</div></div>"
             "<div class=key><small>关键判断</small><b>打破这个循环，<br>而不是加功能</b><span>让信息自动汇聚、让判断主动送达，记录才有回报。</span></div></div></div>"
             f"<div class=right><div class='glass glassbg'></div>{shot('08-关系网络.png', (540, 290, 860, 645), 700, 551, label='五位一体 · 客户关系网络')}"
             "<div class=cap>关系网络：断点与单点一目了然 · 界面示意 · 样例数据</div></div></div>")
    return page(3, '问题的本质：组织没有“记忆”', '三个结构性矛盾，不是哪个人不努力', body, css)

# ============ 04 第一阶段成果 ============
@reg(4)
def p04():
    shots = [('总体信息', 'cyan', '01-总体信息.png'), ('经营分析', 'blue', '02-经营分析.png'), ('五位一体', 'gold', '03-五位一体.png'), ('项目作战地图', 'orange', '05-项目作战地图.png')]
    css = """.l{position:absolute;left:0;top:0;width:1040px;bottom:0;padding:26px 28px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px 24px}.lab{display:inline-flex;gap:8px;align-items:center;font-size:19px;font-weight:800;color:#0B2458;margin-bottom:9px}.lab i{width:10px;height:10px;border-radius:50%}
.cap2{position:absolute;right:30px;bottom:12px;font-size:14px;color:#94A3B8}
.r{position:absolute;left:1076px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:16px}
.rc{display:flex;gap:20px;align-items:center;padding:20px 24px;flex:1}.rc b{display:block;font-size:28px;color:#0B2458;font-weight:800}.rc span{font-size:20px;color:#64748B}
.rc em{margin-left:auto;font-style:normal;font-size:15px;color:#2F7BEA;background:#EAF2FF;padding:4px 10px;border-radius:99px}
.note{padding:18px 24px;border-radius:16px;background:linear-gradient(90deg,#FFF8EB,#FFFFFF);border:1px solid #F3D59C;color:#92400E;font-size:22px;font-weight:800;display:flex;gap:14px;align-items:center}"""
    body = "<div class=stage><div class='l glass'><div class=grid>"
    for t, c, f in shots:
        body += f"<div><div class=lab><i style='background:{COL[c][0]}'></i>{t}</div>{shot(f, (0, 0, 1920, 1080), 480, 296)}</div>"
    body += "</div><div class=cap2>界面示意 · 样例数据</div></div><div class=r>"
    for i, t, d, e in [('doc', '统一档案', '一个客户一份档案', '五层账本'), ('ruler', '统一口径', '投资与份额分开统计', '签约丢标自动剔除'),
                       ('gauge', '一张驾驶舱', '四大作战板块 + 工作台', '领导与一线同一份数据'), ('shield', '权限与留痕', '分级查看，全程留痕', '个人 / 团队 / 区域 / 全局')]:
        body += f"<div class='card rc'>{ic(i, 'blue', 56)}<div><b>{t}</b><span>{d}</span></div><em>{e}</em></div>"
    body += f"<div class=note>{ic('lock', 'gold', 42)}现状：能记能算，还不会想——目前没有 AI 能力</div></div></div>"
    return page(4, '第一阶段成果：底座已经建成', '先建账本、口径、权限和驾驶舱，AI 才有东西可用', body, css)

# ============ 05 AI 辅助 vs AI 原生 ============
@reg(5)
def p05():
    rows = [('信息来源', '人事后补填', 'AI 自动汇聚多源信息', 'scan', '会议纪要、邮件、公告自动识别并关联档案'), ('判断方式', '人看报表下结论', 'AI 起草结论并附出处', 'chart', '每句结论都能点开看依据'),
            ('行动发起', '想起来才去做', '系统主动推送下一步', 'bell', '晨报：今天先联系谁、为什么、带什么'), ('经验沉淀', '在个人脑子里', '沉淀为组织剧本', 'book', '什么客户、什么阶段、什么做法有效'),
            ('AI 角色', '问了才答的工具', '嵌入每个环节的数字助手', 'chip', '感知、研判、行动、学习全链路参与')]
    css = """.hdr{display:grid;grid-template-columns:170px 1fr 140px 1fr;align-items:end;margin-bottom:12px}
.hdr b{font-size:26px;font-weight:800}.grid{display:grid;grid-template-columns:170px 1fr 140px 1fr;row-gap:14px;align-items:center}
.dim{font-size:21px;color:#64748B;font-weight:700}
.old{padding:30px 24px;border-radius:14px;background:#F1F5F9;color:#94A3B8;font-size:23px;border:1px solid #E2E8F0}
.new{padding:16px 22px;display:flex;gap:18px;align-items:center;font-size:25px;font-weight:800;color:#0B2458;border-left:5px solid #2F7BEA}
.new small{display:block;font-size:18px;color:#64748B;font-weight:400;margin-top:4px}.mid{display:flex;justify-content:center}.glassarrow{position:absolute;left:870px;top:40px;width:160px;height:560px;z-index:0;opacity:.9}
.banner{margin-top:26px;padding:22px;border-radius:18px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;font-size:30px;font-weight:800;text-align:center;box-shadow:0 24px 40px -20px rgba(21,73,156,.8);letter-spacing:1px}
.banner span{color:#FDE68A}"""
    arrow = """<svg class=glassarrow viewBox="0 0 160 560"><defs><linearGradient id="ga" x1="0" x2="1"><stop offset="0" stop-color="#E6F0FF"/><stop offset="1" stop-color="#BFD6FA"/></linearGradient></defs>
<path d="M40 20 H100 V430 H140 L70 540 L0 430 H40 Z" transform="rotate(-90 80 280) translate(0 0)" fill="none"/></svg>"""
    body = ("<div class=stage><div class=hdr><span></span><b style='color:#94A3B8'>传统 / AI 辅助</b><span></span><b class=grad style='font-size:30px'>AI 原生</b></div><div class=grid>")
    for dim, old, new, icn, hint in rows:
        body += (f"<div class=dim>{dim}</div><div class=old>{old}</div>"
                 f"<div class=mid>{ic('arrow', 'blue', 44)}</div><div class='card new'>{ic(icn, 'blue', 52)}<div>{new}<small>{hint}</small></div></div>")
    body += "</div><div class=banner>检验标准：拿掉 AI，工作会不会退回原样？<span> 会，才算 AI 原生。</span></div></div>"
    return page(5, 'AI 辅助 vs AI 原生', '不是加一个聊天框，而是让工作默认经过 AI', body, css)

# ============ 06 架构总图 ============
@reg(6)
def p06():
    def loop(k, name, sub, agents, outs):
        c1, c2 = COL[k]
        ags = ''.join(f"<div class=ag>{ic(i, k, 46)}<div><b style='color:{c1}'>{a}</b><span>{d}</span></div></div><ul class=pts>"
                      + ''.join(f"<li><i class=dia style='background:{c1}'></i>{t}</li>" for t in pts) + "</ul>" for i, a, d, pts in agents)
        chips = ''.join(f"<em style='color:{c1};border-color:{c1}55;background:{c1}0d'>{o}</em>" for o in outs)
        return f"<div class='card loop' style='border-top:5px solid {c1}'><div class=lh><b style='color:{c1}'>{name}</b><small>{sub}</small></div>{ags}<div class=out><span>产出</span>{chips}</div></div>"
    css = """.main{position:absolute;inset:0;display:flex;flex-direction:column;gap:14px}
.entry{display:flex;gap:14px;align-items:center;padding:12px 16px}.entry>span{font-size:18px;color:#64748B;width:110px;font-weight:700}.entry em{flex:1;font-style:normal;text-align:center;padding:11px;border-radius:99px;background:#F1F6FF;border:1px solid #D9E6FA;color:#15499C;font-size:21px;font-weight:700}
.loops{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;flex:1}
.loop{padding:18px 18px 16px;display:flex;flex-direction:column}.lh b{font-size:29px;font-weight:800}.lh small{font-size:18px;color:#64748B;margin-left:10px}
.ag{display:flex;gap:14px;align-items:center;margin-top:12px;padding:12px 14px;border-radius:14px;background:#F7FAFF;border:1px solid #E5EEFB}.ag b{font-size:23px;display:block;font-weight:800}.ag span{font-size:17px;color:#64748B}
.pts{list-style:none;margin:8px 4px 0 8px}.pts li{display:flex;gap:10px;align-items:center;font-size:18px;color:#334155;padding:4px 0}
.out{margin-top:auto;padding-top:12px;border-top:1px dashed #D9E6FA;display:flex;flex-wrap:wrap;gap:8px;align-items:center}.out span{font-size:15px;color:#94A3B8}.out em{font-style:normal;font-size:16px;padding:4px 12px;border-radius:99px;border:1px solid;font-weight:700}
.platform{position:relative;padding:14px 22px 20px;transform:perspective(1400px) rotateX(14deg);transform-origin:top}
.platform:after{content:'';position:absolute;left:14px;right:14px;bottom:-12px;height:12px;border-radius:0 0 18px 18px;background:linear-gradient(180deg,#BBD3F5,#E3EEFD)}
.platform .t{font-size:23px;font-weight:800;background:linear-gradient(90deg,#B45309,#D97706);-webkit-background-clip:text;color:transparent;margin-bottom:10px}
.bricks{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.bricks div{text-align:center;padding:13px 0;border-radius:12px;background:linear-gradient(180deg,#FFFBF2,#FDEFD3);border:1px solid #F3D59C;color:#92400E;font-size:21px;font-weight:700;box-shadow:0 6px 0 #F1D7A6}
.guard{display:grid;grid-template-columns:120px repeat(4,1fr);gap:12px;align-items:center;padding:10px 16px;background:linear-gradient(90deg,#FFF5F5,#FFFFFF)}.guard>span{color:#DC2626;font-size:19px;font-weight:800}
.guard div{display:flex;gap:10px;align-items:center;justify-content:center;padding:9px;border-radius:12px;border:1px solid #FBCACA;background:#fff;color:#991B1B;font-size:20px;font-weight:700}"""
    body = ("<div class=stage><div class=main><div class='card entry'><span>使用入口</span><em>驾驶舱 · 工作台</em><em>页面侧边助手</em><em>企微 / 钉钉推送</em><em>会议 / 邮件 / 文档接入</em></div><div class=loops>"
            + loop('cyan', '感知闭环', '自动汇聚', [('scan', '资料解析员', '会议 · 邮件 · 合同', ['识别客户、人物与承诺', '自动关联已有档案']), ('radar', '外部情报员', '招标 · 中标 · 任免', ['公告匹配在谈商机', '任免更新联系人'])], ['待确认记录', '商机信号', '职务变动'])
            + loop('blue', '研判闭环', '会解读', [('chart', '分析师', '体检 · 解读 · 风险', ['客户体检：现状、风险、机会', '经营解读：差在哪、为什么', '把握度说明：缺材料、缺人', '每条结论附证据出处'])], ['体检报告', '把握度说明', '风险清单'])
            + loop('orange', '行动闭环', '先开口', [('flag', '作战参谋', '打谁 · 谁去 · 第一步', ['找引荐路径与候选人', '生成话术与材料清单']), ('bell', '督办助理', '晨报 · 催办 · 交接', ['每天推送最重要的几件事', '逾期与单点风险催办'])], ['每日晨报', '作战方案', '交接包'])
            + loop('green', '学习闭环', '越用越准', [('loop', '复盘教练', '什么有效 → 更新剧本', ['追踪建议—采纳—结果', '提炼有效打法入剧本', '提出规则校准（人审核）', '季度组织能力报告'])], ['经营剧本', '规则校准', '能力报告'])
            + "</div><div class='glass platform'><div class=t>经营知识底座 · 组织记忆（唯一事实来源）</div><div class=bricks>"
            + ''.join(f"<div>{t}</div>" for t in ['客户与组织', '人与关系', '互动与情报', '商机与项目', '经营结果', '剧本与规则'])
            + "</div></div><div class='card guard'><span>四条底线</span>"
            + ''.join(f"<div>{line_icon('shield', '#DC2626', 20)}{t}</div>" for t in ['数据不出内网', '权限不扩大', 'AI 不直接改数据', '评估不用于考核'])
            + "</div></div></div>")
    return page(6, 'AI 原生架构总图', '一个底座 · 四个闭环 · 六个数字助手 · 四条底线', body, css)

# ============ 07 底座 ============
@reg(7)
def p07():
    rows = [('01', '一个客户一份档案', '全公司看同一个事实', 'doc', 1), ('02', '过程要留痕', '关系判断的依据', 'calendar', 2),
            ('03', '记录建议—采纳—结果', '没有它，“越用越聪明”就无从谈起', 'loop', 3), ('04', '经验成为资产', '有专人维护、有版本、可回退', 'book', 4)]
    css = """.l{position:absolute;left:0;top:10px;width:880px}
.plat{position:absolute;left:30px;top:520px;width:820px;height:150px;border-radius:26px;transform:perspective(1200px) rotateX(58deg);
 background:linear-gradient(180deg,rgba(255,255,255,.9),rgba(190,214,250,.7));border:1px solid #fff;box-shadow:0 40px 60px -30px rgba(21,73,156,.55)}
.plat2{position:absolute;left:80px;top:600px;width:720px;height:120px;border-radius:26px;transform:perspective(1200px) rotateX(58deg);background:linear-gradient(180deg,#F5DDA8,#FDF3DC);border:1px solid #fff;opacity:.9}
.lbl{position:absolute;left:0;right:0;top:700px;text-align:center}.lbl b{font-size:28px;font-weight:800;background:linear-gradient(90deg,#B45309,#D97706);-webkit-background-clip:text;color:transparent}.lbl div{font-size:17px;color:#94A3B8;margin-top:4px}
.r{position:absolute;left:940px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:16px}
.rc{flex:1;display:flex;align-items:center;gap:22px;padding:18px 26px}.rc .n{font-size:50px;font-weight:900;width:80px}
.rc b{display:block;font-size:27px;color:#0B2458;font-weight:800}.rc span{font-size:19px;color:#64748B}
.prog{margin-left:auto;display:flex;gap:5px}.prog i{width:12px;height:30px;border-radius:4px;background:#E6EEF9}.prog i.on{background:linear-gradient(180deg,#FBBF24,#D97706)}
.hot{border:2px solid #2F7BEA;box-shadow:0 22px 40px -16px rgba(47,123,234,.55)}.hot .tag{position:absolute;right:18px;top:-13px;background:linear-gradient(90deg,#D97706,#FBBF24);color:#fff;font-size:15px;padding:3px 12px;border-radius:99px;font-weight:700}
.beam{position:absolute;left:870px;top:60px;z-index:0}"""
    body = ("<div class=stage><div class=l><div class=plat2></div><div class=plat></div>"
            f"<div style='position:relative;left:60px;top:120px;z-index:2'>{shot('09-客户组织架构.png', (265, 395, 1063, 670), 760, 505, label='五位一体 · 客户档案 · 客户组织架构')}</div>"
            "<div class=lbl><b>经营知识底座 · 组织记忆</b><div>客户组织架构 · 界面示意 · 样例数据</div></div></div>"
                        "<div class=r>")
    for n, t, d, i, k in rows:
        hot = n == '03'
        body += (f"<div class='card rc{' hot' if hot else ''}'>" + ("<span class=tag>最关键</span>" if hot else '')
                 + f"<div class='n grad'>{n}</div>{ic(i, 'blue' if not hot else 'cyan', 52)}<div><b>{t}</b><span>{d}</span></div>"
                 + "<div class=prog>" + ''.join(f"<i class={'on' if j < k else ''}></i>" for j in range(4)) + "</div></div>")
    body += "</div></div>"
    return page(7, '底座：组织记忆决定 AI 上限', '数据统一、过程留痕、结果回收，三件事决定 AI 能走多远', body, css)

# ============ 08 感知闭环 ============
@reg(8)
def p08():
    srcs = [('meeting', '会议纪要'), ('mail', '往来邮件'), ('notice', '招标 / 中标公告'), ('badge', '人事任免公告'), ('file', '合同与文档')]
    caps = ['识别客户与人物', '关联已有档案', '发现商机信号', '识别职务变动', '提取承诺与待办', '标注原文出处']
    outs = [('新增互动记录', '拜访 / 交流 / 承诺', 'doc'), ('商机阶段变化', '公告 → 阶段推进建议', 'flag'), ('联系人职务更新', '任免 → 档案更新', 'user'), ('风险与缺口提醒', '久未维系 · 单点 · 缺口', 'warn')]
    css = """.col{position:absolute;top:0;bottom:90px;display:flex;flex-direction:column;gap:14px;justify-content:center}
.src{width:360px;display:flex;gap:16px;align-items:center;padding:16px 20px;font-size:23px;font-weight:800;color:#0B2458}
.engine{position:absolute;left:470px;right:520px;top:0;bottom:90px;display:flex;align-items:center;justify-content:center}
.core{position:relative;width:250px;height:250px;border-radius:56px;transform:rotate(45deg);background:linear-gradient(145deg,rgba(255,255,255,.95),rgba(125,190,250,.6));border:1px solid #fff;
 box-shadow:inset 0 2px 0 #fff,0 40px 60px -24px rgba(14,165,233,.6);display:flex;align-items:center;justify-content:center}
.core>div{transform:rotate(-45deg);text-align:center}.core b{display:block;font-size:30px;font-weight:900;color:#0B2458;margin-top:8px}.core small{font-size:16px;color:#0369A1;letter-spacing:3px}
.orbit{position:absolute;border-radius:50%;border:1.5px dashed #7DD3FC}
.cap{position:absolute;transform:translate(-50%,-50%);background:#fff;color:#0369A1;border-color:#7DD3FC;font-size:19px;box-shadow:0 8px 16px -8px rgba(14,165,233,.5)}
.out{width:470px;display:flex;gap:16px;align-items:center;padding:16px 20px}.out b{display:block;font-size:23px;color:#0B2458;font-weight:800}.out span{font-size:17px;color:#64748B}
.out em{margin-left:auto;font-style:normal;font-size:15px;color:#B45309;background:#FEF3C7;border:1px solid #FCD34D;padding:3px 10px;border-radius:99px;font-weight:700;white-space:nowrap}
.foot{position:absolute;left:0;right:0;bottom:0;height:68px;border-radius:16px;background:linear-gradient(90deg,#E0F2FE,#EEF4FF);border:1px solid #BAE6FD;display:flex;align-items:center;justify-content:center;gap:14px;font-size:24px;font-weight:800;color:#0B2458}
.flow{position:absolute;left:0;top:0;z-index:0}"""
    body = "<div class=stage><svg class=flow width=1728 height=700 fill=none stroke='#7DD3FC' stroke-width=2 stroke-dasharray='6 7'>"
    for i in range(5):
        y = 70 + i * 106
        body += f"<path d='M360 {y} C 520 {y}, 560 353, 690 353'/>"
    for i in range(4):
        y = 105 + i * 128
        body += f"<path d='M994 353 C 1120 353, 1150 {y}, 1258 {y}'/>"
    body += "</svg><div class=col style='left:0'>" + ''.join(f"<div class='card src'>{ic(i, 'cyan', 50)}{t}</div>" for i, t in srcs) + "</div>"
    body += "<div class=engine><div style='position:relative;width:680px;height:620px;display:flex;align-items:center;justify-content:center'>"
    body += "<div class=orbit style='width:520px;height:300px;left:80px;top:160px'></div><div class=orbit style='width:600px;height:420px;left:40px;top:100px;opacity:.6'></div>"
    body += f"<div class=core><div>{line_icon('chip', '#0284C7', 64, 1.6)}<b>AI 解析引擎</b><small>PARSE · LINK · FLAG</small></div></div>"
    pos = [(340, 70), (620, 190), (620, 430), (340, 560), (60, 430), (60, 190)]
    body += ''.join(f"<span class='pill cap' style='left:{x}px;top:{y}px'>{t}</span>" for (x, y), t in zip(pos, caps))
    body += "</div></div><div class=col style='right:0'>" + ''.join(f"<div class='card out'>{ic(i, 'blue', 46)}<div><b>{t}</b><span>{d}</span></div><em>待确认</em></div>" for t, d, i in outs) + "</div>"
    body += f"<div class=foot>{line_icon('shield', '#0284C7', 28)}所有 AI 结果先进入“待确认”队列，负责人确认后才入库</div></div>"
    return page(8, '感知闭环：多源情报自动汇聚', 'AI 从会议、邮件、公告、合同中识别客户动态，自动关联到档案', body, css)

# ============ 09 研判闭环 ============
@reg(9)
def p09():
    caps = [('doc', '客户体检报告', '现状、风险、机会、建议', '业主关系稳定，设计院关键技术负责人尚未接触'), ('chart', '经营解读', '差在哪、可能原因、关注谁', '管理订货达成率最低，主要差在两个区域'),
            ('target', '把握度说明', '缺什么材料、缺哪个关键人', '招标阶段缺技术方案材料，把握度下调'), ('radar', '风险主动发现', '久未维系、单点、决策链缺口', '两位关键人超过维系周期，建议本周联系')]
    css = """.l{position:absolute;left:0;top:0;bottom:0;width:760px;display:flex;flex-direction:column;align-items:center;justify-content:center}
.bubble{position:absolute;right:-10px;top:30px;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff;font-size:19px;font-weight:700;padding:10px 18px;border-radius:14px 14px 14px 4px;box-shadow:0 16px 30px -12px rgba(21,73,156,.7);z-index:3}
.r{position:absolute;left:820px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:20px}
.g{display:grid;grid-template-columns:1fr 1fr;gap:18px;flex:1}.cc{padding:24px;display:flex;flex-direction:column;gap:14px}.ex{margin-top:auto;padding:14px 16px;border-radius:12px;background:#F1F6FF;border:1px solid #D9E6FA;font-size:18px;color:#1E3A8A;line-height:1.5}.ex small{display:block;font-size:14px;color:#2F7BEA;font-weight:700;letter-spacing:2px;margin-bottom:4px}.ex i{font-style:normal;display:inline-flex;gap:4px;align-items:center;margin-left:8px;font-size:14px;color:#2F7BEA}.cc b{font-size:27px;color:#0B2458;font-weight:800}.cc span{font-size:19px;color:#64748B}
.chain{height:190px;display:flex;align-items:center;gap:0;padding:0 10px}.brick{flex:1;height:120px;border-radius:20px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;
 background:linear-gradient(160deg,rgba(255,255,255,.95),var(--c2));border:1px solid #fff;box-shadow:0 22px 34px -16px var(--c1),inset 0 1px 0 #fff;transform:perspective(700px) rotateX(10deg)}
.brick b{font-size:26px;font-weight:900;color:var(--c1)}.brick small{font-size:16px;color:#475569}
.link{width:60px;height:4px;background:repeating-linear-gradient(90deg,#94B8EC 0 8px,transparent 8px 14px)}"""
    body = (f"<div class=stage><div class=l><div style='position:relative'><div class=bubble>每个结论都能追溯证据</div>"
            f"{shot('10-关系评估详情.png', (1066, 0, 848, 1080), 580, 764, label='五位一体 · 关系评估 · 评分与建议')}</div>"
            "<div class=cap style='margin-top:10px'>评分公式 · 证据 · 缺口 · 下一步建议 · 界面示意 · 样例数据</div></div><div class=r><div class=g>")
    body += ''.join(f"<div class='card cc'><div style='display:flex;gap:16px;align-items:center'>{ic(i, 'blue', 56)}<div><b>{t}</b><br><span>{d}</span></div></div><div class=ex><small>AI 示例</small>“{e}”<i>{line_icon('link', '#2F7BEA', 18)}出处</i></div></div>" for i, t, d, e in caps)
    body += "</div><div class='glass chain'>"
    bricks = [('数字有规则', '规则打分 · 稳定可审计', '#15499C', '#BFD6FA'), ('结论有出处', 'AI 解释 · 每句可点开', '#0284C7', '#BAE6FD'), ('决定有人签', '负责人拍板 · 可追溯', '#B45309', '#FDE68A')]
    body += "<i class=link></i>".join(f"<div class=brick style='--c1:{c1};--c2:{c2}'><b>{t}</b><small>{d}</small></div>" for t, d, c1, c2 in bricks)
    body += "</div></div></div>"
    return page(9, '研判闭环：会解读，有出处', '规则负责算，AI 负责讲清楚，人负责拍板', body, css)

# ============ 10 行动闭环 ============
@reg(10)
def p10():
    cards = [('sun', '每日晨报', '今天先联系谁、为什么、带什么', ['转计划', '不需要', '可调频率'], '今天先联系：设计院技术负责人', '已超维系周期，项目进入招标设计；建议带技术方案'),
             ('flag', '作战参谋', '打谁、谁去、通过谁引荐、第一步', ['引荐路径', '话术', '材料清单'], '建议：经合作过的同事引荐', '第一步安排技术交流，附方案要点与同类案例'),
             ('bell', '督办助理', '逾期、无人负责、单点风险', ['提醒', '催办', '上报'], '提醒：一条关键关系跟进已逾期', '负责人未处理，已同步区域指挥'),
             ('box', '交接包', '轮岗离职时一键生成并确认交接', ['客户', '关系', '待办'], '交接包已生成，待接收人确认', '含客户概况、关系历史、承诺事项与待办')]
    css = """.l{position:absolute;left:0;top:0;bottom:0;width:470px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px}
.ltag{position:absolute;left:50%;bottom:52px;transform:translateX(-50%);background:linear-gradient(90deg,#F97316,#FB923C);color:#fff;font-size:17px;font-weight:700;padding:6px 16px;border-radius:99px;white-space:nowrap;box-shadow:0 10px 20px -8px #F9731699}
.r{position:absolute;left:560px;right:0;top:0;bottom:0;display:grid;grid-template-columns:1fr 1fr;gap:22px}
.ac{padding:26px 28px;display:flex;flex-direction:column;border-top:5px solid #F97316}.ac b{font-size:30px;color:#0B2458;font-weight:800;margin-top:16px}.ac span{font-size:20px;color:#64748B;margin-top:8px}
.ac .tags{margin-top:auto;display:flex;gap:10px}.ac .tags em{font-style:normal;font-size:17px;padding:5px 14px;border-radius:99px;border:1px solid #FDBA74;color:#C2410C;background:#FFF7ED;font-weight:700}
.sig{position:absolute;left:470px;top:0}.msg{margin:18px 0 16px;padding:14px 18px;border-radius:14px;background:#FFF7ED;border:1px solid #FED7AA;border-left:4px solid #F97316}.msg small{display:flex;gap:6px;align-items:center;font-size:14px;color:#EA580C;font-weight:700;letter-spacing:1px}.msg b{display:block;font-size:20px;color:#7C2D12;margin-top:6px;font-weight:800}.msg span{display:block;font-size:17px;color:#9A3412;margin-top:4px}"""
    body = (f"<div class=stage><div class=l><div style='position:relative'>{shot('06-作战情报卡.png', (895, 378, 360, 534), 420, 649, label='项目作战地图 · 作战情报卡')}<span class=ltag>现有：作战情报卡 → AI 主动推送</span></div>"
            "<div class=cap>界面示意 · 样例数据</div></div>"
            "<svg class=sig width=90 height=780 fill=none stroke='#FDBA74' stroke-width=2 stroke-dasharray='6 6'><path d='M0 390 C45 390 45 180 90 180'/><path d='M0 400 C45 400 45 400 90 400'/><path d='M0 410 C45 410 45 600 90 600'/></svg><div class=r>")
    body += ''.join(f"<div class='card ac'><div style='display:flex;gap:18px;align-items:center'>{ic(i, 'orange', 58)}<div><b style='margin:0'>{t}</b><br><span>{d}</span></div></div>"
                    f"<div class=msg><small>{line_icon('bell', '#F97316', 16)} AI 推送示例</small><b>{m1}</b><span>{m2}</span></div><div class=tags>" + ''.join(f"<em>{x}</em>" for x in tg) + "</div></div>" for i, t, d, tg, m1, m2 in cards)
    body += "</div></div>"
    return page(10, '行动闭环：系统先开口', '从“人找系统”到“系统找人”，判断落到具体的人、时间和做法', body, css)

# ============ 11 学习闭环 ============
@reg(11)
def p11():
    steps = ['建议', '采纳', '执行', '结果', '总结规律', '更新剧本']
    css = """.l{position:absolute;left:0;top:0;bottom:0;width:860px;display:flex;align-items:center;justify-content:center}
.ring{position:relative;width:700px;height:700px}
.orb{position:absolute;left:230px;top:230px;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff,#FDE68A 55%,#F59E0B);box-shadow:0 30px 60px -20px #D9770699,inset 0 2px 0 #fff;display:flex;flex-direction:column;align-items:center;justify-content:center}
.orb b{font-size:36px;color:#0B2458;font-weight:900}.orb small{font-size:18px;color:#78350F;margin-top:4px}
.st{position:absolute;transform:translate(-50%,-50%);background:#fff;color:#15803D;border-color:#86EFAC;font-size:22px;padding:8px 20px;box-shadow:0 10px 20px -10px #16A34A88}
.r{position:absolute;left:900px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:16px}
.r h4{font-size:24px;color:#16A34A;font-weight:800;letter-spacing:2px}
.oc{display:flex;gap:18px;align-items:center;padding:20px 24px;flex:1}.oc i{font-style:normal;display:inline-block;margin-top:8px;font-size:16px;color:#15803D;background:#F0FDF4;border:1px solid #BBF7D0;padding:3px 10px;border-radius:8px}.oc b{display:block;font-size:26px;color:#0B2458;font-weight:800}.oc span{font-size:18px;color:#64748B}
.tip{padding:18px 22px;border-radius:16px;display:flex;gap:14px;align-items:center;font-size:21px;font-weight:700}"""
    ring = """<svg width="700" height="700" viewBox="0 0 700 700" fill="none" style="position:absolute;left:0;top:0">
<defs><linearGradient id="lr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#86EFAC"/><stop offset="1" stop-color="#7FB2FF"/></linearGradient>
<marker id="ma" markerWidth="12" markerHeight="12" refX="6" refY="6" orient="auto"><path d="M0 0 12 6 0 12z" fill="#16A34A"/></marker></defs>
<circle cx="350" cy="350" r="260" stroke="url(#lr)" stroke-width="34" opacity=".35"/>
<circle cx="350" cy="350" r="260" stroke="#fff" stroke-width="2" opacity=".9"/>
<path d="M350 90 A260 260 0 0 1 575 220" stroke="#16A34A" stroke-width="3" marker-end="url(#ma)"/>
<path d="M575 480 A260 260 0 0 1 350 610" stroke="#16A34A" stroke-width="3" marker-end="url(#ma)"/>
<path d="M125 480 A260 260 0 0 1 125 220" stroke="#16A34A" stroke-width="3" marker-end="url(#ma)"/></svg>"""
    import math
    pos = [(350 + 260 * math.sin(math.radians(a)), 350 - 260 * math.cos(math.radians(a))) for a in range(0, 360, 60)]
    body = (f"<div class=stage><div class=l><div class=ring>{ring}<div class=orb><b>组织记忆</b><small>越用越准</small></div>"
            + ''.join(f"<span class='pill st' style='left:{x:.0f}px;top:{y:.0f}px'>{t}</span>" for (x, y), t in zip(pos, steps))
            + "</div></div><div class=r><h4>产出</h4>")
    body += ''.join(f"<div class='card oc'>{ic(i, 'green', 54)}<div><b>{t}</b><span>{d}</span></div></div>" for i, t, d in
                    [('book', '经营剧本', '哪类客户、哪个阶段、什么做法最有效<br><i>例：设计阶段先做技术交流，关系提升更快</i>'), ('ruler', '规则校准（人审核）', '维系周期、阶段把握度按实际结果调整<br><i>例：业主高层维系周期由系统建议调整</i>'), ('chart', '季度能力报告', '关系资产结构、风险消解、预测偏差<br><i>例：预测与实际签约的偏差逐季缩小</i>')])
    body += (f"<div class=tip style='background:#FFF8EB;border:1px solid #F3D59C;color:#92400E'>{ic('calendar', 'gold', 40)}见效节奏：同时看中间结果，约两到三个季度出现规律</div>"
             f"<div class=tip style='background:#EEF4FF;border:1px solid #C9DBF6;color:#15499C'>{ic('lock', 'blue', 40)}只用去除个人信息的汇总经验，不看个人明细</div></div></div>")
    return page(11, '学习闭环：越用越聪明', '经验不随人员流动流失，而是随时间积累', body, css)

# ============ 12 项目旅程 ============
PROD12 = ['商机建议', '体检报告', '作战计划', '晨报', '互动记录', '阶段推进', '剧本条目']
@reg(12)
def p12():
    steps = [('cyan', '发现', '外部情报员', '招标公告 → 建议新建商机', '区域指挥确认'), ('blue', '研判', '分析师', '体检：设计院关键人未接触', None),
             ('orange', '部署', '作战参谋', '找到引荐人，建议先做技术交流', '客户经理确认转计划'), ('orange', '提醒', '督办助理', '晨报提示，到期前再提醒', None),
             ('cyan', '记录', '资料解析员', '纪要自动解析：对方关注国产化', '本人确认入档'), ('blue', '推进', '分析师', '关系更新，建议推进阶段', '负责人确认'),
             ('green', '复盘', '复盘教练', '“设计阶段先做技术交流”入剧本', '剧本负责人审核')]
    css = """.track{position:absolute;left:0;right:0;top:40px;height:34px;border-radius:20px;background:linear-gradient(90deg,#BAE6FD,#BFD6FA,#FED7AA,#BBF7D0);
 box-shadow:inset 0 2px 0 #ffffffcc,0 18px 30px -16px rgba(21,73,156,.45);transform:perspective(900px) rotateX(30deg)}
.steps{position:absolute;left:0;right:0;top:0;display:grid;grid-template-columns:repeat(7,1fr);gap:16px}
.s{display:flex;flex-direction:column;align-items:center}
.dot{width:108px;height:108px;border-radius:50%;background:#fff;border:5px solid var(--c);display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:900;color:var(--c);box-shadow:0 16px 28px -12px var(--c)}
.nm{font-size:32px;font-weight:900;color:var(--c);margin:14px 0 12px}
.sc{width:100%;height:480px;padding:22px 18px;display:flex;flex-direction:column;align-items:center;text-align:center;border-top:4px solid var(--c)}
.sc b{font-size:24px;color:#0B2458;font-weight:800}.sc span{font-size:20px;color:#475569;line-height:1.55;margin-top:14px}
.prod{margin-top:auto;margin-bottom:12px;font-size:15px;color:#94A3B8}.prod b{display:block;margin-top:4px;font-size:19px;color:var(--c);padding:6px 14px;border-radius:99px;background:#fff;border:1px solid var(--c)}
.sc em{font-style:normal;font-size:17px;padding:8px 12px;border-radius:12px;background:#FFF8EB;border:1px solid #F3D59C;color:#92400E;font-weight:700}
.sc em.auto{background:#F1F5F9;border-color:#E2E8F0;color:#94A3B8;font-weight:400}
.note{position:absolute;left:0;right:0;bottom:0;text-align:center;font-size:32px;font-weight:800;color:#0B2458}.note span{background:linear-gradient(90deg,#D97706,#F59E0B);-webkit-background-clip:text;color:transparent}"""
    body = "<div class=stage><div class=track></div><div class=steps>"
    for i, (c, nm, who, d, human) in enumerate(steps, 1):
        body += (f"<div class=s style='--c:{COL[c][0]}'><div class=dot>{i}</div><div class=nm>{nm}</div><div class='card sc'>{ic({'外部情报员':'radar','分析师':'chart','作战参谋':'flag','督办助理':'bell','资料解析员':'scan','复盘教练':'loop'}[who], c, 50)}"
                 f"<b style='margin-top:12px'>{who}</b><span>{d}</span><div class=prod>产出<b>{PROD12[i-1]}</b></div>" + (f"<em>人：{human}</em>" if human else "<em class=auto>自动完成</em>") + "</div></div>")
    body += "</div><div class=note>AI 负责<span>感知、整理、提醒、起草</span>；判断与承诺<span>始终由人做</span></div></div>"
    return page(12, '一个项目的完整旅程', '情景示意（虚构）：某市地铁新线，六个数字助手接力，人在关键节点拍板', body, css)

# ============ 13 人机分工 ============
def glass_obj(icon, color):
    c1, c2 = COL[color]
    return (f"<div style='width:130px;height:130px;border-radius:36px;transform:perspective(500px) rotateX(12deg) rotateY(-12deg);"
            f"background:linear-gradient(145deg,rgba(255,255,255,.96),{c2}88);border:1px solid #fff;box-shadow:inset 0 2px 0 #fff,0 26px 40px -18px {c1};"
            f"display:flex;align-items:center;justify-content:center'>{line_icon(icon, c1, 64, 1.8)}</div>")

@reg(13)
def p13():
    cols = [('cyan', 'eye', 'AI 直接做', '只读不写：查询 · 汇总 · 提醒 · 起草', ['查询与汇总', '生成晨报与体检报告', '风险发现与到期提醒', '起草话术与材料']),
            ('gold', 'shield', 'AI 建议 · 人确认', '任何写入与变更，确认人即责任人', ['新增互动记录', '推进商机阶段', '生成跟进计划', '完成交接、调整剧本']),
            ('red', 'lock', '只能人做', 'AI 不参与决定', ['对客户的任何承诺与发送', '资源调配、调整负责人', '评价员工、绩效考核', '权限授予'])]
    css = """.scale{display:flex;align-items:center;gap:16px;margin-top:18px;width:1300px;font-size:18px;color:#64748B;font-weight:700}.scale i{flex:1;height:8px;border-radius:6px;background:linear-gradient(90deg,#0EA5E9,#D97706,#DC2626)}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;height:690px}.exm{margin-top:auto;padding:14px 16px;border-radius:12px;border:1.5px dashed;font-size:18px;color:#334155;line-height:1.5}.exm small{display:block;font-size:14px;font-weight:800;letter-spacing:2px}
.col{padding:30px 32px;display:flex;flex-direction:column;border-top:6px solid var(--c)}
.col h3{font-size:36px;font-weight:900;color:var(--c);margin-top:22px}.col .s{font-size:19px;color:#64748B;margin-top:6px}
.col ul{list-style:none;margin-top:22px;display:flex;flex-direction:column;gap:12px}.col li{display:flex;gap:12px;align-items:center;padding:15px 18px;border-radius:14px;background:var(--bg);font-size:22px;color:#1E293B;font-weight:600}
.foot2{position:absolute;right:0;bottom:0;font-size:17px;color:#94A3B8}"""
    exs = ['问：“这个项目决策链还缺谁？”——AI 直接回答', 'AI 起草一条互动记录，负责人一键确认入档', '对客户的承诺，必须由负责人本人做出']
    body = "<div class=stage><div class=cols>"
    for (c, icn, t, sub, items), ex in zip(cols, exs):
        c1, c2 = COL[c]
        body += (f"<div class='card col' style='--c:{c1};--bg:{c2}14'>{glass_obj(icn, c)}<h3>{t}</h3><div class=s>{sub}</div><ul>"
                 + ''.join(f"<li><i class=dia style='background:{c1}'></i>{x}</li>" for x in items) + f"</ul><div class=exm style='border-color:{c1}55'><small style='color:{c1}'>示例</small>{ex}</div></div>")
    body += "</div><div class=scale>放开<i></i>收紧</div><div class=foot2>所有 AI 参与的操作都记录“由哪个助手提出、谁确认”，全程可追溯</div></div>"
    return page(13, '人机分工：三档边界', '责任始终在人，AI 能做什么、不能做什么都有边界', body, css)

# ============ 14 组织怎么变 ============
@reg(14)
def p14():
    roles = [('user', '客户经理', None, '事后补录，凭记忆跟进', 'AI 预填记录，按晨报行动，专注见客户'),
             ('users', '区域指挥', None, '层层要表，靠汇报了解', '看信号、调资源，处理风险与缺口'),
             ('grid', '联合指挥', None, '听汇报，看滞后数据', '用驾驶舱开会，基于同一份事实定策略'),
             ('doc', '经营数据管家', '新增 · 兼职', '—', '负责本区域数据完整、口径一致'),
             ('book', '剧本负责人', '新增 · 业务专家兼任', '—', '审核 AI 提炼的经验与规则调整')]
    css = """.rows{display:flex;flex-direction:column;gap:16px}
.rr{display:grid;grid-template-columns:330px 1fr 60px 1.25fr;align-items:center;gap:14px}
.who{display:flex;gap:16px;align-items:center;padding:22px 18px}.who b{font-size:25px;color:#0B2458;font-weight:800;display:block}.who em{font-style:normal;font-size:14px;color:#B45309;background:#FEF3C7;border:1px solid #FCD34D;padding:2px 9px;border-radius:99px;font-weight:700}
.old{padding:30px 22px;border-radius:14px;background:#F1F5F9;border:1px solid #E2E8F0;color:#94A3B8;font-size:21px}
.nw{padding:28px 24px;border-radius:14px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;font-size:22px;font-weight:700;box-shadow:0 18px 30px -16px rgba(21,73,156,.7)}
.lbl{display:grid;grid-template-columns:330px 1fr 60px 1.25fr;gap:14px;font-size:17px;color:#94A3B8;font-weight:700;margin-bottom:8px;letter-spacing:2px}
.rh{margin-top:34px;display:flex;align-items:center;gap:22px}.rh h4{font-size:24px;color:#0B2458;font-weight:800;width:140px}
.blk{flex:1;display:flex;gap:16px;align-items:center;padding:28px 24px;border-radius:18px;background:linear-gradient(145deg,rgba(255,255,255,.95),var(--c2));border:1px solid #fff;box-shadow:0 18px 30px -16px var(--c1),inset 0 1px 0 #fff}
.blk b{font-size:24px;color:#0B2458;font-weight:800;display:block}.blk span{font-size:17px;color:#475569}"""
    body = "<div class=stage><div class=lbl><span>角色</span><span>过去</span><span></span><span>以后</span></div><div class=rows>"
    for icn, name, new, old, nw in roles:
        body += (f"<div class=rr><div class='card who'>{ic(icn, 'gold' if new else 'blue', 50)}<div><b>{name}</b>" + (f"<em>{new}</em>" if new else '') + "</div></div>"
                 f"<div class=old>{old}</div><div style='display:flex;justify-content:center'>{ic('arrow', 'blue', 40)}</div><div class=nw>{nw}</div></div>")
    body += "</div><div class=rh><h4>管理节奏</h4>"
    body += ''.join(f"<div class=blk style='--c1:{COL[c][0]}88;--c2:{COL[c][1]}33'>{ic(i, c, 50)}<div><b>{t}</b><span>{d}</span></div></div>" for c, i, t, d in
                    [('cyan', 'calendar', '每周 · 驾驶舱例会', '基于同一份事实开会'), ('blue', 'warn', '每月 · 风险复盘', '缺口与单点消解情况'), ('green', 'ruler', '每季 · 规则校准', '审核剧本与规则调整')])
    body += "</div></div>"
    return page(14, '组织怎么变：角色、节奏与新岗位', 'AI 原生首先是工作方式的改变，技术只是载体', body, css)

# ============ 15 四条底线 ============
@reg(15)
def p15():
    items = [('01', 'chip', '数据不出内网', 'AI 走公司内部通道与已有安全网关，客户数据不发往外部', False, ['内部通道', '安全网关', '不外发']),
             ('02', 'key', '权限不扩大', 'AI 只看到使用者本来能看的数据，所有调用留痕', False, ['权限继承', '调用留痕', '范围声明']),
             ('03', 'stamp', 'AI 不直接改数据', '一切写入须人确认，确认人即责任人，内容可追溯来源', False, ['待确认队列', '确认人负责', '原文出处']),
             ('04', 'scale', '评估不用于个人考核', '一旦挂钩考核，数据就会失真——需要以制度固定', True, ['不排名', '不考核', '制度固定'])]
    css = """.q{position:absolute;width:640px;height:340px;padding:30px 32px;display:flex;flex-direction:column}
.q .top{display:flex;align-items:center;gap:18px}.q .n{font-size:56px;font-weight:900;color:#DC2626;opacity:.9}
.q b{font-size:30px;color:#0B2458;font-weight:800;margin-top:18px}.q span{font-size:21px;color:#475569;margin-top:10px;line-height:1.55}
.q.hot{border:2px solid #F87171;box-shadow:0 24px 40px -18px rgba(220,38,38,.45)}.q .flag{position:absolute;right:20px;top:20px;background:#DC2626;color:#fff;font-size:15px;font-weight:700;padding:4px 12px;border-radius:99px}
.q .tg{margin-top:auto;display:flex;gap:10px}.q .tg em{font-style:normal;font-size:16px}
.shield{position:absolute;left:684px;top:120px;width:360px;height:440px}"""
    shield = """<svg class=shield viewBox="0 0 360 440"><defs><linearGradient id="sg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#BFD6FA"/></linearGradient>
<linearGradient id="se" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#15499C"/><stop offset="1" stop-color="#2F7BEA"/></linearGradient>
<pattern id="gp" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M16 0H0V16" fill="none" stroke="#9DBDEB" stroke-width=".6" opacity=".6"/></pattern></defs>
<path d="M180 20 L330 80 V210 C330 320 260 390 180 425 C100 390 30 320 30 210 V80 Z" fill="url(#sg)" stroke="url(#se)" stroke-width="6"/>
<path d="M180 40 L312 93 V210 C312 308 250 372 180 404 C110 372 48 308 48 210 V93 Z" fill="url(#gp)" opacity=".8"/>
<text x="180" y="215" text-anchor="middle" font-size="44" font-weight="900" fill="#0B2458">四条底线</text>
<text x="180" y="262" text-anchor="middle" font-size="20" fill="#475569">安全 · 可信 · 合规</text></svg>"""
    pos = [(0, 10), (1088, 10), (0, 410), (1088, 410)]
    body = "<div class=stage>" + shield
    body += "<svg style='position:absolute;left:0;top:0' width=1728 height=760 fill=none stroke='#93B4E6' stroke-width=1.6 stroke-dasharray='6 7'><path d='M640 170 L720 250'/><path d='M1088 170 L1010 250'/><path d='M640 570 L740 490'/><path d='M1088 570 L990 490'/></svg>"
    for (x, y), (n, i, t, d, hot, tags) in zip(pos, items):
        body += (f"<div class='card q{' hot' if hot else ''}' style='left:{x}px;top:{y}px'>" + ("<span class=flag>需制度化</span>" if hot else '')
                 + f"<div class=top><span class=n>{n}</span>{ic(i, 'red' if hot else 'blue', 54)}</div><b>{t}</b><span>{d}</span><div class=tg>"
                 + ''.join(f"<em class=pill style='color:{'#B91C1C' if hot else '#15499C'};border-color:{'#FCA5A5' if hot else '#C9DBF6'};background:{'#FEF2F2' if hot else '#F1F6FF'}'>{x}</em>" for x in tags) + "</div></div>")
    body += "</div>"
    return page(15, '安全与可信：四条底线', '数据安全、结果可信、使用合规，是 AI 进入客户经营的前提', body, css)

# ============ 16 三层指标 ============
@reg(16)
def p16():
    lv = [('cyan', 'click', '用起来', '一线愿不愿意用', ['每周活跃人数', '记录及时性', '建议采纳率'], '1–2 个月'),
          ('blue', 'shield', '管得住', '风险有没有减少', ['无人负责的关系', '单点风险', '逾期跟进'], '约 1 个季度'),
          ('green', 'trophy', '打得赢', '经营结果有没有改善', ['关键人覆盖', '预测与实际偏差', '赢单情况'], '2–3 个季度')]
    css = """.stairs{position:absolute;left:0;top:0;width:1020px;height:770px}
.step{position:absolute;width:320px;padding:22px 24px;display:flex;flex-direction:column;gap:8px}
.step b{font-size:32px;font-weight:900}.step small{font-size:17px;color:#64748B}.step li{list-style:none;display:flex;gap:10px;align-items:center;font-size:20px;color:#334155;padding:3px 0}
.step em{align-self:flex-start;margin-top:8px;font-style:normal;font-size:16px;font-weight:700;padding:4px 12px;border-radius:99px}
.block{position:absolute;width:320px;border-radius:18px;background:linear-gradient(170deg,rgba(255,255,255,.95),var(--c2));border:1px solid #fff;box-shadow:0 26px 40px -20px var(--c1),inset 0 2px 0 #fff}
.r{position:absolute;left:1070px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:16px}
.r .t{font-size:17px;color:#64748B;font-weight:700}
.ex{padding:20px 24px;display:flex;gap:16px;align-items:center}.ex b{display:block;font-size:24px;color:#0B2458;font-weight:800}.ex span{font-size:18px;color:#64748B}"""
    body = "<div class=stage><div class=stairs>"
    for k, (c, i, t, s, items, time) in enumerate(lv):
        c1, c2 = COL[c]
        x = k * 345; h = 150 + k * 110; top = 770 - h
        body += f"<div class=block style='left:{x}px;top:{top}px;height:{h}px;--c1:{c1}88;--c2:{c2}44'></div>"
        body += (f"<div class='card step' style='left:{x}px;bottom:{770 - top + 18}px;border-top:5px solid {c1}'><div style='display:flex;gap:14px;align-items:center'>{ic(i, c, 50)}<div><b style='color:{c1}'>{t}</b><br><small>{s}</small></div></div>"
                 + ''.join(f"<li><i class=dia style='background:{c1}'></i>{x_}</li>" for x_ in items)
                 + f"<em style='background:{c2}22;color:{c1};border:1px solid {c2}'>{line_icon('calendar', c1, 14)} {time}</em></div>")
    body += "<svg style='position:absolute;left:0;top:0' width=1020 height=770 fill=none><path d='M60 740 C 400 700, 700 420, 1000 250' stroke='#2F7BEA' stroke-width=3 stroke-dasharray='8 8'/><path d='M990 244 l14 4 -8 12' stroke='#2F7BEA' stroke-width=3/></svg></div>"
    body += (f"<div class=r><div class=t>成效在经营分析看板持续追踪</div>{shot('02-经营分析.png', (222, 282, 1098, 618), 658, 396, label='经营分析 · 01 核心经营总览')}"
             f"<div class='card ex'>{ic('chart', 'blue', 48)}<div><b>试点前后对比</b><span>并与非试点区域横向对照，不排个人名次</span></div></div>"
             f"<div class='card ex' style='border:1.5px solid #FCD34D'>{ic('target', 'gold', 48)}<div><b>先建基线，再定目标</b><span>试点第一个月建立基线，不拍脑袋定数字</span></div></div></div></div>")
    return page(16, '怎么衡量成效：三层指标', '先看用起来，再看管得住，最后看打得赢', body, css)

# ============ 17 推进路线 ============
@reg(17)
def p17():
    cols = [('gold', '第 0 步', '夯实底座', '第 1 个月', ['试点区域导入真实数据', '明确区域数据管家', '开始记录“建议—结果”'], '试点数据全部入库并经区域确认', 'M1', '试点区驾驶舱全部换成真实数据'),
            ('cyan', '第 1 步', '自动感知', '第 2–3 个月', ['会议纪要 / 邮件自动解析', '公开信息自动监测', '客户体检报告'], 'AI 识别结果多数无需修改', 'M3', '客户动态自动进档，补录明显减少'),
            ('orange', '第 2 步', '系统先开口', '第 4–6 个月', ['每日晨报', '作战参谋', '交接包'], '推送有人看、建议有人采纳', 'M6', '一线每天收晨报，重点项目有打法'),
            ('green', '第 3 步', '越用越准', '第 6 个月以后', ['复盘教练与剧本库', '规则校准（人审核）', '季度能力报告'], '预测与实际偏差持续缩小', 'M6+', '形成组织经营剧本与季度能力报告')]
    css = """.cols{display:grid;grid-template-columns:repeat(4,1fr);gap:34px;height:640px}
.c{padding:26px 26px 22px;display:flex;flex-direction:column;border-top:6px solid var(--c)}
.c small{font-size:17px;color:var(--c);font-weight:800;letter-spacing:2px}.c h3{font-size:36px;font-weight:900;color:#0B2458;margin-top:6px}.c .tm{font-size:18px;color:#64748B;margin-top:4px}
.c ul{list-style:none;margin-top:20px}.c li{display:flex;gap:10px;align-items:center;font-size:21px;color:#334155;padding:12px 0;border-bottom:1px dashed #DCE7F7}
.win2{margin-top:auto;margin-bottom:14px;padding:16px 18px;border-radius:14px;background:linear-gradient(145deg,#fff,var(--bg));border:1px solid #E2EBF8;font-size:20px;font-weight:700;color:#0B2458;line-height:1.45}.win2 small{display:flex;gap:6px;align-items:center;font-size:14px;color:var(--c);letter-spacing:2px;margin-bottom:6px}
.gate{padding:16px 18px;border-radius:14px;border:1.5px dashed var(--c);background:var(--bg)}.gate b{display:flex;gap:6px;align-items:center;font-size:16px;color:var(--c);font-weight:800}.gate span{display:block;font-size:19px;color:#1E293B;margin-top:6px;font-weight:600}
.rail{position:relative;margin-top:30px;height:44px;border-radius:24px;background:linear-gradient(90deg,#FDE68A,#BAE6FD,#FED7AA,#BBF7D0);box-shadow:inset 0 2px 0 #ffffffcc,0 18px 30px -16px rgba(21,73,156,.45);transform:perspective(900px) rotateX(28deg)}
.tick{position:absolute;top:50%;transform:translate(-50%,-50%);background:#fff;border:2px solid var(--c);color:var(--c);font-size:17px;font-weight:900;padding:4px 14px;border-radius:99px}
.arr{position:absolute;top:300px;width:36px;height:36px;margin-left:-18px;border-radius:50%;background:#fff;border:1px solid #DDE8F8;display:flex;align-items:center;justify-content:center;z-index:3;box-shadow:0 8px 16px -8px rgba(21,73,156,.4)}"""
    body = "<div class=stage><div class=cols>"
    for c, st, nm, tm, items, gate, _, win in cols:
        c1, c2 = COL[c]
        body += (f"<div class='card c' style='--c:{c1};--bg:{c2}12'><small>{st}</small><h3>{nm}</h3><div class=tm>{tm}</div><ul>"
                 + ''.join(f"<li><i class=dia style='background:{c1}'></i>{x}</li>" for x in items)
                 + f"</ul><div class=win2><small>{line_icon('eye', c1, 15)} 可见成果</small>{win}</div><div class=gate><b>{line_icon('flag', c1, 16)}进入下一步的门槛</b><span>{gate}</span></div></div>")
    body += "</div>" + ''.join(f"<div class=arr style='left:{(i + 1) * 432.0 - 17:.0f}px'>{line_icon('arrow', '#2F7BEA', 18)}</div>" for i in range(3))
    body += "<div class=rail>" + ''.join(f"<span class=tick style='left:{12.5 + i * 25}%;--c:{COL[c][0]}'>{m}</span>" for i, (c, *_, m, _w) in enumerate(cols)) + "</div></div>"
    return page(17, '推进路线：四步走，每步设门槛', '过了门槛才进入下一步 · 时间为建议值', body, css)

# ============ 18 风险与应对 ============
@reg(18)
def p18():
    rows = [('数据导不全、更新不及时', '第 0 步设门槛；数据管家负责到人；AI 自动汇聚降低补录'), ('一线抵触，觉得增加负担', '先上线“减负”能力；推送克制；不与考核挂钩'),
            ('AI 说错、编造', '只引用已有记录，证据不足明说；人确认后生效；监控修改比例'), ('客户数据安全', '内网通道、权限继承、全程留痕'),
            ('评分变成考核工具，数据失真', '以制度明确“评估不用于个人考核”'), ('期望过高', '分步验收；学习效果预期两到三个季度以上')]
    css = """.rows{display:flex;flex-direction:column;gap:18px;width:1500px}
.rr{display:grid;grid-template-columns:560px 60px 1fr;align-items:center;gap:14px}
.risk{display:flex;gap:16px;align-items:center;padding:26px 20px;border-radius:16px;background:linear-gradient(90deg,#FEF2F2,#FFF7F7);border:1px solid #FBCACA;font-size:23px;font-weight:800;color:#991B1B}
.fix{display:flex;gap:16px;align-items:center;padding:26px 22px;font-size:21px;color:#1E293B;font-weight:600}
.bgshield{position:absolute;right:-30px;top:170px;opacity:.9}"""
    body = """<div class=stage><svg class=bgshield width=300 height=380 viewBox="0 0 360 440"><defs><linearGradient id="bs" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#BBF7D0"/></linearGradient></defs>
<path d="M180 20 L330 80 V210 C330 320 260 390 180 425 C100 390 30 320 30 210 V80 Z" fill="url(#bs)" stroke="#86EFAC" stroke-width="5"/><path d="m120 220 45 45 80-95" stroke="#16A34A" stroke-width="16" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg><div class=rows>"""
    for r, f in rows:
        body += f"<div class=rr><div class=risk>{ic('warn', 'red', 46)}{r}</div><div style='display:flex;justify-content:center'>{ic('arrow', 'blue', 40)}</div><div class='card fix'>{ic('check', 'green', 46)}{f}</div></div>"
    body += "</div></div>"
    return page(18, '风险与应对', '主要风险在数据和人，不在技术', body, css)

# ============ 19 拍板事项 ============
@reg(19)
def p19():
    items = [('01', 'pin', '试点范围', '首批试点区域与团队；各区域数据导入责任人与完成时间', None),
             ('02', 'scale', '考核红线', '以制度明确：关系评估只用于经营辅助，不用于个人考核', '制度'),
             ('03', 'chip', 'AI 使用边界', 'AI 走公司内部通道，客户数据不出内网', None),
             ('04', 'chat', '推送渠道', '统一使用企业微信还是钉钉', None),
             ('05', 'share', '经验共享授权', '去除个人信息后跨区域汇总；明确谁可看季度能力报告', '制度'),
             ('06', 'users', '人员与流程', '设立区域数据管家与剧本负责人；交接包确认纳入调动流程', '制度')]
    css = """.g{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:22px;height:640px}
.d{padding:26px 28px;display:flex;flex-direction:column}.d .top{display:flex;align-items:center;justify-content:space-between}.d .n{font-size:54px;font-weight:900}
.d b{font-size:30px;color:#0B2458;font-weight:800;margin-top:14px}.d span{font-size:20px;color:#475569;margin-top:10px;line-height:1.55}
.d .bx{position:absolute;right:24px;bottom:24px;width:34px;height:34px;border-radius:9px;border:2.5px solid #F59E0B;background:#FFFBEB}
.d.sys{border:1.5px solid #FCA5A5}.d .tag{position:absolute;left:120px;top:40px;font-size:14px;font-weight:800;color:#fff;background:#DC2626;padding:3px 10px;border-radius:99px}
.ban{margin-top:22px;padding:20px 28px;border-radius:18px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;font-size:24px;font-weight:700;display:flex;align-items:center;gap:16px;box-shadow:0 22px 36px -18px rgba(21,73,156,.8)}
.ban em{font-style:normal;margin-left:auto;font-size:18px;opacity:.85}"""
    body = "<div class=stage><div class=g>"
    for n, i, t, d, tag in items:
        body += (f"<div class='card d{' sys' if tag else ''}'>" + (f"<span class=tag>{tag}</span>" if tag else '')
                 + f"<div class=top><span class='n grad'>{n}</span>{ic(i, 'red' if tag else 'blue', 56)}</div><b>{t}</b><span>{d}</span><i class=bx></i></div>")
    body += f"</div><div class=ban>{ic('users', 'cyan', 46)}建议投入：核心小组 4–5 人（产品 1、研发 2–3、业务专家 1 兼职）+ 各试点区域数据管家（兼职）<em>标“制度”的三项需组织决定</em></div></div>"
    return page(19, '需要领导拍板的六件事', '这些事由组织决定，系统替代不了', body, css)

# ============ 20 结束页 ============
@reg(20)
def p20():
    css = """.t{position:absolute;left:0;right:0;top:230px;text-align:center;z-index:2}
.t h0{display:block;font-size:76px;font-weight:900;color:#0B2458;letter-spacing:4px;line-height:1.35}
.t p{font-size:26px;color:#64748B;margin-top:26px;letter-spacing:2px}
.track{position:absolute;left:260px;top:690px;width:1400px;height:40px;border-radius:24px;background:linear-gradient(90deg,#BFD6FA,#FED7AA,#BBF7D0);transform:perspective(900px) rotateX(30deg) rotateZ(-4deg);box-shadow:inset 0 2px 0 #ffffffcc,0 20px 40px -18px rgba(21,73,156,.5);z-index:1}
.ball{position:absolute;border-radius:50%;z-index:2;box-shadow:0 20px 30px -12px var(--c),inset 0 3px 0 #fff}
.lb{position:absolute;transform:translateX(-50%);font-size:24px;font-weight:800;z-index:2}
.bye{position:absolute;left:0;right:0;bottom:120px;text-align:center;font-size:40px;font-weight:900;letter-spacing:22px;color:#15499C;z-index:2}"""
    balls = [(470, 700, 40, '#15499C', '#BFD6FA', '看清经营'), (960, 666, 54, '#F97316', '#FED7AA', '指挥作战'), (1450, 626, 70, '#16A34A', '#BBF7D0', '越用越聪明')]
    body = ("<div class=t><h0>从看清经营，到指挥作战，<br>再到<span class=grad>越用越聪明</span>。</h0><p>底座已建成 · 架构已清晰 · 请定试点、边界与机制</p></div><div class=track></div>"
            + ''.join(f"<div class=ball style='left:{x - r}px;top:{y - r}px;width:{2 * r}px;height:{2 * r}px;--c:{c};background:radial-gradient(circle at 35% 30%,#fff,{c2} 55%,{c})'></div>"
                      f"<div class=lb style='left:{x}px;top:{y + r + 14}px;color:{c}'>{t}</div>" for x, y, r, c, c2, t in balls)
            + "<div class=bye>谢谢</div>" + glass_cube(200, 300, 60, 16) + glass_cube(1680, 360, 76, -14) + glass_cube(1560, 820, 46, 22))
    return page(20, '', '', body, css, header=False)

# ============ 21 常见追问 ============
@reg(21)
def p21():
    qa = [('和外面买一个 CRM 有什么区别？', '通用 CRM 管销售漏斗；我们管轨交“五类单位 × 项目全周期”决策链，行业模型与剧本是自有资产'),
          ('为什么不直接接一个大模型问答？', '问答框解决不了信息汇聚，也不会主动服务；价值在感知、行动、学习三个闭环'),
          ('AI 判断错了谁负责？', '确认人负责；AI 只起草，写入与对外动作都要人确认，全程可追溯'),
          ('数据不全能用吗？', '能用，明确标“资料不足”，不把缺资料当关系差，并提示该补什么'),
          ('会不会变成监控员工的工具？', '只记业务信息；评估不用于考核；管理者看风险与缺口，不看个人排名'),
          ('投入多大？什么时候见效？', '核心小组 4–5 人，复用平台智能体框架与安全网关；减负两三个月可见，学习需两到三个季度'),
          ('人员离职带走关系怎么办？', '过程留痕 + 交接包 + 单点风险提醒，提前安排第二对接人'),
          ('公开信息采集合规吗？', '只采公开的招标、中标、任免信息，记录来源与时间，范围频率报批后执行')]
    css = """.g{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(4,1fr);gap:18px;height:790px}
.q{display:flex;gap:20px;align-items:center;padding:18px 24px}.q .qq{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff;font-size:28px;font-weight:900;display:flex;align-items:center;justify-content:center;flex:none;box-shadow:0 10px 20px -8px #15499C99}
.q b{display:block;font-size:24px;color:#0B2458;font-weight:800}.q span{display:block;font-size:18px;color:#64748B;margin-top:6px;line-height:1.5}"""
    body = "<div class=stage><div class=g>" + ''.join(f"<div class='card q'><div class=qq>Q</div><div><b>{q}</b><span>{a}</span></div></div>" for q, a in qa) + "</div></div>"
    return page(21, '备用 1｜常见追问', '被追问时调出', body, css)

# ============ 22 功能清单 ============
@reg(22)
def p22():
    mods = [('cyan', 'gauge', '驾驶舱', ['总体信息', '经营分析', '五位一体', '商机管理', '项目作战地图'], '一屏看经营全局，四大板块统一风格', '联合指挥 · 区域指挥'),
            ('orange', 'calendar', '工作台', ['优先待办', '督办队列', '四板块概览', '进入驾驶舱'], '每天先做哪几件事，管理者直接督办', '客户经理 · 管理者'),
            ('gold', 'users', '客户与组织', ['客户档案', '联系人档案', '客户组织架构', '快速建档', 'Excel 导入', '资料补充'], '一个客户一份档案，组织层级清晰', '客户经理 · 数据管家'),
            ('blue', 'network', '关系', ['关系评估', '关系维系', '指派', '转移', '协办', '交接'], '关系强弱可评估，责任可指派可交接', '客户经理 · 区域指挥'),
            ('green', 'flag', '商机', ['商机清单', '六阶段推进', '材料与关系人', '成交结果', '导入导出'], '投资与份额分开，阶段推进有依据', '客户经理 · 联合指挥'),
            ('red', 'shield', '治理', ['分级权限', '操作留痕', '评分规则配置', '区域配置', '使用说明'], '谁能看、能改什么、做过什么都可查', '管理员')]
    css = """.g{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:24px;height:790px}
.m{padding:28px 30px;border-top:6px solid var(--c);display:flex;flex-direction:column}.m .ds{font-size:18px;color:#64748B;margin-top:4px}.m .who{margin-top:auto;padding-top:14px;border-top:1px dashed #DCE7F7;display:flex;gap:8px;align-items:center;font-size:18px;color:#475569}.m .h{display:flex;gap:16px;align-items:center}.m .h b{font-size:32px;font-weight:900;color:var(--c)}
.m .ps{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}.m .ps span{font-size:20px;padding:9px 16px;border-radius:99px;border:1px solid var(--c2);background:var(--bg);color:#1E293B;font-weight:600}"""
    body = "<div class=stage><div class=g>"
    for c, i, t, ps, d, who in mods:
        c1, c2 = COL[c]
        body += (f"<div class='card m' style='--c:{c1};--c2:{c2}88;--bg:{c2}12'><div class=h>{ic(i, c, 58)}<div><b>{t}</b><div class=ds>{d}</div></div></div><div class=ps>" + ''.join(f"<span>{p}</span>" for p in ps)
                 + f"</div><div class=who>{line_icon('users', c1, 18)}主要使用者：{who}</div></div>")
    body += "</div></div>"
    return page(22, '备用 2｜现有功能清单', '第一阶段已建成的能力一览', body, css)

# ============ 23 界面截图 ============
@reg(23)
def p23():
    shots = [('五位一体', '03-五位一体.png'), ('商机管理', '04-商机管理.png'), ('作战情报卡', '06-作战情报卡.png'), ('日常工作台', '07-日常工作台.png')]
    css = """.wall{position:absolute;left:40px;right:40px;top:0;bottom:6px;padding:22px 40px;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:14px 40px;justify-items:center;align-items:center}
.it{display:flex;flex-direction:column;align-items:center;gap:10px}.it b{font-size:22px;color:#0B2458;font-weight:800;display:flex;gap:10px;align-items:center}.it b i{width:10px;height:10px;border-radius:50%;background:#2F7BEA}"""
    body = "<div class=stage><div class='wall glass'>" + ''.join(f"<div class=it>{shot(f, (0, 0, 1920, 1080), 540, 330)}<b><i></i>{t}</b></div>" for t, f in shots) + "</div></div>"
    body += "<div style='position:absolute;right:160px;bottom:80px;font-size:15px;color:#94A3B8;z-index:3'>界面示意 · 样例数据</div>"
    return page(23, '备用 3｜界面截图', '界面示意 · 样例数据', body, css)

# ============ 24 名词解释 ============
@reg(24)
def p24():
    terms = [('gold', 'pentagon', '五位一体', '主管、业主、总包、设计、厂商（运营）五类客户单位的协同经营体系'),
             ('blue', 'link', '决策链缺口', '项目某个关键环节，我方没有能说上话的人'),
             ('red', 'user', '单点风险', '某位关键客户只有一名我方人员在对接'),
             ('cyan', 'chip', '数字助手', '承担特定分工的 AI 能力，只提建议，由人确认')]
    css = """.list{display:flex;flex-direction:column;gap:22px;height:780px}
.tm{flex:1;display:flex;align-items:center;gap:30px;padding:0 36px;border-left:8px solid var(--c);overflow:hidden}
.tm b{font-size:36px;font-weight:900;color:var(--c);width:260px}.tm .d{font-size:26px;color:#1E293B;flex:1}
.tm .wm{opacity:.9}"""
    body = "<div class=stage><div class=list>"
    for c, i, t, d in terms:
        body += f"<div class='card tm' style='--c:{COL[c][0]}'>{ic(i, c, 64)}<b>{t}</b><span class=d>{d}</span><span class=wm style='flex:none'>{line_icon(i, COL[c][1] + '55', 110, 1.2)}</span></div>"
    body += "</div></div>"
    return page(24, '备用 4｜名词解释', '汇报中出现的关键术语', body, css)

def render(nums):
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=['--no-sandbox']); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        for n in nums:
            html = PAGES[n]()
            pg.set_content(html); pg.wait_for_timeout(250)
            name = OUT / f"{n:02d}.png"
            pg.screenshot(path=str(name)); print('saved', name.name)
        b.close()

if __name__ == '__main__':
    nums = [int(a) for a in sys.argv[1:]] or sorted(PAGES)
    render(nums)
