<script setup lang="ts">
import { computed, ref } from 'vue'
import CommandPanel from './CommandPanel.vue'
import type { CrmRelation, CrmOpportunity } from '../../../../src/services/personalWorkApi'
import { activityOverview, type Followup } from './commandOverview'

const props = defineProps<{ followups: Followup[]; relations: CrmRelation[]; opportunities: CrmOpportunity[] }>()
const opened = ref(false)
const events = computed(() => activityOverview(props.followups, props.relations, props.opportunities).events)
</script>

<template>
  <CommandPanel title="最近动态" more="更多" class="cv-feed" @more="opened = true">
    <div class="cv-divider" />
    <ul class="list" aria-label="最近动态">
      <li v-for="e in events.slice(0, 5)" :key="e.key">
        <button type="button" :title="`${e.text} · ${e.date}`" @click="opened = true">
          <span class="tag" :class="{ 'is-followup': e.kind === '跟进' }">{{ e.kind }}</span>
          <span class="text">{{ e.text }}</span>
          <span class="date num">{{ e.date.slice(5, 10) }}</span>
        </button>
      </li>
      <li v-if="!events.length" class="cv-empty">暂无带时间的跟进或商机记录</li>
    </ul>
    <el-dialog v-model="opened" title="最近动态" width="min(680px, 92vw)" append-to-body>
      <p class="detail-note">按跟进发生时间及商机最新更新时间排序；并非完整操作日志。</p>
      <div class="detail-list">
        <article v-for="e in events" :key="e.key"><strong>{{ e.kind }} · {{ e.text }}</strong><p>{{ e.date }}</p></article>
        <el-empty v-if="!events.length" description="暂无记录" />
      </div>
    </el-dialog>
  </CommandPanel>
</template>

<style scoped>
.cv-feed :deep(.cv-panel__head) {
  height: 48px;
}
.cv-feed :deep(.cv-more) {
  color: #8fd6f5;
}
.cv-divider {
  margin-top: -3px;
}
.list {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
}
.list button {
  display: flex;
  align-items: center;
  width: 100%;
  height: 34px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.list button:hover .text {
  color: #fff;
}
.tag {
  flex: none;
  width: 44px;
  height: 23px;
  line-height: 21px;
  box-sizing: border-box;
  text-align: center;
  font-size: 12.5px;
  font-weight: 600;
  color: #8ff5c6;
  border-radius: 3px;
  border: 1px solid rgba(40, 190, 130, 0.45);
  background: linear-gradient(180deg, #11664a, #0b4a37);
}
.tag.is-followup {
  color: #8fe0ff;
  border-color: rgba(60, 160, 230, 0.5);
  background: linear-gradient(180deg, #123d57, #0d2e45);
}
.text {
  flex: 1;
  min-width: 0;
  margin: 0 10px;
  font-size: 12.5px;
  color: #dfe8f4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.date {
  font-size: 12.5px;
  color: #a9bad0;
  flex: none;
}
.list .cv-empty {
  padding: 12px 0;
  text-align: center;
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
}
</style>
