import type { CrmOpportunity, CrmUnit, CrmPlaybook, CrmRelation } from '../../../src/services/personalWorkApi'
import { opportunityAttention } from './customerWorkspace'
export function associationCandidates(name:string,units:CrmUnit[]) {
 const normalize=(s:string)=>(s||'').toLowerCase().replace(/[\s（）()·、，,./\\-]/g,'').replace(/(有限责任公司|股份有限公司|有限公司)$/,'')
 const key=normalize(name)
 if(key.length<3)return []
 return units.map(unit=>({unit,exact:normalize(unit.name)===key,match:normalize(unit.name)}))
  .filter(x=>x.exact || (x.match.length>=3 && (x.match.includes(key)||key.includes(x.match))))
  .sort((a,b)=>Number(b.exact)-Number(a.exact)||a.unit.name.localeCompare(b.unit.name,'zh-CN')).slice(0,5)
}
export function managementQueue(opportunities:CrmOpportunity[],followups:CrmPlaybook['followups'],relations:CrmRelation[],today:string) {
 const overdue=followups.filter(t=>!t.completed_at&&t.due_date&&t.due_date<today).sort((a,b)=>a.due_date!.localeCompare(b.due_date!))
 const undated=followups.filter(t=>!t.completed_at&&!t.due_date?.trim())
 const scheduled=followups.filter(t=>!t.completed_at&&t.due_date&&t.due_date>=today).sort((a,b)=>a.due_date!.localeCompare(b.due_date!))
 const stale=opportunityAttention(opportunities,relations,today,14).filter(i=>i.stale)
 const unassigned=opportunities.filter(o=>!o.cancelled&&(!o.outcome||o.outcome==='open')&&!o.manager?.trim())
 const risks=relations.filter(r=>r.single_point_risk || !r.our_member?.trim())
 return {overdue,undated,scheduled,stale,unassigned,risks}
}
