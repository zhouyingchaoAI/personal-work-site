// 联合指挥驾驶舱「总体信息」大屏的数据口径。纯函数，便于单测；界面组件只负责呈现。
import type { BusinessAnalysisData, CrmUnit, CrmPerson, CrmRelation, CrmOpportunity, CrmPlaybook } from '../../../../src/services/personalWorkApi'
import { opportunityProbability } from '../opportunityProbability'

export type Followup = CrmPlaybook['followups'][number]
export interface RegionSummary { name: string; units: number; people: number; warnings: number; followups: number }

// 一家客户 = 一个顶级客户组织（无上级）。下级单位 / 部门只是该客户的组织节点，不单独计为客户；
// 不再按 organization_level === 'unit' 统计，否则没有登记下级的公司会从各类客户计数中消失。
export const isCustomerUnit = (unit: CrmUnit) => !unit.parent_unit_id
// 导入数据里“业务状态=丢标/作废”的记录没有同步成 outcome，也不算在谈。
const CLOSED_STATUS = /丢标|作废|取消|终止/
export const isActiveOpportunity = (item: CrmOpportunity) => !item.cancelled && (!item.outcome || item.outcome === 'open') && !CLOSED_STATUS.test(item.status || '')
// 单个商机可参与份额 ≥ 10 亿元视为录入异常（占位值或单位错误），不计入金额合计与重点项目，单独提示核实。
export const SUSPECT_AMOUNT = 100000
export const isAmountSuspect = (item: CrmOpportunity) => Number(item.amount || 0) >= SUSPECT_AMOUNT
export const countedAmount = (item: CrmOpportunity) => isAmountSuspect(item) ? 0 : Number(item.amount || 0)
export const num = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
export const today = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const stageOf = (item: CrmOpportunity) => item.sales_stage || item.stage || '未填阶段'
const amountOf = countedAmount

// 区域卡主题：与地图区域色保持一致；未知区域按顺序轮换。
export const REGION_THEMES: Record<string, 'blue' | 'purple' | 'teal' | 'orange'> = { 东区: 'blue', 西区: 'purple', 中区: 'teal', 广东区: 'orange' }
export const THEME_CYCLE = ['blue', 'purple', 'teal', 'orange'] as const
export function regionTheme(name: string, index: number) { return REGION_THEMES[name] || THEME_CYCLE[index % THEME_CYCLE.length] }

// ---- 经营分析 ----
export interface BusinessIndicator { name: string; target: number | null; value: number | null; rate: number | null; q3Rate: number | null; light: string }
export function businessOverview(business: BusinessAnalysisData | null | undefined) {
  const dash = (business as { dashboard?: Record<string, any> } | null | undefined)?.dashboard || null
  const rows: any[] = dash?.P01_红绿灯 || []
  const find = (name: string) => rows.find(row => row?.指标 === name)
  const indicators: BusinessIndicator[] = ['订货', '管理订货', '财务收入', '回款', '毛利'].map(name => {
    const row = find(name)
    const target = num(row?.全年目标)
    const value = num(row?.实际)
    // 达成率优先取导入的全年完成率；历史版本缺该列时按 实际 / 全年目标 现算。
    const annual = num(row?.全年完成率)
    const rate = annual !== null ? annual * 100 : (target !== null && target > 0 && value !== null ? value / target * 100 : null)
    const q3 = num(row?.Q3完成率)
    return { name, target, value, rate, q3Rate: q3 === null ? null : q3 * 100, light: row?.灯 || '' }
  })
  const aux = dash?.P01_辅助 || {}
  const grossMargin = num(aux.毛利率实际)
  const focusRows = indicators.filter(row => ['订货', '回款', '毛利'].includes(row.name) && row.rate !== null)
  const lowest = [...focusRows].sort((a, b) => a.rate! - b.rate!)[0]
  const tip = !dash ? '待导入经营数据' : lowest ? `${lowest.name}全年达成最低 ${lowest.rate!.toFixed(1)}%` : '暂无可比较的达成率'
  return { available: !!dash, indicators, grossMargin: grossMargin === null ? null : grossMargin * 100, costRatio: num(aux.费效比实际), operatingProfit: num(aux.营业利润), tip }
}

// ---- 五位一体 ----
export const TYPE_ICONS: Record<string, string> = { 厂商: 'vendor', 业主单位: 'owner', 总包单位: 'general', 设计单位: 'design', 主管单位: 'owner' }
export function fiveInOneOverview(units: CrmUnit[], people: CrmPerson[], relations: CrmRelation[]) {
  const customerUnits = units.filter(isCustomerUnit)
  const total = relations.length
  const alarm = relations.filter(r => r.decay_state === 'alarm').length
  const warn = relations.filter(r => r.decay_state === 'warning').length
  const normal = Math.max(0, total - alarm - warn)
  const pct = (value: number) => (total ? value / total * 100 : 0)
  const counts = new Map<string, number>()
  for (const unit of customerUnits) counts.set(unit.type || '未分类', (counts.get(unit.type || '未分类') || 0) + 1)
  const types = [...counts].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([name, value]) => ({ name, value, icon: TYPE_ICONS[name] || '' }))
  return {
    customers: customerUnits.length, contacts: people.length, onlineRelations: total,
    health: [
      { name: '正常', value: normal, percent: pct(normal), color: 'green' },
      { name: '预警', value: warn, percent: pct(warn), color: 'yellow' },
      { name: '告警', value: alarm, percent: pct(alarm), color: 'red' },
    ],
    toMaintain: warn + alarm,
    singleRisk: relations.filter(r => r.single_point_risk).length,
    types,
  }
}

// ---- 商机管理 ----
export function followupCounts(followups: Followup[]) {
  const counts = new Map<string, number>()
  for (const item of followups || []) {
    if (!item.project_id || item.completed_at) continue
    const key = JSON.stringify([(item as { _owner?: string })._owner || '', item.project_id])
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return counts
}
export function probabilityOf(item: CrmOpportunity, counts: Map<string, number>) {
  return opportunityProbability(item, counts.get(JSON.stringify([item._owner || '', item.code])) || 0).probability
}
export function opportunityOverview(opportunities: CrmOpportunity[], followups: Followup[]) {
  const active = opportunities.filter(isActiveOpportunity)
  const counts = followupCounts(followups)
  const talking = active.length
  const amount = active.reduce((sum, item) => sum + amountOf(item), 0)
  const bucket = (item: CrmOpportunity) => { const p = probabilityOf(item, counts); return p >= 70 ? 'high' : p >= 40 ? 'mid' : 'low' }
  const probability = { high: 0, mid: 0, low: 0 }
  for (const item of active) probability[bucket(item)]++
  const stageCounts = new Map<string, number>()
  for (const item of active) stageCounts.set(stageOf(item), (stageCounts.get(stageOf(item)) || 0) + 1)
  const ranked = [...stageCounts].sort((a, b) => b[1] - a[1])
  const stages = ranked.slice(0, 2).map(([name, value], index) => ({ name, value, percent: talking ? value / talking * 100 : 0, color: index ? 'lavender' : 'blue' }))
  const topNames = new Set(stages.map(stage => stage.name))
  const others = active.filter(item => !topNames.has(stageOf(item)))
  const otherBuckets = { high: 0, mid: 0, low: 0 }
  for (const item of others) otherBuckets[bucket(item)]++
  const otherSegments = others.length
    ? ([['high', 'green'], ['mid', 'orange'], ['low', 'red']] as const).map(([key, color]) => ({ percent: otherBuckets[key] / others.length * 100, color })).filter(segment => segment.percent > 0)
    : []
  const unassigned = active.filter(item => !item.manager?.trim()).length
  const tip = !talking ? '暂无在谈商机' : unassigned ? `${unassigned} 条在谈商机待指派负责人` : '在谈商机均已填写负责人'
  return { talking, amount, stages, others: others.length, otherSegments, probability, unassigned, tip }
}

// ---- 项目作战地图 ----
export function projectMapOverview(opportunities: CrmOpportunity[]) {
  const active = opportunities.filter(isActiveOpportunity)
  const amount = active.reduce((sum, item) => sum + amountOf(item), 0)
  const key = active.filter(item => amountOf(item) >= 1000).sort((a, b) => amountOf(b) - amountOf(a))
  const keyAmount = key.reduce((sum, item) => sum + amountOf(item), 0)
  const areas = new Map<string, number>()
  for (const item of key) { const region = (item.region || '').trim() || '未分区'; areas.set(region, (areas.get(region) || 0) + amountOf(item)) }
  return {
    keyProjects: key.length,
    topProjects: key.slice(0, 2).map(item => ({ amount: amountOf(item), name: item.name || item.code || '未命名商机', item })),
    topAreas: [...areas].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([name, value]) => ({ name, value })),
    tip: amount > 0 ? `重点项目占在谈金额 ${(keyAmount / amount * 100).toFixed(1)}%` : '暂无在谈金额可计算占比',
  }
}

// ---- 五类客户布局 / 五类分区 ----
export const CUSTOMER_CATEGORIES = [
  { name: '主管单位', color: '#9d6bff' },
  { name: '业主单位', color: '#f2c14a' },
  { name: '总包单位', color: '#1fd9d9' },
  { name: '设计单位', color: '#2f8dff' },
  { name: '厂商', color: '#ff6a1a' },
]
export function customerLayoutOverview(units: CrmUnit[], people: CrmPerson[]) {
  const customerUnits = units.filter(isCustomerUnit)
  const rows = CUSTOMER_CATEGORIES.map(category => {
    const ids = new Set(units.filter(unit => unit.type === category.name).map(unit => unit.id))
    const count = customerUnits.filter(unit => unit.type === category.name).length
    return { ...category, units: count, contacts: people.filter(person => ids.has(person.unit_id)).length, percent: customerUnits.length ? count / customerUnits.length * 100 : 0 }
  })
  const others = customerUnits.filter(unit => !CUSTOMER_CATEGORIES.some(category => category.name === unit.type)).length
  return { rows, others, total: customerUnits.length, contacts: people.length }
}

// ---- 风险雷达 ----
export function riskOverview(units: CrmUnit[], people: CrmPerson[], relations: CrmRelation[], followups: Followup[], date = today()) {
  const single = relations.filter(r => r.single_point_risk)
  const linked = new Set(relations.map(r => r.person_id))
  const unlinked = people.filter(p => !linked.has(p.id))
  const overdue = (followups || []).filter(a => !a.completed_at && a.due_date && a.due_date.slice(0, 10) < date)
  const peopleById = new Map(people.map(p => [p.id, p])), unitsById = new Map(units.map(u => [u.id, u]))
  const rows = new Map<string, { id: string; name: string; days: number | null; count: number }>()
  for (const relation of relations.filter(r => r.decay_state === 'alarm')) {
    const person = peopleById.get(relation.person_id)
    const id = person?.unit_id || `person:${relation.person_id}`
    const row = rows.get(id) || { id, name: unitsById.get(id)?.name || person?.unit_name || person?.name || relation.person_name || '未关联客户', days: null, count: 0 }
    row.count++
    if (relation.days_since_touch != null && Number.isFinite(relation.days_since_touch)) row.days = Math.max(row.days ?? 0, relation.days_since_touch)
    rows.set(id, row)
  }
  const customers = [...rows.values()].sort((a, b) => (b.days ?? -1) - (a.days ?? -1) || b.count - a.count)
  return { single, unlinked, overdue, customers }
}

// ---- 行动指挥台 / 最近动态 ----
export function activityOverview(followups: Followup[], relations: CrmRelation[], opportunities: CrmOpportunity[], now = new Date()) {
  const pending = (followups || []).filter(a => !a.completed_at)
  const current = today(now)
  const start = new Date(now); start.setDate(now.getDate() - (now.getDay() + 6) % 7)
  const end = new Date(start); end.setDate(start.getDate() + 6)
  const groups = [
    { key: 'today', name: '今日待办', icon: 'today', color: 'var(--cv-cyan)', hint: '未完成且今天到期', rows: pending.filter(a => a.due_date?.slice(0, 10) === current) },
    { key: 'overdue', name: '逾期待办', icon: 'overdue', color: 'var(--cv-red)', hint: '未完成且截止日期早于今天', rows: pending.filter(a => a.due_date && a.due_date.slice(0, 10) < current) },
    { key: 'week', name: '本周计划', icon: 'week', color: '#b68cff', hint: '本周一至周日到期的未完成事项，含本周逾期事项', rows: pending.filter(a => a.due_date && a.due_date.slice(0, 10) >= today(start) && a.due_date.slice(0, 10) <= today(end)) },
    { key: 'coord', name: '需协调', icon: 'flag', color: 'var(--cv-yellow)', hint: '存在单点风险的关系，作为协调线索', rows: relations.filter(r => r.single_point_risk) as unknown[] },
  ]
  const events: { key: string; kind: string; text: string; date: string; time: number }[] = []
  const seen = new Set<string>()
  const add = (key: string, kind: string, text: string, date?: string) => {
    const time = date ? Date.parse(date.replace(' ', 'T')) : NaN
    if (seen.has(key) || !Number.isFinite(time)) return
    seen.add(key); events.push({ key, kind, text, date: date!, time })
  }
  for (const r of relations) for (const a of r.actions || []) add(`a:${r._owner || ''}:${a.id}`, '跟进', `${r.person_name || '客户关系'} · ${a.intel || a.type || '跟进记录'}`, a.happened_at)
  for (const a of followups || []) add(`a:${relations.find(r => r.id === a.relation_id)?._owner || ''}:${a.id}`, '跟进', `${a.person_name || '客户关系'} · ${a.intel || a.next_step || a.type || '跟进记录'}`, a.happened_at)
  for (const o of opportunities) add(`o:${o._owner || ''}:${o.id || o.code}`, '商机', `${o.updated_at && o.updated_at !== o.created_at ? '更新' : '新增'}商机 · ${o.name || o.code}`, o.updated_at || o.created_at)
  events.sort((a, b) => b.time - a.time)
  return { pending, groups, events }
}

export function formatNumber(value: number | null | undefined, decimals = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  return Number(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}
