<script setup lang="ts">
import { computed, ref, reactive, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus, Download } from '@element-plus/icons-vue'
import { authState } from '../../services/authSession'
import type { CrmPerson, CrmUnit } from '../../services/personalWorkApi'
import { layoutOrganization, ORGANIZATION_NODE_WIDTH as nodeWidth } from './organizationLayout'
import { organizationSvg, downloadOrganizationDiagram } from './organizationExport'
const nodeHeight = 132
const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; readOnly?: boolean; internal?: boolean; initialRootId?: string; selectedId?: string }>()
const emit = defineEmits<{ addUnit:[level:'company'|'subsidiary'|'unit',parentId?:string]; editUnit:[unit:CrmUnit]; editPerson:[person:CrmPerson]; moveUnit:[unit:CrmUnit,parentId:string]; movePerson:[person:CrmPerson,unitId:string,department:string]; deleteUnit:[unit:CrmUnit]; addDepartmentChild:[unitId:string,department:string]; deleteDepartment:[unitId:string,department:string] }>()
type Point = { x:number; y:number }
type Node = { id:string; label:string; parent:string; unit?:CrmUnit; department?:string; unitId:string; depth:number }
const primaryRoot = ref(''), secondaryRoot = ref('')
const focusedRoot = ref('')
const root = computed(() => focusedRoot.value || secondaryRoot.value || primaryRoot.value)
const selected = ref(''), newParent = ref(''), search = ref(''), department = ref('')
const stage = ref<HTMLElement>(), positions = ref<Record<string,Point>>({}), history = ref<Record<string,Point>[]>([])
const view = reactive({x:40,y:40,zoom:1}), dragPerson = ref<CrmPerson|null>(null)
const collapsed = ref(new Set<string>()), showDepartments = ref(true), detailId = ref('')
const detailPage = ref(1), childPage = ref(1)
const exporting = ref(false)
async function exportDiagram(format: 'png' | 'svg') {
  if(exporting.value || !visibleNodes.value.length)return
  exporting.value=true
  try {
    await document.fonts.ready
    const title = `${byId.value.get(root.value)?.name || '组织'}组织架构图`
    const diagram = organizationSvg(visibleNodes.value.map(n => ({
      id:n.id, parent:n.parent, label:n.label, category:n.unit ? `组织 · 第 ${n.depth+1} 层` : '人员部门',
      subtitle:n.unit?.type || `${(nodePeople.value.get(n.id)||[]).length} 位联系人`,
      names:(nodePeople.value.get(n.id)||[]).map(p => props.internal ? p.name.split(' · ')[0]! : p.name),
      department:!n.unit, collapsed:collapsed.value.has(n.id),
      x:positions.value[n.id]?.x ?? NaN, y:positions.value[n.id]?.y ?? NaN,
    })), title, nodeWidth, nodeHeight)
    await downloadOrganizationDiagram(diagram, title, format)
    ElMessage.success('架构图已导出')
  } catch(error) { ElMessage.error(error instanceof Error ? error.message : '导出失败，请重试') }
  finally { exporting.value=false }
}
const byId = computed(() => new Map(props.units.map(u => [u.id,u])))
// Use actual parent links, not legacy company/subsidiary/unit category labels.
// A parent outside the visible dataset is treated as a visible top-level entry.
const primaryOptions = computed(() => props.units.filter(u => !u.parent_unit_id || !byId.value.has(u.parent_unit_id)))
const secondaryOptions = computed(() => props.units.filter(u => u.parent_unit_id === primaryRoot.value))
watch(primaryRoot,()=>{focusedRoot.value='';secondaryRoot.value=''}, {flush:'sync'})
watch(secondaryRoot,()=>{focusedRoot.value=''}, {flush:'sync'})
watch(primaryOptions,options=>{if(primaryRoot.value&&!options.some(u=>u.id===primaryRoot.value))primaryRoot.value=''}, {flush:'sync'})
watch(secondaryOptions,options=>{if(secondaryRoot.value&&!options.some(u=>u.id===secondaryRoot.value))secondaryRoot.value=''}, {flush:'sync'})
function descendants(id:string) {
  const ids = new Set<string>([id]); let changed = true
  while(changed) { changed=false; for(const u of props.units) if(u.parent_unit_id && ids.has(u.parent_unit_id) && !ids.has(u.id)) { ids.add(u.id); changed=true } }
  return ids
}
const ids = computed(() => root.value && byId.value.has(root.value) ? descendants(root.value) : new Set<string>())
const units = computed(() => props.units.filter(u => ids.value.has(u.id)))
const people = computed(() => props.people.filter(p => ids.value.has(p.unit_id)))
const visiblePeople = computed(() => {
  const n=current.value
  const branch=n?.unit?descendants(n.unitId):ids.value
  return props.people.filter(p=>{
    if(props.internal)return true
    const unassigned=p.unit_id===primaryRoot.value&&!p.department?.trim()
    if(unassigned)return true
    if(n&&!n.unit)return p.unit_id===n.unitId&&(p.department||'')===n.department
    return branch.has(p.unit_id)
  }).filter(p=>`${p.name} ${p.department||''} ${byId.value.get(p.unit_id)?.name||''}`.includes(search.value.trim()))
})
function unassignPerson(p:CrmPerson) {
  if(props.readOnly||props.internal||!primaryRoot.value)return
  emit('movePerson',p,primaryRoot.value,'')
}
function unassignedLabel(p:CrmPerson) {
  if(!byId.value.has(p.unit_id)||p.unit_id==='own:unassigned')return '未分配人员'
  const parent = byId.value.get(p.unit_id)?.parent_unit_id
  return !props.internal && !p.department?.trim() && (!parent || !byId.value.has(parent)) ? '未分配人员' : ''
}
const nodePeople = computed(() => {
  const result=new Map<string,CrmPerson[]>()
  for(const p of people.value){
    for(const key of [p.unit_id,'dept:'+JSON.stringify([p.unit_id,p.department||''])]){
      const list=result.get(key)||[];list.push(p);result.set(key,list)
    }
  }
  return result
})
const nodes = computed<Node[]>(() => {
  const list:Node[] = units.value.map(u => {
    let depth=0, cursor=u, seen=new Set<string>([u.id])
    while(cursor.id!==primaryRoot.value && cursor.parent_unit_id && byId.value.has(cursor.parent_unit_id) && !seen.has(cursor.parent_unit_id)) {
      seen.add(cursor.parent_unit_id); cursor=byId.value.get(cursor.parent_unit_id)!; depth++
    }
    return {id:u.id,label:u.name,parent:u.id===root.value?'':u.parent_unit_id||'',unit:u,unitId:u.id,depth}
  })
  const departments = new Set<string>()
  if(props.internal)return list
  for(const p of people.value) {
    if(!p.department?.trim() && !unassignedLabel(p))continue
    const id='dept:'+JSON.stringify([p.unit_id,p.department || ''])
    if(departments.has(id)) continue
    departments.add(id)
    list.push({id,label:p.department||'未分配人员',parent:p.unit_id,unitId:p.unit_id,department:p.department||'',depth:(list.find(n=>n.id===p.unit_id)?.depth||0)+1})
  }
  return list
})
const current = computed(() => nodes.value.find(n => n.id===selected.value))
const nodeById = computed(() => new Map(nodes.value.map(n => [n.id,n])))
const children = computed(() => {
  const result = new Map<string,Node[]>()
  for(const n of nodes.value) { const list=result.get(n.parent)||[];list.push(n);result.set(n.parent,list) }
  return result
})
const visibleNodes = computed(() => nodes.value.filter(n => {
  if(!showDepartments.value && !n.unit)return false
  let parent=n.parent;const seen=new Set<string>([n.id])
  while(parent && !seen.has(parent)) {
    if(collapsed.value.has(parent))return false
    seen.add(parent);parent=nodeById.value.get(parent)?.parent||''
  }
  return true
}))
const visibleIds = computed(() => new Set(visibleNodes.value.map(n=>n.id)))
const detailNode = computed(() => nodeById.value.get(detailId.value))
const detailChildren = computed(() => children.value.get(detailId.value)||[])
const detailPeople = computed(() => {
  const n=detailNode.value;if(!n)return []
  const branch=n.unit?descendants(n.unitId):new Set([n.unitId])
  return people.value.filter(p=>branch.has(p.unit_id) && (n.unit || (p.department||'')===n.department))
})
function toggleBranch(id:string) {
  const next=new Set(collapsed.value);if(next.has(id))next.delete(id);else next.add(id);collapsed.value=next
}
function openDetail(id:string) { detailId.value=id;detailPage.value=1;childPage.value=1 }
function locateDetail() {
  const n=detailNode.value;if(!n)return
  const next=new Set(collapsed.value), seen=new Set<string>();let parent=n.parent
  while(parent && !seen.has(parent)){seen.add(parent);next.delete(parent);parent=nodeById.value.get(parent)?.parent||''}
  collapsed.value=next;if(!n.unit)showDepartments.value=true
  selected.value=n.id;detailId.value=''
  void nextTick(()=>{const p=positions.value[n.id];if(p && stage.value){view.x=stage.value.clientWidth/2-(p.x+nodeWidth/2)*view.zoom;view.y=stage.value.clientHeight/2-(p.y+nodeHeight/2)*view.zoom}})
}
watch(visibleIds, ids=>{if(!ids.has(selected.value))selected.value=''})
const parentOptions = computed(() => current.value?.unit ? (props.internal ? props.units : units.value).filter(u => !descendants(current.value!.id).has(u.id)) : [])
const storageKey = () => `crm-org-layout-v2:${authState.user?.username || 'anonymous'}:${root.value}`
function persist() { try { localStorage.setItem(storageKey(),JSON.stringify(positions.value)) } catch { ElMessage.warning('浏览器无法保存布局，本次位置仍保留在画布中') } }
function checkpoint() { history.value.push(JSON.parse(JSON.stringify(positions.value))); if(history.value.length>20)history.value.shift() }
function layout(remember=true) {
  if(remember)checkpoint()
  // Hidden branches do not reserve space. Expanding relayouts the visible tree.
  positions.value={...positions.value,...layoutOrganization(visibleNodes.value)};persist();void nextTick(fit)
}
watch([collapsed, showDepartments], () => { if(root.value)layout() }, {flush:'post'})
function fit() {
  const rect=stage.value?.getBoundingClientRect(), points=visibleNodes.value.map(n=>positions.value[n.id]).filter((p):p is Point=>!!p)
  if(!rect || !points.length)return
  const left=Math.min(...points.map(p=>p.x)), top=Math.min(...points.map(p=>p.y))
  const width=Math.max(...points.map(p=>p.x))+nodeWidth-left, height=Math.max(...points.map(p=>p.y))+nodeHeight-top
  view.zoom=Math.min(1.2,Math.max(.08,Math.min((rect.width-70)/width,(rect.height-70)/height)))
  view.x=(rect.width-width*view.zoom)/2-left*view.zoom;view.y=(rect.height-height*view.zoom)/2-top*view.zoom
}
watch(stage, (element, _previous, cleanup) => {
  if(!element)return
  const observer=new ResizeObserver(()=>fit())
  observer.observe(element)
  cleanup(()=>observer.disconnect())
})
function undo() { const previous=history.value.pop();if(previous){positions.value=previous;persist()} }
function zoom(factor:number, x?:number,y?:number) {
  const next=Math.max(.08,Math.min(2.5,view.zoom*factor)), cx=x??(stage.value?.clientWidth||600)/2, cy=y??(stage.value?.clientHeight||500)/2
  view.x=cx-(cx-view.x)*next/view.zoom;view.y=cy-(cy-view.y)*next/view.zoom;view.zoom=next
}
function wheel(event:WheelEvent) { const r=stage.value!.getBoundingClientRect();zoom(event.deltaY<0?1.12:1/1.12,event.clientX-r.left,event.clientY-r.top) }
let motion:{id?:string;x:number;y:number;origin:Point}|null=null
function down(event:PointerEvent,id?:string) {
  if(event.button!==0 || (event.target as HTMLElement).closest('button,select,input'))return
  if(!id)selected.value=''
  if(id){selected.value=id;newParent.value='';checkpoint()}
  motion={id,x:event.clientX,y:event.clientY,origin:id?{...positions.value[id]!}:{x:view.x,y:view.y}}
  stage.value?.setPointerCapture(event.pointerId)
}
function move(event:PointerEvent) {
  if(!motion)return
  const dx=event.clientX-motion.x,dy=event.clientY-motion.y
  if(motion.id)positions.value[motion.id]={x:motion.origin.x+dx/view.zoom,y:motion.origin.y+dy/view.zoom}
  else {view.x=motion.origin.x+dx;view.y=motion.origin.y+dy}
}
function up() {if(motion?.id)persist();motion=null}
function drop(node:Node) {
  const person=dragPerson.value;dragPerson.value=null
  if(props.readOnly || !person)return
  const dep=node.unit?department.value.trim():node.department||''
  if(person.unit_id!==node.unitId || person.department!==dep)emit('movePerson',person,node.unitId,dep)
}
function reparent() { if(!props.readOnly && current.value?.unit && parentOptions.value.some(u=>u.id===newParent.value))emit('moveUnit',current.value.unit,newParent.value) }
watch(root, () => {
  selected.value='';history.value=[];dragPerson.value=null;collapsed.value=new Set();showDepartments.value=true;detailId.value=''
  let saved:Record<string,Point>={}
  try { saved=JSON.parse(localStorage.getItem(storageKey())||'{}') }catch { /* damaged browser layout gets rebuilt */ }
  positions.value={}
  if(saved && typeof saved==='object')for(const n of nodes.value) {const p=saved[n.id];if(p && Number.isFinite(p.x)&&Number.isFinite(p.y))positions.value[n.id]=p}
  if(!Object.keys(positions.value).length)layout(false)
  else void nextTick(fit)
})
watch(nodes, (nextNodes, previousNodes) => {
  const previousRoot=previousNodes.find(n=>!n.parent)?.id
  const topology=(items:Node[])=>JSON.stringify(items.map(n=>[n.id,n.parent]).sort((a,b)=>a[0]!.localeCompare(b[0]!)))
  // Refresh structural edits, but do not turn data reloads, renames, node drags,
  // zooming or changing the selected organization into unwanted layout resets.
  if(previousRoot===root.value && topology(nextNodes)!==topology(previousNodes)) {
    positions.value={...layoutOrganization(nextNodes),...layoutOrganization(visibleNodes.value)}
    history.value=[]
    persist()
    return
  }
  const keep:Record<string,Point>={}
  for(const n of nodes.value)if(positions.value[n.id])keep[n.id]=positions.value[n.id]!
  for(const n of nodes.value)if(!keep[n.id]) {
    const point={x:0,y:n.depth*200}
    while(Object.values(keep).some(p=>Math.abs(p.x-point.x)<nodeWidth+20 && Math.abs(p.y-point.y)<nodeHeight+20))point.x+=290
    keep[n.id]=point
  }
  positions.value=keep
}, {flush:'post'})
// Apply the row entry after layout watchers have been registered. Keep the
// ancestor selectors meaningful even when opening a third/deeper-level branch.
watch(() => props.initialRootId, async id => {
  const unit = id ? byId.value.get(id) : undefined
  if (!unit) {
    focusedRoot.value = ''
    // 打开画布直接进入脑图：未指定节点时自动落到第一个顶级组织，不再停留在空白「先选组织」态。
    if (!primaryRoot.value || !primaryOptions.value.some(u => u.id === primaryRoot.value)) primaryRoot.value = primaryOptions.value[0]?.id || ''
    return
  }
  const chain = [unit]
  const seen = new Set([unit.id])
  let parent = byId.value.get(unit.parent_unit_id || '')
  while (parent && !seen.has(parent.id)) {
    seen.add(parent.id); chain.unshift(parent)
    parent = byId.value.get(parent.parent_unit_id || '')
  }
  primaryRoot.value = chain[0]!.id
  secondaryRoot.value = chain[1]?.id || ''
  focusedRoot.value = unit.id
  await nextTick()
  if (root.value === unit.id) selected.value = unit.id
}, { immediate: true })
function addNodeChild(node: Node) {
  if(props.readOnly)return
  if(node.unit)emit('addUnit','unit',node.id)
  else emit('addDepartmentChild',node.unitId,node.department || '')
}
function deleteNode(node: Node) {
  if(props.readOnly)return
  if(node.unit)emit('deleteUnit',node.unit)
  else emit('deleteDepartment',node.unitId,node.department || '')
}
function jumpToNode(id: string) {
  if (!id) { selected.value=''; return }
  const next=new Set(collapsed.value), seen=new Set<string>()
  let parent=byId.value.get(id)?.parent_unit_id
  while(parent && !seen.has(parent)){seen.add(parent);next.delete(parent);parent=byId.value.get(parent)?.parent_unit_id}
  collapsed.value=next
  detailId.value=id
  void nextTick(locateDetail)
}
watch(() => props.selectedId, async id => {
  if(!id || !byId.value.has(id))return
  if(!ids.value.has(id)){
    let unit=byId.value.get(id)!, seen=new Set<string>()
    while(unit.parent_unit_id && byId.value.has(unit.parent_unit_id) && !seen.has(unit.id)){
      seen.add(unit.id);unit=byId.value.get(unit.parent_unit_id)!
    }
    primaryRoot.value=unit.id;secondaryRoot.value='';focusedRoot.value=''
  }
  await nextTick()
  jumpToNode(id)
})
watch(byId, index => { if (focusedRoot.value && !index.has(focusedRoot.value)) focusedRoot.value = '' })
</script>
<template>
<section class="org-editor" aria-label="可扩展组织架构编辑器">
  <header class="oe-toolbar">
    <el-select v-model="primaryRoot" filterable placeholder="选择组织架构" aria-label="本次调整组织"><el-option v-for="u in primaryOptions" :key="u.id" :value="u.id" :label="u.name" /></el-select>
    <el-select :model-value="selected" filterable clearable placeholder="搜索并定位任意层级节点" aria-label="定位组织节点" @change="jumpToNode"><el-option v-for="n in nodes" :key="n.id" :value="n.id" :label="n.label" /></el-select>
    <el-button v-if="!readOnly" :icon="Plus" @click="emit('addUnit','company','')">新建架构</el-button>
    <el-button @click="fit">适应画布</el-button><el-button @click="layout()">整理布局</el-button>
    <el-dropdown trigger="click" :disabled="exporting || !visibleNodes.length" @command="exportDiagram"><el-button :icon="Download" :loading="exporting" :disabled="!visibleNodes.length">导出架构图</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="png">PNG 图片</el-dropdown-item><el-dropdown-item command="svg">SVG 矢量图</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
    <el-dropdown trigger="click"><el-button>显示与布局 ▾</el-button><template #dropdown><el-dropdown-menu>
      <el-dropdown-item @click="zoom(1.2)">放大</el-dropdown-item><el-dropdown-item @click="zoom(1/1.2)">缩小</el-dropdown-item>
      <el-dropdown-item v-if="!internal" @click="showDepartments=!showDepartments">{{ showDepartments ? '收起部门' : '显示部门' }}</el-dropdown-item>
      <el-dropdown-item @click="collapsed=new Set();showDepartments=true">展开全部</el-dropdown-item>
      <el-dropdown-item :disabled="!history.length" @click="undo">撤销位置</el-dropdown-item>
    </el-dropdown-menu></template></el-dropdown>
    <span>{{ units.length }} 个组织 · {{ people.length }} 人</span><b>{{ Math.round(view.zoom*100) }}%</b>
  </header>
  <p class="oe-help">选中节点 → ＋ 输入名称创建下级 · 支持任意层级 · 拖动调整位置，滚轮缩放</p>
  <div v-if="focusedRoot" class="oe-focus-scope"><strong>当前调整：{{ byId.get(focusedRoot)?.name }}</strong><el-button link type="primary" @click="focusedRoot = ''; secondaryRoot = ''">查看完整一级组织</el-button></div>
  <div v-if="root" class="oe-properties"><template v-if="current"><b>{{ current.label }}</b><span>第 {{ current.depth+1 }} 层</span><template v-if="current.unit && !readOnly"><el-button :icon="Plus" @click="emit('addUnit','unit',current.id)">新增下级</el-button><el-button @click="emit('editUnit',current.unit)">编辑节点</el-button><el-select v-if="current.id!==root && current.unit.organization_level!=='company'" v-model="newParent" filterable placeholder="选择新上级" aria-label="新上级组织"><el-option v-for="u in parentOptions" :key="u.id" :value="u.id" :label="u.name"/></el-select><el-button v-if="newParent" @click="reparent">修改上级</el-button><el-button type="danger" plain :icon="Delete" @click="emit('deleteUnit',current.unit)">删除当前节点</el-button></template></template><span v-else>点击节点，编辑或继续增加下级组织。层数不受三级限制。</span></div>
  <div ref="stage" class="oe-stage" @pointerdown="down($event)" @pointermove="move" @pointerup="up" @pointercancel="up" @wheel.prevent="wheel">
    <el-empty v-if="!root" description="还没有可编辑的组织节点，点下方按钮直接在画布上新建"><el-button v-if="!readOnly" type="primary" @click="emit('addUnit','company','')">＋ 新增顶级组织</el-button></el-empty>
    <div v-else class="oe-world" :style="{transform:`translate(${view.x}px,${view.y}px) scale(${view.zoom})`}">
      <svg class="oe-edges"><template v-for="n in visibleNodes" :key="n.id"><path v-if="positions[n.id] && positions[n.parent] && visibleIds.has(n.parent)" :d="`M ${positions[n.parent]!.x+nodeWidth/2} ${positions[n.parent]!.y+nodeHeight} C ${positions[n.parent]!.x+nodeWidth/2} ${(positions[n.parent]!.y+nodeHeight+positions[n.id]!.y)/2} ${positions[n.id]!.x+nodeWidth/2} ${(positions[n.parent]!.y+nodeHeight+positions[n.id]!.y)/2} ${positions[n.id]!.x+nodeWidth/2} ${positions[n.id]!.y}`"/></template></svg>
      <article v-for="n in visibleNodes" :key="n.id" class="oe-node" :class="{selected:selected===n.id,department:!n.unit}" :data-node-id="n.id" :style="{width:nodeWidth+'px',height:nodeHeight+'px',left:(positions[n.id]?.x||0)+'px',top:(positions[n.id]?.y||0)+'px'}" tabindex="0" @keydown.enter="selected=n.id" @pointerdown.stop="down($event,n.id)" @dragover.prevent @drop.prevent="drop(n)"><small>{{ n.unit ? `组织 · 第 ${n.depth+1} 层` : '人员部门' }}</small><strong :title="n.label">{{ n.label }}</strong><span>{{ n.unit?.type || `${people.filter(p=>p.unit_id===n.unitId && (p.department||'')===n.department).length} 位联系人` }}</span><div class="oe-node-names"><span v-for="p in (nodePeople.get(n.id)||[]).slice(0,2)" :key="p.id" :class="{unassigned:!!unassignedLabel(p)}" :title="p.name+(unassignedLabel(p)?' · '+unassignedLabel(p):'')">{{ internal ? p.name.split(' · ')[0] : p.name }}</span><small v-if="!(nodePeople.get(n.id)||[]).length">暂无直属人员</small></div><small v-if="(nodePeople.get(n.id)?.length||0)>2" class="oe-more-names">另有 {{ (nodePeople.get(n.id)?.length||0)-2 }} 人 · 单独查看完整名单</small><div class="oe-node-actions"><button v-if="children.get(n.id)?.length" :aria-label="collapsed.has(n.id) ? '展开下级' : '收起下级'" :aria-expanded="!collapsed.has(n.id)" @click.stop="toggleBranch(n.id)">{{ collapsed.has(n.id) ? '展开' : '收起' }} {{ children.get(n.id)?.length }}</button><button @click.stop="openDetail(n.id)">单独查看</button></div><div v-if="!readOnly && selected === n.id" class="oe-node-quick-actions" @pointerdown.stop><button class="oe-node-add" :aria-label="`为${n.label}新增下级组织`" title="新增下级组织" @click.stop="addNodeChild(n)"><el-icon><Plus /></el-icon></button><button class="oe-node-delete" :aria-label="`删除${n.label}`" title="删除当前节点" @click.stop="deleteNode(n)"><el-icon><Delete /></el-icon></button></div></article>
    </div>
  </div>
<section v-if="root" class="oe-people"><header><b>组织人员匹配</b><el-input v-model="search" placeholder="搜索姓名或部门" aria-label="搜索待匹配人员"/><el-input v-if="!internal" v-model="department" placeholder="拖到组织时的目标部门，可新增" aria-label="目标部门" :disabled="readOnly"/></header><p>{{ internal ? '下方列出全部账号，可跨公司拖到目标部门；也可点击人员选择归属。修改保存后生效，账号和对接标识保持不变。' : '当前显示选中部门（选中组织时含下级）及一级组织未分配人员。移回未分配会清空部门并归回一级组织，保留关系与行动。' }}</p><div><article v-for="p in visiblePeople" :key="p.id" class="oe-person-item"><button :data-person-id="p.id" :class="{unassigned:!!unassignedLabel(p)}" :draggable="!readOnly" @dragstart="dragPerson=p" @dragend="dragPerson=null" @click="emit('editPerson',p)"><b>{{ p.name }} <em v-if="unassignedLabel(p)">{{unassignedLabel(p)}}</em></b><small>{{ byId.get(p.unit_id)?.name || '尚未分配组织' }}{{ internal ? '' : ' / '+(p.department||unassignedLabel(p)||'直属人员') }}</small></button><button v-if="!internal && !readOnly && (p.unit_id!==primaryRoot || p.department)" class="oe-unassign" @click="unassignPerson(p)" :aria-label="`将${p.name}移回未分配`">移回未分配</button></article><p v-if="!visiblePeople.length">当前范围暂无人员</p></div></section>
</section>
<el-dialog :model-value="!!detailNode" title="子节点与人员" width="min(780px, 94vw)" append-to-body @close="detailId=''">
  <template v-if="detailNode">
    <div class="oe-branch-head"><div><h3 class="oe-branch-title">{{ detailNode.label }}</h3><p>{{ detailNode.unit ? '组织分支' : '人员部门' }} · {{ detailChildren.length }} 个直接子节点 · {{ detailPeople.length }} 位联系人</p></div><el-button v-if="nodeById.has(detailNode.parent)" @click="openDetail(detailNode.parent)">返回上级</el-button></div>
    <h4>直接子节点 <small>点击逐层查看，不受画布收起状态影响</small></h4>
    <div class="oe-branch-children"><button v-for="n in detailChildren.slice((childPage-1)*12,childPage*12)" :key="n.id" class="oe-branch-item" @click="openDetail(n.id)"><strong>{{ n.label }}</strong><small>{{ n.unit ? '组织' : '部门' }} · 查看 →</small></button><p v-if="!detailChildren.length">当前节点没有下级节点</p></div>
    <el-pagination v-if="detailChildren.length>12" v-model:current-page="childPage" :page-size="12" :total="detailChildren.length" layout="prev, pager, next"/>
    <h4>{{ detailNode.unit ? '该分支联系人（含下级）' : '部门联系人' }}</h4>
    <div class="oe-branch-people"><article v-for="p in detailPeople.slice((detailPage-1)*15,detailPage*15)" :key="p.id"><b>{{ p.name }}</b><span>{{ byId.get(p.unit_id)?.name }} / {{ p.department || unassignedLabel(p) || '直属人员' }} / {{ p.title || '职务待补充' }}</span></article><p v-if="!detailPeople.length">暂无联系人</p></div>
    <el-pagination v-if="detailPeople.length>15" v-model:current-page="detailPage" :page-size="15" :total="detailPeople.length" layout="prev, pager, next, total"/>
  </template>
  <template #footer><el-button @click="detailId=''">返回画布</el-button><el-button type="primary" @click="locateDetail">定位到画布</el-button></template>
</el-dialog>
</template>
<style>
.crm-organization-canvas-dialog.el-dialog{height:92dvh;max-height:92dvh;display:flex;flex-direction:column;overflow:hidden;margin-bottom:0;box-sizing:border-box}
.crm-organization-canvas-dialog>.el-dialog__header{flex:none}
.crm-organization-canvas-dialog>.el-dialog__body{flex:1;min-height:0;overflow:hidden;display:flex;padding-top:0}
.crm-organization-canvas-dialog .oe-focus-scope {display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:8px 12px;background:#edf4ff;color:#15499c;font-size:13px;flex-shrink:0;}
.crm-organization-canvas-dialog .org-editor{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}
.crm-organization-canvas-dialog .oe-toolbar,.crm-organization-canvas-dialog .oe-properties{flex:none;padding:6px 10px;gap:6px;min-height:0;max-height:100px;overflow:auto}
.crm-organization-canvas-dialog .oe-toolbar .el-select{width:220px}
.crm-organization-canvas-dialog .oe-help{flex:none;margin:6px 0;max-height:32px;overflow:auto;font-size:11px}
.crm-organization-canvas-dialog .oe-stage{flex:1;min-height:120px;height:auto}
.crm-organization-canvas-dialog .oe-people{flex:0 1 24vh;min-height:90px;display:flex;flex-direction:column;overflow:hidden;padding:6px 10px}
.crm-organization-canvas-dialog .oe-people header{flex:none;padding:4px;gap:6px}
.crm-organization-canvas-dialog .oe-people p{flex:none;margin:4px 0;font-size:11px}
.crm-organization-canvas-dialog .oe-people>div{flex:1;min-height:0;max-height:none;overflow:auto;align-content:flex-start}
@media(max-width:650px){.crm-organization-canvas-dialog .oe-toolbar .el-select{width:150px}.crm-organization-canvas-dialog .oe-people header .el-input{width:150px}.crm-organization-canvas-dialog .oe-help{display:none}}
</style>
<style scoped>
.oe-person-item{display:flex;flex-direction:column;gap:3px}.oe-people .oe-unassign{font-size:11px;color:#a36522;padding:3px 8px;cursor:pointer}
.oe-person-item:has(>button.unassigned){background:#ffedcc;border-radius:7px;box-shadow:inset 0 0 0 2px #dc922b}
.oe-people .oe-person-item>button.unassigned{flex:1;background:#ffedcc;border-color:#dc922b;color:#78430e;box-shadow:inset 4px 0 #dc922b}
.oe-people .oe-person-item>button.unassigned small,.oe-people .oe-person-item>button.unassigned em{color:#87551c}
.oe-people .oe-person-item:has(>button.unassigned)>.oe-unassign{background:#ffedcc;border-color:#dc922b;color:#78430e}
.oe-people .oe-person-item>button.unassigned:hover{background:#ffe1a8}
.oe-node-names{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3px 5px;margin-top:7px}.oe-node .oe-node-names span{font-size:11px;color:#326aa1;background:#edf5ff;border-radius:4px;padding:2px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:15px}.oe-node .oe-node-names span.unassigned{color:#97551a;background:#fff0d6}.oe-node .oe-more-names{font-size:10px;margin-top:3px;color:#7d8fa1}.oe-people>div button.unassigned{border-color:#e8b567;background:#fff6e8;color:#97551a}.oe-people em{font-size:10px;font-style:normal;font-weight:normal;margin-left:4px}.oe-node-names small{grid-column:1/-1}
.oe-node-actions{position:absolute;bottom:8px;left:8px;right:8px;display:flex;justify-content:flex-end;gap:5px;}.oe-node .oe-node-actions button{position:static;font-size:11px;padding:4px 6px;}.oe-node-quick-actions{position:absolute;z-index:2;left:50%;bottom:-19px;display:flex;gap:6px;transform:translateX(-50%);}.oe-node .oe-node-quick-actions button{position:static;display:grid;place-items:center;width:28px;height:28px;padding:0;border:1px solid;border-radius:50%;line-height:1;box-shadow:0 2px 5px #284a6b26;}.oe-node .oe-node-quick-actions .el-icon{font-size:15px;}.oe-node .oe-node-quick-actions .oe-node-add{border-color:#58b98c;background:#e9f9f0;color:#12834e;}.oe-node .oe-node-quick-actions .oe-node-add:hover{background:#c9f0dc;}.oe-node .oe-node-quick-actions .oe-node-delete{border-color:#ef9b9b;background:#fff0f0;color:#d04b4b;}.oe-node .oe-node-quick-actions .oe-node-delete:hover{background:#ffe0e0;}.oe-node button:focus-visible{outline:2px solid #2473b8;outline-offset:2px;}
.oe-branch-head{display:flex;align-items:center;justify-content:space-between;gap:12px;}.oe-branch-title{margin:0;color:#203f5c;}.oe-branch-head p{font-size:12px;color:#6d819a;}h4 small{font-weight:normal;color:#7890a6;font-size:12px;margin-left:8px;}.oe-branch-children{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;max-height:260px;overflow:auto;}.oe-branch-item{border:1px solid #cadcec;background:#f6faff;border-radius:7px;padding:12px;text-align:left;cursor:pointer;min-width:0;}.oe-branch-item strong{display:block;overflow-wrap:anywhere;color:#234c71;}.oe-branch-item small{display:block;color:#6d819a;margin-top:6px;}.oe-branch-people{max-height:280px;overflow:auto;}.oe-branch-people article{display:flex;gap:14px;border-bottom:1px solid #e3ebf3;padding:10px 4px;}.oe-branch-people b{min-width:70px;color:#244762;}.oe-branch-people span{font-size:12px;color:#6d819a;}.oe-branch-children>p,.oe-branch-people>p{color:#7890a6;font-size:13px;}
.org-editor{border:1px solid #d5e1ef;border-radius:12px;overflow:hidden;background:#f7faff;}.oe-toolbar,.oe-properties,.oe-people header{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:12px;background:white;}.oe-toolbar .el-select{width:300px;}.oe-properties .el-select{width:220px;}.oe-toolbar span,.oe-help,.oe-properties span,.oe-people p{font-size:12px;color:#6d819a;}.oe-help{padding:0 14px;}.oe-properties{border-top:1px solid #d5e1ef;min-height:50px;}.oe-stage{height:560px;position:relative;overflow:hidden;touch-action:none;cursor:grab;background-color:#eef4fb;background-image:radial-gradient(#b6c9df 1px,transparent 1px);background-size:20px 20px;}.oe-world{position:absolute;transform-origin:0 0;}.oe-edges{position:absolute;width:1px;height:1px;overflow:visible;pointer-events:none;}.oe-edges path{stroke:#7e9fbe;stroke-width:2;fill:none;}.oe-node{position:absolute;width:230px;height:105px;box-sizing:border-box;background:white;border:1px solid #bbcee2;border-top:4px solid #347fc8;border-radius:9px;padding:10px 12px;user-select:none;box-shadow:0 4px 12px #284a6b12;cursor:grab;}.oe-node.selected{outline:3px solid #339be655;}.oe-node.department{border-top-color:#d79a38;}.oe-node small,.oe-node strong,.oe-node span{display:block;}.oe-node small{color:#7890a6;font-size:11px;}.oe-node strong{font-size:14px;color:#203f5c;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:5px 0;}.oe-node span{font-size:12px;color:#7890a6;}.oe-node button{position:absolute;right:8px;bottom:8px;border:0;color:#2473b8;background:#edf5fc;border-radius:4px;cursor:pointer;padding:3px 6px;}.oe-people{padding:12px;border-top:1px solid #d5e1ef;}.oe-people .el-input{width:260px;}.oe-people>div{display:flex;gap:8px;flex-wrap:wrap;max-height:200px;overflow:auto;}.oe-people>div button{border:1px solid #c9d9e8;border-radius:6px;background:white;padding:8px;text-align:left;cursor:grab;color:#244762;}.oe-people small{display:block;font-size:11px;margin-top:5px;color:#6d819a;}@media(max-width:600px){.oe-stage{height:450px;}.oe-toolbar .el-select{width:100%;}}
/* Quiet canvas with a single contextual action dock for the selected node. */
.oe-stage{background-color:#f7f9fc;background-image:radial-gradient(#ccd7e5 .8px,transparent .8px);background-size:24px 24px;}
.oe-edges path{stroke:#a4b8ce;stroke-width:1.6;}
.oe-node{border-color:#dbe4ee;border-top-width:3px;border-radius:12px;box-shadow:0 3px 12px #233b5510;transition:border-color .15s,box-shadow .15s;}
.oe-node:hover{border-color:#9cbade;box-shadow:0 6px 20px #233b5518;}
.oe-node.selected{z-index:3;outline:3px solid #3b82f622;border-color:#4b8ddd;box-shadow:0 8px 24px #2864ac24;}
.oe-node strong{font-weight:600;color:#243b53;}
.oe-node .oe-node-names span{background:#f1f5fa;color:#506b87;border-radius:5px;}
.oe-node .oe-node-actions button{background:#f5f8fc;color:#587796;border-radius:6px;}
.oe-node-quick-actions{bottom:-26px;padding:4px;gap:4px;border:1px solid #e0e7ef;border-radius:12px;background:#fff;box-shadow:0 4px 14px #213c5b24;}
.oe-node .oe-node-quick-actions button{width:32px;height:32px;border:0;border-radius:8px;box-shadow:none;}
.oe-node .oe-node-quick-actions .oe-node-add{background:#edf5ff;color:#2468c4;}
.oe-node .oe-node-quick-actions .oe-node-add:hover{background:#dceaff;}
.oe-node .oe-node-quick-actions .oe-node-delete{background:#fff;color:#bf5962;}
.oe-node .oe-node-quick-actions .oe-node-delete:hover{background:#fff0f1;color:#c53948;}
.oe-node .oe-node-quick-actions .el-icon{font-size:17px;}
.oe-properties{background:#fbfcfe;border-color:#e5ebf3;}
.oe-help{color:#8091a5;}

.oe-toolbar{border-bottom:1px solid #e6edf5;}
.oe-toolbar :deep(.el-button){border-radius:8px;margin-left:0;}
.oe-node strong{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:18px;margin:4px 0;max-height:36px;}
.oe-node .oe-more-names{display:none;}
.oe-node-names{margin-top:4px;}
.oe-node-actions{bottom:6px;}
.oe-node{padding:8px 12px;}
</style>
