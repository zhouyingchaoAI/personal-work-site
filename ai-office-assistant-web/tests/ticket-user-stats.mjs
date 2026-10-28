import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
const source = fs.readFileSync(new URL('../src/views/WorkOrderView/ticketUserStats.ts',import.meta.url),'utf8')
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports})
const records = [
  {author:'同名',author_username:'a',module:'联指经营助手',closed:false},
  {author:'同名',author_username:'a',module:'邮件助手',closed:true},
  {author:'同名',author_username:'b',module:'邮件助手',closed:false},
  {author:'同名',module:'',closed:false},
]
const stats = exports.ticketUserStats(records)
assert.equal(stats.length,3)
assert.equal(stats[0].total,2)
assert.equal(stats[0].open,1)
assert.equal(stats[0].closed,1)
assert.equal(stats[0].modules.length,2)
assert.equal(stats.reduce((sum,user)=>sum+user.total,0),records.length)
assert.equal(exports.ticketUserStats([]).length,0)
assert.notEqual(exports.ticketUserKey(records[0]),exports.ticketUserKey(records[2]))
assert.notEqual(exports.ticketUserKey(records[0]),exports.ticketUserKey(records[3]))
console.log('PASS user counts, assistant distribution, same-name accounts, legacy separation, empty data')
