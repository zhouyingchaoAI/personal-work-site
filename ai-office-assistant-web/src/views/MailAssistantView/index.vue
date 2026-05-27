<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CollectionTag, Delete, Message, Paperclip, Promotion, Refresh, View } from '@element-plus/icons-vue'
import {
  getMailConfig,
  getMailboxDetail,
  listMailbox,
  sendAssistantMail,
  type MailMessage,
} from '../../services/personalWorkApi'
import './index.scss'

interface ComposeForm {
  to: string
  cc: string
  subject: string
  body: string
}

const mailboxLimit = ref('20')
const selectedUid = ref('')
const messages = ref<MailMessage[]>([])
const detail = ref<MailMessage | null>(null)
const attachments = ref<File[]>([])
const mailSignature = ref('')
const statusText = ref('')
const errorText = ref('')
const compose = reactive<ComposeForm>({ to: '', cc: '', subject: '', body: '' })
const loading = reactive({
  mailbox: false,
  detail: false,
  send: false,
})

const selectedMessage = computed(() => messages.value.find((message) => message.uid === selectedUid.value) || null)
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

function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '')
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

function updateFiles(event: Event) {
  attachments.value = Array.from((event.target as HTMLInputElement).files || [])
}

function removeFile(index: number) {
  attachments.value.splice(index, 1)
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
  compose.to = ''
  compose.cc = ''
  compose.subject = ''
  compose.body = ''
  attachments.value = []
}

async function sendMail() {
  if (!compose.to.trim()) {
    ElMessage.warning('请填写收件人')
    return
  }
  if (loading.send) return
  loading.send = true
  try {
    const files = []
    for (const file of attachments.value) {
      files.push({
        name: file.name,
        type: file.type || 'application/octet-stream',
        content: await readFileAsBase64(file),
      })
    }
    const result = await sendAssistantMail({
      to: compose.to,
      cc: compose.cc,
      subject: compose.subject,
      body: compose.body,
      attachments: files,
    })
    ElMessage.success(result.message || '邮件已发送')
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
        <span class="mail-kicker">
          <el-icon><Message /></el-icon>
          邮件助手
        </span>
        <h2>邮件助手</h2>
        <p>查看收件箱、阅读邮件、发送普通邮件</p>
      </div>
      <div class="mail-page-actions">
        <select v-model="mailboxLimit" @change="loadMailbox(false)">
          <option value="10">最近 10 封</option>
          <option value="20">最近 20 封</option>
          <option value="50">最近 50 封</option>
        </select>
        <button class="mail-button mail-button--ghost" type="button" :disabled="loading.mailbox" @click="loadMailbox(true)">
          <el-icon><Refresh /></el-icon>
          {{ loading.mailbox ? '刷新中' : '刷新' }}
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
              <span v-for="file in detail.attachments || []" :key="file.name">
                <el-icon><Paperclip /></el-icon>
                {{ file.name }}{{ file.size ? ` · ${formatFileSize(file.size)}` : '' }}
              </span>
              <em v-if="!detail.attachments?.length">无附件</em>
            </div>
          </header>
          <div v-if="detail.body_html" class="mail-detail-body" v-html="detail.body_html"></div>
          <div v-else class="mail-detail-body mail-detail-body--plain">{{ detail.body || detail.preview || '暂无可读取的文本正文' }}</div>
        </article>
        <div v-else class="mail-empty">暂无选中邮件。</div>
      </section>

      <section class="mail-card mail-compose-card">
        <div class="mail-section-head">
          <div>
            <h3>发送邮件</h3>
            <span>使用当前账号 SMTP 发送普通邮件</span>
          </div>
          <el-icon><Promotion /></el-icon>
        </div>

        <div class="mail-compose-grid">
          <div class="mail-compose-form">
            <label>
              <span>收件人</span>
              <input v-model="compose.to" type="text" placeholder="recipient@example.com" />
            </label>
            <label>
              <span>抄送</span>
              <input v-model="compose.cc" type="text" placeholder="可选，多个邮箱用分号分隔" />
            </label>
            <label class="mail-compose-full">
              <span>主题</span>
              <input v-model="compose.subject" type="text" placeholder="请输入邮件主题" />
            </label>
            <label class="mail-compose-full">
              <span>正文</span>
              <textarea v-model="compose.body" placeholder="请输入邮件正文"></textarea>
            </label>
            <label class="mail-compose-full mail-file-input">
              <span>附件</span>
              <input type="file" multiple @change="updateFiles" />
            </label>
            <div class="mail-file-list mail-compose-full">
              <div v-if="attachments.length">
                <span v-for="(file, index) in attachments" :key="`${file.name}-${index}`">
                  <el-icon><Paperclip /></el-icon>
                  {{ file.name }} · {{ formatFileSize(file.size) }}
                  <button type="button" :aria-label="`移除 ${file.name}`" @click="removeFile(index)">
                    <el-icon><Delete /></el-icon>
                  </button>
                </span>
              </div>
              <em v-else>未添加附件</em>
            </div>
            <div class="mail-compose-actions mail-compose-full">
              <button class="mail-button mail-button--ghost" type="button" @click="clearCompose">清空</button>
              <button class="mail-button mail-button--primary" type="button" :disabled="loading.send" @click="sendMail">
                <el-icon><Promotion /></el-icon>
                {{ loading.send ? '发送中' : '发送邮件' }}
              </button>
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
      </section>
    </div>
  </section>
</template>
