<script setup lang="ts">
const emit = defineEmits<{ navigate: [tab: 'archive' | 'overview' | 'workflow' | 'battle' | 'relation']; regional: [] }>()
const items = [
  ['总览', '⌘', 'overview'], ['客户管理', '▣', 'archive'], ['关系网络', '◎', 'relation'], ['项目机会', '◈', 'battle'], ['经营分析', '▥', 'overview'], ['风险雷达', '◉', 'overview'], ['组织协同', '⊞', 'regional'],
] as const
</script>
<template><aside class="dashboard-sidebar"><div class="dashboard-sidebar__logo">CI</div><nav><button v-for="item in items" :key="item[0]" :class="{active:item[2] === 'overview'}" @click="item[2] === 'regional' ? emit('regional') : emit('navigate', item[2] as 'archive' | 'overview' | 'workflow' | 'battle' | 'relation')"><b>{{ item[1] }}</b><span>{{ item[0] }}</span></button></nav><button class="dashboard-sidebar__settings" aria-label="系统设置">⚙<span>设置</span></button></aside></template>
<style scoped lang="scss">
.dashboard-sidebar{width:88px;align-self:stretch;display:flex;flex-direction:column;flex:none;border-right:1px solid rgba(69,143,201,.18);background:#071426;color:#8fafcb}.dashboard-sidebar__logo{display:grid;place-items:center;height:72px;color:#3caeff;font-size:17px;font-weight:800;letter-spacing:1px}nav{display:grid;gap:6px;padding:6px 8px}button{position:relative;display:grid;gap:5px;place-items:center;min-height:57px;border:0;border-radius:7px;background:transparent;color:inherit;font-size:10px;cursor:pointer}button b{font-size:17px;font-weight:500}.active,button:hover{background:linear-gradient(90deg,rgba(0,119,255,.25),rgba(0,200,255,.08));color:#fff}.active:before{position:absolute;left:-8px;top:10px;bottom:10px;width:3px;border-radius:0 3px 3px 0;background:#3caeff;content:''}.dashboard-sidebar__settings{margin:auto 8px 14px}.dashboard-sidebar__settings span{font-size:10px}@media(max-width:1366px){.dashboard-sidebar{width:70px}.dashboard-sidebar__logo{height:56px}nav{padding:4px}.dashboard-sidebar button{min-height:49px;font-size:9px}}
</style>
