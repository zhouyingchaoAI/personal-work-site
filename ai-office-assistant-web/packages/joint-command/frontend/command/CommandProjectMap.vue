<script setup lang="ts">
import { computed } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import TipLine from './TipLine.vue'
import { img } from './img'
import type { CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { projectMapOverview } from './commandOverview'

const props = defineProps<{ opportunities: CrmOpportunity[] }>()
const emit = defineEmits<{ more: []; opportunity: [item: CrmOpportunity] }>()
const data = computed(() => projectMapOverview(props.opportunities))
const maxArea = computed(() => Math.max(1, ...data.value.topAreas.map(a => a.value)))
</script>

<template>
  <CommandPanel title="项目作战地图" :icon="img('ic-panel-map')" more="详情" class="cv-map" @more="emit('more')">
    <div class="head">
      <CountUp class="big" :value="data.keyProjects" />
      <span class="head-label">重点项目(≥1000万)</span>
    </div>
    <div class="cv-divider" />
    <p class="caption">重点项目 · 金额前二</p>
    <ul class="projects" aria-label="重点项目金额前二">
      <li v-for="p in data.topProjects" :key="p.item.id || p.item.code">
        <button type="button" :title="`${p.name} · ${p.amount} 万元 · 点击进入项目作战`" @click="emit('opportunity', p.item)">
          <span class="amt"><CountUp :value="p.amount" />万</span>
          <span class="pname">{{ p.name }}</span>
        </button>
      </li>
      <li v-if="!data.topProjects.length" class="cv-empty">暂无大额在谈项目</li>
    </ul>
    <div class="cv-divider" />
    <p class="caption">区域金额 · 前二（万元）</p>
    <ul class="rows" aria-label="重点项目区域金额前二">
      <li v-for="a in data.topAreas" :key="a.name">
        <span class="name" :title="a.name">{{ a.name }}</span>
        <div class="cv-bar-track"><div class="cv-bar-fill" :style="{ width: (a.value / maxArea) * 100 + '%' }" /></div>
        <CountUp class="val" :value="a.value" />
      </li>
      <li v-if="!data.topAreas.length" class="cv-empty">暂无区域金额</li>
    </ul>
    <div class="cv-divider" />
    <TipLine class="tip">重点：{{ data.tip }}</TipLine>
  </CommandPanel>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  height: 34px;
  margin: 1px 0 0 6px;
}
.big {
  min-width: 58px;
  padding-right: 8px;
  font-size: 33px;
  font-weight: 600;
  color: var(--cv-cyan);
  text-shadow: 0 0 12px rgba(54, 220, 240, 0.35);
}
.head-label {
  font-size: 13.5px;
  color: #c5d3e6;
}
.caption {
  margin: 9px 0 0 6px;
  font-size: 13.5px;
  line-height: 20px;
  color: #c5d3e6;
}
.projects {
  list-style: none;
  margin: 5px 0 7px 6px;
  padding: 0;
  min-height: 60px;
}
.projects li button {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 30px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.projects li button:hover .pname {
  color: var(--cv-cyan);
}
.amt {
  width: 108px;
  flex: none;
  font-size: 15px;
  font-weight: 600;
  color: var(--cv-yellow);
  white-space: nowrap;
}
.amt .num {
  font-size: 16.5px;
}
.pname {
  font-size: 13.5px;
  line-height: 19px;
  color: #e3ebf6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.2s;
}
.rows {
  list-style: none;
  margin: 3px 0 5px 6px;
  padding: 0;
  min-height: 48px;
}
.rows li {
  display: flex;
  align-items: center;
  height: 24px;
  font-size: 13.5px;
  color: #d6e1ef;
}
.name {
  width: 38px;
  flex: none;
  margin-right: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cv-bar-track {
  flex: 1;
}
.cv-bar-fill {
  background: linear-gradient(90deg, #f3c043, #ffd766);
}
.val {
  width: 76px;
  flex: none;
  text-align: right;
  font-size: 14px;
  color: #e9f1fb;
}
.tip {
  height: 40px;
  margin: 6px 0 0 6px;
}
</style>
