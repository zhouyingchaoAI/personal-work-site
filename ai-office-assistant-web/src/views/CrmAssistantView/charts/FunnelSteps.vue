<script setup lang="ts">
import { computed } from 'vue'
// Penetration funnel: how customer organizations narrow from "in scope" down to "role coverage met".
// Width is relative to the first (largest) step so the drop-off at each stage is visible.
const props = defineProps<{ steps: { label: string; value: number; hint?: string }[] }>()
const base = computed(() => props.steps[0]?.value || 0)
const shades = ['#3f74ab', '#5a89ba', '#7aa1c8', '#9bbad6']
</script>
<template>
 <ol class="funnel">
  <li v-for="(s, i) in steps" :key="s.label">
   <div class="funnel-row">
    <span class="funnel-label">{{ s.label }}</span>
    <b class="funnel-value">{{ s.value }}</b>
   </div>
   <div class="funnel-track"><span :style="{ width: `${base ? Math.max(4, s.value / base * 100) : 0}%`, background: shades[Math.min(i, 3)] }"/></div>
   <small v-if="s.hint">{{ s.hint }}<template v-if="i > 0 && steps[i-1].value"> · 留存 {{ Math.round(s.value / steps[i-1].value * 100) }}%</template></small>
  </li>
 </ol>
</template>
<style scoped>
.funnel{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px}
.funnel-row{display:flex;justify-content:space-between;align-items:baseline}
.funnel-label{font-size:13px;color:#4d6480;font-weight:600}
.funnel-value{font-variant-numeric:tabular-nums;font-size:16px;color:#294f78}
.funnel-track{height:10px;border-radius:6px;background:#eef2f6;margin-top:5px;overflow:hidden}
.funnel-track span{display:block;height:100%;border-radius:6px;transition:width .5s ease}
.funnel small{display:block;margin-top:4px;color:#93a1b2;font-size:11.5px}
</style>
