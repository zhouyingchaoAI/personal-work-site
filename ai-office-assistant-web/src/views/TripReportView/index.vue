<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, EditPen } from '@element-plus/icons-vue'
import AssistantChat from '../../components/AssistantChat/index.vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import { authState } from '../../services/authSession'
import {
  agentChat,
  deleteHistory,
  deleteReport,
  downloadUrl,
  generateTrip,
  getDraft,
  getReports,
  getTripPrefill,
  optimizeText,
  resourceUrl,
  sendMail,
  type AgentMessage,
  type DraftResponse,
  type ReportFile,
  type SendMailPayload,
  type TripPayload,
} from '../../services/personalWorkApi'
import './index.scss'

type TripFieldKey = keyof TripPayload
type TripTone = 'blue' | 'green' | 'orange' | 'violet' | 'mint'

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

const workflowSteps = [
  { id: 1, title: '填写内容', description: '整理出差信息' },
  { id: 2, title: '生成预览', description: '生成报告与邮件预览' },
  { id: 3, title: '确认发送', description: '确认无误后发送邮件' },
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

const fieldPrompts: Partial<Record<TripFieldKey, string>> = {
  purpose: '请将出差目的优化为清晰、具体、适合正式报告的表述，保留原意，不添加未提供的事项。',
  itinerary: '请将行程概览优化为按时间或事项推进的报告文本，语言简洁、层次清楚。',
  details: '请将工作详情优化为正式出差报告中的工作过程和成果描述，突出事实、动作和结果。',
  issues: '请将问题与反馈优化为客观、具体、便于后续跟进的表达。',
  suggestions: '请将总结与建议优化为可执行、可复盘的报告结论，表达稳妥专业。',
}

const assistantAvatar = resourceUrl('/assets/ai-assistant-avatar.png')
const assistantQuickActions = [
  '帮我检查这份出差报告还缺什么。',
  '把当前出差内容整理得更正式。',
  '根据当前内容提炼后续建议。',
]

const activeStep = ref(1)
const selectedReport = ref('')
const reports = ref<ReportFile[]>([])
const visibleHistoryCount = ref(6)
const editGroup = ref<TripGroup | null>(null)
const activeOptimizeField = ref<TripFieldKey | ''>('')
const promptEditor = ref<TripFieldKey | ''>('')
const promptDraft = ref('')
const statusMessage = ref('')
const statusTone = ref<'normal' | 'ok' | 'error'>('normal')
const initialized = ref(false)
const isReportDirty = ref(true)
const previewSource = ref<'instant' | 'generated'>('instant')
const sendBlockers = ref<string[]>([])
const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantLoading = ref(false)
const assistantMessages = ref<AgentMessage[]>([
  { role: 'assistant', content: '你好，我是犇犇。你可以把出差地点、行程和现场事项发给我，我会帮你整理成报告内容。' },
])

const loading = reactive({
  init: false,
  reports: false,
  prefill: false,
  draft: false,
  generate: false,
  send: false,
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

const editForm = reactive<Record<TripFieldKey, string>>({ ...tripForm })
const promptForm = reactive<Partial<Record<TripFieldKey, string>>>({ ...fieldPrompts })

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
const visibleTripReports = computed(() => {
  const current = selectedReport.value ? tripReports.value.find((report) => report.name === selectedReport.value) : null
  const base = tripReports.value.slice(0, visibleHistoryCount.value)
  if (!current || base.some((report) => report.name === current.name)) return base
  return [current, ...base.slice(0, Math.max(0, visibleHistoryCount.value - 1))]
})
const hiddenTripReportCount = computed(() => Math.max(tripReports.value.length - visibleTripReports.value.length, 0))
const currentFileName = computed(() => mailDraft.attachment || selectedReport.value)
const currentDownloadUrl = computed(() => {
  if (mailDraft.download_url) return downloadUrl(mailDraft.download_url)
  return mailDraft.attachment ? `/personal-work-download?file=${encodeURIComponent(mailDraft.attachment)}` : ''
})
const periodText = computed(() => formatTripDateText(tripForm.trip_start, tripForm.trip_end) || '未选择时间')
const filledRequiredCount = computed(() => requiredFields().filter((field) => tripForm[field.key]?.trim()).length)
const requiredCount = computed(() => requiredFields().length)
const completionPercent = computed(() => Math.round((filledRequiredCount.value / requiredCount.value) * 100))
const completedGroupCount = computed(() => tripGroups.filter((group) => group.fields.some((field) => tripForm[field.key]?.trim())).length)
const draftStorageKey = computed(() => (authState.user?.username ? `personalWorkSite.tripDraft.v1:${authState.user.username}` : ''))
const previewStateText = computed(() => {
  if (previewSource.value === 'instant' && !mailDraft.attachment) return '待生成预览'
  if (mailDraft.attachment && !isReportDirty.value) return '已生成'
  return mailDraft.attachment ? '待重新生成' : '待生成预览'
})
const stepHint = computed(() => {
  if (activeStep.value === 1) return `已完善 ${filledRequiredCount.value}/${requiredCount.value} 个必填项`
  if (activeStep.value === 2) return mailDraft.attachment ? `当前附件：${mailDraft.attachment}` : '当前为表单预览'
  return sendBlockers.value.length ? '请补齐发送信息后再确认' : '确认收件人、主题、正文和附件'
})
const nextActionText = computed(() => {
  if (activeStep.value === 1) return loading.generate ? '正在生成预览' : '下一步：生成预览'
  if (activeStep.value === 2) return '下一步：填写邮件'
  return loading.send ? '正在发送' : '确认发送'
})
const stepActionDisabled = computed(() => loading.generate || loading.send)
const sendPayload = computed(() => buildSendPayload())
const sendReadinessBlockers = computed(() => findSendBlockers(sendPayload.value))
const sendReadyText = computed(() => (sendReadinessBlockers.value.length ? '还有信息待确认' : '一切就绪，可发送'))
const currentPromptField = computed(() => editGroup.value?.fields.find((field) => field.key === promptEditor.value))
const promptDialogTitle = computed(() => (currentPromptField.value ? `${currentPromptField.value.label}提示词` : '修改提示词'))
const editDialogVisible = computed({
  get: () => Boolean(editGroup.value),
  set: (visible: boolean) => {
    if (!visible) closeEditDialog()
  },
})
const promptDialogVisible = computed({
  get: () => Boolean(promptEditor.value),
  set: (visible: boolean) => {
    if (!visible) promptEditor.value = ''
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

function groupPreview(group: TripGroup) {
  const values = group.fields
    .map((field) => {
      const value = tripForm[field.key]?.trim()
      if (!value) return ''
      return group.id === 'base' ? `${field.label}：${field.type === 'date' ? formatDateForCn(value) : value}` : value
    })
    .filter(Boolean)
  return values.join('\n') || '点击填写内容'
}

function groupFilledCount(group: TripGroup) {
  return group.fields.filter((field) => tripForm[field.key]?.trim()).length
}

function openEditDialog(group: TripGroup) {
  editGroup.value = group
  group.fields.forEach((field) => {
    editForm[field.key] = tripForm[field.key] || ''
    promptForm[field.key] = fieldPrompts[field.key] || ''
    fieldOptimizePreview[field.key] = null
  })
  activeOptimizeField.value = ''
  promptEditor.value = ''
}

function closeEditDialog() {
  editGroup.value = null
  activeOptimizeField.value = ''
  promptEditor.value = ''
}

function validateEditGroup(group: TripGroup) {
  const missing = group.fields.filter((field) => field.required && !editForm[field.key].trim()).map((field) => field.label)
  if (!missing.length) return true
  ElMessage.warning(`请填写${missing.join('、')}`)
  return false
}

function saveEditDialog() {
  if (!editGroup.value) return
  if (!validateEditGroup(editGroup.value)) return
  editGroup.value.fields.forEach((field) => {
    tripForm[field.key] = editForm[field.key].trim()
  })
  tripForm.trip_date_text = formatTripDateText(tripForm.trip_start, tripForm.trip_end)
  closeEditDialog()
  ElMessage.success('内容已保存')
}

function handleEditInput(fieldKey: TripFieldKey) {
  fieldOptimizePreview[fieldKey] = null
}

function openPromptEditor(field: TripField) {
  if (!canOptimizeField(field)) return
  promptEditor.value = field.key
  promptDraft.value = promptForm[field.key] || fieldPrompts[field.key] || ''
}

function savePromptEditor() {
  if (!promptEditor.value) return
  promptForm[promptEditor.value] = promptDraft.value.trim() || fieldPrompts[promptEditor.value] || ''
  promptEditor.value = ''
  ElMessage.success('提示词已更新')
}

async function optimizeEditField(field: TripField) {
  if (!canOptimizeField(field)) return
  const original = editForm[field.key].trim()
  if (!original) {
    ElMessage.warning('请先填写需要优化的内容')
    return
  }
  activeOptimizeField.value = field.key
  fieldOptimizePreview[field.key] = null
  try {
    const result = await optimizeText(original, promptForm[field.key] || fieldPrompts[field.key] || '请优化这段出差报告内容，保持事实准确、表达清楚。')
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

function undoOptimizePreview(field: TripField) {
  fieldOptimizePreview[field.key] = null
}

function acceptOptimizePreview(field: TripField) {
  const preview = fieldOptimizePreview[field.key]
  if (!preview) return
  editForm[field.key] = preview.suggestion
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

async function loadDraft(name: string) {
  if (!name) return
  loading.draft = true
  try {
    const draft = await getDraft('trip', name)
    applyDraft(draft)
    selectedReport.value = name
    activeStep.value = 2
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
  activeStep.value = 1
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
  setStatus('正在按模板生成出差报告...', 'normal')
  try {
    const result = await generateTrip({ kind: 'trip', ...tripPayload() })
    clearTripDraft()
    await loadReports()
    applyDraft(result.draft)
    selectedReport.value = result.file
    activeStep.value = 2
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
    setStatus(result.message || '邮件已发送', 'ok')
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

async function copyBody() {
  if (!mailDraft.body) {
    ElMessage.warning('暂无可复制正文')
    return
  }
  await navigator.clipboard.writeText(mailDraft.body)
  ElMessage.success('正文已复制')
}

async function nextStep() {
  if (activeStep.value === 1) {
    await generateReport()
    return
  }
  if (activeStep.value === 2) {
    activeStep.value = 3
    return
  }
  await sendReport()
}

function previousStep() {
  if (activeStep.value > 1) activeStep.value -= 1
}

function assistantContext() {
  return {
    step: workflowSteps[activeStep.value - 1].title,
    location: tripForm.location,
    period: periodText.value,
    trip: tripPayload(),
    subject: mailDraft.subject,
    attachment: mailDraft.attachment,
    preview_state: previewStateText.value,
  }
}

async function sendAssistantMessage(text = assistantInput.value) {
  const content = text.trim()
  if (!content) {
    ElMessage.warning('请输入要问犇犇的内容')
    return
  }
  assistantOpen.value = true
  assistantMessages.value.push({ role: 'user', content })
  assistantInput.value = ''
  assistantLoading.value = true
  try {
    const messages = assistantMessages.value.slice(-8)
    messages.push({
      role: 'user',
      content: `[当前出差报告页面上下文]\n${JSON.stringify(assistantContext(), null, 2)}\n\n${content}`,
    })
    const result = await agentChat('trip', messages)
    if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
    assistantMessages.value.push({ role: 'assistant', content: result.reply || '我看到了，当前没有新的补充。' })
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
  } finally {
    assistantLoading.value = false
  }
}

async function initializeTrip() {
  loading.init = true
  try {
    setDefaultTripDates()
    await Promise.all([loadReports(), loadTripPrefill(false)])
    const latestGenerated = reports.value.find((report) => report.generated)
    if (latestGenerated) await loadDraft(latestGenerated.name)
    else refreshInstantPreview()
    initialized.value = true
  } finally {
    loading.init = false
  }
}

onMounted(initializeTrip)
</script>

<template>
  <section class="trip-main">
    <section class="trip-flow" aria-label="出差报告生成步骤">
      <button
        v-for="step in workflowSteps"
        :key="step.id"
        :class="['trip-flow-step', { active: activeStep === step.id, completed: activeStep > step.id }]"
        type="button"
        :disabled="step.id > 1 && step.id > activeStep + 1"
        @click="activeStep = Math.min(step.id, activeStep + 1)"
      >
        <span class="trip-flow-index">{{ activeStep > step.id ? '✓' : step.id }}</span>
        <span>
          <strong>{{ step.title }}</strong>
          <small>{{ step.description }}</small>
        </span>
      </button>
    </section>

    <section v-if="activeStep === 1" class="trip-step trip-edit-workspace">
      <div class="trip-edit-column">
        <section class="trip-period-card">
          <div>
            <h2>出差信息</h2>
            <p>先把地点、时间和现场事项补齐，后续会生成标准报告与邮件正文。</p>
          </div>
          <div class="trip-period-summary">
            <span>当前出差时段</span>
            <strong>{{ periodText }}</strong>
            <em>{{ tripForm.location || '未填写地点' }}</em>
          </div>
          <div class="trip-period-actions">
            <IconTextButton icon="history" :disabled="loading.prefill" @click="loadTripPrefill(true)">
              获取最新历史报告
            </IconTextButton>
            <IconTextButton icon="sparkle" variant="primary" :disabled="loading.generate" @click="generateReport">
              生成报告预览
            </IconTextButton>
          </div>
          <div :class="['trip-status', statusTone]">{{ statusMessage || '内容会自动保存为本地草稿。' }}</div>
        </section>

        <section class="trip-card-grid">
          <article v-for="(group, index) in tripGroups" :key="group.id" :class="['trip-edit-card', group.tone]">
            <button class="trip-card-body" type="button" @click="openEditDialog(group)">
              <span class="trip-card-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="trip-card-copy">
                <strong>{{ group.title }}</strong>
                <small>{{ group.subtitle }}</small>
                <em>{{ groupPreview(group) }}</em>
              </span>
              <span class="trip-card-edit" aria-hidden="true"><el-icon><EditPen /></el-icon></span>
            </button>
          </article>
        </section>
      </div>

      <aside class="trip-side-panel">
        <section class="trip-side-card trip-progress-card">
          <div class="trip-side-card-head">
            <h3>填写进度</h3>
            <span>{{ completionPercent }}%</span>
          </div>
          <div class="trip-progress-track"><i :style="{ width: completionPercent + '%' }"></i></div>
          <div v-for="group in tripGroups" :key="group.id" class="trip-side-check">
            <span>{{ group.title }}</span>
            <strong>{{ groupFilledCount(group) }}/{{ group.fields.length }}</strong>
          </div>
        </section>

        <section class="trip-side-card trip-assistant-side-card">
          <div class="trip-assistant-side-title">
            <img :src="assistantAvatar" alt="犇犇" />
            <div>
              <h3>犇犇助手</h3>
              <p>可以帮你检查内容、整理表述。</p>
            </div>
          </div>
          <div class="trip-assistant-quick-list">
            <button v-for="item in assistantQuickActions" :key="item" type="button" @click="sendAssistantMessage(item)">
              {{ item }}
            </button>
          </div>
        </section>
      </aside>
    </section>

    <section v-else-if="activeStep === 2" class="trip-step trip-preview-workspace">
      <section class="trip-preview-card trip-preview-card--wide">
        <header class="trip-card-head">
          <div>
            <h3>报告预览</h3>
            <span>{{ currentFileName || '当前为未生成预览' }}</span>
          </div>
          <div class="trip-preview-actions">
            <IconTextButton icon="refresh" :disabled="loading.generate" @click="generateReport">重新生成</IconTextButton>
            <IconTextButton icon="download" :disabled="!currentDownloadUrl" @click="downloadAttachment">下载附件</IconTextButton>
          </div>
        </header>

        <div v-if="currentFileName" class="trip-file-chip">
          <span class="trip-word-icon">W</span>
          <div>
            <strong>{{ currentFileName }}</strong>
            <small>{{ previewStateText }}</small>
          </div>
        </div>

        <div class="trip-preview-scroll">
          <div v-if="mailDraft.preview_html || mailDraft.body_html" class="trip-html" v-html="mailDraft.preview_html || mailDraft.body_html"></div>
          <div v-else class="trip-empty">还没有预览内容，请先生成报告。</div>
        </div>

        <section class="trip-history-panel">
          <div class="trip-history-head">
            <div>
              <strong>历史出差报告</strong>
              <small>{{ loading.reports ? '刷新中' : `${tripReports.length} 份` }}</small>
            </div>
            <button v-if="hiddenTripReportCount" class="trip-link-button" type="button" @click="visibleHistoryCount += 8">
              展开 {{ hiddenTripReportCount }} 份
            </button>
          </div>
          <div class="trip-history-scroll">
            <div v-for="report in visibleTripReports" :key="report.name" class="trip-history-item">
              <button class="trip-history-load" type="button" @click="loadDraft(report.name)">
                <span>
                  <strong>{{ report.name }}</strong>
                  <small>{{ report.generated ? '新生成' : '出差报告模板' }} · {{ new Date(report.mtime * 1000).toLocaleString() }}</small>
                </span>
                <em>{{ selectedReport === report.name ? '当前' : '加载' }}</em>
              </button>
              <button v-if="report.deletable" class="trip-history-delete" type="button" aria-label="删除历史报告" @click="deleteReportItem(report)">
                <el-icon><Delete /></el-icon>
              </button>
            </div>
            <div v-if="!tripReports.length" class="trip-history-empty">暂无历史出差报告。</div>
          </div>
        </section>
      </section>

      <aside class="trip-side-panel">
        <section class="trip-side-card trip-status-check-card">
          <h3>生成状态</h3>
          <div class="trip-status-check-list">
            <div :class="['trip-status-check-item', { done: mailDraft.attachment && !isReportDirty }]">
              <span></span>
              <div>
                <strong>文件已生成</strong>
                <small>{{ mailDraft.attachment ? 'Word 附件已生成并可下载' : '等待生成标准附件' }}</small>
              </div>
            </div>
            <div :class="['trip-status-check-item', { done: !!mailDraft.body }]">
              <span></span>
              <div>
                <strong>邮件正文已同步</strong>
                <small>{{ mailDraft.body ? '正文内容已根据报告生成' : '生成后同步邮件正文' }}</small>
              </div>
            </div>
            <div :class="['trip-status-check-item', { done: !!currentDownloadUrl }]">
              <span></span>
              <div>
                <strong>附件可下载</strong>
                <small>{{ currentDownloadUrl ? '可下载附件用于本地查看' : '暂无可下载附件' }}</small>
              </div>
            </div>
          </div>
        </section>

        <section class="trip-side-card trip-assistant-side-card">
          <div class="trip-assistant-side-title">
            <img :src="assistantAvatar" alt="犇犇" />
            <div>
              <h3>犇犇助手</h3>
              <p>预览阶段帮你检查结构和遗漏。</p>
            </div>
          </div>
          <div class="trip-assistant-quick-list">
            <button type="button" @click="sendAssistantMessage('预览的出差报告内容是否完整？')">预览内容是否完整？</button>
            <button type="button" @click="sendAssistantMessage('邮件正文是否适合发送给领导？')">邮件正文是否清晰？</button>
          </div>
        </section>
      </aside>
    </section>

    <section v-else class="trip-step trip-send-workspace">
      <section class="trip-mail-card">
        <h3>邮件内容</h3>
        <label>
          <span>收件人</span>
          <el-input v-model="mailDraft.to" />
        </label>
        <label>
          <span>抄送</span>
          <el-input v-model="mailDraft.cc" />
        </label>
        <label>
          <span>主题</span>
          <el-input v-model="mailDraft.subject" />
        </label>
        <div v-if="currentFileName" class="trip-mail-attachment-card">
          <span class="trip-word-icon">W</span>
          <div>
            <strong>{{ currentFileName }}</strong>
            <small>{{ previewStateText }}</small>
          </div>
          <button class="trip-link-button" type="button" @click="downloadAttachment">下载</button>
        </div>

        <div class="trip-body-preview">
          <span>正文预览</span>
          <div class="trip-body-preview-content">
            <div v-if="mailDraft.body_html" class="trip-html" v-html="mailDraft.body_html"></div>
            <div v-else-if="mailDraft.body" class="trip-body-text">{{ mailDraft.body }}</div>
            <p v-else>生成正文后，这里会显示邮件内容。</p>
          </div>
        </div>

        <div class="trip-mail-actions">
          <IconTextButton icon="refresh" size="md" block :disabled="loading.generate" @click="generateReport">重新生成正文</IconTextButton>
          <IconTextButton icon="copy" size="md" block @click="copyBody">复制正文</IconTextButton>
        </div>

        <div class="trip-mail-status">
          <el-icon><Document /></el-icon>
          {{ statusMessage || '请确认邮件信息后发送' }}
        </div>
      </section>

      <aside class="trip-side-panel trip-send-side-panel">
        <section class="trip-send-review-card">
          <div :class="['trip-send-ready-mark', { warning: sendReadinessBlockers.length }]">
            <span>{{ sendReadinessBlockers.length ? '!' : '✓' }}</span>
            <strong>{{ sendReadyText }}</strong>
          </div>
          <div class="trip-send-review-list">
            <span>收件人</span><strong>{{ sendPayload.to || '未填写' }}</strong>
            <span>抄送</span><strong>{{ sendPayload.cc || '无' }}</strong>
            <span>主题</span><strong>{{ sendPayload.subject || '未填写' }}</strong>
            <span>附件</span><strong>{{ sendPayload.attachment || '未选择' }}</strong>
            <span>正文状态</span><strong>{{ mailDraft.body || mailDraft.body_html ? '已同步' : '未生成' }}</strong>
          </div>
          <p v-if="sendReadinessBlockers.length" class="trip-send-warning">{{ sendReadinessBlockers.join('；') }}</p>
          <p v-else class="trip-send-info-note">邮件将通过企业邮箱服务发送，请确认收件人、主题和附件无误。</p>
        </section>

        <section class="trip-side-card trip-progress-card">
          <h3>报告上下文</h3>
          <div class="trip-side-check"><span>出差地点</span><strong>{{ tripForm.location || '未填' }}</strong></div>
          <div class="trip-side-check"><span>出差时段</span><strong>{{ periodText }}</strong></div>
          <div class="trip-side-check"><span>已填模块</span><strong>{{ completedGroupCount }}/{{ tripGroups.length }}</strong></div>
          <button class="trip-side-outline-button" type="button" @click="activeStep = 2">查看预览内容</button>
        </section>
      </aside>
    </section>

    <el-dialog
      v-model="editDialogVisible"
      class="trip-edit-dialog"
      :title="editGroup?.title || '编辑出差报告'"
      width="min(880px, 96vw)"
      align-center
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-if="editGroup" class="trip-edit-fields">
        <div
          v-for="field in editGroup.fields"
          :key="field.key"
          :class="['trip-edit-field', { wide: field.multiline, 'is-ai': canOptimizeField(field) }]"
        >
          <div class="trip-edit-field-head">
            <label :class="{ required: field.required }">{{ field.label }}</label>
            <button v-if="canOptimizeField(field)" class="trip-field-prompt-button" type="button" @click="openPromptEditor(field)">
              <span aria-hidden="true">
                <svg viewBox="0 0 16 16" focusable="false">
                  <path d="M3 2.5h10a1 1 0 0 1 1 1v7.4a1 1 0 0 1-1 1H7.2L4 14.2v-2.3H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Zm2.4 3h5.2v1.2H5.4V5.5Zm0 2.5h4.2v1.2H5.4V8Z" />
                </svg>
              </span>
              提示词
            </button>
          </div>
          <div :class="['trip-edit-input-wrap', { 'has-ai': canOptimizeField(field) }]">
            <el-input
              v-if="field.multiline"
              v-model="editForm[field.key]"
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 9 }"
              @input="handleEditInput(field.key)"
            />
            <el-date-picker
              v-else-if="field.type === 'date'"
              v-model="editForm[field.key]"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              @change="handleEditInput(field.key)"
            />
            <el-input v-else v-model="editForm[field.key]" type="text" @input="handleEditInput(field.key)" />
            <button
              v-if="canOptimizeField(field)"
              class="trip-field-ai-icon-button"
              type="button"
              title="AI 辅助优化"
              aria-label="AI 辅助优化"
              :disabled="activeOptimizeField !== ''"
              @click="optimizeEditField(field)"
            >
              <span aria-hidden="true">
                <svg viewBox="0 0 16 16" focusable="false">
                  <path d="M7.1 2.1 8.4 5.6l3.5 1.3-3.5 1.3-1.3 3.5-1.3-3.5-3.5-1.3 3.5-1.3Z" />
                  <path d="M12.1 10.2 12.7 11.5l1.3.6-1.3.6-.6 1.3-.6-1.3-1.3-.6 1.3-.6Z" />
                </svg>
              </span>
            </button>
          </div>
          <div v-if="canOptimizeField(field) && fieldOptimizePreview[field.key]" class="trip-ai-compare-card">
            <div class="trip-ai-compare-grid">
              <section>
                <span>原内容</span>
                <p>{{ fieldOptimizePreview[field.key]?.original }}</p>
              </section>
              <section>
                <span>优化结果</span>
                <p>{{ fieldOptimizePreview[field.key]?.suggestion }}</p>
              </section>
            </div>
            <div class="trip-ai-compare-actions">
              <button type="button" @click="undoOptimizePreview(field)">撤销</button>
              <button type="button" class="primary" @click="acceptOptimizePreview(field)">采纳</button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="trip-edit-actions">
          <el-button @click="closeEditDialog">取消</el-button>
          <el-button type="primary" @click="saveEditDialog">保存</el-button>
        </div>
      </template>
    </el-dialog>

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
        <div class="trip-edit-actions">
          <el-button @click="promptEditor = ''">取消</el-button>
          <el-button type="primary" @click="savePromptEditor">保存提示词</el-button>
        </div>
      </template>
    </el-dialog>

    <section class="trip-footer">
      <div>
        <strong>{{ workflowSteps[activeStep - 1].title }}</strong>
        <span>{{ stepHint }}</span>
      </div>
      <div class="trip-footer-actions">
        <button v-if="activeStep > 1" class="trip-nav-button" type="button" @click="previousStep">上一步</button>
        <button class="trip-nav-button primary" type="button" :disabled="stepActionDisabled" @click="nextStep">
          {{ nextActionText }}
        </button>
      </div>
    </section>

    <AssistantChat
      v-model:open="assistantOpen"
      v-model:input="assistantInput"
      :avatar="assistantAvatar"
      :messages="assistantMessages"
      :quick-actions="assistantQuickActions"
      :loading="assistantLoading"
      @send="sendAssistantMessage"
    />
  </section>
</template>
