"""联指经营助手 · 三阶段 12 页汇报 PPT 渲染（复用 deck.py 的蓝白视觉组件）。
用法：python3 deck12.py [页码 ...]"""
import sys
from pathlib import Path
from PIL import Image
import deck as D
from deck import ic, line_icon, glass_cube, COL

D.OUT = Path('/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1790648398002_t6o3ty')
D.SHOTS = D.OUT / '截图素材'
D.TOTAL = 12
D.PARTS = {2: ('总览 · 三步走', 'THREE-PHASE ROADMAP'),
           **{i: ('第一阶段 · 管理侧', 'PHASE 01 · DIGITAL COMMAND') for i in (3, 4, 5)},
           **{i: ('第二阶段 · 执行侧', 'PHASE 02 · EXECUTION') for i in (6, 7)},
           **{i: ('第三阶段 · 组织侧', 'PHASE 03 · AI-NATIVE BRAIN') for i in (8, 9, 10)},
           **{i: ('推进与决策', 'ROADMAP & DECISIONS') for i in (11, 12)}}
PAGES = {}
def reg(n):
    def f(fn):
        PAGES[n] = fn; return fn
    return f

def shot(file, crop, w, h, label='', bar=True):
    iw, ih = Image.open(D.SHOTS / file).size
    x, y, cw, ch = crop
    bh = 26 if bar else 0
    s = w / cw
    img = (f"<div style='height:{h - bh}px;background:url({D.data_url(file)}) no-repeat;background-size:{iw * s:.1f}px {ih * s:.1f}px;"
           f"background-position:{-x * s:.1f}px {-y * s:.1f}px'></div>")
    tb = f"<div class=tb><i></i><i></i><i></i><span>{label}</span></div>" if bar else ''
    return f"<div class=win style='width:{w}px;height:{h}px'>{tb}{img}</div>"

PH = {1: ('cyan', '#0EA5E9'), 2: ('orange', '#F97316'), 3: ('green', '#16A34A')}
def tag(t, c='#15499C', bg=None):
    return f"<span class=pill style='color:{c};border-color:{c}55;background:{bg or '#fff'}'>{t}</span>"

COMMON = """.stage{top:222px}
.sec{font-size:15px;letter-spacing:3px;color:#2F7BEA;font-weight:800;margin-bottom:10px;display:flex;gap:8px;align-items:center}
.li{list-style:none}.li li{display:flex;gap:10px;align-items:flex-start;font-size:19px;color:#1E293B;line-height:1.5;padding:5px 0}.li li i{margin-top:9px}
.li li b{color:#0B2458}
.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:18px}.tbl th{text-align:left;font-size:15px;color:#64748B;font-weight:700;padding:8px 12px;border-bottom:1.5px solid #D6E3F7}
.tbl td{padding:10px 12px;border-bottom:1px dashed #E2EBF8;color:#1E293B;vertical-align:top;line-height:1.45}.tbl tr:last-child td{border-bottom:0}
.st{display:inline-block;font-size:14px;font-weight:800;padding:3px 10px;border-radius:99px;white-space:nowrap}
.st.ok{color:#15803D;background:#DCFCE7}.st.mid{color:#B45309;background:#FEF3C7}.st.todo{color:#64748B;background:#F1F5F9;border:1px dashed #CBD5E1}
.foot-note{position:absolute;left:0;right:0;bottom:0;padding:14px 22px;border-radius:14px;background:linear-gradient(90deg,#EEF4FF,#F8FBFF);border:1px solid #D6E3F7;font-size:19px;color:#0B2458;font-weight:700;display:flex;gap:12px;align-items:center}
.cap2{font-size:14px;color:#94A3B8;margin-top:6px;text-align:right}
"""

# ============ 01 封面 ============
@reg(1)
def p01():
    phases = [('管理侧 · 战略牵引', 'cyan'), ('执行侧 · 效率体验', 'orange'), ('组织侧 · 自我进化', 'green')]
    chips = ''.join(f"<span class=pill style='color:{COL[c][0]};border-color:{COL[c][0]}66;background:#fff;font-size:20px;padding:8px 18px'>{t}</span>" + ("<i class=dash></i>" if i < 2 else '') for i, (t, c) in enumerate(phases))
    css = COMMON + """.l{position:absolute;left:150px;top:230px;width:800px;z-index:2}
.l .eb2{font-size:17px;letter-spacing:5px;color:#2F7BEA;font-weight:700}
.l h0{display:block;font-size:108px;font-weight:900;color:#0B2458;letter-spacing:6px;margin-top:18px;line-height:1.1}
.l h2{font-size:44px;margin-top:20px;font-weight:800}
.l .ln{width:84px;height:5px;border-radius:3px;background:linear-gradient(90deg,#15499C,#2F7BEA);margin:34px 0 26px}
.l .tag{font-size:25px;color:#475569;letter-spacing:2px;line-height:1.6}
.l .chips{display:flex;align-items:center;margin-top:36px}.dash{width:26px;height:0;border-top:2px dashed #93B4E6;display:inline-block}
.l .date{margin-top:110px;font-size:22px;color:#94A3B8;letter-spacing:2px}
.arc{position:absolute;border-radius:50%;border:1px solid #BFD4F5;z-index:0}
.hero{position:absolute;left:980px;top:240px;z-index:2}.hero .win{transform:perspective(2200px) rotateY(-9deg) rotateX(2deg);transform-origin:left center}"""
    body = ("<div class=arc style='left:-260px;top:250px;width:820px;height:820px'></div><div class=arc style='left:-180px;top:330px;width:660px;height:660px'></div>"
            "<div class=l><div class=eb2>FROM DIGITAL COMMAND TO AI-NATIVE ORGANIZATION</div><h0>联指经营助手</h0><h2 class=grad>从数字化指挥，到承希智能大脑</h2>"
            "<div class=ln></div><div class=tag>管理看得清 · 一线用得顺 · 组织自我进化</div>"
            f"<div class=chips>{chips}</div><div class=date>2026 年 9 月</div></div>"
            f"<div class=hero>{shot('01-总体信息.png', (0, 0, 1920, 1080), 980, 577, '联合指挥驾驶舱 · 总体信息')}</div>"
            + glass_cube(920, 200, 70, 18) + glass_cube(1800, 170, 54, -12) + glass_cube(1840, 790, 82, 24) + glass_cube(940, 830, 46, -20, .9))
    return D.page(1, '', '', body, css, header=False)

# ============ 02 一页看懂 ============
@reg(2)
def p02():
    cols = [
        ('cyan', '01', '数字化指挥', '数字化、系统化', '管理侧：数据分散、口径不一、层层要表，战略目标落不到区域、客户和项目', '统一档案 · 统一口径 · 驾驶舱 · 分级权限', '沉淀', '客户、关系、商机、目标进入统一档案', '领导用驾驶舱开会', ('同步推进', 'mid')),
        ('orange', '02', '执行提效', '系统 + 工具', '执行侧：填报多、入口多、提醒靠人记、交接靠口头，一线负担重', '已有：工作台、督办、责任统筹 · 待建：移动端、推送、助手联动', '沉淀 + 流动', '每天的跟进、承诺、交接持续进档，不再随人走', '一线打开工作台就知道干什么，人员调整关系不断档', ('同步推进', 'mid')),
        ('green', '03', '承希智能大脑', 'AI 原生', '组织侧：经验已沉淀，但只是“存着”——靠人去翻、去悟，组织不会自己变好', '数字助手 · 智能研判 · 主动推送 · 自我复盘与校准', '进化', '从沉淀的经验中自动发现规律、校准规则、升级打法', '组织自己复盘、自己校准，越用越准', ('框架设计', 'todo')),
    ]
    feats = [['驾驶舱', '经营分析', '五位一体', '商机管理', '作战地图'], ['工作台', '督办队列', '责任统筹', '交接清单', '移动端 · 待建'], ['资料解析员', '分析师', '作战参谋', '督办助理', '复盘教练']]
    css = COMMON + """.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;height:690px}
.c .fs{display:flex;flex-wrap:wrap;gap:8px}.c .fs span{font-size:15px;padding:4px 11px;border-radius:99px;border:1px solid var(--c2);color:#1E293B;background:#fff}
.c{padding:24px 24px;display:flex;flex-direction:column;gap:15px;border-top:6px solid var(--c)}
.c .hd2{display:flex;align-items:center;gap:14px}.c .n{font-size:54px;font-weight:900;line-height:1;color:var(--c)}.c h3{font-size:30px;color:#0B2458;font-weight:900}.c .via{font-size:16px;color:var(--c);font-weight:800}
.c .row{padding:14px 16px;border-radius:12px;background:#F7FAFF;border:1px solid #E5EEFB}.c .row small{display:block;font-size:13px;color:#94A3B8;letter-spacing:2px;font-weight:700;margin-bottom:4px}.c .row div{font-size:18px;color:#1E293B;line-height:1.45}
.c .exp{padding:12px 14px;border-radius:12px;background:var(--bg);border:1.5px solid var(--c2)}.c .exp b{font-size:24px;color:var(--c);font-weight:900;margin-right:8px}.c .exp span{font-size:17px;color:#334155}
.c .ft{margin-top:auto;display:flex;justify-content:space-between;align-items:center}
.flow{position:absolute;top:320px;width:34px;height:34px;margin-left:-17px;border-radius:50%;background:#fff;border:1px solid #DDE8F8;display:flex;align-items:center;justify-content:center;z-index:3;box-shadow:0 8px 16px -8px rgba(21,73,156,.4)}
.bottom{margin-top:18px;padding:16px 22px;border-radius:14px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;font-size:20px;font-weight:700;box-shadow:0 18px 30px -18px rgba(21,73,156,.8)}.bottom b{color:#FDE68A}"""
    body = "<div class=stage><div class=cols>"
    for (c, n, name, via, prob, cap, exp, expd, win, (stt, cls)), fs in zip(cols, feats):
        c1, c2 = COL[c]
        body += (f"<div class='card c' style='--c:{c1};--c2:{c2}88;--bg:{c2}14'><div class=hd2><span class=n>{n}</span><div><div class=via>{via}</div><h3>{name}</h3></div></div>"
                 f"<div class=row><small>解决的问题</small><div>{prob}</div></div><div class=row><small>核心能力</small><div>{cap}</div></div>"
                 f"<div class=exp><b>{exp}</b><span>{expd}</span></div><div class=row><small>标志性成果</small><div>{win}</div></div>"
                 f"<div class=row><small>{'代表功能' if n != '03' else '六个数字助手（规划）'}</small><div class=fs>" + ''.join(f"<span>{x}</span>" for x in fs) + "</div></div>"
                 f"<div class=ft><span style='font-size:15px;color:#94A3B8'>当前进展</span><span class='st {cls}' style='font-size:17px'>{stt}</span></div></div>")
    body += "</div>" + ''.join(f"<div class=flow style='left:{x}px'>{line_icon('arrow', '#2F7BEA', 18)}</div>" for x in (589, 1164))
    body += "<div class=bottom>前两个阶段把“个人的”变成“组织的”——<b>经验沉淀</b>；第三阶段把“组织存着的”变成“组织会用、会长的”——<b>自我进化</b>。</div></div>"
    return D.page(2, '一页看懂：三类问题，三步解决', '第一、二阶段同步推进，把个人经验沉淀为组织资产；第三阶段完成框架设计，让组织资产“活”起来', body, css)

# ============ 03 驾驶舱 ============
@reg(3)
def p03():
    qs = [('chart', '全年目标完成得怎么样，差在哪个区域、哪个产业？'), ('users', '重点客户关系稳不稳，哪里有缺口、哪里只有一人对接？'),
          ('target', '在谈商机有多少可争取份额，处在什么阶段？'), ('flag', '重点项目打到哪一步，谁在负责，有没有逾期？'), ('warn', '今天有哪些风险需要协调？')]
    base = [('doc', '统一档案', '一个客户一份档案'), ('ruler', '统一口径', '投资与份额分开，签约丢标自动剔除'), ('users', '分级权限', '本人 / 团队 / 组织 / 区域 / 全局'), ('shield', '全程留痕', '看了、改了、导出了都可查')]
    css = COMMON + """.l{position:absolute;left:0;top:0;width:1110px}
.r{position:absolute;left:1146px;right:0;top:0;height:650px;display:flex;flex-direction:column;gap:10px}
.q{display:flex;gap:14px;align-items:center;padding:12px 16px;font-size:18px;color:#0B2458;font-weight:700;flex:1}.q .n{font-size:28px;font-weight:900;width:34px}
.base{position:absolute;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.b{display:flex;gap:14px;align-items:center;padding:16px 18px}.b b{display:block;font-size:22px;color:#0B2458;font-weight:800}.b span{font-size:15px;color:#64748B}"""
    body = (f"<div class=stage><div class=l>{shot('01-总体信息.png', (0, 0, 1920, 1080), 1040, 612, '联合指挥驾驶舱 · 总体信息')}</div>"
            "<div class=r><div class=sec>驾驶舱能直接回答的五个问题</div>"
            + ''.join(f"<div class='card q'><span class='n grad'>{i}</span>{ic(icn, 'blue', 42)}{t}</div>" for i, (icn, t) in enumerate(qs, 1))
            + "</div><div class=base>" + ''.join(f"<div class='card b'>{ic(i, 'cyan', 48)}<div><b>{t}</b><span>{d}</span></div></div>" for i, t, d in base) + "</div></div>")
    return D.page(3, '第一阶段：一张驾驶舱，管理看得清', '经营、客户、商机、项目放在同一份事实上，领导和一线看同一份数据', body, css)

def half(title, color, icn, shot_html, items, cap):
    c1, _ = COL[color]
    return (f"<div class='card half' style='border-top:5px solid {c1}'><div class=hh>{ic(icn, color, 48)}<div><b>{title[0]}</b><span>{title[1]}</span></div></div>"
            f"{shot_html}<div class=cap2>{cap}</div><ul class=li>" + ''.join(f"<li><i class=dia style='background:{c1}'></i><span>{x}</span></li>" for x in items) + "</ul></div>")

HALF_CSS = COMMON + """.two{display:grid;grid-template-columns:1fr 1fr;gap:28px;height:700px}
.half{padding:20px 24px;display:flex;flex-direction:column}.hh{display:flex;gap:14px;align-items:center;margin-bottom:14px}.hh b{display:block;font-size:26px;color:#0B2458;font-weight:900}.hh span{font-size:16px;color:#64748B}
.half .li{margin-top:10px}.half .li li{font-size:19px;padding:5px 0}"""

# ============ 04 经营分析 + 五位一体 ============
@reg(4)
def p04():
    a = half(('经营分析', '目标牵引：目标 → 区域 → 产业'), 'blue', 'chart', shot('02-经营分析.png', (200, 100, 1720, 900), 780, 434, '经营分析 · 核心经营总览'),
             ['<b>导入即更新</b>：按标准模板导入，每次导入留历史版本，可切换对比', '<b>阅读顺序</b>：公司整体 → 经营结构 → 区域经营 → 产业经营 → 经营基础 → 项目监测',
              '<b>指标写清楚</b>：订货、收入、回款、毛利等写明全年目标、当前达成、达成率、缺口', '<b>可追溯</b>：自动生成三条结论；每张图可放大、查看数据与原始来源表'], '界面示意 · 样例数据')
    b = half(('五位一体', '关系布局：哪里稳、哪里缺'), 'gold', 'pentagon', shot('03-五位一体.png', (0, 0, 1920, 1000), 780, 434, '驾驶舱 · 五位一体'),
             ['<b>五类客户单位</b>：主管、业主、总包、设计、厂商（运营），按区域、按类型看布局', '<b>关系健康</b>：正常 / 预警 / 告警；单点风险、对接缺口自动标出',
              '<b>三种视角</b>：客户经理看自己负责的，区域指挥看本区域，联合指挥看全局', '<b>配套功能</b>：关系评估（试行，不用于考核）、关系维系、责任统筹、资料补充'], '界面示意 · 样例数据')
    return D.page(4, '第一阶段：目标牵引到区域与产业，关系布局看得清', '经营目标和客户关系都沉淀在组织档案里，不再只在个人表格和记忆中', f"<div class=stage><div class=two>{a}{b}</div></div>", HALF_CSS)

# ============ 05 商机 + 作战地图 ============
@reg(5)
def p05():
    a = half(('商机管理', '签约支撑：口径清、阶段明'), 'green', 'flag', shot('04-商机管理.png', (0, 0, 1920, 1080), 780, 350, '驾驶舱 · 商机管理'),
             ['<b>口径清楚</b>：项目总投资与我方可参与份额（集成 + 服务）分开；已签约、已丢标不计入在谈', '<b>六阶段推进</b>：立项 → 初设 → 招标设计 → 招标执行 → 设计联络 → 合同签订，每阶段有材料与关系人',
              '<b>把握度有依据</b>：按阶段、材料、关系人、跟进计划综合估算，列出依据与缺口', '<b>关注提醒</b>：预计签约已逾期、没有负责人的商机自动提示'], '界面示意 · 样例数据')
    b = half(('项目作战地图', '重点项目：打哪里、谁去打'), 'orange', 'pin', shot('06-作战情报卡.png', (240, 140, 1500, 820), 780, 350, '项目作战地图 · 作战情报卡'),
             ['<b>重点项目上图</b>：按省份分布，气泡大小代表可参与份额', '<b>联动筛选</b>：指标、省份、阶段、把握度、签约逾期、待指派均可点击',
              '<b>作战情报卡</b>：份额、投资、阶段、招标与签约倒计时、负责人、风险提示', '<b>一键进入作战部署</b>：把工作安排落到人和节点'], '界面示意 · 样例数据')
    css = HALF_CSS.replace('height:700px', 'height:620px') + ".foot-note{bottom:0}"
    note = f"<div class=foot-note>{ic('info', 'blue', 36) if 'info' in D.ICON else ic('eye', 'blue', 36)}管理侧看得清了；但日常数据仍靠人录入、一线要在多个页面间切换——这正是同步推进的第二阶段要解决的</div>"
    return D.page(5, '第一阶段：重点项目牵引到人和节点', '签约有支撑、项目打得准——打哪里、谁去打、下一步做什么，一张图说清楚', f"<div class=stage><div class=two>{a}{b}</div>{note}</div>", css)

# ============ 06 第二阶段工具 ============
@reg(6)
def p06():
    rows = [('grid', '入口多：信息分散在不同页面', '统一工作台', '今天的待办、到期计划、需维系客户、负责项目一屏处理', ('已有', 'ok')),
            ('box', '交接难：口头交代容易丢', '交接工具', '指派、转移、协办、交接计划；下一步一键生成交接清单', ('已有基础', 'ok')),
            ('doc', '填报多：同一件事写好几遍', '模板与批量', '批量指派与更新、导入缺项进补充队列；补跟进模板、周报引用', ('部分已有', 'mid')),
            ('bell', '提醒靠人记', '提醒推送', '计划到期、关系超期、节点临近推送到企业微信 / 钉钉', ('待建', 'todo')),
            ('mail', '信息散：纪要、邮件对不上客户', '平台助手联动', '会议 / 邮件助手记录一键关联客户和商机，参会人自动带出', ('待建', 'todo')),
            ('user', '离开电脑就用不上', '移动端', '手机上查客户、登记跟进、完成计划', ('待建', 'todo'))]
    css = COMMON + """.l{position:absolute;left:0;top:0;width:1080px;bottom:90px;padding:20px 24px}
.r{position:absolute;left:1116px;right:0;top:0;bottom:90px;display:flex;flex-direction:column}
.tbl td:first-child{width:250px}.l .tbl td{padding:17px 12px}.tbl .tool{display:flex;gap:12px;align-items:center}.tbl .tool b{font-size:20px;color:#0B2458}.tbl small{display:block;font-size:15px;color:#64748B;margin-top:2px}"""
    body = "<div class=stage><div class='card l'><div class=sec>痛点 → 工具 → 当前进展</div><table class=tbl><tr><th>一线痛点</th><th>工具</th><th>进展</th></tr>"
    for i, p, t, d, (s, cls) in rows:
        body += f"<tr><td>{p}</td><td><div class=tool>{ic(i, 'orange', 40)}<div><b>{t}</b><small>{d}</small></div></div></td><td><span class='st {cls}'>{s}</span></td></tr>"
    body += (f"</table></div><div class=r><div class=sec>现有：联指经营助手 · 工作台</div>{shot('07-日常工作台.png', (230, 80, 1100, 880), 604, 480, '工作台 · 优先待办 / 督办队列 / 四板块概览')}"
             "<div class=cap2>界面示意 · 样例数据</div>"
             "<div class='card' style='margin-top:auto;padding:18px 20px;border-left:5px solid #F97316'><div style='font-size:22px;font-weight:900;color:#0B2458'>目标：少做重复的事、不漏该做的事</div>"
             "<div style='font-size:17px;color:#64748B;margin-top:6px;line-height:1.5'>第二阶段靠系统和工具提效，不依赖 AI：风险小、见效快</div></div></div>"
             f"<div class=foot-note>{ic('loop', 'green', 36)}第一、二阶段完成后，每一次拜访、承诺、交接都进入组织档案；同时开始记录“建议—采纳—结果”，为第三阶段积累素材</div></div>")
    return D.page(6, '第二阶段：系统 + 工具，解决执行侧效率与体验', '与第一阶段同步推进——不追求功能多，追求一线少做重复的事、不漏该做的事', body, css)

# ============ 07 客户经理的一天 ============
@reg(7)
def p07():
    rows = [('sun', '早上', '翻微信、翻表格，想今天该联系谁', '收到提醒 ★，打开工作台看到今天的待办和到期计划'),
            ('users', '拜访前', '到处找客户资料和上次沟通情况', '打开客户详情（手机端 ★）：联系人、历史互动、关联商机'),
            ('doc', '拜访后', '回到电脑补录，常拖到周末', '按模板当场登记（手机端 ★），下一步计划顺手安排'),
            ('meeting', '开会后', '纪要在会议助手里，和客户对不上', '纪要一键关联到客户和商机 ★'),
            ('calendar', '周五', '手工汇总写周报', '本周跟进自动汇总，周报直接引用'),
            ('box', '人员调整', '口头交代，关系和承诺易丢', '一键生成交接清单，接收人确认')]
    css = COMMON + """.l{position:absolute;left:0;top:0;width:1100px;bottom:0;display:flex;flex-direction:column;gap:10px}
.hdr{display:grid;grid-template-columns:150px 1fr 40px 1.25fr;gap:12px;font-size:15px;color:#94A3B8;font-weight:800;letter-spacing:2px;padding:0 4px}
.rw{display:grid;grid-template-columns:150px 1fr 40px 1.25fr;gap:12px;align-items:center}
.rw .t{display:flex;gap:10px;align-items:center;font-size:20px;font-weight:900;color:#0B2458}
.rw .o{padding:24px 16px;border-radius:12px;background:#F1F5F9;border:1px solid #E2E8F0;color:#94A3B8;font-size:17px}
.rw .n{padding:24px 16px;border-radius:12px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;font-size:17px;font-weight:700;box-shadow:0 12px 24px -16px rgba(21,73,156,.8)}
.r{position:absolute;left:1136px;right:0;top:0;bottom:0;display:flex;flex-direction:column;gap:12px}
.acc{padding:18px 20px;flex:1}.acc b{font-size:19px;color:#0B2458}
.sum{padding:18px 20px;border-radius:16px;background:linear-gradient(135deg,#15499C,#2F7BEA);color:#fff}.sum small{font-size:14px;letter-spacing:3px;opacity:.8}.sum b{display:block;font-size:26px;margin-top:6px}"""
    body = "<div class=stage><div class=l><div class=hdr><span>时段</span><span>改变前</span><span></span><span>改变后（第二阶段目标状态）</span></div>"
    for i, t, o, n in rows:
        body += f"<div class=rw><div class=t>{ic(i, 'orange', 40)}{t}</div><div class=o>{o}</div><div>{ic('arrow', 'blue', 36)}</div><div class=n>{n}</div></div>"
    body += "<div style='font-size:15px;color:#94A3B8'>★ 依赖待建的移动端、提醒推送或平台助手联动</div></div>"
    body += (f"<div class=r>{shot('11-客户总览.png', (60, 80, 1540, 900), 584, 342, '五位一体 · 客户总览')}<div class=cap2>现有：客户卡片、关系健康、筛选 · 样例数据</div>"
             "<div class='card acc'><div class=sec style='margin:0 0 8px'>验收标准</div><ul class=li>"
             + ''.join(f"<li style='font-size:17px;padding:2px 0'><i class=dia style='background:#F97316'></i>{x}</li>" for x in ['每周活跃人数、拜访后多久登记', '一线每周录入时间下降', '逾期计划与无人负责关系减少', '人员调整后关系无断档'])
             + "</ul></div><div class=sum style='margin-top:auto'><small>阶段小结</small><b>人走了，关系和经验还在</b></div></div></div>")
    return D.page(7, '第二阶段：客户经理的一天', '用一个人的一天看变化——个人经验在日常工作中自然沉淀到组织', body, css)

# ============ 08 智能大脑框架 ============
@reg(8)
def p08():
    loops = [('cyan', 'scan', '感知 · 自动汇聚', '资料解析员 · 外部情报员', '从纪要、邮件、合同、招标 / 中标公告、人事任免中识别客户动态，生成“待确认”记录', ['待确认记录', '商机信号', '职务变动']),
             ('blue', 'chart', '研判 · 会解读', '分析师', '客户体检、经营解读、把握度说明、风险发现，每条结论附出处', ['体检报告', '把握度说明', '风险清单']),
             ('orange', 'flag', '行动 · 先开口', '作战参谋 · 督办助理', '每日晨报、引荐路径与话术材料、逾期催办、交接包', ['每日晨报', '作战方案', '交接包']),
             ('green', 'loop', '学习 · 自我进化', '复盘教练', '追踪建议—采纳—结果，发现有效打法，提炼剧本，校准规则——组织自我进化的引擎', ['经营剧本', '规则校准', '能力报告'])]
    cmp = [('经验在哪', '在组织档案里', '被持续提炼成剧本'), ('谁来用经验', '人去翻、去悟', '系统主动送到合适的人手里'), ('规则怎么变', '靠人拍脑袋调整', '按结果提出校准，人审核生效'), ('组织能力', '不再流失', '随时间自我增长、持续升华')]
    css = COMMON + """.top{display:grid;grid-template-columns:600px 1fr;gap:24px;height:390px}
.cmp{padding:20px 22px}.cmp .tbl td{padding:16px 10px;font-size:18px}.cmp .tbl th{padding:4px 10px}
.loops{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.lp{padding:16px 16px;border-top:5px solid var(--c);display:flex;flex-direction:column;height:352px}.lp .o{margin-top:auto;padding-top:10px;border-top:1px dashed #D9E6FA;display:flex;flex-wrap:wrap;gap:6px;align-items:center}.lp .o span{font-size:13px;color:#94A3B8}.lp .o i{font-style:normal;font-size:14px;padding:3px 9px;border-radius:99px;border:1px solid var(--c);color:var(--c);font-weight:700}.lp .h{display:flex;gap:10px;align-items:center}.lp b{font-size:21px;color:var(--c);font-weight:900}.lp em{display:block;font-style:normal;font-size:17px;color:#0B2458;font-weight:700;margin-top:8px}.lp p{font-size:17px;color:#475569;line-height:1.6;margin-top:8px}
.base{margin-top:22px;padding:16px 20px;transform:perspective(1400px) rotateX(12deg);transform-origin:top}.base .t{font-size:18px;font-weight:900;color:#B45309;margin-bottom:8px}
.bricks{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}.bricks div{text-align:center;padding:14px 0;border-radius:10px;background:linear-gradient(180deg,#FFFBF2,#FDEFD3);border:1px solid #F3D59C;color:#92400E;font-size:20px;font-weight:700;box-shadow:0 5px 0 #F1D7A6}
.guard{margin-top:26px;display:grid;grid-template-columns:110px repeat(4,1fr) 1.3fr;gap:10px;align-items:center;padding:14px 16px}.guard>span{color:#DC2626;font-size:17px;font-weight:900}
.guard div{display:flex;gap:6px;align-items:center;justify-content:center;padding:12px 8px;border-radius:10px;border:1px solid #FBCACA;background:#fff;color:#991B1B;font-size:17px;font-weight:700}
.guard .test{border-color:#BFD6FA;color:#15499C;background:#EEF4FF}
.vs{margin-top:20px;display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.vs div{display:flex;align-items:center;gap:10px;padding:14px 16px;border-radius:14px;background:#fff;border:1px solid #DDE8F8;box-shadow:0 12px 24px -18px rgba(21,73,156,.4)}
.vs small{font-size:14px;color:#fff;background:#2F7BEA;border-radius:8px;padding:2px 8px;font-weight:800}.vs .o2{font-size:16px;color:#94A3B8}.vs b{font-size:17px;color:#15499C}"""
    body = ("<div class=stage><div class=top><div class='card cmp'><div class=sec>从沉淀到进化</div><table class=tbl><tr><th></th><th>沉淀（第一、二阶段）</th><th>进化（第三阶段）</th></tr>"
            + ''.join(f"<tr><td style='color:#64748B;font-weight:700'>{a}</td><td style='color:#94A3B8'>{b}</td><td style='color:#15803D;font-weight:700'>{c}</td></tr>" for a, b, c in cmp)
            + "</table></div><div><div class=sec>架构：一个底座 · 四个闭环 · 六个数字助手 · 四条底线</div><div class=loops>"
            + ''.join(f"<div class='card lp' style='--c:{COL[c][0]}'><div class=h>{ic(i, c, 40)}<b>{t}</b></div><em>{who}</em><p>{d}</p><div class=o><span>产出</span>" + ''.join(f"<i>{x}</i>" for x in outs) + "</div></div>" for c, i, t, who, d, outs in loops)
            + "</div></div></div><div class='glass base'><div class=t>经营知识底座 · 组织记忆（第一、二阶段沉淀的全部资产）</div><div class=bricks>"
            + ''.join(f"<div>{t}</div>" for t in ['客户与组织', '人与关系', '互动与情报', '商机与项目', '经营结果', '剧本与规则'])
            + "</div></div><div class='card guard'><span>四条底线</span>"
            + ''.join(f"<div>{line_icon('shield', '#DC2626', 16)}{t}</div>" for t in ['数据不出内网', '权限不扩大', 'AI 不直接改数据', '评估不用于考核'])
            + "<div class=test>检验：拿掉 AI，工作会退回原样吗？</div></div>"
            + "<div class=vs>" + ''.join(f"<div><small>{a}</small><span class=o2>{b}</span>{line_icon('arrow', '#2F7BEA', 18)}<b>{c}</b></div>" for a, b, c in
                [('信息', '人事后补填', 'AI 自动汇聚'), ('判断', '人看报表下结论', 'AI 起草并附出处'), ('行动', '想起来才去做', '系统主动推送'), ('经验', '存在档案里', '持续提炼、自我校准')]) + "</div></div>")
    return D.page(8, '第三阶段：让组织“活”起来——承希智能大脑', '框架设计：前两阶段让经验“存得下”，第三阶段让组织“自己会长”——自己发现、复盘、校准、升级打法', body, css)

# ============ 09 项目旅程 ============
@reg(9)
def p09():
    steps = [('cyan', 'radar', '发现', '外部情报员', '招标公告 → 建议新建商机', '商机建议', '区域指挥确认'), ('blue', 'chart', '研判', '分析师', '体检：设计院关键人未接触', '体检报告', None),
             ('orange', 'flag', '部署', '作战参谋', '找到引荐人，建议先做技术交流', '作战计划', '客户经理确认'), ('orange', 'bell', '提醒', '督办助理', '晨报提示，到期前再提醒', '晨报', None),
             ('cyan', 'scan', '记录', '资料解析员', '纪要解析：对方关注国产化', '互动记录', '本人确认入档'), ('blue', 'chart', '推进', '分析师', '关系更新，建议推进阶段', '阶段推进', '负责人确认'),
             ('green', 'loop', '复盘', '复盘教练', '“设计阶段先做技术交流”入剧本', '剧本条目', '剧本负责人审核')]
    says = [('体检', '业主关系稳定，设计院关键技术负责人尚未接触'), ('晨报', '今天先联系设计院技术负责人：已超维系周期，项目进入招标设计，建议带技术方案'),
            ('把握度', '招标阶段缺技术方案材料，把握度下调'), ('督办', '一条关键关系跟进已逾期，负责人未处理，已同步区域指挥')]
    css = COMMON + """.track{position:absolute;left:0;right:0;top:34px;height:26px;border-radius:20px;background:linear-gradient(90deg,#BAE6FD,#BFD6FA,#FED7AA,#BBF7D0);box-shadow:inset 0 2px 0 #ffffffcc,0 14px 24px -14px rgba(21,73,156,.45)}
.steps{position:relative;display:grid;grid-template-columns:repeat(7,1fr);gap:12px}
.s{display:flex;flex-direction:column;align-items:center}.dot{width:92px;height:92px;border-radius:50%;background:#fff;border:5px solid var(--c);display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:900;color:var(--c);box-shadow:0 14px 24px -12px var(--c)}
.nm{font-size:26px;font-weight:900;color:var(--c);margin:10px 0 8px}
.sc{width:100%;height:350px;padding:18px 12px;display:flex;flex-direction:column;align-items:center;text-align:center;border-top:4px solid var(--c)}
.sc b{font-size:21px;color:#0B2458;font-weight:800;margin-top:10px}.sc span{font-size:18px;color:#475569;line-height:1.5;margin-top:8px}
.sc .prod{margin-top:auto;font-size:13px;color:#94A3B8}.sc .prod b{display:block;font-size:15px;color:var(--c);padding:3px 10px;border-radius:99px;border:1px solid var(--c);margin:3px 0 8px}
.sc em{font-style:normal;font-size:14px;padding:5px 8px;border-radius:10px;background:#FFF8EB;border:1px solid #F3D59C;color:#92400E;font-weight:700}.sc em.a{background:#F1F5F9;border-color:#E2E8F0;color:#94A3B8;font-weight:400}
.says{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:24px}.say{padding:18px 18px;min-height:130px;border-left:4px solid #2F7BEA}.say small{display:flex;gap:6px;align-items:center;font-size:13px;color:#2F7BEA;font-weight:800;letter-spacing:2px}.say p{font-size:18px;color:#1E3A8A;margin-top:6px;line-height:1.5}
.note{margin-top:24px;text-align:center;font-size:28px;font-weight:900;color:#0B2458}.note span{background:linear-gradient(90deg,#D97706,#F59E0B);-webkit-background-clip:text;color:transparent}"""
    body = "<div class=stage><div class=track></div><div class=steps>"
    for i, (c, icn, nm, who, d, prod, human) in enumerate(steps, 1):
        body += (f"<div class=s style='--c:{COL[c][0]}'><div class=dot>{i}</div><div class=nm>{nm}</div><div class='card sc'>{ic(icn, c, 40)}<b>{who}</b><span>{d}</span>"
                 f"<div class=prod>产出<b>{prod}</b></div>" + (f"<em>人：{human}</em>" if human else "<em class=a>自动完成</em>") + "</div></div>")
    body += "</div><div class=says>" + ''.join(f"<div class='card say'><small>{line_icon('link', '#2F7BEA', 14)} AI 会怎么说 · {t} · 附出处</small><p>“{d}”</p></div>" for t, d in says)
    body += "</div><div class=note>AI 负责<span>感知、整理、提醒、起草</span>；判断与承诺<span>始终由人做</span></div></div>"
    return D.page(9, '第三阶段：一个项目的完整旅程', '情景示意（虚构）：某市地铁新线——六个数字助手接力，人在关键节点拍板；项目结束，经验回流', body, css)

# ============ 10 自我进化机制与底线 ============
@reg(10)
def p10():
    css = COMMON + """.g{display:grid;grid-template-columns:1.05fr 1fr 0.95fr;gap:22px;height:760px}
.col{padding:20px 22px;display:flex;flex-direction:column}
.ring{position:relative;width:100%;height:340px;margin:4px 0 10px}
.orb{position:absolute;left:50%;top:50%;width:120px;height:120px;margin:-60px 0 0 -60px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff,#FDE68A 55%,#F59E0B);display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:900;color:#0B2458;box-shadow:0 20px 30px -14px #D9770699}
.stp{position:absolute;transform:translate(-50%,-50%);background:#fff;color:#15803D;border-color:#86EFAC;font-size:15px;padding:4px 12px}
.out{padding:16px 16px;border-radius:12px;background:#F0FDF4;border:1px solid #BBF7D0;margin-top:12px;font-size:18px;color:#14532D;line-height:1.45}.out b{color:#15803D}
.tier{padding:20px 18px;border-radius:14px;margin-top:14px;border:1.5px solid var(--c);background:var(--bg)}.tier b{font-size:22px;color:var(--c);font-weight:900}.tier p{font-size:17px;color:#334155;margin-top:4px;line-height:1.5}
.gd{display:flex;gap:12px;align-items:flex-start;padding:26px 0;border-bottom:1px dashed #F3C4C4}.gd:last-of-type{border-bottom:0}.gd .n{font-size:26px;font-weight:900;color:#DC2626;width:36px}.gd b{font-size:21px;color:#0B2458}.gd p{font-size:16px;color:#64748B;margin-top:2px}"""
    import math
    stepsx = ['建议', '采纳', '执行', '结果', '总结规律', '更新剧本']
    pos = [(50 + 36 * math.sin(math.radians(a)), 50 - 40 * math.cos(math.radians(a))) for a in range(0, 360, 60)]
    ring = ("<svg style='position:absolute;inset:0' width='100%' height='100%' viewBox='0 0 100 100' preserveAspectRatio='none'><ellipse cx=50 cy=50 rx=36 ry=40 fill=none stroke='#86EFAC' stroke-width=6 opacity=.35/>"
            "<ellipse cx=50 cy=50 rx=36 ry=40 fill=none stroke='#16A34A' stroke-width=.6 stroke-dasharray='2 2'/></svg><div class=orb>组织记忆</div>"
            + ''.join(f"<span class='pill stp' style='left:{x:.0f}%;top:{y:.0f}%'>{t}</span>" for (x, y), t in zip(pos, stepsx)))
    left = (f"<div class='card col' style='border-top:5px solid #16A34A'><div class=sec style='color:#16A34A'>自我进化的循环</div><div class=ring>{ring}</div>"
            "<div class=out><b>经营剧本</b>：哪类客户、哪个阶段、什么做法最有效</div><div class=out><b>规则校准</b>：维系周期、把握度按结果提出调整，人审核后生效</div>"
            "<div class=out><b>季度组织能力报告</b>：关系资产结构、风险消解、预测偏差</div>"
            "<div style='margin-top:auto;font-size:15px;color:#64748B;line-height:1.5'>见效约两到三个季度 · 只用脱敏汇总经验，不看个人明细</div></div>")
    tiers = [('#0EA5E9', '#E0F2FE55', 'AI 直接做（只读）', '查询汇总、生成晨报与体检报告、风险提醒、起草话术与材料'),
             ('#D97706', '#FEF3C755', 'AI 建议 · 人确认', '新增互动记录、推进商机阶段、生成跟进计划、完成交接、调整剧本'),
             ('#DC2626', '#FEE2E255', '只能人做', '对客户的任何承诺与发送、资源调配、评价员工、权限授予')]
    mid = ("<div class='card col' style='border-top:5px solid #D97706'><div class=sec style='color:#D97706'>人机分工三档</div>"
           + ''.join(f"<div class=tier style='--c:{c};--bg:{bg}'><b>{t}</b><p>{d}</p></div>" for c, bg, t, d in tiers)
           + f"<div style='margin-top:auto'>{shot('10-关系评估详情.png', (1066, 170, 848, 480), 470, 200, '现有：关系评估 · 评分与建议')}<div class=cap2>公式 + 证据 + 缺口 + 下一步，是研判能力的基础</div></div></div>")
    gds = [('数据不出内网', '走公司内部通道与已有 AI 安全网关'), ('权限不扩大', 'AI 只看使用者本来能看的数据，全程留痕'), ('AI 不直接改数据', '写入须人确认，确认人即责任人，可追溯'), ('评估不用于个人考核', '挂钩考核会让数据失真，需制度化')]
    right = ("<div class='card col' style='border-top:5px solid #DC2626'><div class=sec style='color:#DC2626'>四条底线</div>"
             + ''.join(f"<div class=gd><span class=n>0{i}</span><div><b>{t}</b><p>{d}</p></div></div>" for i, (t, d) in enumerate(gds, 1))
             + "<div style='margin-top:auto;padding:16px 18px;border-radius:14px;background:linear-gradient(135deg,#DC2626,#F87171);color:#fff'><small style='font-size:13px;letter-spacing:3px;opacity:.85'>需要制度配合</small><div style='font-size:20px;font-weight:900;margin-top:6px;line-height:1.45'>第 4 条是底线中的底线：评分一旦与考核挂钩，组织学到的就是失真的经验</div></div></div>")
    return D.page(10, '第三阶段：自我进化机制与安全底线', '组织靠“建议—结果”闭环自我进化；靠三档分工和四条底线保证可控、可信', f"<div class=stage><div class=g>{left}{mid}{right}</div></div>", css)

def glass_obj_html():
    return ("<svg width=180 height=200 viewBox='0 0 360 440'><defs><linearGradient id=sg2 x1=0 y1=0 x2=1 y2=1><stop offset=0 stop-color='#fff'/><stop offset=1 stop-color='#FECACA'/></linearGradient></defs>"
            "<path d='M180 20 L330 80 V210 C330 320 260 390 180 425 C100 390 30 320 30 210 V80 Z' fill='url(#sg2)' stroke='#F87171' stroke-width=6/>"
            "<path d='m120 220 45 45 80-95' stroke='#DC2626' stroke-width=18 fill=none stroke-linecap=round stroke-linejoin=round/></svg>")

# ============ 11 推进路线与组织 ============
@reg(11)
def p11():
    rows = [('cyan', '第一阶段 · 管理侧', ('同步推进', 'mid'), '驾驶舱、经营分析、五位一体、商机管理、项目作战地图、权限留痕已上线', '试点区域导入真实数据，替换样例数据；驾驶舱用于周例会', '试点区域真实数据全部入库并经区域确认'),
            ('orange', '第二阶段 · 执行侧', ('同步推进', 'mid'), '工作台、督办队列、责任统筹、资料补充已有基础', '补齐移动端、提醒推送、会议 / 邮件助手联动、模板、交接清单；开始记录“建议—结果”', '一线持续使用、录入时间下降、人员调整关系不断档'),
            ('green', '第三阶段 · 组织侧', ('框架设计', 'todo'), '底座、四个闭环、六个数字助手、四条底线已明确', '数据到位后：先感知与研判 → 再行动 → 最后学习，助手分批试点、分别验收', 'AI 结果多数无需修改、建议有人采纳、预测偏差缩小')]
    roles = [('客户经理', '事后补录，凭记忆跟进', '在工作台处理当天事务，按晨报行动'), ('区域指挥', '层层要表', '看信号、调资源、直接督办'), ('联合指挥', '听汇报、看滞后数据', '用驾驶舱与智能研判定策略'),
             ('经营数据管家 · 新增兼职', '—', '本区域数据完整、口径一致'), ('剧本负责人 · 新增兼任', '—', '审核 AI 提炼的经验与规则调整')]
    css = COMMON + """.rt{padding:20px 22px}.rt .tbl td{font-size:18px;padding:18px 10px}.rt .tbl th{font-size:16px}.rt .ph{display:flex;gap:10px;align-items:center;font-size:18px;font-weight:900;color:#0B2458;white-space:nowrap}
.low{display:grid;grid-template-columns:1.35fr 1fr;gap:20px;margin-top:20px;height:390px}
.ro{padding:18px 22px}.ro .tbl td{font-size:18px;padding:12px 10px}
.rh{padding:18px 22px;display:flex;flex-direction:column;gap:14px}.rh .blk{flex:1;display:flex;gap:14px;align-items:center;padding:14px 16px;border-radius:14px;background:linear-gradient(145deg,#fff,var(--bg));border:1px solid #E2EBF8}.rh b{font-size:21px;color:#0B2458}.rh span{display:block;font-size:16px;color:#64748B}"""
    body = "<div class=stage><div class='card rt'><div class=sec>推进路线</div><table class=tbl><tr><th>阶段</th><th>当前进展</th><th>已有基础</th><th>接下来做什么</th><th>验收门槛</th></tr>"
    for c, name, (s, cls), have, nxt, gate in rows:
        body += f"<tr><td><div class=ph><i class=dia style='background:{COL[c][0]}'></i>{name}</div></td><td><span class='st {cls}'>{s}</span></td><td>{have}</td><td>{nxt}</td><td style='color:#0B2458;font-weight:700'>{gate}</td></tr>"
    body += "</table></div><div class=low><div class='card ro'><div class=sec>角色变化</div><table class=tbl><tr><th>角色</th><th>过去</th><th>以后</th></tr>"
    body += ''.join(f"<tr><td style='font-weight:800;color:#0B2458'>{a}</td><td style='color:#94A3B8'>{b}</td><td style='color:#15499C;font-weight:700'>{c}</td></tr>" for a, b, c in roles)
    body += "</table></div><div class='card rh'><div class=sec>管理节奏</div>"
    body += ''.join(f"<div class=blk style='--bg:{COL[c][1]}22'>{ic(i, c, 44)}<div><b>{t}</b><span>{d}</span></div></div>" for c, i, t, d in
                    [('cyan', 'calendar', '每周 · 驾驶舱例会', '基于同一份事实开会'), ('blue', 'warn', '每月 · 风险复盘', '缺口与单点消解情况'), ('green', 'ruler', '每季 · 规则校准', '审核剧本与规则调整')])
    body += "</div></div></div>"
    return D.page(11, '推进路线与组织配合', '第一、二阶段同步推进，第三阶段先设计框架、再分批落地；每一步设门槛，组织同步调整', body, css)

# ============ 12 风险与拍板 ============
@reg(12)
def p12():
    risks = [('数据不全、更新不及时', '真实数据入库设门槛；数据管家到人；第二阶段工具降低录入'), ('一线抵触', '第二阶段以“减负”为验收标准；推送克制'),
             ('AI 说错、编造', '只引用已有记录，证据不足明说；人确认后生效'), ('客户数据安全', '内网通道、安全网关、权限继承、全程留痕'),
             ('评分变考核，数据失真', '以制度明确“评估不用于个人考核”'), ('期望过高', '分阶段验收；学习效果预期两到三个季度以上')]
    dec = [('pin', '试点范围', '首批试点区域与团队，数据导入责任人与完成时间', None), ('scale', '考核红线', '关系评估只用于经营辅助，不用于个人考核', '制度'),
           ('chip', 'AI 使用边界', '走公司内部通道，客户数据不出内网', None), ('chat', '推送渠道', '企业微信还是钉钉', None),
           ('share', '经验共享授权', '脱敏后跨区域汇总经验，明确谁可看能力报告', '制度'), ('users', '人员与流程', '设立数据管家与剧本负责人；交接确认纳入调动流程', '制度')]
    css = COMMON + """.g{display:grid;grid-template-columns:0.95fr 1.05fr;gap:22px;height:610px}
.rk{padding:22px 24px}.rk .tbl td{font-size:18px;padding:24px 8px;line-height:1.5}.rk .r1{display:flex;gap:8px;align-items:center;font-weight:800;color:#991B1B;font-size:19px;white-space:nowrap}
.dc{padding:18px 20px}.dg{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.d{position:relative;padding:26px 18px;border-radius:14px;border:1px solid #DDE8F8;background:#fff;display:flex;gap:12px;align-items:flex-start}.d.sys{border-color:#FCA5A5;background:#FFF7F7}
.d b{font-size:22px;color:#0B2458;font-weight:900}.d p{font-size:17px;color:#475569;margin-top:4px;line-height:1.45}.d .t{position:absolute;right:10px;top:10px;font-size:12px;font-weight:800;color:#fff;background:#DC2626;padding:2px 8px;border-radius:99px}
.inv{margin-top:18px;padding:16px 18px;border-radius:12px;background:#EEF4FF;border:1px solid #C9DBF6;font-size:17px;color:#15499C;font-weight:700}
.end{margin-top:18px;padding:22px 28px;border-radius:18px;background:linear-gradient(90deg,#15499C,#2F7BEA);color:#fff;display:flex;align-items:center;justify-content:space-between;box-shadow:0 22px 36px -18px rgba(21,73,156,.8)}
.end b{font-size:30px;font-weight:900;letter-spacing:1px}.end span{font-size:20px;opacity:.9}"""
    body = "<div class=stage><div class=g><div class='card rk'><div class=sec style='color:#DC2626'>风险与应对</div><table class=tbl>"
    body += ''.join(f"<tr><td><div class=r1>{line_icon('warn', '#DC2626', 18)}{r}</div></td><td>{a}</td></tr>" for r, a in risks)
    body += "</table></div><div class='card dc'><div class=sec>请领导拍板的六件事</div><div class=dg>"
    body += ''.join(f"<div class='d{' sys' if t else ''}'>" + (f"<span class=t>{t}</span>" if t else '') + f"{ic(i, 'red' if t else 'blue', 42)}<div><b>{n:02d} {nm}</b><p>{d}</p></div></div>" for n, (i, nm, d, t) in enumerate(dec, 1))
    body += "</div><div class=inv>建议投入：核心小组 4–5 人（产品 1、研发 2–3、业务专家 1 兼职）+ 各试点区域数据管家（兼职）</div></div></div>"
    body += "<div class=end><b>管理看得清 → 一线用得顺 → 组织自我进化</b><span>从数字化指挥，到承希智能大脑 · 谢谢</span></div></div>"
    return D.page(12, '风险底线与需要拍板的事项', '技术风险可控，关键在数据、人和制度', body, css)

if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    nums = [int(a) for a in sys.argv[1:]] or sorted(PAGES)
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=['--no-sandbox']); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        for n in nums:
            pg.set_content(PAGES[n]()); pg.wait_for_timeout(250)
            over = pg.evaluate("() => [...document.querySelectorAll('.card,.glass')].filter(e => e.scrollHeight > e.clientHeight + 2 || e.getBoundingClientRect().bottom > 1062).length")
            pg.screenshot(path=str(D.OUT / f'{n:02d}.png')); print('saved', n, 'overflow', over)
        b.close()
