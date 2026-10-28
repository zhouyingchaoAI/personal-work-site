<script setup lang="ts">
import type { CrmPlaybook } from '../../../../src/services/personalWorkApi'
import CustomerDistribution from './CustomerDistribution.vue'
defineProps<{ kind: 'customers' | 'tasks'; scope: string; groups: {type:string;color:string;units:number;people:number}[]; total: number; followups: NonNullable<CrmPlaybook>['followups']; warnings: number; compact?: boolean; activeType?: string; health?: { strong: number; warning: number; alarm: number; single: number } }>()
const emit = defineEmits<{ navigate: [tab: 'archive' | 'workflow' | 'relation' | 'overview']; followup: [relationId?: string]; type: [value: string] }>()
</script>
<template>
 <section class="map-support" :class="{compact}">
  <header><div><h3>{{ kind === 'customers' ? '客户概况' : '优先跟进' }}<b v-if="kind === 'tasks' && followups.length" class="map-support__count">{{ followups.length }}</b></h3><small>{{ scope }}</small></div><button @click="kind === 'customers' ? emit('navigate','archive') : emit('followup')">{{ kind === 'customers' ? '档案 →' : '全部 →' }}</button></header>
  <template v-if="kind === 'customers'">
   <div v-if="health" class="map-support__health" role="group" aria-label="关系健康">
    <button title="强度 L3 及以上的在维关系（可信任/可协同/关键盟友）" @click="emit('navigate','overview')"><b class="good">{{ health.strong }}</b><span>L3+ 关系</span></button>
    <button title="超过维系周期的关系，点击查看网络" @click="emit('navigate','overview')"><b class="warn">{{ health.warning }}</b><span>预警</span></button>
    <button title="超过两倍维系周期的关系" @click="emit('navigate','overview')"><b class="bad">{{ health.alarm }}</b><span>告警</span></button>
    <button title="仅一名我方成员触达的客户联系人" @click="emit('navigate','overview')"><b class="single">{{ health.single }}</b><span>单点</span></button>
   </div>
   <CustomerDistribution :groups="groups" :total="total" :active-type="activeType" @archive="emit('navigate','archive')" @type="value => emit('type', value)" />
  </template>
  <template v-else>
   <div v-if="followups.length" class="map-support__tasks"><button v-for="(item,i) in followups.slice(0,compact ? 3 : 4)" :key="item.relation_id + ':' + i" :class="{overdue:item.overdue}" @click="emit('followup',item.relation_id)"><span>{{ item.next_step || '跟进客户关系' }}</span><small><em v-if="item.person_name">{{ item.person_name }} · </em><u :class="{late:item.overdue}">{{ item.overdue ? '逾期 ' : '' }}{{ item.due_date || '日期待定' }}</u></small></button></div>
   <p v-else class="empty">暂无待跟进行动</p>
   <button v-if="warnings" class="warning" @click="emit('navigate','overview')">{{ warnings }} 条关系待维系 →</button>
  </template>
 </section>
</template>
<style scoped>
.map-support { min-width:0;padding:16px;border:1px solid #294c69;border-radius:10px;background:#0a2036e8;color:#d9e9fa; }
header {display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:14px;} h3 {margin:0;font-size:15px;display:flex;align-items:center;gap:7px;} small {display:block;color:#91afc8;font-size:11px;margin-top:4px;}
.map-support__count {min-width:18px;height:18px;padding:0 5px;box-sizing:border-box;border-radius:9px;background:#12456b;color:#8fe8ff;font-size:11px;font-weight:600;line-height:18px;text-align:center;}
button {cursor:pointer;font:inherit;color:#7ce4df;border:0;background:transparent;font-size:12px;} button:focus-visible {outline:2px solid #53e9e0;outline-offset:2px;}
.map-support__health {display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-bottom:10px;}
.map-support__health button {display:flex;flex-direction:column;align-items:center;gap:1px;padding:6px 2px;border:1px solid rgba(63,110,158,.5);border-radius:7px;background:rgba(14,40,70,.6);transition:border-color .15s,background .15s;}
.map-support__health button:hover {border-color:#4f9fd6;background:rgba(28,70,116,.6);}
.map-support__health b {font-size:16px;line-height:1.1;font-variant-numeric:tabular-nums;}
.map-support__health span {font-size:10px;color:#8aa9c6;}
.map-support__health .good{color:#4ade9d}.map-support__health .warn{color:#ffc46b}.map-support__health .bad{color:#ff7d88}.map-support__health .single{color:#c6a5ff}
.map-support__tasks button {display:block;width:100%;text-align:left;border-bottom:1px solid #24415b;border-left:2px solid transparent;padding:8px 0 8px 8px;color:#d9e9fa;border-radius:0 6px 6px 0;transition:background .15s;}
.map-support__tasks button:hover {background:rgba(64,140,210,.12);}
.map-support__tasks button.overdue {border-left-color:#f59e0b;}
.map-support__tasks span {display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.map-support__tasks small {margin-top:2px;} .map-support__tasks em {font-style:normal;color:#91afc8;}
.map-support__tasks u {text-decoration:none;color:#7fa5c6;} .map-support__tasks u.late {color:#ffd078;font-weight:600;}
.warning {margin-top:10px;padding:0;color:#ffd078;}
.empty {font-size:12px;color:#91afc8;padding:12px 0;}
.compact {padding:12px;} .compact header {margin-bottom:8px;} .compact .map-support__tasks button {padding:6px 0 6px 8px;} .compact h3 {font-size:13px;}
</style>
