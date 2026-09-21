import type { CrmQualityRules } from '../../services/personalWorkApi'
import type { OrganizationQuality } from './organizationQuality'
import type { PersonalRelationshipQuality } from './personalRelationshipQuality'
import type { personalOrganizationQuality } from './personalOrganizationQuality'

type PersonalOrg = ReturnType<typeof personalOrganizationQuality>[number]
export interface Distribution { good: number; fair: number; weak: number; pending: number }
export interface DimensionStat { name: string; weight: number; score: number | null; count: number }
export interface RegionStat { name: string; orgs: number; scored: number; avg: number | null; risk: number }
export interface FragileOrg { id: string; name: string; score: number; liaisons: number; reason: string }
export interface AttentionOrg { id: string; name: string; score: number | null; reason: string; risks: number }

const round = (n: number) => Math.round(n)
const avgOf = (values: (number | null)[]) => {
  const real = values.filter((v): v is number => v !== null)
  return real.length ? round(real.reduce((a, b) => a + b, 0) / real.length) : null
}
function distribute(scores: (number | null)[], good: number, fair: number): Distribution {
  const d: Distribution = { good: 0, fair: 0, weak: 0, pending: 0 }
  for (const s of scores) {
    if (s === null) d.pending++
    else if (s >= good) d.good++
    else if (s >= fair) d.fair++
    else d.weak++
  }
  return d
}
function dimensionStats(rows: { dimensions: { name: string; weight: number; score: number | null }[] }[]): DimensionStat[] {
  const order = rows[0]?.dimensions.map(d => d.name) || []
  return order.map((name, i) => {
    const cells = rows.map(r => r.dimensions[i]).filter(Boolean)
    return { name, weight: cells[0]?.weight ?? 0, score: avgOf(cells.map(c => c!.score)), count: cells.filter(c => c!.score !== null).length }
  })
}
function riskTally(lists: string[][]): { label: string; count: number }[] {
  const map = new Map<string, number>()
  for (const list of lists) for (const r of list) map.set(r, (map.get(r) || 0) + 1)
  return [...map].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count)
}

// Read-only synthesis across the three provisional layers. Never mutates inputs; a null layer average means "not enough evidence", not zero.
export function assessmentOverview(
  orgs: OrganizationQuality[],
  personal: PersonalRelationshipQuality[],
  personalOrgs: PersonalOrg[],
  rules: CrmQualityRules,
  now = Date.now(),
) {
  const good = rules.good_threshold, fair = rules.fair_threshold
  const active = (touch: string) => !!touch && now - Date.parse(touch) <= rules.recent_days * 86400000
  const company = {
    count: orgs.length,
    scored: orgs.filter(o => o.score !== null).length,
    avg: avgOf(orgs.map(o => o.score)),
    distribution: distribute(orgs.map(o => o.score), good, fair),
    dimensions: dimensionStats(orgs),
    risks: riskTally(orgs.map(o => o.risks)),
  }
  const personalBlock = {
    count: personal.length,
    scored: personal.filter(p => p.score !== null).length,
    avg: avgOf(personal.map(p => p.score)),
    distribution: distribute(personal.map(p => p.score), good, fair),
    dimensions: dimensionStats(personal),
    overdue: personal.filter(p => p.days !== null && p.days > p.cadence).length,
    risks: riskTally(personal.map(p => p.risks)),
  }
  const personalOrgBlock = {
    count: personalOrgs.length,
    avg: avgOf(personalOrgs.map(o => o.score)),
    soloLiaison: personalOrgs.length,
  }
  // Penetration funnel: customer organizations narrowing from in-scope to full role coverage.
  const engaged = orgs.filter(o => o.relations.length)
  const recentlyActive = engaged.filter(o => active(o.lastTouch))
  const roleCovered = orgs.filter(o => o.roles.length && o.coveredRoles.length === o.roles.length)
  const penetration = [
    { label: '范围内客户组织', value: orgs.length, hint: '含尚未登记对接' },
    { label: '已登记对接', value: engaged.length, hint: '存在关系记录' },
    { label: `近 ${rules.recent_days} 天有互动`, value: recentlyActive.length, hint: '有有效互动证据' },
    { label: '关键岗位覆盖达标', value: roleCovered.length, hint: '按模板全部覆盖' },
  ]
  // Region rollup by customer business region; an organization spanning regions counts in each.
  const regionMap = new Map<string, OrganizationQuality[]>()
  for (const o of orgs) for (const r of o.regions.length ? o.regions : ['未分区']) {
    if (!regionMap.has(r)) regionMap.set(r, [])
    regionMap.get(r)!.push(o)
  }
  const regions: RegionStat[] = [...regionMap].map(([name, list]) => ({
    name, orgs: list.length, scored: list.filter(o => o.score !== null).length,
    avg: avgOf(list.map(o => o.score)), risk: list.filter(o => o.risks.length).length,
  })).sort((a, b) => (b.avg ?? -1) - (a.avg ?? -1))
  // Cross-layer fragility: company relationship reads acceptable but rests on a single liaison or unverified backup.
  const fragile: FragileOrg[] = orgs
    .filter(o => o.score !== null && o.score >= fair && (o.members.length <= 1 || o.risks.includes('主备对接待核实')))
    .map(o => ({ id: o.id, name: o.name, score: o.score!, liaisons: o.members.length, reason: o.members.length <= 1 ? '仅一位我方对接人支撑' : '主备对接待核实' }))
    .sort((a, b) => b.score - a.score)
  // Attention: worst-first, weighing recorded risks then low/absent score, capped for a readable shortlist.
  const attention: AttentionOrg[] = [...orgs]
    .filter(o => o.risks.length || (o.score !== null && o.score < fair))
    .sort((a, b) => b.risks.length - a.risks.length || (a.score ?? 999) - (b.score ?? 999))
    .slice(0, 8)
    .map(o => ({ id: o.id, name: o.name, score: o.score, risks: o.risks.length, reason: o.risks[0] || (o.score !== null && o.score < fair ? '暂估待改善' : '待评估') }))
  return { company, personal: personalBlock, personalOrg: personalOrgBlock, penetration, regions, fragile, attention }
}
export type AssessmentOverview = ReturnType<typeof assessmentOverview>
