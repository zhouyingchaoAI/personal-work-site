import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const directory = new URL('../src/views/CrmAssistantView/dashboard/', import.meta.url)
function load(name, require = () => { throw new Error('Unexpected import') }) {
  const exports = {}
  const source = fs.readFileSync(new URL(name, directory), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports, require })
  return exports
}
const cities = load('cityProvince.ts')
const { customerCityGroups } = load('customerMapLabels.ts', () => cities)
const result = customerCityGroups([
  { name: '部门', company_full_name: '完整企业名称', region: '杭州市', business_regions: ['东区'] },
  { name: '分公司', company_full_name: '完整企业名称', region: '杭州', business_regions: ['西区'] },
  { name: '北京企业', region: '北京', business_region: '中区' },
  { name: '缺少城市', region: '' }, { name: '省份', region: '浙江' }, { name: '未知', region: '未知' },
])
assert.equal(result.groups.length, 2)
assert.equal(result.missing, 3)
assert.equal(result.groups[0].companies.length, 1)
assert.equal(result.groups[0].companies[0].name, '完整企业名称')
assert.equal(result.groups[0].companies[0].regions.join(','), '东区,西区')
assert.equal(result.groups[1].city, '北京')
assert.equal(customerCityGroups([]).groups.length, 0)
const { CITY_CENTERS } = load('cityCenters.ts')
for (const city of ['北京','天津','石家庄','衡水','青岛','洛阳','武汉','杭州','上海','广州','重庆']) {
  assert.equal(CITY_CENTERS[city].length, 2, `${city} has an offline center`)
}
for (const [lng,lat] of Object.values(CITY_CENTERS)) {
  assert.ok(Number.isFinite(lng) && lng >= 70 && lng <= 140)
  assert.ok(Number.isFinite(lat) && lat >= 0 && lat <= 60)
}
console.log('PASS: full names, same-city deduplication, cross-region merge, municipality, invalid/province-only exclusion, empty input')
