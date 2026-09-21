<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { crmSecurityUsers, crmSecurityGrant, type CrmSecurityUser, type CrmRelation, type CrmPerson, type CrmUnit } from '../../services/personalWorkApi'
import { resolveLiaisonRegion } from './liaisonRegions'
import PersonFlags from './PersonFlags.vue'
const props=defineProps<{relations:CrmRelation[];people:CrmPerson[];units:CrmUnit[];canManage:boolean;initialView?:string}>()
const emit=defineEmits<{refresh:[];navigate:[tab:'archive'|'relation']}>()
const ownRootName='湖南承希科技有限公司'
const region=ref(''),search=ref(''),importance=ref(''),support=ref(''),selected=ref(''),busy=ref(false),accounts=ref<CrmSecurityUser[]>([])
const matchesLevel=(value:string|undefined,filter:string)=>!filter||(filter==='__empty__'?!value?.trim():value===filter)
const hasFilters=computed(()=>!!(region.value||search.value||importance.value||support.value))
function resetFilters(){region.value='';search.value='';importance.value='';support.value=''}
async function loadAccounts(){if(!props.canManage){accounts.value=[];return}try{accounts.value=(await crmSecurityUsers()).users}catch{accounts.value=[];ElMessage.warning('授权名单加载失败，请刷新重试')}}
watch(()=>props.canManage,loadAccounts,{immediate:true})
const rows=computed(()=>props.relations.map(r=>{const person=props.people.find(p=>p.id===r.person_id);const unit=props.units.find(u=>u.id===person?.unit_id);return{r,person,unit,regions:unit?.business_regions?.length?unit.business_regions:[unit?.business_region||'未分区']}}))
const allMembers=computed(()=>{
 const groups=new Map<string,{key:string;name:string;username:string;department:string;region:string;regionPriority:number;items:typeof rows.value}>()
 for(const row of rows.value){
  const key=row.r.our_staff?.username||row.r.our_member
  if(!key)continue
  let group=groups.get(key)
  const staffRegion=row.r.our_staff?.business_region||''
  const resolved=resolveLiaisonRegion(row.r.our_staff,staffRegion,row.regions[0])
  if(!group){group={key,name:row.r.our_staff?.name||row.r.our_member,username:row.r.our_staff?.username||'',department:[row.r.our_staff?.department,row.r.our_staff?.title].filter(Boolean).join(' · '),region:resolved.region,regionPriority:resolved.priority,items:[]};groups.set(key,group)}
  else if(resolved.priority>group.regionPriority){group.region=resolved.region;group.regionPriority=resolved.priority}
  group.items.push(row)
 }
 return [...groups.values()]
})
const regions=computed(()=>[...new Set(allMembers.value.map(member=>member.region))].sort())
const levelFilter=(items:typeof rows.value)=>items.filter(i=>matchesLevel(i.person?.importance,importance.value)&&matchesLevel(i.person?.support_level,support.value))
const members=computed(()=>allMembers.value.map(g=>({...g,items:levelFilter(g.items)})).filter(g=>g.items.length&&(!region.value||g.region===region.value)&&`${ownRootName} ${g.name} ${g.items.map(i=>i.r.our_staff?.company||'').join(' ')} ${g.department} ${g.key} ${g.items.map(i=>`${i.person?.name} ${i.unit?.name}`).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())).sort((a,b)=>b.items.length-a.items.length))
const active=computed(()=>members.value.find(m=>m.key===selected.value)||members.value[0])
const view=ref(props.initialView||'organizations'), selectedOrg=ref(''), customerOrg=ref('')
const ownOrganizations=computed(()=>{
 const groups=new Map<string,{key:string;company:string;department:string;items:typeof rows.value}>()
 for(const member of members.value) for(const item of member.items){
  const company=item.r.our_staff?.company?.trim()||ownRootName
  const department=item.r.our_staff?.department?.trim()||'部门待补充'
  const key=JSON.stringify([company,department])
  if(!groups.has(key))groups.set(key,{key,company,department,items:[]})
  groups.get(key)!.items.push(item)
 }
 return [...groups.values()].sort((a,b)=>b.items.length-a.items.length)
})
const ownRoot=computed(()=>({key:'',company:ownRootName,department:'全部下级组织',items:ownOrganizations.value.flatMap(org=>org.items)}))
const activeOrg=computed(()=>ownOrganizations.value.find(o=>o.key===selectedOrg.value)||ownRoot.value)
const memberCount=(items:typeof rows.value)=>new Set(items.map(i=>i.r.our_staff?.username||i.r.our_member).filter(Boolean)).size
const organizationConnections=computed(()=>{
 const groups=new Map<string,{key:string;name:string;type:string;items:typeof rows.value}>()
 for(const item of activeOrg.value?.items||[]){
  const key=item.unit?.id||'unassigned'
  if(!groups.has(key))groups.set(key,{key,name:item.unit?.name||'客户组织待补充',type:item.unit?.type||'未分类',items:[]})
  groups.get(key)!.items.push(item)
 }
 return [...groups.values()].map(g=>({...g,memberCount:memberCount(g.items),peopleCount:countPeople(g.items),lastTouch:g.items.map(i=>i.r.last_touch).filter(Boolean).sort().at(-1)||'暂无互动'})).sort((a,b)=>b.items.length-a.items.length)
})
const visibleConnections=computed(()=>organizationConnections.value.filter(g=>!customerOrg.value||g.key===customerOrg.value))
watch(activeOrg,()=>{if(!organizationConnections.value.some(g=>g.key===customerOrg.value))customerOrg.value=''})
const countPeople=(items:typeof rows.value)=>new Set(items.map(i=>i.r.person_id)).size
const countUnits=(items:typeof rows.value)=>new Set(items.map(i=>i.unit?.id).filter(Boolean)).size
const targets=computed(()=>accounts.value.filter(a=>!a.superadmin&&!a.capabilities.manage&&!a.capabilities.read&&members.value.some(m=>m.username===a.username||m.key===a.username||!!a.employee_id&&m.key===a.employee_id)))
async function authorize(){
 const users=[...targets.value];if(!users.length)return
 try{await ElMessageBox.confirm(`为当前列表中 ${users.length} 位尚未开通人员开放“只读 · 仅本人”客户经营权限？已授权人员不变，不开放全区域或全量数据。`,'批量开放权限',{type:'warning'})}catch{return}
 busy.value=true;const failed:string[]=[]
 for(const user of users){try{await crmSecurityGrant({username:user.username,role:'viewer',data_scope:'self',expires_on:''})}catch{failed.push(user.name||user.username)}}
 busy.value=false;await loadAccounts();emit('refresh')
 if(failed.length)ElMessage.warning(`成功 ${users.length-failed.length} 人；未成功：${failed.join('、')}`)
 else ElMessage.success(`已为 ${users.length} 人开放本人只读权限`)
}
</script>
<template>
 <section class="liaisons" aria-label="组织对接工作区">
  <header><el-radio-group v-model="view" class="ld-view-switch" aria-label="组织对接视图"><el-radio-button value="organizations">按组织查看</el-radio-button><el-radio-button value="people">按人员查看</el-radio-button></el-radio-group><div class="ld-actions"><el-button :icon="Refresh" @click="loadAccounts();emit('refresh')">刷新</el-button><el-tooltip v-if="canManage" content="仅为匹配到平台账号且未开通的人员开放本人只读权限；重名及未绑定人员不自动授权。"><el-button :loading="busy" :disabled="!targets.length" @click="authorize">开通只读权限（{{targets.length}}）</el-button></el-tooltip></div></header>
  <div class="ld-tools" role="group" aria-label="客户对接人筛选"><el-input v-model="search" :prefix-icon="Search" clearable placeholder="搜索组织、对接人或客户" aria-label="搜索客户对接人"/><el-select v-model="region" clearable placeholder="全部所属区域" aria-label="对接人员区域"><el-option v-for="r in regions" :key="r" :label="r" :value="r"/></el-select><el-select v-model="importance" clearable placeholder="全部重要程度" aria-label="对接客户重要程度筛选"><el-option v-for="t in ['重要','一般']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select><el-select v-model="support" clearable placeholder="全部支持程度" aria-label="对接客户支持程度筛选"><el-option v-for="t in ['反对','中立','支持','积极支持']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select><el-button :disabled="!hasFilters" @click="resetFilters">重置筛选</el-button></div>
  <div class="ld-results"><strong>{{members.length}} 位客户对接人</strong><span>已匹配 {{region||'全部区域'}} · {{view === 'organizations' ? '选择左侧我方组织查看对接覆盖' : '选择左侧人员查看关联客户'}}</span></div>
  <div v-if="view === 'organizations' && ownRoot.items.length" class="ld-body ld-organization-view">
    <aside aria-label="我方组织"><h3>我方组织</h3>
      <button class="ld-own-root" :aria-pressed="activeOrg.key === ''" @click="selectedOrg=''"><b>{{ownRootName}}</b><small>我方根组织 · 全部下级汇总</small><span>{{memberCount(ownRoot.items)}} 位对接人 · {{countUnits(ownRoot.items)}} 个客户组织</span></button>
      <div class="ld-own-children"><button v-for="org in ownOrganizations" :key="org.key" :aria-pressed="activeOrg.key===org.key" @click="selectedOrg=org.key"><b>{{org.company===ownRootName ? org.department : org.company}}</b><small v-if="org.company!==ownRootName">{{org.department}}</small><span>{{memberCount(org.items)}} 位对接人 · {{countUnits(org.items)}} 个客户组织</span></button></div>
    </aside>
    <main>
      <h3>{{ownRootName}}</h3><p>{{activeOrg.key ? [activeOrg.company===ownRootName ? '' : activeOrg.company,activeOrg.department].filter(Boolean).join(' / ') : '全部下级组织对接情况'}}</p>
      <div class="ld-org-summary"><span>我方对接人 <b>{{memberCount(activeOrg.items)}}</b></span><span>客户组织 <b>{{organizationConnections.length}}</b></span><span>客户联系人 <b>{{countPeople(activeOrg.items)}}</b></span><span>对接关系 <b>{{activeOrg.items.length}}</b></span></div>
      <el-select v-model="customerOrg" clearable filterable placeholder="查看全部客户组织" aria-label="对接客户组织" class="ld-customer-org"><el-option v-for="org in organizationConnections" :key="org.key" :label="org.name" :value="org.key"/></el-select>
      <p>我方统一归属湖南承希科技有限公司，下级分组保留原公司、部门信息；展开客户组织查看双方人员明细，未登记关系的组织不计入覆盖。</p>
      <el-table :data="visibleConnections" row-key="key" class="ld-connections" empty-text="暂无匹配的组织对接关系">
        <el-table-column type="expand"><template #default="{row:org}">
          <el-table :data="org.items" class="ld-connection-details">
            <el-table-column label="我方对接人" min-width="150"><template #default="{row}">{{row.r.our_staff?.name||row.r.our_member_label||row.r.our_member||'待补充'}}</template></el-table-column>
            <el-table-column label="客户联系人" min-width="150"><template #default="{row}">{{row.person?.name||row.r.person_name||'待补充'}}</template></el-table-column>
            <el-table-column label="客户部门 / 职务" min-width="180"><template #default="{row}">{{[row.person?.department,row.person?.title].filter(Boolean).join(' / ')||'待补充'}}</template></el-table-column>
            <el-table-column label="重要程度" width="105"><template #default="{row}"><PersonFlags field="importance" :importance="row.person?.importance"/></template></el-table-column>
            <el-table-column label="支持程度" width="115"><template #default="{row}"><PersonFlags field="support" :support="row.person?.support_level"/></template></el-table-column>
            <el-table-column label="关系强度" width="100"><template #default="{row}">L{{row.r.strength}}</template></el-table-column>
            <el-table-column label="最近互动" min-width="120"><template #default="{row}">{{row.r.last_touch||'暂无互动'}}</template></el-table-column>
          </el-table>
        </template></el-table-column>
        <el-table-column label="客户组织" prop="name" min-width="240" show-overflow-tooltip/>
        <el-table-column label="组织类型" prop="type" width="100"/>
        <el-table-column label="我方人数" prop="memberCount" width="100"/>
        <el-table-column label="联系人" prop="peopleCount" width="90"/>
        <el-table-column label="关系数" width="90"><template #default="{row}">{{row.items.length}}</template></el-table-column>
        <el-table-column label="最近互动" prop="lastTouch" min-width="120"/>
      </el-table>
    </main>
  </div>
  <el-empty v-else-if="view === 'organizations'" description="当前筛选范围暂无组织对接记录，请重置筛选或登记客户关系"/>
  <div v-if="view === 'people' && active" class="ld-body"><aside><button v-for="m in members" :key="m.key" :aria-pressed="active.key===m.key" @click="selected=m.key"><b>{{m.name}} · {{m.region}}</b><small>{{m.department||'组织岗位待补充'}}</small><span>{{countUnits(m.items)}} 个组织 · {{countPeople(m.items)}} 位客户 · {{m.items.length}} 条链路</span></button></aside>
   <main><h3>{{active.name}} 对接客户</h3><p>{{active.department}}</p><el-table :data="active.items" height="440"><el-table-column label="客户联系人" min-width="180"><template #default="{row}"><b>{{row.person?.name||row.r.person_name||'待补充'}}</b><div>{{row.person?.title}}</div><PersonFlags compact :importance="row.person?.importance" :support="row.person?.support_level"/></template></el-table-column><el-table-column label="客户组织 / 部门" min-width="230"><template #default="{row}">{{row.unit?.company_full_name||row.unit?.name||'组织待补充'}}<div>{{row.unit?.name}} · {{row.person?.department}}</div></template></el-table-column><el-table-column label="区域" min-width="110"><template #default="{row}">{{row.regions.join('、')}}</template></el-table-column><el-table-column label="关系 / 最近互动" min-width="160"><template #default="{row}">L{{row.r.strength}} · {{row.r.last_touch||'暂无互动'}}</template></el-table-column></el-table></main>
  </div><el-empty v-else-if="view === 'people'" :description="hasFilters ? '没有匹配的客户对接人，请调整或重置筛选' : '暂无客户对接人，建立客户关系后将自动显示'"/>
 </section>
</template>
<style scoped>
.liaisons{padding:16px;background:#f6f9fe;border-radius:12px}.liaisons header,.ld-tools{display:flex;align-items:center;gap:12px;justify-content:space-between}.liaisons h3{margin:0 0 8px;color:#23476d}.liaisons p{color:#6c8097;font-size:13px}.ld-tools{flex-wrap:wrap}.ld-tools .el-select{width:170px;flex-shrink:0}.ld-tools .el-input{flex:1;min-width:200px;max-width:500px}.ld-body{display:grid;grid-template-columns:290px minmax(0,1fr);gap:18px}.ld-body aside{max-height:510px;overflow:auto}.ld-body aside button{display:block;width:100%;text-align:left;padding:14px;margin-bottom:8px;border:1px solid #d2dfef;border-radius:8px;background:white;color:#26496c;cursor:pointer}.ld-body aside button[aria-pressed=true]{background:#e8f2ff;border-color:#307bcb}.ld-body small,.ld-body span{display:block;margin-top:7px}.ld-body main{min-width:0}.ld-body small{color:#6c8097}@media(max-width:750px){.ld-body{grid-template-columns:1fr}.ld-body aside{max-height:210px}.ld-tools{flex-wrap:wrap}}
</style>
<style scoped>
.liaisons {padding:0;background:transparent;}
.liaisons header {margin-bottom:16px;align-items:flex-start;flex-wrap:wrap;}
.liaisons header p {margin:4px 0 0;line-height:1.6;}
.ld-actions {display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.ld-actions .el-button {margin:0;}
.ld-tools {justify-content:flex-start;gap:10px;padding:12px;border:1px solid #e7edf5;border-radius:10px;background:#f7f9fc;}
.ld-tools .el-input {flex:0 1 340px;width:340px;min-width:240px;max-width:340px;}
.ld-tools .el-select {width:150px;}
.ld-tools :deep(.el-input__wrapper),.ld-tools :deep(.el-select__wrapper) {min-height:36px;border-radius:7px;}
.ld-tools .el-button {margin:0;min-height:36px;}
.ld-results {display:flex;align-items:center;gap:16px;margin:14px 0;color:#385570;font-size:13px;flex-wrap:wrap;}
.ld-results span {color:#73869b;}
.ld-body {gap:14px;grid-template-columns:260px minmax(0,1fr);}
.ld-body aside {padding:6px;background:#f7f9fc;border:1px solid #e7edf5;border-radius:10px;}
.ld-body aside button {padding:12px;border-color:transparent;margin-bottom:6px;}
.ld-body aside button[aria-pressed=true] {border-color:#8cb0dc;background:#edf4ff;box-shadow:inset 3px 0 #245aa0;}
.ld-body main {padding:14px;border:1px solid #e7edf5;border-radius:10px;background:#fff;}
.ld-view-switch {margin-bottom:14px;}
.ld-organization-view aside h3 {padding:8px;font-size:14px;}
.ld-own-children {margin-left:12px;padding-left:10px;border-left:2px solid #dce6f3;}
.ld-own-root b {line-height:1.6;}
.ld-org-summary {display:flex;gap:12px;flex-wrap:wrap;margin:14px 0;}
.ld-org-summary span {display:inline-flex;align-items:center;gap:12px;margin:0;padding:10px 14px;border-radius:8px;background:#f4f7fc;color:#5a7189;font-size:12px;}
.ld-org-summary b {font-size:20px;color:#24558b;}
.ld-customer-org {width:300px;max-width:100%;}
.ld-connection-details {padding:8px 16px;}
@media(max-width:750px) {
 .ld-body {grid-template-columns:1fr;}
 .ld-tools {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));}
 .ld-tools .el-input {grid-column:1 / -1;width:100%;min-width:0;max-width:none;}
 .ld-tools .el-select {width:100%;min-width:0;}
}
</style>
