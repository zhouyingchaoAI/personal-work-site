import type { CrmManagerView, CrmStaff, CrmRelation, CrmPerson, CrmUnit } from '../../../src/services/personalWorkApi'
import { organizationLiaisonRegion, normalizeLiaisonRegion } from './liaisonRegions'
export function managerReviewOptions(accounts:CrmManagerView[], staff:CrmStaff[], relations:CrmRelation[], _people:CrmPerson[], _units:CrmUnit[]) {
 const staffByAccount = new Map<string, CrmStaff[]>(), staffByKey = new Map<string, CrmStaff[]>()
 const relationsByAccount = new Map<string, CrmRelation[]>(), relationsByKey = new Map<string, CrmRelation[]>()
 function add<T>(index: Map<string, T[]>, key: string | undefined, value: T) {
  if (!key) return
  const values = index.get(key)
  if (values) values.push(value)
  else index.set(key, [value])
 }
 for (const s of staff) { add(staffByAccount, s.username, s); add(staffByKey, s.member_key, s) }
 for (const r of relations) { add(relationsByAccount, r.our_staff?.username, r); add(relationsByKey, r.our_member, r) }
 // The API resolves legacy name-based relationship keys to one unique account.
 // Keep those keys as aliases of that account so the person is not emitted again
 // as a pseudo liaison (or classified by a customer's region).
 const managers=accounts.map(m=>({...m,member_keys:[...new Set([
  ...m.member_keys,
  ...(staffByAccount.get(m.username) || []).map(s=>s.member_key),
  ...(relationsByAccount.get(m.username) || []).map(r=>r.our_member),
 ])]}))
 const known=new Set(managers.flatMap(m=>m.member_keys))
 // CRM may contain a genuine liaison without a system login. Never merge by name.
 for(const key of new Set([...staff.map(s=>s.member_key),...relations.map(r=>r.our_member)].filter(Boolean))) {
  if(known.has(key))continue
  const s=staffByKey.get(key)?.[0]
  managers.push({username:`liaison:${key}`,name:s?.name||key,department:s?.department||'',member_keys:[key]});known.add(key)
 }
 return managers.map(m=>{
  const linked=m.member_keys.flatMap(key=>relationsByKey.get(key)||[])
  const profiles=m.member_keys.flatMap(key=>staffByKey.get(key)||[])
  const organization=[organizationLiaisonRegion(m),...profiles.map(organizationLiaisonRegion)].filter(Boolean)
  const explicit=profiles.map(s=>normalizeLiaisonRegion(s.business_region)).filter(Boolean)
  // Personnel affiliation only: having a customer in a region does not make
  // headquarters/admin/technical staff a regional customer manager.
  return {...m,count:new Set(linked.map(r=>r.person_id)).size,regions:[...new Set<string>(organization.length?organization:explicit)]}
 }).filter(m=>m.regions.length>0)
}
