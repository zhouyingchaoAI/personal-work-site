<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Upload, Download, DataAnalysis, TrendCharts } from '@element-plus/icons-vue'
import type { BusinessAnalysisData, BusinessCell, BusinessVersion, BusinessView, BusinessViewOptions } from '../../../src/services/personalWorkApi'
import { renderBusinessReport, formatBusinessCell } from './businessAnalysisReport'
import { bizIcon, SECTION_ICONS } from './businessIcons'
import CompanyOrders from './CompanyOrders.vue'
import RegionDataDetails from './RegionDataDetails.vue'
import { businessRegionTone, businessRegionLabels } from './businessRegionTone'
import { authState } from '../../../src/services/authSession'
import { useChartLayout } from './useChartLayout'
import './chartAppearance.css'
import './businessDarkControls.css'
import './businessRegionPeriods.css'
import './businessRegionDesign.css'
import './businessExecutiveDesign.css'
import { applyExecutiveDesign, numberBusinessSections } from './businessExecutiveDesign'
import { companyCashFlow } from './companyOrders'

const props = defineProps<{ data: BusinessAnalysisData | null; versions?: BusinessVersion[]; canImport: boolean; theme?: 'light' | 'dark'; viewOptions?: BusinessViewOptions | null; selection?: BusinessView; loading?: boolean }>()
const emit = defineEmits<{ import: []; download: [blocks?: string[]]; taskImport: []; taskDownload: []; version: [id: string]; view: [selection: BusinessView] }>()
const templateOpen = ref(false)
const templateBlocks = [
  { key: 'overall', label: '公司整体' }, { key: 'taskOrder', label: '任务令' },
  { key: 'structure', label: '经营结构' }, { key: 'region', label: '区域经营' },
  { key: 'industry', label: '产业经营' }, { key: 'foundation', label: '经营基础' },
  { key: 'projects', label: '项目监测' },
]
const selectedTemplates = ref(templateBlocks.map(block => block.key))
function changeView(view: BusinessView['view']) {
  emit('view', { view, ...(view === 'region' ? { region: props.selection?.region || props.viewOptions?.regions[0] } : {}),
    ...(view === 'personal' ? { manager: props.selection?.manager || props.viewOptions?.managers[0]?.username } : {}) })
}
const scopeLevel = computed(() => props.data?.scope?.level || 'company')
const scopedImport = computed(() => props.canImport && scopeLevel.value === 'company')

const versionList = computed(() => props.versions || [])
const currentVersion = computed({ get: () => props.data?.version || '', set: v => { if (v && v !== props.data?.version) emit('version', v) } })
const fmtTime = (v?: string) => String(v || '').replace('T', ' ').replace(/(:\d{2}):\d{2}(\.\d+)?$/, '$1')
function versionLabel(v: BusinessVersion) { return `${fmtTime(v.imported_at) || v.version}${v.filename ? ' · ' + v.filename : ''}` }

const dashboardData = computed(() => (props.data as any)?.dashboard || null)
// 按公司、区域、产业组织聚合分析与完整来源表，换版本自动更新。
const regionPeriod = ref('全年')
function openRegionDetails() {
  const details = layoutRoot.value?.querySelector<HTMLDetailsElement>('.region-details')
  if (details) {
    details.open = true
    details.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
const regionPeriods = computed(() => {
  const sheet = props.data?.sheets.find(item => item.key === '区域经营_期间指标')
  if (!sheet) return []
  return [...new Set(sheet.rows.map(row => String(row[sheet.headers.indexOf('期间')])).filter(Boolean))]
})
const periodGroups = computed(() => [
  { label: '月份', values: Array.from({ length: 12 }, (_, index) => `${index + 1}月`) },
  { label: '季度', values: ['Q1', 'Q2', 'Q3', 'Q4'] },
  { label: '年度 / 累计', values: ['全年', 'H1', 'YTD-3季度'] },
].map(group => ({ ...group, values: group.values.filter(value => regionPeriods.value.includes(value)) })).filter(group => group.values.length))
const periodCategory = ref('年度 / 累计')
const visiblePeriodGroup = computed(() => periodGroups.value.find(group => group.label === periodCategory.value) || periodGroups.value[0])
watch(regionPeriod, value => {
  const group = periodGroups.value.find(item => item.values.includes(value))
  if (group) periodCategory.value = group.label
})
const periodLabel = (value: string) => ({ Q1: '第一季度', Q2: '第二季度', Q3: '第三季度', Q4: '第四季度', H1: '上半年', 'YTD-3季度': '截至三季度' }[value] || value)
watch(regionPeriods, periods => { if (periods.length && !periods.includes(regionPeriod.value)) regionPeriod.value = periods[0]! })
const profitBasis = ref<'公司' | '利润核算角度' | 'both'>('公司')
const fullHtml = computed(() => {
  let sheets = props.data?.sheets || []
  const periods = sheets.find(item => item.key === '区域经营_期间指标')
  if (periods) {
    const headers = ['区域', '负责人', '指标', '目标', '实际', '完成率', '差额', '期间', '统计时间范围', '指标口径说明', '目标说明']
    const selected = periods.rows.filter(row => row[periods.headers.indexOf('期间')] === regionPeriod.value)
    sheets = sheets.map(sheet => sheet.key === '区域经营_年度指标' ? { ...sheet, headers, rows: selected.map(row => headers.map(header => row[periods.headers.indexOf(header)] ?? null)) } : sheet)
  }
  return renderBusinessReport(dashboardData.value, sheets, scopeLevel.value, profitBasis.value)
})
const panelTitle = computed(() => ({ company: '公司经营驾驶舱', region: '区域经营工作台', personal: '客户经理经营工作台' })[scopeLevel.value])
const panelDescription = computed(() => ({ company: '经营结果 · 区域对比 · 产业与资金质量', region: '授权区域 · 任务达成 · 项目推进', personal: '本人业务 · 任务进度 · 商机与订单' })[scopeLevel.value])
const hasOrders = computed(() => props.data?.sheets.some(sheet => sheet.key.startsWith('19_') && sheet.rows.length))
const hasReceipts = computed(() => props.data?.sheets.some(sheet => sheet.key === '实际回款明细' && sheet.rows.length))
const dashboardRoot = ref<HTMLElement | null>(null)
const dashboardParts = computed(() => {
  const doc = new DOMParser().parseFromString(fullHtml.value, 'text/html')
  doc.querySelector('.br-scope')?.remove()
  doc.querySelectorAll<HTMLElement>('[data-section]').forEach(section => {
    if (section.dataset.section !== activeSection.value) section.remove()
  })
  doc.querySelectorAll<HTMLElement>('[data-section] .br-chart-card').forEach(card => {
    if (card.closest('[data-section="region"]')) return
    const visuals = Array.from(card.querySelectorAll<HTMLElement>(':scope > .br-visual-unit'))
    if (visuals.length < 2) return
    const tables = Array.from(card.querySelectorAll(':scope > template[data-analysis-table]'))
    visuals.forEach((visual, index) => {
      const panel = card.cloneNode(false) as HTMLElement
      const title = visual.querySelector('h4')?.textContent || card.dataset.chartTitle || ''
      panel.dataset.chartTitle = title
      panel.setAttribute('aria-label', `放大图表：${title}`)
      const header = card.querySelector(':scope > header')?.cloneNode(true) as HTMLElement | undefined
      if (header) {
        const heading = header.querySelector('.br-card-title')
        if (heading) heading.textContent = title
        panel.append(header)
      }
      const note = card.querySelector(':scope > .br-note')
      if (note) panel.append(note.cloneNode(true))
      panel.append(visual.cloneNode(true))
      if (tables[index]) panel.append(tables[index]!.cloneNode(true))
      card.before(panel)
    })
    card.remove()
  })
  doc.querySelectorAll<HTMLElement>('.br-chart-card').forEach(card => {
    card.dataset.visuals = String(card.querySelectorAll(':scope > .br-visual-unit').length)
  })
  const regionCard = doc.querySelector<HTMLElement>('[data-chart-title="区域经营结果"]')
  if (regionCard) {
    const controls = doc.createElement('nav'); controls.className = 'br-region-controls'; controls.setAttribute('aria-label','区域对比指标')
    controls.innerHTML = '<span>经营结果对比</span>' + ['全部指标','收入','毛利','最终利润'].map((label,i)=>`<button type="button" data-region-series="${i-1}" aria-pressed="${i===0}">${label}</button>`).join('')
    regionCard.before(controls)
  }
  doc.querySelectorAll<HTMLElement>('.br-chart-card').forEach(card => {
    if (card.querySelectorAll('.br-plot-row,.br-heat-row,.br-record').length > 8) card.classList.add('br-full-card')
  })
  doc.querySelectorAll<HTMLElement>('.br-chart-count').forEach(c => c.insertAdjacentHTML('afterbegin', bizIcon('zoom')))
  const regionalElements = doc.querySelectorAll<HTMLElement>('.br-region-group, .br-chart-card, .br-plot-row, .br-heat-row')
  const visibleRegions = new Set<string>()
  regionalElements.forEach(element => {
    const name = element.classList.contains('br-region-group') ? element.querySelector(':scope > h3,:scope > h4')?.textContent
      : element.classList.contains('br-chart-card') ? element.dataset.chartTitle
      : element.classList.contains('br-heat-row') ? element.querySelector(':scope > span')?.textContent
      : element.querySelector('.br-plot-name,text')?.textContent
    const tone = businessRegionTone(name)
    if (!tone) return
    element.dataset.regionTone = tone
    element.setAttribute('aria-label', `${businessRegionLabels[tone]}：${name || ''}`)
    visibleRegions.add(tone)
  })
  if (visibleRegions.size) {
    const legend = doc.createElement('aside')
    legend.className = 'br-region-key'
    legend.setAttribute('aria-label', '区域颜色说明')
    const heading = doc.createElement('span'); heading.textContent = '区域标识'; legend.append(heading)
    Object.entries(businessRegionLabels).forEach(([tone, label]) => {
      if (!visibleRegions.has(tone)) return
      const item = doc.createElement('span'); item.dataset.regionTone = tone; item.textContent = label; legend.append(item)
    })
    doc.querySelector('.br-section-head')?.after(legend)
  }
  applyExecutiveDesign(doc, activeSection.value)
  const profit = doc.querySelector<HTMLElement>('.be-management-board')
  if (profit) {
    const heading = profit.querySelector('h3')
    if (heading) heading.textContent = '利润来源与费用消耗'
    const note = profit.querySelector('.be-profit-heading > p')
    if (note) note.textContent = `统计口径：${dashboardData.value?._meta?.口径 || '原表未提供统计期间，请核对来源'}。公司口径沿用原表“公司”列；利润核算角度沿用对应调整列，两者不是同比，不相加。费用明细仅按原表分类，不推测缺失的组成。`
  }
  numberBusinessSections(doc, activeSection.value)
  const profitHtml = profit?.outerHTML || ''
  profit?.remove()
  if (activeSection.value === 'overall') {
    const cashCard = doc.createElement('article')
    cashCard.className = 'br-kpi be-cash-kpi'
    cashCard.dataset.layoutKey = 'company-cash-flow'
    const cashYears = props.data?.sheets.find(sheet => sheet.key === '公司月度现金流')
    const yearIndex = cashYears?.headers.indexOf('年份') ?? -1
    const years = yearIndex >= 0 ? cashYears!.rows.map(row => Number(row[yearIndex])).filter(Number.isFinite) : []
    const cashYear = years.length ? Math.max(...years) : null
    const cash = companyCashFlow(props.data?.sheets || [], cashYear || 0)
    cashCard.innerHTML = `<span>经营现金流<small>${cashYear || '年度待提供'} · 已提供月份累计 · 万元</small></span><strong>${cash.total === null ? '未提供' : cash.total.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</strong><p>${cash.count}/12个月 · ${cash.positive}个月为正 / ${cash.negative}个月为负</p><footer>仅使用公司月度现金流，不混用项目年份口径</footer>`
    doc.querySelector('.br-kpis')?.append(cashCard)
  }
  const sources = Array.from(doc.querySelectorAll('.br-source-group'))
  const sourceHtml = sources.map(source => source.outerHTML).join('')
  sources.forEach(source => source.remove())
  doc.querySelectorAll('.be-source-list').forEach(directory => {
    const wrapper = directory.closest('.be-disclosure, .be-open-information')
    if (wrapper) wrapper.remove()
    else directory.remove()
  })
  return { content: doc.body.innerHTML, sources: sourceHtml, profit: profitHtml }
})
const dashHtml = computed(() => dashboardParts.value.content)
const activeSection = ref('overall')
const layoutRoot = ref<HTMLElement | null>(null)
const canLayout = computed(() => !!authState.user && ['admin', 'superadmin'].includes(authState.user.role))
const layoutKey = computed(() => `business-layout:v1:${authState.user?.username || ''}:${JSON.stringify(props.selection || { view: scopeLevel.value })}:${activeSection.value}`)
const { editing: layoutEditing, message: layoutMessage, reset: resetLayout, selected: selectedBlocks, fitSelected, compact: compactLayout,
  canUndo, canRedo, undo, redo, resetIndustryComparison } = useChartLayout(layoutRoot, canLayout, layoutKey)
const ic = (name: string) => bizIcon(name)
const taskMonthLabel = computed(() => {
  const sheets = props.data?.sheets || []
  const explanation = sheets.find(sheet => sheet.key === '任务令总表说明')
  const text = explanation ? explanation.rows.flat().join(' ') : sheets.filter(sheet => sheet.key.includes('任务令')).flatMap(sheet => sheet.headers).join(' ')
  const match = text.match(/(?:^|[^\d])(1[0-2]|[1-9])月/)
  return match ? `${match[1]}月任务令` : '任务令'
})
// 阅读逻辑：公司整体 → 区域经营 → 产业经营。
const dashboardSections = computed(() => [
  { key:'overall', label:'公司整体' }, { key:'taskOrder', label:taskMonthLabel.value },
  { key:'region', label:'区域经营' }, { key:'industry', label:'产业经营' }, { key:'structure', label:'经营结构' },
  { key:'foundation', label:'经营基础' }, { key:'projects', label:'项目监测' },
].filter(item => scopeLevel.value === 'company' || (scopeLevel.value === 'region' ? ['overall','taskOrder','region','projects'] : ['overall','taskOrder','projects']).includes(item.key))
  .map(item => scopeLevel.value === 'personal' ? { ...item, label: ({ overall: '我的经营', taskOrder: '我的任务', projects: '我的项目' } as Record<string,string>)[item.key] || item.label }
    : item.key === 'overall' && scopeLevel.value === 'region' ? { ...item, label: '区域总览' } : item))
watch(scopeLevel, () => { activeSection.value = 'overall'; rawOpen.value = false })
const activeSectionIndex = computed(() => Math.max(0, dashboardSections.value.findIndex(item => item.key === activeSection.value)))
function scrollParent(el: HTMLElement | null) {
  for (let n = el?.parentElement; n; n = n.parentElement) if (/(auto|scroll)/.test(getComputedStyle(n).overflowY) && n.scrollHeight > n.clientHeight) return n
  return document.scrollingElement as HTMLElement
}
function selectSection(key: string) {
  if (!dashboardSections.value.some(item => item.key === key)) return
  activeSection.value = key
  void nextTick(() => {
    const root = dashboardRoot.value
    if (root) scrollParent(root).scrollTo({ top:0, behavior:'smooth' })
  })
}
function changeSectionPage(offset: number) {
  const target = dashboardSections.value[activeSectionIndex.value + offset]
  if (target) selectSection(target.key)
}

// 点击任一可视化卡片 → 查看其来源子表原始数据
const rawOpen = ref(false)
const detailTitle = ref('图表数据')
const detailHtml = ref('')
const enlargedChart = ref('')
const detailMode = ref('chart')
const detailNote = ref('')
const sourceIds = ref<string[]>([])
const sourceExpanded = ref(false)
const detailSources = computed(() => sheets.value.filter(s => sourceIds.value.includes(s.key) || sourceIds.value.includes(s.key.slice(0, 2))))
watch(() => props.data, () => { rawOpen.value = false })
function openDataCenter() {
  detailTitle.value = '原始数据目录'; detailHtml.value = ''; enlargedChart.value = ''; detailNote.value = '沿用导入数据的字段、单位与统计范围。'
  sourceIds.value = dataSheets.value.map(s => s.key.slice(0,2)); detailMode.value = 'source'; rawOpen.value = true
}
function onDashClick(e: MouseEvent | KeyboardEvent) {
  if (layoutEditing.value) return
  if ((e.target as HTMLElement).closest('summary')) return
  const filter = (e.target as HTMLElement).closest<HTMLElement>('[data-region-series]')
  if (filter) {
    if (e.type !== 'click') return
    const selected = Number(filter.dataset.regionSeries)
    filter.parentElement?.querySelectorAll<HTMLElement>('button').forEach(b => b.setAttribute('aria-pressed',String(b===filter)))
    const card = dashboardRoot.value?.querySelector('[data-chart-title="区域经营结果"]')
    card?.querySelectorAll('.br-plot-row').forEach(row => row.querySelectorAll<HTMLElement>('.br-series-row').forEach((series,i) => {series.hidden = selected >= 0 && selected !== i}))
    card?.querySelectorAll<SVGElement>('[data-series-index]').forEach(series => { series.style.display = selected >= 0 && selected !== Number(series.dataset.seriesIndex) ? 'none' : '' })
    card?.querySelectorAll<HTMLElement>('.br-chart-legend>span').forEach((legend,i) => {legend.hidden = selected >= 0 && selected !== i})
    return
  }
  const el = (e.target as HTMLElement).closest<HTMLElement>('[data-chart-title], [data-source-ids]')
  if (!el) return
  if (e instanceof KeyboardEvent) {
    if (e.target !== el || !['Enter', ' '].includes(e.key) || el.tagName === 'BUTTON') return
    e.preventDefault()
  }
  detailTitle.value = el.dataset.chartTitle || '原始数据目录'
  detailNote.value = el.querySelector('.br-note')?.textContent || ''
  detailHtml.value = Array.from(el.querySelectorAll<HTMLTemplateElement>('template[data-analysis-table]')).map(t => t.innerHTML).join('')
  const copy = el.cloneNode(true) as HTMLElement
  copy.querySelectorAll('template,header,.br-note,.br-preview-note').forEach(n => n.remove())
  copy.querySelectorAll<HTMLElement>('[hidden]').forEach(n => { n.hidden = false })
  enlargedChart.value = copy.innerHTML
  detailMode.value = el.dataset.chartTitle ? 'chart' : 'source'
  sourceIds.value = (el.dataset.chartSources || el.dataset.sourceIds || '').split(',')
  sourceExpanded.value = !el.dataset.chartTitle
  rawOpen.value = true
}

// 导入明细（原始子表）
const sheets = computed(() => props.data?.sheets || [])
const dataSheets = computed(() => sheets.value.filter(s => !s.key.includes('导入说明')))
function isRatioHeader(h: string) { return /率|占比|达标|偏差率/.test(h) }
function fmt(v: BusinessCell, header = ''): string {
  if (v === '' || v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (typeof v === 'number') {
    return formatBusinessCell(v, header)
  }
  return String(v)
}
function cellClass(v: BusinessCell, header: string) {
  if (typeof v !== 'number') return ''
  if (/缺口|偏差/.test(header) && v < 0) return 'ba-neg'
  if (isRatioHeader(header)) return v < 0 ? 'ba-neg' : ''
  return ''
}
</script>

<template>
  <section ref="layoutRoot" class="business-analysis bi-dashboard" :class="{ 'is-dark': theme === 'dark', 'layout-editing': layoutEditing }">
    <el-dialog v-model="templateOpen" title="按板块下载当前数据模板" width="min(600px, 94vw)" append-to-body>
      <p>填入当前所选历史版本的全部实际数据，不生成随机样例。单选下载 Excel，多选下载 ZIP。</p>
      <el-checkbox-group v-model="selectedTemplates">
        <el-checkbox v-for="block in templateBlocks" :key="block.key" :value="block.key">{{ block.label }}</el-checkbox>
      </el-checkbox-group>
      <p>全选附带完整数据工作簿，可一次更新全部来源表。数据核验自动重算，无需单独填报。</p>
      <p>解压后上传 Excel；按同名表更新，其他表保留。共享表会影响多个板块，请勿重复导入旧副本。</p>
      <template #footer>
        <el-button @click="selectedTemplates = templateBlocks.map(block => block.key)">全选</el-button>
        <el-button @click="templateOpen = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedTemplates.length" @click="emit('download', selectedTemplates.slice()); templateOpen = false">下载所选（{{ selectedTemplates.length }}）</el-button>
      </template>
    </el-dialog>
    <div v-if="canLayout" class="ba-layout-toolbar">
      <el-button @click="layoutEditing = !layoutEditing">{{ layoutEditing ? '完成排版' : '编辑图表布局' }}</el-button>
      <el-button v-if="layoutEditing" @click="resetLayout">恢复默认布局</el-button>
      <el-button v-if="layoutEditing && activeSection === 'industry'" @click="resetIndustryComparison">统一产业图表尺寸</el-button>
      <el-button v-if="layoutEditing" :disabled="selectedBlocks.length < 2" @click="fitSelected">所选等宽适配（{{ selectedBlocks.length }}）</el-button>
      <el-button v-if="layoutEditing" @click="compactLayout">整理空位</el-button>
      <el-button v-if="layoutEditing" :disabled="!canUndo" @click="undo">撤销</el-button>
      <el-button v-if="layoutEditing" :disabled="!canRedo" @click="redo">重做</el-button>
      <span v-if="layoutEditing">拖顶部移动板块，拉右侧或底部边缘缩放；自动吸附对齐。{{ layoutMessage }}</span>
    </div>
    <div v-if="viewOptions" class="ba-head-actions" style="margin-bottom:12px" aria-label="经营视图切换">
      <el-select :model-value="selection?.view || 'company'" :disabled="loading" style="width:160px" aria-label="视图级别" @change="changeView">
        <el-option label="管理者视图" value="company" />
        <el-option label="区域视图" value="region" />
        <el-option label="客户经理视图" value="personal" :disabled="!viewOptions.managers.length" />
      </el-select>
      <el-select v-if="selection?.view === 'region'" :model-value="selection.region" :disabled="loading" style="width:180px" aria-label="选择区域" @change="(region: string) => emit('view', { view: 'region', region })">
        <el-option v-for="region in viewOptions.regions" :key="region" :label="region" :value="region" />
      </el-select>
      <el-select v-if="selection?.view === 'personal'" :model-value="selection.manager" :disabled="loading" filterable style="width:240px" aria-label="选择客户经理" @change="(manager: string) => emit('view', { view: 'personal', manager })">
        <el-option v-for="manager in viewOptions.managers" :key="manager.username" :label="`${manager.name}（${manager.username}）`" :value="manager.username" />
      </el-select>
      <span v-if="loading">正在加载…</span>
    </div>
    <div v-if="loading" class="ba-empty"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="!data" class="ba-empty">
      <el-icon class="ba-empty-ic"><DataAnalysis /></el-icon>
      <h3>经营分析需要先导入数据</h3>
      <p>请按《2026联指经营数据 · 标准导入模板》整理数据后导入，看板将按你上传的表格自动生成一页综合分析；重新上传新表格会更新面板。支持核心指标、作战平台、产业结构、省份、费用、订单质量、损益、现金流、机会点等 20 张子表。</p>
      <div class="ba-empty-actions">
        <el-button type="primary" :icon="Upload" :disabled="!canImport" @click="emit('import')">导入经营数据</el-button>
        <el-button :icon="Download" @click="emit('download')">下载导入模板</el-button>
      </div>
      <p v-if="!canImport" class="ba-empty-note">当前账号无导入权限，可先下载模板查看结构，导入请联系管理员。</p>
    </div>

    <template v-else>
      <header class="ba-head">
        <div class="ba-title"><span class="ba-title-icon"><el-icon><TrendCharts /></el-icon></span><div><h2>{{ panelTitle }}</h2><p>{{ panelDescription }}</p></div></div>
        <div class="ba-head-actions">
          <el-popover v-if="data.scope || dashboardData?._meta?.口径" placement="bottom-end" :width="360" trigger="click">
            <template #reference><el-button text size="small">口径说明</el-button></template>
            <p v-if="data.scope">{{ data.scope.label }}</p>
            <p v-if="dashboardData?._meta?.口径">{{ dashboardData._meta.口径 }}</p>
          </el-popover>
          <label v-if="versionList.length" class="ba-version">历史版本<el-select v-model="currentVersion" size="default" style="width:230px"><el-option v-for="v in versionList" :key="v.version" :label="versionLabel(v)" :value="v.version" /></el-select></label>
          <el-button v-if="scopeLevel === 'company'" :icon="Download" @click="templateOpen = true">下载模板</el-button>
          <el-button v-if="scopeLevel === 'company'" type="primary" :icon="Upload" :disabled="!scopedImport" @click="emit('import')">重新导入</el-button>
        </div>
      </header>

      <nav class="ba-dashboard-nav" aria-label="经营分析分页">
        <button v-for="(item,index) in dashboardSections" :key="item.key" :class="{ active:activeSection===item.key }" :aria-current="activeSection===item.key ? 'page' : undefined" @click="selectSection(item.key)"><span class="ba-page-no">{{ index + 1 }}</span><i class="ba-nav-ic" v-html="ic(SECTION_ICONS[item.key] || 'overview')"></i>{{ item.label }}</button>
        <button class="ba-data-center" @click="openDataCenter"><i class="ba-nav-ic" v-html="ic('database')"></i>数据中心</button>
      </nav>

      <div v-if="activeSection === 'taskOrder' && scopeLevel === 'company'" class="ba-task-actions">
        <span>任务令数据单独维护，导入后自动形成新的经营分析历史版本。</span>
        <el-button :icon="Download" @click="emit('taskDownload')">下载任务令模板</el-button>
        <el-button type="primary" :icon="Upload" :disabled="!canImport" @click="emit('taskImport')">导入任务令数据</el-button>
      </div>

      <template v-if="dashboardData || dataSheets.length">
        <section v-if="activeSection === 'region' && regionPeriods.length" class="region-period-picker" aria-label="区域经营统计期间">
          <header><div><strong>经营期间</strong><span>按时间查看四区域经营表现</span><el-button link type="primary" @click="openRegionDetails()">查看完整数据 ↓</el-button></div><b aria-live="polite">2026 · {{ periodLabel(regionPeriod) }}</b></header>
          <div class="region-period-tabs" role="group" aria-label="期间类型">
            <button v-for="group in periodGroups" :key="group.label" type="button" :aria-pressed="visiblePeriodGroup?.label === group.label" :class="{ selected: visiblePeriodGroup?.label === group.label }" @click="periodCategory = group.label">{{ group.label }}</button>
          </div>
          <div v-for="group in (visiblePeriodGroup ? [visiblePeriodGroup] : [])" :key="group.label" class="region-period-row" role="group" :aria-label="group.label">
            <span class="region-period-label">{{ group.label }}</span>
            <div class="region-period-buttons"><button v-for="period in group.values" :key="period" type="button" :aria-pressed="regionPeriod === period" :class="{ selected: regionPeriod === period }" @click="regionPeriod = period">{{ periodLabel(period) }}</button></div>
          </div>
        </section>
        <div ref="dashboardRoot" class="bd-scope br-workspace" :class="{ 'bd-dark': theme === 'dark' }" v-html="dashHtml" @click="onDashClick" @keydown="onDashClick"></div>
        <RegionDataDetails v-if="activeSection === 'region'" :sheets="data?.sheets || []" :period="regionPeriod" />
      </template>
      <el-empty v-else description="该版本未生成看板分析数据，请重新导入标准模板" :image-size="70" />
      <section v-if="activeSection === 'overall' && (scopeLevel === 'company' || hasOrders)" class="be-open-information be-company-detail">
        <CompanyOrders :sheets="data?.sheets || []" :dark="theme === 'dark'" />
      </section>
      <section v-if="activeSection === 'overall' && (scopeLevel === 'company' || hasReceipts)" class="be-open-information be-company-detail">
        <CompanyOrders receipts :sheets="data?.sheets || []" :dark="theme === 'dark'" />
      </section>
      <div v-if="dashboardParts.profit" class="bd-scope br-workspace be-profit-final" :class="{ 'bd-dark': theme === 'dark' }">
        <label class="profit-basis-control">损益展示口径 <select v-model="profitBasis"><option value="公司">公司口径</option><option value="利润核算角度">利润核算角度</option><option value="both">两种口径对照</option></select></label>
        <section class="br-section be-overall" v-html="dashboardParts.profit" @click="onDashClick" @keydown="onDashClick"></section>
      </div>
      <details v-if="dashboardParts.sources" :key="activeSection" class="be-disclosure be-source-directory" data-layout-key="source-directory">
        <summary><strong>来源与核对口径</strong><span>数据来源明细 · 点击展开</span></summary>
        <div class="bd-scope be-source-list" :class="{ 'bd-dark': theme === 'dark' }" v-html="dashboardParts.sources" @click="onDashClick" @keydown="onDashClick"></div>
      </details>
      <footer v-if="dashboardData || dataSheets.length" class="ba-page-footer" aria-label="经营分析翻页">
        <button :disabled="activeSectionIndex === 0" @click="changeSectionPage(-1)">← 上一页</button>
        <span><b>{{ activeSectionIndex + 1 }}</b> / {{ dashboardSections.length }} · {{ dashboardSections[activeSectionIndex].label }}</span>
        <button :disabled="activeSectionIndex === dashboardSections.length - 1" @click="changeSectionPage(1)">下一页 →</button>
      </footer>

      <el-dialog v-model="rawOpen" :title="detailTitle" width="min(1700px,96vw)" top="4vh" append-to-body class="ba-raw-dialog" :class="{ 'ba-dialog-dark': theme === 'dark' }">
        <div class="bd-scope br-modal-content" :class="{ 'bd-dark': theme === 'dark' }">
          <nav class="ba-detail-tabs"><button v-for="tab in [{key:'chart',label:'放大图表'},{key:'data',label:'数据表'},{key:'source',label:'原始数据'}]" :key="tab.key" :class="{active:detailMode===tab.key}" @click="detailMode=tab.key">{{ tab.label }}</button></nav>
          <p class="br-note">{{ detailNote }}</p>
          <div v-show="detailMode==='chart'" class="br-enlarged-chart" v-html="enlargedChart" @click="onDashClick"></div>
          <div v-if="detailHtml" v-show="detailMode==='data'" class="br-enlarged-data" v-html="detailHtml"></div>
          <p v-else-if="detailTitle !== '原始数据目录'">暂无该图表数据，可展开原始数据查看。</p>
          <details v-show="detailMode==='source'" :open="true" class="br-modal-sources">
            <summary>展开原始数据 · {{ detailSources.length }} 张来源表</summary>
            <details v-for="rawSheet in detailSources" :key="rawSheet.key" class="br-raw" :data-source-sheet="rawSheet.key">
              <summary>{{ rawSheet.key }} · {{ rawSheet.rows.length }} 行 / {{ rawSheet.headers.length }} 列</summary>
              <p class="br-note">{{ rawSheet.source }}</p>
        <div class="ba-table-wrap br-table-scroll">
          <table class="ba-rawtable">
            <thead><tr><th v-for="(h, i) in rawSheet.headers" :key="i">{{ h || '—' }}</th></tr></thead>
            <tbody>
              <tr v-for="(row, ri) in rawSheet.rows" :key="ri">
                <td v-for="(h, ci) in rawSheet.headers" :key="ci" :class="[cellClass(row[ci], h), { 'ba-firstcol': ci === 0 }]">{{ fmt(row[ci], h) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
            </details>
          </details>
        </div>
      </el-dialog>

    </template>
  </section>
</template>

<style scoped>
.ba-empty { text-align:center; padding:56px 20px; background:linear-gradient(135deg,#fff,#f6f9ff); border:1px dashed #cdd9ec; border-radius:16px; }
.ba-empty-ic { font-size:48px; color:#9fc0ec; }
.ba-empty h3 { margin:14px 0 8px; font-size:18px; color:#15499c; }
.ba-empty p { max-width:640px; margin:0 auto; font-size:13px; color:#64789a; line-height:1.8; }
.ba-empty-actions { margin:20px 0 0; display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
.ba-empty-note { margin-top:12px; color:#94a3b8; font-size:12px; }
.business-analysis { min-width:0; color:#21395e; }
.ba-head { display:flex; align-items:center; justify-content:space-between; gap:18px; flex-wrap:wrap; margin-bottom:12px; padding:18px 20px; background:linear-gradient(135deg,#f7faff,#eef5ff); border:1px solid #dfe9f7; border-radius:10px; }
.ba-title { display:flex; align-items:center; gap:13px; min-width:0; }
.ba-title-icon { display:grid; place-items:center; flex:0 0 42px; width:42px; height:42px; border-radius:9px; background:#15499a; color:#fff; box-shadow:0 7px 18px #15499a26; font-size:23px; }
.ba-head h2 { margin:0; font-size:24px; color:#12386f; letter-spacing:-.3px; }
.ba-head p { margin:6px 0 0; font-size:12.5px; color:#64789a; }
.ba-head-actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.ba-version { display:flex; align-items:center; gap:6px; font-size:12.5px; color:#64789a; }
.ba-dashboard-nav { position:sticky; top:0; z-index:6; display:flex; align-items:center; gap:5px; padding:8px 10px; margin-bottom:14px; overflow-x:auto; border:1px solid #dce7f5; border-radius:8px; background:#fffffff2; box-shadow:0 6px 18px -16px #174f9733; backdrop-filter:blur(8px); scrollbar-width:none; }
.ba-dashboard-nav>span { margin:0 7px 0 3px; color:#8192aa; font-size:11px; white-space:nowrap; }
.ba-dashboard-nav button { flex:none; border:0; border-radius:5px; padding:7px 11px; color:#577092; background:transparent; font:inherit; font-size:12px; cursor:pointer; transition:background .15s,color .15s; }
.ba-dashboard-nav button:hover,.ba-dashboard-nav button.active { color:#15499a; background:#eaf2fd; font-weight:600; }
.ba-page-no { display:inline-grid; place-items:center; width:18px; height:18px; margin-right:5px; border-radius:50%; background:#dfeafa; color:#55708f; font-size:10px; }
.ba-dashboard-nav button.active .ba-page-no { background:#15499a; color:#fff; }
.ba-page-footer { display:flex; align-items:center; justify-content:center; gap:18px; margin-top:14px; padding:10px; border:1px solid #dce7f5; border-radius:8px; background:#f8fbff; color:#64789a; font-size:12px; }
.ba-page-footer span { min-width:150px; text-align:center; }.ba-page-footer b { color:#15499a; font-size:14px; }
.ba-page-footer button { border:1px solid #cddcf0; border-radius:5px; padding:7px 14px; background:#fff; color:#15499a; cursor:pointer; }.ba-page-footer button:disabled { opacity:.4; cursor:not-allowed; }
.ba-task-actions { display:flex; align-items:center; justify-content:flex-end; gap:10px; margin:0 0 12px; padding:9px 12px; border:1px solid #dce7f5; border-radius:8px; background:#f8fbff; }.ba-task-actions span { margin-right:auto; color:#64789a; font-size:12px; }
.ba-dims { display:inline-flex; align-items:center; gap:14px; padding:8px 18px; margin-bottom:14px; background:#ECE8FA; border-radius:20px; }
.ba-dims b { font-size:13px; font-weight:600; color:#2E1B93; }
.ba-dims i { display:inline-block; width:1px; height:12px; background:#c7bff0; margin-left:14px; vertical-align:middle; }
.ba-collapse { border-top:1px solid #e6edf5; margin-top:16px; }
.ba-sheet-title { display:flex; align-items:center; gap:10px; width:100%; }
.ba-sheet-title strong { font-size:14px; color:#1f3350; }
.ba-sheet-title span { margin-left:auto; font-size:12px; color:#8a94a6; }
.ba-source { margin:0 0 10px; font-size:12px; color:#8a94a6; }
.ba-table-wrap { overflow-x:auto; border:1px solid #eef2f7; border-radius:8px; }
.ba-rawtable { border-collapse:collapse; width:100%; font-size:13px; white-space:nowrap; }
.ba-rawtable th { background:#f4f8ff; color:#31506d; font-weight:600; padding:9px 12px; text-align:right; border-bottom:1px solid #e6edf5; }
.ba-rawtable th:first-child { text-align:left; }
.ba-rawtable td { padding:8px 12px; text-align:right; color:#334155; border-bottom:1px solid #f0f3f8; font-variant-numeric:tabular-nums; }
.ba-rawtable td.ba-firstcol { text-align:left; color:#1f3350; font-weight:500; }
.ba-rawtable tbody tr:hover td { background:#f7faff; }
.ba-rawtable td.ba-neg { color:#d64545; }
@media(max-width:700px){.ba-head{align-items:flex-start;padding:14px}.ba-title-icon{display:none}.ba-head h2{font-size:21px}.ba-head-actions{width:100%}.ba-version{width:100%}.ba-version :deep(.el-select){flex:1}.ba-dashboard-nav{margin-inline:-2px}.ba-dashboard-nav>span{display:none}}
/* ===== 驾驶舱深色主题（与总体信息大屏一致） ===== */
.business-analysis.is-dark { color:#e8f0fb; }
.is-dark .ba-empty { background:linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92)); border-color:rgba(74,138,214,.38); }
.is-dark .ba-empty-ic { color:#3b9bff; } .is-dark .ba-empty h3 { color:#f3f8ff; } .is-dark .ba-empty p,.is-dark .ba-empty-note { color:#b3c3d8; }
.is-dark .ba-head { background:linear-gradient(180deg,rgba(38,86,150,.22),rgba(10,26,54,0) 90px),linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92)); border-color:rgba(74,138,214,.38); box-shadow:inset 0 1px 0 rgba(120,180,255,.18),inset 0 0 24px rgba(40,110,200,.12); border-radius:9px; }
.is-dark .ba-title-icon { background:linear-gradient(180deg,#36dcf0,#3b9bff); color:#04122a; box-shadow:0 0 14px rgba(54,220,240,.45); }
.is-dark .ba-head h2 { color:#f3f8ff; } .is-dark .ba-head p,.is-dark .ba-version { color:#b3c3d8; }
.is-dark .ba-dashboard-nav { background:rgba(8,24,50,.92); border-color:rgba(74,138,214,.38); box-shadow:0 4px 18px rgba(0,0,0,.35); }
.is-dark .ba-dashboard-nav>span { color:#7f96b4; } .is-dark .ba-dashboard-nav button { color:#b3c3d8; }
.is-dark .ba-dashboard-nav button:hover,.is-dark .ba-dashboard-nav button.active { color:#fff; background:linear-gradient(90deg,rgba(20,150,210,.9),rgba(12,96,160,.75)); box-shadow:0 0 10px rgba(30,170,255,.35); }
.is-dark .ba-page-no { background:rgba(74,138,214,.28); color:#b3c3d8; }.is-dark .ba-dashboard-nav button.active .ba-page-no { background:#36dcf0; color:#04122a; }
.is-dark .ba-page-footer { border-color:rgba(74,138,214,.38); background:rgba(8,24,50,.72); color:#91afc8; }.is-dark .ba-page-footer b { color:#36dcf0; }.is-dark .ba-page-footer button { border-color:rgba(86,156,236,.55); background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85)); color:#eaf3ff; }
.is-dark .ba-task-actions { border-color:rgba(74,138,214,.38); background:rgba(8,24,50,.72); }.is-dark .ba-task-actions span { color:#91afc8; }
.is-dark .ba-dims { background:rgba(165,123,255,.16); border:1px solid rgba(165,123,255,.35); } .is-dark .ba-dims b { color:#d9c9ff; } .is-dark .ba-dims i { background:rgba(165,123,255,.45); }
.is-dark .ba-collapse { border-top-color:rgba(88,142,208,.25); }
.is-dark .ba-collapse :deep(.el-collapse-item__header),.is-dark .ba-collapse :deep(.el-collapse-item__wrap) { background:transparent; border-color:rgba(88,142,208,.2); color:#e8f0fb; }
.is-dark .ba-sheet-title strong { color:#e8f0fb; } .is-dark .ba-sheet-title span,.is-dark .ba-source { color:#7f96b4; }
.is-dark .ba-table-wrap { border-color:rgba(88,142,208,.25); }
.is-dark .ba-rawtable th { background:rgba(22,48,86,.55); color:#b3c3d8; border-bottom-color:rgba(88,142,208,.25); }
.is-dark .ba-rawtable td { color:#d6e1ef; border-bottom-color:rgba(88,142,208,.15); } .is-dark .ba-rawtable td.ba-firstcol { color:#f3f8ff; }
.is-dark .ba-rawtable tbody tr:hover td { background:rgba(40,110,200,.12); } .is-dark .ba-rawtable td.ba-neg { color:#ff5c69; }
.is-dark .ba-version :deep(.el-select__wrapper) { background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85)); box-shadow:inset 0 0 0 1px rgba(86,156,236,.55),inset 0 0 12px rgba(60,140,240,.2); color:#eaf3ff; }
.is-dark .ba-version :deep(.el-select__placeholder),.is-dark .ba-version :deep(.el-select__selected-item) { color:#eaf3ff; }
.is-dark .ba-version :deep(.el-select__caret) { color:#9fd8ff; }
.is-dark .ba-head-actions :deep(.el-button) { border:1px solid rgba(86,156,236,.55); background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85)); color:#eaf3ff; font-weight:600; box-shadow:inset 0 0 12px rgba(60,140,240,.2); border-radius:4px; }
.is-dark .ba-head-actions :deep(.el-button:hover) { color:#9ff0ff; border-color:#36dcf0; box-shadow:inset 0 0 16px rgba(54,220,240,.35),0 0 14px rgba(54,220,240,.45); }
.is-dark .ba-head-actions :deep(.el-button--primary) { background:linear-gradient(90deg,rgba(20,150,210,.9),rgba(12,96,160,.75)); border-color:rgba(64,200,255,.75); box-shadow:0 0 12px rgba(30,170,255,.4),inset 0 0 12px rgba(120,220,255,.3); }
.is-dark .ba-empty-actions :deep(.el-button) { border:1px solid rgba(86,156,236,.55); background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85)); color:#eaf3ff; }
</style>

<style>
/* 单页综合看板（v-html，非 scoped，限定在 .bd-scope 下） */
.bd-scope { --primary:#15499A;--primary-deep:#103B7C;--primary-mid:#3385ED;--tint-bg:#F0F5FD;--tint-line:#DCE7F7;--danger:#E34B66;--success:#1AA389;--warning:#F2902D;--magenta:#7766CC;--text:#21395E;--text-sub:#5C7190;--text-muted:#8191AC; --series-1:#2878c9;--series-2:#1fa98f;--series-3:#e08a2e;--series-4:#7a5fd6;--series-5:#6f8db3;--series-6:#a9bbd2; font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif; color:var(--text); }
.bd-scope *{box-sizing:border-box}
.ba-topic-nav,.ba-detail-tabs{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 14px}
.ba-scope-note{font-size:12px;color:#7b91ab;margin-bottom:8px}.ba-scope-note summary{cursor:pointer}.ba-scope-note>div{padding:10px;border:1px solid #44618155;border-radius:6px}
.ba-topic-nav button,.ba-detail-tabs button,.ba-workspace-caption button{border:1px solid #d5e3f5;background:#f5f8ff;color:#426084;padding:8px 13px;border-radius:7px;font:inherit;font-size:14px;cursor:pointer}
.ba-topic-nav button.active,.ba-detail-tabs button.active{background:#1857a9;color:white;border-color:#367bd1;box-shadow:0 3px 10px #1857a925}
.is-dark .ba-topic-nav button,.is-dark .ba-workspace-caption button,.ba-dialog-dark .ba-detail-tabs button{background:#102b4d;border-color:#294c78;color:#bad1ea}
.is-dark .ba-topic-nav button.active,.ba-dialog-dark .ba-detail-tabs button.active{background:#176497;color:#fff;border-color:#39b8eb}
.ba-workspace-caption{display:flex;align-items:center;gap:15px;flex-wrap:wrap;margin:12px 0;color:inherit}.ba-workspace-caption>span{font-size:19px;font-weight:650}.ba-workspace-caption small{color:#7b91ab;font-size:13px}.ba-workspace-caption>div{margin-left:auto;display:flex;gap:12px;align-items:center}.ba-workspace-caption b{font-size:13px}.ba-workspace-caption button:disabled{opacity:.35;cursor:default}
.br-workspace{min-height:360px}.br-workspace>.br-kpis{margin-bottom:12px}.br-workspace>.br-quality{margin-bottom:12px}
.br-workspace .br-chart-card,.br-enlarged-chart{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-content:start;gap:0 16px}
.br-workspace .br-chart-card>header,.br-workspace .br-chart-card>.br-note{grid-column:1/-1}.br-visual-unit{min-width:0}.br-visual-unit:first-of-type:last-of-type{grid-column:1/-1}
.br-workspace .br-chart-card>header{font-size:17px;padding:15px 18px}.br-workspace .br-note{font-size:13px;line-height:1.7}
.br-workspace .br-chart-legend,.br-modal-content .br-chart-legend{font-size:14px;gap:20px;padding:10px 18px}
.br-workspace .br-plot-name,.br-modal-content .br-plot-name{font-size:14px;line-height:1.5}.br-workspace .br-series-row b,.br-modal-content .br-series-row b{font-size:14px}
.br-workspace .br-series-row,.br-modal-content .br-series-row{grid-template-columns:minmax(0,1fr) 105px;min-height:24px}.br-workspace .br-series-track,.br-modal-content .br-series-track{height:11px}
.br-workspace .br-plot-bars,.br-workspace .br-heat,.br-modal-content .br-plot-bars,.br-modal-content .br-heat{max-height:none;overflow:visible}
.br-chart [hidden]{display:none!important}.br-chart-pager{display:flex;align-items:center;justify-content:center;gap:15px;padding:12px 0 0;color:var(--text-sub);font-size:13px}.br-chart-pager button{background:var(--tint-bg);border:1px solid var(--tint-line);color:var(--primary);border-radius:5px;padding:4px 15px;cursor:pointer}.br-chart-pager button:disabled{opacity:.3;cursor:default}
.br-modal-content .br-chart svg{max-height:440px;min-height:250px}.br-workspace .br-chart svg{max-height:320px}.br-modal-content .br-donut svg{max-width:320px}.br-modal-content .br-donut p,.br-modal-content .br-donut p b{font-size:15px}
.br-modal-content .br-plot-name,.br-modal-content .br-series-row b{font-size:16px}.br-modal-content .br-series-row{min-height:28px}.br-modal-content .br-chart-legend{font-size:16px}
.br-workspace .br-heat-head,.br-workspace .br-heat-row,.br-modal-content .br-heat-head,.br-modal-content .br-heat-row{font-size:14px}
@media(max-width:900px){.br-workspace .br-chart-card,.br-enlarged-chart{grid-template-columns:minmax(0,1fr)}.ba-topic-nav button{font-size:12px;padding:6px 9px}.ba-workspace-caption small{display:none}.br-workspace .br-heat{overflow-x:auto}.br-workspace .br-series-row{grid-template-columns:minmax(0,1fr) 85px}}
.br-report{display:flex;flex-direction:column;gap:26px;font-size:13px;line-height:1.6}
.br-section{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}
.br-section>.br-section-head,.br-section>.br-kpis,.br-section>.br-quality,.br-section>.br-conclusions,.br-section>.br-source-group{grid-column:1/-1}
.br-chart-card{cursor:pointer;transition:border-color .15s,box-shadow .15s;height:100%}
.br-chart-card:hover,.br-chart-card:focus-visible{border-color:var(--primary);box-shadow:0 0 0 1px var(--primary);outline:none}
.br-chart{padding:10px 16px;max-width:100%;min-width:0}.br-chart svg{width:100%;display:block;max-height:270px}
.br-chart-legend{display:flex;gap:12px;flex-wrap:wrap;padding:6px 16px;font-size:12px;color:var(--text-sub)}
.br-chart-legend i,.br-donut p>i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
.br-chart-count{padding:6px 16px 12px;margin:0;font-size:11px;color:var(--text-muted)}
.br-plot-bars{max-height:340px;overflow:auto;scrollbar-width:thin}
/* 纵向分组柱：每个类目一列，柱顶直接标值，负值从零线向下 */
.br-columns{display:flex;align-items:stretch;gap:6px;padding:30px 10px 0;max-height:none;overflow:hidden}
.br-columns .br-plot-row{display:flex;flex-direction:column;flex:1 1 0;min-width:0;gap:6px;padding:0;border:0}
.br-columns.has-negative .br-plot-name{padding-top:14px}
.br-col.lift-1 b{margin-bottom:11px}.br-col.lift-2 b{margin-bottom:22px}.br-col.is-neg.lift-1 b{margin-bottom:0;margin-top:11px}.br-col.is-neg.lift-2 b{margin-bottom:0;margin-top:22px}
.br-columns .br-plot-row:first-child .br-col:first-child b{left:0;transform:none}.br-columns .br-plot-row:last-child .br-col:last-child b{left:auto;right:0;transform:none}
.br-col-group{position:relative;display:flex;align-items:flex-end;justify-content:center;gap:4px;width:100%;min-width:0;box-sizing:border-box;height:150px;border-bottom:1px solid var(--tint-line)}
.br-columns.has-negative .br-col-group::before{content:'';position:absolute;left:0;right:0;top:var(--zero,50%);border-top:1px dashed var(--text-muted);opacity:.7}
.br-col{position:relative;width:var(--w,18px);min-width:6px;flex:0 1 var(--w,18px);height:100%;min-height:0}
/* 柱子复用 .br-series-row 只为沿用区域筛选逻辑，必须清掉横向条的网格规则 */
.br-columns .br-series-row.br-col,.br-workspace .br-columns .br-col,.br-modal-content .br-columns .br-col{display:block;grid-template-columns:none;gap:0;margin:0;min-height:0;height:100%}
.br-col i{position:absolute;left:0;right:0;border-radius:3px 3px 0 0;min-height:2px}
.br-col.is-neg i{border-radius:0 0 3px 3px}
.br-col b{position:absolute;left:50%;transform:translateX(-50%);font-size:10.5px;font-weight:500;line-height:1;white-space:nowrap;color:var(--text);font-variant-numeric:tabular-nums;text-align:center}
.br-columns .br-plot-name{text-align:center;font-size:11.5px;line-height:1.3;color:var(--text-sub);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.br-modal-content .br-columns{overflow-x:auto;overflow-y:hidden;padding:32px 12px 0}.br-modal-content .br-col-group{height:300px}.br-modal-content .br-col b{font-size:12px}.br-modal-content .br-columns .br-plot-name{font-size:13px}.br-modal-content .br-columns .br-plot-row{min-width:max(var(--col-min,64px),88px)}
.br-plot-row{display:grid;grid-template-columns:minmax(80px,30%) minmax(0,1fr);gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--tint-line)}
.br-plot-name{font-size:12px;overflow-wrap:anywhere}.br-series-row{display:grid;grid-template-columns:minmax(0,1fr) 78px;gap:8px;align-items:center;min-height:21px}
.br-series-row b{font-size:11px;font-weight:500;text-align:right;font-variant-numeric:tabular-nums}.br-series-track{height:9px;position:relative;background:var(--tint-bg);border-radius:2px}
.br-series-track i{position:absolute;height:100%;min-width:0;border-radius:2px}.br-series-track.signed::before{content:'';position:absolute;left:50%;height:15px;top:-3px;border-left:1px solid var(--text-muted)}
.br-donut{display:flex;align-items:center;gap:16px;min-height:210px}.br-donut svg{width:44%;max-width:220px;flex:none}.br-donut>div{flex:1;min-width:0}.br-donut p{font-size:12px;margin:7px 0}.br-donut p b{display:block;padding-left:14px;font-size:12px}
.br-heat{overflow:auto;max-height:340px}.br-heat-head,.br-heat-row{display:grid;grid-template-columns:minmax(100px,1fr) repeat(var(--heat-cols),minmax(90px,1fr));gap:4px;margin-bottom:4px;min-width:380px;font-size:12px}.br-heat-head span,.br-heat-row span{padding:9px 6px;border-radius:3px}.br-heat-row span:not(:first-child){text-align:center}
.br-modal-content .br-table{font-size:14px}.br-modal-content h4{padding:8px 14px;margin:8px 0;color:var(--primary-deep)}.br-modal-content .br-table-scroll{max-height:55vh}.br-modal-sources{padding:14px;border:1px solid var(--tint-line);border-radius:8px;margin-top:18px}.br-modal-sources>summary{cursor:pointer;color:var(--primary);font-weight:600}
.ba-dialog-dark.el-dialog{background:#0b203c;--el-text-color-primary:#e8f0fb;--el-text-color-regular:#b3c3d8}.ba-dialog-dark .ba-rawtable th{background:#142e50;color:#b3c3d8}.ba-dialog-dark .ba-rawtable td{color:#e8f0fb;background:#0b203c;border-color:#29405b}
@media(max-width:900px){.br-section{grid-template-columns:minmax(0,1fr)}.br-chart-card{height:auto}.br-donut{gap:8px}.br-chart{padding:10px}.br-series-row{grid-template-columns:minmax(0,1fr) 70px}}
.br-scope{padding:14px 18px;background:var(--tint-bg);border:1px solid var(--tint-line);border-radius:8px;color:var(--text-sub)}
.br-scope b{color:var(--primary-deep);margin-right:10px}.br-scope p{margin:5px 0}.br-scope small{font-size:12px}
.br-section{display:flex;flex-direction:column;gap:14px;min-width:0}
.br-section-head{display:flex;gap:12px;align-items:center;padding:6px 0}
.br-section-head>span{display:grid;place-items:center;width:42px;height:42px;background:var(--tint-bg);border:1px solid var(--tint-line);border-radius:10px;color:var(--primary);font-weight:700;font-size:16px}
.br-section-head h3{font-size:21px;margin:0;color:var(--text)}.br-section-head p{margin:2px 0 0;color:var(--text-sub)}
.br-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.br-kpi{border:1px solid var(--tint-line);border-top:3px solid var(--primary);border-radius:8px;padding:15px;background:var(--tint-bg);min-width:0}
.br-kpi>span{display:flex;justify-content:space-between;font-weight:600}.br-kpi small{font-weight:400;color:var(--text-sub)}
.br-kpi>strong{display:block;font-size:29px;line-height:1.3;margin:10px 0 4px;color:var(--primary-deep);font-variant-numeric:tabular-nums}.br-kpi em{font-size:12px;font-weight:400;font-style:normal;margin-left:6px;color:var(--text-sub)}
.br-kpi p{margin:3px 0 10px;color:var(--text-sub)}.br-kpi footer{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;font-size:12px}.br-kpi footer>span{margin-left:auto;color:var(--text-sub)}
.br-bar-track{height:7px;background:var(--tint-line);border-radius:5px;overflow:hidden}.br-bar-track i{display:block;height:100%;background:var(--primary);border-radius:5px}
.br-quality{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--tint-line);border-radius:8px;background:var(--tint-bg)}
.br-quality>div{display:flex;align-items:baseline;gap:12px;padding:12px 16px;flex-wrap:wrap}.br-quality strong{font-size:23px;color:var(--primary-deep)}.br-quality small{color:var(--text-sub)}
.br-conclusions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.br-conclusions p{margin:0;padding:13px 15px;border:1px solid var(--tint-line);border-radius:8px;color:var(--text-sub)}.br-conclusions b{color:var(--primary);margin-right:9px}
.br-card{border:1px solid var(--tint-line);border-radius:8px;overflow:hidden;min-width:0;background:var(--br-card-bg,#fff)}
.bd-dark{--br-card-bg:rgba(8,26,53,.8)}
.br-card>header,.br-detail>summary{padding:13px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-weight:650;font-size:15px;background:var(--tint-bg);color:var(--text)}
.br-note{margin:10px 16px;color:var(--text-sub);font-size:12px}.br-empty{margin:16px;color:var(--text-muted)}
.br-source{border:1px solid var(--tint-line);border-radius:5px;padding:3px 8px;font:inherit;font-size:12px;white-space:nowrap;background:transparent;color:var(--primary);cursor:pointer}
.br-source:focus-visible,.br-table-scroll:focus-visible,summary:focus-visible{outline:2px solid var(--primary);outline-offset:-2px}
.br-table-scroll{overflow:auto;max-width:100%;max-height:480px;scrollbar-width:thin;margin:0 0 10px}
.br-table{border-collapse:separate;border-spacing:0;width:100%;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.br-table th,.br-table td{padding:10px 14px;text-align:right;border-bottom:1px solid var(--tint-line);font-weight:400}
.br-table thead th{position:sticky;top:0;z-index:1;background:var(--br-head-bg,#edf3fc);font-weight:600;color:var(--primary-deep)}
.bd-dark{--br-head-bg:#142e50}.br-table th:first-child,.br-table td:first-child{text-align:left}.br-table tbody th{font-weight:600}.br-table tr:hover{background:var(--tint-bg)}
.br-negative{color:var(--danger)!important}.br-detail>summary{cursor:pointer;list-style:none}.br-detail>summary::before{content:'›';color:var(--primary);font-size:20px}.br-detail[open]>summary::before{content:'⌄'}.br-detail>summary>span{margin-left:auto;color:var(--text-muted);font-size:12px;font-weight:400}.br-detail-source{display:flex;justify-content:flex-end;padding:10px 16px 0}
.br-bars{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 28px;padding:12px 16px 20px}
.br-bar-row>div:first-child{display:flex;justify-content:space-between;flex-wrap:wrap;gap:5px;margin-bottom:7px}.br-bar-row span{font-size:12px;color:var(--text-sub)}.br-bar-row>b{display:block;text-align:right;font-size:12px;margin-top:3px;color:var(--text-sub)}
.br-source-group{border:1px dashed var(--tint-line);border-radius:8px;padding:12px 16px;background:var(--tint-bg);color:var(--primary);font:inherit;text-align:left;cursor:pointer}.br-source-group>summary{font-weight:600;color:var(--primary);cursor:pointer}.br-raw{margin-top:10px;border-top:1px solid var(--tint-line);padding-top:8px;min-width:0}.br-raw>summary{cursor:pointer}.br-raw>summary span{color:var(--text-sub);font-size:12px;margin-left:8px}
@media(max-width:1100px){.br-conclusions{grid-template-columns:1fr}.br-quality>div{gap:5px}.br-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.br-kpis,.br-bars,.br-quality{grid-template-columns:1fr}.br-kpi>strong{font-size:27px}.br-section-head h3{font-size:18px}.br-card>header,.br-detail>summary{font-size:14px;padding:11px}.br-note{margin:10px 11px}.br-table th,.br-table td{padding:9px 11px}.br-scope{padding:12px}.br-quality>div{padding:8px 14px}.br-quality strong{margin-left:auto}.br-source-group{padding:12px}.br-bars{padding:12px}}
.bd-scope .bd1{display:flex;flex-direction:column;gap:14px}
.bd-scope .bd-kpis1{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;scroll-margin-top:64px}
.bd-scope .bd-k{background:#fcfdff;border:1px solid var(--tint-line);border-left:3px solid var(--metric-accent);border-radius:7px;padding:11px 13px;position:relative;min-height:112px;box-shadow:0 8px 22px -20px rgba(21,73,154,.55)}
.bd-scope .bd-k-dot{position:absolute;right:12px;top:12px;width:8px;height:8px;border-radius:50%}
.bd-scope .bd-k-hd{display:flex;align-items:center;gap:7px}
.bd-scope .bd-k-ic{width:28px;height:28px;border-radius:6px;display:inline-grid;place-items:center;flex:none}.bd-scope .bd-k-ic img{width:22px;height:22px;object-fit:contain}
.bd-scope .bd-k-lb{font-size:12px;color:var(--text-sub)}
.bd-scope .bd-k-v{font-family:Arial,"PingFang SC",sans-serif;font-size:26px;font-weight:700;margin:7px 0 4px;font-variant-numeric:tabular-nums;line-height:1.1;letter-spacing:-.3px}
.bd-scope .bd-k:not(.bd-k-featured) .bd-k-v{color:#103f85}.bd-scope .bd-k-featured{color:#d4e6ff;background:#15499a;border-color:#2763b1}.bd-scope .bd-k-featured .bd-k-v{color:#fff}.bd-scope .bd-k-featured .bd-k-lb,.bd-scope .bd-k-featured .bd-k-sub{color:#d4e6ff}.bd-scope .bd-k-featured .bd-k-ic{background:#2a6bbb!important}.bd-scope .bd-k-featured .bd-k-ic img{filter:brightness(0) invert(1)}.bd-scope .bd-k-featured .bd-track{background:#3874bc}
.bd-scope .bd-k-sub{font-size:11px;color:var(--text-muted)}
.bd-scope .bd-track{height:6px;background:var(--tint-line);border-radius:4px;overflow:hidden;margin:5px 0}
.bd-scope .bd-k-tick{position:absolute;top:-3px;bottom:-3px;width:0;border-left:2px dashed rgba(129,145,172,.75)}
.bd-scope .bd-k-pace{font-weight:700}
.bd-scope.bd-dark .bd-k-tick{border-left-color:rgba(232,240,251,.55)}
.bd-scope .bd-sec{display:flex;align-items:center;gap:10px;margin:7px 0 3px;min-height:36px}
.bd-scope .bd-sec-no,.bd-scope .bd-sec-icon{width:36px;height:36px;border-radius:8px;background:#eff5ff;border:1px solid #dce9fc;color:var(--primary);font-size:13px;font-weight:700;display:grid;place-items:center;flex:none}.bd-scope .bd-sec-icon img{width:27px;height:27px;object-fit:contain}
.bd-scope .bd-sec h3{margin:0;font-size:19px;font-weight:700;color:#143668}
.bd-scope .bd-sec-d{font-size:12px;color:var(--text-muted)}
.bd-scope [data-section]{scroll-margin-top:64px}
.bd-scope .bd-insights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.bd-scope .bd-ins{display:flex;gap:12px;align-items:flex-start;background:#fffbf7;border:1px solid #f8e9d8;border-radius:7px;padding:17px 15px;min-width:0}
.bd-scope .bd-ins-no{width:30px;height:30px;border-radius:7px;background:#fff2e5;border:1px solid #fee5ca;color:var(--warning);font-size:11px;font-weight:700;display:grid;place-items:center;flex:none}
.bd-scope .bd-ins b{display:block;font-size:13.5px;color:var(--primary-deep);margin-bottom:4px}
.bd-scope .bd-ins span{font-size:12px;color:var(--text-sub);line-height:1.6}
.bd-scope .bd-grid1{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));grid-auto-flow:row dense;gap:12px;align-items:stretch}
.bd-scope .bd-c{grid-column:span 2;background:#fff;border:1px solid #dce7f7;border-radius:7px;padding:0 0 12px;box-shadow:0 2px 8px -7px rgba(21,73,154,.35);min-width:0;overflow:hidden;scroll-margin-top:64px}
.bd-scope .bd-c2{grid-column:span 4}
.bd-scope .bd-grid1>.bd-c-full{grid-column:1/-1}
.bd-scope .bd-c-full .bd-cbody svg{max-width:1220px;margin:0 auto;display:block}
.bd-scope .bd-ct{margin:0 0 12px;padding:8px 11px;min-height:40px;font-size:13px;font-weight:650;color:#173e76;background:#f0f5fd;border-bottom:1px solid #e0eafa;display:flex;justify-content:space-between;align-items:center;gap:8px}
.bd-scope .bd-ct-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bd-scope .bd-ct .bd-legend{color:#6d82a1}
.bd-scope .bd-ct-r{display:flex;align-items:center;gap:10px}
.bd-scope .bd-src{font-size:10px;color:#15499a;background:#e0eafb;border-radius:12px;padding:3px 8px;white-space:nowrap;opacity:0;transition:opacity .15s}
.bd-scope .bd-clk{cursor:pointer;transition:box-shadow .15s,transform .15s,border-color .15s}
.bd-scope .bd-clk:hover{border-color:#8eafe0;box-shadow:0 7px 20px -13px rgba(21,73,154,.45);transform:translateY(-1px)}
.bd-scope .bd-clk:hover .bd-src{opacity:1}
.bd-scope .bd-cbody{min-width:0;padding:0 16px}
.bd-scope .bd-chart-note{margin:7px 1px 0;padding-top:7px;border-top:1px dashed var(--tint-line);font-size:10.5px;line-height:1.45;color:var(--text-muted)}
.bd-scope .bd-mlist{padding:6px 2px 2px}
.bd-scope .bd-mrow{display:grid;grid-template-columns:82px 1fr 52px;align-items:center;gap:10px;margin-bottom:13px}
.bd-scope .bd-mrow.has-values{grid-template-columns:70px 128px 1fr 52px;gap:8px}
.bd-scope .bd-mv{font-size:11.5px;color:var(--text);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bd-scope .bd-mv i{font-style:normal;color:var(--text-muted);font-size:10.5px}
.bd-scope .bd-ml{font-size:12.5px;color:var(--text)}
.bd-scope .bd-mt{height:14px;background:var(--tint-line);border-radius:7px;overflow:hidden}
.bd-scope .bd-mt i{display:block;height:100%;border-radius:7px;transition:width .4s}
.bd-scope .bd-mp{font-size:13px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.bd-scope .bd-mnote{font-size:11px;color:var(--text-muted);margin-top:6px;line-height:1.5}
.bd-scope .bd-legend{display:flex;gap:12px;font-size:11px;color:var(--text-sub);font-weight:400}
.bd-scope .bd-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.bd-scope table.bd-table{width:100%;border-collapse:collapse;font-size:12px}
.bd-scope table.bd-table th{background:var(--tint-bg);color:var(--primary-deep);font-weight:600;height:30px;padding:0 8px;text-align:right}
.bd-scope table.bd-table th:first-child{text-align:left}
.bd-scope table.bd-table td{height:27px;padding:0 8px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px solid var(--tint-line)}
.bd-scope table.bd-table td:first-child{text-align:left;color:var(--text)}
.bd-scope table.bd-table tr.bd-total td{font-weight:700;border-top:1.5px solid var(--primary)}
.bd-scope .bd-neg{color:var(--danger)}.bd-scope .bd-pos{color:var(--success)}
.bd-scope svg{display:block;max-width:100%}
@media(max-width:1100px){.bd-scope .bd-grid1{grid-template-columns:repeat(2,minmax(0,1fr))}.bd-scope .bd-c{grid-column:span 1}.bd-scope .bd-c2{grid-column:span 2}.bd-scope .bd-kpis1{grid-template-columns:repeat(2,minmax(0,1fr))}.bd-scope .bd-insights{grid-template-columns:1fr}}
@media(max-width:650px){.bd-scope .bd-grid1{grid-template-columns:1fr}.bd-scope .bd-c,.bd-scope .bd-c2{grid-column:1}.bd-scope .bd-k{min-height:126px;padding:10px}.bd-scope .bd-sec-d{display:none}.bd-scope .bd-sec h3{font-size:17px}.bd-scope .bd-legend{display:none}.bd-scope .bd-cbody{padding:0 10px}.bd-scope .bd-ct{padding-inline:9px}.bd-scope .bd-mrow,.bd-scope .bd-mrow.has-values{grid-template-columns:64px 1fr 46px;gap:6px}.bd-scope .bd-mv{display:none}}
/* 驾驶舱深色主题：覆盖单页综合看板的浅色底与描边 */
.bd-scope.bd-dark { --primary:#3b9bff;--primary-deep:#9fd8ff;--primary-mid:#36dcf0;--tint-bg:rgba(22,48,86,.55);--tint-line:rgba(88,142,208,.32);--danger:#ff5c69;--success:#20c98f;--warning:#ffc83d;--magenta:#a57bff;--text:#e8f0fb;--text-sub:#b3c3d8;--text-muted:#7f96b4; --series-1:#3a8ee6;--series-2:#1ea16f;--series-3:#c67d20;--series-4:#8f74e8;--series-5:#5b7ba3;--series-6:#8fa6c4; color:var(--text); }
.bd-scope.bd-dark .bd-k{background:linear-gradient(180deg,rgba(22,48,86,.55),rgba(12,30,60,.55));border-color:rgba(72,130,200,.35);border-left-color:var(--metric-accent);box-shadow:inset 0 1px 0 rgba(120,180,255,.12)}
.bd-scope.bd-dark .bd-k:not(.bd-k-featured) .bd-k-v{color:#36dcf0;text-shadow:0 0 12px rgba(54,220,240,.35)}
.bd-scope.bd-dark .bd-k-featured{background:linear-gradient(90deg,rgba(20,150,210,.55),rgba(12,96,160,.45));border-color:rgba(64,200,255,.6);box-shadow:0 0 16px rgba(30,170,255,.3),inset 0 0 14px rgba(120,220,255,.2);color:#e8f0fb}
.bd-scope.bd-dark .bd-k-featured .bd-k-ic{background:rgba(255,255,255,.14)!important}
.bd-scope.bd-dark .bd-k-ic{background:rgba(59,155,255,.16)!important}
.bd-scope.bd-dark .bd-sec-no,.bd-scope.bd-dark .bd-sec-icon{background:rgba(22,48,86,.55);border-color:rgba(72,130,200,.35);color:#36dcf0}
.bd-scope.bd-dark .bd-sec h3{color:#f3f8ff}
.bd-scope.bd-dark .bd-ins{background:linear-gradient(180deg,rgba(70,50,20,.35),rgba(40,28,20,.35));border-color:rgba(255,200,61,.3)}
.bd-scope.bd-dark .bd-ins-no{background:rgba(255,200,61,.14);border-color:rgba(255,200,61,.4)}
.bd-scope.bd-dark .bd-ins b{color:#ffe9a8}
.bd-scope.bd-dark .bd-c{background:linear-gradient(180deg,rgba(38,86,150,.22),rgba(10,26,54,0) 90px),linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92));border-color:rgba(74,138,214,.38);box-shadow:inset 0 1px 0 rgba(120,180,255,.18),inset 0 0 24px rgba(40,110,200,.12),0 4px 18px rgba(0,0,0,.35)}
.bd-scope.bd-dark .bd-ct{background:transparent;border-bottom:1px solid rgba(88,142,208,.25);color:#f3f8ff;font-size:14px}
.bd-scope.bd-dark .bd-ct-title::before{content:'';display:inline-block;width:3px;height:14px;margin-right:9px;vertical-align:-2px;border-radius:2px;background:linear-gradient(180deg,#36dcf0,#3b9bff);box-shadow:0 0 8px rgba(54,220,240,.6)}
.bd-scope.bd-dark .bd-ct .bd-legend{color:#b3c3d8}
.bd-scope.bd-dark .bd-src{color:#9ff0ff;background:rgba(54,220,240,.14)}
.bd-scope.bd-dark .bd-clk:hover{border-color:#36dcf0;box-shadow:0 0 14px rgba(54,220,240,.35)}
.bd-scope.bd-dark table.bd-table th{background:rgba(22,48,86,.55);color:#b3c3d8}
.bd-scope.bd-dark table.bd-table tr.bd-total td{border-top-color:#3b9bff}
.bd-scope.bd-dark .bd-mt,.bd-scope.bd-dark .bd-track{background:rgba(58,92,140,.35)}
.bd-scope.bd-dark .bd-mp{color:#e8f0fb}
/* 连续多图看板：并排阅读，不按主题拆页。 */
.br-workspace .br-section{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;scroll-margin-top:64px}
.br-workspace .br-kpis{grid-template-columns:repeat(6,minmax(0,1fr))}
.br-workspace .br-kpi{padding:12px}.br-workspace .br-kpi>strong{font-size:26px}
.br-workspace .br-chart-card{display:block;min-width:0;overflow:hidden}
.br-workspace .br-chart-card>header{font-size:16px;padding:13px 14px}
.br-workspace .br-chart-legend{font-size:13px;gap:8px;padding:8px 12px}
.br-workspace .br-note{font-size:12px;line-height:1.6;margin:10px 14px}
.br-workspace .br-plot-row{grid-template-columns:minmax(65px,25%) minmax(0,1fr);gap:8px;padding:6px 0}
.br-workspace .br-series-row{grid-template-columns:minmax(0,1fr) 76px;min-height:21px}
.br-workspace .br-series-row b,.br-workspace .br-plot-name{font-size:13px}
.br-workspace .br-donut p,.br-workspace .br-donut p b{font-size:13px}
.br-workspace .br-heat{overflow-x:auto}
.br-workspace .br-heat-head,.br-workspace .br-heat-row{min-width:0;grid-template-columns:minmax(65px,1fr) repeat(var(--heat-cols),minmax(0,1fr));font-size:12px;overflow-wrap:anywhere}
.br-preview-note{font-size:12px;color:var(--text-sub);margin:10px 0 0}
.br-workspace .br-conclusions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.br-workspace .br-conclusions p{margin:0;font-size:13px}
@media(max-width:1500px){.br-workspace .br-section{grid-template-columns:repeat(2,minmax(0,1fr))}.br-workspace .br-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:900px){.br-workspace .br-section,.br-workspace .br-conclusions{grid-template-columns:minmax(0,1fr)}.br-workspace .br-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:500px){.br-workspace .br-kpis{grid-template-columns:minmax(0,1fr)}}
.br-workspace .br-columns,.br-modal-content .br-columns{gap:clamp(10px,.8vw,16px);justify-content:center;overflow:hidden;padding:44px 12px 16px}
.br-workspace .br-columns .br-plot-row,.br-modal-content .br-columns .br-plot-row{flex:0 1 130px;min-width:0;gap:10px;padding:0;border:0}
.br-workspace .br-columns .br-col-group,.br-modal-content .br-columns .br-col-group{gap:4px}
.br-workspace .br-columns .br-plot-name,.br-modal-content .br-columns .br-plot-name{line-height:1.6;min-height:42px}
.br-workspace .br-columns .br-col,.br-modal-content .br-columns .br-col{flex:0 1 24px;min-width:0;max-width:24px}
.business-analysis.bi-dashboard .br-workspace .br-chart-card[data-visuals="2"],.business-analysis.bi-dashboard .br-workspace .br-chart-card[data-visuals="3"],.br-modal-content .br-enlarged-chart{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:20px}
.business-analysis.bi-dashboard .br-chart-card .br-visual-unit::before{display:none!important}
.business-analysis.bi-dashboard .br-workspace .br-plot-bars:not(.br-columns) .br-plot-row,.br-modal-content .br-plot-bars:not(.br-columns) .br-plot-row{display:block;padding:12px 0}
.business-analysis.bi-dashboard .br-workspace .br-plot-bars:not(.br-columns) .br-plot-name,.br-modal-content .br-plot-bars:not(.br-columns) .br-plot-name{display:block;margin-bottom:8px;font-size:13px;line-height:1.6}
.business-analysis.bi-dashboard .br-workspace .br-plot-bars:not(.br-columns) .br-series-row,.br-modal-content .br-plot-bars:not(.br-columns) .br-series-row{display:grid;grid-template-columns:minmax(0,1fr) 88px;gap:12px;min-height:25px}
.business-analysis.bi-dashboard .br-workspace .br-heat,.br-modal-content .br-heat{overflow:visible}
.business-analysis.bi-dashboard .br-workspace .br-heat-head,.business-analysis.bi-dashboard .br-workspace .br-heat-row,.br-modal-content .br-heat-head,.br-modal-content .br-heat-row{min-width:0;grid-template-columns:minmax(0,1.4fr) repeat(var(--heat-cols),minmax(0,1fr))}
.business-analysis.bi-dashboard .br-workspace .br-heat span,.br-modal-content .br-heat span{overflow-wrap:anywhere}
</style>
<style lang="scss" src="./businessDashboard.scss"></style>
<style>
.ba-layout-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.ba-layout-toolbar span{font-size:12px;color:#6884a3}
.chart-layout-tools{display:flex;flex-wrap:wrap;gap:6px;padding:8px;border:1px dashed #4596ff;border-radius:8px;margin-bottom:10px;grid-column:1/-1}
.chart-layout-tools button{background:#edf5ff;color:#245f9d;border:1px solid #bdd6f2;border-radius:5px;padding:5px 8px;cursor:pointer;font-size:12px}
.chart-layout-tools button[draggable]{cursor:grab}
.chart-layout-stack{display:flex!important;flex-direction:column;align-items:stretch}
.br-region-overview{padding:14px;margin:0 0 16px;border:1px solid var(--tint-line,#dbe7f4);border-left:4px solid var(--primary,#4596ff);border-radius:10px}
.br-region-overview>h4{font-size:16px;margin:0 0 12px}
.business-analysis .chart-layout-flow{display:flex!important;flex-flow:row wrap!important;align-items:flex-start;justify-content:flex-start;gap:12px}
.chart-layout-stack>template{display:none}
.layout-editing [data-layout-id]{outline:1px dashed #9cbfe3;outline-offset:2px}
.layout-editing [data-layout-id]>.chart-layout-tools{position:absolute;z-index:2;background:rgba(237,245,255,.95)}
.business-analysis [data-layout-id]{overflow:visible!important}
.chart-layout-resize{position:absolute;right:0;bottom:0;width:28px;height:28px;cursor:nwse-resize;touch-action:none;border:1px solid #4596ff;background:#edf5ff;color:#245f9d;border-radius:5px;z-index:2}
.chart-layout-tools{justify-content:flex-end;padding:2px 6px;min-height:26px;border:0;border-bottom:1px dashed #9cbfe3;cursor:move;touch-action:none}
.chart-layout-tools::before{content:'⠿';margin-right:auto;color:#6884a3}
.chart-layout-tools button:first-child{cursor:pointer}
.chart-layout-resize{border:0;background:transparent;border-radius:0}
.chart-layout-resize.edge-right{right:-4px;top:28px;bottom:12px;width:8px;height:auto;cursor:ew-resize}
.chart-layout-resize.edge-bottom{bottom:-4px;left:0;right:12px;height:8px;width:auto;cursor:ns-resize}
.chart-layout-resize.edge-corner{right:-3px;bottom:-3px;width:14px;height:14px;border-right:2px solid #4596ff;border-bottom:2px solid #4596ff}
.chart-layout-guide{position:fixed;pointer-events:none;z-index:99999;background:#ec4899}
.chart-layout-guide.vertical{top:0;bottom:0;width:1px}
.chart-layout-guide.horizontal{left:0;right:0;height:1px}
.layout-editing .br-chart-card{cursor:default}
@media(max-width:800px){.business-analysis .br-chart-card[style]{grid-column:1/-1!important}}
</style>
