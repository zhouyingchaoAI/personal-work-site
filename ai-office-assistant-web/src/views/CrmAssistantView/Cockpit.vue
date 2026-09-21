<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount, onDeactivated } from 'vue'
import type { CrmOverview, CrmUnit, CrmPerson, CrmRelation, CrmPlaybook, CrmStaff, CrmManagerView } from '../../services/personalWorkApi'
import NetworkExplorer from './NetworkExplorer.vue'
import FollowupDialog from './FollowupDialog.vue'
import RegionMap from './dashboard/RegionMap.vue'
import RegionInspector from './dashboard/RegionInspector.vue'
import MapSupport from './dashboard/MapSupport.vue'
import './dashboard/dashboard-theme.scss'
type CockpitMode = 'manager' | 'regional' | 'joint'
type Tab = 'archive' | 'overview' | 'workflow' | 'battle' | 'relation'
type FullScreenTab = 'cockpit' | 'customers' | 'relation' | 'opportunities' | 'battle' | 'security'
const props = defineProps<{ organizationUnits?: CrmUnit[]; managerSelectionRegion?: string; managerSelectionRegions?: string[]; managerOptions?: (CrmManagerView & { count: number })[]; managerId?: string; managerLabel?: string; canReviewManagers?: boolean; canExport?: boolean; canManage?: boolean; fullScreen?: boolean; organizationGraph?: CrmOverview['graph']; staff?: CrmStaff[]; responsibility?: string; mode: CockpitMode; modes: { value: CockpitMode; label: string; description: string }[]; overview: CrmOverview; units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; playbook: CrmPlaybook | null; canWrite: boolean; region?: string; regions: { name: string; units: number; people: number; warnings: number; followups: number }[] }>()
const emit = defineEmits<{ managerRegion: [region: string]; manager: [username: string]; showcase: []; fullscreen: [value: boolean]; department: [value: string]; region: [value: string]; mode: [value: CockpitMode]; navigate: [tab: Tab | FullScreenTab]; create: []; refresh: []; select: [id: string, kind: string]; search: [query: string]; export: [] }>()
const expanded = ref(false)
const networkExpanded = ref(false)
const inspectorOpen = ref(false)
const followupOpen = ref(false), followupRelation = ref('')
function openFollowups(id = '') { followupRelation.value = id; followupOpen.value = true }
const query = ref('')
const activeType = ref('')
const mapRevision = ref(0)
const fullScreenMenu = computed(() => [
 { value: 'cockpit' as FullScreenTab, label: '经营驾驶舱' },
 { value: 'customers' as FullScreenTab, label: '客户关系' },
 { value: 'relation' as FullScreenTab, label: '关系维系' },
 { value: 'opportunities' as FullScreenTab, label: '机会点管理' },
 { value: 'battle' as FullScreenTab, label: '项目作战地图' },
 ...(props.canManage ? [{ value: 'security' as FullScreenTab, label: '安全权限' }] : []),
])
watch(() => props.fullScreen, value => { if (value !== undefined) expanded.value = value }, { immediate: true })
watch(expanded, value => { if (props.fullScreen !== undefined && props.fullScreen !== value) emit('fullscreen', value) })
watch(() => [props.mode, props.managerId, props.managerSelectionRegion], () => { activeType.value = ''; mapRevision.value++; followupOpen.value = false; inspectorOpen.value = false; networkExpanded.value = false })
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
const operatingUnits = computed(() => scopedUnits.value.filter(u => !u.organization_level || u.organization_level === 'unit'))
const colors: Record<string,string> = {主管单位:'#9a8cff',业主单位:'#f5c242',总包单位:'#23e0d0',设计单位:'#4596ff',厂商:'#f97316',我方:'#f5c242'}
const groups = computed(() => Object.entries(colors).filter(([t]) => t !== '我方').map(([type,color]) => { const ids = new Set(scopedUnits.value.filter(u => u.type === type).map(u => u.id)); return {type,color,units:operatingUnits.value.filter(u => u.type === type).length,people:scopedPeople.value.filter(p => ids.has(p.unit_id)).length} }))
const metrics = computed(() => [
 { label:'客户单位', value:operatingUnits.value.length, tab:'archive' as Tab },
 { label:'联系人', value:scopedPeople.value.length, tab:'archive' as Tab },
 { label:'待维系', value:warnings.value.length, tab:'overview' as Tab },
 { label:'待跟进', value:followups.value.length, tab:'workflow' as Tab },
])
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
 if (followupOpen.value) { followupOpen.value = false; return }
 if (inspectorOpen.value) inspectorOpen.value = false
 else if (networkExpanded.value) networkExpanded.value = false
 else expanded.value = false
}
onMounted(() => window.addEventListener('keydown', escape))
onBeforeUnmount(() => window.removeEventListener('keydown', escape))
onDeactivated(() => { expanded.value = false; networkExpanded.value = false; inspectorOpen.value = false; followupOpen.value = false })
</script>

<template>
 <Teleport to="body" :disabled="!expanded">
  <section class="cockpit map-cockpit" :class="{ 'cockpit-expanded': expanded }">
   <header class="map-cockpit__header">
    <div><small class="eyebrow">客户经营 · 区域视图</small><h2>经营驾驶舱</h2></div>
    <nav v-if="expanded" class="cockpit-fullscreen-menu" aria-label="全屏模式功能菜单"><button v-for="item in fullScreenMenu" :key="item.value" :class="{ selected: item.value === 'cockpit' }" @click="navigateFromFullscreen(item.value)">{{ item.label }}</button></nav>
    <div class="map-cockpit__modes" aria-label="驾驶舱形态">
     <button v-for="item in modes" :key="item.value" :class="{ selected: mode === item.value }" :aria-pressed="mode === item.value" @click="emit('mode',item.value)">{{ item.label.replace('形态','') }}</button>
    </div>
    <div class="map-cockpit__tools">
     <button v-if="canExport" @click="emit('export')">导出关系表</button>
     <button @click="emit('refresh')">刷新</button>
     <button :aria-pressed="expanded" @click="expanded = !expanded">{{ expanded ? '退出大屏' : '全屏作战大屏' }}</button>
    </div>
   </header>
   <div v-if="mode === 'manager' && canReviewManagers" class="map-cockpit__review map-cockpit__tools">
    <label>人员所属区域 <select aria-label="人员所属区域" :value="managerSelectionRegion || ''" @change="emit('managerRegion', ($event.target as HTMLSelectElement).value)"><option value="">全部区域人员</option><option v-for="area in managerSelectionRegions" :key="area" :value="area">{{ area }}</option><option value="__unassigned__">未分区人员</option></select></label>
    <label>查看客户经理 <select aria-label="查看客户经理" :value="managerId || ''" @change="emit('manager', ($event.target as HTMLSelectElement).value)"><option v-if="!managerSelectionRegion" value="">本人负责客户</option><option v-else-if="!managerOptions?.length" value="">该区域暂无对接人员</option><option v-for="manager in managerOptions" :key="manager.username" :value="manager.username">{{ manager.name }} · {{ manager.member_keys[0] }} · {{ manager.count }} 位联系人</option></select></label>
    <button :disabled="managerIndex <= 0" @click="stepManager(-1)">上一位</button><span>{{ managerIndex < 0 ? (managerSelectionRegion ? '暂无人员' : '本人') : `${managerIndex + 1} / ${managerOptions?.length}` }}</span><button :disabled="!managerOptions?.length || managerIndex >= managerOptions.length - 1" @click="stepManager(1)">下一位</button>
    <small>区域用于筛选客户对接人；选人后展示其全部关联客户，可再通过地图筛选客户区域</small>
   </div>
   <section class="map-cockpit__map" aria-label="区域经营主地图">
    <div class="map-cockpit__map-head">
     <div class="map-cockpit__scope" aria-live="polite"><h3>{{ scope }} <small> / {{ activeType || '全部单位类型' }}</small></h3><p>① 选查看对象　② 点区域聚焦　③ 筛单位类型　④ 打开明细或跟进</p></div>
     <div class="map-cockpit__tools"><select aria-label="地图区域" :value="region || ''" @change="emit('region', ($event.target as HTMLSelectElement).value)"><option value="">全部区域</option><option v-for="area in regions" :key="area.name" :value="area.name">{{ area.name }}</option></select><button @click="inspectorOpen = true">数据明细</button><button v-if="region" @click="emit('region','')">返回全部区域</button><button v-if="region || activeType" @click="resetScope">重置筛选</button></div>
    </div>
    <div class="map-cockpit__metrics" aria-label="当前区域摘要">
     <button v-for="item in metrics" :key="item.label" @click="item.tab === 'workflow' ? openFollowups() : navigate(item.tab)"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></button>
    </div>
    <div class="map-cockpit__stage"><RegionMap :key="`${mode}-${mapRevision}`" immersive :regions="regions" :units="units" :people="people" :relations="relations" :playbook="playbook" :selected="region" @region="value => emit('region',value)" @type="value => activeType = value">
     <template #left><MapSupport kind="customers" compact :scope="scope" :groups="groups" :total="operatingUnits.length" :followups="followups" :warnings="warnings.length" @navigate="navigate" @followup="openFollowups" /></template>
     <template #right><MapSupport kind="tasks" compact :scope="scope" :groups="groups" :total="operatingUnits.length" :followups="followups" :warnings="warnings.length" @navigate="navigate" @followup="openFollowups" /></template>
    </RegionMap></div>

   </section>
   <footer class="map-cockpit__footer">
    <span>{{ mode === 'manager' ? `${managerLabel || '本人'}负责的客户与行动` : currentMode?.description }} · 跨区客户总数去重，区域卡可重复计入</span>
    <div class="map-cockpit__tools"><button @click="networkExpanded = true">关系网络</button><button @click="navigate('battle')">项目作战</button><form @submit.prevent="search"><input v-model="query" aria-label="搜索客户或联系人" placeholder="搜索客户或联系人" /><button :disabled="!query.trim()">搜索</button></form></div>
   </footer>
  </section>
 </Teleport>
 <Teleport to="body">
  <section v-if="networkExpanded" class="network-modal" role="dialog" aria-modal="true" aria-label="区域关系网络" @click.self="networkExpanded = false">
   <div class="network-modal-card"><header><h3>客户关系网络 · 区域与单位类型</h3><button @click="networkExpanded = false">关闭 ×</button></header><NetworkExplorer :units="units" :people="people" :relations="relations" :staff="staff || []" :initial-region="region" :initial-type="activeType" @select="selectNode" /></div>
  </section>
 </Teleport>
 <FollowupDialog command :organization-units="organizationUnits || units" v-if="followupOpen" :scope="`${scope}${activeType ? ' · ' + activeType : ''} `" :followups="followups" :relations="scopedRelations" :people="scopedPeople" :units="scopedUnits" :initial-relation="followupRelation" @close="followupOpen = false" @refresh="emit('refresh')" />
 <RegionInspector v-if="inspectorOpen" :scope="`${scope} · ${activeType || '全部单位类型'}`" :units="scopedUnits" :people="scopedPeople" :regions="region ? regions.filter(r => r.name === region) : regions" @close="inspectorOpen = false" />
</template>

<style scoped lang="scss">
.map-cockpit { color:#d9e9fa; padding:22px; border-radius:14px; background:radial-gradient(ellipse at 55% 0,#14395d77,transparent 60%),#071529; min-width:0;
 h2,h3,p { margin:0; } h2 { font-size:24px; margin-top:5px; letter-spacing:1px; } h3 { font-size:16px; }
 button { font:inherit; cursor:pointer; color:inherit; } button:focus-visible,input:focus-visible { outline:2px solid #53e9e0; outline-offset:3px; }
 small { color:#91afc8; font-size:12px; } .eyebrow { color:#65d7d7; font-size:11px; }
}
.map-cockpit__header,.map-cockpit__map-head,.map-cockpit__panel>header,.map-cockpit__footer { display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap; }
.map-cockpit__header { margin-bottom:20px; }
.map-cockpit select { color:#e0f5ff;background:#102b44;border:1px solid #416783;border-radius:6px;padding:8px;font:inherit;max-width:100%; }
.map-cockpit__review { padding:10px 14px;margin-bottom:12px;border:1px solid #315575;border-radius:8px;background:#0e2b43;font-size:12px;flex-shrink:0; }
.map-cockpit__review label { display:flex;align-items:center;gap:10px;min-width:0; }
.map-cockpit__review select { max-width:340px; }
.map-cockpit__review span { color:#6de6dd;min-width:45px;text-align:center; }
.map-cockpit button:disabled { opacity:.4;cursor:not-allowed; }
.map-cockpit__modes,.map-cockpit__tools { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.map-cockpit__modes button,.map-cockpit__tools button { border:1px solid #315575; border-radius:7px; background:#0c2943; padding:8px 12px; font-size:12px; }
.map-cockpit__modes button.selected { border-color:#50d6d7; color:#a7ffef; background:#114354; }
.map-cockpit__map { border:1px solid #306181; border-radius:12px; padding:20px; background:linear-gradient(135deg,#0b2845cc,#081b30); }
.map-cockpit__map-head p { color:#8daec9; font-size:12px; margin-top:7px; }
.map-cockpit__stage { height:clamp(480px,62vh,820px); margin:16px 0; display:flex; min-width:0; }
.map-cockpit__metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); border-bottom:1px solid #24445f; margin-top:14px; padding-bottom:14px; gap:12px; }
.map-cockpit__metrics button { display:flex; align-items:baseline; justify-content:center; gap:12px; background:transparent; border:0; border-right:1px solid #24445f; padding:4px; font-size:12px; color:#a6c3dc; }
.map-cockpit__metrics button:last-child { border:0; }
.map-cockpit__metrics strong { font-size:28px; color:#66e4dd; font-weight:600; font-variant-numeric:tabular-nums; }
.map-cockpit__support { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
.map-cockpit__panel { min-width:0; padding:18px; border:1px solid #233e58; border-radius:10px; background:#0a2036; }
.map-cockpit__panel>header { margin-bottom:16px; } .map-cockpit__panel>header small { display:block; margin-top:5px; }
.map-cockpit__panel>header button,.map-cockpit__warning { background:none; border:0; color:#6edbd9; font-size:12px; padding:4px 0; }
.map-cockpit__tasks button { display:flex; align-items:center; justify-content:space-between; gap:12px; width:100%; border:0; border-bottom:1px solid #213c53; background:transparent; padding:12px 0; text-align:left; font-size:13px; }
.map-cockpit__tasks span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; } .map-cockpit__tasks small { flex-shrink:0; } .map-cockpit__tasks .overdue { color:#ffd078; }
.map-cockpit__warning { margin-top:12px; color:#ffd078; }
.map-cockpit__empty { color:#8daec9; font-size:13px; padding:24px 0; }
.map-cockpit__footer { margin-top:18px; color:#829eb8; font-size:11px; } .map-cockpit__footer form { display:flex; border:1px solid #315575; border-radius:7px; overflow:hidden; } .map-cockpit__footer input { color:#dfedfa; background:#091e33; border:0; padding:8px; width:160px; min-width:0; } .map-cockpit__footer form button { border:0; border-radius:0; }
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
 .map-cockpit__support { grid-template-columns:1fr; } .map-cockpit__metrics { gap:8px; grid-template-columns:repeat(2,minmax(0,1fr)); } .map-cockpit__metrics button:nth-child(2) { border:0; } .map-cockpit__metrics strong { font-size:25px; }
 .map-cockpit__modes { order:3; width:100%; } .map-cockpit__modes button { flex:1; padding:8px; }
 .map-cockpit__tasks button { align-items:flex-start; flex-direction:column; gap:5px; } .map-cockpit__tasks span { white-space:normal; }
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
 .cockpit-expanded .eyebrow {font-size:13px;letter-spacing:1px;}
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
 .cockpit-expanded .eyebrow {display:none;}
 .cockpit-expanded .map-cockpit__map-head p {font-size:11px;margin-top:3px;}
 .cockpit-expanded .map-cockpit__metrics strong {font-size:24px;}
 .cockpit-expanded .map-cockpit__tools button {padding:6px 10px;}
 .cockpit-expanded .map-cockpit__footer>span {font-size:10px;}
}
</style>
