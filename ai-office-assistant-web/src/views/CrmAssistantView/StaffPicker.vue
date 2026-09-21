<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { crmStaff, type CrmStaff } from '../../services/personalWorkApi'
const props=defineProps<{ modelValue?: string }>()
const emit=defineEmits<{ 'update:modelValue':[value:string] }>()
const staff=ref<CrmStaff[]>([])
const selected=computed(()=>staff.value.find(p=>p.member_key===props.modelValue))
const text = (value?: string) => value?.trim() || ''
const organization = (p: CrmStaff) => [text(p.company), text(p.department)].filter(Boolean).join(' / ')
const identifier = (p: CrmStaff) => text(p.member_key) !== text(p.name) ? text(p.member_key) : ''
const label = (p: CrmStaff) => [text(p.name), text(p.title), organization(p), identifier(p)].filter(Boolean).join(' · ')
const selectedDetails = computed(() => selected.value ? [organization(selected.value), text(selected.value.title)].filter(Boolean).join(' · ') : '')
onMounted(()=>load(true))
async function load(open:boolean){if(open)try{staff.value=(await crmStaff()).staff}catch{ElMessage.error('我方人员加载失败，请重试')}}
</script>
<template>
  <div class="staff-picker">
    <el-select :model-value="modelValue" @update:model-value="(v: string) => emit('update:modelValue',v)" @visible-change="load" filterable allow-create default-first-option clearable placeholder="搜索姓名、工号、部门或岗位" style="width:100%">
      <el-option v-for="p in staff" :key="p.id" :value="p.member_key" :label="label(p)" class="staff-picker-option">
        <div class="staff-picker-option__main"><strong>{{p.name}}</strong><span v-if="text(p.title)">{{text(p.title)}}</span><small v-if="identifier(p)" class="staff-picker-option__id">{{identifier(p)}}</small></div>
        <div v-if="organization(p)" class="staff-picker-option__organization">{{organization(p)}}</div>
      </el-option>
      <template #label="{ label: optionLabel }">{{selected?.name || optionLabel}}<span v-if="selected && identifier(selected)" class="staff-picker__key"> · {{identifier(selected)}}</span></template>
    </el-select>
    <div v-if="selectedDetails" class="staff-picker__details">{{selectedDetails}}</div>
  </div>
</template>

<style scoped>
.staff-picker { width: 100%; min-width: 0; }
.staff-picker-option { height: auto; min-height: 44px; padding: 10px 16px; line-height: 1.5; }
.staff-picker-option__main { display: flex; align-items: baseline; gap: 10px; }
.staff-picker-option__main strong { color: #263f5b; font-weight: 600; }
.staff-picker-option__main > span { color: #64748b; font-size: 12px; }
.staff-picker-option__id { margin-left: auto; color: #64748b; font-size: 12px; }
.staff-picker-option__organization { color: #64748b; font-size: 12px; margin-top: 3px; }
.staff-picker__key { color: #64748b; font-size: 12px; }
.staff-picker__details { margin-top: 6px; color: #64748b; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
</style>
