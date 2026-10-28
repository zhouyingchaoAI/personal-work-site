import type { CrmOpportunity, CrmPerson, CrmPlaybook, CrmUnit } from '../../../src/services/personalWorkApi'

export function opportunityKey(item: Pick<CrmOpportunity, 'id' | 'code' | '_owner'>) {
  return JSON.stringify([item._owner || '', item.id || item.code])
}

export function opportunityTasks(item: CrmOpportunity, tasks: CrmPlaybook['followups']) {
  return tasks.filter(task => task.project_id === item.code &&
    ((task as { _owner?: string })._owner || '') === (item._owner || '') && !task.completed_at)
    .sort((a,b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'))
}

export function opportunityTaskIndex(items:CrmOpportunity[], tasks:CrmPlaybook['followups']) {
  const byProject=new Map<string,CrmPlaybook['followups'][number]>()
  for(const task of tasks) {
    if(!task.project_id || task.completed_at)continue
    const key=JSON.stringify([(task as {_owner?:string})._owner||'',task.project_id])
    const previous=byProject.get(key)
    if(!previous || (task.due_date||'9999') < (previous.due_date||'9999'))byProject.set(key,task)
  }
  const result=new Map<string,CrmPlaybook['followups'][number]>()
  for(const item of items){const task=byProject.get(JSON.stringify([item._owner||'',item.code]));if(task)result.set(opportunityKey(item),task)}
  return result
}

// Only explicitly linked, visible customer nodes; never infer identity from names.
export function opportunityContacts(item: CrmOpportunity, units: CrmUnit[], people: CrmPerson[]) {
  if (!item.owner_unit_id || !units.some(u => u.id === item.owner_unit_id)) return []
  const ids = new Set([item.owner_unit_id])
  let changed = true
  while (changed) {
    changed = false
    for (const unit of units) if (unit.parent_unit_id && ids.has(unit.parent_unit_id) && !ids.has(unit.id)) {
      ids.add(unit.id); changed = true
    }
  }
  return people.filter(p => ids.has(p.unit_id)).sort((a,b) =>
    Number(!!b.decision_role) - Number(!!a.decision_role) || a.name.localeCompare(b.name, 'zh-CN'))
}
