<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, Calendar, Check, Clock, Flag } from '@element-plus/icons-vue'
import type { CrmOpportunity, CrmPlaybook, CrmRelation, CrmStaff } from '../../../src/services/personalWorkApi'
import { opportunityAttention } from './customerWorkspace'
import ManagementQueue from './ManagementQueue.vue'
import { authState } from '../../../src/services/authSession'
import { personalFollowups } from './personalFollowups'
const props = defineProps<{ staff?:CrmStaff[]; managerView?:boolean; opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups']; relations: CrmRelation[]; canWrite: boolean; canRecord?:boolean; busy: boolean }>()
const emit = defineEmits<{ opportunity: [item: CrmOpportunity | null]; all: []; relation: [id: string]; complete: [id: string]; record: [relation: CrmRelation]; map: [] }>()
const personalOpen=ref(false), filter=ref('all'),staleDays=ref(14),showAll=ref(false),dutyOpen=ref(false)
const managing=computed(()=>props.managerView && !personalOpen.value)
const today = () => new Date().toLocaleDateString('sv-SE')
const dateLabel=computed(()=>new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'}))
const pending=computed(()=>personalFollowups(props.followups,authState.user?.username || '').filter(t=>!t.completed_at))
const overdue = computed(() => pending.value.filter(t => t.due_date && t.due_date < today()).length)
const dueToday = computed(() => pending.value.filter(t => t.due_date === today()).length)
const filtered=computed(()=>pending.value.filter(t=>filter.value==='overdue'?t.due_date&&t.due_date<today():filter.value==='today'?t.due_date===today():true).sort((a,b)=>(a.due_date||'9999').localeCompare(b.due_date||'9999')))
const tasks=computed(()=>showAll.value?filtered.value:filtered.value.slice(0,8))
const reason=(date?:string)=>!date?'未定日期':date<today()?'已逾期':date===today()?'今天到期':'后续跟进'
const warnings = computed(() => props.relations.filter(r => r.decay_state !== 'normal').sort((a,b) => Number(b.decay_state==='alarm') - Number(a.decay_state==='alarm')).slice(0,3))
const attention = computed(() => opportunityAttention(props.opportunities,props.relations,today(),staleDays.value))
const stale = computed(() => attention.value.filter(item=>item.stale))
const unknown = computed(() => attention.value.filter(item=>item.days===null).length)
function openOpportunity(item:CrmOpportunity){emit('opportunity',item)}
function openRelation(id:string){emit('relation',id)}
</script>
<template>
 <section class="crm-workbench">
  <header class="wb-heading">
   <div><p class="wb-date">{{dateLabel}}</p><h2>{{managing?'需要你督办的事':'今天先做这几件事'}}</h2><p v-if="managing" class="wb-intro">看哪些跟进逾期、哪些商机停滞、哪里需要协调。</p><p class="wb-intro" v-else-if="overdue || dueToday"><span v-if="overdue"><b>{{overdue}}</b> 项已逾期</span><span v-if="overdue && dueToday">，</span><span v-if="dueToday"><b>{{dueToday}}</b> 项今天到期</span>。先处理有截止日期的跟进。</p><p class="wb-intro" v-else>今天没有到期事项，看看后续安排，或联系一位客户。</p></div>
   <div class="wb-tools"><el-button v-if="managerView" text @click="personalOpen=!personalOpen">{{managing?'我的跟进':'管理待办'}}</el-button><el-button text :icon="Flag" @click="emit('map')">经营总览</el-button></div>
  </header>
  <section v-if="managing" class="wb-tasks" aria-label="管理待办">
   <button type="button" class="wb-duty-head" :aria-expanded="dutyOpen" @click="dutyOpen=!dutyOpen">
    <el-icon class="wb-duty-arw" :class="{'is-open':dutyOpen}"><ArrowRight/></el-icon>
    <h3>管理待办</h3><span class="wb-scope">当前授权范围 · 按负责人督办</span>
    <span class="wb-duty-toggle">{{dutyOpen?'收起':'展开'}}</span>
   </button>
   <ManagementQueue v-if="dutyOpen" :staff="staff" :opportunities="opportunities" :relations="relations" :followups="followups" @opportunity="openOpportunity" @relation="openRelation"/>
   <p v-else class="wb-duty-hint">督办明细默认收起。上方“四大板块概览”已给出关键结论；需要逐条督办时点此展开。</p>
  </section>
  <div v-else class="wb-layout" :class="{'wb-personal-only':managerView}">
   <section class="wb-tasks" aria-label="跟进待办">
    <div class="wb-section-heading"><h3><el-icon><Calendar/></el-icon>跟进待办 <span>{{pending.length}}</span></h3><span class="wb-scope">仅分配给我的跟进</span></div>
    <div class="wb-filters" role="group" aria-label="待办筛选"><button :aria-pressed="filter==='all'" @click="filter='all'">全部</button><button :aria-pressed="filter==='overdue'" @click="filter='overdue'">逾期 <span>{{overdue}}</span></button><button :aria-pressed="filter==='today'" @click="filter='today'">今天 <span>{{dueToday}}</span></button></div>
    <div v-if="tasks.length" class="wb-list">
     <article v-for="task in tasks" :key="`${task.relation_id}-${task.id}`" class="wb-task" :class="{'is-overdue':task.due_date && task.due_date<today()}">
      <div class="wb-task-context"><span class="wb-person">{{task.person_name || '联系人待补充'}}</span><span class="wb-status">{{reason(task.due_date)}}</span></div>
      <h4>{{task.next_step}}</h4>
      <div class="wb-task-bottom"><div class="wb-meta"><span><el-icon><Clock/></el-icon><span>截止 <b>{{task.due_date || '待安排'}}</b></span></span><span>负责人 <b>{{task.owner_label || task.owner || '待指派'}}</b></span></div><div class="wb-actions"><el-button type="primary" plain @click="openRelation(task.relation_id)">查看跟进<el-icon><ArrowRight/></el-icon></el-button><el-button text :icon="Check" :disabled="!canWrite || task.can_complete===false" :loading="busy" @click="emit('complete',task.id)">完成</el-button></div></div>
     </article>
    </div>
    <div v-else class="wb-empty"><el-icon><Check/></el-icon><h4>{{filter==='all'?'暂时没有待办':'这类事项已清空'}}</h4><p>{{filter==='all'?'记录一次沟通，并安排下一步，就会显示在这里。':'可以切回全部，查看接下来的安排。'}}</p><el-button v-if="filter!=='all'" @click="filter='all'">查看全部待办</el-button></div>
    <footer class="wb-list-footer"><span>按截止日期排序 · {{showAll?'显示全部':'最多显示 8 项'}}</span><el-button v-if="filtered.length>8" link type="primary" @click="showAll=!showAll">{{showAll?'收起':`查看全部 ${filtered.length} 项`}}<el-icon><ArrowRight/></el-icon></el-button></footer>
   </section>
   <aside v-if="!managerView" class="wb-aside">
    <section class="wb-opportunities" aria-label="商机跟进提醒">
     <div class="wb-section-heading"><h3>这些商机该跟进了</h3><span class="wb-count">{{stale.length}}</span></div>
     <p class="wb-aside-intro">已有一段时间没有登记商机互动</p>
     <article v-for="item in stale.slice(0,3)" :key="`${item.opportunity._owner}-${item.opportunity.id}`" class="wb-stale"><strong>{{item.opportunity.name}}</strong><div><span>{{item.days}} 天未登记</span><el-button link type="primary" @click="openOpportunity(item.opportunity)">查看商机</el-button></div></article>
     <p v-if="!stale.length" class="wb-quiet">暂无需要提醒的商机</p>
     <el-button v-if="stale.length>3 || unknown" link type="primary" @click="emit('opportunity',null)">查看全部商机</el-button>
     <details class="wb-explanation"><summary>提醒怎么算？</summary><p>按真实商机互动计算；没有互动时从建档日计算。计划不算互动，不代表项目实际没有进展。</p><el-select v-model="staleDays" aria-label="商机未跟进天数"><el-option v-for="days in [14,30,60]" :key="days" :value="days" :label="`${days} 天未登记互动`"/></el-select><p v-if="unknown">{{unknown}} 个商机缺少日期，未参与判断。</p></details>
    </section>
    <section v-if="warnings.length" class="wb-warnings"><div class="wb-section-heading"><h3>找时间联系一下</h3></div><article v-for="r in warnings" :key="`${r._owner}-${r.id}`"><div><strong>{{r.person_name || '客户联系人'}}</strong><p>{{r.last_touch?`上次联系 ${r.last_touch}`:'还没有沟通记录'}}</p></div><el-button link type="primary" :disabled="!canRecord" @click="emit('record',r)">记录跟进</el-button></article></section>
   </aside>
  </div>
 </section>
</template>
<style scoped>
.wb-layout.wb-personal-only{grid-template-columns:minmax(0,1fr)}
.crm-workbench{max-width:1440px;margin:0 auto;padding:24px;color:#24354b;background:#f5f7fa;border-radius:14px;font-size:14px}.wb-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:26px}.wb-date{color:#778398;font-size:13px;margin:0 0 8px}.wb-heading h2{font-size:26px;letter-spacing:-.5px;margin:0;line-height:1.4;font-weight:650}.wb-intro{margin:10px 0 0;color:#66748a;font-size:14px;line-height:1.7}.wb-intro b{color:#c45839;font-weight:650}.wb-tools{display:flex;flex-shrink:0;gap:4px}.wb-tools .el-button{margin:0;color:#536985}.wb-layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:22px;align-items:start}.wb-tasks,.wb-opportunities,.wb-warnings{background:#fff;border:1px solid #e5eaf0;border-radius:12px;overflow:hidden}.wb-tasks{padding:24px}.wb-section-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}.wb-section-heading h3{display:flex;align-items:center;gap:9px;font-size:16px;margin:0;font-weight:650}.wb-section-heading h3 .el-icon{color:#527298;font-size:19px}.wb-section-heading h3 span,.wb-count{font-size:12px;background:#eef2f7;color:#62738a;padding:2px 7px;border-radius:5px}.wb-scope{font-size:12px;color:#8692a3}.wb-filters{display:flex;gap:6px;margin:22px 0 2px;padding-bottom:15px;border-bottom:1px solid #edf0f4}.wb-filters button{border:0;background:transparent;border-radius:7px;padding:7px 12px;font:inherit;font-size:13px;color:#6c7b8f;cursor:pointer}.wb-filters button[aria-pressed=true]{background:#edf3fd;color:#245ab0;font-weight:600}.wb-filters button span{margin-left:5px;font-variant-numeric:tabular-nums}.wb-filters button:focus-visible{outline:2px solid #2466c1;outline-offset:2px}.wb-task{padding:22px 0;border-bottom:1px solid #edf0f4}.wb-task-context{display:flex;gap:12px;align-items:center}.wb-person{font-size:13px;font-weight:600;color:#65758c}.wb-status{border-radius:4px;background:#f1f4f8;color:#758398;padding:3px 7px;font-size:11px}.is-overdue .wb-status{background:#fff1ea;color:#b95733}.wb-task h4{font-size:16px;font-weight:550;line-height:1.75;margin:10px 0 18px;overflow-wrap:anywhere;white-space:pre-wrap}.wb-task-bottom{display:flex;align-items:center;justify-content:space-between;gap:16px}.wb-meta{display:flex;flex-direction:column;gap:7px;font-size:12px;color:#8893a2;min-width:0}.wb-meta>span{display:flex;gap:6px;align-items:center;overflow-wrap:anywhere}.wb-meta b{font-weight:400;color:#65758b}.is-overdue .wb-meta>span:first-child b{color:#b95733}.wb-actions{display:flex;flex-shrink:0;gap:4px}.wb-actions .el-button{margin:0}.wb-actions .el-icon{margin-left:4px}.wb-list-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-top:18px}.wb-list-footer>span{color:#8a95a5;font-size:12px}.wb-aside{display:flex;flex-direction:column;gap:18px}.wb-opportunities,.wb-warnings{padding:20px}.wb-aside-intro{font-size:12px;color:#8893a2;margin:10px 0 6px}.wb-stale{padding:18px 0;border-bottom:1px solid #edf0f4}.wb-stale strong{font-size:14px;font-weight:550;line-height:1.65;display:block;overflow-wrap:anywhere}.wb-stale>div{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:9px}.wb-stale>div>span{font-size:12px;color:#9b7556}.wb-stale .el-button{font-size:12px}.wb-explanation{font-size:12px;color:#8793a3;margin-top:18px;line-height:1.7}.wb-explanation summary{cursor:pointer}.wb-explanation .el-select{width:100%}.wb-explanation p{margin:10px 0}.wb-warnings article{display:flex;justify-content:space-between;align-items:center;gap:8px;padding-top:18px}.wb-warnings strong{font-size:14px;font-weight:550;overflow-wrap:anywhere}.wb-warnings p,.wb-quiet{font-size:12px;color:#8a95a5;line-height:1.7}.wb-warnings p{margin:5px 0 0}.wb-warnings .el-button{flex-shrink:0;font-size:12px}.wb-empty{text-align:center;padding:46px 16px;color:#8a95a5}.wb-empty>.el-icon{font-size:28px;padding:16px;background:#edf7f3;color:#4e967c;border-radius:50%;box-sizing:content-box}.wb-empty h4{font-size:16px;color:#52657c;margin:18px 0 8px}.wb-empty p{font-size:13px;line-height:1.8}.wb-quiet{margin:22px 0}
.wb-duty-head{display:flex;align-items:center;gap:10px;width:100%;background:transparent;border:0;font:inherit;cursor:pointer;padding:2px 0;text-align:left}
.wb-duty-head h3{font-size:16px;margin:0;font-weight:650;color:#24354b}
.wb-duty-arw{color:#527298;font-size:16px;transition:transform .2s}.wb-duty-arw.is-open{transform:rotate(90deg)}
.wb-duty-toggle{margin-left:auto;font-size:12px;color:#245ab0;background:#edf3fd;padding:3px 12px;border-radius:20px;font-weight:600}
.wb-duty-hint{margin:14px 0 0;font-size:13px;color:#8a95a5;line-height:1.7}
@media(min-width:1550px){.wb-layout{grid-template-columns:minmax(0,1fr) 350px}.wb-tasks{padding:28px}}
@media(max-width:1100px){.wb-layout{grid-template-columns:minmax(0,1fr)}.wb-aside{display:grid;grid-template-columns:1fr 1fr}.wb-task-bottom{gap:12px}.wb-heading h2{font-size:24px}}
@media(max-width:650px){.crm-workbench{padding:16px 0;background:transparent}.wb-heading{align-items:flex-start;flex-direction:column;gap:12px;margin-bottom:18px;padding:0 4px}.wb-heading h2{font-size:23px}.wb-tools .el-button{padding-left:0;padding-right:16px}.wb-intro{font-size:13px}.wb-layout{gap:16px}.wb-aside{display:flex}.wb-tasks{padding:18px 16px}.wb-task-bottom{flex-direction:column;align-items:stretch}.wb-actions{justify-content:flex-end;margin-top:4px}.wb-task h4{font-size:15px}.wb-list-footer{align-items:flex-start;flex-direction:column;gap:10px}.wb-scope{font-size:11px}}
</style>
