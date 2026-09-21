<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CrmGraphNode, CrmGraphEdge } from '../../services/personalWorkApi'
import OrganizationBranch, { type Branch } from './OrganizationBranch.vue'
const props=defineProps<{graph:{nodes:CrmGraphNode[];edges:CrmGraphEdge[]}}>()
const emit=defineEmits<{select:[id:string,kind:string]}>()
const selected=ref('')
const byId=computed(()=>new Map(props.graph.nodes.map(n=>[n.id,n])))
const parent=computed(()=>{const m=new Map<string,string>();for(const e of props.graph.edges)if(e.relation_kind==='belongs'||e.relation_kind==='reports'&&byId.value.get(e.target)?.kind==='unit')m.set(e.target,e.source);return m})
function tree(n:CrmGraphNode,seen=new Set<string>()):Branch {
 const next=new Set(seen).add(n.id)
 const manager=props.graph.edges.find(e=>e.relation_kind==='reports'&&e.target===n.id)
 return {node:n,manager:manager?byId.value.get(manager.source)?.label||'':'',children:props.graph.nodes.filter(c=>parent.value.get(c.id)===n.id&&!next.has(c.id)).map(c=>tree(c,next))}
}
const own=computed(()=>props.graph.nodes.filter(n=>parent.value.get(n.id)==='self').map(n=>tree(n)))
const customers=computed(()=>props.graph.nodes.filter(n=>n.kind==='unit'&&!parent.value.has(n.id)).map(n=>tree(n)))
function within(id:string,ancestor:string){const seen=new Set<string>();while(id&&!seen.has(id)){if(id===ancestor)return true;seen.add(id);id=parent.value.get(id)||''}return false}
const contacts=computed(()=>props.graph.edges.filter(e=>e.relation_kind==='contact'&&(!selected.value||within(e.source,selected.value)||within(e.target,selected.value))))
const active=computed(()=>{const ids=new Set<string>();for(const e of contacts.value)for(let id of [e.source,e.target]){while(id&&!ids.has(id)){ids.add(id);id=parent.value.get(id)||''}}return ids})
function focus(id:string){selected.value=selected.value===id?'':id}
function path(id:string){const labels:string[]=[];const seen=new Set<string>();while(id&&id!=='self'&&!seen.has(id)){seen.add(id);labels.unshift(byId.value.get(id)?.label||id);id=parent.value.get(id)||''}return labels.join(' / ')}
</script>
<template>
 <div class="organization-map">
  <div class="org-instruction"><span>按组织逐级查看 · 点击节点筛选对接 · ↗ 查看档案</span><button v-if="selected" @click="selected=''">清除筛选</button></div>
  <div class="org-columns">
   <section><header>我方组织<small>公司 → 部门 → 岗位 → 人员</small></header><div class="org-scroll"><ul><OrganizationBranch v-for="b in own" :key="b.node.id" :branch="b" :active="active" :selected="selected" @focus="focus" @detail="(id,kind)=>emit('select',id,kind)" /></ul><p v-if="!own.length">尚未登记我方人员</p></div></section>
   <section class="connections"><header>双方对接<small>{{ selected ? '当前节点' : '全部' }} · {{ contacts.length }} 条关系</small></header><div class="org-scroll"><article v-for="(e,i) in contacts" :key="i"><button @click="focus(e.source)" :title="path(e.source)">{{ byId.get(e.source)?.label }}</button><div class="arrow">↓ 对接 ↓</div><button @click="focus(e.target)" :title="path(e.target)">{{ byId.get(e.target)?.label }}</button></article><p v-if="!contacts.length">该节点暂无已登记对接关系</p></div></section>
   <section><header>客户组织<small>单位 → 部门 → 联系人</small></header><div class="org-scroll"><ul><OrganizationBranch v-for="b in customers" :key="b.node.id" :branch="b" :active="active" :selected="selected" @focus="focus" @detail="(id,kind)=>emit('select',id,kind)" /></ul><p v-if="!customers.length">尚未登记客户组织</p></div></section>
  </div>
 </div>
</template>
<style scoped>
.organization-map{height:470px;min-height:0;flex:1;display:flex;flex-direction:column;color:#d5e9ff;background:#081c30;border-radius:8px;overflow:hidden}.org-instruction{padding:8px 10px;font-size:11px;color:#95b6ce;display:flex;justify-content:space-between;gap:8px}.org-instruction button{background:transparent;border:0;color:#f5c242;cursor:pointer}.org-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(110px,.65fr) minmax(0,1fr);gap:8px;flex:1;min-height:0;padding:0 8px 8px}section{border:1px solid #2a506a;border-radius:8px;min-width:0;display:flex;flex-direction:column;overflow:hidden}header{padding:10px;color:#7ee7e0;border-bottom:1px solid #29485e;font-size:14px;font-weight:600;flex-shrink:0}header small{display:block;color:#8dadc8;font-size:10px;font-weight:400;margin-top:5px}.org-scroll{overflow:auto;min-height:0;padding:6px;scrollbar-width:thin;scrollbar-color:#3b6a82 #10263a}ul{margin:0;padding:0}p{font-size:12px;color:#93b0ca;padding:8px}article{border:1px solid #315264;border-radius:6px;background:#102b40;padding:8px;margin-bottom:8px;text-align:center}article button{background:none;border:0;color:#e3effa;cursor:pointer;font-size:12px;overflow-wrap:anywhere;line-height:1.6}.arrow{font-size:10px;color:#23e0d0;padding:3px}
</style>
