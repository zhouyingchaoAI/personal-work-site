import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/views/CrmAssistantView/personalOrganizationQuality.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports})
const evaluate=exports.personalOrganizationQuality
const units=[{id:'root',name:'客户',type:'业主单位'},{id:'child',parent_unit_id:'root'}]
const rules={templates:{'业主单位':['定技术','定标']}}
const row={memberKey:'m1',member:'甲',person:{id:'p1',unit_id:'root',decision_role:'定技术'},score:80,completeness:100,days:2,cadence:30,lastTouch:'2026-09-18',regions:['东区'],risks:[]}
const pending={...row,person:{id:'p2',unit_id:'child'},score:null,completeness:20,days:null,lastTouch:'',risks:['证据待补充']}
const crossRegion={...pending,score:20,regions:['西区']}
const east=evaluate([row,crossRegion],units,rules,'东区')
assert.equal(east[0].contacts.length,1,'region must scope contacts before organization scoring')
assert.equal(east[0].score,80,'west score must not dilute east score')
assert.equal(evaluate([row,crossRegion],units,rules,'西区')[0].score,20)
assert.equal(evaluate([row,crossRegion],units,rules,'广东区').length,0)
const result=evaluate([row,pending,{...row,memberKey:'m2',member:'乙',score:20}],units,rules)
assert.equal(result.length,2)
assert.equal(result[0].contacts.length,2)
assert.equal(result[0].score,80,'missing scores are not zero')
assert.equal(result[0].assessed,1,'show sample completeness alongside mean')
assert.equal(result[0].coveredRoles.length,1)
assert.equal(result[1].score,20,'do not borrow colleagues scores')
assert.equal(evaluate([row,row],units,rules)[0].contacts.length,1)
assert.equal(evaluate([pending],units,rules)[0].score,null)
assert.equal(evaluate([row,pending],[units[0]],rules).length,2,'do not invent invisible parent links')
assert.equal(evaluate([{...row,person:{id:'p',unit_id:'a'}}],[{id:'a',parent_unit_id:'b'},{id:'b',parent_unit_id:'a'}],rules).length,1)
console.log('PASS liaison/root organization grouping, descendants, score denominator, deduplication, scope and cycles')
