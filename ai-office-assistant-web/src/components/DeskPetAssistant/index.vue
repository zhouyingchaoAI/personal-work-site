<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowRight, Close, MagicStick, Position, StarFilled } from '@element-plus/icons-vue'
import type { MenuId } from '../../layout/menu'
import {
  agentChat,
  getAssistantLobster,
  lobsterChat,
  type AgentKind,
  type AgentMessage,
  type BoundLobster,
} from '../../services/personalWorkApi'
import sleepPetImage from '../../assets/L1.png'
import activePetImage from '../../assets/L2.png'
import './index.scss'

type PetMode = 'sleep' | 'menu' | 'chat'

interface DeskPetConfig {
  agent: AgentKind
  title: string
  intro: string
  summary: string
  actions: string[]
}

const props = defineProps<{
  activeMenu: MenuId
  userName: string
}>()

const petRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const mode = ref<PetMode>('sleep')
const inputText = ref('')
const loading = ref(false)
const messages = ref<AgentMessage[]>([])
// 已绑定的龙虾：绑定后对话直通该龙虾，否则走本地页面助手。
const boundLobster = ref<BoundLobster | null>(null)
const position = ref({ left: 0, top: 0 })
const hasPosition = ref(false)
const windowSize = ref({ width: 0, height: 0 })
const panelSize = ref({ width: 0, height: 0 })
let dragStart:
  | {
      pointerId: number
      x: number
      y: number
      left: number
      top: number
      moved: boolean
    }
  | null = null
let ignoreNextClick = false

const pageConfigs: Record<MenuId, DeskPetConfig> = {
  dashboard: {
    agent: 'dashboard',
    title: '首页助手',
    intro: 'Hi~ 我是你的办公小助手，有什么可以帮你？',
    summary: '我可以帮你梳理今日重点、快速进入常用功能，或把碎片想法整理成行动清单。',
    actions: ['梳理今天的工作重点', '推荐一个常用入口', '整理待办优先级'],
  },
  weekly: {
    agent: 'weekly',
    title: '周报助手',
    intro: 'Hi~ 我可以协助你整理本周工作。',
    summary: '根据当前周报内容，我可以帮你补全总结、润色表达，或生成预览前的检查建议。',
    actions: ['帮你总结本周工作', '润色当前内容', '生成预览检查'],
  },
  trip: {
    agent: 'trip',
    title: '出差报告助手',
    intro: 'Hi~ 我可以帮你把出差素材整理成报告。',
    summary: '我可以梳理出差目的、行程成果、费用说明和邮件发送内容。',
    actions: ['整理出差目的', '检查报告结构', '生成邮件摘要'],
  },
  diary: {
    agent: 'diary',
    title: '日记助手',
    intro: 'Hi~ 我可以帮你把今天的工作沉淀下来。',
    summary: '我可以根据当前日记内容做润色、补全计划，或提炼可复用的周报素材。',
    actions: ['整理今日记录', 'AI 润色工作内容', '提炼周报素材'],
  },
  forum: {
    agent: 'forum',
    title: '论坛助手',
    intro: 'Hi~ 我可以帮你参与金点子讨论。',
    summary: '我可以生成话题、提炼观点、补充评论，让讨论更容易沉淀为可执行建议。',
    actions: ['生成讨论话题', '提炼当前观点', 'AI 潜水评论'],
  },
  news: {
    agent: 'news',
    title: '资讯助手',
    intro: 'Hi~ 我可以帮你快速读懂每日资讯。',
    summary: '我可以汇总重点新闻、提炼风险机会，或生成适合内部同步的摘要。',
    actions: ['汇总今日资讯', '生成阅读摘要', '提炼跟进行动'],
  },
  mailassistant: {
    agent: 'mailassistant',
    title: '邮件助手',
    intro: 'Hi~ 我可以帮你写出更清晰的邮件。',
    summary: '我可以润色邮件正文、生成正式回复，或从邮件内容里提炼待办事项。',
    actions: ['润色邮件正文', '生成正式回复', '提炼待办事项'],
  },
  lobsterbase: {
    agent: 'dashboard',
    title: '龙虾基地助手',
    intro: 'Hi~ 我可以帮你衔接当前办公流程。',
    summary: '我可以帮你记录当前事项、整理下一步动作，或回到办公助手继续处理材料。',
    actions: ['整理当前事项', '生成下一步动作', '回到办公助手'],
  },
  help: {
    agent: 'dashboard',
    title: '帮助助手',
    intro: 'Hi~ 我可以帮你定位使用问题。',
    summary: '我可以解释当前功能、整理反馈内容，或帮你准备一段清晰的问题描述。',
    actions: ['解释当前功能', '整理反馈内容', '生成问题描述'],
  },
  config: {
    agent: 'dashboard',
    title: '设置助手',
    intro: 'Hi~ 我可以帮你检查助手配置。',
    summary: '我可以解释配置项、检查账号信息，或帮你梳理需要调整的系统能力。',
    actions: ['检查助手配置', '解释设置项', '整理配置建议'],
  },
  mailconfig: {
    agent: 'mailassistant',
    title: '邮件配置助手',
    intro: 'Hi~ 我可以帮你检查邮件配置。',
    summary: '我可以说明 SMTP/IMAP 配置含义、排查发送问题，或整理配置注意事项。',
    actions: ['检查邮件配置', '说明配置项', '排查发送问题'],
  },
  skills: {
    agent: 'dashboard',
    title: 'Skill 助手',
    intro: 'Hi~ 我可以帮你管理系统 Skill。',
    summary: '我可以梳理 Skill 用途、整理提示词方向，或帮助你检查启用状态。',
    actions: ['梳理 Skill 用途', '整理提示词方向', '检查启用状态'],
  },
  usermanage: {
    agent: 'dashboard',
    title: '用户管理助手',
    intro: 'Hi~ 我可以帮你处理用户管理事项。',
    summary: '我可以整理账号权限、生成用户说明，或帮助排查角色配置问题。',
    actions: ['整理账号权限', '生成用户说明', '排查角色配置'],
  },
  mcp: {
    agent: 'dashboard',
    title: 'MCP 服务助手',
    intro: 'Hi~ 我可以帮你检查 MCP 服务配置。',
    summary: '我可以说明连接配置、检查密钥状态，或帮你梳理外部客户端接入步骤。',
    actions: ['检查 MCP 状态', '说明连接配置', '梳理接入步骤'],
  },
  reimbursement: {
    agent: 'dashboard',
    title: '报销助手',
    intro: 'Hi~ 我可以帮你整理报销单据。',
    summary: '我可以帮你检查发票信息、整理报销说明，或汇总本次报销的费用明细。',
    actions: ['检查发票信息', '整理报销说明', '汇总费用明细'],
  },
}

const currentConfig = computed(() => pageConfigs[props.activeMenu])
const shellClass = computed(() => [`desk-pet-shell`, `desk-pet-shell--${mode.value}`])
const panelWidth = computed(() => Math.min(mode.value === 'chat' ? 390 : 320, Math.max(280, windowSize.value.width - 24)))
const panelHeight = computed(() => panelSize.value.height || (mode.value === 'chat' ? 520 : 302))
const panelOpensLeft = computed(() => {
  const petWidth = mode.value === 'sleep' ? 112 : 168
  return position.value.left + petWidth + panelWidth.value + 10 > windowSize.value.width
})
const panelStyle = computed(() => {
  if (mode.value === 'sleep') return {}
  const petWidth = 168
  const visualGap = 6
  const arrowOffsetFromBottom = 35
  const petAnchorY = position.value.top + 92
  const rawLeft = panelOpensLeft.value ? position.value.left - panelWidth.value + visualGap : position.value.left + petWidth - visualGap
  const rawTop = petAnchorY - (panelHeight.value - arrowOffsetFromBottom)
  return {
    width: `${panelWidth.value}px`,
    left: `${Math.min(Math.max(12, rawLeft), Math.max(12, windowSize.value.width - panelWidth.value - 12))}px`,
    top: `${Math.min(Math.max(12, rawTop), Math.max(12, windowSize.value.height - Math.min(panelHeight.value, windowSize.value.height - 24) - 12))}px`,
  }
})
const panelClass = computed(() => [
  'desk-pet-panel',
  mode.value === 'chat' ? 'desk-pet-panel--chat' : 'desk-pet-panel--menu',
  panelOpensLeft.value ? 'desk-pet-panel--left' : 'desk-pet-panel--right',
])

function sizeForMode(value: PetMode) {
  const compact = windowSize.value.width > 0 && windowSize.value.width <= 720
  if (value === 'sleep') return compact ? { width: 62, height: 130 } : { width: 66, height: 138 }
  return { width: 168, height: compact ? 124 : 170 }
}

function petSize() {
  return sizeForMode(mode.value)
}

function positionForMode(nextMode: PetMode) {
  const currentSize = sizeForMode(mode.value)
  const nextSize = sizeForMode(nextMode)
  const viewportWidth = windowSize.value.width || window.innerWidth
  const viewportHeight = windowSize.value.height || window.innerHeight
  const lockRight = position.value.left > viewportWidth - position.value.left - currentSize.width
  const lockBottom = position.value.top > viewportHeight - position.value.top - currentSize.height
  return {
    left: lockRight ? position.value.left + currentSize.width - nextSize.width : position.value.left,
    top: lockBottom ? position.value.top + currentSize.height - nextSize.height : position.value.top,
  }
}

function setMode(nextMode: PetMode) {
  if (mode.value === nextMode) return
  if (hasPosition.value) {
    // 状态尺寸不同，按最近边缘换算坐标，避免靠左或靠右时展开收起后漂移。
    position.value = positionForMode(nextMode)
  }
  mode.value = nextMode
  nextTick(() => {
    measurePanel()
    constrainPosition()
  })
}

function initialMessage() {
  return {
    role: 'assistant' as const,
    content: `${currentConfig.value.intro}\n${currentConfig.value.summary}`,
  }
}

function resetMessages() {
  messages.value = [initialMessage()]
  inputText.value = ''
}

async function loadBinding() {
  try {
    const result = await getAssistantLobster()
    boundLobster.value = result.ok ? result.lobster : null
  } catch {
    boundLobster.value = null
  }
}

function wake() {
  if (ignoreNextClick) {
    ignoreNextClick = false
    return
  }
  if (mode.value === 'sleep') {
    loadBinding()
    setMode('menu')
    return
  }
  sleep()
}

function sleep() {
  setMode('sleep')
}

function openChat() {
  setMode('chat')
  nextTick(() => {
    measurePanel()
    constrainPosition()
  })
}

async function sendAction(text: string) {
  inputText.value = ''
  setMode('chat')
  await nextTick()
  await sendMessage(text)
}

async function sendMessage(text = inputText.value) {
  const content = text.trim()
  if (!content || loading.value) return
  setMode('chat')
  messages.value.push({ role: 'user', content })
  inputText.value = ''
  loading.value = true
  try {
    if (boundLobster.value) {
      // 已绑定龙虾：对话直通该龙虾（多轮由后端固定 session 维持连续）。
      const result = await lobsterChat(content)
      if (!result.ok) throw new Error(result.error || '龙虾暂时不可用')
      messages.value.push({ role: 'assistant', content: result.reply || '（龙虾没有返回内容）' })
    } else {
      const result = await agentChat(currentConfig.value.agent, messages.value.slice(-8))
      if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
      messages.value.push({ role: 'assistant', content: result.reply || '我已经看过当前内容，暂时没有新的补充。' })
    }
  } catch (error) {
    messages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
  } finally {
    loading.value = false
    await nextTick()
    measurePanel()
    scrollMessagesToBottom()
  }
}

function startDrag(event: PointerEvent) {
  if (event.button !== 0) return
  const rect = petRef.value?.getBoundingClientRect()
  if (!rect) return
  dragStart = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    left: rect.left,
    top: rect.top,
    moved: false,
  }
  window.addEventListener('pointermove', drag)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
}

function drag(event: PointerEvent) {
  if (!dragStart || event.pointerId !== dragStart.pointerId) return
  const deltaX = event.clientX - dragStart.x
  const deltaY = event.clientY - dragStart.y
  if (Math.abs(deltaX) + Math.abs(deltaY) > 5) dragStart.moved = true
  position.value = {
    left: dragStart.left + deltaX,
    top: dragStart.top + deltaY,
  }
  hasPosition.value = true
  constrainPosition()
}

function stopDrag(event: PointerEvent) {
  if (dragStart && event.pointerId === dragStart.pointerId) {
    ignoreNextClick = dragStart.moved
    savePosition()
  }
  dragStart = null
  window.removeEventListener('pointermove', drag)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
}

function defaultPosition() {
  const { width, height } = petSize()
  position.value = {
    left: Math.max(4, window.innerWidth - width - 8),
    top: Math.max(12, window.innerHeight - height - 20),
  }
  hasPosition.value = true
}

function constrainPosition() {
  const { width, height } = petSize()
  position.value = {
    left: Math.min(Math.max(4, position.value.left), Math.max(4, window.innerWidth - width - 4)),
    top: Math.min(Math.max(12, position.value.top), Math.max(12, window.innerHeight - height - 12)),
  }
}

function measurePanel() {
  const rect = panelRef.value?.getBoundingClientRect()
  if (!rect) return
  panelSize.value = { width: rect.width, height: rect.height }
}

function savePosition() {
  if (!hasPosition.value) return
  localStorage.setItem('desk-pet-position', JSON.stringify(position.value))
}

function restorePosition() {
  const raw = localStorage.getItem('desk-pet-position')
  if (raw) {
    try {
      const saved = JSON.parse(raw) as { left: number; top: number }
      position.value = saved
      hasPosition.value = true
      nextTick(constrainPosition)
      return
    } catch {
      localStorage.removeItem('desk-pet-position')
    }
  }
  nextTick(defaultPosition)
}

function scrollMessagesToBottom() {
  const list = panelRef.value?.querySelector('.desk-pet-chat-messages')
  if (list) list.scrollTop = list.scrollHeight
}

function handleResize() {
  windowSize.value = { width: window.innerWidth, height: window.innerHeight }
  if (!hasPosition.value) defaultPosition()
  measurePanel()
  constrainPosition()
}

function handleOutsidePointerDown(event: PointerEvent) {
  if (mode.value === 'sleep') return
  if (petRef.value?.contains(event.target as Node)) return
  if (panelRef.value?.contains(event.target as Node)) return
  sleep()
}

watch(
  () => props.activeMenu,
  () => {
    // 页面切换后刷新桌宠上下文，保证不同页面展示不同对话入口。
    setMode('sleep')
    resetMessages()
    nextTick(constrainPosition)
  },
)

watch(mode, () => nextTick(constrainPosition))
watch(mode, () => nextTick(measurePanel))
watch(panelWidth, () => nextTick(measurePanel))

onMounted(() => {
  windowSize.value = { width: window.innerWidth, height: window.innerHeight }
  resetMessages()
  loadBinding()
  restorePosition()
  window.addEventListener('resize', handleResize)
  window.addEventListener('pointerdown', handleOutsidePointerDown)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('pointerdown', handleOutsidePointerDown)
  window.removeEventListener('pointermove', drag)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
})

defineExpose({
  wake,
  sendAction,
})
</script>

<template>
  <section
    ref="petRef"
    :class="shellClass"
    :style="{ left: `${position.left}px`, top: `${position.top}px` }"
    aria-label="犇犇 AI 桌宠"
  >
    <section v-if="mode !== 'sleep'" ref="panelRef" :class="panelClass" :style="panelStyle">
      <template v-if="mode === 'menu'">
        <header class="desk-pet-panel-head">
          <strong>{{ currentConfig.intro }}</strong>
          <button type="button" aria-label="休眠桌宠" @click="sleep">
            <el-icon><Close /></el-icon>
          </button>
        </header>
        <p>{{ currentConfig.summary }}</p>
        <div class="desk-pet-actions">
          <button v-for="action in currentConfig.actions" :key="action" type="button" @click="sendAction(action)">
            <span><el-icon><MagicStick /></el-icon></span>
            {{ action }}
            <el-icon><ArrowRight /></el-icon>
          </button>
        </div>
        <button class="desk-pet-enter-chat" type="button" @click="openChat">
          进入对话
          <el-icon><ArrowRight /></el-icon>
        </button>
      </template>

      <template v-else>
        <header class="desk-pet-chat-head">
          <div>
            <strong>{{ boundLobster ? `龙虾 · ${boundLobster.agent_name} #${boundLobster.agent_id}` : currentConfig.title }}</strong>
            <span>{{ boundLobster ? `已绑定龙虾，对话直通 ${boundLobster.agent_name} #${boundLobster.agent_id}` : `${props.userName}，我正在看当前页面` }}</span>
          </div>
          <button type="button" aria-label="休眠桌宠" @click="sleep">
            <el-icon><Close /></el-icon>
          </button>
        </header>
        <div class="desk-pet-chat-messages">
          <article v-for="(message, index) in messages" :key="index" :class="['desk-pet-message', message.role]">
            {{ message.content }}
          </article>
          <article v-if="loading" class="desk-pet-message assistant">{{ boundLobster ? '龙虾正在思考，请稍候…' : '正在思考...' }}</article>
        </div>
        <div class="desk-pet-chat-actions">
          <button v-for="action in currentConfig.actions" :key="action" type="button" :disabled="loading" @click="sendAction(action)">
            {{ action }}
          </button>
        </div>
        <form class="desk-pet-chat-input" @submit.prevent="sendMessage()">
          <textarea
            v-model="inputText"
            placeholder="输入问题，Ctrl/⌘ + Enter 发送"
            @keydown.ctrl.enter.prevent="sendMessage()"
            @keydown.meta.enter.prevent="sendMessage()"
          ></textarea>
          <button type="submit" :disabled="loading || !inputText.trim()">
            <el-icon><Position /></el-icon>
          </button>
        </form>
      </template>
    </section>

    <button
      :class="['desk-pet-body', mode === 'sleep' ? 'desk-pet-body--sleep' : 'desk-pet-body--active']"
      type="button"
      :aria-label="mode === 'sleep' ? '唤醒犇犇桌宠' : '拖动犇犇桌宠'"
      @pointerdown="startDrag"
      @click="wake"
    >
      <span v-if="mode === 'sleep'" class="desk-pet-sleep-card">
        <strong>待命中</strong>
        <em>点击唤醒</em>
        <img class="desk-pet-sleep-image" :src="sleepPetImage" alt="" draggable="false" />
        <span class="desk-pet-sleep-dot" aria-hidden="true"></span>
      </span>
      <template v-else>
        <span class="desk-pet-sparkle desk-pet-sparkle--one"><el-icon><StarFilled /></el-icon></span>
        <span class="desk-pet-sparkle desk-pet-sparkle--two"><el-icon><StarFilled /></el-icon></span>
        <img class="desk-pet-active-image" :src="activePetImage" alt="" draggable="false" />
        <span class="desk-pet-online" aria-hidden="true"></span>
      </template>
    </button>
  </section>
</template>
