<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, CopyDocument, Delete, Document, Download, EditPen, MagicStick, UploadFilled } from '@element-plus/icons-vue'
import {
  deleteWritingHistory,
  deleteWritingUpload,
  exportWritingDraft,
  generateWritingDraft,
  generateWritingOutline,
  getWritingHistory,
  getWritingHistoryItem,
  getWritingTemplates,
  getWritingUploads,
  getReports,
  listKnowledgeKbs,
  rewriteWritingDraft,
  saveWritingTemplate,
  uploadWritingFile,
  writingDownloadUrl,
  type KnowledgeKb,
  type ReportFile,
  type WritingHistoryItem,
  type WritingMaterial,
  type WritingSource,
  type WritingTemplate,
} from '../../services/personalWorkApi'
import { renderMarkdown } from '../../utils/markdown'
import { authState } from '../../services/authSession'
import './index.scss'

// 正文/大纲的展示模式：阅读（渲染 Markdown）或编辑（纯文本框）。
const contentView = ref<'read' | 'edit'>('read')
const outlineView = ref<'read' | 'edit'>('read')

const writingTypes = ref<string[]>([])
const templates = ref<WritingTemplate[]>([])
const history = ref<WritingHistoryItem[]>([])
const materials = ref<WritingMaterial[]>([])
const selectedMaterialIds = ref<string[]>([])
const materialsExpanded = ref(false)
const reports = ref<ReportFile[]>([])
const selectedReportRefs = ref<Array<{ kind: 'weekly' | 'trip'; name: string }>>([])
const kbs = ref<KnowledgeKb[]>([])
const selectedKbIds = ref<string[]>([])
const expandedKbIds = ref<string[]>([])
const selectedHistoryId = ref('')
const activeWritingPage = ref<'editor' | 'history'>('editor')
const fileInputRef = ref<HTMLInputElement | null>(null)
const loading = reactive({ init: false, upload: false, outline: false, generate: false, rewrite: false, export: false, history: false, template: false })
const sources = ref<WritingSource[]>([])
const statusText = ref('')
const draftStatus = ref('')
const WRITING_DRAFT_KEY = computed(() => `ai-office-writing-draft:${authState.user?.username || 'guest'}`)
let draftSaveTimer: number | undefined

const form = reactive({
  id: '',
  title: '',
  writing_type: '方案文档',
  audience: '',
  tone: '正式、清晰、可执行',
  length: '1200-2000字',
  requirements: '',
  outline: '',
  content: '',
  rewrite_instruction: '润色表达，使结构更清晰、语气更正式',
  use_knowledge: false,
  knowledge_top_k: 6,
})

const selectableKbs = computed(() => kbs.value.filter((item) => item.chunk_count > 0))
const knowledgeTree = computed(() => {
  const byParent = new Map<string, KnowledgeKb[]>()
  const ids = new Set(kbs.value.map((item) => item.id))
  for (const kb of kbs.value) {
    const parent = kb.parent_id && ids.has(kb.parent_id) ? kb.parent_id : ''
    byParent.set(parent, [...(byParent.get(parent) || []), kb])
  }
  const rows: Array<{ kb: KnowledgeKb; depth: number; hasChildren: boolean }> = []
  const visit = (parentId: string, depth: number) => {
    for (const kb of byParent.get(parentId) || []) {
      const children = byParent.get(kb.id) || []
      rows.push({ kb, depth, hasChildren: children.length > 0 })
      if (!children.length || expandedKbIds.value.includes(kb.id)) visit(kb.id, depth + 1)
    }
  }
  visit('', 0)
  return rows
})
const activeKbIds = computed(() => selectedKbIds.value.length ? selectedKbIds.value : selectableKbs.value.map((item) => item.id))
const visibleMaterials = computed(() => materialsExpanded.value ? materials.value : materials.value.slice(0, 3))
const selectedTemplate = ref('')
const canGenerate = computed(() => Boolean(form.title.trim() || form.requirements.trim() || selectedMaterialIds.value.length || selectedReportRefs.value.length))
const availableReports = computed(() => reports.value.filter((item) => item.kind === 'weekly' || item.kind === 'trip'))
const contentStats = computed(() => {
  const text = form.content.trim()
  return { characters: text.length, paragraphs: text ? text.split(/\n\s*\n/).filter(Boolean).length : 0 }
})

// 清洗模型偶发的「数字、」行号前缀与分隔线/标题后多余句号，保证阅读模式排版干净
// （后端已统一清洗，这里对历史遗留内容再兜底一次）。
function cleanMarkdown(text: string): string {
  return String(text || '')
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line
      .replace(/^(\s*)\d+[、]\s*/, '$1')
      .replace(/^(\s*[-*_]{3,})[。.\s]*$/, '$1')
      // 模型偶发在 Markdown 表格每行结尾追加句号，导致 GFM 表格无法被识别。
      .replace(/^(\s*\|.*\|)\s*[。．]\s*$/, '$1')
      .replace(/^(\s*#{1,6}\s+.*?)[。]\s*$/, '$1'))
    .filter((line) => !/^\s*#{1,6}[。.\s]*$/.test(line))
    .join('\n')
}

// 把 [知识库N] 行内引用渲染成醒目的角标。
function markCitations(html: string): string {
  return html.replace(/\[知识库(\d+)\]/g, '<span class="writing-cite">知识库$1</span>')
}

// 阅读模式下渲染成排版后的 HTML（标题/列表/加粗/表格），不再展示原始 Markdown。
const contentHtml = computed(() => markCitations(renderMarkdown(cleanMarkdown(form.content))))
const outlineHtml = computed(() => renderMarkdown(cleanMarkdown(form.outline)))

onMounted(() => {
  restoreDraft()
  loadInitialData()
})

onBeforeUnmount(() => {
  if (draftSaveTimer) window.clearTimeout(draftSaveTimer)
})

watch(form, () => scheduleDraftSave(), { deep: true })
watch(selectedKbIds, () => scheduleDraftSave(), { deep: true })
watch(selectedMaterialIds, () => scheduleDraftSave(), { deep: true })
watch(selectedReportRefs, () => scheduleDraftSave(), { deep: true })

function draftPayload() {
  return { form: { ...form }, selectedKbIds: selectedKbIds.value, selectedMaterialIds: selectedMaterialIds.value, selectedReportRefs: selectedReportRefs.value, savedAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
}

function scheduleDraftSave() {
  if (draftSaveTimer) window.clearTimeout(draftSaveTimer)
  draftSaveTimer = window.setTimeout(() => {
    try {
      localStorage.setItem(WRITING_DRAFT_KEY.value, JSON.stringify(draftPayload()))
      draftStatus.value = '草稿已自动保存'
    } catch {
      draftStatus.value = ''
    }
  }, 700)
}

function restoreDraft() {
  try {
    const saved = JSON.parse(localStorage.getItem(WRITING_DRAFT_KEY.value) || '{}')
    if (!saved.form || !Object.values(saved.form).some(Boolean)) return
    Object.assign(form, saved.form)
    selectedKbIds.value = Array.isArray(saved.selectedKbIds) ? saved.selectedKbIds : []
    selectedMaterialIds.value = Array.isArray(saved.selectedMaterialIds) ? saved.selectedMaterialIds : []
    selectedReportRefs.value = Array.isArray(saved.selectedReportRefs) ? saved.selectedReportRefs : []
    draftStatus.value = `已恢复本地草稿（${saved.savedAt || '刚刚'}）`
  } catch {
    // 本地草稿不可用时不影响正常写作。
  }
}

async function loadInitialData() {
  loading.init = true
  try {
    const [templateData, historyData, uploadData, kbData, reportData] = await Promise.all([
      getWritingTemplates(),
      getWritingHistory(),
      getWritingUploads().catch(() => ({ ok: false, files: [] as WritingMaterial[] })),
      listKnowledgeKbs().catch(() => ({ ok: false, provider: '', kbs: [] })),
      getReports().catch(() => ({ reports: [] as ReportFile[], latest_weekly: '', latest_trip: '' })),
    ])
    templates.value = templateData.templates || []
    writingTypes.value = templateData.types || []
    history.value = historyData.items || []
    materials.value = uploadData.files || []
    kbs.value = kbData.kbs || []
    reports.value = reportData.reports || []
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '智能写作初始化失败')
  } finally {
    loading.init = false
  }
}

// 生成/改写完成后从服务端重新拉取历史，作为乐观更新之外的兜底，
// 保证「文稿历史」始终与后端保存的记录一致。
async function refreshHistory() {
  try {
    const data = await getWritingHistory()
    history.value = data.items || []
  } catch {
    // 拉取失败时保留本地乐观更新的列表，不打断写作流程。
  }
}

function applyTemplate() {
  const template = templates.value.find((item) => item.id === selectedTemplate.value)
  if (!template) return
  form.writing_type = template.writing_type || form.writing_type
  form.requirements = [form.requirements, template.prompt].filter(Boolean).join('\n')
  ElMessage.success(`已应用模板：${template.name}`)
}

function toggleKbBranch(id: string) {
  expandedKbIds.value = expandedKbIds.value.includes(id)
    ? expandedKbIds.value.filter((item) => item !== id)
    : [...expandedKbIds.value, id]
}

async function handleSaveTemplate() {
  const name = await ElMessageBox.prompt('请输入模板名称', '保存模板', { inputValue: form.title ? `${form.title}模板` : `${form.writing_type}模板` })
  const value = String(name.value || '').trim()
  if (!value) return
  loading.template = true
  try {
    const result = await saveWritingTemplate({ name: value, writing_type: form.writing_type, prompt: form.requirements || form.outline || form.content })
    templates.value = [result.template, ...templates.value.filter((item) => item.id !== result.template.id)]
    selectedTemplate.value = result.template.id
    ElMessage.success('保存模板成功')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存模板失败')
  } finally {
    loading.template = false
  }
}

function pickFiles() {
  fileInputRef.value?.click()
}

async function readFile(file: File) {
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
  if (!files.length) return
  loading.upload = true
  try {
    const payload = await Promise.all(files.map(readFile))
    const result = await uploadWritingFile(payload)
    materials.value = [...result.files, ...materials.value]
    selectedMaterialIds.value = [...new Set([...result.files.map((item) => item.id), ...selectedMaterialIds.value])]
    ElMessage.success(`已上传 ${result.files.length} 个素材`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传素材失败')
  } finally {
    loading.upload = false
  }
}

function basePayload() {
  return {
    id: form.id || undefined,
    title: form.title,
    writing_type: form.writing_type,
    audience: form.audience,
    tone: form.tone,
    length: form.length,
    requirements: form.requirements,
    outline: form.outline,
    content: form.content,
    rewrite_instruction: form.rewrite_instruction,
    file_ids: selectedMaterialIds.value,
    report_refs: selectedReportRefs.value,
    use_knowledge: form.use_knowledge,
    kb_ids: form.use_knowledge ? activeKbIds.value : [],
    knowledge_top_k: form.knowledge_top_k,
  }
}

async function handleOutline() {
  loading.outline = true
  try {
    const result = await generateWritingOutline(basePayload())
    form.outline = result.outline || ''
    sources.value = result.sources || []
    statusText.value = `大纲已生成 · ${result.mode || 'api'}`
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成大纲失败')
  } finally {
    loading.outline = false
  }
}

async function handleGenerate() {
  if (!canGenerate.value) {
    ElMessage.warning('请先填写主题、要求或上传素材')
    return
  }
  loading.generate = true
  try {
    const result = await generateWritingDraft(basePayload())
    applyHistoryItem(result.item)
    history.value = [summaryOf(result.item), ...history.value.filter((item) => item.id !== result.item.id)]
    statusText.value = `正文已生成 · ${result.mode || 'api'}`
    void refreshHistory()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成正文失败')
  } finally {
    loading.generate = false
  }
}

async function handleRewrite() {
  if (!form.content.trim()) {
    ElMessage.warning('请先生成或粘贴正文')
    return
  }
  loading.rewrite = true
  try {
    const result = await rewriteWritingDraft(basePayload())
    applyHistoryItem(result.item)
    history.value = [summaryOf(result.item), ...history.value.filter((item) => item.id !== result.item.id)]
    statusText.value = `改写完成 · ${result.mode || 'api'}`
    void refreshHistory()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '改写失败')
  } finally {
    loading.rewrite = false
  }
}

function summaryOf(item: WritingHistoryItem): WritingHistoryItem {
  return { ...item, content_preview: (item.content || item.content_preview || '').slice(0, 240), content: undefined }
}

function applyHistoryItem(item: WritingHistoryItem) {
  form.id = item.id || ''
  form.title = item.title || ''
  form.writing_type = item.writing_type || form.writing_type
  form.requirements = item.requirements || ''
  form.outline = item.outline || ''
  form.content = item.content || item.content_preview || ''
  // 不覆盖已上传素材列表：素材由 uploads 持久化，始终展示用户上传的全部素材。
  sources.value = item.sources || []
  selectedHistoryId.value = item.id || ''
  contentView.value = 'read'
  outlineView.value = 'read'
}

async function handleDeleteMaterial(item: WritingMaterial) {
  try {
    await deleteWritingUpload(item.id)
    materials.value = materials.value.filter((entry) => entry.id !== item.id)
    selectedMaterialIds.value = selectedMaterialIds.value.filter((id) => id !== item.id)
    ElMessage.success('已删除素材')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除素材失败')
  }
}

async function loadHistoryItem(item: WritingHistoryItem) {
  loading.history = true
  try {
    const result = await getWritingHistoryItem(item.id)
    applyHistoryItem(result.item)
    activeWritingPage.value = 'editor'
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载历史失败')
  } finally {
    loading.history = false
  }
}

async function handleDeleteHistory(item: WritingHistoryItem) {
  try {
    await ElMessageBox.confirm(`确定删除《${item.title}》？删除后无法恢复。`, '删除文稿', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
    await deleteWritingHistory(item.id)
    history.value = history.value.filter((entry) => entry.id !== item.id)
    if (selectedHistoryId.value === item.id) selectedHistoryId.value = ''
    ElMessage.success('已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

async function copyContent() {
  await navigator.clipboard.writeText(form.content || '')
  ElMessage.success('已复制正文')
}

async function handleExport(format: 'md' | 'txt' | 'docx' | 'xlsx') {
  loading.export = true
  try {
    const result = await exportWritingDraft({ id: form.id || undefined, title: form.title, content: form.content, format })
    window.open(writingDownloadUrl(result.download_url), '_blank', 'noopener,noreferrer')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    loading.export = false
  }
}

function newDraft() {
  form.id = ''
  form.title = ''
  form.requirements = ''
  form.outline = ''
  form.content = ''
  form.audience = ''
  selectedMaterialIds.value = []
  selectedReportRefs.value = []
  sources.value = []
  selectedHistoryId.value = ''
  statusText.value = ''
  localStorage.removeItem(WRITING_DRAFT_KEY.value)
  draftStatus.value = '已新建空白文稿'
}
</script>

<template>
  <section class="writing-page">
    <header class="writing-header">
      <div class="writing-page-tabs">
        <button type="button" :class="{ active: activeWritingPage === 'editor' }" @click="activeWritingPage = 'editor'">写作编辑</button>
        <button type="button" :class="{ active: activeWritingPage === 'history' }" @click="activeWritingPage = 'history'">文稿历史 <em>{{ history.length }}</em></button>
      </div>
      <button v-if="activeWritingPage === 'editor'" class="writing-btn writing-btn--ghost" type="button" @click="newDraft">新建文稿</button>
    </header>

    <div v-if="activeWritingPage === 'editor'" class="writing-layout">
      <aside class="writing-panel writing-sidebar">
        <section class="writing-block">
          <h2><el-icon><EditPen /></el-icon> 写作配置</h2>
          <label>写作类型
            <select v-model="form.writing_type">
              <option v-for="type in writingTypes" :key="type" :value="type">{{ type }}</option>
            </select>
          </label>
          <label>主题 / 标题
            <input v-model="form.title" placeholder="例如：AI 智能办公平台建设方案" />
          </label>
          <label>目标读者
            <input v-model="form.audience" placeholder="例如：公司管理层、客户、项目组" />
          </label>
          <label>语气风格
            <input v-model="form.tone" placeholder="正式、简洁、专业" />
          </label>
          <label>篇幅要求
            <input v-model="form.length" placeholder="例如：1200-2000字" />
          </label>
          <label>补充要求
            <textarea v-model="form.requirements" rows="5" placeholder="写作目标、必须包含的信息、格式要求等"></textarea>
          </label>
        </section>

        <section class="writing-block">
          <h2><el-icon><Document /></el-icon> 模板</h2>
          <div class="writing-row">
            <select v-model="selectedTemplate" @change="applyTemplate">
              <option value="">选择模板</option>
              <option v-for="template in templates" :key="template.id" :value="template.id">{{ template.name }}</option>
            </select>
            <button class="writing-btn" type="button" :disabled="loading.template" @click="handleSaveTemplate">保存模板</button>
          </div>
        </section>

        <section class="writing-block">
          <h2><el-icon><UploadFilled /></el-icon> 上传素材</h2>
          <button class="writing-upload" type="button" :disabled="loading.upload" @click="pickFiles">
            {{ loading.upload ? '上传中...' : '上传素材' }}
          </button>
          <input ref="fileInputRef" type="file" multiple hidden accept=".txt,.md,.csv,.log,.json,.html,.htm,.doc,.docx,.pdf,.xls,.xlsx,.ppt,.pptx,.wps" @change="handleFiles" />
          <p v-if="!materials.length" class="writing-empty">还没有上传素材。素材会保存在个人素材库，按需勾选后才会用于本次生成。</p>
          <p v-else class="writing-material-summary">素材库共 {{ materials.length }} 份 · 本次已选 {{ selectedMaterialIds.length }} 份</p>
          <ul class="writing-materials">
            <li v-for="item in visibleMaterials" :key="item.id">
              <div class="writing-material-main">
                <label><input v-model="selectedMaterialIds" type="checkbox" :value="item.id" /><strong>{{ item.name }}</strong></label>
                <span>{{ item.text_preview || '已上传' }}</span>
              </div>
              <button class="writing-material-del" type="button" title="删除素材" @click="handleDeleteMaterial(item)"><el-icon><Delete /></el-icon></button>
            </li>
          </ul>
          <button v-if="materials.length > 3" class="writing-material-toggle" type="button" @click="materialsExpanded = !materialsExpanded">{{ materialsExpanded ? '收起素材' : `展开全部素材（${materials.length}）` }}</button>
        </section>

        <section class="writing-block">
          <h2><el-icon><Collection /></el-icon> 知识库</h2>
          <label class="writing-check"><input v-model="form.use_knowledge" type="checkbox" /> 参考知识库</label>
          <small>不选择具体知识库时，默认检索全部可用知识库。</small>
          <div v-if="form.use_knowledge" class="writing-kbs">
            <label v-for="row in knowledgeTree" :key="row.kb.id" class="writing-check writing-kb-node" :style="{ paddingLeft: `${row.depth * 16}px` }">
              <button v-if="row.hasChildren" class="writing-kb-toggle" type="button" :aria-label="expandedKbIds.includes(row.kb.id) ? '收起子知识库' : '展开子知识库'" @click.prevent="toggleKbBranch(row.kb.id)">
                {{ expandedKbIds.includes(row.kb.id) ? '⌄' : '›' }}
              </button>
              <span v-else class="writing-kb-spacer"></span>
              <input v-model="selectedKbIds" type="checkbox" :value="row.kb.id" :disabled="row.kb.chunk_count <= 0" />
              {{ row.kb.shared ? '共享 · ' : '' }}{{ row.kb.name }}（{{ row.kb.chunk_count }} 块）
            </label>
          </div>
        </section>

        <section class="writing-block">
          <h2><el-icon><Document /></el-icon> 历史报告</h2>
          <small>可勾选个人历史周报或出差报告，作为本次生成的参考资料。</small>
          <p v-if="!availableReports.length" class="writing-empty">暂无可参考的历史周报或出差报告。</p>
          <div v-else class="writing-report-refs">
            <label v-for="report in availableReports" :key="`${report.kind}:${report.name}`" class="writing-report-ref">
              <input v-model="selectedReportRefs" type="checkbox" :value="{ kind: report.kind, name: report.name }" />
              <span :class="`writing-report-kind writing-report-kind--${report.kind}`">{{ report.kind === 'weekly' ? '周报' : '出差' }}</span>
              <strong :title="report.name">{{ report.name }}</strong>
            </label>
          </div>
        </section>
      </aside>

      <main class="writing-panel writing-editor">
        <div class="writing-toolbar">
          <button class="writing-btn" type="button" :disabled="loading.outline" @click="handleOutline"><el-icon><MagicStick /></el-icon> 生成大纲</button>
          <button class="writing-btn writing-btn--primary" type="button" :disabled="loading.generate" @click="handleGenerate"><el-icon><MagicStick /></el-icon> 生成正文</button>
          <button class="writing-btn" type="button" :disabled="loading.rewrite" @click="handleRewrite">润色 / 改写</button>
          <span>{{ statusText || draftStatus }}</span>
        </div>
        <div class="writing-editor-field">
          <div class="writing-field-head">
            <span>大纲</span>
            <div class="writing-viewtoggle">
              <button type="button" :class="{ active: outlineView === 'read' }" @click="outlineView = 'read'">阅读</button>
              <button type="button" :class="{ active: outlineView === 'edit' }" @click="outlineView = 'edit'">编辑</button>
            </div>
          </div>
          <div v-if="outlineView === 'read'" class="writing-reader writing-reader--outline">
            <div v-if="form.outline.trim()" class="writing-markdown" v-html="outlineHtml"></div>
            <p v-else class="writing-empty">可先生成大纲，也可以切到「编辑」手动输入。</p>
          </div>
          <textarea v-else v-model="form.outline" rows="8" placeholder="可先生成大纲，也可以手动编辑后再生成正文"></textarea>
        </div>
        <div class="writing-editor-field writing-editor-field--content">
          <div class="writing-field-head">
            <span>正文</span>
            <div class="writing-viewtoggle">
              <button type="button" :class="{ active: contentView === 'read' }" @click="contentView = 'read'">阅读</button>
              <button type="button" :class="{ active: contentView === 'edit' }" @click="contentView = 'edit'">编辑</button>
            </div>
          </div>
          <div v-if="contentView === 'read'" class="writing-reader">
            <div v-if="form.content.trim()" class="writing-markdown" v-html="contentHtml"></div>
            <p v-else class="writing-empty">生成结果会以阅读排版显示在这里；切到「编辑」可粘贴或手动修改正文。</p>
          </div>
          <textarea v-else v-model="form.content" rows="20" placeholder="生成结果会显示在这里，也可以粘贴已有正文后使用改写"></textarea>
          <small class="writing-stats">{{ contentStats.characters }} 字符 · {{ contentStats.paragraphs }} 段</small>
        </div>
        <label class="writing-editor-field">改写要求
          <input v-model="form.rewrite_instruction" placeholder="例如：改正式、压缩到800字、扩写案例、生成新闻稿语气" />
        </label>
        <div class="writing-export">
          <button class="writing-btn" type="button" :disabled="!form.content" @click="copyContent"><el-icon><CopyDocument /></el-icon> 复制正文</button>
          <button class="writing-btn" type="button" :disabled="loading.export || !form.content" @click="handleExport('md')"><el-icon><Download /></el-icon> 导出 Markdown</button>
          <button class="writing-btn" type="button" :disabled="loading.export || !form.content" @click="handleExport('txt')"><el-icon><Download /></el-icon> 导出 TXT</button>
          <button class="writing-btn" type="button" :disabled="loading.export || !form.content" @click="handleExport('xlsx')"><el-icon><Download /></el-icon> 导出 Excel</button>
          <button class="writing-btn writing-btn--primary" type="button" :disabled="loading.export || !form.content" @click="handleExport('docx')"><el-icon><Download /></el-icon> 导出 Word</button>
        </div>
      </main>

    </div>

    <section v-else class="writing-history-page">
      <header>
        <div><h2>文稿历史</h2><p>共 {{ history.length }} 篇文稿，选择后将在编辑页打开。</p></div>
        <button class="writing-btn" type="button" :disabled="loading.history" @click="refreshHistory">刷新列表</button>
      </header>
      <p v-if="!history.length" class="writing-empty">暂无历史文稿。</p>
      <div v-else class="writing-history-list">
        <article v-for="item in history" :key="item.id" :class="{ active: selectedHistoryId === item.id }">
          <button class="writing-history-open" type="button" :disabled="loading.history" @click="loadHistoryItem(item)">
            <strong>{{ item.title || '未命名文稿' }}</strong><span>{{ item.writing_type || '通用文章' }} · {{ item.updated_at || item.created_at || '未知时间' }}</span><p>{{ item.content_preview || '暂无正文预览' }}</p>
          </button>
          <button class="writing-history-delete" type="button" title="删除文稿" @click="handleDeleteHistory(item)"><el-icon><Delete /></el-icon></button>
        </article>
      </div>
    </section>
  </section>
</template>
