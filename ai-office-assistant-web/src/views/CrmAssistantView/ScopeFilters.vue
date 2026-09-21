<script setup lang="ts">
defineProps<{ regions: string[]; departments: string[]; members: { value: string; label: string }[]; regionOnly?: boolean }>()
const region = defineModel<string>('region', { required: true })
const department = defineModel<string>('department', { required: true })
const member = defineModel<string>('member', { required: true })
</script>

<template>
  <el-select v-model="region" clearable placeholder="全部经营区域" aria-label="经营区域" style="width:160px"><el-option v-for="area in [...regions, '未分区']" :key="area" :label="area" :value="area" /></el-select>
  <template v-if="!regionOnly">
    <el-select v-model="department" clearable placeholder="全部责任部门" aria-label="责任部门" style="width:180px"><el-option v-for="d in departments" :key="d" :value="d" :label="d" /></el-select>
    <el-select v-model="member" clearable filterable placeholder="全部责任人员" aria-label="责任人员" style="width:230px"><el-option v-for="p in members" :key="p.value" :value="p.value" :label="p.label" /></el-select>
  </template>
</template>
