<script setup lang="ts">
import { computed, ref } from 'vue'
import FollowupOrganization from './FollowupOrganization.vue'
import type { CrmPlaybook, CrmRelation, CrmPerson, CrmUnit } from '../../../src/services/personalWorkApi'
const props = defineProps<{ scope: string; followups: CrmPlaybook['followups']; relations: CrmRelation[]; people: CrmPerson[]; units: CrmUnit[]; initialRelation?: string; command?: boolean; organizationUnits?: CrmUnit[] }>()
const emit = defineEmits<{ close: []; refresh: [] }>()
const visible = ref(true), selected = ref(props.initialRelation || ''), search = ref(''), status = ref('all')
const organizationOpen = ref(false)
const importanceFilter = ref(''), supportFilter = ref('')
const matchesLevel = (value: string | undefined, filter: string) => !filter || (filter === '__empty__' ? !value?.trim() : value === filter)
const rows = computed(() => props.relations.map(relation => {
  const person = props.people.find(p => p.id === relation.person_id)
  const unit = props.units.find(u => u.id === person?.unit_id)
  const plans = props.followups.filter(a => a.relation_id === relation.id)
    .sort((a,b) => Number(b.overdue) - Number(a.overdue) || (a.due_date || '9999-12-31').localeCompare(b.due_date || '9999-12-31'))
  const actions = [...(relation.actions || [])].sort((a,b) => (b.happened_at || '').localeCompare(a.happened_at || ''))
  return { relation, person, unit, plans, actions, overdue: plans.some(a => a.overdue) }
}))
const filtered = computed(() => rows.value.filter(row =>
  matchesLevel(row.person?.importance, importanceFilter.value) && matchesLevel(row.person?.support_level, supportFilter.value) &&
  (status.value === 'all' || (status.value === 'overdue' ? row.overdue : row.plans.length > 0)) &&
  `${row.person?.name || row.relation.person_name || ''} ${row.unit?.name || ''} ${row.relation.our_member_label || row.relation.our_member} ${row.plans.map(a => a.next_step).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())
).sort((a,b) => Number(b.overdue) - Number(a.overdue) || b.plans.length - a.plans.length))
const active = computed(() => filtered.value.find(r => r.relation.id === selected.value))
type OverviewMode='organizations'|'contacts'|'relations'|'plans'
const expandedGroup=ref(''), overviewMode=ref<OverviewMode>('organizations')
const unitIndex=computed(()=>new Map((props.organizationUnits||props.units).map(u=>[u.id,u])))
function rootUnit(unit?:CrmUnit){
  const seen=new Set<string>()
  while(unit?.parent_unit_id&&unitIndex.value.has(unit.parent_unit_id)&&!seen.has(unit.parent_unit_id)){
    seen.add(unit.id);unit=unitIndex.value.get(unit.parent_unit_id)
  }
  return unit
}
const overview = computed(() => {
  const groups=new Map<string,typeof filtered.value>()
  for(const row of filtered.value){const key=rootUnit(row.unit)?.id||'';const list=groups.get(key)||[];list.push(row);groups.set(key,list)}
  return [...groups].map(([id,items])=>({id,unit:rootUnit(items[0]?.unit),items,
    people:new Set(items.map(r=>r.relation.person_id)).size,
    plans:items.reduce((n,r)=>n+r.plans.length,0),overdue:items.reduce((n,r)=>n+r.plans.filter(p=>p.overdue).length,0)
  })).sort((a,b)=>b.overdue-a.overdue||b.plans-a.plans)
})
const expanded=computed(()=>expandedGroup.value?overview.value.find(g=>g.id===expandedGroup.value):undefined)
const displayGroups=computed(()=>{
  if(!expanded.value)return overview.value.map(g=>({...g,label:g.unit?.company_full_name||g.unit?.name||'组织待补充',subtitle:'集团汇总 · 点击展开下属组织',leaf:!g.id}))
  const groups=new Map<string,typeof filtered.value>()
  for(const row of expanded.value.items){const key=JSON.stringify([row.unit?.id,row.person?.department||'']);const list=groups.get(key)||[];list.push(row);groups.set(key,list)}
  return [...groups].map(([id,items])=>({id,items,label:items[0]?.unit?.name||'组织待补充',subtitle:items[0]?.person?.department||'未分部门',people:new Set(items.map(r=>r.relation.person_id)).size,plans:items.reduce((n,r)=>n+r.plans.length,0),overdue:items.reduce((n,r)=>n+r.plans.filter(p=>p.overdue).length,0),leaf:true}))
})
const contactCount=computed(()=>new Set(filtered.value.map(r=>r.relation.person_id)).size)
const contacts=computed(()=>{
  const groups=new Map<string,typeof filtered.value>()
  for(const row of filtered.value){const key=row.relation.person_id;const list=groups.get(key)||[];list.push(row);groups.set(key,list)}
  return [...groups.values()].map(items=>({items,person:items[0]?.person,unit:items[0]?.unit,relations:items.length,plans:items.reduce((n,r)=>n+r.plans.length,0)}))
})
const plans=computed(()=>filtered.value.flatMap(row=>row.plans.map(plan=>({row,plan}))))
function selectOverviewMode(mode:OverviewMode){overviewMode.value=mode;expandedGroup.value=''}
function selectRelation(id:string){selected.value=id;organizationOpen.value=false}
function showOverview(){selected.value='';organizationOpen.value=false;selectOverviewMode('organizations')}
function importanceTone(value?:string){return value==='重要'?'high':value==='一般'?'normal':'empty'}
function supportTone(value?:string){return value==='积极支持'?'strong':value==='支持'?'positive':value==='反对'?'negative':value==='中立'?'neutral':'empty'}
const page = ref(1)
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 4, page.value * 4))
function filterChanged() { page.value = 1; selected.value = ''; organizationOpen.value = false }
</script>
<template>
  <el-dialog v-model="visible" append-to-body title="客户跟进情况" width="min(1280px,calc(100vw - 24px))" top="6vh" class="followup-dialog" :class="{'followup-dialog--command':command}" @closed="emit('close')">
    <div class="fu-toolbar"><b>{{ scope }}</b><span>{{ followups.length }} 项待跟进 · {{ followups.filter(a => a.overdue).length }} 项逾期 · {{ relations.length }} 条关系</span><el-button @click="emit('refresh')">刷新跟进</el-button></div>
    <div class="fu-filters"><el-input v-model="search" clearable placeholder="搜索客户、单位、负责人或跟进事项" aria-label="搜索跟进情况" @input="filterChanged" /><el-select v-model="importanceFilter" clearable placeholder="全部重要程度" aria-label="跟进重要程度筛选" @change="filterChanged"><el-option v-for="t in ['重要','一般']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select><el-select v-model="supportFilter" clearable placeholder="全部支持程度" aria-label="跟进支持程度筛选" @change="filterChanged"><el-option v-for="t in ['反对','中立','支持','积极支持']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select><el-select v-model="status" aria-label="跟进状态" @change="filterChanged"><el-option label="全部关系" value="all"/><el-option label="有待跟进" value="pending"/><el-option label="有逾期" value="overdue"/></el-select></div>
    <div v-if="filtered.length" class="fu-body">
      <aside class="fu-list">
        <button :aria-pressed="!active" @click="showOverview" class="fu-overview-link"><strong>◈ 对接总览</strong><span>{{overview.filter(g=>g.id).length}} 个集团 · {{contactCount}} 位联系人</span></button>
        <button v-for="row in pageRows" :key="row.relation.id" :aria-pressed="active?.relation.id === row.relation.id" @click="selectRelation(row.relation.id)"><strong>{{ row.person?.name || row.relation.person_name || '联系人待补充' }}</strong><span>{{ row.unit?.company_full_name || row.unit?.name || '单位待补充' }}</span><div class="fu-person-flags fu-person-flags--compact"><span aria-label="客户重要程度" class="fu-importance" :data-tone="importanceTone(row.person?.importance)">重要度 · {{row.person?.importance||'待补充'}}</span><span aria-label="客户支持程度" class="fu-support" :data-tone="supportTone(row.person?.support_level)">支持度 · {{row.person?.support_level||'待补充'}}</span></div><small>{{ row.relation.our_member_label || row.relation.our_member || '未指派' }} · {{ row.plans.length }} 项待跟进 <em v-if="row.overdue">逾期</em></small></button>
        <el-pagination v-if="filtered.length > 4" v-model:current-page="page" small layout="prev, pager, next" :pager-count="5" :page-size="4" :total="filtered.length" />
      </aside>
      <section v-if="active" class="fu-detail">
        <div class="fu-detail-head"><div><h3>{{ active.person?.name || active.relation.person_name }} · {{ active.unit?.name || '单位待补充' }}</h3><div class="fu-person-flags"><span aria-label="客户重要程度" class="fu-importance" :data-tone="importanceTone(active.person?.importance)">重要程度：{{active.person?.importance||'待补充'}}</span><span aria-label="客户支持程度" class="fu-support" :data-tone="supportTone(active.person?.support_level)">支持程度：{{active.person?.support_level||'待补充'}}</span></div><p>对接负责人：{{ active.relation.our_member_label || active.relation.our_member || '未指派' }}</p><p>关系 L{{ active.relation.strength }} · 最近互动：{{ active.relation.last_touch || '暂无记录' }}</p></div><div class="fu-action-count" :class="{ urgent: active.overdue }"><b>{{ active.plans.length }}</b><span>项待跟进</span><em v-if="active.overdue">含逾期</em></div></div>
        <h4 class="fu-section-title"><span>关键待跟进动作</span><small>按逾期优先、截止日期排序</small></h4>
        <article v-for="plan in active.plans" :key="plan.id" class="fu-plan"><b>{{ plan.next_step || plan.type || '跟进事项' }}</b><p>{{ plan.due_date || '日期待定' }} <em v-if="plan.overdue">已逾期</em> · {{ plan.owner_label || plan.owner || active.relation.our_member_label || '负责人待补充' }}</p><p v-if="plan.intel">{{ plan.intel }}</p></article>
        <p v-if="!active.plans.length">暂无待跟进计划，不代表已经完成跟进。</p>
        <h4 class="fu-section-title"><span>已登记行动记录（{{ active.actions.length }}）</span><small>最近动作优先</small></h4>
        <article v-for="action in active.actions" :key="action.id" class="fu-record"><b>{{ action.type || '行动' }}</b> · {{ action.happened_at || '时间未填写' }}<p v-if="action.intel">{{ action.intel }}</p><p v-if="action.next_step">下一步：{{ action.next_step }}</p><small v-if="action.completed_at">完成时间：{{ action.completed_at }}</small></article>
        <p v-if="!active.actions.length">暂无已登记行动记录。</p>
        <section class="fu-org-collapse" :class="{ open: organizationOpen }">
          <button type="button" class="fu-org-toggle" :aria-expanded="organizationOpen" @click="organizationOpen=!organizationOpen"><span><b>客户组织架构</b><small>{{ active.unit?.company_full_name || active.unit?.name || '组织待补充' }}<template v-if="active.person?.department"> · {{ active.person.department }}</template></small></span><em>{{ organizationOpen ? '收起组织架构' : '展开组织架构' }} {{ organizationOpen ? '▴' : '▾' }}</em></button>
          <FollowupOrganization v-if="organizationOpen" :units="organizationUnits || units" :people="people" :person="active.person"/>
        </section>
      </section>
      <section v-else class="fu-detail fu-overview" aria-label="客户经理对接总览">
        <h3>{{scope}} · 对接总览</h3>
        <div class="fu-overview-metrics">
          <button :aria-pressed="overviewMode==='organizations'" @click="selectOverviewMode('organizations')"><b>{{overview.filter(g=>g.id).length}}</b><span>对接组织</span><small>查看集团与下属组织</small></button>
          <button :aria-pressed="overviewMode==='contacts'" @click="selectOverviewMode('contacts')"><b>{{contactCount}}</b><span>客户联系人</span><small>查看联系人明细</small></button>
          <button :aria-pressed="overviewMode==='relations'" @click="selectOverviewMode('relations')"><b>{{filtered.length}}</b><span>关系链路</span><small>查看每条对接关系</small></button>
          <button :aria-pressed="overviewMode==='plans'" @click="selectOverviewMode('plans')"><b>{{plans.length}}</b><span>待跟进事项</span><small>查看计划与负责人</small></button>
        </div>
        <div class="fu-overview-content">
          <template v-if="overviewMode==='organizations'">
            <p>按顶层集团去重汇总，仅统计当前查看范围内的客户与关系。全部集团在当前页面紧凑展示，下属组织默认收起。</p>
            <div class="fu-group-nav"><el-button v-if="expanded" @click="expandedGroup=''">返回集团总览</el-button><b>{{expanded?.unit?.name||'集团总览'}}</b><span>{{displayGroups.length}} {{expanded?'个组织 / 部门':'个集团'}}</span></div>
            <div class="fu-org-cards"><button v-for="group in displayGroups" :key="group.id" @click="group.leaf ? selectRelation(group.items[0]!.relation.id) : expandedGroup=group.id" :aria-expanded="group.leaf?undefined:false"><strong>{{group.label}}</strong><span>{{group.subtitle}}</span><small>{{group.people}} 位联系人 · {{group.items.length}} 条关系 · {{group.plans}} 项待跟进 <em v-if="group.overdue">· {{group.overdue}} 项逾期</em></small></button></div>
          </template>
          <template v-else-if="overviewMode==='contacts'">
            <div class="fu-group-nav"><b>客户联系人明细</b><span>{{contacts.length}} 位，按客户身份去重</span></div>
            <div class="fu-detail-grid"><button v-for="item in contacts" :key="item.person?.id||item.items[0]?.relation.person_id" @click="selectRelation(item.items[0]!.relation.id)"><strong>{{item.person?.name||item.items[0]?.relation.person_name||'联系人待补充'}}</strong><span>{{item.unit?.company_full_name||item.unit?.name||'组织待补充'}}</span><small>{{item.person?.department||'部门待补充'}} · {{item.person?.title||'职务待补充'}}</small><div class="fu-person-flags fu-person-flags--compact"><span aria-label="客户重要程度" class="fu-importance" :data-tone="importanceTone(item.person?.importance)">重要度 · {{item.person?.importance||'待补充'}}</span><span aria-label="客户支持程度" class="fu-support" :data-tone="supportTone(item.person?.support_level)">支持度 · {{item.person?.support_level||'待补充'}}</span></div><em>{{item.relations}} 条关系 · {{item.plans}} 项待跟进</em></button></div>
          </template>
          <template v-else-if="overviewMode==='relations'">
            <div class="fu-group-nav"><b>关系链路明细</b><span>{{filtered.length}} 条，一位客户由多人对接时分别计数</span></div>
            <div class="fu-detail-grid"><button v-for="row in filtered" :key="row.relation.id" @click="selectRelation(row.relation.id)"><strong>{{row.person?.name||row.relation.person_name||'联系人待补充'}} ↔ {{row.relation.our_member_label||row.relation.our_member||'未指派'}}</strong><span>{{row.unit?.company_full_name||row.unit?.name||'组织待补充'}}</span><small>关系 L{{row.relation.strength}} · 最近互动 {{row.relation.last_touch||'暂无记录'}}</small><em>{{row.plans.length}} 项待跟进</em></button></div>
          </template>
          <template v-else>
            <div class="fu-group-nav"><b>待跟进事项明细</b><span>{{plans.length}} 项</span></div>
            <div class="fu-detail-grid"><button v-for="item in plans" :key="item.plan.id" @click="selectRelation(item.row.relation.id)"><strong>{{item.plan.next_step||item.plan.type||'跟进事项'}}</strong><span>{{item.row.person?.name||item.row.relation.person_name||'联系人待补充'}} · {{item.row.unit?.name||'组织待补充'}}</span><small>{{item.plan.due_date||'日期待定'}} · {{item.plan.owner_label||item.plan.owner||item.row.relation.our_member_label||'负责人待补充'}}</small><em v-if="item.plan.overdue">已逾期</em></button></div>
          </template>
        </div>
      </section>
    </div>
    <el-empty v-else description="当前范围暂无匹配的跟进记录" />
    <template #footer><el-button @click="visible = false">关闭跟进情况</el-button></template>
  </el-dialog>
</template>
<style scoped>
.fu-overview{display:flex;flex-direction:column;overflow:hidden}.fu-overview-content{flex:1;min-height:0;overflow:auto;padding-right:4px}.fu-overview-content>p{font-size:12px;line-height:1.5;margin:6px 0}.fu-group-nav{display:flex;align-items:center;gap:12px;margin:8px 0;font-size:13px}.fu-group-nav span{margin-left:auto}.fu-overview .fu-org-cards{grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;align-content:start}.fu-overview .fu-org-cards button{padding:9px 10px;min-height:78px}.fu-overview .fu-org-cards strong{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.fu-overview .fu-org-cards span{font-size:11px;margin-bottom:4px}.fu-overview .fu-org-cards small{font-size:11px;line-height:1.4;margin-bottom:0}.fu-overview-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:8px 0}.fu-overview-metrics button{font:inherit;text-align:left;color:inherit;padding:8px 10px;border:1px solid #7a9db655;border-radius:8px;background:#3999b811;cursor:pointer}.fu-overview-metrics button:hover,.fu-overview-metrics button[aria-pressed=true]{border-color:#39c7d4;background:#39c7d422;box-shadow:inset 0 -3px #39c7d4}.fu-overview-metrics b,.fu-overview-metrics span,.fu-overview-metrics small{display:block}.fu-overview-metrics b{font-size:23px;color:#2aa8b5}.fu-overview-metrics span{font-size:12px}.fu-overview-metrics small{font-size:10px;opacity:.7;margin-top:3px}.fu-org-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.fu-org-cards button{font:inherit;text-align:left;padding:14px;color:inherit;background:#3999b811;border:1px solid #7a9db655;border-radius:8px;cursor:pointer}.fu-org-cards strong,.fu-org-cards span,.fu-org-cards small{display:block;overflow-wrap:anywhere;margin-bottom:7px}.fu-org-cards small{line-height:1.7}.fu-org-cards button:hover{border-color:#39c7d4}.fu-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.fu-detail-grid button{font:inherit;text-align:left;color:inherit;padding:10px;border:1px solid #7a9db655;border-radius:8px;background:#3999b811;cursor:pointer;min-width:0}.fu-detail-grid button:hover{border-color:#39c7d4}.fu-detail-grid strong,.fu-detail-grid span,.fu-detail-grid small,.fu-detail-grid em{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:5px}.fu-detail-grid span,.fu-detail-grid small,.fu-detail-grid em{font-size:11px}.fu-detail-grid em{margin-bottom:0}@media(max-width:1100px){.fu-overview .fu-org-cards{grid-template-columns:repeat(3,minmax(0,1fr))}.fu-detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.fu-overview-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.fu-overview .fu-org-cards,.fu-detail-grid{grid-template-columns:1fr}}
.fu-toolbar,.fu-filters{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px;}.fu-toolbar span{color:#73869b;font-size:13px;}.fu-filters .el-input{flex:1;min-width:220px;}.fu-filters .el-select{width:150px;}
.fu-body{display:grid;grid-template-columns:290px minmax(0,1fr);gap:20px;height:min(58vh,650px);}.fu-list,.fu-detail{overflow:auto;min-width:0;}.fu-list button{width:100%;display:block;text-align:left;background:#f4f8fc;border:1px solid #dce5ef;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer;color:#26465f;}.fu-list button[aria-pressed=true]{border-color:#329ebc;background:#e3f4fa;}.fu-list span,.fu-list small{display:block;margin-top:5px;overflow-wrap:anywhere;}.fu-plan,.fu-record{border-left:3px solid #329ebc;padding:10px 12px;margin:10px 0;background:#f5f8fc;}.fu-record{border-color:#a1b4c6;}.fu-detail p{white-space:pre-wrap;overflow-wrap:anywhere;}em{color:#ce652a;font-style:normal;}
.fu-person-flags{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:7px 0 8px}.fu-person-flags span{display:inline-flex!important;align-items:center;width:auto;margin:0!important;padding:3px 8px;border:1px solid transparent;border-radius:999px;font-size:11px;font-weight:600;line-height:1.35;white-space:nowrap}.fu-person-flags--compact{margin:7px 0 5px}.fu-person-flags--compact span{padding:2px 7px;font-size:10px}.fu-importance[data-tone=high]{color:#9a5710;background:#fff1d4;border-color:#f3ce8c}.fu-importance[data-tone=normal]{color:#576c82;background:#edf2f7;border-color:#d5e0e9}.fu-support[data-tone=strong]{color:#087f75;background:#dcf7f1;border-color:#9addd2}.fu-support[data-tone=positive]{color:#257248;background:#e6f5e9;border-color:#b7dfbf}.fu-support[data-tone=neutral]{color:#58697b;background:#edf1f5;border-color:#d4dde6}.fu-support[data-tone=negative]{color:#b13d3d;background:#fff0f0;border-color:#f0b8b8}.fu-person-flags [data-tone=empty]{color:#78899a;background:#f2f5f8;border-color:#dbe3ea}
.fu-detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding-bottom:10px;border-bottom:1px solid #dce6ef}.fu-detail-head h3{margin:0 0 8px}.fu-detail-head p{margin:4px 0;color:#60788f}.fu-action-count{flex:0 0 auto;display:grid;min-width:88px;padding:10px 14px;border:1px solid #b9dce5;border-radius:9px;background:#ecf8fa;text-align:center}.fu-action-count b{font-size:24px;color:#168ca1}.fu-action-count span,.fu-action-count em{font-size:11px}.fu-action-count.urgent{border-color:#f2c29c;background:#fff4e8}.fu-action-count.urgent b{color:#ce652a}.fu-section-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:16px 0 8px;padding-bottom:8px;border-bottom:1px solid #dce6ef}.fu-section-title small{font-weight:400;color:#8093a5}.fu-org-collapse{margin-top:18px;border:1px solid #d9e5ef;border-radius:9px;background:#f8fbfe;overflow:hidden}.fu-org-toggle{display:flex;justify-content:space-between;align-items:center;gap:16px;width:100%;padding:12px 14px;border:0;background:transparent;color:#294d69;text-align:left;cursor:pointer}.fu-org-toggle span,.fu-org-toggle small{display:block}.fu-org-toggle small{margin-top:4px;color:#8193a4;font-weight:400}.fu-org-toggle em{white-space:nowrap;color:#21728c}.fu-org-collapse.open{background:#fff}.fu-org-collapse .fo-organization{margin:0 12px 12px}
@media(max-width:700px){.fu-body{grid-template-columns:1fr;height:60vh;overflow:auto;}.fu-list{max-height:180px;}.fu-detail{overflow:visible;}}
</style>
<style>
.followup-dialog{height:min(860px,88dvh);max-height:calc(100dvh - 24px);box-sizing:border-box;display:flex;flex-direction:column;margin-bottom:0!important;overflow:hidden}.followup-dialog .el-dialog__header,.followup-dialog .el-dialog__footer{flex:none}.followup-dialog .el-dialog__body{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column}.followup-dialog .fu-body,.followup-dialog--command .fu-body{flex:1;min-height:0;height:auto!important}.followup-dialog .fu-toolbar,.followup-dialog .fu-filters{flex-shrink:0}.followup-dialog .fu-list .fu-overview-link{background:linear-gradient(120deg,#f2eaff,#e8dcfa)!important;border:2px solid #9f7adb!important;color:#58368a!important;box-shadow:inset 4px 0 #a67ae0!important}.followup-dialog--command .fu-list .fu-overview-link{background:linear-gradient(120deg,#47376d,#302953)!important;color:#edddff!important;border-color:#b295e2!important}.followup-dialog .fu-overview>h3{margin:6px 0}.followup-dialog .fu-overview-metrics{margin:8px 0;gap:8px}.followup-dialog .fu-overview-metrics article{padding:8px}.followup-dialog .fu-overview-metrics b{font-size:23px}.followup-dialog .fu-list button:not(.fu-overview-link){padding:9px}.followup-dialog .fu-list small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.followup-dialog--command{--el-bg-color:#10283e;--el-bg-color-overlay:#10283e;--el-fill-color-blank:#0c2034;--el-text-color-primary:#e3f2ff;--el-text-color-regular:#b6cee2;--el-text-color-placeholder:#7394af;--el-border-color:#31506c;--el-color-primary:#39c7d4;background:radial-gradient(ellipse at top right,#183f61,transparent 70%),#0a1d31!important;border:1px solid #345c7c;border-radius:14px!important;box-shadow:0 22px 80px #0008!important;color:#d6e9fa}
.followup-dialog--command .el-dialog__title{color:#e5f5ff;font-weight:600;letter-spacing:1px}.followup-dialog--command .el-dialog__header{border-bottom:1px solid #2c4d66;padding-bottom:16px}.followup-dialog--command .el-dialog__body{color:#b8d1e6;padding-top:16px}.followup-dialog--command .fu-toolbar{padding:12px;background:#16344d;border:1px solid #2d5472;border-radius:9px}.followup-dialog--command .fu-toolbar b{color:#63e5d9}.followup-dialog--command .fu-toolbar span{color:#9fbdd4}.followup-dialog--command .fu-body{height:min(67vh,780px);gap:18px}.followup-dialog--command .fu-list{padding-right:8px}.followup-dialog--command .fu-list button{background:linear-gradient(135deg,#163550,#10293e);border-color:#2b4a65;color:#cce2f5;border-radius:9px;padding:14px}.followup-dialog--command .fu-list button[aria-pressed=true]{background:linear-gradient(120deg,#185065,#163a56);border-color:#42cfdb;box-shadow:inset 3px 0 #44dcca}.followup-dialog--command .fu-list small{color:#8db5d0}.followup-dialog--command .fu-detail{padding:4px 12px}.followup-dialog--command .fu-detail>h3{color:#ecf7ff;font-size:20px}.followup-dialog--command .fu-detail>h4{color:#c2daed;border-bottom:1px solid #294960;padding-bottom:10px}.followup-dialog--command .fu-plan{background:linear-gradient(100deg,#133d47,#102c42);border-left-color:#33d5c4;border-radius:0 9px 9px 0}.followup-dialog--command .fu-record{background:linear-gradient(100deg,#222e4e,#132a43);border-left-color:#9b8ae0;border-radius:0 9px 9px 0}.followup-dialog--command em{color:#ffc56b}.followup-dialog--command .el-input__wrapper,.followup-dialog--command .el-select__wrapper{background:#10283f;box-shadow:0 0 0 1px #345571 inset}.followup-dialog--command .el-dialog__footer{border-top:1px solid #2c4d66;padding-top:14px}.followup-dialog--command ::-webkit-scrollbar{width:6px;height:6px}.followup-dialog--command ::-webkit-scrollbar-thumb{background:#3a5a75;border-radius:6px}
.followup-dialog--command .fu-importance[data-tone=high]{color:#ffd58a;background:#8e5d2238;border-color:#d99a45}.followup-dialog--command .fu-importance[data-tone=normal],.followup-dialog--command .fu-person-flags [data-tone=empty]{color:#aac0d3;background:#7790a51c;border-color:#46647c}.followup-dialog--command .fu-support[data-tone=strong],.followup-dialog--command .fu-support[data-tone=positive]{color:#6ff0d7;background:#1c8b7830;border-color:#35ac99}.followup-dialog--command .fu-support[data-tone=neutral]{color:#c2d0dc;background:#8ba0b11c;border-color:#526b80}.followup-dialog--command .fu-support[data-tone=negative]{color:#ff9f9f;background:#a73c3c2b;border-color:#c35d5d}
@media(max-width:700px){.followup-dialog--command .fu-body{height:65vh}.followup-dialog--command .fu-detail{padding:0}.followup-dialog--command .fu-toolbar{padding:8px}}
</style>
