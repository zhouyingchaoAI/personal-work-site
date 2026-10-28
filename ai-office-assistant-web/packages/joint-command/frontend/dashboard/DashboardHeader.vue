<script setup lang="ts">
import { ref } from 'vue'

type CommandMode = 'manager' | 'regional' | 'joint'
type NavigationTarget = 'archive' | 'overview' | 'workflow' | 'battle' | 'relation'

const props = defineProps<{
  title: string
  description?: string
  scope: string
  responsibility: string
  activeMode: CommandMode
  modes: { value: CommandMode; label: string; description: string }[]
  expanded: boolean
  commandTime: string
}>()

const emit = defineEmits<{
  mode: [value: CommandMode]
  navigate: [tab: NavigationTarget]
  network: []
  search: [query: string]
  refresh: []
  export: []
  showcase: []
  toggle: []
}>()

const query = ref('')
function submitSearch() {
  const keyword = query.value.trim()
  if (keyword) emit('search', keyword)
}
</script>

<template>
  <header class="cockpit-head">
    <div class="cockpit-brand">
      <span class="eyebrow">CUSTOMER INTELLIGENCE · 五位一体</span>
      <h2>{{ title }}</h2>
      <p>{{ description }} · {{ scope }} · {{ responsibility }}</p>
      <div class="cockpit-mode-switch" aria-label="驾驶舱形态">
        <button v-for="item in modes" :key="item.value" :class="{ selected: activeMode === item.value }" :aria-pressed="activeMode === item.value" @click="emit('mode', item.value)">{{ item.label }}</button>
      </div>
    </div>
    <nav v-if="expanded" class="cockpit-deck-nav" aria-label="指挥大屏导航">
      <button class="active">全局概览</button>
      <button @click="emit('navigate', 'archive')">客户管理</button>
      <button @click="emit('mode', 'regional')">区域指挥</button>
      <button @click="emit('network')">关系网络</button>
      <button @click="emit('navigate', 'workflow')">行动管理</button>
      <button @click="emit('navigate', 'overview')">数据分析</button>
    </nav>
    <div class="cockpit-status">
      <span v-if="expanded">实时态势 · {{ commandTime }}</span>
      <div class="cockpit-tools">
        <label class="cockpit-search">
          <input v-model="query" placeholder="搜索客户、联系人、项目…" aria-label="搜索客户、联系人、项目" @keyup.enter="submitSearch" />
          <button :disabled="!query.trim()" @click="submitSearch">搜索</button>
        </label>
        <button @click="emit('refresh')">刷新数据</button>
        <button @click="emit('export')">导出报告</button>
        <button @click="emit('showcase')">全息作战大屏</button>
        <button :aria-pressed="expanded" @click="emit('toggle')">{{ expanded ? '退出大屏' : '大屏模式' }}</button>
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
.cockpit-head{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:24px;flex-wrap:wrap;padding-bottom:0;color:#d5e5fa}.cockpit-head p{margin:0;font-size:12px;color:#9eb9d4}.cockpit-head h2{margin:8px 0;font-size:28px;letter-spacing:3px;color:#f2f9ff}.eyebrow{font-size:10px;letter-spacing:2px;color:#53e9e0}.cockpit-brand{min-width:max-content}.cockpit-status{display:flex;align-items:center;justify-content:flex-end;gap:18px;color:#9ac4dd;font-size:11px;font-variant-numeric:tabular-nums;white-space:nowrap}.cockpit-deck-nav{display:flex;align-items:stretch;min-width:480px;overflow:hidden;border:1px solid #24577d;border-radius:8px;background:#061b32c9}.cockpit-deck-nav button{min-width:76px;padding:9px 13px;border:0;border-right:1px solid #1b4163;background:transparent;color:#a5c7dd;font-size:12px}.cockpit-deck-nav .active,.cockpit-deck-nav button:hover{background:linear-gradient(180deg,#1664a8,#103f75);color:#effcff;box-shadow:inset 0 0 18px #36c5ff44}.cockpit-deck-nav .active{font-weight:700}.cockpit-mode-switch{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.cockpit-mode-switch button{border:1px solid #3b678d;border-radius:999px;background:#102a44;padding:5px 10px;font-size:11px;color:#aac5df;cursor:pointer}.cockpit-mode-switch .selected{border-color:#53e9e0;background:#164c5d;color:#d8fffc;box-shadow:inset 0 0 0 1px #53e9e044}.cockpit-tools{display:flex;gap:10px;flex-wrap:wrap}.cockpit-tools button{border:1px solid #3b678d;border-radius:6px;background:#143254;padding:9px 14px;font:inherit;font-size:12px;color:#c3f9f5;cursor:pointer}.cockpit-search{display:flex;overflow:hidden;border:1px solid #3b678d;border-radius:6px;background:#0b2947}.cockpit-search input{width:clamp(150px,13vw,220px);border:0;background:transparent;padding:0 10px;color:#e2f5ff;font:inherit;font-size:12px;outline:0}.cockpit-search input::placeholder{color:#7193ae}.cockpit-search button{border:0;border-left:1px solid #3b678d;border-radius:0;padding:8px 10px}.cockpit-search button:disabled{cursor:not-allowed;opacity:.5}

@media(max-width:1500px) and (min-width:1101px){.cockpit-head{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:7px}.cockpit-brand{min-width:0}.cockpit-deck-nav{grid-column:1 / -1;grid-row:2;justify-self:center;min-width:0}.cockpit-status{min-width:0;gap:8px}.cockpit-tools{justify-content:flex-end;gap:6px}.cockpit-tools button{padding:7px 9px;font-size:11px}.cockpit-search input{width:clamp(120px,14vw,180px)}}
@media(max-height:760px){.eyebrow{display:none}.cockpit-head h2{font-size:21px}}
</style>
