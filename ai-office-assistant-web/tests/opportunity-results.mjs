import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/opportunityResults.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
const results = exports.opportunityResults
assert.equal(results([]).rate, null)
assert.equal(results([{ outcome: 'active' }, {}]).rate, null)
assert.equal(results([{ outcome: 'lost' }]).rate, 0)
assert.equal(results([{ outcome: 'won' }]).rate, 100)
const mixed = results([{ outcome: 'won' }, { outcome: 'lost' }, { outcome: 'active' }, { outcome: 'cancelled' }])
assert.equal(mixed.rate, 50)
assert.equal(mixed.closed, 2)
console.log('PASS actual conversion: empty, won, lost, active and unknown outcomes')
