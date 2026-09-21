<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Download, Message, Plus, Refresh, UploadFilled, View } from '@element-plus/icons-vue'
import {
  scanInvoiceAttachments,
  uploadReimbursementFile,
  fetchReimbursementUrl,
  fetchReimbursementEmail,
  mergeReimbursementPdf,
  downloadReimbursementInvoicesZip,
  reimbursementAttachmentUrl,
  reimbursementOfdPreviewUrl,
  reimbursementOutputUrl,
  listReimbursementSearches,
  loadReimbursementSearch,
  saveReimbursementSearch,
  type ReimbursementItem,
  type ReimbursementSearchRecord,
  type ReimbursementSearchSummary,
} from '../../services/personalWorkApi'
import './index.scss'

type ListItem = ReimbursementItem & { included: boolean }
type FilteredListItem = ListItem & { originalIndex: number }
type ScanChunkState = { start: string; end: string; status: 'pending' | 'scanning' | 'done' | 'failed'; total_scanned: number; item_count: number; message: string }
type SearchRecordWithChunks = ReimbursementSearchRecord & { scan_chunks?: ScanChunkState[] }

const INVOICE_TYPES = ['住宿', '火车', '机票', '餐饮', '市内交通', '通讯费', '其他']
const TYPE_COLORS: Record<string, string> = {
  住宿: 'purple', 火车: 'green', 机票: 'blue', 餐饮: 'orange', 市内交通: 'yellow', 通讯费: 'teal', 其他: 'gray',
}

function defaultDateRange(): [string, string] {
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 1)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return [fmt(start), fmt(end)]
}

const dateRange = ref<[string, string] | null>(defaultDateRange())
const account = ref<'company' | 'personal'>('personal')
const scanning = ref(false)
const scanStatus = ref('')
const scanChunks = ref<ScanChunkState[]>([])
const retryingChunkKey = ref('')
const merging = ref(false)
const batchDownloading = ref(false)
const items = ref<ListItem[]>([])
const invoiceTypeFilter = ref("")
const outputName = ref('')
const mergeResult = ref<{ filename: string; pages: number; train_ticket_groups?: number } | null>(null)
const mergeTrainTickets = ref(true)
const fileInput = ref<HTMLInputElement | null>(null)
const previewItem = ref<ListItem | null>(null)
const emailModalItem = ref<ListItem | null>(null)
const stubFileInput = ref<HTMLInputElement | null>(null)
const stubUploading = ref(false)
// 原始邮件 HTML 渲染
const emailHtmlLoading = ref(false)
const emailHtml = ref('')
const emailAttachments = ref<string[]>([])
// 行内"上传PDF"（针对缺少附件、仅有金额等信息的占位条目）
const rowUploadTarget = ref<ListItem | null>(null)
const rowFileInput = ref<HTMLInputElement | null>(null)
const searchRecords = ref<ReimbursementSearchSummary[]>([])
const currentSearchId = ref('')
const selectedSearchId = ref('')
const searchLoading = ref(false)
const searchSaving = ref(false)

// 拖拽状态
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

const selectedItems = computed(() => items.value.filter((i) => i.included))
const filteredItems = computed<FilteredListItem[]>(() => items.value
  .map((item, index) => Object.assign(item, { originalIndex: index }))
  .filter((item) => !invoiceTypeFilter.value || item.invoice_type === invoiceTypeFilter.value))
const filteredSelectedCount = computed(() => filteredItems.value.filter((i) => i.included).length)

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function defaultOutputName() {
  if (!dateRange.value) return '报销附件'
  return `报销附件_${dateRange.value[0]}_${dateRange.value[1]}`
}

// 先按 7 天切片扫描；某段失败时再拆成按日切片重扫
const SCAN_CHUNK_DAYS = 7

function splitDateRange(startText: string, endText: string, chunkDays = SCAN_CHUNK_DAYS): [string, string][] {
  const start = new Date(`${startText}T00:00:00`)
  const end = new Date(`${endText}T00:00:00`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return []
  const fmt = (date: Date) => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  const chunks: [string, string][] = []
  const cursor = new Date(start)
  while (cursor <= end) {
    const chunkStart = new Date(cursor)
    const chunkEnd = new Date(cursor)
    chunkEnd.setDate(chunkEnd.getDate() + chunkDays - 1)
    if (chunkEnd > end) chunkEnd.setTime(end.getTime())
    chunks.push([fmt(chunkStart), fmt(chunkEnd)])
    cursor.setTime(chunkEnd.getTime())
    cursor.setDate(cursor.getDate() + 1)
  }
  return chunks
}

function scanErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : '扫描失败'
}

async function scanInvoiceAttachmentsWithRetry(start: string, end: string, scanAccount: 'company' | 'personal', retry = 1) {
  let lastError: unknown = null
  for (let attempt = 0; attempt <= retry; attempt += 1) {
    try {
      return await scanInvoiceAttachments(start, end, scanAccount)
    } catch (error) {
      lastError = error
      if (attempt >= retry) break
    }
  }
  throw lastError
}

function toListItems(rawItems: ReimbursementItem[]): ListItem[] {
  return rawItems.map((item) => ({
    ...item,
    included: item.included ?? !item.is_stub,   // stub 默认不勾选
    source: item.source ?? 'mail',
  }))
}

function appendScannedItems(rawItems: ReimbursementItem[]) {
  items.value.push(...toListItems(rawItems))
  if (items.value.length && !outputName.value) outputName.value = defaultOutputName()
}

function applySearchRecord(record: SearchRecordWithChunks) {
  currentSearchId.value = record.id
  selectedSearchId.value = record.id
  account.value = record.account || account.value
  items.value = toListItems(record.items || [])
  scanChunks.value = (record.scan_chunks || []).map((chunk) => chunk.status === "scanning" ? { ...chunk, status: "failed" as const, message: "上次扫描中断，可重扫" } : chunk)
  const ranges = record.ranges || []
  if (ranges.length) {
    const first = ranges[0]
    const last = ranges[ranges.length - 1]
    if (first.start && last.end) dateRange.value = [first.start, last.end]
  }
  if (items.value.length && !outputName.value) outputName.value = defaultOutputName()
}

async function refreshSearchRecords() {
  try {
    const result = await listReimbursementSearches()
    searchRecords.value = result.records || []
    if (!selectedSearchId.value && currentSearchId.value) selectedSearchId.value = currentSearchId.value
  } catch {
    searchRecords.value = []
  }
}

async function persistCurrentSearch(start?: string, end?: string, totalScanned = 0, forceSave = false) {
  if (!forceSave && !items.value.length) return
  searchSaving.value = true
  try {
    const result = await saveReimbursementSearch({
      id: currentSearchId.value || undefined,
      account: account.value,
      start,
      end,
      total_scanned: totalScanned,
      items: items.value,
      scan_chunks: scanChunks.value,
    })
    // 只记录 id，不能用服务端快照覆盖运行中的切片状态（会导致界面停在"扫描中"）
    if (result.record?.id) {
      currentSearchId.value = result.record.id
      selectedSearchId.value = result.record.id
    }
    await refreshSearchRecords()
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : "搜索记录保存失败")
  } finally {
    searchSaving.value = false
  }
}

async function handleLoadSearch() {
  if (!selectedSearchId.value) return
  searchLoading.value = true
  try {
    const result = await loadReimbursementSearch(selectedSearchId.value)
    applySearchRecord(result.record)
    mergeResult.value = null
    scanStatus.value = '已加载搜索记录，可继续补充搜索或直接生成 PDF。'
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载搜索记录失败')
  } finally {
    searchLoading.value = false
  }
}

function handleNewSearch() {
  currentSearchId.value = ''
  selectedSearchId.value = ''
  items.value = []
  scanChunks.value = []
  scanStatus.value = ''
  mergeResult.value = null
  outputName.value = defaultOutputName()
}

function searchRecordLabel(record: ReimbursementSearchSummary) {
  return record.title + ' · ' + record.item_count + '张'
}

onMounted(async () => {
  await refreshSearchRecords()
})

function chunkKey(chunk: Pick<ScanChunkState, 'start' | 'end'>) {
  return `${chunk.start}_${chunk.end}`
}

function updateScanStatus() {
  const totalScanned = scanChunks.value.reduce((sum, chunk) => sum + chunk.total_scanned, 0)
  const failed = scanChunks.value.filter((chunk) => chunk.status === 'failed').length
  const done = scanChunks.value.filter((chunk) => chunk.status === 'done').length
  const base = `已完成 ${done}/${scanChunks.value.length} 段，共扫描 ${totalScanned} 封邮件，找到 ${items.value.length} 张发票。`
  scanStatus.value = failed ? `${base} ${failed} 段失败，可单独重扫。` : base
}

// ──────────── 扫描 ────────────
function replaceScanChunk(chunk: ScanChunkState, replacements: ScanChunkState[]) {
  const index = scanChunks.value.findIndex((item) => chunkKey(item) === chunkKey(chunk))
  if (index >= 0) scanChunks.value.splice(index, 1, ...replacements)
}

async function scanSingleChunk(chunk: ScanChunkState, index: number, labelPrefix = "正在扫描") {
  chunk.status = "scanning"
  chunk.message = "扫描中"
  scanStatus.value = scanChunks.value.length === 1
    ? labelPrefix + "邮件..."
    : labelPrefix + "第 " + (index + 1) + "/" + scanChunks.value.length + " 段：" + chunk.start + " 至 " + chunk.end
  try {
    const result = await scanInvoiceAttachmentsWithRetry(chunk.start, chunk.end, account.value, 0)
    const rawItems = result.items || []
    appendScannedItems(rawItems)
    chunk.status = "done"
    chunk.total_scanned = result.total_scanned || 0
    chunk.item_count = rawItems.length
    chunk.message = "完成，找到 " + rawItems.length + " 张"
  } catch (error) {
    chunk.message = "正在重试"
    try {
      const result = await scanInvoiceAttachmentsWithRetry(chunk.start, chunk.end, account.value, 1)
      const rawItems = result.items || []
      appendScannedItems(rawItems)
      chunk.status = "done"
      chunk.total_scanned = result.total_scanned || 0
      chunk.item_count = rawItems.length
      chunk.message = "重试完成，找到 " + rawItems.length + " 张"
    } catch (retryError) {
      chunk.status = "failed"
      chunk.message = scanErrorMessage(retryError)
    }
  }
  updateScanStatus()
  await persistCurrentSearch(chunk.start, chunk.end, chunk.total_scanned || 0, true)
}

async function scanDailySubChunks(chunk: ScanChunkState) {
  const dailyRanges = splitDateRange(chunk.start, chunk.end, 1)
  const dailyChunks: ScanChunkState[] = dailyRanges.map(([start, end]) => ({ start, end, status: "pending", total_scanned: 0, item_count: 0, message: "等待扫描" }))
  replaceScanChunk(chunk, dailyChunks)
  updateScanStatus()
  await persistCurrentSearch(chunk.start, chunk.end, 0, true)
  for (let index = 0; index < dailyChunks.length; index += 1) {
    const liveIndex = scanChunks.value.findIndex((item) => chunkKey(item) === chunkKey(dailyChunks[index]))
    const liveChunk = liveIndex >= 0 ? scanChunks.value[liveIndex] : dailyChunks[index]
    await scanSingleChunk(liveChunk, liveIndex, "正在重扫")
  }
}

async function handleScan() {
  if (!dateRange.value?.[0] || !dateRange.value?.[1]) {
    ElMessage.warning("请先选择日期范围")
    return
  }
  const chunks = splitDateRange(dateRange.value[0], dateRange.value[1])
  if (!chunks.length) {
    ElMessage.warning("日期范围不正确")
    return
  }
  const appendToCurrentRecord = Boolean(currentSearchId.value)
  scanning.value = true
  scanStatus.value = "正在连接邮箱扫描..."
  const nextChunks: ScanChunkState[] = chunks.map(([start, end]) => ({ start, end, status: "pending", total_scanned: 0, item_count: 0, message: "" }))
  if (appendToCurrentRecord) scanChunks.value.push(...nextChunks)
  else scanChunks.value = nextChunks
  if (!appendToCurrentRecord) items.value = []
  mergeResult.value = null
  try {
    await persistCurrentSearch(dateRange.value[0], dateRange.value[1], 0, true)
    await scanChunkQueue(nextChunks)
    await finishScanRun(dateRange.value[0], dateRange.value[1])
  } finally {
    scanning.value = false
  }
}

// 依次扫描一批切片；始终操作 scanChunks 里的响应式对象，保证界面状态实时更新
async function scanChunkQueue(chunks: ScanChunkState[], labelPrefix = "正在扫描") {
  for (const chunk of chunks) {
    const liveIndex = scanChunks.value.findIndex((item) => chunkKey(item) === chunkKey(chunk))
    const liveChunk = liveIndex >= 0 ? scanChunks.value[liveIndex] : chunk
    await scanSingleChunk(liveChunk, liveIndex, labelPrefix)
    // 7 天切片失败时，自动拆成按日切片重扫
    if (liveChunk.status === "failed" && splitDateRange(liveChunk.start, liveChunk.end, 1).length > 1) {
      await scanDailySubChunks(liveChunk)
    }
  }
}

// 全部切片扫完后：自动保存最终状态并给出结果提示
async function finishScanRun(start: string, end: string) {
  const totalScanned = scanChunks.value.reduce((sum, chunk) => sum + chunk.total_scanned, 0)
  await persistCurrentSearch(start, end, totalScanned, true)
  const failed = scanChunks.value.filter((chunk) => chunk.status === "failed").length
  if (failed) ElMessage.warning(`扫描完成，${failed} 段失败可点击重扫，记录已自动保存。`)
  else ElMessage.success("全部分段扫描完成，扫描记录已自动保存。")
}

async function retryScanChunk(chunk: ScanChunkState) {
  const key = chunkKey(chunk)
  retryingChunkKey.value = key
  try {
    if (splitDateRange(chunk.start, chunk.end, 1).length > 1) {
      await scanDailySubChunks(chunk)
      // replaceScanChunk is applied inside scanDailySubChunks before each daily retry.
      ElMessage.success("该分段已拆成按日切片重扫")
      return
    }
    await scanSingleChunk(chunk, scanChunks.value.findIndex((item) => chunkKey(item) === key), "正在重扫")
    ElMessage.success("该分段已重扫完成")
  } catch (error) {
    chunk.status = "failed"
    chunk.message = scanErrorMessage(error)
    updateScanStatus()
    await persistCurrentSearch(chunk.start, chunk.end, chunk.total_scanned || 0, true)
    ElMessage.error(chunk.message)
  } finally {
    retryingChunkKey.value = ""
  }
}

function toggleFilteredItems() {
  if (!filteredItems.value.length) return
  const allIncluded = filteredItems.value.every((i) => i.included)
  filteredItems.value.forEach((i) => (i.included = !allIncluded))
}

// ──────────── 拖拽排序 ────────────
function onDragStart(index: number, e: DragEvent) {
  dragIndex.value = index
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragOver(index: number, e: DragEvent) {
  e.preventDefault()
  e.dataTransfer!.dropEffect = 'move'
  dragOverIndex.value = index
}

function onDragLeave() {
  dragOverIndex.value = null
}

function onDrop(index: number) {
  if (dragIndex.value === null || dragIndex.value === index) {
    dragIndex.value = null
    dragOverIndex.value = null
    return
  }
  const arr = [...items.value]
  const [moved] = arr.splice(dragIndex.value, 1)
  arr.splice(index, 0, moved)
  items.value = arr
  dragIndex.value = null
  dragOverIndex.value = null
}

function onDragEnd() {
  dragIndex.value = null
  dragOverIndex.value = null
}

function removeItem(index: number) {
  items.value.splice(index, 1)
}

// ──────────── 上传 ────────────
function openUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  for (const file of files) {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!['pdf', 'ofd', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'zip'].includes(ext)) {
      ElMessage.warning(`${file.name} 格式不支持`)
      continue
    }
    try {
      const b64 = await fileToBase64(file)
      const result = await uploadReimbursementFile(file.name, b64)
      if (result.error) throw new Error(result.error)
      items.value.push({ ...result, included: true, source: 'upload' })
      if (!outputName.value) outputName.value = defaultOutputName()
    } catch (error) {
      ElMessage.error(`${file.name} 上传失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string).split(',')[1] || '')
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// ──────────── 生成 PDF ────────────
async function handleMerge() {
  if (!selectedItems.value.length) { ElMessage.warning('请至少勾选一个附件'); return }
  if (!outputName.value.trim()) { ElMessage.warning('请填写输出文件名'); return }
  merging.value = true
  mergeResult.value = null
  try {
    const result = await mergeReimbursementPdf(
      selectedItems.value.map((i) => ({
        key: i.key,
        invoice_type: i.invoice_type,
        invoice_date: i.invoice_date,
        invoice_amount: i.invoice_amount,
      })),
      outputName.value.trim(),
      mergeTrainTickets.value,
    )
    mergeResult.value = { filename: result.filename, pages: result.pages, train_ticket_groups: (result as any).train_ticket_groups }
    if ((result as any).warning) ElMessage.warning((result as any).warning)
    else ElMessage.success(`PDF 已生成，共 ${result.pages} 页`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成失败')
  } finally {
    merging.value = false
  }
}

async function handleBatchDownload() {
  if (!selectedItems.value.length) { ElMessage.warning('请至少勾选一个附件'); return }
  batchDownloading.value = true
  try {
    const result = await downloadReimbursementInvoicesZip(
      selectedItems.value.map((i) => ({
        key: i.key,
        invoice_type: i.invoice_type,
        invoice_date: i.invoice_date,
        invoice_amount: i.invoice_amount,
        invoice_location: i.invoice_location,
        invoice_from: i.invoice_from,
        invoice_to: i.invoice_to,
      })),
      (outputName.value.trim() || defaultOutputName()) + '_原始发票',
    )
    const link = document.createElement('a')
    link.href = reimbursementOutputUrl(result.filename)
    link.download = result.filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    ElMessage.success('已打包 ' + result.count + ' 张发票')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '批量下载失败')
  } finally {
    batchDownloading.value = false
  }
}

// ──────────── 预览 ────────────
function openPreview(item: ListItem) {
  previewItem.value = item
}

function closePreview() {
  previewItem.value = null
}

function previewUrl(item: ReimbursementItem) {
  return reimbursementAttachmentUrl(item.key)
}

// ──────────── 邮件预览弹框 ────────────
async function openEmailModal(item: ListItem) {
  emailModalItem.value = item
  emailHtml.value = ''
  emailAttachments.value = []
  // 有 email_uid 的（邮件来源）才能回源拉取原始 HTML
  if (!item.email_uid) return
  emailHtmlLoading.value = true
  try {
    const res = await fetchReimbursementEmail(item.email_uid, account.value)
    if (res.ok && res.html) {
      emailHtml.value = res.html
      emailAttachments.value = res.attachments || []
    }
  } catch {
    // 拉取失败时退化为已缓存的纯文本正文
  } finally {
    emailHtmlLoading.value = false
  }
}

function closeEmailModal() {
  emailModalItem.value = null
  emailHtml.value = ''
  emailAttachments.value = []
  emailHtmlLoading.value = false
}

function formatEmailBody(text: string) {
  if (!text) return ''
  const escaped = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  // 把 URL 变成可点击链接
  return escaped.replace(
    /(https?:\/\/[^\s]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer" class="email-link">$1</a>',
  )
}

function _applyStubResult(stub: ListItem, result: Partial<ReimbursementItem>) {
  const newItem: ListItem = {
    ...(result as ReimbursementItem),
    included: true,
    source: 'upload',
    invoice_type:     result.invoice_type     || stub.invoice_type     || '其他',
    invoice_date:     result.invoice_date     || stub.invoice_date     || '',
    invoice_amount:   result.invoice_amount   || stub.invoice_amount   || '',
    invoice_location: result.invoice_location || stub.invoice_location || '',
    invoice_from:     result.invoice_from     || stub.invoice_from     || '',
    invoice_to:       result.invoice_to       || stub.invoice_to       || '',
  }
  const idx = items.value.findIndex((i) => i.key === stub.key)
  if (idx >= 0) items.value.splice(idx, 1, newItem)
  else items.value.push(newItem)
}

// 主按钮：先尝试后端直接下载，SPA 时降级到文件选择器 + 打开下载页
async function handleFetchInvoice() {
  if (!emailModalItem.value) return
  const stub = emailModalItem.value
  if (!stub.source_url) {
    stubFileInput.value?.click()
    return
  }
  stubUploading.value = true
  try {
    const result = await fetchReimbursementUrl(
      stub.source_url,
      stub.email_subject || '',
      stub.email_body || '',
    )
    if (result.ok) {
      _applyStubResult(stub, result)
      ElMessage.success('发票已自动下载并导入')
      closeEmailModal()
      return
    }
    // 后端无法自动下载（SPA 或网络问题）→ 打开下载页 + 弹文件选择器
    if (stub.source_url) window.open(stub.source_url, '_blank', 'noopener,noreferrer')
    stubFileInput.value?.click()
    if (result.spa) {
      ElMessage.info('该发票页面需要浏览器下载，已打开下载页。下载后在弹出的文件选择框中选择文件。')
    }
  } catch {
    if (stub.source_url) window.open(stub.source_url, '_blank', 'noopener,noreferrer')
    stubFileInput.value?.click()
  } finally {
    stubUploading.value = false
  }
}

// 行内上传：直接在占位条目所在行点击"上传PDF"
function openRowUpload(item: ListItem) {
  rowUploadTarget.value = item
  rowFileInput.value?.click()
}

async function handleRowFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || !rowUploadTarget.value) return

  const file = files[0]
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (!['pdf', 'ofd', 'jpg', 'jpeg', 'png', 'zip'].includes(ext)) {
    ElMessage.warning(`${file.name} 格式不支持`)
    rowUploadTarget.value = null
    return
  }
  const stub = rowUploadTarget.value
  try {
    const b64 = await fileToBase64(file)
    const result = await uploadReimbursementFile(file.name, b64)
    if ((result as any).error) throw new Error((result as any).error)
    _applyStubResult(stub, result)
    ElMessage.success('发票已上传，已替换占位条目')
  } catch (error) {
    ElMessage.error(`上传失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    rowUploadTarget.value = null
  }
}

async function handleStubFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || !emailModalItem.value) return

  const file = files[0]
  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  if (!['pdf', 'ofd', 'jpg', 'jpeg', 'png', 'zip'].includes(ext)) {
    ElMessage.warning(`${file.name} 格式不支持`)
    return
  }
  const stub = emailModalItem.value
  stubUploading.value = true
  try {
    const b64 = await fileToBase64(file)
    const result = await uploadReimbursementFile(file.name, b64)
    if ((result as any).error) throw new Error((result as any).error)
    _applyStubResult(stub, result)
    ElMessage.success('发票已上传，已替换占位条目')
    closeEmailModal()
  } catch (error) {
    ElMessage.error(`上传失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    stubUploading.value = false
  }
}
</script>

<template>
  <section class="workspace-main reimbursement-main">
    <div class="reimbursement-body">
      <!-- 扫描控制栏 -->
      <div class="reimbursement-scan-bar">
        <div class="reimbursement-scan-fields">
          <label class="scan-field">
            <span>日期范围</span>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              :clearable="true"
              class="reimbursement-datepicker"
            />
          </label>
          <label class="scan-field">
            <span>扫描账户</span>
            <div class="reimbursement-account-toggle">
              <button :class="{ active: account === 'company' }" type="button" @click="account = 'company'">公司邮箱</button>
              <button :class="{ active: account === 'personal' }" type="button" @click="account = 'personal'">个人邮箱</button>
            </div>
          </label>
        </div>
        <div class="reimbursement-scan-actions">
          <button class="reimb-btn reimb-btn--primary" type="button" :disabled="scanning" @click="handleScan">
            <el-icon><Refresh /></el-icon>
            {{ scanning ? '扫描中...' : '扫描邮件' }}
          </button>
          <button class="reimb-btn reimb-btn--ghost" type="button" @click="openUpload">
            <el-icon><UploadFilled /></el-icon>
            手动上传
          </button>
          <input ref="fileInput" type="file" accept=".pdf,.ofd,.jpg,.jpeg,.png,.gif,.bmp,.tiff,.tif,.zip" multiple style="display:none" @change="handleFileSelect" />
          <input ref="rowFileInput" type="file" accept=".pdf,.ofd,.jpg,.jpeg,.png,.zip" style="display:none" @change="handleRowFileSelect" />
        </div>
      </div>
      <div class="reimbursement-search-records">
        <label class="search-record-field">
          <span>搜索记录</span>
          <select v-model="selectedSearchId" :disabled="searchLoading || scanning">
            <option value="">未选择记录</option>
            <option v-for="record in searchRecords" :key="record.id" :value="record.id">
              {{ searchRecordLabel(record) }}
            </option>
          </select>
        </label>
        <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" :disabled="!selectedSearchId || searchLoading || scanning" @click="handleLoadSearch">
          加载记录
        </button>
        <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" :disabled="searchSaving || !items.length" @click="persistCurrentSearch()">
          {{ searchSaving ? '保存中...' : '保存当前' }}
        </button>
        <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" :disabled="scanning" @click="handleNewSearch">
          新搜索
        </button>
        <span v-if="currentSearchId" class="search-record-current">当前记录将用于补充搜索</span>
      </div>
      <p v-if="scanStatus" class="reimbursement-scan-status">{{ scanStatus }}</p>
      <div v-if="scanChunks.length > 1" class="reimbursement-chunk-list">
        <div
          v-for="chunk in scanChunks"
          :key="chunkKey(chunk)"
          :class="['reimbursement-chunk', `reimbursement-chunk--${chunk.status}`]"
        >
          <span>{{ chunk.start }} 至 {{ chunk.end }}</span>
          <em>{{ chunk.message || '等待扫描' }}</em>
          <button
            v-if="chunk.status === 'failed' || chunk.status === 'scanning'"
            class="reimb-btn reimb-btn--ghost reimb-btn--sm"
            type="button"
            :disabled="scanning || retryingChunkKey === chunkKey(chunk)"
            @click="retryScanChunk(chunk)"
          >
            <el-icon><Refresh /></el-icon>
            重扫
          </button>
        </div>
      </div>

      <!-- 发票列表 -->
      <div v-if="items.length > 0" class="reimbursement-list-section">
        <div class="reimbursement-list-head">
          <span>共 {{ items.length }} 张，当前 {{ filteredItems.length }} 张，已选 {{ selectedItems.length }} 张，拖拽调整顺序</span>
          <div class="reimbursement-list-tools">
            <label class="invoice-type-filter">
              <span>指定类型</span>
              <select v-model="invoiceTypeFilter">
                <option value="">全部类型</option>
                <option v-for="type in INVOICE_TYPES" :key="type" :value="type">{{ type }}</option>
              </select>
            </label>
            <span class="filtered-select-count">当前已选 {{ filteredSelectedCount }} 张</span>
            <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" :disabled="filteredItems.length === 0" @click="toggleFilteredItems">
              {{ filteredItems.every((i) => i.included) ? "取消当前类型" : "全选当前类型" }}
            </button>
          </div>
        </div>

        <div class="reimbursement-table">
          <div class="reimbursement-table__head">
            <span class="col-check"></span>
            <span class="col-drag"></span>
            <span class="col-file">附件</span>
            <span class="col-type">发票类型</span>
            <span class="col-date">票据日期</span>
            <span class="col-amount">金额</span>
            <span class="col-route">地点 / 行程</span>
            <span class="col-source">来源</span>
            <span class="col-mail">邮件</span>
            <span class="col-actions"></span>
          </div>

          <div
            v-for="(item, index) in filteredItems"
            :key="item.key"
            :data-row-index="index"
            :class="[
              'reimbursement-table__row',
              { 'row--excluded': !item.included, 'row--dragging': dragIndex === item.originalIndex, 'row--dragover': dragOverIndex === item.originalIndex },
            ]"
            draggable="true"
            @dragstart="onDragStart(item.originalIndex, $event)"
            @dragover="onDragOver(item.originalIndex, $event)"
            @dragleave="onDragLeave"
            @drop="onDrop(item.originalIndex)"
            @dragend="onDragEnd"
          >
            <div class="col-check">
              <input v-model="item.included" type="checkbox" />
            </div>

            <div class="col-drag" title="拖拽调整顺序">
              <span class="drag-handle">⠿</span>
            </div>

            <!-- 附件名 + 缩略图 -->
            <div class="col-file">
              <div class="file-cell">
                <!-- stub 占位项 -->
                <template v-if="item.is_stub">
                  <div class="file-thumb file-thumb--stub">
                    <span>⚠</span>
                  </div>
                  <div class="file-meta">
                    <strong>{{ item.source_url ? '需手动下载' : '待上传发票' }}</strong>
                    <em :title="item.email_subject">{{ item.email_subject }}</em>
                    <div class="file-meta__tags">
                      <span class="stub-tag">{{ item.source_url ? 'SPA 页面' : '仅邮件信息' }}</span>
                      <a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener" class="stub-link">打开下载页</a>
                    </div>
                  </div>
                </template>
                <!-- 正常文件项 -->
                <template v-else>
                  <div class="file-thumb" @click="openPreview(item)">
                    <img v-if="item.is_image" :src="previewUrl(item)" :alt="item.filename" />
                    <div v-else-if="item.is_ofd" class="pdf-icon ofd-icon">OFD</div>
                    <div v-else class="pdf-icon">PDF</div>
                    <div class="file-thumb__overlay"><el-icon><View /></el-icon></div>
                  </div>
                  <div class="file-meta">
                    <strong :title="item.filename">{{ item.filename }}</strong>
                    <em v-if="item.email_subject" :title="item.email_subject">{{ item.email_subject }}</em>
                    <div class="file-meta__tags">
                      <span class="size-tag">{{ formatSize(item.size) }}</span>
                      <span v-if="item.is_ofd" class="ofd-tag">OFD · 可合并</span>
                    </div>
                  </div>
                </template>
              </div>
            </div>

            <!-- 发票类型 -->
            <div class="col-type">
              <select
                v-model="item.invoice_type"
                :class="['type-select', `type-select--${TYPE_COLORS[item.invoice_type || '其他'] || 'gray'}`]"
              >
                <option v-for="t in INVOICE_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>

            <!-- 票据日期 -->
            <div class="col-date">
              <input v-model="item.invoice_date" type="date" class="date-input" />
              <em v-if="!item.invoice_date && item.email_date" class="fallback-date">{{ item.email_date }}</em>
            </div>

            <!-- 金额 -->
            <div class="col-amount">
              <input v-model="item.invoice_amount" class="amount-input" placeholder="¥0.00" />
            </div>

            <!-- 地点 / 行程 -->
            <div class="col-route">
              <template v-if="item.invoice_type === '火车' || item.invoice_type === '机票'">
                <div class="route-row">
                  <input v-model="item.invoice_from" class="route-input" placeholder="出发地" />
                  <span class="route-arrow">→</span>
                  <input v-model="item.invoice_to" class="route-input" placeholder="目的地" />
                </div>
              </template>
              <template v-else-if="item.invoice_type === '住宿' || item.invoice_type === '餐饮'">
                <input v-model="item.invoice_location" class="location-input" :placeholder="item.invoice_type === '住宿' ? '城市·酒店名' : '餐厅名称'" />
              </template>
              <span v-else class="route-na">—</span>
            </div>

            <!-- 来源 -->
            <div class="col-source">
              <span :class="['source-badge', item.source === 'upload' ? 'source-badge--upload' : 'source-badge--mail']">
                {{ item.source === 'upload' ? '上传' : '邮件' }}
              </span>
            </div>

            <!-- 邮件内容 -->
            <div class="col-mail">
              <button
                v-if="item.email_subject || item.email_body"
                class="reimb-btn reimb-btn--ghost reimb-btn--sm"
                type="button"
                title="查看原始邮件"
                @click="openEmailModal(item)"
              >
                <el-icon><Message /></el-icon>
              </button>
              <span v-else class="route-na">—</span>
            </div>

            <!-- 操作 -->
            <div class="col-actions">
              <template v-if="item.is_stub">
                <button class="reimb-btn reimb-btn--primary reimb-btn--sm" type="button" title="上传PDF" @click="openRowUpload(item)">
                  <el-icon><UploadFilled /></el-icon>
                </button>
                <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" title="查看邮件" @click="openEmailModal(item)">
                  <el-icon><View /></el-icon>
                </button>
              </template>
              <template v-else>
                <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" title="预览" @click="openPreview(item)">
                  <el-icon><View /></el-icon>
                </button>
                <a :href="reimbursementAttachmentUrl(item.key, true)" class="reimb-btn reimb-btn--ghost reimb-btn--sm" title="下载" download>
                  <el-icon><Download /></el-icon>
                </a>
              </template>
              <button class="reimb-btn reimb-btn--danger reimb-btn--sm" type="button" title="移除" @click="removeItem(item.originalIndex)">
                <el-icon><Delete /></el-icon>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!scanning && !scanStatus" class="reimbursement-empty">
        <p>选择日期范围后点击"扫描邮件"，系统将自动识别含发票的附件。</p>
        <p>也可以直接点击"手动上传"添加本地发票文件。</p>
      </div>

      <!-- 生成 PDF -->
      <div v-if="items.length > 0" class="reimbursement-merge-bar">
        <label class="merge-name-field">
          <span>输出文件名</span>
          <input v-model="outputName" placeholder="报销附件" class="merge-name-input" />
        </label>
        <label class="train-merge-toggle">
          <input v-model="mergeTrainTickets" type="checkbox" />
          <span>火车票四张合并</span>
        </label>
        <button class="reimb-btn reimb-btn--primary" type="button" :disabled="merging || selectedItems.length === 0" @click="handleMerge">
          <el-icon><Plus /></el-icon>
          {{ merging ? '生成中...' : `生成报销 PDF（${selectedItems.length} 张）` }}
        </button>
        <button class="reimb-btn reimb-btn--ghost" type="button" :disabled="batchDownloading || selectedItems.length === 0" @click="handleBatchDownload">
          <el-icon><Download /></el-icon>
          {{ batchDownloading ? '打包中...' : '批量下载发票（' + selectedItems.length + ' 张）' }}
        </button>
        <div v-if="mergeResult" class="reimb-result">
          <span>{{ mergeResult.filename }}（{{ mergeResult.pages }} 页<span v-if="mergeResult.train_ticket_groups">，火车票 {{ mergeResult.train_ticket_groups }} 组</span>）</span>
          <a :href="reimbursementOutputUrl(mergeResult.filename)" class="reimb-btn reimb-btn--primary reimb-btn--sm" download>
            <el-icon><Download /></el-icon>
            下载 PDF
          </a>
        </div>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <div v-if="previewItem" class="preview-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <div class="preview-modal__head">
          <strong>{{ previewItem.filename }}</strong>
          <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" @click="closePreview">关闭</button>
        </div>
        <div class="preview-modal__body">
          <img v-if="previewItem.is_image" :src="previewUrl(previewItem)" :alt="previewItem.filename" class="preview-img" />
          <img v-else-if="previewItem.is_ofd" :src="reimbursementOfdPreviewUrl(previewItem.key)" :alt="previewItem.filename" class="preview-img" />
          <iframe v-else :src="previewUrl(previewItem)" class="preview-iframe" />
        </div>
      </div>
    </div>

    <!-- 邮件内容预览弹框（所有邮件来源条目通用；占位条目额外提供"获取发票"） -->
    <div v-if="emailModalItem" class="preview-overlay" @click.self="closeEmailModal">
      <div class="stub-modal">
        <div class="stub-modal__head">
          <div class="stub-modal__title">
            <strong>{{ emailModalItem.email_subject || '发票邮件' }}</strong>
            <span>{{ emailModalItem.email_from }}</span>
            <span>{{ emailModalItem.email_date }}</span>
          </div>
          <button class="reimb-btn reimb-btn--ghost reimb-btn--sm" type="button" @click="closeEmailModal">关闭</button>
        </div>

        <div class="stub-modal__body">
          <!-- 已提取的发票信息 -->
          <div v-if="emailModalItem.invoice_amount || emailModalItem.invoice_date || emailModalItem.invoice_type" class="stub-invoice-meta">
            <span v-if="emailModalItem.invoice_type" :class="['type-badge', `type-badge--${emailModalItem.invoice_type}`]">{{ emailModalItem.invoice_type }}</span>
            <span v-if="emailModalItem.invoice_date">{{ emailModalItem.invoice_date }}</span>
            <strong v-if="emailModalItem.invoice_amount">{{ emailModalItem.invoice_amount }}</strong>
            <span v-if="emailModalItem.invoice_location">{{ emailModalItem.invoice_location }}</span>
            <span v-if="emailModalItem.invoice_from && emailModalItem.invoice_to">{{ emailModalItem.invoice_from }} → {{ emailModalItem.invoice_to }}</span>
          </div>

          <!-- 附件清单 -->
          <div v-if="emailAttachments.length" class="email-attach-bar">
            <span class="email-attach-label">附件（{{ emailAttachments.length }}）：</span>
            <span v-for="(name, i) in emailAttachments" :key="i" class="email-attach-chip">{{ name }}</span>
          </div>

          <!-- 邮件正文 -->
          <div v-if="emailHtmlLoading" class="stub-email-content email-loading">正在加载原始邮件…</div>
          <iframe
            v-else-if="emailHtml"
            class="email-html-frame"
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            referrerpolicy="no-referrer"
            :srcdoc="emailHtml"
          />
          <div
            v-else
            class="stub-email-content"
            v-html="formatEmailBody(emailModalItem.email_body || '')"
          />
        </div>

        <div v-if="emailModalItem.is_stub" class="stub-modal__footer">
          <p class="stub-modal__tip">
            点击"获取发票"——系统先尝试自动下载；若为 SPA 页面则自动打开下载页并弹出文件选择框，下载后直接选择即可。
          </p>
          <div class="stub-modal__actions">
            <button class="reimb-btn reimb-btn--primary stub-fetch-btn" type="button" :disabled="stubUploading" @click="handleFetchInvoice">
              <el-icon><UploadFilled /></el-icon>
              {{ stubUploading ? '获取中...' : '获取发票' }}
            </button>
          </div>
          <input ref="stubFileInput" type="file" accept=".pdf,.ofd,.jpg,.jpeg,.png,.zip" style="display:none" @change="handleStubFileSelect" />
        </div>
      </div>
    </div>
  </section>
</template>
