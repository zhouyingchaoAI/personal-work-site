<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, EditPen, Refresh, Setting, Search, Upload } from '@element-plus/icons-vue'
import { getMonthlyBattle, importMonthlyBattle, saveMonthlyBattle, uploadTicketAttachment, type MonthlyBattleItem, type ForumAttachment } from '../../../src/services/personalWorkApi'
import TicketAttachment from '../../../src/components/TicketAttachment.vue'
import { getMonthlyBattleTemplate, commentMonthlyBattle } from '../../../src/services/personalWorkApi'

const items = ref<MonthlyBattleItem[]>([])
const stages = ref<string[]>([])
const canImport = ref(false)
const scopeLabel = ref('')
const scopeLevel = ref('')
const isPersonal = computed(() => scopeLevel.value === 'personal')
const quickMode = ref(false)
const stageChangeMode = ref(false)
function changeStage(item: MonthlyBattleItem) { open(item); quickMode.value = true; stageChangeMode.value = true; form.value.stage = item.stage || 1 }
const quickItemId = ref('')
const screenshotInput = ref<HTMLInputElement>()
function registerItem(item: MonthlyBattleItem) { open(item); quickMode.value = true }
const writableItems = computed(() => items.value.filter(item => item.can_update && !item.completed))
function quickRegister() {
  const item = writableItems.value.find(entry => entry.id === quickItemId.value)
  if (!item) return void ElMessage.warning('请先选择要登记的机会点')
  open(item)
  quickMode.value = true
}
const viewOptions = ref<{ regions: string[]; users: { username: string; name: string }[] } | null>(null)
const view = ref('company')
const viewRegion = ref('')
const viewManager = ref('')
let loadSequence = 0
function changeView() {
  visible.value = false; selected.value = null; items.value = []; region.value = ''
  if (view.value === 'region' && !viewRegion.value) viewRegion.value = viewOptions.value?.regions[0] || ''
  if (view.value === 'personal' && !viewManager.value) viewManager.value = viewOptions.value?.users[0]?.username || ''
  void load()
}
const loading = ref(false)
const busy = ref(false)
const uploading = ref(false)
const month = ref(new Date().toLocaleDateString('sv-SE').slice(0, 7))
const keyword = ref('')
const region = ref('')
const onlyDue = ref(false)
const grouping = ref('current')
const activeStage = ref<number | null>(null)
const attention = ref('all')
const alertThreshold = ref(3)
try {
  const saved = Number(localStorage.getItem('monthly-battle-alert-threshold'))
  if (Number.isInteger(saved) && saved >= 1 && saved <= 7) alertThreshold.value = saved
} catch {}
watch(alertThreshold, value => {
  page.value = 1
  try { localStorage.setItem('monthly-battle-alert-threshold', String(value)) } catch {}
})
const attentionOptions = [
  { key: 'alert', label: '近14天跟进告警', hint: '未跟进周期累计达到设置阈值' },
  { key: 'followed', label: '近14天有跟进', hint: '至少一个周期登记过沟通动作' },
  { key: 'completed', label: '已实际签订', hint: '已确认合同实际签订' },
  { key: 'signing', label: '签订目标待兑现', hint: '部署阶段11，尚未确认签订' },
  { key: 'overdue', label: '逾期未跟进', hint: '超过每日 / 每两日更新要求' },
  { key: 'unrecorded', label: '尚无动作记录', hint: '先核实进展，再明确下一步' },
  { key: 'conflict', label: '原表信息待核对', hint: '重复行差异或缺少项目编码' },
]
function matchesAttention(item: MonthlyBattleItem, key: string) {
  if (key === 'alert') return !item.completed && (item.action_cycles || []).filter(cycle => cycle.status === 'red').length >= alertThreshold.value
  if (key === 'followed') return (item.action_cycles || []).some(cycle => cycle.status === 'green')
  if (key === 'completed') return item.completed
  if (key === 'signing') return item.target_stage === 11 && !item.completed
  if (key === 'overdue') return item.overdue && !item.completed
  if (key === 'unrecorded') return !item.events.some(event => event.content?.trim()) && !item.completed
  if (key === 'conflict') return !!item.conflicts?.length || item.missing_code
  return true
}
const focusCounts = computed(() => attentionOptions.map(option => ({ ...option, count: filtered.value.filter(item => matchesAttention(item, option.key)).length })))
function priorityScore(item: MonthlyBattleItem) {
  return Number(matchesAttention(item, 'overdue')) * 4 + Number(matchesAttention(item, 'signing')) * 2 + Number(matchesAttention(item, 'unrecorded'))
}
function sourceValues(item: MonthlyBattleItem, key: string) {
  return [...new Set((item.sources || []).map(source => source.values[key]?.trim()).filter((value): value is string => !!value))]
}
function amountText(item: MonthlyBattleItem) {
  const values = sourceValues(item, '可参与份额-总额(万元)')
  if (values.length > 1) return '金额待核对'
  const raw = values[0] ?? item.amount
  if (raw === '' || raw == null) return '未填写'
  const amount = Number(String(raw).replace(/,/g, ''))
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : String(raw)
}
function signingDate(item: MonthlyBattleItem) {
  const values = sourceValues(item, '合同预计签订时间')
  if (values.length > 1) return '日期不一致 · 待核对'
  return values[0]?.replace(/(?:T| )00:00:00$/, '') || '未填写'
}
const financeMetrics = computed(() => {
  if (!selected.value) return []
  const item = selected.value
  return ['管理订货', '毛利', '毛利率', '未税金额', '税率', '赢率'].map(key => {
    const values = sourceValues(item, key)
    const raw = values[0]
    const numeric = raw == null ? NaN : Number(raw.replace(/,/g, ''))
    const value = values.length > 1 ? '口径待核对' : raw == null ? '未填写' : Number.isFinite(numeric) && !key.includes('率') ? numeric.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : raw
    return { key, value, title: values.length > 1 ? values.join(' / ') : '按原表原值展示', accent: key === '毛利' || key === '毛利率' }
  })
})
function focusOn(key: string) { attention.value = attention.value === key ? 'all' : key; activeStage.value = null; page.value = 1 }
const page = ref(1)
const pageSize = 10
const selected = ref<MonthlyBattleItem | null>(null)
const sourceIndex = ref(0)
const originalExpanded = ref(false)
const clockNow = ref(Date.now())
const registrationDate = computed(() => new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long' }).format(clockNow.value))
const clockTimer = setInterval(() => { clockNow.value = Date.now() }, 60000)
onUnmounted(() => clearInterval(clockTimer))
const history = computed(() => [...(selected.value?.events || [])].reverse())
const detailStage = ref<number | null>(null)
const showAllStages = ref(false)
const visibleStages = computed(() => stages.value.map((label, index) => ({ label, index })).filter(entry => entry.index + 1 === selected.value?.stage || (showAllStages.value && Number(selected.value?.stage_days[String(entry.index + 1)]) > 0)))
const historyDays = ref(14)
const commentDrafts = ref<Record<string, string>>({})
const commentBusy = ref(false)
async function submitComment(eventId: string) {
  const content = commentDrafts.value[eventId]?.trim()
  if (!content || !selected.value) return
  commentBusy.value = true
  try { await commentMonthlyBattle(selected.value.id, eventId, content); commentDrafts.value[eventId] = ''; await load(); ElMessage.success('点评已保存') }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '点评失败') }
  finally { commentBusy.value = false }
}
const stageHistory = computed(() => history.value.filter(event => {
  const timestamp = Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(event.at) ? event.at : `${event.at}+08:00`)
  return (!historyDays.value || timestamp >= clockNow.value - historyDays.value * 86400000) && (detailStage.value === null || event.stage === detailStage.value || event.from_stage === detailStage.value)
}))
const screenshotCount = computed(() => history.value.reduce((count, event) => count + event.attachments.length, 0))
const stageEntry = computed(() => history.value.find(event => event.stage !== event.from_stage))
function elapsedSince(value?: string, end = clockNow.value) {
  if (!value) return '暂无记录'
  const timestamp = Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}+08:00`)
  if (!Number.isFinite(timestamp)) return '时间待核对'
  const minutes = Math.max(0, Math.floor((end - timestamp) / 60000))
  if (minutes < 60) return `${minutes} 分钟`
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`
  return `${Math.floor(minutes / 1440)} 天 ${Math.floor(minutes % 1440 / 60)} 小时`
}
const stageElapsed = computed(() => {
  const completed = selected.value?.completed ? history.value.find(event => event.completed)?.at : undefined
  const end = completed ? Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(completed) ? completed : `${completed}+08:00`) : clockNow.value
  return elapsedSince(stageEntry.value?.at, end)
})
const sourceGroups = computed(() => {
  const values = selected.value?.sources?.[sourceIndex.value]?.values || {}
  const groups = [
    { title: '项目与责任归属', pattern: /责任|归属|客户经理|编码|名称/ },
    { title: '订单与财务指标（保留原表单位）', pattern: /赢率|份额|金额|毛利|管理订货|税率/ },
    { title: '月度部署与签订计划', pattern: /目标|动作|签订|月|保底|冲刺|推进/ },
    { title: '区域反馈与其他信息', pattern: /[\s\S]*/ },
  ]
  const fields = Object.entries(values)
  const assigned = new Set<string>()
  return groups.map(group => ({ title: group.title, fields: fields.filter(([key]) => {
    if (assigned.has(key) || !group.pattern.test(key)) return false
    assigned.add(key)
    return true
  }) })).filter(group => group.fields.length)
})
const visible = ref(false)
const input = ref<HTMLInputElement>()
const importOpen = ref(false)
const uploadMonth = ref('')
const templateBusy = ref(false)
function startImport() { uploadMonth.value = month.value; importOpen.value = true }
async function downloadTemplate() {
  templateBusy.value = true
  try {
    const result = await getMonthlyBattleTemplate()
    const blob = new Blob([Uint8Array.from(atob(result.data), char => char.charCodeAt(0))], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = result.name; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '下载失败') }
  finally { templateBusy.value = false }
}
const form = ref({ stage: 1, cadence: 2, completed: false, content: '', stage_reason: '', next_action: '', attachments: [] as ForumAttachment[] })
const filtered = computed(() => items.value.filter(item => item.month === month.value && (!region.value || item.region === region.value) && (!onlyDue.value || item.overdue) && `${item.name} ${item.code} ${item.owner} ${item.manager}`.includes(keyword.value.trim())))
const regions = computed(() => [...new Set(items.value.filter(item => item.month === month.value).map(item => item.region))])
const columns = computed(() => [grouping.value === 'current' ? '待确认当前阶段' : '目标待确认', ...stages.value].map((label, stage) => ({ stage, label, items: filtered.value.filter(item => (grouping.value === 'current' ? item.stage : item.target_stage) === stage) })))
const listed = computed(() => filtered.value.filter(item => matchesAttention(item, attention.value) && (activeStage.value === null || (grouping.value === 'current' ? item.stage : item.target_stage) === activeStage.value)).sort((left, right) => priorityScore(right) - priorityScore(left)))
const paged = computed(() => listed.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const regional = computed(() => regions.value.map(label => ({ label, count: filtered.value.filter(item => item.region === label).length })))
watch([month, region, keyword, onlyDue, activeStage, grouping, view, viewRegion, viewManager], () => { page.value = 1 })
watch(listed, () => { page.value = Math.min(page.value, Math.max(1, Math.ceil(listed.value.length / pageSize))) })
watch(grouping, () => { activeStage.value = null })
function resetFilters() { keyword.value = ''; region.value = ''; onlyDue.value = false; activeStage.value = null; attention.value = 'all' }
async function load(initial = false) {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const data = await getMonthlyBattle(viewOptions.value ? { view: view.value, region: view.value === 'region' ? viewRegion.value : '', manager: view.value === 'personal' ? viewManager.value : '' } : {})
    if (sequence !== loadSequence) return
    scopeLabel.value = data.scope?.label || ''
    scopeLevel.value = data.scope?.level || ''
    if (isPersonal.value) { region.value = ''; keyword.value = ''; onlyDue.value = false }
    viewOptions.value = data.view_options || null
    items.value = data.items; stages.value = data.stages; canImport.value = data.can_import
    if (initial && items.value.length) month.value = [...items.value].map(item => item.month).sort().at(-1)!
    if (selected.value) selected.value = items.value.find(item => item.id === selected.value?.id) || null
  } catch (error) { if (sequence === loadSequence) { items.value = []; ElMessage.error(error instanceof Error ? error.message : '读取失败') } } finally { if (sequence === loadSequence) loading.value = false }
}
async function importFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  ;(event.target as HTMLInputElement).value = ''
  if (!file) return
  const targetMonth = uploadMonth.value
  if (!targetMonth || file.size > 10 * 1024 * 1024) return void ElMessage.warning('请选择月份和不超过10MB的Excel文件')
  busy.value = true
  try {
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]!); reader.onerror = reject; reader.readAsDataURL(file) })
    const result = await importMonthlyBattle(data, targetMonth)
    month.value = targetMonth
    importOpen.value = false
    ElMessage.success(`已更新${result.count}条机会点，${result.unassigned}条未匹配人员账号；原推进历史保留`)
    await load()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导入失败') } finally { busy.value = false }
}
function open(item: MonthlyBattleItem) {
  historyDays.value = 14
  commentDrafts.value = {}
  clockNow.value = Date.now()
  stageChangeMode.value = false
  originalExpanded.value = false
  detailStage.value = null
  showAllStages.value = false
  quickMode.value = false
  selected.value = item
  sourceIndex.value = 0
  form.value = { stage: item.stage, cadence: item.cadence, completed: item.completed, content: '', stage_reason: '', next_action: '', attachments: [] }
  visible.value = true
}
async function attach(event: Event) {
  const target = event.target as HTMLInputElement
  const files = [...(target.files || [])]; target.value = ''
  await attachFiles(files)
}
function pasteScreenshots(event: ClipboardEvent) {
  if (!quickMode.value || !selected.value?.can_update) return
  const files = Array.from(event.clipboardData?.items || []).filter(item => item.kind === 'file').map(item => item.getAsFile()).filter((file): file is File => !!file)
  if (!files.length) return
  event.preventDefault()
  void attachFiles(files)
}
function dragScreenshots(event: DragEvent) {
  if (quickMode.value && Array.from(event.dataTransfer?.types || []).includes('Files')) event.preventDefault()
}
function dropScreenshots(event: DragEvent) {
  if (!quickMode.value) return
  event.preventDefault()
  void attachFiles(Array.from(event.dataTransfer?.files || []))
}
async function attachFiles(files: File[]) {
  if (!visible.value || !quickMode.value || stageChangeMode.value || !selected.value?.can_update || !files.length) return
  if (busy.value || uploading.value) return void ElMessage.warning('正在保存或上传，请稍后再添加截图')
  if (files.length + form.value.attachments.length > 9) return void ElMessage.warning('每次最多9张截图')
  if (files.some(file => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024)) return void ElMessage.warning('截图须为PNG、JPEG或WebP，每张不超过10MB')
  const attachments = form.value.attachments
  uploading.value = true
  try {
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) throw new Error('截图须为PNG、JPEG或WebP，每张不超过10MB')
      attachments.push((await uploadTicketAttachment(file)).attachment)
    }
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '上传失败') } finally { uploading.value = false }
}
async function save() {
  if (!selected.value || busy.value || uploading.value) return
  if (stageChangeMode.value && form.value.stage === selected.value.stage) return void ElMessage.warning('阶段未发生变化，请使用登记动作')
  if (!stageChangeMode.value && (!form.value.content.trim() || !form.value.next_action.trim())) return void ElMessage.warning('请填写沟通推进细节和下一步计划')
  if (form.value.stage !== selected.value.stage && !form.value.stage_reason.trim()) return void ElMessage.warning('请填写阶段修改说明')
  busy.value = true
  try {
    await saveMonthlyBattle({ ...form.value, event_type: stageChangeMode.value ? 'stage_change' : 'action', completed: form.value.stage === 11 && form.value.completed, id: selected.value.id, revision: selected.value.revision })
    ElMessage.success('推进记录已保存，阶段计时已更新')
    await load(); form.value.content = ''; form.value.stage_reason = ''; form.value.next_action = ''; form.value.attachments = []
    if (quickMode.value) visible.value = false
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '保存失败，请刷新后重试') } finally { busy.value = false }
}
onMounted(() => load(true))
</script>

<style scoped>
.monthly-battle.monthly-battle{padding:8px 12px;border-radius:12px}
.monthly-battle.monthly-battle .mb-tools.mb-filter-bar{margin:0 0 4px;gap:8px;padding:0;min-height:32px}
.monthly-battle.monthly-battle .mb-quick-entry{margin:2px 0}
.monthly-battle.monthly-battle .mb-quick-entry>summary{padding:3px 0;font-size:12px}
.monthly-battle.monthly-battle .mb-quick-entry>summary .el-icon{padding:4px;font-size:14px}
.monthly-battle.monthly-battle .mb-compact-summary{margin:5px 0}
.monthly-battle.monthly-battle .mb-compact-summary>div,.monthly-battle.monthly-battle .mb-compact-summary>button{padding:8px 12px;gap:7px}
.monthly-battle.monthly-battle .mb-compact-summary strong{font-size:24px}
.monthly-battle.monthly-battle .mb-distribution{margin:2px 0 5px}
.monthly-battle.monthly-battle .mb-distribution>summary{padding:4px 0;font-size:12px}
.monthly-battle.monthly-battle .mb-opportunities{padding:10px 12px}
.monthly-battle.monthly-battle .mb-panel-heading{margin-bottom:6px}
</style>

<style scoped>
.monthly-battle section.mb-compact-summary{grid-template-columns:repeat(4,minmax(0,1fr));overflow:hidden}
.monthly-battle .mb-compact-summary>button{border-bottom:1px solid #e8edf4;padding:12px 16px;min-height:64px}
.monthly-battle .mb-compact-summary .alert{background:#fff1f1;color:#b52d3b}
.monthly-battle .mb-compact-summary .alert strong{color:#d52d40}
.monthly-battle .mb-compact-summary .followed,.monthly-battle .mb-compact-summary .completed{background:#edf9f3;color:#167453}
.monthly-battle .mb-compact-summary .followed strong,.monthly-battle .mb-compact-summary .completed strong{color:#14855d}
.monthly-battle .mb-compact-summary .overdue,.monthly-battle .mb-compact-summary .signing{background:#fff8ed;color:#97600d}
.monthly-battle .mb-compact-summary .overdue strong,.monthly-battle .mb-compact-summary .signing strong{color:#b66a09}
.monthly-battle .mb-compact-summary .conflict strong{color:#7955ac}
.monthly-battle .mb-compact-summary button.active{box-shadow:inset 0 -3px currentColor;outline:1px solid currentColor;outline-offset:-1px}
.mb-alert-settings{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px;color:#61758c;margin:10px 0 12px;background:#fff;border:1px solid #e6edf5;border-radius:10px;padding:10px 14px}
.mb-insights-heading{display:flex;align-items:baseline;gap:14px;margin:14px 0 10px}.mb-insights-heading h3{margin:0;font-size:17px;color:#183451}.mb-insights-heading>span{font-size:12px;color:#8291a4}
.mb-insight-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.mb-insight-card{--accent:#245caa;display:flex;align-items:center;gap:12px;min-width:0;padding:18px 16px;border:1px solid #e6edf5;border-radius:12px;background:#fff;text-align:left;font:inherit;cursor:pointer;box-shadow:0 4px 16px #254f7810;transition:box-shadow .18s,border-color .18s,transform .18s}
.mb-insight-card:hover{transform:translateY(-2px);border-color:#adc6e2;box-shadow:0 7px 20px #254f781a}.mb-insight-card.active{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.mb-insight-card:focus-visible{outline:3px solid #93b5eb;outline-offset:3px}
.mb-stat-icon{display:block;flex:0 0 50px;width:50px;height:50px;background-image:url('../../../src/assets/battle-stat-icons.png');background-size:400% 400%;background-position:0 28%;border-radius:10px}
.mb-stat-content{display:flex;flex-direction:column;gap:6px;min-width:0}.mb-stat-content>span{font-size:13px;color:#536880;line-height:1.5}.mb-stat-content strong{font-size:32px;line-height:1.1;color:var(--accent);font-variant-numeric:tabular-nums;font-weight:700}.mb-stat-chevron{margin-left:auto;font-size:23px;color:#9bacc0}
.mb-insight-card.alert{--accent:#d94350}.mb-insight-card.followed{--accent:#109f96}.mb-insight-card.completed{--accent:#16a16b}.mb-insight-card.signing{--accent:#c58a17}.mb-insight-card.overdue{--accent:#5b708f}.mb-insight-card.unrecorded{--accent:#7951bb}.mb-insight-card.conflict{--accent:#e3851b}
.mb-insight-card.secondary{padding:12px 16px}.mb-insight-card.secondary strong{font-size:24px}.mb-insight-card.secondary .mb-stat-icon{flex-basis:40px;width:40px;height:40px}
@media(max-width:1100px){.mb-insight-cards{gap:8px}.mb-insight-card{padding:14px 10px;gap:8px}.mb-stat-icon{flex-basis:38px;width:38px;height:38px}.mb-stat-content>span{font-size:12px}}
@media(max-width:760px){.mb-insight-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.mb-insights-heading>span{font-size:11px}.mb-stat-content strong{font-size:27px}.mb-insight-card.secondary{padding:12px 10px}}
.mb-alert-settings small{color:#8796a7;margin-left:auto}
@media(max-width:900px){.monthly-battle section.mb-compact-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.monthly-battle .mb-compact-summary .mb-total{grid-column:auto}}
</style>

<style scoped>
.mb-key-facts.mb-detail-facts{background:#eef5ff;border:1px solid #cbdcf2}
.mb-key-facts.mb-detail-facts .mb-money{color:#b54708;font-weight:800}
.mb-key-facts.mb-detail-facts .mb-date,.mb-key-facts.mb-detail-facts .mb-stage-number{color:#174b85}
.mb-key-facts.mb-detail-facts small{color:#47617e}
.mb-quantified.mb-quantified>div{background:#fff;border:1px solid #cbdcf2}
.mb-quantified>div>strong{color:#174b85}
.mb-quantified>div>span,.mb-quantified>div small{color:#47617e}
.mb-table .mb-money{color:#b54708}
</style>

<style scoped>
.mb-title{display:flex;align-items:center;gap:10px;font-size:21px}
.mb-title>.el-icon{padding:9px;border-radius:11px;background:#e4efff;color:#2466bd;font-size:19px}
.mb-month-label{display:flex;align-items:center;gap:7px;color:#55718f;font-size:13px}
.mb-filter-bar{align-items:center}
.mb-personal .mb-filter-bar{padding:12px 16px;background:white;border:1px solid #e2e9f2;border-radius:10px}
.mb-quick-entry>summary{display:flex;align-items:center;gap:8px;width:fit-content;color:#236bc2;font-weight:600;list-style:none}
.mb-quick-entry>summary::after{content:'⌄';margin-left:8px}
.mb-quick-entry[open]>summary::after{content:'⌃'}
.mb-quick-entry>summary small{font-weight:400;color:#8495ab;margin-left:8px}
.mb-quick-entry>summary .el-icon{padding:7px;background:#e8f1ff;border-radius:8px;font-size:16px}
@media(max-width:600px){.mb-quick-entry>summary small{display:none}.mb-title{font-size:17px}}
</style>

<style scoped src="./monthlyBattleDesign.css"></style>

<style scoped>
.mb-finance-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:10px 0 6px}.mb-finance-grid article{padding:12px 14px;background:#fff;border:1px solid #e1e9f2;border-radius:9px;display:flex;flex-direction:column;gap:6px}.mb-finance-grid span{font-size:12px;color:#6e8197}.mb-finance-grid strong{font-size:22px;color:#264f7b;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.mb-finance-grid .accent{background:#f1faf6;border-color:#d4eade}.mb-finance-grid .accent strong{color:#11835e}.mb-detail-counts{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:#74869b;padding:5px 2px}.mb-detail-counts b{color:#255589}.mb-detail-counts>span:first-child{margin-right:auto}
.mb-detail-dialog .mb-key-facts.mb-detail-facts{padding:12px 16px;margin-top:8px;gap:10px;border-radius:10px}.mb-detail-dialog .mb-key-facts.mb-detail-facts .mb-money{font-size:26px}
.mb-detail-dialog .mb-progress-summary.mb-progress-summary{margin:8px 0 12px;gap:8px}.mb-detail-dialog .mb-progress-summary.mb-progress-summary>div{padding:10px 12px;gap:4px}.mb-detail-dialog .mb-progress-summary.mb-progress-summary small{font-size:11px}
.mb-detail-dialog .mb-progress-workspace.mb-progress-workspace{grid-template-columns:minmax(220px,.55fr) minmax(0,1.5fr);gap:12px}.mb-detail-dialog .mb-state-tree.mb-state-tree,.mb-detail-dialog .mb-timeline.mb-timeline{padding:12px;border-radius:10px}.mb-detail-dialog .mb-state-nodes.mb-state-nodes{grid-template-columns:1fr;padding:4px;gap:6px}.mb-detail-dialog .mb-state-node.mb-state-node{display:grid;grid-template-columns:32px 1fr;gap:4px 8px;padding:10px;margin:0}.mb-detail-dialog .mb-state-node.mb-state-node small{grid-column:1/-1}.mb-detail-dialog .mb-state-node.mb-state-node:before{display:none}.mb-detail-dialog .mb-state-node.mb-state-node b{padding:4px}.mb-detail-dialog .mb-action.mb-action{padding:10px 12px}.mb-detail-dialog .mb-action.mb-action h4{margin:8px 0 3px}.mb-detail-dialog .mb-action.mb-action p{margin:3px 0}
@media(max-width:900px){.mb-finance-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.mb-detail-dialog .mb-progress-workspace.mb-progress-workspace{grid-template-columns:1fr}}
@media(max-width:500px){.mb-finance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>

<style scoped>
.mb-detail-layout{display:grid;grid-template-columns:minmax(300px,.85fr) minmax(0,1.5fr);gap:10px 18px;align-items:start;max-height:75vh;overflow:auto;padding-right:4px}.mb-detail-layout>p,.mb-detail-layout>.mb-detail-facts,.mb-detail-layout>.mb-finance-grid,.mb-detail-layout>.mb-detail-counts,.mb-detail-layout>.mb-progress-summary,.mb-detail-layout>.mb-duration-details,.mb-detail-layout>.mb-original-strip,.mb-detail-layout>.el-alert{grid-column:1;margin:0}
.mb-detail-layout>.mb-finance-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.mb-detail-layout>.mb-progress-workspace{display:contents!important}.mb-detail-layout .mb-state-tree{grid-column:1}.mb-detail-layout .mb-timeline{grid-column:2;grid-row:1 / span 12;position:sticky;top:0;max-height:73vh;overflow:auto;overscroll-behavior:contain}.mb-detail-layout .mb-timeline :deep(.el-timeline){max-height:none;overflow:visible}.mb-detail-layout>.mb-progress-summary{grid-template-columns:1fr}.mb-history-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}.mb-comment{padding:9px 12px;border-left:3px solid #5a8cd0;background:#f1f6fc;margin-top:8px;font-size:12px}.mb-comment time{margin-left:12px;color:#7b8ea5;font-size:11px}.mb-comment p{white-space:pre-wrap}.mb-comment-editor{display:grid;gap:8px;margin-top:12px}.mb-comment-editor>.el-button{justify-self:end}.mb-detail-layout .mb-detail-counts{gap:8px}
@media(max-width:850px){.mb-detail-layout{display:block;max-height:none;overflow:visible}.mb-detail-layout .mb-timeline{position:static;max-height:65vh;margin-top:12px}.mb-detail-layout>section{margin:10px 0}}
</style>

<template>
  <section class="monthly-battle" :class="{ 'mb-personal': isPersonal }" v-loading="loading">
    <div class="mb-tools mb-filter-bar"><template v-if="viewOptions"><el-select v-model="view" aria-label="权限视图" @change="changeView"><el-option label="管理视图" value="company" /><el-option label="区总视图" value="region" /><el-option label="个人视图" value="personal" /></el-select><el-select v-if="view === 'region'" v-model="viewRegion" aria-label="查看区域" @change="changeView"><el-option v-for="value in viewOptions.regions" :key="value" :label="value" :value="value" /></el-select><el-select v-if="view === 'personal'" v-model="viewManager" filterable aria-label="查看人员" @change="changeView"><el-option v-for="user in viewOptions.users" :key="user.username" :label="`${user.name}（${user.username}）`" :value="user.username" /></el-select></template><span v-if="isPersonal" class="mb-month-label"><el-icon><Calendar /></el-icon>任务月份</span><el-date-picker v-model="month" type="month" format="YYYY年MM月" value-format="YYYY-MM" :clearable="false" placeholder="任务月份" /><template v-if="!isPersonal"><el-select v-model="region" clearable placeholder="全部项目归属"><el-option v-for="value in regions" :key="value" :label="value" :value="value" /></el-select><el-input :prefix-icon="Search" v-model="keyword" clearable placeholder="搜索机会点、编码、责任人" /><el-checkbox v-model="onlyDue">仅看逾期未更新</el-checkbox></template><el-button v-if="canImport && !isPersonal" type="primary" :icon="Upload" :loading="busy" @click="startImport">上传月度任务令</el-button><el-button :loading="templateBusy" @click="downloadTemplate">下载模板</el-button><el-button :icon="Refresh" @click="load()">刷新</el-button><input ref="input" hidden type="file" accept=".xlsx" @change="importFile" /></div>
    <el-dialog v-model="importOpen" title="上传月度任务令" width="min(480px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
      <el-form label-position="top"><el-form-item label="任务归属月份" required><el-date-picker v-model="uploadMonth" type="month" format="YYYY年MM月" value-format="YYYY-MM" :clearable="false" :disabled="busy" /></el-form-item></el-form>
      <p class="mb-note">上传 .xlsx 文件，最大10MB。同月同编码将更新原表信息，已登记的推进历史保留。</p>
      <el-button link type="primary" :loading="templateBusy" @click="downloadTemplate">下载月度任务令模板（含11阶段字典及填写说明）</el-button>
      <template #footer><el-button :disabled="busy" @click="importOpen = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="!uploadMonth" @click="input?.click()">选择文件并上传</el-button></template>
    </el-dialog>
    <details class="mb-quick-entry"><summary><el-icon><EditPen /></el-icon> 登记动作 <small>选择机会点，快速记录沟通进展</small></summary>
    <section class="mb-daily-entry"><div><strong>每日动作工作台</strong><small>选机会点 → 登记沟通 → 上传截图</small></div><el-select v-model="quickItemId" filterable placeholder="搜索并选择要登记的机会点" aria-label="快捷登记机会点"><el-option v-for="item in writableItems" :key="item.id" :value="item.id" :label="`${item.name} · ${item.month} · ${item.code}`" /></el-select><el-button type="primary" :disabled="!quickItemId" @click="quickRegister">登记今日动作</el-button></section>
    </details>
    <div class="mb-insights-heading"><h3>任务推进概览</h3><span>点击指标筛选机会点</span></div>
    <section class="mb-insight-cards" aria-label="任务推进统计筛选">
      <button class="mb-insight-card total" :class="{ active: attention === 'all' }" :aria-pressed="attention === 'all'" @click="attention = 'all'; activeStage = null; page = 1"><i class="mb-stat-icon" aria-hidden="true"></i><span class="mb-stat-content"><span>本月机会点</span><strong>{{ filtered.length }}</strong></span><span class="mb-stat-chevron" aria-hidden="true">›</span></button>
      <button v-for="(entry, index) in focusCounts" :key="entry.key" class="mb-insight-card" :class="[entry.key, { active: attention === entry.key, secondary: index > 2 }]" :title="entry.hint" :aria-pressed="attention === entry.key" @click="focusOn(entry.key)"><i class="mb-stat-icon" :style="{ backgroundPosition: `${((index + 1) % 4) * 100 / 3}% ${index < 3 ? 28 : 73}%` }" aria-hidden="true"></i><span class="mb-stat-content"><span>{{ entry.label }}</span><strong>{{ entry.count }}</strong></span><span class="mb-stat-chevron" aria-hidden="true">›</span></button>
    </section>
    <div class="mb-alert-settings"><el-icon><Setting /></el-icon><span>告警规则：近14天累计 <b>{{ alertThreshold }}次</b> 未跟进 · 每2天一个周期</span><el-popover placement="bottom-end" :width="280" trigger="click"><template #reference><el-button link type="primary">阈值设置 ›</el-button></template><div class="mb-threshold-editor"><strong>跟进告警阈值</strong><p>近14天累计未跟进达到以下次数时告警，项目建立前不计入。</p><el-select v-model="alertThreshold" aria-label="未跟进告警阈值"><el-option v-for="count in 7" :key="count" :value="count" :label="`${count}次未跟进`" /></el-select><small>自动保存到当前浏览器</small></div></el-popover></div>
    <details class="mb-distribution"><summary>阶段与区域分布 · 点击展开</summary>
    <div class="mb-overview">
      <section class="mb-panel"><div class="mb-panel-heading"><h3>当前阶段分布</h3></div>
        <div class="mb-stages"><button v-for="column in columns" :key="column.stage" class="mb-stage" :class="{ active: activeStage === column.stage }" :aria-pressed="activeStage === column.stage" @click="activeStage = activeStage === column.stage ? null : column.stage"><span>{{ column.stage ? String(column.stage).padStart(2, '0') : '待确认' }}</span><strong>{{ column.items.length }}<small> 个</small></strong><span>{{ column.label }}</span><i :style="{ '--share': (filtered.length ? column.items.length / filtered.length * 100 : 0) + '%' }" /></button></div>
        <p class="mb-note">原表“目标/动作”中的阶段作为首次导入的当前阶段；后续仅在真实阶段变化时更新。阶段11不等于已实际签订。</p>
      </section>
      <section class="mb-panel"><div class="mb-panel-heading"><h3>区域 / 办事处分布</h3><el-button link @click="region = ''">全部区域</el-button></div><div class="mb-region-list"><button v-for="entry in regional" :key="entry.label" @click="region = region === entry.label ? '' : entry.label"><span>{{ entry.label || '待分配' }}</span><i><b :style="{ width: (filtered.length ? entry.count / filtered.length * 100 : 0) + '%' }" /></i><strong>{{ entry.count }}</strong></button></div><p v-if="!regional.length" class="mb-note">本月暂无区域数据</p></section>
    </div>
    </details>
    <section class="mb-panel mb-opportunities">
      <div class="mb-panel-heading"><div><h3>机会点清单 <small>{{ listed.length }} 个</small></h3><p class="mb-note">逾期优先 · 点击项目查看跟进，原表完整信息在详情中保留</p></div><el-button @click="resetFilters">重置筛选</el-button></div>
      <el-tag v-if="attention !== 'all'" closable @close="attention = 'all'">{{ attentionOptions.find(option => option.key === attention)?.label }}</el-tag>
      <el-tag v-if="activeStage !== null" closable @close="activeStage = null">{{ columns[activeStage]?.label }}</el-tag>
      <el-table :data="paged" class="mb-table" @row-click="open" empty-text="当前条件下暂无机会点，请切换月份或重置筛选">
        <el-table-column type="index" label="序号" width="64" :index="(index: number) => (page - 1) * pageSize + index + 1" />
        <el-table-column label="机会点 / 编码" min-width="250"><template #default="{ row }"><button class="mb-project" @click.stop="open(row)">{{ row.name }}</button><small class="mb-secondary">{{ row.code }}</small></template></el-table-column>
        <el-table-column label="可参与份额（万元）" min-width="170"><template #default="{ row }"><strong class="mb-money">{{ amountText(row) }}</strong><small class="mb-secondary">原表份额，非已成交金额</small></template></el-table-column>
        <el-table-column label="原表预计签订" min-width="175"><template #default="{ row }"><strong class="mb-date">{{ signingDate(row) }}</strong></template></el-table-column>
        <el-table-column prop="region" label="区域归属" min-width="120" />
        <el-table-column label="责任人" min-width="100"><template #default="{ row }">{{ row.owner || row.manager || '待分配' }}<small v-if="!row.assignees.length" class="mb-secondary">账号未匹配</small></template></el-table-column>
        <el-table-column label="当前阶段 / 动作状态" min-width="270"><template #default="{ row }"><el-tag :type="row.completed ? 'success' : row.stage ? 'primary' : 'info'">{{ row.stage ? `${String(row.stage).padStart(2, '0')} · ${stages[row.stage - 1]}` : '原表未明确阶段' }}</el-tag><div class="mb-cycle-head"><span>近14天跟进状态</span><b>每2天一格</b></div><div class="mb-action-cycles" aria-label="近14天跟进状态，每两天登记过动作即绿色"><span v-for="(cycle, index) in row.action_cycles" :key="`${cycle.label}-${index}`" :class="cycle.status" :title="`${cycle.label}：${cycle.status === 'green' ? '已登记动作' : cycle.status === 'red' ? '未登记动作' : '尚未进入统计期'}`"><i></i><small>{{ index === row.action_cycles.length - 1 ? '本期' : index + 1 }}</small></span></div></template></el-table-column>
        <el-table-column label="最近推进 / 更新要求" min-width="175"><template #default="{ row }"><span v-if="row.events.length">{{ row.last_at.replace('T', ' ').slice(0, 16) }}</span><span v-else>暂无推进记录</span><small class="mb-secondary" :class="{ 'mb-overdue': row.overdue }">{{ row.completed ? '合同已实际签订' : row.overdue ? '已逾期 · 请补充记录' : '每' + row.cadence + '天更新' }}</small></template></el-table-column>
        <el-table-column label="操作" width="145" fixed="right"><template #default="{ row }"><div class="mb-row-actions"><el-button v-if="row.can_update" class="mb-register-button" type="primary" size="small" @click.stop="registerItem(row)">＋ 登记动作</el-button><el-button v-if="row.can_update" link type="primary" @click.stop="changeStage(row)">变更阶段</el-button><el-button link type="primary" @click.stop="open(row)">查看推进 →</el-button></div></template></el-table-column>
      </el-table>
      <div class="mb-pagination"><span>共 {{ listed.length }} 个机会点 · 每页 {{ pageSize }} 个</span><el-pagination v-model:current-page="page" :page-size="pageSize" :total="listed.length" layout="prev, pager, next" /></div>
    </section>
    <details class="mb-help"><summary>统计与推进规则</summary><p>进展默认每2天登记，可设为每天；不要求每天更换阶段。阶段停留只统计系统记录的区间，不倒推历史。导入按月份和编码更新并保留推进历史，不自动改写商机成交状态。区域分布按原表项目归属统计，东区办事处分别展示。</p></details>
    <el-dialog class="mb-detail-dialog" :class="{ 'mb-register-dialog': quickMode }" v-model="visible" :title="quickMode ? (stageChangeMode ? '变更项目阶段' : '登记今日动作') : selected?.name || '推进详情'" :width="quickMode ? 'min(760px, 96vw)' : 'min(1280px, 96vw)'" @paste="pasteScreenshots" @dragover="dragScreenshots" @drop="dropScreenshots" append-to-body :close-on-click-modal="false">
      <div v-if="quickMode && selected" class="mb-register-context"><div class="mb-registration-date"><span>登记日期（北京时间）</span><strong>{{ registrationDate }}</strong><small>保存时自动记录实际提交时间，无需手填</small></div><span>当前项目</span><strong>{{ selected.name }}</strong><small>{{ selected.stage ? stages[selected.stage - 1] : '首次登记 · 请确认当前阶段' }} · {{ selected.owner || selected.manager }}</small></div>
      <template v-if="selected"><p>{{ selected.month }} · {{ selected.region }} · {{ selected.code }} · 责任人 {{ selected.owner || selected.manager }}</p><p v-if="quickMode" class="mb-note">登记今日沟通动作，提交后保存在推进时间轴；阶段无变化时无需修改阶段。截图支持多选。</p><div v-if="!quickMode" class="mb-detail-layout"><p>本月目标：{{ selected.target || '未填写' }} ｜ 最近记录：{{ selected.last_at.replace('T', ' ') }}</p>
        <div class="mb-key-facts mb-detail-facts"><div><small>可参与份额（非已成交）</small><strong class="mb-money">{{ amountText(selected) }}<small> 万元</small></strong></div><div><small>原表预计签订日期</small><strong class="mb-date">{{ signingDate(selected) }}</strong></div><div><small>原表导入阶段</small><strong class="mb-stage-number">{{ selected.target_stage ? String(selected.target_stage).padStart(2, '0') : '未明确' }}</strong><small>{{ selected.target_stage ? stages[selected.target_stage - 1] : '详见原文动作' }}</small></div></div>
        <section class="mb-finance-grid" aria-label="原表财务指标"><article v-for="metric in financeMetrics" :key="metric.key" :class="{ accent: metric.accent }" :title="metric.title"><span>{{ metric.key }}</span><strong>{{ metric.value }}</strong></article></section>
        <div v-if="history.length" class="mb-detail-counts"><span v-if="history.some(event => event.event_type !== 'stage_change')">沟通动作 <b>{{ history.filter(event => event.event_type !== 'stage_change').length }}</b> 次</span><span v-if="screenshotCount">截图 <b>{{ screenshotCount }}</b> 张</span></div>
        <div class="mb-progress-workspace">
        <section class="mb-state-tree"><header><h3>阶段与累计停留</h3><el-button v-if="detailStage !== null" link type="primary" @click="detailStage = null">全部动作</el-button></header>
          <div class="mb-state-nodes"><button v-for="{ label, index } in visibleStages" :key="label" class="mb-state-node" :class="{ current: selected.stage === index + 1, picked: detailStage === index + 1 }" :aria-pressed="detailStage === index + 1" @click="detailStage = detailStage === index + 1 ? null : index + 1"><b>{{ String(index + 1).padStart(2, '0') }}</b><strong>{{ label }}</strong><span>{{ selected.stage === index + 1 ? (selected.completed ? '已签订' : '当前阶段') : '历史阶段' }}</span><small v-if="Number(selected.stage_days[String(index + 1)]) > 0">累计停留 {{ selected.stage_days[String(index + 1)] }} 天</small><small v-if="selected.stage === index + 1 && stageEntry">本次停留 {{ stageElapsed }}</small></button></div>
          <el-button v-if="Object.entries(selected.stage_days).some(([stage, days]) => Number(stage) !== selected?.stage && Number(days) > 0)" link type="primary" @click="showAllStages = !showAllStages">{{ showAllStages ? '收起历史阶段' : '展开历史阶段停留' }}</el-button>
          <p v-if="!selected.stage" class="mb-note">当前阶段待确认</p>
          <p v-if="history.some(event => event.event_type !== 'stage_change')" class="mb-note">最近动作：{{ elapsedSince(history.find(event => event.event_type !== 'stage_change')?.at) }}前<span v-if="selected.overdue"> · 跟进已逾期</span></p>
        </section>
        <section class="mb-timeline"><header class="mb-history-toolbar"><h3>阶段与动作时间树 · {{ stageHistory.length }} 条</h3><el-select v-model="historyDays" aria-label="时间树范围" style="width:120px"><el-option :value="14" label="近14天"/><el-option :value="30" label="近30天"/><el-option :value="0" label="全部记录"/></el-select></header><el-tag v-if="detailStage !== null" closable @close="detailStage = null">{{ stages[detailStage - 1] }} · {{ stageHistory.length }} 条相关动作</el-tag><p class="mb-note">最新记录在前，时间为系统提交时间。阶段未变更不等于没有实质进展，请结合沟通结果判断。</p><p v-if="!stageHistory.length">{{ history.length ? '该阶段暂无相关动作记录。' : '暂无记录，请先确认当前阶段并记录首次沟通。' }}</p>
          <el-timeline><el-timeline-item v-for="event in stageHistory" :key="event.id" :timestamp="event.at.replace('T', ' ')" placement="top" :type="event.completed ? 'success' : event.stage !== event.from_stage ? 'primary' : 'info'"><article class="mb-action"><header><strong>{{ event.author }}</strong><el-tag>{{ event.completed ? '确认签订' : event.stage === event.from_stage ? '阶段内进展' : event.stage < event.from_stage ? '阶段回退' : '阶段推进' }}</el-tag></header><p>{{ event.from_stage ? stages[event.from_stage - 1] : '待确认阶段' }} → {{ stages[event.stage - 1] || '阶段尚未确认' }}</p><template v-if="event.from_stage !== event.stage"><h4>阶段修改说明</h4><p>{{ event.stage_reason || '历史记录未单独填写，请结合沟通内容核对' }}</p></template><h4>沟通动作与推进结果</h4><p>{{ event.content }}</p><h4>下一步动作及计划</h4><p>{{ event.next_action }}</p><div class="mb-images"><TicketAttachment v-for="attachment in event.attachments" :key="attachment.id" :attachment="attachment" /></div><section class="mb-comments"><div v-for="comment in event.comments || []" :key="comment.id" class="mb-comment"><strong>{{ comment.author }}</strong><time>{{ comment.at.replace("T", " ") }}</time><p>{{ comment.content }}</p></div><div v-if="selected.can_comment" class="mb-comment-editor"><el-input v-model="commentDrafts[event.id]" type="textarea" :rows="2" maxlength="2000" placeholder="点评本次动作，提出建议或下一步要求" :disabled="commentBusy"/><el-button type="primary" size="small" :disabled="!commentDrafts[event.id]?.trim()" :loading="commentBusy" @click="submitComment(event.id)">提交点评</el-button></div></section></article></el-timeline-item></el-timeline>
        </section>
        </div>
        <el-alert v-if="selected.conflicts?.length || selected.missing_code" type="warning" :closable="false" :title="`原表待核对：${selected.missing_code ? '缺少子项目编码；' : ''}${selected.conflicts?.length ? '重复行部分字段不一致，暂显示首个非空值，请展开来源核对后修正Excel重新导入。' : ''}`" />
        <details class="mb-original-strip" :open="originalExpanded" @toggle="originalExpanded = ($event.target as HTMLDetailsElement).open"><summary>原表完整信息 <span>· {{ selected.sources?.length || 0 }} 条来源 · {{ originalExpanded ? '收起' : '展开' }}</span></summary>
        <section class="mb-original">
          <div class="mb-panel-heading"><h3>原表完整信息</h3><el-select v-if="selected.sources?.length" v-model="sourceIndex" aria-label="原表来源行" style="width: 320px; max-width: 100%"><el-option v-for="(source, index) in selected.sources" :key="source.sheet + source.row" :value="index" :label="`${source.sheet} · 第${source.row}行`" /></el-select></div>
          <p class="mb-note">共 {{ selected.sources?.length || 0 }} 条来源行。下方按选中原始行展示，不合并覆盖差异值；金额、百分比、月份均保留原表文本。</p>
          <section v-for="(group, index) in sourceGroups" :key="group.title" class="mb-field-group"><h4>{{ String(index + 1).padStart(2, '0') }} · {{ group.title }}</h4><dl><div v-for="[key, value] in group.fields" :key="key"><dt>{{ key }}</dt><dd>{{ value === '' || value == null ? '未填写' : value }}</dd></div></dl></section>
          <el-empty v-if="!sourceGroups.length" description="暂无原表来源信息" :image-size="50" />
          <details v-if="selected.sources?.length" class="mb-source-compare"><summary>逐行原文核对 · {{ selected.sources.length }} 条（包括重复行）</summary><article v-for="source in selected.sources" :key="source.sheet + source.row"><h4>{{ source.sheet }} · 第{{ source.row }}行</h4><dl><div v-for="(value, key) in source.values" :key="key"><dt>{{ key }}</dt><dd>{{ value === '' || value == null ? '未填写' : value }}</dd></div></dl></article></details>
        </section>
        </details>
        </div>
        <el-form v-if="quickMode && selected.can_update" label-position="top" :disabled="busy || uploading"><p class="mb-note">{{ stageChangeMode ? '仅在阶段真实变化时提交，说明变更依据；修改将保留日志。' : '仅登记本次沟通进展和截图，保持当前阶段不变。需要调整阶段请使用“变更阶段”。' }}</p><div class="mb-form-row"><el-form-item v-if="stageChangeMode" label="变更后的阶段"><el-select v-model="form.stage"><el-option v-for="(label, index) in stages" :key="label" :label="`${index + 1}. ${label}`" :value="index + 1" /></el-select></el-form-item><el-form-item v-if="!stageChangeMode" label="进展登记频率（不是换阶段频率）"><el-radio-group v-model="form.cadence"><el-radio-button :value="1">每天</el-radio-button><el-radio-button :value="2">每2天</el-radio-button></el-radio-group></el-form-item></div><el-form-item v-if="stageChangeMode && form.stage !== selected.stage" label="阶段修改说明（必填）"><el-input v-model="form.stage_reason" type="textarea" :rows="2" maxlength="2000" show-word-limit placeholder="说明为什么调整阶段、依据是什么；首次确认也需要说明" /></el-form-item><el-form-item v-if="!stageChangeMode" label="沟通推进细节（必填）"><el-input v-model="form.content" type="textarea" :rows="3" maxlength="10000" placeholder="沟通对象、采取的动作、反馈结果、阻碍事项；阶段变化请说明依据" /></el-form-item><el-form-item v-if="!stageChangeMode" label="下一步动作及计划日期（必填）"><el-input v-model="form.next_action" maxlength="2000" placeholder="下一步联系谁、做什么、计划何时完成" /></el-form-item><el-checkbox v-if="!stageChangeMode && form.stage === 11" v-model="form.completed">确认合同已实际签订（仅进入阶段不代表完成）</el-checkbox><div v-if="!stageChangeMode" class="mb-upload-zone" tabindex="0" aria-label="粘贴或拖入沟通截图"><input ref="screenshotInput" hidden type="file" accept="image/png,image/jpeg,image/webp" multiple :disabled="busy || uploading" @change="attach" /><el-button :disabled="busy || uploading" :loading="uploading" @click="screenshotInput?.click()">＋ 添加沟通截图</el-button><span>可直接 Ctrl / ⌘ + V 粘贴截图，或拖入图片 · PNG / JPEG / WebP · 最多9张，每张10MB</span></div><div v-if="!stageChangeMode" class="mb-images"><div v-for="(attachment, index) in form.attachments" :key="attachment.id"><TicketAttachment :attachment="attachment" /><el-button link :disabled="busy || uploading" @click="form.attachments.splice(index, 1)">移除</el-button></div></div><div class="mb-register-footer"><span>保存后进入项目时间轴，领导可查看</span><el-button type="primary" size="large" :loading="busy || uploading" @click="save">{{ stageChangeMode ? '确认变更阶段' : '保存本次推进' }}</el-button></div></el-form>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.mb-registration-date{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding-bottom:12px;margin-bottom:4px;border-bottom:1px solid #d8e6f5}.mb-registration-date strong{font-size:16px;font-variant-numeric:tabular-nums}.mb-registration-date small{flex-basis:100%}
</style>

<style scoped>
.mb-row-actions{display:flex;flex-direction:column;align-items:stretch;gap:6px}.mb-row-actions .el-button+.el-button{margin-left:0}.mb-register-button{font-weight:650;border-radius:6px}.mb-register-context{padding:16px 20px;border-radius:12px;background:linear-gradient(110deg,#e9f3ff,#f2f8fe);display:flex;flex-direction:column;gap:8px;margin-bottom:14px}.mb-register-context span,.mb-register-context small{font-size:12px;color:#6b829a}.mb-register-context strong{font-size:17px;color:#214c75;line-height:1.5}.mb-upload-zone{border:1px dashed #acc9e6;border-radius:10px;background:#f5faff;padding:18px;display:flex;flex-wrap:wrap;align-items:center;gap:12px}.mb-upload-zone span{font-size:11px;color:#7a8fa5}.mb-register-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;padding-top:18px;margin-top:14px;border-top:1px solid #e8eef5}.mb-register-footer span{font-size:12px;color:#7a8fa5}@media(max-width:600px){.mb-register-footer{flex-direction:column;align-items:stretch}}
.mb-cycle-head{display:flex;align-items:center;justify-content:space-between;margin-top:9px;font-size:10px;color:#74879b}.mb-cycle-head b{color:#315f8d;font-weight:650}.mb-action-cycles{display:flex;align-items:flex-start;gap:8px;margin-top:5px}.mb-action-cycles>span{display:grid;justify-items:center;gap:3px;min-width:18px}.mb-action-cycles i{width:12px;height:12px;border-radius:50%;background:#aebbc8;box-shadow:0 0 0 3px #edf1f5}.mb-action-cycles .green i{background:#1eaa71;box-shadow:0 0 0 3px #daf4e8}.mb-action-cycles .red i{background:#e64d4d;box-shadow:0 0 0 3px #fde5e5}.mb-action-cycles small{font-size:9px;color:#8493a4;line-height:1}.mb-action-cycles .green small{color:#16835a}.mb-action-cycles .red small{color:#c33d3d}
</style>
<style>
.mb-register-dialog .el-form{background:white;border:1px solid #e5edf5;border-radius:12px;padding:20px;margin-top:16px}.mb-register-dialog .el-form-item__label{font-size:13px;font-weight:600;color:#345570}.mb-register-dialog .el-textarea__inner{padding:12px;line-height:1.7;border-radius:8px}.mb-register-dialog .el-input__wrapper{border-radius:8px;min-height:36px}
</style>

<style scoped>
.mb-original-strip{margin:10px 0;border:1px solid #e0e7ef;border-radius:5px;background:white;padding:0;min-height:0}.mb-original-strip>summary{cursor:pointer;padding:6px 10px;font-size:12px;line-height:18px;color:#496781}.mb-original-strip>summary span{color:#8a9aac;font-size:11px;margin-left:6px}.mb-original-strip>.mb-original{border:0;border-top:1px solid #eef2f6;border-radius:0;margin:0;padding:14px}.mb-original-strip>summary:focus-visible{outline:2px solid #2981ce;outline-offset:2px}
</style>

<style scoped>
.monthly-battle .mb-compact-summary{display:grid;grid-template-columns:1.2fr repeat(4,1fr);gap:0;background:white;border:1px solid #e2e9f2;border-radius:10px;margin:12px 0}.mb-compact-summary>div,.mb-compact-summary>button{padding:14px 18px;display:flex;flex-wrap:wrap;align-items:center;gap:10px;background:transparent;border:0;border-right:1px solid #e8edf4;color:#38536d;text-align:left;font:inherit}.mb-compact-summary>button{cursor:pointer}.mb-compact-summary>button:last-child{border:0}.mb-compact-summary span{font-size:12px}.mb-compact-summary strong{font-size:26px;color:#204f7c;font-variant-numeric:tabular-nums}.mb-compact-summary small{font-size:11px;color:#71849b}.mb-compact-summary button.active{background:#eaf3ff;box-shadow:inset 0 -3px #2981ce}.mb-distribution,.mb-quick-entry{margin:10px 0;font-size:12px;color:#56748f}.mb-distribution>summary,.mb-quick-entry>summary{cursor:pointer;padding:9px 0}.mb-distribution .mb-overview{margin-top:10px}.monthly-battle .mb-opportunities{padding:14px;border-radius:10px}.monthly-battle .mb-table :deep(.el-table__cell){padding:8px 0}.monthly-battle .mb-table .mb-money{font-size:18px}.monthly-battle .mb-table .mb-date{font-size:13px}.monthly-battle .mb-tools{margin:10px 0}.monthly-battle .mb-secondary{margin-top:4px;font-size:11px}.monthly-battle .mb-table :deep(.cell){line-height:1.5}.monthly-battle .mb-panel-heading{margin-bottom:10px}@media(max-width:900px){.monthly-battle .mb-compact-summary{grid-template-columns:repeat(2,1fr)}.mb-compact-summary .mb-total{grid-column:1/-1}}
</style>

<style>
.mb-detail-dialog.el-dialog{padding:24px;border-radius:20px;background:#f5f8fc;font-family:Inter,"PingFang SC","Microsoft YaHei",sans-serif;color:#243f61}.mb-detail-dialog .el-dialog__header{padding:0 42px 18px 0;border-bottom:1px solid #e0e8f1;margin-bottom:18px}.mb-detail-dialog .el-dialog__title{font-size:21px;font-weight:700;line-height:1.5}.mb-detail-dialog .mb-detail-facts{background:linear-gradient(115deg,#153856,#205784);border:0;margin-top:18px;padding:22px 28px;border-radius:14px}.mb-detail-dialog .mb-detail-facts strong{color:#fff}.mb-detail-dialog .mb-detail-facts small{color:#c3d9ed}.mb-detail-dialog .mb-detail-facts .mb-money{font-size:32px}.mb-detail-dialog .mb-quantified{gap:10px;margin:12px 0}.mb-detail-dialog .mb-quantified>div{background:white;color:#234d73;border:1px solid #e5ecf3;padding:16px 20px}.mb-detail-dialog .mb-quantified strong{color:#236cb5;font-size:30px}.mb-detail-dialog .mb-quantified span,.mb-detail-dialog .mb-quantified small{color:#68829d}.mb-detail-dialog .mb-progress-summary{margin:12px 0 20px}.mb-detail-dialog .mb-progress-summary>div{background:white;border-color:#e5ecf3;padding:14px 18px}.mb-detail-dialog .mb-progress-summary .mb-idle-warning{background:#fff5e8;border-color:#f5dfbe}.mb-detail-dialog .mb-progress-workspace{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.25fr);gap:18px;align-items:start}.mb-detail-dialog .mb-state-tree,.mb-detail-dialog .mb-timeline{background:white;border:1px solid #e4ebf3;border-radius:14px;padding:20px;margin:0;min-width:0}.mb-detail-dialog .mb-state-tree h3,.mb-detail-dialog .mb-timeline h3{font-size:16px;margin:0 0 10px}.mb-detail-dialog .mb-state-nodes{grid-template-columns:1fr;gap:0;max-height:640px;overflow:auto;padding:5px}.mb-detail-dialog .mb-state-node{position:relative;display:grid;grid-template-columns:38px 1fr auto;gap:5px 12px;padding:12px;margin:0 0 10px 12px;border:1px solid #e4ebf3;background:#fafcfe;border-radius:10px}.mb-detail-dialog .mb-state-node:before{content:"";position:absolute;left:-11px;top:45px;bottom:-20px;width:2px;background:#dce7f3}.mb-detail-dialog .mb-state-node:last-child:before{display:none}.mb-detail-dialog .mb-state-node b{grid-row:span 2;align-self:center;background:#eaf0f7;color:#68829d;border-radius:8px;font-size:17px;padding:8px 0;text-align:center}.mb-detail-dialog .mb-state-node strong{align-self:center;font-size:12px}.mb-detail-dialog .mb-state-node small{grid-column:2 / 4;color:#7a8fa5}.mb-detail-dialog .mb-state-node span{font-size:10px;align-self:center}.mb-detail-dialog .mb-state-node.recorded b{background:#e3f4ef;color:#188c76}.mb-detail-dialog .mb-state-node.current{background:#eaf4ff;border-color:#74ace2;box-shadow:0 3px 12px #245c9820}.mb-detail-dialog .mb-state-node.current b{background:#2679c9;color:white}.mb-detail-dialog .mb-timeline>.el-timeline{max-height:640px;overflow:auto;padding:4px 12px}.mb-detail-dialog .el-timeline-item__timestamp{color:#597591;font-weight:600;font-size:12px}.mb-detail-dialog .mb-action{border:1px solid #e3eaf3;border-radius:12px;background:#fff;padding:16px;box-shadow:0 3px 10px #233c5710}.mb-detail-dialog .mb-action header{border-bottom:1px solid #edf1f6;padding-bottom:10px}.mb-detail-dialog .mb-action p{font-size:13px;line-height:1.8}.mb-detail-dialog .mb-action h4{font-size:11px;color:#7d90a6}.mb-detail-dialog .mb-duration-details{margin:18px 0;border:1px solid #e1e9f2;border-radius:10px;background:white;padding:14px 18px}.mb-detail-dialog .mb-duration-details summary{cursor:pointer;color:#426685;font-size:13px}.mb-detail-dialog>.el-dialog__body>.el-form{background:white;border-radius:14px;padding:20px;margin-top:18px}.mb-detail-dialog button:focus-visible{outline:2px solid #2782d1;outline-offset:2px}@media(max-width:900px){.mb-detail-dialog .mb-progress-workspace{grid-template-columns:1fr}.mb-detail-dialog .mb-state-nodes{max-height:330px}.mb-detail-dialog.el-dialog{padding:16px}.mb-detail-dialog .mb-state-node{grid-template-columns:32px 1fr auto}}
</style>

<style scoped>
.mb-quantified{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.mb-quantified>div{background:#173f68;color:white;padding:18px;border-radius:10px;display:flex;flex-direction:column;gap:8px}.mb-quantified strong{font-size:34px;font-variant-numeric:tabular-nums}.mb-quantified strong small{font-size:13px;font-weight:400}.mb-quantified span,.mb-quantified small{font-size:12px;color:#c6def4}.mb-state-tree{border:1px solid #dce8f5;border-radius:12px;padding:18px;margin-bottom:18px}.mb-state-tree header{display:flex;justify-content:space-between;align-items:center}.mb-state-tree h3{margin:0}.mb-state-nodes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.mb-state-node{font:inherit;display:flex;flex-direction:column;text-align:left;gap:8px;padding:12px;border:1px solid #dce5f0;border-left:4px solid #c4d1e1;border-radius:8px;background:#f8fafc;color:#647c97;cursor:pointer}.mb-state-node b{font-size:22px}.mb-state-node strong{font-size:12px}.mb-state-node span,.mb-state-node small{font-size:11px}.mb-state-node.recorded{border-left-color:#23a18a}.mb-state-node.current{background:#eaf4ff;border-color:#2985da;color:#1763a5}.mb-state-node.picked{outline:2px solid #2385df;outline-offset:2px}.mb-progress-summary strong{font-variant-numeric:tabular-nums}@media(max-width:700px){.mb-quantified{grid-template-columns:repeat(2,minmax(0,1fr))}.mb-state-nodes{grid-template-columns:repeat(2,minmax(0,1fr))}}
.mb-key-facts{display:flex;flex-wrap:wrap;gap:18px;margin-top:12px;padding:12px;background:#edf5ff;border-radius:8px}.mb-key-facts>div{min-width:100px}.mb-key-facts small{display:block;font-size:11px;color:#607c9a;margin:0 0 5px}.mb-money,.mb-priority-item .mb-money{font-size:22px;font-weight:750;color:#1467b2;font-variant-numeric:tabular-nums;display:block}.mb-money small,.mb-priority-item .mb-money small{display:inline;font-size:11px;font-weight:400}.mb-date,.mb-priority-item .mb-date{font-size:16px;color:#294e77;font-variant-numeric:tabular-nums}.mb-stage-number,.mb-priority-item .mb-stage-number{font-size:24px;color:#2175c4;font-variant-numeric:tabular-nums}.mb-priority-item .mb-idle-value{display:block;margin-top:14px;font-size:18px;color:#bc651e}.mb-detail-facts{justify-content:space-between;padding:20px}.mb-table :deep(.el-tag){font-weight:650}.monthly-battle .mb-command>header p{color:#d0e2f6}
.mb-command{background:#fff;border:1px solid #cbdcf1;border-radius:14px;margin:16px 0 20px;overflow:hidden}.mb-command>header{background:linear-gradient(115deg,#163455,#235887);color:white;padding:22px 24px;display:flex;justify-content:space-between;align-items:center}.mb-command>header h2{font-size:23px;margin:8px 0}.mb-command>header p{color:#c3d7ee;margin:6px 0;font-size:13px}.mb-command>header>span{border:1px solid #6c94bc;padding:7px 12px;border-radius:6px;font-size:12px}.mb-focus-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:18px 20px}.mb-focus-cards button{font:inherit;text-align:left;display:flex;flex-direction:column;gap:10px;padding:16px;border:1px solid #e0e8f2;border-top:4px solid #287dd1;border-radius:9px;background:#f6faff;cursor:pointer;color:#244363}.mb-focus-cards .overdue{border-top-color:#d95454;background:#fff7f6}.mb-focus-cards .unrecorded{border-top-color:#e1a240;background:#fffaf1}.mb-focus-cards .conflict{border-top-color:#8871c5;background:#faf8ff}.mb-focus-cards button.active{outline:2px solid #287dd1}.mb-focus-cards strong{font-size:34px;color:#205a94}.mb-focus-cards .overdue strong{color:#c44040}.mb-focus-cards small{font-size:11px;color:#768aa2;font-weight:400}.mb-focus-cards b{font-size:11px;color:#287ac3}.mb-priority-heading{display:flex;align-items:center;justify-content:space-between;padding:0 20px;gap:12px}.mb-priority-heading h3{font-size:16px}.mb-priority-heading span,.mb-priority-heading small{font-size:11px;color:#7c8da4}.mb-priority-list{padding:0 20px}.mb-priority-item{display:grid;grid-template-columns:32px minmax(0,2fr) minmax(0,1fr) minmax(0,1.6fr) 100px;align-items:center;gap:14px;width:100%;border:0;border-bottom:1px solid #e6edf5;padding:16px 0;background:white;text-align:left;font:inherit;color:#294866;cursor:pointer}.mb-priority-item:hover{background:#f4f9ff}.mb-priority-item small{display:block;font-size:11px;color:#7c8da4;margin-top:6px;line-height:1.6}.mb-priority-item strong{font-size:13px;line-height:1.6}.mb-priority-item em{font-size:12px;font-style:normal;color:#b56c21;background:#fff1dc;padding:4px 7px;border-radius:4px}.mb-priority-item span,.mb-priority-item>b{font-size:12px;color:#2677bb}.mb-command>.mb-note{padding:0 20px 12px}.mb-rank{background:#eaf2fb;padding:8px;border-radius:6px}@media(max-width:900px){.mb-focus-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.mb-priority-item{grid-template-columns:30px 1fr}.mb-priority-item>div{grid-column:2}.mb-priority-heading{flex-wrap:wrap}}
.mb-daily-entry{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:16px;background:#fff;border:1px solid #dae7f7;border-radius:12px;margin:16px 0}.mb-daily-entry small{display:block;color:#7a8fa8;font-size:12px;margin-top:5px}.mb-daily-entry>.el-select{flex:1;min-width:240px}@media(max-width:900px){.mb-daily-entry>.el-select{min-width:100%}}
.mb-progress-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0}.mb-progress-summary>div{padding:16px;background:#f0f6ff;border:1px solid #dce8f6;border-radius:10px;display:flex;flex-direction:column;gap:10px}.mb-progress-summary span,.mb-progress-summary small{font-size:12px;color:#71849b}.mb-progress-summary strong{font-size:18px;color:#215f9b}.mb-progress-summary .mb-idle-warning{background:#fff5e9;border-color:#f2d2a9}.mb-idle-warning strong{color:#b97522}.mb-timeline{padding:16px;border:1px solid #e0e9f4;border-radius:12px;margin-bottom:18px}.mb-timeline :deep(.el-timeline){padding-left:12px}.mb-action{padding:14px;background:#f7faff;border-radius:8px}.mb-action header{display:flex;justify-content:space-between;gap:10px}.mb-action h4{font-size:12px;color:#70859f;margin:14px 0 5px}.mb-action p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;margin:5px 0}@media(max-width:700px){.mb-progress-summary{grid-template-columns:1fr}}
.mb-original{margin:20px 0;padding:18px;border:1px solid #dce7f4;border-radius:12px;background:#fff}.mb-original h3{margin:0;font-size:16px}.mb-field-group h4,.mb-source-compare h4{font-size:13px;color:#245e96;margin:16px 0 0;padding:10px 12px;background:#edf4fc;border-radius:6px 6px 0 0}.mb-original dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));margin:0;border:1px solid #e5edf6}.mb-original dl>div{display:grid;grid-template-columns:minmax(100px,42%) minmax(0,1fr);border-bottom:1px solid #e5edf6;min-width:0}.mb-original dt,.mb-original dd{margin:0;padding:10px 12px;line-height:1.6;font-size:12px;overflow-wrap:anywhere;white-space:pre-wrap}.mb-original dt{background:#f8fafd;color:#71849b}.mb-original dd{color:#243f61;font-weight:500}.mb-source-compare{margin-top:16px;font-size:12px}.mb-source-compare summary{cursor:pointer;color:#2878c9}@media(max-width:700px){.mb-original dl{grid-template-columns:1fr}.mb-original .mb-panel-heading{flex-wrap:wrap}}
.monthly-battle{padding:18px;background:#f3f7fd;border-radius:16px;color:#243f61}.monthly-battle>header,.mb-event>header{display:flex;justify-content:space-between;gap:12px;align-items:center}.monthly-battle h2{margin:0}.monthly-battle header p,.mb-note{color:#71849b;font-size:12px}.mb-tools{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.mb-tools>.el-input,.mb-tools>.el-select{max-width:240px}.mb-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.mb-kpis>div{background:white;padding:15px;border-radius:12px;border:1px solid #dce8f6;display:flex;justify-content:space-between;align-items:center}.mb-kpis strong{font-size:28px;color:#2279cb}.mb-kpis .warning strong{color:#d66f20}.mb-board{display:flex;gap:12px;overflow-x:auto;padding:8px 0 18px;align-items:flex-start}.mb-column{flex:0 0 280px;background:#e9f0fa;border-radius:12px;padding:10px;max-height:70vh;overflow:auto}.mb-column h3{font-size:14px;display:flex;align-items:center;gap:8px;margin:6px 0 15px}.mb-column h3 b{color:#2878c9}.mb-column h3>span{margin-left:auto}.mb-card{width:100%;text-align:left;padding:14px;margin-bottom:10px;border:1px solid #d6e4f6;border-radius:10px;background:white;color:inherit;cursor:pointer;font-family:inherit}.mb-card:hover{border-color:#3c8fe2}.mb-card.overdue{border-left:4px solid #e79738}.mb-card.completed{border-left:4px solid #26ac8c}.mb-card h4{font-size:14px;line-height:1.5;margin:8px 0}.mb-card p,.mb-card>span,.mb-card small{font-size:12px;color:#6b7d94}.mb-card em{color:#bb7927}.mb-card footer{display:flex;flex-direction:column;gap:6px;font-size:11px}.mb-track{height:5px;background:#e5eef9;border-radius:5px;margin:12px 0}.mb-track i{height:100%;display:block;background:#2d95dd;border-radius:5px}.mb-empty{text-align:center;color:#8c9cb0;font-size:12px}.mb-duration{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mb-duration>div{display:flex;justify-content:space-between;gap:8px;background:#f2f7fd;padding:10px;border-radius:6px;font-size:12px}.mb-duration strong{white-space:nowrap;color:#267eca}.mb-form-row{display:flex;gap:20px}.mb-form-row>.el-form-item{flex:1}.mb-event{border-left:3px solid #87b6ed;background:#f7faff;padding:12px;margin:10px 0}.mb-event p{white-space:pre-wrap;overflow-wrap:anywhere}.mb-event header{font-size:12px;flex-wrap:wrap}.mb-images{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}@media(max-width:700px){.mb-kpis{grid-template-columns:repeat(2,1fr)}.mb-duration{grid-template-columns:1fr}.mb-form-row{flex-direction:column;gap:0}}
</style>
<style scoped>
.mb-kpis{margin-bottom:16px}.mb-kpis>div{gap:12px;justify-content:flex-start;flex-wrap:wrap}.mb-kpis .el-icon{font-size:24px;padding:12px;background:#eaf3ff;border-radius:12px;color:#277be0}.mb-kpis strong{display:block;margin-top:4px;font-size:30px}.mb-kpis small{font-size:11px;color:#8393a8;font-weight:400}.mb-kpis>div>small,.mb-kpis>div>.el-button{margin-left:auto}.mb-kpis .warning .el-icon{background:#fff2e6;color:#db861f}.mb-kpis .success .el-icon{background:#e4f6ef;color:#16a085}.mb-kpis .success strong{color:#16a085}.mb-overview{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(260px,1fr);gap:16px;margin-bottom:16px}.mb-panel{background:#fff;border:1px solid #e0e9f4;border-radius:12px;padding:18px;min-width:0}.mb-panel-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}.mb-panel h3{font-size:16px;margin:0}.mb-panel h3 small{font-size:12px;font-weight:400;color:#71849b;margin-left:10px}.mb-stages{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}.mb-stage{display:flex;flex-direction:column;gap:6px;background:#f7faff;border:1px solid #e5edf7;border-radius:8px;padding:10px;text-align:left;color:#46617f;cursor:pointer;font-family:inherit;min-width:0}.mb-stage>span:first-child{font-size:11px;color:#2981d8}.mb-stage strong{font-size:23px;color:#183e68}.mb-stage strong small{font-size:10px;font-weight:400}.mb-stage>span:last-of-type{font-size:11px;min-height:30px;line-height:15px}.mb-stage.active{background:#eaf3ff;border-color:#3287e5;box-shadow:0 0 0 1px #3287e5}.mb-stage i{height:4px;background:linear-gradient(to right,#3287e5 var(--share),#e3edf8 var(--share));border-radius:4px;width:100%}.mb-region-list{display:flex;flex-direction:column;gap:14px}.mb-region-list button{display:grid;grid-template-columns:100px 1fr 28px;align-items:center;gap:10px;background:none;border:0;cursor:pointer;font:inherit;font-size:12px;color:#46617f;text-align:left}.mb-region-list i{height:9px;background:#eff4fa;border-radius:5px;overflow:hidden}.mb-region-list b{display:block;height:100%;background:linear-gradient(90deg,#2f7de4,#31bec3);border-radius:5px}.mb-secondary{display:block;color:#8695aa;font-size:11px;margin-top:7px}.mb-project{border:0;background:none;padding:0;color:#234e7d;cursor:pointer;font:inherit;text-align:left;font-weight:600;line-height:1.5}.mb-project:hover{color:#1677dc}.mb-table{--el-table-header-bg-color:#f5f8fc;--el-table-row-hover-bg-color:#edf5ff;font-size:12px}.mb-table :deep(.el-table__row){cursor:pointer}.mb-table :deep(.el-table__cell){padding:13px 0}.mb-table :deep(.el-tag){max-width:100%;height:auto;white-space:normal;line-height:1.6}.mb-overdue{color:#d07821}.mb-pagination{display:flex;justify-content:space-between;align-items:center;margin-top:16px;font-size:12px;color:#8292a8}.mb-help{margin-top:16px;color:#8292a8;font-size:12px}.mb-help summary{cursor:pointer}.mb-help p{line-height:1.8}.mb-duration{margin:16px 0}.mb-duration>div{border:1px solid #e0eaf6}.mb-opportunities .mb-note{margin-bottom:0}@media(max-width:1000px){.mb-overview{grid-template-columns:1fr}.mb-kpis{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.mb-stages{grid-template-columns:repeat(3,minmax(0,1fr))}.mb-panel-heading,.mb-pagination{align-items:flex-start;flex-direction:column}.mb-panel{padding:12px}}
</style>
