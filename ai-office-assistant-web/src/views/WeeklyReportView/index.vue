<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { Calendar, Delete, Document, Download, EditPen, FullScreen, Setting, Upload, View } from '@element-plus/icons-vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import weeklyEmptyPlaceholder from '../../assets/weekly-empty-placeholder.png'
import { authState, defaultOptimizePrompt } from '../../services/authSession'
import { createMailSendConfirmMessage } from '../../utils/mailSendConfirm'
import { parseMailRecipients, serializeMailRecipientEmails, serializeMailRecipients, type MailRecipientField } from '../../utils/mailRecipients'
import {
  deleteHistory,
  deleteReport,
  downloadUrl,
  generateWeekly,
  getDraft,
  getMailConfig,
  getReports,
  getWeeklyPrefill,
  optimizeText,
  redirectToLoginOnUnauthorized,
  resourceUrl,
  sendMail,
  summarizeDiaries,
  type DraftResponse,
  type ReportFile,
  type SendMailPayload,
  type WeeklyRowPayload,
} from '../../services/personalWorkApi'
import './index.scss'

type SectionId = 'summary' | 'follow' | 'next'
type WeeklyTabId = 'edit' | 'mail' | 'history'
type Tone = 'blue' | 'green' | 'orange' | 'violet'
type RowField = keyof WeeklyRowPayload
type WeeklyRowsBySection = Record<SectionId, WeeklyRowPayload[]>

interface WeeklyRow extends WeeklyRowPayload {
  id: number
  tone: Tone
}

interface WeeklySection {
  id: SectionId
  title: string
  subtitle: string
  emptyAction: string
  rows: WeeklyRow[]
}

interface EditField {
  key: RowField
  label: string
  multiline?: boolean
}

interface EditTarget {
  sectionId: SectionId
  rowId: number
  isNew: boolean
}

interface FieldOptimizePreview {
  original: string
  suggestion: string
}

interface ReportUploadFile {
  name: string
  data: string
}

interface ReportTemplateInfo {
  kind: 'weekly' | 'trip'
  configured: boolean
  name: string
  mtime: number | null
  download_url: string
}

interface UploadHistoryResponse {
  ok: boolean
  uploaded: { name: string; path: string; size: number }[]
}

interface ReportTemplatesResponse {
  ok: boolean
  templates: Record<'weekly' | 'trip', ReportTemplateInfo>
}

interface SaveReportTemplateResponse {
  ok: boolean
  template: { kind: 'weekly' | 'trip'; name: string; path: string; mtime: number }
}

const workflowSteps = [
  { id: 1, title: '编辑周报', description: '填写与校对内容' },
  { id: 2, title: '邮件发送', description: '确认并发送邮件' },
]

const weeklyTabs: Array<{ id: WeeklyTabId; label: string }> = [
  { id: 'edit', label: '编辑周报' },
  { id: 'mail', label: '邮件发送' },
  { id: 'history', label: '历史管理' },
]

const sectionFields: Record<SectionId, EditField[]> = {
  summary: [
    { key: 'category', label: '工作分类' },
    { key: 'content', label: '工作内容', multiline: true },
    { key: 'status', label: '完成情况' },
    { key: 'plan', label: '后续计划', multiline: true },
  ],
  follow: [
    { key: 'category', label: '工作分类' },
    { key: 'content', label: '工作内容', multiline: true },
    { key: 'progress', label: '当前进展', multiline: true },
    { key: 'difficulty', label: '困难与求助', multiline: true },
  ],
  next: [
    { key: 'category', label: '工作分类' },
    { key: 'content', label: '工作内容', multiline: true },
    { key: 'difficulty', label: '困难与求助', multiline: true },
  ],
}

const backendUrl = import.meta.env.VITE_PERSONAL_WORK_BACKEND_URL?.replace(/\/$/, '') || ''
const elementLocale = zhCn

const activeStep = ref(1)
const activeSectionId = ref<SectionId>('summary')
const nextRowId = ref(1)
const editing = ref<EditTarget | null>(null)
const flowTop = ref<HTMLElement | null>(null)
const weeklyRowsRef = ref<HTMLElement | null>(null)
const selectedReport = ref('')
const reports = ref<ReportFile[]>([])
const sendBlockers = ref<string[]>([])
const isReportDirty = ref(true)
const previewSource = ref<'instant' | 'generated'>('instant')
const initialized = ref(false)
const fieldOptimizing = ref<RowField | ''>('')

const loading = reactive({
  init: false,
  reports: false,
  draft: false,
  prefill: false,
  summarize: false,
  generate: false,
  send: false,
  templates: false,
  uploadHistory: false,
  template: false,
})

const weeklyPeriod = reactive({
  start: '',
  end: '',
})

const editForm = reactive<Record<RowField, string>>({
  category: '',
  content: '',
  status: '',
  progress: '',
  plan: '',
  difficulty: '',
})

const promptForm = reactive<Record<RowField, string>>({
  category: '',
  content: '',
  status: '',
  progress: '',
  plan: '',
  difficulty: '',
})
// AI 优化结果先暂存，用户对比后再决定是否写回输入框。
const fieldOptimizePreview = reactive<Record<RowField, FieldOptimizePreview | null>>({
  category: null,
  content: null,
  status: null,
  progress: null,
  plan: null,
  difficulty: null,
})
const promptEditor = ref<RowField | ''>('')
const promptDraft = ref('')
const historyPanelOpen = ref(false)
const attachmentPreviewOpen = ref(false)
const mailBodyPreviewOpen = ref(false)
const reportPanelCollapsed = ref(false)
const historyUploadInput = ref<HTMLInputElement | null>(null)
const templateUploadInput = ref<HTMLInputElement | null>(null)
const weeklyTemplate = ref<ReportTemplateInfo | null>(null)

const mailDraft = reactive({
  to: '',
  cc: '',
  subject: '',
  body: '',
  body_html: '',
  attachment: '',
  download_url: '',
  preview: '',
  preview_html: '',
})

const sections = ref<WeeklySection[]>([
  { id: 'summary', title: '一、本周工作总结', subtitle: '沉淀本周已完成事项', emptyAction: '新增一条总结', rows: [] },
  { id: 'follow', title: '二、重点工作跟进', subtitle: '记录进展和困难', emptyAction: '新增一条跟进', rows: [] },
  { id: 'next', title: '三、下周工作计划', subtitle: '安排后续计划', emptyAction: '新增一条计划', rows: [] },
])

const activeWeeklyTab = computed<WeeklyTabId>(() => {
  return activeStep.value === 2 ? 'mail' : 'edit'
})
const activeSection = computed(() => findSection(activeSectionId.value))
const totalRows = computed(() => sections.value.reduce((sum, section) => sum + cleanRows(section.id).length, 0))
const weeklyReports = computed(() => reports.value.filter((report) => report.kind === 'weekly'))
const weeklyHistoryReports = computed(() => weeklyReports.value.filter((report) => !report.generated))
const currentFileName = computed(() => mailDraft.attachment || selectedReport.value)
const previewStateText = computed(() => {
  if (previewSource.value === 'instant' && !mailDraft.attachment) return '待生成附件'
  if (mailDraft.attachment && !isReportDirty.value) return '已生成'
  return mailDraft.attachment ? '待重新生成' : '待生成附件'
})
const currentDownloadUrl = computed(() => {
  if (mailDraft.download_url) return downloadUrl(mailDraft.download_url)
  return mailDraft.attachment ? `/personal-work-download?file=${encodeURIComponent(mailDraft.attachment)}` : ''
})
const hasAttachmentPreview = computed(() => Boolean(mailDraft.attachment && mailDraft.preview_html))
const mailBodyPreviewHtml = computed(() => mailDraft.body_html || `<div>${textToHtml(mailDraft.body || '暂无正文内容')}</div>`)
const periodValue = computed(() => {
  const start = formatPeriodDate(weeklyPeriod.start)
  const end = formatPeriodDate(weeklyPeriod.end)
  return start && end ? `${start}-${end}` : start || end
})
const draftStorageKey = computed(() =>
  authState.user?.username ? `personalWorkSite.formDraft.v2:${authState.user.username}` : '',
)
const nextActionText = computed(() => {
  if (activeStep.value === 1) return loading.generate ? '正在生成附件' : '生成附件并进入邮件发送'
  return loading.send ? '发送中' : '发送'
})
const stepHint = computed(() => {
  if (activeStep.value === 1) return `已填写 ${totalRows.value} 条周报内容`
  return sendBlockers.value.length ? '请补齐发送信息后再确认' : '确认收件人、主题、正文和附件'
})
const stepActionDisabled = computed(() => loading.generate || loading.send)
const editingFields = computed(() => (editing.value ? sectionFields[editing.value.sectionId] : []))
const categoryEditingField = computed(() => editingFields.value.find((field) => field.key === 'category'))
const primaryTextEditingField = computed(() => editingFields.value.find((field) => field.key === 'content') || editingFields.value.find((field) => field.key === 'progress'))
const extraEditingFields = computed(() => editingFields.value.filter((field) => field.key !== 'category' && field.key !== 'status' && field.key !== primaryTextEditingField.value?.key))
const editingStateField = computed(() => editingFields.value.find((field) => field.key === 'status'))
const editingStateOptions = computed(() => {
  const stateField = editingStateField.value
  if (!stateField) return []
  const options = ['已完成', '推进中', '需协调']
  const current = editForm[stateField.key].trim()
  return current && !options.includes(current) ? [current, ...options] : options
})
const primaryOptimizePreview = computed(() => {
  const field = primaryTextEditingField.value
  return field ? fieldOptimizePreview[field.key] : null
})
const currentPromptField = computed(() => editingFields.value.find((field) => field.key === promptEditor.value))
const promptDialogTitle = computed(() => (currentPromptField.value ? `${currentPromptField.value.label}提示词` : '修改提示词'))
const promptDialogVisible = computed({
  get: () => Boolean(promptEditor.value),
  set: (visible: boolean) => {
    if (!visible) promptEditor.value = ''
  },
})
const selectedEditingRow = computed(() => {
  if (!editing.value) return null
  return findSection(editing.value.sectionId).rows.find((row) => row.id === editing.value?.rowId) || null
})
const periodRange = computed<string[]>({
  get: () => (weeklyPeriod.start && weeklyPeriod.end ? [weeklyPeriod.start, weeklyPeriod.end] : []),
  set: (value: string[]) => {
    weeklyPeriod.start = value?.[0] || ''
    weeklyPeriod.end = value?.[1] || ''
  },
})
const toRecipients = computed({
  get: () => parseMailRecipients(mailDraft.to, 'to'),
  set: (value: string[]) => {
    mailDraft.to = serializeMailRecipients(value, 'to')
  },
})
const ccRecipients = computed({
  get: () => parseMailRecipients(mailDraft.cc, 'cc'),
  set: (value: string[]) => {
    mailDraft.cc = serializeMailRecipients(value, 'cc')
  },
})
const weeklyTemplateDownloadUrl = computed(() => resourceUrl(weeklyTemplate.value?.download_url || '/download-template?kind=weekly'))

watch(
  () => [weeklyPeriod.start, weeklyPeriod.end],
  () => {
    saveWeeklyDraft()
    if (initialized.value) markReportDirty()
  },
)

watch(
  () => [mailDraft.to, mailDraft.cc, mailDraft.subject, mailDraft.body, mailDraft.attachment],
  () => clearSendReview(),
)

function setStatus(message: string, tone: 'normal' | 'ok' | 'error' = 'normal') {
  if (!message) return
  if (tone === 'error') ElMessage.error(message)
  else if (tone === 'ok') ElMessage.success(message)
  else ElMessage.info(message)
}

function escapeHtml(value: string) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] || char)
}

function textToHtml(value: string) {
  return escapeHtml(value).replace(/\n/g, '<br>')
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

async function readUploadFiles(fileList: FileList | null): Promise<ReportUploadFile[]> {
  const files = Array.from(fileList || [])
  return Promise.all(files.map(async (file) => ({ name: file.name, data: await readFileAsDataUrl(file) })))
}

async function weeklyPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(backendUrl ? `${backendUrl}/api${path}` : `/personal-work-api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  const rawText = await response.text()
  let data: unknown = {}
  if (rawText) {
    try {
      data = JSON.parse(rawText)
    } catch {
      data = {}
    }
  }
  if (!response.ok || (data && typeof data === 'object' && 'error' in data)) {
    const message = data && typeof data === 'object' && 'error' in data ? String(data.error) : `请求失败：${response.status}`
    if (response.status === 401) redirectToLoginOnUnauthorized(path)
    throw new Error(message)
  }
  return data as T
}

function uploadHistoryReports(kind: 'weekly' | 'trip', files: ReportUploadFile[]) {
  return weeklyPost<UploadHistoryResponse>('/upload-history', { kind, files })
}

function getReportTemplates() {
  return weeklyPost<ReportTemplatesResponse>('/report-templates', {})
}

function saveReportTemplate(kind: 'weekly' | 'trip', file: ReportUploadFile) {
  return weeklyPost<SaveReportTemplateResponse>('/report-template', { kind, file })
}

function deleteReportTemplate(kind: 'weekly' | 'trip') {
  return weeklyPost<ReportTemplatesResponse>('/report-template-delete', { kind })
}

function todayText() {
  const now = new Date()
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
}

function toDateInputValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatPeriodDate(value: string) {
  if (!value) return ''
  const [year, month, day] = value.split('-').map(Number)
  return year && month && day ? `${year}.${month}.${day}` : value
}

function setDefaultWeeklyDates() {
  const today = new Date()
  const day = today.getDay() || 7
  const monday = new Date(today)
  monday.setHours(0, 0, 0, 0)
  monday.setDate(today.getDate() - day + 1)
  const friday = new Date(monday)
  friday.setDate(monday.getDate() + 4)
  weeklyPeriod.start = toDateInputValue(monday)
  weeklyPeriod.end = toDateInputValue(friday)
}

function findSection(sectionId: SectionId) {
  return sections.value.find((section) => section.id === sectionId) as WeeklySection
}

function toneForRow(sectionId: SectionId, row: WeeklyRowPayload): Tone {
  if (sectionId === 'follow') return 'blue'
  if (String(row.category || '').includes('研')) return 'green'
  if (String(row.category || '').includes('产品')) return 'violet'
  return 'blue'
}

function createRow(sectionId: SectionId, row: WeeklyRowPayload = {}): WeeklyRow {
  return {
    id: nextRowId.value++,
    category: row.category || '',
    content: row.content || '',
    status: row.status || (sectionId === 'summary' ? '已完成' : ''),
    progress: row.progress || (sectionId === 'follow' ? '推进中' : ''),
    plan: row.plan || '',
    difficulty: row.difficulty || '',
    tone: toneForRow(sectionId, row),
  }
}

function canOptimizeField(field: EditField) {
  return field.key !== 'category'
}

function optimizePrompt(fieldKey: RowField) {
  return promptForm[fieldKey] || defaultOptimizePrompt()
}

function isRequiredField(field: EditField) {
  return field.key === 'category' || field.key === 'content' || field.key === 'progress'
}

function applyRows(sectionId: SectionId, rows: WeeklyRowPayload[]) {
  findSection(sectionId).rows = rows.map((row) => createRow(sectionId, row))
}

function applyRowsBySection(rows: WeeklyRowsBySection) {
  applyRows('summary', rows.summary)
  applyRows('follow', rows.follow)
  applyRows('next', rows.next)
  syncActiveSectionToFirstFilled()
}

function sectionDisplayTitle(title: string) {
  return title.replace(/^[一二三]、/, '')
}

function firstFilledSectionId() {
  return sections.value.find((section) => cleanRows(section.id).length)?.id || 'summary'
}

function syncActiveSectionToFirstFilled() {
  activeSectionId.value = firstFilledSectionId()
  selectFirstRowInSection(activeSectionId.value)
}

function selectFirstRowInSection(sectionId: SectionId) {
  const firstRow = findSection(sectionId).rows[0]
  if (firstRow) beginEdit(sectionId, firstRow)
  else editing.value = null
}

function selectSection(sectionId: SectionId) {
  commitEditSilently()
  activeSectionId.value = sectionId
  selectFirstRowInSection(sectionId)
}

function rowPayload(sectionId: SectionId, row: WeeklyRow) {
  const payload: WeeklyRowPayload = {}
  sectionFields[sectionId].forEach((field) => {
    const value = String(row[field.key] || '').trim()
    if (value) payload[field.key] = value
  })
  return payload
}

function cleanRows(sectionId: SectionId) {
  return findSection(sectionId).rows.map((row) => rowPayload(sectionId, row)).filter((row) => Object.keys(row).length)
}

function rowState(sectionId: SectionId, row: WeeklyRow) {
  if (sectionId === 'summary') return row.status
  if (sectionId === 'follow') return row.progress
  return ''
}

function rowStateLabel(sectionId: SectionId, row: WeeklyRow) {
  const state = rowState(sectionId, row)
  return sectionId === 'follow' ? (state || '').slice(0, 3) : state || ''
}

function rowTitle(sectionId: SectionId, row: WeeklyRow) {
  if (sectionId === 'follow') return row.category || row.progress || '待填写工作分类'
  return row.category || '待分类'
}

function rowSubtitle(sectionId: SectionId, row: WeeklyRow) {
  if (sectionId === 'follow') return row.content || row.progress || row.difficulty || '待填写工作内容'
  return row.content || '待填写工作内容'
}

function beginAdd(section: WeeklySection) {
  commitEditSilently()
  activeSectionId.value = section.id
  const row = createRow(section.id)
  section.rows.unshift(row)
  beginEdit(section.id, row, true)
  revealInlineEditor()
}

function beginEdit(sectionId: SectionId, row: WeeklyRow, isNew = false) {
  if (editing.value && (editing.value.sectionId !== sectionId || editing.value.rowId !== row.id || isNew)) commitEditSilently()
  activeSectionId.value = sectionId
  editing.value = { sectionId, rowId: row.id, isNew }
  Object.keys(editForm).forEach((key) => {
    const fieldKey = key as RowField
    // 历史重点跟进行可能把当前进展写在 content 字段，编辑时迁移到 progress。
    editForm[fieldKey] = sectionId === 'follow' && fieldKey === 'progress' ? String(row.progress || row.content || '') : String(row[fieldKey] || '')
    promptForm[fieldKey] = ''
    fieldOptimizePreview[fieldKey] = null
  })
  fieldOptimizing.value = ''
  promptEditor.value = ''
}

// 新增条目后，把当前分区的编辑卡片带到用户视野内。
function revealInlineEditor() {
  nextTick(() => {
    weeklyRowsRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
    const firstInput = weeklyRowsRef.value?.querySelector<HTMLElement>('.weekly-inline-editor textarea, .weekly-inline-editor input')
    firstInput?.focus({ preventScroll: true })
  })
}

function isEditingRow(sectionId: SectionId, rowId: number) {
  return editing.value?.sectionId === sectionId && editing.value.rowId === rowId
}

function setEditState(value: string) {
  const stateField = editingStateField.value
  if (!stateField) return
  editForm[stateField.key] = value
  handleEditFieldInput(stateField.key)
}

function isEditStateActive(value: string) {
  const stateField = editingStateField.value
  return stateField ? editForm[stateField.key] === value : false
}

function validateEditForm(section: WeeklySection) {
  const missing = sectionFields[section.id].filter((field) => isRequiredField(field) && !editForm[field.key].trim()).map((field) => field.label)
  if (!missing.length) return true
  ElMessage.warning(`请填写${missing.join('、')}`)
  return false
}

function applyEditFormToRow(section: WeeklySection, row: WeeklyRow) {
  Object.keys(editForm).forEach((key) => {
    row[key as RowField] = ''
  })
  sectionFields[section.id].forEach((field) => {
    row[field.key] = editForm[field.key].trim()
  })
  row.tone = toneForRow(section.id, row)
}

function clearEditState() {
  editing.value = null
  fieldOptimizing.value = ''
  promptEditor.value = ''
}

function commitEditSilently(keepEditing = false) {
  if (!editing.value) return
  const target = editing.value
  const section = findSection(target.sectionId)
  const row = section.rows.find((item) => item.id === target.rowId)
  if (!row) {
    clearEditState()
    return
  }
  const hasContent = sectionFields[section.id].some((field) => editForm[field.key].trim())
  if (!hasContent && target.isNew) {
    if (keepEditing) return
    section.rows = section.rows.filter((item) => item.id !== target.rowId)
    clearEditState()
    saveWeeklyDraft()
    return
  }
  applyEditFormToRow(section, row)
  if (!keepEditing) clearEditState()
  activeStep.value = 1
  markReportDirty()
  saveWeeklyDraft()
}

function saveEdit() {
  if (!editing.value) return
  const section = findSection(editing.value.sectionId)
  const row = section.rows.find((item) => item.id === editing.value?.rowId)
  if (!row) return
  if (!validateEditForm(section)) return
  applyEditFormToRow(section, row)
  clearEditState()
  activeStep.value = 1
  markReportDirty()
  saveWeeklyDraft()
}

function saveCurrentChanges() {
  if (editing.value) {
    saveEdit()
    return
  }
  saveWeeklyDraft()
  ElMessage.success('已保存当前修改')
}

function cancelEdit() {
  if (editing.value?.isNew) {
    const section = findSection(editing.value.sectionId)
    section.rows = section.rows.filter((row) => row.id !== editing.value?.rowId)
  }
  clearEditState()
}

function handleEditorOutsidePointer(event: PointerEvent) {
  if (!editing.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('.detail-panel, .weekly-prompt-dialog, .el-overlay, .el-popper')) return
  commitEditSilently(true)
}

function handleEditFieldInput(fieldKey: RowField) {
  if (!fieldOptimizePreview[fieldKey]) return
  fieldOptimizePreview[fieldKey] = null
}

function undoOptimizePreview(field: EditField) {
  fieldOptimizePreview[field.key] = null
}

function acceptOptimizePreview(field: EditField) {
  const preview = fieldOptimizePreview[field.key]
  if (!preview) return
  editForm[field.key] = preview.suggestion
  fieldOptimizePreview[field.key] = null
}

function openPromptEditor(field: EditField) {
  promptEditor.value = field.key
  promptDraft.value = optimizePrompt(field.key)
}

function savePromptEditor() {
  if (!promptEditor.value) return
  promptForm[promptEditor.value] = promptDraft.value.trim()
  promptEditor.value = ''
  ElMessage.success('提示词已更新')
}

function removeRow(section: WeeklySection, rowId: number) {
  section.rows = section.rows.filter((row) => row.id !== rowId)
  if (editing.value?.rowId === rowId) editing.value = null
  markReportDirty()
  saveWeeklyDraft()
}

function instantMailSubject() {
  return `【周报】工作周报（${periodValue.value || '未选择时段'}）`
}

function instantMailBody() {
  const blocks = sections.value.map((section) => {
    const rows = cleanRows(section.id)
    const lines = rows.length
      ? rows.map((row, index) => `${index + 1}. ${[row.category, row.content, row.status || row.progress, row.plan || row.difficulty].filter(Boolean).join('｜')}`)
      : ['暂无内容']
    return `${section.title}\n${lines.join('\n')}`
  })
  return `领导您好：\n\n以下是我本周的工作周报，请查阅。\n\n${blocks.join('\n\n')}\n\n如有需要补充或调整的地方，我会及时完善。\n\n${authState.user?.name || authState.user?.username || ''}\n${todayText()}`
}

function instantMailHtml() {
  const intro = currentFileName.value
    ? `附件为我的本周工作周报《${escapeHtml(currentFileName.value)}》，请查收。`
    : '以下是我本周的工作周报，请查阅。'
  return `<p>领导您好：</p><p>${intro}</p>${instantSheetHtml()}<p>本周主要工作内容已在附件中汇总，如有需要补充或调整的地方，我会及时完善。</p><p>${escapeHtml(authState.user?.name || authState.user?.username || '')}<br>${todayText()}</p>`
}

function instantSheetHtml() {
  const blocks = sections.value.map((section) => {
    const rows = cleanRows(section.id)
    const body = rows.length
      ? rows.map((row, index) => `<tr><td>${index + 1}</td><td>${textToHtml(row.category || '')}</td><td>${textToHtml(row.content || '')}</td><td>${textToHtml(row.status || row.progress || '')}</td><td>${textToHtml(row.plan || row.difficulty || '')}</td></tr>`).join('')
      : '<tr><td colspan="5">暂无内容</td></tr>'
    return `<div class="instant-sheet-section">${escapeHtml(section.title)}</div><table><thead><tr><th>序号</th><th>分类</th><th>工作内容</th><th>状态/进展</th><th>备注</th></tr></thead><tbody>${body}</tbody></table>`
  })
  return `<div class="instant-sheet-title">工作周报（${escapeHtml(periodValue.value || '未选择时段')}）</div>${blocks.join('')}`
}

function refreshInstantPreview() {
  mailDraft.subject = instantMailSubject()
  mailDraft.body = instantMailBody()
  mailDraft.body_html = instantMailHtml()
  mailDraft.preview = ''
  mailDraft.preview_html = instantSheetHtml()
  previewSource.value = 'instant'
}

function markReportDirty() {
  isReportDirty.value = true
  selectedReport.value = ''
  mailDraft.attachment = ''
  mailDraft.download_url = ''
  refreshInstantPreview()
  clearSendReview()
}

function saveWeeklyDraft() {
  if (!draftStorageKey.value) return
  const draft = {
    updatedAt: Date.now(),
    weekly: {
      start: weeklyPeriod.start,
      end: weeklyPeriod.end,
      period: periodValue.value,
      summary: cleanRows('summary'),
      follow: cleanRows('follow'),
      next: cleanRows('next'),
    },
  }
  localStorage.setItem(draftStorageKey.value, JSON.stringify(draft))
}

function restoreWeeklyDraft() {
  if (!draftStorageKey.value) return false
  const raw = localStorage.getItem(draftStorageKey.value)
  if (!raw) return false
  let draft: { weekly?: { start?: string; end?: string; summary?: WeeklyRowPayload[]; follow?: WeeklyRowPayload[]; next?: WeeklyRowPayload[] } }
  try {
    draft = JSON.parse(raw)
  } catch {
    return false
  }
  if (!draft.weekly) return false
  if (draft.weekly.start) weeklyPeriod.start = draft.weekly.start
  if (draft.weekly.end) weeklyPeriod.end = draft.weekly.end
  if (![draft.weekly.summary, draft.weekly.follow, draft.weekly.next].some((rows) => rows?.length)) return false
  applyRowsBySection({
    summary: draft.weekly.summary || [],
    follow: draft.weekly.follow || [],
    next: draft.weekly.next || [],
  })
  return true
}

async function loadReports() {
  loading.reports = true
  try {
    const data = await getReports()
    reports.value = data.reports.filter((report) => report.kind === 'weekly')
    return data.latest_weekly
  } finally {
    loading.reports = false
  }
}

async function loadWeeklyTemplate() {
  loading.templates = true
  try {
    const data = await getReportTemplates()
    weeklyTemplate.value = data.templates.weekly
  } finally {
    loading.templates = false
  }
}

async function openHistoryDrawer() {
  historyPanelOpen.value = true
  await Promise.all([loadReports(), loadWeeklyTemplate()])
}

function reportDownloadUrl(name: string) {
  return `/personal-work-download?file=${encodeURIComponent(name)}`
}

function reportTime(report: ReportFile) {
  return new Date(report.mtime * 1000).toLocaleDateString()
}

function reportDateTime(report: ReportFile) {
  return new Date(report.mtime * 1000).toLocaleString()
}

function reportTypeText(report: ReportFile) {
  return report.generated ? '新生成' : '周报模板'
}

function triggerHistoryUpload() {
  historyUploadInput.value?.click()
}

async function uploadWeeklyHistory(event: Event) {
  const input = event.target as HTMLInputElement
  const files = await readUploadFiles(input.files)
  if (!files.length) return
  loading.uploadHistory = true
  try {
    const result = await uploadHistoryReports('weekly', files)
    ElMessage.success(`已上传 ${result.uploaded.length} 个历史周报`)
    input.value = ''
    await loadReports()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '历史周报上传失败')
  } finally {
    loading.uploadHistory = false
  }
}

function triggerTemplateUpload() {
  templateUploadInput.value?.click()
}

async function uploadWeeklyTemplate(event: Event) {
  const input = event.target as HTMLInputElement
  const [file] = await readUploadFiles(input.files)
  if (!file) return
  loading.template = true
  try {
    await saveReportTemplate('weekly', file)
    ElMessage.success('周报模板已保存')
    input.value = ''
    await loadWeeklyTemplate()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '周报模板保存失败')
  } finally {
    loading.template = false
  }
}

async function removeWeeklyTemplate() {
  loading.template = true
  try {
    const result = await deleteReportTemplate('weekly')
    weeklyTemplate.value = result.templates.weekly
    ElMessage.success('周报模板已删除')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '周报模板删除失败')
  } finally {
    loading.template = false
  }
}

function applyDraft(draft: DraftResponse) {
  mailDraft.to = draft.to || ''
  mailDraft.cc = draft.cc || ''
  mailDraft.subject = draft.subject || ''
  mailDraft.body = draft.body || ''
  mailDraft.body_html = draft.body_html || ''
  mailDraft.attachment = draft.attachment || ''
  mailDraft.download_url = draft.download_url || ''
  mailDraft.preview = draft.preview || ''
  mailDraft.preview_html = draft.preview_html || ''
  previewSource.value = draft.attachment ? 'generated' : 'instant'
  isReportDirty.value = !draft.attachment
  clearSendReview()
}

function applyGeneratedDraft(draft: DraftResponse) {
  const currentTo = mailDraft.to
  const currentCc = mailDraft.cc
  applyDraft(draft)
  // 重新生成附件只更新正文和附件，保留用户已填写的联系人。
  if (currentTo) mailDraft.to = currentTo
  if (currentCc) mailDraft.cc = currentCc
}

async function loadWeeklyMailRecipients() {
  if (mailDraft.to && mailDraft.cc) return
  try {
    const config = await getMailConfig()
    if (!mailDraft.to) mailDraft.to = config.weekly_to || ''
    if (!mailDraft.cc) mailDraft.cc = config.weekly_cc || ''
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '邮件配置读取失败', 'error')
  }
}

async function loadDraft(name: string) {
  loading.draft = true
  try {
    const draft = await getDraft('weekly', name)
    selectedReport.value = name
    applyDraft(draft)
    activeStep.value = 2
    setStatus(name ? `已加载报告：${name}` : '已加载邮件草稿', 'ok')
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '报告加载失败', 'error')
  } finally {
    loading.draft = false
  }
}

async function loadLatestHistory(showSuccess = true) {
  loading.prefill = true
  try {
    const prefill = await getWeeklyPrefill()
    if (prefill.error) {
      setStatus(prefill.error, 'error')
      return
    }
    const prefillRows: WeeklyRowsBySection = {
      summary: prefill.summary_rows || [],
      follow: prefill.follow_rows || [],
      next: prefill.next_rows || [],
    }
    applyRowsBySection(prefillRows)
    if (showSuccess) {
      setStatus(
        prefill.source
          ? `已获取最新历史周报：${prefill.source}。上次“下周计划”已写入本次“本周工作总结”，重点工作跟进已复制，下周工作计划已按本周分类预填、内容待补充。`
          : '没有找到可用于预填的历史周报。',
        prefill.source ? 'ok' : 'error',
      )
    }
    activeStep.value = 1
    markReportDirty()
    saveWeeklyDraft()
    await loadReports()
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '历史周报预填失败', 'error')
  } finally {
    loading.prefill = false
  }
}

// 按后端已有周报格式把日记总结文本拆成三段内容。
function parseDiarySummary(summary: string) {
  const parsed: Record<SectionId, string[]> = { summary: [], follow: [], next: [] }
  let current: SectionId | '' = ''
  summary.split('\n').forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed) return
    if (trimmed.includes('本周工作总结') || trimmed.includes('本周工作')) {
      current = 'summary'
      return
    }
    if (trimmed.includes('重点工作跟进') || trimmed.includes('重点工作')) {
      current = 'follow'
      return
    }
    if (trimmed.includes('下周工作计划') || trimmed.includes('下周工作')) {
      current = 'next'
      return
    }
    const content = trimmed.replace(/^[\d一二三四五六七八九十]+[.、．\s]+/, '').replace(/^[-*]\s+/, '').trim()
    if (current && content) parsed[current].push(content)
  })
  return parsed
}

async function summarizeFromDiaries() {
  if (!weeklyPeriod.start || !weeklyPeriod.end) {
    ElMessage.warning('请选择周报时段')
    return
  }
  loading.summarize = true
  try {
    const data = await summarizeDiaries(weeklyPeriod.start, weeklyPeriod.end)
    if (!data.ok) {
      setStatus(data.error || '工作日记总结失败', 'error')
      return
    }
    if (data.mode === 'empty') {
      setStatus(data.warning || '该范围内没有工作日记', 'error')
      return
    }
    const parsed = parseDiarySummary(data.summary || '')
    applyRowsBySection({
      summary: parsed.summary.map((content) => ({ category: '', content, status: '已完成' })),
      follow: parsed.follow.map((content) => ({ progress: content })),
      next: parsed.next.map((content) => ({ category: '', content, difficulty: '正常' })),
    })
    setStatus('工作日记总结已应用到周报，请检查后再生成正文', 'ok')
    activeStep.value = 1
    markReportDirty()
    saveWeeklyDraft()
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '工作日记总结失败', 'error')
  } finally {
    loading.summarize = false
  }
}

async function generateReport() {
  if (!totalRows.value) {
    ElMessage.warning('请先填写周报内容')
    return
  }
  refreshInstantPreview()
  loading.generate = true
  try {
    const result = await generateWeekly({
      kind: 'weekly',
      period: periodValue.value,
      weekly_summary: cleanRows('summary'),
      weekly_follow: cleanRows('follow'),
      weekly_next: cleanRows('next'),
    })
    selectedReport.value = result.file
    applyGeneratedDraft(result.draft)
    activeStep.value = 2
    isReportDirty.value = false
    setStatus(`已生成标准文件，并设为当前邮件附件：${result.file}`, 'ok')
    localStorage.removeItem(draftStorageKey.value)
    await loadReports()
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '周报生成失败', 'error')
    refreshInstantPreview()
  } finally {
    loading.generate = false
  }
}

async function optimizeEditField(field: EditField) {
  if (!canOptimizeField(field)) return
  const original = editForm[field.key].trim()
  if (!original) {
    ElMessage.warning('请先填写需要优化的内容')
    return
  }
  fieldOptimizing.value = field.key
  fieldOptimizePreview[field.key] = null
  try {
    const result = await optimizeText(original, optimizePrompt(field.key))
    fieldOptimizePreview[field.key] = {
      original,
      suggestion: result.text || original,
    }
    if (result.warning) ElMessage.warning(result.warning)
    else ElMessage.success('已生成优化结果，请对比后采纳')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'AI 优化失败')
  } finally {
    fieldOptimizing.value = ''
  }
}

function clearSendReview() {
  sendBlockers.value = []
}

function handleRecipientPaste(event: Event, field: MailRecipientField) {
  const clipboardEvent = event as ClipboardEvent
  const text = clipboardEvent.clipboardData?.getData('text') || ''
  const pasted = parseMailRecipients(text, field)
  if (!pasted.length) return
  clipboardEvent.preventDefault()
  const current = field === 'to' ? mailDraft.to : mailDraft.cc
  const next = serializeMailRecipients([current, ...pasted], field)
  if (field === 'to') mailDraft.to = next
  else mailDraft.cc = next
  clearSendReview()
}

function buildSendPayload(): SendMailPayload {
  return {
    to: serializeMailRecipientEmails(mailDraft.to, 'to'),
    cc: serializeMailRecipientEmails(mailDraft.cc, 'cc'),
    subject: mailDraft.subject.trim(),
    body: mailDraft.body,
    body_html: mailDraft.body_html,
    attachment: mailDraft.attachment.trim(),
  }
}

function findSendBlockers(payload: SendMailPayload) {
  const blockers: string[] = []
  if (!payload.to) blockers.push('收件人为空')
  if (!payload.subject) blockers.push('主题为空')
  if (!payload.attachment) blockers.push('未选择附件')
  const badWords = ['跟进内容', '计划内容', '很长内容', '总结5', '总结6']
  const found = badWords.filter((word) => payload.body.includes(word))
  if (found.length) blockers.push(`正文存在未替换占位内容：${found.join('、')}`)
  return blockers
}

async function scrollStepTop() {
  await nextTick()
  flowTop.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function stepForWeeklyTab(tab: WeeklyTabId) {
  if (tab === 'mail') return 2
  return 1
}

async function switchWeeklyTab(tab: WeeklyTabId) {
  if (tab === 'history') {
    await openHistoryDrawer()
    return
  }
  if (activeWeeklyTab.value === tab) return
  commitEditSilently(tab === 'edit')
  if (tab === 'mail') {
    if (isReportDirty.value || !mailDraft.body) refreshInstantPreview()
    await loadWeeklyMailRecipients()
  }
  activeStep.value = stepForWeeklyTab(tab)
  if (tab !== 'mail') clearSendReview()
  await scrollStepTop()
}

async function nextStep() {
  if (activeStep.value === 1) {
    commitEditSilently()
    if (!totalRows.value) {
      ElMessage.warning('请先填写周报内容')
      return false
    }
    await generateReport()
    await scrollStepTop()
    return true
  }
  await confirmSend()
  await scrollStepTop()
  return true
}

async function previousStep() {
  if (activeStep.value <= 1) return
  activeStep.value -= 1
  clearSendReview()
  await scrollStepTop()
}

async function confirmSend() {
  const payload = buildSendPayload()
  const blockers = findSendBlockers(payload)
  if (blockers.length) {
    sendBlockers.value = blockers
    return
  }
  const toRecipients = parseMailRecipients(payload.to, 'to')
  const ccRecipients = parseMailRecipients(payload.cc, 'cc')
  try {
    await ElMessageBox.confirm(createMailSendConfirmMessage({
      intro: '确认发送当前周报邮件吗？',
      subject: payload.subject,
      toRecipients,
      ccRecipients,
    }), '发送确认', {
      confirmButtonText: '发送',
      cancelButtonText: '取消',
      customClass: 'mail-send-confirm-box',
    })
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') setStatus(error instanceof Error ? error.message : '发送确认失败', 'error')
    return
  }
  loading.send = true
  try {
    const result = await sendMail(payload)
    loading.send = false
    void ElMessageBox.alert(result.mode === 'sent' ? '邮件已发送' : result.message, result.mode === 'sent' ? '发送成功' : '处理完成', {
      confirmButtonText: '知道了',
      type: 'success',
    }).catch(() => undefined)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '邮件发送失败', 'error')
  } finally {
    loading.send = false
  }
}

async function copyBody() {
  if (!mailDraft.body) {
    ElMessage.warning('暂无可复制正文')
    return
  }
  await navigator.clipboard.writeText(mailDraft.body)
  ElMessage.success('正文已复制')
}

function downloadAttachment() {
  if (!currentDownloadUrl.value) {
    ElMessage.warning('暂无可下载附件')
    return
  }
  window.open(currentDownloadUrl.value, '_blank')
}

function openAttachmentPreview() {
  // 附件预览只对应已生成文件，未生成时不打开模板内容。
  if (!hasAttachmentPreview.value) {
    ElMessage.warning('暂无可预览附件')
    return
  }
  attachmentPreviewOpen.value = true
}

async function deleteReportItem(report: ReportFile) {
  await ElMessageBox.confirm(`确定删除这个报告文件吗？\n${report.name}`, '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  const result = report.generated ? await deleteReport(report.name) : await deleteHistory(report.name)
  ElMessage.success(`已删除：${result.deleted}`)
  if (selectedReport.value === report.name) {
    selectedReport.value = ''
    applyDraft({})
  }
  await loadReports()
}

async function initializeWeekly() {
  loading.init = true
  setDefaultWeeklyDates()
  try {
    const restored = restoreWeeklyDraft()
    const latestWeekly = await loadReports()
    const generated = reports.value.find((report) => report.generated)
    const latest = generated?.name || latestWeekly
    if (!restored && weeklyReports.value.length) await loadLatestHistory(false)
    if (!restored && !weeklyReports.value.length) {
      refreshInstantPreview()
    }
    if (restored) {
      markReportDirty()
    }
    if (!restored && latest && selectedReport.value) await loadDraft(latest)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '周报助手初始化失败', 'error')
  } finally {
    initialized.value = true
    loading.init = false
  }
}

onMounted(initializeWeekly)
</script>

<template>
  <section class="weekly-main weekly-main--wide" @pointerdown.capture="handleEditorOutsidePointer">
    <header ref="flowTop" class="weekly-page-head">
      <div class="weekly-title-block">
        <h1>周报助手</h1>
        <p>填写周报、发送邮件、管理历史周报</p>
      </div>

      <nav class="weekly-tabs" aria-label="周报助手功能页签">
        <button
          v-for="tab in weeklyTabs"
          :key="tab.id"
          :class="{ active: activeWeeklyTab === tab.id }"
          type="button"
          @click="switchWeeklyTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <section v-if="activeStep === 1" class="wizard-step weekly-editor-step">
      <section class="weekly-toolbar">
        <div class="period-control">
          <span class="toolbar-glyph" aria-hidden="true"><el-icon><Calendar /></el-icon></span>
          <strong>周报周期</strong>
          <el-config-provider :locale="elementLocale">
            <el-date-picker
              v-model="periodRange"
              value-format="YYYY-MM-DD"
              format="YYYY.MM.DD"
              type="daterange"
              range-separator="-"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-config-provider>
        </div>

        <div class="toolbar-actions">
          <IconTextButton icon="sparkle" size="md" :disabled="loading.summarize" @click="summarizeFromDiaries">
            从工作日记智能总结
          </IconTextButton>
          <IconTextButton icon="history" size="md" :disabled="loading.prefill" @click="loadLatestHistory(true)">
            获取最新历史报告
          </IconTextButton>
        </div>
      </section>

      <section class="weekly-editor-grid">
        <aside class="section-rail" aria-label="周报内容分区">
          <button
            v-for="section in sections"
            :key="section.id"
            type="button"
            :class="['section-rail-item', { active: activeSectionId === section.id }]"
            @click="selectSection(section.id)"
          >
            <span>{{ sectionDisplayTitle(section.title) }}</span>
            <strong>{{ cleanRows(section.id).length }}</strong>
            <em>+</em>
          </button>
        </aside>

        <section class="entry-panel">
          <header>
            <div>
              <h2>{{ sectionDisplayTitle(activeSection.title) }}</h2>
              <span>{{ cleanRows(activeSection.id).length }} 条</span>
            </div>
            <IconTextButton icon="plus" @click="beginAdd(activeSection)">新增</IconTextButton>
          </header>

          <div ref="weeklyRowsRef" class="entry-list">
            <button
              v-for="(row, index) in activeSection.rows"
              :key="row.id"
              type="button"
              :class="['entry-item', { selected: isEditingRow(activeSection.id, row.id) }]"
              @click="beginEdit(activeSection.id, row)"
            >
              <span :class="['entry-icon', row.tone]">{{ index + 1 }}</span>
              <span class="entry-copy">
                <strong>{{ rowTitle(activeSection.id, row) }}</strong>
                <small>{{ rowSubtitle(activeSection.id, row) }}</small>
              </span>
              <em v-if="rowState(activeSection.id, row)" :class="['entry-state', activeSection.id === 'summary' ? 'done' : 'progress']">
                {{ rowStateLabel(activeSection.id, row) }}
              </em>
              <span class="entry-buttons">
                <span aria-hidden="true"><el-icon><EditPen /></el-icon></span>
                <span aria-hidden="true" class="danger" @click.stop="removeRow(activeSection, row.id)"><el-icon><Delete /></el-icon></span>
              </span>
            </button>

            <div v-if="!activeSection.rows.length" class="empty-section">
              <span>当前分区还没有内容。</span>
              <button type="button" @click="beginAdd(activeSection)">新增内容</button>
            </div>
          </div>

          <button v-if="activeSection.rows.length > 6" class="entry-more" type="button">
            还有 {{ activeSection.rows.length - 6 }} 条内容
          </button>
        </section>

        <aside class="detail-panel">
          <template v-if="editing && selectedEditingRow">
            <header>
              <div>
                <h2>编辑条目</h2>
                <span>{{ sectionDisplayTitle(activeSection.title) }}</span>
              </div>
              <button type="button" @click="cancelEdit">×</button>
            </header>

            <div class="detail-panel-body">
              <label v-if="categoryEditingField" class="detail-field detail-field--category">
                <span>工作分类</span>
                <el-input v-model="editForm.category" placeholder="输入工作分类" @input="handleEditFieldInput('category')" />
              </label>

              <div v-if="editingStateField" class="detail-field">
                <span>{{ editingStateField.label }}</span>
                <div class="weekly-state-segment">
                  <button
                    v-for="option in editingStateOptions"
                    :key="option"
                    type="button"
                    :class="{ active: isEditStateActive(option) }"
                    @click="setEditState(option)"
                  >
                    {{ option }}
                  </button>
                </div>
              </div>

              <label v-if="primaryTextEditingField" class="detail-field detail-field--content">
                <span>{{ primaryTextEditingField.label }}</span>
                <div class="detail-field-tools ai-field-actions">
                  <button class="ai-prompt-button" type="button" @click="openPromptEditor(primaryTextEditingField)">提示词</button>
                  <button class="ai-polish-button" type="button" :disabled="fieldOptimizing !== ''" @click="optimizeEditField(primaryTextEditingField)">
                    <span aria-hidden="true">✦</span>
                    {{ fieldOptimizing === primaryTextEditingField.key ? '润色中' : 'AI 润色' }}
                  </button>
                </div>
                <el-input
                  v-model="editForm[primaryTextEditingField.key]"
                  type="textarea"
                  maxlength="2000"
                  show-word-limit
                  :autosize="{ minRows: 7, maxRows: 12 }"
                  @input="handleEditFieldInput(primaryTextEditingField.key)"
                />
              </label>

              <div v-if="primaryTextEditingField && primaryOptimizePreview" class="ai-compare-card">
                <div class="ai-compare-grid">
                  <section>
                    <span>原内容</span>
                    <p>{{ primaryOptimizePreview.original }}</p>
                  </section>
                  <section>
                    <span>优化结果</span>
                    <p>{{ primaryOptimizePreview.suggestion }}</p>
                  </section>
                </div>
                <div class="ai-compare-actions">
                  <button type="button" @click="undoOptimizePreview(primaryTextEditingField)">忽略</button>
                  <button type="button" class="primary" @click="acceptOptimizePreview(primaryTextEditingField)">采纳建议</button>
                </div>
              </div>

              <details class="detail-extra">
                <summary>补充信息（后续计划、当前进展说明、困难与求助）</summary>
                <label v-for="field in extraEditingFields" :key="field.key" class="detail-field">
                  <span>{{ field.label }}</span>
                  <el-input
                    v-model="editForm[field.key]"
                    type="textarea"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                    @input="handleEditFieldInput(field.key)"
                  />
                </label>
              </details>
            </div>

            <footer>
              <button type="button" @click="cancelEdit">取消</button>
              <button type="button" class="primary" @click="saveEdit">保存内容</button>
            </footer>
          </template>

          <div v-else class="detail-empty">
            <img class="detail-empty-icon" :src="weeklyEmptyPlaceholder" alt="" aria-hidden="true" />
            <strong>选择一条周报内容查看详情和编辑</strong>
            <p>点击左侧的周报内容，查看详细内容并继续完善；<br />或者新增一条内容，开始整理本周周报。</p>
          </div>
        </aside>
      </section>
    </section>

    <section v-else :class="['wizard-step', 'send-step', { 'send-step--report-collapsed': reportPanelCollapsed }]">
      <aside class="mail-report-panel" aria-label="报告文件">
        <header class="mail-report-panel__header">
          <div v-if="!reportPanelCollapsed">
            <strong>报告文件</strong>
            <span>{{ weeklyReports.length ? `共 ${weeklyReports.length} 份` : '暂无报告文件' }}</span>
          </div>
          <button
            class="mail-report-toggle"
            type="button"
            :aria-label="reportPanelCollapsed ? '展开报告文件栏' : '收起报告文件栏'"
            @click="reportPanelCollapsed = !reportPanelCollapsed"
          >
            <el-icon><Document /></el-icon>
            <span>{{ reportPanelCollapsed ? '展开' : '收起' }}</span>
          </button>
        </header>

        <div v-if="reportPanelCollapsed" class="mail-report-collapsed">
          <strong>{{ weeklyReports.length }}</strong>
          <span>报告</span>
        </div>

        <div v-else class="mail-report-list">
          <article
            v-for="report in weeklyReports"
            :key="report.name"
            :class="['mail-report-item', { active: selectedReport === report.name }]"
          >
            <button class="mail-report-main" type="button" :disabled="loading.draft" @click="loadDraft(report.name)">
              <strong>{{ report.name }}</strong>
              <span>{{ reportTypeText(report) }} · {{ reportDateTime(report) }}</span>
            </button>
            <button
              v-if="report.deletable"
              class="mail-report-delete"
              type="button"
              aria-label="删除报告文件"
              @click.stop="deleteReportItem(report)"
            >
              删除
            </button>
          </article>
          <div v-if="loading.reports" class="mail-report-empty">正在加载报告文件...</div>
          <div v-else-if="!weeklyReports.length" class="mail-report-empty">暂无报告文件</div>
        </div>
      </aside>

      <section class="mail-compose-card">
        <div class="mail-row mail-address-row">
          <span>收件人</span>
          <el-select
            v-model="toRecipients"
            multiple
            filterable
            allow-create
            default-first-option
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="3"
            placeholder="添加收件人"
            @paste.capture="handleRecipientPaste($event, 'to')"
          >
            <el-option v-for="item in toRecipients" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div class="mail-row mail-address-row">
          <span>抄送</span>
          <el-select
            v-model="ccRecipients"
            multiple
            filterable
            allow-create
            default-first-option
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="3"
            placeholder="添加抄送"
            @paste.capture="handleRecipientPaste($event, 'cc')"
          >
            <el-option v-for="item in ccRecipients" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div class="mail-row">
          <span>主题</span>
          <el-input v-model="mailDraft.subject" />
        </div>
        <div class="mail-body-preview-row">
          <span>邮件正文</span>
          <div class="mail-body-preview-wrap">
            <button class="mail-body-fullscreen" type="button" aria-label="全屏查看邮件正文" @click="mailBodyPreviewOpen = true">
              <el-icon><FullScreen /></el-icon>
            </button>
            <div class="mail-body-preview" v-html="mailBodyPreviewHtml"></div>
          </div>
        </div>
        <div class="mail-attachment-status">
          <span>附件状态</span>
          <button type="button" :disabled="!hasAttachmentPreview" @click="openAttachmentPreview">
            <span class="excel-icon">X</span>
            <span>
              <strong>{{ currentFileName || '等待生成附件' }}</strong>
              <small>{{ hasAttachmentPreview ? '点击预览附件内容' : '生成后可预览' }}</small>
            </span>
            <em>{{ previewStateText }}</em>
            <el-icon><View /></el-icon>
          </button>
        </div>
        <div v-if="sendBlockers.length" class="mail-send-warnings">
          <strong>发送前需处理</strong>
          <span v-for="item in sendBlockers" :key="item">{{ item }}</span>
        </div>
      </section>

    </section>

    <el-drawer
      v-model="historyPanelOpen"
      class="weekly-history-drawer"
      direction="rtl"
      size="42rem"
      append-to-body
      title="历史报告管理"
    >
      <section class="history-drawer-section history-drawer-section--upload">
        <header>
          <span class="history-drawer-icon"><el-icon><Upload /></el-icon></span>
          <div>
            <strong>上传历史周报</strong>
            <small>支持 .xlsx / .xls，文件会保存到当前账号历史报告库。</small>
          </div>
        </header>
        <button class="history-drawer-primary" type="button" :disabled="loading.uploadHistory" @click="triggerHistoryUpload">
          <el-icon><Upload /></el-icon>
          {{ loading.uploadHistory ? '上传中' : '选择并上传文件' }}
        </button>
        <input ref="historyUploadInput" class="hidden-file-input" type="file" multiple accept=".xlsx,.xls" @change="uploadWeeklyHistory" />
      </section>

      <section class="history-drawer-section">
        <header>
          <span class="history-drawer-icon"><el-icon><Document /></el-icon></span>
          <div>
            <strong>历史报告列表</strong>
            <small>{{ weeklyHistoryReports.length ? `共 ${weeklyHistoryReports.length} 份历史周报` : '暂无历史周报' }}</small>
          </div>
        </header>
        <div class="history-drawer-list">
          <article v-for="report in weeklyHistoryReports" :key="report.name" class="history-drawer-item">
            <div>
              <strong>{{ report.name }}</strong>
              <span>{{ reportTime(report) }}</span>
            </div>
            <a :href="reportDownloadUrl(report.name)" target="_blank" rel="noopener" aria-label="下载历史周报">
              <el-icon><Download /></el-icon>
            </a>
            <button v-if="report.deletable" type="button" aria-label="删除历史周报" @click="deleteReportItem(report)">
              <el-icon><Delete /></el-icon>
            </button>
          </article>
          <div v-if="!weeklyHistoryReports.length" class="history-empty">暂无历史周报。</div>
        </div>
      </section>

      <section v-if="authState.user?.is_admin" class="history-drawer-section history-template-card">
        <header>
          <span class="history-drawer-icon"><el-icon><Setting /></el-icon></span>
          <div>
            <strong>平台模板配置</strong>
            <small>{{ weeklyTemplate?.configured ? `当前模板：${weeklyTemplate.name}` : '周报未保存平台模板，生成时会先找历史报告。' }}</small>
          </div>
        </header>
        <div class="history-template-type">
          <span>模板类型</span>
          <strong>周报模板（.xlsx / .xls）</strong>
        </div>
        <div class="history-template-actions">
          <button type="button" :disabled="loading.template" @click="triggerTemplateUpload">
            <el-icon><Upload /></el-icon>
            {{ weeklyTemplate?.configured ? '替换平台模板' : '保存为平台模板' }}
          </button>
          <a v-if="weeklyTemplate?.configured" :href="weeklyTemplateDownloadUrl" target="_blank" rel="noopener">
            <el-icon><Download /></el-icon>
            下载当前模板编辑
          </a>
          <button v-if="weeklyTemplate?.configured" type="button" :disabled="loading.template" class="danger" @click="removeWeeklyTemplate">
            <el-icon><Delete /></el-icon>
            删除平台模板
          </button>
        </div>
        <p>平台模板会优先用于周报文件生成；删除后回退到历史报告或系统内置基础模板。</p>
        <input ref="templateUploadInput" class="hidden-file-input" type="file" accept=".xlsx,.xls" @change="uploadWeeklyTemplate" />
      </section>
    </el-drawer>

    <el-drawer
      v-model="attachmentPreviewOpen"
      class="weekly-attachment-drawer"
      direction="rtl"
      size="72%"
      append-to-body
      title="模板内容预览"
    >
      <section class="attachment-drawer-preview">
        <label class="attachment-preview-label">附件</label>
        <div class="attachment-preview-file">{{ currentFileName || `工作周报_${periodValue || '待生成'}.xlsx` }}</div>
        <label class="attachment-preview-label">模板内容预览</label>
        <div class="weekly-template-preview-card">
          <div v-if="mailDraft.preview_html" class="weekly-template-preview-html" v-html="mailDraft.preview_html"></div>
          <div v-else class="sheet-empty">暂无可预览内容。</div>
        </div>
      </section>
    </el-drawer>

    <el-dialog
      v-model="promptDialogVisible"
      class="weekly-prompt-dialog"
      :title="promptDialogTitle"
      width="min(62rem, 94vw)"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-input v-model="promptDraft" type="textarea" :autosize="{ minRows: 5, maxRows: 8 }" />
      <template #footer>
        <div class="weekly-prompt-actions prompt-dialog-actions">
          <el-button class="prompt-dialog-button" @click="promptEditor = ''">取消</el-button>
          <el-button class="prompt-dialog-button prompt-dialog-button--primary" @click="savePromptEditor">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="mailBodyPreviewOpen"
      class="mail-body-preview-dialog"
      title="邮件正文"
      fullscreen
      append-to-body
      destroy-on-close
    >
      <div class="mail-body-dialog-preview" v-html="mailBodyPreviewHtml"></div>
    </el-dialog>

    <section class="wizard-footer">
      <div>
        <strong v-if="activeStep === 1">已整理 {{ totalRows }} 条内容，系统已自动保存</strong>
        <strong v-else>{{ workflowSteps[activeStep - 1].title }}</strong>
        <span>{{ stepHint }}</span>
      </div>
      <div v-if="activeStep === 1" class="wizard-footer-actions">
        <button class="wizard-nav-button" type="button" @click="saveCurrentChanges">保存当前修改</button>
        <button class="wizard-nav-button primary" type="button" :disabled="stepActionDisabled" @click="nextStep">
          {{ nextActionText }}
        </button>
      </div>
      <div v-else class="wizard-footer-actions">
        <button class="wizard-nav-button" type="button" @click="previousStep">返回修改</button>
        <button class="wizard-nav-button" type="button" @click="copyBody">复制正文</button>
        <button class="wizard-nav-button" type="button" :disabled="!currentDownloadUrl" @click="downloadAttachment">下载附件</button>
        <button class="wizard-nav-button primary" type="button" :disabled="stepActionDisabled" @click="nextStep">
          {{ nextActionText }}
        </button>
      </div>
    </section>

  </section>
</template>
