<script setup lang="ts">
import { computed } from 'vue'
import './command-canvas.scss'
import type { BusinessAnalysisData, CrmUnit, CrmPerson, CrmRelation, CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { customerLayoutOverview, type Followup } from './commandOverview'
import CommandBizAnalysis from './CommandBizAnalysis.vue'
import CommandFiveInOne from './CommandFiveInOne.vue'
import CommandOpportunity from './CommandOpportunity.vue'
import CommandProjectMap from './CommandProjectMap.vue'
import CommandRiskPanel from './CommandRiskPanel.vue'
import CommandHealthRadar from './CommandHealthRadar.vue'
import CommandZoneGraph from './CommandZoneGraph.vue'
import CommandActionBoard from './CommandActionBoard.vue'
import CommandRecentFeed from './CommandRecentFeed.vue'

// 面板坐标（设计像素）；flow 模式（窄屏）不使用绝对定位。
const props = defineProps<{
  business: BusinessAnalysisData | null
  units: CrmUnit[]
  people: CrmPerson[]
  relations: CrmRelation[]
  opportunities: CrmOpportunity[]
  followups: Followup[]
  flow?: boolean
}>()
const emit = defineEmits<{ section: [value: string]; network: [type: string]; opportunity: [item: CrmOpportunity] }>()

const rem = (v: number) => `${v / 10}rem`
const rect = (x: number, y: number, w: number, h: number) => ({ left: rem(x), top: rem(y), width: rem(w), height: rem(h) })
// 坐标为设计稿减去头部 105px、侧栏 183px 后的内容区坐标（画布 1571 × 792）。
// 区域卡已移入五位一体看板，两行面板拉高填满画布。
const CANVAS_WIDTH = 1571
const CANVAS_HEIGHT = 792
const LAYOUT: Record<string, ReturnType<typeof rect>> = {
  biz: rect(0, 6, 432, 368),
  opp: rect(445, 6, 368, 368),
  five: rect(825, 6, 352, 368),
  map: rect(1188, 6, 366, 368),
  risk: rect(1, 390, 291, 356),
  zone: rect(302, 390, 843, 356),
  action: rect(1155, 390, 399, 110),
  feed: rect(1155, 512, 399, 234),
}
const pos = (key: string) => (props.flow ? undefined : LAYOUT[key])
// 画布尺寸供 Cockpit 的缩放钩子使用（与 useCanvasScale 的 1571 × 792 保持一致）
void CANVAS_WIDTH; void CANVAS_HEIGHT

const layout = computed(() => customerLayoutOverview(props.units, props.people))
</script>

<template>
  <div class="command-overview" :class="{ 'is-flow': flow }" aria-label="总体信息大屏">
    <CommandBizAnalysis :style="pos('biz')" :business="business" @more="emit('section', 'dashboard')" />
    <CommandOpportunity :style="pos('opp')" :opportunities="opportunities" :followups="followups" @more="emit('section', 'opportunities')" />
    <CommandFiveInOne :style="pos('five')" :units="units" :people="people" :relations="relations" @more="emit('section', 'integration')" />
    <CommandProjectMap :style="pos('map')" :opportunities="opportunities" @more="emit('section', 'battle')" @opportunity="item => emit('opportunity', item)" />

    <CommandRiskPanel :style="pos('risk')" :units="units" :people="people" :relations="relations" :followups="followups" />
    <CommandZoneGraph :style="pos('zone')" :rows="layout.rows" :others="layout.others" :total="{ units: layout.total, contacts: layout.contacts }" @network="type => emit('network', type)">
      <template #health><CommandHealthRadar :units="units" :people="people" :relations="relations" /></template>
    </CommandZoneGraph>
    <CommandActionBoard :style="pos('action')" :followups="followups" :relations="relations" :opportunities="opportunities" />
    <CommandRecentFeed :style="pos('feed')" :followups="followups" :relations="relations" :opportunities="opportunities" />
  </div>
</template>

<style scoped>
/* 画布模式：内容层铺满画布，自身不拦截鼠标，避免挡住顶部按钮与侧栏 */
.command-overview {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.command-overview > * {
  pointer-events: auto;
}
/* 面板加高后，把固定尺寸的内部图形垂直居中、列表行距拉开 */
.command-overview:not(.is-flow) :deep(.cv-zone .zone-graph-area) { margin-top: 48px; }
.command-overview:not(.is-flow) :deep(.cv-risk .list button) { min-height: 56px; }
.command-overview:not(.is-flow) :deep(.cv-biz .rows li) { height: 28px; }
.command-overview:not(.is-flow) :deep(.cv-biz .kpi) { height: 60px; }
.command-overview:not(.is-flow) :deep(.cv-five .rows li) { height: 28px; }
.command-overview:not(.is-flow) :deep(.cv-five .types) { margin-top: 12px; }
.command-overview:not(.is-flow) :deep(.cv-opp .rows li) { height: 30px; }
.command-overview:not(.is-flow) :deep(.cv-opp .prob) { margin-top: 32px; }
.command-overview:not(.is-flow) :deep(.cv-map .projects li button) { min-height: 38px; }
.command-overview:not(.is-flow) :deep(.cv-map .rows li) { height: 28px; }
/* 窄屏 flow 模式：面板按顺序纵向堆叠 */
.command-overview.is-flow {
  position: static;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px 0 12px;
}
.command-overview.is-flow :deep(.cv-panel) {
  position: relative;
  width: auto;
  min-height: 0;
  padding-bottom: 12px;
}
.command-overview.is-flow :deep(.cv-zone) {
  overflow: hidden;
}
.command-overview.is-flow :deep(.cv-zone .zone-health) {
  position: static;
  width: 215px;
  height: 296px;
  margin: 4px auto 0;
  padding: 0;
}
.command-overview.is-flow :deep(.cv-zone .zone-graph-area) {
  position: relative;
  left: 50%;
  translate: -50% 0;
}
.command-overview.is-flow :deep(.cv-zone .zone-layout) {
  position: static;
  border-left: 0;
  padding: 8px 0 2px;
}
</style>
