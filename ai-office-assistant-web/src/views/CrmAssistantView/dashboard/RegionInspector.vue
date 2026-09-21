<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import type { CrmUnit, CrmPerson } from '../../../services/personalWorkApi'
import { REGION_COLORS } from './chinaMapData'
import { cityProvince } from './cityProvince'

type RegionStat = { name: string }
const props = defineProps<{ scope?: string; units: CrmUnit[]; people: CrmPerson[]; regions: RegionStat[] }>()
const emit = defineEmits<{ close: [] }>()

const mappedRegions = ['东区', '中区', '广东区', '西区']
const unitTypes = ['主管单位', '业主单位', '总包单位', '设计单位', '厂商']
const typeColor: Record<string, string> = { 主管单位: '#9a8cff', 业主单位: '#f5c242', 总包单位: '#23e0d0', 设计单位: '#4596ff', 厂商: '#f97316' }

function customerUnit(u: CrmUnit) { return !u.organization_level || u.organization_level === 'unit' }
function unitRegions(u: CrmUnit): string[] {
  const rs = Array.isArray(u.business_regions) ? u.business_regions.filter(Boolean) : []
  if (rs.length) return [...new Set(rs)]
  return u.business_region ? [u.business_region] : []
}

const displayNames = computed(() => {
  const authorized = props.regions.length ? new Set(props.regions.map(r => r.name)) : null
  return mappedRegions.filter(name => !authorized || authorized.has(name))
})

type Cell = { units: number; contacts: number; cities: string[]; provinces: string[] }
function aggregate(units: CrmUnit[]): Cell {
  const unitIds = new Set(units.map(u => u.id))
  const cities = [...new Set(units.map(u => (u.region || '').trim()).filter(Boolean))].sort()
  const provinces = [...new Set(units.map(u => cityProvince(u.region)).filter(Boolean))].sort()
  const contacts = props.people.filter(p => unitIds.has(p.unit_id)).length
  return { units: units.filter(customerUnit).length, contacts, cities, provinces }
}

const summaries = computed(() => displayNames.value.map(name => {
  const regionUnits = props.units.filter(u => unitRegions(u).includes(name))
  const rows = unitTypes.map(type => ({ type, ...aggregate(regionUnits.filter(u => u.type === type)) }))
  return { name, total: aggregate(regionUnits), rows }
}))
const hasUnknownCity = computed(() =>
  props.units.some(u => (u.region || '').trim() && !cityProvince(u.region))
)

function esc(e: KeyboardEvent) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', esc))
onBeforeUnmount(() => window.removeEventListener('keydown', esc))
</script>

<template>
  <Teleport to="body">
    <section class="region-inspector" role="dialog" aria-modal="true" aria-label="区域数据明细" @click.self="emit('close')">
      <div class="ri-card">
        <header>
          <div>
            <h2>区域数据明细</h2>
            <small>{{ scope || '当前授权范围' }} · 按单位类型查看城市与省份覆盖</small>
          </div>
          <button class="ri-close" @click="emit('close')">关闭 <em>Esc</em></button>
        </header>
        <div class="ri-scroll">
          <p v-if="!summaries.length" class="ri-empty">暂无可展示的经营区域数据。</p>
          <section v-for="region in summaries" :key="region.name" class="ri-region" :style="{ '--rc': REGION_COLORS[region.name] }">
            <div class="ri-region-head">
              <span class="ri-dot" />
              <h3>{{ region.name }}</h3>
              <p class="ri-region-total">
                <b>{{ region.total.units }}</b> 单位 · <b>{{ region.total.cities.length }}</b> 城市 · <b>{{ region.total.provinces.length }}</b> 省份 · <b>{{ region.total.contacts }}</b> 联系人
              </p>
            </div>
            <table>
              <thead>
                <tr><th>单位类型</th><th>单位</th><th>城市</th><th>省份</th><th>联系人</th><th class="ri-detail-col">覆盖省份 / 城市</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in region.rows" :key="row.type" :class="{ 'ri-zero': !row.units && !row.contacts }">
                  <td><i :style="{ background: typeColor[row.type] }" />{{ row.type }}</td>
                  <td class="ri-num">{{ row.units }}</td>
                  <td class="ri-num">{{ row.cities.length }}</td>
                  <td class="ri-num">{{ row.provinces.length }}</td>
                  <td class="ri-num">{{ row.contacts }}</td>
                  <td class="ri-detail">
                    <span v-if="row.provinces.length" class="ri-prov-list">{{ row.provinces.join('、') }}</span>
                    <span v-if="row.cities.length" class="ri-city-list">{{ row.cities.join('、') }}</span>
                    <span v-if="!row.cities.length && !row.provinces.length" class="ri-none">—</span>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr>
                  <td>合计</td>
                  <td class="ri-num">{{ region.total.units }}</td>
                  <td class="ri-num">{{ region.total.cities.length }}</td>
                  <td class="ri-num">{{ region.total.provinces.length }}</td>
                  <td class="ri-num">{{ region.total.contacts }}</td>
                  <td class="ri-detail"><span class="ri-prov-list">{{ region.total.provinces.join('、') || '—' }}</span></td>
                </tr>
              </tfoot>
            </table>
          </section>
          <p v-if="hasUnknownCity" class="ri-foot-note">注：部分单位填写的城市无法匹配到省级区划，未计入省份统计。</p>
        </div>
      </div>
    </section>
  </Teleport>
</template>

<style scoped lang="scss">
.region-inspector { position: fixed; inset: 0; z-index: 2100; display: grid; place-items: center; padding: 4vh 4vw; background: #020b17df }
.ri-card { width: min(1180px, 94vw); max-height: 92vh; display: flex; flex-direction: column; padding: 18px 20px; border: 1px solid #3e8bad; border-radius: 14px; background: #071a2d; box-shadow: 0 0 60px #2fbfdb4d; color: #dceaf6 }
.ri-card > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 12px }
.ri-card h2 { margin: 0; font-size: 20px; color: #eaf6ff }
.ri-card header small { display: block; margin-top: 4px; color: #8db2cd; font-size: 12px }
.ri-close { border: 1px solid #3c7698; border-radius: 6px; background: #123653; padding: 8px 13px; color: #d6f6fb; cursor: pointer; white-space: nowrap; em { color: #7fa6bd; font-style: normal; margin-left: 8px } }
.ri-scroll { overflow: auto; min-height: 0; display: flex; flex-direction: column; gap: 18px; padding-right: 4px }
.ri-empty { color: #8db2cd; font-size: 13px }
.ri-region { border: 1px solid #274a68; border-radius: 10px; padding: 12px 14px; background: linear-gradient(120deg, #0d2b48aa, #081d33aa) }
.ri-region-head { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; flex-wrap: wrap }
.ri-dot { width: 11px; height: 11px; border-radius: 50%; background: var(--rc); box-shadow: 0 0 10px var(--rc) }
.ri-region-head h3 { margin: 0; font-size: 16px; color: #eef7ff }
.ri-region-total { margin: 0 0 0 auto; font-size: 12px; color: #a7c4dd; b { color: #63e2df; font-size: 16px; margin: 0 2px; font-variant-numeric: tabular-nums } }
table { width: 100%; border-collapse: collapse; font-size: 12px }
th, td { text-align: left; padding: 7px 9px; border-bottom: 1px solid #21415c }
thead th { color: #90b3ce; font-weight: 500; font-size: 11px }
tbody td:first-child, tfoot td:first-child { display: flex; align-items: center; gap: 7px; i { width: 8px; height: 8px; border-radius: 2px; display: inline-block } }
.ri-num { text-align: right; font-variant-numeric: tabular-nums; color: #d7ecff; width: 58px }
.ri-detail-col { width: 46% }
.ri-detail { color: #9fbcd6; line-height: 1.6 }
.ri-prov-list { color: #cfe6ff }
.ri-city-list { display: block; color: #7f9cb6; font-size: 11px; margin-top: 2px }
.ri-zero { opacity: 0.5 }
.ri-none { color: #5f7d97 }
tfoot td { font-weight: 600; color: #eaf6ff; border-top: 1px solid #2f5878; border-bottom: 0 }
.ri-foot-note { margin: 0; font-size: 11px; color: #8aa6c0 }
@media (max-width: 720px) {
  .ri-detail-col, .ri-detail { display: none }
  .ri-region-total { margin: 4px 0 0; flex-basis: 100% }
}
</style>
