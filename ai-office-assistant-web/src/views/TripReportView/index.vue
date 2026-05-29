<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  CopyDocument,
  Delete,
  Document,
  Download,
  Promotion,
  Setting,
  Upload,
  View,
} from '@element-plus/icons-vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import { authState, defaultOptimizePrompt } from '../../services/authSession'
import {
  deleteReportTemplate,
  deleteHistory,
  deleteReport,
  downloadUrl,
  generateTrip,
  getDraft,
  getMailConfig,
  getReportTemplates,
  getReports,
  getTripPrefill,
  optimizeText,
  saveReportTemplate,
  sendMail,
  templateDownloadUrl,
  uploadHistoryReports,
  type DraftResponse,
  type ReportFile,
  type ReportTemplateItem,
  type SendMailPayload,
  type TripPayload,
} from '../../services/personalWorkApi'
import './index.scss'

type TripFieldKey = keyof TripPayload
type TripTone = 'blue' | 'green' | 'orange' | 'violet' | 'mint'
type TripTabId = 'edit' | 'mail' | 'history'

interface TripField {
  key: TripFieldKey
  label: string
  multiline?: boolean
  type?: 'text' | 'date'
  required?: boolean
}

interface TripGroup {
  id: string
  title: string
  subtitle: string
  tone: TripTone
  fields: TripField[]
}

interface FieldOptimizePreview {
  original: string
  suggestion: string
}

const tripTabs: Array<{ id: TripTabId; label: string }> = [
  { id: 'edit', label: '编辑报告' },
  { id: 'mail', label: '邮件发送' },
  { id: 'history', label: '历史管理' },
]

const tripGroups: TripGroup[] = [
  {
    id: 'base',
    title: '基础信息',
    subtitle: '报告人、部门、地点与时间',
    tone: 'blue',
    fields: [
      { key: 'reporter', label: '报告人', type: 'text' },
      { key: 'department', label: '部门', type: 'text', required: true },
      { key: 'location', label: '出差地点', type: 'text', required: true },
      { key: 'trip_start', label: '开始日期', type: 'date', required: true },
      { key: 'trip_end', label: '结束日期', type: 'date', required: true },
    ],
  },
  {
    id: 'purpose',
    title: '出差目的',
    subtitle: '说明本次出差要解决的问题',
    tone: 'green',
    fields: [{ key: 'purpose', label: '出差目的', multiline: true, required: true }],
  },
  {
    id: 'itinerary',
    title: '行程概览',
    subtitle: '按时间梳理主要行程',
    tone: 'orange',
    fields: [{ key: 'itinerary', label: '行程概览', multiline: true, required: true }],
  },
  {
    id: 'details',
    title: '工作详情',
    subtitle: '沉淀现场工作和关键成果',
    tone: 'violet',
    fields: [{ key: 'details', label: '工作详情', multiline: true, required: true }],
  },
  {
    id: 'issues',
    title: '问题与反馈',
    subtitle: '记录问题、风险与待协同事项',
    tone: 'mint',
    fields: [{ key: 'issues', label: '问题与反馈', multiline: true }],
  },
  {
    id: 'suggestions',
    title: '总结与建议',
    subtitle: '形成后续建议和复盘结论',
    tone: 'blue',
    fields: [{ key: 'suggestions', label: '总结与建议', multiline: true }],
  },
]

const activeStep = ref(1)
const activeTab = ref<TripTabId>('edit')
const activeGroupId = ref('details')
const selectedReport = ref('')
const reports = ref<ReportFile[]>([])
const historyPanelOpen = ref(false)
const attachmentPreviewOpen = ref(false)
const reportPanelCollapsed = ref(false)
const historyUploadInput = ref<HTMLInputElement | null>(null)
const templateUploadInput = ref<HTMLInputElement | null>(null)
const historyFiles = ref<File[]>([])
const templateFile = ref<File | null>(null)
const tripTemplate = ref<ReportTemplateItem | null>(null)
const historyUploadStatus = ref('')
const activeOptimizeField = ref<TripFieldKey | ''>('')
const promptEditor = ref<TripFieldKey | ''>('')
const promptDraft = ref('')
const statusMessage = ref('')
const statusTone = ref<'normal' | 'ok' | 'error'>('normal')
const initialized = ref(false)
const isReportDirty = ref(true)
const previewSource = ref<'instant' | 'generated'>('instant')
const sendBlockers = ref<string[]>([])

const loading = reactive({
  init: false,
  reports: false,
  prefill: false,
  draft: false,
  generate: false,
  send: false,
  uploadHistory: false,
  template: false,
})

const tripForm = reactive<Record<TripFieldKey, string>>({
  reporter: '',
  department: '',
  location: '',
  trip_start: '',
  trip_end: '',
  trip_date_text: '',
  purpose: '',
  itinerary: '',
  details: '',
  issues: '',
  suggestions: '',
})

const promptForm = reactive<Partial<Record<TripFieldKey, string>>>({
  purpose: '',
  itinerary: '',
  details: '',
  issues: '',
  suggestions: '',
})

// AI 优化结果先暂存，用户确认采纳后才写回输入框。
const fieldOptimizePreview = reactive<Partial<Record<TripFieldKey, FieldOptimizePreview | null>>>({})

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

const tripReports = computed(() => reports.value.filter((report) => report.kind === 'trip'))
const tripHistoryReports = computed(() => tripReports.value.filter((report) => !report.generated))
const currentFileName = computed(() => mailDraft.attachment || selectedReport.value)
const currentDownloadUrl = computed(() => {
  if (mailDraft.download_url) return downloadUrl(mailDraft.download_url)
  const attachment = mailDraft.attachment || selectedReport.value
  return attachment ? downloadUrl(`/download?file=${encodeURIComponent(attachment)}`) : ''
})
const mailBodyPreviewHtml = computed(() => mailDraft.body_html || `<div>${textToHtml(mailDraft.body || '暂无正文内容')}</div>`)
const activeTripGroup = computed(() => tripGroups.find((group) => group.id === activeGroupId.value)!)
const activeMainField = computed(() => activeTripGroup.value.fields.find((field) => field.multiline))
const periodText = computed(() => formatTripDateText(tripForm.trip_start, tripForm.trip_end) || '未选择时间')
const filledRequiredCount = computed(() => requiredFields().filter((field) => tripForm[field.key]?.trim()).length)
const requiredCount = computed(() => requiredFields().length)
const completionPercent = computed(() => Math.round((filledRequiredCount.value / requiredCount.value) * 100))
const draftStorageKey = computed(() => (authState.user?.username ? `personalWorkSite.tripDraft.v1:${authState.user.username}` : ''))
const previewStateText = computed(() => {
  if (previewSource.value === 'instant' && !mailDraft.attachment) return '待生成附件'
  if (mailDraft.attachment && !isReportDirty.value) return '已生成'
  return mailDraft.attachment ? '待重新生成' : '待生成附件'
})
const stepHint = computed(() => {
  if (activeStep.value === 1) return `已完善 ${filledRequiredCount.value}/${requiredCount.value} 个必填项`
  return sendBlockers.value.length ? '请补齐发送信息后再确认' : '确认收件人、主题、正文和附件'
})
const nextActionText = computed(() => {
  if (activeStep.value === 1) return loading.generate ? '正在生成附件' : '生成附件并进入邮件发送'
  return loading.send ? '发送中' : '发送'
})
const stepActionDisabled = computed(() => loading.generate || loading.send)
const currentPromptField = computed(() => tripGroups.flatMap((group) => group.fields).find((field) => field.key === promptEditor.value))
const promptDialogTitle = computed(() => (currentPromptField.value ? `修改${currentPromptField.value.label}提示词` : '修改提示词'))
const promptDialogVisible = computed({
  get: () => Boolean(promptEditor.value),
  set: (visible: boolean) => {
    if (!visible) closePromptEditor()
  },
})
const toRecipients = computed({
  get: () => splitRecipients(mailDraft.to),
  set: (value: string[]) => {
    mailDraft.to = value.join(';')
  },
})
const ccRecipients = computed({
  get: () => splitRecipients(mailDraft.cc),
  set: (value: string[]) => {
    mailDraft.cc = value.join(';')
  },
})

watch(
  tripForm,
  () => {
    if (!initialized.value) return
    markReportDirty()
    saveTripDraft()
  },
  { deep: true },
)

watch(
  () => [mailDraft.to, mailDraft.cc, mailDraft.subject, mailDraft.body, mailDraft.attachment],
  () => clearSendReview(),
)

function setStatus(message: string, tone: 'normal' | 'ok' | 'error' = 'normal') {
  statusMessage.value = message
  statusTone.value = tone
}

function escapeHtml(value: string) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] || char)
}

function textToHtml(value: string) {
  return escapeHtml(value).replace(/\n/g, '<br>')
}

function splitRecipients(value: string) {
  return value.split(/[;,，；\s]+/).map((item) => item.trim()).filter(Boolean)
}

function stepForTab(tab: TripTabId) {
  if (tab === 'mail') return 2
  return 1
}

async function switchTripTab(tab: TripTabId) {
  if (tab === 'history') {
    void openHistoryDrawer()
    return
  }
  activeTab.value = tab
  activeStep.value = stepForTab(tab)
  if (tab === 'mail') await loadTripMailRecipients()
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

function formatDateForCn(value: string) {
  const [year, month, day] = String(value || '').split('-').map(Number)
  return year && month && day ? `${year}年${String(month).padStart(2, '0')}月${String(day).padStart(2, '0')}日` : value
}

function formatTripDateText(start: string, end: string) {
  const startText = formatDateForCn(start)
  const endText = formatDateForCn(end)
  return startText && endText ? `${startText}至${endText}` : startText || endText
}

function formatReportTime(report: ReportFile) {
  return new Date(report.mtime * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function reportTypeText(report: ReportFile) {
  return report.generated ? '已生成报告' : '历史报告'
}

function setDefaultTripDates() {
  const today = new Date()
  const end = new Date(today)
  end.setDate(today.getDate() + 2)
  if (!tripForm.trip_start) tripForm.trip_start = toDateInputValue(today)
  if (!tripForm.trip_end) tripForm.trip_end = toDateInputValue(end)
}

function requiredFields() {
  return tripGroups.flatMap((group) => group.fields).filter((field) => field.required)
}

function canOptimizeField(field: TripField) {
  return Boolean(field.multiline)
}

function optimizePrompt(fieldKey: TripFieldKey) {
  return promptForm[fieldKey] || defaultOptimizePrompt()
}

function groupPreview(group: TripGroup) {
  const values = group.fields
    .map((field) => {
      const value = tripForm[field.key]?.trim()
      if (!value) return ''
      return group.id === 'base' ? `${field.label}：${field.type === 'date' ? formatDateForCn(value) : value}` : value
    })
    .filter(Boolean)
  return values.join('\n') || group.subtitle
}

function groupFilledCount(group: TripGroup) {
  return group.fields.filter((field) => tripForm[field.key]?.trim()).length
}

function groupCompletionLabel(group: TripGroup) {
  const filled = groupFilledCount(group)
  if (filled === group.fields.length) return '已完成'
  if (filled > 0) return '80%'
  return '待完善'
}

function groupCompletionState(group: TripGroup) {
  const filled = groupFilledCount(group)
  if (filled === group.fields.length) return 'done'
  if (filled > 0) return 'progress'
  return 'pending'
}

function selectTripGroup(groupId: string) {
  activeGroupId.value = groupId
}

function handleEditInput(fieldKey: TripFieldKey) {
  fieldOptimizePreview[fieldKey] = null
}

function openPromptEditor(field: TripField) {
  if (!canOptimizeField(field)) return
  promptEditor.value = field.key
  promptDraft.value = optimizePrompt(field.key)
}

function closePromptEditor() {
  promptEditor.value = ''
  promptDraft.value = ''
}

function savePromptEditor() {
  if (!promptEditor.value) return
  promptForm[promptEditor.value] = promptDraft.value.trim()
  closePromptEditor()
  ElMessage.success('提示词已更新')
}

function undoOptimizePreview(field: TripField) {
  fieldOptimizePreview[field.key] = null
}

async function optimizeTripField(field: TripField) {
  if (!canOptimizeField(field)) return
  const original = tripForm[field.key]?.trim() || ''
  if (!original) {
    ElMessage.warning('请先填写需要优化的内容')
    return
  }
  activeOptimizeField.value = field.key
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
    activeOptimizeField.value = ''
  }
}

function acceptTripOptimizePreview(field: TripField) {
  const preview = fieldOptimizePreview[field.key]
  if (!preview) return
  tripForm[field.key] = preview.suggestion
  fieldOptimizePreview[field.key] = null
}

function saveTripDraft() {
  const key = draftStorageKey.value
  if (!key) return
  localStorage.setItem(key, JSON.stringify({ updatedAt: Date.now(), trip: { ...tripForm } }))
}

function restoreTripDraft() {
  const key = draftStorageKey.value
  if (!key) return false
  try {
    const draft = JSON.parse(localStorage.getItem(key) || 'null')
    if (!draft?.trip) return false
    Object.keys(tripForm).forEach((keyName) => {
      const fieldKey = keyName as TripFieldKey
      if (draft.trip[fieldKey] !== undefined && draft.trip[fieldKey] !== null) tripForm[fieldKey] = String(draft.trip[fieldKey])
    })
    return true
  } catch {
    return false
  }
}

function clearTripDraft() {
  const key = draftStorageKey.value
  if (key) localStorage.removeItem(key)
}

function applyTripPrefill(prefill: TripPayload) {
  tripForm.reporter = authState.user?.name || authState.user?.username || prefill.reporter || ''
  tripForm.department = prefill.department || '场景研究院'
  tripForm.location = prefill.location || ''
  tripForm.trip_start = prefill.trip_start || tripForm.trip_start
  tripForm.trip_end = prefill.trip_end || tripForm.trip_end
  tripForm.trip_date_text = prefill.trip_date_text || formatTripDateText(tripForm.trip_start, tripForm.trip_end)
  tripForm.purpose = prefill.purpose || ''
  tripForm.itinerary = prefill.itinerary || ''
  tripForm.details = prefill.details || ''
  tripForm.issues = prefill.issues || ''
  tripForm.suggestions = prefill.suggestions || ''
}

async function loadTripPrefill(force = false) {
  loading.prefill = true
  if (force) clearTripDraft()
  try {
    const prefill = await getTripPrefill()
    setDefaultTripDates()
    if (prefill.error) {
      applyTripPrefill({})
      setStatus(prefill.error, 'error')
      return false
    }
    applyTripPrefill(prefill)
    const restored = force ? false : restoreTripDraft()
    setStatus(
      prefill.source
        ? restored ? '已恢复上次未生成的出差报告草稿' : `已获取最新历史出差报告：${prefill.source}`
        : '没有找到可用于预填的历史出差报告，已生成空白模板',
      prefill.source ? 'ok' : 'normal',
    )
    return true
  } catch (error) {
    setDefaultTripDates()
    applyTripPrefill({})
    setStatus(error instanceof Error ? error.message : '历史出差报告预填失败', 'error')
    return false
  } finally {
    loading.prefill = false
    refreshInstantPreview()
    saveTripDraft()
  }
}

async function loadReports() {
  loading.reports = true
  try {
    const data = await getReports()
    reports.value = data.reports.filter((report) => report.kind === 'trip')
  } finally {
    loading.reports = false
  }
}

function applyDraft(draft: DraftResponse) {
  mailDraft.to = draft.to || ''
  mailDraft.cc = draft.cc || ''
  mailDraft.subject = draft.subject || instantMailSubject()
  mailDraft.body = draft.body || ''
  mailDraft.body_html = draft.body_html || ''
  mailDraft.attachment = draft.attachment || ''
  mailDraft.download_url = draft.download_url || ''
  mailDraft.preview = draft.preview || ''
  mailDraft.preview_html = draft.preview_html || ''
  previewSource.value = draft.attachment ? 'generated' : 'instant'
  isReportDirty.value = false
  clearSendReview()
}

async function loadTripMailRecipients() {
  if (mailDraft.to && mailDraft.cc) return
  try {
    const config = await getMailConfig()
    if (!mailDraft.to) mailDraft.to = config.trip_to || ''
    if (!mailDraft.cc) mailDraft.cc = config.trip_cc || ''
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '邮件配置读取失败', 'error')
  }
}

async function loadDraft(name: string) {
  if (!name) return
  loading.draft = true
  try {
    const draft = await getDraft('trip', name)
    applyDraft(draft)
    selectedReport.value = name
    switchTripTab('mail')
    setStatus(`已加载报告：${name}`, 'ok')
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '报告加载失败', 'error')
  } finally {
    loading.draft = false
  }
}

function markReportDirty() {
  isReportDirty.value = true
  selectedReport.value = ''
  mailDraft.attachment = ''
  mailDraft.download_url = ''
  refreshInstantPreview()
  clearSendReview()
}

function instantMailSubject() {
  const location = tripForm.location || '出差'
  return `【出差报告】${location}出差报告`
}

function instantTripPreviewHtml() {
  const sections = [
    ['出差目的', tripForm.purpose],
    ['行程概览', tripForm.itinerary],
    ['工作详情', tripForm.details],
    ['问题与反馈', tripForm.issues],
    ['总结与建议', tripForm.suggestions],
  ]
  const sectionHtml = sections
    .filter(([, value]) => String(value || '').trim())
    .map(([title, value]) => `<p class="trip-preview-section">${escapeHtml(title)}</p><p>${textToHtml(String(value || ''))}</p>`)
    .join('')
  return `
    <table class="trip-preview-table">
      <tbody>
        <tr><th>报告人</th><td>${escapeHtml(tripForm.reporter || '')}</td><th>部门</th><td>${escapeHtml(tripForm.department || '')}</td><th>出差地点</th><td>${escapeHtml(tripForm.location || '')}</td></tr>
        <tr><th>出差时间</th><td colspan="5">${escapeHtml(periodText.value)}</td></tr>
      </tbody>
    </table>
    ${sectionHtml || '<p class="trip-preview-empty">还没有填写出差内容。</p>'}
  `
}

function instantMailBody() {
  const blocks = [
    ['出差地点', tripForm.location],
    ['出差时间', periodText.value],
    ['出差目的', tripForm.purpose],
    ['行程概览', tripForm.itinerary],
    ['工作详情', tripForm.details],
    ['问题与反馈', tripForm.issues],
    ['总结与建议', tripForm.suggestions],
  ]
    .filter(([, value]) => String(value || '').trim())
    .map(([label, value]) => `【${label}】\n${value}`)
  return `领导您好：\n\n以下是我的出差报告，请查阅。\n\n${blocks.join('\n\n')}\n\n${todayText()}`
}

function instantMailHtml() {
  const intro = currentFileName.value
    ? `附件为我的出差报告《${escapeHtml(currentFileName.value)}》，请查收。`
    : '以下是我的出差报告，请查阅。'
  return `<p>领导您好：</p><p>${intro}</p>${instantTripPreviewHtml()}<p>${todayText()}</p>`
}

function refreshInstantPreview() {
  mailDraft.subject = instantMailSubject()
  mailDraft.body = instantMailBody()
  mailDraft.body_html = instantMailHtml()
  mailDraft.preview = ''
  mailDraft.preview_html = instantTripPreviewHtml()
  previewSource.value = 'instant'
}

function validateTripForm() {
  const missing = requiredFields().filter((field) => !tripForm[field.key]?.trim()).map((field) => field.label)
  if (!missing.length) return true
  ElMessage.warning(`请先填写${missing.join('、')}`)
  switchTripTab('edit')
  return false
}

function tripPayload(): TripPayload {
  return {
    reporter: tripForm.reporter,
    department: tripForm.department,
    location: tripForm.location,
    trip_start: tripForm.trip_start,
    trip_end: tripForm.trip_end,
    trip_date_text: formatTripDateText(tripForm.trip_start, tripForm.trip_end),
    purpose: tripForm.purpose,
    itinerary: tripForm.itinerary,
    details: tripForm.details,
    issues: tripForm.issues,
    suggestions: tripForm.suggestions,
  }
}

async function generateReport() {
  if (!validateTripForm()) return false
  loading.generate = true
  setStatus('正在生成出差报告附件...', 'normal')
  try {
    const result = await generateTrip({ kind: 'trip', ...tripPayload() })
    clearTripDraft()
    await loadReports()
    applyDraft(result.draft)
    selectedReport.value = result.file
    switchTripTab('mail')
    setStatus(`已生成标准出差报告，并设为当前邮件附件：${result.file}`, 'ok')
    return true
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '出差报告生成失败', 'error')
    return false
  } finally {
    loading.generate = false
  }
}

function buildSendPayload(): SendMailPayload {
  return {
    to: mailDraft.to.trim(),
    cc: mailDraft.cc.trim(),
    subject: mailDraft.subject.trim(),
    body: mailDraft.body.trim(),
    body_html: mailDraft.body_html,
    attachment: mailDraft.attachment || selectedReport.value,
  }
}

function findSendBlockers(payload: SendMailPayload) {
  const blockers: string[] = []
  if (!payload.to) blockers.push('收件人为空')
  if (!payload.subject) blockers.push('主题为空')
  if (!payload.body && !payload.body_html) blockers.push('正文为空')
  if (!payload.attachment) blockers.push('附件为空')
  return blockers
}

function clearSendReview() {
  sendBlockers.value = []
}

async function sendReport() {
  const payload = buildSendPayload()
  const blockers = findSendBlockers(payload)
  sendBlockers.value = blockers
  if (blockers.length) {
    ElMessage.warning(blockers.join('；'))
    return
  }
  loading.send = true
  try {
    const result = await sendMail(payload)
    ElMessage.success(result.mode === 'sent' ? '邮件已发送' : result.message)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '发送失败', 'error')
  } finally {
    loading.send = false
  }
}

async function deleteReportItem(report: ReportFile) {
  await ElMessageBox.confirm(`确定删除这个报告文件吗？\n${report.name}`, '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  const result = report.generated ? await deleteReport(report.name) : await deleteHistory(report.name)
  if (selectedReport.value === report.name) {
    selectedReport.value = ''
    refreshInstantPreview()
  }
  await loadReports()
  ElMessage.success(`已删除：${result.deleted}`)
}

function downloadAttachment() {
  if (!currentDownloadUrl.value) {
    ElMessage.warning('暂无可下载附件')
    return
  }
  window.open(currentDownloadUrl.value, '_blank')
}

function openAttachmentPreview() {
  if (!mailDraft.preview_html && !mailDraft.body_html) {
    ElMessage.warning('暂无可预览附件')
    return
  }
  attachmentPreviewOpen.value = true
}

async function copyBody() {
  if (!mailDraft.body) {
    ElMessage.warning('暂无可复制正文')
    return
  }
  await navigator.clipboard.writeText(mailDraft.body)
  ElMessage.success('正文已复制')
}

function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

async function openHistoryDrawer() {
  historyPanelOpen.value = true
  await Promise.all([loadReports(), loadReportTemplates()])
}

function reportDownloadUrl(name: string) {
  return downloadUrl(`/download?file=${encodeURIComponent(name)}`)
}

function triggerHistoryUpload() {
  historyUploadInput.value?.click()
}

function triggerTemplateUpload() {
  templateUploadInput.value?.click()
}

function handleHistoryFilesChange(event: Event) {
  const input = event.target as HTMLInputElement
  historyFiles.value = Array.from(input.files || [])
  if (historyFiles.value.length) void uploadTripHistory()
}

function handleTemplateFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  templateFile.value = input.files?.[0] || null
  if (templateFile.value) void saveTripTemplate()
}

async function uploadTripHistory() {
  if (!historyFiles.value.length) {
    ElMessage.warning('请先选择历史出差报告文件')
    return
  }
  loading.uploadHistory = true
  historyUploadStatus.value = '正在上传历史出差报告...'
  try {
    const files = []
    for (const file of historyFiles.value) files.push({ name: file.name, data: await readFileAsBase64(file) })
    const result = await uploadHistoryReports('trip', files)
    historyUploadStatus.value = `已上传 ${result.uploaded.length} 份历史出差报告`
    historyFiles.value = []
    if (historyUploadInput.value) historyUploadInput.value.value = ''
    await loadReports()
    ElMessage.success(historyUploadStatus.value)
  } catch (error) {
    historyUploadStatus.value = error instanceof Error ? error.message : '历史报告上传失败'
    ElMessage.error(historyUploadStatus.value)
  } finally {
    loading.uploadHistory = false
  }
}

async function loadReportTemplates() {
  loading.template = true
  try {
    const result = await getReportTemplates()
    tripTemplate.value = result.templates.trip
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '平台模板读取失败')
  } finally {
    loading.template = false
  }
}

async function saveTripTemplate() {
  if (!templateFile.value) {
    ElMessage.warning('请先选择出差报告平台模板文件')
    return
  }
  loading.template = true
  try {
    const result = await saveReportTemplate('trip', { name: templateFile.value.name, data: await readFileAsBase64(templateFile.value) })
    templateFile.value = null
    if (templateUploadInput.value) templateUploadInput.value.value = ''
    await loadReportTemplates()
    ElMessage.success(`出差报告平台模板已保存：${result.template.name}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '平台模板保存失败')
  } finally {
    loading.template = false
  }
}

async function removeTripTemplate() {
  await ElMessageBox.confirm('确定删除当前出差报告平台模板吗？删除后会回退到历史报告或内置基础模板。', '删除平台模板', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  loading.template = true
  try {
    const result = await deleteReportTemplate('trip')
    tripTemplate.value = result.templates.trip
    ElMessage.success(result.deleted.length ? '已删除出差报告平台模板' : '当前没有可删除的出差报告平台模板')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '平台模板删除失败')
  } finally {
    loading.template = false
  }
}

async function nextStep() {
  if (activeTab.value === 'edit') {
    await generateReport()
    return
  }
  if (activeTab.value === 'mail') await sendReport()
}

function previousStep() {
  if (activeTab.value === 'mail') switchTripTab('edit')
}

async function initializeTrip() {
  loading.init = true
  try {
    setDefaultTripDates()
    await Promise.all([loadReports(), loadTripPrefill(false)])
    const latestGenerated = reports.value.find((report) => report.generated)
    if (latestGenerated) {
      await loadDraft(latestGenerated.name)
      switchTripTab('edit')
    } else {
      refreshInstantPreview()
    }
    initialized.value = true
  } finally {
    loading.init = false
  }
}

onMounted(initializeTrip)
</script>

<template>
  <section class="trip-main">
    <header class="trip-page-head">
      <div>
        <h1>{{ activeTab === 'mail' ? '邮件发送' : '出差报告助手' }}</h1>
        <p>
          {{
            activeTab === 'mail'
              ? '确认收件人、正文和附件后发送。'
              : '填写出差基础信息与正文内容，支持 AI 润色和历史报告预填。'
          }}
        </p>
      </div>
      <nav class="trip-tabs" aria-label="出差报告功能页签">
        <button
          v-for="tab in tripTabs"
          :key="tab.id"
          :class="{ active: activeTab === tab.id }"
          type="button"
          @click="switchTripTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </nav>
    </header>

    <section v-if="activeTab === 'edit'" class="trip-tab-panel trip-edit-panel">
      <section class="trip-edit-toolbar">
        <label>
          <span>开始日期</span>
          <el-date-picker v-model="tripForm.trip_start" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </label>
        <label>
          <span>结束日期</span>
          <el-date-picker v-model="tripForm.trip_end" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </label>
        <div class="trip-toolbar-spacer"></div>
        <IconTextButton icon="history" :disabled="loading.prefill" @click="loadTripPrefill(true)">
          获取最新历史报告
        </IconTextButton>
      </section>

      <section class="trip-edit-board">
        <aside class="trip-chapter-nav" aria-label="报告章节">
          <h2>报告章节</h2>
          <button
            v-for="(group, index) in tripGroups"
            :key="group.id"
            :class="['trip-chapter-item', { active: activeGroupId === group.id }, groupCompletionState(group)]"
            type="button"
            @click="selectTripGroup(group.id)"
          >
            <span class="trip-chapter-copy">
              <span class="trip-chapter-title">{{ index + 1 }}. {{ group.title }}</span>
              <small>{{ groupPreview(group) }}</small>
            </span>
            <span class="trip-chapter-state">
              <el-icon v-if="groupCompletionState(group) === 'done'" class="trip-chapter-check"><Check /></el-icon>
              <i v-else-if="groupCompletionState(group) === 'progress'" class="trip-chapter-mark progress"></i>
              <i v-else class="trip-chapter-mark pending"></i>
              {{ groupCompletionLabel(group) }}
            </span>
          </button>
        </aside>

        <section class="trip-editor-panel">
          <header class="trip-section-titlebar">
            <div>
              <h2>编辑章节</h2>
              <span>{{ activeTripGroup.title }}</span>
            </div>
            <div v-if="activeMainField" class="trip-editor-actions ai-field-actions">
              <button class="ai-prompt-button" type="button" @click="openPromptEditor(activeMainField)">
                提示词
              </button>
              <button class="ai-polish-button" type="button" :disabled="activeOptimizeField !== ''" @click="optimizeTripField(activeMainField)">
                <span aria-hidden="true">✦</span>
                {{ activeOptimizeField === activeMainField.key ? '润色中' : 'AI 润色' }}
              </button>
            </div>
          </header>

          <div v-if="activeTripGroup.id === 'base'" class="trip-base-grid">
            <label v-for="field in activeTripGroup.fields" :key="field.key">
              <span>{{ field.label }}</span>
              <el-date-picker
                v-if="field.type === 'date'"
                v-model="tripForm[field.key]"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                @change="handleEditInput(field.key)"
              />
              <el-input v-else v-model="tripForm[field.key]" @input="handleEditInput(field.key)" />
            </label>
          </div>

          <div v-else-if="activeMainField" class="trip-editor-content">
            <label :aria-label="activeMainField.label">
              <div class="trip-editor-textarea-wrap">
              <el-input
                v-model="tripForm[activeMainField.key]"
                type="textarea"
                :autosize="{ minRows: 9, maxRows: 15 }"
                maxlength="2000"
                @input="handleEditInput(activeMainField.key)"
              />
                <span class="trip-word-limit">{{ (tripForm[activeMainField.key] || '').length }} / 2000</span>
              </div>
            </label>
            <div v-if="fieldOptimizePreview[activeMainField.key]" class="trip-ai-compare-card">
              <div class="trip-ai-compare-grid">
                <section>
                  <span>原内容</span>
                  <p>{{ fieldOptimizePreview[activeMainField.key]?.original }}</p>
                </section>
                <section>
                  <span>优化结果</span>
                  <p>{{ fieldOptimizePreview[activeMainField.key]?.suggestion }}</p>
                </section>
              </div>
              <div class="trip-ai-compare-actions">
                <button type="button" @click="undoOptimizePreview(activeMainField)">撤销</button>
                <button type="button" class="primary" @click="acceptTripOptimizePreview(activeMainField)">采纳</button>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section class="trip-action-bar">
        <div :class="['trip-auto-save', statusTone]">
          <strong>完成进度：{{ completionPercent }}%</strong>
          <span>{{ statusMessage || stepHint }}</span>
        </div>
        <div class="trip-action-buttons">
          <button class="trip-footer-button primary" type="button" :disabled="stepActionDisabled" @click="nextStep">
            <el-icon><Promotion /></el-icon>
            {{ nextActionText }}
          </button>
        </div>
      </section>
    </section>

    <section v-else-if="activeTab === 'mail'" :class="['trip-tab-panel', 'trip-mail-panel', { 'trip-mail-panel--report-collapsed': reportPanelCollapsed }]">
      <aside class="trip-mail-report-panel" aria-label="报告文件">
        <header class="trip-mail-report-panel__header">
          <div v-if="!reportPanelCollapsed">
            <strong>报告文件</strong>
            <span>{{ tripReports.length ? `共 ${tripReports.length} 份` : '暂无报告文件' }}</span>
          </div>
          <button
            class="trip-mail-report-toggle"
            type="button"
            :aria-label="reportPanelCollapsed ? '展开报告文件栏' : '收起报告文件栏'"
            @click="reportPanelCollapsed = !reportPanelCollapsed"
          >
            <el-icon><Document /></el-icon>
            <span>{{ reportPanelCollapsed ? '展开' : '收起' }}</span>
          </button>
        </header>

        <div v-if="reportPanelCollapsed" class="trip-mail-report-collapsed">
          <strong>{{ tripReports.length }}</strong>
          <span>报告</span>
        </div>

        <div v-else class="trip-mail-report-list">
          <article
            v-for="report in tripReports"
            :key="report.name"
            :class="['trip-mail-report-item', { active: selectedReport === report.name }]"
          >
            <button class="trip-mail-report-main" type="button" :disabled="loading.draft" @click="loadDraft(report.name)">
              <strong>{{ report.name }}</strong>
              <span>{{ reportTypeText(report) }} · {{ formatReportTime(report) }}</span>
            </button>
            <button
              v-if="report.deletable"
              class="trip-mail-report-delete"
              type="button"
              aria-label="删除报告文件"
              @click.stop="deleteReportItem(report)"
            >
              删除
            </button>
          </article>
          <div v-if="loading.reports" class="trip-mail-report-empty">正在加载报告文件...</div>
          <div v-else-if="!tripReports.length" class="trip-mail-report-empty">暂无报告文件</div>
        </div>
      </aside>

      <section class="trip-mail-compose">
        <div class="trip-mail-form">
          <label>
            <span>收件人 <em>*</em></span>
            <el-select v-model="toRecipients" multiple filterable allow-create default-first-option placeholder="添加收件人">
              <el-option v-for="item in toRecipients" :key="item" :label="item" :value="item" />
            </el-select>
          </label>
          <label>
            <span>抄送</span>
            <el-select v-model="ccRecipients" multiple filterable allow-create default-first-option placeholder="添加抄送">
              <el-option v-for="item in ccRecipients" :key="item" :label="item" :value="item" />
            </el-select>
          </label>
          <label>
            <span>主题 <em>*</em></span>
            <el-input v-model="mailDraft.subject" />
          </label>
          <div class="trip-mail-body-preview-row">
            <span>邮件正文 <em>*</em></span>
            <div class="trip-mail-body-preview trip-html" v-html="mailBodyPreviewHtml"></div>
          </div>
          <div class="trip-mail-attachment-status">
            <span class="trip-mail-field-label">附件状态</span>
            <button type="button" :disabled="!mailDraft.preview_html && !mailDraft.body_html" @click="openAttachmentPreview">
              <span class="trip-word-icon">W</span>
              <span class="trip-attachment-copy">
                <strong>{{ currentFileName || '等待生成附件' }}</strong>
                <small>{{ mailDraft.preview_html || mailDraft.body_html ? '点击预览附件内容' : '生成后可预览' }}</small>
              </span>
              <em>{{ previewStateText }}</em>
              <el-icon><View /></el-icon>
            </button>
          </div>
          <div v-if="sendBlockers.length" class="trip-mail-warnings">
            <strong>发送前需处理</strong>
            <span v-for="item in sendBlockers" :key="item">{{ item }}</span>
          </div>
        </div>
      </section>
      <section class="trip-action-bar">
        <div :class="['trip-auto-save', sendBlockers.length ? 'error' : 'normal']">
          <strong>{{ sendBlockers.length ? '发送前需处理' : '确认邮件内容' }}</strong>
          <span>{{ stepHint }}</span>
        </div>
        <div class="trip-action-buttons">
          <button class="trip-footer-button" type="button" @click="previousStep">返回修改</button>
          <button class="trip-footer-button" type="button" @click="copyBody">
            <el-icon><CopyDocument /></el-icon>
            复制正文
          </button>
          <button class="trip-footer-button" type="button" :disabled="!currentDownloadUrl" @click="downloadAttachment">
            <el-icon><Download /></el-icon>
            下载附件
          </button>
          <button class="trip-footer-button primary" type="button" :disabled="loading.send" @click="sendReport">
            <el-icon><Promotion /></el-icon>
            {{ loading.send ? '发送中' : '发送' }}
          </button>
        </div>
      </section>
    </section>

    <el-drawer
      v-model="attachmentPreviewOpen"
      class="trip-attachment-drawer"
      direction="rtl"
      size="72%"
      append-to-body
      title="附件预览"
    >
      <section class="trip-attachment-drawer-preview">
        <header>
          <div>
            <span>当前附件</span>
            <strong>{{ currentFileName || `出差报告_${periodText}` }}</strong>
          </div>
          <IconTextButton icon="download" size="md" :disabled="!currentDownloadUrl" @click="downloadAttachment">下载附件</IconTextButton>
        </header>
        <article class="trip-attachment-paper trip-attachment-paper--drawer">
          <div v-if="mailDraft.preview_html || mailDraft.body_html" class="trip-html" v-html="mailDraft.preview_html || mailDraft.body_html"></div>
          <div v-else class="trip-empty">暂无可预览内容。</div>
        </article>
      </section>
    </el-drawer>

    <el-drawer
      v-model="historyPanelOpen"
      class="trip-history-drawer"
      direction="rtl"
      size="420px"
      append-to-body
      title="历史报告管理"
    >
      <section class="history-drawer-section history-drawer-section--upload">
        <header>
          <span class="history-drawer-icon"><el-icon><Upload /></el-icon></span>
          <div>
            <strong>上传历史出差报告</strong>
            <small>支持 .docx / .md，文件会保存到当前账号历史报告库。</small>
          </div>
        </header>
        <button class="history-drawer-primary" type="button" :disabled="loading.uploadHistory" @click="triggerHistoryUpload">
          <el-icon><Upload /></el-icon>
          {{ loading.uploadHistory ? '上传中' : '选择并上传文件' }}
        </button>
        <p v-if="historyUploadStatus" class="history-drawer-status">{{ historyUploadStatus }}</p>
        <input ref="historyUploadInput" class="hidden-file-input" type="file" multiple accept=".docx,.md" @change="handleHistoryFilesChange" />
      </section>

      <section class="history-drawer-section">
        <header>
          <span class="history-drawer-icon"><el-icon><Document /></el-icon></span>
          <div>
            <strong>历史报告列表</strong>
            <small>{{ tripHistoryReports.length ? `共 ${tripHistoryReports.length} 份历史出差报告` : '暂无历史出差报告' }}</small>
          </div>
        </header>
        <div class="history-drawer-list">
          <article v-for="report in tripHistoryReports" :key="report.name" class="history-drawer-item">
            <div>
              <strong>{{ report.name }}</strong>
              <span>{{ formatReportTime(report) }}</span>
            </div>
            <a :href="reportDownloadUrl(report.name)" target="_blank" rel="noopener" aria-label="下载历史出差报告">
              <el-icon><Download /></el-icon>
            </a>
            <button v-if="report.deletable" type="button" aria-label="删除历史出差报告" @click="deleteReportItem(report)">
              <el-icon><Delete /></el-icon>
            </button>
          </article>
          <div v-if="!tripHistoryReports.length" class="trip-history-empty">暂无历史出差报告。</div>
        </div>
      </section>

      <section v-if="authState.user?.is_admin" class="history-drawer-section history-template-card">
        <header>
          <span class="history-drawer-icon"><el-icon><Setting /></el-icon></span>
          <div>
            <strong>平台模板配置</strong>
            <small>{{ tripTemplate?.configured ? `当前模板：${tripTemplate.name}` : '出差报告未保存平台模板，生成时会先找历史报告。' }}</small>
          </div>
        </header>
        <div class="history-template-type">
          <span>模板类型</span>
          <strong>出差报告模板（.docx）</strong>
        </div>
        <div class="history-template-actions">
          <button type="button" :disabled="loading.template" @click="triggerTemplateUpload">
            <el-icon><Upload /></el-icon>
            {{ tripTemplate?.configured ? '替换平台模板' : '保存为平台模板' }}
          </button>
          <a v-if="tripTemplate?.configured" :href="templateDownloadUrl('trip')" target="_blank" rel="noopener">
            <el-icon><Download /></el-icon>
            下载当前模板编辑
          </a>
          <button v-if="tripTemplate?.configured" type="button" :disabled="loading.template" class="danger" @click="removeTripTemplate">
            <el-icon><Delete /></el-icon>
            删除平台模板
          </button>
        </div>
        <p>平台模板会优先用于出差报告文件生成；删除后回退到历史报告或系统内置基础模板。</p>
        <input ref="templateUploadInput" class="hidden-file-input" type="file" accept=".docx" @change="handleTemplateFileChange" />
      </section>
    </el-drawer>

    <el-dialog
      v-model="promptDialogVisible"
      class="trip-prompt-dialog"
      :title="promptDialogTitle"
      width="min(620px, 94vw)"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-input v-model="promptDraft" type="textarea" :autosize="{ minRows: 5, maxRows: 8 }" />
      <template #footer>
        <div class="trip-prompt-actions prompt-dialog-actions">
          <el-button class="prompt-dialog-button" @click="closePromptEditor">取消</el-button>
          <el-button class="prompt-dialog-button prompt-dialog-button--primary" @click="savePromptEditor">保存</el-button>
        </div>
      </template>
    </el-dialog>

  </section>
</template>
