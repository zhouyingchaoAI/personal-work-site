import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/customerWorkspace.ts', import.meta.url), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText, {exports})
const {customerPortfolios, opportunityAttention, calendarDay} = exports
const units = [{id:'root',name:'集团'}, {id:'child',name:'分公司',parent_unit_id:'root'}, {id:'other',name:'集团同名公司'}]
const people = [{id:'p',unit_id:'child'}, {id:'hidden',unit_id:'invisible'}]
const relations = [{id:'r',person_id:'p'}, {id:'hidden-r',person_id:'hidden'}]
const opportunities = [{code:'a',owner_unit_id:'child'}, {code:'legacy',owner_unit:'集团'}, {code:'hidden',owner_unit_id:'invisible'}]
const group = customerPortfolios(units,people,relations,opportunities).find(g=>g.unit.id==='root')
assert.equal(group.people.length,1); assert.equal(group.relations.length,1); assert.equal(group.opportunities.length,1)
assert.equal(group.opportunities[0].code,'a', 'name-only records must not silently count as confirmed')
assert.equal(customerPortfolios(units.slice(1),people,relations,opportunities).find(g=>g.unit.id==='child').people.length,1)
assert.equal(customerPortfolios([{id:'a',name:'a',parent_unit_id:'b'},{id:'b',name:'b',parent_unit_id:'a'}],[],[],[]).length,1)
const opp = {code:'a',created_at:'2026-09-01',outcome:'open',_owner:'alice'}
let items = opportunityAttention([opp],[], '2026-09-21',14)
assert.equal(items[0].days,20); assert.equal(items[0].stale,true)
const actions = [{_owner:'alice',actions:[{project_id:'a',happened_at:'2026-09-20',record_kind:'plan'}, {project_id:'a',happened_at:'2026-10-01'}]}]
assert.equal(opportunityAttention([opp],actions,'2026-09-21')[0].days,20, 'plans/future dates cannot refresh last interaction')
actions[0].actions.push({project_id:'a',happened_at:'2026-09-18'})
assert.equal(opportunityAttention([opp],actions,'2026-09-21')[0].days,3)
assert.equal(opportunityAttention([opp],[{...actions[0],_owner:'bob'}],'2026-09-21')[0].days,20, 'same code in another owner must not mask stagnation')
assert.equal(opportunityAttention([{...opp,created_at:''}],[],'2026-09-21')[0].days,null)
assert.equal(opportunityAttention([{...opp,outcome:'won'},{...opp,outcome:'lost'},{...opp,cancelled:true}],[],'2026-09-21').length,0)
assert.equal(calendarDay('2026-02-30'),null)
assert.equal(opportunityAttention([opp],[],'2026-09-15',14)[0].stale,true)
for (const threshold of [14,30,60]) {
  const at = new Date(Date.UTC(2026,8,1+threshold)).toISOString().slice(0,10)
  const before = new Date(Date.UTC(2026,8,threshold)).toISOString().slice(0,10)
  assert.equal(opportunityAttention([opp],[],at,threshold)[0].stale,true)
  assert.equal(opportunityAttention([opp],[],before,threshold)[0].stale,false)
  assert.equal(opportunityAttention([opp],[{_owner:'alice',actions:[{project_id:'a',happened_at:at}]}],at,threshold)[0].stale,false,'real project interaction clears reminder')
}
console.log('PASS authorized hierarchy, orphan/cycle handling, explicit customer association, overdue thresholds, unknown dates, plan/future exclusion and owner isolation')
