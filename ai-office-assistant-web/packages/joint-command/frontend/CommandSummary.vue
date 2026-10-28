<script setup lang="ts">
import { computed } from 'vue'
import { opportunityProbability } from './opportunityProbability'
import { OPPORTUNITY_STAGES } from './opportunityStages'
import { bizIcon } from './businessIcons'
import CountUp from './command/CountUp.vue'
import { opportunityResults } from './opportunityResults'
import CommandBattleMap from './command/CommandBattleMap.vue'
import { isActiveOpportunity, isAmountSuspect, countedAmount } from './command/commandOverview'
import type { BusinessAnalysisData, CrmUnit, CrmPerson, CrmRelation, CrmOpportunity, CrmPlaybook } from '../../../src/services/personalWorkApi'
const props = defineProps<{ section: string; regions: { name: string; units: number; people: number; warnings: number; followups: number }[]; business: BusinessAnalysisData | null; units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups'] }>()
const emit = defineEmits<{ section: [value: string]; opportunity: [item: CrmOpportunity]; detail: [item: CrmOpportunity]; manage: [] }>()
const active = computed(() => props.opportunities.filter(isActiveOpportunity))
const suspects = computed(() => active.value.filter(isAmountSuspect))
// 投资规模 = 项目总投资，可参与份额 = 我方可争取部分（集成产业 + 服务1.0）；两者分开统计，不相加、不互替。
const investment = computed(() => active.value.reduce((sum, o) => sum + (isAmountSuspect(o) ? 0 : Number(o.investment || 0)), 0))
const shareSplit = computed(() => active.value.reduce((acc, o) => { if (!isAmountSuspect(o)) { acc.integration += Number(o.share_integration || 0); acc.service += Number(o.share_service || 0) } return acc }, { integration: 0, service: 0 }))
const history = computed(() => opportunityResults(props.opportunities))
const investmentCoverage = computed(() => investment.value > 0 ? Math.round(amount.value / investment.value * 100) : 0)
const wan = (v: number) => v >= 10000 ? `${(v / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })} 亿` : `${fmt(v)} 万`
const amount = computed(() => active.value.reduce((sum, o) => sum + countedAmount(o), 0))
const fmt = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
const opportunityAmount = countedAmount
const opportunityStage = (o: CrmOpportunity) => o.sales_stage || o.stage || '未填写阶段'
const opportunityRegion = (o: CrmOpportunity) => (o.region || '').trim() || '未分区'
const followupCount = computed(() => {
  const counts = new Map<string, number>()
  for (const item of props.followups || []) {
    if (!item.project_id || item.completed_at) continue
    const key = JSON.stringify([(item as { _owner?: string })._owner || '', item.project_id])
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return counts
})
const assessedOpportunities = computed(() => active.value.map(item => {
  const key = JSON.stringify([item._owner || '', item.code])
  const assessment = opportunityProbability(item, followupCount.value.get(key) || 0)
  return { item, assessment, weighted: opportunityAmount(item) * assessment.probability / 100 }
}))
const weightedAmount = computed(() => assessedOpportunities.value.reduce((sum, row) => sum + row.weighted, 0))
const averageProbability = computed(() => assessedOpportunities.value.length
  ? Math.round(assessedOpportunities.value.reduce((sum, row) => sum + row.assessment.probability, 0) / assessedOpportunities.value.length)
  : 0)
const probabilityBuckets = computed(() => {
  const buckets = [
    { key: 'high', label: '高概率', range: '≥ 70%', count: 0, color: '#25c893' },
    { key: 'mid', label: '中概率', range: '40–69%', count: 0, color: '#e4a136' },
    { key: 'low', label: '低概率', range: '< 40%', count: 0, color: '#df5f6c' },
  ]
  for (const row of assessedOpportunities.value) {
    const index = row.assessment.probability >= 70 ? 0 : row.assessment.probability >= 40 ? 1 : 2
    buckets[index].count++
  }
  return buckets
})
const probabilityDonut = computed(() => {
  const total = active.value.length
  if (!total) return '#25445a'
  let cursor = 0
  const stops = probabilityBuckets.value.map(bucket => {
    const start = cursor
    cursor += bucket.count / total * 100
    return `${bucket.color} ${start}% ${cursor}%`
  })
  return `conic-gradient(${stops.join(',')})`
})
const opportunityRegionStats = computed(() => {
  const values = new Map<string, { label: string; count: number; amount: number }>()
  for (const item of active.value) {
    const label = opportunityRegion(item)
    const current = values.get(label) || { label, count: 0, amount: 0 }
    current.count++
    current.amount += opportunityAmount(item)
    values.set(label, current)
  }
  return [...values.values()].sort((a, b) => b.amount - a.amount).slice(0, 6)
})
const opportunitySupport = computed(() => {
  const total = active.value.length || 1
  const materials = active.value.filter(item => Object.values(item.stage_progress || {}).some(stage => (stage.attachments?.length || 0) > 0)).length
  const contacts = active.value.filter(item => Object.values(item.stage_progress || {}).some(stage => (stage.contacts?.length || 0) > 0)).length
  const plans = active.value.filter(item => followupCount.value.get(JSON.stringify([item._owner || '', item.code]))).length
  return [
    { label: '材料支撑', hint: '证明 / 输出材料', count: materials, pct: Math.round(materials / total * 100) },
    { label: '关系覆盖', hint: '阶段关键关系人', count: contacts, pct: Math.round(contacts / total * 100) },
    { label: '行动覆盖', hint: '已有跟进计划', count: plans, pct: Math.round(plans / total * 100) },
  ]
})
const priorityOpportunities = computed(() => [...assessedOpportunities.value]
  .sort((a, b) => b.weighted - a.weighted || opportunityAmount(b.item) - opportunityAmount(a.item))
  .slice(0, 5))
// ---- 商机驾驶舱补充口径 ----
const ic = bizIcon
const weightedShare = computed(() => amount.value > 0 ? Math.round(weightedAmount.value / amount.value * 100) : 0)
const battleTargets = computed(() => assessedOpportunities.value.filter(r => opportunityAmount(r.item) >= 1000).map(r => ({ item: r.item, probability: r.assessment.probability, weighted: r.weighted, reasons: r.assessment.reasons, gaps: r.assessment.gaps, followups: followupCount.value.get(JSON.stringify([r.item._owner || '', r.item.code])) || 0 })))
const unassigned = computed(() => active.value.filter(o => !(o.manager || '').trim()).length)
const bucketAmounts = computed(() => {
  const totals = [0, 0, 0]
  for (const row of assessedOpportunities.value) totals[row.assessment.probability >= 70 ? 0 : row.assessment.probability >= 40 ? 1 : 2] += opportunityAmount(row.item)
  return totals
})
const STAGE_TONES = ['#4a9dff', '#3b8ff0', '#2f7fe0', '#2bb9a8', '#22c493', '#1fd48a']
// 六阶段流程：按销售阶段顺序排列，未匹配的阶段归入“其他”。
const stagePipeline = computed(() => {
  const rows = OPPORTUNITY_STAGES.map((stage, index) => ({ name: stage.name, phase: stage.phase, group: stage.group, tone: STAGE_TONES[index], count: 0, amount: 0 }))
  const other = { name: '其他', phase: '未归类', group: 'other', tone: '#7f96b4', count: 0, amount: 0 }
  for (const item of active.value) {
    const row = rows.find(r => r.name === opportunityStage(item)) || other
    row.count++; row.amount += opportunityAmount(item)
  }
  return other.count ? [...rows, other] : rows
})
const maxStageCount = computed(() => Math.max(1, ...stagePipeline.value.map(r => r.count)))
const stageGroups = computed(() => {
  const define = stagePipeline.value.filter(r => r.group === 'define'), win = stagePipeline.value.filter(r => r.group === 'win')
  const sum = (rows: typeof define) => rows.reduce((a, r) => a + r.count, 0)
  return { define: sum(define), win: sum(win) }
})
function parseMonth(value?: string) { const m = String(value || '').match(/(\d{4})[\/.\-年](\d{1,2})/); return m ? Number(m[1]) * 12 + Number(m[2]) - 1 : null }
const signingBuckets = computed(() => {
  const now = new Date(); const current = now.getFullYear() * 12 + now.getMonth()
  const buckets = [
    { key: 'overdue', label: '已过预计', count: 0, amount: 0, tone: 'bad' }, { key: 'm0', label: '本月', count: 0, amount: 0, tone: 'hot' },
    { key: 'q1', label: '1–3 月', count: 0, amount: 0, tone: '' }, { key: 'q2', label: '4–6 月', count: 0, amount: 0, tone: '' },
    { key: 'h2', label: '7–12 月', count: 0, amount: 0, tone: '' }, { key: 'far', label: '一年后', count: 0, amount: 0, tone: '' }, { key: 'none', label: '未填写', count: 0, amount: 0, tone: 'muted' },
  ]
  for (const item of active.value) {
    const month = parseMonth(item.contract_date)
    const index = month === null ? 6 : month < current ? 0 : month === current ? 1 : month - current <= 3 ? 2 : month - current <= 6 ? 3 : month - current <= 12 ? 4 : 5
    buckets[index].count++; buckets[index].amount += opportunityAmount(item)
  }
  return buckets
})
const maxSigningCount = computed(() => Math.max(1, ...signingBuckets.value.map(b => b.count)))
const overdueSigning = computed(() => signingBuckets.value[0].count)
const attentionCount = computed(() => {
  const now = new Date()
  const current = now.getFullYear() * 12 + now.getMonth()
  return active.value.filter(item => {
    const month = parseMonth(item.contract_date)
    return !(item.manager || '').trim() || (month !== null && month < current)
  }).length
})
const RING = 2 * Math.PI * 26
const supportRings = computed(() => opportunitySupport.value.map((item, index) => ({ ...item, icon: ['file', 'tree', 'flag'][index], tone: ['#36dcf0', '#a57bff', '#20c98f'][index], dash: `${RING * item.pct / 100} ${RING}` })))
const regionMax = computed(() => Math.max(1, ...opportunityRegionStats.value.map(r => r.amount)))
const compact = (v: number) => v >= 100000 ? `${(v / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}亿` : fmt(v)
</script>
<template>
  <section class="command-summary">
    <template v-if="section === 'opportunities'">
      <div class="command-opportunity-dashboard">
        <div class="command-opportunity-head">
          <div class="command-intro"><span>OPPORTUNITY INTELLIGENCE</span><h3>商机统计分析</h3><p>先看实际成交，再看在谈储备、预测价值与推进风险。统计范围：当前可见商机。</p></div>
          <button @click="emit('manage')">进入商机工作台 →</button>
        </div>

        <div class="command-opportunity-kpis">
          <div class="kpi kpi-teal actual-conversion"><i class="kpi-ic" v-html="ic('target')"></i><small>实际成单率 · 已结案</small><b v-if="history.rate !== null">{{ history.rate.toFixed(1) }}<em>%</em></b><b v-else>—</b><span>已签约 <em>{{ history.won }}</em> · 丢标 <em>{{ history.lost }}</em> · 结案 <em>{{ history.closed }}</em></span><div class="kpi-bar" role="meter" aria-label="实际成单率" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="history.rate ?? undefined"><i :style="{ width: (history.rate ?? 0) + '%' }"></i></div><span>{{ history.rate === null ? '暂无结案样本' : '已签约 ÷（已签约＋丢标）' }} · 非预测赢率</span></div>
          <div class="kpi kpi-blue"><i class="kpi-ic" v-html="ic('growth')"></i><small>在谈商机</small><b><CountUp :value="active.length" /></b><span>历史已签约 <em>{{ history.won }}</em> · 丢标 <em>{{ history.lost }}</em> · 不计入在谈</span></div>
          <div class="kpi kpi-cyan"><i class="kpi-ic" v-html="ic('reserve')"></i><small>可参与份额 · 万元</small><b><CountUp :value="amount" :decimals="1" /></b><span>对应项目投资 <em>{{ wan(investment) }}</em> · 可参与占 <em>{{ investmentCoverage }}%</em></span><div class="kpi-split" :title="`集成产业 ${fmt(shareSplit.integration)} 万 · 服务1.0 ${fmt(shareSplit.service)} 万`"><i :style="{ flexGrow: shareSplit.integration || 0.0001 }"></i><i :style="{ flexGrow: shareSplit.service || 0.0001 }"></i></div><span class="kpi-split-l">集成产业 <em>{{ wan(shareSplit.integration) }}</em> · 服务1.0 <em>{{ wan(shareSplit.service) }}</em></span></div>
          <div class="kpi kpi-teal"><i class="kpi-ic" v-html="ic('revenue')"></i><small>概率加权预期 · 万元</small><b><CountUp :value="weightedAmount" :decimals="1" /></b><span>占在谈份额 <em>{{ weightedShare }}%</em> · 按预测赢率折算</span><div class="kpi-bar"><i :style="{ width: weightedShare + '%' }"></i></div></div>
          <div class="kpi kpi-purple"><i class="kpi-ic" v-html="ic('target')"></i><small>平均预测赢率</small><b><CountUp :value="averageProbability" /><em>%</em></b><span>高概率 <em>{{ probabilityBuckets[0].count }}</em> · 中 <em>{{ probabilityBuckets[1].count }}</em> · 低 <em>{{ probabilityBuckets[2].count }}</em></span><svg class="kpi-gauge" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" /><circle cx="32" cy="32" r="26" class="fill" :style="{ strokeDasharray: `${RING * averageProbability / 100} ${RING}` }" /></svg></div>
          <div class="kpi kpi-amber" :class="{ 'is-alert': attentionCount > 0 }"><i class="kpi-ic" v-html="ic('cost')"></i><small>需要关注 · 去重商机数</small><b><CountUp :value="attentionCount" /></b><span>已过预计签约 <em>{{ overdueSigning }}</em> · 待指派负责人 <em>{{ unassigned }}</em></span><span>同一商机命中多项仅计一次</span></div>
        </div>

        <div class="command-analysis-grid">
          <article class="command-analysis-card command-probability-card">
            <header><i class="card-ic" v-html="ic('target')"></i><div><h4>预测赢率结构</h4><p>当前在谈商机 · 数量与份额</p></div><strong>{{ probabilityBuckets[0].count }}<small> 个高概率</small></strong></header>
            <div class="command-donut-body">
              <div class="command-donut" role="img" :aria-label="`高概率${probabilityBuckets[0].count}个，中概率${probabilityBuckets[1].count}个，低概率${probabilityBuckets[2].count}个`" :style="{ background: probabilityDonut }"><span><b>{{ averageProbability }}%</b><small>平均赢率</small></span></div>
              <ul><li v-for="(bucket, i) in probabilityBuckets" :key="bucket.key"><i :style="{ background: bucket.color }"></i><span>{{ bucket.label }}<small>{{ bucket.range }} · {{ fmt(bucketAmounts[i]) }} 万</small></span><b>{{ bucket.count }}</b><p><em :style="{ width: (active.length ? bucket.count / active.length * 100 : 0) + '%', background: bucket.color }"></em></p></li></ul>
            </div>
          </article>

          <article class="command-analysis-card command-stage-card">
            <header><i class="card-ic" v-html="ic('task')"></i><div><h4>商机阶段流程</h4><p>定义项目 → 赢得项目 · 数量 / 份额</p></div><span class="stage-groups"><i class="define"></i>定义项目 {{ stageGroups.define }}<i class="win"></i>赢得项目 {{ stageGroups.win }}</span></header>
            <ol class="command-pipeline" v-if="active.length">
              <li v-for="row in stagePipeline" :key="row.name" :class="row.group" :style="{ '--tone': row.tone }" :title="`${row.name}：${row.count} 个 · ${fmt(row.amount)} 万元`">
                <small>{{ row.phase }}</small>
                <b>{{ row.count }}</b>
                <span>{{ row.name }}</span>
                <em>{{ compact(row.amount) }} 万</em>
                <p><u>{{ active.length ? Math.round(row.count / active.length * 100) : 0 }}%</u><i :style="{ height: Math.max(4, row.count / maxStageCount * 100) + '%' }"></i></p>
              </li>
            </ol><p v-else class="command-analysis-empty">暂无在谈商机阶段数据</p>
          </article>

          <article class="command-analysis-card command-region-card">
            <header><i class="card-ic" v-html="ic('region')"></i><div><h4>业务归属结构</h4><p>按项目归属 · 可参与份额 TOP{{ opportunityRegionStats.length }}</p></div><span>份额 · 万元 / 数量</span></header>
            <div v-if="opportunityRegionStats.length" class="command-columns">
              <div v-for="(row, i) in opportunityRegionStats" :key="row.label" class="col" :title="`${row.label}：${row.count} 个 · ${fmt(row.amount)} 万元`">
                <b>{{ compact(row.amount) }}</b>
                <div class="bar"><i :style="{ height: Math.max(3, row.amount / regionMax * 100) + '%', opacity: 1 - i * 0.09 }"></i></div>
                <span :title="row.label">{{ row.label }}</span>
                <small>{{ row.count }} 个</small>
              </div>
            </div><p v-else class="command-analysis-empty">暂无区域统计数据</p>
          </article>

          <article class="command-analysis-card command-support-card">
            <header><i class="card-ic" v-html="ic('quality')"></i><div><h4>商机质量支撑</h4><p>提高赢率的关键基础 · 覆盖率</p></div></header>
            <ul class="command-rings"><li v-for="item in supportRings" :key="item.label" :style="{ '--tone': item.tone }">
              <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" class="track" /><circle cx="32" cy="32" r="26" class="fill" :style="{ strokeDasharray: item.dash }" /></svg>
              <b>{{ item.pct }}<small>%</small></b>
              <span><i v-html="ic(item.icon)"></i>{{ item.label }}</span>
              <small>{{ item.count }} / {{ active.length }} · {{ item.hint }}</small>
            </li></ul>
            <p class="command-support-note"><i v-html="ic('info')"></i>优先补齐材料、关键关系人与跟进计划，提升概率判断可信度。</p>
          </article>

          <article class="command-analysis-card command-signing-card">
            <header><i class="card-ic" v-html="ic('calendar')"></i><div><h4>预计签约节奏</h4><p>按合同预计签订时间分布 · 数量 / 份额</p></div><strong v-if="overdueSigning" class="is-bad">{{ overdueSigning }}<small> 个已过期</small></strong></header>
            <div class="command-columns is-signing">
              <div v-for="b in signingBuckets" :key="b.key" class="col" :class="b.tone" :title="`${b.label}：${b.count} 个 · ${fmt(b.amount)} 万元`">
                <b>{{ b.count }}</b>
                <div class="bar"><i :style="{ height: Math.max(3, b.count / maxSigningCount * 100) + '%' }"></i></div>
                <span>{{ b.label }}</span>
                <small>{{ compact(b.amount) }} 万</small>
              </div>
            </div>
          </article>

          <article class="command-analysis-card command-opportunity-priority">
            <header><i class="card-ic" v-html="ic('sprint')"></i><div><h4>优先推进商机</h4><p>按概率加权价值排序 · TOP5</p></div><button @click="emit('manage')">查看全部 →</button></header>
            <div class="command-priority-table">
              <table v-if="priorityOpportunities.length"><thead><tr><th>#</th><th>商机 / 客户</th><th>阶段</th><th>项目归属</th><th>预测赢率</th><th>加权价值 · 万元</th><th></th></tr></thead><tbody><tr v-for="(row, i) in priorityOpportunities" :key="row.item.id || row.item.code"><td><i class="rank" :class="'r' + (i + 1)">{{ i + 1 }}</i></td><td><strong :title="row.item.name">{{ row.item.name || row.item.code || '未命名商机' }}</strong><small>{{ row.item.owner_unit || '未填写业主' }}<template v-if="row.item.manager"> · {{ row.item.manager }}</template></small></td><td><span class="stage-chip">{{ opportunityStage(row.item) }}</span></td><td>{{ opportunityRegion(row.item) }}</td><td><span class="command-probability-pill" :class="row.assessment.probability >= 70 ? 'is-high' : row.assessment.probability >= 40 ? 'is-mid' : 'is-low'">{{ row.assessment.probability }}%</span><p class="prob-bar"><i :style="{ width: row.assessment.probability + '%' }"></i></p></td><td><b>{{ fmt(row.weighted) }}</b><small>份额 {{ wan(opportunityAmount(row.item)) }} · 投资 {{ wan(Number(row.item.investment || 0)) }}</small></td><td><button @click="emit('opportunity', row.item)">推进 →</button></td></tr></tbody></table>
              <p v-else class="command-analysis-empty">暂无在谈商机，可进入商机工作台维护。</p>
            </div>
          </article>
        </div>
      </div>
    </template>
    <template v-else>
      <CommandBattleMap :targets="battleTargets" :active-count="active.length" :suspects="suspects" @opportunity="item => emit('opportunity', item)" @detail="item => emit('detail', item)" @manage="emit('manage')" />
    </template>
  </section>
</template>
<style scoped>
.pulse-side-tabs{display:flex;gap:4px;flex:none;border-bottom:1px solid #28465e;padding-bottom:6px}.command-summary .pulse-side-tabs button{flex:1;border:0;background:transparent;color:#8caac2;padding:5px;font-size:11px}.command-summary .pulse-side-tabs button[aria-pressed=true]{color:#84ece1;background:#133e50;border-radius:5px}.pulse-layout-caption{display:flex;justify-content:space-between;font-size:9px;color:#829eb8;gap:6px}.pulse-layout-rows{display:flex;flex-direction:column;justify-content:space-around;min-height:0;flex:1;gap:5px}.command-summary .pulse-layout-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px;border:0;border-radius:0;padding:3px 0;background:transparent;text-align:left;flex:1;min-height:0;font-size:11px;color:#c2deef;align-content:center}.pulse-layout-row>span{white-space:nowrap}.pulse-layout-row>span i{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px}.pulse-layout-row b{font-size:13px;color:#d0e9f8}.pulse-layout-row small{font-size:10px;color:#8caac2;font-weight:400}.pulse-layout-row>div{grid-column:1/-1;background:#173a50;height:4px;border-radius:3px;overflow:hidden}.pulse-layout-row em{display:block;height:100%;border-radius:3px}.command-panel .pulse-layout-note{font-size:9px;line-height:1.3}
@media(max-height:850px){.pulse-side-tabs{padding-bottom:3px}.command-summary .pulse-side-tabs button{padding:3px}.pulse-layout-rows{gap:2px}.command-summary .pulse-layout-row{gap:3px;padding:1px 0}}
.command-health-side{min-height:0;min-width:0}.command-health-mobile{display:none}
@media(max-width:1000px){.command-health-side{display:none}.command-health-mobile{display:block;position:absolute;top:4px;right:8px;z-index:1;font-size:10px!important;padding:3px 6px!important}.command-landscape{position:relative}.command-network-center{padding-top:22px}}
.command-landscape{display:grid;grid-template-columns:minmax(175px,1.2fr) minmax(110px,.75fr) minmax(150px,1.45fr) minmax(110px,.75fr) minmax(110px,.8fr) minmax(180px,1.25fr);gap:8px;flex:1;min-height:0;overflow:hidden}
@media(min-width:1001px) and (max-width:1350px){.command-landscape{grid-template-columns:minmax(150px,1fr) minmax(100px,.7fr) minmax(120px,1fr) minmax(100px,.7fr) minmax(100px,.7fr) minmax(150px,1fr);gap:4px}.command-landscape .command-panel{padding:5px}}
.command-network-center{display:flex;min-width:0;min-height:0}.command-side{display:grid;grid-template-rows:1fr 1.2fr;gap:10px;min-height:0}
.command-panel{border:1px solid #254862;border-radius:10px;background:linear-gradient(135deg,#102c44bb,#091d30);padding:12px;min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:8px}
.command-panel header{display:flex;align-items:center;justify-content:space-between;color:#d8edff;font-size:13px;font-weight:600;flex:none}.command-panel header>span{border-left:3px solid #50c9dc;padding-left:8px}.command-panel header button{padding:0 5px;background:transparent;border:0;color:#82c8e6;font-size:16px}.command-panel p{margin:0;color:#819eb8;font-size:10px;line-height:1.5}.pulse-values{display:grid;grid-template-columns:1fr 1fr;gap:10px;flex:1;align-items:center}.pulse-values small{font-size:10px;color:#93b2ca;display:block}.pulse-values b{font-size:clamp(16px,1.4vw,25px);display:block;margin-top:5px;color:#8cc5ff;font-variant-numeric:tabular-nums}
.pulse-assigned{display:flex;align-items:baseline;justify-content:space-between;gap:5px}.pulse-assigned b{font-size:22px;color:#7ddee1}.pulse-assigned small{font-size:12px;color:#92b4cf}.pulse-assigned>span{font-size:10px;color:#91adc7}.pulse-track{height:5px;background:#1b3b54;border-radius:5px;flex:none;overflow:hidden}.pulse-track i{display:block;height:100%;background:linear-gradient(90deg,#3180dc,#62ddce)}.pulse-stage{display:flex;justify-content:space-between;gap:6px;font-size:11px;color:#9bb5cb}.pulse-stage span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pulse-stage b{color:#cce4f6;white-space:nowrap}
.command-summary .pulse-project{display:flex;flex-direction:column;gap:6px;border:0;border-top:1px solid #29475e;border-radius:0;background:transparent;padding:10px 0;text-align:left;min-width:0}.pulse-project-rank{display:flex;align-items:center;justify-content:space-between;gap:8px}.pulse-project-rank>span{color:#6b8da9;font-size:12px;letter-spacing:2px}.pulse-project-rank b{color:#efd190;font-size:19px}.pulse-project-rank small{font-size:10px;font-weight:400}.pulse-project strong{color:#cce4f6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;max-width:100%}.pulse-project-meta{font-size:10px;color:#8ea9bf;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:100%}.pulse-project em{font-size:10px;font-style:normal;color:#8cd7d7}.pulse-empty{margin:auto!important;text-align:center}
@media(max-height:850px){.command-panel{padding:8px;gap:5px}.command-summary .pulse-project{padding:6px 0;gap:4px}.pulse-project-meta{display:none}.pulse-values b{font-size:18px}.pulse-assigned b{font-size:18px}}
@media(max-width:1000px){.command-landscape{grid-template-columns:minmax(0,1fr)}.command-side-left,.command-side-right{display:none}}
.command-intro{margin:12px 0 26px}.command-intro>span{color:#36dcf0;font-size:11px;letter-spacing:2px}.command-intro h3{font-size:26px;margin:9px 0;color:#f3f8ff;display:flex;align-items:center;gap:10px}.command-intro h3::before{content:'';width:4px;height:22px;border-radius:2px;background:linear-gradient(180deg,#36dcf0,#3b9bff);box-shadow:0 0 8px rgba(54,220,240,.6)}.command-intro p,.command-note{font-size:13px;color:#91afc8;line-height:1.7}.command-note{padding:16px;border-top:1px solid #294761;margin-top:24px}
.command-summary :deep(.bo-cabin){display:none}.command-summary :deep(.bo-head h3){color:#d4e8fb}.command-summary :deep(.bo-head p){color:#91afc8}.command-summary :deep(.bo-card){background:linear-gradient(135deg,#102e48,#0a1c30);border-color:#2b4d69;min-height:230px;padding:24px;box-shadow:none}.command-summary :deep(.bo-c-hd b),.command-summary :deep(.bo-list){color:#d4e8fb}.command-summary :deep(.bo-kpis b){color:#66e4dd;font-size:32px}.command-summary :deep(.bo-foot),.command-summary :deep(.bo-kpis span),.command-summary :deep(.bo-mrow),.command-summary :deep(.bo-empty){color:#a0b9d0}.command-summary :deep(.bo-seg),.command-summary :deep(.bo-mt){background:#1b3c54}
.command-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:24px 0}.command-kpis>div{padding:18px 22px;border:1px solid rgba(72,130,200,.35);border-radius:9px;background:linear-gradient(180deg,rgba(22,48,86,.55),rgba(12,30,60,.55));box-shadow:inset 0 1px 0 rgba(120,180,255,.12)}.command-kpis small,.command-table small{display:block;color:#91afc8}.command-kpis b{display:block;color:#36dcf0;font-size:32px;margin-top:10px;font-variant-numeric:tabular-nums;text-shadow:0 0 12px rgba(54,220,240,.35)}.command-stages{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.command-stages span{padding:10px 16px;background:#11314a;border:1px solid #315575;border-radius:8px}.command-stages b{color:#66e4dd;margin-left:12px}.command-list-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:24px 0 12px}.command-summary button{color:#eaf3ff;background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85));border:1px solid rgba(86,156,236,.55);border-radius:4px;padding:8px 14px;font-weight:600;box-shadow:inset 0 0 12px rgba(60,140,240,.2);cursor:pointer;transition:color .2s,border-color .2s,box-shadow .25s}.command-summary button:hover{color:#9ff0ff;border-color:#36dcf0;box-shadow:inset 0 0 16px rgba(54,220,240,.35),0 0 14px rgba(54,220,240,.45)}.command-table{overflow:auto;max-height:560px;border:1px solid rgba(74,138,214,.38);border-radius:9px;background:linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92));box-shadow:inset 0 1px 0 rgba(120,180,255,.18),0 4px 18px rgba(0,0,0,.35)}.command-table table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}.command-table th{background:#0f2a4a;color:#b3c3d8;position:sticky;top:0;font-weight:600}.command-table td,.command-table th{padding:14px 16px;border-bottom:1px solid rgba(88,142,208,.18)}.command-table small{margin-top:6px}.command-table td:not(:first-child){white-space:nowrap}.command-empty{padding:36px;text-align:center;color:#91afc8}

.command-summary:has(.command-opportunity-dashboard),.command-summary:has(.battle){overflow:hidden!important}
.command-opportunity-dashboard{--line:rgba(74,138,214,.38);--panel:linear-gradient(180deg,rgba(38,86,150,.22),rgba(10,26,54,0) 90px),linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92));--num:'DIN Alternate','Bahnschrift','Barlow','PingFang SC',sans-serif;height:100%;min-height:0;display:flex;flex-direction:column;gap:10px;overflow:hidden}
.command-opportunity-dashboard .bi-ic{width:1em;height:1em;display:inline-block;vertical-align:-.15em}
.command-opportunity-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;flex:none}
.command-opportunity-head .command-intro{margin:0}.command-opportunity-head .command-intro h3{font-size:22px;margin:5px 0 2px}.command-opportunity-head .command-intro p{margin:0;font-size:11px}.command-opportunity-head>button{margin-bottom:2px;white-space:nowrap}
/* KPI 行：图标徽标 + 大数字 + 次级口径 */
.command-opportunity-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;flex:none}
.command-opportunity-kpis>.kpi{--k:#36dcf0;position:relative;overflow:hidden;padding:11px 14px 10px;border:1px solid var(--line);border-top:2px solid var(--k);border-radius:10px;background:var(--panel);box-shadow:inset 0 1px 0 rgba(120,180,255,.14),0 4px 18px rgba(0,0,0,.35)}
.command-opportunity-kpis>.kpi::after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(150px 70px at 100% 0%,color-mix(in srgb,var(--k) 18%,transparent),transparent 70%)}
.kpi-blue{--k:#3b9bff}.kpi-cyan{--k:#36dcf0}.kpi-teal{--k:#2ee0c6}.kpi-purple{--k:#a57bff}.kpi-amber{--k:#ffc83d}.kpi-amber.is-alert{--k:#ff7a5c}
.command-opportunity-kpis .kpi-ic{position:absolute;right:12px;top:10px;width:32px;height:32px;display:grid;place-items:center;border-radius:9px;font-size:18px;color:#fff;background:linear-gradient(135deg,color-mix(in srgb,var(--k) 85%,#fff),var(--k));box-shadow:0 4px 14px color-mix(in srgb,var(--k) 40%,transparent);z-index:1}
.command-opportunity-kpis small{display:block;color:#9fb6cd;font-size:11px;font-weight:500}
.command-opportunity-kpis b{display:flex;align-items:baseline;gap:3px;color:#f3f8ff;text-shadow:0 0 14px color-mix(in srgb,var(--k) 45%,transparent);font-size:clamp(22px,1.7vw,29px);line-height:1.1;margin:6px 0 4px;font-family:var(--num);font-variant-numeric:tabular-nums;white-space:nowrap}
.command-opportunity-kpis b em{font-size:13px;font-style:normal;color:#b3c3d8}
.command-opportunity-kpis>.kpi>span{display:block;color:#7f96b4;font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.command-opportunity-kpis>.kpi>span em{font-style:normal;color:#e6effb;font-weight:600}
.kpi-split{display:flex;gap:2px;height:4px;margin-top:5px;border-radius:3px;overflow:hidden}.kpi-split i{display:block;height:100%}.kpi-split i:first-child{background:#3b9bff}.kpi-split i:last-child{background:#2ee0c6}.command-opportunity-kpis>.kpi>span.kpi-split-l{margin-top:2px;font-size:10px}
.kpi-bar{height:4px;margin-top:6px;border-radius:3px;background:rgba(58,92,140,.38);overflow:hidden}.kpi-bar i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#2ee0c6,#36dcf0);box-shadow:0 0 8px rgba(54,220,240,.5)}
.kpi-gauge{position:absolute;right:50px;top:12px;width:44px;height:44px;transform:rotate(-90deg)}.kpi-gauge circle{fill:none;stroke:rgba(58,92,140,.45);stroke-width:6}.kpi-gauge .fill{stroke:var(--k);stroke-linecap:round;filter:drop-shadow(0 0 4px color-mix(in srgb,var(--k) 60%,transparent))}
/* 分析卡 */
.command-analysis-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));grid-template-rows:minmax(0,1fr) minmax(0,1.08fr);gap:10px;flex:1;min-height:0;overflow:hidden}
.command-analysis-card{min-width:0;min-height:0;overflow:hidden;border:1px solid var(--line);border-radius:10px;background:var(--panel);box-shadow:inset 0 1px 0 rgba(120,180,255,.18),inset 0 0 24px rgba(40,110,200,.12),0 4px 18px rgba(0,0,0,.35);padding:11px 13px;display:flex;flex-direction:column}
.command-analysis-card>header{display:flex;align-items:center;gap:9px;flex:none;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid rgba(88,142,208,.2)}.command-analysis-card>header>div{flex:1;min-width:0}
.command-analysis-card .card-ic{display:grid;place-items:center;flex:none;width:26px;height:26px;border-radius:8px;font-size:15px;color:#9fe8ff;background:rgba(54,220,240,.14)}
.command-analysis-card h4{font-size:14px;font-weight:700;color:#f3f8ff;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.command-analysis-card header p,.command-analysis-card header>span{margin:0;color:#7f96b4;font-size:10px;white-space:nowrap}.command-analysis-card header>strong{color:#36dcf0;font-size:18px;font-family:var(--num);text-shadow:0 0 10px rgba(54,220,240,.35);white-space:nowrap}.command-analysis-card header>strong.is-bad{color:#ff7a5c;text-shadow:0 0 10px rgba(255,90,90,.4)}.command-analysis-card header>strong small{font-weight:400;font-size:10px;color:#9fb6cd;font-family:inherit}
.command-analysis-card>header>button{padding:4px 10px;font-size:11px}
.command-probability-card{grid-column:span 3}.command-stage-card{grid-column:span 5}.command-region-card{grid-column:span 4}.command-support-card{grid-column:span 3}.command-signing-card{grid-column:span 3}.command-opportunity-priority{grid-column:span 6}
/* 赢率环 */
.command-donut-body{display:flex;align-items:center;justify-content:center;gap:clamp(10px,1.4vw,22px);flex:1;min-height:0}.command-donut{width:clamp(92px,7.5vw,124px);aspect-ratio:1;border-radius:50%;display:grid;place-items:center;flex:none;box-shadow:0 0 18px rgba(54,220,240,.2)}.command-donut>span{width:66%;aspect-ratio:1;border-radius:50%;background:#0a1e3c;display:flex;align-items:center;justify-content:center;flex-direction:column;box-shadow:0 0 0 1px #2b4c63,inset 0 0 14px rgba(40,110,200,.25)}.command-donut>span b{font-size:21px;color:#e7f8ff;font-family:var(--num)}.command-donut>span small{font-size:9px;color:#82a3bc;margin-top:2px}
.command-donut-body ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;min-width:118px;flex:1;max-width:190px}.command-donut-body li{display:grid;grid-template-columns:8px 1fr auto;align-items:center;gap:7px;color:#c5d6e6;font-size:11px}.command-donut-body li>i{width:8px;height:8px;border-radius:2px}.command-donut-body li span small{display:block;color:#7f96b4;font-size:9px;white-space:nowrap}.command-donut-body li b{color:#f3f8ff;font-size:15px;font-family:var(--num)}.command-donut-body li p{grid-column:1/-1;margin:0;height:3px;border-radius:2px;background:rgba(58,92,140,.35);overflow:hidden}.command-donut-body li p em{display:block;height:100%;border-radius:2px}
/* 阶段流程 */
.stage-groups{display:inline-flex;align-items:center;gap:5px}.stage-groups i{width:8px;height:8px;border-radius:2px;margin-left:8px}.stage-groups i.define{background:#3b8ff0}.stage-groups i.win{background:#22c493}
.command-pipeline{list-style:none;margin:0;padding:6px 0 0;display:flex;gap:6px;flex:1;min-height:0}
.command-pipeline li{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;text-align:center;padding:8px 6px 6px;border-radius:8px;border:1px solid color-mix(in srgb,var(--tone) 40%,transparent);background:linear-gradient(180deg,color-mix(in srgb,var(--tone) 22%,transparent),color-mix(in srgb,var(--tone) 6%,transparent));overflow:hidden}
.command-pipeline li::after{content:'';position:absolute;right:-9px;top:50%;width:0;height:0;border:6px solid transparent;border-left:7px solid color-mix(in srgb,var(--tone) 70%,transparent);transform:translateY(-50%);z-index:1}.command-pipeline li:last-child::after{display:none}
.command-pipeline small{font-size:9px;color:#9fb6cd;letter-spacing:.5px}.command-pipeline b{font-size:clamp(18px,1.5vw,26px);line-height:1.1;margin:3px 0 1px;color:#f3f8ff;font-family:var(--num);text-shadow:0 0 12px color-mix(in srgb,var(--tone) 60%,transparent)}.command-pipeline span{font-size:10.5px;color:#d6e1ef;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}.command-pipeline em{font-style:normal;font-size:9.5px;color:#9fb6cd;white-space:nowrap}
.command-pipeline p{position:relative;flex:1;min-height:18px;width:100%;margin:8px 0 0;display:flex;align-items:flex-end;justify-content:center;border-radius:6px;background:repeating-linear-gradient(0deg,color-mix(in srgb,var(--tone) 10%,transparent) 0 1px,transparent 1px 9px);border-bottom:1px solid color-mix(in srgb,var(--tone) 45%,transparent)}.command-pipeline p i{display:block;width:70%;border-radius:4px 4px 0 0;background:linear-gradient(180deg,var(--tone),color-mix(in srgb,var(--tone) 40%,transparent));box-shadow:0 0 12px color-mix(in srgb,var(--tone) 50%,transparent)}.command-pipeline p u{position:absolute;top:6px;left:0;right:0;text-decoration:none;font-size:11px;font-weight:600;color:#e6effb;font-family:var(--num);text-shadow:0 1px 4px rgba(0,0,0,.6)}
/* 纵向柱（区域 / 签约节奏） */
.command-columns{display:flex;gap:6px;flex:1;min-height:0;padding:14px 2px 0}
.command-columns .col{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;text-align:center;min-height:0}
.command-columns .col>b{font-size:11px;color:#e6effb;font-family:var(--num);white-space:nowrap;line-height:1.1;margin-bottom:3px}
.command-columns .bar{flex:1;min-height:0;width:100%;display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid rgba(88,142,208,.28)}.command-columns .bar i{display:block;width:min(34px,62%);border-radius:4px 4px 0 0;background:linear-gradient(180deg,#4fb0ff,#2a84ff);box-shadow:0 0 12px rgba(59,155,255,.4)}
.command-columns .col>span{margin-top:5px;font-size:10.5px;color:#c5d6e6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}.command-columns .col>small{font-size:9.5px;color:#7f96b4;white-space:nowrap}
.command-columns.is-signing .bar i{background:linear-gradient(180deg,#4fb0ff,#2a84ff)}.command-columns.is-signing .col.bad .bar i{background:linear-gradient(180deg,#ff8a7a,#ff4d5a);box-shadow:0 0 12px rgba(255,77,90,.45)}.command-columns.is-signing .col.bad>b{color:#ff8a8a}.command-columns.is-signing .col.hot .bar i{background:linear-gradient(180deg,#ffd76a,#ffb020);box-shadow:0 0 12px rgba(255,200,61,.45)}.command-columns.is-signing .col.muted .bar i{background:rgba(127,150,180,.5);box-shadow:none}
/* 质量支撑环 */
.command-rings{list-style:none;margin:0;padding:6px 0 0;display:flex;justify-content:space-around;align-items:center;gap:6px;flex:1;min-height:0}
.command-rings li{position:relative;display:flex;flex-direction:column;align-items:center;text-align:center;min-width:0;flex:1}
.command-rings svg{width:clamp(66px,5.4vw,84px);height:clamp(66px,5.4vw,84px);transform:rotate(-90deg)}.command-rings circle{fill:none;stroke-width:6}.command-rings .track{stroke:rgba(58,92,140,.42)}.command-rings .fill{stroke:var(--tone);stroke-linecap:round;filter:drop-shadow(0 0 5px color-mix(in srgb,var(--tone) 65%,transparent));transition:stroke-dasharray 1s ease}
.command-rings li>b{position:absolute;top:calc(clamp(66px,5.4vw,84px) / 2 - 10px);font-size:17px;color:#f3f8ff;font-family:var(--num);line-height:1}.command-rings li>b small{font-size:9px;color:#9fb6cd}
.command-rings li>span{margin-top:6px;font-size:11.5px;color:#e6effb;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}.command-rings li>span i{font-size:13px;color:var(--tone);display:inline-grid}.command-rings li>small{font-size:9px;color:#7f96b4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;margin-top:2px}
.command-support-note{display:flex;align-items:center;gap:5px;font-size:9.5px;color:#7f96b4;margin:6px 0 0;line-height:1.4;flex:none}.command-support-note i{font-size:12px;color:#36dcf0;display:inline-grid;flex:none}
/* 优先推进表 */
.command-priority-table{min-height:0;overflow:auto;flex:1}.command-priority-table table{width:100%;height:100%;border-collapse:collapse;text-align:left;table-layout:fixed}.command-priority-table th{font-size:9.5px;color:#7f96b4;font-weight:500;padding:0 7px 6px}.command-priority-table td{font-size:10.5px;color:#c5d6e6;padding:5px 7px;border-top:1px solid rgba(88,142,208,.16);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;vertical-align:middle}.command-priority-table th:first-child{width:28px}.command-priority-table th:nth-child(2){width:32%}.command-priority-table th:nth-child(3){width:13%}.command-priority-table th:nth-child(4){width:12%}.command-priority-table th:nth-child(5){width:13%}.command-priority-table th:nth-child(6){width:15%}.command-priority-table td strong,.command-priority-table td small{display:block;overflow:hidden;text-overflow:ellipsis}.command-priority-table td strong{color:#e6effb;font-size:11px}.command-priority-table td small{color:#7f96b4;font-size:9px;margin-top:2px}.command-priority-table td b{font-family:var(--num);color:#f3f8ff;font-size:12px}.command-priority-table td>button{padding:3px 8px;font-size:10px}
.command-priority-table .rank{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:6px;font-size:10.5px;font-style:normal;font-weight:700;color:#0a1f3a;background:rgba(127,150,180,.45);font-family:var(--num)}.command-priority-table .rank.r1{background:linear-gradient(135deg,#ffe28a,#ffb020);box-shadow:0 0 10px rgba(255,190,50,.5)}.command-priority-table .rank.r2{background:linear-gradient(135deg,#e6f0ff,#9fb6cd)}.command-priority-table .rank.r3{background:linear-gradient(135deg,#ffc19a,#d9824a)}
.command-priority-table .stage-chip{display:inline-block;max-width:100%;overflow:hidden;text-overflow:ellipsis;padding:2px 7px;border-radius:9px;font-size:9.5px;color:#9fe8ff;background:rgba(54,220,240,.12);border:1px solid rgba(54,220,240,.3)}
.command-probability-pill{display:inline-block;padding:2px 7px;border-radius:8px;font-size:9.5px;font-weight:600;font-family:var(--num)}.command-probability-pill.is-high{background:#174f42;color:#6ce4bc}.command-probability-pill.is-mid{background:#55421f;color:#f0c66e}.command-probability-pill.is-low{background:#572c38;color:#f18a98}
.prob-bar{margin:4px 0 0;height:3px;border-radius:2px;background:rgba(58,92,140,.35);overflow:hidden}.prob-bar i{display:block;height:100%;border-radius:2px;background:linear-gradient(90deg,#2a84ff,#36dcf0)}
.command-analysis-empty{margin:auto;text-align:center;color:#6f90a9;font-size:10px}
@media(max-height:820px) and (min-width:901px){.command-opportunity-dashboard{gap:7px}.command-opportunity-head .command-intro p{display:none}.command-opportunity-head .command-intro h3{font-size:17px}.command-opportunity-kpis>.kpi{padding:7px 12px 6px}.command-opportunity-kpis b{font-size:20px;margin:3px 0 2px}.command-opportunity-kpis .kpi-ic{width:26px;height:26px;font-size:15px;top:7px;right:9px}.kpi-gauge{display:none}.kpi-bar{display:none}.kpi-split,.kpi-split-l{display:none!important}.command-analysis-grid{gap:7px}.command-analysis-card{padding:7px 9px}.command-analysis-card>header{margin-bottom:4px;padding-bottom:4px}.command-analysis-card header p{display:none}.command-donut{width:80px}.command-pipeline b{font-size:17px}.command-pipeline em{display:none}.command-rings svg{width:58px;height:58px}.command-rings li>b{top:19px;font-size:14px}.command-rings li>small,.command-support-note{display:none}.command-columns{padding-top:8px}.command-columns .col>small{display:none}.command-priority-table td{padding:3px 6px}.command-priority-table td small,.prob-bar{display:none}}
@media(max-width:1100px){.command-opportunity-dashboard{overflow:auto}.command-opportunity-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.command-analysis-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:none;overflow:visible;flex:none}.command-analysis-card{min-height:230px}.command-probability-card,.command-stage-card,.command-region-card,.command-support-card,.command-signing-card{grid-column:span 1}.command-opportunity-priority{grid-column:1/-1;min-height:250px}}
@media(max-width:700px){.command-opportunity-head{align-items:flex-start;flex-direction:column}.command-opportunity-kpis,.command-analysis-grid{grid-template-columns:1fr}.command-opportunity-priority,.command-probability-card,.command-stage-card,.command-region-card,.command-support-card,.command-signing-card{grid-column:1}.command-analysis-card{min-height:220px}.command-pipeline{flex-wrap:wrap}.command-pipeline li{flex:1 1 30%}}
@media(max-width:900px){.command-summary :deep(.bo-grid){grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.command-summary :deep(.bo-grid),.command-kpis{grid-template-columns:1fr}.command-summary :deep(.bo-card){min-height:180px}.command-list-head{align-items:flex-start;flex-direction:column}}
</style>
