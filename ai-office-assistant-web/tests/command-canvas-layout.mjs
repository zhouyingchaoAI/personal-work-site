import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const exports = {}
const source = fs.readFileSync(new URL('../packages/joint-command/frontend/command/useCanvasScale.ts', import.meta.url), 'utf8')
const callbacks = []
let rootFont = '10px'
vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText, {
  exports,
  require: () => ({ ref: value => ({value}), computed: callback => ({get value(){return callback()}}), onMounted: callback => callbacks.push(callback), onBeforeUnmount: () => {}, watch: () => {} }),
  getComputedStyle: () => ({fontSize:rootFont}),
  document: {documentElement:{}},
  window: {addEventListener:()=>{},removeEventListener:()=>{}},
})
const enabled = {value:true}
const target = {value:{clientWidth:1000,clientHeight:200}}
const canvas = exports.useCanvasScale(target,1000,800,enabled)
canvas.update()
assert.equal(canvas.scale.value,1,'short windows must scroll instead of shrinking content and leaving wide gutters')
assert.equal(canvas.style.value.transform,'scale(1)')
assert.ok(canvas.frameStyle.value.height.includes('80rem'))
target.value.clientWidth=600
canvas.update()
assert.equal(canvas.scale.value,0.6)
rootFont='20px'
canvas.update()
assert.equal(canvas.scale.value,0.3,'browser/root-font zoom must preserve width fit')
enabled.value=false
assert.equal(canvas.style.value,undefined)
assert.equal(canvas.frameStyle.value,undefined)
console.log('Command canvas layout tests passed')
