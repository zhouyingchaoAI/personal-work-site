<script setup lang="ts">
import QuickWorkOrder from './components/QuickWorkOrder.vue'
import { defineAsyncComponent, watch } from 'vue'
import { workOrderPopup } from './services/workOrderPopup'
import { authState } from './services/authSession'
const WorkOrderView = defineAsyncComponent(() => import('./views/WorkOrderView/index.vue'))
watch(() => authState.user?.username, () => { workOrderPopup.value = null })
</script>

<template>
  <router-view />
  <QuickWorkOrder />
  <el-dialog :model-value="!!workOrderPopup" title="我的工单 · 内容与处理进度" width="min(1100px, 96vw)" append-to-body destroy-on-close :close-on-click-modal="false" @close="workOrderPopup = null">
    <div style="max-height: 75vh; overflow: auto">
      <WorkOrderView v-if="workOrderPopup" embedded :ticket-id="workOrderPopup.ticketId" />
    </div>
  </el-dialog>
</template>
