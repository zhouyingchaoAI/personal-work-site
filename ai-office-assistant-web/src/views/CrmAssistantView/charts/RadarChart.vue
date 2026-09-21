<script setup lang="ts">
import { computed } from 'vue'
// Dependency-free SVG radar for the 0–100 dimension model. Null scores render as an open marker at the axis origin (待评估), never as a real zero.
const props = withDefaults(defineProps<{
  axes: { name: string; score: number | null; weight?: number }[]
  reference?: number | null
  size?: number
  accent?: string
}>(), { reference: null, size: 220, accent: '#3f74ab' })
const R = computed(() => props.size / 2 - 34)
const cx = computed(() => props.size / 2)
const cy = computed(() => props.size / 2)
const angleAt = (i: number) => (Math.PI * 2 * i) / props.axes.length - Math.PI / 2
const pointAt = (i: number, ratio: number) => {
  const a = angleAt(i)
  return [cx.value + Math.cos(a) * R.value * ratio, cy.value + Math.sin(a) * R.value * ratio]
}
const rings = [0.25, 0.5, 0.75, 1]
const ringPath = (ratio: number) => props.axes.map((_, i) => pointAt(i, ratio).join(',')).join(' ')
const dataPath = computed(() => props.axes.map((d, i) => pointAt(i, Math.max(0, Math.min(100, d.score ?? 0)) / 100).join(',')).join(' '))
const refPath = computed(() => props.reference == null ? '' : props.axes.map((_, i) => pointAt(i, props.reference! / 100).join(',')).join(' '))
// Compact axis labels keep long dimension names from clipping the viewBox; full names live in the adjacent bars/detail.
const short: Record<string, string> = { 关键岗位覆盖: '覆盖', 关系质量: '关系', 互动有效性: '互动', 对接稳定性: '稳定', 我方维护责任: '责任', 维系及时性: '维系' }
const labels = computed(() => props.axes.map((d, i) => {
  const [x, y] = pointAt(i, 1.18)
  const a = angleAt(i)
  return { name: short[d.name] || d.name, score: d.score, weight: d.weight, x, y, anchor: Math.abs(Math.cos(a)) < 0.3 ? 'middle' : Math.cos(a) > 0 ? 'start' : 'end' }
}))
</script>
<template>
 <svg :viewBox="`0 0 ${size} ${size}`" class="radar" role="img" :aria-label="`维度雷达图：${axes.map(a => `${a.name}${a.score ?? '待评估'}`).join('，')}`">
  <polygon v-for="r in rings" :key="r" :points="ringPath(r)" class="radar-ring"/>
  <line v-for="(_, i) in axes" :key="i" :x1="cx" :y1="cy" :x2="pointAt(i, 1)[0]" :y2="pointAt(i, 1)[1]" class="radar-spoke"/>
  <polygon v-if="refPath" :points="refPath" class="radar-ref"/>
  <polygon :points="dataPath" class="radar-area" :style="{ fill: accent, stroke: accent }"/>
  <template v-for="(d, i) in axes" :key="`p${i}`">
   <circle v-if="d.score !== null" :cx="pointAt(i, d.score / 100)[0]" :cy="pointAt(i, d.score / 100)[1]" r="3.2" :fill="accent"/>
   <circle v-else :cx="cx" :cy="cy" r="3" class="radar-null"/>
  </template>
  <text v-for="(l, i) in labels" :key="`l${i}`" :x="l.x" :y="l.y" :text-anchor="l.anchor" class="radar-label">
   <tspan :x="l.x" dy="0">{{ l.name }}</tspan>
   <tspan :x="l.x" dy="13" class="radar-label-score">{{ l.score === null ? '待评估' : l.score }}</tspan>
  </text>
 </svg>
</template>
<style scoped>
.radar{width:100%;height:auto;max-width:260px;overflow:visible}
.radar-ring{fill:none;stroke:#e5ecf4;stroke-width:1}
.radar-spoke{stroke:#e5ecf4;stroke-width:1}
.radar-ref{fill:none;stroke:#c7a24a;stroke-width:1.2;stroke-dasharray:4 4;opacity:.8}
.radar-area{fill-opacity:.16;stroke-width:2;stroke-linejoin:round}
.radar-null{fill:#fff;stroke:#b7c2d0;stroke-width:1.4}
.radar-label{font-size:11px;fill:#5a6f86;font-weight:600}
.radar-label-score{font-size:10px;fill:#8493a5;font-weight:500}
</style>
