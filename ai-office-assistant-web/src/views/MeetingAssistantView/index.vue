<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, MagicStick, Microphone, Plus, VideoPause } from '@element-plus/icons-vue'
import { MicVAD } from '@ricky0123/vad-web'
import { env as ortEnv } from 'onnxruntime-web/wasm'
import { loadRnnoise, RnnoiseWorkletNode } from '@sapphi-red/web-noise-suppressor'
import rnnoiseWorkletUrl from '@sapphi-red/web-noise-suppressor/rnnoiseWorklet.js?url'
import rnnoiseWasmUrl from '@sapphi-red/web-noise-suppressor/rnnoise.wasm?url'
import rnnoiseSimdUrl from '@sapphi-red/web-noise-suppressor/rnnoise_simd.wasm?url'
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
const micMode = ref<'standard' | 'farfield'>('standard')
const micGain = ref(1.2)
const denoiseEnabled = ref(true)
const previewing = ref(false)
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
const recordedUrl = ref('')
const downloadName = computed(() => `${(title.value || '会议录音').replace(/[\\/:*?"<>|]/g, '_')}.webm`)
const savingMeeting = ref(false)
const viewingHistory = ref(false)
const history = ref<MeetingListItem[]>([])
const historyLoading = ref(false)
const transcriptRef = ref<HTMLElement | null>(null)

let timer: number | undefined
let recognizer: any = null
let mediaStream: MediaStream | null = null
let downloadRecorder: MediaRecorder | null = null
let downloadChunks: Blob[] = []
let rawStream: MediaStream | null = null
let audioContext: AudioContext | null = null
let recordGainNode: GainNode | null = null
let recordRnnoise: RnnoiseWorkletNode | null = null
let previewContext: AudioContext | null = null
let previewStream: MediaStream | null = null
let previewAudio: HTMLAudioElement | null = null
let vad: MicVAD | null = null
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

// 关闭浏览器自动增益（AGC 会让音量忽大忽小），改用 Web Audio 固定增益放大，音量更稳更清楚。
// 远场模式额外关降噪（降噪会把远处低音量人声当噪声滤掉）。
function audioConstraints(): MediaTrackConstraints {
  return {
    echoCancellation: true,
    noiseSuppression: micMode.value !== 'farfield',
    autoGainControl: false,
  }
}

// 限幅器：增益放大后用它压住峰值，避免大声时削波产生“突突”爆音。
function createLimiter(ctx: AudioContext) {
  const limiter = ctx.createDynamicsCompressor()
  limiter.threshold.value = -6
  limiter.knee.value = 6
  limiter.ratio.value = 12
  limiter.attack.value = 0.003
  limiter.release.value = 0.25
  return limiter
}

let rnnoiseWasm: ArrayBuffer | null = null
async function getRnnoiseWasm() {
  if (!rnnoiseWasm) rnnoiseWasm = await loadRnnoise({ url: rnnoiseWasmUrl, simdUrl: rnnoiseSimdUrl })
  return rnnoiseWasm
}

// 组建音频处理链：原始流 →（可选 RNNoise AI 降噪）→ 固定增益 → 限幅 → 输出流。RNNoise 要求 48kHz。
async function connectAudioGraph(ctx: AudioContext, input: MediaStream) {
  const source = ctx.createMediaStreamSource(input)
  const gain = ctx.createGain()
  gain.gain.value = micGain.value
  const limiter = createLimiter(ctx)
  const destination = ctx.createMediaStreamDestination()
  let rnnoise: RnnoiseWorkletNode | null = null
  if (denoiseEnabled.value) {
    await ctx.audioWorklet.addModule(rnnoiseWorkletUrl)
    rnnoise = new RnnoiseWorkletNode(ctx, { maxChannels: 1, wasmBinary: await getRnnoiseWasm() })
    source.connect(rnnoise)
    rnnoise.connect(gain)
  } else {
    source.connect(gain)
  }
  gain.connect(limiter)
  limiter.connect(destination)
  return { stream: destination.stream, gain, rnnoise }
}

// 取麦克风原始流，经处理链（降噪/增益/限幅）后交给录音器；固定增益不会像 AGC 那样忽大忽小。
async function ensureMediaStream() {
  if (mediaStream) return mediaStream
  rawStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints() })
  try {
    audioContext = new AudioContext({ sampleRate: 48000 })
    if (audioContext.state === 'suspended') await audioContext.resume()
    const graph = await connectAudioGraph(audioContext, rawStream)
    recordGainNode = graph.gain
    recordRnnoise = graph.rnnoise
    mediaStream = graph.stream
  } catch {
    // Web Audio 不可用时回退到原始流。
    mediaStream = rawStream
  }
  return mediaStream
}

// 整场持续录制一份完整音频，供会后保存/下载（与分段转写并行，互不影响）。
function startDownloadRecorder() {
  if (!mediaStream) return
  downloadChunks = []
  const mimeType = pickMimeType()
  // 显式提高音频码率，默认值偏低会让录音听起来沉闷模糊。
  const options: MediaRecorderOptions = { audioBitsPerSecond: 128000 }
  if (mimeType) options.mimeType = mimeType
  downloadRecorder = new MediaRecorder(mediaStream, options)
  downloadRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) downloadChunks.push(event.data)
  }
  downloadRecorder.onstop = () => {
    if (!downloadChunks.length) return
    const blob = new Blob(downloadChunks, { type: downloadRecorder?.mimeType || mimeType || 'audio/webm' })
    if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = URL.createObjectURL(blob)
  }
  downloadRecorder.start(1000)
}

// 试听：录 4 秒（经当前增益处理）后立刻回放。录时不外放，避免扬声器→麦克风的声学反馈（回音/卡顿）。
async function togglePreview() {
  if (previewing.value) {
    stopPreview()
    return
  }
  previewing.value = true
  try {
    previewStream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints() })
    previewContext = new AudioContext({ sampleRate: 48000 })
    if (previewContext.state === 'suspended') await previewContext.resume()
    const graph = await connectAudioGraph(previewContext, previewStream)
    const mimeType = pickMimeType()
    const options: MediaRecorderOptions = { audioBitsPerSecond: 128000 }
    if (mimeType) options.mimeType = mimeType
    const recorder = new MediaRecorder(graph.stream, options)
    const chunks: Blob[] = []
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onstop = () => {
      // 先彻底释放麦克风，确保回放时不会再被录进去。
      if (previewStream) {
        previewStream.getTracks().forEach((track) => track.stop())
        previewStream = null
      }
      if (previewContext) {
        void previewContext.close()
        previewContext = null
      }
      if (!chunks.length) {
        previewing.value = false
        return
      }
      previewAudio = new Audio(URL.createObjectURL(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })))
      previewAudio.onended = () => stopPreview()
      ElMessage.info('回放试听片段…')
      void previewAudio.play()
    }
    recorder.start()
    ElMessage.info('正在录制 4 秒试听片段，请正常说话…')
    window.setTimeout(() => {
      if (recorder.state === 'recording') recorder.stop()
    }, 4000)
  } catch (error) {
    ElMessage.error('试听失败：' + errorMessage(error))
    stopPreview()
  }
}

function stopPreview() {
  previewing.value = false
  if (previewAudio) {
    try {
      previewAudio.pause()
    } catch {
      /* ignore */
    }
    if (previewAudio.src) URL.revokeObjectURL(previewAudio.src)
    previewAudio = null
  }
  if (previewStream) {
    previewStream.getTracks().forEach((track) => track.stop())
    previewStream = null
  }
  if (previewContext) {
    void previewContext.close()
    previewContext = null
  }
}

// 录音中调整增益时实时跟随，无需重启。
watch(micGain, (value) => {
  if (recordGainNode) recordGainNode.gain.value = value
})

async function startApiEngine() {
  await ensureMediaStream()
  startDownloadRecorder()
  // 用 Silero VAD 按“说话片段”切分：跳过静音、不腰斩句子，远场低音量也能检出，比固定 15 秒切片更准。
  const assetPath = `${import.meta.env.BASE_URL}vad/`
  ortEnv.wasm.numThreads = 1 // 单线程，免去对 COOP/COEP 跨源隔离的依赖
  vad = await MicVAD.new({
    model: 'v5',
    baseAssetPath: assetPath,
    onnxWASMBasePath: assetPath,
    onSpeechEnd: (audio) => {
      void transcribeSpeech(float32ToWavDataUri(audio, 16000, micGain.value))
    },
  })
  await vad.start()
}

async function transcribeSpeech(dataUri: string) {
  try {
    const result = await transcribeMeetingAudio(dataUri, language.value.split('-')[0])
    pushSegment(result.text)
  } catch (error) {
    ElMessage.error('转写失败：' + errorMessage(error))
  }
}

// 把 VAD 输出的 16kHz 单声道 Float32 PCM（带数字增益）编码成 16-bit WAV data URI，送后端转写。
function float32ToWavDataUri(samples: Float32Array, sampleRate: number, gain: number): string {
  const n = samples.length
  const buffer = new ArrayBuffer(44 + n * 2)
  const view = new DataView(buffer)
  const writeStr = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + n * 2, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, n * 2, true)
  let offset = 44
  for (let i = 0; i < n; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i] * gain))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
    offset += 2
  }
  let binary = ''
  const bytes = new Uint8Array(buffer)
  const block = 0x8000
  for (let i = 0; i < bytes.length; i += block) {
    binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + block)))
  }
  return `data:audio/wav;base64,${btoa(binary)}`
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
  if (micMode.value === 'farfield' && engine.value === 'browser') {
    ElMessage.info('远场模式仅对 API 识别引擎生效，浏览器实时识别无法调整麦克风降噪')
  }
  stopRequested = false
  recording.value = true
  if (previewing.value) stopPreview()
  if (recordedUrl.value) {
    URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = ''
  }
  if (!title.value) title.value = `会议 ${new Date().toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
  timer = window.setInterval(() => {
    elapsed.value += 1
  }, 1000)
  try {
    if (engine.value === 'browser') {
      startBrowserEngine()
      // 浏览器实时识别自带麦克风采集，这里再单独录一份完整音频供下载（失败不影响识别）。
      if (canRecord) {
        try {
          await ensureMediaStream()
          startDownloadRecorder()
        } catch {
          /* 录音存档可选，失败忽略 */
        }
      }
    } else {
      await startApiEngine()
    }
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
  if (recognizer) {
    try {
      recognizer.stop()
    } catch {
      /* ignore */
    }
    recognizer = null
  }
  if (vad) {
    void vad.destroy()
    vad = null
  }
  // 先停整场录制，让 onstop 生成可下载音频，再停轨道。
  if (downloadRecorder && downloadRecorder.state === 'recording') downloadRecorder.stop()
  downloadRecorder = null
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop())
    mediaStream = null
  }
  if (rawStream) {
    rawStream.getTracks().forEach((track) => track.stop())
    rawStream = null
  }
  recordGainNode = null
  if (recordRnnoise) {
    recordRnnoise.destroy()
    recordRnnoise = null
  }
  if (audioContext) {
    void audioContext.close()
    audioContext = null
  }
}

function resetMeeting() {
  stopRecording()
  if (recordedUrl.value) {
    URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = ''
  }
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
  stopPreview()
})
</script>

<template>
  <section class="meeting-main">
    <header class="meeting-head">
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
            <el-select v-model="micMode" class="meeting-select meeting-select--narrow" :disabled="recording">
              <el-option label="标准（近讲）" value="standard" />
              <el-option label="远场（会议室）" value="farfield" />
            </el-select>
            <label class="meeting-check">
              <input v-model="denoiseEnabled" type="checkbox" :disabled="recording" />
              <span>AI 降噪</span>
            </label>
            <label class="meeting-check">
              <input v-model="translateEnabled" type="checkbox" :disabled="recording" />
              <span>实时翻译为</span>
            </label>
            <el-select v-model="translateTarget" class="meeting-select meeting-select--narrow" :disabled="recording || !translateEnabled">
              <el-option v-for="item in translateTargets" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>
          <div class="meeting-tuning">
            <span class="meeting-tuning-label">麦克风增益 ×{{ micGain.toFixed(1) }}</span>
            <el-slider v-model="micGain" :min="0.5" :max="3" :step="0.1" class="meeting-gain-slider" />
            <button type="button" class="meeting-btn meeting-btn--ghost" :disabled="recording || previewing" @click="togglePreview">
              <el-icon><Microphone /></el-icon> {{ previewing ? '录制/回放中…' : '录段试听' }}
            </button>
            <span class="meeting-tuning-hint">点击录 4 秒并回放，听增益后的实际效果</span>
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
          <a
            v-if="recordedUrl && !recording"
            class="meeting-btn meeting-btn--ghost meeting-download"
            :href="recordedUrl"
            :download="downloadName"
          >
            <el-icon><Download /></el-icon> 下载录音
          </a>
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
