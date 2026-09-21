import { reactive } from 'vue'
import { session, type User } from './personalWorkApi.knowledge'

export const authState = reactive({ checked: false, loading: false, user: null as User | null, assistantPrompt: '' })
let task: Promise<typeof authState> | null = null

export async function ensureSession(force = false) {
  if (authState.checked && !force) return authState
  if (task) return task
  authState.loading = true
  task = session().then((data) => {
    authState.user = data.authenticated ? data.user : null
    authState.assistantPrompt = data.assistant_prompt || ''
    authState.checked = true
    return authState
  }).catch(() => {
    authState.user = null
    authState.assistantPrompt = ''
    authState.checked = true
    return authState
  }).finally(() => { authState.loading = false; task = null })
  return task
}
