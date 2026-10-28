import type { CrmUnit, CrmPerson } from '../../../src/services/personalWorkApi'
export function organizationRoot(units: CrmUnit[], id: string) {
  const byId = new Map(units.map(u => [u.id, u])), seen = new Set<string>()
  let unit = byId.get(id)
  while (unit?.parent_unit_id && byId.has(unit.parent_unit_id) && !seen.has(unit.id)) {
    seen.add(unit.id); unit = byId.get(unit.parent_unit_id)
  }
  return unit?.id || id
}
export const assignmentKey = (unitId: string, department = '') => JSON.stringify([unitId, department])
export interface AssignmentOption { value: string; label: string; children: AssignmentOption[] }
export function departmentOptions(units: CrmUnit[], people: CrmPerson[], unitId: string): AssignmentOption[] {
  const root = organizationRoot(units, unitId)
  const scope = units.filter(u => organizationRoot(units, u.id) === root)
  const nodes = new Map(scope.map(u => [u.id, { value: assignmentKey(u.id), label: u.name, children: [] as AssignmentOption[] }]))
  for (const u of scope) if (u.id !== root && u.parent_unit_id) nodes.get(u.parent_unit_id)?.children.push(nodes.get(u.id)!)
  const seen = new Set<string>()
  for (const p of people) {
    if (!p.department?.trim() || !nodes.has(p.unit_id)) continue
    const value = assignmentKey(p.unit_id, p.department)
    if (seen.has(value)) continue
    seen.add(value)
    nodes.get(p.unit_id)!.children.push({ value, label: p.department, children: [] })
  }
  return nodes.get(root)?.children || []
}
