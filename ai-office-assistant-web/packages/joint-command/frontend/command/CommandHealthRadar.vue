<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { crmQualitySettings, type CrmQualitySettings, type CrmUnit, type CrmPerson, type CrmRelation } from '../../../../src/services/personalWorkApi'
import { organizationQuality } from '../organizationQuality'
import { assessmentOverview } from '../assessmentOverview'
import RadarChart from '../charts/RadarChart.vue'
import DimensionBars from '../charts/DimensionBars.vue'

const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[] }>()
const settings = ref<CrmQualitySettings>(), error = ref(''), opened = ref(false)
let request = 0
async function load() {
  const token = ++request
  try { const result = await crmQualitySettings(); if (token === request) { settings.value = result; error.value = '' } }
  catch { if (token === request) { settings.value = undefined; error.value = '评估规则加载失败' } }
}
onMounted(load)
watch(() => props.relations, load)

const company = computed(() => settings.value ? assessmentOverview(organizationQuality(props.units, props.people, props.relations, Date.now(), settings.value.rules, ''), [], [], settings.value.rules).company : null)
const rows = computed(() => company.value?.dimensions.map(d => ({ ...d, hint: `${d.count}/${company.value!.count} 家有据可评` })) || [])
const reference = computed(() => settings.value?.rules.good_threshold ?? 80)
// 虚线 = 当前范围内客户组织综合暂估的真实均值；达标线来自评估规则，仅作对照。
const average = computed(() => company.value?.avg ?? null)
// 雷达标签只放得下四个字，完整名称放在 title 里。
const SHORT: Record<string, string> = { 关键岗位覆盖: '岗位覆盖', 关系质量: '关系质量', 互动有效性: '互动有效', 对接稳定性: '对接稳定', 我方维护责任: '维护责任' }

const CX = 108, CY = 136, R = 52
const LABEL_OFFSET: [number, number, string][] = [[0, -20, 'middle'], [12, -4, 'start'], [6, 15, 'middle'], [-6, 15, 'middle'], [-12, -4, 'end']]
const count = computed(() => Math.max(3, rows.value.length))
const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / count.value
const point = (i: number, r: number) => [CX + r * Math.cos(angle(i)), CY + r * Math.sin(angle(i))] as [number, number]
const poly = (r: number | ((i: number) => number)) => Array.from({ length: count.value }, (_, i) => point(i, typeof r === 'function' ? r(i) : r).join(',')).join(' ')
const levels = computed(() => [0.25, 0.5, 0.75, 1].map(k => poly(R * k)))
const avg = computed(() => average.value === null ? '' : poly((R * average.value) / 100))
const goal = computed(() => poly((R * reference.value) / 100))
const values = computed(() => rows.value.map((d, i) => point(i, (R * (d.score ?? 0)) / 100)))
const valuePoly = computed(() => values.value.map(p => p.join(',')).join(' '))
const labels = computed(() => rows.value.map((d, i) => {
  const [x, y] = point(i, R)
  const [dx, dy, anchor] = LABEL_OFFSET[i % LABEL_OFFSET.length]!
  return { name: d.name, short: SHORT[d.name] || d.name.slice(0, 4), score: d.score, hint: d.hint, x: x + dx, y: y + dy, anchor }
}))
function openDetails() { opened.value = true }
defineExpose({ openDetails })
</script>

<template>
  <div class="cv-health-embedded">
    <template v-if="company && settings && rows.length">
      <button type="button" class="radar-btn" title="公司层五维健康度 · 点击查看评估明细" aria-label="查看公司五维健康度明细" @click="openDetails">
      <svg class="radar" viewBox="0 0 215 236" role="img" :aria-label="`公司层五维健康度：${rows.map(r => `${r.name} ${r.score ?? '待评估'}`).join('，')}；综合暂估 ${average ?? '待评估'} 分`">
        <polygon v-for="(pts, i) in levels" :key="i" :points="pts" class="grid" />
        <line v-for="i in count" :key="'a' + i" :x1="CX" :y1="CY" :x2="point(i - 1, R)[0]" :y2="point(i - 1, R)[1]" class="grid" />
        <polygon :points="goal" class="goal" />
        <polygon v-if="avg" :points="avg" class="avg" />
        <polygon :points="valuePoly" class="val" />
        <circle v-for="(p, i) in values" :key="'p' + i" :cx="p[0]" :cy="p[1]" r="2.6" class="dot" />
        <text v-for="l in labels" :key="l.name" :x="l.x" :y="l.y" :text-anchor="l.anchor" class="lbl">
          <title>{{ l.name }} · {{ l.hint }}</title>
          <tspan :x="l.x" dy="0">{{ l.short }}</tspan>
          <tspan :x="l.x" dy="14" class="lv">{{ l.score ?? '待评估' }}</tspan>
        </text>
      </svg>
      </button>
      <ul class="legend">
        <li :title="`${company.scored}/${company.count} 家客户组织有据可评，均值 ${average ?? '—'} 分`"><i class="yellow" />综合暂估 {{ average ?? '—' }} 分 · {{ company.scored }}/{{ company.count }} 家有据</li>
        <li><i class="grey" />达标线 {{ reference }} 分 · 待评估不记零分</li>
      </ul>
    </template>
    <div v-else class="health-empty">{{ error || (company ? '暂无客户组织可评估' : '正在加载评估规则…') }}<button v-if="error" type="button" @click="load">重试</button></div>
    <el-dialog v-model="opened" title="公司层五维健康度" width="min(920px,96vw)" append-to-body>
      <template v-if="company && settings && rows.length">
        <p>当前授权范围 · {{ company.scored }}/{{ company.count }} 家客户组织有据可评，综合暂估 {{ average ?? '待评估' }} 分；达标线 {{ reference }} 分，缺证据不记零分。</p>
        <div class="health-detail"><RadarChart :axes="rows" :reference="average ?? reference" :size="248" /><DimensionBars :rows="rows" /></div>
      </template>
      <p v-else>{{ error || (company ? '暂无客户组织可评估' : '正在加载评估规则…') }}</p>
    </el-dialog>
  </div>
</template>

<style scoped>
.cv-health-embedded {
  position: relative;
  width: 215px;
  height: 100%;
  min-height: 264px;
}
.radar-btn {
  position: absolute;
  left: 0;
  top: 6px;
  width: 215px;
  height: 236px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.radar-btn:hover .val {
  filter: drop-shadow(0 0 7px rgba(50, 227, 240, 0.9));
}
.radar {
  width: 215px;
  height: 236px;
  overflow: visible;
}
.grid {
  fill: none;
  stroke: rgba(92, 140, 200, 0.35);
  stroke-width: 1;
}
.avg {
  fill: none;
  stroke: #f2b632;
  stroke-width: 1.3;
  stroke-dasharray: 4 3;
}
.goal {
  fill: none;
  stroke: rgba(150, 175, 205, 0.55);
  stroke-width: 1;
  stroke-dasharray: 2 3;
}
.val {
  fill: rgba(40, 220, 240, 0.28);
  stroke: #32e3f0;
  stroke-width: 2;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 4px rgba(50, 227, 240, 0.7));
}
.dot {
  fill: #7ff3ff;
}
.lbl {
  font-size: 10.5px;
  fill: #d6e1ef;
}
.lv {
  font-family: var(--cv-font-num);
  fill: #c3d1e3;
}
.legend {
  position: absolute;
  left: 13px;
  right: 0;
  top: 252px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 11px;
  line-height: 17px;
  color: #b6c6db;
  white-space: nowrap;
}
.legend li {
  overflow: hidden;
  text-overflow: ellipsis;
}
.legend i {
  display: inline-block;
  width: 14px;
  height: 0;
  margin-right: 10px;
  vertical-align: middle;
  border-top: 2px dashed;
}
.cyan {
  color: #32e3f0;
}
.yellow {
  color: #f2b632;
}
.grey {
  color: rgba(150, 175, 205, 0.7);
}
.health-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 60px 0;
  font-size: 12px;
  color: #b6c6db;
  text-align: center;
}
.health-empty button {
  border: 1px solid #3c7698;
  border-radius: 6px;
  background: #123653;
  padding: 5px 10px;
  color: #d6f6fb;
  cursor: pointer;
}
.health-detail {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 24px;
  align-items: center;
}
.health-detail :deep(.radar) {
  width: 100%;
}
@media (max-width: 650px) {
  .health-detail {
    grid-template-columns: 1fr;
    justify-items: center;
  }
  .health-detail :deep(.dimbars) {
    width: 100%;
  }
}
</style>
