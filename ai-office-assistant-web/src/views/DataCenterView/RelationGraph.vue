<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getDatacenterDbFlowTables, type DcFlowInstance, type DcFlowSnapshot, type DcFlowTables } from '../../services/personalWorkApi'
import { DB_CATEGORIES, DB_CATEGORY_ORDER, dbCategory } from './dbCategories'

const props = defineProps<{ snap: DcFlowSnapshot | null; assistant: string | null; instance: string | null }>()
const emit = defineEmits<{ 'update:assistant': [id: string | null]; 'update:instance': [id: string | null]; 'pick-instance': [inst: DcFlowInstance] }>()

const W = 1180
const A_H = 38, A_PITCH = 50, A_MAX_COLS = 8
const I_H = 48, I_PITCH = 60, I_MAX_COLS = 6
const GAP = 118

function grid(count: number, maxCols: number, height: number, pitch: number, top: number, gapX = 10) {
  const cols = Math.max(1, Math.min(count, maxCols))
  const width = (W - (cols - 1) * gapX) / cols
  const rows = Math.ceil(count / cols)
  const boxes: { x: number; y: number }[] = []
  for (let i = 0; i < count; i += 1) {
    const row = Math.floor(i / cols)
    const inRow = row === rows - 1 ? count - row * cols : cols
    const offset = (W - (inRow * width + (inRow - 1) * gapX)) / 2
    boxes.push({ x: offset + (i % cols) * (width + gapX), y: top + row * pitch })
  }
  return { boxes, width, height, rows, bottom: top + (rows - 1) * pitch + height }
}

const layout = computed(() => {
  if (!props.snap) return null
  const assistants = props.snap.assistants
  const instances = props.snap.instances
  const a = grid(assistants.length, A_MAX_COLS, A_H, A_PITCH, 8)
  const i = grid(instances.length, I_MAX_COLS, I_H, I_PITCH, a.bottom + GAP)
  const aPos = new Map(assistants.map((item, idx) => [item.id, a.boxes[idx]]))
  const iPos = new Map(instances.map((item, idx) => [item.id, i.boxes[idx]]))
  const byId = new Map(instances.map(item => [item.id, item]))
  const edges = assistants.flatMap(item => item.instances.filter(id => byId.has(id)).map(id => {
    const inst = byId.get(id)!
    const from = aPos.get(item.id)!, to = iPos.get(id)!
    const x1 = from.x + a.width / 2, y1 = from.y + A_H, x2 = to.x + i.width / 2, y2 = to.y
    const live = inst.status === 'up' && inst.clients.some(c => item.client_hints.some(h => c.label.includes(h)))
    return { key: `${item.id}-${id}`, assistant: item.id, instance: id,
      d: `M ${x1} ${y1} C ${x1} ${y1 + (y2 - y1) * .55}, ${x2} ${y2 - (y2 - y1) * .45}, ${x2} ${y2}`,
      state: inst.status !== 'up' ? 'down' : item.mirror_instances.includes(id) ? 'mirror' : live ? 'live' : 'idle' }
  }))
  return { assistants, instances, a, i, aPos, iPos, edges, height: i.bottom + 10 }
})

const assistantInfo = computed(() => props.snap?.assistants.find(item => item.id === props.assistant) || null)
const instanceInfo = computed(() => props.snap?.instances.find(item => item.id === props.instance) || null)
const relatedInstances = computed(() => new Set(assistantInfo.value?.instances || []))
const relatedAssistants = computed(() => new Set(props.snap?.assistants.filter(item => item.instances.includes(props.instance || '')).map(item => item.id) || []))
const focusEdge = (edge: { assistant: string; instance: string }) =>
  props.assistant ? edge.assistant === props.assistant && (!props.instance || edge.instance === props.instance)
    : props.instance ? edge.instance === props.instance : false
const hasFocus = computed(() => !!(props.assistant || props.instance))
const instanceLabel = (id: string) => props.snap?.instances.find(item => item.id === id)?.label || id
const roleOf = (assistantId: string, instanceId: string) => {
  const item = props.snap?.assistants.find(entry => entry.id === assistantId)
  const inst = props.snap?.instances.find(entry => entry.id === instanceId)
  if (!inst || inst.status !== 'up') return { key: 'down', label: '不可达' }
  return item?.mirror_instances.includes(instanceId) ? { key: 'mirror', label: '定时镜像 / 索引' } : { key: 'live', label: '业务存储' }
}

function pickAssistant(id: string) {
  const next = props.assistant === id ? null : id
  emit('update:assistant', next)
  emit('update:instance', null)
}
function pickInstance(inst: DcFlowInstance) {
  if (props.assistant && !relatedInstances.value.has(inst.id)) {
    emit('update:assistant', null)
  }
  emit('update:instance', props.instance === inst.id && !props.assistant ? null : inst.id)
  emit('pick-instance', inst)
}

const tables = ref<DcFlowTables | null>(null)
const tablesLoading = ref(false)
let tablesRequest = 0
watch(() => [props.assistant, props.instance], async ([assistant, instance]) => {
  const requestId = ++tablesRequest
  tables.value = null
  tablesLoading.value = false
  if (!assistant || !instance || !relatedInstances.value.has(instance)) return
  tablesLoading.value = true
  try {
    const result = await getDatacenterDbFlowTables(assistant, instance)
    if (requestId === tablesRequest) tables.value = result
  } catch (e) {
    if (requestId === tablesRequest) ElMessage.error(e instanceof Error ? e.message : '读取相关数据表失败')
  } finally {
    if (requestId === tablesRequest) tablesLoading.value = false
  }
}, { immediate: true })

/** 节点内显示的短名：去掉括号说明与“ · ”后缀，超长再截断；完整名在悬停提示里。 */
function short(label: string, max: number) {
  const base = label.replace(/\s*[（(].*$/, '').replace(/\s*·.*$/, '').trim() || label
  return base.length > max ? base.slice(0, max - 1) + '…' : base
}

function fmtBytes(n?: number | null) {
  if (!n && n !== 0) return ''
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round((n || 0) / 1024)} KB`
}
</script>

<template>
  <div class="rg" v-if="layout">
    <p class="rg-hint">
      <template v-if="assistantInfo"><b>{{ assistantInfo.label }}</b> 连接 {{ relatedInstances.size }} 个数据库，已高亮；点击高亮的数据库查看相关数据表，再次点击助手取消。</template>
      <template v-else-if="instanceInfo"><b>{{ instanceInfo.label }}</b> 被 {{ relatedAssistants.size }} 个助手 / 系统使用，已高亮；点击上方助手可查看它在此库的数据表。</template>
      <template v-else>上排是助手与支撑系统，下排是数据库实例。点击助手查看它用到的数据库；点击数据库反查有哪些助手在用。</template>
    </p>
    <svg :viewBox="`0 0 ${W} ${layout.height}`" class="rg-svg" role="img" aria-label="助手与数据库关联图">
      <path v-for="e in layout.edges" :key="e.key" class="rg-edge" :class="[e.state, { dim: hasFocus && !focusEdge(e), focus: focusEdge(e) }]" :d="e.d" />
      <g v-for="a in layout.assistants" :key="a.id" class="rg-anode" :data-graph-assistant="a.id"
         :class="{ dim: hasFocus && a.id !== assistant && !(instance && relatedAssistants.has(a.id)), sel: a.id === assistant, related: instance && !assistant && relatedAssistants.has(a.id), system: a.node_type !== 'assistant' }"
         @click="pickAssistant(a.id)">
        <title>{{ a.label }}：{{ a.storage_note }}</title>
        <rect :x="layout.aPos.get(a.id)!.x" :y="layout.aPos.get(a.id)!.y" :width="layout.a.width" :height="A_H" rx="9" />
        <text :x="layout.aPos.get(a.id)!.x + layout.a.width / 2" :y="layout.aPos.get(a.id)!.y + A_H / 2 + 4.5" text-anchor="middle">{{ short(a.label, 9) }}</text>
      </g>
      <g v-for="inst in layout.instances" :key="inst.id" class="rg-inode" :data-graph-instance="inst.id"
         :class="{ dim: hasFocus && !(assistant ? relatedInstances.has(inst.id) : inst.id === instance), sel: inst.id === instance, related: assistant && relatedInstances.has(inst.id) }"
         @click="pickInstance(inst)">
        <title>{{ inst.label }} · {{ dbCategory(inst.category).label }} · {{ inst.status === 'up' ? '在线' : '不可达' }}</title>
        <rect :x="layout.iPos.get(inst.id)!.x" :y="layout.iPos.get(inst.id)!.y" :width="layout.i.width" :height="I_H" rx="9" class="rg-ibox" :class="inst.status" />
        <rect :x="layout.iPos.get(inst.id)!.x" :y="layout.iPos.get(inst.id)!.y + 6" width="4" :height="I_H - 12" rx="2" :fill="dbCategory(inst.category).color" />
        <circle :cx="layout.iPos.get(inst.id)!.x + layout.i.width - 12" :cy="layout.iPos.get(inst.id)!.y + 12" r="4" :class="`rg-dot ${inst.status}`" />
        <text :x="layout.iPos.get(inst.id)!.x + 14" :y="layout.iPos.get(inst.id)!.y + 20" class="rg-ititle">{{ short(inst.label, 13) }}</text>
        <text :x="layout.iPos.get(inst.id)!.x + 14" :y="layout.iPos.get(inst.id)!.y + 37" class="rg-imeta" :fill="dbCategory(inst.category).color">{{ dbCategory(inst.category).label }}<tspan fill="#8c9ab3"> · {{ inst.kind }}</tspan></text>
      </g>
    </svg>
    <p class="rg-legend">
      <i class="l-live" /> 检测到连接 <i class="l-idle" /> 已配置关联 <i class="l-mirror" /> 定时镜像 / 索引 <i class="l-down" /> 不可达
      <span v-for="key in DB_CATEGORY_ORDER" :key="key" class="rg-cat"><i :style="{ background: DB_CATEGORIES[key].color }" />{{ DB_CATEGORIES[key].label }}</span>
    </p>

    <section v-if="assistantInfo" class="rg-panel" data-testid="rg-panel">
      <h4>「{{ assistantInfo.label }}」关联的数据库<small>{{ assistantInfo.storage_note }}</small></h4>
      <div class="rg-chips">
        <button v-for="id in assistantInfo.instances" :key="id" type="button" :class="{ active: instance === id, [roleOf(assistantInfo.id, id).key]: true }"
                @click="pickInstance(snap!.instances.find(item => item.id === id)!)">
          {{ instanceLabel(id) }}<small>{{ roleOf(assistantInfo.id, id).label }}</small>
        </button>
        <span v-if="!assistantInfo.instances.length" class="rg-muted">尚未接入监测</span>
        <span v-if="assistantInfo.unregistered_instances.length" class="rg-muted">未注册：{{ assistantInfo.unregistered_instances.join('、') }}</span>
      </div>
      <div v-if="instance && relatedInstances.has(instance)" class="rg-tables" v-loading="tablesLoading">
        <template v-if="tables">
          <h5>在 {{ tables.instance }} 的相关数据表（{{ tables.objects.length }} 个）<small>{{ tables.note }}</small></h5>
          <div class="rg-tablist">
            <div v-for="o in tables.objects" :key="o.name" class="rg-tab-item">
              <b>{{ o.name }}</b>
              <span v-if="o.rows !== null && o.rows !== undefined">{{ o.rows.toLocaleString() }} {{ tables.rows_label || '行' }}</span>
              <span v-if="o.size">{{ fmtBytes(o.size) }}</span>
              <u v-if="o.kind_label && o.kind_label !== '表'">{{ o.kind_label }}</u>
            </div>
          </div>
          <p v-if="!tables.objects.length" class="rg-muted">没有匹配的数据对象。</p>
        </template>
      </div>
    </section>
    <section v-else-if="instanceInfo" class="rg-panel" data-testid="rg-panel">
      <h4>使用「{{ instanceInfo.label }}」的助手 / 系统<small>{{ dbCategory(instanceInfo.category).label }} · {{ instanceInfo.status === 'up' ? '在线' : '不可达' }}</small></h4>
      <div class="rg-chips">
        <button v-for="a in snap!.assistants.filter(item => item.instances.includes(instanceInfo!.id))" :key="a.id" type="button" :class="roleOf(a.id, instanceInfo.id).key" @click="pickAssistant(a.id)">
          {{ a.label }}<small>{{ roleOf(a.id, instanceInfo.id).label }}</small>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.rg { display: flex; flex-direction: column; gap: 8px; }
.rg-hint { font-size: 12.5px; color: #4c6a99; background: #edf4ff; border-radius: 8px; padding: 7px 12px; b { color: #0b2458; } }
.rg-svg { width: 100%; height: auto; display: block; }
.rg-edge { fill: none; stroke-width: 1.4; opacity: .55; transition: opacity .2s, stroke-width .2s;
  &.idle { stroke: #c9d6ea; } &.mirror { stroke: #a98bca; stroke-dasharray: 3 5; } &.down { stroke: #e79a9a; stroke-dasharray: 4 4; }
  &.live { stroke: #3a7bd5; stroke-width: 2; stroke-dasharray: 7 5; animation: rg-dash 1.1s linear infinite; }
  &.dim { opacity: .07; }
  &.focus { opacity: 1; stroke-width: 2.8; &.idle { stroke: #5e8fd6; } } }
@keyframes rg-dash { to { stroke-dashoffset: -12; } }
.rg-anode { cursor: pointer; transition: opacity .2s;
  rect { fill: #f0f5ff; stroke: #c9dbf7; } text { font-size: 12.5px; font-weight: 600; fill: #15499c; }
  &.system rect { fill: #f5f3fb; stroke: #d7cdea; } &.system text { fill: #5f4b8b; }
  &.dim { opacity: .28; }
  &.related rect { stroke: #3a7bd5; stroke-width: 2; }
  &.sel rect { fill: #15499c; stroke: #15499c; } &.sel text { fill: #fff; } }
.rg-inode { cursor: pointer; transition: opacity .2s;
  &.dim { opacity: .22; }
  &.related .rg-ibox { stroke: #3a7bd5; stroke-width: 2; }
  &.sel .rg-ibox { stroke: #15499c; stroke-width: 2.4; fill: #eef4ff; } }
.rg-ibox { fill: #f8fafd; stroke: #dbe7fb; &.down, &.auth-error { fill: #fdf0f0; stroke: #e7b3b3; } }
.rg-dot { &.up { fill: #22b573; } &.down, &.auth-error { fill: #e15656; } }
.rg-ititle { font-size: 12.5px; font-weight: 600; fill: #14213d; }
.rg-imeta { font-size: 10.5px; font-weight: 600; }
.rg-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; font-size: 12px; color: #64748b;
  > i { width: 18px; height: 3px; border-radius: 2px; display: inline-block; &.l-live { background: #3a7bd5; } &.l-idle { background: #c9d6ea; } &.l-mirror { background: #a98bca; } &.l-down { background: #e79a9a; } }
  .rg-cat { margin-left: 6px; &:first-of-type { margin-left: auto; } i { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; } } }
.rg-panel { border-top: 1px dashed #e3ebf7; padding-top: 10px;
  h4 { font-size: 14px; color: #0b2458; margin-bottom: 8px; small { display: block; font-weight: 400; font-size: 12px; color: #8c9ab3; margin-top: 2px; } }
  h5 { font-size: 13px; color: #0b2458; margin: 10px 0 6px; small { font-weight: 400; font-size: 11.5px; color: #8c9ab3; margin-left: 8px; } } }
.rg-chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  button { cursor: pointer; border: 1px solid #dbe7fb; background: #f6f9fe; border-radius: 9px; padding: 6px 12px; font-size: 12.5px; color: #14213d; text-align: left; border-left-width: 4px;
    small { display: block; font-size: 11px; color: #64748b; margin-top: 2px; }
    &.live { border-left-color: #3a7bd5; } &.mirror { border-left-color: #a98bca; } &.down { border-left-color: #e79a9a; }
    &:hover { border-color: #3a7bd5; background: #eef4ff; }
    &.active { background: #15499c; color: #fff; border-color: #15499c; small { color: #cfe0fa; } } } }
.rg-tablist { display: flex; flex-wrap: wrap; gap: 8px; max-height: 260px; overflow: auto; }
.rg-tab-item { border: 1px solid #dbe7fb; background: #f6f9fe; border-radius: 8px; padding: 5px 10px; font-size: 12.5px;
  b { color: #14213d; font-weight: 600; } span { color: #64748b; margin-left: 8px; font-size: 11.5px; } u { text-decoration: none; margin-left: 8px; font-size: 11px; color: #8a6bd1; } }
.rg-tables { min-height: 24px; }
.rg-muted { font-size: 12px; color: #8c9ab3; }
</style>
