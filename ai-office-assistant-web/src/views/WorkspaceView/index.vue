<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Calendar, ChatDotRound, ChatLineSquare, Document, Message, Notebook, Setting } from '@element-plus/icons-vue'
import DeskPetAssistant from '../../components/DeskPetAssistant/index.vue'
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
import { downloadUrl, getReports, type ReportFile } from '../../services/personalWorkApi'
import { isMenuId, visibleMenuItems, type MenuId } from '../../layout/menu'
import benbenImage from '../../assets/benben.png'
import homeHeroBanner from '../../assets/home-hero-banner.png'
import assistantLogo from '../../assets/logo_1.png'
import {
  focusMomentImage,
  homeAssistantActions,
  homeCapabilities,
  homeFeatures,
  promptQuestions,
  type HomeRecordTone,
} from '../../data/pageData'
import './index.scss'

const route = useRoute()
const router = useRouter()
const focusMinutes = ref(25)
const deskPetRef = ref<InstanceType<typeof DeskPetAssistant> | null>(null)
const currentTime = ref(new Date())
const recentReports = ref<ReportFile[]>([])
const recentReportsLoading = ref(false)
const recentReportsError = ref('')
const user = computed(() => authState.user)
const activeMenu = computed<MenuId>(() => {
  const menu = String(route.params.menu || 'weekly')
  return isMenuId(menu) ? menu : 'weekly'
})
const menuItems = computed(() => (user.value ? visibleMenuItems(user.value) : []))
const homeGreeting = computed(() => greetingByHour(currentTime.value.getHours()))
let greetingTimer: number | undefined

onMounted(() => {
  // 每分钟刷新一次，避免页面长时间停留后问候语过期。
  greetingTimer = window.setInterval(() => {
    currentTime.value = new Date()
  }, 60 * 1000)
})

watch(
  activeMenu,
  (menu) => {
    if (menu === 'dashboard') loadRecentReports()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (greetingTimer) window.clearInterval(greetingTimer)
})

async function loadRecentReports() {
  if (recentReportsLoading.value) return
  recentReportsLoading.value = true
  recentReportsError.value = ''
  try {
    const data = await getReports()
    // 最近编辑按文件修改时间统一排序，不沿用报告管理列表的分类排序。
    recentReports.value = data.reports.slice().sort((left, right) => right.mtime - left.mtime).slice(0, 5)
  } catch (error) {
    recentReportsError.value = error instanceof Error ? error.message : '最近文档加载失败'
  } finally {
    recentReportsLoading.value = false
  }
}

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

function reportDownloadUrl(name: string) {
  return downloadUrl(`/download?file=${encodeURIComponent(name)}`)
}

function reportRecordTone(report: ReportFile): HomeRecordTone {
  return report.kind === 'weekly' ? 'word' : 'excel'
}

function reportRecordIcon(report: ReportFile) {
  return report.kind === 'weekly' ? 'W' : 'X'
}

function reportRecordTag(report: ReportFile) {
  return report.kind === 'weekly' ? '周报助手' : '出差报告助手'
}

function formatRecentTime(mtime: number) {
  const date = new Date(mtime * 1000)
  const now = currentTime.value
  const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  if (day === today) return `今天 ${time}`
  if (day === today - 24 * 60 * 60 * 1000) return `昨天 ${time}`
  return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`
}

function sendAssistantMessage(text: string) {
  deskPetRef.value?.sendAction(text)
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
        </div>
        <ul v-if="recentReports.length" class="home-record-list">
          <li v-for="item in recentReports" :key="item.name">
            <a :href="reportDownloadUrl(item.name)" target="_blank" rel="noopener">
              <span :class="['home-record-icon', `home-record-icon--${reportRecordTone(item)}`]">
                {{ reportRecordIcon(item) }}
              </span>
              <strong>{{ item.name }}</strong>
              <em :class="`home-record-tag--${reportRecordTone(item)}`">{{ reportRecordTag(item) }}</em>
              <time>{{ formatRecentTime(item.mtime) }}</time>
            </a>
          </li>
        </ul>
        <div v-else class="home-record-empty">
          {{ recentReportsLoading ? '正在加载最近文档...' : recentReportsError || '暂无最近文档' }}
        </div>
      </section>
    </section>

    <section v-else class="workspace-main placeholder-main">
      <article class="panel placeholder-panel">
        <h3>{{ menuItems.find((item) => item.id === activeMenu)?.label }}</h3>
        <p>这个功能会接入个人办公助手现有能力，当前先保留入口。</p>
      </article>
    </section>

    <aside v-if="activeMenu === 'dashboard'" class="home-side-panel">
      <section class="home-panel home-capability-panel">
        <div class="home-side-title">
          <span><el-icon><Setting /></el-icon></span>
          <h2>当前能力</h2>
        </div>
        <ul class="home-capability-list">
          <li v-for="item in homeCapabilities" :key="item.id" class="home-capability-item">
            <span class="home-capability-icon">
              <el-icon>
                <Calendar v-if="item.icon === 'report'" />
                <ChatLineSquare v-else-if="item.icon === 'forum'" />
                <Notebook v-else-if="item.icon === 'news'" />
                <Message v-else />
              </el-icon>
            </span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.description }}</p>
            </div>
          </li>
        </ul>
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
        <button class="home-ai-primary" type="button" @click="deskPetRef?.wake()">
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

    <DeskPetAssistant ref="deskPetRef" :active-menu="activeMenu" :user-name="user.name || user.username" />
  </AppLayout>
</template>
