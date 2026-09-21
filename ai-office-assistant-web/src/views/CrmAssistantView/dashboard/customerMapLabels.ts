import type { CrmUnit } from '../../../services/personalWorkApi'
import { cityProvince } from './cityProvince'
export type CityCustomers = { city: string; province: string; companies: { name: string; regions: string[] }[] }
export function customerCityGroups(units: CrmUnit[]) {
  const groups = new Map<string, CityCustomers>()
  let missing = 0
  for (const unit of units) {
    const city = (unit.region || '').trim().replace(/市$/, '')
    const province = cityProvince(city)
    // Province-only entries must not be placed at a fictitious city center.
    if (!city || !province || (province === city && !['北京', '天津', '上海', '重庆'].includes(city))) { missing++; continue }
    const name = (unit.company_full_name || unit.name || '').trim()
    if (!name) { missing++; continue }
    const group = groups.get(city) || { city, province, companies: [] }
    const regions = unit.business_regions?.length ? unit.business_regions : [unit.business_region || '']
    const previous = group.companies.find(c => c.name === name)
    if (previous) previous.regions = [...new Set([...previous.regions, ...regions])].filter(Boolean)
    else group.companies.push({ name, regions: [...new Set(regions)].filter(Boolean) })
    groups.set(city, group)
  }
  return { groups: [...groups.values()], missing }
}
