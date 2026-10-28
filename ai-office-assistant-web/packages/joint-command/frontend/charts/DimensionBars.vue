<script setup lang="ts">
// Horizontal bars for aggregate dimension health. Weight is shown so viewers see which axis moves the total.
defineProps<{ rows: { name: string; weight?: number; score: number | null; hint?: string }[] }>()
const tone = (s: number | null) => s === null ? '#c9d3de' : s >= 80 ? '#2f9e6f' : s >= 60 ? '#d99a1c' : '#cf5d5b'
</script>
<template>
 <ul class="dimbars">
  <li v-for="d in rows" :key="d.name">
   <div class="dimbars-head"><span>{{ d.name }}<em v-if="d.weight != null"> · 权重 {{ d.weight }}%</em></span><b :style="{ color: tone(d.score) }">{{ d.score === null ? '待评估' : d.score }}</b></div>
   <div class="dimbars-track"><span :style="{ width: `${d.score ?? 0}%`, background: tone(d.score) }"/></div>
   <small v-if="d.hint">{{ d.hint }}</small>
  </li>
 </ul>
</template>
<style scoped>
.dimbars{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:13px}
.dimbars-head{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;color:#4d6480}
.dimbars-head em{font-style:normal;color:#93a1b2;font-size:12px}
.dimbars-head b{font-variant-numeric:tabular-nums;font-size:15px}
.dimbars-track{height:8px;border-radius:5px;background:#eef2f6;margin-top:6px;overflow:hidden}
.dimbars-track span{display:block;height:100%;border-radius:5px;transition:width .5s ease}
.dimbars small{display:block;margin-top:4px;color:#93a1b2;font-size:11.5px;line-height:1.5}
</style>
