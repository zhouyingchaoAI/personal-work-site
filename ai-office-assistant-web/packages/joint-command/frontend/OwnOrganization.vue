<script setup lang="ts">
import CompanyFields from './CompanyFields.vue'
import InternalOrganizationEntry from './InternalOrganizationEntry.vue'
import catalog from '../../../../backend/crm_org_catalog.json'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { crmStaff, crmSaveStaff, type CrmStaff } from '../../../src/services/personalWorkApi'
defineProps<{ readOnly?: boolean }>()
const emit=defineEmits<{changed:[]}>()
const staff=ref<CrmStaff[]>([]), query=ref(''), mode=ref('departments'), page=ref(1), busy=ref(false), visible=ref(false)
const form=reactive<Partial<CrmStaff>>({})
const filtered=computed(()=>staff.value.filter(p=>`${p.name} ${p.member_key} ${p.company} ${p.department} ${p.title}`.includes(query.value.trim())))
watch(query,()=>page.value=1)
const managerName=(id:string)=>staff.value.find(p=>p.id===id)?.name || '未指定'
interface Node {id:string;label:string;children:Node[]}
const departments=computed(()=>{
 const roots:Node[]=[]
 const groups=new Map<string,Node>()
 for(const p of staff.value){
  for(const membership of [{company:p.company,department:p.department},...(p.organization_memberships||[])]){
  const company=membership.company || '我方公司', department=membership.department || '待补充部门', position=p.title || '待补充岗位'
  let parent:Node|undefined
  const levels=[company,...department.split(' / '),position]
  for(const [index,label] of levels.entries()){
   const key=JSON.stringify(levels.slice(0,index+1))
   let node=groups.get(key)
   if(!node){node={id:key,label,children:[]};groups.set(key,node);if(parent)parent.children.push(node);else roots.push(node)}
   parent=node
  }
  parent!.children.push({id:`${parent!.id}:${p.id}`,label:`${p.name} · ${p.member_key}${membership.company!==p.company||membership.department!==p.department?' · 兼任':''}${p.business_region ? ' · '+p.business_region : ''}`,children:[]})
  }
 }
 return roots
})
const tree=computed(()=>{
 const nodes=new Map<string,Node>(staff.value.map(p=>[p.id,{id:p.id,label:`${p.name} · ${p.department || '未填部门'} · ${p.title || '待补充岗位'}`,children:[]}]))
 const roots:Node[]=[]
 for(const p of staff.value){const n=nodes.get(p.id)!;if(p.manager_id&&nodes.has(p.manager_id))nodes.get(p.manager_id)!.children.push(n);else roots.push(n)}
 return roots
})
async function load(){busy.value=true;try{staff.value=(await crmStaff()).staff}catch{ElMessage.error('我方组织加载失败')}finally{busy.value=false}}
function edit(p?:CrmStaff){Object.assign(form,{id:'',name:'',member_key:'',company:'',department:'',title:'',manager_id:'',business_region:'',responsibilities:'',version:0},p || {});visible.value=true}
async function save(){if(!form.name?.trim())return ElMessage.warning('请填写姓名');busy.value=true;try{const r=await crmSaveStaff(form);if(!r.ok)return ElMessage.error(r.error||'保存失败');visible.value=false;await load();ElMessage.success('我方人员已保存');emit('changed')}catch{ElMessage.error('保存失败，请重试')}finally{busy.value=false}}
onMounted(load)
</script>
<template>
<section v-loading="busy" class="own-org">
 <InternalOrganizationEntry @changed="load();emit('changed')"/>
 <details class="catalog-guide"><summary>承希科技组织目录（公司 / 部门，可直接选择）</summary><div v-for="c in catalog.companies" :key="c.name"><h4>{{c.name}}</h4><p v-for="d in c.departments" :key="d">{{d}}</p></div><small>{{catalog.note}}</small></details>
 <p>当前账号维护的我方人员档案 · 按部门与岗位组织人员；汇报关系单独维护，不授予系统权限。</p>
 <div class="own-toolbar"><el-radio-group v-model="mode"><el-radio-button value="departments">部门 / 岗位 / 人员</el-radio-button><el-radio-button value="list">人员档案</el-radio-button><el-radio-button value="tree">汇报架构</el-radio-button></el-radio-group><el-input v-if="mode === 'list'" v-model="query" clearable placeholder="搜索姓名、公司、部门或工号" style="max-width:300px"/><el-button @click="load">刷新</el-button><el-button v-if="!readOnly" type="primary" @click="edit()">新增我方人员</el-button></div>
 <template v-if="mode === 'list'"><el-table :data="filtered.slice((page-1)*5,page*5)" empty-text="尚未登记我方人员，先新增负责人，再登记其下属">
 <el-table-column prop="name" label="姓名" min-width="100"/><el-table-column prop="member_key" label="对接标识" min-width="110"/><el-table-column prop="company" label="公司" min-width="130"/><el-table-column prop="department" label="部门" min-width="120"/><el-table-column prop="title" label="岗位" min-width="100"/><el-table-column label="直接上级" min-width="100"><template #default="{row}">{{ managerName(row.manager_id) }}</template></el-table-column><el-table-column prop="business_region" label="负责区域" width="100"/><el-table-column label="操作" width="80" fixed="right"><template #default="{row}"><el-button link @click="edit(row)">{{ readOnly ? '详情' : '编辑' }}</el-button></template></el-table-column>
 </el-table><el-pagination v-if="filtered.length>5" v-model:current-page="page" :page-size="5" :total="filtered.length" layout="prev, pager, next, total"/></template>
 <template v-else-if="mode === 'tree'"><p>按直接上级组织，点击节点展开下属；未指定上级的人员显示在顶层。</p><el-tree :data="tree" node-key="id" empty-text="暂无我方人员" :default-expand-all="false" /></template>
 <template v-else><p>按公司 → 部门 → 岗位 → 人员展示。同一岗位可以有多位人员；在人员档案中维护部门和岗位。</p><el-tree :data="departments" node-key="id" :default-expand-all="true" empty-text="暂无我方人员，请先填写部门、岗位和姓名" /></template>
 <el-dialog v-model="visible" :title="readOnly ? '我方人员详情' : '我方人员档案'" width="min(640px,94vw)" append-to-body class="crm-editor-dialog" :close-on-click-modal="false"><el-form label-position="top" :disabled="readOnly">
 <el-form-item label="姓名" required><el-input v-model="form.name" maxlength="80"/></el-form-item><el-form-item label="对接标识 / 工号（选填）"><el-input v-model="form.member_key" :disabled="!!form.id" placeholder="留空使用姓名；同名人员使用不同工号。保存后标识固定。" maxlength="80"/></el-form-item>
 <CompanyFields v-model:company="form.company" v-model:department="form.department" v-model:position="form.title" />
 <el-form-item label="负责区域"><el-select v-model="form.business_region" clearable><el-option v-for="r in ['东区','西区','中区','广东区']" :key="r" :value="r" :label="r"/></el-select></el-form-item>
 <el-form-item label="直接上级"><el-select v-model="form.manager_id" clearable filterable style="width:100%"><el-option v-for="p in staff.filter(p=>p.id!==form.id)" :key="p.id" :value="p.id" :label="`${p.name} · ${p.department} · ${p.member_key}`"/></el-select></el-form-item><el-form-item label="负责事项"><el-input v-model="form.responsibilities" type="textarea" :rows="2" maxlength="1000"/></el-form-item>
 </el-form><template #footer><el-button @click="visible=false">关闭</el-button><el-button v-if="!readOnly" type="primary" :loading="busy" @click="save">保存人员</el-button></template></el-dialog>
</section>
</template>
<style scoped>.own-toolbar{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}.own-org p{font-size:13px;color:#657991}.el-tree{max-height:40vh;overflow:auto}.el-pagination{margin-top:12px}</style>
