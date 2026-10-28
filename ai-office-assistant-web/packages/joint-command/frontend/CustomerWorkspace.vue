<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CrmOpportunity, CrmPerson, CrmPlaybook, CrmRelation, CrmUnit } from '../../../src/services/personalWorkApi'
import { customerPortfolios } from './customerWorkspace'
import { bizIcon as ic } from './businessIcons'
const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups']; canRecord: boolean; canWrite: boolean }>()
const emit = defineEmits<{ createOpportunity: [unitId: string]; person: [id: string]; record: [relation: CrmRelation]; opportunity: [item: CrmOpportunity] }>()
const query = ref(''), page = ref(1), selected = ref(''), section = ref('overview')
type Portfolio = ReturnType<typeof customerPortfolios>[number]
const portfolios = computed(() => customerPortfolios(props.units, props.people, props.relations, props.opportunities))

// 五类客户单位：固定顺序与配色，与驾驶舱五位一体保持一致；未识别的类型归入“其他”。
const TYPES = [
  { key: '主管单位', short: '主管', color: '#7c5cff' }, { key: '业主单位', short: '业主', color: '#f0a020' },
  { key: '总包单位', short: '总包', color: '#10b39b' }, { key: '设计单位', short: '设计', color: '#2f7bea' },
  { key: '厂商', short: '厂商', color: '#f26b3a' }, { key: '运营单位', short: '运营', color: '#0ea5e9' },
]
const typeOf = (g: Portfolio) => TYPES.find(t => t.key === g.unit.type) || { key: g.unit.type || '其他', short: (g.unit.type || '其他').replace('单位', ''), color: '#94a3b8' }
const regionOf = (g: Portfolio) => (g.unit.business_regions?.length ? g.unit.business_regions : [g.unit.business_region || '']).filter(Boolean)
const health = (g: Portfolio) => {
  const warn = g.relations.filter(r => r.decay_state === 'warning').length, alarm = g.relations.filter(r => r.decay_state === 'alarm').length
  const linked = new Set(g.relations.map(r => r.person_id))
  return { normal: g.relations.length - warn - alarm, warn, alarm, single: g.relations.filter(r => r.single_point_risk).length, gap: g.people.filter(p => !linked.has(p.id)).length }
}
const lastTouch = (g: Portfolio) => g.relations.reduce((m, r) => (r.last_touch || '') > m ? r.last_touch : m, '')
const openOpps = (g: Portfolio) => g.opportunities.filter(o => !o.cancelled && (!o.outcome || o.outcome === 'open')).length

// ---- 交互筛选：类型、区域、关注项、排序、视图 ----
const typeFilter = ref(''), regionFilter = ref(''), focus = ref<'' | 'attention' | 'opportunity' | 'gap'>(''), sortBy = ref('attention'), view = ref<'card' | 'list'>('card')
const matchesText = (g: Portfolio) => { const q = query.value.trim().toLowerCase(); return !q || [g.unit.name, ...g.units.map(u => u.name), ...g.people.map(p => p.name)].join(' ').toLowerCase().includes(q) }
const base = computed(() => portfolios.value.filter(g => matchesText(g) && (!regionFilter.value || regionOf(g).includes(regionFilter.value))))
const typeCounts = computed(() => { const m = new Map<string, number>(); for (const g of base.value) m.set(typeOf(g).key, (m.get(typeOf(g).key) || 0) + 1); return m })
const typeChips = computed(() => [...TYPES.map(t => ({ ...t, count: typeCounts.value.get(t.key) || 0 })),
  ...[...typeCounts.value.entries()].filter(([k]) => !TYPES.some(t => t.key === k)).map(([k, count]) => ({ key: k, short: k.replace('单位', ''), color: '#94a3b8', count }))])
const regions = computed(() => [...new Set(portfolios.value.flatMap(regionOf))].sort((a, b) => a.localeCompare(b, 'zh-CN')))
const focusTest = { attention: (g: Portfolio) => { const h = health(g); return h.warn + h.alarm > 0 }, opportunity: (g: Portfolio) => g.opportunities.length > 0, gap: (g: Portfolio) => health(g).gap > 0 || g.relations.length === 0 }
const filtered = computed(() => {
  const list = base.value.filter(g => (!typeFilter.value || typeOf(g).key === typeFilter.value) && (!focus.value || focusTest[focus.value](g)))
  const score = (g: Portfolio) => { const h = health(g); return h.alarm * 3 + h.warn * 2 + h.single }
  const sorters: Record<string, (a: Portfolio, b: Portfolio) => number> = {
    attention: (a, b) => score(b) - score(a), people: (a, b) => b.people.length - a.people.length,
    opportunity: (a, b) => b.opportunities.length - a.opportunities.length, recent: (a, b) => lastTouch(b).localeCompare(lastTouch(a)), name: () => 0,
  }
  return [...list].sort((a, b) => sorters[sortBy.value](a, b) || a.unit.name.localeCompare(b.unit.name, 'zh-CN'))
})
const pageSize = computed(() => view.value === 'card' ? 24 : 20)
const rows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const kpis = computed(() => {
  const list = base.value
  return {
    customers: list.length, people: list.reduce((s, g) => s + g.people.length, 0),
    opportunity: list.filter(focusTest.opportunity).length, opps: list.reduce((s, g) => s + g.opportunities.length, 0),
    attention: list.filter(focusTest.attention).length, warn: list.reduce((s, g) => s + health(g).warn + health(g).alarm, 0),
    gap: list.filter(focusTest.gap).length, gapPeople: list.reduce((s, g) => s + health(g).gap, 0),
  }
})
const toggleFocus = (v: typeof focus.value) => { focus.value = focus.value === v ? '' : v }
const toggleType = (v: string) => { typeFilter.value = typeFilter.value === v ? '' : v }
const hasFilter = computed(() => !!(query.value || typeFilter.value || regionFilter.value || focus.value))
function clearFilters() { query.value = ''; typeFilter.value = ''; regionFilter.value = ''; focus.value = '' }
const highlight = (text: string) => { const q = query.value.trim(); if (!q) return esc(text); const i = text.toLowerCase().indexOf(q.toLowerCase()); return i < 0 ? esc(text) : esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length)) }
const esc = (t: string) => t.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))
const pct = (n: number, total: number) => total ? `${(n / total) * 100}%` : '0%'

const current = computed(() => portfolios.value.find(g => g.unit.id === selected.value))
const currentHealth = computed(() => current.value ? health(current.value) : null)
const open = computed({get:()=>!!current.value, set:(value:boolean)=>{if(!value)selected.value=''}})
const unlinked = computed(() => { const ids = new Set(props.units.map(u=>u.id)); return props.opportunities.filter(o=>!o.owner_unit_id || !ids.has(o.owner_unit_id)).length })
const relationByPerson = computed(() => {
  const map = new Map<string,CrmRelation[]>()
  for (const relation of current.value?.relations || []) map.set(relation.person_id,[...(map.get(relation.person_id)||[]),relation])
  return map
})
const tasks = computed(() => { const ids = new Set(current.value?.relations.map(r=>r.id)); return props.followups.filter(t=>ids.has(t.relation_id)) })
const history = computed(() => (current.value?.relations || []).flatMap(relation => (relation.actions || []).filter(a => (a as {record_kind?:string}).record_kind !== 'plan').map(action => ({action,relation}))).sort((a,b)=>(b.action.happened_at||'').localeCompare(a.action.happened_at||'')))
const contactPage = ref(1), historyPage = ref(1)
function show(id:string) { selected.value=id;section.value='overview';contactPage.value=1;historyPage.value=1 }
function person(id:string) { selected.value='';emit('person',id) }
function record(relation:CrmRelation) { selected.value='';emit('record',relation) }
function opportunity(item:CrmOpportunity) { selected.value='';emit('opportunity',item) }
function createOpportunity() { const id=current.value?.unit.id; if(id){selected.value='';emit('createOpportunity',id)} }
const decayLabel = { normal: '正常', warning: '预警', alarm: '告警' } as const
watch([query, typeFilter, regionFilter, focus, sortBy, view], () => { page.value = 1 })
</script>
<template>
 <section class="customer-workspace">
  <div class="cw-kpis" role="group" aria-label="客户总览指标">
   <button type="button" class="cw-kpi k-all" :class="{ on: !focus }" @click="focus = ''"><i v-html="ic('results')"></i><span>客户</span><b>{{ kpis.customers }}</b><small>{{ kpis.people }} 位联系人</small></button>
   <button type="button" class="cw-kpi k-opp" :class="{ on: focus === 'opportunity' }" :aria-pressed="focus === 'opportunity'" @click="toggleFocus('opportunity')"><i v-html="ic('target')"></i><span>有关联商机</span><b>{{ kpis.opportunity }}</b><small>共 {{ kpis.opps }} 个商机</small></button>
   <button type="button" class="cw-kpi k-warn" :class="{ on: focus === 'attention' }" :aria-pressed="focus === 'attention'" @click="toggleFocus('attention')"><i v-html="ic('flag')"></i><span>需要维系</span><b>{{ kpis.attention }}</b><small>{{ kpis.warn }} 条关系预警 / 告警</small></button>
   <button type="button" class="cw-kpi k-gap" :class="{ on: focus === 'gap' }" :aria-pressed="focus === 'gap'" @click="toggleFocus('gap')"><i v-html="ic('allocation')"></i><span>对接缺口</span><b>{{ kpis.gap }}</b><small>{{ kpis.gapPeople }} 位联系人未建立对接</small></button>
  </div>

  <div class="cw-types" role="group" aria-label="五类客户单位筛选">
   <button type="button" :class="{ on: !typeFilter }" @click="typeFilter = ''">全部<em>{{ base.length }}</em></button>
   <button v-for="t in typeChips" :key="t.key" type="button" :class="{ on: typeFilter === t.key, empty: !t.count }" :style="{ '--c': t.color }" :aria-pressed="typeFilter === t.key" :disabled="!t.count && typeFilter !== t.key" @click="toggleType(t.key)"><i></i>{{ t.key }}<em>{{ t.count }}</em></button>
  </div>

  <div class="cw-toolbar">
   <el-input v-model="query" clearable placeholder="搜索客户、下属组织或联系人" aria-label="搜索客户总览"><template #prefix><i class="cw-ic" v-html="ic('zoom')"></i></template></el-input>
   <el-select v-model="regionFilter" clearable placeholder="全部经营区域" aria-label="经营区域筛选" style="width:150px"><el-option v-for="r in regions" :key="r" :label="r" :value="r" /></el-select>
   <el-select v-model="sortBy" aria-label="排序方式" style="width:150px">
    <el-option label="待维系优先" value="attention" /><el-option label="联系人最多" value="people" /><el-option label="商机最多" value="opportunity" /><el-option label="最近互动" value="recent" /><el-option label="名称" value="name" />
   </el-select>
   <span class="cw-count">{{ filtered.length }} 家客户 · 授权可见组织及下级<el-button v-if="hasFilter" link type="primary" @click="clearFilters">清除筛选</el-button></span>
   <el-radio-group v-model="view" size="small" class="cw-view" aria-label="显示方式"><el-radio-button value="card">卡片</el-radio-button><el-radio-button value="list">列表</el-radio-button></el-radio-group>
  </div>
  <p v-if="unlinked" class="cw-note cw-banner"><i class="cw-ic" v-html="ic('info')"></i>{{ unlinked }} 个商机尚未明确关联可见客户，暂不计入客户汇总；可在商机编辑中确认。</p>

  <div v-if="view === 'card'" class="cw-grid">
   <el-empty v-if="!rows.length" description="暂无匹配客户" :image-size="64"><el-button v-if="hasFilter" @click="clearFilters">清除筛选</el-button></el-empty>
   <article v-for="g in rows" :key="g.unit.id" class="cw-card" :style="{ '--c': typeOf(g).color }" tabindex="0" role="button" :aria-label="`查看 ${g.unit.name}`" @click="show(g.unit.id)" @keydown.enter="show(g.unit.id)">
    <header>
     <span class="cw-type" @click.stop="toggleType(typeOf(g).key)" :title="`只看${typeOf(g).key}`">{{ typeOf(g).short }}</span>
     <div class="cw-name"><strong v-html="highlight(g.unit.name)"></strong><small>{{ regionOf(g).join(' / ') || '未分区' }} · {{ g.units.length }} 个组织节点</small></div>
     <span v-if="health(g).alarm" class="cw-flag alarm">告警</span><span v-else-if="health(g).warn" class="cw-flag warn">预警</span>
    </header>
    <div class="cw-stats">
     <div><b>{{ g.people.length }}</b><span>联系人</span></div>
     <div><b>{{ g.relations.length }}</b><span>对接关系</span></div>
     <div :class="{ hot: openOpps(g) }"><b>{{ g.opportunities.length }}</b><span>关联商机</span></div>
    </div>
    <div class="cw-health" :title="`正常 ${health(g).normal} · 预警 ${health(g).warn} · 告警 ${health(g).alarm}`">
     <div class="cw-bar"><i class="n" :style="{ width: pct(health(g).normal, g.relations.length) }"></i><i class="w" :style="{ width: pct(health(g).warn, g.relations.length) }"></i><i class="a" :style="{ width: pct(health(g).alarm, g.relations.length) }"></i></div>
     <small v-if="g.relations.length">关系健康 · 正常 {{ health(g).normal }} · 待维系 {{ health(g).warn + health(g).alarm }}</small><small v-else class="gap">尚未建立对接关系</small>
    </div>
    <footer>
     <span v-if="health(g).single" class="chip r">单点 {{ health(g).single }}</span><span v-if="health(g).gap" class="chip o">未对接 {{ health(g).gap }} 人</span>
     <span class="last">{{ lastTouch(g) ? `最近互动 ${lastTouch(g).slice(0, 10)}` : '暂无互动' }}</span>
     <el-button link type="primary" @click.stop="show(g.unit.id)">查看客户</el-button>
    </footer>
   </article>
  </div>

  <el-table v-else :data="rows" empty-text="暂无匹配客户" class="cw-table" @row-click="(row: Portfolio) => show(row.unit.id)">
   <el-table-column label="客户" min-width="260"><template #default="{row}"><div class="cw-cell"><span class="cw-type sm" :style="{ '--c': typeOf(row).color }">{{ typeOf(row).short }}</span><div><el-button link type="primary" @click.stop="show(row.unit.id)"><span v-html="highlight(row.unit.name)"></span></el-button><small>{{ regionOf(row).join(' / ') || '未分区' }} · {{ row.units.length }} 个组织节点</small></div></div></template></el-table-column>
   <el-table-column label="联系人" width="90" align="center"><template #default="{row}">{{ row.people.length }}</template></el-table-column>
   <el-table-column label="已关联商机" width="110" align="center"><template #default="{row}"><b :class="{ 'cw-hot': row.opportunities.length }">{{ row.opportunities.length }}</b></template></el-table-column>
   <el-table-column label="关系健康" min-width="190"><template #default="{row}"><div class="cw-bar"><i class="n" :style="{ width: pct(health(row).normal, row.relations.length) }"></i><i class="w" :style="{ width: pct(health(row).warn, row.relations.length) }"></i><i class="a" :style="{ width: pct(health(row).alarm, row.relations.length) }"></i></div><small>{{ row.relations.length ? `正常 ${health(row).normal} · 预警 ${health(row).warn} · 告警 ${health(row).alarm}` : '尚未建立对接关系' }}</small></template></el-table-column>
   <el-table-column label="待维系关系" width="110" align="center"><template #default="{row}"><b :class="{ 'cw-warn': health(row).warn + health(row).alarm }">{{ health(row).warn + health(row).alarm }}</b></template></el-table-column>
   <el-table-column label="最近互动" width="120"><template #default="{row}">{{ lastTouch(row).slice(0, 10) || '—' }}</template></el-table-column>
   <el-table-column label="操作" width="100"><template #default="{row}"><el-button link type="primary" @click.stop="show(row.unit.id)">查看客户</el-button></template></el-table-column>
  </el-table>
  <el-pagination v-if="filtered.length>pageSize" v-model:current-page="page" :page-size="pageSize" :total="filtered.length" layout="prev, pager, next, total" />
  <el-drawer v-model="open" :title="current?.unit.name || '客户详情'" size="min(860px,96vw)" append-to-body destroy-on-close class="customer-workspace-drawer">
   <template v-if="current">
    <el-radio-group v-model="section" aria-label="客户详情视图"><el-radio-button value="overview">概况</el-radio-button><el-radio-button value="contacts">联系人</el-radio-button><el-radio-button value="activity">动态</el-radio-button></el-radio-group>
    <section v-if="section==='overview'" class="cw-detail">
     <div class="cw-dhead" :style="{ '--c': typeOf(current).color }"><span class="cw-type">{{ typeOf(current).short }}</span><div><strong>{{ current.unit.type || '类型待补充' }}</strong><small>{{ regionOf(current).join(' / ') || '未分区' }} · {{ current.units.length }} 个组织节点 · {{ lastTouch(current) ? `最近互动 ${lastTouch(current).slice(0, 10)}` : '暂无互动' }}</small></div></div>
     <div v-if="currentHealth" class="cw-dstats">
      <button type="button" @click="section='contacts'"><b>{{ current.people.length }}</b><span>联系人</span></button>
      <button type="button" @click="section='contacts'"><b>{{ current.relations.length }}</b><span>对接关系</span></button>
      <div class="ok"><b>{{ currentHealth.normal }}</b><span>正常</span></div>
      <div :class="{ warn: currentHealth.warn + currentHealth.alarm }"><b>{{ currentHealth.warn + currentHealth.alarm }}</b><span>待维系</span></div>
      <div :class="{ risk: currentHealth.single }"><b>{{ currentHealth.single }}</b><span>单点风险</span></div>
      <button type="button" :class="{ risk: currentHealth.gap }" @click="section='contacts'"><b>{{ currentHealth.gap }}</b><span>未对接</span></button>
     </div>
     <div class="cw-section-head"><h3>关联商机</h3><el-button type="primary" :disabled="!canWrite" @click="createOpportunity">新建商机</el-button></div><p class="cw-note">仅汇总已确认客户关联的商机，包含下级组织。</p>
     <el-empty v-if="!current.opportunities.length" description="暂无已确认关联的商机" :image-size="48" />
     <article v-for="o in current.opportunities" :key="`${o._owner || ''}-${o.id}`" class="cw-item"><div><strong>{{ o.name }}</strong><small>{{ o.sales_stage || '销售阶段待确认' }} · {{ o.manager || '负责人待补充' }}</small></div><el-button link type="primary" @click="opportunity(o)">查看商机</el-button></article>
     <h3>下一步</h3><p v-if="!tasks.length" class="cw-note">暂无待跟进计划</p>
     <article v-for="t in tasks.slice(0,8)" :key="t.id" class="cw-item"><div><strong>{{ t.next_step }}</strong><small>{{ t.person_name }} · {{ t.owner_label || t.owner || '负责人待补充' }} · {{ t.due_date || '日期待补充' }}</small></div><el-tag v-if="t.overdue" type="danger">逾期</el-tag></article>
     <el-button v-if="tasks.length>8" link type="primary" @click="section='activity'">查看全部 {{ tasks.length }} 项计划</el-button>
    </section>
    <section v-else-if="section==='contacts'" class="cw-detail">
     <el-empty v-if="!current.people.length" description="暂无联系人" :image-size="48"/>
     <article v-for="p in current.people.slice((contactPage-1)*20,contactPage*20)" :key="p.id" class="cw-contact"><div><strong>{{ p.name }}</strong><small>{{ p.unit_name || units.find(u=>u.id===p.unit_id)?.name }} · {{ p.department || p.title || '岗位待补充' }}</small><small>{{ p.mobile || p.office_phone || p.email || '联系方式待补充' }}</small></div><el-button link type="primary" @click="person(p.id)">查看档案</el-button><div class="cw-relations"><template v-if="relationByPerson.get(p.id)?.length"><div v-for="r in relationByPerson.get(p.id)" :key="r.id"><span>对接：{{ r.our_staff?.name || r.our_member_label || r.our_member || '待指派' }}<em class="cw-decay" :class="r.decay_state">{{ decayLabel[r.decay_state] || '正常' }}</em><em v-if="r.single_point_risk" class="cw-decay alarm">单点</em></span><el-button link type="primary" :disabled="!canRecord" @click="record(r)">记录跟进</el-button></div></template><small v-else>尚未建立对接关系，请在联系人档案中维护。</small></div></article>
     <el-pagination v-if="current.people.length>20" v-model:current-page="contactPage" :page-size="20" :total="current.people.length" layout="prev, pager, next, total" />
    </section>
    <section v-else class="cw-detail">
     <details v-if="tasks.length"><summary>待办计划（{{ tasks.length }}），不计入真实互动</summary><article v-for="t in tasks" :key="t.id" class="cw-item"><div>{{ t.next_step }}<small>{{ t.person_name }} · {{ t.due_date || '日期待补充' }}</small></div></article></details>
     <h3>互动记录</h3><el-empty v-if="!history.length" description="暂无互动记录" :image-size="48" />
     <article v-for="item in history.slice((historyPage-1)*20,historyPage*20)" :key="`${item.relation.id}-${item.action.id}`" class="cw-history"><small>{{ item.action.happened_at || '日期待补充' }} · {{ item.relation.person_name }} · {{ item.action.type }}</small><p>{{ item.action.intel || '未填写沟通结果' }}</p><small v-if="item.action.project_id">商机：{{ item.action.project_id }}</small></article>
     <el-pagination v-if="history.length>20" v-model:current-page="historyPage" :page-size="20" :total="history.length" layout="prev, pager, next, total" />
    </section>
   </template>
  </el-drawer>
 </section>
</template>
<style scoped>
.customer-workspace{--bd:#dde7f5;--muted:#64748b;--ink:#14213d;--pri:#15499c}
.cw-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}
.cw-kpi{position:relative;display:grid;grid-template-columns:40px 1fr;grid-template-rows:auto auto auto;column-gap:12px;align-items:center;text-align:left;padding:14px 16px;border:1px solid #dde7f5;border-radius:14px;background:linear-gradient(180deg,#fff,#f8fbff);cursor:pointer;font:inherit;color:#14213d;transition:box-shadow .15s,border-color .15s,transform .15s}
.cw-kpi:hover{transform:translateY(-1px);box-shadow:0 10px 24px -16px #15499c66}
.cw-kpi i{grid-row:1/4;width:40px;height:40px;border-radius:12px;display:grid;place-items:center;color:#fff;background:linear-gradient(135deg,var(--k1),var(--k2))}.cw-kpi i :deep(svg){width:22px;height:22px}
.cw-kpi span{font-size:13px;color:#64748b}.cw-kpi b{font-size:26px;line-height:1.15;font-weight:700;color:var(--k1)}.cw-kpi small{font-size:12px;color:#64748b;margin:0}
.cw-kpi.on{border-color:var(--k1);box-shadow:0 0 0 2px color-mix(in srgb,var(--k1) 22%,transparent)}
.k-all{--k1:#15499c;--k2:#2f7bea}.k-opp{--k1:#0e7490;--k2:#22b8cf}.k-warn{--k1:#d97706;--k2:#f59e0b}.k-gap{--k1:#dc2626;--k2:#f87171}
.cw-types{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.cw-types button{display:inline-flex;align-items:center;gap:7px;height:32px;padding:0 12px;border:1px solid #dde7f5;border-radius:99px;background:#fff;color:#334155;font:inherit;font-size:13px;cursor:pointer;transition:all .15s}
.cw-types button i{width:8px;height:8px;border-radius:50%;background:var(--c,#15499c)}
.cw-types button em{font-style:normal;font-size:12px;color:#64748b;background:#f1f5f9;border-radius:99px;padding:0 7px;line-height:18px}
.cw-types button:hover:not(:disabled){border-color:var(--c,#15499c);color:var(--c,#15499c)}
.cw-types button.on{background:var(--c,#15499c);border-color:var(--c,#15499c);color:#fff}.cw-types button.on i{background:#fff}.cw-types button.on em{background:#ffffff33;color:#fff}
.cw-types button.empty{opacity:.45;cursor:default}
.cw-toolbar{display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap}.cw-toolbar .el-input{max-width:340px}
.cw-count{color:#64748b;font-size:13px;display:inline-flex;align-items:center;gap:8px}.cw-view{margin-left:auto}
.cw-ic{display:inline-grid;width:15px;height:15px}.cw-ic :deep(svg){width:15px;height:15px}
.cw-banner{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:10px;background:#f4f8ff;border:1px solid #dbe7fb;margin:0 0 12px}
.cw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.cw-grid>.el-empty{grid-column:1/-1}
.cw-card{position:relative;display:flex;flex-direction:column;gap:12px;padding:16px 16px 12px;border:1px solid #dde7f5;border-radius:14px;background:#fff;cursor:pointer;overflow:hidden;transition:transform .15s,box-shadow .15s,border-color .15s}
.cw-card:before{content:'';position:absolute;left:0;top:0;right:0;height:3px;background:var(--c)}
.cw-card:hover,.cw-card:focus-visible{transform:translateY(-2px);border-color:color-mix(in srgb,var(--c) 45%,#dde7f5);box-shadow:0 16px 30px -20px #15499c80;outline:none}
.cw-card header{display:flex;gap:10px;align-items:flex-start}
.cw-type{flex:none;display:grid;place-items:center;width:38px;height:38px;border-radius:10px;font-size:13px;font-weight:700;color:var(--c);background:color-mix(in srgb,var(--c) 12%,#fff);border:1px solid color-mix(in srgb,var(--c) 30%,#fff);cursor:pointer}
.cw-type.sm{width:32px;height:28px;font-size:12px;border-radius:8px;cursor:default}
.cw-name{min-width:0;flex:1}.cw-name strong{display:block;font-size:15px;color:#14213d;line-height:1.4;overflow-wrap:anywhere}.cw-name small{margin-top:3px}
.cw-name :deep(mark),.cw-cell :deep(mark){background:#fde68a;color:inherit;border-radius:3px;padding:0 1px}
.cw-flag{flex:none;font-size:12px;padding:2px 8px;border-radius:99px;font-weight:600}.cw-flag.warn{color:#b45309;background:#fef3c7}.cw-flag.alarm{color:#b91c1c;background:#fee2e2}
.cw-stats{display:grid;grid-template-columns:repeat(3,1fr);border-radius:10px;background:#f6f9fe;border:1px solid #e8eff9}
.cw-stats div{text-align:center;padding:8px 4px}.cw-stats div+div{border-left:1px solid #e3ebf7}.cw-stats b{display:block;font-size:20px;color:#14213d;line-height:1.2}.cw-stats span{font-size:12px;color:#64748b}.cw-stats .hot b{color:#0e7490}
.cw-bar{display:flex;height:7px;border-radius:99px;background:#eef2f7;overflow:hidden}.cw-bar i{display:block;height:100%}.cw-bar .n{background:#22c55e}.cw-bar .w{background:#f59e0b}.cw-bar .a{background:#ef4444}
.cw-health small{margin-top:6px}.cw-health .gap{color:#b45309}
.cw-card footer{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding-top:10px;border-top:1px dashed #e3ebf7}
.chip{font-size:12px;padding:1px 8px;border-radius:99px}.chip.r{color:#b91c1c;background:#fee2e2}.chip.o{color:#b45309;background:#fef3c7}
.last{font-size:12px;color:#64748b;margin-left:auto}
.cw-cell{display:flex;gap:10px;align-items:center}.cw-cell small{margin-top:2px}
.cw-hot{color:#0e7490}.cw-warn{color:#d97706}
.cw-table :deep(.el-table__row){cursor:pointer}
.cw-dhead{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:12px;background:color-mix(in srgb,var(--c) 7%,#fff);border:1px solid color-mix(in srgb,var(--c) 22%,#fff)}.cw-dhead strong{font-size:15px}
.cw-dstats{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px}
.cw-dstats>*{border:1px solid #dde7f5;border-radius:10px;background:#fff;padding:10px 4px;text-align:center;font:inherit;color:#14213d}.cw-dstats button{cursor:pointer}.cw-dstats button:hover{border-color:#15499c}
.cw-dstats b{display:block;font-size:20px}.cw-dstats span{font-size:12px;color:#64748b}.cw-dstats .ok b{color:#16a34a}.cw-dstats .warn b{color:#d97706}.cw-dstats .risk b{color:#dc2626}
.cw-decay{font-style:normal;font-size:12px;margin-left:8px;padding:0 7px;border-radius:99px;color:#15803d;background:#dcfce7}.cw-decay.warning{color:#b45309;background:#fef3c7}.cw-decay.alarm{color:#b91c1c;background:#fee2e2}
.cw-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:16px}.cw-section-head h3{margin:0}
.cw-note,small{color:#64748b;font-size:13px}small{display:block;margin-top:5px}.cw-detail{padding-top:16px}.cw-detail h3{font-size:16px;margin:20px 0 8px}.cw-item strong{font-size:14px;color:#14213d}.cw-item,.cw-contact{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid #e5eaf1}.cw-item>div{min-width:0;overflow-wrap:anywhere}.cw-contact{flex-wrap:wrap}.cw-relations{width:100%;font-size:13px}.cw-relations>div{display:flex;justify-content:space-between;align-items:center;margin-top:8px}.cw-history{padding:12px 0;border-bottom:1px solid #e5eaf1;overflow-wrap:anywhere}.cw-history p{margin:8px 0;white-space:pre-wrap}.cw-detail summary{cursor:pointer;color:#426184}.el-pagination{margin-top:16px}
@media(max-width:1100px){.cw-kpis{grid-template-columns:repeat(2,1fr)}.cw-dstats{grid-template-columns:repeat(3,1fr)}}
@media(max-width:650px){.cw-kpis{grid-template-columns:1fr 1fr;gap:8px}.cw-kpi{padding:10px}.cw-kpi b{font-size:20px}.cw-toolbar{flex-direction:column;align-items:stretch;gap:8px}.cw-toolbar .el-input{max-width:none}.cw-view{margin-left:0}.cw-grid{grid-template-columns:1fr}.cw-item{align-items:flex-start}.cw-contact>div:first-child{min-width:70%}}
</style>
