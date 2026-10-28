<script setup lang="ts">
import { computed } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import TipLine from './TipLine.vue'
import { img } from './img'
import type { BusinessAnalysisData } from '../../../../src/services/personalWorkApi'
import { businessOverview } from './commandOverview'

const props = defineProps<{ business: BusinessAnalysisData | null }>()
const emit = defineEmits<{ more: [] }>()
const data = computed(() => businessOverview(props.business))
const width = (rate: number | null) => Math.max(0, Math.min(100, rate ?? 0))
// 进度条渐变始终按满轨道铺开，短条也能看到起始色。
const barStyle = (rate: number | null) => ({ width: width(rate) + '%', backgroundSize: `${width(rate) > 0 ? 10000 / width(rate) : 100}% 100%` })
</script>

<template>
  <CommandPanel title="经营分析" :icon="img('ic-panel-analysis')" more="详情" class="cv-biz" @more="emit('more')">
    <p class="caption">核心经营指标 · 全年口径 · 万元</p>
    <ul class="rows" aria-label="核心经营指标">
      <li class="head" aria-hidden="true">
        <span class="name">指标</span>
        <span class="target">全年目标</span>
        <span class="value">当前达成</span>
        <div class="bar-space" />
        <span class="rate">达成率</span>
      </li>
      <li v-for="row in data.indicators" :key="row.name" :title="`${row.name}：全年目标 ${row.target ?? '—'} 万元，当前达成 ${row.value ?? '—'} 万元，全年达成率 ${row.rate === null ? '—' : row.rate.toFixed(1) + '%'}，Q3完成率 ${row.q3Rate === null ? '—' : row.q3Rate.toFixed(1) + '%'}`">
        <span class="name">{{ row.name }}</span>
        <span class="target"><CountUp :value="row.target" /></span>
        <span class="value"><CountUp :value="row.value" :decimals="1" /></span>
        <div class="cv-bar-track"><div class="cv-bar-fill" :style="barStyle(row.rate)" /></div>
        <span class="rate"><CountUp :value="row.rate" :decimals="1" /><template v-if="row.rate !== null">%</template></span>
      </li>
    </ul>
    <div class="cv-divider" />
    <div class="kpis">
      <div class="kpi cyan">
        <i><img :src="img('ic-kpi-gross')" alt="" /></i>
        <div><span>毛利率</span><b><CountUp :value="data.grossMargin" :decimals="1" /><template v-if="data.grossMargin !== null">%</template></b></div>
      </div>
      <div class="kpi blue">
        <i><img :src="img('ic-kpi-cost')" alt="" /></i>
        <div><span>费效比</span><b><CountUp :value="data.costRatio" :decimals="2" /></b></div>
      </div>
      <div class="kpi red" :class="{ positive: (data.operatingProfit ?? 0) >= 0 }">
        <i><img :src="img('ic-kpi-profit')" alt="" /></i>
        <div><span>营业利润</span><b><CountUp :value="data.operatingProfit" /><template v-if="data.operatingProfit !== null">万</template></b></div>
      </div>
    </div>
    <div class="cv-divider" />
    <TipLine class="tip">重点：{{ data.tip }}</TipLine>
  </CommandPanel>
</template>

<style scoped>
.caption {
  margin: 0;
  font-size: 13.5px;
  line-height: 18px;
  color: #c5d3e6;
}
.rows {
  list-style: none;
  margin: 7px 0 13px;
  padding: 0;
}
.rows li {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 27px;
  font-size: 13px;
}
.rows li.head {
  height: 20px;
  font-size: 11px;
  color: #7f96b4;
}
.rows li.head .name,
.rows li.head .target,
.rows li.head .value,
.rows li.head .rate {
  color: #7f96b4;
  font-size: 11px;
}
.name {
  width: 58px;
  flex: none;
  color: #d6e1ef;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.target {
  width: 74px;
  flex: none;
  text-align: right;
  color: #b3c3d8;
  white-space: nowrap;
}
.target .num {
  font-size: 13.5px;
}
.value {
  width: 84px;
  flex: none;
  text-align: right;
  color: #e9f1fb;
  white-space: nowrap;
}
.value .num {
  font-size: 14px;
}
.bar-space,
.cv-bar-track {
  flex: 1;
  min-width: 24px;
  height: 10px;
}
.bar-space {
  height: 1px;
}
.cv-bar-fill {
  background-image: linear-gradient(90deg, #2a84ff, #4fb0ff 40%, #8c86ff 58%, #a57bff);
}
.rate {
  width: 56px;
  flex: none;
  text-align: right;
  color: var(--cv-red);
  white-space: nowrap;
}
.rate .num {
  font-size: 15px;
}
.kpis {
  display: flex;
  gap: 17px;
  margin: 4px -2px 9px;
}
.kpi {
  --k: var(--cv-cyan);
  flex: 1;
  min-width: 0;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 7px;
  border-radius: 6px;
  border: 1px solid rgba(72, 130, 200, 0.35);
  background: linear-gradient(180deg, rgba(22, 48, 86, 0.55), rgba(12, 30, 60, 0.55));
}
.kpi.blue {
  --k: #4aa6ff;
}
.kpi.red {
  --k: var(--cv-red);
  border-color: rgba(255, 80, 96, 0.35);
  background: linear-gradient(180deg, rgba(70, 22, 40, 0.45), rgba(40, 18, 38, 0.45));
}
.kpi.red.positive {
  --k: var(--cv-green);
  border-color: rgba(32, 201, 143, 0.35);
  background: linear-gradient(180deg, rgba(18, 70, 52, 0.45), rgba(14, 40, 38, 0.45));
}
.kpi i {
  width: 40px;
  height: 40px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--k) 30%, transparent), color-mix(in srgb, var(--k) 12%, transparent));
}
.kpi img {
  width: 28px;
  height: 28px;
  object-fit: contain;
}
.kpi div {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.kpi span {
  font-size: 12px;
  color: #b9c8dc;
}
.kpi b {
  font-size: 18px;
  font-weight: 600;
  color: var(--k);
  font-family: var(--cv-font-num);
  white-space: nowrap;
}
.kpi b .num {
  font-size: 19px;
}
.tip {
  height: 32px;
}
</style>
