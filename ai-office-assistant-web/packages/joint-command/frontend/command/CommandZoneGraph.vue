<script setup lang="ts">
import { computed, ref } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import { img } from './img'

// 五类客户合并面板：左侧分区光点图（总部为中心，客户与四类外部单位环绕），右侧五类客户布局列表。
// 点击光点或列表行都可进入该类组织的关系网络。
const props = defineProps<{
  rows: { name: string; color: string; units: number; contacts: number; percent: number }[]
  others: number
  total: { units: number; contacts: number }
}>()
const emit = defineEmits<{ network: [type: string] }>()
const stats = computed(() => Object.fromEntries(props.rows.map(row => [row.name, { units: row.units, contacts: row.contacts }])))

const ZONES = [
  { key: 'hq', name: '总部', node: 'yellow', x: 195, y: 162, d: 92, inner: true, type: '' },
  { key: 'customer', name: '客户', node: 'purple', x: 195, y: 66, d: 60, inner: true, type: '' },
  { key: 'owner', name: '业主单位', node: 'orange', x: 73, y: 119, d: 62, label: true, type: '业主单位' },
  { key: 'general', name: '总包单位', node: 'gold', x: 316, y: 119, d: 62, label: true, type: '总包单位' },
  { key: 'design', name: '设计单位', node: 'blue', x: 112, y: 216, d: 62, label: true, type: '设计单位' },
  { key: 'vendor', name: '厂商', node: 'teal', x: 278, y: 216, d: 62, label: true, type: '厂商' },
]
const LINE_COLOR: Record<string, string> = { purple: '#b58cff', orange: '#ff8a3a', gold: '#ffc94a', blue: '#3a9cff', teal: '#2de3d6' }

const active = ref('')
const hq = ZONES[0]!
const spokes = ZONES.filter(n => n.key !== 'hq')
const activeNode = computed(() => ZONES.find(n => n.key === active.value))
const activeStats = computed(() => {
  const node = activeNode.value
  if (!node) return null
  if (node.key === 'customer') return props.total
  return stats.value[node.name] || null
})
function toggle(key: string) {
  if (key === 'hq') { emit('network', ''); return }
  active.value = active.value === key ? '' : key
}
function expand() {
  const node = activeNode.value
  if (!node) return
  emit('network', node.type)
  active.value = ''
}
</script>

<template>
  <CommandPanel class="cv-zone" title="五类客户 · 健康度与布局" more="详情" @more="emit('network', '')">
    <div class="zone-health"><slot name="health" /></div>

    <div class="zone-graph-area">
    <div class="stage" aria-hidden="true">
      <div class="floor" />
      <div class="orbit o1" />
      <div class="orbit o2" />
      <div class="orbit o3" />
      <div class="orbit o4" />
    </div>

    <svg class="links" viewBox="0 0 388 280" aria-hidden="true">
      <defs>
        <radialGradient id="cv-zone-dot">
          <stop offset="0" stop-color="#fff" />
          <stop offset=".4" stop-color="#ffb35a" />
          <stop offset="1" stop-color="#ff7a22" stop-opacity="0" />
        </radialGradient>
      </defs>
      <g v-for="n in spokes" :key="n.key">
        <path :id="'cv-zone-' + n.key" :d="`M${hq.x} ${hq.y}L${n.x} ${n.y}`" :stroke="LINE_COLOR[n.node]" class="spoke" :class="{ on: active === n.key }" />
        <circle r="5" fill="url(#cv-zone-dot)">
          <animateMotion dur="2.6s" repeatCount="indefinite" :begin="(n.x % 7) * 0.3 + 's'">
            <mpath :href="'#cv-zone-' + n.key" />
          </animateMotion>
        </circle>
      </g>
    </svg>

    <button
      v-for="n in ZONES"
      :key="n.key"
      type="button"
      class="node"
      :class="[n.key, { active: active === n.key }]"
      :style="{ left: n.x / 10 + 'rem', top: n.y / 10 + 'rem', width: n.d / 10 + 'rem', height: n.d / 10 + 'rem' }"
      :aria-label="n.key === 'hq' ? '打开客户关系网络' : `${n.name}分区`"
      :aria-expanded="n.key === 'hq' ? undefined : active === n.key"
      @click="toggle(n.key)"
    >
      <img :src="img('node-' + n.node)" alt="" />
      <span v-if="n.inner" class="inner">{{ n.name }}</span>
      <span v-if="n.label" class="outer">{{ n.name }}</span>
    </button>

    <transition name="pop">
      <div
        v-if="activeNode && activeStats"
        class="bubble"
        role="status"
        :style="{ left: activeNode.x / 10 + 'rem', top: (activeNode.y - activeNode.d / 2 - 8) / 10 + 'rem' }"
      >
        <b>{{ activeNode.name }}</b>
        <span>单位 {{ activeStats.units }}</span>
        <span>联系人 {{ activeStats.contacts }}</span>
        <button type="button" @click="expand">展开组织 ↗</button>
      </div>
    </transition>
    </div>

    <div class="zone-layout" aria-label="五类客户布局">
      <ul class="zl-rows">
        <li v-for="row in rows" :key="row.name" :style="{ '--k': row.color }">
          <button type="button" :title="`${row.name}：${row.units} 家单位，${row.contacts} 位联系人，占全部客户 ${row.percent.toFixed(1)}%；点击查看该类组织`" @click="emit('network', row.name)">
            <div class="line">
              <i class="dot" />
              <span class="name">{{ row.name }}</span>
              <span class="val"><CountUp :value="row.units" /><em>/ <CountUp :value="row.contacts" /></em></span>
            </div>
            <div class="cv-bar-track"><div class="cv-bar-fill" :style="{ width: row.percent + '%' }" /></div>
          </button>
        </li>
      </ul>
      <p v-if="others" class="zl-note">另有 {{ others }} 家其他类型客户</p>
    </div>
  </CommandPanel>
</template>

<style scoped>
.cv-zone :deep(.cv-panel__head) {
  position: relative;
  z-index: 2;
}
.cv-zone {
  overflow: hidden;
  min-height: 280px;
  border-color: rgba(74, 150, 230, 0.5);
  background:
    radial-gradient(ellipse 60% 50% at 50% 62%, rgba(30, 110, 200, 0.35), transparent 70%),
    linear-gradient(180deg, rgba(10, 34, 70, 0.92), rgba(6, 22, 48, 0.95));
}
.zone-health {
  position: absolute;
  left: 6px;
  top: 48px;
  bottom: 14px;
  width: 220px;
  z-index: 1;
}
.zone-graph-area {
  position: absolute;
  left: 244px;
  top: 0;
  width: 388px;
  height: 280px;
}
.zone-layout {
  position: absolute;
  left: 654px;
  right: 16px;
  top: 52px;
  bottom: 16px;
  display: flex;
  flex-direction: column;
  z-index: 1;
}
.zl-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-around;
}
.zl-rows button {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.zl-rows button:hover .name {
  color: #fff;
}
.line {
  display: flex;
  align-items: center;
  height: 20px;
}
.dot {
  width: 12px;
  height: 12px;
  flex: none;
  margin-right: 10px;
  border-radius: 50%;
  background: var(--k);
  box-shadow: 0 0 6px var(--k);
}
.name {
  flex: 1;
  font-size: 13.5px;
  color: #dbe5f2;
  white-space: nowrap;
}
.val .num {
  font-size: 15px;
  color: #eef4fc;
}
.val em {
  margin-left: 4px;
  font-style: normal;
  font-size: 13px;
  color: #8ea4c2;
}
.val em .num {
  font-size: 13.5px;
  color: #8ea4c2;
}
.zone-layout .cv-bar-track {
  height: 7px;
  margin-top: 5px;
}
.zone-layout .cv-bar-fill {
  background: linear-gradient(90deg, color-mix(in srgb, var(--k) 70%, #000), var(--k));
}
.zl-note {
  margin: 4px 0 0;
  font-size: 10px;
  color: #8ea4c2;
}
.stage {
  position: absolute;
  inset: 0;
  perspective: 500px;
  pointer-events: none;
}
.floor {
  position: absolute;
  left: -40px;
  right: -40px;
  top: 90px;
  height: 260px;
  transform: rotateX(62deg);
  transform-origin: 50% 30%;
  background:
    repeating-linear-gradient(0deg, rgba(70, 150, 240, 0.12) 0 1px, transparent 1px 22px),
    repeating-linear-gradient(90deg, rgba(70, 150, 240, 0.12) 0 1px, transparent 1px 22px);
  -webkit-mask: radial-gradient(ellipse 50% 50% at 50% 40%, #000 30%, transparent 75%);
  mask: radial-gradient(ellipse 50% 50% at 50% 40%, #000 30%, transparent 75%);
}
.orbit {
  position: absolute;
  left: 50%;
  top: 162px;
  border-radius: 50%;
  translate: -50% -50%;
}
.o1 {
  width: 150px;
  height: 46px;
  border: 1.5px solid rgba(80, 180, 255, 0.55);
  box-shadow: 0 0 12px rgba(60, 160, 255, 0.4);
  top: 178px;
}
.o2 {
  width: 210px;
  height: 66px;
  border: 1px solid rgba(80, 170, 255, 0.35);
  top: 178px;
  animation: cv-pulse 3s ease-in-out infinite;
}
.o3 {
  width: 330px;
  height: 150px;
  border: 1px dashed rgba(90, 170, 255, 0.35);
  top: 170px;
}
.o4 {
  width: 440px;
  height: 250px;
  border: 1px dashed rgba(90, 170, 255, 0.22);
  top: 160px;
}
@keyframes cv-pulse {
  50% {
    width: 250px;
    height: 80px;
    opacity: 0.3;
  }
}
.links {
  position: absolute;
  left: 0;
  top: 0;
  width: 388px;
  height: 280px;
  pointer-events: none;
}
.spoke {
  stroke-width: 1.3;
  stroke-dasharray: 4 4;
  opacity: 0.75;
  animation: cv-flow 1.2s linear infinite;
}
.spoke.on {
  stroke-width: 2;
  opacity: 1;
}
@keyframes cv-flow {
  to {
    stroke-dashoffset: -16;
  }
}
.node {
  position: absolute;
  translate: -50% -50%;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  z-index: 1;
  transition: transform 0.25s;
}
.node:hover,
.node.active {
  transform: scale(1.1);
}
.node img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.node .inner {
  position: absolute;
  top: 64%;
  font-size: 11px;
  color: #ffe9b0;
  text-shadow: 0 0 6px rgba(0, 0, 0, 0.8);
  pointer-events: none;
}
.node.hq .inner {
  top: 66%;
  font-size: 14px;
  font-weight: 700;
  color: #ffe38a;
}
.node.customer .inner {
  top: 62%;
  color: #e9dcff;
}
.node.customer img,
.node.hq img {
  filter: drop-shadow(0 0 10px rgba(255, 200, 80, 0.35));
}
.node.hq::before {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 1px solid rgba(255, 210, 90, 0.45);
  animation: cv-ripple 2.4s ease-out infinite;
}
@keyframes cv-ripple {
  from {
    transform: scale(0.9);
    opacity: 1;
  }
  to {
    transform: scale(1.35);
    opacity: 0;
  }
}
.node.owner img,
.node.general img,
.node.design img,
.node.vendor img {
  transform: scale(0.94);
}
.outer {
  position: absolute;
  top: calc(100% + 1px);
  white-space: nowrap;
  font-size: 13px;
  color: #e3ecf8;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
}
.bubble {
  position: absolute;
  z-index: 3;
  translate: -50% -100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid rgba(80, 180, 255, 0.6);
  background: rgba(6, 24, 52, 0.94);
  box-shadow: 0 0 12px rgba(40, 150, 255, 0.35);
  font-size: 12px;
  color: #c9d8ea;
  white-space: nowrap;
}
.bubble b {
  font-size: 13px;
  color: #fff;
}
.bubble button {
  margin-top: 3px;
  padding: 2px 0;
  border: 0;
  background: transparent;
  color: #6edbd9;
  font-size: 11px;
  cursor: pointer;
  text-align: left;
}
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
