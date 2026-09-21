import { ref } from 'vue'

export type AiWritingStyle = 'clear' | 'concise' | 'formal' | 'detailed'

export const AI_WRITING_STYLE_STORAGE_KEY = 'personalOffice.aiWritingStyle'
const AI_WRITING_STYLE_PROMPT_STORAGE_PREFIX = 'personalOffice.aiWritingStylePrompt'

export const AI_WRITING_STYLES: Array<{ value: AiWritingStyle; label: string; instruction: string }> = [
  { value: 'clear', label: '口语清晰', instruction: '使用自然、易懂、直接的表达，避免生硬套话。' },
  { value: 'concise', label: '精炼专业', instruction: '用简洁、专业的办公表达，突出行动、结果和关键数据。' },
  { value: 'formal', label: '正式官方', instruction: '采用规范、稳重、正式的汇报口吻，措辞严谨、客观。' },
  { value: 'detailed', label: '详述完整', instruction: '在不补充新事实的前提下，充分交代背景、动作、过程和结果。' },
]

function savedStyle(): AiWritingStyle {
  const value = typeof window === 'undefined' ? '' : window.localStorage.getItem(AI_WRITING_STYLE_STORAGE_KEY)
  return AI_WRITING_STYLES.some((item) => item.value === value) ? value as AiWritingStyle : 'concise'
}

export const writingStyle = ref<AiWritingStyle>(savedStyle())

export function setWritingStyle(style: AiWritingStyle) {
  writingStyle.value = style
  if (typeof window !== 'undefined') window.localStorage.setItem(AI_WRITING_STYLE_STORAGE_KEY, style)
}

function stylePromptKey(owner: string, scope: string, field: string, style: AiWritingStyle) {
  return `${AI_WRITING_STYLE_PROMPT_STORAGE_PREFIX}.${owner || 'guest'}.${scope}.${field}.${style}`
}

/** 每个用户、助手字段和行文风格分别保存补充提示词；null 表示从未设置。 */
export function getSavedStylePrompt(owner: string, scope: string, field: string, style: AiWritingStyle) {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(stylePromptKey(owner, scope, field, style))
}

export function saveStylePrompt(owner: string, scope: string, field: string, style: AiWritingStyle, prompt: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(stylePromptKey(owner, scope, field, style), prompt.trim())
}

export function writingStyleInstruction(style: AiWritingStyle) {
  const currentStyle = AI_WRITING_STYLES.find((item) => item.value === style) || AI_WRITING_STYLES[1]
  return `当前为「${currentStyle.label}」：${currentStyle.instruction}`
}

export function extraOptimizePrompt(value: string) {
  const prompt = value.trim()
  // 旧版默认提示词要求拆分、改号，与当前“保留结构”规则冲突；不再把它当成用户额外偏好。
  return /拆分成\s*1[、，,]?\s*2[、，,]?\s*3[、，,]?\s*4.*编号要点/.test(prompt) ? '' : prompt
}

export function buildOptimizePrompt(style: AiWritingStyle, extraInstruction = '') {
  const currentStyle = AI_WRITING_STYLES.find((item) => item.value === style) || AI_WRITING_STYLES[1]
  const extra = extraInstruction.trim()
  return [
    '请润色以下中文办公文本，只输出润色后的正文，不解释。',
    '硬性要求：严格保留原文的段落、编号、列表、表格、字段顺序与事项边界；不得合并、拆分、改号或新增标题。不得编造事实、数据、成果、计划或困难。',
    `行文风格：${currentStyle.label}。${currentStyle.instruction}`,
    '统一修正错别字、病句和不通顺表达，使内容准确、连贯、可直接用于工作日报、周报或出差报告。',
    extra ? `补充偏好（仅在不与硬性要求冲突时执行）：${extra}` : '',
  ].filter(Boolean).join('\n')
}
