<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BusinessSheet } from '../../../src/services/personalWorkApi'
import { companyOrders, companyReceipts, companyCashFlow } from './companyOrders'
import { TrendCharts, Trophy } from '@element-plus/icons-vue'
import { cartesianChart } from './businessCartesianChart'
import { businessRegionTone } from './businessRegionTone'
const props = defineProps<{ sheets: BusinessSheet[]; dark?: boolean; receipts?: boolean; comparison?: boolean }>()
const label = computed(() => props.receipts ? '回款' : '订货')
const dateLabel = computed(() => props.receipts ? '回款' : '签订')
const calculate = computed(() => props.receipts ? companyReceipts : companyOrders)
const year = ref(new Date().getFullYear())
const data = computed(() => calculate.value(props.sheets, year.value))
const cashFlow = computed(() => companyCashFlow(props.sheets, year.value))
watch(() => props.sheets, () => { const latest = calculate.value(props.sheets, year.value).years[0]; if (latest) year.value = latest }, { immediate: true })
const trendCharts = computed(() => {
  const series = [{ key: 'order', label: label.value, color: '#348be3' }, ...(!props.receipts ? [{ key: 'managed', label: '管理订货', color: '#21b9a8' }] : [{ key: 'cash', label: '经营现金流', color: '#21b9a8' }])]
  const chartRows = data.value.months.map((item, index) => ({ ...item, cash: cashFlow.value.months[index]!.cash, category: `${item.month}月` }))
  const values = chartRows.flatMap(item => series.flatMap(entry => {
    const amount = item[entry.key as 'order' | 'managed' | 'cash']
    return amount === null ? [] : [amount]
  }))
  const domain: [number, number] = [Math.min(0, ...values), Math.max(1, ...values)]
  return cartesianChart(chartRows, series,
    { name: 'category', title: `1—12月${label.value}月度柱状对比`, unit: '万元', line: false, domain, width: 1100, decimals: 0 })
})
const format = (value: number | null) => value === null ? '未提供' : value.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
const rankingMaximum = computed(() => Math.max(1, ...data.value.top.map(item => Math.abs(item.amount))))
</script>
<template>
  <section class="company-orders" :class="{ dark }">
    <header><div><h3><span class="business-step">{{ receipts ? '04' : '02' }}</span><el-icon><TrendCharts /></el-icon> 1—12月{{ receipts ? '回款' : '新增订货' }}</h3><p>{{ receipts ? '实际回款' : '订货 / 管理订货' }} · 当月发生额 · 单位：万元</p></div><el-select v-model="year" :aria-label="`${label}统计年份`" style="width:120px"><el-option v-for="item in data.years.length ? data.years : [year]" :key="item" :value="item" :label="`${item}年`"/></el-select></header>
    <p v-if="receipts">取本版本“实际回款明细”，按实际回款日期汇总；有“公司月度回款”表时优先使用其月度实际值。计划回款与合同金额不计入实际回款。</p>
    <p v-else>订货取本版本“已完成订单明细”的含税合同金额，按签订月份汇总；有“公司月度订货”表时优先使用其月度值。管理订货仅使用该表的实际值。</p>
    <div v-if="comparison" class="be-month-matrix"><article v-for="month in data.months" :key="month.month"><h4>{{ month.month }}月</h4><span>{{ label }}</span><b>{{ format(month.order) }}</b><template v-if="!receipts"><span>管理订货</span><b>{{ format(month.managed) }}</b></template></article></div>
    <template v-else>
      <div class="monthly-legend"><span><i class="order-swatch"></i>{{ label }}</span><span><i class="managed-swatch"></i>{{ receipts ? '经营现金流' : '管理订货（折算后）' }}</span></div>
      <div class="monthly-trends monthly-columns" v-html="trendCharts" />
    </template>
    <p>1—12月连续展示；缺失数据标记为未提供，不计为零。</p>
    <p v-if="receipts">现金流仅取“公司月度现金流”的同年实际数据，不使用项目年份现金流替代。已提供 {{ cashFlow.count }}/12 个月；重复月份或缺失数据不绘制。<strong v-if="!cashFlow.count">当前版本未提供可用月度现金流。</strong></p>
    <p v-if="data.invalidDates">有 {{ data.invalidDates }} 条明细缺少有效{{ dateLabel }}日期，未计入月度和年度排名。</p>
    <h3><span class="business-step">{{ receipts ? '05' : '03' }}</span><el-icon><Trophy /></el-icon> {{ year }}年{{ label }}金额 TOP10</h3>
    <p v-if="data.top.length" class="ranking-summary">截至明细最新月份 {{ data.cutoffMonth }}月，四区域{{ label }}合计 <b>{{ format(data.rankingTotal) }}万元</b>，TOP10合计 <b>{{ format(data.topTotal) }}万元</b>，占比 <b>{{ data.rankingTotal > 0 ? (data.topTotal / data.rankingTotal * 100).toFixed(1) + '%' : '不适用' }}</b>。</p>
    <p>排名仅纳入东区、西区、中区、广东；分母为同范围项目明细合计，不与上方公司月度汇总混用。金额取整显示，计算保留原始精度。<template v-if="data.excludedProjects">已排除公司其他、历史区域或归属待核验项目 {{ data.excludedProjects }} 个。</template></p>
    <p>按项目编码汇总本版本{{ receipts ? '实际回款' : '已完成订单' }}明细、金额降序；同项目多个{{ dateLabel }}月份并列展示，排名金额不与月度汇总表重复相加。</p>
    <ol v-if="data.top.length" class="project-ranking" :aria-label="`${label}项目金额排名`">
      <li v-for="(item,index) in data.top" :key="item.code" :data-region-tone="businessRegionTone(item.region) || undefined">
        <span class="rank-number" :class="{ leading: index < 3 }">{{ index + 1 }}</span>
        <div class="rank-project">
          <strong>{{ item.name }}</strong>
          <small>{{ item.region }} · {{ dateLabel }}月份：{{ item.months }}</small>
          <div v-if="!comparison" class="rank-track"><i :class="{ negative: item.amount < 0 }" :style="{ width: `${Math.abs(item.amount) / rankingMaximum * 100}%` }"></i></div>
        </div>
        <b class="rank-value">{{ format(item.amount) }}<small>万元</small></b>
      </li>
    </ol>
    <el-empty v-else :description="`该年份暂无有效${label}明细`" :image-size="60" />
    <details v-if="receipts"><summary>回款数据补充格式</summary><p>在完整经营分析工作簿新增“实际回款明细”：第一行为标题，第二行为表头：项目编码、项目名称、区域、回款日期、实际回款金额（元）；第三行起每笔实际回款一行。可另外新增“公司月度回款”，第二行表头为：年份、月份、实际回款（万元），每年每月一行。现金流需提供同范围“公司月度现金流”，表头为：年份、月份、经营现金流（万元）。每年每月仅一行，缺失留空，不填写计划值。连同其他子表一起导入。</p></details>
    <details v-else><summary>月度数据补充格式</summary><p>在完整经营分析工作簿新增“公司月度订货”子表：第一行为标题，第二行为表头：年份、月份、订货（万元）、管理订货（万元），第三行起填写数据。每年每月一行，空白表示未提供。连同其他子表一起重新导入后随历史版本切换。</p></details>
  </section>
</template>
<style scoped>
.monthly-legend{display:flex;gap:20px;align-items:center;margin:12px 0;font-size:13px}.monthly-legend span{display:flex;align-items:center;gap:7px}.monthly-legend i{width:10px;height:10px;border-radius:3px}.order-swatch{background:#348be3}.managed-swatch{background:#21b9a8}.monthly-columns{padding:6px 0}.monthly-columns :deep(rect){rx:3px}.monthly-columns :deep(text){font-variant-numeric:tabular-nums}
.project-ranking li[data-region-tone]{border-left:4px solid var(--region-accent)}
.monthly-trends{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:20px}.monthly-trends :deep(svg){display:block;width:100%;height:auto}.monthly-trends h4{margin:10px 0;font-size:13px}
.company-orders h3{display:flex;align-items:center;gap:8px}.company-orders h3 .el-icon{color:#348be3}.project-ranking{list-style:none;padding:0;margin:20px 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 28px}.project-ranking li{display:flex;align-items:center;gap:12px;min-width:0;padding:12px;border:1px solid #8aabc433;border-radius:10px}.rank-number{font-size:18px;font-weight:700;color:#8297ad;width:24px;flex-shrink:0}.rank-number.leading{color:#dc9b24}.rank-project{min-width:0;flex:1}.rank-project strong{font-size:13px;line-height:1.6;overflow-wrap:anywhere}.rank-project small{display:block;font-size:11px;opacity:.75;margin:5px 0}.rank-track{height:7px;background:#8aabc422;border-radius:8px;overflow:hidden}.rank-track i{display:block;height:100%;background:linear-gradient(90deg,#348be3,#21b9a8);border-radius:8px}.rank-track i.negative{background:#ef6671}.rank-value{font-size:16px;white-space:nowrap}.rank-value small{display:block;text-align:right;font-size:11px;font-weight:400;opacity:.7}.company-orders summary{cursor:pointer;padding:10px 0;color:#348be3}@media(max-width:900px){.project-ranking{grid-template-columns:1fr}}@media(max-width:480px){.project-ranking li{flex-wrap:wrap}.rank-value{margin-left:36px}}
.company-orders{margin:16px 0;padding:22px;border:1px solid #dbe6f3;border-radius:14px;background:#fff;color:#274665}.company-orders.dark{background:#0b1d35;color:#d2e8ff;border-color:#264c73}.company-orders header{display:flex;justify-content:space-between;gap:16px}.company-orders h3{margin:0 0 12px}.company-orders p,.company-orders details{font-size:12px;line-height:1.8;opacity:.8}.month-scroll{overflow-x:auto}.months{display:grid;grid-template-columns:repeat(12,minmax(75px,1fr));gap:8px;margin:20px 0}.months article{text-align:center}.bars{height:150px;display:flex;gap:5px;align-items:flex-end;border-bottom:1px solid #8aabc455;margin-bottom:10px}.bar{flex:1;border-radius:4px 4px 0 0}.order{background:#348be3}.managed{background:#21b9a8}.order-text{color:#348be3}.managed-text{color:#21a898}.months small{display:block;margin-top:7px;font-size:11px}.dark :deep(.el-table){--el-table-bg-color:#0b1d35;--el-table-tr-bg-color:#0b1d35;--el-table-header-bg-color:#102941;--el-table-text-color:#d2e8ff;--el-table-header-text-color:#b4d5f4;--el-table-border-color:#264c73;--el-table-row-hover-bg-color:#173755}details{margin-top:16px}
</style>
<style scoped>
.months{grid-template-columns:repeat(12,minmax(0,1fr));gap:clamp(4px,.6vw,8px);padding:0 4px;max-width:1080px;margin:20px auto}
.months article{min-width:0}
.bars{justify-content:center;gap:4px;margin-bottom:16px}
.bar{flex:0 1 24px;min-width:0;max-width:24px}
.months small{margin-top:10px;line-height:1.5;overflow-wrap:anywhere}
.month-scroll{overflow:visible;padding-bottom:10px}
.months{grid-template-columns:repeat(auto-fit,minmax(80px,1fr));row-gap:28px}
</style>
