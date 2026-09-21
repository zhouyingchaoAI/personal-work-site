import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports={}
const source=fs.readFileSync(new URL('../src/views/CrmAssistantView/managerReview.ts',import.meta.url),'utf8')
const regions={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/views/CrmAssistantView/liaisonRegions.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:regions})
const require = () => regions
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,require})
const accounts=[{username:'a',name:'同名',member_keys:['a','E1']},{username:'b',name:'同名',member_keys:['b']}]
const staff=[{member_key:'E1',name:'同名',business_region:'西区'},{member_key:'E1',name:'同名',business_region:'西区'},{member_key:'external',name:'无账号对接人',business_region:'中区'}]
const relations=[{our_member:'E1',person_id:'p'},{our_member:'a',person_id:'p'},{our_member:'b',person_id:'q'},{our_member:'external',person_id:'q'}]
const people=[{id:'p',unit_id:'u'},{id:'q',unit_id:'v'}]
const units=[{id:'u',business_regions:['东区']},{id:'v',business_regions:['广东区','东区']}]
const result=exports.managerReviewOptions(accounts,staff,relations,people,units)
const a=result.find(m=>m.username==='a'),b=result.find(m=>m.username==='b')
assert.equal(result.length,3)
assert.equal(a.count,1)
assert.equal(a.regions.join(','),'西区','explicit personnel region beats customer geography')
assert.equal(b.regions.join(','),'广东区,东区','legacy personnel inferred from client business areas')
assert.equal(result.find(m=>m.username==='liaison:external').member_keys[0],'external')
assert.equal(result.filter(m=>m.name==='同名').length,2,'never merge by display name')
assert.equal(accounts.length,2)
console.log('PASS personnel regions, cross-region clients, alias deduplication, non-account liaisons, distinct names')
const legacySource = source
 .replace('(staffByAccount.get(m.username) || [])', 'staff.filter(s=>s.username===m.username)')
 .replace('(relationsByAccount.get(m.username) || [])', 'relations.filter(r=>r.our_staff?.username===m.username)')
 .replace('staffByKey.get(key)?.[0]', 'staff.find(s=>s.member_key===key)')
 .replace('m.member_keys.flatMap(key=>relationsByKey.get(key)||[])', 'relations.filter(r=>m.member_keys.includes(r.our_member))')
 .replace('m.member_keys.flatMap(key=>staffByKey.get(key)||[])', 'staff.filter(s=>m.member_keys.includes(s.member_key))')
const legacy={}
vm.runInNewContext(ts.transpileModule(legacySource,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:legacy,require})
const largeStaff=Array.from({length:21202},(_,i)=>({member_key:`E${i}`,name:`人员${i}`,business_region:'东区'}))
let started=performance.now()
const oldResult=legacy.managerReviewOptions(accounts,largeStaff,relations,people,units)
const oldMs=performance.now()-started
started=performance.now()
const newResult=exports.managerReviewOptions(accounts,largeStaff,relations,people,units)
const newMs=performance.now()-started
assert.equal(JSON.stringify(newResult),JSON.stringify(oldResult),'large-directory output must preserve previous semantics')
assert.ok(newMs < oldMs,'indexed lookup should outperform repeated full scans')
console.log(JSON.stringify({staff:largeStaff.length,beforeMs:Math.round(oldMs),afterMs:Math.round(newMs),speedup:Math.round(oldMs/newMs)}))
