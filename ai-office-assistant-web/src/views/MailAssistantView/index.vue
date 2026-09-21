<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadUserFile } from 'element-plus'
import { CollectionTag, Paperclip, Promotion, Refresh, View } from '@element-plus/icons-vue'
import {
  getMailConfig,
  getMailboxDetail,
  getSentMailDetail,
  listMailbox,
  listSentMail,
  markMailboxRead,
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

type MailboxMode = 'inbox' | 'sent'
type InboxReadStatus = 'all' | 'unread' | 'read'

const mailboxLimit = ref('20')
const mailboxMode = ref<MailboxMode>('inbox')
const inboxReadStatus = ref<InboxReadStatus>('all')
const selectedUid = ref('')
const messages = ref<MailMessage[]>([])
const inboxHasMore = ref(false)
const inboxTotal = ref(0)
const inboxCounts = reactive({ all: 0, unread: 0, read: 0 })
const detail = ref<MailMessage | null>(null)
const attachments = ref<UploadUserFile[]>([])
const mailSignature = ref('')
const mailAccountAddress = ref('')
const statusText = ref('')
const errorText = ref('')
const composeDrawerOpen = ref(false)
const compose = reactive<ComposeForm>({ to: [], cc: [], subject: '', body: '' })
const loading = reactive({
  mailbox: false,
  detail: false,
  send: false,
})
let mailboxRequestVersion = 0
let mailboxRequestController: AbortController | null = null

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

// 正文中的内嵌图片会在邮件打开后才由浏览器请求。列表已带回缓存正文时，
// 先静默预热本地邮件资源，用户点击后可直接复用浏览器缓存。
function warmMailInlineResources(mailList: MailMessage[]) {
  const sources = new Set<string>()
  for (const message of mailList) {
    if (!message.body_html || sources.size >= 36) continue
    const doc = new DOMParser().parseFromString(message.body_html, 'text/html')
    doc.querySelectorAll('img[src]').forEach((image) => {
      const src = image.getAttribute('src')?.trim() || ''
      if (/^\/(?:personal-office-assistant\/)?api\/mailbox-part\?/i.test(src)) {
        sources.add(resourceUrl(normalizeMailResourcePath(src)))
      }
    })
  }
  sources.forEach((src) => {
    const image = new Image()
    image.decoding = 'async'
    image.src = src
  })
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
  const downloadUrl = file.download_url || ''
  // 收件箱原始附件不能复用报告文件下载口，否则后端会按报告目录查找并返回 404。
  if (!downloadUrl || /(?:^|\/)download\?/.test(downloadUrl)) {
    ElMessage.warning('当前仅支持查看附件信息，暂不支持下载收件箱原始附件')
    return
  }
  window.open(mailboxAttachmentDownloadUrl(downloadUrl), '_blank')
}

function parseMailAddresses(value?: string) {
  const source = String(value || '')
  const matched = source.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi)
  return matched ? matched.map((item) => item.trim()) : []
}

function uniqueMailAddresses(addresses: string[], excluded: string[] = []) {
  const excludedSet = new Set(excluded.map((item) => item.toLowerCase()))
  const seen = new Set<string>()
  return addresses.filter((address) => {
    const normalized = address.toLowerCase()
    if (!normalized || excludedSet.has(normalized) || seen.has(normalized)) return false
    seen.add(normalized)
    return true
  })
}

function replySubject(subject?: string) {
  const text = String(subject || '无主题').trim()
  return /^re\s*:/i.test(text) ? text : `Re: ${text}`
}

function plainMailText(message: MailMessage) {
  if (message.body?.trim()) return message.body.trim()
  if (message.body_html) return new DOMParser().parseFromString(message.body_html, 'text/html').body.textContent?.trim() || message.preview || ''
  return message.preview || ''
}

function startReply(mode: 'sender' | 'all') {
  const message = detail.value
  if (!message) {
    ElMessage.warning('请先选择需要回复的邮件')
    return
  }
  const selfAddresses = parseMailAddresses(mailAccountAddress.value)
  const sender = uniqueMailAddresses(parseMailAddresses(message.from), selfAddresses)
  if (!sender.length) {
    ElMessage.warning('未识别到可回复的发件人邮箱')
    return
  }
  const recipientPool = mode === 'all'
    ? [...sender, ...parseMailAddresses(message.to), ...parseMailAddresses(message.cc)]
    : sender
  compose.to = uniqueMailAddresses(recipientPool, selfAddresses)
  compose.cc = mode === 'all'
    ? uniqueMailAddresses(parseMailAddresses(message.cc), [...selfAddresses, ...compose.to])
    : []
  compose.subject = replySubject(message.subject)
  compose.body = `\n\n--- 原始邮件 ---\n发件人：${message.from || '-'}\n时间：${message.date || '-'}\n主题：${message.subject || '无主题'}\n\n${plainMailText(message)}`
  attachments.value = []
  composeDrawerOpen.value = true
}

async function loadSignature() {
  try {
    const config = await getMailConfig()
    mailSignature.value = config.email_signature || ''
    mailAccountAddress.value = config.user_email || config.smtp_user || config.imap_user || ''
  } catch {
    mailSignature.value = ''
    mailAccountAddress.value = ''
  }
}

async function loadMailbox(refresh = false, append = false) {
  mailboxRequestController?.abort()
  const requestController = new AbortController()
  mailboxRequestController = requestController
  const requestVersion = ++mailboxRequestVersion
  const requestedMode = mailboxMode.value
  loading.mailbox = true
  errorText.value = ''
  if (!append) detail.value = null
  try {
    const result = requestedMode === 'sent'
      ? await listSentMail(mailboxLimit.value, requestController.signal)
      : await listMailbox(mailboxLimit.value, refresh, append ? messages.value.length : 0, inboxReadStatus.value, requestController.signal)
    if (requestVersion !== mailboxRequestVersion || requestedMode !== mailboxMode.value) return
    messages.value = append ? [...messages.value, ...(result.messages || [])] : (result.messages || [])
    if (requestedMode === 'inbox') warmMailInlineResources(messages.value)
    if (!append) selectedUid.value = ''
    inboxHasMore.value = requestedMode === 'inbox' && Boolean(result.has_more)
    inboxTotal.value = requestedMode === 'inbox' ? Number(result.total || messages.value.length) : messages.value.length
    if (requestedMode === 'inbox') {
      const fallbackUnread = messages.value.filter((message) => message.is_read === false).length
      const counts = result.counts || {
        all: inboxTotal.value,
        unread: Number(result.unread_count ?? fallbackUnread),
        read: Number(result.read_count ?? Math.max(0, inboxTotal.value - fallbackUnread)),
      }
      inboxCounts.all = Number(counts.all || 0)
      inboxCounts.unread = Number(counts.unread || 0)
      inboxCounts.read = Number(counts.read || 0)
    }
    statusText.value = requestedMode === 'sent'
      ? '展示通过邮件助手发送成功的本地记录。'
      : (result.background_sync
          ? `近一个月邮件已缓存${result.period_start ? `（自 ${result.period_start} 起）` : ''} · 点击“刷新”同步最新邮件`
          : (result.cached ? '已从本地缓存加载，点击刷新可获取最新邮件。' : ''))
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return
    if (requestVersion !== mailboxRequestVersion || requestedMode !== mailboxMode.value) return
    messages.value = []
    errorText.value = errorMessage(error)
  } finally {
    if (mailboxRequestController === requestController) {
      loading.mailbox = false
      mailboxRequestController = null
    }
  }
}

async function loadMoreInbox() {
  if (mailboxMode.value !== 'inbox' || loading.mailbox || !inboxHasMore.value) return
  await loadMailbox(false, true)
}

async function switchMailbox(mode: MailboxMode) {
  if (mailboxMode.value === mode) return
  mailboxMode.value = mode
  await loadMailbox(false)
}

async function switchInboxReadStatus(status: InboxReadStatus) {
  if (inboxReadStatus.value === status) return
  inboxReadStatus.value = status
  inboxHasMore.value = false
  inboxTotal.value = 0
  await loadMailbox(false)
}

function resetMailboxLimit() {
  inboxHasMore.value = false
  inboxTotal.value = 0
  void loadMailbox(false)
}

function markOpenedInboxRead(uid: string) {
  if (mailboxMode.value !== 'inbox') return
  const message = messages.value.find((item) => item.uid === uid)
  if (!message || message.is_read !== false) return
  message.is_read = true
  inboxCounts.unread = Math.max(0, inboxCounts.unread - 1)
  inboxCounts.read = Math.min(inboxCounts.all, inboxCounts.read + 1)
  void markMailboxRead(uid).catch(() => {
    // 已在当前界面完成阅读；下次刷新时以 IMAP 的最终状态为准。
  })
}

async function openMail(uid: string) {
  if (!uid || loading.detail) return
  selectedUid.value = uid
  markOpenedInboxRead(uid)
  // 收件箱列表的前几封邮件已携带本地正文缓存，点击时直接展示，
  // 避免再等待一次详情接口往返。
  const readyDetail = messages.value.find((message) => message.uid === uid)
  if (readyDetail?.body || readyDetail?.body_html) {
    detail.value = readyDetail
    return
  }
  loading.detail = true
  try {
    const result = mailboxMode.value === 'sent' ? await getSentMailDetail(uid) : await getMailboxDetail(uid)
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
      <div class="mail-page-actions">
        <div class="mailbox-mode-tabs">
          <button type="button" :class="{ active: mailboxMode === 'inbox' }" @click="switchMailbox('inbox')">收件箱</button>
          <button type="button" :class="{ active: mailboxMode === 'sent' }" @click="switchMailbox('sent')">已发邮件</button>
        </div>
        <el-select v-model="mailboxLimit" class="mail-limit-select" @change="resetMailboxLimit">
          <el-option label="最近 10 封" value="10" />
          <el-option label="最近 20 封" value="20" />
          <el-option label="最近 50 封" value="50" />
        </el-select>
        <button class="mail-button mail-button--ghost" type="button" :disabled="loading.mailbox" @click="loadMailbox(true)">
          <el-icon><Refresh /></el-icon>
          {{ loading.mailbox ? '刷新中' : (mailboxMode === 'sent' ? '重新加载' : '刷新') }}
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
          <div class="mail-section-title">
            <h3>{{ mailboxMode === 'sent' ? '已发邮件' : '收件箱' }}</h3>
            <span>{{ statusText || `${messages.length} 封邮件` }}</span>
          </div>
          <div v-if="mailboxMode === 'inbox'" class="mail-read-tabs" aria-label="收件箱阅读状态">
            <button type="button" :class="{ active: inboxReadStatus === 'all' }" @click="switchInboxReadStatus('all')">全部邮件 {{ inboxCounts.all }}</button>
            <button type="button" :class="{ active: inboxReadStatus === 'unread' }" @click="switchInboxReadStatus('unread')">未读邮件 {{ inboxCounts.unread }}</button>
            <button type="button" :class="{ active: inboxReadStatus === 'read' }" @click="switchInboxReadStatus('read')">已读邮件 {{ inboxCounts.read }}</button>
          </div>
        </div>

        <div v-if="errorText" class="mail-empty mail-empty--error">{{ errorText }}</div>
        <div v-else-if="loading.mailbox" class="mail-empty">{{ mailboxMode === 'sent' ? '正在读取已发邮件...' : '正在读取收件箱...' }}</div>
        <div v-else-if="messages.length" class="mailbox-list">
          <button
            v-for="message in messages"
            :key="message.uid"
            :class="['mailbox-item', { active: message.uid === selectedUid, unread: mailboxMode === 'inbox' && message.is_read === false }]"
            type="button"
            @click="openMail(message.uid)"
          >
            <span class="mailbox-subject">{{ message.subject || '无主题' }}</span>
            <span class="mailbox-meta">{{ mailboxMode === 'sent' ? `发给：${message.to || '-'}` : (message.from || '未知发件人') }}</span>
            <span class="mailbox-preview">{{ message.preview || '点击邮件查看正文' }}</span>
            <span class="mailbox-bottom">
              <time>{{ message.date || '暂无时间' }}</time>
              <em v-if="message.attachments?.length">{{ message.attachments.length }} 个附件</em>
            </span>
          </button>
          <button
            v-if="mailboxMode === 'inbox' && inboxHasMore"
            class="mail-load-more"
            type="button"
            :disabled="loading.mailbox"
            @click="loadMoreInbox"
          >
            {{ loading.mailbox ? '正在加载…' : `加载更早邮件（已显示 ${messages.length}${inboxTotal ? ` / ${inboxTotal}` : ''}）` }}
          </button>
        </div>
        <div v-else class="mail-empty">{{ mailboxMode === 'sent' ? '暂无已发邮件记录。' : '暂无邮件，或当前邮箱没有可读取的收件箱邮件。' }}</div>
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
            <p v-if="detail.cc">抄送：{{ detail.cc }}</p>
            <p>时间：{{ detail.date || '-' }}</p>
            <div class="mail-reply-actions">
              <button class="mail-button mail-button--ghost" type="button" @click="startReply('sender')">回复发送方</button>
              <button class="mail-button mail-button--primary" type="button" @click="startReply('all')">全部回复</button>
            </div>
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
