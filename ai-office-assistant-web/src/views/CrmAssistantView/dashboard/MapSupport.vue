<script setup lang="ts">
import type { CrmPlaybook } from '../../../services/personalWorkApi'
import CustomerDistribution from './CustomerDistribution.vue'
defineProps<{ kind: 'customers' | 'tasks'; scope: string; groups: {type:string;color:string;units:number;people:number}[]; total: number; followups: NonNullable<CrmPlaybook>['followups']; warnings: number; compact?: boolean }>()
const emit = defineEmits<{ navigate: [tab: 'archive' | 'workflow' | 'relation' | 'overview']; followup: [relationId?: string] }>()
</script>
<template>
 <section class="map-support" :class="{compact}">
  <header><div><h3>{{ kind === 'customers' ? '客户概况' : '优先跟进' }}</h3><small>{{ scope }}</small></div><button @click="kind === 'customers' ? emit('navigate','archive') : emit('followup')">{{ kind === 'customers' ? '档案 →' : '全部 →' }}</button></header>
  <CustomerDistribution v-if="kind === 'customers'" :groups="groups" :total="total" @archive="emit('navigate','archive')" />
  <template v-else>
   <div v-if="followups.length" class="map-support__tasks"><button v-for="(item,i) in followups.slice(0,compact ? 3 : 4)" :key="item.relation_id + ':' + i" @click="emit('followup',item.relation_id)"><span>{{ item.next_step || '跟进客户关系' }}</span><small :class="{overdue:item.overdue}">{{ item.overdue ? '逾期 · ' : '' }}{{ item.due_date || '日期待定' }}</small></button></div>
   <p v-else class="empty">暂无待跟进行动</p>
   <button v-if="warnings" class="warning" @click="emit('navigate','overview')">{{ warnings }} 条关系待维系 →</button>
  </template>
 </section>
</template>
<style scoped>
.map-support { min-width:0;padding:16px;border:1px solid #294c69;border-radius:10px;background:#0a2036e8;color:#d9e9fa; }
header {display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:14px;} h3 {margin:0;font-size:15px;} small {display:block;color:#91afc8;font-size:11px;margin-top:4px;}
button {cursor:pointer;font:inherit;color:#7ce4df;border:0;background:transparent;font-size:12px;} button:focus-visible {outline:2px solid #53e9e0;outline-offset:2px;}
.map-support__tasks button {display:block;width:100%;text-align:left;border-bottom:1px solid #24415b;padding:9px 0;color:#d9e9fa;}.map-support__tasks span {display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.overdue,.warning {color:#ffd078;}.warning {margin-top:10px;padding:0;}.empty {font-size:12px;color:#91afc8;padding:12px 0;}.compact {padding:12px;}.compact header {margin-bottom:8px;}.compact .map-support__tasks button {padding:6px 0;}.compact h3 {font-size:13px;}
</style>
