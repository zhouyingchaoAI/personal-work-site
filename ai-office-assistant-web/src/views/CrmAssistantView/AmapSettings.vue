<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { crmAmapSettings, crmSaveAmapSettings } from '../../services/personalWorkApi'
defineProps<{ canEdit: boolean }>()
const key = ref(''), secret = ref(''), enabled = ref(false), version = ref(0)
const hasSecret = ref(false), loaded = ref(false), saving = ref(false)
onMounted(async () => {
  try {
    const data = await crmAmapSettings()
    key.value = data.key; enabled.value = data.enabled; version.value = data.version
    hasSecret.value = data.has_security_code; loaded.value = true
  } catch { ElMessage.error('高德配置读取失败') }
})
async function save() {
  saving.value = true
  try {
    const result = await crmSaveAmapSettings({ key: key.value, security_code: secret.value, enabled: enabled.value, version: version.value })
    version.value = result.version; hasSecret.value = result.has_security_code; secret.value = ''
    window.dispatchEvent(new Event('crm-amap-settings-changed'))
    ElMessage.success('地图配置已保存，底图正在更新')
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '保存失败') }
  finally { saving.value = false }
}
</script>
<template>
  <section class="amap-settings">
    <h3>高德地图底图</h3>
    <p>使用高德开放平台「Web端（JS API）」凭据；安全密钥仅存服务器，不会返回浏览器。未配置或加载失败时显示备用地图。</p>
    <el-form v-if="canEdit" label-width="110px" :disabled="!loaded || saving">
      <el-form-item label="启用高德"><el-switch v-model="enabled" /></el-form-item>
      <el-form-item label="Web 端 Key"><el-input v-model="key" autocomplete="off" placeholder="高德 JS API Key" /></el-form-item>
      <el-form-item label="安全密钥"><el-input v-model="secret" type="password" show-password autocomplete="new-password" :placeholder="hasSecret ? '已配置，留空保留原密钥' : 'securityJsCode'" /></el-form-item>
      <el-form-item><el-button type="primary" :loading="saving" @click="save">保存高德配置</el-button></el-form-item>
    </el-form>
    <p v-else>{{ enabled && hasSecret ? '已启用高德地图' : '尚未启用，请联系管理员配置' }}</p>
  </section>
</template>
<style scoped>
.amap-settings { margin-top:20px;padding:16px;border:1px solid var(--el-border-color);border-radius:8px; }
p {color:var(--el-text-color-secondary);font-size:13px;line-height:1.6;}
</style>
