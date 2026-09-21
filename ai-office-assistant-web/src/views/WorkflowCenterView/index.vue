<script setup lang="ts">
import { ref } from 'vue'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'

const loading = ref(true)
const failed = ref(false)
// FastGPT 以根路径对外服务（同域根级命名空间，办公助手代理注入单点登录），
// 这样其客户端路由与 query 参数（appId、pane）全部保真，不再被子路径破坏。
// 入口沿用原先的 Agent 工作台（应用/工作流管理），点击应用即可编辑或对话。
// 使用 /zh-CN 语言前缀让 FastGPT 默认以简体中文渲染（SSR locale=zh-CN），
// 其内部导航会自动保持 /zh-CN 前缀。
const workflowUrl = '/zh-CN/dashboard/agent'

function reload() {
  loading.value = true
  failed.value = false
  const frame = document.querySelector<HTMLIFrameElement>('.workflow-center__frame')
  if (frame) frame.src = workflowUrl
}

function onLoad() {
  loading.value = false
}

function onError() {
  loading.value = false
  failed.value = true
}
</script>

<template>
  <section class="workflow-center">
    <header class="workflow-center__header">
      <div class="workflow-center__actions">
        <button type="button" @click="reload"><el-icon><Refresh /></el-icon> 刷新工作台</button>
        <a :href="workflowUrl" target="_blank" rel="noopener"><el-icon><VideoPlay /></el-icon> 新窗口打开</a>
      </div>
    </header>

    <div class="workflow-center__canvas">
      <div v-if="loading" class="workflow-center__state">正在启动工作流中心…</div>
      <div v-else-if="failed" class="workflow-center__state workflow-center__state--error">
        工作流中心暂不可用，请稍后刷新。
      </div>
      <iframe
        class="workflow-center__frame"
        :class="{ 'workflow-center__frame--ready': !loading }"
        :src="workflowUrl"
        title="承希工作流中心"
        @load="onLoad"
        @error="onError"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.workflow-center { min-height: calc(100vh - 94px); padding: 14px 18px 18px; background: #f4f8ff; }
.workflow-center__header { display:flex; justify-content:space-between; align-items:center; gap:24px; height:48px; margin-bottom:10px; padding:0 4px; }
.workflow-center__header p { display:none; }
.workflow-center__header h1 { margin:0; color:#102d61; font-size:21px; letter-spacing:.2px; }
.workflow-center__actions { display:flex; gap:10px; flex-shrink:0; }
.workflow-center__actions a, .workflow-center__actions button { display:inline-flex; gap:7px; align-items:center; border:1px solid #bfd1ee; border-radius:9px; padding:8px 12px; color:#1f58ab; background:#fff; font:inherit; font-size:13px; font-weight:650; cursor:pointer; text-decoration:none; }
.workflow-center__actions a { background:#2057aa; border-color:#2057aa; color:#fff; }
.workflow-center__canvas { position:relative; overflow:hidden; min-height:calc(100vh - 170px); height:calc(100vh - 170px); border:1px solid #cbdcf3; border-radius:12px; background:#fff; box-shadow:0 8px 24px rgba(31, 74, 143, .07); }
.workflow-center__frame { width:100%; height:100%; min-height:calc(100vh - 170px); border:0; opacity:0; transition:opacity .2s; }
.workflow-center__frame--ready { opacity:1; }
.workflow-center__state { position:absolute; inset:0; z-index:1; display:flex; align-items:center; justify-content:center; color:#55719e; font-weight:650; background:linear-gradient(135deg,#f7fbff,#eef5ff); }
.workflow-center__state--error { color:#b54747; }
@media (max-width: 900px) { .workflow-center { padding:10px; } .workflow-center__header { height:auto; align-items:flex-start; flex-direction:column; } .workflow-center__actions { width:100%; } .workflow-center__canvas,.workflow-center__frame { min-height:calc(100vh - 220px); height:calc(100vh - 220px); } }
</style>
