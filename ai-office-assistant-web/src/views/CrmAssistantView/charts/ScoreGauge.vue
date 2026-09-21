<script setup lang="ts">
import { computed } from 'vue'
// Circular arc gauge for a single provisional 0–100 score. Null renders as a dashed "待评估" ring.
const props = withDefaults(defineProps<{
  score: number | null
  grade?: string
  caption?: string
  size?: number
}>(), { grade: '', caption: '', size: 132 })
const stroke = 11
const r = computed(() => props.size / 2 - stroke)
const circ = computed(() => 2 * Math.PI * r.value)
const pct = computed(() => Math.max(0, Math.min(100, props.score ?? 0)))
const tone = computed(() => props.score === null ? '#9aa8b8' : pct.value >= 80 ? '#2f9e6f' : pct.value >= 60 ? '#d99a1c' : '#cf5d5b')
const dash = computed(() => `${circ.value * pct.value / 100} ${circ.value}`)
</script>
<template>
 <div class="gauge">
  <svg :viewBox="`0 0 ${size} ${size}`" :style="{ width: size + 'px' }" role="img" :aria-label="`评分 ${score === null ? '待评估' : score}`">
   <circle :cx="size/2" :cy="size/2" :r="r" fill="none" stroke="#eaf0f7" :stroke-width="stroke"/>
   <circle v-if="score !== null" :cx="size/2" :cy="size/2" :r="r" fill="none" :stroke="tone" :stroke-width="stroke"
     stroke-linecap="round" :stroke-dasharray="dash" :transform="`rotate(-90 ${size/2} ${size/2})`" class="gauge-arc"/>
   <circle v-else :cx="size/2" :cy="size/2" :r="r" fill="none" stroke="#c9d3de" :stroke-width="stroke" stroke-dasharray="3 6"/>
   <text :x="size/2" :y="size/2 - 2" text-anchor="middle" class="gauge-value" :fill="tone">{{ score === null ? '—' : score }}</text>
   <text :x="size/2" :y="size/2 + 18" text-anchor="middle" class="gauge-unit">{{ score === null ? '待评估' : '分 · 暂估' }}</text>
  </svg>
  <span v-if="grade" class="gauge-grade" :style="{ color: tone }">{{ grade }}</span>
  <span v-if="caption" class="gauge-caption">{{ caption }}</span>
 </div>
</template>
<style scoped>
.gauge{display:flex;flex-direction:column;align-items:center;gap:4px}
.gauge-arc{transition:stroke-dasharray .5s ease}
.gauge-value{font-size:34px;font-weight:700;font-variant-numeric:tabular-nums}
.gauge-unit{font-size:11px;fill:#8493a5}
.gauge-grade{font-size:13px;font-weight:600}
.gauge-caption{font-size:12px;color:#7c8c9f;text-align:center;line-height:1.5}
</style>
