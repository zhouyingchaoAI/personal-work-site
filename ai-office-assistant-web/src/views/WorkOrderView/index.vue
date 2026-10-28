<script setup lang="ts">
import { computed, onActivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, Search, Paperclip, Checked, CircleClose, Clock } from '@element-plus/icons-vue'
import {
  listTickets, getTicket, createTicket, addTicketComment, uploadTicketAttachment,
  type Ticket, type ForumAttachment,
} from '../../services/personalWorkApi'
import { authState } from '../../services/authSession'
import { ticketUserKey, ticketUserStats } from './ticketUserStats'
import TicketAttachment from '../../components/TicketAttachment.vue'
const props = defineProps<{ embedded?: boolean; ticketId?: string }>()

// 平台助手 / 模块清单：提交工单先选助手，便于快速定位与分派。
const MODULE_OPTIONS = [
  '智能写作', '周报助手', '出差报告助手', '工作日记', '金点子论坛', '每日资讯',
  '邮件助手', '会议助手', '知识库', '项目助手', '联指经营助手', '项目管理台账', '数据中台',
  '工作流中心', '报销助手', '龙虾基地', '登录 / 账号', '平台整体 / 其他',
]

const tickets = ref<Ticket[]>([])
const summary = reactive({ total: 0, open: 0, closed: 0 })
const loading = ref(false)
const keyword = ref('')
const filter = ref<'all' | 'open' | 'closed'>('all')
const moduleFilter = ref('')

const createVisible = ref(false)
const DEFAULT_TICKET_MODULE = '联指经营助手'
const createForm = reactive<{ module: string; title: string; body: string; attachments: ForumAttachment[] }>({ module: DEFAULT_TICKET_MODULE, title: '', body: '', attachments: [] })
const submitting = ref(false)
const createAttachmentUploading = ref(false)

const detailVisible = ref(false)
const detail = ref<Ticket | null>(null)
const detailLoading = ref(false)
const reply = reactive<{ content: string; status: '' | 'accepted' | 'resolved' | 'rejected'; attachments: ForumAttachment[] }>({ content: '', status: '', attachments: [] })
const replying = ref(false)
const replyAttachmentUploading = ref(false)

const currentUser = computed(() => authState.user?.name || authState.user?.username || '成员')
const isSuperAdmin = computed(() => authState.user?.role === 'superadmin')
const userFilter = ref('')
const userSearch = ref('')
const showOthers = ref(false)
const urging = reactive<Record<string, boolean>>({})
const urged = reactive<Record<string, boolean>>({})
function isMine(ticket: Ticket) {
  return ticket.author_username ? ticket.author_username === authState.user?.username : ticket.author === currentUser.value || ticket.author === authState.user?.username
}
const mySummary = computed(() => {
  const mine = tickets.value.filter(isMine)
  return { total: mine.length, open: mine.filter(ticket => !ticket.closed).length, closed: mine.filter(ticket => ticket.closed).length }
})
async function urge(ticket: Ticket) {
  if (!isMine(ticket) || ticket.closed || urging[ticket.id] || urged[ticket.id]) return
  urging[ticket.id] = true
  try {
    const result = await addTicketComment(ticket.id, '【提交人催办】请关注此工单的处理进度，并回复预计处理时间。', '', '', [])
    urged[ticket.id] = true
    const index = tickets.value.findIndex(item => item.id === ticket.id)
    if (index >= 0) tickets.value[index] = result.ticket
    if (detail.value?.id === ticket.id) detail.value = result.ticket
    ElMessage.success('催办已记录，可在工单处理记录中查看')
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '催办失败，请重试') } finally { urging[ticket.id] = false }
}
const userStats = computed(() => ticketUserStats(tickets.value))
const visibleUserStats = computed(() => userStats.value.filter(user => `${user.name} ${user.username}`.toLowerCase().includes(userSearch.value.trim().toLowerCase())))
const selectedUser = computed(() => userStats.value.find(user => user.key === userFilter.value))
function selectUser(key: string, module = '') {
  userFilter.value = key
  moduleFilter.value = module
  keyword.value = ''
  filter.value = 'all'
}
const route = useRoute()
const expandedTickets = reactive<Record<string, boolean>>({})
function isExpanded(ticket: Ticket) {
  return expandedTickets[ticket.id] ?? (ticket.author_username
    ? ticket.author_username === authState.user?.username
    : ticket.author === currentUser.value || ticket.author === authState.user?.username)
}
async function openLinkedTicket() {
  if (route.params.menu === 'workorder' && typeof route.query.ticket === 'string') await openDetail(route.query.ticket)
}

const statusMeta: Record<string, { label: string; type: 'info' | 'warning' | 'success' | 'danger' }> = {
  open: { label: '待处理', type: 'warning' },
  accepted: { label: '受理中', type: 'info' },
  resolved: { label: '已解决', type: 'success' },
  rejected: { label: '不采纳', type: 'danger' },
}
const commentStatusMeta: Record<string, { label: string; type: 'info' | 'success' | 'danger' }> = {
  accepted: { label: '已受理', type: 'info' },
  resolved: { label: '已解决', type: 'success' },
  rejected: { label: '不采纳', type: 'danger' },
}
function metaOf(status?: string) { return statusMeta[status || 'open'] || statusMeta.open }

const moduleCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const t of tickets.value) counts.set(t.module || '未指定', (counts.get(t.module || '未指定') || 0) + 1)
  return counts
})
const moduleFilterOptions = computed(() => Array.from(moduleCounts.value.entries()).sort((a, b) => b[1] - a[1]))

const filteredTickets = computed(() => tickets.value.filter((t) => {
  const byState = filter.value === 'all' || (filter.value === 'closed' ? t.closed : !t.closed)
  const byModule = !moduleFilter.value || (t.module || '未指定') === moduleFilter.value
  const kw = keyword.value.trim().toLowerCase()
  const byKw = !kw || `${t.title} ${t.body} ${t.author} ${t.module || ''}`.toLowerCase().includes(kw)
  const byUser = !isSuperAdmin.value || !userFilter.value || ticketUserKey(t) === userFilter.value
  return byState && byModule && byKw && byUser
}))
const ticketGroups = computed(() => isSuperAdmin.value && userFilter.value
  ? [{ key: 'selected', label: `${selectedUser.value?.name || '所选用户'}的工单`, items: filteredTickets.value, expanded: true }]
  : [{ key: 'mine', label: '我的工单处理情况', items: filteredTickets.value.filter(isMine), expanded: true },
    { key: 'others', label: '其他人的工单', items: filteredTickets.value.filter(ticket => !isMine(ticket)), expanded: showOthers.value }])

async function load() {
  loading.value = true
  try {
    const r = await listTickets()
    tickets.value = r.tickets
    Object.assign(summary, r.summary)
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '工单加载失败') } finally { loading.value = false }
}

function openCreate() { createForm.module = DEFAULT_TICKET_MODULE; createForm.title = ''; createForm.body = ''; createForm.attachments = []; createVisible.value = true }
async function submitCreate() {
  if (createAttachmentUploading.value) return ElMessage.warning('剪贴板图片上传中，请稍候提交')
  if (!createForm.module) return ElMessage.warning('请先选择该问题所属的助手 / 模块')
  if (!createForm.title.trim()) return ElMessage.warning('请填写工单标题')
  if (!createForm.body.trim()) return ElMessage.warning('请填写工单内容')
  submitting.value = true
  try {
    await createTicket(createForm.title.trim(), createForm.body.trim(), createForm.module, createForm.attachments)
    createVisible.value = false
    ElMessage.success('工单已提交')
    await load()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '提交失败') } finally { submitting.value = false }
}

async function openDetail(id: string) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  reply.content = ''; reply.status = ''; reply.attachments = []
  try {
    detail.value = (await getTicket(id)).ticket
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '工单详情加载失败'); detailVisible.value = false } finally { detailLoading.value = false }
}

async function submitReply() {
  if (!detail.value) return
  if (replyAttachmentUploading.value) return ElMessage.warning('剪贴板图片上传中，请稍候提交')
  if (!reply.content.trim() && !reply.status) return ElMessage.warning('请填写处理内容或选择处理状态')
  if (!reply.content.trim()) reply.content = reply.status ? commentStatusMeta[reply.status].label : ''
  replying.value = true
  try {
    detail.value = (await addTicketComment(detail.value.id, reply.content.trim(), reply.status, '', reply.attachments)).ticket
    reply.content = ''; reply.status = ''; reply.attachments = []
    ElMessage.success('已提交处理')
    await load()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '提交失败') } finally { replying.value = false }
}

async function uploadTo(target: { attachments: ForumAttachment[] }, file: File) {
  try {
    const { attachment } = await uploadTicketAttachment(file)
    target.attachments.push(attachment)
    return true
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '附件上传失败') }
  return false
}

// 截图工具复制的图片通常没有文件名；补齐一个便于下载识别的名称。
function pastedImageName(file: File, index: number) {
  const suffix = file.type === 'image/jpeg' ? 'jpg' : file.type === 'image/webp' ? 'webp' : file.type === 'image/gif' ? 'gif' : 'png'
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)
  return `pasted-image-${stamp}-${index + 1}.${suffix}`
}

function clipboardImageFiles(event: ClipboardEvent) {
  const files: File[] = []
  const items = Array.from(event.clipboardData?.items || [])
  for (const item of items) {
    if (!item.type.startsWith('image/')) continue
    const file = item.getAsFile()
    if (file) files.push(new File([file], pastedImageName(file, files.length), { type: file.type || 'image/png', lastModified: Date.now() }))
  }
  // 兼容部分浏览器只通过 clipboardData.files 暴露截图的情况。
  if (!files.length) {
    for (const file of Array.from(event.clipboardData?.files || [])) {
      if (file.type.startsWith('image/')) files.push(new File([file], pastedImageName(file, files.length), { type: file.type || 'image/png', lastModified: Date.now() }))
    }
  }
  return files
}

async function handleImagePaste(event: ClipboardEvent, target: { attachments: ForumAttachment[] }, place: 'create' | 'reply') {
  const images = clipboardImageFiles(event)
  if (!images.length) return // 纯文本仍由输入框正常粘贴。
  event.preventDefault()
  const uploading = place === 'create' ? createAttachmentUploading : replyAttachmentUploading
  if (uploading.value) return ElMessage.warning('图片正在上传，请稍候再粘贴')
  uploading.value = true
  try {
    let uploaded = 0
    for (const image of images) if (await uploadTo(target, image)) uploaded += 1
    if (uploaded) ElMessage.success(`已添加 ${uploaded} 张剪贴板图片到附件`)
  } finally {
    uploading.value = false
  }
}

function handleCreatePaste(event: ClipboardEvent) { void handleImagePaste(event, createForm, 'create') }
function handleReplyPaste(event: ClipboardEvent) { void handleImagePaste(event, reply, 'reply') }

function removeAttachment(target: { attachments: ForumAttachment[] }, id: string) {
  target.attachments = target.attachments.filter((a) => a.id !== id)
}

onMounted(async () => {
  if (!props.embedded) return
  await load()
  if (props.ticketId) await openDetail(props.ticketId)
})
watch(() => props.ticketId, id => { if (props.embedded && id) void openDetail(id) })
onActivated(async () => { if (!props.embedded) { await load(); await openLinkedTicket() } })
watch(() => route.query.ticket, () => { void openLinkedTicket() })
</script>

<template>
  <section class="workspace-main workorder-main" v-loading="loading">
    <header class="wo-head">
      <div class="wo-head-brand">
        <p class="wo-eyebrow">协作与效率 · 需求工单</p>
        <h1>工单系统</h1>
        <span>提交产品建议与问题工单，跟踪受理、解决与不采纳全流程。</span>
      </div>
      <div class="wo-head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button class="wo-head-primary" type="primary" :icon="Plus" @click="openCreate">提交工单</el-button>
      </div>
    </header>

    <section class="wo-stats">
      <article :class="{ active: filter === 'all' }" @click="filter = 'all'"><span>我的工单</span><strong>{{ mySummary.total }}</strong></article>
      <article class="open" :class="{ active: filter === 'open' }" @click="filter = 'open'"><span>我的待处理</span><strong>{{ mySummary.open }}</strong></article>
      <article class="resolved" :class="{ active: filter === 'closed' }" @click="filter = 'closed'"><span>我的已办结</span><strong>{{ mySummary.closed }}</strong></article>
    </section>

    <section v-if="isSuperAdmin" class="wo-user-overview" aria-label="按用户统计工单">
      <header><div><h2>谁在提工单</h2><p>全部工单口径 · {{ userStats.length }} 个提交人记录 · {{ tickets.length }} 单，不随下方列表筛选变化</p></div><el-input v-model="userSearch" clearable placeholder="查找提交人 / 账号" aria-label="查找提交人" /></header>
      <p class="wo-user-note">历史工单未记录账号，按署名独立统计，不自动与同名账号合并。</p>
      <div class="wo-user-table" tabindex="0" role="region" aria-label="提交人统计，可横向滚动">
        <table><thead><tr><th>提交人</th><th>提交总量</th><th>待处理</th><th>已办结</th><th>涉及助手 · 点击查看</th></tr></thead><tbody>
          <tr v-for="user in visibleUserStats" :key="user.key" :class="{ selected:userFilter === user.key }">
            <th><button type="button" class="wo-user-name" :aria-pressed="userFilter === user.key" @click="selectUser(user.key)">{{ user.name }}</button><small>{{ user.username || '历史署名（未记录账号）' }}</small></th>
            <td><button type="button" class="wo-user-count" @click="selectUser(user.key)">{{ user.total }} 单</button><div class="wo-user-bar"><i :style="{width:`${user.total / (userStats[0]?.total || 1) * 100}%`}" /></div></td>
            <td><strong class="wo-user-open">{{ user.open }}</strong></td><td>{{ user.closed }}</td>
            <td><div class="wo-user-modules"><el-button v-for="[module, count] in user.modules" :key="module" size="small" :type="userFilter === user.key && moduleFilter === module ? 'primary' : 'default'" @click="selectUser(user.key,module)">{{ module }} · {{ count }}</el-button></div></td>
          </tr>
        </tbody></table>
        <p v-if="!visibleUserStats.length" class="wo-empty">暂无匹配的提交人</p>
      </div>
    </section>
    <div v-if="isSuperAdmin && selectedUser" class="wo-user-selection"><strong>正在查看：{{ selectedUser.name }}{{ moduleFilter ? ' / ' + moduleFilter : '' }}</strong><span>{{ filteredTickets.length }} 单</span><el-button link type="primary" @click="selectUser('')">清除用户筛选</el-button></div>
    <div class="wo-toolbar">
      <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索工单标题、内容或提交人" class="wo-search" />
      <el-select v-model="moduleFilter" clearable placeholder="全部助手" class="wo-module-filter">
        <el-option v-for="[name, count] in moduleFilterOptions" :key="name" :value="name" :label="`${name}（${count}）`" />
      </el-select>
      <el-button class="wo-toolbar-create" type="primary" :icon="Plus" @click="openCreate">新建工单</el-button>
      <el-radio-group v-model="filter" class="wo-filter">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="open">待处理</el-radio-button>
        <el-radio-button value="closed">已办结</el-radio-button>
      </el-radio-group>
    </div>

    <section v-for="group in ticketGroups" :key="group.key" class="wo-list" :data-ticket-group="group.key">
      <h2 v-if="group.key !== 'others'">{{ group.label }} <small>（{{ group.items.length }}）</small></h2>
      <el-button v-else class="wo-others-toggle" :aria-expanded="showOthers" @click="showOthers = !showOthers">{{ showOthers ? '收起' : '展开' }}其他人的工单列表（{{ group.items.length }}）</el-button>
      <template v-if="group.expanded">
      <p v-if="!group.items.length" class="wo-empty">暂无匹配工单。</p>
      <article v-for="t in group.items" :key="t.id" class="wo-card" @click="openDetail(t.id)">
        <div class="wo-card-main">
          <div class="wo-card-title">
            <el-tag :type="metaOf(t.status).type" size="small" effect="light">{{ metaOf(t.status).label }}</el-tag>
            <span class="wo-module-tag">{{ t.module || '未指定' }}</span>
            <h3>{{ t.title }}</h3>
            <span v-if="t.pinned" class="wo-pin">置顶</span>
          </div>
          <p v-if="isExpanded(t)" class="wo-card-body wo-card-body-expanded">{{ t.body }}</p>
          <div class="wo-card-actions" @click.stop>
            <el-button link type="primary" :aria-expanded="isExpanded(t)" @click="expandedTickets[t.id] = !isExpanded(t)">{{ isExpanded(t) ? '收起内容' : '展开内容' }}</el-button>
            <el-button link type="primary" @click="openDetail(t.id)">查看详情与处理</el-button>
            <el-button v-if="isMine(t) && !t.closed" link type="warning" :loading="urging[t.id]" :disabled="urged[t.id]" @click="urge(t)">{{ urged[t.id] ? '已催办' : '催办' }}</el-button>
          </div>
          <div class="wo-card-meta">
            <span>{{ t.author }}</span>
            <span><el-icon><Clock /></el-icon>{{ t.updated_at }}</span>
            <span>{{ t.comment_count }} 条处理</span>
            <span v-if="t.attachments && t.attachments.length"><el-icon><Paperclip /></el-icon>{{ t.attachments.length }}</span>
          </div>
        </div>
      </article>
      </template>
    </section>

    <!-- 提交工单 -->
    <el-dialog v-model="createVisible" title="提交工单" class="wo-dialog" width="min(640px, 94vw)" append-to-body>
      <el-form label-position="top">
        <el-form-item label="① 选择助手 / 模块" required>
          <el-select v-model="createForm.module" filterable placeholder="先选择问题所在的助手，便于快速定位处理" class="wo-module-select">
            <el-option v-for="m in MODULE_OPTIONS" :key="m" :value="m" :label="m" />
          </el-select>
          <p class="wo-field-hint">先定位到具体助手，负责同学可按助手快速筛选、分派与处理。</p>
        </el-form-item>
        <el-form-item label="② 工单标题" required>
          <el-input v-model="createForm.title" maxlength="120" show-word-limit placeholder="一句话概括你的建议或问题" />
        </el-form-item>
        <el-form-item label="③ 详细描述" required>
          <el-input v-model="createForm.body" type="textarea" :rows="6" placeholder="请描述场景、期望效果或复现步骤；可直接粘贴截图" @paste="handleCreatePaste" />
          <p class="wo-field-hint">支持直接粘贴剪贴板图片，图片会自动作为工单附件上传。</p>
        </el-form-item>
        <el-form-item label="附件（可选）">
          <el-upload :show-file-list="false" :before-upload="(f: File) => uploadTo(createForm, f)" multiple>
            <el-button :icon="Paperclip" :loading="createAttachmentUploading">上传附件</el-button>
          </el-upload>
          <ul v-if="createForm.attachments.length" class="wo-attach-list">
            <li v-for="a in createForm.attachments" :key="a.id">
              <TicketAttachment :attachment="a" />
              <el-button link type="danger" @click="removeAttachment(createForm, a.id)">移除</el-button>
            </li>
          </ul>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="createAttachmentUploading" @click="submitCreate">提交工单</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情 -->
    <el-dialog v-model="detailVisible" class="wo-dialog wo-detail-dialog" width="min(760px, 96vw)" :title="detail?.title || '工单详情'" append-to-body>
      <div v-loading="detailLoading" class="wo-detail">
        <template v-if="detail">
          <div class="wo-detail-head">
            <el-tag :type="metaOf(detail.status).type" effect="light">{{ metaOf(detail.status).label }}</el-tag>
            <span class="wo-module-tag">{{ detail.module || '未指定' }}</span>
            <span>{{ detail.author }} · {{ detail.created_at }}</span>
          </div>
          <p class="wo-detail-body">{{ detail.body }}</p>
          <ul v-if="detail.attachments && detail.attachments.length" class="wo-attach-list">
            <li v-for="a in detail.attachments" :key="a.id">
              <TicketAttachment :attachment="a" />
            </li>
          </ul>

          <h4 class="wo-thread-title">处理记录（{{ detail.comments?.length || 0 }}）</h4>
          <ul class="wo-thread">
            <li v-if="!detail.comments || !detail.comments.length" class="wo-thread-empty">暂无处理记录，成为第一个受理人。</li>
            <li v-for="c in detail.comments" :key="c.id" class="wo-comment">
              <div class="wo-comment-head">
                <strong>{{ c.author }}</strong>
                <el-tag v-if="c.status && commentStatusMeta[c.status]" :type="commentStatusMeta[c.status].type" size="small" effect="plain">{{ commentStatusMeta[c.status].label }}</el-tag>
                <span>{{ c.created_at }}</span>
              </div>
              <p>{{ c.content }}</p>
              <ul v-if="c.attachments && c.attachments.length" class="wo-attach-list">
                <li v-for="a in c.attachments" :key="a.id"><TicketAttachment :attachment="a" /></li>
              </ul>
            </li>
          </ul>

          <div class="wo-reply">
            <el-input v-model="reply.content" type="textarea" :rows="3" placeholder="填写处理进展、解决方案或说明…；可直接粘贴截图" @paste="handleReplyPaste" />
            <div class="wo-reply-bar">
              <el-select v-model="reply.status" placeholder="标记状态（可选）" clearable class="wo-reply-status">
                <el-option label="受理中" value="accepted" />
                <el-option label="已解决" value="resolved" />
                <el-option label="不采纳" value="rejected" />
              </el-select>
              <el-upload :show-file-list="false" :before-upload="(f: File) => uploadTo(reply, f)" multiple>
                <el-button :icon="Paperclip" :loading="replyAttachmentUploading">附件</el-button>
              </el-upload>
              <el-button type="primary" :icon="Checked" :loading="replying" :disabled="replyAttachmentUploading" @click="submitReply">提交处理</el-button>
            </div>
            <ul v-if="reply.attachments.length" class="wo-attach-list">
              <li v-for="a in reply.attachments" :key="a.id">
                <TicketAttachment :attachment="a" />
                <el-button link type="danger" @click="removeAttachment(reply, a.id)">移除</el-button>
              </li>
            </ul>
            <p class="wo-reply-hint"><el-icon><CircleClose v-if="reply.status === 'rejected'" /><Checked v-else /></el-icon>支持直接粘贴截图；以 {{ currentUser }} 的身份提交，标记“已解决”后工单将自动结单并取消置顶。</p>
          </div>
        </template>
      </div>
    </el-dialog>
  </section>
</template>

<style scoped src="./index.scss"></style>
