import type { CrmUnit, CrmPerson, CrmRelation, CrmQualityRules } from '../../../src/services/personalWorkApi'

export interface QualityDimension { name: string; weight: number; score: number | null; evidence: string; advice: string }
export interface OrganizationQuality {
  id: string; name: string; type: string; regions: string[]; people: CrmPerson[]; relations: CrmRelation[];
  members: string[]; dimensions: QualityDimension[]; score: number | null; evidenceWeight: number;
  completeness: number; risks: string[]; lastTouch: string; roles: string[]; coveredRoles: string[]; childCount: number;
}
const templates: Record<string, string[]> = {
  '主管单位': [],
  '业主单位': ['定技术', '定标', '签验收', '批付款', '运营接管'],
  '设计单位': ['定技术', '需求提出', '影响者'],
  '总包单位': ['定技术', '采购经办', '签验收', '批付款'],
  '厂商': ['定技术', '采购经办', '签验收'],
}
const supportScores: Record<string, number> = { '反对': 0, '中立': 40, '支持': 75, '积极支持': 100 }
export const defaultQualityRules: CrmQualityRules = {weights:[30,25,20,15,10], personal_weights:[45,30,25], personal_min_dimensions:2, personal_maintenance_days:30, good_threshold:80, fair_threshold:60, recent_days:90, min_dimensions:3, backup_count:2, completeness_threshold:80, strength_weight:50, support_scores:supportScores, templates}
const mean = (values: number[]) => values.length ? Math.round(values.reduce((a,b)=>a+b,0)/values.length) : null
const unique = <T,>(items:T[]) => [...new Set(items)]
// Read-only, provisional v1. Only supplied (authorized) data participates. Never writes back to CRM.
export function organizationQuality(units: CrmUnit[], people: CrmPerson[], relations: CrmRelation[], now = Date.now(), rules: CrmQualityRules = defaultQualityRules, region = ''): OrganizationQuality[] {
  const unitMap = new Map(units.map(u=>[u.id,u]))
  const regionsOf=(u:CrmUnit)=>u.business_regions?.length?u.business_regions:[u.business_region||'未分区']
  const matchedIds=new Set(units.filter(u=>!region||regionsOf(u).includes(region)).map(u=>u.id))
  const rootOf = (id:string) => {
    const visited = new Set<string>()
    let current = id
    while (unitMap.get(current)?.parent_unit_id && unitMap.has(unitMap.get(current)!.parent_unit_id!)) {
      if (visited.has(current)) return [...visited].sort()[0]!
      visited.add(current); current = unitMap.get(current)!.parent_unit_id!
    }
    return current
  }
  const groups = new Map<string, CrmUnit[]>()
  for (const unit of units) { const root=rootOf(unit.id); if(!groups.has(root))groups.set(root,[]); groups.get(root)!.push(unit) }
  const personGroups = new Map<string, CrmPerson[]>()
  for (const person of people) { if(!matchedIds.has(person.unit_id))continue; const root=rootOf(person.unit_id); if(!personGroups.has(root))personGroups.set(root,[]); personGroups.get(root)!.push(person) }
  const relByPerson = new Map<string, CrmRelation[]>()
  for (const relation of new Map(relations.map(r=>[r.id,r])).values()) { if(!relByPerson.has(relation.person_id))relByPerson.set(relation.person_id,[]); relByPerson.get(relation.person_id)!.push(relation) }
  return [...groups].filter(([,children])=>children.some(u=>matchedIds.has(u.id))).map(([id, allChildren])=>{
    const children=allChildren.filter(u=>matchedIds.has(u.id))
    const unit=unitMap.get(id)!, contacts=personGroups.get(id)||[], links=contacts.flatMap(p=>relByPerson.get(p.id)||[])
    const roles=rules.templates[unit.type]||[]
    const linked=contacts.filter(p=>(relByPerson.get(p.id)||[]).some(r=>r.our_member?.trim()))
    const coveredRoles=roles.filter(role=>linked.some(p=>p.decision_role===role))
    const keyPeople=contacts.filter(p=>p.importance==='重要'||roles.includes(p.decision_role))
    const validTime=(date:string)=>{const t=Date.parse(date);return Number.isFinite(t)&&t<=now?t:null}
    const evidenced=(r:CrmRelation)=>Number.isFinite(r.strength)&&!!r.last_touch&&validTime(r.last_touch)!==null
    const rated=keyPeople.filter(p=>rules.support_scores[p.support_level||'']!==undefined && (relByPerson.get(p.id)||[]).some(evidenced))
    const relationship=mean(rated.map(p=>{
      const strength=Math.max(...(relByPerson.get(p.id)||[]).filter(evidenced).map(r=>Math.max(0,Math.min(5,r.strength))))
      return strength/5*rules.strength_weight + rules.support_scores[p.support_level!]!*(100-rules.strength_weight)/100
    }))
    const actions=[...new Map(links.flatMap(r=>r.actions||[]).filter(a=>(a as typeof a & {record_kind?:string}).record_kind!=='plan').map(a=>[a.id,a])).values()]
    const recent=actions.filter(a=>{const t=validTime(a.happened_at);return t!==null&&now-t<=rules.recent_days*86400000})
    const validActions=actions.filter(a=>validTime(a.happened_at)!==null)
    // An absence of recorded interaction is unknown, not zero business interaction.
    const interaction=recent.length ? Math.round(recent.filter(a=>a.effective&&a.bidirectional).length/recent.length*100) : null
    const backed=keyPeople.filter(p=>unique((relByPerson.get(p.id)||[]).map(r=>r.our_staff?.username||r.our_member).filter(Boolean)).length>=rules.backup_count)
    const stability=keyPeople.length&&keyPeople.some(p=>(relByPerson.get(p.id)||[]).length) ? Math.round(backed.length/keyPeople.length*100) : null
    const assigned=links.filter(r=>r.our_member?.trim()).length
    const completeness=contacts.length ? Math.round(contacts.reduce((n,p)=>n+[p.decision_role,p.importance,p.support_level,p.department||p.title,(relByPerson.get(p.id)||[]).some(r=>r.our_member?.trim())?'yes':''].filter(Boolean).length,0)/(contacts.length*5)*100) : 0
    const dimensions:QualityDimension[]=[
      {name:'关键岗位覆盖',weight:rules.weights[0]!,score:roles.length&&linked.some(p=>p.decision_role)?Math.round(coveredRoles.length/roles.length*100):null,evidence:roles.length?`建议岗位 ${roles.join('、')}；已登记对接 ${coveredRoles.length}/${roles.length}。仅按决策角色精确匹配，不从职务猜测。`:'此组织类型尚无岗位模板，暂不计分。',advice:'确认本组织适用岗位，再补充关键联系人及对接关系；模板未确认，覆盖分仅供参考。'},
      {name:'关系质量',weight:rules.weights[1]!,score:relationship,evidence:`${keyPeople.length} 位关键联系人中 ${rated.length} 位有支持程度、关系强度及有效日期的互动记录；按每人最佳强度 L0–L5（${rules.strength_weight}%）与支持程度（${100-rules.strength_weight}%）平均。`,advice:`补充关键联系人的支持立场，并用真实沟通记录核实关系强度。反对/中立/支持/积极支持对应 ${['反对','中立','支持','积极支持'].map(s=>rules.support_scores[s]).join('/')}；空值或无互动证据不计分。`},
      {name:'互动有效性',weight:rules.weights[2]!,score:interaction,evidence:`近 ${rules.recent_days} 天已登记 ${recent.length} 条互动，其中 ${recent.filter(a=>a.effective&&a.bidirectional).length} 条同时标记有效、双向；按占比计分。${validActions.length&&!recent.length?'仅有较早记录，需核实近期互动。':''}`,advice:'登记有实质反馈的双向互动；无记录仅表示证据不足，不等于未沟通。'},
      {name:'对接稳定性',weight:rules.weights[3]!,score:stability,evidence:`${keyPeople.length} 位关键联系人中 ${backed.length} 位登记至少 ${rules.backup_count} 位我方对接人；按覆盖占比暂估，人数不代表已确认主备。`,advice:'核实关键联系人主备对接安排，降低单人依赖；主备职责仍需业务确认。'},
      {name:'我方维护责任',weight:rules.weights[4]!,score:links.length?Math.round(assigned/links.length*100):null,evidence:`${links.length} 条关系中 ${assigned} 条填写我方对接人。本项目前仅衡量责任人登记，不代表主责确认或任务按时闭环。`,advice:'确认主责与协同人员；后续闭环质量仍在关系维系中核查，不用创建人代替责任人。'},
    ]
    const available=dimensions.filter(d=>d.score!==null&&d.weight>0), evidenceWeight=available.reduce((n,d)=>n+d.weight,0)
    const score=evidenceWeight>0&&available.length>=rules.min_dimensions ? Math.round(available.reduce((n,d)=>n+d.score!*d.weight,0)/evidenceWeight) : null
    const risks:string[]=[]
    if(!links.length)risks.push('对接未登记')
    if(completeness<rules.completeness_threshold)risks.push('资料待补充')
    if(roles.length&&coveredRoles.length<roles.length)risks.push('岗位覆盖待核实')
    if(!recent.length)risks.push('近期互动证据不足')
    if(links.some(r=>r.single_point_risk)||stability!==null&&stability<100)risks.push('主备对接待核实')
    if(keyPeople.some(p=>p.support_level==='反对'))risks.push('关键联系人反对')
    const dates=[...links.map(r=>r.last_touch),...validActions.map(a=>a.happened_at)].filter(d=>d&&validTime(d)!==null).sort((a,b)=>Date.parse(b)-Date.parse(a))
    return {id,name:unit.company_full_name||unit.name,type:unit.type,regions:unique(children.flatMap(regionsOf)),people:contacts,relations:links,members:unique(links.map(r=>r.our_staff?.name||r.our_member_label||r.our_member).filter(Boolean)),dimensions,score,evidenceWeight,completeness,risks,lastTouch:dates[0]||'',roles,coveredRoles,childCount:children.filter(u=>u.id!==id).length}
  })
}
