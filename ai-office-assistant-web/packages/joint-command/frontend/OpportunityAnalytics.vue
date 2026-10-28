<script setup lang="ts">
import { computed } from 'vue'
import { Collection, TrendCharts, Trophy, Money, Aim, PieChart } from '@element-plus/icons-vue'
import type { CrmOpportunity, CrmPlaybook, CrmSalesContract } from '../../../src/services/personalWorkApi'
import OpportunityExecutiveSummary from './OpportunityExecutiveSummary.vue'
import { OPPORTUNITY_STAGES } from './opportunityStages'
import { opportunityProbability } from './opportunityProbability'
import OpportunityGrowthAnalytics from './OpportunityGrowthAnalytics.vue'

const props = defineProps<{ opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups']; contracts?: CrmSalesContract[] }>()
const emit = defineEmits<{ select: [item: CrmOpportunity] }>()

const followupCount = computed(() => {
  const m = new Map<string, number>()
  for (const f of props.followups || []) if (f.project_id && !f.completed_at) { const key = JSON.stringify([(f as { _owner?: string })._owner || '', f.project_id]); m.set(key, (m.get(key) || 0) + 1) }
  return m
})
const isActive = (o: CrmOpportunity) => !o.cancelled && (!o.outcome || o.outcome === 'open')
const amt = (o: CrmOpportunity) => Number(o.amount || 0)
const region = (o: CrmOpportunity) => (o.region || '').trim() || '未分区'

const active = computed(() => props.opportunities.filter(isActive))
const won = computed(() => props.opportunities.filter(o => o.outcome === 'won'))
const assessmentOf = (o: CrmOpportunity) => opportunityProbability(o, followupCount.value.get(JSON.stringify([o._owner || '', o.code])) || 0)
const probOf = (o: CrmOpportunity) => assessmentOf(o).probability
const totalAmount = computed(() => active.value.reduce((s, o) => s + amt(o), 0))
const weightedAmount = computed(() => active.value.reduce((s, o) => s + amt(o) * probOf(o) / 100, 0))

const kpis = computed(() => [
  { key: 'total', label: '商机总数', value: props.opportunities.length, unit: '个', icon: Collection, tone: 'blue' },
  { key: 'active', label: '在谈商机', value: active.value.length, unit: '个', icon: TrendCharts, tone: 'indigo' },
  { key: 'won', label: '已赢单', value: won.value.length, unit: '个', icon: Trophy, tone: 'green' },
  { key: 'amount', label: '在谈可参与份额', value: Math.round(totalAmount.value), unit: '万', icon: Money, tone: 'gold' },
  { key: 'weighted', label: '概率加权预期', value: Math.round(weightedAmount.value), unit: '万', icon: Aim, tone: 'teal' },
])

const stageFunnel = computed(() => OPPORTUNITY_STAGES.map(stage => {
  const items = active.value.filter(o => (o.sales_stage || '') === stage.name)
  return { label: stage.name, count: items.length, amount: Math.round(items.reduce((s, o) => s + amt(o), 0)), group: stage.group }
}))
const unstaged = computed(() => active.value.filter(o => !OPPORTUNITY_STAGES.some(s => s.name === (o.sales_stage || ''))).length)
const maxFunnel = computed(() => Math.max(1, ...stageFunnel.value.map(r => r.count)))

const regionDist = computed(() => {
  const m = new Map<string, { count: number; amount: number }>()
  for (const o of active.value) { const k = region(o); const cur = m.get(k) || { count: 0, amount: 0 }; cur.count++; cur.amount += amt(o); m.set(k, cur) }
  return [...m.entries()].map(([label, v]) => ({ label, count: v.count, amount: Math.round(v.amount) })).sort((a, b) => b.amount - a.amount)
})
const maxRegion = computed(() => Math.max(1, ...regionDist.value.map(r => r.amount)))

const probBuckets = computed(() => {
  const b = { high: 0, mid: 0, low: 0 }
  for (const o of active.value) { const p = probOf(o); if (p >= 70) b.high++; else if (p >= 40) b.mid++; else b.low++ }
  const total = active.value.length || 1
  return [
    { label: '高（≥70%）', count: b.high, tone: 'green', pct: Math.round(b.high / total * 100) },
    { label: '中（40–69%）', count: b.mid, tone: 'amber', pct: Math.round(b.mid / total * 100) },
    { label: '低（<40%）', count: b.low, tone: 'red', pct: Math.round(b.low / total * 100) },
  ]
})

type DonutSlice = { label: string; count: number; color: string }
const donutGradient = (slices: DonutSlice[]) => {
  const total = slices.reduce((sum, slice) => sum + slice.count, 0)
  if (!total) return '#edf2f8'
  let cursor = 0
  return `conic-gradient(${slices.map(slice => {
    const start = cursor
    cursor += slice.count / total * 100
    return `${slice.color} ${start}% ${cursor}%`
  }).join(',')})`
}
const statusSlices = computed<DonutSlice[]>(() => [
  { label: '在谈', count: active.value.length, color: '#2f6fe4' },
  { label: '赢单', count: props.opportunities.filter(o => !o.cancelled && o.outcome === 'won').length, color: '#1f9d63' },
  { label: '输单', count: props.opportunities.filter(o => !o.cancelled && o.outcome === 'lost').length, color: '#d95c62' },
  { label: '取消', count: props.opportunities.filter(o => o.cancelled || o.outcome === 'cancelled').length, color: '#98a6bc' },
])
const probabilitySlices = computed<DonutSlice[]>(() => probBuckets.value.map((bucket, index) => ({
  label: bucket.label,
  count: bucket.count,
  color: ['#1f9d63', '#d98921', '#d64545'][index]!,
})))
const supportSlices = computed<DonutSlice[]>(() => {
  const counts = { strong: 0, medium: 0, weak: 0 }
  active.value.forEach(o => { counts[assessmentOf(o).support]++ })
  return [
    { label: '支撑充分', count: counts.strong, color: '#0f9c93' },
    { label: '支撑一般', count: counts.medium, color: '#4f6be0' },
    { label: '支撑不足', count: counts.weak, color: '#e1892d' },
  ]
})
const donutCards = computed(() => [
  { key: 'status', title: '商机状态结构', subtitle: '全部可见商机', center: props.opportunities.length, unit: '个', slices: statusSlices.value },
  { key: 'probability', title: '预测赢率结构', subtitle: '当前在谈商机', center: active.value.length, unit: '个', slices: probabilitySlices.value },
  { key: 'support', title: '质量支撑结构', subtitle: '材料 · 关系人 · 行动', center: supportSlices.value.find(s => s.label === '支撑充分')?.count || 0, unit: '条充分', slices: supportSlices.value },
])

const support = computed(() => {
  const total = active.value.length || 1
  const withMat = active.value.filter(o => Object.values(o.stage_progress || {}).some(s => (s.attachments?.length || 0) > 0)).length
  const withContact = active.value.filter(o => Object.values(o.stage_progress || {}).some(s => (s.contacts?.length || 0) > 0)).length
  const withFollow = active.value.filter(o => (followupCount.value.get(JSON.stringify([o._owner || '', o.code])) || 0) > 0).length
  return [
    { label: '有证明 / 输出材料', count: withMat, pct: Math.round(withMat / total * 100) },
    { label: '有阶段关系人', count: withContact, pct: Math.round(withContact / total * 100) },
    { label: '有跟进计划', count: withFollow, pct: Math.round(withFollow / total * 100) },
  ]
})

const yearDist = computed(() => {
  const m = new Map<string, number>()
  for (const o of active.value) { const y = (o.contract_date || '').match(/(\d{4})/)?.[1] || '待定'; m.set(y, (m.get(y) || 0) + 1) }
  return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([label, count]) => ({ label, count }))
})
const maxYear = computed(() => Math.max(1, ...yearDist.value.map(r => r.count)))
</script>

<template>
  <section class="opp-analytics">
    <OpportunityExecutiveSummary :opportunities="opportunities" :contracts="contracts || []" @select="item => emit('select', item)" />
    <div class="oa-kpis">
      <div v-for="k in kpis" :key="k.key" class="oa-kpi" :class="`is-${k.tone}`">
        <span class="oa-kpi-ic"><el-icon><component :is="k.icon" /></el-icon></span>
        <div><span class="oa-kpi-label">{{ k.label }}</span><strong>{{ k.value.toLocaleString('zh-CN') }}<em>{{ k.unit }}</em></strong></div>
      </div>
    </div>

    <div class="oa-donut-grid" aria-label="商机结构概览">
      <article v-for="card in donutCards" :key="card.key" class="oa-donut-card">
        <header><div><h3>{{ card.title }}</h3><span>{{ card.subtitle }}</span></div></header>
        <div class="oa-donut-body">
          <div class="oa-donut" role="img" :aria-label="`${card.title}：${card.slices.map(s => `${s.label}${s.count}个`).join('，')}`" :style="{ background: donutGradient(card.slices) }">
            <div><strong>{{ card.center.toLocaleString('zh-CN') }}</strong><small>{{ card.unit }}</small></div>
          </div>
          <ul class="oa-donut-legend">
            <li v-for="slice in card.slices" :key="slice.label"><i :style="{ background: slice.color }"></i><span>{{ slice.label }}</span><b>{{ slice.count }}</b></li>
          </ul>
        </div>
      </article>
    </div>

    <OpportunityGrowthAnalytics :opportunities="opportunities" :followups="followups" @select="item => emit('select',item)" />

    <div class="oa-grid">
      <article class="oa-card">
        <header><h3><el-icon><TrendCharts /></el-icon> 在谈阶段分布</h3><span>当前存量 · 非阶段转化率</span></header>
        <ul class="oa-bars">
          <li v-for="row in stageFunnel" :key="row.label">
            <span class="oa-bar-label">{{ row.label }}</span>
            <span class="oa-bar-track"><i class="oa-bar-fill" :class="row.group === 'define' ? 'is-define' : 'is-win'" :style="{ width: row.count / maxFunnel * 100 + '%' }"></i></span>
            <b class="oa-bar-val">{{ row.count }} 个 · {{ row.amount }} 万</b>
          </li>
        </ul>
        <p v-if="unstaged" class="oa-note">另有 {{ unstaged }} 个在谈商机阶段待确认。</p>
      </article>

      <article class="oa-card">
        <header><h3><el-icon><PieChart /></el-icon> 成单概率分布</h3><span>综合阶段 + 赢率 + 支撑</span></header>
        <div class="oa-seg" role="img" aria-label="概率分布">
          <i v-for="b in probBuckets" :key="b.label" :class="`is-${b.tone}`" :style="{ width: b.pct + '%' }"></i>
        </div>
        <ul class="oa-legend">
          <li v-for="b in probBuckets" :key="b.label"><i :class="`is-${b.tone}`"></i>{{ b.label }} <b>{{ b.count }}</b></li>
        </ul>
        <p class="oa-note">概率由所处阶段、登记赢率与“动作 / 材料支撑”共同判定，可在每条商机详情查看依据。</p>
      </article>

      <article class="oa-card">
        <header><h3><el-icon><Money /></el-icon> 区域分布</h3><span>按在谈份额</span></header>
        <ul v-if="regionDist.length" class="oa-bars">
          <li v-for="row in regionDist" :key="row.label">
            <span class="oa-bar-label">{{ row.label }}</span>
            <span class="oa-bar-track"><i class="oa-bar-fill is-blue" :style="{ width: row.amount / maxRegion * 100 + '%' }"></i></span>
            <b class="oa-bar-val">{{ row.count }} 个 · {{ row.amount }} 万</b>
          </li>
        </ul>
        <el-empty v-else description="暂无在谈商机" :image-size="50" />
      </article>

      <article class="oa-card">
        <header><h3><el-icon><Aim /></el-icon> 概率支撑情况</h3><span>动作 / 材料覆盖</span></header>
        <ul class="oa-support">
          <li v-for="s in support" :key="s.label">
            <div class="oa-support-top"><span>{{ s.label }}</span><b>{{ s.count }} · {{ s.pct }}%</b></div>
            <span class="oa-bar-track"><i class="oa-bar-fill is-teal" :style="{ width: s.pct + '%' }"></i></span>
          </li>
        </ul>
        <p class="oa-note">支撑越充分，成单概率越可信；缺材料 / 关系人的商机建议尽快补齐。</p>
      </article>

      <article class="oa-card oa-card--wide">
        <header><h3>预计签约年度分布</h3><span>在谈商机</span></header>
        <ul class="oa-year">
          <li v-for="row in yearDist" :key="row.label"><span class="oa-year-bar" :style="{ height: Math.max(8, row.count / maxYear * 100) + 'px' }"></span><b>{{ row.count }}</b><small>{{ row.label }}</small></li>
        </ul>
      </article>
    </div>
  </section>
</template>

<style scoped>
.opp-analytics { --gold:#c98a15; --green:#1f9d63; --amber:#d98921; --red:#d64545; --indigo:#3a5ad6; --teal:#0f9c93; }
.oa-kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:16px; }
.oa-kpi { display:flex; align-items:center; gap:11px; padding:14px; background:#fff; border:1px solid #e4ecf6; border-radius:12px; box-shadow:0 10px 30px -22px rgba(21,73,156,.55); }
.oa-kpi-ic { display:grid; place-items:center; width:40px; height:40px; border-radius:10px; color:#fff; font-size:19px; background:#15499c; flex:none; }
.oa-kpi.is-indigo .oa-kpi-ic{background:var(--indigo)} .oa-kpi.is-green .oa-kpi-ic{background:var(--green)} .oa-kpi.is-gold .oa-kpi-ic{background:var(--gold)} .oa-kpi.is-teal .oa-kpi-ic{background:var(--teal)}
.oa-kpi-label { font-size:12.5px; color:#64789a; display:block; }
.oa-kpi strong { font-size:22px; color:#1f3350; } .oa-kpi em { font-size:12px; font-style:normal; color:#64789a; margin-left:3px; }
.oa-donut-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin-bottom:16px; }
.oa-donut-card { min-width:0; padding:16px 18px; background:#fff; border:1px solid #e4ecf6; border-radius:12px; box-shadow:0 10px 30px -22px rgba(21,73,156,.55); }
.oa-donut-card > header { margin-bottom:10px; }
.oa-donut-card h3 { margin:0 0 4px; font-size:15px; color:#15499c; }
.oa-donut-card header span { font-size:11px; color:#7a8da6; }
.oa-donut-body { display:flex; align-items:center; justify-content:center; gap:20px; min-height:142px; }
.oa-donut { width:126px; height:126px; border-radius:50%; display:grid; place-items:center; flex:none; }
.oa-donut > div { width:88px; height:88px; border-radius:50%; background:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center; box-shadow:0 0 0 1px rgba(220,231,247,.6); }
.oa-donut strong { font-size:24px; line-height:1; color:#173e76; }
.oa-donut small { margin-top:6px; font-size:10px; color:#7b8da4; }
.oa-donut-legend { min-width:112px; list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:9px; }
.oa-donut-legend li { display:grid; grid-template-columns:9px 1fr auto; align-items:center; gap:7px; font-size:12px; color:#536b87; }
.oa-donut-legend i { width:9px; height:9px; border-radius:50%; }
.oa-donut-legend b { color:#173e76; font-variant-numeric:tabular-nums; }
.oa-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.oa-card { background:#fff; border:1px solid #e4ecf6; border-radius:12px; padding:16px; box-shadow:0 10px 30px -22px rgba(21,73,156,.55); }
.oa-card--wide { grid-column:1 / -1; }
.oa-card > header { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px; }
.oa-card h3 { margin:0; font-size:15px; color:#15499c; display:flex; align-items:center; gap:6px; }
.oa-card > header span { font-size:12px; color:#64789a; }
.oa-bars { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:10px; }
.oa-bars li { display:grid; grid-template-columns:120px 1fr auto; align-items:center; gap:10px; }
.oa-bar-label { font-size:13px; color:#1f3350; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.oa-bar-track { height:11px; background:#eef3fb; border-radius:6px; overflow:hidden; }
.oa-bar-fill { display:block; height:100%; border-radius:6px; }
.oa-bar-fill.is-define { background:linear-gradient(90deg,#4f6be0,#15499c); }
.oa-bar-fill.is-win { background:linear-gradient(90deg,#2bb18a,#1f8a72); }
.oa-bar-fill.is-blue { background:linear-gradient(90deg,#1e6bff,#15499c); }
.oa-bar-fill.is-teal { background:linear-gradient(90deg,#2bc0b4,#0f9c93); }
.oa-bar-val { font-size:12.5px; font-weight:600; color:#15499c; white-space:nowrap; }
.oa-seg { display:flex; height:16px; border-radius:8px; overflow:hidden; background:#eef3fb; }
.oa-seg i { display:block; height:100%; } .oa-seg i.is-green,.oa-legend i.is-green{background:var(--green)} .oa-seg i.is-amber,.oa-legend i.is-amber{background:var(--amber)} .oa-seg i.is-red,.oa-legend i.is-red{background:var(--red)}
.oa-legend { list-style:none; margin:12px 0 0; padding:0; display:flex; gap:16px; flex-wrap:wrap; }
.oa-legend li { display:flex; align-items:center; gap:6px; font-size:13px; color:#1f3350; } .oa-legend i { width:11px; height:11px; border-radius:3px; } .oa-legend b { color:#15499c; }
.oa-support { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:12px; }
.oa-support-top { display:flex; justify-content:space-between; font-size:13px; color:#1f3350; margin-bottom:5px; } .oa-support-top b { color:#15499c; }
.oa-note { margin:12px 0 0; font-size:12px; color:#8a94a6; line-height:1.6; }
.oa-year { list-style:none; margin:0; padding:8px 0 0; display:flex; align-items:flex-end; gap:14px; min-height:120px; }
.oa-year li { display:flex; flex-direction:column; align-items:center; gap:4px; justify-content:flex-end; }
.oa-year-bar { width:34px; border-radius:6px 6px 0 0; background:linear-gradient(180deg,#4f6be0,#15499c); }
.oa-year b { font-size:13px; color:#15499c; } .oa-year small { font-size:11px; color:#64789a; }
@media (max-width:1100px){ .oa-donut-grid{grid-template-columns:1fr 1fr}.oa-donut-card:last-child{grid-column:1/-1} }
@media (max-width:900px){ .oa-kpis{grid-template-columns:repeat(2,1fr)} .oa-grid,.oa-donut-grid{grid-template-columns:1fr}.oa-donut-card:last-child{grid-column:auto} }
@media (max-width:520px){ .oa-kpis{grid-template-columns:1fr}.oa-donut-body{justify-content:flex-start}.oa-donut{width:112px;height:112px}.oa-donut>div{width:78px;height:78px} }
</style>
