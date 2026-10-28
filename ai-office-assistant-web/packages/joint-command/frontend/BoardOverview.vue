<script setup lang="ts">
import { computed } from 'vue'
import { DataAnalysis, User, TrendCharts, Aim, Odometer, ArrowRight } from '@element-plus/icons-vue'
import type { CrmUnit, CrmPerson, CrmRelation, CrmOpportunity, CrmPlaybook, BusinessAnalysisData } from '../../../src/services/personalWorkApi'
import { opportunityProbability } from './opportunityProbability'
import { isActiveOpportunity, countedAmount, isCustomerUnit } from './command/commandOverview'

const props = defineProps<{
  representative?: boolean
  business: BusinessAnalysisData | null
  units: CrmUnit[]
  people: CrmPerson[]
  relations: CrmRelation[]
  opportunities: CrmOpportunity[]
  followups: CrmPlaybook['followups']
}>()
const emit = defineEmits<{ navigate: [tab: string]; cockpit: [] }>()

const dash = computed(() => (props.business as any)?.dashboard || null)
const light: Record<string, string> = { green: '#1f9d63', amber: '#d98921', red: '#d64545', gray: '#8a94a6' }
const fmt = (v: any) => (v === null || v === undefined || v === '' || !isFinite(Number(v))) ? '—' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 1 })
const pct = (v: any) => (v === null || v === undefined || v === '') ? '—' : (Number(v) * 100).toFixed(1) + '%'

// 经营分析
const bizMetrics = computed(() => {
  const K = dash.value?.P01_红绿灯 || []
  return ['订货', '回款', '毛利'].map(n => K.find((k: any) => k.指标 === n)).filter(Boolean).map((k: any) => ({ name: k.指标, rate: k.Q3完成率, light: k.灯 }))
})
const bizAux = computed(() => dash.value?.P01_辅助 || null)
const coreBusinessMetrics = computed(() => ['订货','管理订货','财务收入','回款','毛利'].map(name => {
 const row = (dash.value?.P01_红绿灯 || []).find((item: any) => item.指标 === name)
 return {name,actual:row?.实际,rate:row?.Q3完成率,color:light[row?.灯] || '#78b9ef'}
}))
const businessFocus = computed(() => {
  const valid = bizMetrics.value.filter((m: any) => m.rate !== null && m.rate !== undefined && m.rate !== '' && Number.isFinite(Number(m.rate)))
  const lowest = [...valid].sort((a: any,b: any) => Number(a.rate) - Number(b.rate))[0]
  if (!lowest) return '暂无可比较的完成率'
  return `${lowest.name}完成率最低 ${pct(lowest.rate)}`
})
const benefitMetrics = computed(() => [
  { name:'毛利率', value:bizAux.value?.毛利率实际, ratio:true },
  { name:'费效比', value:bizAux.value?.费效比实际, ratio:false },
  { name:'营业利润', value:bizAux.value?.营业利润, ratio:false },
].map(item => ({ ...item, valid:item.value !== null && item.value !== undefined && item.value !== '' && Number.isFinite(Number(item.value)) })))
const customerTypes = computed(() => {
  const counts = new Map<string,number>()
  for (const unit of props.units.filter(isCustomerUnit)) counts.set(unit.type || '未分类',(counts.get(unit.type || '未分类') || 0)+1)
  return [...counts].sort((a,b)=>b[1]-a[1])
})
const projectRegions = computed(() => {
 const totals = new Map<string,number>()
 for (const item of keyProjects.value) totals.set(item.region || '未分区',(totals.get(item.region || '未分区') || 0)+Number(item.amount || 0))
 return [...totals].sort((a,b)=>b[1]-a[1])
})

// 五位一体
const customerCount = computed(() => props.units.filter(isCustomerUnit).length)
const relHealth = computed(() => {
  const total = props.relations.length
  const alarm = props.relations.filter(r => r.decay_state === 'alarm').length
  const warn = props.relations.filter(r => r.decay_state === 'warning').length
  const single = props.relations.filter(r => r.single_point_risk).length
  return { total, alarm, warn, normal: Math.max(0, total - alarm - warn), single }
})

// 商机管理
const followupCount = computed(() => { const m = new Map<string, number>(); for (const f of props.followups || []) if (f.project_id) m.set(f.project_id, (m.get(f.project_id) || 0) + 1); return m })
const oppStat = computed(() => {
  const active = props.opportunities.filter(isActiveOpportunity)
  const amount = active.reduce((s, o) => s + countedAmount(o), 0)
  let hi = 0, mid = 0, lo = 0
  for (const o of active) { const p = opportunityProbability(o, followupCount.value.get(o.code) || 0).probability; if (p >= 70) hi++; else if (p >= 40) mid++; else lo++ }
  return { count: active.length, amount, hi, mid, lo, unassigned: active.filter(o => !o.manager?.trim()).length }
})

// 项目作战地图
const keyProjects = computed(() => props.opportunities
  .filter(o => isActiveOpportunity(o) && countedAmount(o) >= 1000)
  .sort((a, b) => countedAmount(b) - countedAmount(a)))
const projectFocus = computed(() => oppStat.value.amount > 0
  ? `重点项目占在谈金额 ${pct(keyProjects.value.reduce((sum, o) => sum + countedAmount(o), 0) / oppStat.value.amount)}`
  : '暂无在谈金额可计算占比')
const stageDistribution = computed(() => {
  const counts = new Map<string, number>()
  for (const o of props.opportunities.filter(isActiveOpportunity)) {
    const stage = o.sales_stage || o.stage || '未填阶段'
    counts.set(stage, (counts.get(stage) || 0) + 1)
  }
  return [...counts].sort((a,b) => b[1] - a[1]).slice(0, 2)
})
</script>

<template>
  <section class="board-ov" :class="{ 'bo-representative': representative }">
    <header class="bo-head">
      <div><h3>四大板块概览</h3><p>关键结论一屏速览，点卡片进入对应板块</p></div>
      <button type="button" class="bo-cabin" @click="emit('cockpit')"><el-icon><Odometer /></el-icon>进入联合指挥驾驶舱<el-icon class="bo-cabin-arw"><ArrowRight /></el-icon></button>
    </header>
    <div class="bo-grid">
      <!-- 经营分析 -->
      <button type="button" class="bo-card is-biz" @click="emit('navigate', 'dashboard')">
        <div class="bo-c-hd"><span class="bo-ic"><el-icon><DataAnalysis /></el-icon></span><b>经营分析</b><el-icon class="bo-go"><ArrowRight /></el-icon></div>
        <template v-if="dash">
          <div v-if="representative" class="bo-core-business" aria-label="核心经营指标">
            <div class="bo-chart-title">核心经营指标 · 实际 / Q3完成率</div>
            <div v-for="m in coreBusinessMetrics" :key="m.name" class="bo-core-row" :title="`${m.name}：实际${fmt(m.actual)}万元，Q3完成率${pct(m.rate)}`"><span>{{ m.name }}</span><b>{{ fmt(m.actual) }}<small>万</small></b><i><em :style="{width:Math.max(0,Math.min(100,Number(m.rate || 0)*100))+'%',background:m.color}"></em></i><strong :style="{color:m.color}">{{ pct(m.rate) }}</strong></div>
          </div>
          <div v-else class="bo-rows">
            <div v-for="m in bizMetrics" :key="m.name" class="bo-mrow"><span>{{ m.name }}</span><span class="bo-mt"><i :style="{ width: Math.min(100, Number(m.rate || 0) * 100) + '%', background: light[m.light] }"></i></span><b :style="{ color: light[m.light] }">{{ pct(m.rate) }}</b></div>
          </div>
          <div v-if="representative" class="bo-extra-chart" aria-label="经营效益指标图"><div class="bo-chart-title">经营效益 · 实际值</div><div class="bo-benefits"><div v-for="item in benefitMetrics" :key="item.name"><span>{{ item.name }}</span><b :class="{negative:item.valid && Number(item.value)<0}">{{ item.valid ? (item.ratio ? pct(item.value) : (item.name === '费效比' ? Number(item.value).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : fmt(item.value)) + (item.name === '营业利润' ? '万' : '')) : '—' }}</b></div></div></div>
          <div v-else class="bo-foot"><span>毛利率 <b :style="{ color: light.red }">{{ pct(bizAux?.毛利率实际) }}</b></span><span>营业利润 <b :style="{ color: light.red }">{{ fmt(bizAux?.营业利润) }}</b> 万</span></div>
        </template>
        <div v-else class="bo-empty">未导入经营数据 · 点击进入导入</div>
        <div v-if="representative" class="bo-focus" :title="businessFocus"><span>重点</span>{{ dash ? businessFocus : '待导入经营数据' }}</div>
      </button>

      <!-- 五位一体 -->
      <button type="button" class="bo-card is-cust" @click="emit('navigate', 'customers')">
        <div class="bo-c-hd"><span class="bo-ic"><el-icon><User /></el-icon></span><b>五位一体</b><el-icon class="bo-go"><ArrowRight /></el-icon></div>
        <div class="bo-kpis"><div><b>{{ customerCount }}</b><span>客户</span></div><div><b>{{ people.length }}</b><span>联系人</span></div><div><b>{{ relHealth.total }}</b><span>在维关系</span></div></div>
        <div v-if="representative" class="bo-mini-chart" aria-label="关系健康分布">
          <div class="bo-chart-title">关系健康分布</div>
          <div v-for="item in [{label:'正常',value:relHealth.normal,color:light.green},{label:'预警',value:relHealth.warn,color:light.amber},{label:'告警',value:relHealth.alarm,color:light.red}]" :key="item.label" class="bo-mini-row"><span>{{ item.label }}</span><i><em :style="{width: (relHealth.total ? item.value / relHealth.total * 100 : 0) + '%',background:item.color}"></em></i><b>{{ item.value }}</b></div>
        </div>
        <div class="bo-seg" v-if="relHealth.total"><i :style="{ width: relHealth.normal / relHealth.total * 100 + '%', background: light.green }"></i><i :style="{ width: relHealth.warn / relHealth.total * 100 + '%', background: light.amber }"></i><i :style="{ width: relHealth.alarm / relHealth.total * 100 + '%', background: light.red }"></i></div>
        <div class="bo-foot"><span>待维系 <b :style="{ color: light.amber }">{{ relHealth.warn + relHealth.alarm }}</b></span><span>单点风险 <b :style="{ color: light.red }">{{ relHealth.single }}</b></span></div>
        <div v-if="representative" class="bo-extra-chart" aria-label="客户类型分布图"><div class="bo-chart-title">客户类型 · 数量分布</div><div class="bo-distribution"><div v-for="[name,count] in customerTypes" :key="name" :title="`${name} ${count}家`"><i :style="{height:Math.max(3,count / Math.max(...customerTypes.map(x=>x[1]),1)*20)+'px'}"></i><span>{{ name }}</span><b>{{ count }}</b></div><span v-if="!customerTypes.length" class="bo-empty">暂无客户</span></div></div>
      </button>

      <!-- 商机管理 -->
      <button type="button" class="bo-card is-opp" @click="emit('navigate', 'opportunities')">
        <div class="bo-c-hd"><span class="bo-ic"><el-icon><TrendCharts /></el-icon></span><b>商机管理</b><el-icon class="bo-go"><ArrowRight /></el-icon></div>
        <div class="bo-kpis"><div><b>{{ oppStat.count }}</b><span>在谈商机</span></div><div><b>{{ fmt(Math.round(oppStat.amount)) }}</b><span>可参与份额万</span></div></div>
        <div v-if="representative" class="bo-mini-chart" aria-label="在谈商机阶段分布">
          <div class="bo-chart-title">阶段分布 · 数量前二</div>
          <div v-for="[stage,count] in stageDistribution" :key="stage" class="bo-mini-row bo-stage-row"><span :title="stage">{{ stage }}</span><i><em :style="{width: (oppStat.count ? count / oppStat.count * 100 : 0) + '%',background:'#599eff'}"></em></i><b>{{ count }}</b></div>
          <span v-if="!stageDistribution.length" class="bo-empty">暂无在谈商机</span>
        </div>
        <div class="bo-seg" v-if="oppStat.count"><i :style="{ width: oppStat.hi / oppStat.count * 100 + '%', background: light.green }"></i><i :style="{ width: oppStat.mid / oppStat.count * 100 + '%', background: light.amber }"></i><i :style="{ width: oppStat.lo / oppStat.count * 100 + '%', background: light.red }"></i></div>
        <div class="bo-foot"><span>成单概率 高 <b :style="{ color: light.green }">{{ oppStat.hi }}</b></span><span>中 <b :style="{ color: light.amber }">{{ oppStat.mid }}</b></span><span>低 <b :style="{ color: light.red }">{{ oppStat.lo }}</b></span></div>
        <div v-if="representative" class="bo-focus"><span>重点</span>{{ !oppStat.count ? '暂无在谈商机' : oppStat.unassigned ? `${oppStat.unassigned} 条在谈商机待指派负责人` : '在谈商机均已填写负责人' }}</div>
      </button>

      <!-- 项目作战地图 -->
      <button type="button" class="bo-card is-battle" @click="emit('navigate', 'battle')">
        <div class="bo-c-hd"><span class="bo-ic"><el-icon><Aim /></el-icon></span><b>项目作战地图</b><el-icon class="bo-go"><ArrowRight /></el-icon></div>
        <div class="bo-kpis"><div><b>{{ keyProjects.length }}</b><span>重点项目(≥1000万)</span></div></div>
        <div v-if="representative" class="bo-chart-title">重点项目 · 金额前二</div>
        <ul class="bo-list">
          <li v-for="o in keyProjects.slice(0, representative ? 2 : 3)" :key="o.id || o.code" :title="`${o.name} · ${fmt(o.amount)}万元 · ${o.sales_stage || o.stage || '未填阶段'}`"><span class="bo-li-amt">{{ fmt(o.amount) }}万</span><span class="bo-li-nm">{{ o.name }}</span></li>
          <li v-if="!keyProjects.length" class="bo-empty2">暂无大额在谈项目</li>
        </ul>
        <div v-if="representative" class="bo-extra-chart" aria-label="重点项目区域金额分布图"><div class="bo-chart-title">区域金额 · 前二（万元）</div><div v-for="[region,value] in projectRegions.slice(0,2)" :key="region" class="bo-mini-row bo-region-row"><span :title="region">{{ region }}</span><i><em :style="{width:(value / Math.max(projectRegions[0]?.[1] || 1,1)*100)+'%',background:'#d4ae64'}"></em></i><b>{{ fmt(value) }}</b></div><span v-if="!projectRegions.length" class="bo-empty">暂无区域金额</span></div>
        <div v-if="representative" class="bo-focus" :title="projectFocus"><span>重点</span>{{ projectFocus }}</div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.bo-core-business{display:flex;flex-direction:column;gap:5px}.bo-core-row{display:grid;grid-template-columns:50px minmax(55px,auto) minmax(12px,1fr) 43px;align-items:center;gap:5px;font-size:10px;color:#bcd3e5}.bo-core-row b{color:#d0e9fb;font-size:12px;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.bo-core-row small{font-size:9px;font-weight:400;margin-left:2px;color:#91afc8}.bo-core-row i{height:5px;border-radius:3px;background:#1b3c54;overflow:hidden}.bo-core-row em{display:block;height:100%}.bo-core-row strong{text-align:right;font-size:10px}.bo-representative .bo-benefits{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}.bo-representative .bo-benefits b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bo-representative .bo-benefits span{font-size:9px}
@media(max-width:650px){.bo-core-business{gap:3px}.bo-core-row{grid-template-columns:38px minmax(0,1fr) 30px;gap:2px;font-size:9px}.bo-core-row b{font-size:9px;overflow:hidden;text-overflow:ellipsis}.bo-core-row strong{font-size:8px}.bo-core-row small,.bo-core-row i{display:none}.bo-representative .bo-benefits{grid-template-columns:1fr;gap:2px}.bo-representative .bo-benefits>div{flex-direction:row;justify-content:space-between}.bo-representative .bo-benefits b{font-size:9px}}
.bo-extra-chart{display:flex;flex-direction:column;gap:4px;border-top:1px solid #27435a;padding-top:5px}.bo-benefits{display:grid;grid-template-columns:1fr 1fr;gap:8px}.bo-benefits>div{display:flex;flex-direction:column;border-left:2px solid #528ccc;padding-left:7px;gap:2px}.bo-benefits span{color:#91afc8;font-size:10px}.bo-benefits b{color:#79d5d9;font-size:16px}.bo-benefits b.negative{color:#ff9292}.bo-distribution{display:flex;gap:7px;align-items:flex-end;min-height:32px}.bo-distribution>div{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:1px;font-size:9px;color:#aac5d9}.bo-distribution i{width:65%;max-width:28px;background:linear-gradient(#53d5c8,#236b82);border-radius:3px 3px 0 0}.bo-distribution span{white-space:nowrap}.bo-distribution b{color:#95e7dd;font-size:10px}.bo-region-row{grid-template-columns:40px minmax(0,1fr) 55px}
.bo-focus{margin-top:auto;padding-top:5px;border-top:1px solid #294761;color:#efd399;font-size:11px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}.bo-focus>span{color:#8eb1cb;margin-right:6px}
.bo-chart-title{font-size:11px;color:#91afc8;line-height:1.3}
.bo-mini-chart{display:flex;flex-direction:column;gap:5px}
.bo-mini-row{display:grid;grid-template-columns:32px minmax(0,1fr) 28px;gap:7px;align-items:center;font-size:11px;color:#c2d6e9;line-height:1.3}
.bo-mini-row>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bo-mini-row>i{height:6px;background:#1b3c54;border-radius:4px;overflow:hidden}.bo-mini-row em{display:block;height:100%;border-radius:4px}.bo-mini-row b{text-align:right;font-variant-numeric:tabular-nums}.bo-stage-row{grid-template-columns:76px minmax(0,1fr) 24px}
.bo-representative .is-cust>.bo-seg{display:none}
.bo-representative .bo-li-nm{color:#c2d6e9}.bo-representative .bo-li-amt{color:#f4c96c}
.board-ov { margin: 0 0 18px; }
.bo-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 12px; flex-wrap: wrap; }
.bo-head h3 { margin: 0; font-size: 18px; color: #15499c; }
.bo-head p { margin: 4px 0 0; font-size: 12.5px; color: #64789a; }
.bo-cabin { display: inline-flex; align-items: center; gap: 7px; font: inherit; font-size: 14px; font-weight: 600; color: #fff; border: 0; cursor: pointer; padding: 10px 18px; border-radius: 10px; background: linear-gradient(120deg, #1e6bff, #15499c); box-shadow: 0 12px 26px -14px rgba(21, 73, 156, .7); }
.bo-cabin:hover { filter: brightness(1.05); }
.bo-cabin-arw { font-size: 13px; }
.bo-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.bo-card { text-align: left; font: inherit; cursor: pointer; display: flex; flex-direction: column; gap: 10px; padding: 15px 16px; border: 1px solid #e4ecf6; border-top: 3px solid #15499c; border-radius: 14px; background: #fff; box-shadow: 0 10px 26px -20px rgba(21, 73, 156, .5); transition: transform .15s, box-shadow .15s, border-color .15s; min-height: 168px; }
.bo-card:hover { transform: translateY(-2px); box-shadow: 0 16px 32px -18px rgba(21, 73, 156, .6); }
.bo-card.is-cust { border-top-color: #0f9c93; } .bo-card.is-opp { border-top-color: #3a5ad6; } .bo-card.is-battle { border-top-color: #c98a15; }
.bo-c-hd { display: flex; align-items: center; gap: 9px; }
.bo-c-hd b { font-size: 15px; color: #1f3350; }
.bo-ic { width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; font-size: 17px; color: #fff; background: #15499c; flex: none; }
.is-cust .bo-ic { background: #0f9c93; } .is-opp .bo-ic { background: #3a5ad6; } .is-battle .bo-ic { background: #c98a15; }
.bo-go { margin-left: auto; color: #b0bccd; font-size: 14px; }
.bo-card:hover .bo-go { color: #15499c; }
.bo-rows { display: flex; flex-direction: column; gap: 7px; }
.bo-mrow { display: grid; grid-template-columns: 40px 1fr 48px; align-items: center; gap: 8px; font-size: 12px; color: #5e7690; }
.bo-mt { height: 8px; background: #eef3fb; border-radius: 4px; overflow: hidden; }
.bo-mt i { display: block; height: 100%; border-radius: 4px; }
.bo-mrow b { text-align: right; font-variant-numeric: tabular-nums; }
.bo-kpis { display: flex; gap: 16px; flex-wrap: wrap; }
.bo-kpis > div { display: flex; flex-direction: column; }
.bo-kpis b { font-size: 22px; color: #15499c; font-variant-numeric: tabular-nums; line-height: 1.1; }
.bo-kpis span { font-size: 11px; color: #8a94a6; }
.bo-seg { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #eef3fb; }
.bo-seg i { display: block; height: 100%; }
.bo-foot { margin-top: auto; display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: #64789a; }
.bo-foot b { font-variant-numeric: tabular-nums; }
.bo-empty, .bo-empty2 { font-size: 12.5px; color: #94a3b8; }
.bo-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.bo-list li { display: flex; gap: 8px; align-items: baseline; font-size: 12px; }
.bo-li-amt { color: #c0392b; font-weight: 700; font-variant-numeric: tabular-nums; flex: none; min-width: 62px; }
.bo-li-nm { color: #4a5a70; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 1100px) { .bo-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 620px) { .bo-grid { grid-template-columns: 1fr; } }
</style>
