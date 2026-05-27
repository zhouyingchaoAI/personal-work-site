<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Calendar, ChatDotRound, CoffeeCup, Document, Message, Plus, Setting } from '@element-plus/icons-vue'
import AssistantChat from '../../components/AssistantChat/index.vue'
import AppLayout from '../../layout/AppLayout/index.vue'
import DiaryView from '../DiaryView/index.vue'
import ForumView from '../ForumView/index.vue'
import LobsterBaseView from '../LobsterBaseView/index.vue'
import MailAssistantView from '../MailAssistantView/index.vue'
import NewsView from '../NewsView/index.vue'
import SettingsView from '../SettingsView/index.vue'
import TripReportView from '../TripReportView/index.vue'
import WeeklyReportView from '../WeeklyReportView/index.vue'
import { authState, logoutSession } from '../../services/authSession'
import { isMenuId, visibleMenuItems, type MenuId } from '../../layout/menu'
import { agentChat, type AgentMessage } from '../../services/personalWorkApi'
import benbenImage from '../../assets/benben.png'
import homeHeroBanner from '../../assets/home-hero-banner.png'
import assistantLogo from '../../assets/logo_1.png'
import {
  focusMomentImage,
  homeAssistantActions,
  homeFeatures,
  homeRecords,
  homeTodos,
  promptQuestions,
} from '../../data/pageData'
import './index.scss'

const route = useRoute()
const router = useRouter()
const focusMinutes = ref(25)
const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantLoading = ref(false)
const currentTime = ref(new Date())
const todoItems = ref(homeTodos.map((todo) => ({ ...todo })))
const assistantQuickActions = homeAssistantActions.map((item) => item.label)
const assistantMessages = ref<AgentMessage[]>([
  { role: 'assistant', content: '你好，我是犇犇。你可以告诉我想处理的办公事项，我会帮你整理思路或建议下一步。' },
])
const user = computed(() => authState.user)
const activeMenu = computed<MenuId>(() => {
  const menu = String(route.params.menu || 'weekly')
  return isMenuId(menu) ? menu : 'weekly'
})
const menuItems = computed(() => (user.value ? visibleMenuItems(user.value) : []))
const pendingTodoCount = computed(() => todoItems.value.filter((todo) => !todo.checked).length)
const homeGreeting = computed(() => greetingByHour(currentTime.value.getHours()))
let greetingTimer: number | undefined

onMounted(() => {
  // 每分钟刷新一次，避免页面长时间停留后问候语过期。
  greetingTimer = window.setInterval(() => {
    currentTime.value = new Date()
  }, 60 * 1000)
})

onBeforeUnmount(() => {
  if (greetingTimer) window.clearInterval(greetingTimer)
})

function selectMenu(menu: string) {
  if (isMenuId(menu)) router.push(`/workspace/${menu}`)
}

function greetingByHour(hour: number) {
  if (hour < 6) return '夜深了，注意休息'
  if (hour < 9) return '早上好，欢迎回来'
  if (hour < 12) return '上午好，欢迎回来'
  if (hour < 14) return '中午好，欢迎回来'
  if (hour < 18) return '下午好，欢迎回来'
  if (hour < 22) return '晚上好，欢迎回来'
  return '夜深了，欢迎回来'
}

function updateSpotlightPosition(event: MouseEvent) {
  const card = event.currentTarget as HTMLElement
  const rect = card.getBoundingClientRect()
  card.style.setProperty('--mouse-x', `${event.clientX - rect.left}px`)
  card.style.setProperty('--mouse-y', `${event.clientY - rect.top}px`)
}

function selectAction(label: string) {
  ElMessage.success(`已选择：${label}`)
}

async function sendAssistantMessage(text = assistantInput.value) {
  const content = text.trim()
  if (!content) {
    ElMessage.warning('请输入要问犇犇的内容')
    return
  }
  if (assistantLoading.value) return
  assistantOpen.value = true
  assistantMessages.value.push({ role: 'user', content })
  assistantInput.value = ''
  assistantLoading.value = true
  try {
    const result = await agentChat('dashboard', assistantMessages.value.slice(-8))
    if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
    assistantMessages.value.push({ role: 'assistant', content: result.reply || '我看到了，当前没有新的补充。' })
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
  } finally {
    assistantLoading.value = false
  }
}

async function handleLogout() {
  await logoutSession()
  await router.replace('/login')
}
</script>

<template>
  <AppLayout
    v-if="user"
    :active-menu="activeMenu"
    :menu-items="menuItems"
    :user="user"
    @update:active-menu="selectMenu"
    @logout="handleLogout"
  >
    <WeeklyReportView v-if="activeMenu === 'weekly'" />
    <TripReportView v-else-if="activeMenu === 'trip'" />
    <DiaryView v-else-if="activeMenu === 'diary'" />
    <ForumView v-else-if="activeMenu === 'forum'" />
    <NewsView v-else-if="activeMenu === 'news'" />
    <MailAssistantView v-else-if="activeMenu === 'mailassistant'" />
    <LobsterBaseView v-else-if="activeMenu === 'lobsterbase'" />
    <SettingsView
      v-else-if="['config', 'mailconfig', 'skills', 'usermanage'].includes(activeMenu)"
      :active-menu="activeMenu"
      @select-menu="selectMenu"
    />

    <section v-else-if="activeMenu === 'dashboard'" class="workspace-main home-dashboard">
      <section class="home-hero" aria-label="承希智能办公助手">
        <img :src="homeHeroBanner" alt="" aria-hidden="true" />
        <div class="home-hero__copy">
          <p>{{ homeGreeting }}</p>
          <h1>承希智能办公助手</h1>
          <span>AI 赋能办公 · 协同更高效</span>
          <!-- <button type="button" @click="selectAction('智能向导')">
            <el-icon><ChatDotRound /></el-icon>
            智能向导
            <el-icon><ArrowRight /></el-icon>
          </button> -->
        </div>
      </section>

      <section class="home-panel home-quick-panel" aria-label="快捷功能">
        <div class="home-panel-title">
          <span><el-icon><Setting /></el-icon></span>
          <h2>快捷功能</h2>
        </div>
        <div class="home-feature-grid">
          <button
            v-for="item in homeFeatures"
            :key="item.id"
            :class="['home-feature-card', `home-feature-card--${item.tone}`]"
            type="button"
            @mousemove="updateSpotlightPosition"
            @click="selectMenu(item.menuId)"
          >
            <img :src="item.image" alt="" aria-hidden="true" />
            <strong>{{ item.label }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </div>
      </section>

      <section class="home-panel home-record-panel" aria-label="最近编辑">
        <div class="home-panel-title home-panel-title--between">
          <span><el-icon><Document /></el-icon></span>
          <h2>最近编辑</h2>
          <button type="button" @click="selectAction('全部记录')">全部记录 <el-icon><ArrowRight /></el-icon></button>
        </div>
        <ul class="home-record-list">
          <li v-for="item in homeRecords" :key="item.id">
            <button type="button" @click="selectMenu(item.menuId)">
              <span :class="['home-record-icon', `home-record-icon--${item.tone}`]">
                <el-icon v-if="item.tone === 'mail'"><Message /></el-icon>
                <template v-else>{{ item.iconText }}</template>
              </span>
              <strong>{{ item.title }}</strong>
              <em :class="`home-record-tag--${item.tone}`">{{ item.tag }}</em>
              <time>{{ item.time }}</time>
            </button>
          </li>
        </ul>
      </section>
    </section>

    <section v-else class="workspace-main placeholder-main">
      <article class="panel placeholder-panel">
        <h3>{{ menuItems.find((item) => item.id === activeMenu)?.label }}</h3>
        <p>这个功能会接入个人办公助手现有能力，当前先保留入口。</p>
      </article>
    </section>

    <aside v-if="activeMenu === 'dashboard'" class="home-side-panel">
      <section class="home-panel home-todo-panel">
        <div class="home-side-title">
          <span><el-icon><Calendar /></el-icon></span>
          <h2>今日待办</h2>
          <button type="button" @click="selectAction('更多待办')">更多 <el-icon><ArrowRight /></el-icon></button>
        </div>
        <div class="home-todo-count">
          <strong>{{ pendingTodoCount }}</strong>
          <span>项待办</span>
        </div>
        <ul v-if="pendingTodoCount" class="home-todo-list">
          <li v-for="todo in todoItems" :key="todo.id" :class="{ checked: todo.checked }">
            <label class="home-todo-row">
              <span class="home-todo-check">
                <input v-model="todo.checked" type="checkbox" :aria-label="todo.title" />
                <span aria-hidden="true"></span>
              </span>
              <strong>{{ todo.title }}</strong>
              <time>{{ todo.time }}</time>
            </label>
          </li>
        </ul>
        <div v-else class="home-todo-empty">
          <div class="home-todo-empty__icon" aria-hidden="true">
            <el-icon><CoffeeCup /></el-icon>
          </div>
          <strong>暂无待办事项</strong>
          <p>太棒了！今天的工作都已处理完<br />喝杯咖啡休息一下吧~</p>
          <button type="button" @click="selectAction('新建待办')">
            <el-icon><Plus /></el-icon>
            新建待办
          </button>
        </div>
      </section>

      <section class="home-panel home-ai-panel">
        <div class="home-ai-title">
          <img :src="assistantLogo" alt="" aria-hidden="true" />
          <h2>犇犇 AI助手</h2>
          <span>在线</span>
        </div>
        <div class="home-ai-content">
          <div class="home-ai-bubble">
            <p>Hi，我是犇犇，</p>
            <p>可以帮你快速处理办公事项～</p>
          </div>
          <img class="home-ai-mascot" :src="benbenImage" alt="犇犇 AI助手" />
        </div>
        <button class="home-ai-primary" type="button" @click="assistantOpen = true">
          <el-icon><ChatDotRound /></el-icon>
          问问犇犇
        </button>
        <div class="home-ai-actions">
          <button
            v-for="item in homeAssistantActions"
            :key="item.id"
            type="button"
            @click="item.menuId ? selectMenu(item.menuId) : sendAssistantMessage(item.label)"
          >
            {{ item.label }}
          </button>
        </div>
      </section>
    </aside>

    <aside v-else-if="!['weekly', 'trip', 'diary', 'forum', 'news', 'mailassistant', 'lobsterbase', 'config', 'mailconfig', 'skills', 'usermanage'].includes(activeMenu)" class="assistant-panel">
      <section class="assistant-hero">
        <div class="speech-bubble">
          Hi，{{ user.name || user.username }}！今天想先从哪件事开始呢？
        </div>
        <img :src="benbenImage" alt="AI 小助手" />
      </section>

      <section class="assistant-card">
        <h3>你可以试试问我</h3>
        <button v-for="question in promptQuestions" :key="question" type="button" @click="selectAction(question)">
          <span>{{ question }}</span>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </section>

      <section class="assistant-card note-card">
        <strong>今日小贴士</strong>
        <p>专注一件事，把它做好，就是最棒的进步！</p>
      </section>

      <section class="assistant-card focus-card">
        <div>
          <strong>专注时刻</strong>
          <span>沉浸专注，效率翻倍</span>
        </div>
        <strong class="focus-time">{{ focusMinutes }}:00</strong>
        <el-slider v-model="focusMinutes" :min="15" :max="60" :step="5" />
        <el-button type="primary" round @click="selectAction('开始专注')">开始专注</el-button>
        <img class="focus-illustration" :src="focusMomentImage" alt="" aria-hidden="true" />
      </section>
    </aside>

    <AssistantChat
      v-model:open="assistantOpen"
      v-model:input="assistantInput"
      :avatar="assistantLogo"
      title="犇犇"
      :messages="assistantMessages"
      :quick-actions="assistantQuickActions"
      :loading="assistantLoading"
      @send="sendAssistantMessage"
    />
  </AppLayout>
</template>
