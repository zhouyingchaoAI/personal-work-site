import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const source=fs.readFileSync(new URL('../packages/joint-command/frontend/dashboard/AmapBaseMap.vue',import.meta.url),'utf8').split('<script setup lang="ts">')[1].split('</script>')[0]
const watchers=[], requests=[], overlays=[], frames=new Map()
let creates=0, frameId=0
const props={regions:['东区','西区'],selected:'',units:[],showCities:false,showCompanies:false}
const target={remove:()=>{},add:items=>overlays.push(...items),setFitView:()=>{},setZoomAndCenter:()=>{}}
const sdk={Polygon:class{constructor(options){this.options=options;creates++}on(){}setOptions(options){Object.assign(this.options,options)}}}
const modules={
 vue:{ref:()=>({value:undefined}),watch:(read,callback)=>watchers.push({read,callback}),onMounted:()=>{},onBeforeUnmount:()=>{}},
 './chinaMapData':{REGION_PROVINCES:{'东区':['浙江'],'西区':['四川','浙江']},REGION_CITIES:{},REGION_COLORS:{'东区':'blue','西区':'green'}},
 './amapDistrictCache':{searchDistrict:(_sdk,name)=>new Promise(resolve=>requests.push({name,resolve}))},
}
const context={exports:{},defineProps:()=>props,defineEmits:()=>()=>{},require:name=>modules[name]||{},setTimeout,clearTimeout,
 requestAnimationFrame:fn=>{frames.set(++frameId,fn);return frameId},cancelAnimationFrame:id=>frames.delete(id),target,sdkMock:sdk}
vm.runInNewContext(ts.transpileModule(source+'\nmap=target;sdk=sdkMock;exports.draw=draw;', {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,context)
const draw=context.exports.draw()
assert.equal(requests.length,2,'shared province must be requested and drawn once, not once per region')
requests.find(r=>r.name==='浙江').resolve({boundaries:[[[120,30],[121,31],[120,30]]]})
await new Promise(resolve=>setImmediate(resolve))
assert.equal(overlays.length,1,'first boundary must render while another request is pending')
assert.equal(overlays[0].options.fillColor,'#e8d59c','shared province has a neutral deterministic color')
assert.equal(overlays[0].options.strokeStyle,'dashed')
const selection=watchers.find(w=>w.read()===props.selected)
assert.ok(selection,'selection has its own watcher')
props.selected='东区';selection.callback()
for(const fn of frames.values())fn();frames.clear()
assert.equal(creates,1,'region click reuses polygon objects')
assert.equal(requests.length,2,'region click issues no new geometry requests')
assert.equal(overlays[0].options.strokeColor,'#e4ffff')
assert.equal(overlays[0].options.fillColor,'blue')
requests.find(r=>r.name==='四川').resolve({boundaries:[[[103,30],[104,31],[103,30]]]})
await draw
props.selected='西区';selection.callback()
for(const fn of frames.values())fn();frames.clear()
assert.equal(creates,2)
assert.equal(overlays[0].options.fillOpacity,0.3,'shared province remains highlighted when selecting either owner')
assert.equal(overlays[1].options.strokeColor,'#e4ffff')
assert.equal(overlays[0].options.fillColor,'green','shared shape takes selected region color without adding polygons')
props.selected='东区';selection.callback()
for(const fn of frames.values())fn();frames.clear()
assert.equal(overlays[1].options.fillOpacity,0.012,'unshared province from another region dims')
assert.equal(creates,2)
console.log('PASS progressive boundaries, independent selection, no requests or reconstruction on region click')
