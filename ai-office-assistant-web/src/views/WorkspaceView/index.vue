<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, ChatDotRound, Document, Setting } from '@element-plus/icons-vue'
import DigitalHumanAssistant from '../../components/DigitalHumanAssistant/index.vue'
import AppLayout from '../../layout/AppLayout/index.vue'
// 各业务菜单按需切分独立 chunk：打开工作台只加载首页 + 当前菜单对应的模块，
// 首屏不再一次性解析全部功能（原先所有视图打进单一 2.5MB 主包，导致首次打开慢）。
const AssistantCenterView = defineAsyncComponent(() => import('../AssistantCenterView/index.vue'))
const DiaryView = defineAsyncComponent(() => import('../DiaryView/index.vue'))
const ForumView = defineAsyncComponent(() => import('../ForumView/index.vue'))
const WorkOrderView = defineAsyncComponent(() => import('../WorkOrderView/index.vue'))
const LobsterBaseView = defineAsyncComponent(() => import('../LobsterBaseView/index.vue'))
const MailAssistantView = defineAsyncComponent(() => import('../MailAssistantView/index.vue'))
const MeetingAssistantView = defineAsyncComponent(() => import('../MeetingAssistantView/index.vue'))
const KnowledgeBaseView = defineAsyncComponent(() => import('../KnowledgeBaseView/index.vue'))
const ProjectAssistantView = defineAsyncComponent(() => import('../ProjectAssistantView/index.vue'))
const LedgerAssistantView = defineAsyncComponent(() => import('../LedgerAssistantView/index.vue'))
const CashflowAssistantView = defineAsyncComponent(() => import('../CashflowAssistantView/index.vue'))
const DataCenterView = defineAsyncComponent(() => import('../DataCenterView/index.vue'))
const CrmAssistantView = defineAsyncComponent(() => import('../CrmAssistantView/index.vue'))
const ReimbursementView = defineAsyncComponent(() => import('../ReimbursementView/index.vue'))
const NewsView = defineAsyncComponent(() => import('../NewsView/index.vue'))
const SettingsView = defineAsyncComponent(() => import('../SettingsView/index.vue'))
const TripReportView = defineAsyncComponent(() => import('../TripReportView/index.vue'))
const WeeklyReportView = defineAsyncComponent(() => import('../WeeklyReportView/index.vue'))
const WritingAssistantView = defineAsyncComponent(() => import('../WritingAssistantView/index.vue'))
const WorkflowCenterView = defineAsyncComponent(() => import('../WorkflowCenterView/index.vue'))
import { authState, logoutSession } from '../../services/authSession'
import { downloadUrl, getReports, type ReportFile } from '../../services/personalWorkApi'
import { customizableMenuItems, isMenuId, visibleMenuItems, type MenuId } from '../../layout/menu'
import { applyNavPrefs, loadNavPrefs, reorderVisibleAssistants } from '../../layout/navPrefs'
import benbenImage from '../../assets/benben.png'
import homeHeroBanner from '../../assets/home-hero-banner.png'
import assistantLogo from '../../assets/logo_1.png'
import {
  focusMomentImage,
  homeAssistantActions,
  homeFeatures,
  promptQuestions,
  type HomeRecordTone,
} from '../../data/pageData'
import './index.scss'

const route = useRoute()
const router = useRouter()
const focusMinutes = ref(25)
const deskPetRef = ref<InstanceType<typeof DigitalHumanAssistant> | null>(null)
const currentTime = ref(new Date())
const recentReports = ref<ReportFile[]>([])
const recentReportsLoading = ref(false)
const recentReportsError = ref('')
const user = computed(() => authState.user)
const activeMenu = computed<MenuId>(() => {
  const menu = String(route.params.menu || 'dashboard')
  return isMenuId(menu) ? menu : 'dashboard'
})
const menuItems = computed(() => (user.value ? applyNavPrefs(visibleMenuItems(user.value)) : []))
const hasActiveAssistantView = computed(() => [
  'assistants', 'weekly', 'trip', 'diary', 'writing', 'forum', 'workorder', 'news', 'mailassistant',
  'meeting', 'knowledge', 'project', 'crm', 'ledger', 'cashflow', 'datacenter', 'workflow', 'reimbursement', 'lobsterbase',
  'config', 'mailconfig', 'skills', 'usermanage', 'mcp',
].includes(activeMenu.value))
const homeGreeting = computed(() => {
  const name = user.value?.name?.trim() || user.value?.username || ''
  const greeting = greetingByHour(currentTime.value.getHours())
  return name ? greeting.replace('，', `，${name}，`) : greeting
})
const homePage = ref(1)
const homeMenus = computed(() => menuItems.value.filter(item => item.group === 'main' && !item.fixed && item.showInSidebar !== false))
const homeIds = computed(() => new Set(homeMenus.value.map(item => item.id)))
const visibleFeatures = computed(() => homeMenus.value.map(item => {
  const feature = homeFeatures.find(f => f.menuId === item.id)
  return {id:item.id,menuId:item.id,label:item.label,description:feature?.description || `打开${item.label}，开始处理工作`,image:feature?.image,icon:item.icon,tone:feature?.tone || 'blue'}
}))
const pageFeatures = computed(() => visibleFeatures.value.slice((homePage.value - 1) * 6, homePage.value * 6))
const visibleCapabilities = computed(() => pageFeatures.value.slice(0,4).map(item => ({id:item.id,title:item.label,description:item.description,icon:item.icon})))
const visibleActions = computed(() => homeAssistantActions.filter(item => homeIds.value.has(item.menuId || (item.id === 'meeting' ? 'meeting' : 'dashboard'))))
const visibleReports = computed(() => recentReports.value.filter(item => (item.kind === 'weekly' && homeIds.value.has('weekly')) || (item.kind === 'trip' && homeIds.value.has('trip'))).slice(0,5))
const showRecentReports = computed(() => homeIds.value.has('weekly') || homeIds.value.has('trip'))
watch(() => homeMenus.value.map(item => item.id).join(','), () => { homePage.value = 1 })
let greetingTimer: number | undefined

onMounted(() => {
  // 每分钟刷新一次，避免页面长时间停留后问候语过期。
  greetingTimer = window.setInterval(() => {
    currentTime.value = new Date()
  }, 60 * 1000)
  // 加载当前用户的导航偏好（排序 / 隐藏），让侧边栏按个人配置展示。
  loadNavPrefs()
})

async function handleNavReorder(ids: MenuId[]) {
  if (!user.value) return
  try {
    await reorderVisibleAssistants(ids, customizableMenuItems(user.value))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存导航顺序失败')
  }
}

watch(
  activeMenu,
  (menu) => {
    if (menu === 'dashboard' && showRecentReports.value) loadRecentReports()
  },
  { immediate: true },
)

watch(showRecentReports, (show) => { if (show && activeMenu.value === 'dashboard') loadRecentReports() })

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
    recentReports.value = data.reports.slice().sort((left, right) => right.mtime - left.mtime)
  } catch (error) {
    recentReportsError.value = error instanceof Error ? error.message : '最近文档加载失败'
  } finally {
    recentReportsLoading.value = false
  }
}

function selectMenu(menu: string) {
  if (isMenuId(menu)) router.push(`/workspace/${menu}`)
}

function openWeeklyEditor(draft: Record<string, unknown>) {
  if (!user.value?.username) return
  localStorage.setItem(`personalWorkSite.pendingWeeklyAgentDraft:${user.value.username}`, JSON.stringify(draft))
  selectMenu('weekly')
  ElMessage.success('周报草稿已带入编辑页，可继续调整并发送邮件')
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
  window.location.replace('/login')
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
    @reorder="handleNavReorder"
  >
    <!-- 已访问的助手保留实例而非卸载：切换页面不取消生成、上传、AI 请求等后台操作。 -->
    <KeepAlive><AssistantCenterView v-if="activeMenu === 'assistants'" /></KeepAlive>
    <KeepAlive><WeeklyReportView v-if="activeMenu === 'weekly'" /></KeepAlive>
    <KeepAlive><TripReportView v-if="activeMenu === 'trip'" /></KeepAlive>
    <KeepAlive><DiaryView v-if="activeMenu === 'diary'" /></KeepAlive>
    <KeepAlive><WritingAssistantView v-if="activeMenu === 'writing'" /></KeepAlive>
    <KeepAlive><ForumView v-if="activeMenu === 'forum'" /></KeepAlive>
    <KeepAlive><WorkOrderView v-if="activeMenu === 'workorder'" /></KeepAlive>
    <KeepAlive><NewsView v-if="activeMenu === 'news'" /></KeepAlive>
    <KeepAlive><MailAssistantView v-if="activeMenu === 'mailassistant'" /></KeepAlive>
    <KeepAlive><MeetingAssistantView v-if="activeMenu === 'meeting'" /></KeepAlive>
    <KeepAlive><KnowledgeBaseView v-if="activeMenu === 'knowledge'" /></KeepAlive>
    <KeepAlive><ProjectAssistantView v-if="activeMenu === 'project'" /></KeepAlive>
    <KeepAlive><CrmAssistantView v-if="activeMenu === 'crm'" /></KeepAlive>
    <KeepAlive><LedgerAssistantView v-if="activeMenu === 'ledger'" /></KeepAlive>
    <KeepAlive><CashflowAssistantView v-if="activeMenu === 'cashflow'" /></KeepAlive>
    <KeepAlive><DataCenterView v-if="activeMenu === 'datacenter'" /></KeepAlive>
    <KeepAlive><WorkflowCenterView v-if="activeMenu === 'workflow'" /></KeepAlive>
    <KeepAlive><ReimbursementView v-if="activeMenu === 'reimbursement'" /></KeepAlive>
    <KeepAlive><LobsterBaseView v-if="activeMenu === 'lobsterbase'" /></KeepAlive>
    <KeepAlive>
      <SettingsView
        v-if="['config', 'mailconfig', 'skills', 'usermanage', 'mcp'].includes(activeMenu)"
        :active-menu="activeMenu"
        @select-menu="selectMenu"
      />
    </KeepAlive>

    <section v-if="activeMenu === 'dashboard'" class="workspace-main home-dashboard">
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
            v-for="item in pageFeatures"
            :key="item.id"
            :class="['home-feature-card', `home-feature-card--${item.tone}`]"
            type="button"
            @mousemove="updateSpotlightPosition"
            @click="selectMenu(item.menuId)"
          >
            <img v-if="item.image" :src="item.image" alt="" aria-hidden="true" /><el-icon v-else class="home-feature-symbol"><component :is="item.icon || Document" /></el-icon>
            <strong>{{ item.label }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </div>
        <el-pagination v-if="visibleFeatures.length > 6" v-model:current-page="homePage" :page-size="6" :total="visibleFeatures.length" layout="prev, pager, next" style="margin-top:12px" />
        <p v-if="!visibleFeatures.length" class="home-record-empty">暂无已显示的助手，可在助手中心选择已获授权的助手。</p>
      </section>

      <section v-if="showRecentReports" class="home-panel home-record-panel" aria-label="最近编辑">
        <div class="home-panel-title home-panel-title--between">
          <span><el-icon><Document /></el-icon></span>
          <h2>最近编辑</h2>
        </div>
        <ul v-if="visibleReports.length" class="home-record-list">
          <li v-for="item in visibleReports" :key="item.name">
            <div class="home-record-row">
              <span :class="['home-record-icon', `home-record-icon--${reportRecordTone(item)}`]">
                {{ reportRecordIcon(item) }}
              </span>
              <strong>{{ item.name }}</strong>
              <em :class="`home-record-tag--${reportRecordTone(item)}`">{{ reportRecordTag(item) }}</em>
              <time>{{ formatRecentTime(item.mtime) }}</time>
              <a class="home-record-view" :href="reportDownloadUrl(item.name)" target="_blank" rel="noopener" :aria-label="`查看 ${item.name}`">
                查看
              </a>
            </div>
          </li>
        </ul>
        <div v-else class="home-record-empty">
          {{ recentReportsLoading ? '正在加载最近文档...' : recentReportsError || '暂无最近文档' }}
        </div>
      </section>
    </section>

    <section v-if="!hasActiveAssistantView && activeMenu !== 'dashboard'" class="workspace-main placeholder-main">
      <article class="panel placeholder-panel">
        <h3>{{ menuItems.find((item) => item.id === activeMenu)?.label }}</h3>
        <p>这个功能会接入个人办公助手现有能力，当前先保留入口。</p>
      </article>
    </section>

    <aside v-if="activeMenu === 'dashboard'" class="home-side-panel">
      <section v-if="visibleCapabilities.length" class="home-panel home-capability-panel">
        <div class="home-side-title">
          <span><el-icon><Setting /></el-icon></span>
          <h2>当前能力</h2>
        </div>
        <ul class="home-capability-list">
          <li v-for="item in visibleCapabilities" :key="item.id" class="home-capability-item">
            <span class="home-capability-icon">
              <el-icon>
                <component :is="item.icon || Document" />
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
            v-for="item in visibleActions"
            :key="item.id"
            type="button"
            @click="item.menuId ? selectMenu(item.menuId) : sendAssistantMessage(item.label)"
          >
            {{ item.label }}
          </button>
        </div>
      </section>
    </aside>

    <aside v-if="!hasActiveAssistantView && activeMenu !== 'dashboard'" class="assistant-panel">
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

    <DigitalHumanAssistant ref="deskPetRef" :user-name="user.name || user.username" @weekly-ready="openWeeklyEditor" />
  </AppLayout>
</template>
