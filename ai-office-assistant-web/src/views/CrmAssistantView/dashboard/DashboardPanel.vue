<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>
<template>
  <section class="dashboard-panel">
    <header><div><h3>{{ title }}</h3><small v-if="subtitle">{{ subtitle }}</small></div><div class="dashboard-panel__extra"><slot name="extra" /></div></header>
    <div class="dashboard-panel__body"><slot /></div>
  </section>
</template>
<style scoped lang="scss">
.dashboard-panel{min-width:0;min-height:0;padding:14px;border:1px solid var(--panel-border,rgba(69,143,201,.28));border-radius:11px;background:linear-gradient(180deg,rgba(8,35,59,.94),rgba(7,27,47,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}h3{margin:0;color:var(--text-primary,#edf7ff);font-size:15px}small{display:block;margin-top:3px;color:var(--text-muted,#5f819d);font-size:11px}.dashboard-panel__extra{display:flex;gap:10px;align-items:center}.dashboard-panel__body{min-height:0}
</style>
