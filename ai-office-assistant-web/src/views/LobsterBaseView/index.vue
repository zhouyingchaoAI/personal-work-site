<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, Refresh, Ship } from '@element-plus/icons-vue'
import { openclawPlatformUrl, openclawSso } from '../../services/personalWorkApi'
import './index.scss'

const statusText = ref('进入页面后自动登录龙虾平台...')
const statusTone = ref<'normal' | 'ok' | 'error'>('normal')
const frameSrc = ref('about:blank')
const openLink = ref(openclawPlatformUrl('/openclaw/'))
const loading = ref(false)
let loaded = false
let loadSeq = 0

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '龙虾平台单点登录失败'
}

function normalizeOpenClawUrl(url: string) {
  return openclawPlatformUrl(url || '/openclaw/').replace(/\/$/, '/')
}

async function loadOpenClawBase(force = false) {
  if (loaded && !force) return
  const seq = ++loadSeq
  loading.value = true
  statusTone.value = 'normal'
  statusText.value = '正在使用办公助手账号登录龙虾平台...'
  try {
    const result = await openclawSso()
    if (!result.ok || !result.token) throw new Error(result.error || '龙虾平台未返回登录凭据')
    if (seq !== loadSeq) return
    const url = normalizeOpenClawUrl(result.url || '/openclaw/')
    const token = encodeURIComponent(result.token)
    const sep = url.includes('?') ? '&' : '?'
    localStorage.setItem('openclaw_token', result.token)
    document.cookie = `openclaw_token=${token}; path=/; SameSite=Lax`
    if (force) {
      frameSrc.value = 'about:blank'
      await new Promise((resolve) => window.setTimeout(resolve, 30))
      if (seq !== loadSeq) return
    }
    frameSrc.value = `${url}${sep}embed=1&from=personal-office-assistant&ts=${Date.now()}#token=${token}`
    openLink.value = `${url}#token=${token}`
    loaded = true
    statusTone.value = 'ok'
    statusText.value = '已使用当前办公助手账号进入龙虾基地。'
  } catch (error) {
    if (seq !== loadSeq) return
    statusTone.value = 'error'
    statusText.value = errorMessage(error)
    ElMessage.error(statusText.value)
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

onMounted(() => {
  loadOpenClawBase()
})
</script>

<template>
  <section class="workspace-main lobster-main">
    <section class="lobster-panel">
      <header class="lobster-toolbar">
        <div class="lobster-title">
          <span aria-hidden="true"><el-icon><Ship /></el-icon></span>
          <div>
            <h2>龙虾基地</h2>
            <p>OpenClaw 平台</p>
          </div>
        </div>
        <div class="lobster-actions">
          <button type="button" :disabled="loading" @click="loadOpenClawBase(true)">
            <el-icon><Refresh /></el-icon>
            {{ loading ? '登录中...' : '刷新' }}
          </button>
          <a :href="openLink" target="_blank" rel="noopener">
            <el-icon><Link /></el-icon>
            新窗口打开
          </a>
        </div>
      </header>

      <div :class="['lobster-status', statusTone]">{{ statusText }}</div>
      <iframe class="lobster-frame" title="龙虾基地" :src="frameSrc"></iframe>
    </section>
  </section>
</template>
