<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { generateWritingDraft, optimizeText, rewriteWritingDraft, uploadWritingFile, type WritingMaterial } from '../../services/personalWorkApi'
import './index.scss'

interface ChatMessage {
  role: 'assistant' | 'user'
  content: string
}

const props = defineProps<{
  modelValue: boolean
  fieldLabel: string
  taskTitle?: string
  initialContent: string
}>()

const emit = defineEmits<{
  'update:modelValue': [visible: boolean]
  apply: [content: string]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const messages = ref<ChatMessage[]>([])
const messagesRef = ref<HTMLElement | null>(null)
const candidate = ref('')
const instruction = ref('')
const materials = ref<WritingMaterial[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const hasGeneratedContent = ref(false)
const processingSteps = ref<string[]>([])
const summaryMode = ref<'weekly' | null>(null)
const conversationTurns = computed(() => messages.value.filter((message) => message.role === 'user').length)

function normalizeWeeklySummary(source: string) {
  const sectionOnly = /^(本周工作总结|[一二三四五六七八九十]+、[^。；，,]{0,24})[。:：]?$/
  const entries = source.replace(/\r\n/g, '\n').split('\n')
    .filter((raw) => !/^\s*(#{1,6}\s|>|---)/.test(raw))
    .map((raw) => raw.trim()
      .replace(/^#{1,6}\s*/, '')
      .replace(/^[-*•]\s+/, '')
      .replace(/^\d+[、.．]\s*/, ''))
    .filter((line) => line && !sectionOnly.test(line))
  return entries.slice(0, 8).map((line, index) => `${index + 1}. ${line}`).join('\n')
}

const weeklySummaryRequirement = '只保留本周已经完成或正在完成的实际工作，输出 3-8 条一级编号：每行以“1.、2.、3.”依次编号；不要输出“本周工作总结”总标题，不要“一、数据实施工作”这类分组标题，不要二级编号、嵌套列表、Markdown 表格、责任人和完成时间明细；不要生成重点工作跟进、困难与求助或下周计划；只依据材料，不编造内容。'

function resetConversation() {
  candidate.value = props.initialContent.trim()
  instruction.value = ''
  materials.value = []
  hasGeneratedContent.value = false
  processingSteps.value = []
  summaryMode.value = null
  messages.value = [{
    role: 'assistant',
    content: props.initialContent.trim()
      ? `已带入当前「${props.fieldLabel}」内容。你可以补充要求、上传材料，或让我直接总结并整理成可写入的内容。`
      : `请告诉我需要如何撰写「${props.fieldLabel}」，也可以上传材料让我总结。`,
  }]
}

function scrollToLatest() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(() => props.modelValue, (opened) => {
  if (opened) resetConversation()
})

watch(() => [messages.value.length, processingSteps.value.length], scrollToLatest)

function fileAsData(file: File) {
  return new Promise<{ name: string; data: string }>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({ name: file.name, data: String(reader.result || '') })
    reader.onerror = () => reject(new Error(`无法读取文件：${file.name}`))
    reader.readAsDataURL(file)
  })
}

async function uploadMaterials(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || [])
  if (!files.length) return
  try {
    const payload = await Promise.all(files.map(fileAsData))
    const result = await uploadWritingFile(payload)
    const parsedFiles = result.files || []
    materials.value = [...materials.value, ...parsedFiles]
    processingSteps.value = [`已解析 ${parsedFiles.length || files.length} 个文件`, '材料已就绪，可选择总结方式']
    ElMessage.success(`已解析 ${parsedFiles.length || files.length} 个文件，可直接用于总结`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文件上传失败')
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}

function removeMaterial(id: string) {
  materials.value = materials.value.filter((file) => file.id !== id)
}

async function summarizeUploadedMaterials() {
  if (!materials.value.length || busy.value) {
    ElMessage.warning('请先上传需要读取的文件')
    return
  }
  busy.value = true
  processingSteps.value = [
    `正在读取 ${materials.value.length} 个已解析文件`,
    '正在筛选本周已完成与进行中的工作',
    '正在组织候选内容',
  ]
  const request = `请读取全部上传材料，${weeklySummaryRequirement}`
  messages.value.push({ role: 'user', content: '请根据上传文件，仅总结本周工作。' })
  try {
    const result = await generateWritingDraft({
      title: `${props.taskTitle || props.fieldLabel || '当前任务'}本周工作总结`,
      writing_type: '工作总结',
      content: candidate.value || props.initialContent,
      requirements: request,
      file_ids: materials.value.map((file) => file.id),
    })
    const rawContent = result.item?.content?.trim() || candidate.value || props.initialContent
    const content = normalizeWeeklySummary(rawContent)
    summaryMode.value = 'weekly'
    candidate.value = content
    hasGeneratedContent.value = true
    processingSteps.value = [...processingSteps.value, '已生成候选内容，可继续对话调整或确认写入']
    messages.value.push({ role: 'assistant', content })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文件总结失败')
  } finally {
    busy.value = false
  }
}

async function sendMessage() {
  const request = instruction.value.trim()
  if (!request || busy.value) return
  messages.value.push({ role: 'user', content: request })
  instruction.value = ''
  busy.value = true
  processingSteps.value = [
    `正在结合第 ${conversationTurns.value} 轮要求调整内容`,
    materials.value.length ? `正在参考 ${materials.value.length} 个已解析文件` : '正在参考当前字段内容',
    '正在生成新的候选内容',
  ]
  try {
    const history = messages.value
      .filter((message) => message.role === 'user')
      .slice(-3)
      .map((message) => `用户：${message.content}`)
      .join('\n')
    const result = await rewriteWritingDraft({
      title: `${props.fieldLabel} AI 总结`,
      writing_type: '工作报告字段总结',
      content: candidate.value || props.initialContent,
      requirements: summaryMode.value === 'weekly' ? weeklySummaryRequirement : undefined,
      rewrite_instruction: `请根据当前字段内容、已上传材料和以下用户要求生成新版本。${summaryMode.value === 'weekly' ? ` ${weeklySummaryRequirement}` : ' 保留事实，不编造信息；只输出正文，不要解释。'}\n${history}`,
      file_ids: materials.value.map((file) => file.id),
    })
    const rawContent = result.item?.content?.trim() || candidate.value || props.initialContent
    const content = summaryMode.value === 'weekly' ? normalizeWeeklySummary(rawContent) : rawContent
    candidate.value = content
    hasGeneratedContent.value = true
    processingSteps.value = [...processingSteps.value, '已更新候选内容，可继续对话或确认写入']
    messages.value.push({ role: 'assistant', content })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'AI 总结失败')
  } finally {
    busy.value = false
  }
}

async function formatCandidate() {
  const content = candidate.value.trim()
  if (!content || busy.value) return
  busy.value = true
  processingSteps.value = ['正在保留原始事实', '正在整理表达与格式']
  try {
    const result = await optimizeText(content, '请在不遗漏事实、不添加新内容的前提下，整理以下文字格式。按清晰条目和规范中文输出，只返回整理后的正文。')
    const formatted = result.text?.trim() || content
    candidate.value = summaryMode.value === 'weekly' ? normalizeWeeklySummary(formatted) : formatted
    hasGeneratedContent.value = true
    processingSteps.value = [...processingSteps.value, '格式已整理，可继续对话或确认写入']
    messages.value.push({ role: 'assistant', content: candidate.value })
    ElMessage.success('已整理格式，可继续修改或写入字段')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '格式整理失败')
  } finally {
    busy.value = false
  }
}

function writeBack() {
  const content = candidate.value.trim()
  if (!content || !hasGeneratedContent.value) {
    ElMessage.warning('请先通过多轮对话确定内容，再确认写入')
    return
  }
  emit('apply', content)
  visible.value = false
  ElMessage.success('已写入当前字段')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="content-assist-dialog"
    :title="`AI 总结 · ${taskTitle || fieldLabel || '当前字段'}`"
    width="min(1320px, 96vw)"
    top="4vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="content-assist-dialog__intro">支持读取 Word、Excel、PDF 等材料。上传后可直接总结本周工作，并可多轮对话调整；内容确定后再确认写入当前字段。</div>
    <div ref="messagesRef" :class="['content-assist-dialog__messages', { 'is-initial': messages.length === 1 }]">
      <article v-for="(message, index) in messages" :key="`${message.role}-${index}`" :class="['content-assist-dialog__message', `is-${message.role}`]">
        <strong>{{ message.role === 'user' ? '你' : 'AI 助手' }}</strong>
        <p>{{ message.content }}</p>
      </article>
    </div>
    <div v-if="hasGeneratedContent" class="content-assist-dialog__confirm-state">
      已完成 {{ conversationTurns }} 轮对话，可继续修改；确认满意后写入当前字段。
    </div>
    <div v-if="materials.length" class="content-assist-dialog__files">
      <span v-for="file in materials" :key="file.id" class="content-assist-dialog__file">
        {{ file.name }}
        <em>已解析</em>
        <button type="button" :aria-label="`移除 ${file.name}`" @click="removeMaterial(file.id)">×</button>
      </span>
    </div>
    <section v-if="processingSteps.length" class="content-assist-dialog__thinking" :class="{ 'is-busy': busy }">
      <strong>AI 处理进度</strong>
      <ol>
        <li v-for="(step, index) in processingSteps" :key="`${step}-${index}`">{{ step }}</li>
      </ol>
    </section>
    <div class="content-assist-dialog__composer">
      <textarea v-model="instruction" rows="3" placeholder="例如：请从附件中提炼本周完成事项，按条目输出" @keydown.ctrl.enter.prevent="sendMessage" />
      <div class="content-assist-dialog__actions">
        <input ref="fileInput" type="file" multiple accept=".txt,.md,.csv,.log,.json,.html,.htm,.docx,.pdf,.xlsx,.pptx" class="content-assist-dialog__input" @change="uploadMaterials" />
        <button type="button" class="content-assist-dialog__upload" @click="fileInput?.click()">上传文件</button>
        <button type="button" class="content-assist-dialog__summarize" :disabled="busy || !materials.length" @click="summarizeUploadedMaterials">总结</button>
        <button type="button" class="content-assist-dialog__format" :disabled="busy || !candidate.trim()" @click="formatCandidate">整理格式</button>
        <button type="button" class="content-assist-dialog__send" :disabled="!instruction.trim() || busy" @click="sendMessage">{{ busy ? '总结中…' : '发送' }}</button>
      </div>
    </div>
    <template #footer>
      <div class="content-assist-dialog__footer">
        <button type="button" @click="visible = false">取消</button>
        <button type="button" class="is-primary" :disabled="busy || !hasGeneratedContent" @click="writeBack">确认内容并写入当前字段</button>
      </div>
    </template>
  </el-dialog>
</template>
