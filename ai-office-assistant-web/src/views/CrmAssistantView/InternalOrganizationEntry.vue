<script setup lang="ts">
import { ref } from 'vue'
import { authState } from '../../services/authSession'
import InternalOrganizationCanvas from './InternalOrganizationCanvas.vue'
const emit=defineEmits<{changed:[]}>()
const visible=ref(false), dirty=ref(false)
</script>
<template>
<el-button v-if="authState.user?.is_superadmin" type="primary" plain @click="visible=true">调整我方组织画布</el-button>
<el-dialog v-model="visible" title="调整我方组织架构" width="96vw" top="2vh" append-to-body :close-on-click-modal="false">
 <InternalOrganizationCanvas v-if="visible||dirty" @dirty="dirty=$event" @changed="emit('changed')"/>
 <template #footer><span v-if="dirty" class="draft-note">尚未保存；关闭弹框保留本页草稿，离开页面会丢弃。</span><el-button @click="visible=false">关闭画布</el-button></template>
</el-dialog>
</template>
<style scoped>.draft-note{color:#a36c1c;font-size:12px;margin-right:12px}</style>
