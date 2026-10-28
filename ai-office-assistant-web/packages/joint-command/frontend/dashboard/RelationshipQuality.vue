<script setup lang="ts">
import { computed } from 'vue'

type Level = { level: number; count: number }
const props = defineProps<{ levels: Level[]; trustedRate: number | null; maxLevel: number }>()

const levelColors = ['#2dcaeb', '#27e5ff', '#3da8ff', '#7566ff', '#ae58ff', '#ffc83d']
const safeMax = computed(() => Math.max(1, props.maxLevel || 0))
const ringRate = computed(() => `${Math.max(0, props.trustedRate || 0) * 3.6}deg`)
function width(count: number) {
  return `${Math.round((Math.max(0, count) / safeMax.value) * 100)}%`
}
</script>

<template>
  <div class="relationship-quality">
    <div class="relationship-quality__summary">
      <div class="quality-ring" :style="{ '--rate': ringRate }">
        <div><strong>{{ trustedRate === null ? '—' : `${trustedRate}%` }}</strong><span>L3+ 关系占比</span></div>
      </div>
    </div>
    <div class="strength-bars" aria-label="关系强度分布">
      <div v-for="item in levels" :key="item.level" class="strength-row">
        <span>L{{ item.level }}</span>
        <div class="track"><i :style="{ width: width(item.count), background: levelColors[item.level] }" /></div>
        <b>{{ item.count }}</b>
      </div>
    </div>
    <p>关系条数统计；同一联系人可有多条关系</p>
  </div>
</template>

<style scoped lang="scss">
.relationship-quality{display:grid;grid-template-columns:minmax(105px,.7fr) minmax(0,1fr);align-items:center;gap:14px;min-height:142px}.quality-ring{width:118px;height:118px;margin:auto;padding:7px;border-radius:50%;background:conic-gradient(var(--yellow,#ffc83d) var(--rate),rgba(58,112,150,.18) 0)}.quality-ring>div{display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%;background:rgba(8,31,52,.97)}.quality-ring strong{color:var(--yellow,#ffc83d);font-size:27px;font-variant-numeric:tabular-nums}.quality-ring span{margin-top:5px;color:var(--text-secondary,#89a9c4);font-size:11px}.strength-bars{display:flex;flex-direction:column;justify-content:center;gap:8px;min-width:0}.strength-row{display:grid;grid-template-columns:22px minmax(0,1fr) 25px;align-items:center;gap:7px;color:var(--text-secondary,#89a9c4);font-size:11px}.track{height:5px;overflow:hidden;border-radius:4px;background:rgba(58,112,150,.18)}.track i{display:block;height:100%;min-width:0;border-radius:inherit}.strength-row b{color:var(--text-primary,#edf7ff);font-size:11px;text-align:right;font-variant-numeric:tabular-nums}.relationship-quality>p{grid-column:1 / -1;margin:0;color:var(--text-muted,#5f819d);font-size:11px;line-height:1.45}@media(max-width:760px){.relationship-quality{grid-template-columns:1fr}.quality-ring{width:104px;height:104px}.strength-bars{gap:6px}}
</style>
