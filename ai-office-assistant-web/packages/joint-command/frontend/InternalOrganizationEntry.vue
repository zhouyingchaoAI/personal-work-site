<script setup lang="ts">
import { ref } from 'vue'
import { authState } from '../../../src/services/authSession'
import InternalOrganizationCanvas from './InternalOrganizationCanvas.vue'
const emit=defineEmits<{changed:[]}>()
const visible=ref(false), dirty=ref(false)
</script>
<template>
<el-button v-if="authState.user?.is_superadmin" type="primary" plain @click="visible=true">调整我方组织画布</el-button>
<el-dialog v-model="visible" title="调整我方组织架构" class="internal-organization-dialog" width="96vw" top="2vh" append-to-body :close-on-click-modal="false">
 <InternalOrganizationCanvas v-if="visible||dirty" @dirty="dirty=$event" @changed="emit('changed')"/>
 <template #footer><span v-if="dirty" class="draft-note">尚未保存；关闭弹框保留本页草稿，离开页面会丢弃。</span><el-button @click="visible=false">关闭画布</el-button></template>
</el-dialog>
</template>
<style scoped>.draft-note{color:#a36c1c;font-size:12px;margin-right:12px}</style>
<style>
.internal-organization-dialog.el-dialog{height:96dvh;max-height:96dvh;display:flex;flex-direction:column;overflow:hidden;margin-bottom:0;box-sizing:border-box}
.internal-organization-dialog>.el-dialog__header,.internal-organization-dialog>.el-dialog__footer{flex:none}
.internal-organization-dialog>.el-dialog__body{flex:1;min-height:0;overflow:auto;display:flex}
.internal-organization-dialog .internal-org-canvas{flex:1;min-width:0;min-height:560px;display:flex;flex-direction:column}
.internal-organization-dialog .ioc-actions,.internal-organization-dialog .internal-org-canvas>.el-alert{flex:none}
.internal-organization-dialog .org-editor{flex:1;min-height:0;display:flex;flex-direction:column}
.internal-organization-dialog .oe-toolbar,.internal-organization-dialog .oe-properties{flex:none;max-height:80px;overflow:auto;padding:6px 10px;min-height:0}
.internal-organization-dialog .oe-toolbar .el-select{width:220px}
.internal-organization-dialog .oe-help{flex:none;margin:6px 0}
.internal-organization-dialog .internal-org-canvas .oe-stage{flex:1;min-height:120px;height:auto}
.internal-organization-dialog .oe-people{flex:none;height:190px;box-sizing:border-box;display:flex;flex-direction:column;padding:6px 10px;overflow:hidden}
.internal-organization-dialog .oe-people header{flex:none;padding:4px;gap:6px}
.internal-organization-dialog .oe-people p{flex:none;margin:4px 0}
.internal-organization-dialog .oe-people>div{flex:1;min-height:0;max-height:none;overflow:auto;align-content:flex-start}
@media(max-width:650px){.internal-organization-dialog .internal-org-canvas{min-height:720px}.internal-organization-dialog .oe-toolbar .el-select{width:160px}.internal-organization-dialog .oe-people{height:240px}.internal-organization-dialog .oe-people .el-input{width:180px}}
</style>
