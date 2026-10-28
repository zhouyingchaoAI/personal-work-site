import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
import vm from 'node:vm'
const exports = {}
vm.runInNewContext(ts.transpile(fs.readFileSync('packages/joint-command/frontend/chartAppearance.ts', 'utf8'), { module: ts.ModuleKind.CommonJS }), { exports })
assert.equal(exports.cleanAppearance({ fontSize: 99 }).fontSize, 24)
assert.equal(exports.cleanAppearance({ fontSize: NaN }).fontSize, undefined)
assert.equal(exports.cleanAppearance({ background: 'url(https://invalid)' }).background, undefined)
assert.equal(exports.cleanAppearance({ textColor: '#234567' }).textColor, '#234567')
assert.equal(exports.cleanAppearance({ align: 'bad', unknown: 'value' }).align, undefined)
assert.equal(exports.appearanceVariables({ padding: 0 })['--editor-padding'], '0px')
assert.equal(exports.contrastRatio('#ffffff', '#ffffff'), 1)
assert.equal(exports.contrastRatio('#000000', '#ffffff'), 21)
assert.equal(exports.contrastRatio(undefined, '#ffffff'), null)
assert.equal(exports.cleanAppearance({ fontFamily: 'url(test)' }).fontFamily, undefined)
assert.ok(exports.appearanceVariables({ fontFamily: 'mono' })['--editor-fontFamily'].includes('monospace'))
for (const preset of Object.values(exports.appearancePresets)) assert.equal(JSON.stringify(exports.cleanAppearance(preset.style)), JSON.stringify(exports.cleanAppearance(exports.cleanAppearance(preset.style))))
console.log('PASS appearance validation, limits, presets and CSS variables')
