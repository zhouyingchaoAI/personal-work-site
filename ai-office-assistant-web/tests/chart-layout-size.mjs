import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
import vm from 'node:vm'
const exports = {}
const source = fs.readFileSync('packages/joint-command/frontend/chartLayoutSize.ts', 'utf8')
vm.runInNewContext(ts.transpile(source, { module: ts.ModuleKind.CommonJS }), { exports })
const resize = exports.resizeChart
assert.equal(exports.gridSpan(493, [492.5, 492.5], 16), 1)
assert.equal(exports.gridSpan(500, [492.5, 492.5], 16), 2)
assert.equal(exports.gridSpan(1001, [492.5, 492.5], 16), 2)
assert.equal(resize(400, 300, 100, 90, 'right').width, 500)
assert.equal(resize(400, 300, 100, 90, 'right').height, 300)
assert.equal(resize(400, 300, 100, -60, 'bottom').width, 400)
assert.equal(resize(400, 300, 100, -60, 'bottom').height, 240)
assert.equal(resize(400, 300, 100, -60, 'corner').width, 500)
assert.equal(resize(400, 300, 100, -60, 'corner').height, 240)
assert.equal(resize(400, 300, -999, -999, 'corner').width, 180)
console.log('PASS independent width and height resizing')
assert.equal(exports.contentZoom(400, 300, 600, 300, 1, 'right'), 1)
assert.equal(exports.contentZoom(600, 300, 400, 300, 1.2, 'right'), 1.2)
assert.equal(exports.contentZoom(400, 300, 400, 150, 1, 'bottom'), 0.5)
assert.equal(exports.contentZoom(400, 300, 800, 450, 1, 'corner'), 1.5)
