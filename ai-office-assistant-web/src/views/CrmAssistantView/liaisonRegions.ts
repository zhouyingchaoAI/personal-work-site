export const LIAISON_REGION_ORDER = ['东区', '中区', '西区', '广东区'] as const

export type LiaisonRegion = typeof LIAISON_REGION_ORDER[number]
export type OrganizationProfile = {
  company?: string
  department?: string
  position?: string
  title?: string
}

// “广东作战平台”不能用“东区”子串判断，否则“广东区”也会被误归东区。
// 组织架构是人员归属的唯一优先来源；负责区域、客户区域只在组织信息缺失时兜底。
export function organizationLiaisonRegion(profile?: OrganizationProfile | null): LiaisonRegion | '' {
  const organization = [profile?.company, profile?.department, profile?.position, profile?.title].filter(Boolean).join(' ')
  const markers: Array<[LiaisonRegion, string[]]> = [
    ['广东区', ['广东区', '广东作战平台']],
    ['东区', ['东区', '东区作战平台']],
    ['中区', ['中区', '中区作战平台']],
    ['西区', ['西区', '西区作战平台']],
  ]
  return markers.find(([, aliases]) => aliases.some(alias => organization.includes(alias)))?.[0] || ''
}

export function normalizeLiaisonRegion(value?: string | null): LiaisonRegion | '' {
  return LIAISON_REGION_ORDER.includes((value || '') as LiaisonRegion) ? value as LiaisonRegion : ''
}

export function resolveLiaisonRegion(profile?: OrganizationProfile | null, declared?: string | null, customer?: string | null) {
  const organization = organizationLiaisonRegion(profile)
  if (organization) return { region: organization, priority: 3, source: 'organization' as const }
  const explicit = normalizeLiaisonRegion(declared)
  if (explicit) return { region: explicit, priority: 2, source: 'declared' as const }
  const fallback = normalizeLiaisonRegion(customer)
  if (fallback) return { region: fallback, priority: 1, source: 'customer' as const }
  return { region: '未分区', priority: 0, source: 'unassigned' as const }
}
