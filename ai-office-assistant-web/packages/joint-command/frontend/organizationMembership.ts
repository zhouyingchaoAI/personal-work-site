export function personOrganizations(person: { unit_id: string; unit_ids?: string[] }): string[] {
  return [...new Set([person.unit_id, ...(person.unit_ids || [])].filter(Boolean))]
}
