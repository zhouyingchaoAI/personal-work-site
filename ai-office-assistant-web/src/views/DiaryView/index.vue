<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, EditPen, Refresh, Search } from '@element-plus/icons-vue'
import AssistantChat from '../../components/AssistantChat/index.vue'
import IconTextButton from '../../components/IconTextButton/index.vue'
import {
  agentChat,
  deleteDiary,
  getDiary,
  listDiaries,
  resourceUrl,
  saveDiary,
  type AgentMessage,
  type DiaryEntry,
} from '../../services/personalWorkApi'
import './index.scss'

type DiaryFieldKey = 'today_work' | 'tomorrow_plan' | 'thoughts'
type DiaryStatusTone = 'normal' | 'ok' | 'error'

interface DiarySection {
  key: DiaryFieldKey
  title: string
  subtitle: string
  placeholder: string
}

const diarySections: DiarySection[] = [
  {
    key: 'today_work',
    title: '今日工作内容',
    subtitle: '记录已完成、推进中和临时处理的事项',
    placeholder: '例如：完成周报助手页面联调；处理出差报告预览样式；和同事确认接口字段...',
  },
  {
    key: 'tomorrow_plan',
    title: '明日工作计划',
    subtitle: '写下明天要推进的任务和优先级',
    placeholder: '例如：继续验证邮件发送流程；补齐工作日记页面；整理测试结果...',
  },
  {
    key: 'thoughts',
    title: '思路与想法',
    subtitle: '沉淀问题、改进建议、复盘或灵感',
    placeholder: '例如：历史数据列表应该限制在容器内滚动；保存前需要明确提示必填项...',
  },
]

const assistantAvatar = resourceUrl('/assets/ai-assistant-avatar.png')
const assistantQuickActions = ['查看最近日记', '帮我整理今天的工作日记。', '根据本周日记提炼周报素材。']

const today = toDateInputValue(new Date())
const selectedDate = ref(today)
const statusMessage = ref('选择日期后可以直接记录或载入已有日记。')
const statusTone = ref<DiaryStatusTone>('normal')
const diaries = ref<DiaryEntry[]>([])
const detailDiary = ref<DiaryEntry | null>(null)
const detailVisible = ref(false)
const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantLoading = ref(false)
const assistantMessages = ref<AgentMessage[]>([
  { role: 'assistant', content: '你好，我是犇犇。你可以把今天完成的工作、明天计划和想法告诉我，我会帮你整理成工作日记。' },
])

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

const loading = reactive({
  current: false,
  list: false,
  save: false,
  delete: false,
})

const filledSectionCount = computed(() => diarySections.filter((section) => diaryForm[section.key].trim()).length)
const totalContentLength = computed(() => diarySections.reduce((total, section) => total + diaryForm[section.key].trim().length, 0))
const currentDiary = computed(() => diaries.value.find((item) => item.date === selectedDate.value))
const currentUpdatedText = computed(() => formatDateTime(currentDiary.value?.updated_at || ''))
const statusText = computed(() => {
  if (loading.save) return '正在保存'
  if (currentUpdatedText.value) return `上次保存：${currentUpdatedText.value}`
  return '尚未保存'
})
const listSummary = computed(() => {
  if (loading.list) return '加载中'
  return diaries.value.length ? `${diaries.value.length} 篇日记` : '暂无日记'
})

function toDateInputValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDateText(value: string) {
  const [year, month, day] = value.split('-')
  return year && month && day ? `${year}年${month}月${day}日` : value
}

function formatDateTime(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ')
  return date.toLocaleString()
}

function setStatus(message: string, tone: DiaryStatusTone = 'normal') {
  statusMessage.value = message
  statusTone.value = tone
}

function applyDiary(diary: DiaryEntry | null) {
  diaryForm.today_work = diary?.today_work || ''
  diaryForm.tomorrow_plan = diary?.tomorrow_plan || ''
  diaryForm.thoughts = diary?.thoughts || ''
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

async function loadDiaryList() {
  loading.list = true
  try {
    const result = await listDiaries({
      limit: 100,
      start: filters.start,
      end: filters.end,
      keyword: filters.keyword.trim(),
    })
    diaries.value = result.diaries
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
    await saveDiary({ date: selectedDate.value, ...diaryForm })
    await loadDiaryList()
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

async function openDiaryDetail(entry: DiaryEntry) {
  try {
    const result = await getDiary(entry.date)
    detailDiary.value = result.diary || entry
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取日记详情失败')
  }
}

function editDiary(entry: DiaryEntry) {
  detailVisible.value = false
  selectedDate.value = entry.date
  applyDiary(entry)
  setStatus(`正在编辑 ${formatDateText(entry.date)} 的日记`)
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
    if (detailDiary.value?.date === entry.date) detailVisible.value = false
    await loadDiaryList()
    setStatus(`${formatDateText(entry.date)} 的日记已删除`, 'ok')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '删除日记失败')
  } finally {
    loading.delete = false
  }
}

async function sendAssistantMessage(text = assistantInput.value) {
  const content = text.trim()
  if (!content) {
    ElMessage.warning('请输入要问犇犇的内容')
    return
  }
  assistantOpen.value = true
  assistantMessages.value.push({ role: 'user', content })
  assistantInput.value = ''
  assistantLoading.value = true
  try {
    const result = await agentChat('diary', assistantMessages.value.slice(-8))
    if (!result.ok) throw new Error(result.error || 'AI 助手暂时不可用')
    assistantMessages.value.push({ role: 'assistant', content: result.reply || '我看到了，当前没有新的补充。' })
    await loadDiaryList()
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 助手暂时不可用' })
  } finally {
    assistantLoading.value = false
  }
}

async function initializeDiary() {
  await Promise.all([loadDiaryToForm(), loadDiaryList()])
}

onMounted(initializeDiary)
</script>

<template>
  <section class="diary-main">
    <section class="diary-toolbar">
      <div class="diary-toolbar-title">
        <span class="diary-kicker">今日记录</span>
        <h2>{{ formatDateText(selectedDate) }}</h2>
        <p :class="statusTone">{{ statusMessage }}</p>
      </div>
      <div class="diary-toolbar-controls">
        <label>
          <span>日记日期</span>
          <el-date-picker
            v-model="selectedDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            :disabled="loading.current"
            @change="loadDiaryToForm(selectedDate)"
          />
        </label>
        <IconTextButton icon="history" :disabled="loading.current" @click="loadTodayDiary">载入今天</IconTextButton>
        <IconTextButton icon="sparkle" @click="assistantOpen = true">打开日记助手</IconTextButton>
        <IconTextButton icon="send" variant="primary" :disabled="loading.save" @click="saveCurrentDiary">
          {{ loading.save ? '保存中' : '保存日记' }}
        </IconTextButton>
      </div>
    </section>

    <section class="diary-workspace">
      <section class="diary-editor-card">
        <header class="diary-editor-head">
          <div>
            <h3>日记内容</h3>
            <span>{{ filledSectionCount }}/{{ diarySections.length }} 个模块已填写 · {{ totalContentLength }} 字</span>
          </div>
          <button class="diary-ghost-button" type="button" @click="clearDiaryForm">清空当前内容</button>
        </header>

        <div class="diary-field-stack">
          <section v-for="section in diarySections" :key="section.key" class="diary-field-block">
            <div class="diary-field-head">
              <div>
                <strong>{{ section.title }}</strong>
                <span>{{ section.subtitle }}</span>
              </div>
              <em>{{ diaryForm[section.key].trim().length }} 字</em>
            </div>
            <el-input
              v-model="diaryForm[section.key]"
              type="textarea"
              :placeholder="section.placeholder"
              :autosize="{ minRows: section.key === 'today_work' ? 7 : 5, maxRows: 10 }"
            />
          </section>
        </div>
      </section>

      <aside class="diary-side-panel">
        <section class="diary-side-card diary-history-card">
          <header class="diary-side-head">
            <div>
              <h3>历史日记</h3>
              <span>{{ listSummary }}</span>
            </div>
            <button type="button" :disabled="loading.list" aria-label="刷新日记列表" @click="loadDiaryList">
              <el-icon><Refresh /></el-icon>
            </button>
          </header>

          <div class="diary-filter-grid">
            <el-input v-model="filters.keyword" placeholder="搜索内容或日期" clearable @keyup.enter="loadDiaryList">
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-date-picker v-model="filters.start" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
            <el-date-picker v-model="filters.end" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
            <button type="button" @click="loadDiaryList">筛选</button>
          </div>

          <div class="diary-history-scroll">
            <article
              v-for="entry in diaries"
              :key="entry.date"
              :class="['diary-history-item', { active: entry.date === selectedDate }]"
            >
              <button class="diary-history-main" type="button" @click="openDiaryDetail(entry)">
                <span>{{ formatDateText(entry.date) }}</span>
                <strong>{{ diaryPreview(entry) }}</strong>
                <em>{{ formatDateTime(entry.updated_at || entry.created_at || '') || '未记录时间' }}</em>
              </button>
              <div class="diary-history-actions">
                <button type="button" aria-label="编辑日记" @click="editDiary(entry)">
                  <el-icon><EditPen /></el-icon>
                </button>
                <button type="button" aria-label="删除日记" :disabled="loading.delete" @click="deleteDiaryItem(entry)">
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
            </article>
            <div v-if="!diaries.length && !loading.list" class="diary-empty">暂无日记，先记录今天的工作进展。</div>
            <div v-if="loading.list" class="diary-empty">正在加载日记列表...</div>
          </div>
        </section>

        <section class="diary-side-card diary-assistant-card">
          <div class="diary-assistant-title">
            <img :src="assistantAvatar" alt="犇犇" />
            <div>
              <h3>犇犇助手</h3>
              <p>可以帮你整理日记、查询历史记录。</p>
            </div>
          </div>
          <div class="diary-assistant-actions">
            <button v-for="item in assistantQuickActions" :key="item" type="button" @click="sendAssistantMessage(item)">
              {{ item }}
            </button>
          </div>
        </section>
      </aside>
    </section>

    <section class="diary-footer">
      <div>
        <strong>{{ statusText }}</strong>
        <span>{{ selectedDate }} · 已填写 {{ filledSectionCount }} 项</span>
      </div>
      <div class="diary-footer-actions">
        <button type="button" @click="loadDiaryToForm(selectedDate)">重新载入</button>
        <button class="primary" type="button" :disabled="loading.save" @click="saveCurrentDiary">
          {{ loading.save ? '保存中' : '保存日记' }}
        </button>
      </div>
    </section>

    <el-dialog
      v-model="detailVisible"
      class="diary-detail-dialog"
      width="min(760px, 94vw)"
      append-to-body
      destroy-on-close
      :title="detailDiary ? `${formatDateText(detailDiary.date)} 日记详情` : '日记详情'"
    >
      <div v-if="detailDiary" class="diary-detail-body">
        <section v-for="section in diarySections" :key="section.key" class="diary-detail-section">
          <span>{{ section.title }}</span>
          <p>{{ detailDiary[section.key] || '（无内容）' }}</p>
        </section>
      </div>
      <template #footer>
        <div v-if="detailDiary" class="diary-detail-actions">
          <el-button @click="detailVisible = false">关闭</el-button>
          <el-button @click="editDiary(detailDiary)">编辑</el-button>
          <el-button type="danger" :disabled="loading.delete" @click="deleteDiaryItem(detailDiary)">删除</el-button>
        </div>
      </template>
    </el-dialog>

    <AssistantChat
      v-model:open="assistantOpen"
      v-model:input="assistantInput"
      :avatar="assistantAvatar"
      :messages="assistantMessages"
      :quick-actions="assistantQuickActions"
      :loading="assistantLoading"
      @send="sendAssistantMessage"
    />
  </section>
</template>
