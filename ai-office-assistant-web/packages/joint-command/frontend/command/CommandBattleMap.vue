<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { PROVINCES, MAP_VIEWBOX } from '../dashboard/chinaMapData'
import { CITY_PROVINCE } from '../dashboard/cityProvince'
import { OPPORTUNITY_STAGES } from '../opportunityStages'
import { bizIcon } from '../businessIcons'
import CountUp from './CountUp.vue'

export interface BattleTarget { item: CrmOpportunity; probability: number; weighted: number; reasons?: string[]; gaps?: string[]; followups?: number }
const props = defineProps<{ targets: BattleTarget[]; activeCount: number; suspects?: CrmOpportunity[] }>()
const emit = defineEmits<{ opportunity: [item: CrmOpportunity]; detail: [item: CrmOpportunity]; manage: [] }>()

type Tier = 'high' | 'mid' | 'low'
const ic = bizIcon
const fmt = (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
const compact = (v: number) => v >= 10000 ? `${(v / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}亿` : `${fmt(v)}万`
const amountOf = (o: CrmOpportunity) => Number(o.amount || 0)
const investOf = (o: CrmOpportunity) => Number(o.investment || 0)
const stageOf = (o: CrmOpportunity) => o.sales_stage || o.stage || '未填写阶段'
const tier = (p: number): Tier => p >= 70 ? 'high' : p >= 40 ? 'mid' : 'low'
const TIER_LABEL: Record<Tier, string> = { high: '高概率 ≥70%', mid: '中概率 40–69%', low: '低概率 <40%' }

// 从项目名称或业主单位中识别城市，再落到所属省份；识别不到的不上图，只在清单里出现。
const PLACE_KEYS = Object.keys(CITY_PROVINCE).filter(k => k.length >= 2).sort((a, b) => b.length - a.length)
const provinceOf = (o: CrmOpportunity) => {
  const text = `${o.name || ''} ${o.owner_unit || ''}`
  const hit = PLACE_KEYS.find(k => text.includes(k))
  return hit ? CITY_PROVINCE[hit] : ''
}
const provinceCenter = new Map(PROVINCES.map(p => [p.n, p]))

// 源表日期形如 2027/3/30 或 2027-03；只到月份时按月末计。
const today = new Date(); today.setHours(0, 0, 0, 0)
function parseDate(v?: string) {
  const m = String(v || '').match(/(\d{4})[\/.\-年](\d{1,2})(?:[\/.\-月](\d{1,2}))?/)
  if (!m) return null
  const y = Number(m[1]), mo = Number(m[2])
  return m[3] ? new Date(y, mo - 1, Number(m[3])) : new Date(y, mo, 0)
}
const daysFromToday = (v?: string) => { const d = parseDate(v); return d ? Math.round((d.getTime() - today.getTime()) / 86400000) : null }
const signOverdue = (o: CrmOpportunity) => { const d = daysFromToday(o.contract_date); return d !== null && d < 0 }

const located = computed(() => props.targets.map(t => ({ ...t, province: provinceOf(t.item) })))
type Located = (typeof located.value)[number]
const stageIndex = (o: CrmOpportunity) => OPPORTUNITY_STAGES.findIndex(s => s.name === stageOf(o))

// ---- 交互筛选：各控件共用同一组条件，任一处点击即联动地图、清单与战线 ----
const filterProvince = ref('')
const filterStage = ref(-1)
const filterTier = ref<Tier | ''>('')
const filterFocus = ref<'' | 'overdue' | 'unassigned'>('')
const matches = (t: Located, skip = '') =>
  (skip === 'province' || !filterProvince.value || t.province === filterProvince.value) &&
  (skip === 'stage' || filterStage.value < 0 || stageIndex(t.item) === filterStage.value) &&
  (skip === 'tier' || !filterTier.value || tier(t.probability) === filterTier.value) &&
  (filterFocus.value !== 'overdue' || signOverdue(t.item)) &&
  (filterFocus.value !== 'unassigned' || !(t.item.manager || '').trim())
const filtered = computed(() => located.value.filter(t => matches(t)))
const toggleProvince = (v: string) => { filterProvince.value = filterProvince.value === v ? '' : v }
const toggleStage = (v: number) => { filterStage.value = filterStage.value === v ? -1 : v }
const toggleTier = (v: Tier) => { filterTier.value = filterTier.value === v ? '' : v }
const toggleFocus = (v: 'overdue' | 'unassigned') => { filterFocus.value = filterFocus.value === v ? '' : v }
const clearFilters = () => { filterProvince.value = ''; filterStage.value = -1; filterTier.value = ''; filterFocus.value = '' }
const chips = computed(() => [
  filterProvince.value && { key: 'p', label: `战区：${filterProvince.value}`, off: () => { filterProvince.value = '' } },
  filterStage.value >= 0 && { key: 's', label: `阶段：${OPPORTUNITY_STAGES[filterStage.value]?.name}`, off: () => { filterStage.value = -1 } },
  filterTier.value && { key: 't', label: TIER_LABEL[filterTier.value], off: () => { filterTier.value = '' } },
  filterFocus.value === 'overdue' && { key: 'o', label: '预计签约已逾期', off: () => { filterFocus.value = '' } },
  filterFocus.value === 'unassigned' && { key: 'u', label: '待指派负责人', off: () => { filterFocus.value = '' } },
].filter(Boolean) as { key: string; label: string; off: () => void }[])

const totalAmount = computed(() => filtered.value.reduce((s, t) => s + amountOf(t.item), 0))
const totalInvestment = computed(() => filtered.value.reduce((s, t) => s + investOf(t.item), 0))
const highCount = computed(() => located.value.filter(t => matches(t, 'tier') && t.probability >= 70).length)
const overdueCount = computed(() => located.value.filter(t => signOverdue(t.item)).length)
const unassigned = computed(() => located.value.filter(t => !(t.item.manager || '').trim()).length)

// 同省多个目标围绕省中心呈螺旋分布，避免重叠。
const maxAmount = computed(() => Math.max(1, ...props.targets.map(t => amountOf(t.item))))
const markers = computed(() => {
  const perProvince = new Map<string, number>()
  return located.value.filter(t => t.province && provinceCenter.has(t.province)).map(t => {
    const c = provinceCenter.get(t.province)!
    const k = perProvince.get(t.province) || 0
    perProvince.set(t.province, k + 1)
    const angle = k * 2.4, dist = k === 0 ? 0 : 9 + Math.sqrt(k) * 9
    const r = 4 + Math.sqrt(amountOf(t.item) / maxAmount.value) * 16
    return { ...t, x: c.cx + Math.cos(angle) * dist, y: c.cy + Math.sin(angle) * dist, r, on: matches(t) }
  })
})
const unlocated = computed(() => located.value.length - markers.value.length)

// 省份统计不受“战区”条件影响，便于在已选省份时仍能切换到别的省。
const provinceStats = computed(() => {
  const m = new Map<string, { name: string; count: number; amount: number }>()
  for (const t of located.value) {
    if (!t.province || !matches(t, 'province')) continue
    const row = m.get(t.province) || { name: t.province, count: 0, amount: 0 }
    row.count++; row.amount += amountOf(t.item); m.set(t.province, row)
  }
  return [...m.values()].sort((a, b) => b.amount - a.amount)
})
const provinceHeat = computed(() => {
  const max = Math.max(1, ...provinceStats.value.map(p => p.amount))
  return new Map(provinceStats.value.map(p => [p.name, 0.18 + 0.62 * Math.sqrt(p.amount / max)]))
})
const topProvinces = computed(() => provinceStats.value.slice(0, 6))

// 攻坚目标：按概率加权价值排序，份额相同时份额大的优先。
const ranked = computed(() => [...filtered.value].sort((a, b) => b.weighted - a.weighted || amountOf(b.item) - amountOf(a.item)))
const labelled = computed(() => new Set(ranked.value.slice(0, 5).map(t => t.item.code)))

const stageFront = computed(() => OPPORTUNITY_STAGES.map((s, i) => {
  const rows = located.value.filter(t => matches(t, 'stage') && stageIndex(t.item) === i)
  return { index: i, name: s.name, phase: s.phase, group: s.group, count: rows.length, amount: rows.reduce((a, t) => a + amountOf(t.item), 0) }
}))
const maxStageCount = computed(() => Math.max(1, ...stageFront.value.map(s => s.count)))

// 标注牌放在地图左右两侧的固定列，按纵坐标错开，用引线连回目标点，避免互相压盖。
const callouts = computed(() => {
  const picks = markers.value.filter(m => m.on && labelled.value.has(m.item.code))
  const out: { m: (typeof picks)[number]; side: 'l' | 'r'; lx: number; ly: number }[] = []
  for (const side of ['l', 'r'] as const) {
    const group = picks.filter(m => (side === 'l') === (m.x < 700)).sort((a, b) => a.y - b.y)
    // 左下角放了战区排行，左侧标注牌必须停在其上方。
    const floor = side === 'l' ? 420 : MAP_VIEWBOX.height - 30
    const ys: number[] = []
    let last = -Infinity
    for (const m of group) { last = Math.max(40, m.y - 30, last + 52); ys.push(last) }
    const overflow = Math.max(0, (ys[ys.length - 1] ?? 0) - floor)
    group.forEach((m, i) => out.push({ m, side, lx: side === 'l' ? 300 : 880, ly: Math.max(40, ys[i]! - overflow) }))
  }
  return out
})

// ---- 选中目标：地图与清单双向联动，情报卡展示源表字段与研判 ----
const hovered = ref<string | null>(null)
const selected = ref<string | null>(null)
const selectedTarget = computed(() => located.value.find(t => t.item.code === selected.value) || null)
const pick = (code: string) => { selected.value = selected.value === code ? null : code }
watch(filtered, list => { if (selected.value && !list.some(t => t.item.code === selected.value)) selected.value = null })
const listEl = ref<HTMLElement | null>(null)
watch(selected, code => { if (code) requestAnimationFrame(() => listEl.value?.querySelector(`[data-code="${CSS.escape(code)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })) })
const intel = computed(() => {
  const t = selectedTarget.value
  if (!t) return null
  const o = t.item
  const share = amountOf(o), invest = investOf(o)
  const sign = daysFromToday(o.contract_date), bid = daysFromToday(o.bid_date)
  const alerts: string[] = []
  if (sign !== null && sign < 0) alerts.push(`预计签约已逾期 ${-sign} 天，需确认项目是否仍在推进`)
  else if (sign !== null && sign <= 90) alerts.push(`距预计签约仅剩 ${sign} 天`)
  if (!(o.manager || '').trim()) alerts.push('未指派负责人')
  if (invest > 0 && share / invest < 0.1) alerts.push(`可参与份额仅占投资 ${Math.round(share / invest * 100)}%，关注总包/分包界面`)
  for (const g of t.gaps || []) alerts.push(g)
  return {
    t, share, invest, ratio: invest > 0 ? Math.round(share / invest * 100) : null,
    integration: Number(o.share_integration || 0), service: Number(o.share_service || 0),
    sign, bid, alerts: alerts.slice(0, 4), reasons: (t.reasons || []).slice(0, 3),
  }
})
const dayText = (d: number | null) => d === null ? '' : d < 0 ? `已过 ${-d} 天` : d === 0 ? '今天' : `还有 ${d} 天`
const hoverTarget = computed(() => selected.value ? null : markers.value.find(m => m.item.code === hovered.value) || null)
</script>

<template>
  <div class="battle">
    <header class="battle-head">
      <div class="command-intro"><span>PROJECT COMMAND · 作战态势</span><h3>项目作战地图</h3><p>聚焦可参与份额 ≥ 1000 万元的在谈项目。点击指标、省份、图例、阶段或目标即可联动筛选，选中目标查看作战情报。</p></div>
      <button @click="emit('manage')">进入项目作战工作台 →</button>
    </header>

    <div class="battle-kpis">
      <button type="button" class="k k-cyan" :class="{ on: !chips.length }" @click="clearFilters"><i v-html="ic('target')"></i><small>重点攻坚项目</small><b><CountUp :value="filtered.length" /><em v-if="filtered.length !== targets.length">/ {{ targets.length }}</em></b><span>占在谈商机 <em>{{ activeCount ? Math.round(targets.length / activeCount * 100) : 0 }}%</em> · 点击查看全部</span></button>
      <div class="k k-blue"><i v-html="ic('reserve')"></i><small>可参与份额 · 万元</small><b><CountUp :value="totalAmount" :decimals="1" /></b><span v-if="suspects?.length" class="warn" :title="suspects.map(o => `${o.name}：${fmt(Number(o.amount || 0))} 万元`).join('\n')">另有 <em>{{ suspects.length }}</em> 项份额 ≥10 亿待核实，未计入</span><span v-else>对应项目投资 <em>{{ compact(totalInvestment) }}</em> · 可参与占 <em>{{ totalInvestment ? Math.round(totalAmount / totalInvestment * 100) : 0 }}%</em></span></div>
      <button type="button" class="k k-green" :class="{ on: filterTier === 'high' }" :aria-pressed="filterTier === 'high'" @click="toggleTier('high')"><i v-html="ic('growth')"></i><small>高概率目标</small><b><CountUp :value="highCount" /></b><span>预测赢率 ≥ 70% · 点击筛选</span></button>
      <button type="button" class="k k-red" :class="{ on: filterFocus === 'overdue', alert: overdueCount > 0 }" :aria-pressed="filterFocus === 'overdue'" @click="toggleFocus('overdue')"><i v-html="ic('calendar')"></i><small>预计签约已逾期</small><b><CountUp :value="overdueCount" /></b><span>合同预计签订日已过 · 点击筛选</span></button>
      <button type="button" class="k k-amber" :class="{ on: filterFocus === 'unassigned', alert: unassigned > 0 }" :aria-pressed="filterFocus === 'unassigned'" @click="toggleFocus('unassigned')"><i v-html="ic('flag')"></i><small>待指派负责人</small><b><CountUp :value="unassigned" /></b><span>重点项目需明确主攻责任人</span></button>
    </div>

    <div class="battle-main">
      <section class="panel theater" aria-label="战区态势图">
        <header><i class="p-ic" v-html="ic('map')"></i><div><h4>战区态势图 <small>已定位 {{ markers.length }} / {{ targets.length }}<template v-if="unlocated"> · {{ unlocated }} 个未识别城市</template></small></h4><p>点大小 = 可参与份额（非项目投资）· 颜色 = 预测赢率 · 点击省份或目标联动</p></div>
          <ul class="legend"><li v-for="tv in (['high', 'mid', 'low'] as Tier[])" :key="tv"><button type="button" :class="[tv, { on: filterTier === tv }]" :aria-pressed="filterTier === tv" @click="toggleTier(tv)"><i></i>{{ TIER_LABEL[tv].replace('概率', '') }}</button></li></ul></header>
        <div class="theater-body">
          <svg class="map" :viewBox="`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`" preserveAspectRatio="xMidYMid meet" role="img" aria-label="重点项目战区分布" @click.self="selected = null">
            <defs>
              <radialGradient id="bm-sweep" cx="0" cy="0" r="1"><stop offset="0" stop-color="#36dcf0" stop-opacity=".35" /><stop offset="1" stop-color="#36dcf0" stop-opacity="0" /></radialGradient>
              <filter id="bm-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
              <pattern id="bm-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="rgba(88,160,230,.08)" stroke-width="1" /></pattern>
            </defs>
            <rect :width="MAP_VIEWBOX.width" :height="MAP_VIEWBOX.height" fill="url(#bm-grid)" @click="selected = null" />
            <g class="rings" transform="translate(620 470)">
              <circle v-for="r in [110, 220, 330, 440]" :key="r" :r="r" />
              <line x1="-460" y1="0" x2="460" y2="0" /><line x1="0" y1="-460" x2="0" y2="460" />
              <g class="sweep"><path d="M0 0 L460 0 A460 460 0 0 0 398 -230 Z" fill="url(#bm-sweep)" /></g>
            </g>
            <path v-for="p in PROVINCES" :key="p.n" :d="p.d" class="prov" :class="{ hot: provinceHeat.has(p.n), picked: filterProvince === p.n, faded: filterProvince && filterProvince !== p.n }" :style="provinceHeat.has(p.n) ? { fillOpacity: provinceHeat.get(p.n) } : undefined" :tabindex="provinceHeat.has(p.n) ? 0 : -1" :role="provinceHeat.has(p.n) ? 'button' : undefined" :aria-label="provinceHeat.has(p.n) ? `筛选战区 ${p.n}` : undefined" @click="provinceHeat.has(p.n) ? toggleProvince(p.n) : (filterProvince = '')" @keydown.enter="provinceHeat.has(p.n) && toggleProvince(p.n)"><title>{{ p.n }}{{ provinceHeat.has(p.n) ? ' · 点击筛选' : '' }}</title></path>
            <g v-for="m in markers" :key="m.item.code" class="mk" :class="[tier(m.probability), { labelled: labelled.has(m.item.code), off: !m.on, sel: selected === m.item.code, hov: hovered === m.item.code }]" :transform="`translate(${m.x} ${m.y})`" tabindex="0" role="button" :aria-label="`${m.item.name}，${m.province}，份额 ${fmt(amountOf(m.item))} 万元，预测赢率 ${m.probability}%`" @mouseenter="hovered = m.item.code" @mouseleave="hovered = null" @focus="hovered = m.item.code" @blur="hovered = null" @click.stop="pick(m.item.code)" @keydown.enter="pick(m.item.code)">
              <circle class="pulse" :r="m.r" />
              <circle class="halo" :r="m.r" />
              <circle class="core" :r="Math.max(2.5, m.r * .38)" filter="url(#bm-glow)" />
              <circle v-if="selected === m.item.code" class="lock" :r="m.r + 7" />
            </g>
            <g v-for="c in callouts" :key="'l' + c.m.item.code" class="tag" :class="[tier(c.m.probability), { sel: selected === c.m.item.code }]" @click.stop="pick(c.m.item.code)">
              <polyline :points="`${c.m.x},${c.m.y} ${c.side === 'l' ? c.lx + 20 : c.lx - 20},${c.ly} ${c.lx},${c.ly}`" />
              <g :transform="`translate(${c.lx} ${c.ly})`">
                <rect :x="c.side === 'l' ? -214 : 0" y="-21" width="214" height="42" rx="5" />
                <rect :x="c.side === 'l' ? -4 : 0" y="-21" width="4" height="42" class="bar" />
                <text :x="c.side === 'l' ? -204 : 12" y="-3">{{ (c.m.item.name || '').slice(0, 13) }}</text>
                <text :x="c.side === 'l' ? -204 : 12" y="14" class="sub">{{ c.m.province }} · {{ compact(amountOf(c.m.item)) }} · 赢率 {{ c.m.probability }}%</text>
              </g>
            </g>
          </svg>
          <div v-if="hoverTarget" class="tip"><b>{{ hoverTarget.item.name }}</b><span>{{ hoverTarget.province }} · {{ stageOf(hoverTarget.item) }} · {{ hoverTarget.item.manager || '待指派' }}</span><span>可参与 {{ compact(amountOf(hoverTarget.item)) }} · 投资 {{ compact(investOf(hoverTarget.item)) }} · 赢率 {{ hoverTarget.probability }}%</span><em>点击查看作战情报</em></div>

          <article v-if="intel" class="intel" :class="tier(intel.t.probability)" aria-label="目标作战情报">
            <header><span class="pill">{{ intel.t.probability }}%</span><div><b :title="intel.t.item.name">{{ intel.t.item.name }}</b><small>{{ intel.t.item.code }} · {{ intel.t.item.owner_unit || '业主待补充' }}</small></div><button type="button" class="x" aria-label="关闭情报" @click="selected = null">×</button></header>
            <div class="intel-money">
              <div><small>可参与份额</small><b>{{ compact(intel.share) }}</b><span>集成 {{ compact(intel.integration) }} · 服务1.0 {{ compact(intel.service) }}</span></div>
              <div><small>项目投资规模</small><b>{{ intel.invest ? compact(intel.invest) : '未填写' }}</b><span v-if="intel.ratio !== null">可参与占 {{ intel.ratio }}%</span></div>
            </div>
            <p v-if="intel.ratio !== null" class="ratio"><i :style="{ width: Math.min(100, intel.ratio) + '%' }"></i></p>
            <div class="stepper big"><span v-for="(s, si) in OPPORTUNITY_STAGES" :key="s.name" :class="{ done: si < stageIndex(intel.t.item), now: si === stageIndex(intel.t.item) }" :title="s.name"></span><em>{{ stageOf(intel.t.item) }}</em></div>
            <dl>
              <div><dt>战区 / 归属</dt><dd><button type="button" class="link" :disabled="!intel.t.province" @click="toggleProvince(intel.t.province)">{{ intel.t.province || '未识别' }}</button> · {{ intel.t.item.region || '—' }}</dd></div>
              <div><dt>负责人</dt><dd>{{ intel.t.item.manager || '待指派' }}</dd></div>
              <div><dt>预计招标</dt><dd>{{ intel.t.item.bid_date || '—' }} <small :class="{ bad: (intel.bid ?? 1) < 0 }">{{ dayText(intel.bid) }}</small></dd></div>
              <div><dt>预计签约</dt><dd>{{ intel.t.item.contract_date || '—' }} <small :class="{ bad: (intel.sign ?? 1) < 0 }">{{ dayText(intel.sign) }}</small></dd></div>
              <div v-if="intel.t.item.contractor"><dt>总包 / 二代</dt><dd>{{ intel.t.item.contractor }}</dd></div>
              <div v-if="intel.t.item.products || intel.t.item.brand"><dt>产品 / 品牌</dt><dd>{{ [intel.t.item.products, intel.t.item.brand].filter(Boolean).join(' · ') }}</dd></div>
              <div><dt>登记赢率 / 跟进</dt><dd>{{ intel.t.item.win_rate || '—' }} · 跟进计划 {{ intel.t.followups || 0 }} 条</dd></div>
            </dl>
            <ul v-if="intel.alerts.length" class="alerts"><li v-for="a in intel.alerts" :key="a"><i v-html="ic('flag')"></i>{{ a }}</li></ul>
            <p v-if="intel.t.item.remark" class="remark">备注：{{ intel.t.item.remark }}</p>
            <footer>
              <button type="button" class="primary" @click="emit('opportunity', intel.t.item)">进入作战部署 →</button>
              <button type="button" @click="emit('detail', intel.t.item)">商机详情</button>
            </footer>
          </article>

          <aside v-else class="theater-rank">
            <p>战区份额 TOP6 <small>点击筛选</small></p>
            <ol><li v-for="(p, i) in topProvinces" :key="p.name"><button type="button" :class="{ on: filterProvince === p.name }" :aria-pressed="filterProvince === p.name" @click="toggleProvince(p.name)"><i>{{ i + 1 }}</i><span>{{ p.name }}</span><b>{{ compact(p.amount) }}</b><small>{{ p.count }} 项</small><em><u :style="{ width: p.amount / (topProvinces[0]?.amount || 1) * 100 + '%' }"></u></em></button></li></ol>
          </aside>
        </div>
      </section>

      <section class="panel targets" aria-label="攻坚目标">
        <header><i class="p-ic" v-html="ic('sprint')"></i><div><h4>攻坚目标 <small>{{ ranked.length }} 个</small></h4><p>按概率加权价值排序 · 点击行查看情报</p></div></header>
        <div v-if="chips.length" class="chips"><button v-for="c in chips" :key="c.key" type="button" @click="c.off()">{{ c.label }} ×</button><button type="button" class="clear" @click="clearFilters">清除</button></div>
        <ol ref="listEl" class="command-table target-list">
          <li v-for="(t, i) in ranked" :key="t.item.id || t.item.code" :data-code="t.item.code" :class="[tier(t.probability), { sel: selected === t.item.code, hov: hovered === t.item.code }]" tabindex="0" @click="pick(t.item.code)" @keydown.enter.self="pick(t.item.code)" @mouseenter="hovered = t.item.code" @mouseleave="hovered = null">
            <i class="rank" :class="'r' + (i + 1)">{{ i + 1 }}</i>
            <div class="t-main">
              <strong :title="t.item.name">{{ t.item.name || t.item.code }}</strong>
              <small>{{ t.province || '战区待定位' }} · {{ t.item.owner_unit || '业主待补充' }}<b v-if="signOverdue(t.item)" class="late">签约逾期</b></small>
              <div class="stepper" :aria-label="`当前阶段：${stageOf(t.item)}`"><span v-for="(s, si) in OPPORTUNITY_STAGES" :key="s.name" :class="{ done: si < stageIndex(t.item), now: si === stageIndex(t.item) }" :title="s.name"></span><em>{{ stageOf(t.item) }}</em></div>
            </div>
            <div class="t-num"><b :title="`可参与份额 ${fmt(amountOf(t.item))} 万 · 项目投资 ${fmt(investOf(t.item))} 万`">{{ compact(amountOf(t.item)) }}</b><small class="inv">投资 {{ compact(investOf(t.item)) }}</small><span class="pill">{{ t.probability }}%</span><small>{{ t.item.manager || '待指派' }}</small></div>
            <button type="button" @click.stop="emit('opportunity', t.item)">作战 →</button>
          </li>
          <li v-if="!ranked.length" class="empty">当前筛选下没有目标。<button type="button" class="link" @click="clearFilters">清除筛选</button></li>
        </ol>
      </section>
    </div>

    <section class="panel front" aria-label="阶段推进战线">
      <header><i class="p-ic" v-html="ic('flow')"></i><div><h4>阶段推进战线</h4><p>重点项目在六个销售阶段的兵力分布 · 点击阶段筛选</p></div></header>
      <ol class="front-line">
        <li v-for="s in stageFront" :key="s.name" :class="s.group"><button type="button" :class="{ on: filterStage === s.index, empty: !s.count }" :aria-pressed="filterStage === s.index" :disabled="!s.count && filterStage !== s.index" @click="toggleStage(s.index)">
          <small>{{ s.phase }}</small>
          <b>{{ s.count }}</b>
          <span>{{ s.name }}</span>
          <p><i :style="{ width: Math.max(s.count ? 4 : 0, s.count / maxStageCount * 100) + '%' }"></i></p>
          <em>{{ compact(s.amount) }}</em>
        </button></li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.battle { --line: rgba(74,138,214,.38); --num: 'DIN Alternate','Bahnschrift','Barlow','PingFang SC',sans-serif; height: 100%; min-height: 0; display: flex; flex-direction: column; gap: 10px; overflow: hidden; }
.battle :deep(.bi-ic) { width: 1em; height: 1em; display: inline-block; vertical-align: -.15em; }
.battle-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; flex: none; }
.battle-head .command-intro { margin: 0; }
.battle-head .command-intro h3 { font-size: 22px; margin: 5px 0 2px; }
.battle-head .command-intro p { margin: 0; font-size: 11px; }
.battle-head > button { white-space: nowrap; }
.battle-head > button,.target-list li > button { color:#eaf3ff; background:linear-gradient(180deg,#163866,#0a1e3e); border:1px solid #568eBC; border-radius:4px; padding:7px 12px; font:inherit; cursor:pointer; }
.battle-head > button:hover,.target-list li > button:hover { border-color:#36dcf0; color:#9ff0ff; }

.battle-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; flex: none; }
.k { --k: #36dcf0; position: relative; overflow: hidden; padding: 10px 14px 9px; border: 1px solid var(--line); border-top: 2px solid var(--k); border-radius: 10px; background: linear-gradient(180deg, rgba(38,86,150,.22), rgba(10,26,54,0) 80px), linear-gradient(180deg, rgba(11,29,58,.9), rgba(7,21,45,.92)); box-shadow: inset 0 1px 0 rgba(120,180,255,.14), 0 4px 18px rgba(0,0,0,.35); }
.k::after { content: ''; position: absolute; inset: 0; pointer-events: none; background: radial-gradient(150px 70px at 100% 0%, color-mix(in srgb, var(--k) 18%, transparent), transparent 70%); }
.k-cyan { --k: #36dcf0; } .k-blue { --k: #3b9bff; } .k-green { --k: #20c98f; } .k-purple { --k: #a57bff; } .k-amber { --k: #ffc83d; } .k-amber.alert { --k: #ff7a5c; }
.k > i { position: absolute; right: 12px; top: 10px; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 9px; font-size: 17px; color: #fff; background: linear-gradient(135deg, color-mix(in srgb, var(--k) 85%, #fff), var(--k)); box-shadow: 0 4px 14px color-mix(in srgb, var(--k) 40%, transparent); z-index: 1; }
.k small { display: block; font-size: 11px; color: #9fb6cd; }
.k b { display: flex; align-items: baseline; gap: 3px; margin: 5px 0 3px; font-size: clamp(20px, 1.6vw, 28px); line-height: 1.1; color: #f3f8ff; font-family: var(--num); text-shadow: 0 0 14px color-mix(in srgb, var(--k) 45%, transparent); white-space: nowrap; }
.k b em { font-style: normal; font-size: 12px; color: #b3c3d8; }
.k > span { display: block; font-size: 10.5px; color: #7f96b4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.k > span em { font-style: normal; color: #e6effb; font-weight: 600; }
.k > span.warn { color: #ffb86b; cursor: help; } .k > span.warn em { color: #ffd08a; }

.panel { min-width: 0; min-height: 0; overflow: hidden; display: flex; flex-direction: column; padding: 10px 13px; border: 1px solid var(--line); border-radius: 10px; background: linear-gradient(180deg, rgba(38,86,150,.22), rgba(10,26,54,0) 90px), linear-gradient(180deg, rgba(11,29,58,.9), rgba(7,21,45,.92)); box-shadow: inset 0 1px 0 rgba(120,180,255,.18), inset 0 0 24px rgba(40,110,200,.12), 0 4px 18px rgba(0,0,0,.35); }
.panel > header { display: flex; align-items: center; gap: 9px; flex: none; padding-bottom: 7px; margin-bottom: 6px; border-bottom: 1px solid rgba(88,142,208,.2); }
.panel > header > div { flex: 1; min-width: 0; }
.panel h4 { margin: 0; font-size: 14px; font-weight: 700; color: #f3f8ff; }
.panel header p { margin: 0; font-size: 10px; color: #7f96b4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-ic { flex: none; width: 26px; height: 26px; display: grid; place-items: center; border-radius: 8px; font-size: 15px; color: #9fe8ff; background: rgba(54,220,240,.14); }

.battle-main { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr); gap: 10px; }
.legend { display: flex; gap: 10px; margin: 0; padding: 0; list-style: none; font-size: 10.5px; color: #b3c3d8; white-space: nowrap; }
.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: 0; }
.legend .high, .mk.high { --c: #20e0a0; } .legend .mid, .mk.mid { --c: #ffc83d; } .legend .low, .mk.low { --c: #ff5c69; }
.legend i { background: var(--c); box-shadow: 0 0 6px var(--c); }

.theater-body { position: relative; flex: 1; min-height: 0; }
.map { position: absolute; inset: 0; width: 100%; height: 100%; }
.rings circle { fill: none; stroke: rgba(54,220,240,.12); stroke-width: 1; stroke-dasharray: 3 6; }
.rings line { stroke: rgba(54,220,240,.08); stroke-width: 1; }
.sweep { transform-origin: 0 0; animation: bm-spin 7s linear infinite; }
.prov { fill: rgba(22,60,110,.38); stroke: rgba(110,190,255,.55); stroke-width: .8; transition: fill-opacity .3s; }
.prov.hot { fill: #1f7fd6; stroke: rgba(120,210,255,.85); stroke-width: 1.1; filter: drop-shadow(0 0 4px rgba(54,160,255,.55)); }
.mk { cursor: pointer; outline: none; }
.mk .halo { fill: color-mix(in srgb, var(--c) 22%, transparent); stroke: var(--c); stroke-width: 1.2; }
.mk .core { fill: var(--c); }
.mk .pulse { fill: none; stroke: var(--c); stroke-width: 1.5; transform-origin: 0 0; animation: bm-pulse 2.4s ease-out infinite; }
.mk:hover .halo, .mk:focus-visible .halo { stroke-width: 2.5; fill: color-mix(in srgb, var(--c) 40%, transparent); }
.mk.labelled .pulse { animation-duration: 1.6s; stroke-width: 2; }
.tag { --c: #36dcf0; pointer-events: none; }
.tag.high { --c: #20e0a0; } .tag.mid { --c: #ffc83d; } .tag.low { --c: #ff5c69; }
.tag polyline { fill: none; stroke: var(--c); stroke-width: 1.2; stroke-dasharray: 4 3; opacity: .85; }
.tag rect.bar { fill: var(--c); stroke: none; }
.tag rect { fill: rgba(6,22,48,.92); stroke: color-mix(in srgb, var(--c) 60%, transparent); stroke-width: 1; }
.tag text { font-size: 15px; fill: #eef7ff; font-weight: 600; }
.tag text.sub { font-size: 12.5px; fill: #9fd8ee; font-weight: 400; }
.tip { position: absolute; left: 12px; top: 8px; z-index: 2; display: flex; flex-direction: column; gap: 2px; max-width: 320px; padding: 8px 10px; border: 1px solid rgba(54,220,240,.55); border-radius: 8px; background: rgba(6,22,48,.94); box-shadow: 0 0 18px rgba(54,220,240,.25); font-size: 11px; color: #b3c3d8; pointer-events: none; }
.tip b { color: #f3f8ff; font-size: 12px; }
.theater-rank { position: absolute; left: 4px; bottom: 4px; z-index: 1; width: 188px; padding: 8px 10px; border: 1px solid rgba(74,138,214,.35); border-radius: 8px; background: rgba(6,20,44,.82); backdrop-filter: blur(3px); }
.theater-rank p { margin: 0 0 5px; font-size: 11px; font-weight: 600; color: #9fe8ff; }
.theater-rank ol { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
.theater-rank li { display: grid; grid-template-columns: 14px 1fr auto auto; grid-template-rows: auto 3px; align-items: center; gap: 1px 6px; font-size: 11px; color: #d6e1ef; }
.theater-rank li > i { font-style: normal; font-size: 10px; color: #7f96b4; font-family: var(--num); }
.theater-rank li b { font-family: var(--num); color: #f3f8ff; font-size: 11.5px; }
.theater-rank li small { font-size: 9.5px; color: #7f96b4; }
.theater-rank li em { grid-column: 2 / -1; height: 3px; border-radius: 2px; background: rgba(58,92,140,.4); overflow: hidden; }
.theater-rank li em u { display: block; height: 100%; border-radius: 2px; background: linear-gradient(90deg, #3b9bff, #36dcf0); }

.target-list { flex: 1; min-height: 0; margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; justify-content: space-between; gap: 5px; overflow: hidden; border: 0; background: none; box-shadow: none; max-height: none; }
.target-list li { --c: #36dcf0; flex: 1; min-height: 0; display: grid; grid-template-columns: 22px minmax(0, 1fr) auto auto; align-items: center; gap: 9px; padding: 5px 8px; border: 1px solid rgba(74,138,214,.22); border-left: 2px solid var(--c); border-radius: 7px; background: linear-gradient(90deg, color-mix(in srgb, var(--c) 10%, transparent), rgba(8,24,50,.5) 45%); }
.target-list li.high { --c: #20e0a0; } .target-list li.mid { --c: #ffc83d; } .target-list li.low { --c: #ff5c69; }
.target-list li.empty { display: block; border-left-color: rgba(74,138,214,.22); color: #7f96b4; font-size: 12px; text-align: center; padding: 20px; }
.rank { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; font-style: normal; font-size: 11px; font-weight: 700; color: #0a1f3a; background: rgba(127,150,180,.5); font-family: var(--num); }
.rank.r1 { background: linear-gradient(135deg, #ffe28a, #ffb020); box-shadow: 0 0 10px rgba(255,190,50,.55); }
.rank.r2 { background: linear-gradient(135deg, #e6f0ff, #9fb6cd); }
.rank.r3 { background: linear-gradient(135deg, #ffc19a, #d9824a); }
.t-main { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.t-main strong { font-size: 12px; color: #eef5ff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.t-main small { font-size: 9.5px; color: #7f96b4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stepper { display: flex; align-items: center; gap: 3px; margin-top: 3px; }
.stepper span { width: 14px; height: 4px; border-radius: 2px; background: rgba(58,92,140,.5); }
.stepper span.done { background: #3b9bff; }
.stepper span.now { background: var(--c); box-shadow: 0 0 6px var(--c); }
.stepper em { margin-left: 5px; font-style: normal; font-size: 9.5px; color: #9fb6cd; white-space: nowrap; }
.t-num { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; }
.t-num b { font-family: var(--num); font-size: 13px; color: #f3f8ff; white-space: nowrap; }
.t-num small.inv { color: #8fb6d2; }
.t-num small { font-size: 9.5px; color: #7f96b4; white-space: nowrap; }
.pill { padding: 0 6px; border-radius: 8px; font-size: 10px; font-weight: 600; font-family: var(--num); color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent); }
.target-list li > button { padding: 4px 9px; font-size: 10.5px; white-space: nowrap; }

.front { flex: none; }
.front-line { margin: 0; padding: 0; list-style: none; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
.front-line li { --t: #3b8ff0; position: relative; display: block !important; grid-template-columns: auto 1fr auto; grid-template-areas: 'ph ph ph' 'n name amt' 'bar bar bar'; align-items: baseline; gap: 1px 7px; padding: 6px 10px 7px; border: 1px solid color-mix(in srgb, var(--t) 40%, transparent); border-radius: 8px; background: linear-gradient(180deg, color-mix(in srgb, var(--t) 18%, transparent), color-mix(in srgb, var(--t) 4%, transparent)); }
.front-line li.win { --t: #22c493; }
.front-line li::after { content: ''; position: absolute; right: -8px; top: 50%; border: 5px solid transparent; border-left: 6px solid color-mix(in srgb, var(--t) 75%, transparent); transform: translateY(-50%); }
.front-line li:last-child::after { display: none; }
.front-line small { grid-area: ph; font-size: 9px; color: #9fb6cd; letter-spacing: .5px; }
.front-line b { grid-area: n; font-size: 20px; line-height: 1.1; color: #f3f8ff; font-family: var(--num); text-shadow: 0 0 12px color-mix(in srgb, var(--t) 60%, transparent); }
.front-line span { grid-area: name; font-size: 11px; color: #d6e1ef; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.front-line em { grid-area: amt; font-style: normal; font-size: 10px; color: #9fb6cd; white-space: nowrap; }
.front-line p { grid-area: bar; margin: 4px 0 0; height: 4px; border-radius: 2px; background: rgba(58,92,140,.4); overflow: hidden; }
.front-line p i { display: block; height: 100%; border-radius: 2px; background: linear-gradient(90deg, color-mix(in srgb, var(--t) 60%, #fff 0%), var(--t)); box-shadow: 0 0 8px var(--t); }


/* ---- 交互状态 ---- */
button.k { display: block; width: 100%; text-align: left; font: inherit; color: inherit; cursor: pointer; transition: transform .15s, box-shadow .2s, border-color .2s; }
button.k:hover { transform: translateY(-1px); border-color: color-mix(in srgb, var(--k) 70%, transparent); }
.k.on { border-color: var(--k); box-shadow: 0 0 0 1px var(--k), 0 0 18px color-mix(in srgb, var(--k) 40%, transparent), inset 0 0 22px color-mix(in srgb, var(--k) 16%, transparent); }
.k-red { --k: #ff7a8a; }
.k > i, .k small, .k b, .k > span { pointer-events: none; }
.panel h4 small { margin-left: 6px; font-size: 10.5px; font-weight: 500; color: #7f96b4; }
.legend button { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: #b3c3d8; font: inherit; font-size: 10.5px; cursor: pointer; box-shadow: none; font-weight: 500; }
.legend button:hover { border-color: rgba(120,180,255,.35); color: #eaf3ff; box-shadow: none; }
.legend button.on { border-color: var(--c); color: #fff; background: color-mix(in srgb, var(--c) 18%, transparent); }
.legend button.high { --c: #20e0a0; } .legend button.mid { --c: #ffc83d; } .legend button.low { --c: #ff5c69; }
.legend button i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--c); box-shadow: 0 0 6px var(--c); }
.prov.hot { cursor: pointer; }
.prov.hot:hover { fill-opacity: .95 !important; stroke: #bfe9ff; }
.prov.picked { fill: #2a9bff; fill-opacity: .95 !important; stroke: #e6f7ff; stroke-width: 1.8; filter: drop-shadow(0 0 8px rgba(80,190,255,.9)); }
.prov.faded { opacity: .45; }
.prov:focus-visible { outline: none; stroke: #fff; stroke-width: 2; }
.mk.off { opacity: .16; pointer-events: none; }
.mk.hov .halo, .mk.sel .halo { stroke-width: 2.8; fill: color-mix(in srgb, var(--c) 45%, transparent); }
.mk .lock { fill: none; stroke: #fff; stroke-width: 1.6; stroke-dasharray: 4 3; transform-origin: 0 0; animation: bm-spin 6s linear infinite reverse; }
.tag { pointer-events: auto; cursor: pointer; }
.tag.sel rect:not(.bar) { stroke: #fff; stroke-width: 1.6; }
.tip em { font-style: normal; font-size: 10px; color: #36dcf0; }

.intel { --c: #36dcf0; position: absolute; right: 6px; top: 4px; bottom: 4px; z-index: 3; width: min(360px, 46%); display: flex; flex-direction: column; gap: 7px; padding: 10px 12px; overflow-y: auto; scrollbar-width: thin; border: 1px solid color-mix(in srgb, var(--c) 55%, transparent); border-radius: 10px; background: linear-gradient(180deg, rgba(10,30,62,.97), rgba(6,20,44,.97)); box-shadow: 0 0 24px color-mix(in srgb, var(--c) 25%, transparent), 0 8px 26px rgba(0,0,0,.5); animation: bm-in .22s ease-out; }
.intel.high { --c: #20e0a0; } .intel.mid { --c: #ffc83d; } .intel.low { --c: #ff5c69; }
.intel > header { display: flex; align-items: flex-start; gap: 8px; padding-bottom: 7px; border-bottom: 1px solid rgba(88,142,208,.25); }
.intel > header > div { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.intel > header b { font-size: 13px; color: #f3f8ff; line-height: 1.35; }
.intel > header small { font-size: 10px; color: #7f96b4; margin-top: 2px; }
.intel .pill { margin-top: 1px; font-size: 12px; padding: 2px 7px; }
.intel .x { flex: none; width: 24px; height: 24px; padding: 0; border-radius: 6px; font-size: 16px; line-height: 1; }
.intel-money { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.intel-money > div { padding: 7px 9px; border: 1px solid rgba(74,138,214,.28); border-radius: 8px; background: rgba(22,48,86,.45); display: flex; flex-direction: column; }
.intel-money small { font-size: 10px; color: #9fb6cd; }
.intel-money b { font-size: 18px; color: #f3f8ff; font-family: var(--num); line-height: 1.25; }
.intel-money span { font-size: 10px; color: #8fb6d2; }
.ratio { margin: -2px 0 0; height: 4px; border-radius: 2px; background: rgba(58,92,140,.45); overflow: hidden; }
.ratio i { display: block; height: 100%; background: linear-gradient(90deg, #3b9bff, #36dcf0); }
.stepper.big span { width: 22px; height: 5px; }
.intel .stepper em { font-size: 11px; color: #e6effb; }
.intel dl { margin: 0; display: grid; grid-template-columns: 1fr; gap: 3px; }
.intel dl > div { display: grid; grid-template-columns: 78px minmax(0, 1fr); gap: 6px; font-size: 11px; }
.intel dt { color: #7f96b4; }
.intel dd { margin: 0; color: #d6e1ef; overflow-wrap: anywhere; }
.intel dd small { margin-left: 4px; font-size: 10px; color: #8fb6d2; }
.intel dd small.bad { color: #ff8a8a; font-weight: 600; }
.link { padding: 0; border: 0; background: none; box-shadow: none; color: #36dcf0; font: inherit; font-weight: 600; cursor: pointer; text-decoration: underline dotted; }
.link:hover { color: #9ff0ff; box-shadow: none; } .link:disabled { color: #7f96b4; cursor: default; text-decoration: none; }
.alerts { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 3px; }
.alerts li { display: flex; gap: 6px; align-items: flex-start; padding: 4px 7px; border-radius: 6px; font-size: 10.5px; color: #ffd9a8; background: rgba(255,170,60,.1); border: 1px solid rgba(255,170,60,.25); }
.alerts li i { flex: none; font-size: 12px; color: #ffb86b; display: inline-grid; margin-top: 1px; }
.remark { margin: 0; font-size: 10.5px; color: #9fb6cd; }
.intel footer { display: flex; gap: 8px; margin-top: auto; padding-top: 6px; }
.intel footer button { flex: 1; padding: 7px 10px; font-size: 12px; }
.intel footer .primary { background: linear-gradient(90deg, rgba(20,150,210,.95), rgba(12,96,160,.85)); border-color: rgba(64,200,255,.8); box-shadow: 0 0 12px rgba(30,170,255,.4); }

.theater-rank p small { margin-left: 4px; font-size: 9.5px; font-weight: 400; color: #7f96b4; }
.theater-rank li { display: block; }
.theater-rank li button { width: 100%; display: grid; grid-template-columns: 14px 1fr auto auto; grid-template-rows: auto 3px; align-items: center; gap: 1px 6px; padding: 2px 4px; border: 1px solid transparent; border-radius: 5px; background: transparent; box-shadow: none; font: inherit; font-size: 11px; font-weight: 400; color: #d6e1ef; cursor: pointer; text-align: left; }
.theater-rank li button:hover { background: rgba(54,155,255,.12); border-color: rgba(120,180,255,.3); box-shadow: none; color: #fff; }
.theater-rank li button.on { background: rgba(54,155,255,.22); border-color: #36dcf0; }
.theater-rank li button > i { font-style: normal; font-size: 10px; color: #7f96b4; font-family: var(--num); }
.theater-rank li button b { font-family: var(--num); color: #f3f8ff; font-size: 11.5px; }
.theater-rank li button small { font-size: 9.5px; color: #7f96b4; }
.theater-rank li button em { grid-column: 2 / -1; height: 3px; border-radius: 2px; background: rgba(58,92,140,.4); overflow: hidden; }
.theater-rank li button em u { display: block; height: 100%; border-radius: 2px; background: linear-gradient(90deg, #3b9bff, #36dcf0); }

.chips { display: flex; flex-wrap: wrap; gap: 5px; margin: -2px 0 6px; flex: none; }
.chips button { padding: 2px 9px; font-size: 10.5px; font-weight: 500; border-radius: 10px; border-color: rgba(54,220,240,.55); background: rgba(54,220,240,.12); box-shadow: none; }
.chips button.clear { border-color: rgba(127,150,180,.5); background: transparent; color: #b3c3d8; }
.target-list { overflow-y: auto; justify-content: flex-start; scrollbar-width: thin; padding-right: 2px; }
.target-list li { flex: none; min-height: 58px; cursor: pointer; transition: background .15s, border-color .15s, box-shadow .15s; }
.target-list li:hover, .target-list li.hov { border-color: rgba(120,190,255,.55); background: linear-gradient(90deg, color-mix(in srgb, var(--c) 18%, transparent), rgba(12,34,66,.7) 50%); }
.target-list li.sel { border-color: var(--c); box-shadow: 0 0 0 1px var(--c), 0 0 16px color-mix(in srgb, var(--c) 30%, transparent); }
.target-list li:focus-visible { outline: 2px solid #53e9e0; outline-offset: 1px; }
.late { margin-left: 6px; padding: 0 5px; border-radius: 6px; font-size: 9px; font-weight: 600; color: #ff9aa5; background: rgba(255,92,105,.14); }
.target-list li.empty { cursor: default; }

.front-line li { padding: 0; display: block; border: 0; background: none; }
.front-line li button { --t: #3b8ff0; width: 100%; height: 100%; display: grid; grid-template-columns: auto 1fr auto; grid-template-areas: 'ph ph ph' 'n name amt' 'bar bar bar'; align-items: baseline; gap: 1px 7px; padding: 6px 10px 7px; border: 1px solid color-mix(in srgb, var(--t) 40%, transparent); border-radius: 8px; background: linear-gradient(180deg, color-mix(in srgb, var(--t) 18%, transparent), color-mix(in srgb, var(--t) 4%, transparent)); box-shadow: none; font: inherit; font-weight: 400; color: inherit; text-align: left; cursor: pointer; transition: border-color .15s, box-shadow .2s, transform .15s; }
.front-line li.win button { --t: #22c493; }
.front-line li button:hover:not(:disabled) { transform: translateY(-1px); border-color: var(--t); box-shadow: 0 0 12px color-mix(in srgb, var(--t) 35%, transparent); color: inherit; }
.front-line li button.on { border-color: var(--t); box-shadow: 0 0 0 1px var(--t), 0 0 16px color-mix(in srgb, var(--t) 45%, transparent); }
.front-line li button:disabled { cursor: default; opacity: .55; }
@keyframes bm-in { from { opacity: 0; transform: translateX(10px); } to { opacity: 1; transform: none; } }

@keyframes bm-spin { to { transform: rotate(-360deg); } }
@keyframes bm-pulse { 0% { transform: scale(1); opacity: .9; } 100% { transform: scale(2.6); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .sweep, .mk .pulse { animation: none; } }
@media (max-height: 820px) and (min-width: 901px) {
  .intel { width: min(330px, 50%); padding: 8px 10px; gap: 5px; } .intel .remark, .intel dl > div:nth-child(n+6) { display: none; }
  .target-list li { min-height: 46px; } .front-line li button { padding: 4px 8px 5px; }
  .battle { gap: 7px; }
  .battle-head .command-intro p { display: none; }
  .battle-head .command-intro h3 { font-size: 17px; }
  .k { padding: 6px 12px 5px; } .k b { font-size: 19px; margin: 2px 0 1px; } .k > i { width: 24px; height: 24px; font-size: 14px; top: 7px; }
  .panel { padding: 7px 10px; } .panel > header { padding-bottom: 4px; margin-bottom: 4px; } .panel header p { display: none; }
  .t-main small { display: none; } .stepper { margin-top: 2px; }
  .front-line li { padding: 4px 8px 5px; } .front-line b { font-size: 16px; } .front-line small { display: none; }
  .theater-rank { width: 168px; padding: 6px 8px; }
}
@media (max-width: 1100px) {
  .battle { overflow: auto; }
  .battle-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .battle-main { grid-template-columns: 1fr; flex: none; }
  .theater { height: 420px; } .targets { min-height: 380px; }
  .front-line { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .battle-head { flex-direction: column; align-items: flex-start; }
  .battle-kpis { grid-template-columns: 1fr 1fr; }
  .theater { height: 320px; } .theater-rank { display: none; }
  .front-line { grid-template-columns: 1fr 1fr; }
}
</style>
