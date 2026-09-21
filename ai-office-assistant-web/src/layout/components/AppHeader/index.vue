<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ArrowDown, Bell, Loading, Lock, QuestionFilled, Search, Tickets, User as UserIcon } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import HelpCenter from '../HelpCenter/index.vue'
import mascotImage from '../../../assets/mascot.png'
import { authState } from '../../../services/authSession'
import { activeBackgroundTaskCount, backgroundTasks } from '../../../utils/backgroundTasks'
import type { MenuId } from '../../menu'
import { changePassword, fetchWechatAuthStatus, resourceUrl, saveProfile, type User } from '../../../services/personalWorkApi'

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  logout: []
  navigate: [value: MenuId]
}>()

const keyword = ref('')
const helpCenter = ref<InstanceType<typeof HelpCenter> | null>(null)
const profileOpen = ref(false)
const passwordOpen = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)
const avatarFileInput = ref<HTMLInputElement | null>(null)
const avatarPreview = ref('')
const wechatAuthReminder = ref('')
let wechatAuthTimer: ReturnType<typeof setInterval> | null = null
const profileForm = reactive({
  name: '',
  bio: '',
  hobbies: '',
  avatar_data: '',
  avatar_preset: '',
})
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const avatarSrc = computed(() => (props.user.avatar_url ? resourceUrl(props.user.avatar_url) : mascotImage))
const displayName = computed(() => props.user.name || props.user.username)
const taskElapsed = (startedAt: number) => `${Math.max(1, Math.floor((Date.now() - startedAt) / 1000))} 秒`

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('读取头像失败'))
    reader.readAsDataURL(file)
  })
}

function openProfileDialog() {
  profileForm.name = props.user.name || props.user.username
  profileForm.bio = props.user.bio || ''
  profileForm.hobbies = Array.isArray(props.user.hobbies) ? props.user.hobbies.join('、') : props.user.hobbies || ''
  profileForm.avatar_data = ''
  profileForm.avatar_preset = ''
  avatarPreview.value = avatarSrc.value
  if (avatarFileInput.value) avatarFileInput.value.value = ''
  profileOpen.value = true
}

function openPasswordDialog() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordOpen.value = true
}

async function updateAvatar(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  // 后端头像上限为 3MB，前端先阻止超限文件。
  if (file.size > 3 * 1024 * 1024) {
    ElMessage.warning('头像文件不能超过 3MB')
    if (avatarFileInput.value) avatarFileInput.value.value = ''
    return
  }
  profileForm.avatar_data = await readFileAsDataUrl(file)
  profileForm.avatar_preset = ''
  avatarPreview.value = profileForm.avatar_data
}

function useAssistantAvatar() {
  profileForm.avatar_data = ''
  profileForm.avatar_preset = 'assistant'
  avatarPreview.value = mascotImage
  if (avatarFileInput.value) avatarFileInput.value.value = ''
}

async function handleSaveProfile() {
  if (!profileForm.name.trim()) {
    ElMessage.warning('请填写显示名称')
    return
  }
  savingProfile.value = true
  try {
    const result = await saveProfile({
      name: profileForm.name,
      bio: profileForm.bio,
      hobbies: profileForm.hobbies,
      avatar_data: profileForm.avatar_data,
      avatar_preset: profileForm.avatar_preset,
    })
    // 保存成功后同步会话用户，顶部头像和名称立即刷新。
    authState.user = result.user
    avatarPreview.value = result.user.avatar_url ? resourceUrl(result.user.avatar_url) : mascotImage
    profileForm.avatar_data = ''
    profileForm.avatar_preset = ''
    if (avatarFileInput.value) avatarFileInput.value.value = ''
    ElMessage.success('个人资料已保存')
    profileOpen.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingProfile.value = false
  }
}

async function handleChangePassword() {
  if (!passwordForm.old_password || !passwordForm.new_password) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (passwordForm.new_password.length < 4) {
    ElMessage.warning('新密码至少 4 位')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await changePassword(passwordForm.old_password, passwordForm.new_password)
    ElMessage.success('密码已修改')
    passwordOpen.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingPassword.value = false
  }
}

function handleUserCommand(command: 'profile' | 'password' | 'logout') {
  if (command === 'logout') {
    emit('logout')
    return
  }
  if (command === 'password') openPasswordDialog()
  else openProfileDialog()
}

async function checkWechatAuthorization() {
  try {
    const result = await fetchWechatAuthStatus()
    wechatAuthReminder.value = result.expired ? result.message : ''
  } catch {
    // 通知检查失败不打断正常办公；下一次轮询会重试。
  }
}

function openWechatLogin() {
  window.open('/personal-office-assistant/wechat-article/', '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  void checkWechatAuthorization()
  wechatAuthTimer = setInterval(() => void checkWechatAuthorization(), 5 * 60 * 1000)
})

onUnmounted(() => {
  if (wechatAuthTimer) clearInterval(wechatAuthTimer)
})
</script>

<template>
  <header class="app-header">
    <el-input v-model="keyword" class="toolbar-search" size="large" placeholder="搜索文档、功能、联系人或输入快捷指令 /">
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>
    <div class="header-actions">
      <el-popover v-if="activeBackgroundTaskCount" placement="bottom-end" :width="320" trigger="click">
        <template #reference>
          <el-badge :value="activeBackgroundTaskCount" type="primary">
            <el-button class="header-tool-button header-task-button" circle size="large" aria-label="进行中的后台任务">
              <el-icon class="header-task-spinner"><Loading /></el-icon>
            </el-button>
          </el-badge>
        </template>
        <div class="background-task-popover">
          <strong>正在执行 {{ activeBackgroundTaskCount }} 项任务</strong>
          <ul>
            <li v-for="task in backgroundTasks" :key="task.id"><el-icon><Loading /></el-icon><span>{{ task.label }}</span><em>{{ taskElapsed(task.startedAt) }}</em></li>
          </ul>
          <p>切换页面不会中断这些任务。</p>
        </div>
      </el-popover>
      <el-popover v-if="wechatAuthReminder" placement="bottom-end" :width="330" trigger="click">
        <template #reference>
          <el-badge is-dot type="danger">
            <el-button class="header-tool-button" circle size="large" :icon="Bell" aria-label="公众号授权提醒" />
          </el-badge>
        </template>
        <div class="wechat-auth-reminder">
          <strong>公众号采集需要重新授权</strong>
          <p>{{ wechatAuthReminder }}</p>
          <el-button type="primary" size="small" @click="openWechatLogin">去重新扫码</el-button>
        </div>
      </el-popover>
      <el-tooltip content="工单系统 · 提交产品建议与问题" placement="bottom">
        <el-button class="header-tool-button" circle size="large" :icon="Tickets" aria-label="工单系统" @click="emit('navigate', 'workorder')" />
      </el-tooltip>
      <el-tooltip content="帮助中心" placement="bottom">
        <el-button class="header-tool-button" circle size="large" :icon="QuestionFilled" aria-label="帮助中心" @click="helpCenter?.show()" />
      </el-tooltip>
      <el-tooltip content="账户菜单" placement="bottom">
        <el-dropdown trigger="click" @command="handleUserCommand">
          <button class="header-user-button" type="button" aria-haspopup="menu">
            <span class="header-user-avatar">
              <img :src="avatarSrc" alt="用户头像" />
              <span aria-hidden="true"></span>
            </span>
            <strong>{{ displayName }}</strong>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu class="header-user-menu">
              <el-dropdown-item command="profile">修改信息</el-dropdown-item>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-tooltip>
    </div>

    <el-dialog v-model="profileOpen" title="个人资料" width="720px" class="profile-dialog">
      <div class="profile-editor">
        <div class="profile-editor__avatar">
          <img :src="avatarPreview || avatarSrc" alt="用户头像预览" />
          <button class="profile-action-button" type="button" @click="useAssistantAvatar">使用助手头像</button>
        </div>
        <div class="profile-editor__form">
          <label>
            <span>对外显示名称</span>
            <input v-model="profileForm.name" maxlength="40" type="text" placeholder="你的姓名或昵称" />
          </label>
          <label>
            <span>上传头像</span>
            <input ref="avatarFileInput" type="file" accept="image/png,image/jpeg,image/webp" @change="updateAvatar" />
            <em>支持 PNG、JPEG、WebP，大小不超过 3MB。</em>
          </label>
          <label>
            <span>对外介绍</span>
            <textarea v-model="profileForm.bio" maxlength="500" placeholder="例如：负责项目、擅长方向、工作职责等"></textarea>
          </label>
          <label>
            <span>个人爱好</span>
            <textarea v-model="profileForm.hobbies" maxlength="300" placeholder="例如：轨道交通、AI 工具、阅读、跑步..."></textarea>
          </label>
          <div class="profile-editor__actions">
            <button class="profile-action-button profile-action-button--ghost" type="button" @click="profileOpen = false">取消</button>
            <button class="profile-action-button profile-action-button--primary" type="button" :disabled="savingProfile" @click="handleSaveProfile">
              <el-icon><UserIcon /></el-icon>
              {{ savingProfile ? '保存中' : '保存资料' }}
            </button>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="passwordOpen" title="修改密码" width="440px" class="profile-dialog">
      <div class="password-editor">
        <label>
          <span>原密码</span>
          <input v-model="passwordForm.old_password" type="password" autocomplete="current-password" placeholder="输入当前密码" />
        </label>
        <label>
          <span>新密码</span>
          <input v-model="passwordForm.new_password" type="password" autocomplete="new-password" placeholder="至少 4 位" />
        </label>
        <label>
          <span>确认新密码</span>
          <input v-model="passwordForm.confirm_password" type="password" autocomplete="new-password" placeholder="再次输入新密码" @keyup.enter="handleChangePassword" />
        </label>
        <div class="password-editor__actions">
          <button class="profile-action-button profile-action-button--ghost" type="button" @click="passwordOpen = false">取消</button>
          <button class="profile-action-button profile-action-button--primary" type="button" :disabled="savingPassword" @click="handleChangePassword">
            <el-icon><Lock /></el-icon>
            {{ savingPassword ? '修改中' : '确认修改' }}
          </button>
        </div>
      </div>
    </el-dialog>

    <HelpCenter ref="helpCenter" @navigate="emit('navigate', $event)" />
  </header>
</template>
