import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
function load(name){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(`../packages/joint-command/frontend/${name}.ts`,import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,require:p=>load(p.replace('./',''))});return exports}
const {managementRegionQueue:filter}=load('managementRegion')
const staff=[{member_key:'e',name:'同名',department:'东区作战平台'},{member_key:'g',name:'同名',department:'广东作战平台'}]
const queue={overdue:[{owner:'e'},{owner:'g'},{owner:'同名'},{owner:'unknown',owner_staff:{department:'西区作战平台'}}],undated:[{owner:'g'}],scheduled:[],stale:[{opportunity:{manager:'e',region:'广东区'}}],unassigned:[{region:'中区'}],risks:[{our_member:'g'}]}
assert.equal(filter(queue,staff,'').overdue.length,4)
assert.equal(filter(queue,staff,'东区').overdue.length,1)
assert.equal(filter(queue,staff,'东区').stale.length,1)
assert.equal(filter(queue,staff,'广东区').stale.length,0)
assert.equal(filter(queue,staff,'广东区').undated.length,1)
assert.equal(filter(queue,staff,'广东区').risks.length,1)
assert.equal(filter(queue,staff,'中区').unassigned.length,1)
assert.equal(filter(queue,staff,'西区').overdue.length,1)
assert.equal(filter(queue,staff,'未分区').overdue.length,1)
assert.equal(queue.overdue.length,4)
console.log('PASS four-region queue counts, resolved owner, ambiguous name, unassigned, opportunity fallback and nonmutation')
