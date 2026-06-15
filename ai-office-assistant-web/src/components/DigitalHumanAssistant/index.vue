<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { resourceUrl } from '../../services/personalWorkApi'
import benbenImage from '../../assets/benben.png'
import './index.scss'

defineProps<{
  userName: string
}>()

const POSITION_KEY = 'digital-human-position'
const BUTTON_SIZE = 64

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)
const chatHidden = ref(false)
const frameLoaded = ref(false)
const frameRef = ref<HTMLIFrameElement | null>(null)
const pageUrl = resourceUrl('/digital-human/')
// 面板打开前 iframe 不加载，避免每次进入工作台都下载 3D 模型。
const frameSrc = ref('')
// 头像按钮位置（左上角坐标）；null 表示使用默认右下角。
const position = ref<{ x: number; y: number } | null>(null)
// 面板展开方向：根据按钮所处屏幕象限自动选择。
const panelBelow = ref(false)
const panelLeftAlign = ref(false)
let pendingText = ''
let dragStart: { pointerId: number; x: number; y: number; left: number; top: number; moved: boolean } | null = null
let ignoreNextClick = false

const rootStyle = computed(() => {
  if (!position.value) return {}
  return {
    left: `${position.value.x}px`,
    top: `${position.value.y}px`,
    right: 'auto',
    bottom: 'auto',
  }
})

const panelClass = computed(() => [
  'digital-human-panel',
  {
    'digital-human-panel--mini': chatHidden.value,
    'digital-human-panel--below': panelBelow.value,
    'digital-human-panel--left': panelLeftAlign.value,
  },
])

function buttonRect() {
  if (position.value) {
    return { left: position.value.x, top: position.value.y }
  }
  const rect = rootRef.value?.getBoundingClientRect()
  return { left: rect?.left ?? window.innerWidth - 90, top: rect?.top ?? window.innerHeight - 90 }
}

function updatePanelPlacement() {
  const { left, top } = buttonRect()
  // 按钮在屏幕下半区向上展开、上半区向下展开；左半区面板左对齐按钮，右半区右对齐。
  panelBelow.value = top + BUTTON_SIZE / 2 < window.innerHeight / 2
  panelLeftAlign.value = left + BUTTON_SIZE / 2 < window.innerWidth / 2
}

function wake() {
  if (!open.value) {
    updatePanelPlacement()
    open.value = true
    if (!frameSrc.value) frameSrc.value = pageUrl
  }
}

function close() {
  open.value = false
}

function handleToggleClick() {
  if (ignoreNextClick) {
    ignoreNextClick = false
    return
  }
  open.value ? close() : wake()
}

// ---------------------------------------------------------------------------
// 全屏拖拽
// ---------------------------------------------------------------------------
function clampPosition(x: number, y: number) {
  return {
    x: Math.min(Math.max(4, x), Math.max(4, window.innerWidth - BUTTON_SIZE - 4)),
    y: Math.min(Math.max(4, y), Math.max(4, window.innerHeight - BUTTON_SIZE - 4)),
  }
}

function startDrag(event: PointerEvent) {
  if (event.button !== 0) return
  const rect = rootRef.value?.getBoundingClientRect()
  if (!rect) return
  dragStart = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false }
  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
}

function onDrag(event: PointerEvent) {
  if (!dragStart || event.pointerId !== dragStart.pointerId) return
  const deltaX = event.clientX - dragStart.x
  const deltaY = event.clientY - dragStart.y
  if (Math.abs(deltaX) + Math.abs(deltaY) > 5) dragStart.moved = true
  if (!dragStart.moved) return
  position.value = clampPosition(dragStart.left + deltaX, dragStart.top + deltaY)
  updatePanelPlacement()
}

function stopDrag(event: PointerEvent) {
  if (dragStart && event.pointerId === dragStart.pointerId) {
    ignoreNextClick = dragStart.moved
    if (dragStart.moved && position.value) {
      try {
        localStorage.setItem(POSITION_KEY, JSON.stringify(position.value))
      } catch {
        /* 存储不可用时位置仅当次生效 */
      }
    }
  }
  dragStart = null
  window.removeEventListener('pointermove', onDrag)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
}

function restorePosition() {
  try {
    const raw = localStorage.getItem(POSITION_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as { x: number; y: number }
    if (typeof saved?.x === 'number' && typeof saved?.y === 'number') {
      position.value = clampPosition(saved.x, saved.y)
    }
  } catch {
    /* ignore */
  }
}

function handleResize() {
  if (position.value) position.value = clampPosition(position.value.x, position.value.y)
  updatePanelPlacement()
}

// ---------------------------------------------------------------------------
// 与数字人页面的消息互通
// ---------------------------------------------------------------------------
function postToAvatar(text: string) {
  const frameWindow = frameRef.value?.contentWindow
  if (!frameWindow) return false
  frameWindow.postMessage({ type: 'chengxi.ask', text }, '*')
  return true
}

function sendAction(text: string) {
  const content = text.trim()
  if (!content) return
  wake()
  nextTick(() => {
    if (!frameLoaded.value || !postToAvatar(content)) {
      pendingText = content
    }
  })
}

function handleFrameLoad() {
  frameLoaded.value = true
  if (pendingText) {
    const text = pendingText
    pendingText = ''
    postToAvatar(text)
  }
}

// 数字人页面隐藏对话框时同步收窄悬浮区，避免透明 iframe 挡住页面操作。
function handleFrameMessage(event: MessageEvent) {
  const data = event.data
  if (data && data.type === 'chengxi.layout') chatHidden.value = !!data.chatHidden
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) close()
}

// 桌宠形态没有关闭按钮：点击页面其他位置收起（iframe 内部点击不会冒泡到这里，不受影响）。
function handleOutsidePointerDown(event: PointerEvent) {
  if (!open.value) return
  if (rootRef.value?.contains(event.target as Node)) return
  close()
}

onMounted(() => {
  restorePosition()
  updatePanelPlacement()
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('pointerdown', handleOutsidePointerDown)
  window.addEventListener('message', handleFrameMessage)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('pointerdown', handleOutsidePointerDown)
  window.removeEventListener('message', handleFrameMessage)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('pointermove', onDrag)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
})

defineExpose({
  wake,
  sendAction,
})
</script>

<template>
  <section ref="rootRef" class="digital-human-assistant" :style="rootStyle" aria-label="犇犇 3D 数字人助手">
    <Transition name="digital-human-pop">
      <section v-show="open" :class="panelClass">
        <iframe
          v-if="frameSrc"
          ref="frameRef"
          class="digital-human-frame"
          :src="frameSrc"
          title="承希 3D 数字人"
          allow="microphone; autoplay"
          allowtransparency="true"
          @load="handleFrameLoad"
        ></iframe>
      </section>
    </Transition>

    <button
      class="digital-human-toggle"
      type="button"
      :aria-label="open ? '收起犇犇数字人' : '唤醒犇犇数字人'"
      :aria-expanded="open"
      @pointerdown="startDrag"
      @click="handleToggleClick"
    >
      <img :src="benbenImage" alt="" draggable="false" />
      <span class="digital-human-online" aria-hidden="true"></span>
    </button>
  </section>
</template>
