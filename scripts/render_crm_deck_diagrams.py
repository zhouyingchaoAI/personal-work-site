from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path('/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1790564116534_newzkr/diagrams'); OUT.mkdir(parents=True, exist_ok=True)
C = dict(sense='#22d3ee', judge='#60a5fa', act='#fb923c', learn='#4ade80')
BASE = """<style>*{box-sizing:border-box;margin:0;padding:0}body{width:1920px;height:1080px;background:radial-gradient(circle at 18% 12%,#1d4f9e55,transparent 45%),radial-gradient(circle at 85% 90%,#0e749044,transparent 40%),#0b1f45;color:#e6eefc;font-family:'Droid Sans Fallback','Noto Sans CJK SC',sans-serif;padding:56px 80px;overflow:hidden}
h1{font-size:46px;font-weight:700;letter-spacing:2px}h1 small{display:block;font-size:24px;color:#8fb3e8;font-weight:400;margin-top:10px;letter-spacing:1px}
.box{border:1.5px solid #2c5aa0;background:#10306acc;border-radius:18px}.tag{display:inline-block;padding:4px 14px;border-radius:999px;font-size:20px}
.foot{position:absolute;right:80px;bottom:34px;font-size:18px;color:#6f8fc4}</style>"""
pages = {}

pages['01-AI辅助与AI原生对比'] = """<h1>AI 辅助 vs AI 原生<small>不是加一个聊天框，而是改变工作的默认方式</small></h1>
<style>.g{display:grid;grid-template-columns:220px 1fr 90px 1fr;gap:24px 0;margin-top:60px;align-items:stretch}.h{font-size:28px;font-weight:700;padding:14px 26px}.l{font-size:26px;color:#9fc0f0;display:flex;align-items:center}.c{font-size:28px;padding:28px 28px;border-radius:14px;display:flex;align-items:center}.old{background:#1a2b4f;color:#9fb0cc}.new{background:linear-gradient(90deg,#0e4d7a,#0f5f8a);color:#fff;border:1.5px solid #22d3ee88}.ar{display:flex;align-items:center;justify-content:center;font-size:38px;color:#22d3ee}.test{margin-top:56px;text-align:center;font-size:32px;padding:22px;border:2px dashed #22d3ee;border-radius:16px;color:#cffafe}</style>
<div class=g><div></div><div class="h" style="color:#9fb0cc">传统系统 / AI 辅助</div><div></div><div class="h" style="color:#22d3ee">AI 原生</div>
""" + ''.join(f"<div class=l>{a}</div><div class='c old'>{b}</div><div class=ar>➜</div><div class='c new'>{c}</div>" for a,b,c in [
('信息从哪来','人事后补填'),('判断怎么做','人看报表自己得结论'),('行动怎么发起','人想起来才去做'),('经验在哪里','在个人脑子里'),('AI 的角色','问了才答的工具')] and [
('信息从哪来','人事后补填','AI 从语音 / 会议 / 邮件 / 公告整理，人确认'),('判断怎么做','人看报表自己得结论','AI 起草结论并附出处，人拍板'),('行动怎么发起','人想起来才去做','系统每天主动推送该做什么、为什么'),('经验在哪里','在个人脑子里','沉淀为组织剧本，按结果持续校准'),('AI 的角色','问了才答的工具','嵌在每个环节的"数字助手"')]) + """</div>
<div class=test>检验标准：把 AI 拿掉，工作方式会不会退回原样？<b style="color:#22d3ee">会，才算 AI 原生。</b></div>"""

def loopcol(key,name,sub,agents):
    col=C[key]
    ag=''.join(f"<div class=ag style='border-color:{col}66'><b style='color:{col}'>{a}</b><span>{d}</span></div>" for a,d in agents)
    return f"<div class=loop style='border-top:6px solid {col}'><div class=lh><span style='color:{col}'>{name}</span><small>{sub}</small></div>{ag}</div>"
pages['02-AI原生架构总图'] = """<h1>AI 原生架构：一个底座 · 四个闭环 · 六个数字助手 · 四条底线</h1>
<style>.row{margin-top:28px}.loops.row{margin-top:64px}.entry{display:flex;gap:16px;align-items:center;padding:16px 24px}.entry .t{font-size:22px;color:#8fb3e8;width:150px}.chip{flex:1;text-align:center;font-size:25px;padding:16px;border-radius:12px;background:#163c7c}
.loops{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;position:relative}.loop{min-height:330px;background:#0f2c62;border-radius:16px;padding:22px 20px 14px;border:1.5px solid #2c5aa0}.lh{font-size:32px;font-weight:700;margin-bottom:12px}.lh small{font-size:19px;color:#8fb3e8;font-weight:400;margin-left:10px}
.ag{border:1.5px solid;border-radius:12px;padding:14px 16px;margin-bottom:14px;background:#0b2350}.ag b{font-size:27px;display:block}.ag span{font-size:21px;color:#b8cbe8;line-height:1.45}
.flow{position:absolute;top:-44px;left:0;right:0;text-align:center;font-size:23px;letter-spacing:2px;color:#8fb3e8}
.base{padding:18px 24px}.base .t{font-size:26px;font-weight:700;color:#fbbf24;margin-bottom:12px}.cells{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}.cells div{text-align:center;font-size:25px;padding:18px 6px;border-radius:10px;background:#3a2f0f;border:1px solid #fbbf2466;color:#fde68a}
.guard{display:grid;grid-template-columns:150px repeat(4,1fr);gap:14px;align-items:center;padding:14px 24px;border-color:#f8717166;background:#3a142466}.guard .t{font-size:22px;color:#fca5a5}.guard div:not(.t){text-align:center;font-size:25px;padding:14px;border-radius:10px;border:1.5px solid #f8717188;color:#fecaca}</style>
<div class="row box entry"><span class=t>使用入口</span><span class=chip>驾驶舱 · 工作台（保留）</span><span class=chip>页面侧边助手</span><span class=chip>企业微信 / 钉钉推送</span><span class=chip>手机语音速记</span></div>
<div class="row loops"><div class=flow>感知 → 研判 → 行动 → 学习 → 回到感知</div>""" + \
 loopcol('sense','感知闭环','少填表',[('速记员','拜访 / 会议 / 邮件整理成记录'),('情报员','招标 · 中标 · 人事任免')]) + \
 loopcol('judge','研判闭环','会解读',[('分析师','客户体检 · 经营解读 · 把握度说明 · 风险发现')]) + \
 loopcol('act','行动闭环','先开口',[('作战参谋','打谁 · 谁去 · 引荐路径 · 第一步'),('督办助理','晨报 · 提醒 · 催办 · 交接包')]) + \
 loopcol('learn','学习闭环','越用越准',[('复盘教练','什么做法有效 → 更新剧本与规则（人审核发布）')]) + """</div>
<div class="row box base"><div class=t>经营知识底座 · 组织记忆（唯一事实来源）</div><div class=cells><div>客户与组织</div><div>人与关系</div><div>互动与情报</div><div>商机与项目</div><div>经营结果</div><div>剧本与规则</div></div></div>
<div class="row box guard"><span class=t>四条底线</span><div>数据不出内网</div><div>权限不扩大</div><div>AI 不直接改数据</div><div>评估不用于个人考核</div></div>"""

pages['03-感知闭环流程'] = """<h1>感知闭环：从"填表"到"说两句"<small>记录成本降下来，数据才会持续更新</small></h1>
<style>.src{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:70px}.src div{padding:34px 22px;border-radius:16px;background:#0f2c62;border:1.5px solid #22d3ee66;font-size:31px;text-align:center}.src small{display:block;font-size:22px;color:#8fb3e8;margin-top:8px}
.down{text-align:center;font-size:48px;color:#22d3ee;margin:28px 0}.ai{margin:0 auto;width:1400px;padding:34px 40px;border-radius:18px;background:linear-gradient(90deg,#0e4d7a,#115e7e);border:2px solid #22d3ee}.ai b{font-size:34px;color:#cffafe}.ai .f{display:flex;gap:14px;margin-top:16px}.ai .f span{flex:1;text-align:center;font-size:26px;padding:16px;border-radius:10px;background:#0b2350}
.end{display:grid;grid-template-columns:1fr 1fr;gap:30px;width:1400px;margin:0 auto}.end div{padding:34px;border-radius:16px;font-size:32px;text-align:center}</style>
<div class=src><div>语音 / 文字速记<small>最先上线 · 一线最常用</small></div><div>会议纪要<small>按参会人匹配客户</small></div><div>往来邮件<small>按收发件人匹配客户</small></div><div>公开信息<small>招标 · 中标 · 人事任免</small></div></div>
<div class=down>▼</div>
<div class=ai><b>速记员 / 情报员 整理成结构化记录</b><div class=f><span>见了谁</span><span>谈了什么</span><span>对方态度</span><span>对方承诺</span><span>下一步</span><span>原文出处</span></div></div>
<div class=down>▼</div>
<div class=end><div style="background:#3a2f0f;border:2px solid #fbbf24;color:#fde68a">本人确认（一两秒）<br><small style="font-size:20px">确认人即责任人 · 可修改 · 可拒绝</small></div><div style="background:#0f3d2a;border:2px solid #4ade80;color:#bbf7d0">入库并即时反馈<br><small style="font-size:20px">例："该客户的上级我方尚未接触"</small></div></div>"""

pages['04-四个闭环'] = """<h1>四个闭环：让组织越用越聪明</h1>
<style>svg text{font-family:'Droid Sans Fallback',sans-serif}</style>
<svg width="1760" height="890" viewBox="0 0 1760 935" style="margin-top:10px">
<defs><marker id="a" markerWidth="12" markerHeight="12" refX="6" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="#8fb3e8"/></marker></defs>
<circle cx="880" cy="470" r="300" fill="none" stroke="#2c5aa0" stroke-width="3" stroke-dasharray="10 10"/>
<circle cx="880" cy="470" r="150" fill="#10306a" stroke="#fbbf24" stroke-width="3"/>
<text x="880" y="455" text-anchor="middle" font-size="34" fill="#fde68a" font-weight="700">组织记忆</text>
<text x="880" y="500" text-anchor="middle" font-size="22" fill="#e6eefc">建议—采纳—执行—结果</text>
""" + ''.join(f"""<g><rect x="{x-230}" y="{y-85}" width="460" height="170" rx="22" fill="#0f2c62" stroke="{c}" stroke-width="3"/>
<text x="{x}" y="{y-30}" text-anchor="middle" font-size="36" font-weight="700" fill="{c}">{n}</text>
<text x="{x}" y="{y+15}" text-anchor="middle" font-size="23" fill="#e6eefc">{a}</text><text x="{x}" y="{y+52}" text-anchor="middle" font-size="21" fill="#9fb8e0">{b}</text></g>"""
 for x,y,c,n,a,b in [(880,110,C['sense'],'① 感知 · 少填表','速记员 · 情报员','语音 / 会议 / 邮件 / 公告 → 记录'),(1480,470,C['judge'],'② 研判 · 会解读','分析师','规则算分 + AI 讲清原因与出处'),(880,830,C['act'],'③ 行动 · 先开口','作战参谋 · 督办助理','晨报 · 打法 · 催办 · 交接包'),(280,470,C['learn'],'④ 学习 · 越用越准','复盘教练','什么有效 → 剧本与规则（人审核）')]) + """
<path d="M1120,160 Q1380,220 1440,370" stroke="#8fb3e8" stroke-width="3" fill="none" marker-end="url(#a)"/>
<path d="M1440,570 Q1380,720 1120,790" stroke="#8fb3e8" stroke-width="3" fill="none" marker-end="url(#a)"/>
<path d="M640,790 Q380,720 320,570" stroke="#8fb3e8" stroke-width="3" fill="none" marker-end="url(#a)"/>
<path d="M320,370 Q380,220 640,160" stroke="#8fb3e8" stroke-width="3" fill="none" marker-end="url(#a)"/>
</svg>"""

steps=[('sense','发现','情报员','招标公告 → 建议新建商机','区域指挥确认'),('judge','研判','分析师','体检：设计院关键人未接触','—'),('act','部署','作战参谋','引荐路径 + 技术交流 + 材料','客户经理确认转计划'),('act','提醒','督办助理','晨报提示，到期前再提醒','—'),('sense','记录','速记员','说两句 → 识别"关注国产化"','本人确认入库'),('judge','推进','分析师','关系更新，建议推进阶段','负责人确认'),('learn','复盘','复盘教练','"设计阶段先做技术交流"入剧本','剧本负责人审核')]
pages['05-项目旅程'] = """<h1>一个项目的完整旅程<small>情景示意：某市地铁新线（虚构）· 六个数字助手接力，人在关键节点拍板</small></h1>
<style>.tl{display:grid;grid-template-columns:repeat(7,1fr);gap:16px;margin-top:110px;position:relative}.tl:before{content:'';position:absolute;left:3%;right:3%;top:44px;height:4px;background:linear-gradient(90deg,#22d3ee,#60a5fa,#fb923c,#4ade80)}
.st{position:relative;text-align:center}.dot{width:88px;height:88px;border-radius:50%;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:700;background:#0b1f45;border:4px solid}.nm{font-size:36px;font-weight:700;margin:18px 0 10px}.card{border-radius:14px;background:#0f2c62;border:1.5px solid #2c5aa0;padding:26px 16px;min-height:380px;display:flex;flex-direction:column}.who{font-size:27px;font-weight:700;margin-bottom:10px}.what{font-size:24px;line-height:1.6;flex:1;color:#dbe7fb}.hm{margin-top:16px;font-size:21px;padding:12px 8px;border-radius:10px;background:#3a2f0f;color:#fde68a;border:1px solid #fbbf2466}.hm.no{background:transparent;border-color:transparent;color:#5d77a8}
.note{margin-top:80px;text-align:center;font-size:32px;color:#cfe0fa}.note b{color:#fbbf24}</style><div class=tl>""" + ''.join(
 f"<div class=st><div class=dot style='border-color:{C[k]};color:{C[k]}'>{i+1}</div><div class=nm style='color:{C[k]}'>{n}</div><div class=card><div class=who style='color:{C[k]}'>{w}</div><div class=what>{d}</div><div class='hm{' no' if h=='—' else ''}'>{'人：'+h if h!='—' else '自动'}</div></div></div>" for i,(k,n,w,d,h) in enumerate(steps)) + """</div>
<div class=note>AI 负责<b>跑腿、整理、提醒、起草</b>；判断与承诺<b>始终由人做</b></div>"""

pages['06-人机分工三档'] = """<h1>人机分工：AI 能做什么、不能做什么<small>责任始终在人</small></h1>
<style>.tiers{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin-top:56px}.tier{border-radius:20px;padding:40px 32px;min-height:720px}.tier h2{font-size:36px;margin-bottom:8px}.tier .s{font-size:22px;opacity:.85;margin-bottom:26px}.tier li{list-style:none;font-size:28px;padding:18px 20px;border-radius:12px;margin-bottom:14px;background:#0b1f4599}</style>
<div class=tiers>
<div class=tier style="background:#0e3b4f;border:2px solid #22d3ee"><h2 style="color:#22d3ee">AI 可以直接做</h2><div class=s>只读不写 · 查询 · 汇总 · 提醒 · 起草</div><ul><li>回答"这个项目决策链还缺谁"</li><li>生成晨报、客户体检报告</li><li>风险发现与到期提醒</li><li>起草话术与材料清单</li></ul></div>
<div class=tier style="background:#3a2f0f;border:2px solid #fbbf24"><h2 style="color:#fbbf24">AI 建议 · 人确认后生效</h2><div class=s>任何写入与变更 · 确认人即责任人</div><ul><li>新增互动记录</li><li>推进商机阶段</li><li>生成跟进计划</li><li>更新联系人档案</li><li>完成交接、调整剧本与规则</li></ul></div>
<div class=tier style="background:#3a1424;border:2px solid #f87171"><h2 style="color:#f87171">只能由人做</h2><div class=s>AI 不参与决定</div><ul><li>对客户的任何承诺与发送</li><li>资源调配、调整负责人</li><li>评价员工、绩效考核</li><li>权限授予</li></ul></div></div>
<div class=foot>所有 AI 参与的操作记录"由哪个助手提出、谁确认"，全程可追溯</div>"""

phases=[('第 0 步','夯实底座','第 1 个月','#fbbf24',['试点区域导入真实数据','明确区域数据管家','开始记录"建议—结果"'],'重点客户与在谈商机全部入库并经区域确认'),
('第 1 步','少填表','第 2–3 个月',C['sense'],['速记员上线','会议纪要 / 邮件匹配','客户体检报告'],'记录量明显上升，AI 整理的记录大多无需大改'),
('第 2 步','系统先开口','第 4–6 个月',C['act'],['每日晨报','作战参谋','公开信息采集','交接包'],'推送有人看、建议有人采纳，逾期与无人负责下降'),
('第 3 步','越用越准','第 6 个月以后',C['learn'],['复盘教练与剧本库','规则校准（人审核）','季度能力报告'],'预测与实际偏差持续缩小，剧本被一线引用')]
pages['07-推进路线'] = """<h1>推进路线：四步走，每步设门槛<small>过了门槛才进入下一步 · 时间为建议值</small></h1>
<style>.ph{display:grid;grid-template-columns:repeat(4,1fr);gap:22px;margin-top:60px}.p{min-height:760px}.p{border-radius:18px;background:#0f2c62;border:1.5px solid #2c5aa0;overflow:hidden;display:flex;flex-direction:column}.p .hd{padding:20px 24px}.p .hd small{font-size:22px;opacity:.8}.p .hd b{display:block;font-size:36px;margin-top:4px}.p .hd i{font-style:normal;font-size:21px;color:#b8cbe8}.p ul{padding:8px 24px;flex:1}.p li{list-style:none;font-size:27px;padding:16px 0;border-bottom:1px dashed #2c5aa0}.gate{margin:18px;padding:20px;border-radius:12px;font-size:24px;line-height:1.5;background:#0b1f45;border:1.5px dashed}.gate b{display:block;font-size:19px;margin-bottom:4px}</style><div class=ph>""" + ''.join(
 f"<div class=p style='border-top:6px solid {c}'><div class=hd><small style='color:{c}'>{a}</small><b style='color:{c}'>{n}</b><i>{t}</i></div><ul>{''.join(f'<li>{x}</li>' for x in items)}</ul><div class=gate style='border-color:{c}88'><b style='color:{c}'>◆ 进入下一步的门槛</b>{g}</div></div>" for a,n,t,c,items,g in phases) + """</div>
<div class=foot>第 0 步没有 AI，但最重要：在样例数据上做 AI 没有意义</div>"""

with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--no-sandbox']); pg = b.new_page(viewport={'width':1920,'height':1080})
    for name, body in pages.items():
        pg.set_content('<meta charset=utf-8>'+BASE+body); pg.wait_for_timeout(200)
        over = pg.evaluate('document.body.scrollHeight')
        pg.screenshot(path=str(OUT/f'{name}.png')); print(name, 'height', over)
    b.close()
