import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../src/views/LoginView/index.vue', import.meta.url), 'utf8')
const handler = source.slice(source.indexOf('async function handleLogin()'), source.indexOf('async function loadResetCaptcha()'))
async function attempt(redirect, failure = false) {
  const navigations = []
  const errors = []
  const context = vm.createContext({
    loading: { value: false },
    form: { username: ' test ', password: 'test', remember: false },
    loginFormRef: { value: { validate: async () => true } },
    loginSession: async () => { if (failure) throw new Error('failed') },
    localStorage: { removeItem() {}, setItem() {} },
    rememberedUsernameKey: 'username', rememberedPasswordKey: 'password',
    route: { query: { redirect } },
    lastVisitedMenu: () => 'crm',
    window: { location: { replace: path => navigations.push(path) } },
    ElMessage: { error: error => errors.push(error) },
  })
  await vm.runInContext(`${handler}\nhandleLogin()`, context)
  return { navigations, errors }
}
assert.deepEqual((await attempt()).navigations, ['/workspace/crm'])
assert.deepEqual((await attempt('/workspace/knowledge?tab=docs')).navigations, ['/workspace/knowledge?tab=docs'])
for (const redirect of ['https://example.com', '//example.com', '/workspace/\\example.com']) {
  assert.deepEqual((await attempt(redirect)).navigations, ['/workspace/dashboard'])
}
const failed = await attempt('/workspace/crm', true)
assert.equal(failed.navigations.length, 0)
assert.equal(failed.errors.length, 1)
const workspace = fs.readFileSync(new URL('../src/views/WorkspaceView/index.vue', import.meta.url), 'utf8')
assert.match(workspace, /await logoutSession\(\)\s+window.location.replace\('\/login'\)/)
console.log('Account login reload tests passed')
