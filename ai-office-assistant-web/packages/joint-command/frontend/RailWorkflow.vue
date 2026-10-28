<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CrmPlaybook, CrmUnit, CrmPerson } from '../../../src/services/personalWorkApi'
const props = defineProps<{ data: CrmPlaybook; units: CrmUnit[]; people: CrmPerson[]; saving: boolean; readOnly?: boolean }>()
const emit = defineEmits<{ stage: [id: string]; addUnit: []; addPerson: []; relations: []; complete: [id: string] }>()
const selected = ref('设计')
const section = ref('tasks')
const page = ref(1)
const pageSize = 10
const tasks = computed(() => [...props.data.followups].sort((a,b) => Number(b.overdue)-Number(a.overdue)))
watch(() => props.data.followups, () => { page.value = Math.min(page.value, Math.max(1, Math.ceil(tasks.value.length / pageSize))) })
const stage = computed(() => props.data.stages.find(s => s.id === selected.value))
const count = (type: string) => props.units.filter(u => u.type === type).length
const contacts = (type: string) => props.people.filter(p => props.units.some(u => u.id === p.unit_id && u.type === type)).length
</script>
<template>
  <div class="rail-workflow">
    <el-radio-group v-model="section" class="crm-subnav" aria-label="业务导航层级"><el-radio-button value="tasks">待跟进事项</el-radio-button><el-radio-button value="organizations">五类职责</el-radio-button><el-radio-button value="stages">阶段指南</el-radio-button></el-radio-group>
    <section v-if="section === 'tasks'" class="rail-followups">
      <div class="rail-section-head"><h3>待跟进事项 <el-tag>{{ data.followups.length }}</el-tag></h3><span>来自动作留痕中的“下一步事项”</span></div>
      <el-empty v-if="!data.followups.length" :image-size="55" description="暂无待办，在关系维系中登记下一步和跟进日期" />
<article v-for="item in tasks.slice((page-1)*pageSize,page*pageSize)" :key="item.id"><div><b>{{ item.next_step }}</b><p>{{ item.person_name }} · {{ item.project_id || '未关联项目' }} · {{ item.owner_label || item.owner || '待指派' }}</p></div><el-tag :type="item.overdue ? 'danger' : 'info'">{{ item.overdue ? '已逾期 · ' : '' }}{{ item.due_date || '未定日期' }}</el-tag><el-button :loading="saving" :disabled="saving || readOnly || item.can_complete === false" @click="emit('complete', item.id)">{{ item.can_complete === false ? '仅可查看' : '标记完成' }}</el-button></article>
    <el-pagination v-if="tasks.length > pageSize" v-model:current-page="page" :page-size="pageSize" :total="tasks.length" layout="prev, pager, next, total" />
    </section>
    <template v-if="section === 'organizations'">
    <div class="rail-section-head"><h3>五类协同组织图</h3><span>按当前账号已建档数据统计</span></div>
    <div class="rail-orgs">
      <article v-for="(org, index) in data.organizations" :key="org.type">
        <span class="rail-number">0{{ index + 1 }}</span><h3>{{ org.type }}</h3><b>{{ org.label }}</b>
        <p>{{ org.label }} · {{ org.departments }}</p>
        <div class="rail-count"><strong>{{ count(org.type) }}</strong> 单位 <strong>{{ contacts(org.type) }}</strong> 联系人</div>
        <details><summary>建档时核实什么</summary><p>{{ org.duty }}</p><p>{{ org.evidence }}</p></details>
      </article>
    </div>
    <p class="rail-note">五类单位用于客户协作分类，并非固定上下级组织架构。厂商单独管理产品、授权与供货界面；非本范围的协作主体可在项目备注中补充说明。</p>
    </template>
    <section v-if="section === 'stages'" class="rail-stage-panel">
      <div class="rail-section-head"><h3>项目阶段 · 行动指南</h3><span>选择阶段查看责任方与交付材料</span></div>
      <div class="rail-stages"><button v-for="(item, index) in data.stages" :key="item.id" :class="{ active: selected === item.id }" @click="selected = item.id"><small>{{ String(index + 1).padStart(2, '0') }}</small>{{ item.title }}</button></div>
      <div v-if="stage" class="rail-stage-detail"><div><span>当前建议动作</span><h3>{{ stage.action }}</h3><p>协同参考：{{ data.organizations.filter(o => o.stages.includes(stage!.id)).map(o => o.type).join(' / ') }}</p></div><div><span>应留存的证据</span><p>{{ stage.deliverable }}</p><small>{{ stage.gate }}</small></div><el-button type="primary" @click="emit('stage', stage.id)">进入该阶段作战地图</el-button></div>
      <p class="rail-note">阶段可以交叉推进，付款依据合同节点。工程验收、运营前安全评估和运营接管分别核实，不用客户关系分数替代业务完成证据。</p>
    </section>

    <details class="rail-sources"><summary>业务参考依据与适用范围</summary><p>面向城市轨道交通建设及运营场景；具体职责以项目合同、采购文件和属地要求为准。</p><a v-for="source in data.sources" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }} ↗</a></details>
  </div>
</template>
