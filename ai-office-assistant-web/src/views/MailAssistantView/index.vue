<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { CollectionTag, Paperclip, Promotion, Refresh, View } from '@element-plus/icons-vue'
import {
  getMailConfig,
  getMailboxDetail,
  listMailbox,
  mailboxAttachmentDownloadUrl,
  resourceUrl,
  sendAssistantMail,
  type MailAttachment,
  type MailMessage,
} from '../../services/personalWorkApi'
import './index.scss'

interface ComposeForm {
  to: string[]
  cc: string[]
  subject: string
  body: string
}

const mailboxLimit = ref('20')
const selectedUid = ref('')
const messages = ref<MailMessage[]>([])
const detail = ref<MailMessage | null>(null)
const attachments = ref<UploadUserFile[]>([])
const mailSignature = ref('')
const statusText = ref('')
const errorText = ref('')
const composeDrawerOpen = ref(false)
const compose = reactive<ComposeForm>({ to: [], cc: [], subject: '', body: '' })
const loading = reactive({
  mailbox: false,
  detail: false,
  send: false,
})

const selectedMessage = computed(() => messages.value.find((message) => message.uid === selectedUid.value) || null)
const mailDetailHtml = computed(() => (detail.value?.body_html ? normalizeMailBodyHtml(detail.value.body_html) : ''))
// 预览展示签名，实际发送仍交由后端统一拼接。
const previewBody = computed(() => {
  const body = compose.body.trimEnd()
  const signature = mailSignature.value.trim()
  if (!signature || body.endsWith(signature)) return body || '暂无正文内容'
  return body ? `${body}\n\n${signature}` : signature
})

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

function formatFileSize(bytes?: number) {
  const size = Number(bytes || 0)
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function shouldRewriteMailResource(value: string) {
  return Boolean(value.trim()) && !/^(https?:|\/\/|data:|blob:|cid:|mailto:|tel:|#)/i.test(value.trim())
}

function normalizeMailResourcePath(value: string) {
  const trimmed = value.trim()
  if (trimmed.startsWith('/personal-office-assistant/')) return trimmed.slice('/personal-office-assistant'.length)
  return trimmed.startsWith('/') ? trimmed : `/${trimmed.replace(/^\.?\//, '')}`
}

// 将邮件正文中的相对资源地址改为办公后端可访问地址。
function normalizeMailBodyHtml(html: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.body.querySelectorAll<HTMLElement>('[src], [href]').forEach((node) => {
    ;(['src', 'href'] as const).forEach((attr) => {
      const value = node.getAttribute(attr)
      if (value && shouldRewriteMailResource(value)) node.setAttribute(attr, resourceUrl(normalizeMailResourcePath(value)))
    })
  })
  return doc.body.innerHTML
}

function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '')
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

function downloadMailAttachment(file: MailAttachment) {
  if (!file.download_url) {
    ElMessage.warning('该附件暂无下载地址')
    return
  }
  window.open(mailboxAttachmentDownloadUrl(file.download_url), '_blank')
}

async function loadSignature() {
  try {
    const config = await getMailConfig()
    mailSignature.value = config.email_signature || ''
  } catch {
    mailSignature.value = ''
  }
}

async function loadMailbox(refresh = false) {
  if (loading.mailbox) return
  loading.mailbox = true
  errorText.value = ''
  detail.value = null
  try {
    const result = await listMailbox(mailboxLimit.value, refresh)
    messages.value = result.messages || []
    selectedUid.value = ''
    statusText.value = result.cached ? '已从本地缓存加载，点击刷新可获取最新邮件。' : ''
  } catch (error) {
    messages.value = []
    errorText.value = errorMessage(error)
  } finally {
    loading.mailbox = false
  }
}

async function openMail(uid: string) {
  if (!uid || loading.detail) return
  selectedUid.value = uid
  loading.detail = true
  try {
    const result = await getMailboxDetail(uid)
    detail.value = result.message
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.detail = false
  }
}

function clearCompose() {
  compose.to = []
  compose.cc = []
  compose.subject = ''
  compose.body = ''
  attachments.value = []
}

async function sendMail() {
  if (!compose.to.length) {
    ElMessage.warning('请填写收件人')
    return
  }
  if (loading.send) return
  loading.send = true
  try {
    const files = []
    for (const file of attachments.value) {
      if (!file.raw) continue
      files.push({
        name: file.raw.name,
        type: file.raw.type || 'application/octet-stream',
        content: await readFileAsBase64(file.raw),
      })
    }
    const result = await sendAssistantMail({
      to: compose.to.join(';'),
      cc: compose.cc.join(';'),
      subject: compose.subject,
      body: compose.body,
      attachments: files,
    })
    ElMessage.success(result.message || '邮件已发送')
    composeDrawerOpen.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.send = false
  }
}

onMounted(async () => {
  await loadSignature()
  await loadMailbox()
})
</script>

<template>
  <section class="workspace-main mail-main">
    <header class="mail-page-head">
      <div>
        <h1>邮件助手</h1>
        <p>查看收件箱、阅读邮件、发送普通邮件</p>
      </div>
      <div class="mail-page-actions">
        <el-select v-model="mailboxLimit" class="mail-limit-select" @change="loadMailbox(false)">
          <el-option label="最近 10 封" value="10" />
          <el-option label="最近 20 封" value="20" />
          <el-option label="最近 50 封" value="50" />
        </el-select>
        <button class="mail-button mail-button--ghost" type="button" :disabled="loading.mailbox" @click="loadMailbox(true)">
          <el-icon><Refresh /></el-icon>
          {{ loading.mailbox ? '刷新中' : '刷新' }}
        </button>
        <button class="mail-button mail-button--primary" type="button" @click="composeDrawerOpen = true">
          <el-icon><Promotion /></el-icon>
          发送邮件
        </button>
      </div>
    </header>

    <div class="mail-workspace">
      <section class="mail-card mailbox-card">
        <div class="mail-section-head">
          <div>
            <h3>收件箱</h3>
            <span>{{ statusText || `${messages.length} 封邮件` }}</span>
          </div>
        </div>

        <div v-if="errorText" class="mail-empty mail-empty--error">{{ errorText }}</div>
        <div v-else-if="loading.mailbox" class="mail-empty">正在读取收件箱...</div>
        <div v-else-if="messages.length" class="mailbox-list">
          <button
            v-for="message in messages"
            :key="message.uid"
            :class="['mailbox-item', { active: message.uid === selectedUid }]"
            type="button"
            @click="openMail(message.uid)"
          >
            <span class="mailbox-subject">{{ message.subject || '无主题' }}</span>
            <span class="mailbox-meta">{{ message.from || '未知发件人' }}</span>
            <span class="mailbox-preview">{{ message.preview || '点击邮件查看正文' }}</span>
            <span class="mailbox-bottom">
              <time>{{ message.date || '暂无时间' }}</time>
              <em v-if="message.attachments?.length">{{ message.attachments.length }} 个附件</em>
            </span>
          </button>
        </div>
        <div v-else class="mail-empty">暂无邮件，或当前邮箱没有可读取的收件箱邮件。</div>
      </section>

      <section class="mail-card mail-detail-card">
        <div class="mail-section-head">
          <div>
            <h3>邮件详情</h3>
            <span>{{ selectedMessage?.subject || '选择左侧邮件查看详情' }}</span>
          </div>
          <el-icon><View /></el-icon>
        </div>

        <div v-if="loading.detail" class="mail-empty">正在读取邮件详情...</div>
        <article v-else-if="detail" class="mail-detail">
          <header>
            <h3>{{ detail.subject || '无主题' }}</h3>
            <p>发件人：{{ detail.from || '-' }}</p>
            <p>收件人：{{ detail.to || '-' }}</p>
            <p>时间：{{ detail.date || '-' }}</p>
            <div class="mail-attachments">
              <button
                v-for="file in detail.attachments || []"
                :key="file.name"
                class="mail-attachment"
                type="button"
                @click="downloadMailAttachment(file)"
              >
                <el-icon><Paperclip /></el-icon>
                {{ file.name }}{{ file.size ? ` · ${formatFileSize(file.size)}` : '' }}
              </button>
              <em v-if="!detail.attachments?.length">无附件</em>
            </div>
          </header>
          <div v-if="mailDetailHtml" class="mail-detail-body" v-html="mailDetailHtml"></div>
          <div v-else class="mail-detail-body mail-detail-body--plain">{{ detail.body || detail.preview || '暂无可读取的文本正文' }}</div>
        </article>
        <div v-else class="mail-empty">暂无选中邮件。</div>
      </section>
    </div>

    <el-drawer v-model="composeDrawerOpen" class="mail-compose-drawer" title="发送邮件" size="720px">
      <div class="mail-compose-grid mail-compose-grid--drawer">
        <div class="mail-compose-form">
          <div class="mail-compose-field">
            <span>收件人</span>
            <el-select
              v-model="compose.to"
              multiple
              filterable
              allow-create
              default-first-option
              reserve-keyword
              placeholder="输入邮箱后回车添加"
            />
          </div>
          <div class="mail-compose-field">
            <span>抄送</span>
            <el-select
              v-model="compose.cc"
              multiple
              filterable
              allow-create
              default-first-option
              reserve-keyword
              placeholder="可选，输入邮箱后回车添加"
            />
          </div>
          <label class="mail-compose-full">
            <span>主题</span>
            <input v-model="compose.subject" type="text" placeholder="请输入邮件主题" />
          </label>
          <label class="mail-compose-full">
            <span>正文</span>
            <textarea v-model="compose.body" placeholder="请输入邮件正文"></textarea>
          </label>
          <div class="mail-compose-field mail-compose-full">
            <span>附件</span>
            <el-upload v-model:file-list="attachments" class="mail-upload" multiple :auto-upload="false">
              <el-button type="primary" plain>
                <el-icon><Paperclip /></el-icon>
                选择附件
              </el-button>
              <template #tip>
                <div class="mail-upload-tip">{{ attachments.length ? `已选择 ${attachments.length} 个附件` : '未添加附件' }}</div>
              </template>
            </el-upload>
          </div>
        </div>
        <div class="mail-compose-preview">
          <span>
            <el-icon><CollectionTag /></el-icon>
            正文预览
          </span>
          <pre>{{ previewBody }}</pre>
        </div>
      </div>
      <template #footer>
        <div class="mail-compose-actions">
          <button class="mail-button mail-button--ghost" type="button" @click="clearCompose">清空</button>
          <button class="mail-button mail-button--primary" type="button" :disabled="loading.send" @click="sendMail">
            <el-icon><Promotion /></el-icon>
            {{ loading.send ? '发送中' : '发送邮件' }}
          </button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>
