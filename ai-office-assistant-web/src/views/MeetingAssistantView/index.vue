<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, MagicStick, Microphone, Plus, VideoPause } from '@element-plus/icons-vue'
import {
  deleteMeeting,
  getMeeting,
  listMeetings,
  saveMeeting,
  summarizeMeeting,
  transcribeMeetingAudio,
  translateMeetingText,
  type MeetingListItem,
  type MeetingSegment,
} from '../../services/personalWorkApi'
import './index.scss'

type Engine = 'browser' | 'api'

const engine = ref<Engine>('browser')
const language = ref<'zh-CN' | 'en-US'>('zh-CN')
const translateEnabled = ref(true)
const translateTarget = ref('en')
const translateTargets = [
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'ru', label: '俄语' },
]

const recording = ref(false)
const elapsed = ref(0)
const title = ref('')
const meetingId = ref('')
const segments = ref<MeetingSegment[]>([])
const interimText = ref('')
const summary = ref('')
const summarizing = ref(false)
const savingMeeting = ref(false)
const viewingHistory = ref(false)
const history = ref<MeetingListItem[]>([])
const historyLoading = ref(false)
const transcriptRef = ref<HTMLElement | null>(null)

let timer: number | undefined
let recognizer: any = null
let mediaStream: MediaStream | null = null
let mediaRecorder: MediaRecorder | null = null
let segmentTimer: number | undefined
let stopRequested = false

const hasBrowserAsr = typeof window !== 'undefined' && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
const canRecord = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia

const transcriptText = computed(() => segments.value.map((s) => `[${s.time}] ${s.text}`).join('\n'))
const elapsedLabel = computed(() => formatClock(elapsed.value))

function formatClock(totalSeconds: number) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

function scrollTranscript() {
  requestAnimationFrame(() => {
    if (transcriptRef.value) transcriptRef.value.scrollTop = transcriptRef.value.scrollHeight
  })
}

function pushSegment(text: string) {
  const content = text.trim()
  if (!content) return
  const segment: MeetingSegment = { time: formatClock(elapsed.value), text: content, translation: '' }
  segments.value.push(segment)
  scrollTranscript()
  if (translateEnabled.value) {
    translateMeetingText(content, translateTarget.value)
      .then((result) => {
        segment.translation = result.text || ''
        scrollTranscript()
      })
      .catch(() => {
        segment.translation = '（翻译失败）'
      })
  }
}

// ---------------------------------------------------------------------------
// 浏览器实时识别引擎（Web Speech API）
// ---------------------------------------------------------------------------
function startBrowserEngine() {
  const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  recognizer = new Recognition()
  recognizer.lang = language.value
  recognizer.continuous = true
  recognizer.interimResults = true
  recognizer.onresult = (event: any) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i]
      if (result.isFinal) pushSegment(result[0].transcript)
      else interim += result[0].transcript
    }
    interimText.value = interim
  }
  recognizer.onend = () => {
    // 浏览器识别会因静音自动结束，会议未结束就立即重启。
    if (recording.value && !stopRequested) {
      try {
        recognizer.start()
      } catch {
        /* 忽略重复 start */
      }
    }
  }
  recognizer.onerror = (event: any) => {
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      ElMessage.error('麦克风或识别服务不可用，请检查浏览器权限（需要 HTTPS 访问）')
      stopRecording()
    }
  }
  recognizer.start()
}

// ---------------------------------------------------------------------------
// API 分段转写引擎（MediaRecorder + whisper 接口）
// ---------------------------------------------------------------------------
function pickMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return candidates.find((t) => (window as any).MediaRecorder?.isTypeSupported?.(t)) || ''
}

async function startApiEngine() {
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  recordNextSegment()
}

function recordNextSegment() {
  if (!mediaStream || !recording.value || stopRequested) return
  const mimeType = pickMimeType()
  const chunks: Blob[] = []
  mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined)
  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  }
  mediaRecorder.onstop = () => {
    const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || mimeType || 'audio/webm' })
    // 静音段通常很小，跳过避免空请求。
    if (blob.size > 3000) void transcribeSegment(blob)
    recordNextSegment()
  }
  mediaRecorder.start()
  // 每 15 秒切一段独立音频送转写，接近实时。
  segmentTimer = window.setTimeout(() => {
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
  }, 15000)
}

async function transcribeSegment(blob: Blob) {
  try {
    const dataUri = await blobToDataUri(blob)
    const result = await transcribeMeetingAudio(dataUri, language.value.split('-')[0])
    pushSegment(result.text)
  } catch (error) {
    ElMessage.error('转写失败：' + errorMessage(error))
  }
}

function blobToDataUri(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('音频读取失败'))
    reader.readAsDataURL(blob)
  })
}

// ---------------------------------------------------------------------------
// 录音控制
// ---------------------------------------------------------------------------
async function startRecording() {
  if (recording.value) return
  if (viewingHistory.value) resetMeeting()
  if (engine.value === 'browser' && !hasBrowserAsr) {
    ElMessage.error('当前浏览器不支持实时识别，请切换到 API 识别引擎')
    return
  }
  if (engine.value === 'api' && !canRecord) {
    ElMessage.error('当前环境不支持录音（需要 HTTPS 访问）')
    return
  }
  stopRequested = false
  recording.value = true
  if (!title.value) title.value = `会议 ${new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
  timer = window.setInterval(() => {
    elapsed.value += 1
  }, 1000)
  try {
    if (engine.value === 'browser') startBrowserEngine()
    else await startApiEngine()
  } catch (error) {
    ElMessage.error('启动录音失败：' + errorMessage(error))
    stopRecording()
  }
}

function stopRecording() {
  stopRequested = true
  recording.value = false
  interimText.value = ''
  if (timer) {
    window.clearInterval(timer)
    timer = undefined
  }
  if (segmentTimer) {
    window.clearTimeout(segmentTimer)
    segmentTimer = undefined
  }
  if (recognizer) {
    try {
      recognizer.stop()
    } catch {
      /* ignore */
    }
    recognizer = null
  }
  if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop()
  mediaRecorder = null
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop())
    mediaStream = null
  }
}

function resetMeeting() {
  stopRecording()
  meetingId.value = ''
  title.value = ''
  segments.value = []
  summary.value = ''
  elapsed.value = 0
  viewingHistory.value = false
}

// ---------------------------------------------------------------------------
// 总结与存档
// ---------------------------------------------------------------------------
async function persistMeeting() {
  const result = await saveMeeting({
    id: meetingId.value || undefined,
    title: title.value,
    duration: elapsed.value,
    language: language.value,
    translate_target: translateEnabled.value ? translateTarget.value : '',
    segments: segments.value,
    summary: summary.value,
  })
  meetingId.value = result.id
  void loadHistory()
}

async function handleSummarize() {
  if (!segments.value.length) {
    ElMessage.warning('还没有转写内容')
    return
  }
  if (recording.value) stopRecording()
  summarizing.value = true
  try {
    const result = await summarizeMeeting(transcriptText.value, title.value)
    summary.value = result.summary
    await persistMeeting()
    ElMessage.success('会议总结已生成并保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    summarizing.value = false
  }
}

async function handleSave() {
  if (!segments.value.length) {
    ElMessage.warning('还没有转写内容')
    return
  }
  savingMeeting.value = true
  try {
    await persistMeeting()
    ElMessage.success('会议记录已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingMeeting.value = false
  }
}

// ---------------------------------------------------------------------------
// 历史记录
// ---------------------------------------------------------------------------
async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = (await listMeetings()).meetings
  } catch {
    /* 列表加载失败不打断主流程 */
  } finally {
    historyLoading.value = false
  }
}

async function openHistory(item: MeetingListItem) {
  if (recording.value) {
    ElMessage.warning('请先结束当前录音')
    return
  }
  try {
    const record = (await getMeeting(item.id)).meeting
    meetingId.value = record.id
    title.value = record.title
    segments.value = record.segments || []
    summary.value = record.summary || ''
    elapsed.value = record.duration || 0
    viewingHistory.value = true
    scrollTranscript()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleDelete(item: MeetingListItem) {
  try {
    await ElMessageBox.confirm(`确认删除「${item.title}」？`, '删除会议记录', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteMeeting(item.id)
    if (meetingId.value === item.id) resetMeeting()
    void loadHistory()
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

onMounted(() => {
  void loadHistory()
})

onBeforeUnmount(() => {
  stopRecording()
})
</script>

<template>
  <section class="meeting-main">
    <header class="meeting-head">
      <div>
        <h1>会议助手</h1>
        <p>实时录音识别、同步翻译，会后一键生成 AI 纪要。</p>
      </div>
      <button class="meeting-btn meeting-btn--ghost" type="button" @click="resetMeeting">
        <el-icon><Plus /></el-icon> 新会议
      </button>
    </header>

    <div class="meeting-body">
      <section class="meeting-stage">
        <div class="meeting-toolbar">
          <input v-model="title" class="meeting-title" placeholder="会议标题" :disabled="recording" />
          <div class="meeting-options">
            <el-select v-model="engine" class="meeting-select" :disabled="recording">
              <el-option label="浏览器实时识别（零配置）" value="browser" />
              <el-option label="API 识别（Whisper）" value="api" />
            </el-select>
            <el-select v-model="language" class="meeting-select meeting-select--narrow" :disabled="recording">
              <el-option label="中文" value="zh-CN" />
              <el-option label="英语" value="en-US" />
            </el-select>
            <label class="meeting-check">
              <input v-model="translateEnabled" type="checkbox" :disabled="recording" />
              <span>实时翻译为</span>
            </label>
            <el-select v-model="translateTarget" class="meeting-select meeting-select--narrow" :disabled="recording || !translateEnabled">
              <el-option v-for="item in translateTargets" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>
        </div>

        <div class="meeting-control">
          <button v-if="!recording" class="meeting-record" type="button" @click="startRecording">
            <el-icon><Microphone /></el-icon> 开始录音
          </button>
          <button v-else class="meeting-record meeting-record--stop" type="button" @click="stopRecording">
            <el-icon><VideoPause /></el-icon> 结束录音
          </button>
          <span :class="['meeting-timer', { live: recording }]">{{ elapsedLabel }}</span>
          <span v-if="recording" class="meeting-live-dot"></span>
          <span v-if="viewingHistory" class="meeting-tag">查看历史记录</span>
        </div>

        <div ref="transcriptRef" class="meeting-transcript">
          <p v-if="!segments.length && !interimText" class="meeting-empty">
            点击"开始录音"，发言会实时转成文字显示在这里{{ translateEnabled ? '，并同步翻译' : '' }}。
          </p>
          <article v-for="(segment, index) in segments" :key="index" class="meeting-segment">
            <span class="meeting-segment-time">{{ segment.time }}</span>
            <div>
              <p>{{ segment.text }}</p>
              <p v-if="segment.translation" class="meeting-segment-translation">{{ segment.translation }}</p>
            </div>
          </article>
          <article v-if="interimText" class="meeting-segment meeting-segment--interim">
            <span class="meeting-segment-time">…</span>
            <div><p>{{ interimText }}</p></div>
          </article>
        </div>

        <div class="meeting-actions">
          <button class="meeting-btn meeting-btn--ghost" type="button" :disabled="savingMeeting || !segments.length" @click="handleSave">
            {{ savingMeeting ? '保存中…' : '保存记录' }}
          </button>
          <button class="meeting-btn meeting-btn--primary" type="button" :disabled="summarizing || !segments.length" @click="handleSummarize">
            <el-icon><MagicStick /></el-icon> {{ summarizing ? '总结生成中…' : '生成会议总结' }}
          </button>
        </div>

        <section v-if="summary" class="meeting-summary">
          <h3>AI 会议纪要</h3>
          <div class="meeting-summary-body">{{ summary }}</div>
        </section>
      </section>

      <aside class="meeting-history">
        <h3>历史会议</h3>
        <p v-if="historyLoading" class="meeting-empty">加载中…</p>
        <p v-else-if="!history.length" class="meeting-empty">还没有会议记录</p>
        <article v-for="item in history" :key="item.id" :class="['meeting-history-item', { active: item.id === meetingId }]" @click="openHistory(item)">
          <strong>{{ item.title }}</strong>
          <span>{{ item.created_at }} · {{ formatClock(item.duration) }} · {{ item.segment_count }} 段{{ item.has_summary ? ' · 已总结' : '' }}</span>
          <button type="button" aria-label="删除" @click.stop="handleDelete(item)">
            <el-icon><Delete /></el-icon>
          </button>
        </article>
      </aside>
    </div>
  </section>
</template>
