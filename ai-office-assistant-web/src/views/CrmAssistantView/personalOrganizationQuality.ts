import type { CrmUnit, CrmQualityRules } from '../../services/personalWorkApi'
import type { PersonalRelationshipQuality } from './personalRelationshipQuality'

// Each contact contributes at most once to its liaison/root-organization pair.
export function personalOrganizationQuality(rows:PersonalRelationshipQuality[],units:CrmUnit[],rules:CrmQualityRules,region='') {
 const unitMap=new Map(units.map(u=>[u.id,u]))
 function root(id:string){const seen=new Set<string>();let cursor=id;while(unitMap.get(cursor)?.parent_unit_id&&unitMap.has(unitMap.get(cursor)!.parent_unit_id!)){if(seen.has(cursor))return [...seen].sort()[0]!;seen.add(cursor);cursor=unitMap.get(cursor)!.parent_unit_id!}return cursor}
 const groups=new Map<string,PersonalRelationshipQuality[]>()
 for(const row of rows){if(region&&!row.regions.includes(region))continue;const id=JSON.stringify([row.memberKey,root(row.person.unit_id)]);if(!groups.has(id))groups.set(id,[]);groups.get(id)!.push(row)}
 return [...groups].map(([id,items])=>{
  const contacts=[...new Map(items.map(r=>[r.person.id,r])).values()],first=contacts[0]!,unit=unitMap.get(root(first.person.unit_id))
  const assessed=contacts.filter(r=>r.score!==null)
  const roles=rules.templates[unit?.type||'']||[]
  const coveredRoles=roles.filter(role=>contacts.some(r=>r.person.decision_role===role))
  const dates=contacts.map(r=>r.lastTouch).filter(Boolean).sort((a,b)=>Date.parse(b)-Date.parse(a))
  return {id,memberKey:first.memberKey,member:first.member,department:first.department,unit,
   name:unit?.company_full_name||unit?.name||'客户组织待补充',contacts,assessed:assessed.length,
   score:assessed.length?Math.round(assessed.reduce((n,r)=>n+r.score!,0)/assessed.length):null,
   completeness:Math.round(contacts.reduce((n,r)=>n+r.completeness,0)/contacts.length),
   overdue:contacts.filter(r=>r.days!==null&&r.days>r.cadence).length,
   roles,coveredRoles,regions:[...new Set(contacts.flatMap(r=>r.regions))],lastTouch:dates[0]||'',
   risks:[...new Set(contacts.flatMap(r=>r.risks))]}
 })
}
