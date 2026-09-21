<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import OrganizationEditor from './OrganizationEditor.vue'
import { getInternalOrganization, saveInternalOrganization, type InternalOrganizationData, type CrmUnit, type CrmPerson } from '../../services/personalWorkApi'
const emit=defineEmits<{changed:[]; dirty:[value:boolean]}>()
const data=ref<InternalOrganizationData>(), busy=ref(false), dirty=ref(false)
const nodeDialog=ref(false), nodeId=ref(''), nodeName=ref(''), parentId=ref('')
const personDialog=ref(false), personId=ref(''), targetId=ref('')
const members=computed(()=>data.value?.members||[])
const nodes=computed(()=>data.value?.nodes||[])
const units=computed<CrmUnit[]>(()=>nodes.value.map(n=>({id:n.id,name:n.name,parent_unit_id:n.parent_id,organization_level:n.parent_id?'unit':'company',type:`${n.parent_id?'部门':'公司'} · ${members.value.filter(p=>p.node_id===n.id).length} 人`,region:'',line_scale:'',bid_preference:'',history:'',win_rate:'',source:'',version:0})))
const people=computed<CrmPerson[]>(()=>members.value.map(p=>({id:p.username,name:`${p.name}${p.employee_id?' · '+p.employee_id:''}`,unit_id:p.node_id,department:'',title:p.position,decision_role:'',power_radius:'',influence:0,stance:'',career_track:[],rotation_window:'',version:0})))
function mark(value=true){dirty.value=value;emit('dirty',value)}
async function load(){busy.value=true;try{data.value=await getInternalOrganization();mark(false)}catch(e){ElMessage.error(e instanceof Error?e.message:'组织加载失败')}finally{busy.value=false}}
function path(id:string){const parts:string[]=[],seen=new Set<string>();let n=nodes.value.find(n=>n.id===id);while(n&&!seen.has(n.id)){parts.unshift(n.name);seen.add(n.id);n=nodes.value.find(p=>p.id===n!.parent_id)}return parts.join(' / ')}
function editNode(unit?:CrmUnit){if(unit?.id==='own:unassigned')return ElMessage.info('请将未分配人员拖入正式公司；该保留节点不能改名');nodeId.value=unit?.id||'';nodeName.value=unit?.name||'';parentId.value=unit?.parent_unit_id||'';nodeDialog.value=true}
function addNode(_level?:string,parent?:string){editNode();parentId.value=parent||''}
function saveNode(){const name=nodeName.value.trim();if(!name||name.includes('/')||name.length>200)return ElMessage.warning('请输入 1–200 字名称，不能包含 /');if(nodes.value.some(n=>n.id!==nodeId.value&&n.parent_id===parentId.value&&n.name===name))return ElMessage.warning('同一上级下已有这个名称');const n=nodes.value.find(n=>n.id===nodeId.value);if(n)n.name=name;else nodes.value.push({id:'own:'+crypto.randomUUID(),name,parent_id:parentId.value});mark();nodeDialog.value=false}
function moveUnit(unit:CrmUnit,parent:string){const n=nodes.value.find(n=>n.id===unit.id);if(!n||!n.parent_id)return ElMessage.warning('公司根节点不能移为部门');let cursor=parent;const seen=new Set<string>();while(cursor){if(cursor===n.id||seen.has(cursor))return ElMessage.warning('不能将节点移入自己的下级');seen.add(cursor);cursor=nodes.value.find(n=>n.id===cursor)?.parent_id||''}if(nodes.value.some(o=>o.id!==n.id&&o.parent_id===parent&&o.name===n.name))return ElMessage.warning('目标上级下已有同名部门');n.parent_id=parent;mark()}
function deleteUnit(unit:CrmUnit){if(nodes.value.some(n=>n.parent_id===unit.id)||members.value.some(p=>p.node_id===unit.id))return ElMessage.warning('只能删除没有子节点、没有人员的空节点');if(data.value){data.value.nodes=nodes.value.filter(n=>n.id!==unit.id);mark()}}
function movePerson(person:CrmPerson,target:string){const p=members.value.find(p=>p.username===person.id);if(p&&nodes.value.some(n=>n.id===target)){p.node_id=target;mark()}}
function editPerson(person:CrmPerson){personId.value=person.id;targetId.value=person.unit_id;personDialog.value=true}
function savePerson(){const p=people.value.find(p=>p.id===personId.value);if(!p||!targetId.value)return ElMessage.warning('请选择目标公司或部门');movePerson(p,targetId.value);personDialog.value=false}
async function save(){if(!data.value||busy.value)return;busy.value=true;try{data.value=await saveInternalOrganization({revision:data.value.revision,nodes:nodes.value,assignments:Object.fromEntries(members.value.map(p=>[p.username,p.node_id]))});mark(false);emit('changed');ElMessage.success(`组织已保存，${data.value.updated_members||0} 位人员归属已同步`)}catch(e){ElMessage.error(e instanceof Error?e.message:'保存失败，草稿已保留')}finally{busy.value=false}}
onMounted(load)
</script>
<template>
<section v-loading="busy" class="internal-org-canvas">
 <div class="ioc-actions"><div><strong>正式账号组织架构</strong><p>两处入口共用数据 · 先选公司，再逐层调整部门与人员；支持多级结构、折叠、拖动和自动排版。</p></div><el-button :disabled="!data||busy" @click="addNode()">新增公司</el-button><el-button type="primary" :disabled="!dirty||busy" @click="save">保存组织调整{{dirty?'（未保存）':''}}</el-button></div>
 <el-alert type="info" :closable="false" title="仅更新公司与部门，不修改账号、工号、岗位、角色或授权。按部门/公司授权的数据范围会随真实归属变化。"/>
 <OrganizationEditor v-if="data" :units="units" :people="people" internal :read-only="busy" @add-unit="addNode" @edit-unit="editNode" @move-unit="moveUnit" @delete-unit="deleteUnit" @move-person="movePerson" @edit-person="editPerson"/>
 <el-button v-else-if="!busy" @click="load">重试加载</el-button>
 <el-dialog v-model="nodeDialog" :title="nodeId?'编辑组织节点':parentId?'新增下级部门':'新增公司'" width="min(500px,94vw)" append-to-body><p v-if="parentId">上级：{{path(parentId)}}</p><el-input v-model="nodeName" aria-label="组织节点名称" maxlength="200" placeholder="填写公司或部门名称" @keyup.enter="saveNode"/><template #footer><el-button @click="nodeDialog=false">取消</el-button><el-button type="primary" @click="saveNode">加入草稿</el-button></template></el-dialog>
 <el-dialog v-model="personDialog" title="匹配人员归属" width="min(620px,94vw)" append-to-body><p>{{members.find(p=>p.username===personId)?.name}} · {{personId}}（账号保持不变）</p><el-select v-model="targetId" filterable placeholder="选择公司或部门" aria-label="人员目标组织" style="width:100%"><el-option v-for="n in nodes" :key="n.id" :value="n.id" :label="path(n.id)"/></el-select><template #footer><el-button @click="personDialog=false">取消</el-button><el-button type="primary" @click="savePerson">加入草稿</el-button></template></el-dialog>
</section>
</template>
<style scoped>.ioc-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.ioc-actions>div{flex:1;min-width:240px}.ioc-actions p{font-size:12px;color:#6d819a;margin:6px 0}.internal-org-canvas>.el-alert{margin-bottom:10px}.internal-org-canvas :deep(.oe-stage){height:clamp(340px,52vh,640px)}</style>
