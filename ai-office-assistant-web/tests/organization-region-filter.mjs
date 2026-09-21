import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'

const file = new URL('../src/views/CrmAssistantView/organizationRegionFilter.ts', import.meta.url)
assert.ok(fs.existsSync(file), 'missing organization region filter')
const exports = {}
vm.runInNewContext(
  ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText,
  { exports },
)
const { filterOrganizationByRegion } = exports

const units = [
  { id: 'group', name: '集团', parent_unit_id: '', business_regions: [] },
  { id: 'east', name: '东区公司', parent_unit_id: 'group', business_regions: ['东区'] },
  { id: 'east-dept', name: '东区技术部', parent_unit_id: 'east', business_regions: ['东区'] },
  { id: 'west', name: '西区公司', parent_unit_id: 'group', business_regions: ['西区'] },
  { id: 'unassigned', name: '待分区单位', parent_unit_id: '', business_regions: [] },
]

assert.deepEqual(
  filterOrganizationByRegion(units, '东区').map(unit => unit.id),
  ['group', 'east', 'east-dept'],
  'keeps matching organizations and their ancestry so the tree remains connected',
)
assert.deepEqual(
  filterOrganizationByRegion(units, '未分区').map(unit => unit.id),
  ['group', 'unassigned'],
  'includes every organization without a business region when filtering unassigned',
)
assert.deepEqual(
  filterOrganizationByRegion(units, '').map(unit => unit.id),
  units.map(unit => unit.id),
  'does not alter the organization tree when no region is selected',
)
console.log('PASS region filter retains organization ancestry and unassigned units')
