import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const load = rel => {
  const exports = {}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(rel, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
  return exports
}
const { assessmentOverview } = load('../packages/joint-command/frontend/assessmentOverview.ts')
const rules = { good_threshold: 80, fair_threshold: 60, recent_days: 90, weights: [30, 25, 20, 15, 10] }
const now = Date.parse('2026-09-20T12:00:00Z')
const dims = (a, b, c) => [
  { name: '关键岗位覆盖', weight: 30, score: a }, { name: '关系质量', weight: 25, score: b },
  { name: '互动有效性', weight: 20, score: c }, { name: '对接稳定性', weight: 15, score: null }, { name: '我方维护责任', weight: 10, score: 100 },
]
const orgs = [
  { id: 'a', name: '甲业主', score: 85, regions: ['东区'], relations: [{}], members: ['张三'], lastTouch: '2026-09-15', roles: ['定技术'], coveredRoles: ['定技术'], risks: [], dimensions: dims(90, 80, 70) },
  { id: 'b', name: '乙设计', score: 70, regions: ['东区', '西区'], relations: [{}], members: ['李四'], lastTouch: '2026-01-01', roles: ['定技术'], coveredRoles: [], risks: ['主备对接待核实', '岗位覆盖待核实'], dimensions: dims(0, 60, null) },
  { id: 'c', name: '丙厂商', score: 40, regions: ['西区'], relations: [{}], members: ['王五', '赵六'], lastTouch: '2026-09-18', roles: [], coveredRoles: [], risks: ['资料待补充'], dimensions: dims(null, 30, 50) },
  { id: 'd', name: '丁待评', score: null, regions: ['东区'], relations: [], members: [], lastTouch: '', roles: ['定技术'], coveredRoles: [], risks: ['对接未登记'], dimensions: dims(null, null, null) },
]
const personal = [
  { id: 'p1', score: 82, days: 5, cadence: 30, risks: [], dimensions: [{ name: '关系质量', weight: 45, score: 82 }, { name: '互动有效性', weight: 30, score: 80 }, { name: '维系及时性', weight: 25, score: 100 }] },
  { id: 'p2', score: 50, days: 90, cadence: 30, risks: ['维系超期'], dimensions: [{ name: '关系质量', weight: 45, score: 50 }, { name: '互动有效性', weight: 30, score: null }, { name: '维系及时性', weight: 25, score: 20 }] },
  { id: 'p3', score: null, days: null, cadence: 30, risks: ['近期互动证据不足'], dimensions: [{ name: '关系质量', weight: 45, score: null }, { name: '互动有效性', weight: 30, score: null }, { name: '维系及时性', weight: 25, score: null }] },
]
const personalOrgs = [{ score: 82 }, { score: null }]
const r = assessmentOverview(orgs, personal, personalOrgs, rules, now)
const eq = (a, b, m) => assert.equal(JSON.stringify(a), JSON.stringify(b), m)

// company block
assert.equal(r.company.count, 4)
assert.equal(r.company.scored, 3)
assert.equal(r.company.avg, Math.round((85 + 70 + 40) / 3), 'company avg ignores pending')
eq(r.company.distribution, { good: 1, fair: 1, weak: 1, pending: 1 })
assert.equal(r.company.dimensions[0].name, '关键岗位覆盖')
assert.equal(r.company.dimensions[0].score, Math.round((90 + 0) / 2), 'dimension avg over non-null cells only')
assert.equal(r.company.dimensions[0].count, 2)
assert.equal(r.company.risks[0].count >= 1, true)

// personal block
assert.equal(r.personal.avg, Math.round((82 + 50) / 2))
assert.equal(r.personal.overdue, 1, 'p2 is overdue')
eq(r.personal.distribution, { good: 1, fair: 0, weak: 1, pending: 1 })

// penetration funnel
eq(r.penetration.map(s => s.value), [4, 3, 2, 1], 'total → engaged → recent → role covered')

// regions (东区 has a,b,d; 西区 has b,c)
const east = r.regions.find(x => x.name === '东区')
assert.equal(east.orgs, 3)
assert.equal(east.avg, Math.round((85 + 70) / 2), 'east avg over scored a,b')
assert.equal(east.risk, 2, 'b and d carry risks in east')

// fragility: a (1 liaison, score 85) and b (backup risk, score 70) qualify; c has 2 liaisons and score<fair
const fragileIds = r.fragile.map(f => f.id)
eq(fragileIds, ["a", "b"], 'high-value but thin, worst-value first')
assert.equal(r.fragile[0].reason, '仅一位我方对接人支撑')

// attention: risk-bearing first; d and b have risks, c has 1 risk
assert.equal(r.attention[0].risks >= r.attention[r.attention.length - 1].risks, true, 'attention sorted by risk count desc')
assert.ok(r.attention.every(a => a.reason))

console.log('PASS assessment overview: distributions, dimension averages, penetration funnel, regions, cross-layer fragility, attention')
