import type { CrmPerson, CrmRelation, CrmUnit, CrmQualityRules } from '../../services/personalWorkApi'
import type { QualityDimension } from './organizationQuality'

// Evaluate a specific liaison/contact pair, never borrow another colleague's interaction evidence.
export function personalRelationshipQuality(units:CrmUnit[],people:CrmPerson[],relations:CrmRelation[],rules:CrmQualityRules,now=Date.now()) {
 const peopleById=new Map(people.map(p=>[p.id,p])),unitById=new Map(units.map(u=>[u.id,u]))
 const memberKey=(r:CrmRelation)=>r.our_staff?.id||r.our_staff?.username||r.our_member?.trim()
 const groups=new Map<string,CrmRelation[]>()
 for(const r of new Map(relations.map(r=>[r.id,r])).values()){
  if(!memberKey(r)||!peopleById.has(r.person_id))continue
  const key=JSON.stringify([memberKey(r),r.person_id]);if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(r)
 }
 return [...groups].map(([id,links])=>{
  const first=links[0]!,person=peopleById.get(first.person_id)!,unit=unitById.get(person.unit_id)
  const time=(date:string)=>{const t=Date.parse(date);return Number.isFinite(t)&&t<=now?t:null}
  const dated=links.filter(r=>r.last_touch&&time(r.last_touch)!==null)
  const lastTouch=dated.map(r=>r.last_touch).sort((a,b)=>Date.parse(b)-Date.parse(a))[0]||''
  const days=lastTouch?Math.floor((now-Date.parse(lastTouch))/86400000):null
  const configuredCadence=Number(person.maintenance_days)
  const cadence=Number.isInteger(configuredCadence)&&configuredCadence>=1&&configuredCadence<=365?configuredCadence:rules.personal_maintenance_days
  const strength=dated.some(r=>Number.isFinite(r.strength))?Math.max(...dated.filter(r=>Number.isFinite(r.strength)).map(r=>Math.min(5,Math.max(0,r.strength)))):null
  // Support is contact-level information, not a proven stance toward this particular liaison.
  const support=rules.support_scores[person.support_level||'']
  const quality=strength!==null&&support!==undefined?Math.round(strength/5*rules.strength_weight+support*(100-rules.strength_weight)/100):null
  const actions=[...new Map(links.flatMap(r=>r.actions||[]).filter(a=>(a as typeof a&{record_kind?:string}).record_kind!=='plan'&&time(a.happened_at)!==null).map(a=>[a.id,a])).values()]
  const recent=actions.filter(a=>now-Date.parse(a.happened_at)<=rules.recent_days*86400000)
  const effective=recent.filter(a=>a.effective&&a.bidirectional).length
  const interaction=recent.length?Math.round(effective/recent.length*100):null
  const timeliness=days===null?null:days<=cadence?100:Math.max(0,Math.round(100*(2-days/cadence)))
  const dimensions:QualityDimension[]=[
   {name:'关系质量',weight:rules.personal_weights[0]!,score:quality,evidence:`仅使用该对接人名下强度 ${strength===null?'待核实':`L${strength}`}；客户档案支持程度：${person.support_level||'待补充'}。强度占 ${rules.strength_weight}%，档案立场占 ${100-rules.strength_weight}%。`,advice:'核实双方沟通深度；档案支持程度是客户整体立场，不代表对某位员工的个人认可。'},
   {name:'互动有效性',weight:rules.personal_weights[1]!,score:interaction,evidence:`近 ${rules.recent_days} 天本对接人登记 ${recent.length} 条真实互动，其中 ${effective} 条同时标记有效且双向，按占比计分。`,advice:'记录实际沟通和客户反馈；不计其他同事的互动，不把未来计划计作已完成。'},
   {name:'维系及时性',weight:rules.personal_weights[2]!,score:timeliness,evidence:`维系周期 ${cadence} 天（${cadence===configuredCadence?'客户档案':'默认规则'}）；${days===null?'无有效最近互动日期':`距最近登记互动 ${days} 天`}。周期内 100 分，之后线性下降，达到两倍周期为 0。`,advice:'核实是否漏记沟通；确有超期时安排下一次联络，日期缺失为待评估而非零分。'},
  ]
  const available=dimensions.filter(d=>d.score!==null&&d.weight>0),evidenceWeight=available.reduce((n,d)=>n+d.weight,0)
  const score=evidenceWeight&&available.length>=rules.personal_min_dimensions?Math.round(available.reduce((n,d)=>n+d.score!*d.weight,0)/evidenceWeight):null
  const completeness=Math.round([person.importance,person.support_level,lastTouch,person.department||person.title,recent.length?'yes':''].filter(Boolean).length/5*100)
  const risks:string[]=[]
  if(days===null)risks.push('互动日期待核实');else if(days>cadence)risks.push('维系超期')
  if(!recent.length)risks.push('近期互动证据不足')
  if(support===undefined)risks.push('客户立场待补充')
  if(person.support_level==='反对')risks.push('客户档案立场反对')
  return {id,memberKey:memberKey(first)!,member:first.our_staff?.name||first.our_member_label||first.our_member,department:first.our_staff?.department||'',person,unit,relations:links,actions,dimensions,score,evidenceWeight,completeness,risks,lastTouch,days,cadence,strength,regions:unit?.business_regions?.length?unit.business_regions:[unit?.business_region||'未分区']}
 })
}
export type PersonalRelationshipQuality=ReturnType<typeof personalRelationshipQuality>[number]
