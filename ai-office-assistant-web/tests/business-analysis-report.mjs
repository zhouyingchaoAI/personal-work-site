import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const source = fs.readFileSync(new URL('../packages/joint-command/frontend/businessAnalysisReport.ts', import.meta.url), 'utf8')
const exports = {}
const regionTones = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/businessRegionTone.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: regionTones })
assert.equal(regionTones.businessRegionTone('集成 · 东区-江苏'), 'east')
assert.equal(regionTones.businessRegionTone('广东作战平台'), 'guangdong')
assert.equal(regionTones.businessRegionTone('张经理 · 回款 · 西区'), 'west')
assert.equal(regionTones.businessRegionTone('中区'), 'central')
assert.equal(regionTones.businessRegionTone('东区外部'), '')
assert.equal(regionTones.businessRegionTone('东区 / 西区'), '')
assert.equal(regionTones.businessRegionTone('湖南'), '')
const mapColors = fs.readFileSync(new URL('../packages/joint-command/frontend/dashboard/chinaMapData.ts', import.meta.url), 'utf8')
const businessStyles = fs.readFileSync(new URL('../packages/joint-command/frontend/businessDashboard.scss', import.meta.url), 'utf8')
for (const [tone, region] of Object.entries(regionTones.businessRegionLabels)) {
  const color = mapColors.match(new RegExp(`${region}: '(#[0-9a-f]+)'`))?.[1]
  assert.ok(color && businessStyles.includes(`[data-region-tone="${tone}"] { --region-accent:${color}; }`), `${region}与五位一体配色一致`)
}
const charts = {}
const cartesian = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/businessCartesianChart.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: cartesian })
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/businessReportCharts.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: charts, require: () => cartesian })
const trend = cartesian.cartesianChart([{name:'1月',amount:10},{name:'2月',amount:null},{name:'3月',amount:-5}], [{key:'amount',label:'回款',color:'#123456'}], {name:'name',title:'回款趋势',unit:'万元',line:true})
assert.ok(trend.includes('万元') && trend.includes('-5') && trend.includes('3月'))
assert.match(trend, /d="M[^"L]+M[^"L]+"/)
const annualTrend = cartesian.cartesianChart(Array.from({length:12},(_,index)=>({month:`${index+1}月`,amount:index+1})),[{key:'amount',label:'订货',color:'#123456'}],{name:'month',title:'全年趋势',unit:'万元',line:true,width:1100})
assert.equal((annualTrend.match(/<svg/g)||[]).length,1)
assert.equal((annualTrend.match(/<circle/g)||[]).length,12)
assert.ok(annualTrend.includes('12月') && annualTrend.includes('viewBox="0 0 1100 340"'))
assert.ok(annualTrend.includes('stroke-linecap="round"'))
assert.equal(cartesian.smoothLinePath([{x:0,y:10},{x:10,y:30},null,{x:30,y:5},{x:40,y:0}]), 'M0,10 C5,10 5,30 10,30  M30,5 C35,5 35,0 40,0')
const icons = {}
const completeRows = Array.from({ length: 65 }, (_, index) => ({ 项目: `完整项目${index}`, 金额: index + 1, '销售合同金额(未税)': index + 1 }))
const completeChart = charts.reportChart(completeRows, [['项目', '项目', 'text'], ['销售合同金额(未税)', '金额', 'money']], '已完成订单')
assert.equal((completeChart.match(/class="br-plot-row"/g) || []).length, 65)
assert.ok(completeChart.includes('完整项目64'))
assert.ok(!completeChart.includes('预览前'))
const regionChart = charts.reportChart(completeRows, [['项目', '项目', 'text'], ['金额', '金额', 'money']], '全部区域')
assert.equal((regionChart.match(/class="br-plot-row"/g) || []).length, 65)
assert.ok(!regionChart.includes('br-columns'))
assert.equal((regionChart.match(/class="br-horizontal-axis"/g) || []).length, 1, '全部分类共享一个坐标轴')
assert.ok(regionChart.includes('br-comparison'), '统一对齐比较，不拆成独立小卡片')
const textChart = charts.reportChart([{ 项目: '<项目>' }], [['项目', '项目', 'text']], '项目明细')
assert.ok(textChart.includes('&lt;项目&gt;'))
const viewSource = fs.readFileSync(new URL('../packages/joint-command/frontend/BusinessAnalysis.vue', import.meta.url), 'utf8')
assert.ok(!viewSource.includes('el.hidden = i >= 5'))
const quality = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/businessDataQuality.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: quality })
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/businessIcons.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: icons })
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports, require: (name) => name.includes('businessIcons') ? icons : name.includes('businessDataQuality') ? quality : charts })
const { renderBusinessReport: render, formatBusinessCell: fmt } = exports
const expenses = render({P06_费用构成:[{科目:'差旅',金额:20},{科目:'薪酬',金额:80},{科目:'合计',金额:100}]}, [])
assert.ok(expenses.includes('实际费用合计') && expenses.includes('100.0'))
assert.ok(expenses.indexOf('薪酬 · 80.0%') < expenses.indexOf('差旅 · 20.0%'))
assert.ok(!expenses.includes('200.0'), '合计行不重复计入')
const missingExpenses = render({P06_费用构成:[{科目:'差旅',金额:null},{科目:'薪酬',金额:80}]}, [])
assert.ok(missingExpenses.includes('已提供费用小计') && missingExpenses.includes('不适用'))
const profitReport = render({P04_损益全表:[{科目:'财务收入',公司:10000,利润核算角度:10000},{科目:'财务收入毛利',公司:1000,利润核算角度:900},{科目:'销售费用',公司:100,利润核算角度:100},{科目:'公司销售平台',公司:50,利润核算角度:50},{科目:'营业利润',公司:-200,利润核算角度:-200}]}, [])
const profitBlock = profitReport.split('class="be-management-board"')[1].split('data-section="taskOrder"')[0]
assert.ok(!profitBlock.includes('经营规模参考') && !profitBlock.includes('be-scale'), '移除经营规模参考板块')
for (const subject of ['财务收入毛利', '销售费用', '公司销售平台', '营业利润']) assert.ok(profitBlock.includes(subject))
assert.ok(profitBlock.includes('利润来源 · 费用消耗 · 营业利润'))
assert.ok(!profitBlock.includes('01 利润来源') && !profitBlock.includes('02 费用消耗'))
assert.ok(profitBlock.includes('不再扣减一次'))
assert.ok(profitBlock.includes('-200'))
const mergedProfit = profitBlock.split('be-profit-panel be-combined')[1].split('</section>')[0]
assert.equal((mergedProfit.match(/class="br-cartesian"/g) || []).length, 1, '来源、费用和结果合并同一坐标')
for (const subject of ['收入毛利', '销售费用', '营业利润']) assert.ok(mergedProfit.includes(subject))
assert.ok(expenses.includes('data-chart-kind="donut"'), '完整非负费用同时展示构成占比')
assert.ok(!missingExpenses.includes('data-chart-kind="donut"'), '缺失费用不计算饼图占比')
const grouped = exports.businessGroups([{产业:'服务2.0',区域:'西区作战平台',责任人:'乙'}, {产业:'集成',区域:'广东',责任人:'丙'}, {产业:'集成',区域:'东区-江苏',责任人:'甲'}, {区域:'东区',责任人:'未知产业'}])
assert.equal(grouped.map(group=>group.industry+'/'+group.region).join(','), '集成/东区,集成/广东区,服务/西区,产业待确认/东区')
assert.equal(grouped.reduce((sum,group)=>sum+group.rows.length,0), 4)
const regionalOwners = render({}, [{key:'任务令区域进度',headers:['区域','责任人','指标','任务令','合计完成'],rows:[['东区','甲经理','订货',100,20],['东区','甲经理','回款',50,10],['东区-江苏','乙经理','财务收入',80,30]]}])
assert.ok(regionalOwners.includes('br-owner-grid'))
assert.equal((regionalOwners.match(/<h4>甲经理<\/h4>/g) || []).length,0)
assert.ok(regionalOwners.includes('甲经理'))
assert.ok(regionalOwners.indexOf('东区总体') < regionalOwners.indexOf('<h4>乙经理</h4>'))
assert.ok(regionalOwners.includes('<h4>乙经理</h4>'))
const totalAndOwners = render({}, [{key:'任务令区域进度',headers:['区域','责任人','指标','任务令','合计完成'],rows:[['合计','','订货',100,20],['东区','甲经理','订货',100,20],['东区-江苏','乙经理','订货',100,20]]}])
assert.ok(totalAndOwners.indexOf('区域任务总体进度') < totalAndOwners.indexOf('东区总体'))
assert.ok(!totalAndOwners.includes('<h3>合计</h3>'))
assert.ok(totalAndOwners.includes('20.0<small> / 100.0'), '直接使用总计行，不累加区域和子区域')
const scaledOwners = render({}, [{key:'任务令区域进度',headers:['区域','责任人','指标','任务令','合计完成'],rows:[['东区','大任务','回款',1000,200],['西区','小任务','回款',100,20]]}])
const smallPanel = scaledOwners.split('<h4>西区总体</h4>')[1].split('</section>')[0]
assert.ok(smallPanel.includes('width:10%'), '小任务使用所有个人图表的共同尺度，不放大为满格')
assert.ok(smallPanel.includes('1,000'), '各个人图表使用相同轴上限')
const ownerProgress = render({}, [{key:'任务令责任人进度',headers:['角色','区域','责任人','指标','任务令','合计完成'],rows:[['客户经理','东区','甲','订货',1000,200],['客户经理','东区','甲','回款',500,100],['项目经理','西区','乙','财务收入',100,20]]}])
assert.ok(ownerProgress.includes('br-regional-tasks'))
assert.equal((ownerProgress.match(/<h4>甲<\/h4>/g) || []).length, 1, '同一责任人的指标集中展示')
assert.ok(ownerProgress.split('<h4>乙</h4>')[1].split('</article>')[0].includes('width:10%'), '责任人面板使用全体统一刻度')
const owners = charts.reportChart([{角色:'客户经理',指标:'订货',区域:'东区',责任人:'张经理',任务令:100,合计完成:20}], [['角色','角色','text'],['指标','指标','text'],['区域','区域','text'],['责任人','责任人','text'],['任务令','任务令'],['合计完成','累计完成']], '责任人任务推进')
assert.ok(owners.includes('张经理 · 客户经理 · 订货 · 东区'), '姓名优先且保留角色、指标与区域')
const industrySplit = render({P05_产业:[{产业:'集成',订货:100},{产业:'服务1.0',订货:200},{产业:'服务2.0',订货:300},{产业:'场研',订货:400},{产业:'其他',订货:50}]}, [])
const industryQuality = render({
  P05_子产业:[{大产业:'集成',子产业:'轨道',订货:120,毛利:20,毛利率:1/6}],
  P09_项目属性:[{产业:'服务',属性:'自行拓展',订货:30,毛利:6,现金流:-8,毛利率:.2,回款转化率:null,收入转化率:.5}],
  P07_预付分产业:[{产业:'集成',年份:2026,'预付≥30%金额占比':.4}],
  P07_账龄:[{产业:'集成',年份:2026,M1:.1,M3:.3,M6:null}],
}, [])
const qualityCharts = industryQuality.split('<div class="be-industry-quality">')[1].split('<div class="br-industry-group"')[0]
for (const title of ['子产业订货与毛利贡献','项目属性：规模与资金质量','合同质量：预付与回款周期']) assert.ok(qualityCharts.includes(title))
assert.ok(qualityCharts.includes('轨道'))
assert.ok(qualityCharts.includes('自行拓展'))
assert.ok(qualityCharts.includes('-8'))
assert.ok(qualityCharts.includes('未提供'))
assert.ok(!industryQuality.includes('data-chart-title="子产业与项目属性"'))
assert.deepEqual([...industrySplit.matchAll(/data-industry="([^"]+)"/g)].map(match=>match[1]), ['集成','服务','场研','其他'])
const servicePart = industrySplit.split('data-industry="服务"')[1].split('data-industry="场研"')[0]
assert.ok(servicePart.includes('服务1.0') && servicePart.includes('服务2.0') && !servicePart.includes('>集成<'))
assert.equal(quality.taskEvidence({ '是否已回款': 0 }, '回款'), '未提供完成证据')
assert.equal(quality.taskEvidence({ '是否已签合同': true }, '订货'), '待补证据')
assert.equal(quality.taskEvidence({ '合同签订金额': 100, '合同签订日期': '2026-10-01', '合同编号': 'C001' }, '订货'), '待核验凭证')
const qualityResult = quality.businessDataQuality([
  { key: '订货任务令', headers: ['是否已签合同', '*机会点名称'], rows: [[true, '项目A'], [false, '项目B']] },
  { key: '01_核心指标总览', headers: ['指标', '实际完成'], rows: [['订货', 100]] },
  { key: '任务令公司进度', headers: ['指标', '1-10月完成'], rows: [['订货', 80]] },
])
assert.equal(qualityResult.issues.length, 2)
assert.equal(qualityResult.comparisons[0].difference, 20)
const data = {
  P01_红绿灯: [{ 指标: '订货', 实际: 40, 全年目标: 100, Q3目标: 60, '10月预估': 15 }],
  P04_目标达成: [{ 平台: '东区', Q3订货任务令: 100, 实际订货: 80, 管理订货: 30 }],
  P05_产业: [{ 产业: '集成', 订货目标: 50000, 订货: 10250, 毛利: 960 }, { 产业: '合计', 订货: 50 }],
  P08_省份: Array.from({length: 12}, (_, i) => ({ 省份: `省份${i}`, 订货: i ? i * 10 : 0, 现金流: -10 })),
  P06_预算执行: [{ 平台: '联指', Q3费用目标: 100, 已使用: 120, 剩余: -20, 使用率: 1.2 }],
}
const sheets = [
  ...Array.from({length:19}, (_, i) => ({ key: `${String(i+1).padStart(2,'0')}_测试`, title: '测试', source: '', headers: ['名称','达标订单量','毛利率'], rows: [['<img onerror=evil()>', 8, .2]] })),
  { key: '订货任务令', title: '订货任务令', source: '', headers: ['*机会点名称', '*可参与份额-总额(万元)'], rows: [['订货项目', 27003.6253]] },
  { key: '回款任务令', title: '回款任务令', source: '', headers: ['销售子项目名称', '本月计划回款金额'], rows: [['回款项目', 79202251.33799483]] },
  { key: '财务收入任务令', title: '财务收入任务令', source: '', headers: ['销售子项目名称', '收入金额（含税）'], rows: [['收入项目', 44112981.33]] },
  { key: '任务令公司进度', title: '任务令公司进度', source: '', headers: ['指标','年度目标','1-10月完成','年度完成率','年度缺口','本月任务令','本月完成','本月完成率','本月排名','本月缺口'], rows: [['回款',38000,13433.46,.3535,-24566.54,3960.11,138.42,.03495,2,-3821.69]] },
  { key: '任务令区域进度', title: '任务令区域进度', source: '', headers: ['层级','指标','区域','责任人','任务令','第一周完成','第二周完成','第三周完成','第四周完成','合计完成','完成率','排名','缺口'], rows: [['区域','回款','广东','黄宇',414.53,70,4.92,0,0,74.92,.1807,1,-339.61]] },
  { key: '任务令责任人进度', title: '任务令责任人进度', source: '', headers: ['角色','指标','区域','责任人','任务令','第一周完成','第二周完成','第三周完成','第四周完成','合计完成','完成率','排名','缺口'], rows: [['项目经理','回款','广东','孙良珑',414.53,70,4.92,0,0,74.92,.1807,1,-339.61]] },
  { key: '任务令总表说明', title: '任务令总表说明', source: '', headers: ['报表标题','数据截止','单位'], rows: [['2026年10月冲刺任务令简报','2026-10-18','万元']] },
  { key: '任务令进度总表原表', title: '任务令进度总表原表', source: '', headers: ['行号','第1列','第2列'], rows: [[1,'2026年10月冲刺任务令简报','数据截止：2026-10-18'],[12,'二、区域 - 10月订货冲刺任务令','']] },
]
const html = render(data, sheets)
assert.deepEqual([...html.matchAll(/data-section="([^"]+)"/g)].map(m=>m[1]), ['overall','taskOrder','structure','region','industry','foundation','projects'])
assert.ok(html.includes('27,003.6'), '订货任务令的万元字段不得再次除以10000')
assert.ok(html.includes('7,920.2'), '回款任务令的元字段必须折算为万元')
assert.ok(html.includes('4,411.3'), '财务收入任务令的元字段必须折算为万元')
assert.ok(html.includes('公司年度目标进度') && html.includes('本月任务令兑现'), '任务令页应展示总表公司进度图表')
assert.ok(html.includes('区域任务推进') && html.includes('责任人任务推进'), '任务令页应展示区域和责任人进度图表')
assert.ok(!html.includes('data-chart-title="任务令简报信息"'), '任务令页暂不展示简报信息卡片')
assert.ok(html.includes('任务进度总表完整原表'), '任务令页应保留完整原表')
assert.equal([...html.matchAll(/data-chart-title=/g)].length,24,'保留产业对比图，不生成无数据的产业质量卡片')
for (const title of ['产业订货目标与完成', '产业毛利留存对比', '产业投入与贡献']) assert.ok(html.includes(`data-chart-title="${title}"`))
assert.ok(!html.includes('be-target-matrix'), '公司整体不重复展示年度目标表')
assert.ok(html.includes('利润从哪里产生、被哪些费用消耗'))
assert.ok(!html.includes('data-chart-title="目标、完成与预测"'))
assert.ok(html.includes('class="br-kpi"'))
assert.ok(!html.includes('地区生产总值'), '不能虚构不存在的宏观指标')
assert.ok(html.includes('达成率 30.0%'), '管理订货任务必须用管理订货30，而不是实际订货80')
assert.ok(!html.includes('达成率 80.0%'))
assert.ok(html.includes('目标 50,000.0 · 当前 10,250.0'))
assert.ok(html.includes('达成率 20.5%'), '产业目标与实际计算达成，不误标未设置')
assert.ok(html.includes('相差 10.0 万元'), '不同范围合计须明确说明')
assert.ok(html.includes('省份11'), '不能只显示TOP8而丢失其余省份')
assert.ok(html.includes('省份0'), '零订货省份仍保留')
const accessible = [...html.matchAll(/data-(?:source-ids|chart-sources)="([^"]+)"/g)].flatMap(m => m[1].split(','))
assert.ok(new Set(accessible).size >= 19, '原有19张经营来源表都可从数据弹窗访问')
for (const key of ['任务令公司进度','任务令区域进度','任务令责任人进度','订货任务令','回款任务令','财务收入任务令']) assert.ok(html.includes(key), `${key}可从任务令图表访问`)
assert.ok(!html.includes('<img onerror=evil()>'))
assert.ok(html.includes('data-chart-kind="grouped-bars"'))
assert.ok(html.includes('data-chart-kind="diverging"'))
assert.ok(html.includes('<template data-analysis-table>'), '数据表必须位于不可见template，点击图表才展示')
const escaped = charts.reportChart([{name:'<img onerror=evil()>',value:10}], [['name','名称','text'],['value','数值']], '转义')
assert.ok(escaped.includes('&lt;img onerror=evil()&gt;') && !escaped.includes('<img onerror=evil()>'))
assert.ok(charts.reportChart([{科目:'薪酬',金额:10}], [['科目','科目','text'],['金额','金额']], '费用构成').includes('data-chart-kind="donut"'))
const pie = charts.reportChart([{阶段:'跟进',可参与份额:30},{阶段:'投标',可参与份额:70},{阶段:'合计',可参与份额:100}], [['阶段','阶段','text'],['可参与份额','可参与份额']], '机会阶段')
assert.ok(pie.includes('data-chart-kind="pie"'), '阶段占比用饼图')
assert.ok(pie.includes('30.0%') && pie.includes('70.0%'), '总计行不能重复计入占比')
const allStages = charts.reportChart(Array.from({length:8},(_,i)=>({阶段:`阶段${i}`,可参与份额:10})), [['阶段','阶段','text'],['可参与份额','可参与份额']], '机会阶段')
assert.ok(allStages.includes('阶段7') && !allStages.includes('其他阶段'), '全部阶段逐项展示，不合并隐藏')
assert.ok(!charts.reportChart([{阶段:'负值',可参与份额:-1}], [['阶段','阶段','text'],['可参与份额','可参与份额']], '机会阶段').includes('data-chart-kind="pie"'), '负数不能绘制饼图')
assert.ok(charts.reportChart([{年份:2026,M1:.2}], [['年份','年','text'],['M1','回款率','percent']], '回款转化').includes('20.0%'))
assert.ok(html.includes('120.0%'), '费用超支不可截为100%')
assert.equal(fmt(8, '达标订单量'), '8')
assert.equal(fmt(.2, '毛利率'), '20.0%')
assert.equal(fmt(5.26, '费效比'), '5.26')
assert.equal(fmt(null, '毛利'), '未提供')
const empty = render({ P05_产业: [{产业:'零目标',订货目标:0,订货:1}] })
assert.ok(empty.includes('达成率 未提供'))
assert.ok(!empty.includes('NaN') && !empty.includes('Infinity'))
const incomplete = render({P04_目标达成:[{平台:'缺失实际',Q3订货任务令:100,实际订货:80}]})
assert.ok(incomplete.includes('达成率 未提供') && incomplete.includes('缺口 未提供万元'), '缺管理订货不得回退为实际订货或零')
console.log('PASS business report: scopes, targets, missing values, full coverage, escaping, units')
const regionalOverview = render({}, [{
  key: '本次区域经营汇总',
  headers: ['区域', '订货', '管理订货', '财务收入', '回款', '毛利'],
  rows: [['东区', 100, 80, 60, 50, -10]],
}])
assert.ok(regionalOverview.includes('本次导入 · 区域经营对比'))
assert.ok(regionalOverview.includes('data-chart-sources="本次区域经营汇总"'))
assert.ok(regionalOverview.includes('本次区域经营对比'))
assert.ok(regionalOverview.includes('-10.0'))
console.log('PASS overall regional chart and exact source linkage')
const personalPanel = render(data, [
  { key: '19_已完成订单明细', headers: ['销售项目名称', '销售合同金额'], rows: [['本人项目', 100000]] },
], 'personal')
assert.deepEqual([...personalPanel.matchAll(/data-section="([^"]+)"/g)].map(match => match[1]), ['overall', 'taskOrder', 'projects'])
assert.ok(personalPanel.includes('我的经营总览'))
assert.ok(personalPanel.includes('10.0'))
assert.ok(!personalPanel.includes('公司损益'))
assert.ok(personalPanel.includes('非年度累计口径'))
const regionalPanel = render({}, [{ key: '本次区域经营汇总', headers: ['区域','订货','回款'], rows: [['东区',100,50]] }], 'region')
assert.ok(regionalPanel.includes('授权区域经营结果'))
assert.ok(!regionalPanel.includes('公司年度目标'))
assert.ok(render({}, [], 'personal').includes('暂无明确归属的数据'))
assert.ok(!regionalOverview.includes('class="br-quality"'))
assert.ok(!regionalOverview.includes('年度进度：'))
assert.ok(!regionalOverview.includes('费用控制：'))
const overallPage = regionalOverview.split('data-section="overall"')[1].split('data-section="taskOrder"')[0]
assert.ok(!overallPage.includes('本次导入 · 区域经营对比'))
assert.ok(!html.includes('data-chart-title="任务进度总表完整原表"'))
assert.ok(!html.includes('其他导入数据'))
assert.ok(!html.includes('公司费用预算'), '经营结构不再展示公司费用预算图')
assert.ok(html.includes('data-chart-title="费用构成"'), '保留费用构成')
for (const label of ['区域预算', '平台分摊']) {
  const rendered = charts.reportChart([
    { 平台: '东区作战平台', Q3费用目标: 405, 已使用: 353.5, 合计: 353.5, 管理平台分摊: 119.7, 销售平台分摊: 104.4 },
  ], [['平台', '平台', 'text'], ['Q3费用目标', 'Q3费用预算'], ['已使用', '已使用'], ['合计', '费用合计'], ['管理平台分摊', '管理平台分摊'], ['销售平台分摊', '销售平台分摊']], label)
  assert.ok(rendered.includes('br-cartesian') && rendered.includes('<rect'), `${label}使用带坐标轴的分组柱状图`)
  assert.ok(rendered.includes('万元') && rendered.includes('<line'), '展示单位、坐标轴及网格刻度')
  assert.ok(rendered.includes('东区作战平台'))
  assert.ok(rendered.includes('353.5'))
}
const compositionColumns = [['科目','科目','text'], ['金额','金额']]
for (const mode of ['pie', 'donut']) {
  const output = charts.renderReportChart([{科目:'差旅',金额:20},{科目:'薪酬',金额:80}], compositionColumns, '费用构成', undefined, mode)
  assert.ok(output.includes(`data-chart-kind="${mode}"`))
  const invalid = charts.renderReportChart([{科目:'调整',金额:-20}], compositionColumns, '费用构成', undefined, mode)
  assert.ok(invalid.includes('当前保留原图'))
}
console.log('PASS composition switching and negative-value safeguards')
const authoritativeSheets = [
  {key:'区域经营_年度指标',headers:['区域','负责人','指标','目标','实际'],rows:[['东区','董涛','订货',25000,7723.194844]]},
  {key:'区域经营_月度实绩',headers:['区域','月份','订货','财务收入','回款'],rows:[['东区','1月',100,200,300]]},
  {key:'区域经营_回款计划',headers:['区域','计划月份','预计回款'],rows:[['东区','2026年3月',2161.58620935]]},
]
const updatedReport = exports.renderBusinessReport({}, authoritativeSheets)
const regionalSection = updatedReport.split('data-section="region"')[1].split('data-section="industry"')[0]
assert.ok(regionalSection.includes('年度目标与完成'))
assert.ok(regionalSection.includes('完成率（右轴）'))
assert.ok(regionalSection.includes('<th>排名</th>'))
assert.ok(regionalSection.includes('差额（实际−目标）'))
assert.ok(regionalSection.includes('双轴组合图'))
assert.ok(regionalSection.includes('3月回款计划（非实际）'))
assert.ok(!regionalSection.includes('区域费用、分摊与预算'))
assert.ok(exports.renderScopedBusinessReport(authoritativeSheets,'region').includes('年度目标与完成'))
console.log('PASS authoritative regional source replaces historical charts in company and regional views')
const periodReport = exports.renderBusinessReport({}, [
  {key:'区域经营_年度指标',headers:['区域','负责人','指标','目标','实际','完成率','差额','期间','目标说明'],rows:[['东区','董涛','回款',null,63.50856,null,null,'10月','原表未提供目标']]},
  {key:'区域经营_期间指标',headers:['区域','期间'],rows:[['东区','10月']]},
])
assert.ok(periodReport.includes('10月 · 区域经营总览'))
assert.ok(periodReport.includes('本期间未提供目标'))
assert.ok(!periodReport.includes('3月回款计划（非实际）'))
assert.ok(periodReport.includes('四区域经营一览'))
assert.ok(!periodReport.includes('经营关注'))
assert.ok(periodReport.includes('订货 · 收入 · 回款对比'))
assert.equal((periodReport.match(/br-kpi rx-kpi/g) || []).length, 5)
console.log('PASS period labels, missing targets and removal of stale plan chart')
const progressReport = exports.renderBusinessReport({}, [
  {key:'区域经营_年度指标',headers:['区域','指标','实际','目标','完成率','差额','期间'],rows:[['东区','订货',136,100,1.36,36,'全年'],['西区','订货',50,100,.5,-50,'全年'],['中区','订货',null,null,null,null,'全年']]},
  {key:'区域经营_期间指标',headers:['区域','期间'],rows:[['东区','全年']]},
])
assert.ok(progressReport.includes('136.0% · 达标'))
assert.ok(progressReport.includes('rx-design-meter achieved'))
assert.ok(progressReport.includes('aria-valuenow="50"'))
assert.ok(progressReport.includes('rx-rate-missing'))
assert.ok(progressReport.includes('rx-overlay-fill'))
assert.ok(!progressReport.includes('rx-amount-bar'))
assert.ok(progressReport.includes('订货 → 管理订货（折算后）'))
assert.ok(!progressReport.includes('rx-conversion-cell'))
assert.ok(progressReport.includes('/region-order.png'))
assert.ok(progressReport.includes('rx-design-meter'))
assert.ok(progressReport.includes('实际折算比例'))
assert.ok(progressReport.includes('rx-conversion-ratio'))
console.log('PASS matrix amount comparison, percentage meters, overachievement and missing values')
