<script setup lang="ts">
import { computed } from 'vue'
import CountUp from './CountUp.vue'
import { img } from './img'
import { PROVINCES, REGION_PROVINCES, REGION_CITIES } from '../dashboard/chinaMapData'
import type { RegionSummary } from './commandOverview'

const props = defineProps<{ region: RegionSummary; index: number; theme: 'blue' | 'purple' | 'teal' | 'orange' }>()
const emit = defineEmits<{ open: [region: string] }>()

const THEMES = {
  blue: { color: '#3ea4ff', frame: 'frame-blue' },
  purple: { color: '#a77dff', frame: 'frame-purple' },
  teal: { color: '#2ee3cb', frame: 'frame-teal' },
  orange: { color: '#ff7a22', frame: 'frame-orange' },
}
const theme = computed(() => THEMES[props.theme])
// 区域覆盖省份剪影：沿用地图模块的省级路径与区域划分。
const shape = computed(() => {
  const name = props.region.name
  const provinces = new Set([...(REGION_PROVINCES[name] || []), ...(REGION_CITIES[name] || []).map(c => c.province)])
  const shapes = PROVINCES.filter(p => provinces.has(p.n))
  const xs: number[] = [], ys: number[] = []
  for (const item of shapes) {
    const coords = (item.d.match(/-?\d+(?:\.\d+)?/g) || []).map(Number)
    for (let i = 0; i + 1 < coords.length; i += 2) { xs.push(coords[i]!); ys.push(coords[i + 1]!) }
  }
  if (!shapes.length) return { shapes, viewBox: '0 0 100 100' }
  const x = Math.min(...xs), y = Math.min(...ys)
  const width = Math.max(...xs) - x, height = Math.max(...ys) - y
  const padding = Math.max(width, height) * 0.08
  return { shapes, viewBox: `${x - padding} ${y - padding} ${width + padding * 2} ${height + padding * 2}` }
})
const code = computed(() => `REGION ${String(props.index + 1).padStart(2, '0')}`)
</script>

<template>
  <button
    type="button"
    class="cv-region"
    :style="{ '--c': theme.color, backgroundImage: `url(${img(theme.frame)})` }"
    :title="`${region.name}：${region.units} 家客户单位、${region.people} 位联系人；点击进入五位一体查看该区域`"
    @click="emit('open', region.name)"
  >
    <svg v-if="shape.shapes.length" class="cv-region__map" :viewBox="shape.viewBox" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <path v-for="(item, i) in shape.shapes" :key="item.n" :d="item.d" :style="{ filter: `brightness(${1 - (i % 3) * 0.1})` }"><title>{{ item.n }}</title></path>
    </svg>
    <span v-else class="cv-region__map cv-region__map--empty">未配置地图</span>
    <div class="cv-region__name">{{ region.name }}<em>{{ code }}</em></div>
    <div class="cv-region__col c1">
      <CountUp class="big" :value="region.units" />
      <span class="label">客户单位</span>
      <span class="sub">待维系<CountUp :value="region.warnings" /></span>
    </div>
    <div class="cv-region__col c2">
      <CountUp class="big" :value="region.people" />
      <span class="label">位联系人</span>
      <span class="sub">待跟进<CountUp :value="region.followups" /></span>
    </div>
  </button>
</template>

<style scoped>
.cv-region {
  position: absolute;
  top: 0;
  width: 380px;
  height: 117px;
  padding: 0;
  border: 0;
  background: center / 100% 100% no-repeat;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s, filter 0.2s;
}
.cv-region:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
}
.cv-region__map {
  position: absolute;
  left: 26px;
  top: 18px;
  width: 64px;
  height: 80px;
  fill: var(--c);
  stroke: var(--c);
  stroke-width: 0.6;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 6px color-mix(in srgb, var(--c) 70%, transparent));
}
.cv-region__map--empty {
  display: grid;
  place-items: center;
  font-size: 10px;
  color: #809bb1;
  text-align: center;
}
.cv-region__map path {
  transition: filter 0.2s;
}
.cv-region__name {
  position: absolute;
  left: 115px;
  top: 10px;
  font-size: 14.5px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}
.cv-region__name em {
  margin-left: 14px;
  font: 500 10.5px var(--cv-font-num);
  font-style: normal;
  letter-spacing: 1px;
  color: #8ea6c6;
}
.cv-region__col {
  position: absolute;
  top: 31px;
  display: flex;
  flex-direction: column;
}
.c1 {
  left: 113px;
}
.c2 {
  left: 222px;
}
.big {
  font-size: 25px;
  font-weight: 600;
  line-height: 30px;
  color: var(--c);
  text-shadow: 0 0 10px color-mix(in srgb, var(--c) 45%, transparent);
}
.label {
  font-size: 12.5px;
  line-height: 18px;
  color: #c3d1e3;
  white-space: nowrap;
}
.sub {
  margin-top: 8px;
  font-size: 13px;
  color: #c3d1e3;
  display: flex;
  align-items: baseline;
  gap: 10px;
  white-space: nowrap;
}
.sub .num {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}
</style>
