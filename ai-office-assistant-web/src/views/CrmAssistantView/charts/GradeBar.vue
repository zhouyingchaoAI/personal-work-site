<script setup lang="ts">
import { computed } from 'vue'
// Stacked distribution bar across the four provisional grades. Zero-width segments are dropped so the legend stays readable.
const props = defineProps<{
  segments: { label: string; value: number; tone: 'good' | 'fair' | 'weak' | 'pending' }[]
  legend?: boolean
}>()
const colors = { good: '#2f9e6f', fair: '#d99a1c', weak: '#cf5d5b', pending: '#9aa8b8' }
const total = computed(() => props.segments.reduce((n, s) => n + s.value, 0))
const shown = computed(() => props.segments.filter(s => s.value > 0))
</script>
<template>
 <div class="gradebar">
  <div class="gradebar-track" role="img" :aria-label="segments.map(s => `${s.label}${s.value}`).join('，')">
   <span v-for="s in shown" :key="s.label" class="gradebar-seg" :style="{ width: `${total ? s.value / total * 100 : 0}%`, background: colors[s.tone] }" :title="`${s.label} ${s.value}`"/>
   <span v-if="!total" class="gradebar-empty">暂无数据</span>
  </div>
  <div v-if="legend !== false" class="gradebar-legend">
   <span v-for="s in segments" :key="s.label"><i :style="{ background: colors[s.tone] }"/>{{ s.label }} {{ s.value }}</span>
  </div>
 </div>
</template>
<style scoped>
.gradebar{display:flex;flex-direction:column;gap:8px}
.gradebar-track{display:flex;height:12px;border-radius:7px;overflow:hidden;background:#eef2f6}
.gradebar-seg{display:block;height:100%}
.gradebar-seg+.gradebar-seg{box-shadow:-1px 0 0 rgba(255,255,255,.6)}
.gradebar-empty{margin:auto;font-size:11px;color:#9aa8b8}
.gradebar-legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#6c7d90}
.gradebar-legend span{display:inline-flex;align-items:center;gap:5px}
.gradebar-legend i{width:9px;height:9px;border-radius:3px;display:inline-block}
</style>
