import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const file = new URL('../packages/joint-command/frontend/organizationLayout.ts', import.meta.url)
assert.ok(fs.existsSync(file), 'missing centered tree layout')
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports})
const { layoutOrganization } = exports
const nodes = [
 {id:'r',parent:''}, {id:'a',parent:'r'}, {id:'b',parent:'r'}, {id:'c',parent:'r'},
 {id:'a1',parent:'a'}, {id:'a2',parent:'a'}, {id:'b1',parent:'b'},
 {id:'b2',parent:'b1'}, {id:'b3',parent:'b2'}, {id:'b4',parent:'b3'},
]
const p = layoutOrganization(nodes)
assert.equal(p.r.x, (p.a.x+p.c.x)/2, 'parent centered between outer children')
assert.equal(p.a.x, (p.a1.x+p.a2.x)/2)
assert.equal(p.b.x, p.b4.x, 'single-child chain remains vertically aligned')
for (const n of nodes) {
 if(n.parent) assert.ok(p[n.id].y > p[n.parent].y)
 for (const other of nodes) if(other.id!==n.id && p[other.id].y===p[n.id].y)
   assert.ok(Math.abs(p[other.id].x-p[n.id].x)>=270,'sibling branches overlap')
}
assert.equal(Object.keys(layoutOrganization([])).length,0)
assert.equal(Object.keys(layoutOrganization([{id:'a',parent:'b'},{id:'b',parent:'a'}])).length,2,'malformed cycles terminate safely')
const deep=Array.from({length:2000},(_,i)=>({id:String(i),parent:i?String(i-1):''}))
assert.equal(Object.keys(layoutOrganization(deep)).length,2000,'no fixed depth limit')
console.log('PASS centered parents, balanced branches, spacing, deep hierarchy, empty and cyclic inputs')
