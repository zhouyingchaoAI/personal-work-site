<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Delete, EditPen, Search } from '@element-plus/icons-vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import { defaultOptimizePrompt } from '../../services/authSession'
import {
  deleteDiary,
  getDiary,
  listDiaries,
  optimizeText,
  saveDiary,
  type DiaryEntry,
} from '../../services/personalWorkApi'
import './index.scss'

type DiaryFieldKey = 'today_work' | 'tomorrow_plan' | 'thoughts'
type DiaryStatusTone = 'normal' | 'ok' | 'error'
type DiaryMode = 'write' | 'browse'

interface DiarySection {
  key: DiaryFieldKey
  title: string
  subtitle: string
  placeholder: string
}

interface DiaryOptimizePreview {
  original: string
  suggestion: string
}

const diarySections: DiarySection[] = [
  {
    key: 'today_work',
    title: '今日工作内容',
    subtitle: '记录今天完成的主要工作、遇到的问题、解决方案',
    placeholder: '例如：优化周报助手页面交互，调整编辑、预览、邮件发送三个核心流程...',
  },
  {
    key: 'tomorrow_plan',
    title: '明日工作计划',
    subtitle: '记录明天要推进的事项',
    placeholder: '例如：检查工作日记入口和保存交互，优化用户引导文案...',
  },
  {
    key: 'thoughts',
    title: '思路与想法',
    subtitle: '记录灵感、改进建议、学习心得',
    placeholder: '例如：工作日记的目标是降低记录成本，让用户每天愿意打开...',
  },
]

const weekdayTexts = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

const today = toDateInputValue(new Date())
const activeMode = ref<DiaryMode>('write')
const selectedDate = ref(today)
const selectedDiary = ref<DiaryEntry | null>(null)
const statusMessage = ref('选择日期后可以直接记录或载入已有日记。')
const statusTone = ref<DiaryStatusTone>('normal')
const diaries = ref<DiaryEntry[]>([])
const optimizingField = ref<DiaryFieldKey | ''>('')
const promptEditor = ref<DiaryFieldKey | ''>('')
const promptDraft = ref('')

const filters = reactive({
  keyword: '',
  start: '',
  end: '',
})

const diaryForm = reactive<Record<DiaryFieldKey, string>>({
  today_work: '',
  tomorrow_plan: '',
  thoughts: '',
})
const promptForm = reactive<Record<DiaryFieldKey, string>>({
  today_work: '',
  tomorrow_plan: '',
  thoughts: '',
})
const optimizePreview = reactive<Record<DiaryFieldKey, DiaryOptimizePreview | null>>({
  today_work: null,
  tomorrow_plan: null,
  thoughts: null,
})

const loading = reactive({
  current: false,
  list: false,
  detail: false,
  save: false,
  delete: false,
})

const pageTitle = computed(() => (activeMode.value === 'browse' ? '浏览日记' : '工作日记'))
const pageSubtitle = computed(() =>
  activeMode.value === 'browse'
    ? '查看历史工作记录，快速回顾每日进展。'
    : '记录今天的工作、明日计划和临时想法，系统会自动沉淀为周报素材。',
)
const filledSectionCount = computed(() => diarySections.filter((section) => diaryForm[section.key].trim()).length)
const totalContentLength = computed(() => diarySections.reduce((total, section) => total + diaryForm[section.key].trim().length, 0))
const currentDiary = computed(() => diaries.value.find((item) => item.date === selectedDate.value))
const currentUpdatedText = computed(() => formatDateTime(currentDiary.value?.updated_at || ''))
const statusText = computed(() => {
  if (loading.save) return '正在保存'
  if (currentUpdatedText.value) return `最后更新：${currentUpdatedText.value}`
  return '尚未保存'
})
const listSummary = computed(() => {
  if (loading.list) return '加载中'
  return diaries.value.length ? `共 ${diaries.value.length} 条` : '暂无日记'
})
const recentDiaries = computed(() => diaries.value.slice(0, 3))
const detailUpdatedText = computed(() => formatDateTime(selectedDiary.value?.updated_at || selectedDiary.value?.created_at || ''))
const currentPromptSection = computed(() => diarySections.find((section) => section.key === promptEditor.value))
const promptDialogVisible = computed({
  get: () => Boolean(promptEditor.value),
  set: (visible) => {
    if (!visible) promptEditor.value = ''
  },
})
const promptDialogTitle = computed(() => (currentPromptSection.value ? `${currentPromptSection.value.title}提示词` : '提示词'))

function toDateInputValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseDateValue(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function formatDateText(value: string) {
  const [year, month, day] = value.split('-')
  return year && month && day ? `${year}年${month}月${day}日` : value
}

function formatDiaryDate(value: string) {
  const date = parseDateValue(value)
  if (!date) return value
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}.${month}.${day}（${weekdayTexts[date.getDay()]}）`
}

function formatMonthDay(value: string) {
  const date = parseDateValue(value)
  if (!date) return value
  return `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')}`
}

function formatWeekday(value: string) {
  const date = parseDateValue(value)
  return date ? weekdayTexts[date.getDay()].replace('星期', '周') : ''
}

function formatDateTime(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ')
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatUpdateTime(value: string) {
  if (!value) return '未记录时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ')
  return `${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })} 更新`
}

function setStatus(message: string, tone: DiaryStatusTone = 'normal') {
  statusMessage.value = message
  statusTone.value = tone
}

function applyDiary(diary: DiaryEntry | null) {
  diaryForm.today_work = diary?.today_work || ''
  diaryForm.tomorrow_plan = diary?.tomorrow_plan || ''
  diaryForm.thoughts = diary?.thoughts || ''
  diarySections.forEach((section) => {
    optimizePreview[section.key] = null
  })
}

function diaryPreview(entry: DiaryEntry) {
  return entry.today_work_preview || entry.today_work || entry.tomorrow_plan || entry.thoughts || '无内容'
}

function validateDiary() {
  if (!selectedDate.value) {
    ElMessage.warning('请选择日记日期')
    return false
  }
  if (!totalContentLength.value) {
    ElMessage.warning('请至少填写一项日记内容')
    return false
  }
  return true
}

function handleDiaryFieldInput(key: DiaryFieldKey) {
  if (!optimizePreview[key]) return
  optimizePreview[key] = null
}

function openPromptEditor(section: DiarySection) {
  promptEditor.value = section.key
  promptDraft.value = optimizePrompt(section.key)
}

function savePromptEditor() {
  if (!promptEditor.value) return
  promptForm[promptEditor.value] = promptDraft.value.trim()
  promptEditor.value = ''
  ElMessage.success('提示词已更新')
}

function optimizePrompt(fieldKey: DiaryFieldKey) {
  return promptForm[fieldKey] || defaultOptimizePrompt()
}

async function optimizeDiaryField(section: DiarySection) {
  const original = diaryForm[section.key].trim()
  if (!original) {
    ElMessage.warning('请先填写需要润色的内容')
    return
  }
  optimizingField.value = section.key
  optimizePreview[section.key] = null
  try {
    const result = await optimizeText(original, optimizePrompt(section.key))
    optimizePreview[section.key] = {
      original,
      suggestion: result.text || original,
    }
    if (result.warning) ElMessage.warning(result.warning)
    else ElMessage.success('已生成润色结果，请对比后采纳')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'AI 润色失败')
  } finally {
    optimizingField.value = ''
  }
}

function ignoreOptimizePreview(key: DiaryFieldKey) {
  optimizePreview[key] = null
}

function acceptOptimizePreview(key: DiaryFieldKey) {
  const preview = optimizePreview[key]
  if (!preview) return
  diaryForm[key] = preview.suggestion
  optimizePreview[key] = null
}

async function setDiaryMode(mode: DiaryMode) {
  activeMode.value = mode
  if (mode === 'browse') {
    await loadDiaryList(true)
  }
}

async function loadDiaryToForm(date = selectedDate.value) {
  if (!date) return
  loading.current = true
  try {
    const result = await getDiary(date)
    selectedDate.value = date
    applyDiary(result.diary)
    setStatus(result.diary ? `已载入 ${formatDateText(date)} 的日记` : `${formatDateText(date)} 暂无日记，可以直接填写`, result.diary ? 'ok' : 'normal')
  } catch (error) {
    applyDiary(null)
    setStatus(error instanceof Error ? error.message : '读取日记失败', 'error')
  } finally {
    loading.current = false
  }
}

async function loadDiaryList(selectFirst = false) {
  loading.list = true
  try {
    const result = await listDiaries({
      limit: 100,
      start: filters.start,
      end: filters.end,
      keyword: filters.keyword.trim(),
    })
    diaries.value = result.diaries
    if (activeMode.value === 'browse') {
      const existing = selectedDiary.value ? result.diaries.find((item) => item.date === selectedDiary.value?.date) : null
      const nextDiary = selectFirst || !existing ? result.diaries[0] || null : existing
      selectedDiary.value = nextDiary
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '日记列表加载失败')
  } finally {
    loading.list = false
  }
}

async function saveCurrentDiary() {
  if (!validateDiary()) return
  loading.save = true
  try {
    const result = await saveDiary({ date: selectedDate.value, ...diaryForm })
    await loadDiaryList()
    selectedDiary.value = result.diary
    setStatus(`${formatDateText(selectedDate.value)} 的日记已保存`, 'ok')
    ElMessage.success('日记已保存')
  } catch (error) {
    setStatus(error instanceof Error ? error.message : '日记保存失败', 'error')
  } finally {
    loading.save = false
  }
}

function clearDiaryForm() {
  applyDiary(null)
  setStatus('已清空当前表单，保存后才会覆盖日记。')
}

async function loadTodayDiary() {
  selectedDate.value = today
  await loadDiaryToForm(today)
}

async function returnTodayDiary() {
  activeMode.value = 'write'
  await loadTodayDiary()
}

async function selectDiary(entry: DiaryEntry) {
  loading.detail = true
  try {
    const result = await getDiary(entry.date)
    selectedDiary.value = result.diary || entry
  } catch (error) {
    selectedDiary.value = entry
    ElMessage.error(error instanceof Error ? error.message : '读取日记详情失败')
  } finally {
    loading.detail = false
  }
}

async function viewDiary(entry: DiaryEntry) {
  activeMode.value = 'browse'
  await selectDiary(entry)
}

async function editDiary(entry: DiaryEntry) {
  activeMode.value = 'write'
  selectedDate.value = entry.date
  await loadDiaryToForm(entry.date)
}

async function deleteDiaryItem(entry: DiaryEntry) {
  try {
    await ElMessageBox.confirm(`确定删除 ${formatDateText(entry.date)} 的工作日记吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    loading.delete = true
    await deleteDiary(entry.date)
    if (selectedDate.value === entry.date) applyDiary(null)
    if (selectedDiary.value?.date === entry.date) selectedDiary.value = null
    await loadDiaryList(true)
    setStatus(`${formatDateText(entry.date)} 的日记已删除`, 'ok')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '删除日记失败')
  } finally {
    loading.delete = false
  }
}

async function initializeDiary() {
  await Promise.all([loadDiaryToForm(), loadDiaryList()])
}

onMounted(initializeDiary)
</script>

<template>
  <section class="diary-main">
    <header class="diary-page-head">
      <div>
        <h1>{{ pageTitle }}</h1>
        <p>{{ pageSubtitle }}</p>
      </div>
      <nav class="diary-mode-tabs" aria-label="工作日记视图">
        <button :class="{ active: activeMode === 'write' }" type="button" @click="setDiaryMode('write')">记录日记</button>
        <button :class="{ active: activeMode === 'browse' }" type="button" @click="setDiaryMode('browse')">浏览日记</button>
      </nav>
    </header>

    <section v-if="activeMode === 'write'" class="diary-write-layout">
      <div class="diary-write-column">
        <section class="diary-control-card">
          <el-date-picker
            v-model="selectedDate"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY.MM.DD"
            placeholder="选择日期"
            :disabled="loading.current"
            @change="loadDiaryToForm(selectedDate)"
          />
          <div class="diary-control-actions">
            <IconTextButton icon="history" :disabled="loading.current" @click="loadTodayDiary">载入今天</IconTextButton>
            <IconTextButton icon="refresh" @click="clearDiaryForm">清空</IconTextButton>
            <IconTextButton icon="send" variant="primary" :disabled="loading.save" @click="saveCurrentDiary">
              {{ loading.save ? '保存中' : '保存日记' }}
            </IconTextButton>
          </div>
        </section>

        <section
          v-for="section in diarySections"
          :key="section.key"
          :data-field="section.key"
          :class="['diary-section-card', { featured: section.key === 'today_work' }]"
        >
          <header class="diary-section-head">
            <span class="diary-section-dot" aria-hidden="true"></span>
            <div>
              <h2>{{ section.title }}</h2>
              <p>{{ section.subtitle }}</p>
            </div>
            <div class="diary-section-tools ai-field-actions">
              <button class="ai-prompt-button" type="button" @click="openPromptEditor(section)">提示词</button>
              <button class="ai-polish-button" type="button" :disabled="optimizingField !== ''" @click="optimizeDiaryField(section)">
                <span aria-hidden="true">✦</span>
                {{ optimizingField === section.key ? '润色中' : 'AI 润色' }}
              </button>
            </div>
          </header>
          <el-input
            v-model="diaryForm[section.key]"
            type="textarea"
            :placeholder="section.placeholder"
            :autosize="{ minRows: section.key === 'today_work' ? 5 : 3, maxRows: 10 }"
            @input="handleDiaryFieldInput(section.key)"
          />
          <div v-if="optimizePreview[section.key]" class="diary-ai-compare-card">
            <div class="diary-ai-compare-grid">
              <section>
                <span>原内容</span>
                <p>{{ optimizePreview[section.key]?.original }}</p>
              </section>
              <section>
                <span>润色结果</span>
                <p>{{ optimizePreview[section.key]?.suggestion }}</p>
              </section>
            </div>
            <div class="diary-ai-compare-actions">
              <button type="button" @click="ignoreOptimizePreview(section.key)">忽略</button>
              <button class="primary" type="button" @click="acceptOptimizePreview(section.key)">采纳建议</button>
            </div>
          </div>
        </section>

        <div class="diary-status-strip" :class="statusTone">
          <span aria-hidden="true"></span>
          <strong>{{ statusText }}</strong>
          <em>|</em>
          <small>{{ statusMessage }} · 已填写 {{ filledSectionCount }}/{{ diarySections.length }} 项 · {{ totalContentLength }} 字</small>
        </div>
      </div>

      <aside class="diary-right-rail">
        <section class="diary-recent-card">
          <header>
            <h2>最近日记</h2>
            <button type="button" @click="setDiaryMode('browse')">查看更多</button>
          </header>
          <div class="diary-recent-list">
            <button v-for="(entry, index) in recentDiaries" :key="entry.date" type="button" @click="viewDiary(entry)">
              <span class="diary-recent-date">
                <strong>{{ formatMonthDay(entry.date) }}</strong>
                <em>{{ formatWeekday(entry.date) }}</em>
              </span>
              <span :class="['diary-recent-dot', index % 2 ? 'warm' : 'blue']" aria-hidden="true"></span>
              <span class="diary-recent-copy">
                <strong>{{ diaryPreview(entry) }}</strong>
                <small>{{ formatUpdateTime(entry.updated_at || entry.created_at || '') }}</small>
              </span>
            </button>
            <div v-if="!recentDiaries.length && !loading.list" class="diary-empty">暂无日记，先记录今天的工作进展。</div>
            <div v-if="loading.list" class="diary-empty">正在加载日记列表...</div>
          </div>
          <button class="diary-all-button" type="button" @click="setDiaryMode('browse')">
            查看全部日记
            <el-icon><ArrowRight /></el-icon>
          </button>
        </section>
      </aside>
    </section>

    <section v-else class="diary-browse-layout">
      <section class="diary-browse-toolbar">
        <el-date-picker v-model="filters.start" type="date" value-format="YYYY-MM-DD" format="YYYY.MM.DD" placeholder="开始日期" />
        <span class="diary-date-separator">→</span>
        <el-date-picker v-model="filters.end" type="date" value-format="YYYY-MM-DD" format="YYYY.MM.DD" placeholder="结束日期" />
        <el-input v-model="filters.keyword" placeholder="搜索关键词" clearable @keyup.enter="loadDiaryList(true)">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <IconTextButton icon="refresh" :disabled="loading.list" @click="loadDiaryList(true)">刷新</IconTextButton>
        <button class="diary-back-write" type="button" @click="setDiaryMode('write')">返回记录日记</button>
      </section>

      <section class="diary-browse-content">
        <aside class="diary-list-card">
          <div class="diary-list-scroll">
            <button
              v-for="entry in diaries"
              :key="entry.date"
              :class="['diary-list-item', { active: selectedDiary?.date === entry.date }]"
              type="button"
              @click="selectDiary(entry)"
            >
              <span class="diary-list-date">
                <strong>{{ entry.date.replaceAll('-', '.') }}</strong>
                <em>{{ formatWeekday(entry.date) }}</em>
              </span>
              <span class="diary-list-copy">
                <strong>{{ diaryPreview(entry) }}</strong>
                <small>{{ formatUpdateTime(entry.updated_at || entry.created_at || '') }}</small>
              </span>
              <span class="diary-list-tag">已记录</span>
            </button>
            <div v-if="!diaries.length && !loading.list" class="diary-empty diary-empty--list">暂无日记，去记录第一篇吧。</div>
            <div v-if="loading.list" class="diary-empty diary-empty--list">正在加载日记列表...</div>
          </div>
          <footer>{{ listSummary }}</footer>
        </aside>

        <article class="diary-detail-panel">
          <template v-if="selectedDiary">
            <header>
              <div>
                <h2>{{ formatDiaryDate(selectedDiary.date) }}</h2>
                <p>{{ detailUpdatedText ? `${detailUpdatedText} 更新` : '未记录更新时间' }}</p>
              </div>
              <div class="diary-detail-top-actions">
                <button type="button" @click="editDiary(selectedDiary)">
                  <el-icon><EditPen /></el-icon>
                  编辑
                </button>
                <button class="danger" type="button" :disabled="loading.delete" @click="deleteDiaryItem(selectedDiary)">
                  <el-icon><Delete /></el-icon>
                  删除
                </button>
              </div>
            </header>

            <div class="diary-detail-sections">
              <section v-for="section in diarySections" :key="section.key">
                <h3>{{ section.title }}</h3>
                <p>{{ selectedDiary[section.key] || '（无内容）' }}</p>
              </section>
            </div>

            <footer>
              <button type="button" @click="editDiary(selectedDiary)">编辑这篇日记</button>
              <button class="primary" type="button" @click="returnTodayDiary">返回记录今天</button>
            </footer>
          </template>
          <div v-else class="diary-detail-empty">
            <strong>暂无可查看的日记</strong>
            <span>记录保存后，会在这里展示完整内容。</span>
          </div>
        </article>
      </section>
    </section>

    <el-dialog
      v-model="promptDialogVisible"
      class="diary-prompt-dialog"
      :title="promptDialogTitle"
      width="min(620px, 94vw)"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-input v-model="promptDraft" type="textarea" :autosize="{ minRows: 5, maxRows: 8 }" />
      <template #footer>
        <div class="diary-prompt-actions prompt-dialog-actions">
          <el-button class="prompt-dialog-button" @click="promptEditor = ''">取消</el-button>
          <el-button class="prompt-dialog-button prompt-dialog-button--primary" @click="savePromptEditor">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>
