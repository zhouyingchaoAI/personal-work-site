<script setup lang="ts">
import { ref } from 'vue'
import type { CrmGraphNode } from '../../services/personalWorkApi'
export interface Branch { node: CrmGraphNode; children: Branch[]; manager: string }
defineProps<{ branch: Branch; active: Set<string>; selected: string }>()
const collapsed = ref(false)
const emit = defineEmits<{ focus: [id: string]; detail: [id: string, kind: string] }>()
</script>
<template>
 <li>
  <div class="branch-row" :class="{active:active.has(branch.node.id),selected:selected===branch.node.id}">
   <button v-if="branch.children.length" class="fold" :aria-expanded="!collapsed" :aria-label="(collapsed ? '展开' : '收起') + branch.node.label" @click="collapsed=!collapsed">{{ collapsed ? '▸' : '▾' }}</button>
   <button class="branch-name" @click="emit('focus',branch.node.id)" :title="branch.node.label"><span class="kind">{{ branch.node.kind==='staff'?'人员':branch.node.kind==='person'?'联系人':branch.node.kind==='unit'?'单位':branch.node.id.startsWith('org:job:')?'岗位':branch.node.id.startsWith('org:company:')?'公司':branch.node.id.startsWith('org:unregistered:')?'待建档':'部门' }}</span>{{ branch.node.label }}<small v-if="branch.manager">直属上级：{{ branch.manager }}</small></button>
   <button v-if="['staff','person','unit'].includes(branch.node.kind)" class="detail" @click="emit('detail',branch.node.id,branch.node.kind)" aria-label="查看详情">↗</button>
  </div>
  <ul v-if="branch.children.length" v-show="!collapsed"><OrganizationBranch v-for="child in branch.children" :key="child.node.id" :branch="child" :active="active" :selected="selected" @focus="emit('focus',$event)" @detail="(id,kind)=>emit('detail',id,kind)" /></ul>
 </li>
</template>
<style scoped>
li{list-style:none;min-width:0}ul{padding:0 0 0 12px;margin:4px 0 8px 8px;border-left:1px solid #3d6782}.branch-row{display:flex;align-items:center;border:1px solid #30536d;border-radius:6px;background:#112d45;margin:5px 0;min-width:0}.branch-row.active{border-color:#23cbbd;background:#123e4c}.branch-row.selected{box-shadow:inset 3px 0 #f5c242;border-color:#f5c242}.branch-name{background:none;border:0;color:#e0efff;text-align:left;padding:8px;flex:1;min-width:0;overflow-wrap:anywhere;cursor:pointer;font-size:12px;line-height:1.5}.kind{display:inline-block;font-size:10px;color:#7dd7dc;margin-right:6px}.branch-name small{display:block;color:#bba8ed;font-size:10px}.fold{background:none;border:0;color:#76bcca;cursor:pointer;padding:6px}.detail{border:0;background:none;color:#77d9ec;cursor:pointer;padding:8px}
</style>
