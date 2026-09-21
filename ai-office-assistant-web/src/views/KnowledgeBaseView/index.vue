<script setup lang="ts">
import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Delete, Document, Link, RefreshRight, Search, Setting, UploadFilled } from '@element-plus/icons-vue'
import {
  bootstrapRagflow,
  createKnowledgeChatSession,
  deleteKnowledgeDoc,
  getDigitalHumanKbConfig,
  getKnowledgeConfig,
  getKnowledgeExternalApiInfo,
  getKnowledgeDocChunks,
  getKnowledgeChatHistory,
  getKnowledgeChatSession,
  clearKnowledgeChat,
  getRagflowSso,
  getRagflowStatus,
  knowledgeAskStreamUrl,
  knowledgeDocFileUrl,
  saveDigitalHumanKbConfig,
  reparseKnowledgeDoc,
  listKnowledgeChatSessions,
  listKnowledgeDocs,
  listKnowledgeKbs,
  manageKnowledgeKb,
  saveKnowledgeConfig,
  saveRagflowChunkConfig,
  searchKnowledge,
  testKnowledgeEmbedding,
  uploadKnowledgeDoc,
  type KnowledgeAskSource,
  type KnowledgeChatSession,
  type KnowledgeDoc,
  type KnowledgeExternalApiInfo,
  type KnowledgeKb,
  type KnowledgeSearchResult,
  type RagflowStatus,
} from '../../services/personalWorkApi'
import { authState, ensureSession } from '../../services/authSession'
import { htmlToText, renderChunk, renderMarkdown } from '../../utils/markdown'
import PdfMarkdownStudio from './PdfMarkdownStudio.vue'
import './index.scss'

const pdfMdVisible = ref(false)

const kbs = ref<KnowledgeKb[]>([])
const currentKbId = ref('')
const canManage = ref(true)
const provider = ref('')
const docs = ref<KnowledgeDoc[]>([])

const currentKb = computed(() => kbs.value.find((kb) => kb.id === currentKbId.value))
// 业务接口的 scope：共享库传 'shared'（后端按管理员校验），个人库传数据集 ID。
const scopeParam = computed(() => (currentKb.value?.shared ? 'shared' : currentKbId.value || 'mine'))
const docsLoading = ref(false)
const embeddingModel = ref('')
const staleDocs = ref<string[]>([])
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const externalGuideVisible = ref(false)
const externalApiInfo = ref<KnowledgeExternalApiInfo | null>(null)
const externalApiLoading = ref(false)

const externalMcpEndpoint = computed(() => `${window.location.origin}/personal-office-assistant/mcp`)
const externalMcpUsername = computed(() => authState.user?.username || 'your_username')
const externalMcpConfig = computed(() => JSON.stringify({
  mcpServers: {
    personal_office_knowledge: {
      type: 'streamable-http',
      url: externalMcpEndpoint.value,
      headers: {
        Authorization: 'Bearer <mcp_secret>',
        'X-MCP-Username': externalMcpUsername.value,
      },
    },
  },
}, null, 2))
const externalSearchExample = computed(() => `curl -X POST '${externalMcpEndpoint.value}' \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <mcp_secret>' \\
  -H 'X-MCP-Username: ${externalMcpUsername.value}' \\
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"knowledge.search","arguments":{"query":"报销流程","top_k":5}}}'`)
const ragflowOpenAiExample = computed(() => {
  const endpoint = externalApiInfo.value?.completion_url || 'https://ragflow.example.com/api/v1/chats_openai/<chat_id>/chat/completions'
  return `curl -X POST '${endpoint}' \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer <ragflow_api_key>' \\
  --data '{"model":"ragflow","messages":[{"role":"user","content":"请说明报销流程"}],"stream":false}'`
})

const query = ref('')
const searching = ref(false)
const asking = ref(false)
const searchResults = ref<KnowledgeSearchResult[]>([])
const warning = ref('')

// ---- 对话式问答（办公助手风格 UI + RAGFlow 流式后端）----
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: KnowledgeAskSource[]
  failed?: boolean
}

const chat = ref<ChatMessage[]>([])
const chatBodyRef = ref<HTMLElement | null>(null)
const chatSessions = ref<KnowledgeChatSession[]>([])
const currentSessionId = ref('')
const sessionsLoading = ref(false)
const selectedKbIds = ref<string[]>([])

const selectableKbs = computed(() => kbs.value.filter((kb) => kb.chunk_count > 0))
const activeKbIds = computed(() => selectedKbIds.value.length ? selectedKbIds.value : selectableKbs.value.map((kb) => kb.id))
const selectedKbSummary = computed(() => {
  if (!selectableKbs.value.length) return '暂无可用知识库'
  const active = activeKbIds.value
  if (active.length === selectableKbs.value.length) return `全部知识库（${active.length}）`
  if (active.length === 1) return kbs.value.find((kb) => kb.id === active[0])?.name || '1 个知识库'
  return `已选 ${active.length} 个知识库`
})

function escapeHtml(value: string) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

async function copyExternalGuide(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

async function openExternalGuide() {
  externalGuideVisible.value = true
  externalApiLoading.value = true
  try {
    externalApiInfo.value = await getKnowledgeExternalApiInfo()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    externalApiLoading.value = false
  }
}

function splitSessionTitle(title: string) {
  const text = String(title || '').trim()
  const match = text.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?:\s+(.+))?$/)
  if (!match) return { topic: text || '新会话', date: '' }
  return { topic: match[2]?.trim() || '新会话', date: match[1] }
}

function citationSourceIndex(citeNumber: number, sources: KnowledgeAskSource[] = []) {
  const byExactIndex = sources.findIndex((source) => source.index === citeNumber)
  if (byExactIndex >= 0) return byExactIndex
  const byZeroBasedRagflowIndex = sources.findIndex((source) => source.index === citeNumber + 1)
  if (byZeroBasedRagflowIndex >= 0) return byZeroBasedRagflowIndex
  if (citeNumber >= 0 && citeNumber < sources.length) return citeNumber
  const oneBasedOffset = citeNumber - 1
  return oneBasedOffset >= 0 && oneBasedOffset < sources.length ? oneBasedOffset : -1
}

function renderAnswer(msg: ChatMessage) {
  let text = msg.content
  // 推理模型的 <think> 过程折叠展示；流式中未闭合时保持展开。
  let think = ''
  let thinkOpen = false
  const match = text.match(/<think>([\s\S]*?)(<\/think>|$)/)
  if (match) {
    think = match[1].trim()
    thinkOpen = !match[2]
    text = text.replace(match[0], '').trim()
  }
  // RAGFlow 引用标记（[ID:n] / ##n$$）转成可点击角标。
  const cited = text
    .replace(/\s*##(\d+)\$\$/g, (_, n) => ` [CITE:${n}]`)
    .replace(/\s*\[ID:(\d+)\]/g, (_, n) => ` [CITE:${n}]`)
  const fallbackCitationIndexes = new Map<number, number>()
  let fallbackNextSourceIndex = 0
  let html = renderMarkdown(cited).replace(
    /\[CITE:(\d+)\]/g,
    (_, n) => {
      const citeNumber = Number(n)
      let sourceIndex = citationSourceIndex(citeNumber, msg.sources || [])
      if (sourceIndex < 0 && msg.sources?.length) {
        if (!fallbackCitationIndexes.has(citeNumber) && fallbackNextSourceIndex < msg.sources.length) {
          fallbackCitationIndexes.set(citeNumber, fallbackNextSourceIndex)
          fallbackNextSourceIndex += 1
        }
        sourceIndex = fallbackCitationIndexes.get(citeNumber) ?? -1
      }
      const label = sourceIndex >= 0 ? (msg.sources || [])[sourceIndex].index : citeNumber + 1
      return `<sup class="kb-cite" data-cite="${citeNumber}" data-cite-index="${sourceIndex}">${label}</sup>`
    },
  )
  if (think) {
    html =
      `<details class="kb-think"${thinkOpen ? ' open' : ''}><summary>💭 深度思考过程</summary><div>${escapeHtml(think)}</div></details>` +
      html
  }
  return html
}

function scrollChat() {
  void nextTick(() => {
    chatBodyRef.value?.scrollTo({ top: chatBodyRef.value.scrollHeight, behavior: 'smooth' })
  })
}

function defaultChatKbIds() {
  return selectableKbs.value.map((kb) => kb.id)
}

function normalizeChatKbSelection(ids: string[] = []) {
  const available = new Set(selectableKbs.value.map((kb) => kb.id))
  const filtered = ids.filter((id) => available.has(id))
  selectedKbIds.value = filtered.length ? filtered : defaultChatKbIds()
}

function applySessionKbSelection(session?: KnowledgeChatSession) {
  normalizeChatKbSelection(session?.selected_kb_ids || [])
}


async function loadChatSessions(selectLatest = false) {
  sessionsLoading.value = true
  try {
    const result = await listKnowledgeChatSessions()
    chatSessions.value = result.sessions
    if (selectLatest || !currentSessionId.value || !chatSessions.value.some((item) => item.id === currentSessionId.value)) {
      currentSessionId.value = chatSessions.value[0]?.id || ''
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    sessionsLoading.value = false
  }
}

async function loadChatHistory(sessionId = currentSessionId.value) {
  try {
    const result = sessionId ? await getKnowledgeChatSession(sessionId) : await getKnowledgeChatHistory()
    if (result.session?.id) {
      currentSessionId.value = result.session.id
      applySessionKbSelection(result.session)
    }
    chat.value = result.messages || []
    scrollChat()
  } catch {
    chat.value = []
  }
}

async function startNewChat() {
  try {
    const result = await createKnowledgeChatSession('', activeKbIds.value)
    currentSessionId.value = result.session.id
    chatSessions.value = [result.session, ...chatSessions.value.filter((item) => item.id !== result.session.id)]
    applySessionKbSelection(result.session)
    chat.value = []
    searchResults.value = []
    warning.value = ''
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function selectChatSession(sessionId: string) {
  if (sessionId === currentSessionId.value) return
  currentSessionId.value = sessionId
  searchResults.value = []
  warning.value = ''
  await loadChatHistory(sessionId)
}

async function deleteChatSession(sessionId = currentSessionId.value, shouldConfirm = true) {
  if (!sessionId) return
  const session = chatSessions.value.find((item) => item.id === sessionId)
  if (shouldConfirm) {
    try {
      await ElMessageBox.confirm(`确认删除会话“${session?.title || '新会话'}”？删除后该会话历史将不再显示。`, '删除会话', {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  try {
    await clearKnowledgeChat(sessionId)
    chatSessions.value = chatSessions.value.filter((item) => item.id !== sessionId)
    searchResults.value = []
    warning.value = ''
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = chatSessions.value[0]?.id || ''
      if (currentSessionId.value) {
        await loadChatHistory(currentSessionId.value)
      } else {
        chat.value = []
        await startNewChat()
      }
    }
    void loadChatSessions()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function clearChat() {
  const session = chatSessions.value.find((item) => item.id === currentSessionId.value)
  try {
    await ElMessageBox.confirm(
      `将永久清空“${session?.title || '当前会话'}”的全部对话内容，且无法恢复。是否继续？`,
      '清空当前对话',
      {
        type: 'warning',
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  await deleteChatSession(currentSessionId.value, false)
}

// 引用角标浮层：鼠标悬浮在角标上即预览对应片段（含表格渲染）；要看完整文档再点「预览原文」进抽屉。
const cite = reactive({ visible: false, x: 0, y: 0, source: null as KnowledgeAskSource | null })
// 移出角标后延时关闭，留出时间让鼠标移到浮层上操作（点「预览原文」等）。
let citeCloseTimer: number | undefined

function resolveCitationSourceIndex(target: HTMLElement, msg: ChatMessage) {
  const sources = msg.sources || []
  const directIndex = Number(target.dataset.citeIndex)
  if (Number.isInteger(directIndex) && directIndex >= 0 && directIndex < sources.length) return directIndex
  const citeNumber = Number(target.dataset.cite || 0)
  const matchedIndex = citationSourceIndex(citeNumber, sources)
  if (matchedIndex >= 0) return matchedIndex
  const container = target.closest('.kb-markdown')
  const citeNodes = Array.from(container?.querySelectorAll<HTMLElement>('.kb-cite') || [])
  const fallbackByCite = new Map<number, number>()
  let nextFallback = 0
  for (const item of citeNodes) {
    const itemNumber = Number(item.dataset.cite || 0)
    if (citationSourceIndex(itemNumber, sources) >= 0) continue
    if (!fallbackByCite.has(itemNumber) && nextFallback < sources.length) {
      fallbackByCite.set(itemNumber, nextFallback)
      nextFallback += 1
    }
  }
  return fallbackByCite.get(citeNumber) ?? -1
}

function showCite(target: HTMLElement, msg: ChatMessage) {
  const sourceIndex = resolveCitationSourceIndex(target, msg)
  const source = (msg.sources || [])[sourceIndex]
  if (!source) return
  const rect = target.getBoundingClientRect()
  cite.source = source
  cite.x = Math.min(rect.left, window.innerWidth - 620)
  cite.y = Math.min(rect.bottom + 8, window.innerHeight - 480)
  cite.visible = true
}

function handleCiteHover(event: MouseEvent, msg: ChatMessage) {
  const target = event.target as HTMLElement
  if (!target.classList.contains('kb-cite')) return
  cancelCloseCite()
  showCite(target, msg)
}

function handleCiteClick(event: MouseEvent, msg: ChatMessage) {
  const target = event.target as HTMLElement
  if (!target.classList.contains('kb-cite')) return
  cancelCloseCite()
  showCite(target, msg)
}

function handleCiteLeave(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.classList?.contains('kb-cite')) return
  scheduleCloseCite()
}

function scheduleCloseCite() {
  cancelCloseCite()
  citeCloseTimer = window.setTimeout(() => {
    cite.visible = false
  }, 220)
}

function cancelCloseCite() {
  if (citeCloseTimer) {
    window.clearTimeout(citeCloseTimer)
    citeCloseTimer = undefined
  }
}

function closeCite() {
  cancelCloseCite()
  cite.visible = false
}

function handleGlobalClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.kb-cite-pop') && !target.classList.contains('kb-cite')) closeCite()
}

function handleQueryKeydown(event: KeyboardEvent) {
  if (event.shiftKey) return
  event.preventDefault()
  void handleAsk()
}

async function handleAsk() {
  const text = query.value.trim()
  if (!text || asking.value) return
  chat.value.push({ role: 'user', content: text })
  chat.value.push({ role: 'assistant', content: '', sources: [] })
  const assistant = chat.value[chat.value.length - 1]
  query.value = ''
  searchResults.value = []
  asking.value = true
  scrollChat()
  try {
    const response = await fetch(knowledgeAskStreamUrl(), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, top_k: 5, session_id: currentSessionId.value, kb_ids: activeKbIds.value }),
    })
    if (!response.ok || !response.body) throw new Error(`请求失败（${response.status}）`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        let data: { answer?: string; done?: boolean; sources?: KnowledgeAskSource[]; error?: string; session_id?: string; session?: KnowledgeChatSession }
        try {
          data = JSON.parse(line.slice(5))
        } catch {
          continue
        }
        if (data.session_id) currentSessionId.value = data.session_id
        if (data.session) {
          chatSessions.value = [data.session, ...chatSessions.value.filter((item) => item.id !== data.session!.id)]
        }
        if (data.error) throw new Error(data.error)
        if (typeof data.answer === 'string' && data.answer) {
          assistant.content = data.answer
          scrollChat()
        }
        if (data.done) {
          assistant.sources = data.sources || []
          void loadChatSessions()
        }
      }
    }
    if (!assistant.content) assistant.content = '知识库中没有找到相关内容。'
  } catch (error) {
    assistant.failed = true
    if (!assistant.content) assistant.content = `回答失败：${errorMessage(error)}`
  } finally {
    asking.value = false
    scrollChat()
  }
}

// 引用文档预览抽屉：PDF/图片内嵌原件并跳到引用所在页，其余展示分块文本并高亮命中片段。
const PREVIEW_FILE_PATTERN = /\.(pdf|png|jpe?g|gif|bmp|webp)$/i
const preview = reactive({
  visible: false,
  name: '',
  datasetId: '',
  docId: '',
  mode: 'file' as 'file' | 'chunks',
  chunks: [] as string[],
  loading: false,
  page: 0,
  highlight: -1,
})

function locateChunk(chunks: string[], text: string) {
  // 引用片段与解析分块按去空白前缀互相包含来匹配。
  const norm = (value: string) => value.replace(/\s+/g, '')
  const probe = norm(text).slice(0, 60)
  if (!probe) return -1
  return chunks.findIndex((chunk) => {
    const c = norm(chunk)
    return c.includes(probe.slice(0, 40)) || (c.length >= 30 && probe.includes(c.slice(0, 30)))
  })
}

async function openPreview(source: { doc_id?: string; dataset_id?: string; doc_name: string; text?: string; page?: number }) {
  if (!source.doc_id || !source.dataset_id) {
    ElMessage.info('该引用暂不支持原文预览')
    return
  }
  closeCite()
  preview.name = source.doc_name
  preview.datasetId = source.dataset_id
  preview.docId = source.doc_id
  preview.mode = PREVIEW_FILE_PATTERN.test(source.doc_name) ? 'file' : 'chunks'
  preview.chunks = []
  preview.page = Number(source.page || 0)
  preview.highlight = -1
  preview.visible = true
  if (preview.mode === 'chunks') {
    preview.loading = true
    try {
      const result = await getKnowledgeDocChunks(source.dataset_id, source.doc_id)
      preview.chunks = result.chunks
      preview.highlight = source.text ? locateChunk(result.chunks, source.text) : -1
      if (preview.highlight >= 0) {
        // 等抽屉动画结束再滚动到高亮片段。
        window.setTimeout(() => {
          document.getElementById(`kb-chunk-${preview.highlight}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 300)
      }
    } catch (error) {
      ElMessage.error(errorMessage(error))
    } finally {
      preview.loading = false
    }
  }
}

function previewFileUrl() {
  const url = knowledgeDocFileUrl(preview.datasetId, preview.docId)
  // 浏览器内置 PDF 查看器支持 #page= 定位到引用所在页。
  return preview.page > 0 && /\.pdf$/i.test(preview.name) ? `${url}#page=${preview.page}` : url
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

// ---- 引擎设置（管理员）：RAGFlow 配置/初始化/控制台直达全部整合在本页 ----
const isAdmin = computed(() => Boolean(authState.user?.is_admin))
const showSettings = ref(false)
const settingsLoaded = ref(false)
const cfgLoading = reactive({ config: false, status: false, save: false, test: false, bootstrap: false, chunk: false, sso: false })
const kbForm = reactive({
  provider: 'builtin' as 'builtin' | 'ragflow',
  api_url: '',
  api_key: '',
  model: 'bge-m3',
  vector_store: 'local' as 'local' | 'qdrant',
  qdrant_url: '',
  rerank_model: '',
  ragflow_url: '',
  ragflow_public_url: '',
  ragflow_api_key: '',
})
const kbApiKeyStatus = ref('未配置')
const kbRagflowKeyStatus = ref('未配置')
const ragflowStatus = ref<RagflowStatus | null>(null)
const ragflowChunkForm = reactive({ chunk_method: 'naive', chunk_token_num: 512, layout_recognize: 'DeepDOC' })

function applyKbConfig(config: Awaited<ReturnType<typeof getKnowledgeConfig>>) {
  kbForm.provider = config.provider || 'builtin'
  kbForm.api_url = config.api_url || ''
  kbForm.api_key = ''
  kbForm.model = config.model || 'bge-m3'
  kbForm.vector_store = config.vector_store || 'local'
  kbForm.qdrant_url = config.qdrant_url || 'http://qdrant:6333'
  kbForm.rerank_model = config.rerank_model || ''
  kbForm.ragflow_url = config.ragflow_url || ''
  kbForm.ragflow_public_url = config.ragflow_public_url || ''
  kbForm.ragflow_api_key = ''
  kbApiKeyStatus.value = config.api_key_masked || '未配置'
  kbRagflowKeyStatus.value = config.ragflow_api_key_masked || '未配置'
}

async function loadKbConfig() {
  cfgLoading.config = true
  try {
    applyKbConfig(await getKnowledgeConfig())
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.config = false
  }
}

async function loadRagflowStatus() {
  cfgLoading.status = true
  try {
    const status = await getRagflowStatus()
    ragflowStatus.value = status
    ragflowChunkForm.chunk_method = status.chunk_method || 'naive'
    ragflowChunkForm.chunk_token_num = status.chunk_token_num || 512
    ragflowChunkForm.layout_recognize = status.layout_recognize || 'DeepDOC'
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.status = false
  }
}

function toggleSettings() {
  showSettings.value = !showSettings.value
  if (showSettings.value && !settingsLoaded.value) {
    settingsLoaded.value = true
    void loadKbConfig()
    void loadRagflowStatus()
  }
}

async function handleSaveKbConfig() {
  cfgLoading.save = true
  try {
    applyKbConfig(await saveKnowledgeConfig({ ...kbForm }))
    ElMessage.success('知识库配置已保存')
    void loadDocs()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.save = false
  }
}

async function handleTestKbConfig() {
  cfgLoading.test = true
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
    cfgLoading.test = false
  }
}

async function handleRagflowBootstrap() {
  cfgLoading.bootstrap = true
  try {
    const result = await bootstrapRagflow()
    ElMessage.success(result.steps.join('；'))
    await Promise.all([loadKbConfig(), loadRagflowStatus()])
    void loadDocs()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.bootstrap = false
  }
}

async function handleSaveRagflowChunk() {
  cfgLoading.chunk = true
  try {
    const result = await saveRagflowChunkConfig({ ...ragflowChunkForm })
    ElMessage.success(`解析配置已应用到 ${result.updated.length} 个知识库。${result.hint || ''}`)
    if (result.warning) ElMessage.warning(result.warning)
    void loadRagflowStatus()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.chunk = false
  }
}

// ---- 数字人接入：让 3D 数字人回答时检索指定知识库 ----
const dhDialogVisible = ref(false)
const dhSaving = ref(false)
const dhForm = reactive({ enabled: false, kb_ids: [] as string[] })

async function openDhDialog() {
  dhDialogVisible.value = true
  try {
    const config = await getDigitalHumanKbConfig()
    dhForm.enabled = config.enabled
    dhForm.kb_ids = config.kb_ids || []
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleSaveDhConfig() {
  dhSaving.value = true
  try {
    await saveDigitalHumanKbConfig({ enabled: dhForm.enabled, kb_ids: dhForm.kb_ids })
    ElMessage.success(dhForm.enabled ? '数字人已连接知识库' : '数字人已断开知识库')
    dhDialogVisible.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    dhSaving.value = false
  }
}

// RAGFlow 控制台内嵌在本页（iframe + 免登录），不跳转外部窗口。
const consoleUrl = ref('')

async function openRagflowConsole() {
  cfgLoading.sso = true
  try {
    const result = await getRagflowSso()
    // 未配置浏览器访问地址时，按当前站点主机 + 本环境 RAGFlow Web 端口 18088 推断（9380 是纯 API 端口）。
    const url = result.url || `${window.location.protocol}//${window.location.hostname}:18088/login?auth=${encodeURIComponent(result.auth)}`
    consoleUrl.value = url
    showSettings.value = false
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    cfgLoading.sso = false
  }
}

function closeRagflowConsole() {
  consoleUrl.value = ''
  void loadDocs()
}

function applyDocList(result: Awaited<ReturnType<typeof listKnowledgeDocs>>) {
  if (JSON.stringify(docs.value) !== JSON.stringify(result.docs)) docs.value = result.docs
  embeddingModel.value = result.embedding_model
  staleDocs.value = result.stale_docs || []
  canManage.value = result.can_manage !== false
  provider.value = result.provider || ''
}

let docsRequest = 0
let knowledgeActive = true
async function loadDocs(silent = false) {
  if (!knowledgeActive) return
  stopParsingPoll()
  const requestId = ++docsRequest
  const scope = scopeParam.value
  docsLoading.value = !silent && !docs.value.length
  try {
    const result = await listKnowledgeDocs(scope)
    if (knowledgeActive && requestId === docsRequest && scope === scopeParam.value) applyDocList(result)
  } catch (error) {
    if (!silent && knowledgeActive && requestId === docsRequest) ElMessage.error(errorMessage(error))
  } finally {
    if (knowledgeActive && requestId === docsRequest) {
      docsLoading.value = false
      schedulePollParsing()
    }
  }
}

async function loadKbs(selectId = '') {
  try {
    const result = await listKnowledgeKbs()
    kbs.value = result.kbs
    provider.value = result.provider || ''
    normalizeChatKbSelection(selectedKbIds.value)
    const exists = result.kbs.some((kb) => kb.id === currentKbId.value)
    if (selectId && result.kbs.some((kb) => kb.id === selectId)) {
      currentKbId.value = selectId
    } else if (!currentKbId.value || !exists) {
      currentKbId.value = (result.kbs.find((kb) => kb.default) || result.kbs[0])?.id || ''
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function selectKb(id: string) {
  if (currentKbId.value === id) return
  currentKbId.value = id
  docs.value = []
  void loadDocs()
}

async function handleCreateKb() {
  let name = ''
  try {
    const result = await ElMessageBox.prompt('输入新知识库名称（仅自己可见，可分主题建多个）', '新建知识库', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    })
    name = result.value.trim()
  } catch {
    return
  }
  try {
    const created = await manageKnowledgeKb({ action: 'create', name })
    ElMessage.success(`知识库《${created.name || name}》已创建`)
    await loadKbs(created.id || '')
    void loadDocs()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleDeleteKb(kb: KnowledgeKb) {
  try {
    await ElMessageBox.confirm(`确认删除知识库《${kb.name}》？其中 ${kb.document_count} 个文档将一并删除。`, '删除知识库', { type: 'warning' })
  } catch {
    return
  }
  try {
    await manageKnowledgeKb({ action: 'delete', id: kb.id })
    ElMessage.success('已删除')
    await loadKbs()
    void loadDocs()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

// 有解析中的文档时每 4 秒静默刷新，实时展示 DeepDoc 解析进度。
let pollTimer: number | undefined

function stopParsingPoll() {
  if (pollTimer !== undefined) window.clearTimeout(pollTimer)
  pollTimer = undefined
}

function schedulePollParsing() {
  stopParsingPoll()
  if (!knowledgeActive || !docs.value.some((doc) => doc.status === 'parsing')) return
  pollTimer = window.setTimeout(() => void loadDocs(true), 4000)
}

function pauseKnowledge() {
  knowledgeActive = false
  ++docsRequest
  docsLoading.value = false
  stopParsingPoll()
  closeCite()
}
onDeactivated(pauseKnowledge)
onUnmounted(pauseKnowledge)
onActivated(() => {
  const resuming = !knowledgeActive
  knowledgeActive = true
  if (resuming) void loadDocs(true)
})

function pickFiles() {
  fileInputRef.value?.click()
}

function fileToBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

async function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  uploading.value = true
  try {
    for (const file of files) {
      const data = await fileToBase64(file)
      await uploadKnowledgeDoc(file.name, data, scopeParam.value)
      ElMessage.success(`《${file.name}》已入库`)
    }
    await loadDocs()
  } catch (error) {
    ElMessage.error('入库失败：' + errorMessage(error))
  } finally {
    uploading.value = false
  }
}

async function handleDelete(doc: KnowledgeDoc) {
  try {
    await ElMessageBox.confirm(`确认删除《${doc.name}》？`, '删除文档', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteKnowledgeDoc(doc.id, scopeParam.value)
    ElMessage.success('已删除')
    void loadDocs()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleReparse(doc: KnowledgeDoc) {
  try {
    await reparseKnowledgeDoc(doc.id, scopeParam.value)
    ElMessage.success(`《${doc.name}》已重新加入解析队列`)
    window.setTimeout(() => void loadDocs(), 1500)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleSearch() {
  const text = query.value.trim()
  if (!text) return
  searching.value = true
  try {
    const result = await searchKnowledge(text, 8, activeKbIds.value)
    searchResults.value = result.results
    warning.value = result.warning || ''
    if (!result.results.length) ElMessage.info('没有检索到相关内容')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    searching.value = false
  }
}


onMounted(async () => {
  window.addEventListener('click', handleGlobalClick)
  void ensureSession()
  await loadKbs()
  await loadChatSessions(true)
  void loadChatHistory()
  void loadDocs()
})

onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
})
</script>

<template>
  <section class="kb-main">
    <header class="kb-head">
      <div class="kb-head-actions">
        <button class="kb-btn" type="button" title="配置 3D 数字人回答时是否检索知识库" @click="openDhDialog">
          <el-icon><ChatDotRound /></el-icon> 数字人接入
        </button>
        <button v-if="provider === 'ragflow' || consoleUrl" :class="['kb-btn', { 'kb-btn--active': consoleUrl }]" type="button" :disabled="cfgLoading.sso" :title="consoleUrl ? '关闭控制台返回文档视图' : '在本页打开你自己的 RAGFlow 租户控制台（免登录）'" @click="consoleUrl ? closeRagflowConsole() : openRagflowConsole()">
          <el-icon><Link /></el-icon> {{ cfgLoading.sso ? '登录中…' : (consoleUrl ? '返回知识库' : 'RAGFlow 控制台') }}
        </button>
        <button v-if="isAdmin" :class="['kb-btn', { 'kb-btn--active': showSettings }]" type="button" @click="toggleSettings">
          <el-icon><Setting /></el-icon> 引擎设置
        </button>
        <button v-if="provider === 'ragflow' || kbForm.provider === 'ragflow'" class="kb-btn" type="button" title="上传 PDF，用 DeepDoc OCR 解析成图文并茂的 Markdown，并可框选区域校准图文错配" @click="pdfMdVisible = true">
          <el-icon><Document /></el-icon> PDF 转 Markdown
        </button>
        <button class="kb-btn" type="button" title="查看外部系统调用知识库的接入说明" @click="openExternalGuide">
          <el-icon><Link /></el-icon> 外部调用
        </button>
      </div>
      <input ref="fileInputRef" type="file" multiple accept=".txt,.md,.csv,.log,.json,.html,.htm,.doc,.docx,.pdf,.xls,.xlsx,.ppt,.pptx,.wps" hidden @change="handleFiles" />
    </header>

    <section v-if="isAdmin && showSettings" class="kb-settings">
      <header class="kb-settings-head">
        <h3>知识库引擎设置</h3>
        <span v-if="ragflowStatus" class="kb-settings-status">
          RAGFlow：{{ ragflowStatus.reachable ? `运行中 v${ragflowStatus.version || '?'}` : '不可达' }}
          · {{ ragflowStatus.configured ? 'API Key 已配置' : '未初始化' }}
          <template v-if="ragflowStatus.admin_email"> · 共用账号 {{ ragflowStatus.admin_email }}</template>
          <a href="javascript:;" @click="loadRagflowStatus">刷新</a>
        </span>
      </header>
      <p v-if="ragflowStatus?.error" class="kb-warning">{{ ragflowStatus.error }}</p>

      <div class="kb-settings-grid">
        <label>
          <span>知识库引擎</span>
          <select v-model="kbForm.provider">
            <option value="ragflow">RAGFlow（推荐：DeepDoc 解析 + 混合检索 + 引用问答）</option>
            <option value="builtin">内置引擎（嵌入 + Qdrant/本地向量）</option>
          </select>
        </label>
        <template v-if="kbForm.provider === 'ragflow'">
          <label>
            <span>RAGFlow API 地址（后端访问）</span>
            <input v-model="kbForm.ragflow_url" placeholder="容器内 http://host.docker.internal:9380" />
          </label>
          <label>
            <span>RAGFlow 浏览器访问地址</span>
            <input v-model="kbForm.ragflow_public_url" placeholder="如 http://10.1.6.230:18088 或 https://ragflow.chencytech.com" />
            <em>「打开 RAGFlow 控制台」用此地址免登录跳转</em>
          </label>
          <label>
            <span>RAGFlow API Key</span>
            <input v-model="kbForm.ragflow_api_key" type="password" placeholder="留空保持原值；点「一键初始化」自动生成" />
            <em>状态：{{ kbRagflowKeyStatus }}</em>
          </label>
          <label>
            <span>解析分块模板</span>
            <select v-model="ragflowChunkForm.chunk_method">
              <option v-for="item in ragflowStatus?.chunk_methods || []" :key="item.id" :value="item.id">{{ item.label }}</option>
            </select>
            <em>制度文件选「法规制度」、报表选「表格」，调整后旧文档需重新解析</em>
          </label>
          <label>
            <span>分块大小（token）</span>
            <input v-model.number="ragflowChunkForm.chunk_token_num" type="number" min="64" max="2048" placeholder="512" />
          </label>
          <label>
            <span>版面识别（解析速度）</span>
            <select v-model="ragflowChunkForm.layout_recognize">
              <option value="DeepDOC">DeepDOC（OCR+版面分析，扫描件/复杂排版）</option>
              <option value="Plain Text">Plain Text（快速：直接抽取文本层，快一到两个数量级）</option>
            </select>
            <em>制度文件、系统导出的 PDF/Word 选 Plain Text；拍照扫描件必须用 DeepDOC</em>
          </label>
        </template>
        <template v-else>
          <label>
            <span>嵌入 API 地址</span>
            <input v-model="kbForm.api_url" placeholder="留空复用大模型地址；本地 Xinference 填 http://主机:9997" />
          </label>
          <label>
            <span>嵌入 API Key</span>
            <input v-model="kbForm.api_key" type="password" placeholder="无鉴权可留空；留空保持原 Key" />
            <em>状态：{{ kbApiKeyStatus }}</em>
          </label>
          <label>
            <span>嵌入模型名称</span>
            <input v-model="kbForm.model" placeholder="bge-m3 / bge-large-zh-v1.5" />
          </label>
          <label>
            <span>向量存储</span>
            <select v-model="kbForm.vector_store">
              <option value="local">本地文件（零依赖，小规模）</option>
              <option value="qdrant">Qdrant 向量库（推荐）</option>
            </select>
          </label>
          <label v-if="kbForm.vector_store === 'qdrant'">
            <span>Qdrant 地址</span>
            <input v-model="kbForm.qdrant_url" placeholder="容器内 http://qdrant:6333" />
          </label>
          <label>
            <span>重排模型（可选）</span>
            <input v-model="kbForm.rerank_model" placeholder="留空关闭；如 bge-reranker-v2-m3" />
          </label>
        </template>
      </div>

      <div class="kb-settings-actions">
        <button class="kb-btn" type="button" :disabled="cfgLoading.test" @click="handleTestKbConfig">{{ cfgLoading.test ? '测试中…' : '测试连接' }}</button>
        <template v-if="kbForm.provider === 'ragflow'">
          <button class="kb-btn" type="button" :disabled="cfgLoading.bootstrap" @click="handleRagflowBootstrap" title="自动注册托管账号、生成 API Key、同步平台大模型，账号与办公助手共用">
            {{ cfgLoading.bootstrap ? '初始化中…' : '一键初始化（账号打通）' }}
          </button>
          <button class="kb-btn" type="button" :disabled="cfgLoading.chunk" @click="handleSaveRagflowChunk">{{ cfgLoading.chunk ? '应用中…' : '应用解析配置' }}</button>
          <button class="kb-btn" type="button" :disabled="cfgLoading.sso || !ragflowStatus?.sso_available" :title="ragflowStatus?.sso_available ? '使用托管账号免登录打开 RAGFlow 后台' : '先执行一键初始化托管账号'" @click="openRagflowConsole">
            <el-icon><Link /></el-icon> {{ cfgLoading.sso ? '登录中…' : '打开 RAGFlow 控制台' }}
          </button>
        </template>
        <button class="kb-btn kb-btn--primary" type="button" :disabled="cfgLoading.save" @click="handleSaveKbConfig">{{ cfgLoading.save ? '保存中…' : '保存配置' }}</button>
      </div>

      <template v-if="kbForm.provider === 'ragflow' && ragflowStatus">
        <table v-if="ragflowStatus.datasets.length" class="kb-settings-table">
          <thead><tr><th>知识库数据集</th><th>文档数</th><th>分块数</th><th>解析模板</th></tr></thead>
          <tbody>
            <tr v-for="ds in ragflowStatus.datasets" :key="ds.id">
              <td>{{ ds.name }}</td>
              <td>{{ ds.document_count }}</td>
              <td>{{ ds.chunk_count }}</td>
              <td>{{ ds.chunk_method }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="ragflowStatus.reachable" class="kb-empty">还没有任何知识库数据集，上传第一个文档后自动创建。</p>
      </template>
    </section>

    <Teleport to="body">
      <div v-if="cite.visible && cite.source" class="kb-cite-pop" :style="{ left: cite.x + 'px', top: cite.y + 'px' }" @click.stop @mouseenter="cancelCloseCite" @mouseleave="scheduleCloseCite">
        <header>
          <el-icon><Document /></el-icon>
          <strong :title="cite.source.doc_name">{{ cite.source.doc_name }}</strong>
          <span>{{ (cite.source.score * 100).toFixed(1) }}%</span>
        </header>
        <div class="kb-cite-text kb-markdown" v-html="renderChunk(cite.source.text)"></div>
        <footer>
          <button v-if="cite.source.doc_id && cite.source.dataset_id" type="button" @click="openPreview(cite.source!)">预览原文</button>
          <button type="button" @click="closeCite">关闭</button>
        </footer>
      </div>
    </Teleport>

    <el-drawer v-model="preview.visible" :title="preview.name" size="58%" class="kb-preview-drawer">
      <iframe v-if="preview.mode === 'file'" :src="previewFileUrl()" class="kb-preview-frame" :title="preview.name" />
      <div v-else class="kb-preview-chunks">
        <p v-if="preview.loading" class="kb-empty">加载中…</p>
        <p v-else-if="!preview.chunks.length" class="kb-empty">该文档暂无可展示的解析内容</p>
        <article v-for="(chunk, i) in preview.chunks" :id="`kb-chunk-${i}`" :key="i" :class="{ highlight: i === preview.highlight }">
          <span>{{ i === preview.highlight ? '★ 引用片段' : `#${i + 1}` }}</span>
          <div class="kb-chunk-body kb-markdown" v-html="renderChunk(chunk)"></div>
        </article>
      </div>
    </el-drawer>

    <el-dialog v-model="dhDialogVisible" title="数字人连接知识库" width="460px">
      <div class="kb-dh-config">
        <label class="kb-dh-switch">
          <el-switch v-model="dhForm.enabled" />
          <span>数字人回答时检索知识库（命中资料优先作答，闲聊不受影响）</span>
        </label>
        <template v-if="dhForm.enabled">
          <p class="kb-dh-hint">选择要连接的知识库（不选 = 全部可见知识库）：</p>
          <el-checkbox-group v-model="dhForm.kb_ids" class="kb-dh-list">
            <el-checkbox v-for="kb in kbs" :key="kb.id" :value="kb.id" :label="kb.id">
              {{ kb.shared ? '🏢 ' : '' }}{{ kb.name }}（{{ kb.document_count }} 文档）
            </el-checkbox>
          </el-checkbox-group>
        </template>
      </div>
      <template #footer>
        <button class="kb-btn" type="button" @click="dhDialogVisible = false">取消</button>
        <button class="kb-btn kb-btn--primary" type="button" :disabled="dhSaving" @click="handleSaveDhConfig">{{ dhSaving ? '保存中…' : '保存' }}</button>
      </template>
    </el-dialog>

    <section v-if="consoleUrl" class="kb-console">
      <iframe :src="consoleUrl" class="kb-console-frame" title="RAGFlow 控制台" allow="clipboard-write" />
    </section>

    <div v-else class="kb-body">
      <aside class="kb-sessions">
        <header>
          <h3>会话</h3>
          <button type="button" title="新建会话" @click="startNewChat">＋ 新建</button>
        </header>
        <p v-if="sessionsLoading" class="kb-empty">加载中…</p>
        <p v-else-if="!chatSessions.length" class="kb-empty">还没有会话</p>
        <article
          v-for="session in chatSessions"
          :key="session.id"
          :class="['kb-session-item', { active: session.id === currentSessionId }]"
        >
          <button class="kb-session-main" type="button" @click="selectChatSession(session.id)">
            <strong :title="session.title">{{ splitSessionTitle(session.title).topic }}</strong>
            <span v-if="splitSessionTitle(session.title).date">{{ splitSessionTitle(session.title).date }}</span>
            <em>{{ session.message_count }} 条消息</em>
          </button>
          <button class="kb-session-delete" type="button" title="删除会话" aria-label="删除会话" @click="deleteChatSession(session.id)">
            <el-icon><Delete /></el-icon>
          </button>
        </article>
      </aside>

      <section class="kb-stage">
        <p v-if="warning" class="kb-warning">{{ warning }}</p>

        <div ref="chatBodyRef" class="kb-chat">
          <p v-if="!chat.length && !searchResults.length" class="kb-empty kb-chat-empty">
            你好！我是企业知识库助手，回答会标注引用来源——<br />
            悬浮角标查看原文片段，点击文档名预览原文。<br />
            问答覆盖你的全部个人知识库与全员共享知识库。
          </p>

          <div v-for="(msg, i) in chat" :key="i" :class="['kb-msg', msg.role]">
            <div v-if="msg.role === 'user'" class="kb-bubble kb-bubble--user">{{ msg.content }}</div>
            <div v-else :class="['kb-bubble', 'kb-bubble--assistant', { failed: msg.failed }]">
              <div v-if="!msg.content && asking && i === chat.length - 1" class="kb-typing"><span></span><span></span><span></span></div>
              <div v-else class="kb-markdown" v-html="renderAnswer(msg)" @mouseover="handleCiteHover($event, msg)" @click="handleCiteClick($event, msg)" @mouseout="handleCiteLeave($event)"></div>
              <div v-if="msg.sources?.length" class="kb-refs">
                <span class="kb-refs-label">引用 {{ msg.sources.length }} 篇</span>
                <button v-for="(source, idx) in msg.sources" :key="source.index" type="button" class="kb-ref-chip" :title="htmlToText(source.text)" @click="openPreview(source)">
                  <span class="kb-ref-idx">{{ idx + 1 }}</span>
                  <el-icon><Document /></el-icon>
                  <span class="kb-ref-name">{{ source.doc_name }}</span>
                  <em>{{ (source.score * 100).toFixed(0) }}%</em>
                </button>
              </div>
            </div>
          </div>

          <section v-if="searchResults.length" class="kb-results">
            <h3>检索结果 <a href="javascript:;" @click="searchResults = []">清除</a></h3>
            <article v-for="(item, index) in searchResults" :key="index" class="kb-result">
              <header>
                <el-icon><Document /></el-icon>
                <strong>{{ item.doc_name }}</strong>
                <button v-if="item.dataset_id" type="button" class="kb-result-preview" @click="openPreview(item)">预览</button>
                <span>相关度 {{ (item.score * 100).toFixed(1) }}%</span>
              </header>
              <div class="kb-result-text kb-markdown" v-html="renderChunk(item.text)"></div>
            </article>
          </section>
        </div>

        <div class="kb-chat-scope">
          <span>检索范围</span>
          <el-select
            v-model="selectedKbIds"
            class="kb-chat-scope-select"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            :max-collapse-tags="2"
            placeholder="全部知识库"
          >
            <el-option
              v-for="kb in kbs"
              :key="kb.id"
              :label="`${kb.shared ? '共享 · ' : ''}${kb.name}（${kb.document_count} 文档）`"
              :value="kb.id"
              :disabled="kb.chunk_count <= 0"
            />
          </el-select>
          <small>{{ selectedKbSummary }} · 个人知识库优先</small>
        </div>

        <div class="kb-query">
          <button v-if="chat.length" class="kb-btn kb-btn--danger kb-clear-chat" type="button" @click="clearChat">
            <el-icon><Delete /></el-icon> 清空对话
          </button>
          <textarea v-model="query" rows="2" placeholder="输入问题，Enter 发送；Shift+Enter 换行…" @keydown.enter="handleQueryKeydown" />
          <button class="kb-btn" type="button" :disabled="searching" @click="handleSearch">
            <el-icon><Search /></el-icon> {{ searching ? '检索中…' : '语义检索' }}
          </button>
          <button class="kb-btn kb-btn--primary" type="button" :disabled="asking" @click="handleAsk">
            <el-icon><ChatDotRound /></el-icon> {{ asking ? '回答中…' : '发送' }}
          </button>
        </div>
      </section>

      <aside class="kb-docs">
        <div class="kb-kbs">
          <header>
            <h3>知识库（{{ kbs.length }}）</h3>
            <div class="kb-kbs-actions">
              <button v-if="canManage" type="button" class="kb-kbs-upload" :disabled="uploading" :title="currentKb ? `上传文档到《${currentKb.name}》` : '请先选择知识库'" @click="pickFiles">
                <el-icon><UploadFilled /></el-icon> {{ uploading ? '入库中…' : '上传' }}
              </button>
              <button v-if="provider === 'ragflow'" type="button" class="kb-kbs-add" title="新建知识库" @click="handleCreateKb">＋ 新建</button>
            </div>
          </header>
          <p v-if="canManage && currentKb" class="kb-upload-target">上传文档将保存到：<strong>{{ currentKb.shared ? '共享库' : currentKb.name }}</strong></p>
          <button
            v-for="kb in kbs"
            :key="kb.id"
            :class="['kb-kbs-item', { active: kb.id === currentKbId }]"
            type="button"
            @click="selectKb(kb.id)"
          >
            <span class="kb-kbs-name" :title="kb.name">{{ kb.shared ? '🏢 ' : '' }}{{ kb.name }}</span>
            <span class="kb-kbs-count">{{ kb.document_count }} 文档</span>
            <span
              v-if="!kb.shared && provider === 'ragflow'"
              class="kb-kbs-del"
              title="删除知识库"
              @click.stop="handleDeleteKb(kb)"
            ><el-icon><Delete /></el-icon></span>
          </button>
        </div>
        <h3>文档（{{ docs.length }}）</h3>
        <p v-if="docsLoading" class="kb-empty">加载中…</p>
        <p v-else-if="!docs.length" class="kb-empty">还没有文档，请在上方选择知识库后上传</p>
        <article v-for="doc in docs" :key="doc.id" :class="['kb-doc', { stale: staleDocs.includes(doc.name) }]">
          <strong :title="doc.name">{{ doc.name }}</strong>
          <span>{{ doc.created_at }} · {{ doc.chunk_count }} 块 · {{ doc.uploaded_by }}</span>
          <template v-if="doc.status === 'parsing'">
            <span class="kb-doc-stale" :title="doc.progress_msg">解析中 {{ doc.progress ?? 0 }}%<template v-if="doc.progress_msg"> · {{ doc.progress_msg }}</template></span>
            <span class="kb-doc-progress"><i :style="{ width: Math.max(2, doc.progress ?? 0) + '%' }" /></span>
          </template>
          <span v-else-if="doc.status === 'failed'" class="kb-doc-stale" :title="doc.progress_msg">解析失败{{ doc.progress_msg ? '：' + doc.progress_msg : '' }}</span>
          <span v-if="staleDocs.includes(doc.name)" class="kb-doc-stale">嵌入模型已变更，需重新上传</span>
          <span v-if="canManage" class="kb-doc-actions">
            <button type="button" aria-label="重新解析" title="重新解析" @click="handleReparse(doc)">
              <el-icon><RefreshRight /></el-icon>
            </button>
            <button type="button" aria-label="删除" title="删除" @click="handleDelete(doc)">
              <el-icon><Delete /></el-icon>
            </button>
          </span>
        </article>
      </aside>
    </div>

    <el-dialog v-model="externalGuideVisible" title="外部调用知识库" width="760px" class="kb-external-dialog">
      <div class="kb-external-guide">
        <p class="kb-external-intro">外部智能体、工作流或自建应用可通过标准 <strong>MCP Streamable HTTP</strong> 调用本平台知识库。调用会按“用户上下文”读取该用户的个人知识库与可见共享知识库。</p>

        <section>
          <h4>接入前准备</h4>
          <ol>
            <li>管理员在“设置中心 → MCP 管理”生成 MCP 密钥。</li>
            <li>调用方使用该密钥，并在请求头填写要访问的数据账号。</li>
            <li>请勿在浏览器前端、公开仓库或日志中暴露密钥。</li>
          </ol>
        </section>

        <section>
          <h4>通用 MCP 客户端配置</h4>
          <p>适用于 Claude、Cursor、Cline、OpenClaw、Cherry Studio 等支持 Streamable HTTP MCP 的客户端。</p>
          <pre>{{ externalMcpConfig }}</pre>
          <button class="kb-btn" type="button" @click="copyExternalGuide(externalMcpConfig)">复制 MCP 配置</button>
        </section>

        <section class="kb-ragflow-api-guide">
          <h4>标准 RAGFlow / OpenAI 兼容接口</h4>
          <p>适用于自建 Web 应用、Python/Java 服务、Dify、n8n 等可调用 OpenAI Chat Completions 的系统。该接口由 RAGFlow 原生提供，当前助手已绑定你的个人知识库和可见共享库。</p>
          <p v-if="externalApiLoading" class="kb-external-status">正在准备当前用户的 RAGFlow Chat Assistant…</p>
          <template v-else-if="externalApiInfo?.ready">
            <div class="kb-ragflow-endpoint"><span>OpenAI Base URL</span><code>{{ externalApiInfo.base_url }}</code></div>
            <div class="kb-ragflow-endpoint"><span>Chat Assistant ID</span><code>{{ externalApiInfo.chat_id }}</code></div>
            <p class="kb-external-status">{{ externalApiInfo.api_key_masked }} 已绑定 {{ externalApiInfo.dataset_count }} 个可检索知识库。</p>
          </template>
          <p v-else class="kb-external-status">{{ externalApiInfo?.hint || 'RAGFlow 信息暂不可用。' }}</p>
          <pre>{{ ragflowOpenAiExample }}</pre>
          <button class="kb-btn" type="button" @click="copyExternalGuide(ragflowOpenAiExample)">复制 RAGFlow 调用示例</button>
          <p class="kb-external-note">在 RAGFlow 控制台的 API Key 页面创建或查看 <code>ragflow_api_key</code>。传入 <code>stream: true</code> 即可接收 SSE 流式响应；非流式回答中的引用位于 <code>choices[0].message.reference</code>。</p>
        </section>

        <section>
          <h4>可用知识库工具</h4>
          <ul>
            <li><code>knowledge.datasets</code>：列出当前用户可访问的知识库。</li>
            <li><code>knowledge.search</code>：返回命中片段和来源；可传 <code>query</code>、<code>top_k</code>、<code>kb_ids</code>。</li>
            <li><code>knowledge.ask</code>：基于资料生成带引用来源的回答；可传 <code>question</code>、<code>top_k</code>、<code>kb_ids</code>。</li>
          </ul>
        </section>

        <section>
          <h4>直接测试：语义检索</h4>
          <pre>{{ externalSearchExample }}</pre>
          <button class="kb-btn" type="button" @click="copyExternalGuide(externalSearchExample)">复制测试命令</button>
        </section>

        <p class="kb-external-note">当前用户上下文：<strong>{{ externalMcpUsername }}</strong>。如需访问另一位用户的个人库，必须将请求头 <code>X-MCP-Username</code> 改为对应账号；共享库会依照平台权限自动过滤。</p>
      </div>
    </el-dialog>

    <PdfMarkdownStudio
      v-if="pdfMdVisible"
      :scope="scopeParam"
      :scope-label="currentKb ? (currentKb.shared ? '共享库' : currentKb.name) : '个人知识库'"
      :can-write="canManage"
      @close="pdfMdVisible = false"
      @stored="loadDocs()"
    />
  </section>
</template>
