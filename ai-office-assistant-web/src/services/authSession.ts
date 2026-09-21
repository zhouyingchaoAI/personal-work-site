import { reactive } from 'vue'
import { login, logout, session, type User } from './personalWorkApi'

export const DEFAULT_ASSISTANT_PROMPT = `请帮我优化下面的工作内容，要求：
1、严格保留原有段落、编号、列表、表格和字段顺序，不拆分、合并或重新编号。
2、语言准确、清晰，体现已有的实际工作量和推进成果。
3、修正错别字、病句和不通顺表达。
4、不要编造不存在的事项、数据、计划或结论，不写空话套话。`

export const authState = reactive({
  checked: false,
  loading: false,
  user: null as User | null,
  assistantPrompt: '',
})

let sessionTask: Promise<typeof authState> | null = null

// 字段润色默认使用后台会话配置，配置缺失时回到内置提示词。
export function defaultOptimizePrompt() {
  return authState.assistantPrompt || DEFAULT_ASSISTANT_PROMPT
}

export async function ensureSession(force = false) {
  if (authState.checked && !force) return authState
  if (sessionTask) return sessionTask
  authState.loading = true
  sessionTask = session()
    .then((data) => {
      authState.user = data.authenticated ? data.user : null
      authState.assistantPrompt = data.assistant_prompt || ''
      authState.checked = true
      return authState
    })
    .catch(() => {
      authState.user = null
      authState.assistantPrompt = ''
      authState.checked = true
      return authState
    })
    .finally(() => {
      authState.loading = false
      sessionTask = null
    })
  return sessionTask
}

export async function loginSession(username: string, password: string) {
  const data = await login(username, password)
  authState.user = data.user
  authState.assistantPrompt = data.assistant_prompt || ''
  authState.checked = true
}

export async function logoutSession() {
  await logout()
  authState.user = null
  authState.checked = true
}
