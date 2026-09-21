<script setup lang="ts">
import { computed, ref, reactive, watch, nextTick } from 'vue'
import type { CrmUnit, CrmPerson } from '../../services/personalWorkApi'
import { layoutOrganization } from './organizationLayout'
const props=defineProps<{units:CrmUnit[];people:CrmPerson[];person?:CrmPerson}>()
const full=ref(false),stage=ref<HTMLElement>(),view=reactive({x:20,y:20,zoom:1})
const graph=computed(()=>{
 const unitById=new Map(props.units.map(u=>[u.id,u])),current=unitById.get(props.person?.unit_id||'')
 if(!current)return {nodes:[] as {id:string;parent:string;label:string;kind:string}[],focus:'',root:''}
 let root=current;const visited=new Set([root.id]);while(root.parent_unit_id&&unitById.has(root.parent_unit_id)&&!visited.has(root.parent_unit_id)){root=unitById.get(root.parent_unit_id)!;visited.add(root.id)}
 const ids=new Set([root.id]);let changed=true;while(changed){changed=false;for(const u of props.units)if(u.parent_unit_id&&ids.has(u.parent_unit_id)&&!ids.has(u.id)){ids.add(u.id);changed=true}}
 const nodes=props.units.filter(u=>ids.has(u.id)).map(u=>({id:'unit:'+u.id,parent:u.id===root.id?'':'unit:'+u.parent_unit_id,label:u.name,kind:'组织'}))
 const seen=new Set(nodes.map(n=>n.id));let focus='unit:'+current.id
 for(const p of props.people.filter(p=>ids.has(p.unit_id))){let parent='unit:'+p.unit_id;const parts=(p.department||'').split('/').map(s=>s.trim()).filter(Boolean)
  for(let i=0;i<parts.length;i++){const id='dept:'+JSON.stringify([p.unit_id,...parts.slice(0,i+1)]);if(!seen.has(id)){nodes.push({id,parent,label:parts[i]!,kind:'部门'});seen.add(id)}parent=id}
  nodes.push({id:'person:'+p.id,parent,label:p.name+(p.title?' · '+p.title:''),kind:'人员'})
  if(p.id===props.person?.id)focus=parent
 }
 return {nodes,focus,root:'unit:'+root.id}
})
const nodes=computed(()=>{const start=full.value?graph.value.root:graph.value.focus,ids=new Set([start]);let changed=true;while(changed){changed=false;for(const n of graph.value.nodes)if(ids.has(n.parent)&&!ids.has(n.id)){ids.add(n.id);changed=true}}return graph.value.nodes.filter(n=>ids.has(n.id)).map(n=>({...n,parent:n.id===start?'':n.parent}))})
const positions=computed(()=>layoutOrganization(nodes.value))
function fit(){const ps=Object.values(positions.value);if(!ps.length||!stage.value)return;const w=Math.max(...ps.map(p=>p.x))+230,h=Math.max(...ps.map(p=>p.y))+132;view.zoom=Math.min(1,(stage.value.clientWidth-40)/w,(stage.value.clientHeight-40)/h);view.x=(stage.value.clientWidth-w*view.zoom)/2;view.y=(stage.value.clientHeight-h*view.zoom)/2}
function zoom(factor:number){const next=Math.max(.08,Math.min(2,view.zoom*factor)),x=(stage.value?.clientWidth||600)/2,y=(stage.value?.clientHeight||300)/2;view.x=x-(x-view.x)*next/view.zoom;view.y=y-(y-view.y)*next/view.zoom;view.zoom=next}
watch(()=>props.person?.id,()=>{full.value=false})
watch(nodes,()=>void nextTick(fit),{immediate:true})
let drag:{x:number;y:number;vx:number;vy:number}|null=null
function down(e:PointerEvent){if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y};stage.value?.setPointerCapture(e.pointerId)}
function move(e:PointerEvent){if(drag){view.x=drag.vx+e.clientX-drag.x;view.y=drag.vy+e.clientY-drag.y}}
</script>
<template>
<section class="fo-organization" aria-label="跟进客户组织架构"><header><div><b>客户组织架构</b><small>{{full?'该客户全部架构':'当前联系人所在子架构'}} · 人员仅显示当前查看范围</small></div><div><button :aria-pressed="!full" @click="full=false">所在子架构</button><button :aria-pressed="full" @click="full=true">全部架构</button><button @click="zoom(1.25)">放大</button><button @click="zoom(.8)">缩小</button><button @click="fit">适应</button></div></header>
 <div ref="stage" class="fo-stage" @pointerdown="down" @pointermove="move" @pointerup="drag=null" @pointercancel="drag=null">
  <p v-if="!nodes.length">该联系人的组织归属尚未补充，暂无法绘制架构。</p>
  <div v-else class="fo-world" :style="{transform:`translate(${view.x}px,${view.y}px) scale(${view.zoom})`}"><svg><path v-for="n in nodes.filter(n=>n.parent&&positions[n.parent])" :key="n.id" :d="`M${positions[n.parent]!.x+115},${positions[n.parent]!.y+110} V${positions[n.id]!.y-36} H${positions[n.id]!.x+115} V${positions[n.id]!.y}`"/></svg><article v-for="n in nodes" :key="n.id" :data-org-node="n.id" :class="{current:n.id==='person:'+person?.id,department:n.kind==='部门'}" :style="{left:positions[n.id]!.x+'px',top:positions[n.id]!.y+'px'}"><small>{{n.kind}}{{n.id==='person:'+person?.id?' · 当前联系人':''}}</small><strong :title="n.label">{{n.label}}</strong></article></div>
 </div>
</section>
</template>
<style scoped>.fo-organization{border:1px solid #315371;border-radius:10px;overflow:hidden;margin:16px 0;background:#0b2238;color:#dcedff}.fo-organization header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:12px}.fo-organization header small{display:block;color:#8daeca;font-size:11px;margin-top:5px}.fo-organization header button{border:1px solid #355872;border-radius:5px;background:#122e47;color:#b9d4eb;cursor:pointer;padding:5px 8px;margin:2px;font-size:12px}.fo-organization button[aria-pressed=true]{background:#15526a;border-color:#39c7d4;color:#dfffff}.fo-stage{position:relative;height:290px;overflow:hidden;touch-action:none;cursor:grab;background:radial-gradient(#365879 1px,transparent 1px);background-size:20px 20px}.fo-stage>p{padding:30px;font-size:13px;color:#a0bed7}.fo-world{position:absolute;transform-origin:0 0}.fo-world svg{position:absolute;width:1px;height:1px;overflow:visible;pointer-events:none}.fo-world path{stroke:#5a89ae;stroke-width:2;fill:none}.fo-world article{position:absolute;box-sizing:border-box;width:230px;height:110px;padding:15px;background:#173753;border:1px solid #468ac1;border-top:4px solid #459af0;border-radius:9px}.fo-world article.department{border-top-color:#b994ff}.fo-world article.current{border:2px solid #36dfd0;background:#12454b;box-shadow:0 0 20px #36dfd025}.fo-world article small{display:block;color:#9bbcd5;font-size:12px;margin-bottom:8px}.fo-world article strong{font-size:15px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}</style>
