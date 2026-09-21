<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import type { CrmGraphNode, CrmGraphEdge } from '../../services/personalWorkApi'
const props=defineProps<{graph:{nodes:CrmGraphNode[];edges:CrmGraphEdge[]}}>()
const emit=defineEmits<{select:[id:string,kind:string]}>()
const uid='radial'+useId().replace(/\W/g,'')
const focus=ref(''), page=ref(0), history=ref<string[]>([])
const colors=['#ad85ff','#f5c242','#23e0d0','#378bff','#f97316']
const types=['主管单位','业主单位','总包单位','设计单位','厂商']
const byId=computed(()=>new Map(props.graph.nodes.map(n=>[n.id,n])))
const parents=computed(()=>{const m=new Map<string,string>();props.graph.edges.forEach(e=>{if(e.relation_kind==='belongs'||e.relation_kind==='reports'&&byId.value.get(e.target)?.kind==='unit')m.set(e.target,e.source)});return m})
const contacts=computed(()=>props.graph.edges.filter(e=>e.relation_kind==='contact'))
function under(id:string,root:string){const seen=new Set<string>();while(id&&!seen.has(id)){if(id===root)return true;seen.add(id);id=parents.value.get(id)||''}return false}
function stats(id:string){const edges=contacts.value.filter(e=>under(e.target,id)||under(e.source,id));return {count:edges.length,strong:edges.some(e=>e.strength>=4),days:edges.map(e=>e.days_since_touch).filter((d):d is number=>d!==null&&d!==undefined).sort((a,b)=>a-b)[0]}}
function color(n:CrmGraphNode){return colors[types.indexOf(n.type)]||'#f5c242'}
const clusters=computed(()=>types.map((type,i)=>{const a=(-90+i*(360/types.length))*Math.PI/180;return {type,color:colors[i],x:450+Math.cos(a)*260,y:335+Math.sin(a)*205,units:props.graph.nodes.filter(n=>n.kind==='unit'&&n.type===type)}}))
function satellites(c:typeof clusters.value[number]){return c.units.slice(0,4).map((node,i,arr)=>{const a=(-155+i*250/Math.max(1,arr.length-1))*Math.PI/180;return {node,x:c.x+Math.cos(a)*85,y:c.y+Math.sin(a)*77,...stats(node.id)}})}
const center=computed(()=>focus.value.startsWith('type:')?focus.value.slice(5):byId.value.get(focus.value)?.label||'我方')
const children=computed(()=>{
 if(focus.value.startsWith('type:'))return props.graph.nodes.filter(n=>n.kind==='unit'&&n.type===focus.value.slice(5))
 const list=props.graph.nodes.filter(n=>parents.value.get(n.id)===focus.value)
 if(list.length)return list
 const ids=new Set(contacts.value.flatMap(e=>e.source===focus.value?[e.target]:e.target===focus.value?[e.source]:[]))
 return props.graph.nodes.filter(n=>ids.has(n.id))
})
const isContact=computed(()=>!props.graph.nodes.some(n=>parents.value.get(n.id)===focus.value)&&!focus.value.startsWith('type:'))
const points=computed(()=>children.value.slice(page.value*8,page.value*8+8).map((node,i,arr)=>{const a=(-90+i*360/arr.length)*Math.PI/180;return {node,x:450+Math.cos(a)*265,y:330+Math.sin(a)*205,...stats(node.id)}}))
const pages=computed(()=>Math.ceil(children.value.length/8))
const manager=computed(()=>{const e=props.graph.edges.find(e=>e.relation_kind==='reports'&&e.target===focus.value);return e?byId.value.get(e.source)?.label:''})
function enter(id:string){history.value.push(focus.value);focus.value=id;page.value=0}
function back(){focus.value=history.value.pop()||'';page.value=0}
function home(){focus.value='';page.value=0;history.value=[]}
function short(s:string,max=12){return s.length>max?s.slice(0,max)+'…':s}
function icon(type:string){return type==='业主单位'?'M -15 -20 Q 0 -27 15 -20 L 15 7 Q 0 15 -15 7 Z M -10 -15 H 10 V -3 H -10 Z M -12 18 L -7 10 M 12 18 L 7 10 M -8 5 H -5 M 5 5 H 8':type==='设计单位'?'M -20 15 L 8 -23 L 24 15 Z M -4 15 L 10 -5 L 17 15 M -18 23 H 23':type==='主管单位'?'M -24 -10 L 0 -26 L 24 -10 Z M -18 -5 V 18 M -6 -5 V 18 M 6 -5 V 18 M 18 -5 V 18 M -24 23 H 24':'M -20 23 V -15 H 3 V 23 M 3 -5 H 19 V 23 M -14 -8 H -7 M -14 0 H -7 M -14 8 H -7 M 8 3 H 13 M 8 11 H 13 M -25 23 H 24'}
</script>
<template>
 <div class="radial-org">
  <div class="radial-tools"><span>五类分区 · 点击光点逐层展开组织与对接</span><div v-if="focus"><button @click="back">‹ 上一层</button><button @click="home">全局视图</button><button v-if="byId.get(focus) && ['staff','person','unit'].includes(byId.get(focus)!.kind)" @click="emit('select',focus,byId.get(focus)!.kind)">查看档案 ↗</button></div></div>
  <svg viewBox="0 0 900 660" class="radial-canvas" role="img" aria-label="五类分区组织与客户对接图">
   <defs><radialGradient :id="uid+'bg'"><stop stop-color="#123d5b"/><stop offset="1" stop-color="#041328"/></radialGradient><radialGradient :id="uid+'node'"><stop stop-color="#185475"/><stop offset=".75" stop-color="#092642"/><stop offset="1" stop-color="#1c678b"/></radialGradient><filter :id="uid+'glow'" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter><pattern :id="uid+'grid'" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#2589b4" stroke-opacity=".1"/></pattern></defs>
   <rect width="900" height="660" :fill="'url(#'+uid+'bg)'"/><rect width="900" height="660" :fill="'url(#'+uid+'grid)'"/>
   <g fill="none" stroke="#20bed9"><ellipse cx="450" cy="355" rx="110" ry="35" stroke-width="3" opacity=".6"/><ellipse cx="450" cy="355" rx="130" ry="45" stroke-dasharray="70 15 4 15" opacity=".7"/><circle cx="450" cy="335" r="290" stroke-dasharray="3 12" opacity=".2"/><circle cx="450" cy="335" r="310" opacity=".1"/></g>
   <template v-if="!focus">
    <g v-for="c in clusters" :key="c.type">
     <line x1="450" y1="335" :x2="c.x" :y2="c.y" :stroke="c.color" stroke-width="2" stroke-opacity=".7"/>
     <circle :cx="c.x" :cy="c.y" r="95" fill="none" :stroke="c.color" stroke-dasharray="4 9" opacity=".22"/>
     <g v-for="p in satellites(c)" :key="p.node.id" class="radial-node" role="button" tabindex="0" :aria-label="p.node.label" @click="enter(p.node.id)" @keydown.enter.prevent="enter(p.node.id)">
      <line :x1="c.x" :y1="c.y" :x2="p.x" :y2="p.y" :stroke="p.count ? c.color : '#70859c'" :stroke-dasharray="p.count ? undefined : '4 5'"/>
      <circle :cx="p.x" :cy="p.y" r="10" :fill="p.count ? c.color : '#153b55'" :stroke="c.color" :filter="'url(#'+uid+'glow)'"/>
      <text :x="p.x" :y="p.y-20" text-anchor="middle" class="satellite-label">{{ short(p.node.label,10) }}</text><title>{{ p.node.label }} · {{ p.count }} 条已登记对接</title>
     </g>
     <g class="radial-node" role="button" tabindex="0" :aria-label="c.type" @click="enter('type:'+c.type)" @keydown.enter.prevent="enter('type:'+c.type)">
      <circle :cx="c.x" :cy="c.y" r="44" :fill="'url(#'+uid+'node)'" :stroke="c.color" stroke-width="3" :filter="'url(#'+uid+'glow)'"/>
      <path :d="icon(c.type)" :transform="'translate('+c.x+','+(c.y-8)+') scale(.65)'" fill="none" :stroke="c.color" stroke-width="3"/>
      <text :x="c.x" :y="c.y+25" text-anchor="middle" class="cluster-label">{{ c.type }}</text>
      <text :x="c.x" :y="c.y+60" text-anchor="middle" class="count-label">{{ c.units.length }} 家单位{{ c.units.length>4?' · 点击查看全部':'' }}</text>
     </g>
    </g>
   </template>
   <template v-else>
    <g v-for="p in points" :key="p.node.id" class="radial-node" role="button" tabindex="0" :aria-label="p.node.label" @click="enter(p.node.id)" @keydown.enter.prevent="enter(p.node.id)">
     <line x1="450" y1="330" :x2="p.x" :y2="p.y" :stroke="isContact?'#23e0d0':color(p.node)" :stroke-dasharray="isContact?undefined:'5 6'" opacity=".65"/>
     <circle :cx="p.x" :cy="p.y" r="26" :fill="'url(#'+uid+'node)'" :stroke="color(p.node)" stroke-width="2" :filter="'url(#'+uid+'glow)'"/>
     <text :x="p.x" :y="p.y+5" text-anchor="middle" class="count-label">{{ p.node.kind==='person'||p.node.kind==='staff'?'人员':p.node.kind==='unit'?'单位':p.node.id.startsWith('org:job:')?'岗位':p.node.id.startsWith('org:company:')?'公司':'部门' }}</text>
     <text :x="p.x" :y="p.y+47" text-anchor="middle" class="satellite-label">{{ short(p.node.label,16) }}</text><title>{{ p.node.label }}</title>
    </g>
   </template>
   <g class="radial-node" role="button" tabindex="0" aria-label="我方组织" @click="!focus && enter('self')" @keydown.enter.prevent="!focus && enter('self')">
    <circle cx="450" cy="330" r="61" fill="#30270f" stroke="#f5c242" stroke-width="3" :filter="'url(#'+uid+'glow)'"/><circle cx="450" cy="330" r="68" fill="none" stroke="#f5c242" opacity=".4"/>
    <path v-if="!focus" :d="icon('我方')" transform="translate(450,311) scale(.65)" fill="none" stroke="#ffdf7b" stroke-width="3"/>
    <text x="450" :y="focus?335:357" text-anchor="middle" class="center-label">{{ short(center,7) }}</text><title>{{ center }}</title>
   </g>
   <text v-if="focus" x="450" y="610" text-anchor="middle" class="count-label">{{ isContact ? '已登记对接人员' : '下一级组织' }} · {{ children.length }} 项{{ manager ? ' · 直属上级：'+manager : '' }}</text>
   <text v-if="focus && !children.length" x="450" y="440" text-anchor="middle" class="count-label">暂无下级组织或已登记对接关系</text>
   <text v-if="!focus" x="450" y="635" text-anchor="middle" class="count-label">中心查看我方组织 · 五类节点查看客户单位 · 连线表示分区归属，不代表关系强度</text>
  </svg>
  <div v-if="pages>1 && focus" class="radial-pager"><button :disabled="!page" @click="page--">上一页</button><span>{{page+1}} / {{pages}}</span><button :disabled="page+1>=pages" @click="page++">下一页</button></div>
 </div>
</template>
<style scoped>
.radial-org{position:relative;flex:1;min-height:0;height:470px;display:flex;flex-direction:column;background:#06182b;border:1px solid #1c6583;border-radius:10px;overflow:hidden;box-shadow:inset 0 0 28px #007eb426}.radial-tools{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;color:#72bdd5;font-size:11px;padding:8px 12px;flex-shrink:0}.radial-tools button,.radial-pager button{background:#10314a;color:#9ce4ef;border:1px solid #2d7892;border-radius:4px;padding:4px 8px;cursor:pointer;margin-left:6px}.radial-canvas{width:100%;height:0;flex:1;min-height:0}.radial-node{cursor:pointer;outline:none}.radial-node:focus-visible circle{stroke:white;stroke-width:4}.cluster-label{fill:#e0f6ff;font-size:18px;font-weight:700}.satellite-label{fill:#c3e4f5;font-size:13px}.count-label{fill:#8fc4d9;font-size:11px}.center-label{fill:#ffe49a;font-size:22px;font-weight:700}.radial-pager{position:absolute;bottom:8px;right:10px;font-size:12px;color:#b5dbea}.radial-pager button:disabled{opacity:.4}
</style>
