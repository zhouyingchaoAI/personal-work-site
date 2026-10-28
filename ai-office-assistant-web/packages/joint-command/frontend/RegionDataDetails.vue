<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BusinessSheet } from '../../../src/services/personalWorkApi'

const props = defineProps<{ sheets: BusinessSheet[]; period: string }>()
const sections = [
  { id: 'business', label: '业务明细', keys: ['原表业务', '业务明细'], timed: true },
  { id: 'monthly', label: '月度拆解 / 发货验收', keys: ['月度拆解'], timed: true },
  { id: 'receivables', label: '应收款性质', keys: ['应收原表', '应收款结构'], timed: false },
  { id: 'plans', label: '历史回款计划', keys: ['历史回款计划'], timed: false },
  { id: 'periods', label: '完整期间指标', keys: ['原表期间', '期间指标'], timed: true },
  { id: 'audit', label: '原表核对说明', keys: ['原表核对说明'], timed: false },
]
const sheetFor = (keys: string[]) => keys.map(key => props.sheets.find(sheet => sheet.key === '区域经营_' + key)).find(Boolean)
const available = computed(() => sections.filter(section => sheetFor(section.keys)))
const active = ref('business')
const search = ref('')
const region = ref('全部可见范围')
const page = ref(1)
const pageSize = 20
const selected = computed(() => available.value.find(section => section.id === active.value) || available.value[0])
const sheet = computed(() => selected.value ? sheetFor(selected.value.keys) : undefined)
const objects = computed(() => (sheet.value?.rows || []).map((row, index) => ({ index, values: Object.fromEntries(sheet.value!.headers.map((header, column) => [header, row[column]])) })))
const range = (values: Record<string, unknown>) => String(values['原表范围'] || values['区域'] || '')
const ranges = computed(() => [...new Set(objects.value.map(row => range(row.values)).filter(Boolean))])
function inPeriod(values: Record<string, unknown>) {
  if (!selected.value?.timed) return true
  if (values['期间']) return values['期间'] === props.period
  const month = Number(values['月份'])
  if (!Number.isFinite(month) || month < 1 || month > 12) return false
  if (props.period === '全年') return true
  if (props.period === 'H1') return month <= 6
  if (props.period === 'YTD-3季度') return month <= 9
  if (/^Q[1-4]$/.test(props.period)) return Math.ceil(month / 3) === Number(props.period.slice(1))
  return month === Number(props.period.replace('月', ''))
}
const filtered = computed(() => objects.value.filter(row => inPeriod(row.values) && (region.value === '全部可见范围' || range(row.values) === region.value) && (!search.value.trim() || Object.values(row.values).some(value => String(value ?? '').toLowerCase().includes(search.value.trim().toLowerCase())))))
const shown = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const headers = computed(() => (sheet.value?.headers || []).filter(header => header !== '区域' || !sheet.value?.headers.includes('原表范围')))
const display = (header: string, value: unknown) => {
  if (value === null || value === undefined || value === '') return '未提供'
  if (typeof value !== 'number') return String(value)
  if (/完成率|比例|占比/.test(header)) return (value * 100).toFixed(1) + '%'
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 6 })
}
watch([active, () => props.period, region, search, () => props.sheets], () => { page.value = 1 })
watch(active, () => { region.value = '全部可见范围'; search.value = '' })
</script>

<template>
  <details v-if="available.length" class="region-details">
    <summary>完整经营数据与来源明细 <span>· {{ available.length }} 类数据，点击展开</span></summary>
    <header><p>按需查阅业务、月度拆解、应收款及核对说明，支持筛选。</p></header>
    <nav aria-label="区域经营明细分类"><button v-for="section in available" :key="section.id" type="button" :class="{ active: selected?.id === section.id }" :aria-pressed="selected?.id === section.id" @click="active = section.id">{{ section.label }} <b>{{ sheetFor(section.keys)?.rows.length || 0 }}</b></button></nav>
    <div class="detail-filters">
      <el-select v-model="region" aria-label="明细范围" style="width:220px"><el-option label="全部可见范围" value="全部可见范围" /><el-option v-for="item in ranges" :key="item" :label="item" :value="item" /></el-select>
      <el-input v-model="search" clearable placeholder="搜索合同号、指标、性质、来源…" aria-label="搜索区域经营明细" style="width:300px;max-width:100%" />
      <span>{{ selected?.timed ? '当前期间：' + period : '历史计划 / 存量 / 核对说明，不随期间分摊' }} · 匹配 {{ filtered.length }} / 原表 {{ objects.length }} 条</span>
    </div>
    <p class="detail-note">不同指标、区域行与合计行不能重复相加。历史上海、公司其他仅保留原表归属，不计入四区域业绩；空值与零值分别展示。</p>
    <p v-if="!filtered.length" class="detail-empty">当前期间或筛选条件没有记录；可切换全年、清空搜索或更换范围。</p>
    <div class="detail-records">
      <article v-for="row in shown" :key="row.index"><div class="record-heading"><b>#{{ row.index + 1 }}</b><strong>{{ range(row.values) || selected?.label }}</strong><span>{{ row.values['经营指标'] || row.values['指标'] || row.values['回款性质'] || row.values['性质'] || '' }}</span></div><dl><div v-for="header in headers" :key="header"><dt>{{ header }}</dt><dd>{{ display(header, row.values[header]) }}</dd></div></dl></article>
    </div>
    <el-pagination v-if="filtered.length" v-model:current-page="page" :page-size="pageSize" :total="filtered.length" :pager-count="5" layout="prev, pager, next" aria-label="经营明细翻页" />
    <p class="detail-note">每页 {{ pageSize }} 条，全部匹配记录均可翻页查看。来源：{{ sheet?.source }}</p>
  </details>
</template>

<style scoped>
summary{cursor:pointer;font-weight:600;padding:4px 0}summary span{font-size:12px;font-weight:400;opacity:.65}
.region-details{margin:20px 0;padding:18px;border:1px solid var(--bi-line,#dce7f3);background:var(--bi-panel,#fff);border-radius:14px;color:inherit}
h3{margin:0;font-size:18px}header p,.detail-note{font-size:12px;opacity:.7;line-height:1.6}
nav{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0}nav button{cursor:pointer;border:1px solid var(--bi-line,#dce7f3);border-radius:8px;padding:9px 12px;background:transparent;color:inherit}nav button.active{background:#246da4;color:white;border-color:#246da4}nav b{margin-left:5px;opacity:.7}
.detail-filters{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.detail-filters>span{font-size:12px;opacity:.7}
.detail-records{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0}
article{border:1px solid var(--bi-line,#dce7f3);border-radius:9px;padding:12px;min-width:0}.record-heading{display:flex;gap:9px;align-items:center;font-size:13px}.record-heading>b{font-size:11px;opacity:.5}.record-heading>span{margin-left:auto;opacity:.7}
dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:0}dt{font-size:10px;opacity:.6}dd{margin:4px 0 0;font-size:12px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}.detail-empty{padding:24px;text-align:center;opacity:.6}
@media(max-width:1000px){.detail-records{grid-template-columns:1fr}}@media(max-width:600px){dl{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
