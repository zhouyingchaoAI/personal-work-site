<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Delete, Document, EditPen } from '@element-plus/icons-vue'
import AssistantChat from '../../components/AssistantChat/index.vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import { authState } from '../../services/authSession'
import {
  agentChat,
  deleteHistory,
  deleteReport,
  downloadUrl,
  generateWeekly,
  getDraft,
  getReports,
  getWeeklyPrefill,
  optimizeText,
  resourceUrl,
  sendMail,
  summarizeDiaries,
  type AgentMessage,
  type DraftResponse,
  type ReportFile,
  type SendMailPayload,
  type WeeklyRowPayload,
} from '../../services/personalWorkApi'
import './index.scss'

type SectionId = 'summary' | 'follow' | 'next'
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

const workflowSteps = [
  { id: 1, title: '填写内容', description: '整理本周工作要点' },
  { id: 2, title: '生成预览', description: '生成文件与邮件预览' },
  { id: 3, title: '确认发送', description: '确认无误后发送邮件' },
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
    { key: 'progress', label: '当前进展' },
    { key: 'difficulty', label: '困难与求助', multiline: true },
  ],
  next: [
    { key: 'category', label: '工作分类' },
    { key: 'content', label: '工作内容', multiline: true },
    { key: 'difficulty', label: '困难与求助', multiline: true },
  ],
}

const fieldPrompts: Record<RowField, string> = {
  category: '请提炼为 2-6 个字的工作分类，保留业务含义，不添加新事项。',
  content: '请优化为清楚、具体、可汇报的工作描述，保留原意，不添加未提供的事项。',
  status: '请优化为简洁的完成情况描述，突出结果和状态。',
  progress: '请优化为明确的推进状态描述，说明当前进展。',
  plan: '请优化为清晰的下一步动作，表达具体、可执行。',
  difficulty: '请优化为问题和所需支持描述，表达客观、具体。',
}

const assistantAvatar = resourceUrl('/assets/ai-assistant-avatar.png')
const assistantQuickActions = [
  '帮我检查这份周报还缺什么。',
  '把当前内容整理得更适合汇报。',
  '告诉我下一步应该做什么。',
]
const assistantSideActions = assistantQuickActions

const activeStep = ref(1)
const activeSectionId = ref<SectionId>('summary')
const nextRowId = ref(1)
const editing = ref<EditTarget | null>(null)
const flowTop = ref<HTMLElement | null>(null)
const weeklyRowsRef = ref<HTMLElement | null>(null)
const sourceMessage = ref('')
const statusMessage = ref('')
const statusTone = ref<'normal' | 'ok' | 'error'>('normal')
const selectedReport = ref('')
const reports = ref<ReportFile[]>([])
const sendBlockers = ref<string[]>([])
const isReportDirty = ref(true)
const previewSource = ref<'instant' | 'generated'>('instant')
const initialized = ref(false)
const fieldOptimizing = ref<RowField | ''>('')
const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantLoading = ref(false)
const historyExpanded = ref(false)
const assistantMessages = ref<AgentMessage[]>([
  { role: 'assistant', content: '你好，我是犇犇。你可以把零散想法发给我，我会结合当前周报内容帮你整理。' },
])

const loading = reactive({
  init: false,
  reports: false,
  draft: false,
  prefill: false,
  summarize: false,
  generate: false,
  send: false,
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

const promptForm = reactive<Record<RowField, string>>({ ...fieldPrompts })
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

const activeSection = computed(() => findSection(activeSectionId.value))
const activeSectionIndex = computed(() => Math.max(0, sections.value.findIndex((section) => section.id === activeSectionId.value)))
const totalRows = computed(() => sections.value.reduce((sum, section) => sum + cleanRows(section.id).length, 0))
const filledSectionCount = computed(() => sections.value.filter((section) => cleanRows(section.id).length).length)
const completionPercent = computed(() => Math.round((filledSectionCount.value / sections.value.length) * 100))
const weeklyReports = computed(() => reports.value.filter((report) => report.kind === 'weekly'))
// 折叠历史列表时保留当前选中的报告，避免当前附件入口消失。
const visibleWeeklyReports = computed(() => {
  if (historyExpanded.value) return weeklyReports.value
  const recentReports = weeklyReports.value.slice(0, 5)
  if (!selectedReport.value || recentReports.some((report) => report.name === selectedReport.value)) return recentReports
  const currentReport = weeklyReports.value.find((report) => report.name === selectedReport.value)
  return currentReport ? [currentReport, ...recentReports.slice(0, 4)] : recentReports
})
const hiddenWeeklyReportCount = computed(() => Math.max(weeklyReports.value.length - visibleWeeklyReports.value.length, 0))
const currentFileName = computed(() => mailDraft.attachment || selectedReport.value)
const previewStateText = computed(() => {
  if (previewSource.value === 'instant' && !mailDraft.attachment) return '待生成预览'
  if (mailDraft.attachment && !isReportDirty.value) return '已生成'
  return mailDraft.attachment ? '待重新生成' : '待生成预览'
})
const currentDownloadUrl = computed(() => {
  if (mailDraft.download_url) return downloadUrl(mailDraft.download_url)
  return mailDraft.attachment ? `/personal-work-download?file=${encodeURIComponent(mailDraft.attachment)}` : ''
})
const periodValue = computed(() => {
  const start = formatPeriodDate(weeklyPeriod.start)
  const end = formatPeriodDate(weeklyPeriod.end)
  return start && end ? `${start}-${end}` : start || end
})
const periodDisplay = computed(() => periodValue.value.replace('-', ' - ') || '未选择时段')
const draftStorageKey = computed(() =>
  authState.user?.username ? `personalWorkSite.formDraft.v2:${authState.user.username}` : '',
)
const mailStatusText = computed(() => statusMessage.value || (isReportDirty.value ? '待生成预览' : '待确认'))
const nextActionText = computed(() => {
  if (activeStep.value === 1) return loading.generate ? '正在生成预览' : '下一步：生成预览'
  if (activeStep.value === 2) return '下一步：填写邮件'
  return loading.send ? '正在发送' : '确认发送'
})
const stepHint = computed(() => {
  if (activeStep.value === 1) return `已填写 ${totalRows.value} 条周报内容`
  if (activeStep.value === 2) return mailDraft.attachment ? `当前附件：${mailDraft.attachment}` : '当前为待生成预览'
  return sendBlockers.value.length ? '请补齐发送信息后再确认' : '确认收件人、主题、正文和附件'
})
const stepActionDisabled = computed(() => loading.generate || loading.send)
const contentStateText = computed(() => {
  if (!totalRows.value) return '还没有周报内容'
  if (editing.value) return '有内容正在编辑'
  return isReportDirty.value ? '内容已变更，预览待更新' : '内容已同步到预览'
})
const sendPayload = computed(() => buildSendPayload())
const sendReadinessBlockers = computed(() => findSendBlockers(sendPayload.value))
const sendReadyText = computed(() => (sendReadinessBlockers.value.length ? '还有信息待确认' : '一切就绪，可发送'))
const editingFields = computed(() => (editing.value ? sectionFields[editing.value.sectionId] : []))
const visibleEditingFields = computed(() => editingFields.value.filter((field) => field.key !== 'status' && field.key !== 'progress'))
const editingStateField = computed(() => editingFields.value.find((field) => field.key === 'status' || field.key === 'progress'))
const editingStateOptions = computed(() => {
  const stateField = editingStateField.value
  if (!stateField) return []
  return stateField.key === 'status' ? ['已完成', '推进中', '需协调'] : ['推进中', '待验证', '需协调']
})
const currentPromptField = computed(() => editingFields.value.find((field) => field.key === promptEditor.value))
const promptDialogTitle = computed(() => (currentPromptField.value ? `${currentPromptField.value.label}提示词` : '修改提示词'))
const promptDialogVisible = computed({
  get: () => Boolean(promptEditor.value),
  set: (visible: boolean) => {
    if (!visible) promptEditor.value = ''
  },
})

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
  statusMessage.value = message
  statusTone.value = tone
}

function assistantContext() {
  return {
    step: workflowSteps[activeStep.value - 1].title,
    period: periodDisplay.value,
    weekly_summary: cleanRows('summary'),
    weekly_follow: cleanRows('follow'),
    weekly_next: cleanRows('next'),
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
      content: `[当前周报页面上下文]\n${JSON.stringify(assistantContext(), null, 2)}\n\n${content}`,
    })
    const result = await agentChat('weekly', messages)
    if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
    assistantMessages.value.push({ role: 'assistant', content: result.reply || '我看到了，当前没有新的补充。' })
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
  } finally {
    assistantLoading.value = false
  }
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
  if (sectionId === 'follow') return 'orange'
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

function isRequiredField(field: EditField) {
  return field.key === 'category' || field.key === 'content'
}

function fieldInputAutosize(field: EditField) {
  return field.multiline ? { minRows: 5, maxRows: 9 } : { minRows: 3, maxRows: 5 }
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

function hasWeeklyRows(rows: WeeklyRowsBySection) {
  return Object.values(rows).some((sectionRows) => sectionRows.some((row) => Object.values(row).some((value) => String(value || '').trim())))
}

function sectionDisplayTitle(title: string) {
  return title.replace(/^[一二三]、/, '')
}

function firstFilledSectionId() {
  return sections.value.find((section) => cleanRows(section.id).length)?.id || 'summary'
}

function syncActiveSectionToFirstFilled() {
  activeSectionId.value = firstFilledSectionId()
}

function selectSection(sectionId: SectionId) {
  if (sectionId === activeSectionId.value) return
  if (editing.value) {
    ElMessage.warning('请先保存当前编辑内容')
    return
  }
  activeSectionId.value = sectionId
}

// 历史草稿正文保留三段结构，用它还原可编辑行。
function parseDraftRows(body: string): WeeklyRowsBySection {
  const rows: WeeklyRowsBySection = { summary: [], follow: [], next: [] }
  let sectionId: SectionId | '' = ''
  let row: WeeklyRowPayload | null = null
  const saveRow = () => {
    if (sectionId && row && Object.values(row).some((value) => String(value || '').trim())) rows[sectionId].push(row)
    row = null
  }

  body.split('\n').forEach((line) => {
    const text = line.trim()
    if (!text) return
    if (text === '一、本周工作总结') {
      saveRow()
      sectionId = 'summary'
      return
    }
    if (text === '二、重点工作跟进') {
      saveRow()
      sectionId = 'follow'
      return
    }
    if (text === '三、下周工作计划') {
      saveRow()
      sectionId = 'next'
      return
    }
    if (!sectionId) return
    if (text.startsWith('本周主要工作内容') || text.startsWith('如有需要补充')) {
      saveRow()
      sectionId = ''
      return
    }

    const category = text.match(/^【(.+)】$/)
    if (category) {
      saveRow()
      row = { category: category[1].trim() }
      return
    }

    if (!row) row = {}
    if (text.startsWith('完成情况：')) row.status = text.replace('完成情况：', '').trim()
    else if (text.startsWith('后续计划：')) row.plan = text.replace('后续计划：', '').trim()
    else if (text.startsWith('当前进展：')) row.progress = text.replace('当前进展：', '').trim()
    else if (text.startsWith('困难与求助：')) row.difficulty = text.replace('困难与求助：', '').trim()
    else row.content = [row.content, text.replace(/^\d+[.、．\s]+/, '')].filter(Boolean).join('\n')
  })

  saveRow()
  return rows
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

function rowDetail(sectionId: SectionId, row: WeeklyRow) {
  if (sectionId === 'summary' && row.plan) return `后续计划：${row.plan}`
  if (sectionId === 'follow' && row.difficulty) return `困难与求助：${row.difficulty}`
  if (sectionId === 'next' && row.difficulty) return `困难与求助：${row.difficulty}`
  return ''
}

function rowState(sectionId: SectionId, row: WeeklyRow) {
  if (sectionId === 'summary') return row.status
  if (sectionId === 'follow') return row.progress
  return ''
}

function beginAdd(section: WeeklySection) {
  if (editing.value) {
    ElMessage.warning('请先保存当前编辑内容')
    return
  }
  activeSectionId.value = section.id
  const row = createRow(section.id)
  section.rows.unshift(row)
  beginEdit(section.id, row, true)
  revealInlineEditor()
}

function beginEdit(sectionId: SectionId, row: WeeklyRow, isNew = false) {
  activeSectionId.value = sectionId
  editing.value = { sectionId, rowId: row.id, isNew }
  Object.keys(editForm).forEach((key) => {
    const fieldKey = key as RowField
    editForm[fieldKey] = String(row[fieldKey] || '')
    promptForm[fieldKey] = fieldPrompts[fieldKey]
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

function saveEdit() {
  if (!editing.value) return
  const section = findSection(editing.value.sectionId)
  const row = section.rows.find((item) => item.id === editing.value?.rowId)
  if (!row) return
  if (!validateEditForm(section)) return
  sectionFields[section.id].forEach((field) => {
    row[field.key] = editForm[field.key].trim()
  })
  row.tone = toneForRow(section.id, row)
  editing.value = null
  fieldOptimizing.value = ''
  promptEditor.value = ''
  activeStep.value = 1
  markReportDirty()
  saveWeeklyDraft()
}

function cancelEdit() {
  if (editing.value?.isNew) {
    const section = findSection(editing.value.sectionId)
    section.rows = section.rows.filter((row) => row.id !== editing.value?.rowId)
  }
  editing.value = null
  fieldOptimizing.value = ''
  promptEditor.value = ''
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
  promptDraft.value = promptForm[field.key]
}

function savePromptEditor() {
  if (!promptEditor.value) return
  promptForm[promptEditor.value] = promptDraft.value.trim() || fieldPrompts[promptEditor.value]
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

async function loadLatestHistory() {
  if (!weeklyReports.value.length) {
    setStatus('暂无历史周报，可先手动新增内容。', 'normal')
    return
  }
  const latestReport = weeklyReports.value[0]
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
    const draft = await getDraft('weekly', latestReport.name)
    const draftRows = parseDraftRows(draft.body || '')
    applyRowsBySection(hasWeeklyRows(draftRows) ? draftRows : prefillRows)
    sourceMessage.value = `已获取最新历史周报：${prefill.source || latestReport.name}`
    setStatus(sourceMessage.value, 'ok')
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
      follow: parsed.follow.map((content) => ({ category: '', content, progress: '推进中' })),
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
  activeStep.value = 2
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
    applyDraft(result.draft)
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
    const result = await optimizeText(original, promptForm[field.key])
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

function addCcSeparator() {
  if (mailDraft.cc && !mailDraft.cc.endsWith(';')) mailDraft.cc += ';'
}

function clearSendReview() {
  sendBlockers.value = []
}

function buildSendPayload(): SendMailPayload {
  return {
    to: mailDraft.to.trim(),
    cc: mailDraft.cc.trim(),
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

async function nextStep() {
  if (activeStep.value === 1) {
    if (editing.value) {
      ElMessage.warning('请先保存当前编辑内容')
      return false
    }
    if (!totalRows.value) {
      ElMessage.warning('请先填写周报内容')
      return false
    }
    await generateReport()
    await scrollStepTop()
    return true
  }
  if (activeStep.value === 2) {
    if (isReportDirty.value || !mailDraft.attachment) await generateReport()
    if (!mailDraft.attachment) {
      ElMessage.warning('请先生成附件后再填写邮件')
      return false
    }
    activeStep.value = 3
    clearSendReview()
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

async function goStep(stepId: number) {
  if (stepId === activeStep.value) return
  if (stepId < activeStep.value) {
    activeStep.value = stepId
    if (stepId < 3) clearSendReview()
    await scrollStepTop()
    return
  }
  if (stepId > activeStep.value + 1) {
    ElMessage.warning('请先完成当前步骤')
    return
  }
  await nextStep()
}

async function confirmSend() {
  const payload = buildSendPayload()
  const blockers = findSendBlockers(payload)
  if (blockers.length) {
    sendBlockers.value = blockers
    return
  }
  loading.send = true
  try {
    const result = await sendMail(payload)
    setStatus(result.message, 'ok')
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
    if (!restored && weeklyReports.value.length) await loadLatestHistory()
    if (!restored && !weeklyReports.value.length) {
      refreshInstantPreview()
      setStatus('暂无历史周报，可先手动新增内容。', 'normal')
    }
    if (restored) {
      markReportDirty()
      setStatus('已恢复上次未生成的周报草稿', 'ok')
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
  <section class="weekly-main weekly-main--wide">
    <section ref="flowTop" class="weekly-flow" aria-label="周报生成步骤">
      <button
        v-for="step in workflowSteps"
        :key="step.id"
        :class="['flow-step', { active: activeStep === step.id, completed: activeStep > step.id }]"
        type="button"
        :disabled="step.id > activeStep + 1"
        @click="goStep(step.id)"
      >
        <span class="flow-index">
          <el-icon v-if="activeStep > step.id"><CircleCheck /></el-icon>
          <span v-else>{{ step.id }}</span>
        </span>
        <span>
          <strong>{{ step.title }}</strong>
          <small>{{ step.description }}</small>
        </span>
      </button>
    </section>

    <template v-if="activeStep === 1">
      <section class="wizard-step edit-workspace">
        <div class="edit-column">
          <section class="period-card">
            <div class="period-title">
              <h2>周报时段</h2>
            </div>
            <div class="date-fields">
              <label>
                <span>开始日期</span>
                <el-date-picker v-model="weeklyPeriod.start" value-format="YYYY-MM-DD" type="date" />
              </label>
              <label>
                <span>结束日期</span>
                <el-date-picker v-model="weeklyPeriod.end" value-format="YYYY-MM-DD" type="date" />
              </label>
            </div>
            <div class="period-summary">
              <span class="period-summary-label">当前周报时段</span>
              <span class="period-summary-date">{{ periodDisplay }}</span>
              <em>本周</em>
            </div>
            <div class="period-actions">
              <IconTextButton icon="history" size="md" :disabled="loading.prefill" @click="loadLatestHistory">
                获取最新历史报告
              </IconTextButton>
              <IconTextButton icon="sparkle" size="md" variant="primary" :disabled="loading.summarize" @click="summarizeFromDiaries">
                从工作日记智能总结
              </IconTextButton>
            </div>
            <p v-if="statusMessage" :class="['weekly-status', statusTone]">{{ statusMessage }}</p>
          </section>

          <section class="weekly-section-tabs" aria-label="周报内容分区">
            <button
              v-for="(section, sectionIndex) in sections"
              :key="section.id"
              type="button"
              :class="['weekly-section-tab', { active: activeSectionId === section.id }]"
              @click="selectSection(section.id)"
            >
              <span class="weekly-section-tab__index">0{{ sectionIndex + 1 }}</span>
              <span>
                <strong>{{ sectionDisplayTitle(section.title) }}</strong>
                <small>{{ section.subtitle }}</small>
              </span>
              <em>{{ cleanRows(section.id).length }}</em>
            </button>
          </section>

          <section :key="activeSection.id" :class="['weekly-section-card', `weekly-section-card--${activeSection.id}`]">
            <header class="section-head">
              <div class="section-title-wrap">
                <span class="section-index">0{{ activeSectionIndex + 1 }}</span>
                <div>
                  <h3>{{ activeSection.title }} <span>({{ cleanRows(activeSection.id).length }})</span></h3>
                  <p>{{ activeSection.subtitle }}</p>
                </div>
              </div>
              <div class="section-actions">
                <IconTextButton icon="plus" @click="beginAdd(activeSection)">新增</IconTextButton>
              </div>
            </header>

            <div ref="weeklyRowsRef" class="weekly-rows">
              <div v-if="!activeSection.rows.length" class="empty-section">
                <span>还没有内容，先写一条也可以。</span>
              </div>

              <div v-for="(row, index) in activeSection.rows" :key="row.id" class="row-shell">
                <article v-if="isEditingRow(activeSection.id, row.id)" class="weekly-inline-editor">
                  <header class="weekly-inline-editor__head">
                    <div>
                      <strong>
                        <el-icon><EditPen /></el-icon>
                        {{ editing?.isNew ? '新增条目' : '编辑条目' }}
                      </strong>
                      <small>{{ sectionDisplayTitle(activeSection.title) }}</small>
                    </div>
                    <div v-if="editingStateField" class="weekly-state-segment" :aria-label="editingStateField.label">
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
                  </header>

                  <div class="weekly-edit-fields">
                    <div
                      v-for="field in visibleEditingFields"
                      :key="field.key"
                      :class="['weekly-edit-field', { wide: field.multiline || canOptimizeField(field), 'is-ai': canOptimizeField(field) }]"
                    >
                      <div class="weekly-edit-field-head">
                        <label :class="{ required: isRequiredField(field) }">{{ field.label }}</label>
                        <div v-if="canOptimizeField(field)" class="weekly-edit-field-tools">
                          <button class="field-prompt-button" type="button" @click="openPromptEditor(field)">
                            <span aria-hidden="true">
                              <svg viewBox="0 0 16 16" focusable="false">
                                <path d="M3 2.5h10a1 1 0 0 1 1 1v7.4a1 1 0 0 1-1 1H7.2L4 14.2v-2.3H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Zm2.4 3h5.2v1.2H5.4V5.5Zm0 2.5h4.2v1.2H5.4V8Z" />
                              </svg>
                            </span>
                            提示词
                          </button>
                          <button class="field-ai-text-button" type="button" :disabled="fieldOptimizing !== ''" @click="optimizeEditField(field)">
                            <span aria-hidden="true">
                              <svg viewBox="0 0 16 16" focusable="false">
                                <path d="M7.1 2.1 8.4 5.6l3.5 1.3-3.5 1.3-1.3 3.5-1.3-3.5-3.5-1.3 3.5-1.3Z" />
                                <path d="M12.1 10.2 12.7 11.5l1.3.6-1.3.6-.6 1.3-.6-1.3-1.3-.6 1.3-.6Z" />
                              </svg>
                            </span>
                            {{ fieldOptimizing === field.key ? '优化中...' : '智能优化' }}
                          </button>
                        </div>
                      </div>
                      <div class="edit-input-wrap">
                        <el-input
                          v-if="canOptimizeField(field)"
                          v-model="editForm[field.key]"
                          type="textarea"
                          :autosize="fieldInputAutosize(field)"
                          @input="handleEditFieldInput(field.key)"
                        />
                        <el-input v-else v-model="editForm[field.key]" type="text" @input="handleEditFieldInput(field.key)" />
                      </div>
                      <div v-if="canOptimizeField(field) && fieldOptimizePreview[field.key]" class="ai-compare-card">
                        <div class="ai-compare-grid">
                          <section>
                            <span>原内容</span>
                            <p>{{ fieldOptimizePreview[field.key]?.original }}</p>
                          </section>
                          <section>
                            <span>优化结果</span>
                            <p>{{ fieldOptimizePreview[field.key]?.suggestion }}</p>
                          </section>
                        </div>
                        <div class="ai-compare-actions">
                          <button type="button" @click="undoOptimizePreview(field)">忽略</button>
                          <button type="button" class="primary" @click="acceptOptimizePreview(field)">采纳建议</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <footer class="weekly-inline-editor__actions">
                    <button type="button" @click="cancelEdit">取消</button>
                    <button type="button" class="primary" @click="saveEdit">保存内容</button>
                  </footer>
                </article>

                <article v-else class="weekly-row">
                  <span class="row-index">{{ index + 1 }}</span>
                  <div class="row-copy">
                    <div class="row-meta">
                      <span :class="['row-tag', row.tone]">{{ row.category || '待分类' }}</span>
                      <span v-if="rowState(activeSection.id, row)" :class="['row-state', activeSection.id === 'summary' ? 'done' : 'progress']">
                        {{ rowState(activeSection.id, row) }}
                      </span>
                    </div>
                    <strong>{{ row.content || '待填写工作内容' }}</strong>
                    <small v-if="rowDetail(activeSection.id, row)">{{ rowDetail(activeSection.id, row) }}</small>
                  </div>
                  <div class="row-actions">
                    <button class="icon-button" type="button" aria-label="编辑" @click="beginEdit(activeSection.id, row)">
                      <el-icon><EditPen /></el-icon>
                    </button>
                    <button class="icon-button danger-icon-button" type="button" aria-label="删除" @click="removeRow(activeSection, row.id)">
                      <el-icon><Delete /></el-icon>
                    </button>
                  </div>
                </article>

              </div>

            </div>
          </section>
        </div>

        <aside class="step-side-panel">
          <section class="step-side-card progress-card">
            <div class="side-card-head">
              <h3>工作上下文</h3>
              <span>{{ completionPercent }}%</span>
            </div>
            <div class="progress-track">
              <i :style="{ width: completionPercent + '%' }"></i>
            </div>
            <div class="side-check">
              <span>本周总结</span>
              <strong>{{ cleanRows('summary').length }}</strong>
            </div>
            <div class="side-check">
              <span>重点跟进</span>
              <strong>{{ cleanRows('follow').length }}</strong>
            </div>
            <div class="side-check">
              <span>下周计划</span>
              <strong>{{ cleanRows('next').length }}</strong>
            </div>
            <p>{{ contentStateText }}</p>
          </section>

          <section class="step-side-card assistant-side-card">
            <div class="assistant-side-title">
              <img :src="assistantAvatar" alt="犇犇" />
              <div>
                <h3>犇犇助手</h3>
                <p>围绕当前周报内容提供建议。</p>
              </div>
            </div>
            <div class="assistant-quick-list">
              <button v-for="item in assistantSideActions" :key="item" type="button" @click="sendAssistantMessage(item)">
                {{ item }}
              </button>
            </div>
            <button class="assistant-open-chat" type="button" @click="assistantOpen = true">打开助手聊天</button>
          </section>
        </aside>
      </section>

    </template>

    <section v-else-if="activeStep === 2" class="wizard-step preview-workspace">
      <div class="preview-column">
        <section class="preview-card preview-card--wide">
          <div class="card-head">
            <h3>预览与附件</h3>
            <span>{{ weeklyReports.length }} 份报告</span>
          </div>

          <div class="preview-file-row">
            <div v-if="currentFileName" class="file-chip">
              <span class="excel-icon">X</span>
              <div>
                <strong>{{ currentFileName }}</strong>
                <small>{{ selectedReport ? '当前附件' : '待生成附件' }}</small>
              </div>
              <em>{{ previewStateText }}</em>
            </div>
            <div v-else class="empty-file">当前内容已同步为邮件预览，生成后会显示附件。</div>
            <div class="preview-actions">
              <IconTextButton icon="refresh" size="md" :disabled="loading.generate" @click="generateReport">
                重新生成预览
              </IconTextButton>
              <IconTextButton icon="download" size="md" :disabled="!currentDownloadUrl" @click="downloadAttachment">
                下载查看当前附件
              </IconTextButton>
            </div>
          </div>

          <div class="sheet-preview">
            <div v-if="mailDraft.preview_html" class="sheet-html" v-html="mailDraft.preview_html"></div>
            <div v-else class="sheet-empty">填写内容后，这里会显示预览。</div>
          </div>

          <div class="history-list">
            <div class="history-head">
              <strong>历史报告列表</strong>
              <div class="history-head-actions">
                <small>{{ loading.reports ? '刷新中' : `${weeklyReports.length} 份` }}</small>
                <button v-if="weeklyReports.length > 5" class="history-toggle" type="button" @click="historyExpanded = !historyExpanded">
                  {{ historyExpanded ? '收起' : `展开其余 ${hiddenWeeklyReportCount} 份` }}
                </button>
              </div>
            </div>
            <div class="history-scroll">
              <div v-for="report in visibleWeeklyReports" :key="report.name" class="history-item">
                <button class="history-load" type="button" @click="loadDraft(report.name)">
                  <span>
                    <strong>{{ report.name }}</strong>
                    <small>{{ report.generated ? '新生成' : '周报模板' }} · {{ new Date(report.mtime * 1000).toLocaleString() }}</small>
                  </span>
                  <em>{{ selectedReport === report.name ? '当前' : '加载' }}</em>
                </button>
                <button
                  v-if="report.deletable"
                  class="history-delete"
                  type="button"
                  aria-label="删除历史报告"
                  @click="deleteReportItem(report)"
                >
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
              <div v-if="!weeklyReports.length" class="history-empty">暂无历史周报。</div>
            </div>
          </div>
        </section>
      </div>

      <aside class="step-side-panel preview-side-panel">
        <section class="step-side-card status-check-card">
          <h3>生成状态</h3>
          <div class="status-check-list">
            <div :class="['status-check-item', { done: mailDraft.attachment && !isReportDirty }]">
              <span></span>
              <div>
                <strong>文件已生成</strong>
                <small>{{ mailDraft.attachment ? 'Excel 附件已生成并可下载' : '等待生成标准附件' }}</small>
              </div>
            </div>
            <div :class="['status-check-item', { done: !!mailDraft.body }]">
              <span></span>
              <div>
                <strong>邮件正文已同步</strong>
                <small>{{ mailDraft.body ? '正文内容已根据周报生成' : '生成后同步邮件正文' }}</small>
              </div>
            </div>
            <div :class="['status-check-item', { done: !!currentDownloadUrl }]">
              <span></span>
              <div>
                <strong>附件可下载</strong>
                <small>{{ currentDownloadUrl ? '可下载附件用于本地查看' : '暂无可下载附件' }}</small>
              </div>
            </div>
          </div>
        </section>

        <section class="step-side-card progress-card">
          <div class="side-card-head">
            <h3>工作上下文</h3>
            <span>{{ completionPercent }}%</span>
          </div>
          <div class="progress-track">
            <i :style="{ width: completionPercent + '%' }"></i>
          </div>
          <div class="side-check">
            <span>本周总结</span>
            <strong>{{ cleanRows('summary').length }}</strong>
          </div>
          <div class="side-check">
            <span>重点跟进</span>
            <strong>{{ cleanRows('follow').length }}</strong>
          </div>
          <div class="side-check">
            <span>下周计划</span>
            <strong>{{ cleanRows('next').length }}</strong>
          </div>
        </section>

        <section class="step-side-card assistant-side-card">
          <div class="assistant-side-title">
            <img :src="assistantAvatar" alt="犇犇" />
            <div>
              <h3>犇犇助手</h3>
              <p>预览阶段帮你检查附件和正文。</p>
            </div>
          </div>
          <div class="assistant-quick-list">
            <button type="button" @click="sendAssistantMessage('预览的附件内容是否符合预期？')">预览的附件内容是否符合预期？</button>
            <button type="button" @click="sendAssistantMessage('邮件正文结构是否清晰完整？')">邮件正文结构是否清晰完整？</button>
          </div>
        </section>
      </aside>
    </section>

    <section v-else class="wizard-step send-workspace">
      <section class="mail-card">
        <h3>邮件内容</h3>
        <label>
          <span>收件人</span>
          <el-input v-model="mailDraft.to" />
        </label>
        <label>
          <span>抄送</span>
          <el-input v-model="mailDraft.cc" />
          <button class="link-button" type="button" @click="addCcSeparator">添加抄送</button>
        </label>
        <label>
          <span>主题</span>
          <el-input v-model="mailDraft.subject" />
        </label>
        <div v-if="currentFileName" class="mail-attachment-card">
          <span class="excel-icon">X</span>
          <div>
            <strong>{{ currentFileName }}</strong>
            <small>{{ previewStateText }}</small>
          </div>
          <button class="link-button" type="button" @click="downloadAttachment">下载</button>
        </div>

        <div class="body-preview">
          <span>正文预览</span>
          <div class="body-preview-content">
            <div v-if="mailDraft.body_html" class="body-html sheet-html" v-html="mailDraft.body_html"></div>
            <div v-else-if="mailDraft.body" class="body-text">{{ mailDraft.body }}</div>
            <p v-else>生成正文后，这里会显示邮件内容。</p>
          </div>
        </div>

        <div class="mail-actions">
          <IconTextButton icon="refresh" size="md" block :disabled="loading.generate" @click="generateReport">
            重新生成正文
          </IconTextButton>
          <IconTextButton icon="copy" size="md" block @click="copyBody">
            复制正文
          </IconTextButton>
        </div>

        <div class="mail-status">
          <el-icon><Document /></el-icon>
          {{ mailStatusText }} · 共 {{ totalRows }} 条周报内容
        </div>
      </section>

      <aside class="send-confirm-column send-side-panel">
        <section class="send-review-card">
          <div :class="['send-ready-mark', { warning: sendReadinessBlockers.length }]">
            <span>{{ sendReadinessBlockers.length ? '!' : '✓' }}</span>
            <strong>{{ sendReadyText }}</strong>
          </div>
          <div class="send-review-list">
            <span>收件人</span><strong>{{ sendPayload.to || '未填写' }}</strong>
            <span>抄送</span><strong>{{ sendPayload.cc || '无' }}</strong>
            <span>主题</span><strong>{{ sendPayload.subject || '未填写' }}</strong>
            <span>附件</span><strong>{{ sendPayload.attachment || '未选择' }}</strong>
            <span>正文状态</span><strong>{{ mailDraft.body ? '已同步' : '未生成' }}</strong>
          </div>
          <div class="send-check-panel">
            <span>发送检查</span>
            <div class="status-check-list send-review-checks">
              <div :class="['status-check-item', { done: !!sendPayload.to }]">
                <span></span>
                <strong>收件人已填写</strong>
              </div>
              <div :class="['status-check-item', { done: !!sendPayload.subject }]">
                <span></span>
                <strong>主题已生成</strong>
              </div>
              <div :class="['status-check-item', { done: !!sendPayload.attachment }]">
                <span></span>
                <strong>附件已选择</strong>
              </div>
              <div :class="['status-check-item', { done: !!mailDraft.body }]">
                <span></span>
                <strong>正文已同步</strong>
              </div>
            </div>
          </div>
          <p v-if="sendReadinessBlockers.length" class="send-warning">{{ sendReadinessBlockers.join('；') }}</p>
          <p v-else class="send-info-note">邮件将通过企业邮箱服务发送，请确认收件人、主题和附件无误。</p>
        </section>

        <section class="step-side-card progress-card">
          <h3>工作上下文</h3>
          <div class="side-check">
            <span>本周总结</span>
            <strong>{{ cleanRows('summary').length }}</strong>
          </div>
          <div class="side-check">
            <span>重点跟进</span>
            <strong>{{ cleanRows('follow').length }}</strong>
          </div>
          <div class="side-check">
            <span>下周计划</span>
            <strong>{{ cleanRows('next').length }}</strong>
          </div>
          <button class="side-outline-button" type="button" @click="activeStep = 2">查看预览内容</button>
        </section>

        <section class="step-side-card assistant-side-card">
          <div class="assistant-side-title">
            <img :src="assistantAvatar" alt="犇犇" />
            <div>
              <h3>犇犇助手</h3>
              <p>发送前帮你再检查一遍。</p>
            </div>
          </div>
          <div class="assistant-quick-list">
            <button type="button" @click="sendAssistantMessage('发送前帮我再次检查收件人和附件。')">发送前帮我再次检查收件人和附件。</button>
            <button type="button" @click="sendAssistantMessage('如果不确定时发送，应该先保存草稿吗？')">如果不确定时发送，应该先保存草稿吗？</button>
          </div>
        </section>
      </aside>
    </section>

    <el-dialog
      v-model="promptDialogVisible"
      class="weekly-prompt-dialog"
      :title="promptDialogTitle"
      width="min(620px, 94vw)"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-input v-model="promptDraft" type="textarea" :autosize="{ minRows: 5, maxRows: 8 }" />
      <template #footer>
        <div class="weekly-edit-actions">
          <el-button @click="promptEditor = ''">取消</el-button>
          <el-button type="primary" @click="savePromptEditor">保存提示词</el-button>
        </div>
      </template>
    </el-dialog>

    <section class="wizard-footer">
      <div>
        <strong>{{ workflowSteps[activeStep - 1].title }}</strong>
        <span>{{ stepHint }}</span>
      </div>
      <div class="wizard-footer-actions">
        <button v-if="activeStep > 1" class="wizard-nav-button" type="button" @click="previousStep">上一步</button>
        <button class="wizard-nav-button primary" type="button" :disabled="stepActionDisabled" @click="nextStep">
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
