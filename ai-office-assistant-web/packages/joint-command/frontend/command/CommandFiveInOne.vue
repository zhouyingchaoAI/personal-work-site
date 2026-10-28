<script setup lang="ts">
import { computed } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import { img } from './img'
import type { CrmUnit, CrmPerson, CrmRelation } from '../../../../src/services/personalWorkApi'
import { fiveInOneOverview } from './commandOverview'

const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[] }>()
const emit = defineEmits<{ more: [] }>()
const data = computed(() => fiveInOneOverview(props.units, props.people, props.relations))
const BAR: Record<string, string> = {
  green: 'linear-gradient(90deg, #14a877, #22cf93)',
  yellow: 'linear-gradient(90deg, #f3b92c, #ffd257)',
  red: 'linear-gradient(90deg, #f0404e, #ff5b66)',
}
</script>

<template>
  <CommandPanel title="五位一体" :icon="img('ic-panel-five')" more="详情" class="cv-five" @more="emit('more')">
    <div class="stats">
      <div><CountUp :value="data.customers" :grouping="false" /><span>客户</span></div>
      <i class="chev" />
      <div><CountUp :value="data.contacts" :grouping="false" /><span>联系人</span></div>
      <i class="chev" />
      <div><CountUp :value="data.onlineRelations" :grouping="false" /><span>在维关系</span></div>
    </div>

    <p class="caption">关系健康度分布</p>
    <ul class="rows" aria-label="关系健康度分布">
      <li v-for="row in data.health" :key="row.name">
        <span class="name">{{ row.name }}</span>
        <div class="cv-bar-track"><div class="cv-bar-fill" :style="{ width: row.percent + '%', background: BAR[row.color] }" /></div>
        <CountUp class="val" :value="row.value" />
      </li>
    </ul>
    <p class="risk">
      待维系<CountUp :value="data.toMaintain" />单点风险<CountUp :value="data.singleRisk" />
    </p>
    <div class="cv-divider" />
    <p class="caption">客户类型 · 数量分布</p>
    <ul class="types" aria-label="客户类型数量分布">
      <li v-for="t in data.types" :key="t.name" :title="`${t.name} ${t.value} 家`">
        <img v-if="t.icon" :src="img('ic-type-' + t.icon)" alt="" />
        <i v-else class="type-fallback" />
        <span>{{ t.name }}</span>
        <CountUp :value="t.value" />
      </li>
      <li v-if="!data.types.length" class="cv-empty">暂无客户</li>
    </ul>
  </CommandPanel>
</template>

<style scoped>
.stats {
  display: flex;
  align-items: flex-start;
  height: 56px;
  margin: -2px 0 0 4px;
}
.stats > div {
  display: flex;
  flex-direction: column;
  min-width: 76px;
  padding-right: 8px;
}
.stats .num {
  font-size: 29px;
  font-weight: 600;
  line-height: 32px;
  color: var(--cv-cyan);
  text-shadow: 0 0 12px rgba(54, 220, 240, 0.35);
}
.stats span {
  font-size: 13.5px;
  line-height: 20px;
  color: #c9d6e7;
  white-space: nowrap;
}
.chev {
  width: 12px;
  height: 32px;
  margin-right: 2px;
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
  margin: 0;
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
  height: 24.5px;
  font-size: 13.5px;
  color: #d6e1ef;
}
.name {
  width: 62px;
  flex: none;
}
.cv-bar-track {
  flex: 1;
}
.val {
  width: 48px;
  flex: none;
  text-align: right;
  font-size: 14.5px;
  color: #e9f1fb;
}
.risk {
  display: flex;
  align-items: baseline;
  height: 24px;
  line-height: 24px;
  margin: 0;
  font-size: 13.5px;
  color: #c9d6e7;
}
.risk .num {
  margin: 0 18px 0 10px;
  font-size: 17px;
  color: var(--cv-red);
}
.cv-divider {
  margin: 3px 0 5px;
}
.types {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 4px 0 0;
  padding: 0;
}
.types li {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}
.types img,
.type-fallback {
  height: 25px;
  width: 30px;
  object-fit: contain;
  filter: drop-shadow(0 0 4px rgba(54, 220, 240, 0.4));
}
.type-fallback {
  border-radius: 6px;
  background: linear-gradient(180deg, #2f8dff, #1a5db3);
  opacity: 0.8;
}
.types span {
  margin-top: 2px;
  font-size: 13px;
  line-height: 17px;
  color: #d6e1ef;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.types .num {
  font-size: 14.5px;
  line-height: 17px;
  color: #e9f1fb;
}
.types .cv-empty {
  grid-column: 1 / -1;
  align-items: flex-start;
}
</style>
