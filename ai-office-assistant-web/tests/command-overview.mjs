import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const view = new URL('../packages/joint-command/frontend/', import.meta.url)
function load(name, require = () => { throw new Error('Unexpected import: ' + name) }) {
  const exports = {}
  const source = fs.readFileSync(new URL(name, view), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports, require })
  return exports
}
const stages = load('opportunityStages.ts')
const probability = load('opportunityProbability.ts', () => stages)
const m = load('command/commandOverview.ts', () => probability)

// 经营分析：完成率换算为百分数，重点提示取最低完成率
const biz = m.businessOverview({ dashboard: { P01_红绿灯: [
  { 指标: '订货', 实际: 11785.8, 全年目标: 55000, 全年完成率: .2143, Q3完成率: .357, 灯: 'red' },
  { 指标: '回款', 实际: 9917.6, 全年目标: 38000, 全年完成率: .261, Q3完成率: .402, 灯: 'red' },
  { 指标: '毛利', 实际: 1183.3, 全年目标: 6750, Q3完成率: .292, 灯: 'red' },
], P01_辅助: { 毛利率实际: .113, 费效比实际: 1.44, 营业利润: -372 } } })
assert.equal(biz.available, true)
assert.equal(biz.indicators.length, 5)
assert.equal(biz.indicators[0].name, '订货')
assert.equal(biz.indicators[0].target, 55000)
assert.ok(Math.abs(biz.indicators[0].rate - 21.43) < 1e-9, '达成率取导入的全年完成率')
assert.ok(Math.abs(biz.indicators[0].q3Rate - 35.7) < 1e-9)
assert.ok(Math.abs(biz.indicators[4].rate - 1183.3 / 6750 * 100) < 1e-9, '缺全年完成率时按 实际/全年目标 现算')
assert.equal(biz.indicators[1].value, null, '缺失指标保持空值而不是 0')
assert.equal(biz.indicators[1].target, null)
assert.equal(biz.indicators[1].rate, null)
assert.ok(Math.abs(biz.grossMargin - 11.3) < 1e-9)
assert.equal(biz.operatingProfit, -372)
assert.equal(biz.tip, '毛利全年达成最低 17.5%')
assert.equal(m.businessOverview(null).available, false)
assert.equal(m.businessOverview(null).tip, '待导入经营数据')

// 五位一体：关系健康分布与客户类型前四
const units = [
  // 客户 = 顶级客户组织：甲是集团的下级单位，不单独计为客户。
  { id: 'u1', name: '甲', type: '厂商', organization_level: 'unit', parent_unit_id: 'c1' }, { id: 'u2', name: '乙', type: '厂商' }, { id: 'u3', name: '丙', type: '业主单位' },
  { id: 'u4', name: '丁', type: '设计单位' }, { id: 'u5', name: '戊', type: '总包单位' }, { id: 'u6', name: '己', type: '主管单位' },
  { id: 'c1', name: '集团', type: '厂商', organization_level: 'company' },
]
const people = [
  { id: 'p1', unit_id: 'u1', name: '甲一' }, { id: 'p2', unit_id: 'u1', name: '甲二' }, { id: 'p3', unit_id: 'u3', name: '丙一' }, { id: 'p4', unit_id: 'u6', name: '己一' },
]
const relations = [
  { id: 'r1', person_id: 'p1', person_name: '甲一', decay_state: 'alarm', single_point_risk: true, days_since_touch: 414, actions: [{ id: 'a1', intel: '拜访', happened_at: '2026-09-01' }] },
  { id: 'r2', person_id: 'p2', person_name: '甲二', decay_state: 'warning', single_point_risk: false, days_since_touch: 40 },
  { id: 'r3', person_id: 'p3', person_name: '丙一', decay_state: 'normal', single_point_risk: false, days_since_touch: 3 },
  { id: 'r4', person_id: 'p1', person_name: '甲一', decay_state: 'alarm', single_point_risk: false, days_since_touch: 200 },
]
const five = m.fiveInOneOverview(units, people, relations)
assert.equal(five.customers, 6, '下级单位不单独计入客户数，集团本身计一家客户')
assert.equal(five.contacts, 4)
assert.equal(five.onlineRelations, 4)
assert.equal(five.health.map(h => h.value).join(','), '1,1,2')
assert.equal(five.toMaintain, 3)
assert.equal(five.singleRisk, 1)
assert.equal(five.types[0].name, '厂商')
assert.equal(five.types[0].icon, 'vendor')
assert.equal(five.types.length, 4)

// 商机：阶段前二 + 其他阶段按概率分段，未指派提示
const opps = [
  { id: 'o1', code: 'O1', name: '商机一', sales_stage: '合同签订', amount: 500, manager: '张三', outcome: 'open', win_rate: '90' },
  { id: 'o2', code: 'O2', name: '商机二', sales_stage: '合同签订', amount: 1200, manager: '', outcome: 'open', region: '东区', win_rate: '80' },
  { id: 'o3', code: 'O3', name: '商机三', sales_stage: '招标执行', amount: 3000, manager: '李四', outcome: 'open', region: '中区', win_rate: '60' },
  { id: 'o4', code: 'O4', name: '商机四', sales_stage: '立项阶段', amount: 8000, manager: '李四', outcome: 'open', region: '东区', win_rate: '10' },
  { id: 'o5', code: 'O5', name: '已赢', sales_stage: '合同签订', amount: 999, manager: '李四', outcome: 'won' },
  { id: 'o6', code: 'O6', name: '取消', sales_stage: '合同签订', amount: 999, manager: '李四', cancelled: true },
]
const opp = m.opportunityOverview(opps, [])
assert.equal(opp.talking, 4)
assert.equal(opp.amount, 12700)
assert.equal(opp.stages[0].name, '合同签订')
assert.equal(opp.stages[0].value, 2)
assert.equal(opp.stages[0].percent, 50)
assert.equal(opp.stages[1].color, 'lavender')
assert.equal(opp.others, 1)
assert.equal(opp.otherSegments.reduce((s, x) => s + x.percent, 0), 100)
assert.equal(opp.probability.high + opp.probability.mid + opp.probability.low, 4)
assert.equal(opp.tip, '1 条在谈商机待指派负责人')
assert.equal(m.opportunityOverview([], []).tip, '暂无在谈商机')
assert.equal(m.opportunityOverview([], []).otherSegments.length, 0)

// 项目作战地图：≥1000 万重点项目、区域金额前二、占比提示
const map = m.projectMapOverview(opps)
assert.equal(map.keyProjects, 3)
assert.equal(map.topProjects[0].name, '商机四')
assert.equal(map.topAreas[0].name, '东区')
assert.equal(map.topAreas[0].value, 9200)
assert.equal(map.tip, '重点项目占在谈金额 96.1%')

// 五类客户布局
const layout = m.customerLayoutOverview(units, people)
assert.equal(layout.rows.length, 5)
assert.equal(layout.rows.find(r => r.name === '厂商').units, 2)
assert.equal(layout.rows.find(r => r.name === '厂商').contacts, 2)
assert.ok(Math.abs(layout.rows.find(r => r.name === '厂商').percent - 100 / 3) < 1e-9)
assert.equal(layout.others, 0)

// 风险雷达：告警关系按客户去重，取最长未维系天数
const followups = [
  { id: 'f1', relation_id: 'r1', person_name: '甲一', next_step: '回访', due_date: '2026-09-01', project_id: 'O1', happened_at: '2026-08-30' },
  { id: 'f2', relation_id: 'r3', person_name: '丙一', next_step: '送样', due_date: '2026-09-23', happened_at: '2026-09-20' },
  { id: 'f3', relation_id: 'r3', person_name: '丙一', next_step: '已完成', due_date: '2026-09-01', completed_at: '2026-09-02' },
]
const risk = m.riskOverview(units, people, relations, followups, '2026-09-23')
assert.equal(risk.single.length, 1)
assert.equal(risk.unlinked.length, 1, '己一没有关系记录')
assert.equal(risk.overdue.length, 1)
assert.equal(risk.customers.length, 1)
assert.equal(risk.customers[0].name, '甲')
assert.equal(risk.customers[0].days, 414)
assert.equal(risk.customers[0].count, 2)

// 行动指挥台 / 最近动态
const activity = m.activityOverview(followups, relations, opps, new Date(2026, 8, 23, 10))
assert.equal(activity.groups.map(g => g.rows.length).join(','), '1,1,1,1')
assert.equal(activity.events[0].kind, '跟进')
assert.equal(activity.events[0].date, '2026-09-20')
assert.equal(activity.events.filter(e => e.kind === '商机').length, 0, '无时间的商机不进入动态')

assert.equal(m.formatNumber(1307635), '1,307,635')
assert.equal(m.formatNumber(11785.8, 1), '11,785.8')
assert.equal(m.formatNumber(null), '—')
assert.equal(m.regionTheme('西区', 0), 'purple')
assert.equal(m.regionTheme('华北', 2), 'teal')
console.log('PASS: command overview model (business, five-in-one, opportunity, project map, layout, risk, activity)')
