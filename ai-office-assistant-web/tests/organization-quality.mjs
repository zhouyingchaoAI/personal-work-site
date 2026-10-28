import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/organizationQuality.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports})
const {organizationQuality:evaluate}=exports
const now=Date.parse('2026-09-20T12:00:00Z')
const regionalUnits=[{id:'root',name:'跨区公司',type:'业主单位'}, {id:'east',parent_unit_id:'root',business_regions:['东区']}, {id:'west',parent_unit_id:'root',business_regions:['西区']}]
const scoped=evaluate(regionalUnits,[{id:'ep',unit_id:'east'},{id:'wp',unit_id:'west'}],[{id:'er',person_id:'ep',our_member:'e'},{id:'wr',person_id:'wp',our_member:'w'}],now,exports.defaultQualityRules,'东区')
assert.equal(scoped[0].people.length,1,'east evaluation must not include west contacts under same root')
assert.equal(scoped[0].people[0].id,'ep')
assert.equal(scoped[0].relations.length,1)
assert.equal(scoped[0].relations[0].id,'er')
assert.equal(scoped[0].name,'跨区公司','retain ancestor identity without its other regional data')
assert.equal(evaluate(regionalUnits,[],[],now,exports.defaultQualityRules,'广东区').length,0)
const units=[{id:'a',name:'甲',type:'业主单位'},{id:'b',name:'部门',parent_unit_id:'a',type:'业主单位'},{id:'empty',name:'无对接',type:'厂商'}]
const person={id:'p',unit_id:'b',name:'联系人',importance:'重要',decision_role:'定技术',support_level:'支持',department:'技术部'}
const action={id:'act',happened_at:'2026-09-19',effective:true,bidirectional:true}
const relation={id:'r',person_id:'p',our_member:'m',strength:4,last_touch:'2026-09-19',actions:[action]}
const rows=evaluate(units,[person],[relation],now), row=rows[0]
assert.equal(rows.length,2,'roll up descendants, do not duplicate organizations')
assert.equal(row.people.length,1)
assert.equal(row.childCount,1)
assert.equal(row.completeness,100)
assert.equal(row.dimensions[0].score,20)
assert.equal(row.dimensions[1].score,78)
assert.equal(row.dimensions[2].score,100)
assert.equal(row.dimensions[3].score,0,'single liaison is not a backup')
assert.equal(row.score,56)
assert.equal(rows[1].score,null,'empty organization is pending, not zero')
assert.equal(rows[1].completeness,0)
const missing=evaluate(units,[{...person,decision_role:'',support_level:''}],[{...relation,last_touch:'',actions:[]}],now)[0]
assert.equal(missing.dimensions[0].score,null)
assert.equal(missing.dimensions[1].score,null,'missing support and interaction must not become opposition/zero')
assert.equal(missing.dimensions[2].score,null)
assert.equal(missing.score,null,'less than three dimensions cannot produce a total')
assert.equal(evaluate(units,[person],[{...relation,last_touch:'',actions:[]}],now)[0].dimensions[1].score,null,'default strength without interaction is not evidence')
const plans=evaluate(units,[person],[{...relation,actions:[{...action,record_kind:'plan'},{...action,id:'future',happened_at:'2030-01-01'},{...action,id:'bad',happened_at:'bad'}]}],now)[0]
assert.equal(plans.dimensions[2].score,null,'plans, future dates and invalid dates are not actual interactions')
const duplicate=evaluate(units,[person],[relation,relation],now)[0]
assert.equal(duplicate.relations.length,1)
assert.equal(duplicate.score,row.score,'duplicate records cannot boost scores')
const backup=evaluate(units,[person],[relation,{...relation,id:'r2',our_member:'m2'}],now)[0]
assert.equal(backup.dimensions[3].score,100)
assert.match(backup.dimensions[2].evidence,/近 90 天已登记 1 条/,'deduplicate actions')
assert.equal(evaluate(units.slice(0,1),[person],[relation],now)[0].people.length,0,'inaccessible child data excluded')
assert.equal(evaluate([{id:'x',parent_unit_id:'y'},{id:'y',parent_unit_id:'x'}],[{...person,unit_id:'x'}],[relation],now).length,1,'cycles terminate and coalesce')
assert.equal(evaluate([{id:'b',type:'未知'}],[person],[relation],now)[0].dimensions[0].score,null,'unknown type has no invented template')
console.log('PASS provisional scores, missing evidence, role templates, deduplication, hierarchy, scope and dates')
const custom=JSON.parse(JSON.stringify(exports.defaultQualityRules))
custom.weights=[0,0,0,0,100]
custom.min_dimensions=1
assert.equal(evaluate(units,[person],[relation],now,custom)[0].score,100,'disabled dimensions do not dilute total or evidence count')
custom.min_dimensions=2
assert.equal(evaluate(units,[person],[relation],now,custom)[0].score,null,'zero weight dimensions do not satisfy evidence gate')
custom.min_dimensions=1
custom.recent_days=1
assert.equal(evaluate(units,[person],[relation],now,custom)[0].dimensions[2].score,null,'configured time window takes effect')
custom.templates['业主单位']=['定技术']
custom.strength_weight=0
custom.support_scores['支持']=90
custom.backup_count=3
const configured=evaluate(units,[person],[relation,{...relation,id:'r2',our_member:'m2'}],now,custom)[0]
assert.equal(configured.dimensions[0].score,100)
assert.equal(configured.dimensions[1].score,90)
assert.equal(configured.dimensions[3].score,0)
console.log('PASS configurable weights, evidence gate, period, roles, support scores and backup count')
