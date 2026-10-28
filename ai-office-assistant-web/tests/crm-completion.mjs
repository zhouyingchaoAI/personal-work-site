import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
function load(name){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(`../packages/joint-command/frontend/${name}.ts`,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,require:(path)=>load(path.replace('./',''))});return exports}
const {associationCandidates,managementQueue}=load('crmCompletion')
const units=[{id:'a',name:'测试地铁集团有限公司'},{id:'b',name:'测试地铁集团运营部'},{id:'c',name:'另一地铁集团'}]
assert.equal(associationCandidates('测试地铁集团',units).map(x=>x.unit.id).join(','),'a,b')
assert.equal(associationCandidates('',units).length,0)
assert.equal(associationCandidates('集团',units).length,0)
assert.equal(associationCandidates('测试地铁集团',units.slice(2)).length,0)
assert.equal(units[0].name,'测试地铁集团有限公司','candidate generation must not mutate data')
const queue=managementQueue([{id:'old',code:'old',created_at:'2020-01-01',manager:''},{id:'closed',code:'closed',outcome:'won',manager:''}], [{id:'late',due_date:'2020-01-01'},{id:'done',due_date:'2020-01-01',completed_at:'2026-09-20'},{id:'today',due_date:'2026-09-21'}],[{id:'risk',our_member:'a',single_point_risk:true},{id:'blank',our_member:''},{id:'ok',our_member:'a'}],'2026-09-21')
assert.equal(queue.overdue.map(x=>x.id).join(','),'late')
assert.equal(queue.stale.length,1)
assert.equal(queue.unassigned.map(x=>x.id).join(','),'old')
assert.equal(queue.risks.length,2)
const missingDates=managementQueue([], [{id:'missing'},{id:'blank',due_date:''},{id:'done',completed_at:'2026-09-20'},{id:'future',due_date:'2026-09-22'},{id:'today',due_date:'2026-09-21'}], [], '2026-09-21')
assert.equal(missingDates.undated.map(x=>x.id).join(','),'missing,blank')
assert.equal(missingDates.overdue.length,0)
assert.equal(missingDates.scheduled.map(x=>x.id).join(','),'today,future')
console.log('PASS authorized candidate matching without mutation, management overdue/stale/coordination and closed/completed exclusion')
