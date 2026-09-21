import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const source = fs.readFileSync(new URL('../src/views/CrmAssistantView/dashboard/amapDistrictCache.ts', import.meta.url), 'utf8')
const storage = new Map()
const sessionStorage = { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v) }
function load() {
  const exports = {}
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports, sessionStorage, setTimeout, clearTimeout })
  return exports.searchDistrict
}
const search = load(), calls = []
const sdk = { DistrictSearch: class {
  constructor(options) { this.options = options }
  search(name, done) { calls.push({ name, done, options: this.options }) }
} }
const request = search(sdk, '湖南', 'province', 'all')
assert.equal(search(sdk, '湖南', 'province', 'all'), request, 'deduplicate in-flight requests')
calls[0].done('complete', { districtList: [{ name:'湖南省',level:'province',center:{lng:112,lat:28},boundaries:[[{lng:112,lat:28},{lng:113,lat:29}]] }] })
assert.equal((await request).boundaries[0][0][0], 112)
await search(sdk,'湖南','province','all')
await load()(sdk,'湖南','province','all')
assert.equal(calls.length,1,'reuse geometry after component/module recreation')
const requests = Array.from({ length:7 },(_,i)=>search(sdk,`城市${i}`,'city','base'))
assert.equal(calls.length,5,'limit active requests to four')
for(let i=1;i<8;i++) {
  const call=calls[i]
  call.done('complete',{ districtList:[{ name:call.name+'市',level:'city',center:[110+i,30] }] })
}
assert.equal((await Promise.all(requests)).length,7)
const failure=search(sdk,'失败','city','base')
calls.at(-1).done('error',{})
assert.equal(await failure,null)
const retry=search(sdk,'失败','city','base')
calls.at(-1).done('complete',{districtList:[{name:'失败市',level:'city',center:[110,30]}]})
assert.ok(await retry,'failed requests do not poison cache')
console.log('PASS shared cache, reload cache, in-flight deduplication, concurrency limit, normalization, failure retry')
