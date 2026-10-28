import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/views/DataCenterView/storageStatus.ts', import.meta.url), 'utf8')
const exports = {}
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
const classify = (modes) => exports.storageStatus(modes.map(mode => ({ mode })))
assert.equal(classify(['database', 'database']).key, 'database')
assert.equal(classify(['database', 'object']).key, 'managed')
assert.equal(classify(['object']).key, 'managed')
assert.equal(classify(['database', 'file']).key, 'mixed')
assert.equal(classify(['file']).key, 'file')
assert.equal(classify(['file', 'external']).key, 'file')
assert.equal(classify(['database', 'unknown']).key, 'unknown')
assert.equal(classify([]).key, 'unknown')
assert.equal(classify(['external']).key, 'unknown')
assert.equal(classify(['file', 'external']).unverified, 1)
assert.equal(exports.storageStatus([{ mode: 'file', mirror_evidence: [{ verified: true }] }]).key, 'file')
assert.equal(classify(['database', 'file', 'object']).local, 1)
console.log('PASS: 12 storage status checks; mirrors never count as primary migration')
