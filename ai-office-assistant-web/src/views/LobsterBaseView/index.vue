<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { openclawPlatformUrl, openclawSso } from '../../services/personalWorkApi'
import './index.scss'

const frameSrc = ref('about:blank')

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '龙虾平台单点登录失败'
}

function normalizeOpenClawUrl(url: string) {
  const value = openclawPlatformUrl(url || '/openclaw/')
  const parsed = new URL(value, window.location.href)
  // OpenClaw 网页端依赖同源 cookie，嵌入页必须走当前站点的 /openclaw 代理路径。
  if (parsed.pathname.includes('/openclaw')) {
    const path = parsed.pathname.endsWith('/') ? parsed.pathname : `${parsed.pathname}/`
    return `${path}${parsed.search}`
  }
  return value.replace(/\/$/, '/')
}

async function loadOpenClawBase() {
  try {
    const result = await openclawSso()
    if (!result.ok || !result.token) throw new Error(result.error || '龙虾平台未返回登录凭据')
    const url = normalizeOpenClawUrl(result.url || '/openclaw/')
    const token = encodeURIComponent(result.token)
    const sep = url.includes('?') ? '&' : '?'
    localStorage.setItem('openclaw_token', result.token)
    document.cookie = `openclaw_token=${token}; path=/; SameSite=Lax`
    frameSrc.value = `${url}${sep}embed=1&from=personal-office-assistant&ts=${Date.now()}#token=${token}`
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(() => {
  loadOpenClawBase()
})
</script>

<template>
  <section class="workspace-main lobster-main">
    <iframe class="lobster-frame" title="龙虾基地" :src="frameSrc"></iframe>
  </section>
</template>
