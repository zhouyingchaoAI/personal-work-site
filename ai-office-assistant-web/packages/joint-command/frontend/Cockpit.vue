<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount, onDeactivated, nextTick, defineAsyncComponent } from 'vue'
import type { CrmOverview, CrmUnit, CrmPerson, CrmRelation, CrmPlaybook, CrmStaff, CrmManagerView } from '../../../src/services/personalWorkApi'
import NetworkExplorer from './NetworkExplorer.vue'
import FollowupDialog from './FollowupDialog.vue'
import RegionMap from './dashboard/RegionMap.vue'
import RegionInspector from './dashboard/RegionInspector.vue'
import MapSupport from './dashboard/MapSupport.vue'
import './dashboard/dashboard-theme.scss'
import CommandSummary from './CommandSummary.vue'
import CommandOverviewScreen from './command/CommandOverviewScreen.vue'
import CommandRegionCard from './command/CommandRegionCard.vue'
import { regionTheme, isCustomerUnit } from './command/commandOverview'
import { img as commandImg } from './command/img'
import { bizIcon as ic } from './businessIcons'
import { useCanvasScale } from './command/useCanvasScale'
import type { BusinessAnalysisData, CrmOpportunity } from '../../../src/services/personalWorkApi'
const section = ref('overview')
const RelationshipAssessment = defineAsyncComponent(() => import('./RelationshipAssessment.vue'))
const assessmentOpen = ref(false)
const sections = [{ value:'dashboard', label:'经营分析', icon:'nav-analysis' }, { value:'integration', label:'五位一体', icon:'nav-five' }, { value:'opportunities', label:'商机管理', icon:'nav-biz' }, { value:'battle', label:'项目作战地图', icon:'nav-map' }]
function changeSection(value: string) { section.value = value; networkExpanded.value = false; inspectorOpen.value = false; followupOpen.value = false; assessmentOpen.value = false }
// 总体信息按 1754 × 897 设计稿画布等比缩放；窄屏改为纵向流式布局。
const viewport = ref<HTMLElement | null>(null)
const narrowQuery = typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia('(max-width: 700px)') : null
const narrow = ref(!!narrowQuery?.matches)
const syncNarrow = () => { narrow.value = !!narrowQuery?.matches }
onMounted(() => narrowQuery?.addEventListener('change', syncNarrow))
onBeforeUnmount(() => narrowQuery?.removeEventListener('change', syncNarrow))
const canvasMode = computed(() => section.value === 'overview' && !narrow.value)
const { style: canvasStyle, frameStyle: canvasFrameStyle } = useCanvasScale(viewport, 1571, 792, canvasMode)
const networkType = ref('')
function openNetwork(type: string) { networkType.value = type; networkExpanded.value = true }
function openRegion(name: string) { changeSection('integration'); emit('region', name) }
type CockpitMode = 'manager' | 'regional' | 'joint'
type Tab = 'archive' | 'overview' | 'workflow' | 'battle' | 'relation'
type FullScreenTab = 'cockpit' | 'customers' | 'relation' | 'opportunities' | 'battle' | 'security'
const props = defineProps<{ business?: BusinessAnalysisData | null; opportunities?: CrmOpportunity[]; summaryPeople?: CrmPerson[]; summaryRelations?: CrmRelation[]; summaryFollowups?: CrmPlaybook['followups']; organizationUnits?: CrmUnit[]; managerSelectionRegion?: string; managerSelectionRegions?: string[]; managerOptions?: (CrmManagerView & { count: number })[]; managerId?: string; managerLabel?: string; canReviewManagers?: boolean; canExport?: boolean; canManage?: boolean; fullScreen?: boolean; organizationGraph?: CrmOverview['graph']; staff?: CrmStaff[]; responsibility?: string; mode: CockpitMode; modes: { value: CockpitMode; label: string; description: string }[]; overview: CrmOverview; units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; playbook: CrmPlaybook | null; canWrite: boolean; region?: string; regions: { name: string; units: number; people: number; warnings: number; followups: number }[] }>()
const emit = defineEmits<{ opportunity: [item: CrmOpportunity, battle: boolean]; managerRegion: [region: string]; manager: [username: string]; showcase: []; fullscreen: [value: boolean]; department: [value: string]; region: [value: string]; mode: [value: CockpitMode]; navigate: [tab: Tab | FullScreenTab]; create: []; refresh: []; select: [id: string, kind: string]; search: [query: string]; export: [] }>()
const expanded = ref(false)
const deck = ref<HTMLElement | null>(null)
const overviewHeight = ref('calc(100dvh - 260px)')
function fitOverview() {
 if (!deck.value || expanded.value) return
 overviewHeight.value = `${Math.max(340, window.innerHeight - Math.max(0, deck.value.getBoundingClientRect().top) - 16)}px`
}
onMounted(() => { nextTick(fitOverview); window.addEventListener('resize', fitOverview) })
onBeforeUnmount(() => window.removeEventListener('resize', fitOverview))
watch([section, expanded], () => nextTick(fitOverview))
const networkExpanded = ref(false)
const inspectorOpen = ref(false)
const followupOpen = ref(false), followupRelation = ref('')
function openFollowups(id = '') { followupRelation.value = id; followupOpen.value = true }
const query = ref('')
const activeType = ref('')
const mapRevision = ref(0)
watch(() => props.fullScreen, value => { if (value !== undefined) expanded.value = value }, { immediate: true })
watch(expanded, value => { if (props.fullScreen !== undefined && props.fullScreen !== value) emit('fullscreen', value) })
watch(() => [props.mode, props.managerId, props.managerSelectionRegion], () => { activeType.value = ''; mapRevision.value++; followupOpen.value = false; inspectorOpen.value = false; networkExpanded.value = false; assessmentOpen.value = false })
const managerIndex = computed(() => (props.managerOptions || []).findIndex(m => m.username === props.managerId))
function stepManager(step: number) {
 const target = props.managerOptions?.[managerIndex.value + step]
 if (target) emit('manager', target.username)
}
function resetScope() { activeType.value = ''; mapRevision.value++; emit('region', '') }
const currentMode = computed(() => props.modes.find(item => item.value === props.mode))
const scope = computed(() => `${props.mode === 'manager' ? (props.managerLabel || '本人') + ' · ' : ''}${props.region || '全部区域'}`)
const scopedUnits = computed(() => props.units.filter(u => (!activeType.value || u.type === activeType.value) && (!props.region || (u.business_regions?.length ? u.business_regions : [u.business_region]).includes(props.region))))
const unitIds = computed(() => new Set(scopedUnits.value.map(u => u.id)))
const scopedPeople = computed(() => props.people.filter(p => unitIds.value.has(p.unit_id)))
const personIds = computed(() => new Set(scopedPeople.value.map(p => p.id)))
const scopedRelations = computed(() => props.relations.filter(r => personIds.value.has(r.person_id)))
const relationIds = computed(() => new Set(scopedRelations.value.map(r => r.id)))
const followups = computed(() => (props.playbook?.followups || []).filter(a => relationIds.value.has(a.relation_id)).sort((a,b) => Number(b.overdue) - Number(a.overdue) || (a.due_date || '9999').localeCompare(b.due_date || '9999')))
const warnings = computed(() => scopedRelations.value.filter(r => r.decay_state !== 'normal'))
const operatingUnits = computed(() => scopedUnits.value.filter(isCustomerUnit))
// 关系健康摘要：L3+（可信任及以上）、预警/告警、单点风险，随区域与类型筛选联动。
const relationHealth = computed(() => ({
 strong: scopedRelations.value.filter(r => Number(r.strength || 0) >= 3).length,
 warning: scopedRelations.value.filter(r => r.decay_state === 'warning').length,
 alarm: scopedRelations.value.filter(r => r.decay_state === 'alarm').length,
 single: scopedRelations.value.filter(r => r.single_point_risk).length,
}))
function toggleType(value: string) { activeType.value = activeType.value === value ? '' : value }
const allRegionStats = computed(() => {
 const peopleIds = new Set(props.people.map(p => p.id))
 const relations = props.relations.filter(r => peopleIds.has(r.person_id))
 const ids = new Set(relations.map(r => r.id))
 return {
  units: new Set(props.units.filter(isCustomerUnit).map(u => u.id)).size,
  people: peopleIds.size,
  warnings: new Set(relations.filter(r => r.decay_state !== 'normal').map(r => r.id)).size,
  followups: (props.playbook?.followups || []).filter(f => ids.has(f.relation_id)).length,
 }
})
const colors: Record<string,string> = {主管单位:'#9a8cff',业主单位:'#f5c242',总包单位:'#23e0d0',设计单位:'#4596ff',厂商:'#f97316',我方:'#f5c242'}
// 客户概况按区域统计但不按类型过滤：选中类型时各行仍显示真实数字，仅高亮当前类型。
const regionUnits = computed(() => props.units.filter(u => !props.region || (u.business_regions?.length ? u.business_regions : [u.business_region]).includes(props.region)))
const groups = computed(() => {
 const typeByUnit = new Map(regionUnits.value.map(u => [u.id, u.type]))
 const peopleByType = new Map<string, number>()
 for (const p of props.people) { const t = typeByUnit.get(p.unit_id); if (t) peopleByType.set(t, (peopleByType.get(t) || 0) + 1) }
 return Object.entries(colors).filter(([t]) => t !== '我方').map(([type,color]) => ({type,color,units:regionUnits.value.filter(u => u.type === type && (!u.organization_level || u.organization_level === 'unit')).length,people:peopleByType.get(type) || 0}))
})
const groupTotal = computed(() => regionUnits.value.filter(isCustomerUnit).length)
function navigate(tab: Tab) {
 if (tab === 'archive') { inspectorOpen.value = true; return }
 if (tab === 'overview') { networkExpanded.value = true; return }
 if (tab === 'workflow') { openFollowups(); return }
 expanded.value = false; emit('navigate', tab)
}
function navigateFromFullscreen(tab: FullScreenTab) { expanded.value = false; emit('navigate', tab) }
function selectNode(id: string, kind: string) { networkExpanded.value = false; expanded.value = false; emit('select', id, kind) }
function search() { if (query.value.trim()) { expanded.value = false; emit('search', query.value.trim()) } }
function escape(event: KeyboardEvent) {
 if (event.key !== 'Escape') return
 if (assessmentOpen.value || (event.target instanceof HTMLElement && event.target.closest('.cockpit-assessment-dialog'))) { assessmentOpen.value = false; return }
 if (followupOpen.value) { followupOpen.value = false; return }
 if (inspectorOpen.value) inspectorOpen.value = false
 else if (networkExpanded.value) networkExpanded.value = false
 else expanded.value = false
}
onMounted(() => window.addEventListener('keydown', escape))
onBeforeUnmount(() => window.removeEventListener('keydown', escape))
onDeactivated(() => { expanded.value = false; networkExpanded.value = false; inspectorOpen.value = false; followupOpen.value = false; assessmentOpen.value = false })
watch(networkExpanded, value => { if (!value) networkType.value = '' })
</script>

<style scoped>
/* Full-canvas map with bounded, click-through floating panels. */
@media(min-width:701px){
 .map-cockpit .integration-map-layout :deep(.region-map__body){display:block;position:relative;min-height:0;isolation:isolate}
 .map-cockpit .command-content .integration-map-layout :deep(.region-map__stage){position:absolute;inset:0;width:100%;height:100%;min-height:0;box-sizing:border-box;z-index:0;border-radius:10px;overflow:hidden}
 .map-cockpit .command-content .integration-map-layout :deep(.region-map__left){position:absolute;inset:12px auto auto 12px;width:clamp(165px,15vw,240px);height:auto;max-height:calc(100% - 24px);min-height:0;z-index:2;pointer-events:none;box-sizing:border-box;overflow:auto}
 .map-cockpit .command-content .integration-map-layout :deep(.region-map__side){position:absolute;inset:12px 12px 12px auto;width:clamp(220px,22vw,310px);height:calc(100% - 24px);min-height:0;z-index:2;pointer-events:none;box-sizing:border-box}
 .map-cockpit .integration-map-layout :deep(.region-map__left>*),.map-cockpit .integration-map-layout :deep(.region-map__side>header),.map-cockpit .integration-map-layout :deep(.region-map__card),.map-cockpit .integration-map-layout :deep(.region-map__support>*){pointer-events:auto}
 .map-cockpit .integration-map-layout :deep(.region-map__side){display:flex;flex-direction:column;gap:8px;overflow:hidden}
 .map-cockpit .integration-map-layout :deep(.region-map__side>header),.map-cockpit .integration-map-layout :deep(.region-map__side .region-map__card){display:none}
 .map-cockpit .integration-map-layout :deep(.region-map__support){flex:1}
 .map-cockpit .integration-map-layout :deep(.region-map__side>header),.map-cockpit .integration-map-layout :deep(.region-map__support){grid-column:1/-1}
 .map-cockpit .integration-map-layout :deep(.region-map__support){margin:0;min-height:0;overflow:auto;pointer-events:none;backdrop-filter:none}
 .map-cockpit .integration-map-layout :deep(.region-map__hint){display:none}
 .map-cockpit .integration-map-layout :deep(.region-map__filters button){background:linear-gradient(180deg,rgba(22,48,86,.55),rgba(12,30,60,.55));border-color:rgba(72,130,200,.35);color:#c9d6e7}
 .map-cockpit .integration-map-layout :deep(.region-map__filters button.active){background:linear-gradient(90deg,rgba(20,150,210,.9),rgba(12,96,160,.75));border-color:rgba(64,200,255,.75);color:#fff;box-shadow:0 0 10px rgba(30,170,255,.35)}
 .map-cockpit .integration-map-layout :deep(.region-map__filter-scope){color:#b3c3d8}
 .map-cockpit .integration-map-layout :deep(.region-map__card){padding:9px 8px;gap:4px 6px;min-width:0;grid-template-areas:'dot name' 'nums nums';grid-template-columns:10px minmax(0,1fr);background:rgba(11,29,58,.88);border-color:rgba(74,138,214,.38);backdrop-filter:blur(6px);box-shadow:inset 0 1px 0 rgba(120,180,255,.18),0 4px 16px #020b1733}
 .map-cockpit .integration-map-layout :deep(.region-map__name){font-size:14px}
 .map-cockpit .integration-map-layout :deep(.region-map__nums){font-size:10px;white-space:nowrap}
 .map-cockpit .integration-map-layout :deep(.region-map__nums b){font-size:16px}
 .map-cockpit .integration-map-layout :deep(.region-map__warn){display:none}
 .map-cockpit .integration-map-layout :deep(.map-support){background:rgba(11,29,58,.88);border-color:rgba(74,138,214,.38);backdrop-filter:blur(6px);box-shadow:inset 0 1px 0 rgba(120,180,255,.18),0 4px 16px #020b1733;box-sizing:border-box}
 .map-cockpit .integration-map-layout :deep(.region-map__side>header){padding:6px 8px;background:rgba(11,29,58,.88);border:1px solid rgba(74,138,214,.38);border-radius:7px}
 .map-cockpit.cockpit-expanded:has(.integration-map-layout) .command-content{overflow:hidden;gap:8px}
 .map-cockpit.cockpit-expanded:has(.integration-map-layout) .command-breadcrumb{padding:3px 2px;flex:none}
 .map-cockpit.cockpit-expanded:has(.integration-map-layout) .map-cockpit__header h2{font-size:25px}
 .map-cockpit.cockpit-expanded .integration-map-layout{padding:12px;overflow:hidden}
 .map-cockpit.cockpit-expanded .integration-map-layout .map-cockpit__scope p{font-size:11px;margin-top:4px}
 .map-cockpit.cockpit-expanded .integration-map-layout .map-cockpit__stage{margin:10px 0 0;min-height:0}
 .map-cockpit.cockpit-expanded:has(.integration-map-layout) .map-cockpit__footer{gap:8px;padding:2px 0}
 .map-cockpit.cockpit-expanded:has(.integration-map-layout) .map-cockpit__tools button,.map-cockpit.cockpit-expanded:has(.integration-map-layout) select{font-size:12px;padding:7px 10px}
}
</style>

<template>
 <Teleport to="body" :disabled="!expanded">
  <section ref="deck" class="cockpit map-cockpit" :class="{ 'cockpit-expanded': expanded, 'business-bi-screen': section === 'dashboard', 'command-overview-screen': section === 'overview', 'command-canvas-mode': canvasMode }" :style="{ '--overview-height': overviewHeight, backgroundImage: `linear-gradient(180deg, rgba(2,10,28,.15) 0, rgba(2,10,28,.5) 230px, rgba(2,10,28,.72) var(--cockpit-shade-end, 100%)), url(${commandImg('bg')})` }">
   <header class="map-cockpit__header">
    <div class="map-cockpit__brand"><img class="map-cockpit__logo" :src="commandImg('logo')" alt="" /><div><h2>联合指挥驾驶舱</h2><p class="map-cockpit__subtitle">数据驱动决策 · 协同创造价值</p></div></div>
    <div class="map-cockpit__slogan" aria-hidden="true"><span>数据连接未来</span><span>让运营更高效</span></div>
    <div class="map-cockpit__tools">
     <button class="map-cockpit__refresh" @click="emit('refresh')"><svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M13.2 6.2A5.4 5.4 0 0 0 3.4 4.6M2.8 9.8a5.4 5.4 0 0 0 9.8 1.6" /><path d="M3.2 1.8v3h3M12.8 14.2v-3h-3" /></svg>刷新</button>
     <button :aria-pressed="expanded" @click="expanded = !expanded"><svg class="ic" viewBox="0 0 16 16" aria-hidden="true"><path d="M1.8 5.2V1.8h3.4M10.8 1.8h3.4v3.4M14.2 10.8v3.4h-3.4M5.2 14.2H1.8v-3.4" /><path v-if="expanded" d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4" /><rect v-else x="5.6" y="5.6" width="4.8" height="4.8" rx=".6" /></svg>{{ expanded ? '退出大屏' : '全屏作战大屏' }}</button>
    </div>
   </header>
   <div class="command-body">
   <nav class="command-navigation" aria-label="驾驶舱内部导航">
    <button :aria-current="section === 'overview' ? 'page' : undefined" @click="changeSection('overview')"><img :src="commandImg('nav-home')" alt="" /><span>总体信息</span></button><span class="command-divider">/</span><div><small>专题看板</small><button v-for="item in sections" :key="item.value" :aria-current="section === item.value ? 'page' : undefined" @click="changeSection(item.value)"><img :src="commandImg(item.icon)" alt="" /><span>{{ item.label }}</span></button></div>
    <button class="command-navigation__settings" @click="navigateFromFullscreen('security')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8Zm8.1 4.9-.1-3 2-1.6-2-3.5-2.4.8a8 8 0 0 0-2.6-1.5L14.5 2h-5L9 4.7a8 8 0 0 0-2.6 1.5L4 5.4 2 8.9l2 1.6a8 8 0 0 0 0 3L2 15.1l2 3.5 2.4-.8A8 8 0 0 0 9 19.3l.5 2.7h5l.5-2.7a8 8 0 0 0 2.6-1.5l2.4.8 2-3.5Z" /></svg><span>系统设置</span></button>
   </nav>
   <div class="command-content">
   <div class="command-breadcrumb">总体信息<span v-if="section !== 'overview'"> / {{ sections.find(item => item.value === section)?.label }}</span></div>
   <div v-if="section === 'overview'" ref="viewport" class="command-viewport">
   <div class="command-canvas-frame" :style="canvasFrameStyle">
   <div class="command-canvas" :class="{ 'is-flow': narrow }" :style="canvasStyle">
   <CommandOverviewScreen :flow="narrow" :business="business || null" :units="organizationUnits || units" :people="summaryPeople || people" :relations="summaryRelations || relations" :opportunities="opportunities || []" :followups="summaryFollowups || playbook?.followups || []" @section="changeSection" @region="openRegion" @network="openNetwork" @opportunity="item => { expanded = false; emit('opportunity', item, true) }" />
   <footer class="command-canvas-footer" aria-hidden="true">
    <span class="left">联合指挥驾驶舱<i />DATA EMPOWERS OPERATION</span>
    <span class="line" />
    <span class="right">更高效 · 更智能 · 更有价值</span>
   </footer>
   </div>
   </div>
   </div>
   <CommandSummary v-if="section === 'opportunities' || section === 'battle'" :section="section" :regions="regions" :business="business || null" :units="organizationUnits || units" :people="summaryPeople || people" :relations="summaryRelations || relations" :opportunities="opportunities || []" :followups="summaryFollowups || playbook?.followups || []" @section="changeSection" @manage="navigateFromFullscreen(section === 'battle' ? 'battle' : 'opportunities')" @opportunity="item => { expanded = false; emit('opportunity', item, section === 'battle') }" @detail="item => { expanded = false; emit('opportunity', item, false) }" />
   <div v-if="section === 'dashboard'" class="command-business"><slot name="business" /></div>
   <template v-if="section === 'integration'">
   <section class="map-cockpit__map integration-map-layout" aria-label="区域经营主地图">
    <div class="map-cockpit__map-head">
     <div class="map-cockpit__modes" aria-label="驾驶舱形态">
      <button v-for="item in modes" :key="item.value" :class="{ selected: mode === item.value }" :aria-pressed="mode === item.value" @click="emit('mode',item.value)">{{ item.label.replace('形态','') }}</button>
     </div>
    <div class="map-cockpit__review-slot">
     <div v-if="mode === 'manager' && canReviewManagers" class="map-cockpit__review map-cockpit__tools">
      <select aria-label="人员所属区域" title="经理所属区域" :value="managerSelectionRegion || ''" @change="emit('managerRegion', ($event.target as HTMLSelectElement).value)"><option value="">全部四大区域</option><option v-for="area in managerSelectionRegions" :key="area" :value="area">{{ area }}</option></select>
      <select aria-label="查看客户经理" :title="managerLabel || '查看客户经理'" :disabled="!managerOptions?.length" :value="managerId || ''" @change="emit('manager', ($event.target as HTMLSelectElement).value)"><option v-if="!managerOptions?.length" value="">该区域暂无客户经理</option><option v-for="manager in managerOptions" :key="manager.username" :value="manager.username">{{ manager.name }} · {{ manager.member_keys[0] }} · {{ manager.count }} 位联系人</option></select>
      <button aria-label="上一位" title="上一位客户经理" :disabled="managerIndex <= 0" @click="stepManager(-1)">‹</button><span>{{ managerIndex < 0 ? '0 / 0' : `${managerIndex + 1} / ${managerOptions?.length}` }}</span><button aria-label="下一位" title="下一位客户经理" :disabled="!managerOptions?.length || managerIndex >= managerOptions.length - 1" @click="stepManager(1)">›</button>
     </div>
    </div>
     <div class="map-cockpit__tools"><button v-if="canExport" @click="emit('export')">导出关系表</button><select aria-label="地图区域" :value="region || ''" @change="emit('region', ($event.target as HTMLSelectElement).value)"><option value="">全部区域</option><option v-for="area in regions" :key="area.name" :value="area.name">{{ area.name }}</option></select><button @click="inspectorOpen = true">数据明细</button><button v-if="region" @click="emit('region','')">返回全部区域</button><button v-if="region || activeType" @click="resetScope">重置筛选</button></div>
    </div>
    <div class="map-cockpit__regions" aria-label="四大区域概览">
     <CommandRegionCard v-for="(area, i) in regions.slice(0, 4)" :key="area.name" :region="area" :index="i" :theme="regionTheme(area.name, i)" :class="{ 'is-selected': region === area.name }" @open="name => emit('region', region === name ? '' : name)" />
    </div>
    <div class="integration-summary" role="group" aria-label="全区统计" title="当前查看权限内全区去重统计，不随地图区域与单位类型筛选变化">
     <span class="integration-summary__label">{{ mode === 'manager' ? '个人全区' : '全区统计' }}</span>
     <span><i class="integration-summary__ic" v-html="ic('results')"></i>客户单位 <b>{{ allRegionStats.units }}</b></span><span><i class="integration-summary__ic" v-html="ic('target')"></i>联系人 <b>{{ allRegionStats.people }}</b></span><button class="integration-summary__link" title="点击查看关系网络中的待维系关系" @click="networkExpanded = true"><i class="integration-summary__ic warn" v-html="ic('flag')"></i>待维系 <b>{{ allRegionStats.warnings }}</b></button><button class="integration-summary__link" title="点击打开跟进清单" @click="openFollowups()"><i class="integration-summary__ic" v-html="ic('calendar')"></i>待跟进 <b>{{ allRegionStats.followups }}</b></button>
    </div>
    <div class="map-cockpit__stage"><RegionMap :key="`${mode}-${mapRevision}`" immersive :regions="regions" :units="units" :people="people" :relations="relations" :playbook="playbook" :selected="region" :type="activeType" @region="value => emit('region',value)" @type="value => activeType = value">
     <template #left>
      <MapSupport kind="customers" compact :scope="`${scope}${activeType ? ' · ' + activeType : ''}`" :groups="groups" :total="groupTotal" :followups="followups" :warnings="warnings.length" :active-type="activeType" :health="relationHealth" @navigate="navigate" @followup="openFollowups" @type="toggleType" />
     </template>
     <template #right>
      <MapSupport kind="tasks" compact :scope="`${scope}${activeType ? ' · ' + activeType : ''}`" :groups="groups" :total="operatingUnits.length" :followups="followups" :warnings="warnings.length" @navigate="navigate" @followup="openFollowups" />
     </template>
    </RegionMap></div>
    <footer class="map-cockpit__footer">
     <span>{{ mode === 'manager' ? `${managerLabel || '本人'}负责的客户与行动` : currentMode?.description }} · 跨区客户总数去重，区域卡可重复计入</span>
     <div class="map-cockpit__tools integration-actions"><button title="公司覆盖、个人维系、组织渗透" @click="assessmentOpen = true"><i v-html="ic('tree')"></i>三层关系</button><button @click="networkExpanded = true"><i v-html="ic('allocation')"></i>关系网络</button><button @click="navigate('battle')"><i v-html="ic('map')"></i>项目作战</button><form @submit.prevent="search"><input v-model="query" aria-label="搜索客户或联系人" placeholder="搜索客户或联系人" /><button :disabled="!query.trim()">搜索</button></form></div>
    </footer>
   </section>
   </template>
   </div>
   </div>
  </section>
 </Teleport>
 <Teleport to="body">
  <section v-if="networkExpanded" class="network-modal" role="dialog" aria-modal="true" aria-label="区域关系网络" @click.self="networkExpanded = false">
   <div class="network-modal-card"><header><h3>客户关系网络 · 区域与单位类型</h3><button @click="networkExpanded = false">关闭 ×</button></header><NetworkExplorer :key="networkType" :units="section === 'overview' ? (organizationUnits || units) : units" :people="section === 'overview' ? (summaryPeople || people) : people" :relations="section === 'overview' ? (summaryRelations || relations) : relations" :staff="staff || []" :initial-region="region" :initial-type="networkType || activeType" @select="selectNode" /></div>
  </section>
 </Teleport>
 <el-dialog v-model="assessmentOpen" title="三层关系评估" width="min(1440px, 96vw)" top="4vh" append-to-body destroy-on-close class="cockpit-assessment-dialog">
  <div class="cockpit-assessment-scope">{{ scope }} · {{ activeType || '全部单位类型' }}</div>
  <RelationshipAssessment v-if="assessmentOpen" :units="scopedUnits" :people="scopedPeople" :relations="scopedRelations" :can-manage="!!canManage" @refresh="emit('refresh')" @navigate="tab => { assessmentOpen = false; navigate(tab) }" />
 </el-dialog>
 <FollowupDialog command :organization-units="organizationUnits || units" v-if="followupOpen" :scope="`${scope}${activeType ? ' · ' + activeType : ''} `" :followups="followups" :relations="scopedRelations" :people="scopedPeople" :units="scopedUnits" :initial-relation="followupRelation" @close="followupOpen = false" @refresh="emit('refresh')" />
 <RegionInspector v-if="inspectorOpen" :scope="`${scope} · ${activeType || '全部单位类型'}`" :units="scopedUnits" :people="scopedPeople" :regions="region ? regions.filter(r => r.name === region) : regions" @close="inspectorOpen = false" />
</template>

<style scoped>
.cockpit-assessment-scope{color:#647d98;font-size:13px;margin-bottom:12px}
.integration-summary{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:6px 22px;flex:none;padding:6px 12px 0;color:#91afc8;font-size:13px;line-height:24px}
.integration-summary__ic{display:inline-grid;font-size:14px;color:#5f9fd0;margin-right:5px;vertical-align:-2px}
.integration-summary__ic.warn{color:#ffc46b}
.integration-summary__ic :deep(svg){width:1em;height:1em}
.integration-summary__link{border:0;background:none;padding:0;font:inherit;color:inherit;line-height:inherit;cursor:pointer;border-bottom:1px dashed rgba(120,170,220,.45)}
.integration-summary__link:hover{color:#d9e9fa;border-bottom-color:#53cfe0}
.integration-actions>button{display:inline-flex;align-items:center;gap:7px;padding:9px 16px!important;font-size:13.5px}
.integration-actions>button>i{display:inline-grid;font-size:16px;color:#7fd9ff}
.integration-actions>button>i :deep(svg){width:1em;height:1em}
.integration-summary>span{white-space:nowrap}
.integration-summary__label{color:#d9e9fa;font-weight:500}
.integration-summary b{margin-left:5px;color:#51c9ff;font-size:18px;font-weight:600;font-variant-numeric:tabular-nums}
:global(.cockpit-assessment-dialog .el-dialog__body){max-height:calc(92vh - 90px);overflow:auto;overscroll-behavior:contain}
.command-body{display:flex;gap:12px;flex:1;min-height:0;min-width:0;align-items:stretch}
.command-content{display:flex;flex-direction:column;flex:1;min-width:0;min-height:0}
.map-cockpit .command-body>.command-navigation{width:167px;flex:0 0 167px;box-sizing:border-box;display:flex;flex-direction:column;align-items:stretch;justify-content:flex-start;gap:6px;padding:16px 2px 12px;flex-wrap:nowrap;min-height:0;overflow:hidden;border-radius:8px;border:1px solid rgba(70,120,190,.22);background:linear-gradient(180deg,rgba(10,28,56,.72),rgba(6,18,40,.55));box-shadow:inset 0 1px 0 rgba(120,180,255,.1)}
.map-cockpit .command-body>.command-navigation>div{display:contents}
.map-cockpit .command-body>.command-navigation button{position:relative;width:100%;height:auto;flex:0 1 60px;min-height:36px;box-sizing:border-box;text-align:left;padding:0 0 0 20px;white-space:nowrap;line-height:1.3;font-size:14.5px;border-radius:6px}
.map-cockpit .command-body>.command-navigation button:not(.command-navigation__settings)::after{content:'';position:absolute;left:16px;right:16px;bottom:-4px;height:1px;background:linear-gradient(90deg,transparent,rgba(90,140,210,.3),transparent)}
.map-cockpit .command-body>.command-navigation small{display:none}
.map-cockpit .command-body>.command-navigation .command-divider{display:none}
.command-overview-screen .command-content{overflow:hidden}
.cockpit-expanded .command-content{overflow:auto}
.cockpit-expanded.command-overview-screen .command-content{overflow:hidden}
.cockpit-expanded .command-content>.command-summary,.cockpit-expanded .command-content>.command-business{flex:1;min-height:0}
@media(max-width:650px){
 .command-body{gap:5px}
 .map-cockpit .command-body>.command-navigation{width:64px;flex-basis:64px;padding:5px 3px;gap:5px}
 .map-cockpit .command-body>.command-navigation button{height:auto;font-size:11px;padding:8px 3px;text-align:center;white-space:normal;overflow-wrap:anywhere}
 .map-cockpit .command-body>.command-navigation button::after{display:none}
 .map-cockpit .command-body>.command-navigation small{display:none}
}
</style>

<style scoped lang="scss">
.command-navigation { display:flex; align-items:center; gap:18px; padding:12px; border-radius:12px; flex-wrap:wrap; }
.command-navigation>div { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.command-navigation button { border:1px solid transparent; border-radius:8px; background:transparent; padding:10px 18px; color:#aac3da; cursor:pointer; }
.command-navigation button[aria-current='page'] { color:#8dfff2; background:#104451; border-color:#40c8cc; }
.command-divider { color:#517591; }.command-breadcrumb { padding:14px 4px; color:#7f96b4; font-size:12px; letter-spacing:.5px; }.command-breadcrumb span { color:#36dcf0; }
.command-business { padding:0; border-radius:0; background:transparent; color:#e8f0fb; }
.cockpit-expanded .command-summary,.cockpit-expanded .command-business { flex:1; min-height:0; overflow:auto; }
.cockpit-expanded .command-navigation,.cockpit-expanded .command-breadcrumb { flex-shrink:0; }
@media(max-width:650px){.command-navigation {gap:8px}.command-navigation button{padding:9px 10px}.command-navigation>div{gap:5px}.command-divider{display:none}}
.map-cockpit { color:#d9e9fa; padding:22px; border-radius:14px; background-color:#041029; background-size:auto,cover; background-position:0 0,center top; background-repeat:no-repeat; min-width:0;
 h2,h3,p { margin:0; } h2 { font-size:24px; margin-top:5px; letter-spacing:1px; } h3 { font-size:16px; }
 button { font:inherit; cursor:pointer; color:inherit; } button:focus-visible,input:focus-visible { outline:2px solid #53e9e0; outline-offset:3px; }
 small { color:#91afc8; font-size:12px; }
}
.map-cockpit { --cockpit-shade-end:720px; background-size:auto,100% auto; }
.map-cockpit,.map-cockpit :deep(*) { scrollbar-width:thin; scrollbar-color:rgba(92,145,196,.45) transparent; }
.map-cockpit::-webkit-scrollbar,.map-cockpit :deep(*::-webkit-scrollbar) { width:6px; height:6px; }
.map-cockpit::-webkit-scrollbar-track,.map-cockpit :deep(*::-webkit-scrollbar-track) { background:transparent; }
.map-cockpit::-webkit-scrollbar-thumb,.map-cockpit :deep(*::-webkit-scrollbar-thumb) { background:rgba(92,145,196,.45); border-radius:8px; }
.map-cockpit::-webkit-scrollbar-thumb:hover,.map-cockpit :deep(*::-webkit-scrollbar-thumb:hover) { background:rgba(112,185,240,.75); }
.map-cockpit::-webkit-scrollbar-corner,.map-cockpit :deep(*::-webkit-scrollbar-corner) { background:transparent; }
.map-cockpit__header,.map-cockpit__map-head,.map-cockpit__panel>header,.map-cockpit__footer { display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap; }
.map-cockpit__header { margin-bottom:20px; }
.map-cockpit select { color:#eaf3ff;background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85));border:1px solid rgba(86,156,236,.55);border-radius:4px;padding:8px 10px;font:inherit;font-size:12px;max-width:100%;box-shadow:inset 0 0 12px rgba(60,140,240,.2); }
.map-cockpit__review { padding:10px 14px;margin-bottom:12px;border:1px solid rgba(74,138,214,.38);border-radius:9px;background:linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92));box-shadow:inset 0 1px 0 rgba(120,180,255,.18);font-size:12px;flex-shrink:0; }
.map-cockpit__review label { display:flex;align-items:center;gap:10px;min-width:0; }
.map-cockpit__review select { max-width:340px; }
.map-cockpit__review span { color:#6de6dd;min-width:45px;text-align:center; }
.map-cockpit button:disabled { opacity:.4;cursor:not-allowed; }
.map-cockpit__modes,.map-cockpit__tools { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.map-cockpit__modes { gap:0; padding:3px; border:1px solid rgba(74,138,214,.38); border-radius:6px; background:linear-gradient(180deg,rgba(10,28,56,.72),rgba(6,18,40,.55)); box-shadow:inset 0 1px 0 rgba(120,180,255,.1); }
.map-cockpit__modes button { border:1px solid transparent; border-radius:4px; background:transparent; padding:7px 14px; font-size:13px; color:#cbd8ea; transition:background .25s,color .25s; }
.map-cockpit__modes button:not(.selected):hover { background:rgba(40,110,200,.14); color:#fff; }
.map-cockpit__modes button.selected { color:#fff; font-weight:700; border-color:rgba(64,200,255,.75); background:linear-gradient(90deg,rgba(20,150,210,.9),rgba(12,96,160,.75) 60%,rgba(10,70,130,.6)); box-shadow:0 0 12px rgba(30,170,255,.4),inset 0 0 12px rgba(120,220,255,.3); }
.map-cockpit__map { border:1px solid rgba(74,138,214,.38); border-radius:9px; padding:20px; background:linear-gradient(180deg,rgba(38,86,150,.22),rgba(10,26,54,0) 90px),linear-gradient(180deg,rgba(11,29,58,.9),rgba(7,21,45,.92)); box-shadow:inset 0 1px 0 rgba(120,180,255,.18),inset 0 0 24px rgba(40,110,200,.12),0 4px 18px rgba(0,0,0,.35); }
.map-cockpit__scope h3 { display:flex; align-items:center; gap:10px; font-size:18px; font-weight:700; color:#f3f8ff; letter-spacing:.5px; }
.map-cockpit__scope h3::before { content:''; width:4px; height:18px; border-radius:2px; background:linear-gradient(180deg,#36dcf0,#3b9bff); box-shadow:0 0 8px rgba(54,220,240,.6); }
.map-cockpit__scope h3 small { font-size:13px; font-weight:400; color:#8ea6c6; }
.map-cockpit__map-head p { color:#8daec9; font-size:12px; margin-top:7px; }
.map-cockpit__stage { height:clamp(480px,62vh,820px); margin:16px 0; display:flex; min-width:0; }
.map-cockpit__regions { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin-top:14px; gap:12px; --cv-font-num:'DIN Alternate','Bahnschrift','Barlow','PingFang SC','Microsoft YaHei',sans-serif; }
.map-cockpit__regions :deep(.num) { font-family:var(--cv-font-num); font-variant-numeric:tabular-nums; }
.map-cockpit__regions :deep(.cv-region) { position:relative; top:auto; width:auto; height:117px; }
.map-cockpit__regions :deep(.cv-region.is-selected) { filter:brightness(1.22) drop-shadow(0 0 12px rgba(120,200,255,.4)); }
.map-cockpit__support { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
.map-cockpit__panel { min-width:0; padding:18px; border:1px solid #233e58; border-radius:10px; background:#0a2036; }
.map-cockpit__panel>header { margin-bottom:16px; } .map-cockpit__panel>header small { display:block; margin-top:5px; }
.map-cockpit__panel>header button,.map-cockpit__warning { background:none; border:0; color:#6edbd9; font-size:12px; padding:4px 0; }
.map-cockpit__tasks button { display:flex; align-items:center; justify-content:space-between; gap:12px; width:100%; border:0; border-bottom:1px solid #213c53; background:transparent; padding:12px 0; text-align:left; font-size:13px; }
.map-cockpit__tasks span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; } .map-cockpit__tasks small { flex-shrink:0; } .map-cockpit__tasks .overdue { color:#ffd078; }
.map-cockpit__warning { margin-top:12px; color:#ffd078; }
.map-cockpit__empty { color:#8daec9; font-size:13px; padding:24px 0; }
.map-cockpit__footer { margin-top:12px; padding-top:10px; border-top:1px solid transparent; border-image:linear-gradient(90deg,rgba(88,142,208,.08),rgba(88,142,208,.32) 20%,rgba(88,142,208,.32) 80%,rgba(88,142,208,.08)) 1; color:#829eb8; font-size:11px; } .map-cockpit__footer form { display:flex; border:1px solid rgba(86,156,236,.55); border-radius:4px; overflow:hidden; box-shadow:inset 0 0 12px rgba(60,140,240,.15); } .map-cockpit__footer input { color:#dfedfa; background:rgba(10,30,62,.85); border:0; padding:8px; width:160px; min-width:0; } .map-cockpit__footer form button { border:0; border-radius:0; }
.map-cockpit.cockpit-expanded { position:fixed; inset:0; z-index:1900; border-radius:0; overflow:auto; padding:24px 4vw; }
.map-cockpit.cockpit-expanded .map-cockpit__stage { height:clamp(480px,66vh,1000px); }
.network-modal { position:fixed; inset:0; z-index:2100; display:grid; place-items:center; padding:3vh 4vw; background:#020b17df; }
.network-modal-card { width:min(1400px,92vw); height:90dvh; display:flex; flex-direction:column; padding:16px; border:1px solid #3e8bad; border-radius:12px; background:#071a2d; color:#e1f6ff; }
.network-modal-card>header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; } .network-modal-card button { border:1px solid #3c7698; border-radius:6px; background:#123653; padding:7px 12px; color:#d6f6fb; cursor:pointer; }
.network-modal-card :deep(.rg-wrap) { flex:1; min-height:0; max-width:none; display:flex; flex-direction:column; } .network-modal-card :deep(.radial-org) { height:auto; min-height:0; flex:1; }
@media(max-width:1100px) { .map-cockpit__stage { height:auto; min-height:580px; } .map-cockpit__stage :deep(.region-map__stage) { min-height:360px; } .map-cockpit.cockpit-expanded .map-cockpit__stage { height:auto; } }
@media(max-width:650px) {
 .map-cockpit,.map-cockpit.cockpit-expanded { padding:12px; } .map-cockpit__map { padding:12px; } .map-cockpit__header { gap:12px; } .map-cockpit__header h2 { font-size:21px; }
 .map-cockpit__stage { min-height:0; } .map-cockpit__stage :deep(.region-map__stage) { min-height:260px; }
 .map-cockpit__support { grid-template-columns:1fr; } .map-cockpit__regions { gap:8px; grid-template-columns:repeat(2,minmax(0,1fr)); }
 .map-cockpit__modes { order:3; width:100%; } .map-cockpit__modes button { flex:1; padding:8px; }
 .map-cockpit__tasks button { align-items:flex-start; flex-direction:column; gap:5px; } .map-cockpit__tasks span { white-space:normal; }
}
</style>

<style scoped lang="scss">
/* ===== 总体信息：头部与侧栏是所有看板共用的固定外壳；内容区按 1571 × 792 设计画布等比缩放 ===== */
.map-cockpit { height:var(--overview-height); min-height:340px; box-sizing:border-box; display:flex; flex-direction:column; gap:12px; padding:22px; overflow:hidden; }
.map-cockpit.cockpit-expanded { height:100dvh; }
.map-cockpit .map-cockpit__header { margin:0; flex:none; }
.map-cockpit .command-content { overflow:auto; }
.map-cockpit .command-content>.command-summary,.map-cockpit .command-content>.command-business { flex:1; min-height:0; }
.map-cockpit .command-content>.command-summary { min-height:540px; }
.command-overview-screen .command-breadcrumb { display:none; }
.command-viewport { position:relative; flex:1; min-height:0; min-width:0; overflow:auto; }
.command-canvas-frame { position:relative; width:100%; overflow:hidden; }
.command-canvas { position:absolute; left:0; top:0; transform-origin:top left; overflow:visible; }
.command-canvas.is-flow { position:static; transform:none; }
.command-canvas-footer { position:absolute; left:0; right:17px; top:763px; height:20px; display:flex; align-items:center; gap:16px; pointer-events:none; }
.command-canvas.is-flow .command-canvas-footer { display:none; }
.command-canvas-footer .left { display:flex; align-items:center; font-size:11.5px; letter-spacing:1px; color:#5a7ca3; white-space:nowrap; }
.command-canvas-footer .left i { width:1px; height:11px; margin:0 12px; background:#3d5a80; }
.command-canvas-footer .line { flex:1; height:1px; margin-right:20px; background:linear-gradient(90deg,rgba(70,130,210,.55),rgba(70,130,210,.25) 70%,rgba(70,130,210,0)); }
.command-canvas-footer .right { font-size:12.5px; letter-spacing:1.5px; color:#5f90c4; word-spacing:4px; white-space:nowrap; }

/* 窄屏：不缩放，纵向流式 */
@media(max-width:700px) {
 .map-cockpit.command-overview-screen, .map-cockpit.command-overview-screen.cockpit-expanded { padding:8px; gap:5px; }
 .map-cockpit.command-overview-screen .command-content { overflow:auto; }
 .command-viewport { overflow:visible; flex:none; }
 .command-overview-screen .map-cockpit__header { gap:5px; }
 .command-overview-screen .map-cockpit__header h2 { font-size:18px; }
 .command-overview-screen .map-cockpit__tools button { padding:5px 7px; }
}
</style>

<style scoped lang="scss">
@media(min-width:701px) {
 .map-cockpit:not(.cockpit-expanded) .map-cockpit__stage {height:clamp(560px,68vh,760px);min-height:0;}
 .map-cockpit:not(.cockpit-expanded) .map-cockpit__stage:has(.region-map--fallback) {height:clamp(340px,calc(100dvh - 420px),640px);}
 .map-cockpit:not(.cockpit-expanded) :deep(.region-map__stage) {min-height:0;}
 .map-cockpit:not(.cockpit-expanded) :deep(.region-map:not(.region-map--fallback) .region-map__left) {width:clamp(170px,23%,230px);}
 .map-cockpit:not(.cockpit-expanded) :deep(.region-map:not(.region-map--fallback) .region-map__side) {width:clamp(185px,24%,240px);}
 .map-cockpit:not(.cockpit-expanded) :deep(.region-map__card) {grid-template-areas:'dot name' 'dot nums';padding:5px 9px;}
 .map-cockpit:not(.cockpit-expanded) :deep(.region-map__warn) {display:none;}
 .map-cockpit.cockpit-expanded {height:100dvh;box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;padding:16px 24px;gap:12px;}
 .cockpit-expanded .map-cockpit__header {flex-shrink:0;margin:0;}
 .cockpit-fullscreen-menu {display:flex;align-items:center;justify-content:center;gap:8px;flex:1;flex-wrap:wrap;}
 .cockpit-fullscreen-menu button {border:0;border-bottom:2px solid transparent;background:transparent;padding:7px 8px;color:#a7c5df;font-size:14px;white-space:nowrap;}
 .cockpit-fullscreen-menu button:hover,.cockpit-fullscreen-menu button.selected {color:#79f0e4;border-color:#50d6d7;background:#113a51;}
 .cockpit-expanded .map-cockpit__header h2 {font-size:clamp(26px,2vw,34px);}
 .cockpit-expanded .map-cockpit__modes button,.cockpit-expanded .map-cockpit__tools button,.cockpit-expanded .map-cockpit select {font-size:14px;padding:9px 14px;}
 .cockpit-expanded .map-cockpit__map {display:flex;flex-direction:column;flex:1;min-height:0;padding:14px 16px;}
 .cockpit-expanded .map-cockpit__map-head {flex-shrink:0;}
 .cockpit-expanded .map-cockpit__scope h3 {font-size:20px;}
 .cockpit-expanded .map-cockpit__scope p {font-size:14px;margin-top:8px;}
 .cockpit-expanded .map-cockpit__stage {height:0;min-height:0;flex:1;margin:12px 0;}
 .cockpit-expanded .map-cockpit__stage :deep(.region-map__stage) {min-height:0;}
 .cockpit-expanded .map-cockpit__metrics {flex-shrink:0;padding-bottom:10px;}
 .cockpit-expanded .map-cockpit__metrics button {font-size:15px;gap:16px;padding:7px;}
 .cockpit-expanded .map-cockpit__metrics strong {font-size:clamp(32px,2.5vw,44px);}
 .cockpit-expanded :deep(.region-map--immersive .region-map__left) {width:clamp(230px,20vw,330px);}
 .cockpit-expanded :deep(.region-map--immersive .region-map__side) {width:clamp(250px,21vw,360px);}
 .cockpit-expanded :deep(.region-map__card) {padding:11px 14px;gap:4px 11px;}
 .cockpit-expanded :deep(.region-map__name) {font-size:17px;}
 .cockpit-expanded :deep(.region-map__nums) {font-size:13px;}
 .cockpit-expanded :deep(.region-map__nums b) {font-size:19px;}
 .cockpit-expanded :deep(.region-map__warn),.cockpit-expanded :deep(.region-map__hint) {font-size:12px;}
 .cockpit-expanded .map-cockpit__footer {flex-shrink:0;margin:0;}
}
@media(max-height:820px) and (min-width:701px) {
 .map-cockpit.cockpit-expanded {padding:10px 16px;gap:8px;}
 .cockpit-expanded h2 {font-size:20px;margin:0;}
 .cockpit-expanded .map-cockpit__map-head p {font-size:11px;margin-top:3px;}
 .cockpit-expanded .map-cockpit__metrics strong {font-size:24px;}
 .cockpit-expanded .map-cockpit__tools button {padding:6px 10px;}
 .cockpit-expanded .map-cockpit__footer>span {font-size:10px;}
}
</style>

<style scoped lang="scss">
/* ===== 参考大屏视觉：头部品牌区、发光按钮、图标侧栏（各专题看板共用） ===== */
.map-cockpit .map-cockpit__header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; min-height:72px; }
.map-cockpit__brand { display:flex; align-items:center; gap:12px; position:relative; min-width:0; }
.map-cockpit__logo { height:56px; flex:none; filter:drop-shadow(0 0 8px rgba(40,140,255,.5)); }
.map-cockpit .map-cockpit__brand h2 { margin:0; font-size:30px; font-weight:800; letter-spacing:2px; line-height:1.25; background:linear-gradient(180deg,#ffffff 30%,#bcdcff); -webkit-background-clip:text; background-clip:text; color:transparent; filter:drop-shadow(0 2px 6px rgba(30,120,255,.45)); white-space:nowrap; }
.map-cockpit .map-cockpit__subtitle { margin:3px 0 0; font-size:14px; letter-spacing:1px; color:#b8cbe6; white-space:nowrap; }
.map-cockpit__header .map-cockpit__tools { margin-left:auto; gap:19px; }
.map-cockpit__header .map-cockpit__tools button { height:36px; min-width:95px; }
.map-cockpit .map-cockpit__tools button { height:34px; font-size:13px; padding:0 14px; }
.map-cockpit .map-cockpit__footer form button { height:auto; border:0; border-radius:0; box-shadow:none; }
.map-cockpit .map-cockpit__footer form button::before,.map-cockpit .map-cockpit__footer form button::after { display:none; }
.map-cockpit__slogan { display:none; flex-direction:column; font-family:'STXingkai','Xingkai SC','KaiTi','STKaiti','Long Cang',cursive; font-size:19px; line-height:25px; color:#d4e4f8; letter-spacing:1.5px; transform:rotate(-8deg); text-shadow:0 0 10px rgba(80,160,255,.55); opacity:.9; pointer-events:none; }
.map-cockpit__slogan span:last-child { padding-left:50px; }
@media(min-width:1300px) { .map-cockpit__slogan { display:flex; margin-left:auto; margin-right:24px; } .map-cockpit__header .map-cockpit__tools { margin-left:0; } }
.map-cockpit .map-cockpit__tools button { position:relative; display:inline-flex; align-items:center; justify-content:center; gap:8px; overflow:hidden; border-radius:4px; border:1px solid rgba(86,156,236,.55); background:linear-gradient(180deg,rgba(22,56,102,.8),rgba(10,30,62,.85)); box-shadow:inset 0 0 12px rgba(60,140,240,.2); color:#eaf3ff; font-weight:600; transition:transform .2s,color .2s,border-color .2s,background .25s,box-shadow .25s,text-shadow .25s; }
.map-cockpit .map-cockpit__tools button::before { content:''; position:absolute; top:0; bottom:0; left:-60%; width:50%; background:linear-gradient(100deg,transparent,rgba(140,230,255,.35),transparent); transform:skewX(-20deg); pointer-events:none; }
.map-cockpit .map-cockpit__tools button::after { content:''; position:absolute; left:50%; right:50%; bottom:0; height:2px; background:linear-gradient(90deg,transparent,#36dcf0,transparent); transition:left .3s,right .3s; }
.map-cockpit .map-cockpit__tools button:hover,.map-cockpit .map-cockpit__tools button:focus-visible { transform:translateY(-1px); color:#9ff0ff; text-shadow:0 0 8px rgba(54,220,240,.8); border-color:#36dcf0; background:linear-gradient(180deg,rgba(30,100,170,.9),rgba(12,52,102,.92)); box-shadow:inset 0 0 16px rgba(54,220,240,.35),0 0 14px rgba(54,220,240,.45),0 4px 12px rgba(0,0,0,.35); }
.map-cockpit .map-cockpit__tools button:hover::before { left:120%; transition:left .6s ease; }
.map-cockpit .map-cockpit__tools button:hover::after,.map-cockpit .map-cockpit__tools button:focus-visible::after { left:8%; right:8%; }
.map-cockpit .map-cockpit__tools button:active { transform:translateY(0) scale(.97); }
.map-cockpit .map-cockpit__tools .ic { width:15px; height:15px; fill:none; stroke:currentColor; stroke-width:1.5; stroke-linecap:round; stroke-linejoin:round; transition:transform .4s; }
.map-cockpit .map-cockpit__tools .map-cockpit__refresh:hover .ic { transform:rotate(180deg); }
.map-cockpit .map-cockpit__tools button:hover .ic { filter:drop-shadow(0 0 3px rgba(54,220,240,.9)); }

.map-cockpit .command-body>.command-navigation button { display:flex; align-items:center; gap:10px; color:#cbd8ea; transition:background .25s,color .25s; }
.map-cockpit .command-body>.command-navigation button img { width:22px; height:22px; flex:none; object-fit:contain; filter:grayscale(.55) brightness(1.25) opacity(.85); }
.map-cockpit .command-body>.command-navigation button:not([aria-current='page']):hover { background:rgba(40,110,200,.14); color:#fff; }
.map-cockpit .command-body>.command-navigation button[aria-current='page'] { color:#fff; font-weight:700; border:1px solid rgba(64,200,255,.75); background:linear-gradient(90deg,rgba(20,150,210,.9),rgba(12,96,160,.75) 60%,rgba(10,70,130,.6)); box-shadow:0 0 16px rgba(30,170,255,.45),inset 0 0 14px rgba(120,220,255,.35); }
.map-cockpit .command-body>.command-navigation button[aria-current='page'] img { filter:brightness(1.6) drop-shadow(0 0 4px rgba(160,240,255,.8)); }
.map-cockpit .command-body>.command-navigation .command-navigation__settings { margin-top:auto; color:#aac6ea; }
.map-cockpit .command-body>.command-navigation .command-navigation__settings svg { width:20px; height:20px; flex:none; fill:none; stroke:#aac6ea; stroke-width:1.6; stroke-linejoin:round; }
@media(max-width:650px) {
 .map-cockpit .command-body>.command-navigation button { justify-content:center; gap:4px; }
 .map-cockpit .command-body>.command-navigation button img,.map-cockpit .command-body>.command-navigation .command-navigation__settings svg { display:none; }
 .map-cockpit__logo { height:30px; }
 .map-cockpit .map-cockpit__brand h2 { font-size:19px; }
 .map-cockpit .map-cockpit__subtitle { display:none; }
}
/* The optional manager controls must never displace the navigation or map. */
.map-cockpit .integration-map-layout .map-cockpit__map-head { display:grid; grid-template-columns:auto minmax(0,1fr) auto; height:60px; min-height:60px; gap:16px; }
.integration-map-layout .map-cockpit__scope { min-width:0; }
.integration-map-layout .map-cockpit__scope h3 { min-width:0; flex-wrap:nowrap; }
.integration-map-layout .map-cockpit__scope h3::before { flex-shrink:0; }
.integration-map-layout .map-cockpit__scope h3>span,.integration-map-layout .map-cockpit__scope small { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
.integration-map-layout .map-cockpit__scope p { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.integration-map-layout .map-cockpit__modes { flex-wrap:nowrap; width:auto; order:initial; justify-self:center; }
.integration-map-layout .map-cockpit__modes button { white-space:nowrap; }
.integration-map-layout .map-cockpit__map-head>.map-cockpit__tools { justify-content:flex-end; align-content:center; flex-wrap:nowrap; min-height:44px; }
.map-cockpit__review-slot { height:60px; min-width:0; margin:0; overflow:hidden; }
.map-cockpit .map-cockpit__review-slot .map-cockpit__review { height:60px; box-sizing:border-box; margin:0; padding:4px 0; flex-wrap:nowrap; overflow-x:auto; overflow-y:hidden; scrollbar-width:thin; border:0; background:none; box-shadow:none; }
.map-cockpit__review-slot label,.map-cockpit__review-slot button,.map-cockpit__review-slot span { flex-shrink:0; white-space:nowrap; }
.map-cockpit__review-slot select { flex-shrink:0; }
.map-cockpit__review-slot select[aria-label='人员所属区域'] { width:130px; }
.map-cockpit__review-slot select[aria-label='查看客户经理'] { width:220px; text-overflow:ellipsis; }
.map-cockpit__review-slot small { white-space:nowrap; color:#8daec9; }
.map-cockpit__review-context { height:100%; display:flex; align-items:center; gap:12px; padding:0 12px; box-sizing:border-box; border-radius:8px; background:rgba(16,43,77,.3); font-size:12px; color:#8daec9; overflow:hidden; white-space:nowrap; }
.map-cockpit__review-context strong { color:#c4d9ec; font-weight:500; }
@media(max-width:1500px) {
 .map-cockpit .integration-map-layout .map-cockpit__map-head { grid-template-columns:auto minmax(0,1fr) auto; gap:10px; }
 .integration-map-layout .map-cockpit__map-head>.map-cockpit__tools { min-height:42px; flex-wrap:nowrap; overflow-x:auto; }
 .integration-map-layout .map-cockpit__map-head>.map-cockpit__tools>* { flex-shrink:0; }
}
@media(max-width:650px) {
 .map-cockpit .integration-map-layout .map-cockpit__map-head { grid-template-columns:minmax(0,1fr); grid-template-rows:42px 48px 42px; height:148px; gap:8px; }
 .map-cockpit__review-slot,.map-cockpit .map-cockpit__review-slot .map-cockpit__review { height:48px; }
 .integration-map-layout .map-cockpit__modes { width:100%; justify-self:stretch; }
 .map-cockpit__review-slot select[aria-label='查看客户经理'] { width:220px; }
}
</style>
