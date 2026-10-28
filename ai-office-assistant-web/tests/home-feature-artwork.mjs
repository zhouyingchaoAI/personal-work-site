import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

function loadSource(relative) {
  const url = new URL(relative, import.meta.url)
  const exports = {}
  const source = ts.transpileModule(fs.readFileSync(url, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  vm.runInNewContext(source, { exports, require: path => path.startsWith('.') ? { __esModule: true, default: new URL(path, url).pathname } : new Proxy({}, { get: (_, name) => name }) })
  return exports
}

const { homeFeatures } = loadSource('../src/data/pageData.ts')
const { sidebarMenuItems } = loadSource('../src/layout/menu.ts')
const menus = sidebarMenuItems.filter(item => item.group === 'main' && !item.fixed && item.showInSidebar !== false)
assert.equal(new Set(homeFeatures.map(item => item.menuId)).size, homeFeatures.length)
for (const menu of menus) {
  const feature = homeFeatures.find(item => item.menuId === menu.id)
  assert.ok(feature?.image, `${menu.id} needs dedicated homepage artwork`)
  assert.ok(fs.existsSync(feature.image), `${menu.id} artwork must exist locally`)
  assert.ok(feature.description && !feature.description.startsWith('打开'), `${menu.id} needs a meaningful caption`)
  if (feature.image.endsWith('.svg')) {
    const svg = fs.readFileSync(feature.image, 'utf8')
    assert.match(svg, /viewBox="0 0 96 96"/)
    assert.match(svg, /linearGradient/)
    assert.doesNotMatch(svg, /<script|<foreignObject|href="https?:/)
    assert.ok(Buffer.byteLength(svg) < 12000)
  }
}
console.log(`Homepage artwork coverage passed: ${menus.length} entries`)
