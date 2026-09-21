import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../src/views/CrmAssistantView/organizationStats.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
const { organizationStats } = exports
const units = [{id:'root'}, {id:'child',parent_unit_id:'root'}, {id:'leaf',parent_unit_id:'child'}, {id:'empty'}]
const people = [
  {id:'1',unit_id:'root',importance:'一般',support_level:'中立'},
  {id:'2',unit_id:'child',importance:'重要',support_level:'支持'},
  {id:'3',unit_id:'leaf',importance:'重要',support_level:'积极支持'},
  {id:'4',unit_id:'leaf',importance:'',support_level:''},
  {id:'5',unit_id:'missing',importance:'重要',support_level:'支持'},
]
const plain = value => JSON.parse(JSON.stringify(value))
assert.deepEqual(plain(organizationStats(units, people).get('root')), {total:4,important:2,supportive:2,incomplete:1})
assert.deepEqual(plain(organizationStats(units, people).get('child')), {total:3,important:2,supportive:2,incomplete:1})
assert.deepEqual(plain(organizationStats(units, people).get('empty')), {total:0,important:0,supportive:0,incomplete:0})
assert.equal(organizationStats(units.slice(0,2), people).get('root').total, 2, 'excluded descendants must not leak into scoped totals')
assert.equal(organizationStats([{id:'a',parent_unit_id:'b'},{id:'b',parent_unit_id:'a'}], [{id:'p',unit_id:'a'}]).get('a').total, 1, 'cycle must terminate without double counting')
console.log('PASS ancestor totals, support grouping, incomplete counted once, empty/scoped/cyclic organizations')
