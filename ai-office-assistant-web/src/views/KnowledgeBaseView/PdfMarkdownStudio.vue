<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Close, Delete, Document, Download, DocumentCopy, MagicStick, Picture, RefreshRight, UploadFilled,
} from '@element-plus/icons-vue'
import {
  createPdfMdJob,
  deletePdfMdJob,
  getPdfMdJob,
  listPdfMdJobs,
  parsePdfMdJob,
  pdfMdPageImageUrl,
  pdfMdToKnowledge,
  regionOcrPdfMd,
  savePdfMdMarkdown,
  type PdfMdJob,
  type PdfMdJobBrief,
  type PdfMdPage,
} from '../../services/personalWorkApi'
import { renderMarkdown } from '../../utils/markdown'

const props = defineProps<{ scope: string; scopeLabel: string; canWrite: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'stored'): void }>()

const jobs = ref<PdfMdJobBrief[]>([])
const job = ref<PdfMdJob | null>(null)
const markdown = ref('')
const dirty = ref(false)
const currentPage = ref(1)
const uploading = ref(false)
const saving = ref(false)
let parsePollTimer: ReturnType<typeof setTimeout> | null = null

const parsing = computed(() => job.value?.parse_status === 'running')
const parseProgress = computed(() => job.value?.parse_progress || 0)
const fileInputRef = ref<HTMLInputElement | null>(null)
const mdEditorRef = ref<HTMLTextAreaElement | null>(null)
const mdPreviewRef = ref<HTMLElement | null>(null)
const viewMode = ref<'split' | 'edit' | 'preview'>('split')

// ---- 绘图框取 ----
const overlayRef = ref<HTMLDivElement | null>(null)
const drawing = ref(false)
const rect = ref<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
const regionLoading = ref(false)
const regionResult = ref('')
const regionVisible = ref(false)

const pages = computed<PdfMdPage[]>(() => job.value?.pages || [])
const pageInfo = computed(() => pages.value.find((p) => p.page === currentPage.value) || null)
const renderedMarkdown = computed(() => renderMarkdown(markdown.value || ''))
const pageImage = computed(() => (job.value ? pdfMdPageImageUrl(job.value.id, currentPage.value) : ''))
const normRect = computed(() => {
  if (!rect.value) return null
  return {
    left: `${Math.min(rect.value.x0, rect.value.x1) * 100}%`,
    top: `${Math.min(rect.value.y0, rect.value.y1) * 100}%`,
    width: `${Math.abs(rect.value.x1 - rect.value.x0) * 100}%`,
    height: `${Math.abs(rect.value.y1 - rect.value.y0) * 100}%`,
  }
})

async function refreshJobs() {
  try {
    const res = await listPdfMdJobs()
    jobs.value = res.jobs || []
  } catch (err) {
    ElMessage.error((err as Error).message || '加载历史失败')
  }
}

async function loadJob(id: string) {
  try {
    const res = await getPdfMdJob(id)
    job.value = res.job
    markdown.value = res.job.markdown || ''
    dirty.value = false
    currentPage.value = 1
    resetRegion()
    if (res.job.parse_status === 'running') pollParse()
  } catch (err) {
    ElMessage.error((err as Error).message || '加载失败')
  }
}

function pickFile() {
  fileInputRef.value?.click()
}

async function onFileChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.warning('仅支持 PDF 文件')
    return
  }
  uploading.value = true
  try {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result || ''))
      reader.onerror = () => reject(new Error('读取文件失败'))
      reader.readAsDataURL(file)
    })
    const base64 = dataUrl.includes(',') ? dataUrl.split(',', 2)[1] : dataUrl
    const res = await createPdfMdJob(file.name, base64)
    job.value = res.job
    markdown.value = res.job.markdown || ''
    dirty.value = false
    currentPage.value = 1
    resetRegion()
    await refreshJobs()
    ElMessage.success('已上传并渲染页面，点击「OCR 整篇解析」用 DeepDoc 生成 Markdown')
  } catch (err) {
    ElMessage.error((err as Error).message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function runFullParse() {
  if (!job.value) return
  if (markdown.value.trim()) {
    try {
      await ElMessageBox.confirm('整篇解析会逐页 OCR 并用图文并茂结果覆盖当前 Markdown，是否继续？', '整篇 OCR 解析', { type: 'warning' })
    } catch {
      return
    }
  }
  try {
    const res = await parsePdfMdJob(job.value.id)
    job.value = res.job
    markdown.value = res.job.markdown || ''
    dirty.value = false
    pollParse()
  } catch (err) {
    ElMessage.error((err as Error).message || '无法启动 OCR 解析（请确认知识库引擎为 RAGFlow）')
  }
}

function stopPolling() {
  if (parsePollTimer) {
    clearTimeout(parsePollTimer)
    parsePollTimer = null
  }
}

function pollParse() {
  stopPolling()
  parsePollTimer = setTimeout(async () => {
    if (!job.value) return
    try {
      const res = await getPdfMdJob(job.value.id)
      const status = res.job.parse_status
      // 解析进行中：以服务端增量结果为准，不接受本地编辑覆盖。
      job.value = res.job
      markdown.value = res.job.markdown || ''
      dirty.value = false
      if (status === 'running') {
        pollParse()
      } else if (status === 'failed') {
        ElMessage.error(res.job.parse_error || 'OCR 解析失败')
        await refreshJobs()
      } else {
        ElMessage.success('图文并茂 Markdown 已生成')
        await refreshJobs()
      }
    } catch {
      pollParse()
    }
  }, 2000)
}

// ---- 页面导航 ----
function goPage(delta: number) {
  if (!job.value) return
  const next = currentPage.value + delta
  if (next < 1 || next > job.value.page_count) return
  currentPage.value = next
  resetRegion()
}

function syncMarkdownPreview(page: number) {
  const preview = mdPreviewRef.value
  if (!preview) return
  const heading = Array.from(preview.querySelectorAll('h2')).find((item) => item.textContent?.trim() === `第 ${page} 页`)
  if (!heading) return
  const top = preview.scrollTop + heading.getBoundingClientRect().top - preview.getBoundingClientRect().top
  preview.scrollTo({ top, behavior: 'smooth' })
}

// ---- 绘图框取交互 ----
function overlayPoint(event: MouseEvent) {
  const el = overlayRef.value
  if (!el) return { x: 0, y: 0 }
  const box = el.getBoundingClientRect()
  return {
    x: Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)),
    y: Math.min(1, Math.max(0, (event.clientY - box.top) / box.height)),
  }
}

function onDrawStart(event: MouseEvent) {
  if (event.button !== 0) return
  regionVisible.value = false
  regionResult.value = ''
  const p = overlayPoint(event)
  drawing.value = true
  rect.value = { x0: p.x, y0: p.y, x1: p.x, y1: p.y }
  window.addEventListener('mousemove', onDrawMove)
  window.addEventListener('mouseup', onDrawEnd)
}

function onDrawMove(event: MouseEvent) {
  if (!drawing.value || !rect.value) return
  const p = overlayPoint(event)
  rect.value = { ...rect.value, x1: p.x, y1: p.y }
}

function onDrawEnd() {
  drawing.value = false
  window.removeEventListener('mousemove', onDrawMove)
  window.removeEventListener('mouseup', onDrawEnd)
  if (rect.value && (Math.abs(rect.value.x1 - rect.value.x0) < 0.01 || Math.abs(rect.value.y1 - rect.value.y0) < 0.01)) {
    rect.value = null
  }
}

function resetRegion() {
  rect.value = null
  regionVisible.value = false
  regionResult.value = ''
  regionLoading.value = false
}

async function ocrRegion() {
  if (!job.value || !rect.value) return
  const r = {
    x0: Math.min(rect.value.x0, rect.value.x1),
    y0: Math.min(rect.value.y0, rect.value.y1),
    x1: Math.max(rect.value.x0, rect.value.x1),
    y1: Math.max(rect.value.y0, rect.value.y1),
  }
  regionLoading.value = true
  regionVisible.value = true
  regionResult.value = ''
  try {
    const res = await regionOcrPdfMd(job.value.id, currentPage.value, r)
    regionResult.value = res.markdown || ''
    if (!regionResult.value) ElMessage.info('该区域未识别出文字，可调整框选范围')
  } catch (err) {
    regionVisible.value = false
    ElMessage.error((err as Error).message || '区域 OCR 失败')
  } finally {
    regionLoading.value = false
  }
}

function insertRegion(mode: 'cursor' | 'append') {
  const text = regionResult.value.trim()
  if (!text) return
  const block = `\n\n${text}\n\n`
  if (mode === 'append') {
    markdown.value = `${markdown.value.replace(/\s+$/, '')}${block}`
  } else {
    const ta = mdEditorRef.value
    const pos = ta ? ta.selectionStart : markdown.value.length
    markdown.value = markdown.value.slice(0, pos) + block + markdown.value.slice(pos)
  }
  dirty.value = true
  resetRegion()
  ElMessage.success('已插入子 Markdown')
}

// ---- 保存 / 入库 / 导出 ----
async function save() {
  if (!job.value) return
  saving.value = true
  try {
    await savePdfMdMarkdown(job.value.id, markdown.value)
    dirty.value = false
    ElMessage.success('已保存')
  } catch (err) {
    ElMessage.error((err as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function storeToKnowledge() {
  if (!job.value) return
  if (!props.canWrite) {
    ElMessage.warning('当前知识库无写入权限')
    return
  }
  try {
    await ElMessageBox.confirm(`将校对后的 Markdown 存入「${props.scopeLabel}」知识库？`, '存入知识库', { type: 'info' })
  } catch {
    return
  }
  try {
    await pdfMdToKnowledge(job.value.id, markdown.value, props.scope)
    ElMessage.success('已存入知识库并开始解析')
    emit('stored')
  } catch (err) {
    ElMessage.error((err as Error).message || '入库失败')
  }
}

async function copyMarkdown() {
  try {
    await navigator.clipboard.writeText(markdown.value)
    ElMessage.success('已复制 Markdown')
  } catch {
    ElMessage.error('复制失败')
  }
}

function downloadMarkdown() {
  if (!job.value) return
  const blob = new Blob([markdown.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${job.value.filename.replace(/\.pdf$/i, '')}.md`
  a.click()
  URL.revokeObjectURL(url)
}

async function removeJob(id: string, event: Event) {
  event.stopPropagation()
  try {
    await ElMessageBox.confirm('删除该解析任务及其页面图片？', '删除任务', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deletePdfMdJob(id)
    if (job.value?.id === id) {
      job.value = null
      markdown.value = ''
    }
    await refreshJobs()
  } catch (err) {
    ElMessage.error((err as Error).message || '删除失败')
  }
}

function onMarkdownInput() {
  dirty.value = true
}

async function close() {
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('有未保存的修改，确定关闭吗？', '关闭', { type: 'warning' })
    } catch {
      return
    }
  }
  emit('close')
}

watch(currentPage, () => nextTick(() => {
  resetRegion()
  syncMarkdownPreview(currentPage.value)
}))
watch([renderedMarkdown, viewMode], () => nextTick(() => syncMarkdownPreview(currentPage.value)))

onMounted(refreshJobs)
onUnmounted(stopPolling)
</script>

<template>
  <div class="pm-overlay">
    <div class="pm-panel">
      <header class="pm-head">
        <div class="pm-title"><el-icon><Document /></el-icon> PDF 解析成 Markdown</div>
        <div class="pm-head-actions">
          <button class="pm-btn pm-btn--primary" :disabled="uploading" @click="pickFile">
            <el-icon><UploadFilled /></el-icon> {{ uploading ? '上传中…' : '上传 PDF' }}
          </button>
          <button class="pm-btn" title="关闭" @click="close"><el-icon><Close /></el-icon></button>
        </div>
        <input ref="fileInputRef" type="file" accept="application/pdf,.pdf" hidden @change="onFileChosen" />
      </header>

      <div class="pm-body">
        <!-- 历史任务侧栏 -->
        <aside class="pm-jobs">
          <h4>解析历史</h4>
          <p v-if="!jobs.length" class="pm-empty">还没有解析任务，上传 PDF 开始。</p>
          <ul>
            <li v-for="j in jobs" :key="j.id" :class="{ active: job?.id === j.id }" @click="loadJob(j.id)">
              <div class="pm-job-name" :title="j.filename">{{ j.filename }}</div>
              <div class="pm-job-meta">
                {{ j.page_count }} 页 ·
                <span :class="j.ocr_done ? 'ok' : 'todo'">{{ j.ocr_done ? 'OCR已解析' : '待OCR' }}</span>
              </div>
              <button class="pm-job-del" title="删除" @click="removeJob(j.id, $event)"><el-icon><Delete /></el-icon></button>
            </li>
          </ul>
        </aside>

        <!-- 左：页面 review + 绘图框取 -->
        <section class="pm-viewer">
          <template v-if="job">
            <div class="pm-viewer-bar">
              <div class="pm-pager">
                <button class="pm-btn" :disabled="currentPage <= 1" @click="goPage(-1)">上一页</button>
                <span>{{ currentPage }} / {{ job.page_count }}</span>
                <button class="pm-btn" :disabled="currentPage >= job.page_count" @click="goPage(1)">下一页</button>
              </div>
              <button class="pm-btn pm-btn--primary" :disabled="parsing" @click="runFullParse">
                <el-icon><RefreshRight /></el-icon>
                {{ parsing ? `OCR 解析中 ${job.parse_page}/${job.page_count}…` : 'OCR 整篇解析' }}
              </button>
            </div>
            <div v-if="parsing" class="pm-progress"><div class="pm-progress-bar" :style="{ width: parseProgress + '%' }"></div></div>
            <p class="pm-hint"><el-icon><Picture /></el-icon> 逐页 DeepDoc OCR 生成图文并茂 Markdown（含 PDF 内嵌图片）；对图文错配处，在页面上拖拽框选后点「OCR 此区域」生成子 Markdown 再插入。</p>
            <div class="pm-canvas-wrap">
              <div class="pm-canvas" :style="pageInfo ? { aspectRatio: `${pageInfo.width} / ${pageInfo.height}` } : {}">
                <img :src="pageImage" class="pm-page-img" draggable="false" alt="page" />
                <div
                  ref="overlayRef"
                  class="pm-overlay-draw"
                  @mousedown="onDrawStart"
                >
                  <div v-if="normRect" class="pm-rect" :style="normRect"></div>
                </div>
                <!-- 区域动作条 -->
                <div v-if="rect && !drawing" class="pm-region-actions" :style="{ top: normRect?.top, left: normRect?.left }">
                  <button class="pm-btn pm-btn--primary" :disabled="regionLoading" @click="ocrRegion">
                    <el-icon><MagicStick /></el-icon> {{ regionLoading ? '识别中…' : 'OCR 此区域' }}
                  </button>
                  <button class="pm-btn" @click="resetRegion">取消</button>
                </div>
              </div>
            </div>
            <!-- 区域结果 -->
            <div v-if="regionVisible" class="pm-region-result">
              <div class="pm-region-result-head">
                <strong>区域 OCR 结果</strong>
                <div>
                  <button class="pm-btn pm-btn--primary" :disabled="!regionResult" @click="insertRegion('cursor')">插入到光标处</button>
                  <button class="pm-btn" :disabled="!regionResult" @click="insertRegion('append')">追加到末尾</button>
                  <button class="pm-btn" @click="regionVisible = false">收起</button>
                </div>
              </div>
              <pre v-if="regionResult">{{ regionResult }}</pre>
              <p v-else-if="regionLoading" class="pm-empty">正在用 DeepDoc OCR 识别该区域…</p>
              <p v-else class="pm-empty">未识别出文字。</p>
            </div>
          </template>
          <div v-else class="pm-drop" @click="pickFile">
            <el-icon :size="46"><UploadFilled /></el-icon>
            <p>上传 PDF 开始解析</p>
            <span>DeepDoc OCR 生成 Markdown，左右对照 review，框选区域校准图文错配</span>
          </div>
        </section>

        <!-- 右：Markdown review / 编辑 -->
        <section class="pm-md" v-if="job">
          <div class="pm-md-bar">
            <div class="pm-seg">
              <button :class="{ active: viewMode === 'split' }" @click="viewMode = 'split'">对照</button>
              <button :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
              <button :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
            </div>
            <div class="pm-md-actions">
              <span v-if="dirty" class="pm-dirty">未保存</span>
              <button class="pm-btn" title="复制" @click="copyMarkdown"><el-icon><DocumentCopy /></el-icon></button>
              <button class="pm-btn" title="下载 .md" @click="downloadMarkdown"><el-icon><Download /></el-icon></button>
              <button class="pm-btn pm-btn--primary" :disabled="saving || parsing" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
              <button class="pm-btn" :disabled="!canWrite || parsing" @click="storeToKnowledge">存入知识库</button>
            </div>
          </div>
          <div class="pm-md-panes" :class="`pm-md-panes--${viewMode}`">
            <textarea
              v-if="viewMode !== 'preview'"
              ref="mdEditorRef"
              v-model="markdown"
              class="pm-md-edit"
              spellcheck="false"
              :readonly="parsing"
              :placeholder="parsing ? '正在逐页解析，请稍候…' : 'Markdown 内容…'"
              @input="onMarkdownInput"
            ></textarea>
            <div v-if="viewMode !== 'edit'" ref="mdPreviewRef" class="pm-md-preview markdown-body" v-html="renderedMarkdown"></div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
$pm-primary: #15499c;

.pm-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(12, 24, 48, 0.55);
  display: flex;
  padding: 24px;
}
.pm-panel {
  margin: auto;
  width: min(1560px, 100%);
  height: 100%;
  background: #f5f7fb;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(10, 26, 60, 0.35);
}
.pm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: $pm-primary;
  color: #fff;
}
.pm-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.pm-head-actions { display: flex; align-items: center; gap: 10px; }

.pm-body { flex: 1; display: flex; min-height: 0; }
.pm-jobs {
  width: 210px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f4;
  background: #fff;
  padding: 12px;
  overflow: auto;
  h4 { margin: 0 0 8px; font-size: 13px; color: #64748b; }
  ul { list-style: none; margin: 0; padding: 0; }
  li {
    position: relative;
    padding: 8px 26px 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    margin-bottom: 4px;
    &:hover { background: #eef3fb; }
    &.active { background: #e5edfb; box-shadow: inset 0 0 0 1px #bcd0f5; }
  }
  .pm-job-name { font-size: 13px; color: #1f2d3d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pm-job-meta { font-size: 11px; color: #94a3b8; margin-top: 2px; .ok { color: #16a34a; } .todo { color: #d97706; } }
  .pm-job-del {
    position: absolute; top: 6px; right: 4px; border: none; background: transparent;
    color: #cbd5e1; cursor: pointer; padding: 3px;
    &:hover { color: #ef4444; }
  }
}

.pm-viewer {
  flex: 1.05;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  overflow: auto;
  border-right: 1px solid #e2e8f4;
}
.pm-viewer-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.pm-pager { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #475569; }
.pm-hint { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748b; margin: 0 0 10px; }
.pm-progress { height: 6px; background: #e6edf8; border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
.pm-progress-bar { height: 100%; background: $pm-primary; transition: width 0.3s ease; }
.pm-md-preview :deep(img) { max-width: 100%; height: auto; border-radius: 6px; margin: 6px 0; }
.pm-canvas-wrap { display: flex; justify-content: center; }
.pm-canvas {
  position: relative;
  width: 100%;
  max-width: 760px;
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 40, 90, 0.12);
}
.pm-page-img { display: block; width: 100%; user-select: none; }
.pm-overlay-draw { position: absolute; inset: 0; cursor: crosshair; }
.pm-rect {
  position: absolute;
  border: 2px solid $pm-primary;
  background: rgba(21, 73, 156, 0.14);
  pointer-events: none;
}
.pm-region-actions {
  position: absolute;
  transform: translateY(-110%);
  display: flex;
  gap: 6px;
  z-index: 5;
}
.pm-region-result {
  margin-top: 12px;
  background: #fff;
  border: 1px solid #e2e8f4;
  border-radius: 10px;
  padding: 10px 12px;
  pre { white-space: pre-wrap; word-break: break-word; font-size: 12.5px; margin: 8px 0 0; max-height: 220px; overflow: auto; background: #f8fafc; padding: 8px; border-radius: 6px; }
}
.pm-region-result-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; div { display: flex; gap: 6px; } }

.pm-md { flex: 1; min-width: 0; display: flex; flex-direction: column; padding: 12px 14px; }
.pm-md-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.pm-seg {
  display: inline-flex; background: #e8eef8; border-radius: 8px; padding: 2px;
  button { border: none; background: transparent; padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; color: #475569;
    &.active { background: #fff; color: $pm-primary; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.08); } }
}
.pm-md-actions { display: flex; align-items: center; gap: 8px; }
.pm-dirty { font-size: 12px; color: #d97706; }
.pm-md-panes { flex: 1; display: flex; gap: 10px; min-height: 0; }
.pm-md-panes--split .pm-md-edit, .pm-md-panes--split .pm-md-preview { width: 50%; }
.pm-md-panes--edit .pm-md-edit, .pm-md-panes--preview .pm-md-preview { width: 100%; }
.pm-md-edit {
  flex: 1; resize: none; border: 1px solid #d7e0f0; border-radius: 10px; padding: 12px;
  font-family: 'JetBrains Mono', Consolas, monospace; font-size: 13px; line-height: 1.6; color: #1f2d3d;
  &:focus { outline: none; border-color: $pm-primary; }
}
.pm-md-preview {
  flex: 1; overflow: auto; background: #fff; border: 1px solid #e2e8f4; border-radius: 10px; padding: 14px 18px;
}

.pm-drop {
  margin: auto; text-align: center; color: #94a3b8; cursor: pointer;
  padding: 40px; border: 2px dashed #c6d4ec; border-radius: 14px; background: #fff;
  p { font-size: 16px; color: #475569; margin: 12px 0 4px; }
  span { font-size: 12px; }
  &:hover { border-color: $pm-primary; }
}
.pm-empty { color: #94a3b8; font-size: 13px; }

.pm-btn {
  display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid #d0dbef; background: #fff; color: #33507f;
  padding: 6px 12px; border-radius: 8px; cursor: pointer; font-size: 13px;
  &:hover:not(:disabled) { border-color: $pm-primary; color: $pm-primary; }
  &:disabled { opacity: 0.55; cursor: not-allowed; }
}
.pm-btn--primary { background: $pm-primary; border-color: $pm-primary; color: #fff;
  &:hover:not(:disabled) { background: #103a80; color: #fff; } }
</style>
