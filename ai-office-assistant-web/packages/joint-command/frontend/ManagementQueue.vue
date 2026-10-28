<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CrmOpportunity, CrmPlaybook, CrmRelation, CrmStaff } from '../../../src/services/personalWorkApi'
import { managementQueue } from './crmCompletion'
import { managementRegionQueue } from './managementRegion'
import { LIAISON_REGION_ORDER } from './liaisonRegions'
const props = defineProps<{ opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups']; relations: CrmRelation[]; staff?: CrmStaff[] }>()
const emit = defineEmits<{ opportunity: [item: CrmOpportunity]; relation: [id: string] }>()
const selectedSection = ref(''), page = ref(1), region = ref('')
const queues = computed(() => managementRegionQueue(managementQueue(props.opportunities, props.followups, props.relations, new Date().toLocaleDateString('sv-SE')), props.staff || [], region.value))
watch(region, () => { selectedSection.value = ''; page.value = 1 }, { flush: 'sync' })
const section = computed({ get: () => selectedSection.value || (queues.value.overdue.length ? 'overdue' : queues.value.undated.length ? 'undated' : queues.value.stale.length ? 'stale' : queues.value.unassigned.length + queues.value.risks.length ? 'coordination' : queues.value.scheduled.length ? 'scheduled' : 'overdue'), set: (value: string) => { selectedSection.value = value } })

interface Row { key: string; title: string; metas: string[]; date: string; tag: string; tone: string; relation: string; opportunity?: CrmOpportunity }
const rows = computed<Row[]>(() => {
  const s = section.value
  if (['overdue', 'undated', 'scheduled'].includes(s)) {
    const list = s === 'undated' ? queues.value.undated : s === 'scheduled' ? queues.value.scheduled : queues.value.overdue
    const tag = s === 'overdue' ? '逾期' : s === 'undated' ? '待定日期' : '已安排'
    const tone = s === 'overdue' ? 'danger' : s === 'undated' ? 'warning' : 'success'
    return list.map(t => ({ key: `${t.relation_id}-${t.id}`, title: t.next_step || '跟进客户关系', metas: [t.person_name, t.owner_label || t.owner || '未指派'].filter(Boolean) as string[], date: t.due_date || '未定日期', tag, tone, relation: t.relation_id, opportunity: undefined }))
  }
  if (s === 'stale') return queues.value.stale.map(x => ({ key: `${x.opportunity._owner}-${x.opportunity.id}`, title: x.opportunity.name || '商机', metas: [x.opportunity.manager || '未指派', x.basis].filter(Boolean) as string[], date: `${x.days} 天未跟进`, tag: '久未跟进', tone: 'warning', relation: '', opportunity: x.opportunity }))
  return [
    ...queues.value.unassigned.map(o => ({ key: `o-${o._owner}-${o.id}`, title: o.name || '商机', metas: ['商机负责人待指派'], date: '', tag: '待指派', tone: 'info', relation: '', opportunity: o as CrmOpportunity | undefined })),
    ...queues.value.risks.map(r => ({ key: `r-${r._owner}-${r.id}`, title: r.person_name || '客户联系人', metas: [!r.our_member?.trim() ? '对接责任待指派' : '单点关系风险，建议核实是否需要协同'], date: '', tag: !r.our_member?.trim() ? '待指派' : '单点风险', tone: 'danger', relation: r.id, opportunity: undefined })),
  ]
})
watch(section, () => { page.value = 1 })
watch(() => rows.value.length, count => { page.value = Math.min(page.value, Math.max(1, Math.ceil(count / 20))) })
</script>
<template>
 <section class="management-queue">
  <div class="management-region"><label for="management-region">管控区域</label><select id="management-region" v-model="region" aria-label="管控区域"><option value="">全部区域</option><option v-for="r in LIAISON_REGION_ORDER" :key="r" :value="r">{{ r }}</option><option value="未分区">未分区</option></select><span>按负责人所属区域；商机无区域负责人时按登记区域，无法确认的列入未分区。</span></div>
  <p class="mq-note">仅汇总当前授权范围，不是全公司排名。待协调为系统提示的风险线索，并非已创建协同任务。</p>
  <el-radio-group v-model="section" aria-label="管理事项分类"><el-radio-button value="overdue">逾期 {{ queues.overdue.length }}</el-radio-button><el-radio-button value="undated">待定日期 {{ queues.undated.length }}</el-radio-button><el-radio-button value="stale">久未跟进 {{ queues.stale.length }}</el-radio-button><el-radio-button value="coordination">待协调 {{ queues.unassigned.length + queues.risks.length }}</el-radio-button><el-radio-button value="scheduled">已安排 {{ queues.scheduled.length }}</el-radio-button></el-radio-group>
  <p v-if="section === 'undated'" class="mq-note">这些跟进已有下一步，但尚未明确日期；请联系负责人确认时间，不计为逾期。</p>
  <el-empty v-if="!rows.length" description="当前范围暂无此类事项" :image-size="56" />
  <ul v-else class="mq-list">
   <li v-for="row in rows.slice((page - 1) * 20, page * 20)" :key="row.key" class="mq-item" :class="`is-${row.tone}`">
    <span class="mq-tag" :class="`is-${row.tone}`">{{ row.tag }}</span>
    <div class="mq-body">
     <strong class="mq-title">{{ row.title }}</strong>
     <div class="mq-meta"><span v-for="(m, i) in row.metas" :key="i">{{ m }}</span><span v-if="row.date" class="mq-date" :class="{ 'is-danger': row.tone === 'danger' }">{{ row.date }}</span></div>
    </div>
    <el-button type="primary" plain size="small" class="mq-act" @click="row.opportunity ? emit('opportunity', row.opportunity) : emit('relation', row.relation)">查看处理</el-button>
   </li>
  </ul>
  <el-pagination v-if="rows.length > 20" v-model:current-page="page" :page-size="20" :pager-count="5" size="small" :total="rows.length" layout="prev,pager,next" class="mq-pager" />
 </section>
</template>
<style scoped>
.management-region { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin: 16px 0 }
.management-region label { font-size: 14px; font-weight: 600 }
.management-region select { font: inherit; padding: 7px 12px; border: 1px solid #dce3ed; border-radius: 8px; background: #fff; color: #334155 }
.management-region span { font-size: 12px; color: #64748b }
.mq-note { font-size: 13px; color: #64748b; line-height: 1.7 }
.el-radio-group { display: flex; flex-wrap: wrap; margin: 4px 0 6px }
.mq-list { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 10px }
.mq-item { display: flex; align-items: center; gap: 14px; padding: 13px 16px; border: 1px solid #e8edf5; border-left: 3px solid #cdd6e4; border-radius: 12px; background: #fff; transition: box-shadow .15s, transform .15s, border-color .15s }
.mq-item:hover { box-shadow: 0 12px 26px -20px rgba(21, 73, 156, .55); transform: translateY(-1px); border-color: #c3d4ee }
.mq-item.is-danger { border-left-color: #d64545 } .mq-item.is-warning { border-left-color: #d98921 } .mq-item.is-success { border-left-color: #1f9d63 } .mq-item.is-info { border-left-color: #3a5ad6 }
.mq-tag { flex: none; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; white-space: nowrap }
.mq-tag.is-danger { color: #d64545; background: rgba(213,1,60,.1) } .mq-tag.is-warning { color: #b9740f; background: rgba(251,144,28,.14) } .mq-tag.is-success { color: #1f8a72; background: rgba(4,188,138,.14) } .mq-tag.is-info { color: #3a5ad6; background: rgba(58,90,214,.12) }
.mq-body { flex: 1; min-width: 0 }
.mq-title { display: block; font-size: 14px; color: #1f3350; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.mq-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-top: 4px; font-size: 12px; color: #64789a }
.mq-meta > span { position: relative }
.mq-meta > span + span::before { content: '·'; position: absolute; left: -7px; color: #c4cddb }
.mq-date { color: #8a94a6 } .mq-date.is-danger { color: #d64545; font-weight: 600 }
.mq-act { flex: none }
.mq-pager { margin-top: 12px }
@media (max-width: 640px) { .mq-item { flex-wrap: wrap } .mq-act { margin-left: auto } }
</style>
