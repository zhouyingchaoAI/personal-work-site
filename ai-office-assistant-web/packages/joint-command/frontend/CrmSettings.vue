<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { OfficeBuilding, MapLocation, Odometer, Lock, Document, Flag } from '@element-plus/icons-vue'
import { crmQualitySettings, type CrmQualitySettings, type CrmUnit, type CrmPerson, type CrmRelation } from '../../../src/services/personalWorkApi'
import SecurityPanel from './SecurityPanel.vue'
import AuditTrail from './AuditTrail.vue'
import OwnOrganization from './OwnOrganization.vue'
import RegionSettings from './RegionSettings.vue'
import QualityRuleSettings from './QualityRuleSettings.vue'
import BattleRosterPanel from './BattleRosterPanel.vue'
const props = defineProps<{ manage: boolean; appoint: boolean; write: boolean; units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[] }>()
const emit = defineEmits<{ changed: [] }>()
const section = ref(props.appoint ? 'battleRoster' : 'organization'), rules = ref<CrmQualitySettings>(), error = ref(''), loading = ref(false)
const tabs = computed(() => [
  ...(props.appoint ? [{ k: 'battleRoster', label: '三级作战名单', icon: Flag, intro: '统一配置管理者、区总与个人名单；保存后立即同步月度任务令作战地图的数据范围。' }] : []),
  { k: 'organization', label: '我方组织', icon: OfficeBuilding, intro: '维护我方公司 / 部门组织目录，用于责任归属与授权。' },
  { k: 'regions', label: '区域与地图', icon: MapLocation, intro: '集中维护经营区域边界与地图配置；配置权限沿用原授权。' },
  { k: 'rules', label: '评分规则', icon: Odometer, intro: '统一公司与个人关系评估口径，不把计划当作真实互动；评分保持暂估，不作为人员排名。' },
  ...(props.manage || props.appoint ? [{ k: 'permissions', label: '权限管理', icon: Lock, intro: '按角色与数据范围授权，控制客户经营的可见与可操作范围。' }] : []),
  ...(props.manage || props.appoint ? [{ k: 'audit', label: '操作留痕', icon: Document, intro: '查看关键操作的审计记录，可见范围随权限而定。' }] : []),
])
const intro = computed(() => tabs.value.find(t => t.k === section.value)?.intro || '')
async function loadRules() { loading.value = true; error.value = ''; try { rules.value = await crmQualitySettings() } catch (e) { rules.value = undefined; error.value = e instanceof Error ? e.message : '加载失败' } finally { loading.value = false } }
watch(section, value => { if (value === 'rules') loadRules() })
function saved(value: CrmQualitySettings) { rules.value = value; emit('changed') }
</script>
<template>
 <section class="crm-settings">
  <header class="cs-head"><h2>设置</h2><p>组织、区域、评分、权限与操作留痕，集中在此维护。</p></header>
  <nav class="cs-nav" role="tablist" aria-label="客户经营设置分类">
   <button v-for="t in tabs" :key="t.k" type="button" role="tab" :aria-selected="section === t.k" :class="{ on: section === t.k }" @click="section = t.k"><el-icon><component :is="t.icon" /></el-icon>{{ t.label }}</button>
  </nav>
  <div class="cs-panel">
   <p v-if="intro" class="cs-intro">{{ intro }}</p>
   <BattleRosterPanel v-if="section === 'battleRoster' && appoint" expanded />
   <OwnOrganization v-else-if="section === 'organization'" :read-only="!write" @changed="emit('changed')" />
   <RegionSettings v-else-if="section === 'regions'" :can-edit="manage || appoint" />
   <div v-else-if="section === 'rules'" v-loading="loading"><el-alert v-if="error" :title="error" type="error" :closable="false" /><QualityRuleSettings v-if="rules" :settings="rules" :can-manage="manage || appoint" @saved="saved" @reload="loadRules" /><el-button v-if="error" @click="loadRules">重试</el-button></div>
   <SecurityPanel v-else-if="section === 'permissions' && (manage || appoint)" :relations="relations" :people="people" :units="units" :appoint="appoint" :manage="manage" @changed="emit('changed')" />
   <AuditTrail v-else-if="section === 'audit' && (manage || appoint)" />
  </div>
 </section>
</template>
<style scoped>
.cs-head { margin: 2px 2px 16px; }
.cs-head h2 { font-size: 21px; margin: 0; color: #173656; }
.cs-head p { margin: 6px 0 0; font-size: 13px; color: #64789a; }
.cs-nav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.cs-nav button { display: inline-flex; align-items: center; gap: 7px; font: inherit; font-size: 14px; color: #5e7690; background: #f4f8ff; border: 1px solid #e4ecf6; border-radius: 10px; padding: 9px 16px; cursor: pointer; transition: all .15s; }
.cs-nav button:hover { border-color: #b7d0f2; color: #15499c; }
.cs-nav button.on { background: linear-gradient(135deg, #1e6bff, #15499c); border-color: #15499c; color: #fff; box-shadow: 0 10px 22px -14px rgba(21, 73, 156, .7); }
.cs-nav button .el-icon { font-size: 16px; }
.cs-panel { background: #fff; border: 1px solid #e6edf5; border-radius: 14px; padding: 20px; box-shadow: 0 10px 30px -24px rgba(21, 73, 156, .5); min-height: 120px; }
.cs-intro { margin: 0 0 16px; padding: 10px 14px; font-size: 12.5px; color: #5e7690; line-height: 1.7; background: #f6f9ff; border: 1px solid #e8eef8; border-radius: 9px; }
</style>
