<script setup lang="ts">
import { computed, ref } from 'vue'
import catalog from '../../../../backend/crm_org_catalog.json'
const props=defineProps<{company?:string;department?:string;position?:string}>()
const emit=defineEmits<{'update:company':[value:string];'update:department':[value:string];'update:position':[value:string]}>()
const departments=computed(()=>catalog.companies.find(c=>c.name===props.company)?.departments||[])
const custom=ref(false)
interface DeptNode { value:string; label:string; children:DeptNode[] }
const departmentTree=computed(()=>{
 const roots:DeptNode[]=[], map=new Map<string,DeptNode>()
 for(const path of departments.value){
  let parent:DeptNode|undefined
  const parts=path.split(' / ')
  parts.forEach((label,i)=>{const value=parts.slice(0,i+1).join(' / ');let node=map.get(value)
   if(!node){node={value,label,children:[]};map.set(value,node);if(parent)parent.children.push(node);else roots.push(node)}
   parent=node
  })
 }
 if(props.department&&!map.has(props.department))roots.push({value:props.department,label:props.department,children:[]})
 return roots
})
function changeCompany(value:string){emit('update:company',value);if(value!==props.company)emit('update:department','')}
</script>
<template>
 <el-form-item label="我方公司（选填）"><el-select :model-value="company" filterable allow-create clearable placeholder="选择所属公司，可补充其他公司" style="width:100%" @update:model-value="changeCompany"><el-option v-for="c in catalog.companies" :key="c.name" :value="c.name" :label="c.name"/></el-select></el-form-item>
 <el-form-item label="我方部门（选填）">
  <el-tree-select v-if="!custom" :model-value="department" :data="departmentTree" node-key="value" check-strictly filterable clearable :disabled="!company" :render-after-expand="false" placeholder="逐级展开或搜索部门，可选择中心、部门或办事处" style="width:100%" @update:model-value="emit('update:department',$event || '')" />
  <el-input v-else :model-value="department" maxlength="120" placeholder="填写实际部门，上下级用 / 分隔" @update:model-value="emit('update:department',$event)" />
  <div class="department-help"><span>{{company ? (department || '可选择任意层级，无需全部展开') : '请先选择所属公司'}}</span><el-button link type="primary" @click="custom=!custom">{{ custom ? '返回组织目录' : '目录中没有？补充部门' }}</el-button></div>
 </el-form-item>
 <el-form-item label="我方岗位（选填）"><el-select :model-value="position" filterable allow-create clearable placeholder="选择常用岗位，或填写实际岗位" style="width:100%" @update:model-value="emit('update:position',$event)"><el-option v-for="p in catalog.positions" :key="p" :value="p" :label="p"/></el-select></el-form-item>
</template>

<style scoped>.department-help{width:100%;display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:12px;color:#7c8da5;line-height:1.6;margin-top:5px}.department-help span{overflow-wrap:anywhere}</style>
