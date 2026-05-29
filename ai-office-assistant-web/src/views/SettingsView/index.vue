<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete,
  EditPen,
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
import type { MenuId } from '../../layout/menu'
import {
  addAdminUser,
  deleteAdminUser,
  getAdminConfig,
  getAgentConfig,
  getAgentOrchestration,
  getMailConfig,
  listAdminModels,
  listAdminUsers,
  listSkills,
  resourceUrl,
  runSkillTest,
  saveAdminConfig,
  saveAgentConfig,
  saveMailConfig,
  saveServerConfig,
  testAdminModel,
  testMailConfig,
  updateAdminUser,
  type AdminConfig,
  type AgentConfig,
  type MailConfig,
  type SkillDefinition,
  type User,
} from '../../services/personalWorkApi'
import './index.scss'

type SettingsTab = 'mailconfig' | 'config' | 'skills' | 'usermanage'

const props = defineProps<{
  activeMenu: MenuId
}>()

const emit = defineEmits<{
  selectMenu: [value: MenuId]
}>()

const user = computed(() => authState.user)
const activeTab = ref<SettingsTab>('mailconfig')
const loadedTabs = reactive<Record<SettingsTab, boolean>>({
  mailconfig: false,
  config: false,
  skills: false,
  usermanage: false,
})
const loading = reactive({
  mailConfig: false,
  saveMail: false,
  testMail: false,
  adminConfig: false,
  saveAdmin: false,
  models: false,
  testModel: false,
  saveServer: false,
  skills: false,
  orchestration: false,
  agentConfig: false,
  saveAgentConfig: false,
  skillTest: false,
  users: false,
  addUser: false,
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
const mailMeta = reactive({
  smtp_password_masked: '',
  imap_password_masked: '',
  smtp_host: '',
  smtp_port: 465,
  smtp_ssl: true,
  imap_host: '',
  imap_port: 993,
  imap_ssl: true,
})
const mailReference = ref<Partial<MailConfig>>({})

const adminForm = reactive({
  assistant_api_url: '',
  assistant_api_key: '',
  assistant_model: '',
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

const users = ref<User[]>([])
const userDrafts = reactive<Record<string, { name: string; password: string; role: User['role'] }>>({})
const newUser = reactive<{ username: string; name: string; password: string; role: User['role'] }>({
  username: '',
  name: '',
  password: '',
  role: 'member',
})

const agentLabels = [
  { key: 'weekly', label: '周报助手' },
  { key: 'trip', label: '出差报告助手' },
  { key: 'diary', label: '日记助手' },
  { key: 'mailassistant', label: '邮件助手' },
  { key: 'news', label: '资讯助手' },
  { key: 'forum', label: '论坛助手' },
  { key: 'dashboard', label: '总助手' },
]

const tabItems = computed(() => {
  const items: Array<{ id: SettingsTab; label: string; icon: Component; visible: boolean }> = [
    { id: 'mailconfig', label: '邮件配置', icon: Message, visible: true },
    { id: 'config', label: '系统配置', icon: Setting, visible: !!user.value?.is_admin },
    { id: 'skills', label: '系统 Skill', icon: Tools, visible: !!user.value?.is_superadmin },
    { id: 'usermanage', label: '用户管理', icon: UserFilled, visible: !!user.value?.is_superadmin },
  ]
  return items.filter((item) => item.visible)
})
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
  return !!user.value?.is_superadmin
}

function tabPermissionText(tab: SettingsTab) {
  if (tab === 'config') return '系统配置仅管理员可访问。'
  if (tab === 'skills') return '系统 Skill 仅超级管理员可访问。'
  if (tab === 'usermanage') return '用户管理仅超级管理员可访问。'
  return '当前账号无法访问该模块。'
}

function tabFromMenu(menu: MenuId): SettingsTab {
  if (menu === 'mailconfig') return 'mailconfig'
  if (menu === 'skills') return 'skills'
  if (menu === 'usermanage') return 'usermanage'
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
  mailMeta.smtp_password_masked = data.smtp_password_masked || '未配置'
  mailMeta.imap_password_masked = data.imap_password_masked || '未配置'
  mailMeta.smtp_host = data.smtp_host || ''
  mailMeta.smtp_port = data.smtp_port || 465
  mailMeta.smtp_ssl = !!data.smtp_ssl
  mailMeta.imap_host = data.imap_host || ''
  mailMeta.imap_port = data.imap_port || 993
  mailMeta.imap_ssl = !!data.imap_ssl
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
    email_signature: mailForm.email_signature,
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
    const result = await testMailConfig()
    await loadMailConfig()
    ElMessage.success(result.message || '邮箱配置测试成功')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.testMail = false
  }
}

function applyAdminConfig(data: AdminConfig) {
  adminForm.assistant_api_url = data.assistant_api_url || ''
  adminForm.assistant_api_key = ''
  adminForm.assistant_model = data.assistant_model || 'MiniMax-M2.7'
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
}

function adminConfigPayload() {
  return {
    assistant_api_url: adminForm.assistant_api_url,
    assistant_api_key: adminForm.assistant_api_key,
    assistant_model: adminForm.assistant_model,
    assistant_prompt: adminForm.assistant_prompt,
  }
}

async function handleSaveAdminConfig() {
  loading.saveAdmin = true
  try {
    const result = await saveAdminConfig(adminConfigPayload())
    applyAdminConfig(result.config)
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
      userDrafts[item.username] = { name: item.name || item.username, password: '', role: item.role }
    }
    loadedTabs.usermanage = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.users = false
  }
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
    })
    users.value = result.users || []
    newUser.username = ''
    newUser.name = ''
    newUser.password = ''
    newUser.role = 'member'
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
      role: draft.role,
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

async function loadActiveTab() {
  // 无权限 tab 只展示提示，不发起管理接口请求。
  if (!canOpenTab(activeTab.value)) return
  if (activeTab.value === 'mailconfig' && !loadedTabs.mailconfig) await loadMailConfig()
  if (activeTab.value === 'config' && !loadedTabs.config) await loadAdminConfig()
  if (activeTab.value === 'skills' && !loadedTabs.skills) await loadSkills()
  if (activeTab.value === 'usermanage' && !loadedTabs.usermanage) await loadUsers()
}

watch(
  () => props.activeMenu,
  (menu) => {
    const nextTab = tabFromMenu(menu)
    activeTab.value = nextTab
    void loadActiveTab()
  },
)

watch(activeTab, () => {
  void loadActiveTab()
})

onMounted(() => {
  activeTab.value = tabFromMenu(props.activeMenu)
  void loadActiveTab()
})
</script>

<template>
  <section class="workspace-main settings-main">
    <header class="settings-page-head">
      <div>
        <span class="settings-kicker">
          <el-icon><Setting /></el-icon>
          设置
        </span>
        <h2>设置中心</h2>
        <p>管理邮箱账号、系统参数、Skill 能力和用户权限</p>
      </div>
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
            <h3>我的邮箱账户</h3>
            <span>发送邮件需要 SMTP；读取收件箱需要 IMAP。</span>
          </div>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.mailConfig" @click="loadMailConfig">
            <el-icon><Refresh /></el-icon>
            重新读取
          </button>
        </div>

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
          <label class="settings-field-full">
            <span>邮件签名模板</span>
            <textarea v-model="mailForm.email_signature" placeholder="留空则使用默认签名"></textarea>
          </label>
        </div>
        <div class="settings-actions">
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.saveMail" @click="handleSaveMailConfig">保存我的邮件配置</button>
          <button class="settings-button settings-button--primary" type="button" :disabled="loading.testMail" @click="handleTestMailConfig">测试我的邮箱配置</button>
        </div>
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
            <span>管理系统用户、角色权限和密码。</span>
          </div>
          <button class="settings-button settings-button--ghost" type="button" :disabled="loading.users" @click="loadUsers">
            <el-icon><Refresh /></el-icon>
            刷新
          </button>
        </div>

        <div class="settings-grid user-create-grid">
          <label>
            <span>用户名</span>
            <input v-model="newUser.username" placeholder="zhangsan" />
          </label>
          <label>
            <span>显示名称</span>
            <input v-model="newUser.name" placeholder="张三" />
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
            <input v-model="newUser.password" type="password" placeholder="至少 4 位" />
          </label>
          <div class="settings-actions">
            <button class="settings-button settings-button--primary" type="button" :disabled="loading.addUser" @click="handleAddUser">
              <el-icon><Plus /></el-icon>
              新增用户
            </button>
          </div>
        </div>

        <div v-if="loading.users" class="settings-empty">正在加载用户列表...</div>
        <div v-else class="user-list">
          <article v-for="item in users" :key="item.username" class="user-card">
            <div class="user-card-head">
              <span>
                <el-icon><UserFilled /></el-icon>
              </span>
              <div>
                <strong>{{ item.username }}</strong>
                <em>{{ roleLabel(item.role) }}</em>
              </div>
            </div>
            <label>
              <span>显示名称</span>
              <input v-model="userDrafts[item.username].name" />
            </label>
            <label>
              <span>新密码</span>
              <input v-model="userDrafts[item.username].password" type="password" placeholder="留空则不修改" />
            </label>
            <label>
              <span>角色</span>
              <el-select v-model="userDrafts[item.username].role" class="settings-select">
                <el-option label="普通成员" value="member" />
                <el-option label="管理员" value="admin" />
                <el-option label="超级管理员" value="superadmin" />
              </el-select>
            </label>
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
          </article>
          <div v-if="!users.length" class="settings-empty">暂无用户。</div>
        </div>
      </section>
    </div>

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
