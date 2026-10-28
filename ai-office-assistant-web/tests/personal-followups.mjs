import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/personalFollowups.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports})
const tasks=[
 {id:'mine',owner:'admin'},
 {id:'alias',owner:'工号001',owner_staff:{username:'admin'}},
 {id:'other',owner:'east',_owner:'admin',can_complete:true},
 {id:'resolved-other',owner:'admin',owner_staff:{username:'east'}},
 {id:'unassigned',_owner:'admin',created_by:'admin'},
]
assert.equal(exports.personalFollowups(tasks,'admin').map(t=>t.id).join(','),'mine,alias')
assert.equal(exports.personalFollowups(tasks,'').length,0)
assert.equal(tasks.length,5)
console.log('PASS personal assignment excludes storage ownership, completion permission, unassigned and conflicting resolved account')
