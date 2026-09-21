<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Component } from 'vue'
import InternalOrganizationEntry from '../CrmAssistantView/InternalOrganizationEntry.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DOMPurify from 'dompurify'
import {
  Connection,
  CopyDocument,
  Delete,
  EditPen,
  Key,
  Link,
  MagicStick,
  Message,
  Plus,
  Refresh,
  Search,
  Setting,
  Tools,
  UserFilled,
} from '@element-plus/icons-vue'
import { authState } from '../../services/authSession'
import { sidebarMenuItems, type MenuId } from '../../layout/menu'
const permissionAssistants = sidebarMenuItems.filter(item => item.category)
import {
  addAdminUser,
  batchUpdateAdminUserPermissions,
  batchUpdateUsersForAssistant,
  deleteAdminUser,
  getMcpConfig,
  getAdminConfig,
  getAgentConfig,
  getAgentOrchestration,
  getMailConfig,
  listAdminModels,
  listAdminUsers,
  listMyLobsters,
  listLobsterModelOptions,
  listSkills,
  mcpEndpointUrl,
  resourceUrl,
  runSkillTest,
  saveAdminConfig,
  saveAgentConfig,
  saveMailConfig,
  saveMcpConfig,
  saveServerConfig,
  testAdminModel,
  testMailConfig,
  updateAdminUser,
  updateLobsterModel,
  installMcpToLobster,
  restartLobster,
  getAssistantLobster,
  saveAssistantLobster,
  getTtsConfig,
  saveTtsConfig,
  previewTts,
  probeTtsVoices,
  getMeetingConfig,
  saveMeetingConfig,
  testMeetingAsr,
  getKnowledgeConfig,
  saveKnowledgeConfig,
  testKnowledgeEmbedding,
  getRagflowStatus,
  bootstrapRagflow,
  saveRagflowChunkConfig,
  getXinferenceConfig,
  probeXinference,
  applyXinference,
  type RagflowStatus,
  type TtsVoiceOption,
  type AdminConfig,
  type AgentConfig,
  type LobsterAgent,
  type MailConfig,
  type McpConfigResponse,
  type SkillDefinition,
  type User,
  importOrganizationExcel,
  type OrganizationExcelResult,
} from '../../services/personalWorkApi'
import './index.scss'

type SettingsTab = 'mailconfig' | 'config' | 'skills' | 'usermanage' | 'mcp'
type MailTab = 'company' | 'personal'

const props = defineProps<{
  activeMenu: MenuId
}>()

const emit = defineEmits<{
  selectMenu: [value: MenuId]
}>()

const user = computed(() => authState.user)
const activeTab = ref<SettingsTab>('mailconfig')
const activeMailTab = ref<MailTab>('company')
const loadedTabs = reactive<Record<SettingsTab, boolean>>({
  mailconfig: false,
  config: false,
  skills: false,
  usermanage: false,
  mcp: false,
})
const loading = reactive({
  mailConfig: false,
  saveMail: false,
  testMail: false,
  savePersonalMail: false,
  testPersonalMail: false,
  adminConfig: false,
  saveAdmin: false,
  models: false,
  testModel: false,
  saveServer: false,
  ttsConfig: false,
  saveTts: false,
  previewTts: false,
  meetingConfig: false,
  saveMeeting: false,
  testMeeting: false,
  ttsVoiceProbe: false,
  kbConfig: false,
  saveKb: false,
  testKb: false,
  ragflowStatus: false,
  ragflowBootstrap: false,
  ragflowChunk: false,
  xfProbe: false,
  xfApply: false,
  skills: false,
  orchestration: false,
  agentConfig: false,
  saveAgentConfig: false,
  skillTest: false,
  users: false,
  addUser: false,
  batchPermissions: false,
  organizationImport: false,
  mcpConfig: false,
  mcpSecret: false,
  lobsters: false,
  mcpInstall: false,
})

const mailForm = reactive({
  user_email: '',
  smtp_from: '',
  smtp_user: '',
  smtp_password: '',
  imap_user: '',
  imap_password: '',
  weekly_to: '',
  weekly_cc: '',
  trip_to: '',
  trip_cc: '',
  email_signature: '',
})
const personalMailForm = reactive({
  personal_email: '',
  personal_smtp_host: '',
  personal_smtp_port: 587,
  personal_smtp_user: '',
  personal_smtp_password: '',
  personal_smtp_ssl: false,
  personal_smtp_tls: true,
  personal_imap_host: '',
  personal_imap_port: 993,
  personal_imap_user: '',
  personal_imap_password: '',
  personal_imap_ssl: true,
})
const mailMeta = reactive({
  smtp_password_masked: '',
  imap_password_masked: '',
  smtp_host: '',
  smtp_port: 465,
  smtp_ssl: true,
  imap_host: '',
  imap_port: 993,
  imap_ssl: true,
  personal_smtp_password_masked: '',
  personal_imap_password_masked: '',
})
const mailReference = ref<Partial<MailConfig>>({})
const signatureEditorRef = ref<HTMLElement | null>(null)
const signatureEditorHtml = ref('')
let signatureRange: Range | null = null

function signatureHtml(value: string) {
  const source = /<[^>]+>/.test(value)
    ? value
    : value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  return DOMPurify.sanitize(source, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target'],
  })
}

const adminForm = reactive({
  assistant_api_url: '',
  assistant_api_key: '',
  assistant_model: '',
  assistant_reasoning_effort: 'off',
  assistant_prompt: '',
})
const serverForm = reactive({
  smtp_host: '',
  smtp_port: 465,
  smtp_tls: false,
  smtp_ssl: true,
  imap_host: '',
  imap_port: 993,
  imap_ssl: true,
})
const apiKeyStatus = ref('')
const modelOptions = ref<string[]>([])

const xfForm = reactive({ api_url: '', asr_model: '', tts_model: '', embedding_model: '' })
const xfModels = reactive({ embedding: [] as string[], asr: [] as string[], tts: [] as string[] })
const xfCurrent = ref({ meeting: '', tts: '', kb: '' })

const ttsForm = reactive({
  provider: 'edge' as 'edge' | 'api',
  voice: 'zh-CN-XiaoyiNeural',
  rate: '+0%',
  pitch: '+0Hz',
  api_url: '',
  api_key: '',
  api_model: 'tts-1',
  api_voice: 'alloy',
})
const ttsApiKeyStatus = ref('未配置')
const ttsVoices = ref<TtsVoiceOption[]>([])
// API 模式音色候选：默认常见值，可点"获取音色列表"从服务实测拉取。
const ttsApiVoices = ref<string[]>(['中文女', '中文男', '粤语女', '日语男', '英文女', '英文男', '韩语女', 'alloy', 'nova'])

const meetingForm = reactive({
  api_url: '',
  api_key: '',
  model: 'whisper-1',
})
const meetingApiKeyStatus = ref('未配置')

const kbForm = reactive({
  provider: 'builtin' as 'builtin' | 'ragflow',
  api_url: '',
  api_key: '',
  model: 'bge-m3',
  vector_store: 'local' as 'local' | 'qdrant',
  qdrant_url: 'http://qdrant:6333',
  rerank_model: '',
  ragflow_url: '',
  ragflow_api_key: '',
})
const kbRagflowKeyStatus = ref('未配置')
const kbApiKeyStatus = ref('未配置')
const ragflowStatus = ref<RagflowStatus | null>(null)
const ragflowChunkForm = reactive({ chunk_method: 'naive', chunk_token_num: 512, layout_recognize: 'DeepDOC' })
const ttsRateOptions = [
  { value: '-20%', label: '慢' },
  { value: '+0%', label: '正常' },
  { value: '+15%', label: '稍快' },
  { value: '+30%', label: '快' },
]
const ttsPitchOptions = [
  { value: '-20Hz', label: '低沉' },
  { value: '+0Hz', label: '正常' },
  { value: '+20Hz', label: '明亮' },
]

const skills = ref<SkillDefinition[]>([])
const skillSearch = ref('')
const skillModule = ref('all')
const orchestrationOpen = ref(false)
const orchestration = ref<{
  agents: Record<string, string>
  workflows: Record<string, string>
  skills: SkillDefinition[]
  skill_mode_suffix: string
} | null>(null)
const installMcpDialog = ref(false)
const pendingInstallAgent = ref<LobsterAgent | null>(null)
const mcpRestartLoading = ref(false)
const agentConfigDialog = ref(false)
const agentConfigTab = ref<'prompts' | 'workflows'>('prompts')
const agentPromptDraft = reactive<Record<string, string>>({})
const agentWorkflowDraft = reactive<Record<string, string>>({})
const skillTestDialog = ref(false)
const currentSkill = ref<SkillDefinition | null>(null)
const skillTestArgs = ref('{}')
const skillTestInstruction = ref('')
const skillConfirmUnsafe = ref(false)
const skillTestResult = ref('点击“运行测试”后，这里会显示 Skill 返回结果。')
const addUserDialog = ref(false)
const organizationExcelDialog = ref(false)
const organizationExcelPicker = ref<HTMLInputElement | null>(null)
const organizationExcelResult = ref<OrganizationExcelResult | null>(null)
const organizationCreateUsers = ref(true)

const users = ref<User[]>([])
const userSearch = ref('')
const organizationStatusFilter = ref<'all' | 'missing'>('all')
const expandedUsername = ref<string | null>(null)
const missingOrganizationUsers = computed(() => users.value.filter(item => item.organization_check?.status === 'missing'))
const filteredUsers = computed(() => {
  const query = userSearch.value.trim().toLocaleLowerCase()
  return users.value.filter(item => {
    if (organizationStatusFilter.value === 'missing' && item.organization_check?.status !== 'missing') return false
    return !query || [item.username, item.name, item.employee_id, item.company, item.department, item.position, roleLabel(item.role)]
      .some(value => (value || '').toLocaleLowerCase().includes(query))
  })
})
const organizationUsers = computed(() => {
  const companies = new Map<string, Map<string, User[]>>()
  for (const item of filteredUsers.value) {
    const company = item.company?.trim() || '未归属组织'
    const department = item.department?.trim() || '未登记部门'
    if (!companies.has(company)) companies.set(company, new Map())
    const departments = companies.get(company)!
    if (!departments.has(department)) departments.set(department, [])
    departments.get(department)!.push(item)
  }
  const byCompany = ([left]: [string, Map<string, User[]>], [right]: [string, Map<string, User[]>]) => {
    if (left === '未归属组织') return 1
    if (right === '未归属组织') return -1
    return left.localeCompare(right, 'zh-Hans-CN')
  }
  return [...companies.entries()].sort(byCompany).map(([company, departments]) => ({
    company,
    departments: [...departments.entries()]
      .sort(([left], [right]) => left.localeCompare(right, 'zh-Hans-CN'))
      .map(([department, members]) => ({
        department,
        members: [...members].sort((left, right) => (left.employee_id || left.username).localeCompare(right.employee_id || right.username)),
      })),
  }))
})
const organizationCompanies = computed(() => [...new Set(users.value.map(item => item.company?.trim()).filter(Boolean))].sort((left, right) => left!.localeCompare(right!, 'zh-Hans-CN')) as string[])
const newUserDepartments = computed(() => [...new Set(users.value
  .filter(item => item.company?.trim() === newUser.company.trim())
  .map(item => item.department?.trim())
  .filter(Boolean))].sort((left, right) => left!.localeCompare(right!, 'zh-Hans-CN')) as string[])
const batchCompany = ref('')
const batchDepartments = ref<string[]>([])
const batchAssistantIds = ref<string[]>([])
const batchEnabled = ref(true)
const batchDepartmentsOptions = computed(() => [...new Set(users.value
  .filter(item => item.company?.trim() === batchCompany.value.trim())
  .map(item => item.department?.trim())
  .filter(Boolean))].sort((left, right) => left!.localeCompare(right!, 'zh-Hans-CN')) as string[])
const batchTargetCount = computed(() => users.value.filter(item =>
  item.role !== 'superadmin' && item.company?.trim() === batchCompany.value.trim() &&
  (!batchDepartments.value.length || batchDepartments.value.includes(item.department?.trim() || '')),
).length)
const batchPermissionAssistants = computed(() => permissionAssistants)
const assistantUserFilter = ref('')
const assistantUserSelection = ref<string[]>([])
const assistantUserEnabled = ref(false)
const selectedAssistant = computed(() => batchPermissionAssistants.value.find(item => item.id === assistantUserFilter.value))
const usersWithSelectedAssistant = computed(() => users.value.filter(item => item.role !== 'superadmin' && item.assistant_permissions?.[assistantUserFilter.value]))
const assistantUserCandidates = computed(() => users.value.filter(item => item.role !== 'superadmin'))
const companyEmailFor = (username: string) => username.includes('@') ? username : `${username}@chencytech.com`
const userDrafts = reactive<Record<string, { name: string; password: string; email: string; role: User['role']; assistant_permissions: Record<string, boolean> }>>({})
const newUser = reactive<{ username: string; name: string; password: string; email: string; role: User['role']; employee_id: string; company: string; department: string; position: string }>({
  username: '',
  name: '',
  password: '',
  email: '',
  role: 'member',
  employee_id: '',
  company: '',
  department: '',
  position: '',
})
const mcpConfig = ref<McpConfigResponse | null>(null)
const mcpNewSecret = ref('')
const mcpStatus = ref('')
const lobsters = ref<LobsterAgent[]>([])
const lobsterStatus = ref('')
const lobsterModelOptions = ref<Record<number, Array<{ id: string; owned_by?: string }>>>({})
const lobsterModelDrafts = ref<Record<number, string>>({})
const loadingLobsterModels = ref<number | null>(null)
const savingLobsterModel = ref<number | null>(null)
const installingLobsterId = ref<number | null>(null)
// 悬浮助手绑定龙虾
const boundLobsterId = ref<number | null>(null)
const selectedBindId = ref<number | null>(null)
const bindStatus = ref('')
const savingBind = ref(false)

const agentLabels = [
  { key: 'weekly', label: '周报助手' },
  { key: 'trip', label: '出差报告助手' },
  { key: 'diary', label: '日记助手' },
  { key: 'mailassistant', label: '邮件助手' },
  { key: 'news', label: '资讯助手' },
  { key: 'forum', label: '论坛助手' },
  { key: 'dashboard', label: '总助手' },
]
const mcpModules = ['周报', '出差报告', '工作日记', '邮件', '金点子论坛', '资讯', '智能写作', '会议', '知识库', '报销', '报告', '通用', '记忆', '工作流']

const tabItems = computed(() => {
  const items: Array<{ id: SettingsTab; label: string; icon: Component; visible: boolean }> = [
    { id: 'mailconfig', label: '邮件配置', icon: Message, visible: true },
    { id: 'config', label: '系统配置', icon: Setting, visible: !!user.value?.is_admin },
    { id: 'skills', label: '系统 Skill', icon: Tools, visible: !!user.value?.is_superadmin },
    { id: 'usermanage', label: '用户管理', icon: UserFilled, visible: !!user.value?.is_superadmin },
    { id: 'mcp', label: 'MCP 服务', icon: Connection, visible: !!user.value?.is_admin },
  ]
  return items.filter((item) => item.visible)
})
const mcpEnabled = computed(() => !!mcpConfig.value?.enabled)
const mcpEndpoint = computed(() => mcpEndpointUrl())
const mcpUsername = computed(() => user.value?.username || '<username>')
// 管理员只能查看 MCP 状态，密钥启停由超级管理员控制。
const mcpSecretDescription = computed(() => {
  if (mcpEnabled.value) return '密钥已配置，MCP 端点正在响应请求。生成新密钥后旧密钥立即失效。'
  return user.value?.is_superadmin
    ? '未配置密钥，MCP 端点处于禁用状态。点击“生成新密钥”激活服务。'
    : '未配置密钥，MCP 端点处于禁用状态。请联系超级管理员生成密钥。'
})
const mcpClaudeConfig = computed(() =>
  JSON.stringify(
    {
      mcpServers: {
        'personal-office-assistant': {
          type: 'http',
          url: mcpEndpoint.value,
          headers: {
            Authorization: 'Bearer <mcp_secret>',
            'X-MCP-Username': mcpUsername.value,
          },
        },
      },
    },
    null,
    2,
  ),
)
const mcpCodexConfig = computed(
  () =>
    `# ~/.codex/config.toml（保留文件中的其他配置）\n` +
    `[mcp_servers.personal_office_assistant]\n` +
    `url = "${mcpEndpoint.value}"\n` +
    `http_headers = { "Authorization" = "Bearer <mcp_secret>", "X-MCP-Username" = "${mcpUsername.value}" }\n` +
    `startup_timeout_sec = 20\n` +
    `tool_timeout_sec = 120`,
)
const mcpCodexVerify = computed(
  () =>
    `# 保存 ~/.codex/config.toml 后，重新启动 Codex\n` +
    `codex mcp list\n` +
    `codex mcp get personal_office_assistant`,
)
const mcpGenericConfig = computed(() =>
  JSON.stringify(
    {
      name: '承希智能办公平台',
      type: 'streamable-http',
      url: mcpEndpoint.value,
      headers: {
        Authorization: 'Bearer <mcp_secret>',
        'X-MCP-Username': mcpUsername.value,
      },
    },
    null,
    2,
  ),
)
const mcpCurlExample = computed(
  () =>
    `curl -X POST ${mcpEndpoint.value} \\\n` +
    `  -H "Content-Type: application/json" \\\n` +
    `  -H "Authorization: Bearer <mcp_secret>" \\\n` +
    `  -H "X-MCP-Username: ${mcpUsername.value}" \\\n` +
    `  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'`,
)
const skillModules = computed(() => ['all', ...Array.from(new Set(skills.value.map((skill) => skill.module).filter(Boolean)))])
const filteredSkills = computed(() => {
  const keyword = skillSearch.value.trim().toLowerCase()
  return skills.value.filter((skill) => {
    const matchModule = skillModule.value === 'all' || skill.module === skillModule.value
    const text = `${skill.name} ${skill.module} ${skill.title} ${skill.description}`.toLowerCase()
    return matchModule && (!keyword || text.includes(keyword))
  })
})

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

function roleLabel(role: User['role']) {
  return role === 'superadmin' ? '超级管理员' : role === 'admin' ? '管理员' : '普通成员'
}

function canOpenTab(tab: SettingsTab) {
  if (tab === 'mailconfig') return true
  if (tab === 'config') return !!user.value?.is_admin
  if (tab === 'mcp') return !!user.value?.is_admin
  return !!user.value?.is_superadmin
}

function tabPermissionText(tab: SettingsTab) {
  if (tab === 'config') return '系统配置仅管理员可访问。'
  if (tab === 'skills') return '系统 Skill 仅超级管理员可访问。'
  if (tab === 'usermanage') return '用户管理仅超级管理员可访问。'
  if (tab === 'mcp') return 'MCP 服务仅管理员可访问。'
  return '当前账号无法访问该模块。'
}

function tabFromMenu(menu: MenuId): SettingsTab {
  if (menu === 'mailconfig') return 'mailconfig'
  if (menu === 'skills') return 'skills'
  if (menu === 'usermanage') return 'usermanage'
  if (menu === 'mcp') return 'mcp'
  return user.value?.is_admin ? 'config' : 'mailconfig'
}

function selectTab(tab: SettingsTab) {
  if (!canOpenTab(tab)) return
  activeTab.value = tab
  emit('selectMenu', tab)
}

function applyMailConfig(data: MailConfig) {
  mailForm.user_email = data.user_email || ''
  mailForm.smtp_from = data.smtp_from || ''
  mailForm.smtp_user = data.smtp_user || ''
  mailForm.smtp_password = ''
  mailForm.imap_user = data.imap_user || ''
  mailForm.imap_password = ''
  mailForm.weekly_to = data.weekly_to || ''
  mailForm.weekly_cc = data.weekly_cc || ''
  mailForm.trip_to = data.trip_to || ''
  mailForm.trip_cc = data.trip_cc || ''
  mailForm.email_signature = data.email_signature || ''
  signatureEditorHtml.value = signatureHtml(mailForm.email_signature)
  mailMeta.smtp_password_masked = data.smtp_password_masked || '未配置'
  mailMeta.imap_password_masked = data.imap_password_masked || '未配置'
  mailMeta.smtp_host = data.smtp_host || ''
  mailMeta.smtp_port = data.smtp_port || 465
  mailMeta.smtp_ssl = !!data.smtp_ssl
  mailMeta.imap_host = data.imap_host || ''
  mailMeta.imap_port = data.imap_port || 993
  mailMeta.imap_ssl = !!data.imap_ssl
  personalMailForm.personal_email = data.personal_email || ''
  personalMailForm.personal_smtp_host = data.personal_smtp_host || ''
  personalMailForm.personal_smtp_port = data.personal_smtp_port || 587
  personalMailForm.personal_smtp_user = data.personal_smtp_user || ''
  personalMailForm.personal_smtp_password = ''
  personalMailForm.personal_smtp_ssl = !!data.personal_smtp_ssl
  personalMailForm.personal_smtp_tls = data.personal_smtp_tls !== false
  personalMailForm.personal_imap_host = data.personal_imap_host || ''
  personalMailForm.personal_imap_port = data.personal_imap_port || 993
  personalMailForm.personal_imap_user = data.personal_imap_user || ''
  personalMailForm.personal_imap_password = ''
  personalMailForm.personal_imap_ssl = data.personal_imap_ssl !== false
  mailMeta.personal_smtp_password_masked = data.personal_smtp_password_masked || '未配置'
  mailMeta.personal_imap_password_masked = data.personal_imap_password_masked || '未配置'
  mailReference.value = data.reference || {}
}

async function loadMailConfig() {
  loading.mailConfig = true
  try {
    applyMailConfig(await getMailConfig())
    loadedTabs.mailconfig = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.mailConfig = false
  }
}

function mailConfigPayload() {
  const userEmail = mailForm.user_email.trim()
  const smtpUser = mailForm.smtp_user.trim() || userEmail
  return {
    user_email: userEmail,
    smtp_from: mailForm.smtp_from.trim() || userEmail,
    smtp_user: smtpUser,
    smtp_password: mailForm.smtp_password,
    imap_user: mailForm.imap_user.trim() || smtpUser,
    imap_password: mailForm.imap_password,
    weekly_to: mailForm.weekly_to,
    weekly_cc: mailForm.weekly_cc,
    trip_to: mailForm.trip_to,
    trip_cc: mailForm.trip_cc,
    email_signature: signatureHtml(mailForm.email_signature),
  }
}

function syncSignatureEditor() {
  const editor = signatureEditorRef.value
  if (!editor) return
  // 输入期间不能回写 innerHTML：浏览器会销毁当前 Range，导致插入光标在
  // 每次输入后消失。内容仍会先清洗后保存，编辑时只同步表单状态。
  const cleaned = signatureHtml(editor.innerHTML || '')
  mailForm.email_signature = cleaned
}

function rememberSignatureSelection() {
  const editor = signatureEditorRef.value
  const selection = window.getSelection()
  if (!editor || !selection?.rangeCount) return
  const range = selection.getRangeAt(0)
  if (editor.contains(range.commonAncestorContainer)) signatureRange = range.cloneRange()
}

function focusSignatureEditor() {
  const editor = signatureEditorRef.value
  if (!editor) return
  editor.focus()
  if (!signatureRange) return
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(signatureRange)
}

function selectAllSignature() {
  const editor = signatureEditorRef.value
  if (!editor) return
  editor.focus({ preventScroll: true })
  const range = document.createRange()
  range.selectNodeContents(editor)
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  signatureRange = range.cloneRange()
}

function handleSignatureEditorKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
    event.preventDefault()
    selectAllSignature()
  }
}

function formatSignature(command: string, value?: string) {
  focusSignatureEditor()
  document.execCommand(command, false, value)
  rememberSignatureSelection()
  syncSignatureEditor()
}

function addSignatureLink() {
  const url = window.prompt('请输入链接地址')?.trim()
  if (!url) return
  formatSignature('createLink', url)
}

function addSignatureImage() {
  const url = window.prompt('请输入图片地址')?.trim()
  if (!url) return
  formatSignature('insertImage', url)
}

function insertSignatureTable() {
  formatSignature('insertHTML', '<table style="border-collapse:collapse;width:100%;margin:8px 0"><tbody><tr><td style="border:1px solid #cbd5e1;padding:8px">内容</td><td style="border:1px solid #cbd5e1;padding:8px">内容</td></tr><tr><td style="border:1px solid #cbd5e1;padding:8px">内容</td><td style="border:1px solid #cbd5e1;padding:8px">内容</td></tr></tbody></table><p><br></p>')
}

function signatureSelect(event: Event, command: string) {
  const value = (event.target as HTMLSelectElement).value
  if (!value) return
  formatSignature(command, value)
  ;(event.target as HTMLSelectElement).value = ''
}

function personalMailConfigPayload() {
  const email = personalMailForm.personal_email.trim()
  const smtpUser = personalMailForm.personal_smtp_user.trim() || email
  return {
    personal_email: email,
    personal_smtp_host: personalMailForm.personal_smtp_host.trim(),
    personal_smtp_port: personalMailForm.personal_smtp_port,
    personal_smtp_user: smtpUser,
    personal_smtp_password: personalMailForm.personal_smtp_password,
    personal_smtp_ssl: personalMailForm.personal_smtp_ssl,
    personal_smtp_tls: personalMailForm.personal_smtp_tls,
    personal_imap_host: personalMailForm.personal_imap_host.trim(),
    personal_imap_port: personalMailForm.personal_imap_port,
    personal_imap_user: personalMailForm.personal_imap_user.trim() || smtpUser,
    personal_imap_password: personalMailForm.personal_imap_password,
    personal_imap_ssl: personalMailForm.personal_imap_ssl,
  }
}

async function handleSaveMailConfig() {
  loading.saveMail = true
  try {
    const result = await saveMailConfig(mailConfigPayload())
    applyMailConfig(result.mail_config)
    ElMessage.success('邮件配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveMail = false
  }
}

async function handleTestMailConfig() {
  loading.testMail = true
  try {
    await saveMailConfig(mailConfigPayload())
    const result = await testMailConfig('company')
    await loadMailConfig()
    ElMessage.success(result.message || '邮箱配置测试成功')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testMail = false
  }
}

async function handleSavePersonalMailConfig() {
  loading.savePersonalMail = true
  try {
    const result = await saveMailConfig(personalMailConfigPayload())
    applyMailConfig(result.mail_config)
    ElMessage.success('个人邮箱配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.savePersonalMail = false
  }
}

async function handleTestPersonalMailConfig() {
  loading.testPersonalMail = true
  try {
    await saveMailConfig(personalMailConfigPayload())
    const result = await testMailConfig('personal')
    await loadMailConfig()
    ElMessage.success(result.message || '个人邮箱配置测试成功')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testPersonalMail = false
  }
}

function applyAdminConfig(data: AdminConfig) {
  adminForm.assistant_api_url = data.assistant_api_url || ''
  adminForm.assistant_api_key = ''
  adminForm.assistant_model = data.assistant_model || 'MiniMax-M2.7'
  adminForm.assistant_reasoning_effort = data.assistant_reasoning_effort || 'off'
  adminForm.assistant_prompt = data.assistant_prompt || ''
  apiKeyStatus.value = data.assistant_api_key_masked || '未配置'
  modelOptions.value = [adminForm.assistant_model]
  serverForm.smtp_host = data.smtp_host || 'smtp.263.net'
  serverForm.smtp_port = data.smtp_port || 465
  serverForm.smtp_tls = !!data.smtp_tls
  serverForm.smtp_ssl = !!data.smtp_ssl
  serverForm.imap_host = data.imap_host || 'imap.263.net'
  serverForm.imap_port = data.imap_port || 993
  serverForm.imap_ssl = !!data.imap_ssl
}

async function loadAdminConfig() {
  if (!user.value?.is_admin) return
  loading.adminConfig = true
  try {
    applyAdminConfig(await getAdminConfig())
    loadedTabs.config = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.adminConfig = false
  }
  void loadTtsConfig()
  void loadMeetingConfig()
  void loadKbConfig()
  void loadRagflowStatus()
  void loadXinferenceConfig()
}

async function loadXinferenceConfig() {
  if (!user.value?.is_admin) return
  try {
    const config = await getXinferenceConfig()
    xfForm.api_url = config.api_url
    xfForm.asr_model = config.asr_model
    xfForm.tts_model = config.tts_model
    xfForm.embedding_model = config.embedding_model
    xfCurrent.value = {
      meeting: config.current.meeting.model ? `${config.current.meeting.model}（${config.current.meeting.api_url || '复用大模型地址'}）` : '',
      tts: config.current.tts.provider === 'api' ? `${config.current.tts.model}（${config.current.tts.api_url}）` : 'Edge-TTS 内置引擎',
      kb: config.current.kb.model ? `${config.current.kb.model}（${config.current.kb.provider === 'ragflow' ? 'RAGFlow 引擎' : '内置引擎'}）` : '',
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleProbeXinference() {
  loading.xfProbe = true
  try {
    const result = await probeXinference(xfForm.api_url)
    xfModels.embedding = result.embedding
    xfModels.asr = result.asr
    xfModels.tts = result.tts
    // 各类只发现一个模型时自动填充，省得手选。
    if (!xfForm.asr_model && result.asr.length === 1) xfForm.asr_model = result.asr[0]
    if (!xfForm.tts_model && result.tts.length === 1) xfForm.tts_model = result.tts[0]
    if (!xfForm.embedding_model && result.embedding.length === 1) xfForm.embedding_model = result.embedding[0]
    ElMessage.success(`发现模型：识别 ${result.asr.length} 个、合成 ${result.tts.length} 个、嵌入 ${result.embedding.length} 个`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.xfProbe = false
  }
}

async function handleApplyXinference() {
  loading.xfApply = true
  try {
    const result = await applyXinference({ ...xfForm })
    ElMessage.success(result.steps.join('；') || '没有需要应用的模型')
    if (result.warning) ElMessage({ type: 'warning', message: result.warning, duration: 12000, showClose: true })
    await Promise.all([loadTtsConfig(), loadMeetingConfig(), loadKbConfig(), loadXinferenceConfig()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.xfApply = false
  }
}

function applyKbConfig(config: Awaited<ReturnType<typeof getKnowledgeConfig>>) {
  kbForm.provider = config.provider || 'builtin'
  kbForm.api_url = config.api_url || ''
  kbForm.api_key = ''
  kbForm.model = config.model || 'bge-m3'
  kbForm.vector_store = config.vector_store || 'local'
  kbForm.qdrant_url = config.qdrant_url || 'http://qdrant:6333'
  kbForm.rerank_model = config.rerank_model || ''
  kbForm.ragflow_url = config.ragflow_url || ''
  kbForm.ragflow_api_key = ''
  kbApiKeyStatus.value = config.api_key_masked || '未配置'
  kbRagflowKeyStatus.value = config.ragflow_api_key_masked || '未配置'
}

async function loadKbConfig() {
  if (!user.value?.is_admin) return
  loading.kbConfig = true
  try {
    const config = await getKnowledgeConfig()
    applyKbConfig(config)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.kbConfig = false
  }
}

async function handleSaveKbConfig() {
  loading.saveKb = true
  try {
    const config = await saveKnowledgeConfig({ ...kbForm })
    applyKbConfig(config)
    ElMessage.success('知识库嵌入模型配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveKb = false
  }
}

async function handleClearKbKey() {
  loading.saveKb = true
  try {
    const config = await saveKnowledgeConfig({ ...kbForm, api_key: '', api_key_clear: true })
    kbForm.api_key = ''
    kbApiKeyStatus.value = config.api_key_masked || '未配置'
    ElMessage.success('已清除嵌入 API Key（无鉴权模式）')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveKb = false
  }
}

async function loadRagflowStatus() {
  loading.ragflowStatus = true
  try {
    const status = await getRagflowStatus()
    ragflowStatus.value = status
    ragflowChunkForm.chunk_method = status.chunk_method || 'naive'
    ragflowChunkForm.chunk_token_num = status.chunk_token_num || 512
    ragflowChunkForm.layout_recognize = status.layout_recognize || 'DeepDOC'
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.ragflowStatus = false
  }
}

async function handleRagflowBootstrap() {
  loading.ragflowBootstrap = true
  try {
    const result = await bootstrapRagflow()
    ElMessage.success(result.steps.join('；'))
    await Promise.all([loadKbConfig(), loadRagflowStatus()])
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.ragflowBootstrap = false
  }
}

async function handleSaveRagflowChunk() {
  loading.ragflowChunk = true
  try {
    const result = await saveRagflowChunkConfig({ ...ragflowChunkForm })
    ElMessage.success(`解析配置已应用到 ${result.updated.length} 个知识库。${result.hint || ''}`)
    if (result.warning) ElMessage.warning(result.warning)
    void loadRagflowStatus()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.ragflowChunk = false
  }
}

async function handleTestKbEmbedding() {
  loading.testKb = true
  try {
    const result = await testKnowledgeEmbedding({ ...kbForm })
    if (kbForm.provider === 'ragflow') {
      ElMessage.success(`RAGFlow ${result.ragflow || '连接正常'}`)
    } else {
      const extras = [result.qdrant ? `Qdrant ${result.qdrant}` : '', result.rerank ? `重排 ${result.rerank}` : ''].filter(Boolean).join('；')
      ElMessage.success(`嵌入连接成功：${result.model}（${result.dimensions} 维）${extras ? '；' + extras : ''}`)
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testKb = false
  }
}

async function loadMeetingConfig() {
  if (!user.value?.is_admin) return
  loading.meetingConfig = true
  try {
    const config = await getMeetingConfig()
    meetingForm.api_url = config.api_url || ''
    meetingForm.api_key = ''
    meetingForm.model = config.model || 'whisper-1'
    meetingApiKeyStatus.value = config.api_key_masked || '未配置'
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.meetingConfig = false
  }
}

async function handleClearMeetingKey() {
  loading.saveMeeting = true
  try {
    const config = await saveMeetingConfig({ api_url: meetingForm.api_url, api_key: '', model: meetingForm.model, api_key_clear: true })
    meetingForm.api_key = ''
    meetingApiKeyStatus.value = config.api_key_masked || '未配置'
    ElMessage.success('已清除识别 API Key（无鉴权模式）')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveMeeting = false
  }
}

async function handleTestMeetingAsr() {
  loading.testMeeting = true
  try {
    const result = await testMeetingAsr({ api_url: meetingForm.api_url, api_key: meetingForm.api_key, model: meetingForm.model })
    ElMessage.success(`识别成功（${result.model}）：${result.text || '（空文本）'}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testMeeting = false
  }
}

async function handleSaveMeetingConfig() {
  loading.saveMeeting = true
  try {
    const config = await saveMeetingConfig({ api_url: meetingForm.api_url, api_key: meetingForm.api_key, model: meetingForm.model })
    meetingForm.api_url = config.api_url || ''
    meetingForm.api_key = ''
    meetingForm.model = config.model || 'whisper-1'
    meetingApiKeyStatus.value = config.api_key_masked || '未配置'
    ElMessage.success('会议语音识别配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveMeeting = false
  }
}

function applyTtsConfig(config: Awaited<ReturnType<typeof getTtsConfig>>) {
  ttsVoices.value = config.voices || []
  ttsForm.provider = config.provider || 'edge'
  ttsForm.voice = config.voice || 'zh-CN-XiaoyiNeural'
  ttsForm.rate = config.rate || '+0%'
  ttsForm.pitch = config.pitch || '+0Hz'
  ttsForm.api_url = config.api_url || ''
  ttsForm.api_key = ''
  ttsForm.api_model = config.api_model || 'tts-1'
  ttsForm.api_voice = config.api_voice || 'alloy'
  ttsApiKeyStatus.value = config.api_key_masked || '未配置'
}

function ttsConfigPayload() {
  return {
    provider: ttsForm.provider,
    voice: ttsForm.voice,
    rate: ttsForm.rate,
    pitch: ttsForm.pitch,
    api_url: ttsForm.api_url,
    api_key: ttsForm.api_key,
    api_model: ttsForm.api_model,
    api_voice: ttsForm.api_voice,
  }
}

async function loadTtsConfig() {
  if (!user.value?.is_admin) return
  loading.ttsConfig = true
  try {
    applyTtsConfig(await getTtsConfig())
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.ttsConfig = false
  }
}

async function handleSaveTtsConfig() {
  loading.saveTts = true
  try {
    applyTtsConfig(await saveTtsConfig(ttsConfigPayload()))
    ElMessage.success('数字人语音配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveTts = false
  }
}

async function handleClearTtsKey() {
  loading.saveTts = true
  try {
    applyTtsConfig(await saveTtsConfig({ ...ttsConfigPayload(), api_key: '', api_key_clear: true }))
    ElMessage.success('已清除语音 API Key（无鉴权模式）')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveTts = false
  }
}

async function handleProbeTtsVoices() {
  loading.ttsVoiceProbe = true
  try {
    const result = await probeTtsVoices({ api_url: ttsForm.api_url, api_key: ttsForm.api_key, api_model: ttsForm.api_model })
    ttsApiVoices.value = result.voices
    if (result.voices.length && !result.voices.includes(ttsForm.api_voice)) {
      ttsForm.api_voice = result.voices[0]
    }
    if (result.source === 'service') ElMessage.success(`已从语音服务获取 ${result.voices.length} 个音色`)
    else ElMessage.warning('服务未返回音色清单，已展示常见候选')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.ttsVoiceProbe = false
  }
}

async function handlePreviewTts() {
  loading.previewTts = true
  try {
    const result = await previewTts('你好，我是犇犇，这是当前语音的试听效果。', ttsConfigPayload())
    await new Audio(result.audio).play()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.previewTts = false
  }
}

function adminConfigPayload() {
  return {
    assistant_api_url: adminForm.assistant_api_url,
    assistant_api_key: adminForm.assistant_api_key,
    assistant_model: adminForm.assistant_model,
    assistant_reasoning_effort: adminForm.assistant_reasoning_effort,
    assistant_prompt: adminForm.assistant_prompt,
  }
}

async function handleSaveAdminConfig() {
  loading.saveAdmin = true
  try {
    const result = await saveAdminConfig(adminConfigPayload())
    applyAdminConfig(result.config)
    authState.assistantPrompt = result.config.assistant_prompt || ''
    ElMessage.success('系统配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveAdmin = false
  }
}

async function handleLoadModels() {
  loading.models = true
  try {
    const result = await listAdminModels(adminConfigPayload())
    modelOptions.value = result.models
    adminForm.assistant_model = result.models[0] || adminForm.assistant_model
    if (result.warning) ElMessage.warning(result.warning)
    else ElMessage.success(`已获取 ${result.models.length} 个模型`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.models = false
  }
}

async function handleTestModel() {
  loading.testModel = true
  try {
    const result = await testAdminModel(adminConfigPayload())
    ElMessage.success(`测试成功：${result.model} 返回 ${result.message}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testModel = false
  }
}

async function handleSaveServerConfig() {
  loading.saveServer = true
  try {
    const result = await saveServerConfig(serverForm)
    applyAdminConfig(result.config)
    ElMessage.success('邮件服务器配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveServer = false
  }
}

async function loadSkills() {
  if (!user.value?.is_superadmin) return
  loading.skills = true
  try {
    const result = await listSkills()
    skills.value = result.skills || []
    loadedTabs.skills = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.skills = false
  }
}

async function toggleOrchestration() {
  if (orchestrationOpen.value) {
    orchestrationOpen.value = false
    return
  }
  orchestrationOpen.value = true
  if (orchestration.value) return
  loading.orchestration = true
  try {
    orchestration.value = await getAgentOrchestration()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.orchestration = false
  }
}

async function openAgentConfigEditor() {
  agentConfigDialog.value = true
  loading.agentConfig = true
  try {
    const result = await getAgentConfig()
    applyAgentConfig(result.config || {})
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.agentConfig = false
  }
}

function applyAgentConfig(config: AgentConfig) {
  for (const item of agentLabels) {
    agentPromptDraft[item.key] = config.prompts?.[item.key] || ''
    if (item.key !== 'dashboard') agentWorkflowDraft[item.key] = config.workflows?.[item.key] || ''
  }
}

async function handleSaveAgentConfig() {
  loading.saveAgentConfig = true
  try {
    const prompts: Record<string, string> = {}
    const workflows: Record<string, string> = {}
    for (const item of agentLabels) {
      if (agentPromptDraft[item.key]?.trim()) prompts[item.key] = agentPromptDraft[item.key].trim()
      if (item.key !== 'dashboard' && agentWorkflowDraft[item.key]?.trim()) workflows[item.key] = agentWorkflowDraft[item.key].trim()
    }
    const result = await saveAgentConfig({ prompts, workflows })
    ElMessage.success(result.message || '犇犇配置已保存')
    agentConfigDialog.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveAgentConfig = false
  }
}

function openSkillTest(skill: SkillDefinition) {
  currentSkill.value = skill
  const example = skill.detail?.call_example as { skill_call?: { arguments?: Record<string, unknown> } } | undefined
  skillTestArgs.value = JSON.stringify(example?.skill_call?.arguments || {}, null, 2)
  skillTestInstruction.value = ''
  skillConfirmUnsafe.value = false
  skillTestResult.value = '点击“运行测试”后，这里会显示 Skill 返回结果。'
  skillTestDialog.value = true
}

async function handleRunSkillTest() {
  if (!currentSkill.value || loading.skillTest) return
  let args: Record<string, unknown>
  try {
    const parsed = JSON.parse(skillTestArgs.value || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('调用参数必须是 JSON 对象')
    args = parsed
  } catch (error) {
    ElMessage.error(errorMessage(error))
    return
  }
  loading.skillTest = true
  try {
    const result = await runSkillTest({
      name: currentSkill.value.name,
      arguments: args,
      instruction: skillTestInstruction.value,
      confirm_unsafe: skillConfirmUnsafe.value,
    })
    skillTestResult.value = JSON.stringify(result, null, 2)
  } catch (error) {
    skillTestResult.value = errorMessage(error)
  } finally {
    loading.skillTest = false
  }
}

function openSkillDocs() {
  window.open(resourceUrl('/skill-docs'), '_blank', 'noopener,noreferrer')
}

function downloadSkillDocs() {
  window.open(resourceUrl('/download-skill-doc'), '_blank', 'noopener,noreferrer')
}

async function loadUsers() {
  if (!user.value?.is_superadmin) return
  loading.users = true
  try {
    const result = await listAdminUsers()
    users.value = result.users || []
    for (const item of users.value) {
      userDrafts[item.username] = { name: item.name || item.username, password: '', email: item.email || companyEmailFor(item.username), role: item.role, assistant_permissions: { ...item.assistant_permissions } }
    }
    loadedTabs.usermanage = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.users = false
  }
}

function resetNewUser() {
  newUser.username = ''
  newUser.name = ''
  newUser.password = ''
  newUser.email = ''
  newUser.role = 'member'
  newUser.employee_id = ''
  newUser.company = ''
  newUser.department = ''
  newUser.position = ''
}

function handleNewUserCompanyChange() {
  if (!newUserDepartments.value.includes(newUser.department.trim())) newUser.department = ''
}

function handleBatchCompanyChange() {
  batchDepartments.value = []
}

watch(assistantUserFilter, () => { assistantUserSelection.value = usersWithSelectedAssistant.value.map(item => item.username); assistantUserEnabled.value = false })

async function handleAssistantUserBatch() {
  if (!assistantUserFilter.value || !assistantUserSelection.value.length) return ElMessage.warning('请选择助手和至少一位用户')
  const action = assistantUserEnabled.value ? '开通' : '取消'
  try {
    await ElMessageBox.confirm(`确定为 ${assistantUserSelection.value.length} 位用户${action}「${selectedAssistant.value?.label || ''}」权限吗？`, `批量${action}助手权限`, { type: 'warning' })
    loading.batchPermissions = true
    const result = await batchUpdateUsersForAssistant({ assistant_id: assistantUserFilter.value, usernames: assistantUserSelection.value, enabled: assistantUserEnabled.value })
    users.value = result.users || []
    ElMessage.success(`已为 ${result.updated} 位用户${result.enabled ? '开通' : '取消'}权限`)
    await loadUsers()
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error)) } finally { loading.batchPermissions = false }
}

async function handleBatchPermissions() {
  if (!batchCompany.value || !batchAssistantIds.value.length) {
    ElMessage.warning('请选择公司和至少一个助手')
    return
  }
  if (!batchTargetCount.value) {
    ElMessage.warning('当前组织范围内没有可批量管理的成员')
    return
  }
  const scope = batchDepartments.value.length ? batchDepartments.value.join('、') : `${batchCompany.value}全公司`
  const action = batchEnabled.value ? '开通' : '关闭'
  try {
    await ElMessageBox.confirm(`将为 ${scope} 的 ${batchTargetCount.value} 位成员${action}所选助手权限。超级管理员与客户经营助手权限不受影响。`, `确认批量${action}`, {
      confirmButtonText: `确认${action}`,
      cancelButtonText: '取消',
      type: 'warning',
    })
    loading.batchPermissions = true
    const result = await batchUpdateAdminUserPermissions({
      company: batchCompany.value,
      departments: batchDepartments.value,
      assistant_ids: batchAssistantIds.value,
      enabled: batchEnabled.value,
    })
    users.value = result.users || []
    ElMessage.success(`已为 ${result.updated} 位成员${result.enabled ? '开通' : '关闭'}权限`)
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error))
  } finally {
    loading.batchPermissions = false
  }
}

async function handleOrganizationExcelUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  if (!file.name.toLowerCase().endsWith('.xlsx')) return ElMessage.warning('请选择 .xlsx 格式的组织架构表')
  if (file.size > 5 * 1024 * 1024) return ElMessage.warning('文件不能超过5MB')
  loading.organizationImport = true
  organizationExcelResult.value = null
  try {
    organizationExcelResult.value = await importOrganizationExcel(file, organizationCreateUsers.value)
    ElMessage.success(`名册已保存 ${organizationExcelResult.value.imported ?? organizationExcelResult.value.updated} 条，账号已更新 ${organizationExcelResult.value.updated} 条`)
    await loadUsers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.organizationImport = false
  }
}

function openAddUserDialog() {
  resetNewUser()
  addUserDialog.value = true
}

async function handleAddUser() {
  if (!newUser.username.trim() || !newUser.password.trim()) {
    ElMessage.warning('请填写用户名和初始密码')
    return
  }
  loading.addUser = true
  try {
    const result = await addAdminUser({
      username: newUser.username,
      password: newUser.password,
      name: newUser.name,
      role: newUser.role,
      employee_id: newUser.employee_id,
      company: newUser.company,
      department: newUser.department,
      position: newUser.position,
      email: newUser.email,
    })
    users.value = result.users || []
    addUserDialog.value = false
    ElMessage.success('用户已新增')
    await loadUsers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.addUser = false
  }
}

async function handleUpdateUser(item: User) {
  const draft = userDrafts[item.username]
  if (!draft) return
  try {
    const result = await updateAdminUser({
      username: item.username,
      name: draft.name,
      password: draft.password,
      email: draft.email,
      role: draft.role,
      assistant_permissions: draft.assistant_permissions,
    })
    users.value = result.users || []
    draft.password = ''
    ElMessage.success('用户已更新')
    await loadUsers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleDeleteUser(item: User) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${item.username} 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const result = await deleteAdminUser(item.username)
    users.value = result.users || []
    ElMessage.success('用户已删除')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error))
  }
}

function copyTextFallback(text: string) {
  // 非安全上下文无法使用 Clipboard API，降级为临时文本域复制。
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.cssText = 'position:fixed;opacity:0;top:0;left:0;'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  try {
    document.execCommand('copy')
    ElMessage.success('已复制')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    document.body.removeChild(textarea)
  }
}

function copyText(text: string) {
  if (!text) return
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制')).catch(() => copyTextFallback(text))
    return
  }
  copyTextFallback(text)
}

function isMcpInstalled(agent: LobsterAgent) {
  return (agent.mcp_services || []).some((service) => service.name === 'personal-office-assistant')
}

async function loadLobsters() {
  if (!user.value?.is_admin) return
  loading.lobsters = true
  lobsterStatus.value = ''
  try {
    const result = await listMyLobsters()
    if (!result.ok) throw new Error(result.error || '龙虾列表加载失败')
    lobsters.value = result.agents || []
  } catch (error) {
    lobsters.value = []
    lobsterStatus.value = errorMessage(error)
  } finally {
    loading.lobsters = false
  }
}

async function handleLoadLobsterModels(agent: LobsterAgent) {
  loadingLobsterModels.value = agent.agent_id
  lobsterStatus.value = `正在加载「${agent.agent_name}」的可用模型...`
  try {
    const result = await listLobsterModelOptions(agent.agent_id)
    lobsterModelOptions.value = { ...lobsterModelOptions.value, [agent.agent_id]: result.models || [] }
    lobsterModelDrafts.value = {
      ...lobsterModelDrafts.value,
      [agent.agent_id]: lobsterModelDrafts.value[agent.agent_id] || agent.model || result.models?.[0]?.id || '',
    }
    lobsterStatus.value = `已加载 ${result.models?.length || 0} 个模型。`
  } catch (error) {
    lobsterStatus.value = errorMessage(error)
  } finally {
    loadingLobsterModels.value = null
  }
}

async function handleSaveLobsterModel(agent: LobsterAgent) {
  const modelName = (lobsterModelDrafts.value[agent.agent_id] || agent.model || '').trim()
  if (!modelName) {
    ElMessage.warning('请选择或输入模型')
    return
  }
  savingLobsterModel.value = agent.agent_id
  lobsterStatus.value = `正在保存「${agent.agent_name}」模型...`
  try {
    const result = await updateLobsterModel(agent.agent_id, modelName)
    lobsterStatus.value = result.restart_required ? '模型已保存，重启龙虾后生效。' : '模型已保存。'
    await loadLobsters()
  } catch (error) {
    lobsterStatus.value = errorMessage(error)
  } finally {
    savingLobsterModel.value = null
  }
}

async function loadMcpConfig() {
  if (!user.value?.is_admin) return
  loading.mcpConfig = true
  mcpStatus.value = ''
  try {
    mcpConfig.value = await getMcpConfig()
    loadedTabs.mcp = true
    await loadLobsters()
  } catch (error) {
    mcpStatus.value = errorMessage(error)
  } finally {
    loading.mcpConfig = false
  }
}

async function handleGenerateMcpSecret() {
  if (!user.value?.is_superadmin) return
  try {
    await ElMessageBox.confirm('生成新密钥后，旧密钥立即失效，已接入的客户端需更新配置。确定继续？', '生成 MCP 密钥', {
      confirmButtonText: '生成',
      cancelButtonText: '取消',
      type: 'warning',
    })
    loading.mcpSecret = true
    const result = await saveMcpConfig({ generate: true })
    mcpNewSecret.value = result.mcp_secret || ''
    ElMessage.success(result.message || '新密钥已生成')
    await loadMcpConfig()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error))
  } finally {
    loading.mcpSecret = false
  }
}

async function handleClearMcpSecret() {
  if (!user.value?.is_superadmin) return
  try {
    await ElMessageBox.confirm('清除密钥后 MCP 服务立即停止响应，所有客户端连接将断开。确定清除？', '清除 MCP 密钥', {
      confirmButtonText: '清除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    loading.mcpSecret = true
    const result = await saveMcpConfig({ clear: true })
    mcpNewSecret.value = ''
    ElMessage.success(result.message || 'MCP 密钥已清除')
    await loadMcpConfig()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorMessage(error))
  } finally {
    loading.mcpSecret = false
  }
}

function handleInstallMcpToLobster(agent: LobsterAgent) {
  if (!mcpEnabled.value) {
    ElMessage.warning('请先生成 MCP 密钥')
    return
  }
  pendingInstallAgent.value = agent
  installMcpDialog.value = true
}

async function confirmInstallMcp(withRestart: boolean) {
  const agent = pendingInstallAgent.value
  if (!agent) return
  installMcpDialog.value = false
  installingLobsterId.value = agent.agent_id
  loading.mcpInstall = true
  lobsterStatus.value = `正在安装到「${agent.agent_name}」...`
  try {
    const result = await installMcpToLobster(agent.agent_id)
    if (!result.ok) throw new Error(result.error || result.detail || '安装失败')
    if (withRestart) {
      lobsterStatus.value = `安装成功，正在重启「${agent.agent_name}」...`
      mcpRestartLoading.value = true
      await restartLobster(agent.agent_id)
      lobsterStatus.value = `已成功安装并重启「${agent.agent_name}」，MCP 服务即时生效。`
    } else {
      lobsterStatus.value = `已成功安装到「${agent.agent_name}」，重启龙虾后生效。`
    }
    await loadLobsters()
  } catch (error) {
    lobsterStatus.value = errorMessage(error)
  } finally {
    installingLobsterId.value = null
    loading.mcpInstall = false
    mcpRestartLoading.value = false
    pendingInstallAgent.value = null
  }
}

function lobsterLabel(agent: LobsterAgent) {
  // 多个同名龙虾靠 #编号 + 模型 + 创建日期 区分。
  const statusText = agent.status === 'running' ? '运行中' : agent.status === 'exited' ? '已停止' : agent.status || '未知'
  const parts = [`${agent.agent_name} #${agent.agent_id}`, statusText]
  if (agent.model) parts.push(agent.model)
  const created = (agent.created_at || '').slice(0, 10)
  if (created) parts.push(`建于${created}`)
  return parts.join(' · ')
}

async function loadAssistantBinding() {
  // 悬浮助手绑定：拉龙虾列表 + 当前绑定。
  await loadLobsters()
  try {
    const result = await getAssistantLobster()
    boundLobsterId.value = result.ok && result.lobster ? result.lobster.agent_id : null
    selectedBindId.value = boundLobsterId.value
  } catch (error) {
    bindStatus.value = errorMessage(error)
  }
}

async function saveAssistantBinding() {
  savingBind.value = true
  bindStatus.value = ''
  try {
    const agentId = selectedBindId.value
    const name = lobsters.value.find((item) => item.agent_id === agentId)?.agent_name || ''
    const result = await saveAssistantLobster(agentId, name)
    boundLobsterId.value = result.lobster ? result.lobster.agent_id : null
    selectedBindId.value = boundLobsterId.value
    bindStatus.value = boundLobsterId.value ? `已绑定「${name} #${boundLobsterId.value}」，悬浮助手对话将直通该龙虾。` : '已解除绑定，悬浮助手恢复本地助手。'
    ElMessage.success(bindStatus.value)
  } catch (error) {
    bindStatus.value = errorMessage(error)
    ElMessage.error(bindStatus.value)
  } finally {
    savingBind.value = false
  }
}

async function unbindAssistant() {
  selectedBindId.value = null
  await saveAssistantBinding()
}

async function loadActiveTab() {
  // 无权限 tab 只展示提示，不发起管理接口请求。
  if (!canOpenTab(activeTab.value)) return
  if (activeTab.value === 'mailconfig' && !loadedTabs.mailconfig) {
    await loadMailConfig()
    void loadAssistantBinding()
  }
  if (activeTab.value === 'config' && !loadedTabs.config) await loadAdminConfig()
  if (activeTab.value === 'skills' && !loadedTabs.skills) await loadSkills()
  if (activeTab.value === 'usermanage' && !loadedTabs.usermanage) await loadUsers()
  if (activeTab.value === 'mcp' && !loadedTabs.mcp) await loadMcpConfig()
}

watch(
  () => props.activeMenu,
  (menu) => {
    const nextTab = tabFromMenu(menu)
    if (activeTab.value === nextTab) {
      void loadActiveTab()
      return
    }
    activeTab.value = nextTab
  },
)

watch(activeTab, () => {
  void loadActiveTab()
})

onMounted(() => {
  const nextTab = tabFromMenu(props.activeMenu)
  if (activeTab.value === nextTab) {
    void loadActiveTab()
    return
  }
  activeTab.value = nextTab
})
</script>

<template>
  <section class="workspace-main settings-main">
    <header class="settings-page-head">
      <div class="settings-tabs" role="tablist" aria-label="设置模块">
        <button
          v-for="tab in tabItems"
          :key="tab.id"
          :class="{ active: activeTab === tab.id }"
          type="button"
          @click="selectTab(tab.id)"
        >
          <el-icon><component :is="tab.icon" /></el-icon>
          {{ tab.label }}
        </button>
      </div>
    </header>

    <div class="settings-body">
      <section v-if="!canOpenTab(activeTab)" class="settings-panel settings-permission">
        <div class="settings-empty">
          <strong>暂无访问权限</strong>
          <span>{{ tabPermissionText(activeTab) }}</span>
        </div>
      </section>

      <section v-else-if="activeTab === 'mailconfig'" class="settings-panel">
        <div class="settings-section-head">
          <div>
            <h3>悬浮助手绑定龙虾</h3>
            <span>绑定后，右下角悬浮助手的对话将直通所选龙虾（支持多轮）；不绑定则使用本地页面助手。</span>
          </div>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.lobsters" @click="loadAssistantBinding">
            <el-icon><Refresh /></el-icon>
            刷新列表
          </button>
        </div>
        <div class="settings-assistant-bind">
          <el-select
            v-model="selectedBindId"
            clearable
            filterable
            :loading="loading.lobsters"
            placeholder="选择要绑定的龙虾（留空=不绑定）"
            class="settings-assistant-bind-select"
          >
            <el-option
              v-for="agent in lobsters"
              :key="agent.agent_id"
              :label="lobsterLabel(agent)"
              :value="agent.agent_id"
              :disabled="agent.status !== 'running'"
            />
          </el-select>
          <button class="settings-button settings-button--primary" type="button" :disabled="savingBind" @click="saveAssistantBinding">
            {{ savingBind ? '保存中…' : '保存绑定' }}
          </button>
          <button v-if="boundLobsterId" class="settings-button settings-button--ghost" type="button" :disabled="savingBind" @click="unbindAssistant">
            解除绑定
          </button>
        </div>
        <p v-if="!loading.lobsters && !lobsters.length" class="settings-hint">还没有龙虾，去「龙虾基地」创建一个后再来绑定。</p>
        <p v-if="bindStatus" class="settings-hint">{{ bindStatus }}</p>

        <div class="settings-section-head settings-section-head--spaced">
          <div>
            <h3>我的邮箱账户</h3>
            <span>发送邮件需要 SMTP；读取收件箱需要 IMAP。</span>
          </div>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.mailConfig" @click="loadMailConfig">
            <el-icon><Refresh /></el-icon>
            重新读取
          </button>
        </div>

        <div class="settings-mail-tabs">
          <button
            :class="{ active: activeMailTab === 'company' }"
            type="button"
            @click="activeMailTab = 'company'"
          >
            公司邮箱
            <em v-if="mailForm.user_email">{{ mailForm.user_email }}</em>
            <em v-else class="unconfigured">未配置</em>
          </button>
          <button
            :class="{ active: activeMailTab === 'personal' }"
            type="button"
            @click="activeMailTab = 'personal'"
          >
            个人邮箱
            <em v-if="personalMailForm.personal_email">{{ personalMailForm.personal_email }}</em>
            <em v-else class="unconfigured">未配置</em>
          </button>
        </div>

        <template v-if="activeMailTab === 'company'">
          <div class="settings-grid">
            <label>
              <span>本人邮箱</span>
              <input v-model="mailForm.user_email" :placeholder="mailReference.user_email" />
            </label>
            <label>
              <span>SMTP 发件地址</span>
              <input v-model="mailForm.smtp_from" :placeholder="mailReference.smtp_from" />
            </label>
            <label>
              <span>SMTP 用户名</span>
              <input v-model="mailForm.smtp_user" :placeholder="mailReference.smtp_user" />
              <em>留空保存时会自动使用本人邮箱。</em>
            </label>
            <label>
              <span>SMTP 授权码/密码</span>
              <input v-model="mailForm.smtp_password" type="password" placeholder="留空则保持原密码不变" />
              <em>状态：{{ mailMeta.smtp_password_masked }}</em>
            </label>
            <div class="settings-info-box">
              <span>SMTP 服务器（全局）</span>
              <strong>{{ mailMeta.smtp_host || 'smtp.263.net' }}</strong>
            </div>
            <div class="settings-info-box">
              <span>SMTP 端口 / SSL</span>
              <strong>{{ mailMeta.smtp_port }} / {{ mailMeta.smtp_ssl ? 'SSL' : 'TLS' }}</strong>
            </div>
          </div>

          <h4 class="settings-subtitle">收件箱 IMAP</h4>
          <div class="settings-grid">
            <label>
              <span>IMAP 用户名</span>
              <input v-model="mailForm.imap_user" :placeholder="mailReference.imap_user" />
              <em>留空保存时会自动使用 SMTP 用户名。</em>
            </label>
            <label>
              <span>IMAP 授权码/密码</span>
              <input v-model="mailForm.imap_password" type="password" placeholder="留空则保持原密码不变" />
              <em>状态：{{ mailMeta.imap_password_masked }}</em>
            </label>
            <div class="settings-info-box">
              <span>IMAP 服务器（全局）</span>
              <strong>{{ mailMeta.imap_host || 'imap.263.net' }}</strong>
            </div>
            <div class="settings-info-box">
              <span>IMAP 端口 / SSL</span>
              <strong>{{ mailMeta.imap_port }} / {{ mailMeta.imap_ssl ? 'SSL' : '非 SSL' }}</strong>
            </div>
          </div>

          <h4 class="settings-subtitle">报告邮件</h4>
          <div class="settings-grid">
            <label>
              <span>周报收件人</span>
              <input v-model="mailForm.weekly_to" :placeholder="mailReference.weekly_to" />
            </label>
            <label>
              <span>周报抄送</span>
              <input v-model="mailForm.weekly_cc" :placeholder="mailReference.weekly_cc" />
            </label>
            <label>
              <span>出差报告收件人</span>
              <input v-model="mailForm.trip_to" :placeholder="mailReference.trip_to" />
            </label>
            <label>
              <span>出差报告抄送</span>
              <input v-model="mailForm.trip_cc" :placeholder="mailReference.trip_cc" />
            </label>
            <div class="settings-field-full signature-settings-field">
              <span>邮件签名模板</span>
              <div class="signature-editor-shell">
                <div class="signature-editor-toolbar" aria-label="签名格式工具栏">
                  <select title="字体" aria-label="字体" @mousedown.stop @change="signatureSelect($event, 'fontName')">
                    <option value="">字体</option>
                    <option value="Arial">Arial</option>
                    <option value="Microsoft YaHei">微软雅黑</option>
                    <option value="SimSun">宋体</option>
                    <option value="Verdana">Verdana</option>
                  </select>
                  <select title="字号" aria-label="字号" @mousedown.stop @change="signatureSelect($event, 'fontSize')">
                    <option value="">字号</option>
                    <option value="2">12px</option>
                    <option value="3">14px</option>
                    <option value="4">16px</option>
                    <option value="5">18px</option>
                    <option value="6">24px</option>
                  </select>
                  <span class="signature-toolbar-divider"></span>
                  <button type="button" title="加粗" aria-label="加粗" @mousedown.prevent @click="formatSignature('bold')"><strong>B</strong></button>
                  <button type="button" title="斜体" aria-label="斜体" @mousedown.prevent @click="formatSignature('italic')"><i>I</i></button>
                  <button type="button" title="下划线" aria-label="下划线" @mousedown.prevent @click="formatSignature('underline')"><u>U</u></button>
                  <label class="signature-color-button" title="文字颜色" aria-label="文字颜色" @mousedown.stop>
                    <span>A</span><input type="color" value="#172554" @input="formatSignature('foreColor', ($event.target as HTMLInputElement).value)" />
                  </label>
                  <button type="button" title="清除格式" aria-label="清除格式" @mousedown.prevent @click="formatSignature('removeFormat')">Tx</button>
                  <span class="signature-toolbar-divider"></span>
                  <button type="button" title="项目符号列表" aria-label="项目符号列表" @mousedown.prevent @click="formatSignature('insertUnorderedList')">•≡</button>
                  <button type="button" title="编号列表" aria-label="编号列表" @mousedown.prevent @click="formatSignature('insertOrderedList')">1≡</button>
                  <button type="button" title="左对齐" aria-label="左对齐" @mousedown.prevent @click="formatSignature('justifyLeft')">≡</button>
                  <button type="button" title="居中" aria-label="居中" @mousedown.prevent @click="formatSignature('justifyCenter')">≡</button>
                  <button type="button" title="右对齐" aria-label="右对齐" @mousedown.prevent @click="formatSignature('justifyRight')">≡</button>
                  <span class="signature-toolbar-divider"></span>
                  <button type="button" title="插入链接" aria-label="插入链接" @mousedown.prevent @click="addSignatureLink">链接</button>
                  <button type="button" title="插入图片" aria-label="插入图片" @mousedown.prevent @click="addSignatureImage">图片</button>
                  <button type="button" title="插入表格" aria-label="插入表格" @mousedown.prevent @click="insertSignatureTable">表格</button>
                </div>
                <div ref="signatureEditorRef" class="signature-editor" contenteditable="true" role="textbox" aria-multiline="true" tabindex="0" data-placeholder="留空则使用默认签名" v-html="signatureEditorHtml" @focus="rememberSignatureSelection" @mouseup="rememberSignatureSelection" @keyup="rememberSignatureSelection" @keydown="handleSignatureEditorKeydown" @input="syncSignatureEditor"></div>
              </div>
            </div>
          </div>
          <div class="settings-actions">
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.saveMail" @click="handleSaveMailConfig">保存</button>
            <button class="settings-button settings-button--primary" type="button" :disabled="loading.testMail" @click="handleTestMailConfig">测试连接</button>
          </div>
        </template>

        <template v-else>
          <div class="settings-grid">
            <label>
              <span>邮箱地址</span>
              <input v-model="personalMailForm.personal_email" placeholder="yourname@gmail.com" />
            </label>
            <label>
              <span>SMTP 用户名</span>
              <input v-model="personalMailForm.personal_smtp_user" placeholder="留空则使用邮箱地址" />
            </label>
            <label>
              <span>SMTP 授权码/密码</span>
              <input v-model="personalMailForm.personal_smtp_password" type="password" placeholder="留空则保持原密码不变" />
              <em>状态：{{ mailMeta.personal_smtp_password_masked }}</em>
            </label>
            <label>
              <span>SMTP 服务器</span>
              <input v-model="personalMailForm.personal_smtp_host" placeholder="smtp.gmail.com" />
            </label>
            <label>
              <span>SMTP 端口</span>
              <input v-model.number="personalMailForm.personal_smtp_port" type="number" placeholder="587" />
            </label>
            <label class="settings-check">
              <input v-model="personalMailForm.personal_smtp_ssl" type="checkbox" />
              <span>使用 SSL</span>
            </label>
            <label class="settings-check">
              <input v-model="personalMailForm.personal_smtp_tls" type="checkbox" />
              <span>使用 TLS (STARTTLS)</span>
            </label>
          </div>

          <h4 class="settings-subtitle">收件箱 IMAP</h4>
          <div class="settings-grid">
            <label>
              <span>IMAP 服务器</span>
              <input v-model="personalMailForm.personal_imap_host" placeholder="imap.gmail.com" />
            </label>
            <label>
              <span>IMAP 端口</span>
              <input v-model.number="personalMailForm.personal_imap_port" type="number" placeholder="993" />
            </label>
            <label>
              <span>IMAP 用户名</span>
              <input v-model="personalMailForm.personal_imap_user" placeholder="留空则使用 SMTP 用户名" />
            </label>
            <label>
              <span>IMAP 授权码/密码</span>
              <input v-model="personalMailForm.personal_imap_password" type="password" placeholder="留空则保持原密码不变" />
              <em>状态：{{ mailMeta.personal_imap_password_masked }}</em>
            </label>
            <label class="settings-check">
              <input v-model="personalMailForm.personal_imap_ssl" type="checkbox" />
              <span>使用 SSL 连接 IMAP</span>
            </label>
          </div>
          <div class="settings-actions">
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.savePersonalMail" @click="handleSavePersonalMailConfig">保存</button>
            <button class="settings-button settings-button--primary" type="button" :disabled="loading.testPersonalMail" @click="handleTestPersonalMailConfig">测试连接</button>
          </div>
        </template>
      </section>

      <section v-else-if="activeTab === 'config'" class="settings-panel">
        <div class="settings-section-head">
          <div>
            <h3>系统配置</h3>
            <span>配置平台大模型 API 和全局邮件服务器。</span>
          </div>
        </div>
        <div class="settings-grid">
          <label>
            <span>NewAPI 地址</span>
            <input v-model="adminForm.assistant_api_url" placeholder="http://host:port" />
          </label>
          <label>
            <span>模型名称</span>
            <el-select v-model="adminForm.assistant_model" class="settings-select" placeholder="请选择模型">
              <el-option v-for="model in modelOptions" :key="model" :label="model" :value="model" />
            </el-select>
          </label>
          <label>
            <span>手动模型名称</span>
            <input v-model="adminForm.assistant_model" placeholder="MiniMax-M2.7" />
          </label>
          <label>
            <span>深度思考</span>
            <el-select v-model="adminForm.assistant_reasoning_effort" class="settings-select">
              <el-option label="关闭（推荐，常规办公）" value="off" />
              <el-option label="最小" value="minimal" />
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高（响应较慢）" value="high" />
            </el-select>
            <em>应用于周报、写作、日记、数字人、会议纪要、资讯、报销和 Skill 等所有平台大模型调用。</em>
          </label>
          <label>
            <span>API Key</span>
            <input v-model="adminForm.assistant_api_key" type="password" placeholder="留空则保持原 Key 不变" />
            <em>状态：{{ apiKeyStatus }}</em>
          </label>
          <label class="settings-field-full">
            <span>默认优化提示词</span>
            <textarea v-model="adminForm.assistant_prompt"></textarea>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.models" @click="handleLoadModels">获取模型列表</button>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.testModel" @click="handleTestModel">测试 API Key</button>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveAdmin" @click="handleSaveAdminConfig">保存系统配置</button>
        </div>

        <h4 class="settings-subtitle">统一模型服务（Xinference）</h4>
        <p class="settings-hint">本地 Xinference 同时提供语音识别 / 语音合成 / 向量嵌入。在这里一处配置，「一键应用」会同步到会议助手、数字人与知识库（含 RAGFlow 全部用户租户）。</p>
        <div class="settings-grid">
          <label>
            <span>Xinference 地址</span>
            <input v-model="xfForm.api_url" placeholder="http://10.1.6.230:9997" />
          </label>
          <label>
            <span>语音识别模型（ASR）</span>
            <el-select v-model="xfForm.asr_model" class="settings-select" filterable allow-create clearable placeholder="点「检测模型」自动发现">
              <el-option v-for="m in xfModels.asr" :key="m" :label="m" :value="m" />
            </el-select>
            <em>应用到会议助手 · 当前：{{ xfCurrent.meeting || '未配置' }}</em>
          </label>
          <label>
            <span>语音合成模型（TTS）</span>
            <el-select v-model="xfForm.tts_model" class="settings-select" filterable allow-create clearable placeholder="点「检测模型」自动发现">
              <el-option v-for="m in xfModels.tts" :key="m" :label="m" :value="m" />
            </el-select>
            <em>应用到数字人 · 当前：{{ xfCurrent.tts || '未配置' }}</em>
          </label>
          <label>
            <span>向量嵌入模型</span>
            <el-select v-model="xfForm.embedding_model" class="settings-select" filterable allow-create clearable placeholder="点「检测模型」自动发现">
              <el-option v-for="m in xfModels.embedding" :key="m" :label="m" :value="m" />
            </el-select>
            <em>应用到知识库与 RAGFlow 全部租户 · 当前：{{ xfCurrent.kb || '未配置' }}</em>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.xfProbe" @click="handleProbeXinference">{{ loading.xfProbe ? '检测中…' : '检测模型' }}</button>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.xfApply" @click="handleApplyXinference">{{ loading.xfApply ? '应用中…' : '一键应用到三大功能' }}</button>
        </div>

        <h4 class="settings-subtitle">数字人语音（TTS）</h4>
        <div class="settings-grid">
          <label>
            <span>语音引擎</span>
            <el-select v-model="ttsForm.provider" class="settings-select" :loading="loading.ttsConfig">
              <el-option label="内置 Edge-TTS（免费在线合成）" value="edge" />
              <el-option label="API 接口（OpenAI 兼容 / 本地 Xinference）" value="api" />
            </el-select>
          </label>
          <template v-if="ttsForm.provider === 'edge'">
            <label>
              <span>音色</span>
              <el-select v-model="ttsForm.voice" class="settings-select" placeholder="请选择音色" filterable allow-create default-first-option>
                <el-option v-for="voice in ttsVoices" :key="voice.id" :label="voice.label" :value="voice.id" />
              </el-select>
              <em>支持手动输入其他 edge-tts 音色名（如 en-US-AriaNeural）</em>
            </label>
            <label>
              <span>语调</span>
              <el-select v-model="ttsForm.pitch" class="settings-select">
                <el-option v-for="item in ttsPitchOptions" :key="item.value" :label="`${item.label}（${item.value}）`" :value="item.value" />
              </el-select>
            </label>
          </template>
          <template v-else>
            <label>
              <span>语音 API 地址</span>
              <input v-model="ttsForm.api_url" placeholder="留空复用大模型地址；本地 Xinference 填 http://主机:9997" />
            </label>
            <label>
              <span>语音 API Key</span>
              <input v-model="ttsForm.api_key" type="password" placeholder="Xinference 无鉴权可留空；留空保持原 Key" />
              <em>状态：{{ ttsApiKeyStatus }} <a v-if="ttsApiKeyStatus === '已配置'" href="javascript:;" @click="handleClearTtsKey">清除已存 Key</a></em>
            </label>
            <label>
              <span>语音模型名称</span>
              <input v-model="ttsForm.api_model" placeholder="tts-1 / CosyVoice-300M-SFT / ChatTTS 等" />
            </label>
            <label>
              <span>音色名称</span>
              <el-select v-model="ttsForm.api_voice" class="settings-select" filterable allow-create default-first-option :loading="loading.ttsVoiceProbe" placeholder="选择或输入音色">
                <el-option v-for="voice in ttsApiVoices" :key="voice" :label="voice" :value="voice" />
              </el-select>
              <em><a href="javascript:;" @click="handleProbeTtsVoices">从语音服务获取音色列表</a>（CosyVoice 用 中文女 / 中文男 等）</em>
            </label>
          </template>
          <label>
            <span>语速</span>
            <el-select v-model="ttsForm.rate" class="settings-select">
              <el-option v-for="item in ttsRateOptions" :key="item.value" :label="`${item.label}（${item.value}）`" :value="item.value" />
            </el-select>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.previewTts" @click="handlePreviewTts">{{ loading.previewTts ? '合成中…' : '试听' }}</button>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveTts" @click="handleSaveTtsConfig">保存语音配置</button>
        </div>

        <h4 class="settings-subtitle">会议助手语音识别（ASR）</h4>
        <div class="settings-grid">
          <label>
            <span>识别 API 地址</span>
            <input v-model="meetingForm.api_url" placeholder="留空复用大模型地址；本地 Xinference 填 http://主机:9997" />
          </label>
          <label>
            <span>识别 API Key</span>
            <input v-model="meetingForm.api_key" type="password" placeholder="Xinference 无鉴权可留空；留空保持原 Key" />
            <em>状态：{{ meetingApiKeyStatus }} <a v-if="meetingApiKeyStatus === '已配置'" href="javascript:;" @click="handleClearMeetingKey">清除已存 Key</a></em>
          </label>
          <label>
            <span>识别模型名称</span>
            <input v-model="meetingForm.model" placeholder="whisper-1 / SenseVoiceSmall / whisper-large-v3" />
            <em>会议助手的"浏览器实时识别"引擎无需此配置</em>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.testMeeting" @click="handleTestMeetingAsr">{{ loading.testMeeting ? '识别中…' : '测试识别' }}</button>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveMeeting" @click="handleSaveMeetingConfig">保存识别配置</button>
        </div>

        <h4 class="settings-subtitle">知识库（RAG）</h4>
        <div class="settings-grid">
          <label>
            <span>知识库引擎</span>
            <el-select v-model="kbForm.provider" class="settings-select" :loading="loading.kbConfig">
              <el-option label="RAGFlow（推荐：DeepDoc 解析 + 混合检索 + 引用问答）" value="ragflow" />
              <el-option label="内置引擎（嵌入 + Qdrant/本地向量）" value="builtin" />
            </el-select>
          </label>
          <template v-if="kbForm.provider === 'ragflow'">
            <label>
              <span>RAGFlow API 地址</span>
              <input v-model="kbForm.ragflow_url" placeholder="http://主机:9380" />
            </label>
            <label>
              <span>RAGFlow API Key</span>
              <input v-model="kbForm.ragflow_api_key" type="password" placeholder="留空保持原值；点下方「一键初始化」自动生成" />
              <em>状态：{{ kbRagflowKeyStatus }}</em>
            </label>
            <label>
              <span>解析分块模板</span>
              <el-select v-model="ragflowChunkForm.chunk_method" class="settings-select" :loading="loading.ragflowStatus">
                <el-option v-for="item in ragflowStatus?.chunk_methods || []" :key="item.id" :label="item.label" :value="item.id" />
              </el-select>
              <em>制度文件选"法规制度"、报表选"表格"，调整后旧文档需重新解析</em>
            </label>
            <label>
              <span>分块大小（token）</span>
              <input v-model.number="ragflowChunkForm.chunk_token_num" type="number" min="64" max="2048" placeholder="512" />
            </label>
            <label>
              <span>版面识别（解析速度）</span>
              <el-select v-model="ragflowChunkForm.layout_recognize" class="settings-select">
                <el-option label="DeepDOC（OCR+版面分析，扫描件/复杂排版）" value="DeepDOC" />
                <el-option label="Plain Text（快速：直接抽取文本层）" value="Plain Text" />
              </el-select>
              <em>制度文件、系统导出的 PDF/Word 选 Plain Text 可快一到两个数量级</em>
            </label>
          </template>
          <label v-if="kbForm.provider === 'builtin'">
            <span>嵌入 API 地址</span>
            <input v-model="kbForm.api_url" placeholder="留空复用大模型地址；本地 Xinference 填 http://主机:9997" />
          </label>
          <label v-if="kbForm.provider === 'builtin'">
            <span>嵌入 API Key</span>
            <input v-model="kbForm.api_key" type="password" placeholder="Xinference 无鉴权可留空；留空保持原 Key" />
            <em>状态：{{ kbApiKeyStatus }} <a v-if="kbApiKeyStatus === '已配置'" href="javascript:;" @click="handleClearKbKey">清除已存 Key</a></em>
          </label>
          <label v-if="kbForm.provider === 'builtin'">
            <span>嵌入模型名称</span>
            <input v-model="kbForm.model" placeholder="bge-m3 / bge-large-zh-v1.5 / text-embedding-3-small" />
            <em>更换模型后已入库文档需删除重新上传</em>
          </label>
          <label v-if="kbForm.provider === 'builtin'">
            <span>向量存储</span>
            <el-select v-model="kbForm.vector_store" class="settings-select">
              <el-option label="本地文件（零依赖，小规模）" value="local" />
              <el-option label="Qdrant 向量库（推荐，compose 启动）" value="qdrant" />
            </el-select>
          </label>
          <label v-if="kbForm.provider === 'builtin' && kbForm.vector_store === 'qdrant'">
            <span>Qdrant 地址</span>
            <input v-model="kbForm.qdrant_url" placeholder="容器内 http://qdrant:6333" />
          </label>
          <label v-if="kbForm.provider === 'builtin'">
            <span>重排模型（可选）</span>
            <input v-model="kbForm.rerank_model" placeholder="留空关闭；如 bge-reranker-v2-m3（复用嵌入 API 地址）" />
            <em>启用后先向量粗排再精排，显著提升检索准确率</em>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.testKb" @click="handleTestKbEmbedding">{{ loading.testKb ? '测试中…' : '测试连接' }}</button>
          <template v-if="kbForm.provider === 'ragflow'">
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.ragflowBootstrap" @click="handleRagflowBootstrap">{{ loading.ragflowBootstrap ? '初始化中…' : '一键初始化/同步模型' }}</button>
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.ragflowChunk" @click="handleSaveRagflowChunk">{{ loading.ragflowChunk ? '应用中…' : '应用解析配置' }}</button>
          </template>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveKb" @click="handleSaveKbConfig">保存知识库配置</button>
        </div>

        <template v-if="kbForm.provider === 'ragflow' && ragflowStatus">
          <h4 class="settings-subtitle">RAGFlow 服务总览
            <em style="font-weight:400;margin-left:8px;">{{ ragflowStatus.reachable ? `运行中 v${ragflowStatus.version || '?'}` : '不可达' }} · {{ ragflowStatus.configured ? 'Key 已配置' : '未初始化' }}
              <a href="javascript:;" style="margin-left:6px;" @click="loadRagflowStatus">刷新</a>
            </em>
          </h4>
          <p v-if="ragflowStatus.error" class="settings-hint" style="color:#b88230;">{{ ragflowStatus.error }}</p>
          <table v-if="ragflowStatus.datasets.length" class="settings-table">
            <thead><tr><th>知识库</th><th>文档数</th><th>分块数</th><th>解析模板</th></tr></thead>
            <tbody>
              <tr v-for="ds in ragflowStatus.datasets" :key="ds.id">
                <td>{{ ds.name }}</td>
                <td>{{ ds.document_count }}</td>
                <td>{{ ds.chunk_count }}</td>
                <td>{{ ds.chunk_method }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="settings-hint">还没有任何知识库数据集。</p>
        </template>

        <template v-if="user?.is_superadmin">
          <h4 class="settings-subtitle">邮件服务器（全局）</h4>
          <div class="settings-grid">
            <label>
              <span>SMTP 服务器</span>
              <input v-model="serverForm.smtp_host" placeholder="smtp.263.net" />
            </label>
            <label>
              <span>SMTP 端口</span>
              <input v-model.number="serverForm.smtp_port" type="number" placeholder="465" />
            </label>
            <label class="settings-check">
              <input v-model="serverForm.smtp_tls" type="checkbox" />
              <span>使用 TLS</span>
            </label>
            <label class="settings-check">
              <input v-model="serverForm.smtp_ssl" type="checkbox" />
              <span>使用 SSL</span>
            </label>
            <label>
              <span>IMAP 服务器</span>
              <input v-model="serverForm.imap_host" placeholder="imap.263.net" />
            </label>
            <label>
              <span>IMAP 端口</span>
              <input v-model.number="serverForm.imap_port" type="number" placeholder="993" />
            </label>
            <label class="settings-check">
              <input v-model="serverForm.imap_ssl" type="checkbox" />
              <span>使用 SSL 连接 IMAP</span>
            </label>
          </div>
          <div class="settings-actions">
            <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveServer" @click="handleSaveServerConfig">保存邮件服务器配置</button>
          </div>
        </template>
      </section>

      <section v-else-if="activeTab === 'skills'" class="settings-panel">
        <div class="settings-section-head">
          <div>
            <h3>系统 Skill 管理</h3>
            <span>查看当前已安装的 Skill、能力说明、调用参数和调用示例。</span>
          </div>
          <div class="settings-actions settings-actions--compact">
            <button class="settings-button settings-button--ghost" type="button" @click="toggleOrchestration">犇犇编排逻辑</button>
            <button class="settings-button settings-button--ghost" type="button" @click="openAgentConfigEditor">编辑犇犇配置</button>
            <button class="settings-button settings-button--ghost" type="button" @click="openSkillDocs">查看完整文档</button>
            <button class="settings-button settings-button--primary" type="button" @click="downloadSkillDocs">下载文档</button>
          </div>
        </div>

        <div class="skill-protocol">
          <strong>大模型调用协议</strong>
          <span>当大模型需要操作软件时，返回 JSON；普通问答直接自然语言回复。</span>
          <pre>{"reply":"给用户看的说明","skill_call":{"name":"skill.name","arguments":{}}}</pre>
        </div>

        <div v-if="orchestrationOpen" class="skill-orchestration">
          <h4>犇犇编排逻辑</h4>
          <div v-if="loading.orchestration" class="settings-empty">正在加载编排逻辑...</div>
          <div v-else-if="orchestration" class="skill-orchestration-grid">
            <pre>{{ JSON.stringify(orchestration.agents, null, 2) }}</pre>
            <pre>{{ JSON.stringify(orchestration.workflows, null, 2) }}</pre>
          </div>
        </div>

        <div class="skill-toolbar">
          <label>
            <el-icon><Search /></el-icon>
            <input v-model="skillSearch" placeholder="搜索 Skill 名称、模块或说明..." />
          </label>
          <el-select v-model="skillModule" class="settings-select" placeholder="全部模块">
            <el-option
              v-for="module in skillModules"
              :key="module"
              :label="module === 'all' ? '全部模块' : module"
              :value="module"
            />
          </el-select>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.skills" @click="loadSkills">
            <el-icon><Refresh /></el-icon>
            刷新
          </button>
        </div>

        <div class="skill-module-summary">
          <button
            v-for="module in skillModules"
            :key="module"
            :class="{ active: skillModule === module }"
            type="button"
            @click="skillModule = module"
          >
            <strong>{{ module === 'all' ? '全部 Skill' : `${module} Skill` }}</strong>
            <span>{{ module === 'all' ? skills.length : skills.filter((skill) => skill.module === module).length }} 个能力</span>
          </button>
        </div>

        <div v-if="loading.skills" class="settings-empty">正在读取系统 Skill...</div>
        <div v-else class="skill-list">
          <article v-for="skill in filteredSkills" :key="skill.name" class="skill-card">
            <div class="skill-card-head">
              <div>
                <strong>{{ skill.name }}</strong>
                <span>{{ skill.module }} · {{ skill.title }}</span>
              </div>
              <em :class="{ warn: !skill.safe }">{{ skill.safe ? '查询/预览' : '写入/发送' }}</em>
            </div>
            <p>{{ skill.description }}</p>
            <pre>{{ JSON.stringify(skill.detail?.call_example || { skill_call: { name: skill.name, arguments: {} } }, null, 2) }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="openSkillTest(skill)">
              <el-icon><MagicStick /></el-icon>
              运行测试
            </button>
          </article>
          <div v-if="!filteredSkills.length" class="settings-empty">没有匹配的 Skill。</div>
        </div>
      </section>

      <section v-else-if="activeTab === 'usermanage'" class="settings-panel">
        <div class="settings-section-head">
          <div>
            <h3>用户管理</h3>
    <span>仅超级管理员可授予或撤销助手权限。客户经营助手会同步写入其专项数据范围权限，默认仅可见本人资料。</span>
          </div>
          <div class="settings-section-actions">
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.users" @click="loadUsers">
              <el-icon><Refresh /></el-icon>
              刷新
            </button>
            <button class="settings-button settings-button--primary" type="button" @click="openAddUserDialog">
              <el-icon><Plus /></el-icon>
              新增用户
            </button>
            <button class="settings-button settings-button--ghost" type="button" @click="organizationExcelDialog = true">
              组织架构同步
            </button>
            <InternalOrganizationEntry @changed="loadUsers"/>
          </div>
        </div>

        <div class="user-search-toolbar">
          <el-input v-model="userSearch" clearable :prefix-icon="Search" placeholder="搜索姓名、工号、公司、部门或账号" aria-label="搜索用户" />
          <el-radio-group v-model="organizationStatusFilter" class="organization-status-filter">
            <el-radio-button label="all">全部 {{ users.length }}</el-radio-button>
            <el-radio-button label="missing">待核验 {{ missingOrganizationUsers.length }}</el-radio-button>
          </el-radio-group>
          <span>{{ userSearch.trim() ? `找到 ${filteredUsers.length} 位用户 / 共 ${users.length} 位` : `共 ${users.length} 位用户` }}</span>
          <el-button v-if="expandedUsername" text @click="expandedUsername = null">全部收起</el-button>
        </div>

        <section class="batch-permission-panel">
          <div>
            <strong>按组织批量授权</strong>
            <span>全部助手均可在此批量开通或关闭；客户经营助手会按专项规则授予“仅本人数据”访问权限。</span>
          </div>
          <div class="batch-permission-controls">
            <el-select v-model="batchCompany" filterable placeholder="选择公司" class="settings-select" @change="handleBatchCompanyChange">
              <el-option v-for="company in organizationCompanies" :key="company" :label="company" :value="company" />
            </el-select>
            <el-select v-model="batchDepartments" multiple collapse-tags collapse-tags-tooltip :disabled="!batchCompany" placeholder="全部部门（默认）" class="settings-select">
              <el-option v-for="department in batchDepartmentsOptions" :key="department" :label="department" :value="department" />
            </el-select>
            <el-radio-group v-model="batchEnabled" class="batch-permission-action">
              <el-radio-button :label="true">开通</el-radio-button>
              <el-radio-button :label="false">关闭</el-radio-button>
            </el-radio-group>
          </div>
          <el-checkbox-group v-model="batchAssistantIds" class="batch-permission-assistants">
            <el-checkbox v-for="assistant in batchPermissionAssistants" :key="assistant.id" :value="assistant.id">{{ assistant.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="batch-permission-footer">
            <span>{{ batchCompany ? `将影响 ${batchTargetCount} 位非超级管理员成员` : '请先选择公司' }}</span>
            <button class="settings-button settings-button--primary" type="button" :disabled="loading.batchPermissions || !batchCompany || !batchAssistantIds.length" @click="handleBatchPermissions">
              批量{{ batchEnabled ? '开通' : '关闭' }}
            </button>
          </div>
        </section>

        <section class="batch-permission-panel assistant-user-panel">
          <div><strong>按助手查看与批量调整</strong><span>选择助手后会列出当前已开通用户；勾选名单后可批量取消或开通。</span></div>
          <div class="batch-permission-controls">
            <el-select v-model="assistantUserFilter" filterable clearable placeholder="选择要查看的助手" class="settings-select"><el-option v-for="assistant in batchPermissionAssistants" :key="assistant.id" :label="`${assistant.label}（${users.filter(user => user.role !== 'superadmin' && user.assistant_permissions?.[assistant.id]).length} 人已开通）`" :value="assistant.id" /></el-select>
            <el-radio-group v-model="assistantUserEnabled" class="batch-permission-action"><el-radio-button :label="false">取消权限</el-radio-button><el-radio-button :label="true">开通权限</el-radio-button></el-radio-group>
          </div>
          <el-checkbox-group v-if="assistantUserFilter" v-model="assistantUserSelection" class="batch-permission-assistants assistant-user-list">
            <el-checkbox v-for="user in assistantUserCandidates" :key="user.username" :value="user.username"><strong>{{ user.name || user.username }}</strong> · {{ user.username }}<small>{{ user.company || '未归属公司' }}{{ user.department ? ` / ${user.department}` : '' }}<template v-if="user.assistant_permissions?.[assistantUserFilter]"> · 已开通</template></small></el-checkbox>
          </el-checkbox-group>
          <div class="batch-permission-footer"><span>{{ assistantUserFilter ? `${usersWithSelectedAssistant.length} 位用户已开通，当前选中 ${assistantUserSelection.length} 位` : '请选择助手查看授权用户' }}</span><button class="settings-button settings-button--primary" type="button" :disabled="loading.batchPermissions || !assistantUserFilter || !assistantUserSelection.length" @click="handleAssistantUserBatch">批量{{ assistantUserEnabled ? '开通' : '取消' }}</button></div>
        </section>

        <div v-if="loading.users" class="settings-empty">正在加载用户列表...</div>
        <div v-else class="organization-user-list">
          <details v-for="company in organizationUsers" :key="company.company" class="organization-company" open>
            <summary>
              <span class="organization-company__icon">⌘</span>
              <strong>{{ company.company }}</strong>
              <em>{{ company.departments.length }} 个组织单元 · {{ company.departments.reduce((total, department) => total + department.members.length, 0) }} 位成员</em>
            </summary>
            <div class="organization-company__body">
              <details v-for="department in company.departments" :key="department.department" class="organization-department" :open="Boolean(userSearch.trim())">
                <summary>
                  <span>{{ department.department.split(' / ').join(' › ') }}</span>
                  <em>{{ department.members.length }} 人</em>
                </summary>
                <div class="user-list">
          <article v-for="item in department.members" :key="item.username" class="user-card" :class="{ 'is-expanded': expandedUsername === item.username, 'is-roster-missing': item.organization_check?.status === 'missing' }">
            <button type="button" class="user-card-head" :aria-expanded="expandedUsername === item.username"
              :aria-controls="`user-details-${item.username}`"
              @click="expandedUsername = expandedUsername === item.username ? null : item.username">
              <span>
                <el-icon><UserFilled /></el-icon>
              </span>
              <div>
                <div class="user-card-title">
                  <strong>{{ item.name || item.username }}</strong>
                  <span v-if="item.organization_check?.status === 'missing'" class="user-roster-status">未在最新组织表中 · 待核验</span>
                </div>
                <em>{{ item.username }} · {{ roleLabel(item.role) }}</em>
                <small v-if="item.company || item.department || item.position" class="user-organization-summary">
                  {{ [item.company, item.department, item.position].filter(Boolean).join(' · ') }}
                </small>
              </div>
              <small class="user-expand-label">{{ expandedUsername === item.username ? '收起详情 ▴' : '管理 / 展开 ▾' }}</small>
            </button>
            <div v-if="expandedUsername === item.username" :id="`user-details-${item.username}`" class="user-card-details">
            <div v-if="item.organization_check?.status === 'missing'" class="user-roster-warning">
              <strong>该成员未出现在最近一次公司组织架构表中</strong>
              <span>请核实是否离职、调动或表格遗漏。账号、权限和历史数据尚未改变。</span>
              <small>核对时间：{{ item.organization_check.checked_at.replace('T', ' ') }} · 来源：{{ item.organization_check.source }}</small>
            </div>
            <div v-if="item.company || item.department || item.position || item.employee_id" class="user-organization-profile">
              <span v-if="item.employee_id">工号：{{ item.employee_id }}</span>
              <span v-if="item.company">公司：{{ item.company }}</span>
              <span v-if="item.department">部门：{{ item.department }}</span>
              <span v-if="item.position">岗位：{{ item.position }}</span>
            </div>
            <div class="user-profile-fields">
            <label>
              <span>显示名称</span>
              <input v-model="userDrafts[item.username].name" />
            </label>
            <label>
              <span>新密码</span>
              <input v-model="userDrafts[item.username].password" type="password" placeholder="留空则不修改" />
            </label>
            <label>
              <span>绑定邮箱</span>
              <input v-model="userDrafts[item.username].email" type="email" placeholder="用于邮件找回密码" />
            </label>
            <label>
              <span>角色</span>
              <el-select v-model="userDrafts[item.username].role" class="settings-select">
                <el-option label="普通成员" value="member" />
                <el-option label="管理员" value="admin" />
                <el-option label="超级管理员" value="superadmin" />
              </el-select>
            </label>
            </div>
            <div class="user-assistant-permissions">
              <strong>助手使用权限</strong>
              <p>客户经营助手由「客户经营助手 → 安全权限」专门管理。</p>
              <p v-if="userDrafts[item.username].role === 'superadmin'">超级管理员拥有全部助手权限。</p>
              <div class="user-permission-options">
              <el-checkbox v-for="assistant in permissionAssistants" :key="assistant.id"
                v-model="userDrafts[item.username].assistant_permissions[assistant.id]"
                :disabled="userDrafts[item.username].role === 'superadmin' || assistant.id === 'crm'">{{ assistant.label }}</el-checkbox>
              </div>
            </div>
            <div class="user-card-actions">
              <button class="settings-button settings-button--ghost" type="button" @click="handleUpdateUser(item)">
                <el-icon><EditPen /></el-icon>
                保存
              </button>
              <button class="settings-button settings-button--danger" type="button" :disabled="item.role === 'superadmin'" @click="handleDeleteUser(item)">
                <el-icon><Delete /></el-icon>
                删除
              </button>
            </div>
            </div>
          </article>
                </div>
              </details>
            </div>
          </details>
          <div v-if="!filteredUsers.length" class="settings-empty">{{ userSearch.trim() ? '没有匹配的用户，请调整搜索条件。' : '暂无用户。' }}</div>
        </div>
      </section>

      <section v-else-if="activeTab === 'mcp'" class="settings-panel settings-mcp-panel">
        <div class="settings-section-head">
          <div>
            <h3>MCP 服务管理</h3>
            <span>通过 Model Context Protocol（MCP）将平台 Skill 开放给外部 AI 客户端。</span>
          </div>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.mcpConfig" @click="loadMcpConfig">
            <el-icon><Refresh /></el-icon>
            刷新状态
          </button>
        </div>

        <div class="settings-mcp-overview">
          <div class="settings-mcp-overview-main">
            <span :class="['settings-mcp-status-badge', { enabled: mcpEnabled }]">
              {{ mcpEnabled ? '已启用' : '未启用' }}
            </span>
            <span>{{ mcpConfig?.skill_count || 0 }} 个工具可用</span>
            <span>协议 {{ mcpConfig?.protocol_version || '-' }}</span>
          </div>
          <div class="settings-mcp-endpoint">
            <code>{{ mcpEndpoint }}</code>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpEndpoint)">
              <el-icon><CopyDocument /></el-icon>
              复制
            </button>
          </div>
        </div>

        <h4 class="settings-subtitle">密钥管理</h4>
        <div class="settings-mcp-secret-card">
          <div>
            <strong>MCP 访问密钥</strong>
            <span>{{ mcpSecretDescription }}</span>
            <em>状态：{{ mcpConfig?.mcp_secret_masked || '未读取' }}</em>
          </div>
          <div v-if="user?.is_superadmin" class="settings-section-actions">
            <button class="settings-button settings-button--primary settings-button--warn" type="button" :disabled="loading.mcpSecret" @click="handleGenerateMcpSecret">
              <el-icon><Key /></el-icon>
              生成新密钥
            </button>
            <button v-if="mcpEnabled" class="settings-button settings-button--danger" type="button" :disabled="loading.mcpSecret" @click="handleClearMcpSecret">
              清除密钥
            </button>
          </div>
        </div>

        <div v-if="mcpNewSecret" class="settings-mcp-new-secret">
          <div>
            <strong>新密钥已生成</strong>
            <span>请立即复制保存，页面刷新后不再显示明文。</span>
          </div>
          <code>{{ mcpNewSecret }}</code>
          <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpNewSecret)">
            <el-icon><CopyDocument /></el-icon>
            复制密钥
          </button>
        </div>

        <div v-if="mcpStatus" class="settings-empty settings-mcp-status-message">{{ mcpStatus }}</div>

        <h4 class="settings-subtitle">连接方式</h4>
        <div class="settings-mcp-connect-grid">
          <article class="settings-mcp-connect-card">
            <div class="settings-mcp-connect-head">
              <span><el-icon><Connection /></el-icon></span>
              <div>
                <strong>本地 Codex CLI 配置</strong>
                <em>将下方内容追加到 <code>~/.codex/config.toml</code>；把 <code>&lt;mcp_secret&gt;</code> 替换为上方刚生成的密钥。</em>
              </div>
            </div>
            <ol class="settings-mcp-install-steps">
              <li>确认已安装 Codex：运行 <code>codex --version</code>。</li>
              <li>编辑 <code>~/.codex/config.toml</code>，粘贴配置并替换密钥。</li>
              <li>完全退出后重新启动 Codex，再运行下方命令确认服务已加载。</li>
            </ol>
            <pre>{{ mcpCodexConfig }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpCodexConfig)">
              <el-icon><CopyDocument /></el-icon>
              复制 Codex 配置
            </button>
            <pre>{{ mcpCodexVerify }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpCodexVerify)">
              <el-icon><CopyDocument /></el-icon>
              复制验证命令
            </button>
          </article>

          <article class="settings-mcp-connect-card">
            <div class="settings-mcp-connect-head">
              <span><el-icon><Connection /></el-icon></span>
              <div>
                <strong>Claude Desktop / Claude Code MCP 配置</strong>
                <em>添加到 ~/.claude/settings.json 的 mcpServers 字段，或 claude_desktop_config.json。</em>
              </div>
            </div>
            <pre>{{ mcpClaudeConfig }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpClaudeConfig)">
              <el-icon><CopyDocument /></el-icon>
              复制
            </button>
          </article>

          <article class="settings-mcp-connect-card">
            <div class="settings-mcp-connect-head">
              <span><el-icon><Link /></el-icon></span>
              <div>
                <strong>其他支持 MCP 的智能体平台</strong>
                <em>在 Cursor、Cline、Cherry Studio、VS Code 扩展等客户端新增「Streamable HTTP / HTTP MCP」服务后，填入以下字段。</em>
              </div>
            </div>
            <ol class="settings-mcp-install-steps">
              <li>传输方式选择 <strong>Streamable HTTP</strong>（不要选择 stdio）。</li>
              <li>填写服务地址和两个请求头；用户名决定读取哪个平台账号的数据。</li>
              <li>保存后使用客户端的「测试连接」或工具列表确认。</li>
            </ol>
            <pre>{{ mcpGenericConfig }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpGenericConfig)">
              <el-icon><CopyDocument /></el-icon>
              复制通用配置
            </button>
          </article>

          <article class="settings-mcp-connect-card">
            <div class="settings-mcp-connect-head">
              <span><el-icon><Link /></el-icon></span>
              <div>
                <strong>curl 快速测试（tools/list）</strong>
                <em>验证 MCP 服务是否正常响应，替换密钥后执行。</em>
              </div>
            </div>
            <pre>{{ mcpCurlExample }}</pre>
            <button class="settings-button settings-button--ghost" type="button" @click="copyText(mcpCurlExample)">
              <el-icon><CopyDocument /></el-icon>
              复制
            </button>
          </article>
        </div>

        <div class="settings-mcp-headers">
          <strong>请求头说明</strong>
          <pre>Authorization: Bearer &lt;mcp_secret&gt;    ← 密钥（上方生成）
X-MCP-Username: &lt;username&gt;           ← 使用哪个账号的数据空间（如 {{ mcpUsername }}）</pre>
        </div>

        <h4 class="settings-subtitle">已开放 MCP 工具</h4>
        <div class="settings-mcp-tools">
          <template v-if="mcpEnabled">
            <strong>共 {{ mcpConfig?.skill_count || 0 }} 个 MCP 工具（Skill），分布在以下模块：</strong>
            <div class="settings-mcp-chip-list">
              <span v-for="module in mcpModules" :key="module">{{ module }} Skill</span>
            </div>
            <p>
              每个工具对应一个平台 Skill，工具名即 Skill 名。
              <button v-if="user?.is_superadmin" type="button" @click="selectTab('skills')">查看完整 Skill 列表</button>
            </p>
          </template>
          <div v-else class="settings-empty">MCP 服务未启用，启用后此处显示已开放工具列表。</div>
        </div>

        <h4 class="settings-subtitle">安装到龙虾</h4>
        <div class="settings-mcp-lobsters">
          <div class="settings-mcp-lobsters-head">
            <span>选择下方龙虾后点击“安装”，确认后选择“安装并重启”。完成后该龙虾可直接调用平台 Skill 工具；显示“已安装”即表示接入成功。</span>
            <button class="settings-button settings-button--ghost" type="button" :disabled="loading.lobsters" @click="loadLobsters">
              <el-icon><Refresh /></el-icon>
              刷新龙虾
            </button>
          </div>
          <div v-if="loading.lobsters" class="settings-empty">正在加载龙虾列表...</div>
          <div v-else-if="!lobsters.length" class="settings-empty">暂无龙虾，请先在龙虾基地创建一个龙虾智能体。</div>
          <div v-else class="settings-mcp-lobster-list">
            <article v-for="agent in lobsters" :key="agent.agent_id" class="settings-mcp-lobster-row">
              <div class="settings-mcp-lobster-main">
                <strong>{{ agent.agent_name }}</strong>
                <span>{{ agent.provider || '-' }} / {{ agent.model || '-' }} · {{ agent.status || '-' }}</span>
                <div class="settings-lobster-model-edit">
                  <span>{{ agent.provider || '-' }} /</span>
                  <el-select
                    v-if="lobsterModelOptions[agent.agent_id]?.length"
                    v-model="lobsterModelDrafts[agent.agent_id]"
                    class="settings-lobster-model-select"
                    filterable
                    allow-create
                    default-first-option
                    placeholder="选择模型"
                  >
                    <el-option
                      v-for="model in lobsterModelOptions[agent.agent_id]"
                      :key="model.id"
                      :label="model.owned_by ? `${model.id} · ${model.owned_by}` : model.id"
                      :value="model.id"
                    />
                  </el-select>
                  <input v-else v-model="lobsterModelDrafts[agent.agent_id]" :placeholder="agent.model || '输入模型名'" />
                  <button
                    class="settings-button settings-button--ghost"
                    type="button"
                    :disabled="loadingLobsterModels === agent.agent_id"
                    @click="handleLoadLobsterModels(agent)"
                  >
                    {{ loadingLobsterModels === agent.agent_id ? '加载中' : '加载模型' }}
                  </button>
                  <button
                    class="settings-button settings-button--ghost"
                    type="button"
                    :disabled="savingLobsterModel === agent.agent_id"
                    @click="handleSaveLobsterModel(agent)"
                  >
                    {{ savingLobsterModel === agent.agent_id ? '保存中' : '保存模型' }}
                  </button>
                </div>
              </div>
              <em :class="{ installed: isMcpInstalled(agent) }">{{ isMcpInstalled(agent) ? '已安装' : '未安装' }}</em>
              <button
                class="settings-button settings-button--ghost"
                type="button"
                :disabled="!mcpEnabled || loading.mcpInstall"
                @click="handleInstallMcpToLobster(agent)"
              >
                {{ installingLobsterId === agent.agent_id ? '安装中...' : isMcpInstalled(agent) ? '重新安装' : '安装' }}
              </button>
            </article>
          </div>
          <div v-if="lobsterStatus" class="settings-mcp-lobster-status">{{ lobsterStatus }}</div>
        </div>
      </section>
    </div>

    <el-dialog v-model="addUserDialog" title="新增用户" width="680px" class="settings-dialog" @closed="resetNewUser">
      <div class="settings-dialog-form">
        <label>
          <span>用户名</span>
          <el-input v-model="newUser.username" placeholder="zhangsan" />
        </label>
        <label>
          <span>显示名称</span>
          <el-input v-model="newUser.name" placeholder="张三" />
        </label>
        <label>
          <span>角色权限</span>
          <el-select v-model="newUser.role" class="settings-select">
            <el-option label="普通成员" value="member" />
            <el-option label="管理员" value="admin" />
            <el-option label="超级管理员" value="superadmin" />
          </el-select>
        </label>
        <label>
          <span>初始密码</span>
          <el-input v-model="newUser.password" type="password" show-password placeholder="至少 4 位" @keyup.enter="handleAddUser" />
        </label>
        <label>
          <span>绑定邮箱（选填）</span>
          <el-input v-model="newUser.email" type="email" :placeholder="newUser.username ? `默认：${companyEmailFor(newUser.username)}` : '默认：账号@chencytech.com'" />
        </label>
        <div class="new-user-organization-fields">
          <strong>组织架构关系（选填）</strong>
          <p>选择后会在用户管理中自动归入对应公司和部门；目录未收录时可直接录入。</p>
          <label>
            <span>公司</span>
            <el-select v-model="newUser.company" filterable allow-create clearable default-first-option placeholder="请选择或输入公司" class="settings-select" @change="handleNewUserCompanyChange">
              <el-option v-for="company in organizationCompanies" :key="company" :label="company" :value="company" />
            </el-select>
          </label>
          <label>
            <span>部门</span>
            <el-select v-model="newUser.department" filterable allow-create clearable default-first-option :disabled="!newUser.company.trim()" placeholder="请先选择公司" class="settings-select">
              <el-option v-for="department in newUserDepartments" :key="department" :label="department" :value="department" />
            </el-select>
          </label>
          <label>
            <span>岗位</span>
            <el-input v-model="newUser.position" placeholder="例如：交付工程师" />
          </label>
          <label>
            <span>工号</span>
            <el-input v-model="newUser.employee_id" placeholder="例如：120001" />
          </label>
        </div>
      </div>
      <template #footer>
        <button class="settings-button settings-button--ghost" type="button" @click="addUserDialog = false">取消</button>
        <button class="settings-button settings-button--primary" type="button" :disabled="loading.addUser" @click="handleAddUser">
          确认
        </button>
      </template>
    </el-dialog>

    <el-dialog v-model="organizationExcelDialog" title="组织架构同步（仅超级管理员）" width="min(680px,94vw)" class="settings-dialog">
      <div class="organization-excel-dialog">
        <p>下载当前组织架构表，维护最新组织信息后上传。系统以账号（用户名）为主键，自动匹配并调整公司、部门、岗位。</p>
        <p>支持直接上传岗位信息表：成本中心映射为公司，一级部门 / 二级部门组成层级，岗位及职位分类完整保存到名册。工号按文本保存，优先匹配已有工号；新工号可绑定唯一同名且尚无工号的账号，自动开户时同时保存工号。工号冲突、重名或非在职人员保留资料、等待核对，不覆盖已有身份。下载组织架构表可在“岗位名册”页查看全部已上传资料。</p>
        <el-checkbox v-model="organizationCreateUsers">自动为未开户人员创建普通用户</el-checkbox>
        <p>自动开户要求姓名、公司、部门完整且身份无冲突；岗位信息表仅为在职人员开户。新账号使用不可预测的随机密码，请在用户管理中设置密码后交付本人；不重置已有密码、不提升角色。关闭自动开户时仅保存名册和更新已匹配账号。</p>
        <div class="organization-excel-actions">
          <a class="settings-button settings-button--primary" :href="resourceUrl('/api/admin-organization/excel')" download>下载组织架构表</a>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.organizationImport" @click="organizationExcelPicker?.click()">{{ loading.organizationImport ? '上传处理中…' : '上传并更新组织信息' }}</button>
          <input ref="organizationExcelPicker" type="file" accept=".xlsx" hidden @change="handleOrganizationExcelUpload" />
        </div>
        <el-alert v-if="organizationExcelResult" :closable="false" :type="organizationExcelResult.errors.length || (organizationExcelResult.roster_check?.missing ?? 0) ? 'warning' : 'success'" :title="`已保存 ${organizationExcelResult.imported ?? organizationExcelResult.updated} 条；账号更新 ${organizationExcelResult.updated} 条，未变更 ${organizationExcelResult.skipped} 条，待绑定/核对 ${organizationExcelResult.pending ?? 0} 条，格式错误 ${organizationExcelResult.errors.length} 条${organizationExcelResult.roster_check?.applied ? `，未在本表 ${organizationExcelResult.roster_check.missing ?? 0} 人` : ''}`" style="margin-top:16px" />
        <p v-if="organizationExcelResult?.roster_check && !organizationExcelResult.roster_check.applied">{{ organizationExcelResult.roster_check.reason }}</p>
        <el-table v-if="organizationExcelResult?.roster_check?.missing_users?.length" :data="organizationExcelResult.roster_check.missing_users" max-height="260" style="margin-top:12px">
          <el-table-column prop="name" label="未在最新组织表中" width="160" />
          <el-table-column prop="employee_id" label="工号" width="120" />
          <el-table-column prop="username" label="账号" width="170" />
          <el-table-column prop="company" label="当前公司" min-width="190" />
          <el-table-column prop="department" label="当前部门" min-width="220" />
        </el-table>
        <el-table v-if="organizationExcelResult?.notices?.length" :data="organizationExcelResult.notices" max-height="260"><el-table-column prop="row" label="原表行号" width="110"/><el-table-column prop="error" label="已保存，待核对"/></el-table>
        <p v-if="organizationExcelResult">本次新建 {{ organizationExcelResult.created ?? 0 }} 个普通用户；账号首次使用前请设置密码。</p>
        <el-table v-if="organizationExcelResult?.created_users?.length" :data="organizationExcelResult.created_users" max-height="260"><el-table-column prop="name" label="姓名"/><el-table-column prop="username" label="新建账号"/></el-table>
        <el-table v-if="organizationExcelResult?.errors.length" :data="organizationExcelResult.errors" max-height="260" style="margin-top:12px">
          <el-table-column prop="row" label="Excel 行号" width="110" /><el-table-column prop="error" label="修正提示" min-width="260" />
        </el-table>
      </div>
      <template #footer><button class="settings-button settings-button--primary" type="button" @click="organizationExcelDialog = false">完成</button></template>
    </el-dialog>

    <el-dialog v-model="agentConfigDialog" title="编辑犇犇配置" width="840px" class="settings-dialog">
      <div class="settings-dialog-tabs">
        <button :class="{ active: agentConfigTab === 'prompts' }" type="button" @click="agentConfigTab = 'prompts'">系统提示词</button>
        <button :class="{ active: agentConfigTab === 'workflows' }" type="button" @click="agentConfigTab = 'workflows'">工作流</button>
      </div>
      <div v-if="loading.agentConfig" class="settings-empty">正在加载...</div>
      <div v-else class="agent-config-editor">
        <label v-for="item in agentLabels" v-show="agentConfigTab === 'prompts'" :key="`prompt-${item.key}`">
          <span>{{ item.label }}</span>
          <textarea v-model="agentPromptDraft[item.key]" rows="5"></textarea>
        </label>
        <label v-for="item in agentLabels.filter((item) => item.key !== 'dashboard')" v-show="agentConfigTab === 'workflows'" :key="`workflow-${item.key}`">
          <span>{{ item.label }}</span>
          <textarea v-model="agentWorkflowDraft[item.key]" rows="3"></textarea>
        </label>
      </div>
      <template #footer>
        <button class="settings-button settings-button--ghost" type="button" @click="agentConfigDialog = false">取消</button>
        <button class="settings-button settings-button--primary" type="button" :disabled="loading.saveAgentConfig" @click="handleSaveAgentConfig">保存配置</button>
      </template>
    </el-dialog>

    <el-dialog v-model="installMcpDialog" title="安装 MCP 服务" width="420px" class="settings-dialog" :close-on-click-modal="false">
      <p style="margin: 0 0 8px;">
        确认将 MCP 服务安装到「<strong>{{ pendingInstallAgent?.agent_name }}</strong>」？
      </p>
      <p style="margin: 0; color: var(--color-text-secondary, #888); font-size: 13px;">
        安装后需要重启龙虾才能使 MCP 工具生效。您也可以稍后手动重启。
      </p>
      <template #footer>
        <button class="settings-button settings-button--ghost" type="button" @click="installMcpDialog = false">取消</button>
        <button class="settings-button settings-button--ghost" type="button" :disabled="loading.mcpInstall" @click="confirmInstallMcp(false)">仅安装</button>
        <button class="settings-button settings-button--primary" type="button" :disabled="loading.mcpInstall" @click="confirmInstallMcp(true)">安装并重启</button>
      </template>
    </el-dialog>

    <el-dialog v-model="skillTestDialog" title="Skill 测试" width="880px" class="settings-dialog">
      <div class="skill-test-grid">
        <div class="skill-test-panel">
          <strong>{{ currentSkill?.name }}</strong>
          <span>{{ currentSkill?.title }}</span>
          <textarea v-model="skillTestArgs" spellcheck="false"></textarea>
          <textarea v-model="skillTestInstruction" placeholder="可输入自然语言测试要求，留空则直接使用 arguments。"></textarea>
          <label v-if="currentSkill && !currentSkill.safe" class="settings-check">
            <input v-model="skillConfirmUnsafe" type="checkbox" />
            <span>我确认执行该 Skill 测试，可能会生成文件、写入数据或发送内容</span>
          </label>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.skillTest" @click="handleRunSkillTest">运行测试</button>
        </div>
        <pre class="skill-test-result">{{ skillTestResult }}</pre>
      </div>
    </el-dialog>
  </section>
</template>
