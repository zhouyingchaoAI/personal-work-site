import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = fs.readFileSync(new URL('../src/services/personalWorkApi.ts', import.meta.url), 'utf8').replaceAll('import.meta.env', '({})')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const redirects = []
const exports = {}
let response
vm.runInNewContext(compiled, {
  exports,
  URL,
  fetch: async () => response,
  require: () => ({ apiTaskLabel: () => '', beginBackgroundTask: () => 0, finishBackgroundTask: () => {} }),
  window: { location: { pathname: '/workspace/knowledge', search: '', hash: '', assign: value => redirects.push(value) } },
})
for (const status of [200, 502, 503]) {
  response = new Response('<html>upstream unavailable</html>', { status, headers: { 'content-type': 'text/html' } })
  await assert.rejects(exports.listKnowledgeDocs('mine'), /服务暂时不可用/)
  assert.equal(redirects.length, 0)
}
response = new Response('{"error":"请先登录"}', { status: 401, headers: { 'content-type': 'application/json' } })
await assert.rejects(exports.listKnowledgeDocs('mine'), /请先登录/)
assert.deepEqual(redirects, ['/login?redirect=%2Fworkspace%2Fknowledge'])
console.log('API redirect regression tests passed')
