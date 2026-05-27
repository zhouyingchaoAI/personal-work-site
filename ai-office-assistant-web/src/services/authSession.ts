import { reactive } from 'vue'
import { login, logout, session, type User } from './personalWorkApi'

export const authState = reactive({
  checked: false,
  loading: false,
  user: null as User | null,
  assistantPrompt: '',
})

let sessionTask: Promise<typeof authState> | null = null

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
