<script setup lang="ts">
import { computed, ref } from 'vue'
import CommandPanel from './CommandPanel.vue'
import CountUp from './CountUp.vue'
import type { CrmUnit, CrmPerson, CrmRelation } from '../../../../src/services/personalWorkApi'
import { riskOverview, type Followup } from './commandOverview'

const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; followups: Followup[] }>()
const selected = ref('')
const data = computed(() => riskOverview(props.units, props.people, props.relations, props.followups))
const sections = computed(() => [
  { name: '单点风险关系', rows: data.value.single.map(r => ({ id: r.id, title: r.person_name || props.people.find(p => p.id === r.person_id)?.name || '客户关系', meta: `对接人：${r.our_member_label || r.our_member || '待补充'}` })) },
  { name: '未建立关系的联系人', rows: data.value.unlinked.map(p => ({ id: p.id, title: p.name, meta: props.units.find(u => u.id === p.unit_id)?.name || p.unit_name || '未关联客户' })) },
  { name: '逾期跟进事项', rows: data.value.overdue.map(a => ({ id: a.id, title: a.next_step || a.intel || a.person_name || '跟进事项', meta: `${a.person_name || '联系人待补充'} · 截止 ${a.due_date}` })) },
  { name: '高风险客户', rows: data.value.customers.map(c => ({ id: c.id, title: c.name, meta: `${c.count} 条告警关系 · ${c.days == null ? '无维系日期记录' : `最长 ${c.days} 天未维系`}` })) },
].filter(s => selected.value === '全部预警' || selected.value === s.name))
</script>

<template>
  <CommandPanel title="风险雷达" more="查看预警" class="cv-risk" @more="selected = '全部预警'">
    <div class="cards">
      <button type="button" class="card red" title="存在单点风险的关系" @click="selected = '单点风险关系'">
        <b><i class="ring dot" /><CountUp :value="data.single.length" /></b><span>单点风险</span>
      </button>
      <button type="button" class="card yellow" title="尚未建立关系记录的联系人" @click="selected = '未建立关系的联系人'">
        <b><i class="ring" /><CountUp :value="data.unlinked.length" /></b><span>未建关系</span>
      </button>
      <button type="button" class="card blue" title="未完成且已过截止日期的跟进计划" @click="selected = '逾期跟进事项'">
        <b><i class="ring" /><CountUp :value="data.overdue.length" /></b><span>逾期跟进</span>
      </button>
    </div>
    <div class="cv-divider" />
    <div class="sub-head"><b>高风险客户</b><span>告警关系</span></div>
    <ul class="list" aria-label="高风险客户">
      <li v-for="c in data.customers.slice(0, 3)" :key="c.id">
        <button type="button" :title="`${c.name} · ${c.count} 条告警关系`" @click="selected = '高风险客户'">
          <i class="led" />
          <span class="cname">{{ c.name }}</span>
          <span class="days" v-if="c.days != null"><CountUp :value="c.days" />天未维系</span>
          <span class="days" v-else>维系日期缺失</span>
        </button>
      </li>
      <li v-if="!data.customers.length" class="cv-empty">暂无告警客户</li>
    </ul>
    <el-dialog :model-value="!!selected" :title="selected" append-to-body width="min(680px, 92vw)" @close="selected = ''">
      <p class="risk-explanation">当前授权范围。高风险客户按告警关系归属单位去重，天数为其中最长未维系天数；逾期只统计未完成且已过截止日期的跟进计划。</p>
      <div class="risk-details">
        <section v-for="s in sections" :key="s.name">
          <h4>{{ s.name }} · {{ s.rows.length }}</h4>
          <article v-for="r in s.rows" :key="r.id"><strong>{{ r.title }}</strong><p>{{ r.meta }}</p></article>
          <p v-if="!s.rows.length">暂无记录</p>
        </section>
      </div>
    </el-dialog>
  </CommandPanel>
</template>

<style scoped>
.cards {
  display: flex;
  gap: 9px;
  margin: -3px -6px 0;
}
.card {
  --k: var(--cv-red);
  flex: 1;
  min-width: 0;
  height: 67px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0;
  border-radius: 6px;
  border: 1px solid rgba(72, 130, 200, 0.35);
  background: linear-gradient(180deg, rgba(22, 48, 86, 0.55), rgba(12, 30, 60, 0.55));
  color: inherit;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;
}
.card:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--k) 70%, transparent);
}
.card.red {
  border-color: rgba(255, 78, 92, 0.6);
  background: linear-gradient(180deg, rgba(90, 24, 44, 0.45), rgba(40, 18, 38, 0.5));
  box-shadow: inset 0 0 12px rgba(255, 70, 90, 0.2);
}
.card.yellow {
  --k: var(--cv-yellow);
}
.card.blue {
  --k: #3aa8ff;
}
.card b {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--k);
  font-weight: 600;
}
.card b .num {
  font-size: 25px;
  line-height: 30px;
}
.card span {
  margin-top: 4px;
  font-size: 12.5px;
  color: #c9d6e7;
  white-space: nowrap;
}
.ring {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--k);
  position: relative;
  box-sizing: border-box;
}
.ring.dot::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: 50%;
  background: var(--k);
}
.cv-divider {
  margin-top: 9px;
}
.sub-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  font-size: 14px;
  color: #e6eef9;
}
.sub-head span {
  font-size: 13px;
  color: #c3d1e3;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.list li + li {
  border-top: 1px solid rgba(88, 142, 208, 0.25);
}
.list button {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 46px;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.led {
  width: 14px;
  height: 14px;
  flex: none;
  margin: 4px 12px 0 1px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #ff8a92, #ff3b4b 60%);
  box-shadow: 0 0 8px rgba(255, 59, 75, 0.7);
  align-self: flex-start;
}
.cname {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  line-height: 20px;
  color: #e6eef9;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.days {
  margin-left: 10px;
  font-size: 13px;
  color: var(--cv-red);
  white-space: nowrap;
}
.list .cv-empty {
  padding: 14px 0;
  text-align: center;
}
.risk-explanation {
  font-size: 12px;
  color: #6c8196;
}
.risk-details {
  max-height: 55vh;
  overflow: auto;
}
.risk-details article {
  padding: 10px 0;
  border-bottom: 1px solid #e1eaf0;
  overflow-wrap: anywhere;
}
.risk-details strong {
  color: #29465d;
  font-size: 14px;
}
.risk-details p {
  font-size: 12px;
  color: #7890a4;
}
.risk-details h4 {
  color: #29465d;
}
</style>
