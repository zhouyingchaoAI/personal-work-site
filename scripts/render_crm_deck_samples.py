import base64
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path('/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1790580673737_ovovj4')
SHOTS = Path('/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1790563946904_0r05yt')
img = lambda f: 'data:image/png;base64,' + base64.b64encode((SHOTS / f).read_bytes()).decode()
ICON = {  # 白色线性图标（24 视框）
 'doc':'<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M10 12h5M10 16h5"/>','ruler':'<path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2m1-5 2 2m1-5 2 2"/>',
 'gauge':'<path d="M4 16a8 8 0 1 1 16 0"/><path d="m12 16 4-5"/><circle cx="12" cy="16" r="1.4"/>','shield':'<path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z"/><path d="m9 12 2 2 4-4"/>',
 'scan':'<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M8 12h8"/>',
 'radar':'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12 18 6"/>','chart':'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
 'flag':'<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>','bell':'<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>','loop':'<path d="M20 12a8 8 0 1 1-3-6.2"/><path d="M20 4v5h-5"/>',
 'plug':'<path d="M9 3v5M15 3v5M7 8h10v4a5 5 0 0 1-10 0z"/><path d="M12 17v4"/>','user':'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
 'lock':'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>'}
def ic(name, c1='#1D5CAB', c2='#2F7BEA', size=52):
    return (f"<span class=ib style='width:{size}px;height:{size}px;background:linear-gradient(135deg,{c1},{c2})'>"
            f"<svg viewBox='0 0 24 24' width='{size*0.5}' height='{size*0.5}' fill='none' stroke='#fff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>{ICON[name]}</svg></span>")
BASE = """<meta charset=utf-8><style>*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;position:relative;overflow:hidden;font-family:'Droid Sans Fallback',sans-serif;color:#1E293B;background:linear-gradient(155deg,#FFFFFF 0%,#F5F9FF 50%,#EEF4FF 100%)}
.blob{position:absolute;border-radius:50%;filter:blur(60px)}
.wave{position:absolute;right:-40px;bottom:-40px;width:900px;height:420px;opacity:.55}
.dots{position:absolute;left:30px;top:200px;width:260px;height:200px;background-image:radial-gradient(#15499C30 1.5px,transparent 1.5px);background-size:18px 18px}
.ribbon{position:absolute;right:-260px;top:-300px;width:760px;height:520px;border-radius:50%;background:linear-gradient(130deg,#15499C,#2F7BEA 60%,#7FB2FF);transform:rotate(-18deg);box-shadow:0 30px 80px rgba(47,123,234,.25)}
.ribbon2{position:absolute;right:-170px;top:-330px;width:700px;height:500px;border-radius:50%;border:1.5px solid #A9C6F2;transform:rotate(-10deg)}
.hd{position:absolute;left:96px;top:56px;display:flex;gap:24px;align-items:flex-start}
.no{width:72px;height:72px;border-radius:18px;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff;font-size:32px;font-weight:800;display:flex;align-items:center;justify-content:center;box-shadow:0 12px 26px rgba(21,73,156,.3);margin-top:6px}
.eb{font-size:16px;letter-spacing:5px;color:#2F7BEA;font-weight:700} h1{font-size:50px;color:#0B2458;letter-spacing:1px;line-height:1.2;font-weight:800}
.sub{font-size:22px;color:#64748B;margin-top:4px}
.rule{position:absolute;left:96px;top:196px;width:1728px;height:2px;background:linear-gradient(90deg,#15499C,#2F7BEA55 40%,transparent)}
.part{position:absolute;right:340px;top:70px;padding:7px 18px;border-radius:99px;background:#EAF2FF;color:#15499C;font-size:17px;border:1px solid #D3E3FB;font-weight:600}
.card{background:linear-gradient(180deg,#FFFFFF,#FBFDFF);border:1px solid #DDE8F8;border-radius:18px;box-shadow:0 18px 40px -18px rgba(21,73,156,.28),0 2px 6px rgba(21,73,156,.05)}
.ib{display:inline-flex;align-items:center;justify-content:center;border-radius:14px;flex:none;box-shadow:0 8px 18px -6px rgba(21,73,156,.45)}
.ft{position:absolute;left:96px;right:96px;bottom:24px;display:flex;justify-content:space-between;color:#94A3B8;font-size:16px}
.bar{position:absolute;left:0;right:0;bottom:0;height:5px;background:#E2EBF8}.bar i{display:block;height:100%;background:linear-gradient(90deg,#15499C,#2F7BEA)}
.glass{background:linear-gradient(145deg,rgba(255,255,255,.75),rgba(214,230,255,.55));border:1px solid rgba(255,255,255,.9);box-shadow:inset 0 1px 0 #fff,0 24px 50px -20px rgba(21,73,156,.35);backdrop-filter:blur(6px)}
</style>
<div class=blob style="left:-160px;top:-120px;width:620px;height:420px;background:#DCEAFF"></div>
<div class=blob style="left:780px;top:560px;width:720px;height:420px;background:#E6F0FF"></div>
<svg class=wave viewBox="0 0 900 420" fill="none" stroke="#9DBDEB" stroke-width="1">""" + ''.join(f'<path d="M0 {300+i*9} C 220 {200+i*12}, 480 {420-i*6}, 900 {170+i*11}"/>' for i in range(12)) + """</svg>
<div class=dots></div><div class=ribbon></div><div class=ribbon2></div>"""
def head(n, en, title, sub, part, pct):
    return (f"<div class=hd><div class=no>{n}</div><div><div class=eb>{en}</div><h1>{title}</h1><div class=sub>{sub}</div></div></div>"
            f"<div class=rule></div><div class=part>{part}</div>"
            f"<div class=ft><span>联指经营助手 · AI 原生客户经营</span><span>{n} / 24</span></div><div class=bar><i style='width:{pct}%'></i></div>")

# ---- 第 06 页 ----
C = dict(s=('#0EA5E9', '#38BDF8'), j=('#15499C', '#2F7BEA'), a=('#F97316', '#FDBA74'), l=('#16A34A', '#4ADE80'))
def loop(k, name, sub, agents, outs=()):
    c1, c2 = C[k]
    ags = ''.join(f"<div class=ag>{ic(i, c1, c2, 46)}<div><b style='color:{c1}'>{a}</b><span>{d}</span></div></div><ul class=pts>" + ''.join(f"<li><i style='background:{c1}'></i>{t}</li>" for t in pts) + "</ul>" for i, a, d, pts in agents)
    chips = ''.join(f"<em style='color:{c1};border-color:{c1}55;background:{c1}0d'>{o}</em>" for o in outs)
    return f"<div class='card loop' style='border-top:5px solid {c1}'><div class=lh><b style='color:{c1}'>{name}</b><small>{sub}</small></div>{ags}<div class=out><span>产出</span>{chips}</div></div>"
p06 = BASE + head('06', 'AI-NATIVE ARCHITECTURE', 'AI 原生架构总图', '一个底座 · 四个闭环 · 六个数字助手 · 四条底线', 'PART 02 · AI 原生架构', 25) + """
<style>.main{position:absolute;left:96px;right:96px;top:222px;bottom:62px;display:flex;flex-direction:column;gap:14px}
.entry{display:flex;gap:14px;align-items:center;padding:12px 16px}.entry>span{font-size:18px;color:#64748B;width:110px;font-weight:600}.entry em{flex:1;font-style:normal;text-align:center;padding:11px;border-radius:99px;background:#F1F6FF;border:1px solid #D9E6FA;color:#15499C;font-size:21px;font-weight:600}
.loops{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;flex:1;position:relative}
.loops:after{content:'';position:absolute;left:12%;right:12%;top:46px;height:2px;background:repeating-linear-gradient(90deg,#2F7BEA 0 10px,transparent 10px 18px);z-index:0;opacity:.5}
.loop{padding:18px 18px 16px;position:relative;z-index:1;display:flex;flex-direction:column}.pts{list-style:none;margin:10px 4px 2px 8px}.pts li{display:flex;gap:10px;align-items:center;font-size:18px;color:#334155;padding:5px 0}.pts li i{width:7px;height:7px;transform:rotate(45deg);flex:none}.out{margin-top:auto;padding-top:14px;border-top:1px dashed #D9E6FA;display:flex;flex-wrap:wrap;gap:8px;align-items:center}.out span{font-size:15px;color:#94A3B8;margin-right:2px}.out em{font-style:normal;font-size:16px;padding:5px 12px;border-radius:99px;border:1px solid;font-weight:600}.lh b{font-size:29px;font-weight:800}.lh small{font-size:18px;color:#64748B;margin-left:10px}
.ag{display:flex;gap:14px;align-items:center;margin-top:14px;padding:14px;border-radius:14px;background:#F7FAFF;border:1px solid #E5EEFB}.ag b{font-size:23px;display:block}.ag span{font-size:17px;color:#64748B}
.platform{position:relative;padding:16px 22px 22px;border-radius:22px;transform:perspective(1400px) rotateX(14deg);transform-origin:top}
.platform:after{content:'';position:absolute;left:14px;right:14px;bottom:-12px;height:12px;border-radius:0 0 18px 18px;background:linear-gradient(180deg,#BBD3F5,#E3EEFD)}
.platform .t{font-size:23px;font-weight:800;background:linear-gradient(90deg,#B45309,#D97706);-webkit-background-clip:text;color:transparent;margin-bottom:10px}
.bricks{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.bricks div{text-align:center;padding:14px 0;border-radius:12px;background:linear-gradient(180deg,#FFFBF2,#FDEFD3);border:1px solid #F3D59C;color:#92400E;font-size:21px;font-weight:600;box-shadow:0 6px 0 #F1D7A6}
.beams{position:absolute;left:0;right:0;top:-14px;display:grid;grid-template-columns:repeat(4,1fr);pointer-events:none}.beams i{justify-self:center;width:60px;height:26px;background:linear-gradient(0deg,#9CC2FF88,transparent);filter:blur(2px)}
.guard{display:grid;grid-template-columns:120px repeat(4,1fr);gap:12px;align-items:center;padding:10px 16px;background:linear-gradient(90deg,#FFF5F5,#FFFFFF)}.guard>span{color:#DC2626;font-size:19px;font-weight:800}
.guard div{display:flex;gap:10px;align-items:center;justify-content:center;padding:10px;border-radius:12px;border:1px solid #FBCACA;background:#fff;color:#991B1B;font-size:20px;font-weight:600}
</style><div class=main>
<div class="card entry"><span>使用入口</span><em>驾驶舱 · 工作台</em><em>页面侧边助手</em><em>企微 / 钉钉推送</em><em>会议 / 邮件 / 文档接入</em></div>
<div class=loops>""" + loop('s', '感知闭环', '自动汇聚', [('scan', '资料解析员', '会议 · 邮件 · 合同', ['识别客户、人物与承诺', '自动关联已有档案']), ('radar', '外部情报员', '招标 · 中标 · 任免', ['公告匹配在谈商机', '任免更新联系人'])], ['待确认记录', '商机信号', '职务变动']) + loop('j', '研判闭环', '会解读', [('chart', '分析师', '体检 · 解读 · 风险', ['客户体检：现状、风险、机会', '经营解读：差在哪、为什么', '把握度说明：缺材料、缺人', '每条结论附证据出处'])], ['体检报告', '把握度说明', '风险清单']) + loop('a', '行动闭环', '先开口', [('flag', '作战参谋', '打谁 · 谁去 · 第一步', ['找引荐路径与候选人', '生成话术与材料清单']), ('bell', '督办助理', '晨报 · 催办 · 交接', ['每天推送最重要的几件事', '逾期与单点风险催办'])], ['每日晨报', '作战方案', '交接包']) + loop('l', '学习闭环', '越用越准', [('loop', '复盘教练', '什么有效 → 更新剧本', ['追踪建议—采纳—结果', '提炼有效打法入剧本', '提出规则校准（人审核）', '季度组织能力报告'])], ['经营剧本', '规则校准', '能力报告']) + """</div>
<div class="glass platform"><div class=beams><i></i><i></i><i></i><i></i></div><div class=t>经营知识底座 · 组织记忆</div><div class=bricks><div>客户与组织</div><div>人与关系</div><div>互动与情报</div><div>商机与项目</div><div>经营结果</div><div>剧本与规则</div></div></div>
<div class="card guard"><span>四条底线</span>""" + ''.join(f"<div><svg viewBox='0 0 24 24' width=20 height=20 fill=none stroke='#DC2626' stroke-width=2>{ICON['shield']}</svg>{t}</div>" for t in ['数据不出内网', '权限不扩大', 'AI 不直接改数据', '评估不用于考核']) + "</div></div>"

# ---- 第 04 页（截图已贴入） ----
shots = [('总体信息', '#0EA5E9', '01-总体信息.png'), ('经营分析', '#15499C', '02-经营分析.png'), ('五位一体', '#D97706', '03-五位一体.png'), ('项目作战地图', '#F97316', '05-项目作战地图.png')]
p04 = BASE + head('04', 'WHY IT MATTERS', '第一阶段成果：底座已经建成', '先建账本、口径、权限和驾驶舱，AI 才有东西可用', 'PART 01 · 为什么做', 17) + """
<style>.l{position:absolute;left:96px;top:236px;width:1030px;height:760px;border-radius:26px;padding:26px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:26px 24px}.sh .lab{display:inline-flex;gap:8px;align-items:center;font-size:18px;font-weight:700;color:#0B2458;margin-bottom:8px}.sh .lab i{width:10px;height:10px;border-radius:50%}
.win{border-radius:14px;overflow:hidden;background:#fff;border:1px solid #D6E3F7;box-shadow:0 20px 40px -18px rgba(21,73,156,.4)}.win .tb{height:26px;background:#EEF3FB;display:flex;gap:6px;align-items:center;padding-left:10px}.win .tb i{width:8px;height:8px;border-radius:50%;background:#C5D3E8}
.win img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;object-position:top}
.r{position:absolute;left:1166px;right:96px;top:236px;display:flex;flex-direction:column;gap:16px}
.rc{display:flex;gap:18px;align-items:center;padding:20px 22px}.rc b{display:block;font-size:26px;color:#0B2458;font-weight:800}.rc span{font-size:19px;color:#64748B}
.note{margin-top:4px;padding:18px 22px;border-radius:16px;background:linear-gradient(90deg,#FFF8EB,#FFFFFF);border:1px solid #F3D59C;color:#92400E;font-size:21px;font-weight:700;display:flex;gap:12px;align-items:center}
</style><div class="l glass"><div class=grid>""" + ''.join(f"<div class=sh><div class=lab><i style='background:{c}'></i>{t}</div><div class=win><div class=tb><i></i><i></i><i></i></div><img src='{img(f)}'></div></div>" for t, c, f in shots) + """</div></div>
<div class=r>""" + ''.join(f"<div class='card rc'>{ic(i)}<div><b>{t}</b><span>{d}</span></div></div>" for i, t, d in [('doc', '统一档案', '一个客户一份档案'), ('ruler', '统一口径', '投资与份额分开统计'), ('gauge', '一张驾驶舱', '四大作战板块 + 工作台'), ('shield', '权限与留痕', '分级查看，全程留痕')]) + """
<div class=note>""" + ic('lock', '#B45309', '#F59E0B', 40) + """现状：能记能算，还不会想</div></div>"""

with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--no-sandbox']); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    for name, html in [('蓝白风格样张-06-AI原生架构总图.png', p06), ('蓝白风格样张-04-截图已贴入.png', p04)]:
        pg.set_content(html); pg.wait_for_timeout(300); pg.screenshot(path=str(OUT / name)); print(name)
    b.close()
