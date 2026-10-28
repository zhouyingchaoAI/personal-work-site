import type { CrmStaff } from '../../../src/services/personalWorkApi'
import { normalizeLiaisonRegion, organizationLiaisonRegion } from './liaisonRegions'
import { managementQueue } from './crmCompletion'

export function managementRegionQueue(queue: ReturnType<typeof managementQueue>, staff: CrmStaff[], region: string) {
 if (!region) return queue
 const byKey=new Map<string,CrmStaff[]>()
 for(const p of staff) for(const key of new Set([p.member_key,p.username,p.name].filter(Boolean) as string[])) byKey.set(key,[...(byKey.get(key)||[]),p])
 const profileRegion=(p?:CrmStaff|null)=>organizationLiaisonRegion(p)||normalizeLiaisonRegion(p?.business_region)
 function assigned(key?:string,profile?:CrmStaff|null) {
  if(profile) return profileRegion(profile)
  const matches=byKey.get(key||'')||[]
  const regions=new Set(matches.map(profileRegion))
  return regions.size===1?[...regions][0]:''
 }
 const matches=(value:string|undefined)=>(value||'未分区')===region
 const opportunity=(o:ReturnType<typeof managementQueue>['unassigned'][number])=>matches(assigned(o.manager)||normalizeLiaisonRegion(o.region))
 return {
  overdue:queue.overdue.filter(t=>matches(assigned(t.owner,t.owner_staff))),
  undated:queue.undated.filter(t=>matches(assigned(t.owner,t.owner_staff))),
  scheduled:queue.scheduled.filter(t=>matches(assigned(t.owner,t.owner_staff))),
  stale:queue.stale.filter(x=>opportunity(x.opportunity)),
  unassigned:queue.unassigned.filter(opportunity),
  risks:queue.risks.filter(r=>matches(assigned(r.our_member,r.our_staff))),
 }
}
