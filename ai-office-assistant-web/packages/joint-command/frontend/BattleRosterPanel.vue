<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { crmBattleRoster, crmSaveBattleRoster, crmSecurityUsers, type CrmBattleRoster, type CrmSecurityUser } from '../../../src/services/personalWorkApi'

const loading=ref(false)
const saving=ref(false)
const roster=ref<CrmBattleRoster|null>(null)
const users=ref<CrmSecurityUser[]>([])
const roleNames=['主管/办事处负责人','客户经理/销售工程师','集成解决方案销售','轨道BD','服务区域经理','项目管理/项目经理','战区综合专员']
defineProps<{ expanded?: boolean }>()
const candidates=computed(()=>users.value.filter(user=>!user.superadmin).sort((a,b)=>a.name.localeCompare(b.name,'zh')))
const optionLabel=(username:string)=>{const user=users.value.find(item=>item.username===username);return user?`${user.name} · ${user.position||user.department||username}`:username}
async function load(){loading.value=true;try{const [data,people]=await Promise.all([crmBattleRoster(),crmSecurityUsers()]);roster.value=data;users.value=people.users}catch(error){ElMessage.error(error instanceof Error?error.message:'名单加载失败')}finally{loading.value=false}}
async function save(){if(!roster.value)return;saving.value=true;try{roster.value=await crmSaveBattleRoster({version:roster.value.version,management:roster.value.management,units:roster.value.units});ElMessage.success('三级作战名单及权限已同步')}catch(error){ElMessage.error(error instanceof Error?error.message:'名单保存失败')}finally{saving.value=false}}
onMounted(load)
</script>

<template>
  <details class="battle-roster" v-loading="loading" :open="expanded">
    <summary><span><b>三级作战名单统一配置</b><small>管理看全部 · 区总看本单元 · 个人看本人</small></span><em>{{ roster?.units.length||0 }} 个作战单元</em></summary>
    <div v-if="roster" class="roster-body">
      <section class="management-row"><div><b>管理名单</b><small>可查看全部机会点和推进情况</small></div><el-select v-model="roster.management" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择管理人员"><el-option v-for="user in candidates" :key="user.username" :label="optionLabel(user.username)" :value="user.username" /></el-select></section>
      <div class="unit-grid">
        <article v-for="unit in roster.units" :key="unit.id" class="unit-card">
          <header><div><b>{{ unit.name }}</b><small>{{ unit.areas }}</small></div><el-tag effect="plain">{{ unit.business_region }}</el-tag></header>
          <label class="leader-field"><span>区总 / 负责人</span><el-select v-model="unit.leaders" multiple filterable collapse-tags placeholder="选择负责人"><el-option v-for="user in candidates" :key="user.username" :label="optionLabel(user.username)" :value="user.username" /></el-select></label>
          <label v-for="role in roleNames" :key="role" class="role-field"><span>{{ role }}</span><el-select v-model="unit.roles[role]" multiple filterable collapse-tags collapse-tags-tooltip placeholder="未配置"><el-option v-for="user in candidates" :key="user.username" :label="optionLabel(user.username)" :value="user.username" /></el-select></label>
        </article>
      </div>
      <footer><span>保存后立即同步三级数据范围；同一人多个岗位只授权一次。</span><el-button type="primary" :loading="saving" @click="save">保存并同步权限</el-button></footer>
    </div>
  </details>
</template>

<style scoped>
.battle-roster{border:1px solid #cfe0f3;border-radius:12px;background:#f7faff}.battle-roster>summary{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;cursor:pointer;list-style:none;color:#1d4f86}.battle-roster>summary span{display:flex;align-items:baseline;gap:12px}.battle-roster>summary small{color:#70869d;font-weight:400}.battle-roster>summary em{font-style:normal;font-size:12px;color:#55718e}.roster-body{padding:0 14px 14px}.management-row{display:grid;grid-template-columns:230px 1fr;gap:14px;align-items:center;padding:12px;background:#fff;border:1px solid #dfe8f2;border-radius:10px;margin-bottom:10px}.management-row div{display:flex;flex-direction:column;gap:4px}.management-row small,.unit-card small,footer span{font-size:11px;color:#758aa0}.unit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.unit-card{padding:12px;background:#fff;border:1px solid #dfe8f2;border-radius:10px}.unit-card header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;padding-bottom:9px;margin-bottom:8px;border-bottom:1px solid #edf1f6}.unit-card header div{display:flex;flex-direction:column;gap:4px}.leader-field,.role-field{display:grid;grid-template-columns:125px 1fr;gap:8px;align-items:center;margin-top:7px}.leader-field span,.role-field span{font-size:12px;color:#425f7d}.leader-field span{font-weight:700;color:#1b5ba0}.battle-roster footer{display:flex;justify-content:space-between;align-items:center;margin-top:12px;padding-top:10px;border-top:1px solid #dfe8f2}@media(max-width:1200px){.unit-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.unit-grid{grid-template-columns:1fr}.management-row{grid-template-columns:1fr}.leader-field,.role-field{grid-template-columns:110px 1fr}}
</style>
