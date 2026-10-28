import type { CrmOpportunity, CrmPerson, CrmRelation, CrmUnit } from '../../../src/services/personalWorkApi'

// Only group the authorized snapshot supplied by the page. An absent parent
// is not fetched implicitly, and name similarity never establishes ownership.
export function customerPortfolios(units: CrmUnit[], people: CrmPerson[], relations: CrmRelation[], opportunities: CrmOpportunity[]) {
  const byId = new Map(units.map(u => [u.id, u]))
  const roots = new Map<string, string>()
  function root(id: string): string {
    if (roots.has(id)) return roots.get(id)!
    const path: string[] = []
    let current = id
    while (byId.get(current)?.parent_unit_id && byId.has(byId.get(current)!.parent_unit_id!)) {
      if (roots.has(current)) { current = roots.get(current)!; break }
      if (path.includes(current)) { current = path.slice(path.indexOf(current)).sort()[0]!; break }
      path.push(current); current = byId.get(current)!.parent_unit_id!
    }
    roots.set(id, current)
    for (const item of path) roots.set(item, current)
    return current
  }
  const groups = new Map<string, { unit: CrmUnit; units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; opportunities: CrmOpportunity[] }>()
  for (const unit of units) {
    const id = root(unit.id)
    if (!groups.has(id)) groups.set(id, { unit: byId.get(id)!, units: [], people: [], relations: [], opportunities: [] })
    groups.get(id)!.units.push(unit)
  }
  const personRoots = new Map<string, string>()
  for (const person of people) if (byId.has(person.unit_id)) {
    const id = root(person.unit_id); groups.get(id)!.people.push(person); personRoots.set(person.id, id)
  }
  for (const relation of relations) {
    const id = personRoots.get(relation.person_id)
    if (id) groups.get(id)?.relations.push(relation)
  }
  for (const opportunity of opportunities) if (opportunity.owner_unit_id && byId.has(opportunity.owner_unit_id)) {
    groups.get(root(opportunity.owner_unit_id))?.opportunities.push(opportunity)
  }
  return [...groups.values()].sort((a,b) => a.unit.name.localeCompare(b.unit.name, 'zh-CN'))
}

export function calendarDay(value?: string): number | null {
  const day = value?.slice(0, 10) || ''
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null
  const date = new Date(day + 'T00:00:00Z')
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0,10) !== day) return null
  return date.getTime() / 86400000
}

export function opportunityAttention(opportunities: CrmOpportunity[], relations: CrmRelation[], today: string, threshold = 14) {
  const now = calendarDay(today)
  const lastTouches = new Map<string, { day: number; date: string }>()
  for (const relation of relations) for (const action of relation.actions || []) {
    const day = calendarDay(action.happened_at)
    if ((action as { record_kind?: string }).record_kind === 'plan' || !action.project_id || day === null || now === null || day > now) continue
    const key = JSON.stringify([relation._owner || '', action.project_id])
    if (!lastTouches.has(key) || lastTouches.get(key)!.day < day) lastTouches.set(key, { day, date: action.happened_at.slice(0,10) })
  }
  return opportunities.filter(o => !o.cancelled && (!o.outcome || o.outcome === 'open')).map(opportunity => {
    const touch = lastTouches.get(JSON.stringify([opportunity._owner || '', opportunity.code]))
    const created = calendarDay(opportunity.created_at)
    const baseline = touch?.day ?? (created !== null && now !== null && created <= now ? created : null)
    const days = baseline !== null && now !== null ? now - baseline : null
    return { opportunity, days, stale: days !== null && days >= threshold,
      basis: touch ? `最近商机互动 ${touch.date}` : baseline !== null ? `建档后尚未记录商机互动（${opportunity.created_at!.slice(0,10)}）` : '缺少有效建档及互动日期，暂不判断停滞' }
  }).sort((a,b) => Number(b.stale) - Number(a.stale) || (b.days ?? -1) - (a.days ?? -1) || a.opportunity.code.localeCompare(b.opportunity.code))
}
