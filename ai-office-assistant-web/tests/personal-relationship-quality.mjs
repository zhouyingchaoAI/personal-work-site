import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
function module(name){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(`../src/views/CrmAssistantView/${name}.ts`,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});return exports}
const {personalRelationshipQuality:evaluate}=module('personalRelationshipQuality')
const {defaultQualityRules:rules}=module('organizationQuality')
const now=Date.parse('2026-09-20T00:00:00Z')
const units=[{id:'u',name:'客户组织'}],people=[{id:'p',unit_id:'u',name:'客户',support_level:'支持',maintenance_days:10}]
const recent={id:'a',happened_at:'2026-09-19',effective:true,bidirectional:true}
const rel={id:'r',person_id:'p',our_member:'E1',strength:4,last_touch:'2026-09-19',actions:[recent]}
const result=evaluate(units,people,[rel,{id:'r2',person_id:'p',our_member:'E2',strength:0,last_touch:'',actions:[]}],rules,now)
assert.equal(result.length,2)
assert.equal(result[0].score,90)
assert.equal(result[1].score,null,'never borrow another liaison evidence for same customer')
assert.equal(result[1].dimensions[2].score,null,'missing date is not zero')
assert.equal(result[0].dimensions.length,3,'company coverage/backup not personal criteria')
const duplicate=evaluate(units,people,[rel,{...rel,id:'r3'}],rules,now)[0]
assert.equal(duplicate.actions.length,1)
assert.equal(duplicate.score,result[0].score)
const aliases=evaluate(units,people,[{...rel,our_staff:{id:'staff1'}},{...rel,id:'r3',our_member:'alias',our_staff:{id:'staff1'}}],rules,now)
assert.equal(aliases.length,1)
const overdue=evaluate(units,people,[{...rel,last_touch:'2026-09-05'}],rules,now)[0]
assert.equal(overdue.dimensions[2].score,50)
assert.ok(overdue.risks.includes('维系超期'))
const noSupport=evaluate(units,[{...people[0],support_level:''}],[rel],rules,now)[0]
assert.equal(noSupport.dimensions[0].score,null)
const future=evaluate(units,people,[{...rel,last_touch:'2030-01-01',actions:[{...recent,happened_at:'2030-01-01'},{...recent,id:'plan',record_kind:'plan'}]}],rules,now)[0]
assert.equal(future.score,null)
assert.equal(future.actions.length,0)
assert.equal(evaluate(units,[],[rel],rules,now).length,0,'invisible contacts excluded')
const custom={...rules,personal_weights:[0,0,100],personal_min_dimensions:1}
assert.equal(evaluate(units,people,[rel],custom,now)[0].score,100)
assert.equal(evaluate(units,[{...people[0],maintenance_days:''}],[rel],rules,now)[0].cadence,30)
console.log('PASS separate personal model, colleague isolation, deduplication, scoped contacts, dates, cadence and configurable weights')
