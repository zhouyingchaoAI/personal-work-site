<script setup lang="ts">
import { isCustomerUnit } from '../command/commandOverview'
import { computed, ref } from 'vue'
import AmapBaseMap from './AmapBaseMap.vue'
const amapReady = ref(false)
import type { CrmUnit, CrmPerson, CrmRelation, CrmPlaybook } from '../../../../src/services/personalWorkApi'
import { PROVINCES, MAP_VIEWBOX, REGION_COLORS, REGION_CITIES, provinceRegions } from './chinaMapData'

type Region = { name: string; units: number; people: number; warnings: number; followups: number }
const props = defineProps<{
  regions: Region[]
  units: CrmUnit[]
  people: CrmPerson[]
  relations: CrmRelation[]
  playbook?: CrmPlaybook | null
  selected?: string
  stack?: boolean
  immersive?: boolean
  type?: string
}>()
const emit = defineEmits<{ region: [value: string]; type: [value: string] }>()

// 地图仅标注已定义省份归属的经营区域，避免展示无对应数据的区域。
const mappedRegions = ['东区', '中区', '广东区', '西区']
const priority = ['东区', '中区', '西区', '广东区'] // 省份归属多区域时的主色优先级（官方三区优先于广东区）
const unitTypes = ['主管单位', '业主单位', '总包单位', '设计单位', '厂商']
const typeColor: Record<string, string> = { 主管单位: '#9a8cff', 业主单位: '#f5c242', 总包单位: '#23e0d0', 设计单位: '#4596ff', 厂商: '#f97316' }
const localType = ref('') // '' = 全部单位类型
// 父级传入 type 时以父级为准（客户概况行等外部入口也能筛选类型），否则用本地状态。
const activeType = computed({ get: () => props.type !== undefined ? props.type : localType.value, set: v => { localType.value = v } })
const showCities = ref(false)
const showCompanies = ref(false)
const labelUnits = computed(() => props.units.filter(u =>
  (!activeType.value || u.type === activeType.value) &&
  unitRegions(u).some(r => displayNames.value.includes(r) && (!props.selected || r === props.selected))))

// 授权可见的区域集合（由父级下发的 regions 决定），只展示其中已定义省份归属的区域。
const displayNames = computed(() => {
  const authorized = props.regions.length ? new Set(props.regions.map(r => r.name)) : null
  return mappedRegions.filter(name => !authorized || authorized.has(name))
})
const displayedSet = computed(() => new Set(displayNames.value))

const customerUnit = isCustomerUnit
function unitRegions(u: CrmUnit): string[] {
  const rs = Array.isArray(u.business_regions) ? u.business_regions.filter(Boolean) : []
  if (rs.length) return [...new Set(rs)]
  return u.business_region ? [u.business_region] : []
}
// 按经营区域 + 单位类型即时统计，单位类型为空表示全部类型。
function statFor(region: string, type: string): Region {
  // Contact ownership can point at company, subsidiary or unit nodes.
  // Only the unit count is restricted to operating-unit nodes.
  const us = props.units.filter(u => (!type || u.type === type) && unitRegions(u).includes(region))
  const unitIds = new Set(us.map(u => u.id))
  const ps = props.people.filter(p => unitIds.has(p.unit_id))
  const personIds = new Set(ps.map(p => p.id))
  const rs = props.relations.filter(r => personIds.has(r.person_id))
  const relationIds = new Set(rs.map(r => r.id))
  return {
    name: region,
    units: us.filter(customerUnit).length,
    people: ps.length,
    warnings: rs.filter(r => r.decay_state !== 'normal').length,
    followups: (props.playbook?.followups || []).filter(a => relationIds.has(a.relation_id)).length,
  }
}
const mapRegions = computed(() => displayNames.value.map(name => statFor(name, activeType.value)))
const statByRegion = computed(() => new Map(mapRegions.value.map(r => [r.name, r])))
// 选定单位类型时，该类型下无单位的区域淡出。
const activeRegions = computed(() => new Set(mapRegions.value.filter(r => r.units > 0 || r.people > 0).map(r => r.name)))
// 每类单位的联系人与待维系数（跟随选中区域），供五位一体类型卡展示。
const typeStats = computed(() => {
  const rows = new Map(unitTypes.map(t => [t, { people: 0, warnings: 0 }]))
  const unitType = new Map<string, string>()
  for (const u of props.units) {
    if (!unitRegions(u).length) continue
    if (props.selected && !unitRegions(u).includes(props.selected)) continue
    unitType.set(u.id, u.type)
  }
  const personType = new Map<string, string>()
  for (const p of props.people) { const t = unitType.get(p.unit_id); if (t && rows.has(t)) { personType.set(p.id, t); rows.get(t)!.people++ } }
  for (const r of props.relations) { const t = personType.get(r.person_id); if (t && r.decay_state !== 'normal') rows.get(t)!.warnings++ }
  return rows
})
const typeTotals = computed(() => new Map(
  ['', ...unitTypes].map(type => [type, props.units.filter(u => customerUnit(u) && (!type || u.type === type) &&
    (!props.selected || unitRegions(u).includes(props.selected))).length])
))

function primaryRegion(name: string): string {
  const regions = provinceRegions(name).filter(r => displayedSet.value.has(r))
  return priority.find(r => regions.includes(r)) || ''
}
const sharedProvinces = computed(() =>
  PROVINCES.map(p => p.n).filter(n => provinceRegions(n).filter(r => displayedSet.value.has(r)).length > 1)
)

function fill(name: string): string {
  const regions = provinceRegions(name).filter(r => displayedSet.value.has(r))
  if (!regions.length) return 'var(--map-idle)'
  if (props.selected && displayedSet.value.has(props.selected)) {
    return regions.includes(props.selected) ? REGION_COLORS[props.selected] : 'var(--map-dim)'
  }
  return REGION_COLORS[primaryRegion(name)] || 'var(--map-idle)'
}
function opacity(name: string): number {
  const regions = provinceRegions(name).filter(r => displayedSet.value.has(r))
  if (!regions.length) return 0.85
  if (props.selected && displayedSet.value.has(props.selected)) return regions.includes(props.selected) ? 1 : 0.4
  if (activeType.value) return regions.some(r => activeRegions.value.has(r)) ? 0.92 : 0.32
  return 0.92
}
// 官方指定按省份边缘描边：区域内省份用该区域色加粗描边，非区域省份保持暗色细边。
function stroke(name: string): string {
  const region = props.selected && displayedSet.value.has(props.selected) && provinceRegions(name).includes(props.selected)
    ? props.selected
    : primaryRegion(name)
  if (props.selected && provinceRegions(name).includes(props.selected)) return '#e4ffff'
  return region ? REGION_COLORS[region] : '#50728b'
}
function strokeWidth(name: string): number {
  if (props.selected) return provinceRegions(name).includes(props.selected) ? 3.5 : 0.6
  return primaryRegion(name) ? 2.5 : 0.8
}

const hover = ref<{ name: string; x: number; y: number } | null>(null)
function onMove(name: string, event: MouseEvent) {
  const host = (event.currentTarget as SVGElement).closest('.region-map__stage') as HTMLElement | null
  if (!host) return
  const rect = host.getBoundingClientRect()
  hover.value = { name, x: event.clientX - rect.left, y: event.clientY - rect.top }
}
function hoverRegions(name: string): string {
  return provinceRegions(name).filter(r => displayedSet.value.has(r)).join(' · ') || '未纳入经营区域'
}
function hoverStat(name: string): Region | null {
  const region = primaryRegion(name)
  return region ? statByRegion.value.get(region) || null : null
}

function setType(type: string) { const next = activeType.value === type ? '' : type; localType.value = next; emit('type', next) }
function pick(name: string) {
  const region = primaryRegion(name)
  if (region) emit('region', props.selected === region ? '' : region)
}
function pickRegion(name: string) { emit('region', props.selected === name ? '' : name) }
</script>

<template>
  <section class="region-map" :class="{ 'region-map--stack': stack, 'region-map--immersive': immersive, 'region-map--fallback': !amapReady }">
    <div class="region-map__filters" role="group" aria-label="按单位类型查看">
      <span class="region-map__filter-scope" aria-live="polite">{{ selected || '全部区域' }}<small>五位一体 · 点击类型联动</small></span>
      <button class="region-map__type region-map__type--all" :class="{ active: !activeType }" :aria-pressed="!activeType" @click="setType('')"><span class="region-map__type-name">全部类型</span><em>{{ typeTotals.get('') }}</em><small>家单位</small></button>
      <button
        v-for="type in unitTypes"
        :key="type"
        class="region-map__type"
        :class="{ active: activeType === type, dim: activeType && activeType !== type }"
        :style="{ '--tc': typeColor[type] }"
        :aria-pressed="activeType === type"
        :title="`${type}：${typeTotals.get(type)} 家单位 · ${typeStats.get(type)?.people || 0} 位联系人${typeStats.get(type)?.warnings ? ` · ${typeStats.get(type)!.warnings} 条关系待维系` : ''}`"
        @click="setType(type)"
      ><i /><span class="region-map__type-name">{{ type }}</span><em>{{ typeTotals.get(type) }}</em><small>{{ typeStats.get(type)?.people || 0 }}人</small><u v-if="typeStats.get(type)?.warnings" class="region-map__type-warn">{{ typeStats.get(type)!.warnings }}</u></button>
      <span class="region-map__filter-gap" />
      <button class="region-map__toggle" :disabled="!amapReady" :class="{ active: showCities }" :aria-pressed="showCities" @click="showCities = !showCities">城市标注</button>
      <button class="region-map__toggle" :disabled="!amapReady" :class="{ active: showCompanies }" :aria-pressed="showCompanies" @click="showCompanies = !showCompanies">公司全称标注</button>
    </div>
    <div class="region-map__body">
    <aside v-if="immersive" class="region-map__left"><slot name="left" /></aside>
    <div class="region-map__stage" @mouseleave="hover = null">
      <AmapBaseMap :selected="selected" :regions="displayNames" :units="labelUnits" :show-cities="showCities" :show-companies="showCompanies" @ready="amapReady = $event" @region="emit('region', $event)" />
      <svg v-show="!amapReady" :viewBox="`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="客户经营区域地图">
        <defs>
          <filter id="region-map-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#48d7ff" flood-opacity="0.5" />
          </filter>
        </defs>
        <g>
          <path
            v-for="p in PROVINCES"
            :key="p.n"
            :d="p.d"
            :fill="fill(p.n)"
            :fill-opacity="opacity(p.n)"
            :stroke="stroke(p.n)"
            :stroke-width="strokeWidth(p.n)"
            :filter="selected && provinceRegions(p.n).includes(selected) ? 'url(#region-map-glow)' : undefined"
            :class="['region-map__prov', { 'is-active': provinceRegions(p.n).length, 'is-outlined': primaryRegion(p.n) }]"
            @mousemove="onMove(p.n, $event)"
            @click="pick(p.n)"
          />
        </g>
      </svg>
      <transition name="region-map-tip">
        <div v-if="hover" class="region-map__tip" :style="{ left: hover.x + 'px', top: hover.y + 'px' }">
          <strong>{{ hover.name }}</strong>
          <em>{{ hoverRegions(hover.name) }}</em>
          <span v-if="hoverStat(hover.name)">{{ hoverStat(hover.name)!.units }} 家单位 · {{ hoverStat(hover.name)!.people }} 位联系人</span>
        </div>
      </transition>
    </div>

    <aside class="region-map__side">
      <header>
        <h4>{{ activeType || '全部类型' }}区域布局</h4>
        <button v-if="selected" @click="emit('region', '')">全部区域</button>
      </header>
      <button
        v-for="area in mapRegions"
        :key="area.name"
        class="region-map__card"
        :class="{ selected: selected === area.name }"
        :style="{ '--rc': REGION_COLORS[area.name] }"
        @click="pickRegion(area.name)"
      >
        <span class="region-map__dot" />
        <span class="region-map__name">{{ area.name }}</span>
        <span class="region-map__nums"><b>{{ area.units }}</b>单位 · <b>{{ area.people }}</b>人</span>
        <span class="region-map__warn" :class="{ on: area.warnings }">待维系 {{ area.warnings }}</span>
      </button>
      <p class="region-map__hint">{{ selected ? '亮白边界＋区域色光晕：当前选中 ' + selected : '彩色边界：标准区域范围，点击聚焦' }}。统计按客户资料经营区域归属，非按省界推算<template v-if="sharedProvinces.length">；{{ sharedProvinces.join('、') }} 跨区</template>。</p>
      <template v-for="name in displayNames.filter(n => !selected || n === selected)" :key="name">
        <p v-if="REGION_CITIES[name]?.length" class="region-map__hint">{{ name }}单独绑定城市：{{ REGION_CITIES[name].map(c => `${c.province}·${c.city}`).join('、') }}（不代表整省覆盖）</p>
      </template>
      <div v-if="immersive" class="region-map__support"><slot name="right" /></div>
    </aside>
    </div>
  </section>
</template>

<style scoped lang="scss">
.region-map__filter-scope { display:flex;flex-direction:column;justify-content:center;color:#a8eeef;font-size:13px;font-weight:600;padding:0 10px 0 0;white-space:nowrap;
  small { font-size:10px;font-weight:400;color:#6f93b4;margin-top:1px; } }
.region-map__filter-gap { flex:1; }
.region-map .region-map__type {
  position:relative; display:grid; grid-template-columns:auto auto; grid-template-areas:'dot name' 'num sub'; align-items:baseline; column-gap:6px;
  min-width:96px; padding:5px 12px 5px 11px; border-radius:8px; border:1px solid rgba(64,110,160,.55);
  background:linear-gradient(180deg, color-mix(in srgb, var(--tc, #4a7096) 16%, rgba(10,32,58,.9)), rgba(8,24,46,.92));
  box-shadow:inset 0 1px 0 rgba(140,190,250,.1);
  i { grid-area:dot; align-self:center; width:8px; height:8px; }
  .region-map__type-name { grid-area:name; font-size:12px; color:#cfe4f6; }
  em { grid-area:num; justify-self:end; font-size:17px; font-weight:700; color:#eafcff; line-height:1.05; text-shadow:0 0 10px color-mix(in srgb, var(--tc, #53cfe0) 55%, transparent); }
  small { grid-area:sub; font-size:10px; color:#7d9cba; }
  u { position:absolute; top:-6px; right:-5px; min-width:16px; height:16px; padding:0 4px; box-sizing:border-box; border-radius:8px; background:#b45309; color:#ffe9c7; font-size:10px; font-weight:700; line-height:16px; text-align:center; text-decoration:none; box-shadow:0 0 8px rgba(244,160,50,.5); }
  &.dim { opacity:.55; }
  &:hover { opacity:1; transform:translateY(-1px); }
  &.active { background:linear-gradient(180deg, color-mix(in srgb, var(--tc, #53cfe0) 30%, rgba(12,42,72,.95)), rgba(10,30,56,.95)); border-color:var(--tc, #53cfe0); box-shadow:0 0 0 1px color-mix(in srgb, var(--tc, #53cfe0) 65%, transparent), 0 0 16px color-mix(in srgb, var(--tc, #53cfe0) 40%, transparent); }
}
.region-map__type--all { --tc:#53cfe0; grid-template-areas:'name name' 'num sub'; }
.region-map .region-map__toggle { align-self:center; }
.region-map {
  --map-idle: #294d6c;
  --map-dim: #102c49;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  min-width: 0;
  flex: 1;
  height: 100%;
}
.region-map__filters {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
  button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid #2c5378;
    border-radius: 999px;
    background: #0c2c49;
    color: #b6d2ea;
    padding: 4px 10px;
    font-size: 11px;
    cursor: pointer;
    transition: border-color .15s, background .15s, color .15s;
    i { width: 7px; height: 7px; border-radius: 50%; background: var(--tc, #7aa0c0); box-shadow: 0 0 7px var(--tc, transparent) }
    em { font-style: normal; color: #6fe6dc; font-variant-numeric: tabular-nums }
    &:hover { border-color: #4a86b3 }
    &.active { background: #13456b; border-color: #53cfe0; color: #eafcff }
  }
}
.region-map__body {
  display: flex;
  gap: 14px;
  flex: 1;
  min-height: 0;
  min-width: 0;
}
.region-map__stage {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  border-radius: 10px;
  background: radial-gradient(ellipse at 60% 42%, #113c6633, transparent 62%);
  overflow: hidden;
  /* 绝对定位铺满舞台，避免 SVG 以固有高度撑破面板、渗透到下方组件。 */
  svg { position: absolute; inset: 0; width: 100%; height: 100%; display: block }
}
.region-map__prov {
  transition: fill-opacity .18s, filter .18s;
  stroke-linejoin: round;
  &.is-active { cursor: pointer }
  &.is-active:hover { fill-opacity: 1 !important; filter: url(#region-map-glow) }
}
.region-map--fallback .region-map__stage {
  > svg { height:calc(100% - 56px); }
  :deep(.amap-status) { bottom:0; width:max-content; max-width:calc(100% - 20px); box-sizing:border-box; text-align:center; }
}
.region-map__tip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 12px));
  pointer-events: none;
  background: #061a30f2;
  border: 1px solid #3a86b8;
  border-radius: 8px;
  padding: 8px 11px;
  white-space: nowrap;
  box-shadow: 0 8px 22px #0009;
  z-index: 5;
  strong { display: block; font-size: 13px; color: #eaf6ff }
  em { display: block; font-style: normal; font-size: 11px; color: #6fe6dc; margin: 2px 0 }
  span { display: block; font-size: 11px; color: #a9c6df }
}
.region-map-tip-enter-active, .region-map-tip-leave-active { transition: opacity .12s }
.region-map-tip-enter-from, .region-map-tip-leave-to { opacity: 0 }
.region-map__side { flex: 0 0 clamp(150px, 30%, 210px); display: flex; flex-direction: column; gap: 8px; min-width: 0; min-height: 0; overflow: auto }
.region-map__side header { display: flex; align-items: center; justify-content: space-between; gap: 8px }
.region-map__side h4 { margin: 0; font-size: 13px; color: #dcefff }
.region-map__side header button { border: 1px solid #3c698b; background: #0b3459; color: #9eeaff; border-radius: 5px; padding: 4px 8px; font-size: 11px; cursor: pointer }
.region-map__card {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas: 'dot name' 'dot nums' 'dot warn';
  align-items: center;
  gap: 2px 9px;
  text-align: left;
  padding: 9px 11px;
  border: 1px solid #2c5378;
  border-left: 3px solid var(--rc);
  border-radius: 8px;
  background: linear-gradient(120deg, #0e2f4fcc, #081d34cc);
  color: #dcefff;
  cursor: pointer;
  transition: border-color .16s, background .16s;
  &:hover, &.selected { border-color: var(--rc); background: linear-gradient(120deg, #13456bd0, #0b273fcc) }
}
.region-map__dot { grid-area: dot; width: 10px; height: 10px; border-radius: 50%; background: var(--rc); box-shadow: 0 0 10px var(--rc) }
.region-map__name { grid-area: name; font-size: 14px; font-weight: 600 }
.region-map__nums { grid-area: nums; font-size: 11px; color: #a7c4dd; b { color: #63e2df; font-size: 15px; margin: 0 2px } }
.region-map__warn { grid-area: warn; font-size: 11px; color: #8fabc6; &.on { color: #ffc13c } }
.region-map__hint { margin: 2px 0 0; font-size: 10px; line-height: 1.6; color: #7f9cb8 }
/* 纵向布局：地图在上、区域卡横向排布在下（用于大屏窄高面板）。 */
.region-map--stack .region-map__body { flex-direction: column }
.region-map--stack .region-map__side { flex: 0 0 auto; flex-direction: row; flex-wrap: wrap; overflow: visible }
.region-map--stack .region-map__side header { flex-basis: 100% }
.region-map--stack .region-map__card { flex: 1 1 130px; min-width: 120px }
.region-map--stack .region-map__hint { flex-basis: 100% }
@media (max-width: 1100px) {
  .region-map__body { flex-direction: column }
  .region-map__stage { min-height: 180px }
  .region-map__side { flex: 0 0 auto; flex-direction: row; flex-wrap: wrap; overflow: visible }
  .region-map__side header { flex-basis: 100% }
  .region-map__card { flex: 1 1 130px; min-width: 130px }
  .region-map__hint { flex-basis: 100% }
}
</style>
<style scoped lang="scss">
.region-map--immersive {
 .region-map__body {flex-direction:row;gap:16px;}
 .region-map__left {flex:0 0 clamp(190px,18vw,270px);min-width:0;}
 .region-map__side {flex:0 0 clamp(215px,19vw,280px);overflow:visible;flex-direction:column;flex-wrap:nowrap;gap:6px;}
 .region-map__stage {min-height:0;}
 .region-map__support {margin-top:auto;}
 .region-map__card {flex:none;min-width:0;padding:7px 10px;}
 .region-map__side header {flex-basis:auto;}
 .region-map__hint {font-size:9px;flex-basis:auto;}
}
@media(max-height:820px) and (min-width:701px) {
 .region-map--immersive {
  .region-map__card {grid-template-areas:'dot name' 'dot nums';padding:5px 9px;}
  .region-map__warn {display:none;}
  .region-map__hint {display:none;}
  .region-map__side h4 {font-size:11px;}
 }
}
@media(max-width:700px) {
 .region-map--immersive .region-map__body {flex-direction:column;}
 .region-map--immersive .region-map__left,.region-map--immersive .region-map__side {flex-basis:auto;}
 .region-map--immersive .region-map__stage {min-height:260px;order:-1;}
}
@media(min-width:701px) {
 .region-map--immersive.region-map--fallback {
  .region-map__body {display:grid;grid-template-columns:minmax(150px,20%) minmax(0,1fr) minmax(170px,22%);}
  .region-map__stage {position:relative;inset:auto;width:100%;height:100%;}
  .region-map__left,.region-map__side {position:relative;inset:auto;width:auto;overflow:auto;pointer-events:auto;}
 }
 .region-map--immersive {
  .region-map__body {position:relative;isolation:isolate;display:block;}
  .region-map__stage {position:absolute;inset:0;z-index:0;width:100%;height:100%;}
  .region-map__left {position:absolute;top:0;left:0;z-index:2;width:clamp(190px,18vw,270px);pointer-events:none;}
  .region-map__side {position:absolute;inset:0 0 0 auto;z-index:2;width:clamp(215px,19vw,280px);pointer-events:none;}
  .region-map__left > *, .region-map__side > * {pointer-events:auto;}
  .region-map__card {backdrop-filter:blur(8px);}
  .region-map__support {backdrop-filter:blur(8px);border-radius:10px;}
 }
}
</style>
