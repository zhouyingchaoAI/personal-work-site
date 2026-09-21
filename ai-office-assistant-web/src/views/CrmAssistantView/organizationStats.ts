export interface OrganizationStats { total: number; important: number; supportive: number; incomplete: number }

// Only aggregate the authorized/scoped inputs. Walk each person's ancestors once;
// malformed cycles cannot count a person twice in the same organization.
export function organizationStats(
  units: { id: string; parent_unit_id?: string }[],
  people: { unit_id: string; importance?: string; support_level?: string }[],
): Map<string, OrganizationStats> {
  const parents = new Map(units.map(unit => [unit.id, unit.parent_unit_id || '']))
  const result = new Map(units.map(unit => [unit.id, { total: 0, important: 0, supportive: 0, incomplete: 0 }]))
  for (const person of people) {
    const visited = new Set<string>()
    let id = person.unit_id
    while (result.has(id) && !visited.has(id)) {
      visited.add(id)
      const stats = result.get(id)!
      stats.total++
      if (person.importance === '重要') stats.important++
      if (['支持', '积极支持'].includes(person.support_level || '')) stats.supportive++
      if (!person.importance?.trim() || !person.support_level?.trim()) stats.incomplete++
      id = parents.get(id) || ''
    }
  }
  return result
}
