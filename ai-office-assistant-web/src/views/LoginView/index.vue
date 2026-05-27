<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Calendar, ChatDotRound, Lock, Reading, UserFilled } from '@element-plus/icons-vue'
import loginBackground from '../../assets/login-background.jpeg'
import chencyLogo from '../../assets/logo.png'
import { loginSession } from '../../services/authSession'
import './index.scss'

interface LoginForm {
  username: string
  password: string
  remember: boolean
}

const form = reactive<LoginForm>({
  username: '',
  password: '',
  remember: false,
})
const rememberedUsernameKey = 'ai-office-assistant.username'
const rememberedPasswordKey = 'ai-office-assistant.password'
const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const route = useRoute()
const router = useRouter()
const loginTitle = '承希智能办公助手'
const loginSubtitle = 'AI 赋能办公 · 协同更高效'
const displayedTitle = ref('')
const displayedSubtitle = ref('')
const activeTyping = ref<'title' | 'subtitle' | ''>('title')
const typingTimers: number[] = []
const rules: FormRules<LoginForm> = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(() => {
  form.username = localStorage.getItem(rememberedUsernameKey) || ''
  form.password = localStorage.getItem(rememberedPasswordKey) || ''
  form.remember = Boolean(form.username || form.password)
  startLoginCopyTyping()
})

onBeforeUnmount(() => {
  typingTimers.forEach((timer) => window.clearTimeout(timer))
})

async function handleLogin() {
  if (loading.value) return
  form.username = form.username.trim()
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await loginSession(form.username, form.password)
    if (form.remember) {
      localStorage.setItem(rememberedUsernameKey, form.username)
      localStorage.setItem(rememberedPasswordKey, form.password)
    } else {
      localStorage.removeItem(rememberedUsernameKey)
      localStorage.removeItem(rememberedPasswordKey)
    }
    await router.replace(String(route.query.redirect || '/workspace/weekly'))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}

function handleForgotPassword() {
  ElMessage.info('请联系管理员重置密码')
}

function handleLoginCardMouseMove(event: MouseEvent) {
  const card = event.currentTarget as HTMLElement
  const rect = card.getBoundingClientRect()
  // 使用卡片内相对坐标驱动边缘与内层光晕。
  card.style.setProperty('--mouse-x', `${event.clientX - rect.left}px`)
  card.style.setProperty('--mouse-y', `${event.clientY - rect.top}px`)
}

function startLoginCopyTyping() {
  // 系统减少动态效果时直接展示完整文案。
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    displayedTitle.value = loginTitle
    displayedSubtitle.value = loginSubtitle
    activeTyping.value = ''
    return
  }

  displayedTitle.value = ''
  displayedSubtitle.value = ''
  activeTyping.value = 'title'
  typeLoginCopy(loginTitle, displayedTitle, 120, () => {
    activeTyping.value = 'subtitle'
    typeLoginCopy(loginSubtitle, displayedSubtitle, 70, () => {
      activeTyping.value = ''
    }, 240)
  })
}

// 逐字更新目标文案，让光标跟随真实字符位置。
function typeLoginCopy(text: string, target: Ref<string>, interval: number, done: () => void, delay = 0) {
  let index = 0
  const tick = () => {
    index += 1
    target.value = text.slice(0, index)
    if (index < text.length) {
      typingTimers.push(window.setTimeout(tick, interval))
      return
    }
    done()
  }

  typingTimers.push(window.setTimeout(tick, delay))
}
</script>

<template>
  <main class="login-page">
    <img class="login-background" :src="loginBackground" alt="" aria-hidden="true" />
    <div class="login-feature-cards" aria-hidden="true">
      <div class="login-feature-stage">
        <div class="login-feature-card login-feature-card--qa">
          <span class="login-feature-icon"><el-icon><ChatDotRound /></el-icon></span>
          <span>智能问答</span>
        </div>
        <div class="login-feature-card login-feature-card--schedule">
          <span class="login-feature-icon"><el-icon><Calendar /></el-icon></span>
          <span>日程任务</span>
        </div>
        <div class="login-feature-card login-feature-card--knowledge">
          <span class="login-feature-icon"><el-icon><Reading /></el-icon></span>
          <span>知识助手</span>
        </div>
      </div>
    </div>
    <div class="login-canvas">
      <section class="login-brand" aria-label="平台介绍">
        <img class="login-logo" :src="chencyLogo" alt="CHENCY" />
        <div class="login-copy">
          <h1 :aria-label="loginTitle">
            <span :class="['login-typewriter', { 'is-typing': activeTyping === 'title' }]">{{ displayedTitle }}</span>
          </h1>
          <p :aria-label="loginSubtitle">
            <span :class="['login-typewriter', { 'is-typing': activeTyping === 'subtitle' }]">{{ displayedSubtitle }}</span>
          </p>
        </div>
      </section>

      <section class="login-card" aria-label="登录" @mousemove="handleLoginCardMouseMove">
        <div class="mouse-glow-inner" aria-hidden="true"></div>
        <div class="top-highlight" aria-hidden="true"></div>
        <div class="border-mask" aria-hidden="true">
          <div class="mouse-glow-border"></div>
        </div>
        <header class="login-title">
          <h2>欢迎登录</h2>
        </header>

        <el-form
          ref="loginFormRef"
          class="login-form"
          :model="form"
          :rules="rules"
          label-position="top"
          hide-required-asterisk
          @submit.prevent="handleLogin"
        >
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="form.username"
              class="login-input"
              autocomplete="username"
              clearable
              placeholder="请输入账号"
            >
              <template #prefix>
                <el-icon><UserFilled /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              class="login-input"
              autocomplete="current-password"
              type="password"
              show-password
              placeholder="请输入密码"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <div class="login-options">
            <el-checkbox v-model="form.remember">记住我</el-checkbox>
            <button class="text-button" type="button" @click="handleForgotPassword">忘记密码？</button>
          </div>

          <el-button class="login-submit" type="primary" native-type="submit" :loading="loading">登录</el-button>
        </el-form>
      </section>
    </div>
  </main>
</template>
