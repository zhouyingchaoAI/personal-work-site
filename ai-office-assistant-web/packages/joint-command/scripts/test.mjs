import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const webRoot = fileURLToPath(new URL('../../../', import.meta.url))
const tests = readdirSync(resolve(webRoot, 'tests')).filter(name => name.endsWith('.mjs') && readFileSync(resolve(webRoot, 'tests', name), 'utf8').includes('packages/joint-command/frontend'))
let failures = 0
for (const name of tests) {
  const result = spawnSync(process.execPath, [resolve(webRoot, 'tests', name)], { cwd: webRoot, stdio: 'inherit' })
  if (result.status !== 0) failures += 1
}
console.log(`Joint command: ${tests.length} suites, ${failures} failed`)
process.exitCode = failures ? 1 : 0
