<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Plus, EditPen, Delete } from '@element-plus/icons-vue'
import type { CrmPerson, CrmUnit } from '../../services/personalWorkApi'

type Level = 'company' | 'subsidiary' | 'unit' | 'department'
interface CanvasNode {
  id: string
  label: string
  hint: string
  level: Level
  parentId: string
  unit?: CrmUnit
  person?: CrmPerson
}

const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; readOnly?: boolean }>()
const emit = defineEmits<{
  addUnit: [level: Exclude<Level, 'department'>, parentId?: string]
  editUnit: [unit: CrmUnit]
  editPerson: [person: CrmPerson]
  moveUnit: [unit: CrmUnit, parentId: string]
  deleteUnit: [unit: CrmUnit]
  movePerson: [person: CrmPerson, unitId: string, department: string]
}>()
const selectedRoot = ref(''), personSearch = ref(''), personDrag = ref<CrmPerson | null>(null), targetDepartment = ref('')
const scopedIds = computed(() => {
  const ids = new Set<string>()
  if (!props.units.some(u => u.id === selectedRoot.value)) return ids
  ids.add(selectedRoot.value)
  let changed = true
  while (changed) { changed = false; for (const u of props.units) if (u.parent_unit_id && ids.has(u.parent_unit_id) && !ids.has(u.id)) { ids.add(u.id); changed = true } }
  return ids
})
const scopedUnits = computed(() => props.units.filter(u => scopedIds.value.has(u.id)))
const scopedPeople = computed(() => props.people.filter(p => scopedIds.value.has(p.unit_id)))
const matchingPeople = computed(() => scopedPeople.value.filter(p => `${p.name} ${p.department || ''}`.includes(personSearch.value.trim())))
function personDrop(target: CanvasNode) {
  const person = personDrag.value
  personDrag.value = null
  if (!person || props.readOnly) return
  const unitId = target.unit?.id || target.parentId
  const department = target.level === 'department' ? target.person?.department || '' : targetDepartment.value.trim()
  if (scopedIds.value.has(unitId) && (person.unit_id !== unitId || person.department !== department)) emit('movePerson', person, unitId, department)
}

const stage = ref<HTMLElement>()
const itemRefs = new Map<string, HTMLElement>()
const linePoints = ref<Record<string, { x: number; y: number }>>({})
const dragging = ref<CanvasNode | null>(null)
const dropTarget = ref('')
const columns: Array<{ level: Level; title: string; subtitle: string }> = [
  { level: 'company', title: '公司', subtitle: '最高级组织' },
  { level: 'subsidiary', title: '子公司', subtitle: '归属公司' },
  { level: 'unit', title: '单位', subtitle: '业务组织' },
  { level: 'department', title: '部门', subtitle: '联系人归属' },
]

const normalizedLevel = (unit: CrmUnit): Exclude<Level, 'department'> => {
  if (unit.organization_level === 'company' || unit.organization_level === 'subsidiary') return unit.organization_level
  return 'unit'
}
const nodes = computed<CanvasNode[]>(() => {
  const organization = scopedUnits.value.map((unit) => ({
    id: unit.id,
    label: unit.name,
    hint: [unit.type, unit.region].filter(Boolean).join(' · ') || '客户组织',
    level: normalizedLevel(unit),
    parentId: unit.parent_unit_id || '',
    unit,
  }))
  const departments = new Map<string, CanvasNode>()
  for (const person of scopedPeople.value) {
    const unit = scopedUnits.value.find((item) => item.id === person.unit_id)
    if (!unit) continue
    const name = person.department || '待补充部门'
    const id = `department:${unit.id}:${name}`
    const current = departments.get(id)
    if (current) current.hint = `${unit.name} · ${scopedPeople.value.filter(p => p.unit_id === unit.id && (p.department || '待补充部门') === name).length} 位联系人`
    else departments.set(id, { id, label: name, hint: `${unit.name} · 1 位联系人`, level: 'department', parentId: unit.id, person })
  }
  return [...organization, ...departments.values()]
})
const nodesByLevel = computed<Record<Level, CanvasNode[]>>(() => ({
  company: nodes.value.filter((node) => node.level === 'company'),
  subsidiary: nodes.value.filter((node) => node.level === 'subsidiary'),
  unit: nodes.value.filter((node) => node.level === 'unit'),
  department: nodes.value.filter((node) => node.level === 'department'),
}))
const allNodes = computed(() => nodes.value)

const links = computed(() => allNodes.value
  .filter((node) => node.parentId && linePoints.value[node.id] && linePoints.value[node.parentId])
  .map((node) => ({ id: node.id, from: linePoints.value[node.parentId], to: linePoints.value[node.id] })))

function setItemRef(id: string, element: unknown) {
  if (element instanceof HTMLElement) itemRefs.set(id, element)
  else itemRefs.delete(id)
}
function refreshLines() {
  const box = stage.value?.getBoundingClientRect()
  if (!box) return
  const next: Record<string, { x: number; y: number }> = {}
  for (const node of allNodes.value) {
    const rect = itemRefs.get(node.id)?.getBoundingClientRect()
    if (rect) next[node.id] = { x: rect.left - box.left + rect.width / 2, y: rect.top - box.top + rect.height / 2 }
  }
  linePoints.value = next
}
function isValidTarget(source: CanvasNode, target: CanvasNode) {
  if (!source.unit || !target.unit || source.id === target.id) return false
  if (source.level === 'subsidiary') return target.level === 'company'
  if (source.level === 'unit') return target.level === 'company' || target.level === 'subsidiary'
  return false
}
function startDrag(node: CanvasNode) {
  if (props.readOnly || !node.unit || node.level === 'company') return
  dragging.value = node
}
function dropOn(target: CanvasNode) {
  const source = dragging.value
  dragging.value = null
  dropTarget.value = ''
  if (source?.unit && isValidTarget(source, target) && source.parentId !== target.id) emit('moveUnit', source.unit, target.id)
}
function add(level: Exclude<Level, 'department'>) {
  const candidate = level === 'subsidiary'
    ? allNodes.value.find((node) => node.level === 'company')
    : level === 'unit'
      ? allNodes.value.find((node) => node.level === 'subsidiary') || allNodes.value.find((node) => node.level === 'company')
      : undefined
  emit('addUnit', level, candidate?.id || '')
}
function addChild(node: CanvasNode) {
  if (node.level === 'company') emit('addUnit', 'subsidiary', node.id)
  if (node.level === 'subsidiary') emit('addUnit', 'unit', node.id)
}
function nodeClick(node: CanvasNode) {
  if (node.unit) emit('editUnit', node.unit)
  else if (node.person) emit('editPerson', node.person)
}
watch(nodes, () => nextTick(refreshLines), { deep: true })
onMounted(() => { window.addEventListener('resize', refreshLines); nextTick(refreshLines) })
onBeforeUnmount(() => window.removeEventListener('resize', refreshLines))
</script>

<template>
  <section class="organization-canvas" aria-label="客户组织调整画布">
    <div class="scope-picker"><b>先选择一个客户或组织</b><el-select v-model="selectedRoot" filterable clearable placeholder="搜索并选择本次调整的组织" aria-label="本次调整组织" @change="personDrag = null; dragging = null"><el-option v-for="unit in units" :key="unit.id" :value="unit.id" :label="`${unit.company_full_name && unit.company_full_name !== unit.name ? unit.company_full_name + ' / ' : ''}${unit.name}`" /></el-select><span v-if="selectedRoot">{{ scopedUnits.length }} 个组织 · {{ scopedPeople.length }} 位联系人</span></div>
    <el-empty v-if="!selectedRoot" description="每次仅调整一个组织及其下级，请先选择组织" />
    <template v-else>
    <header class="canvas-head">
      <div><h3>自顶而下调整组织</h3><p>先调整公司、子公司和单位，再将下方联系人拖到单位或部门；人员已有关系和行动记录保留。</p></div>
      <div v-if="!readOnly" class="canvas-add">
        <el-button size="small" :icon="Plus" @click="add('unit')">新增单位</el-button>
      </div>
    </header>
    <div ref="stage" class="canvas-stage">
      <svg class="canvas-links" aria-hidden="true"><path v-for="link in links" :key="link.id" :d="`M ${link.from.x} ${link.from.y} C ${(link.from.x + link.to.x) / 2} ${link.from.y}, ${(link.from.x + link.to.x) / 2} ${link.to.y}, ${link.to.x} ${link.to.y}`" /></svg>
      <section v-for="column in columns" :key="column.level" class="canvas-column">
        <div class="column-head"><strong>{{ column.title }}</strong><small>{{ column.subtitle }}</small><el-button v-if="!readOnly && column.level !== 'department' && column.level !== 'company'" link size="small" :icon="Plus" @click="add(column.level as Exclude<Level, 'department'>)">新增</el-button></div>
        <div class="canvas-column-body">
          <article v-for="node in nodesByLevel[column.level]" :key="node.id" :ref="(element) => setItemRef(node.id, element)" class="canvas-node" :data-node-id="node.id" :class="[`canvas-node--${node.level}`, { 'canvas-node--dragging': dragging?.id === node.id, 'canvas-node--drop': dropTarget === node.id }]" :draggable="!readOnly && !!node.unit && node.level !== 'company' && node.id !== selectedRoot" @dragstart="startDrag(node)" @dragend="dragging = null; dropTarget = ''" @dragover.prevent="!readOnly && (personDrag || isValidTarget(dragging || node, node)) && (dropTarget = node.id)" @dragleave="dropTarget === node.id && (dropTarget = '')" @drop.prevent="personDrag ? personDrop(node) : dropOn(node)">
            <button class="node-main" @click="nodeClick(node)"><strong>{{ node.label }}</strong><small>{{ node.hint }}</small></button>
            <div v-if="node.unit && !readOnly" class="node-actions">
              <el-button v-if="node.level === 'company' || node.level === 'subsidiary'" link size="small" :icon="Plus" title="新增下级组织" @click.stop="addChild(node)" />
              <el-button link size="small" :icon="EditPen" title="编辑组织" @click.stop="emit('editUnit', node.unit)" />
              <el-button link size="small" type="danger" :icon="Delete" title="删除空组织" @click.stop="emit('deleteUnit', node.unit)" />
            </div>
          </article>
          <p v-if="!nodesByLevel[column.level].length" class="empty-column">暂无{{ column.title }}节点</p>
        </div>
      </section>
    </div>
    <section class="person-pool"><h3>组织联系人 · 拖到上方单位或部门匹配</h3><div class="scope-picker"><el-input v-model="personSearch" placeholder="搜索姓名或部门" aria-label="搜索待匹配人员" /><el-input v-model="targetDepartment" :disabled="readOnly" placeholder="拖到单位时的目标部门（可填写新部门；留空为未分部门）" aria-label="目标部门" /></div><div class="person-pool-items"><button v-for="person in matchingPeople" :key="person.id" :draggable="!readOnly" :data-person-id="person.id" @dragstart="personDrag = person; dragging = null" @dragend="personDrag = null; dropTarget = ''" @click="emit('editPerson',person)"><b>{{ person.name }}</b><small>{{ scopedUnits.find(u => u.id === person.unit_id)?.name }} / {{ person.department || '未分部门' }}</small></button></div><p v-if="!matchingPeople.length">当前组织下暂无匹配联系人。</p></section>
    <footer><span>可编辑：公司、子公司、单位；部门由联系人所属部门自动汇总。</span><span v-if="readOnly">当前为只读权限</span><span v-else>删除前需先处理下级组织与联系人。</span></footer>
    </template>
  </section>
</template>

<style scoped>
.scope-picker{display:flex;gap:12px;align-items:center;padding:16px;flex-wrap:wrap;}.scope-picker .el-select{width:440px;max-width:100%;}.scope-picker .el-input{flex:1;min-width:240px;}.person-pool{padding:16px;background:#fff;}.person-pool-items{display:flex;flex-wrap:wrap;gap:10px;max-height:240px;overflow:auto;}.person-pool-items button{padding:10px;border:1px solid #b9cde0;border-radius:8px;background:#f3f8ff;color:#244568;text-align:left;cursor:grab;}.person-pool-items small{display:block;margin-top:5px;}.canvas-stage{grid-template-columns:1fr!important;}.canvas-column-body{flex-direction:row!important;flex-wrap:wrap;min-height:80px!important;}.canvas-node{width:250px;max-width:100%;}.canvas-column{min-height:120px;}
.organization-canvas{min-height:590px;border:1px solid #dce7f4;border-radius:12px;background:#f8fbff;overflow:hidden}.canvas-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:16px 18px 12px;border-bottom:1px solid #e2ebf5;background:linear-gradient(135deg,#fff,#f1f7ff)}h3{margin:0;color:#1d3d62;font-size:16px}.canvas-head p,footer{margin:6px 0 0;color:#6f87a2;font-size:12px;line-height:1.55}.canvas-add{display:flex;gap:8px;flex-shrink:0}.canvas-stage{position:relative;display:grid;grid-template-columns:repeat(4,minmax(170px,1fr));gap:16px;min-height:488px;padding:16px;background-image:linear-gradient(rgba(72,126,177,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(72,126,177,.07) 1px,transparent 1px);background-size:24px 24px}.canvas-links{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}.canvas-links path{fill:none;stroke:#8caeca;stroke-width:2;stroke-dasharray:5 5;opacity:.72}.canvas-column{z-index:1;min-width:0;border:1px solid #d8e4f0;border-radius:10px;background:rgba(255,255,255,.86);box-shadow:0 5px 16px rgba(39,82,122,.05)}.column-head{min-height:58px;display:grid;grid-template-columns:1fr auto;gap:2px 8px;align-items:center;padding:10px 12px;border-bottom:1px solid #e7edf5;color:#315777}.column-head strong{font-size:14px}.column-head small{grid-column:1;color:#849ab0;font-size:11px}.column-head .el-button{grid-column:2;grid-row:1 / span 2}.canvas-column-body{display:flex;flex-direction:column;gap:10px;padding:12px;min-height:410px}.canvas-node{border:1px solid #b9cde0;border-radius:8px;background:#fff;box-shadow:0 2px 8px rgba(37,79,116,.08);transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}.canvas-node[draggable=true]{cursor:grab}.canvas-node[draggable=true]:active{cursor:grabbing}.canvas-node--company{border-left:4px solid #276bd0}.canvas-node--subsidiary{border-left:4px solid #7b61d9}.canvas-node--unit{border-left:4px solid #26a6a1}.canvas-node--department{border-left:4px solid #e4a33f}.canvas-node--dragging{opacity:.45;transform:scale(.97)}.canvas-node--drop{border-color:#2369d1;box-shadow:0 0 0 3px rgba(35,105,209,.18)}.node-main{display:block;width:100%;padding:10px 10px 6px;text-align:left;border:0;background:transparent;color:#244568;cursor:pointer}.node-main strong,.node-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.node-main strong{font-size:13px}.node-main small{margin-top:5px;color:#7d93a9;font-size:11px}.node-actions{display:flex;justify-content:flex-end;gap:1px;padding:0 6px 5px}.empty-column{margin:26px 0;color:#94a6b8;font-size:12px;text-align:center}footer{display:flex;justify-content:space-between;gap:16px;padding:10px 18px;background:#fff;border-top:1px solid #e2ebf5}@media(max-width:900px){.canvas-stage{grid-template-columns:repeat(2,minmax(170px,1fr));overflow:auto}.canvas-head{flex-direction:column}.canvas-add{flex-wrap:wrap}.organization-canvas{min-height:680px}}@media(max-width:560px){.canvas-stage{grid-template-columns:minmax(200px,1fr);min-height:780px}.canvas-links{display:none}}
</style>
