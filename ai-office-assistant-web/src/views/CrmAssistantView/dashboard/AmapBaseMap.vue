<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { crmAmapSettings } from '../../../services/personalWorkApi'
import type { CrmUnit } from '../../../services/personalWorkApi'
import { customerCityGroups, type CityCustomers } from './customerMapLabels'
import { REGION_PROVINCES, REGION_CITIES, REGION_COLORS } from './chinaMapData'
import { loadAmap } from './amapLoader'
import { searchDistrict } from './amapDistrictCache'
import { CITY_CENTERS } from './cityCenters'
const props = defineProps<{ selected?: string; regions: string[]; units: CrmUnit[]; showCities: boolean; showCompanies: boolean }>()
const emit = defineEmits<{ ready: [value: boolean]; region: [value: string] }>()
const container = ref<HTMLElement>(), message = ref('正在加载高德地图…')
let map: any, sdk: any, disposed = false, generation = 0, drawing = 0
let observer: ResizeObserver | undefined
let readyTimer: ReturnType<typeof setTimeout> | undefined
let fitTimer: ReturnType<typeof setTimeout> | undefined
let focusPolygons: any[] = []
let regionPolygons: { names: string[]; polygon: any }[] = []
const sharedBoundaryNote = ref('')
function boundaryStyle(names: string[]) {
  const selected=!!props.selected&&names.includes(props.selected)
  const active=!props.selected||selected
  const color=selected?REGION_COLORS[props.selected!]:names.length>1?'#e8d59c':REGION_COLORS[names[0]!]
  return {strokeColor:selected?'#e4ffff':color,fillColor:color,
    strokeWeight:selected?3.5:active?3:1,strokeOpacity:active?1:0.18,
    fillOpacity:selected?0.3:active?0.14:0.012,zIndex:selected?25:10,
    strokeStyle:names.length>1?'dashed':'solid'}
}
let selectionFrame = 0
function updateSelection() {
  if (!map || disposed) return
  focusPolygons = []
  for (const { names, polygon } of regionPolygons) {
    const selected = !!props.selected && names.includes(props.selected)
    const active = !props.selected || selected
    polygon.setOptions(boundaryStyle(names))
    if (active) focusPolygons.push(polygon)
  }
  fitRegion()
}
function scheduleSelection() {
  cancelAnimationFrame(selectionFrame)
  selectionFrame = requestAnimationFrame(updateSelection)
}
function fitRegion() {
  if (!map || !container.value) return
  if (!focusPolygons.length) { map.setZoomAndCenter(4.5, [105.5, 35.5]); return }
  const stage = container.value.getBoundingClientRect()
  const body = container.value.closest('.region-map__body')
  const panelWidth = (selector: string) => {
    const element = body?.querySelector(selector) as HTMLElement | null
    if (!element || getComputedStyle(element).position !== 'absolute') return 0
    return Math.min(element.getBoundingClientRect().width + 24, stage.width * 0.28)
  }
  // Gaode padding order: top, bottom, left, right. Only boundaries affect fitting;
  // city-center labels outside a standard region must not pull its camera away.
  map.setFitView(focusPolygons, false, [35, 65, Math.max(35, panelWidth('.region-map__left')), Math.max(35, panelWidth('.region-map__side'))], 9)
}
let polygons: any[] = [], markers: any[] = [], labelGeneration = 0, infoWindow: any
const labelStatus = ref('')
async function cityCenter(city: string) {
  const known = CITY_CENTERS[city]
  if (known) return [...known]
  return (await searchDistrict(sdk, city, 'city', 'base'))?.center || null
}
function companyRow(company: CityCustomers['companies'][number]) {
  const row = document.createElement('div')
  row.className = 'customer-map-company'
  row.style.borderLeftColor = REGION_COLORS[props.selected || company.regions.find(r => props.regions.includes(r)) || ''] || '#87a8c2'
  row.textContent = company.name
  row.title = `${company.name} · ${company.regions.filter(r => props.regions.includes(r)).join(' / ')}`
  return row
}
async function drawLabels() {
  const current = ++labelGeneration, target = map
  if (!target || !sdk) return
  target.remove(markers); markers = []; infoWindow?.close()
  labelStatus.value = ''
  if (!props.showCities && !props.showCompanies) return
  const { groups, missing } = customerCityGroups(props.units)
  let failed = 0, loaded = 0, next = 0
  labelStatus.value = '正在定位客户城市…'
  // Bound concurrent requests; company names remain local and are never sent to Gaode.
  async function worker() {
    while (next < groups.length && current === labelGeneration && !disposed) {
      const group = groups[next++]!
      const position = await cityCenter(group.city)
      if (disposed || current !== labelGeneration || target !== map) return
      if (!position) { failed++; continue }
      const content = document.createElement('button')
      content.type = 'button'; content.className = 'customer-map-label'
      content.setAttribute('aria-label', `${group.city}，${group.companies.length} 家企业，查看公司全称`)
      if (props.showCities) {
        const title = document.createElement('strong')
        title.textContent = `${group.city} · ${group.companies.length} 家企业`
        content.appendChild(title)
      }
      if (props.showCompanies) {
        group.companies.slice(0, 1).forEach(c => content.appendChild(companyRow(c)))
        if (group.companies.length > 1) {
          const more = document.createElement('small'); more.textContent = `另 ${group.companies.length - 1} 家 · 点击展开`; content.appendChild(more)
        }
      }
      content.onclick = e => {
        e.stopPropagation()
        const detail = document.createElement('div'); detail.className = 'customer-map-detail'
        const title = document.createElement('strong'); title.textContent = `${group.province} · ${group.city} · ${group.companies.length} 家企业`
        const note = document.createElement('p'); note.textContent = '按客户资料城市中心定位，非企业实际地址。'
        detail.append(title, note)
        group.companies.forEach(company => {
          detail.appendChild(companyRow(company))
          const region = document.createElement('small'); region.textContent = company.regions.filter(r => props.regions.includes(r)).join(' / '); detail.appendChild(region)
        })
        infoWindow?.close()
        infoWindow = new sdk.InfoWindow({ content: detail, offset: new sdk.Pixel(0, -12) })
        infoWindow.open(target, position)
      }
      // Zero-size origin is the city coordinate; the callout must never move the target.
      const markerContent = document.createElement('div')
      markerContent.className = 'customer-map-marker'
      markerContent.style.setProperty('--marker-color', REGION_COLORS[props.selected || group.companies.flatMap(c => c.regions).find(r => props.regions.includes(r)) || ''] || '#7ee5f2')
      const targetPoint = document.createElement('span')
      targetPoint.className = 'customer-map-target'
      targetPoint.setAttribute('aria-hidden', 'true')
      const leader = document.createElement('span')
      leader.className = 'customer-map-leader'
      leader.setAttribute('aria-hidden', 'true')
      markerContent.append(targetPoint, leader, content)
      const marker = new sdk.Marker({ position, content: markerContent, anchor: 'top-left', offset: new sdk.Pixel(0, 0), zIndex: 150 })
      content.addEventListener('mouseenter', () => marker.setzIndex(180))
      content.addEventListener('mouseleave', () => marker.setzIndex(150))
      content.addEventListener('focus', () => marker.setzIndex(180))
      content.addEventListener('blur', () => marker.setzIndex(150))
      markers.push(marker); target.add(marker); loaded++
      labelStatus.value = `城市级定位 ${loaded}/${groups.length} 处${failed ? ` · ${failed} 处暂不可用` : ''} · 同城企业合并展示`
    }
  }
  await Promise.all([worker(), worker(), worker()])
  if (current === labelGeneration && !disposed) labelStatus.value = `城市级定位 ${loaded} 处 · 同城企业合并展示${missing ? ` · ${missing} 条资料缺少有效城市` : ''}${failed ? ` · ${failed} 处定位失败` : ''}`
}
async function district(name: string, level: string) {
  return (await searchDistrict(sdk, name, level, 'all'))?.boundaries || []
}
async function draw() {
  if (!map || !sdk) return
  const current = ++drawing, target = map
  const names = ['广东区', '西区', '中区', '东区'].filter(n => props.regions.includes(n))
  names.sort((a, b) => Number(b === props.selected) - Number(a === props.selected))
  target.remove(polygons); polygons = []; regionPolygons = []; focusPolygons = []
  let missing = 0
  let completed = 0
  const grouped = new Map<string,{name:string;level:string;regions:string[]}>()
  names.forEach(name => {
    const provinces = REGION_PROVINCES[name] || []
    const searches = [...provinces.map(p => ({ name: p, level: 'province' })),
      ...(REGION_CITIES[name] || []).filter(c => !provinces.includes(c.province)).map(c => ({ name: c.city, level: 'city' }))]
    for(const search of searches){
      const key=`${search.level}:${search.name}`
      if(!grouped.has(key))grouped.set(key,{...search,regions:[]})
      if(!grouped.get(key)!.regions.includes(name))grouped.get(key)!.regions.push(name)
    }
  })
  const jobs=[...grouped.values()]
  sharedBoundaryNote.value=jobs.filter(j=>j.regions.length>1).map(j=>`${j.name}：${j.regions.join(' / ')}共同覆盖`).join('；')
  await Promise.all(jobs.map(async job => {
      const paths = await district(job.name, job.level)
      if (disposed || current !== drawing || target !== map) return
      if (!paths.length) missing++
      const overlays: any[] = []
      for (const path of paths) {
        const polygon = new sdk.Polygon({ path, ...boundaryStyle(job.regions), bubble: true })
        // Shared geometry cannot choose a unique owner; use the explicit regional controls.
        polygon.on('click', () => {
          if(job.regions.length>1){message.value=`${job.name}由${job.regions.join('、')}共同覆盖，请点击区域卡片选择`;return}
          const name=job.regions[0]!
          emit('region', props.selected === name ? '' : name)
        })
        overlays.push(polygon)
        regionPolygons.push({ names: job.regions, polygon })
      }
      target.add(overlays); polygons.push(...overlays)
      completed++
      message.value = completed < jobs.length ? `区域边界加载中 ${completed}/${jobs.length}，可先点击右侧区域` : missing ? `高德底图 · ${missing} 处边界暂不可用，区域筛选可正常使用` : ''
      scheduleSelection()
  }))
}
async function initialize() {
  const current = ++generation
  sharedBoundaryNote.value = ''
  clearTimeout(fitTimer); cancelAnimationFrame(selectionFrame); focusPolygons = []; regionPolygons = []
  ++labelGeneration; markers = []; polygons = []; infoWindow?.close(); labelStatus.value = ''
  clearTimeout(readyTimer)
  ++drawing; emit('ready', false); map?.destroy(); map = undefined
  message.value = '正在加载高德地图…'
  try {
    const config = await crmAmapSettings()
    if (disposed || current !== generation) return
    if (!config.enabled || !config.key || !config.has_security_code) { message.value = '备用地图 · 请在「区域设置」配置高德 Key 和安全密钥'; return }
    sdk = await loadAmap(config.key)
    if (disposed || current !== generation || !container.value) return
    const target = new sdk.Map(container.value, { viewMode: '2D', zoom: 4.5, center: [105.5, 35.5], mapStyle: 'amap://styles/darkblue', resizeEnable: true, showLabel: true })
    map = target
    target.addControl(new sdk.Scale({ position: 'LB', offset: new sdk.Pixel(120, 12) }))
    target.addControl(new sdk.ToolBar({ position: 'LB', offset: new sdk.Pixel(230, 12) }))
    readyTimer = setTimeout(() => {
      if (map === target && message.value === '正在加载高德地图…') {
        ++drawing; target.destroy(); map = undefined; emit('ready', false)
        message.value = '备用地图 · 高德响应超时，请检查凭据和网络'
      }
    }, 20000)
    let completed = false
    target.on('complete', () => {
      clearTimeout(readyTimer)
      if (disposed || map !== target) return
      if (completed) return
      completed = true
      emit('ready', true); message.value = ''; void draw(); void drawLabels()
    })
  } catch (e) { if (current === generation && !disposed) message.value = `备用地图 · ${e instanceof Error ? e.message : '高德加载失败'}` }
}
watch(() => props.selected, scheduleSelection)
watch(() => [props.regions, REGION_PROVINCES, REGION_CITIES], () => { void draw() }, { deep: true })
// props.units 是父级 computed（每次变化产生新数组引用），浅比较引用即可捕获，无需深度遍历大数组。
watch(() => [props.units, props.showCities, props.showCompanies, props.selected], () => { void drawLabels() })
onMounted(() => {
  void initialize()
  window.addEventListener('crm-amap-settings-changed', initialize)
  observer = new ResizeObserver(() => {
    map?.resize?.()
    clearTimeout(fitTimer)
    fitTimer = setTimeout(() => { if (focusPolygons.length) fitRegion() }, 200)
  })
  if (container.value) observer.observe(container.value)
})
onBeforeUnmount(() => { disposed = true; generation++; drawing++; labelGeneration++; cancelAnimationFrame(selectionFrame); clearTimeout(readyTimer); clearTimeout(fitTimer); observer?.disconnect(); window.removeEventListener('crm-amap-settings-changed', initialize); map?.destroy() })
</script>
<template>
  <div ref="container" class="amap-base" aria-label="高德客户经营区域地图" />
  <div v-if="sharedBoundaryNote" class="amap-shared" role="note">虚线为共同覆盖边界 · {{sharedBoundaryNote}}</div>
  <div v-if="message || labelStatus" class="amap-status" role="status">{{ [message, labelStatus].filter(Boolean).join(' · ') }}</div>
</template>
<style scoped>
.amap-base {position:absolute;inset:0;}
.amap-shared{position:absolute;top:12px;left:50%;transform:translateX(-50%);z-index:2;max-width:65%;padding:6px 10px;border:1px dashed #e8d59c;border-radius:6px;background:#081c2df0;color:#e8d59c;font-size:12px;pointer-events:none;}
/* JS API's raster fallback ignores mapStyle. Tone only its tile layer;
   leave region polygons, labels, controls and Gaode attribution untouched. */
.amap-base :deep(.amap-layer-tile) {filter:invert(1) hue-rotate(180deg) saturate(.35) brightness(.65) contrast(.85);}
.amap-base :deep(.amap-maps) {background:#0a1727;}
.amap-status {position:absolute;bottom:42px;left:50%;transform:translateX(-50%);z-index:1;max-width:60%;padding:5px 10px;border-radius:5px;background:#081c2de6;color:#bbd7ef;font-size:12px;pointer-events:none;}
</style>
<style>
.customer-map-marker {position:relative;width:0;height:0;overflow:visible;--marker-color:#7ee5f2;}
.customer-map-marker .customer-map-label {position:absolute;left:20px;bottom:26px;border:1px solid #f6dc82;border-left:4px solid var(--marker-color);background:#0a2238;color:#fff5cf;border-radius:4px 10px 4px 10px;}
.customer-map-target {position:absolute;left:-14px;top:-14px;width:28px;height:28px;box-sizing:border-box;border:2px solid #ffe16b;border-radius:50%;background:radial-gradient(circle,#fff 0 3px,#ffd447 3px 6px,transparent 7px),#071b30;box-shadow:0 0 0 3px #061326,0 0 18px #ffd447bb;pointer-events:none;}
.customer-map-target::before,.customer-map-target::after {content:'';position:absolute;background:#fff2ad;}
.customer-map-target::before {width:40px;height:2px;left:-8px;top:11px;}
.customer-map-target::after {width:2px;height:40px;left:11px;top:-8px;}
.customer-map-leader {position:absolute;left:0;top:0;width:33px;height:2px;background:#ffe16b;transform:rotate(-52deg);transform-origin:left center;pointer-events:none;}
.customer-map-marker:focus-within .customer-map-target,.customer-map-marker:hover .customer-map-target {box-shadow:0 0 0 5px #ffd44744,0 0 24px #ffe16b;}
.customer-map-label {width:210px;min-width:210px;box-sizing:border-box;display:block;text-align:left;color:#e8f5ff;background:#10263af5;border:1px solid #476780;border-radius:10px;padding:8px 10px;box-shadow:0 5px 18px #0005;cursor:pointer;font:12px/1.5 sans-serif;white-space:normal;}
.customer-map-label .customer-map-company {overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.customer-map-label:hover,.customer-map-label:focus-visible {border-color:#79d4e9;background:#183c53;outline:2px solid #79d4e940;}
.customer-map-label strong {display:block;color:#fff2ad;margin-bottom:3px;}
.customer-map-company {border-left:3px solid;padding-left:6px;margin:3px 0;overflow-wrap:anywhere;white-space:normal;}
.customer-map-label small {color:#a6c4d9;}
.customer-map-detail {width:280px;max-height:280px;overflow:auto;color:#16384b;font:13px/1.6 sans-serif;}
.customer-map-detail p,.customer-map-detail small {color:#536c7b;font-size:12px;}
</style>
