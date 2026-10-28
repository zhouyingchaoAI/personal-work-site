<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import quickTicketIcon from '../assets/quick-ticket-icon.png'
import { sidebarMenuItems } from '../layout/menu'
import { createTicket, uploadTicketAttachment, type ForumAttachment } from '../services/personalWorkApi'
import { authState } from '../services/authSession'
import { openWorkOrderPopup } from '../services/workOrderPopup'

type Point = { x: number; y: number }
type Mark = { points: Point[] }
const route = useRoute()
const floatingTools = ref<HTMLElement>()
const floatingPosition = ref<Point | null>(null)
const floatingStyle = computed(() => floatingPosition.value ? { left: `${floatingPosition.value.x}px`, top: `${floatingPosition.value.y}px`, right: 'auto', bottom: 'auto' } : {})
let pointerStart: Point | null = null
let origin: Point = { x: 0, y: 0 }
let dragged = false
const positionKey = 'quick-ticket-position-v1'
function constrainPosition(point: Point) {
  const rect = floatingTools.value?.getBoundingClientRect()
  return { x: Math.max(8, Math.min(point.x, window.innerWidth - (rect?.width || 180) - 8)), y: Math.max(8, Math.min(point.y, window.innerHeight - (rect?.height || 100) - 8)) }
}
function startDrag(event: PointerEvent) {
  if (event.button !== 0 || capturing.value) return
  const rect = floatingTools.value!.getBoundingClientRect()
  pointerStart = { x: event.clientX, y: event.clientY }
  origin = { x: rect.left, y: rect.top }
  dragged = false
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function moveDrag(event: PointerEvent) {
  if (!pointerStart) return
  const dx = event.clientX - pointerStart.x
  const dy = event.clientY - pointerStart.y
  if (Math.hypot(dx, dy) > 5) dragged = true
  if (dragged) floatingPosition.value = constrainPosition({ x: origin.x + dx, y: origin.y + dy })
}
function finishDrag() {
  pointerStart = null
  if (floatingPosition.value) {
    try { localStorage.setItem(positionKey, JSON.stringify(floatingPosition.value)) } catch {}
  }
}
function clickFloating(event: MouseEvent) {
  if (dragged) { event.preventDefault(); event.stopPropagation(); dragged = false }
}
function resizeFloating() {
  if (floatingPosition.value) floatingPosition.value = constrainPosition(floatingPosition.value)
}
onMounted(() => {
  try {
    const saved = JSON.parse(localStorage.getItem(positionKey) || 'null')
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) floatingPosition.value = constrainPosition(saved)
  } catch {}
  window.addEventListener('resize', resizeFloating)
})
onUnmounted(() => window.removeEventListener('resize', resizeFloating))
const enabled = computed(() => !!authState.user && route.path.startsWith('/workspace'))
const visible = ref(false)
const capturing = ref(false)
const submitting = ref(false)
const canvas = ref<HTMLCanvasElement>()
const screenshot = ref(false)
const moduleName = ref('')
const title = ref('')
const description = ref('')
const location = ref('')
const pagePath = ref('')
const capturedAt = ref('')
const captureError = ref('')
const marks = ref<Mark[]>([])
let base: HTMLCanvasElement | null = null
let active: Mark | null = null
let attachment: ForumAttachment | null = null
const crops = ref<{ url: string; source: HTMLCanvasElement; attachment?: ForumAttachment }[]>([])
const modules = [...new Set([...sidebarMenuItems.map(item => item.label), '平台整体 / 其他'])]
watch(() => authState.user?.username, () => {
  visible.value = false
  description.value = ''
  removeScreenshot()
})

function redraw() {
  const target = canvas.value
  const context = target?.getContext('2d')
  if (!target || !context || !base) return
  context.clearRect(0, 0, target.width, target.height)
  context.drawImage(base, 0, 0)
  context.strokeStyle = '#ed3548'
  context.lineWidth = 3
  context.lineCap = 'round'
  for (const mark of [...marks.value, ...(active ? [active] : [])]) {
    const first = mark.points[0]!
    const last = mark.points[mark.points.length - 1]!
    context.strokeRect(first.x, first.y, last.x - first.x, last.y - first.y)
  }
}
function point(event: PointerEvent): Point {
  const rect = canvas.value!.getBoundingClientRect()
  return { x: (event.clientX - rect.left) * canvas.value!.width / rect.width, y: (event.clientY - rect.top) * canvas.value!.height / rect.height }
}
function start(event: PointerEvent) {
  if (submitting.value || event.button !== 0) return
  canvas.value!.setPointerCapture(event.pointerId)
  active = { points: [point(event)] }
  redraw()
}
function move(event: PointerEvent) {
  if (!active) return
  active.points[1] = point(event)
  redraw()
}
function finish() {
  if (!active) return
  const first = active.points[0]!
  const last = active.points[active.points.length - 1]!
  const left = Math.max(0, Math.floor(Math.min(first.x, last.x)))
  const top = Math.max(0, Math.floor(Math.min(first.y, last.y)))
  const right = Math.min(base?.width || 0, Math.ceil(Math.max(first.x, last.x)))
  const bottom = Math.min(base?.height || 0, Math.ceil(Math.max(first.y, last.y)))
  if (!base || right - left < 3 || bottom - top < 3) { active = null; redraw(); return }
  const source = document.createElement('canvas')
  source.width = right - left
  source.height = bottom - top
  source.getContext('2d')!.drawImage(base, left, top, source.width, source.height, 0, 0, source.width, source.height)
  crops.value.push({ source, url: source.toDataURL('image/png') })
  marks.value.push(active)
  active = null
  attachment = null
  redraw()
}
function undo() { marks.value.pop(); crops.value.pop(); attachment = null; redraw() }
function removeScreenshot() { screenshot.value = false; base = null; marks.value = []; crops.value = []; attachment = null }
async function setScreenshot(source: HTMLCanvasElement) {
  base = source
  marks.value = []
  crops.value = []
  attachment = null
  screenshot.value = true
  await nextTick()
  if (canvas.value) { canvas.value.width = source.width; canvas.value.height = source.height; redraw() }
}
async function open() {
  if (capturing.value || submitting.value || visible.value) return
  capturing.value = true
  moduleName.value = sidebarMenuItems.find(item => item.id === route.params.menu)?.label || '平台整体 / 其他'
  const labels = Array.from(document.querySelectorAll<HTMLElement>('[role="tab"][aria-selected="true"], .ba-dashboard-nav button.active, .ba-dashboard-nav button.is-active'))
    .filter(element => element.getClientRects().length)
    .map(element => element.innerText.trim().replace(/^\d+\s*/, ''))
  location.value = [...new Set([moduleName.value, ...labels])].join(' / ')
  pagePath.value = window.location.pathname
  capturedAt.value = new Date().toLocaleString('zh-CN')
  title.value = `${location.value}：问题反馈`.slice(0, 120)
  description.value = ''
  captureError.value = ''
  removeScreenshot()
  try {
    const { default: html2canvas } = await import('html2canvas-pro')
    base = await html2canvas(document.body, {
      scale: 1, width: window.innerWidth, height: window.innerHeight,
      x: window.scrollX, y: window.scrollY, useCORS: true, logging: false,
      ignoreElements: element => element.hasAttribute('data-quick-ticket') || element.matches('input[type="password"], [data-private]'),
    })
  } catch {
    captureError.value = '自动截图失败，可选择本地截图，或直接填写文字提交。'
  } finally {
    visible.value = true
    capturing.value = false
    if (base) await setScreenshot(base)
  }
}
async function chooseImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) return void ElMessage.warning('请选择不超过10MB的PNG、JPEG或WebP截图')
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    const source = document.createElement('canvas')
    const scale = Math.min(1, 2400 / Math.max(image.width, image.height))
    source.width = Math.round(image.width * scale); source.height = Math.round(image.height * scale)
    source.getContext('2d')!.drawImage(image, 0, 0, source.width, source.height)
    await setScreenshot(source)
    captureError.value = ''
  } catch { ElMessage.error('图片读取失败') } finally { URL.revokeObjectURL(url) }
}
async function submit() {
  if (submitting.value) return
  if (!moduleName.value || !title.value.trim() || !description.value.trim()) return void ElMessage.warning('请填写所属助手、标题和问题描述')
  submitting.value = true
  try {
    if (screenshot.value && canvas.value && !attachment) {
      const blob = await new Promise<Blob>((resolve, reject) => canvas.value!.toBlob(value => value ? resolve(value) : reject(new Error('截图导出失败')), 'image/png'))
      attachment = (await uploadTicketAttachment(new File([blob], `工单截图-${Date.now()}.png`, { type: 'image/png' }))).attachment
    }
    for (const [index, crop] of crops.value.entries()) {
      if (crop.attachment) continue
      const blob = await new Promise<Blob>((resolve, reject) => crop.source.toBlob(value => value ? resolve(value) : reject(new Error('子图导出失败')), 'image/png'))
      crop.attachment = (await uploadTicketAttachment(new File([blob], `工单局部-${index + 1}-${Date.now()}.png`, { type: 'image/png' }))).attachment
    }
    const body = `${description.value.trim()}\n\n【页面定位】\n助手：${moduleName.value}\n导航：${location.value}\n页面：${pagePath.value}\n截图时间：${capturedAt.value}`
    const images = attachment ? [attachment, ...crops.value.map(crop => crop.attachment!)] : []
    const result = await createTicket(title.value.trim(), body + (images.length ? `\n截图附件：1张全景图、${crops.value.length}张局部图（按框选顺序）` : ''), moduleName.value, images)
    visible.value = false
    removeScreenshot()
    const notice = ElNotification({
      title: '工单提交成功', type: 'success', duration: 10000,
      message: h('div', [h('p', '可在工单系统查看内容和处理进度。'), h('button', {
        type: 'button', class: 'el-button el-button--primary el-button--small',
        onClick: () => { notice.close(); openWorkOrderPopup(result.ticket.id) },
      }, '查看工单')]),
    })
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '提交失败，已保留填写内容，请重试') } finally { submitting.value = false }
}
</script>

<style scoped>
.quick-ticket-floating{position:fixed;right:24px;bottom:42px;z-index:2100;display:flex;flex-direction:column;align-items:flex-end;gap:5px;max-width:calc(100vw - 16px)}
.quick-ticket-floating .quick-ticket-fab,.quick-ticket-floating .quick-ticket-mine{position:static;margin:0}
.quick-ticket-drag{border:1px solid #d5e3f4;border-radius:8px;padding:2px 9px;background:#f4f8ff;color:#526b87;font:inherit;font-size:11px;cursor:grab;touch-action:none;user-select:none}
.quick-ticket-drag:active{cursor:grabbing}
.quick-ticket-floating .quick-ticket-fab{touch-action:none;user-select:none}
</style>

<template>
  <div v-if="enabled" data-quick-ticket>
    <div ref="floatingTools" v-show="!visible" class="quick-ticket-floating" :style="floatingStyle" @click.capture="clickFloating">
      <button class="quick-ticket-drag" type="button" title="拖动调整位置" aria-label="拖动工单按钮" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="finishDrag" @pointercancel="finishDrag">⠿ 拖动</button>
    <button v-show="!visible" class="quick-ticket-fab" type="button" :disabled="capturing" :aria-busy="capturing" aria-label="截图并快速提交工单" title="点击提交工单，按住拖动调整位置" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="finishDrag" @pointercancel="finishDrag" @dragstart.prevent @click="open"><img :src="quickTicketIcon" alt="" width="48" height="48" /><span>{{ capturing ? '截图中…' : '快速工单' }}</span></button>
    <button v-show="!visible" class="quick-ticket-mine" type="button" @click="openWorkOrderPopup()">我的工单 · 查看进度</button>
    </div>
    <el-dialog v-model="visible" title="快速工单 · 截图反馈" width="min(1100px, 96vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!submitting" :show-close="!submitting" class="quick-ticket-dialog">
      <div data-quick-ticket class="quick-ticket-content">
        <p class="quick-ticket-notice">截图仅包含当前可见页面，可能含业务信息；请检查后再提交。截图在提交时才上传，跨域图片或视频可能无法截取。</p>
        <div class="quick-ticket-grid">
          <section class="quick-ticket-preview" aria-label="截图标记">
            <div class="quick-ticket-tools">
              <span>矩形框选 · 拖动标记问题位置</span>
              <el-button size="small" :disabled="!marks.length || submitting" @click="undo">撤销</el-button>
              <el-button size="small" :disabled="!screenshot || submitting" @click="removeScreenshot">移除截图</el-button>
            </div>
            <div v-if="screenshot" class="quick-ticket-canvas"><canvas ref="canvas" aria-label="截图，拖动绘制矩形框" @pointerdown="start" @pointermove="move" @pointerup="finish" @pointercancel="finish" /></div>
            <div v-if="crops.length" class="quick-ticket-crops"><span>将随全景图提交 {{ crops.length }} 张局部图</span><figure v-for="(crop, index) in crops" :key="index"><el-image :src="crop.url" :preview-src-list="crops.map(item => item.url)" :initial-index="index" preview-teleported fit="contain" /><figcaption>局部 {{ index + 1 }}</figcaption></figure></div>
            <p v-else>{{ captureError || '未附截图，可仅提交文字，也可以选择本地截图。' }}</p>
            <label class="quick-ticket-file">选择本地截图<input type="file" accept="image/png,image/jpeg,image/webp" :disabled="submitting" @change="chooseImage" /></label>
          </section>
          <el-form label-position="top" :disabled="submitting">
            <el-form-item label="助手 / 模块" required><el-select v-model="moduleName" filterable aria-label="助手 / 模块"><el-option v-for="item in modules" :key="item" :label="item" :value="item" /></el-select></el-form-item>
            <p class="quick-ticket-location">当前导航：{{ location }}</p>
            <el-form-item label="工单标题" required><el-input v-model="title" maxlength="120" show-word-limit aria-label="工单标题" /></el-form-item>
            <el-form-item label="问题描述" required><el-input v-model="description" type="textarea" :rows="7" maxlength="10000" show-word-limit placeholder="哪里有问题？期望什么效果？可在左侧截图标记位置。" aria-label="问题描述" /></el-form-item>
            <p class="quick-ticket-location">页面位置、时间和截图标注将自动附加工单，无需重复填写。</p>
          </el-form>
        </div>
      </div>
      <template #footer><el-button :disabled="submitting" @click="visible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">提交工单</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.quick-ticket-fab { position:fixed;right:24px;bottom:88px;z-index:2100;display:flex;align-items:center;gap:8px;padding:5px 15px 5px 5px;border:1px solid #c3dcf9;border-radius:18px;background:linear-gradient(135deg,#fff,#edf6ff);color:#194b87;font-family:inherit;font-size:14px;font-weight:600;line-height:1.4;box-shadow:0 6px 22px #16457e35;cursor:pointer;transition:transform .15s,box-shadow .15s; }
.quick-ticket-fab img { width:48px;height:48px;object-fit:contain; }
.quick-ticket-mine { position:fixed;right:24px;bottom:52px;z-index:2100;border:1px solid #c3dcf9;border-radius:16px;padding:6px 12px;background:#fff;color:#194b87;cursor:pointer; }
.quick-ticket-fab:hover { transform:translateY(-2px);box-shadow:0 8px 26px #16457e50; }
.quick-ticket-fab:focus-visible { outline:3px solid #3889e8;outline-offset:3px; }
.quick-ticket-fab:disabled { cursor:wait;opacity:.75; }
.quick-ticket-grid { display:grid;grid-template-columns:minmax(0,1.5fr) minmax(280px,1fr);gap:24px; }
.quick-ticket-notice,.quick-ticket-location { color:var(--el-text-color-secondary);font-size:13px;line-height:1.6; }
.quick-ticket-preview { min-width:0;background:var(--el-fill-color-light);border:1px solid var(--el-border-color);border-radius:12px;padding:12px; }
.quick-ticket-tools { display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px; }
.quick-ticket-canvas { max-height:55vh;overflow:auto;margin:12px 0; }
.quick-ticket-canvas canvas { width:100%;height:auto;display:block;touch-action:none;cursor:crosshair; }
.quick-ticket-crops { display:flex;flex-wrap:wrap;gap:8px;align-items:center; }.quick-ticket-crops>span { width:100%;font-size:12px;color:#617998; }.quick-ticket-crops figure { margin:0; }.quick-ticket-crops .el-image { width:100px;height:65px;border:1px solid #c3dcf9;border-radius:6px;cursor:zoom-in; }.quick-ticket-crops figcaption { font-size:12px;color:#617998;text-align:center; }
.quick-ticket-file { display:block;font-size:13px; }
.quick-ticket-file input { display:block;margin-top:8px;max-width:100%; }
@media(max-width:750px) { .quick-ticket-grid { grid-template-columns:minmax(0,1fr);gap:16px; }.quick-ticket-fab { right:12px;bottom:76px; }.quick-ticket-canvas { max-height:35vh; } }
</style>
