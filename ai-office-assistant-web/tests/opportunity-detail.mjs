import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/opportunityDetail.ts', import.meta.url), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText, {exports})
const {opportunityKey,opportunityTasks,opportunityTaskIndex,opportunityContacts} = exports
const opp = {id:'one',code:'OPP-1',_owner:'alice',owner_unit_id:'child'}
assert.notEqual(opportunityKey(opp),opportunityKey({...opp,_owner:'bob'}))
assert.notEqual(opportunityKey(opp),opportunityKey({...opp,id:'two',code:'OPP-10'}))
const tasks = [
  {id:'late',project_id:'OPP-1',_owner:'alice',due_date:'2026-10-01'},
  {id:'early',project_id:'OPP-1',_owner:'alice',due_date:'2026-09-01'},
  {id:'unknown',project_id:'OPP-1',_owner:'alice'},
  {id:'other',project_id:'OPP-1',_owner:'bob'},
  {id:'prefix',project_id:'OPP-10',_owner:'alice'},
  {id:'done',project_id:'OPP-1',_owner:'alice',completed_at:'2026-09-21'}
]
assert.equal(opportunityTasks(opp,tasks).map(t=>t.id).join(','),'early,late,unknown')
assert.equal(opportunityTaskIndex([opp],tasks).get(opportunityKey(opp)).id,'early')
const batch=Array.from({length:5000},(_,i)=>({...opp,id:`o-${i}`,code:`OPP-${i}`}))
const batchTasks=Array.from({length:20000},(_,i)=>({id:`t-${i}`,project_id:`OPP-${i%5000}`,_owner:'alice',due_date:'2026-09-21'}))
const started=performance.now()
assert.equal(opportunityTaskIndex(batch,batchTasks).size,5000)
console.log(`indexed 5000 opportunities / 20000 tasks in ${Math.round(performance.now()-started)}ms`)
const units = [{id:'root'},{id:'child',parent_unit_id:'root'},{id:'grandchild',parent_unit_id:'child'},{id:'sibling',parent_unit_id:'root'}]
const people = [{id:'a',name:'甲',unit_id:'child'}, {id:'b',name:'乙',unit_id:'grandchild',decision_role:'决策'}, {id:'c',name:'丙',unit_id:'sibling'}]
assert.equal(opportunityContacts(opp,units,people).map(p=>p.id).join(','),'b,a')
assert.equal(opportunityContacts({...opp,owner_unit_id:''},units,people).length,0)
assert.equal(opportunityContacts({...opp,owner_unit_id:'hidden'},units,people).length,0)
assert.equal(opportunityContacts(opp,[...units,{id:'child',parent_unit_id:'grandchild'}],people).length,2)
console.log('PASS exact opportunity identity, owner-isolated tasks, dates/completion, explicit descendants and no sibling/name fallback')
