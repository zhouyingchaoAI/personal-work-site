<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CrmUnit, CrmPerson, CrmRelation, CrmStaff } from '../../services/personalWorkApi'
import { organizationGraph } from './organizationGraph'
import RelationGraph from './RelationGraph.vue'
import { REGION_COLORS } from './dashboard/chinaMapData'
const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; staff: CrmStaff[]; initialRegion?: string; initialType?: string }>()
const emit = defineEmits<{ select: [id: string, kind: string] }>()
const region = ref(props.initialRegion || ''), type = ref(props.initialType || ''), query = ref('')
const colors: Record<string, string> = {主管单位:'#9a8cff',业主单位:'#f5c242',总包单位:'#23e0d0',设计单位:'#4596ff',厂商:'#f97316',我方:'#f5c242'}
const memberships = (u: CrmUnit) => u.business_regions?.length ? u.business_regions : [u.business_region || '未分区']
const regionUnits = computed(() => props.units.filter(u => !region.value || memberships(u).includes(region.value)))
function counts(units: CrmUnit[]) {
  const ids = new Set(units.map(u => u.id))
  return { units: units.filter(u => !u.organization_level || u.organization_level === 'unit').length, people: props.people.filter(p => ids.has(p.unit_id)).length }
}
const regionCards = computed(() => [...new Set(props.units.flatMap(memberships))].sort().map(name => ({ name, ...counts(props.units.filter(u => memberships(u).includes(name))) })))
const typeCards = computed(() => [...new Set([...Object.keys(colors).filter(t => t !== '我方'), ...regionUnits.value.map(u => u.type || '未分类')])].map(name => ({ name, ...counts(regionUnits.value.filter(u => (u.type || '未分类') === name)) })))
const filtered = computed(() => {
  let units = regionUnits.value.filter(u => !type.value || (u.type || '未分类') === type.value)
  const q = query.value.trim().toLowerCase()
  if (q) {
    const matchingPeople = new Set(props.people.filter(p => `${p.name} ${p.title || ''}`.toLowerCase().includes(q)).map(p => p.unit_id))
    units = units.filter(u => `${u.name} ${u.company_full_name || ''} ${u.region || ''}`.toLowerCase().includes(q) || matchingPeople.has(u.id))
  }
  const ids = new Set(units.map(u => u.id)), people = props.people.filter(p => ids.has(p.unit_id))
  const personIds = new Set(people.map(p => p.id)), relations = props.relations.filter(r => personIds.has(r.person_id))
  const members = new Set(relations.map(r => r.our_member))
  const staffIds = new Set(props.staff.filter(s => members.has(s.member_key)).map(s => s.id))
  const byId = new Map(props.staff.map(s => [s.id, s]))
  for (const id of [...staffIds]) {
    let parent = byId.get(id)?.manager_id
    while (parent && !staffIds.has(parent)) { staffIds.add(parent); parent = byId.get(parent)?.manager_id }
  }
  return { units, people, relations, staff: props.staff.filter(s => staffIds.has(s.id)) }
})
const graph = computed(() => organizationGraph(filtered.value.units, filtered.value.people, filtered.value.staff, filtered.value.relations))
const stats = computed(() => ({ ...counts(filtered.value.units), relations: filtered.value.relations.length,
  warnings: filtered.value.relations.filter(r => r.decay_state !== 'normal').length,
  uncovered: filtered.value.people.filter(p => !filtered.value.relations.some(r => r.person_id === p.id && r.our_member)).length }))
const graphKey = computed(() => JSON.stringify([region.value, type.value, query.value]))
function reset() { region.value = ''; type.value = ''; query.value = '' }
</script>
<template>
  <div class="network-explorer">
    <div class="network-filter" role="group" aria-label="关系网络区域">
      <button :aria-pressed="!region" @click="region = ''">全部区域</button>
      <button v-for="item in regionCards" :key="item.name" :aria-pressed="region === item.name" :style="{ '--filter-color': REGION_COLORS[item.name] || '#86a9c2' }" @click="region = item.name">{{ item.name }} <small>{{ item.units }} 单位 · {{ item.people }} 人</small></button>
    </div>
    <div class="network-filter" role="group" aria-label="关系网络单位类型">
      <button :aria-pressed="!type" @click="type = ''">全部类型</button>
      <button v-for="item in typeCards" :key="item.name" :aria-pressed="type === item.name" :style="{ '--filter-color': colors[item.name] || '#86a9c2' }" @click="type = item.name">{{ item.name }} <small>{{ item.units }} 单位 · {{ item.people }} 人</small></button>
    </div>
    <div class="network-search"><input v-model="query" placeholder="搜索企业、联系人或城市" aria-label="搜索关系网络" /><button @click="reset">重置筛选</button><span>搜索保留命中单位的完整关系；跨区客户可在各归属区域查看。</span></div>
    <div class="network-stats" aria-live="polite"><span>客户单位 <b>{{ stats.units }}</b></span><span>联系人 <b>{{ stats.people }}</b></span><span>关系 <b>{{ stats.relations }}</b></span><span>待维系 <b>{{ stats.warnings }}</b></span><span>未指派对接 <b>{{ stats.uncovered }}</b></span></div>
    <RelationGraph v-if="filtered.units.length || filtered.people.length" :key="graphKey" :organization-graph="graph" :nodes="graph.nodes" :edges="graph.edges" :type-color="colors" :highlight-path="[]" :hidden-types="[]" :only-gaps="false" @select="(id, kind) => emit('select', id, kind)" />
    <div v-else class="network-empty">当前筛选下暂无客户关系。<button @click="reset">查看全部</button></div>
  </div>
</template>
<style scoped>
.network-explorer{display:flex;flex-direction:column;flex:1;min-height:0;gap:8px;overflow:auto;}
.network-filter{display:flex;flex-wrap:wrap;gap:6px;}
.network-filter button,.network-search button,.network-empty button{border:1px solid #345872;border-radius:6px;background:#102c42;color:#c9deef;padding:7px 10px;cursor:pointer;}
.network-filter button{border-left:3px solid var(--filter-color,#23e0d0);}
.network-filter button[aria-pressed=true]{background:#205273;border-color:var(--filter-color,#23e0d0);color:white;}
.network-filter small{margin-left:6px;opacity:.8;}
.network-search{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
.network-search input{background:#0b2337;color:white;border:1px solid #345872;padding:8px;border-radius:5px;min-width:230px;}
.network-search span{color:#91adc5;font-size:12px;}
.network-stats{display:flex;gap:20px;flex-wrap:wrap;color:#b7d0e5;font-size:13px;}.network-stats b{color:#5fe2e2;margin-left:6px;font-size:18px;}
.network-empty{margin:auto;color:#a6bfd3;display:flex;gap:16px;align-items:center;}
.network-explorer :deep(.rg-wrap){flex:1;min-height:300px;display:flex;flex-direction:column;}
.network-explorer :deep(.radial-org){flex:1;min-height:300px;height:auto;}
.network-explorer :deep(.rg-svg){flex:1;min-height:300px;height:100%;}
</style>
