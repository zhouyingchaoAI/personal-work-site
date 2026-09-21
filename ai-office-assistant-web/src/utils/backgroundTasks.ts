import { computed, reactive } from 'vue'

export interface BackgroundTask {
  id: number
  label: string
  startedAt: number
}

const state = reactive<{ nextId: number; tasks: BackgroundTask[] }>({ nextId: 1, tasks: [] })

export const backgroundTasks = computed(() => state.tasks)
export const activeBackgroundTaskCount = computed(() => state.tasks.length)

export function beginBackgroundTask(label: string) {
  const id = state.nextId++
  state.tasks.push({ id, label, startedAt: Date.now() })
  return id
}

export function finishBackgroundTask(id: number) {
  const index = state.tasks.findIndex((task) => task.id === id)
  if (index >= 0) state.tasks.splice(index, 1)
}

export function apiTaskLabel(path: string, method?: string) {
  const value = path.split('?')[0]
  if (value === '/generate') return '报告助手：正在生成报告'
  if (value === '/optimize') return 'AI：正在润色内容'
  if (value === '/diary/summarize') return '工作日记：正在智能总结'
  if (value === '/reimbursement/scan') return '报销助手：正在扫描票据'
  if (value.startsWith('/writing/outline')) return '智能写作：正在生成大纲'
  if (value.startsWith('/writing/generate')) return '智能写作：正在生成正文'
  if (value.startsWith('/writing/rewrite')) return '智能写作：正在改写文稿'
  if (value.startsWith('/writing/upload')) return '智能写作：正在上传素材'
  if (value.startsWith('/knowledge/upload')) return '知识库：正在上传文档'
  if (value.startsWith('/knowledge/ask') || value.startsWith('/knowledge/search')) return '知识库：正在检索回答'
  if (value.startsWith('/agent')) return 'AI 助手：正在思考回复'
  if (value.startsWith('/meeting/')) return '会议助手：正在处理会议内容'
  if (method?.toUpperCase() === 'POST') return '助手：正在处理操作'
  return ''
}
