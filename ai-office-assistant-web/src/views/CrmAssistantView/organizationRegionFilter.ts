import type { CrmUnit } from '../../services/personalWorkApi'

function regionsOf(unit: CrmUnit): string[] {
  const regions = Array.isArray(unit.business_regions) ? unit.business_regions.filter(Boolean) : []
  return regions.length ? [...new Set(regions)] : unit.business_region ? [unit.business_region] : ['未分区']
}

/**
 * Keeps a region's organizations connected to their root so both the tree and
 * canvas retain meaningful parent-child paths after filtering.
 */
export function filterOrganizationByRegion(units: CrmUnit[], region: string): CrmUnit[] {
  if (!region) return units
  const byId = new Map(units.map(unit => [unit.id, unit]))
  const included = new Set(units.filter(unit => regionsOf(unit).includes(region)).map(unit => unit.id))
  for (const id of [...included]) {
    const seen = new Set<string>()
    let parentId = byId.get(id)?.parent_unit_id || ''
    while (parentId && !seen.has(parentId)) {
      seen.add(parentId)
      const parent = byId.get(parentId)
      if (!parent) break
      included.add(parent.id)
      parentId = parent.parent_unit_id || ''
    }
  }
  return units.filter(unit => included.has(unit.id))
}
