<script setup lang="ts">
import { computed } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import TipLine from './TipLine.vue'
import { img } from './img'
import type { CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { opportunityOverview, type Followup } from './commandOverview'

const props = defineProps<{ opportunities: CrmOpportunity[]; followups: Followup[] }>()
const emit = defineEmits<{ more: [] }>()
const data = computed(() => opportunityOverview(props.opportunities, props.followups))
const BAR: Record<string, string> = {
  blue: 'linear-gradient(90deg, #2b8cff, #45a6ff)',
  lavender: 'linear-gradient(90deg, #a898ff, #c9bcff)',
  green: '#1fb886',
  orange: '#f7a93a',
  red: '#ff4655',
}
</script>

<template>
  <CommandPanel title="商机管理" :icon="img('ic-panel-biz')" more="详情" class="cv-opp" @more="emit('more')">
    <div class="stats">
      <div class="first"><CountUp :value="data.talking" /><span>在谈商机</span></div>
      <i class="chev" />
      <div><CountUp :value="Math.round(data.amount)" /><span>可参与份额(万)</span></div>
    </div>

    <p class="caption">阶段分布 · 数量</p>
    <ul class="rows" aria-label="商机阶段分布">
      <li v-for="row in data.stages" :key="row.name" :title="`${row.name} ${row.value} 个`">
        <span class="name">{{ row.name }}</span>
        <div class="cv-bar-track"><div class="cv-bar-fill" :style="{ width: row.percent + '%', background: BAR[row.color] }" /></div>
        <CountUp class="val" :value="row.value" />
      </li>
      <li v-if="!data.stages.length" class="cv-empty">暂无在谈商机</li>
      <li v-else :title="`其他阶段 ${data.others} 个，按成单概率高 / 中 / 低分段`">
        <span class="name">其他阶段</span>
        <div class="cv-bar-track seg">
          <div v-for="(s, i) in data.otherSegments" :key="i" :style="{ width: s.percent + '%', background: BAR[s.color] }" />
        </div>
        <CountUp class="val" :value="data.others" />
      </li>
    </ul>

    <p class="prob">
      成单概率
      <span>高<CountUp class="g" :value="data.probability.high" /></span>
      <span>中<CountUp class="y" :value="data.probability.mid" /></span>
      <span>低<CountUp class="r" :value="data.probability.low" /></span>
    </p>
    <div class="cv-divider" />
    <TipLine class="tip">重点：{{ data.tip }}</TipLine>
  </CommandPanel>
</template>

<style scoped>
.stats {
  display: flex;
  align-items: flex-start;
  height: 58px;
  margin: -2px 0 0 4px;
}
.stats > div {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.stats .first {
  min-width: 80px;
  padding-right: 6px;
}
.stats .num {
  font-size: 29px;
  font-weight: 600;
  line-height: 32px;
  color: var(--cv-cyan);
  text-shadow: 0 0 12px rgba(54, 220, 240, 0.35);
  white-space: nowrap;
}
.stats span {
  font-size: 13.5px;
  line-height: 20px;
  color: #c9d6e7;
  white-space: nowrap;
}
.chev {
  width: 24px;
  height: 32px;
  position: relative;
  flex: none;
}
.chev::after {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  width: 5px;
  height: 5px;
  border-right: 1px solid rgba(120, 180, 240, 0.6);
  border-top: 1px solid rgba(120, 180, 240, 0.6);
  transform: rotate(45deg);
}
.caption {
  margin: 10px 0 0;
  font-size: 13.5px;
  line-height: 20px;
  color: #c5d3e6;
}
.rows {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
}
.rows li {
  display: flex;
  align-items: center;
  height: 26.5px;
  font-size: 13.5px;
  color: #d6e1ef;
}
.name {
  width: 83px;
  flex: none;
  padding-left: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cv-bar-track {
  flex: 1;
}
.cv-bar-track.seg {
  display: flex;
}
.cv-bar-track.seg div {
  height: 100%;
}
.cv-bar-track.seg div:last-child {
  border-radius: 0 5px 5px 0;
}
.val {
  width: 44px;
  flex: none;
  text-align: right;
  font-size: 14.5px;
  color: #e9f1fb;
}
.prob {
  display: flex;
  align-items: baseline;
  gap: 12px;
  height: 22px;
  margin: 24px 0 12px 4px;
  font-size: 13.5px;
  color: #c9d6e7;
}
.prob span {
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.prob .num {
  font-size: 16px;
}
.g {
  color: var(--cv-green);
}
.y {
  color: var(--cv-yellow);
}
.r {
  color: var(--cv-red);
}
.tip {
  height: 42px;
}
</style>
