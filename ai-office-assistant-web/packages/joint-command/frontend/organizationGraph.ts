import type { CrmGraphNode, CrmGraphEdge, CrmUnit, CrmPerson, CrmStaff, CrmRelation } from '../../../src/services/personalWorkApi'
export function organizationGraph(units:CrmUnit[],people:CrmPerson[],staff:CrmStaff[],relations:CrmRelation[]) {
 const nodes=new Map<string,CrmGraphNode>(),edges:CrmGraphEdge[]=[]
 const add=(id:string,label:string,kind:CrmGraphNode['kind'],type='我方')=>{if(!nodes.has(id))nodes.set(id,{id,label,kind,type});return id}
 const edge=(source:string,target:string,kind:'belongs'|'reports'|'contact',label:string,r?:CrmRelation)=>{edges.push({source,target,relation_kind:kind,our_member_label:label,strength:r?.strength||0,score:r?.score||0,decay_state:r?.decay_state||'normal',days_since_touch:r?.days_since_touch??null,single_point_risk:r?.single_point_risk||false})}
 add('self','我方组织','self')
 const memberIds=new Map<string,string>()
 for(const p of staff){
  const company=add('org:company:'+JSON.stringify(p.company||''),p.company||'公司待补充','group')
  let dept=company
  const parts=(p.department||'部门待补充').split(' / ')
  for(let i=0;i<parts.length;i++){
   const next=add('org:dept:'+JSON.stringify([p.company,parts.slice(0,i+1).join(' / ')]),parts[i],'group')
   edge(dept,next,'belongs','部门归属');dept=next
  }
  const job=add('org:job:'+JSON.stringify([p.company,p.department,p.title]),p.title||'岗位待补充','group')
  const id=add(p.id,p.name,'staff');memberIds.set(p.member_key,id)
  edge('self',company,'belongs','我方公司');edge(dept,job,'belongs','岗位设置');edge(job,id,'belongs','任职人员')
 }
 for(const p of staff)if(p.manager_id&&nodes.has(p.manager_id))edge(p.manager_id,p.id,'reports','直接上级 → 下属')
 const customerLevel:Record<string,string>={company:'公司全称',subsidiary:'子公司全称',unit:'单位'}
 for(const u of units)add(u.id,`${customerLevel[u.organization_level||'']||'单位'} · ${u.name}`,'unit',u.type)
 for(const u of units)if(u.parent_unit_id&&nodes.has(u.parent_unit_id))edge(u.parent_unit_id,u.id,'reports','上级单位 → 下级单位')
 for(const p of people){
  const u=units.find(u=>u.id===p.unit_id),type=u?.type||''
  add(p.id,`${p.name}${p.title ? ' · '+p.title : ''}`,'person',type)
  if(u){const d=add('org:client-dept:'+JSON.stringify([u.id,p.department]),p.department||'部门待补充','group',type);edge(u.id,d,'belongs','客户部门归属');edge(d,p.id,'belongs','部门人员')}
 }
 for(const p of people)if(p.manager_id&&nodes.has(p.manager_id))edge(p.manager_id,p.id,'reports','直接上级 → 下属')
 for(const r of relations){
  // 空白就是“暂未指派”，不是一个可被画出来的我方联系人。
  if(!nodes.has(r.person_id)||!r.our_member)continue
  let id=memberIds.get(r.our_member)
  if(!id){id=add('org:unregistered:'+r.our_member,`${r.our_member}（待建档）`,'group');edge('self',id,'belongs','我方对接人，部门岗位待补充')}
  edge(id,r.person_id,'contact',`客户对接 · ${r.our_member_label||r.our_member} · L${r.strength}`,r)
 }
 return {nodes:[...nodes.values()],edges:edges.filter((e,i,a)=>a.findIndex(x=>x.source===e.source&&x.target===e.target&&x.relation_kind===e.relation_kind)===i)}
}
