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
  // 统一使用绝对地址（OpenClaw 独立域名，来自后端 OPENCLAW_PLATFORM_PUBLIC_URL）。
  // 登录态经 #token= 传递，OpenClaw 的 initialToken() 会把它写进自己源下的
  // localStorage/cookie，不依赖第三方 cookie，任何入口域名下都可用。
  const value = openclawPlatformUrl(url || '/openclaw/')
  const parsed = new URL(value, window.location.href)
  if (!parsed.pathname.endsWith('/')) parsed.pathname += '/'
  return parsed.href
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
