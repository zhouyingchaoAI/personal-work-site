<script setup lang="ts">
import {computed,ref,watch,onMounted} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {crmBatchAssignRelations,crmAssignmentDirectory,type CrmUnit,type CrmPerson,type CrmRelation,type CrmStaff} from '../../../src/services/personalWorkApi'
const props=defineProps<{units:CrmUnit[];people:CrmPerson[];relations:CrmRelation[];staff:CrmStaff[]}>()
const emit=defineEmits<{refresh:[]}>()
const mode=ref('assign'),scope=ref('unit'),unit=ref(''),personIds=ref<string[]>([]),source=ref(''),target=ref(''),replace=ref(false),busy=ref(false),message=ref('')
const accounts=ref<Awaited<ReturnType<typeof crmAssignmentDirectory>>['people']>([])
onMounted(async()=>{try{accounts.value=(await crmAssignmentDirectory()).people}catch{ElMessage.error('可指派人员加载失败，请刷新重试')}})
const sourceOptions=computed(()=>[...new Map(props.relations.filter(r=>r.our_member).map(r=>{const account=accounts.value.find(a=>a.username===r.our_staff?.username||a.member_key===r.our_member||a.username===r.our_member);return [account?.member_key||r.our_member,{key:account?.member_key||r.our_member,label:account?`${account.name} · ${account.department} · ${account.member_key}`:r.our_member_label||r.our_member}]})).values()])
const targetOptions=computed(()=>accounts.value.map(s=>({value:s.member_key,label:[s.name,s.department,s.company,s.member_key].filter(Boolean).join(' · ')})))
const selectedSource=computed(()=>accounts.value.find(s=>s.member_key===source.value))
const sourceRelations=computed(()=>props.relations.filter(r=>source.value && (r.our_member===source.value || (selectedSource.value?.username && r.our_staff?.username===selectedSource.value.username))))
const selectedPeople=computed(()=>{
 if(mode.value==='handover')return [...new Set(sourceRelations.value.map(r=>r.person_id))]
 if(scope.value==='person')return personIds.value.filter(id=>props.people.some(p=>p.id===id))
 if(!unit.value)return []
 const ids=new Set([unit.value]);let changed=true
 while(changed){changed=false;for(const u of props.units)if(u.parent_unit_id&&ids.has(u.parent_unit_id)&&!ids.has(u.id)){ids.add(u.id);changed=true}}
 return props.people.filter(p=>ids.has(p.unit_id)).map(p=>p.id)
})
const count=computed(()=>mode.value==='handover'&&replace.value?sourceRelations.value.length:selectedPeople.value.length)
const valid=computed(()=>!!target.value&&count.value>0&&count.value<=500&&!(mode.value==='handover'&&source.value===target.value))
watch([mode,scope,unit,source,target,replace,personIds],()=>message.value='')
watch(mode,()=>{replace.value=false;target.value=''})
async function submit(){
 if(busy.value||!valid.value)return
 busy.value=true
 try{
  if(mode.value==='handover'&&replace.value)await ElMessageBox.confirm(`将 ${count.value} 条关系及原负责人的未完成计划移交给新对接人，原对接人不再负责这些关系。历史互动保留。`,'确认移交替换',{confirmButtonText:'确认移交',cancelButtonText:'取消',type:'warning'})
  const result=await crmBatchAssignRelations(mode.value==='handover'&&replace.value?{relation_ids:sourceRelations.value.map(r=>r.id),our_member:target.value,transfer:true}:{person_ids:selectedPeople.value,our_member:target.value,mode:'add'})
  message.value=`操作完成：${replace.value?'移交':'新增指派'} ${result.updated} 条${result.skipped?`，已有 ${result.skipped} 条已跳过`:''}。`
  emit('refresh')
 }catch(error){if(error!=='cancel'&&error!=='close')ElMessage.error(error instanceof Error?error.message:'操作失败，请重试')}
 finally{busy.value=false}
}
</script>
<template>
 <section class="simple-assignment">
  <header><h3>关系统筹</h3><p>选好客户和对接人即可，无需逐条勾选关系或填写监督任务。</p></header>
  <div class="sa-tabs" role="group" aria-label="统筹方式"><button :disabled="busy" :aria-pressed="mode==='assign'" @click="mode='assign'">关系指派</button><button :disabled="busy" :aria-pressed="mode==='handover'" @click="mode='handover'">关系转移</button></div>
  <fieldset :disabled="busy">
   <div v-if="mode==='assign'" class="sa-field"><label>指派范围</label><el-radio-group v-model="scope" :disabled="busy"><el-radio-button value="unit">按客户组织</el-radio-button><el-radio-button value="person">按客户联系人</el-radio-button></el-radio-group></div>
   <div class="sa-grid">
    <div v-if="mode==='handover'" class="sa-field"><label for="sa-source">原对接人</label><el-select-v2 id="sa-source" v-model="source" :options="sourceOptions.map(s=>({value:s.key,label:s.label}))" filterable clearable :disabled="busy" placeholder="选择或搜索原对接人" aria-label="原对接人"/></div>
    <div v-else-if="scope==='unit'" class="sa-field"><label for="sa-unit">客户组织</label><el-select-v2 id="sa-unit" v-model="unit" :options="units.map(u=>({value:u.id,label:(u.company_full_name && u.company_full_name!==u.name?u.company_full_name+' / ':'')+u.name}))" filterable clearable :disabled="busy" placeholder="选择或搜索客户组织" aria-label="客户组织"/><small>包含该组织及下级组织的当前可见联系人。</small></div>
    <div v-else class="sa-field"><label>客户联系人</label><el-select-v2 v-model="personIds" multiple filterable :disabled="busy" :options="people.map(p=>({value:p.id,label:p.name+' · '+(units.find(u=>u.id===p.unit_id)?.name||'')+' · '+(p.title||'')}))" placeholder="搜索并选择客户联系人" aria-label="客户联系人"/></div>
    <div class="sa-field"><label for="sa-target">目标对接人</label><el-select-v2 id="sa-target" v-model="target" :options="targetOptions" filterable clearable :disabled="busy" placeholder="选择或搜索姓名、工号、部门" aria-label="目标对接人"/></div>
   </div>
   <label v-if="mode==='handover'" class="sa-replace"><input v-model="replace" type="checkbox"/>移交替换：原人员退出，并移交未完成计划</label>
   <p class="sa-hint">{{mode==='handover'&&!replace?'默认保留原人员，将其对接客户添加给新人；不复制历史互动或待办。':mode==='assign'?'新增对接关系，保留现有人员；已指派给该人的客户自动跳过。':'历史互动保留原记录，不改写为新人的业绩。'}}仅调整客户对接关系，不授予系统管理权限。</p>
   <footer><span>本次涉及 {{count}} {{replace?'条关系':'位联系人'}}<small v-if="count>500"> · 单次最多500，请缩小范围</small></span><el-button type="primary" :disabled="!valid||busy" :loading="busy" @click="submit">{{mode==='assign'?'确认指派':replace?'确认移交':'确认添加'}}</el-button></footer>
  </fieldset>
  <p v-if="message" role="status" class="sa-result">{{message}}</p>
 </section>
</template>
<style scoped>
.sa-field :deep(.el-select-v2){width:100%}.sa-field :deep(.el-select-v2__wrapper){min-height:40px}.sa-field select{min-height:40px}
.simple-assignment{padding:20px;background:white;border:1px solid #e1e7ef;border-radius:10px;margin-bottom:16px}.simple-assignment h3{margin:0;font-size:18px}.simple-assignment header p,.sa-hint{font-size:13px;color:#64748b;line-height:1.8}.sa-tabs{display:flex;gap:8px;margin:20px 0}.sa-tabs button{font:inherit;border:1px solid #dbe3ef;background:white;border-radius:6px;padding:8px 20px;color:#475569;cursor:pointer}.sa-tabs button[aria-pressed=true]{background:#edf4ff;color:#205ca0;border-color:#91b6e8}fieldset{border:0;padding:0;margin:0;min-width:0}.sa-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.sa-field{display:flex;flex-direction:column;gap:9px;margin-bottom:18px;min-width:0}.sa-field label{font-size:14px;font-weight:600}.sa-field select,.sa-field>input{font:inherit;font-size:14px;padding:10px;border:1px solid #d9e1ec;border-radius:6px;background:white;width:100%;box-sizing:border-box;min-width:0;color:#334155}.sa-field small{font-size:12px;color:#64748b}.sa-replace{font-size:13px;display:flex;align-items:center;gap:8px}.sa-hint{margin:8px 0 18px}footer{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:14px}.sa-result{padding:12px;background:#edf8f1;color:#26704b;border-radius:6px;font-size:14px}@media(max-width:650px){.sa-grid{grid-template-columns:1fr;gap:0}.simple-assignment{padding:14px}.sa-tabs button{padding:8px 12px}footer{flex-wrap:wrap}}
</style>
