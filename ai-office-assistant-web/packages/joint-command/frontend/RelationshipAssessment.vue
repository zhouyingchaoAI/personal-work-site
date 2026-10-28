<script setup lang="ts">
import {ref} from 'vue'
import {Refresh} from '@element-plus/icons-vue'
import type {CrmUnit,CrmPerson,CrmRelation} from '../../../src/services/personalWorkApi'
import AssessmentOverview from './AssessmentOverview.vue'
import OrganizationQuality from './OrganizationQuality.vue'
import PersonalRelationshipAssessment from './PersonalRelationshipAssessment.vue'
import LiaisonDirectory from './LiaisonDirectory.vue'
defineProps<{units:CrmUnit[];people:CrmPerson[];relations:CrmRelation[];canManage:boolean}>()
const emit=defineEmits<{refresh:[];navigate:[tab:'archive'|'relation']}>()
const mode=ref('overview'),details=ref(false),focusId=ref('')
function openLayer(target:string){focusId.value='';mode.value=target}
function focusCompany(id:string){focusId.value=id;mode.value='company'}
</script>
<template>
 <section aria-label="关系评估工作区">
  <div class="assessment-toolbar"><el-radio-group v-model="mode" class="assessment-tabs" aria-label="关系评估维度"><el-radio-button value="overview">总览</el-radio-button><el-radio-button value="company">公司与客户</el-radio-button><el-radio-button value="personal">个人与客户</el-radio-button><el-radio-button value="personal-organization">个人与客户组织</el-radio-button></el-radio-group><div><el-button @click="details=true">查看对接明细</el-button><el-button :icon="Refresh" @click="emit('refresh')">刷新</el-button></div></div>
  <AssessmentOverview v-if="mode==='overview'" :units="units" :people="people" :relations="relations" :can-manage="canManage" @navigate="tab=>emit('navigate',tab)" @layer="openLayer" @focus="focusCompany"/>
  <OrganizationQuality v-else-if="mode==='company'" :units="units" :people="people" :relations="relations" :can-manage="canManage" :focus-id="focusId" @navigate="tab=>emit('navigate',tab)"/>
  <PersonalRelationshipAssessment v-else :key="mode" :organization-mode="mode==='personal-organization'" :units="units" :people="people" :relations="relations" :can-manage="canManage" @navigate="tab=>emit('navigate',tab)"/>
  <el-drawer v-model="details" title="组织与人员对接明细" size="min(1400px, 100vw)" class="assessment-details" destroy-on-close>
   <LiaisonDirectory initial-view="organizations" :units="units" :people="people" :relations="relations" :can-manage="canManage" @refresh="emit('refresh')" @navigate="tab=>{details=false;emit('navigate',tab)}"/>
  </el-drawer>
 </section>
</template>
<style scoped>
.assessment-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0 22px}.assessment-toolbar>div{display:flex;gap:8px}.assessment-toolbar .el-button{margin:0}
</style>
