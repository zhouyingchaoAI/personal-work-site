<script setup lang="ts">
import { computed, ref } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import { img } from './img'
import type { CrmRelation, CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { activityOverview, type Followup } from './commandOverview'

const props = defineProps<{ followups: Followup[]; relations: CrmRelation[]; opportunities: CrmOpportunity[] }>()
const selected = ref('')
const data = computed(() => activityOverview(props.followups, props.relations, props.opportunities))
const details = computed(() => {
  if (selected.value === '需协调') return props.relations.filter(r => r.single_point_risk).map(r => ({ key: r.id, title: r.person_name || '客户关系', meta: `单点风险 · ${r.our_member_label || r.our_member || '负责人待补充'}` }))
  const rows = (selected.value === '全部待办' ? data.value.pending : (data.value.groups.find(g => g.name === selected.value)?.rows || [])) as Followup[]
  return rows.map(a => ({ key: a.id, title: a.next_step || a.intel || `${a.person_name || '客户关系'}跟进`, meta: `${a.person_name || '联系人待补充'} · ${a.owner_label || a.owner || '待指派'} · ${a.due_date || '未定日期'}` }))
})
</script>

<template>
  <CommandPanel title="行动指挥台" more="全部待办" class="cv-action" @more="selected = '全部待办'">
    <ul class="cards" aria-label="行动指挥台">
      <li v-for="(g, i) in data.groups" :key="g.key" :class="{ first: i === 0, overdue: g.key === 'overdue' }" :style="{ '--k': g.color }">
        <button type="button" :title="g.hint" @click="selected = g.name">
          <div class="top">
            <img :src="img('ic-todo-' + g.icon)" alt="" />
            <CountUp :value="g.rows.length" />
          </div>
          <span>{{ g.name }}</span>
        </button>
      </li>
    </ul>
    <el-dialog :model-value="!!selected" :title="selected" width="min(680px, 92vw)" append-to-body @close="selected = ''">
      <p class="detail-note">{{ selected === '需协调' ? '当前单点风险关系，作为协调线索，并非已发起的协同任务。' : '仅统计未完成的跟进计划；今日、本周、逾期分类可能重叠。' }}</p>
      <div class="detail-list">
        <article v-for="item in details" :key="item.key"><strong>{{ item.title }}</strong><p>{{ item.meta }}</p></article>
        <el-empty v-if="!details.length" description="暂无记录" />
      </div>
    </el-dialog>
  </CommandPanel>
</template>

<style scoped>
.cv-action :deep(.cv-panel__head) {
  height: 38px;
}
.cv-action :deep(.cv-more) {
  color: #8fd6f5;
}
.cards {
  list-style: none;
  display: flex;
  gap: 7px;
  margin: -3px -9px 0;
  padding: 0;
}
.cards li {
  flex: 1;
  min-width: 0;
}
.cards button {
  width: 100%;
  height: 65px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 6px;
  border: 1px solid rgba(72, 130, 200, 0.35);
  background: linear-gradient(180deg, rgba(22, 50, 90, 0.55), rgba(12, 30, 60, 0.55));
  color: inherit;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s;
}
.cards button:hover {
  transform: translateY(-1px);
  border-color: rgba(54, 200, 240, 0.65);
}
.cards li.first button {
  border-color: rgba(54, 200, 240, 0.65);
  box-shadow: inset 0 0 14px rgba(54, 200, 240, 0.25);
}
.top {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 30px;
}
.top img {
  width: 24px;
  height: 24px;
  object-fit: contain;
}
.top .num {
  font-size: 25px;
  font-weight: 600;
  color: var(--k);
}
.cards span {
  margin-top: 2px;
  font-size: 13px;
  color: #c9d6e7;
  white-space: nowrap;
}
.cards li.overdue span {
  color: #f0d68a;
}
.detail-note {
  color: #6b8196;
  font-size: 12px;
}
.detail-list {
  max-height: 55vh;
  overflow: auto;
}
.detail-list article {
  padding: 12px 0;
  border-bottom: 1px solid #e3ebf2;
}
.detail-list strong {
  color: #28445e;
  font-size: 14px;
  overflow-wrap: anywhere;
}
.detail-list p {
  font-size: 12px;
  color: #7b8fa2;
  margin: 6px 0;
  overflow-wrap: anywhere;
}
</style>
