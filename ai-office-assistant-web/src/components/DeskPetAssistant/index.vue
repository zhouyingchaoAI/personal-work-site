<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowRight, Close, MagicStick, Paperclip, Position, Refresh, StarFilled } from '@element-plus/icons-vue'
import {
  agentChat,
  getAgentSession,
  getAssistantLobster,
  lobsterChat,
  uploadWritingFile,
  type AgentKind,
  type AgentMessage,
  type BoundLobster,
  type WritingMaterial,
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
  userName: string
}>()

const petRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const chatDialogRef = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const mode = ref<PetMode>('sleep')
const inputText = ref('')
const loading = ref(false)
const messages = ref<AgentMessage[]>([])
const historyLoadedKey = ref('')
const agentSessionIds = ref<Partial<Record<AgentKind, string>>>({})
// 已绑定的龙虾：绑定后对话直通该龙虾，否则走本地犇犇助手。
const boundLobster = ref<BoundLobster | null>(null)
const position = ref({ left: 0, top: 0 })
const hasPosition = ref(false)
const windowSize = ref({ width: 0, height: 0 })
const panelSize = ref({ width: 0, height: 0 })
const attachedFiles = ref<WritingMaterial[]>([])
const uploading = ref(false)
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

const fixedConfig: DeskPetConfig = {
  agent: 'dashboard',
  title: '犇犇 AI助手',
  intro: 'Hi~ 我是犇犇，有什么可以帮你？',
  summary: '我可以帮你整理想法、生成待办、润色文字，或回答办公系统相关问题。',
  actions: ['生成本周周报', '写一份出差报告', '整理今日待办', '润色一段文字'],
}


const currentConfig = computed(() => fixedConfig)
const shellClass = computed(() => [`desk-pet-shell`, `desk-pet-shell--${mode.value}`])
const panelWidth = computed(() => Math.min(320, Math.max(280, windowSize.value.width - 24)))
const panelHeight = computed(() => panelSize.value.height || 302)
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
  'desk-pet-panel--menu',
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

function sessionStorageKey() {
  return `desk-pet-agent-sessions:${props.userName || 'anonymous'}`
}

function visibleHistoryKey(kind = currentConfig.value.agent) {
  const lobsterKey = boundLobster.value ? `lobster:${boundLobster.value.agent_id}` : `agent:${kind}`
  return `desk-pet-visible-history:${props.userName || 'anonymous'}:${lobsterKey}`
}

function normalizeVisibleMessages(items: AgentMessage[]) {
  const cleaned = items
    .filter((item) => (item.role === 'user' || item.role === 'assistant') && String(item.content || '').trim())
    .map((item) => ({ role: item.role, content: String(item.content) }))
  return cleaned.length ? cleaned : [initialMessage()]
}

function saveVisibleHistory() {
  localStorage.setItem(visibleHistoryKey(), JSON.stringify(messages.value.slice(-100)))
}

function loadVisibleHistory() {
  const raw = localStorage.getItem(visibleHistoryKey())
  if (!raw) {
    resetMessages()
    return
  }
  try {
    const parsed = JSON.parse(raw) as AgentMessage[]
    messages.value = normalizeVisibleMessages(Array.isArray(parsed) ? parsed : [])
  } catch {
    localStorage.removeItem(visibleHistoryKey())
    resetMessages()
  }
}

async function loadChatHistory(force = false) {
  const kind = currentConfig.value.agent
  const key = visibleHistoryKey(kind)
  if (!force && historyLoadedKey.value === key) return
  historyLoadedKey.value = key
  if (boundLobster.value) {
    loadVisibleHistory()
    await nextTick()
    scrollMessagesToBottom()
    return
  }
  const sessionId = agentSessionIds.value[kind]
  if (!sessionId) {
    loadVisibleHistory()
    await nextTick()
    scrollMessagesToBottom()
    return
  }
  try {
    const result = await getAgentSession(sessionId)
    if (result.ok && result.messages?.length) {
      messages.value = normalizeVisibleMessages(result.messages)
      saveVisibleHistory()
    } else {
      loadVisibleHistory()
    }
  } catch {
    loadVisibleHistory()
  }
  await nextTick()
  scrollMessagesToBottom()
}

function loadAgentSessions() {
  const raw = localStorage.getItem(sessionStorageKey())
  if (!raw) {
    agentSessionIds.value = {}
    return
  }
  try {
    const parsed = JSON.parse(raw) as Partial<Record<AgentKind, string>>
    agentSessionIds.value = parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    localStorage.removeItem(sessionStorageKey())
    agentSessionIds.value = {}
  }
}

function saveAgentSession(kind: AgentKind, sessionId?: string) {
  if (!sessionId) return
  agentSessionIds.value = { ...agentSessionIds.value, [kind]: sessionId }
  localStorage.setItem(sessionStorageKey(), JSON.stringify(agentSessionIds.value))
}

async function loadBinding() {
  try {
    const result = await getAssistantLobster()
    boundLobster.value = result.ok ? result.lobster : null
  } catch {
    boundLobster.value = null
  } finally {
    historyLoadedKey.value = ''
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

function startNewChat() {
  const kind = currentConfig.value.agent
  if (!boundLobster.value) {
    const nextSessions = { ...agentSessionIds.value }
    delete nextSessions[kind]
    agentSessionIds.value = nextSessions
    localStorage.setItem(sessionStorageKey(), JSON.stringify(nextSessions))
  }
  localStorage.removeItem(visibleHistoryKey(kind))
  historyLoadedKey.value = ''
  attachedFiles.value = []
  resetMessages()
  void nextTick(scrollMessagesToBottom)
}

function openChat() {
  setMode('chat')
  void loadChatHistory()
  nextTick(() => {
    measurePanel()
    constrainPosition()
  })
}

async function sendAction(text: string) {
  inputText.value = ''
  setMode('chat')
  await nextTick()
  await loadChatHistory()
  await sendMessage(text)
}

async function sendMessage(text = inputText.value) {
  const content = text.trim()
  if (!content || loading.value) return
  if (boundLobster.value && attachedFiles.value.length) {
    messages.value.push({ role: 'assistant', content: '当前绑定的龙虾暂不支持读取本地附件。请先解除绑定后使用犇犇识别文件内容。' })
    return
  }
  setMode('chat')
  const fileIds = attachedFiles.value.map((item) => item.id)
  const displayContent = fileIds.length ? `${content}\n\n已附带文件：${attachedFiles.value.map((item) => item.name).join('、')}` : content
  messages.value.push({ role: 'user', content: displayContent })
  saveVisibleHistory()
  inputText.value = ''
  loading.value = true
  try {
    if (boundLobster.value) {
      // 已绑定龙虾：对话直通该龙虾（多轮由后端固定 session 维持连续）。
      const result = await lobsterChat(content)
      if (!result.ok) throw new Error(result.error || '龙虾暂时不可用')
      messages.value.push({ role: 'assistant', content: result.reply || '（龙虾没有返回内容）' })
      saveVisibleHistory()
    } else {
      const agentKind = currentConfig.value.agent
      const payloadMessages: AgentMessage[] = [{ role: 'user', content }]
      const result = await agentChat(agentKind, payloadMessages, agentSessionIds.value[agentKind], fileIds)
      if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
      saveAgentSession(agentKind, result.session_id)
      messages.value.push({ role: 'assistant', content: result.reply || '我已经看过当前内容，暂时没有新的补充。' })
      saveVisibleHistory()
      attachedFiles.value = []
    }
  } catch (error) {
    messages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
    saveVisibleHistory()
  } finally {
    loading.value = false
    await nextTick()
    measurePanel()
    scrollMessagesToBottom()
  }
}

function pickFiles() {
  if (!loading.value && !uploading.value && !boundLobster.value) fileInputRef.value?.click()
}

function readFile(file: File) {
  return new Promise<{ name: string; data: string }>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({ name: file.name, data: String(reader.result || '') })
    reader.onerror = () => reject(new Error(`${file.name} 读取失败`))
    reader.readAsDataURL(file)
  })
}

async function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || uploading.value) return
  uploading.value = true
  try {
    const result = await uploadWritingFile(await Promise.all(files.map(readFile)))
    attachedFiles.value = [...attachedFiles.value, ...result.files].slice(-6)
  } catch (error) {
    messages.value.push({ role: 'assistant', content: error instanceof Error ? `文件识别失败：${error.message}` : '文件识别失败，请重试。' })
  } finally {
    uploading.value = false
  }
}

function removeAttachedFile(id: string) {
  attachedFiles.value = attachedFiles.value.filter((item) => item.id !== id)
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
  const list = chatDialogRef.value?.querySelector('.desk-pet-chat-messages')
  if (list) list.scrollTop = list.scrollHeight
}

function handleResize() {
  windowSize.value = { width: window.innerWidth, height: window.innerHeight }
  if (!hasPosition.value) defaultPosition()
  measurePanel()
  constrainPosition()
}

function handleOutsidePointerDown(event: PointerEvent) {
  if (mode.value === 'sleep' || mode.value === 'chat') return
  if (petRef.value?.contains(event.target as Node)) return
  if (panelRef.value?.contains(event.target as Node)) return
  sleep()
}

watch(
  () => props.userName,
  () => {
    loadAgentSessions()
    historyLoadedKey.value = ''
    loadVisibleHistory()
  },
)

watch(mode, () => nextTick(constrainPosition))
watch(mode, () => nextTick(measurePanel))
watch(panelWidth, () => nextTick(measurePanel))

onMounted(() => {
  windowSize.value = { width: window.innerWidth, height: window.innerHeight }
  loadAgentSessions()
  loadVisibleHistory()
  loadBinding().then(() => loadChatHistory(true))
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
    <section v-if="mode === 'menu'" ref="panelRef" :class="panelClass" :style="panelStyle">
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
      <template v-else-if="mode === 'menu'">
        <span class="desk-pet-sparkle desk-pet-sparkle--one"><el-icon><StarFilled /></el-icon></span>
        <span class="desk-pet-sparkle desk-pet-sparkle--two"><el-icon><StarFilled /></el-icon></span>
        <img class="desk-pet-active-image" :src="activePetImage" alt="" draggable="false" />
        <span class="desk-pet-online" aria-hidden="true"></span>
      </template>
    </button>
  </section>

  <Teleport to="body">
    <div v-if="mode === 'chat'" class="desk-pet-chat-backdrop" @pointerdown.self="sleep">
      <section ref="chatDialogRef" class="desk-pet-chat-dialog" role="dialog" aria-modal="true" aria-label="犇犇 AI 对话">
        <header class="desk-pet-chat-head">
          <div>
            <strong>{{ boundLobster ? `龙虾 · ${boundLobster.agent_name} #${boundLobster.agent_id}` : currentConfig.title }}</strong>
            <span>{{ boundLobster ? `已绑定龙虾，对话直通 ${boundLobster.agent_name} #${boundLobster.agent_id}` : '连续对话、报告起草与文件内容识别' }}</span>
          </div>
          <div class="desk-pet-chat-head-actions">
            <button type="button" title="开启新对话" aria-label="开启新对话" @click="startNewChat"><el-icon><Refresh /></el-icon></button>
            <button type="button" aria-label="关闭对话" @click="sleep"><el-icon><Close /></el-icon></button>
          </div>
        </header>
        <div class="desk-pet-chat-messages">
          <article v-for="(message, index) in messages" :key="index" :class="['desk-pet-message', message.role]">{{ message.content }}</article>
          <article v-if="loading" class="desk-pet-message assistant">{{ boundLobster ? '龙虾正在思考，请稍候…' : '正在思考...' }}</article>
        </div>
        <div class="desk-pet-chat-actions" aria-label="快捷任务">
          <button v-for="action in currentConfig.actions" :key="action" type="button" :disabled="loading" @click="sendAction(action)">{{ action }}</button>
        </div>
        <div v-if="attachedFiles.length" class="desk-pet-attachments" aria-label="已附带文件">
          <span v-for="file in attachedFiles" :key="file.id">{{ file.name }}<button type="button" aria-label="移除文件" @click="removeAttachedFile(file.id)"><el-icon><Close /></el-icon></button></span>
        </div>
        <form class="desk-pet-chat-input" @submit.prevent="sendMessage()">
          <textarea v-model="inputText" placeholder="输入问题，Ctrl/⌘ + Enter 发送；可附带文件让犇犇识别内容" @keydown.ctrl.enter.prevent="sendMessage()" @keydown.meta.enter.prevent="sendMessage()"></textarea>
          <input ref="fileInputRef" type="file" multiple hidden accept=".txt,.md,.csv,.log,.json,.html,.htm,.doc,.docx,.pdf,.xls,.xlsx,.ppt,.pptx,.wps" @change="handleFiles" />
          <button class="desk-pet-attach-button" type="button" :disabled="loading || uploading || !!boundLobster" :title="boundLobster ? '绑定龙虾时暂不支持本地附件' : '上传文件并识别内容'" aria-label="上传文件" @click="pickFiles"><el-icon><Paperclip /></el-icon></button>
          <button type="submit" :disabled="loading || uploading || !inputText.trim()"><el-icon><Position /></el-icon></button>
        </form>
        <p class="desk-pet-file-hint">支持 PDF、Word、Excel、PPT、WPS、文本等文件，单个文件最大 20MB。</p>
      </section>
    </div>
  </Teleport>
</template>
