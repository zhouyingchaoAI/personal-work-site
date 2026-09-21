<script setup lang="ts">
/**
 * 交互式关系网络图谱：自研轻量力导向布局，零第三方依赖。
 * 支持缩放 / 平移 / 节点拖拽 / 悬停高亮邻居 / 点击选中 / 引荐路径高亮。
 */
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch, useId } from 'vue'
import RadialOrganization from './RadialOrganization.vue'
import type { CrmGraphNode, CrmGraphEdge } from '../../services/personalWorkApi'

const props = defineProps<{
  organizationGraph?: {nodes: CrmGraphNode[]; edges: CrmGraphEdge[]}
  holographic?: boolean
  nodes: CrmGraphNode[]
  edges: CrmGraphEdge[]
  highlightPath: string[]
  typeColor: Record<string, string>
  hiddenTypes: string[]
  onlyGaps: boolean
}>()
const organizationMode = ref(Boolean(props.organizationGraph))
const markerId = 'org-arrow-' + useId().replace(/[^a-zA-Z0-9_-]/g,'')
const activeNodes = computed(() => props.organizationGraph?.nodes || props.nodes)
const activeEdges = computed(() => props.organizationGraph?.edges || props.edges)
const emit = defineEmits<{ (e: 'select', id: string, kind: string): void }>()

interface Pt { x: number; y: number; vx: number; vy: number; fixed: boolean }
const WIDTH = 640
const HEIGHT = 470
const pos = new Map<string, Pt>()          // 非响应式坐标，靠 frame 触发重绘
const frame = ref(0)
const view = reactive({ scale: 1, tx: 0, ty: 0 })
const hoverId = ref('')
const selectedId = ref('')
const draggingId = ref('')
let autoFit = true
let alpha = 0
let raf = 0

// 参与力导向的节点：我方 + 人物 + 单位；单位作为聚类锚
const simNodes = computed(() => activeNodes.value.filter((n) => n.kind !== 'unit' ? true : true))
const edgeIndex = computed(() => {
  // self→person 边 + person→unit 归属边
  const list: { a: string; b: string; strength: number; strong: boolean; weak?: boolean; relationKind?: string; label?: string }[] = activeEdges.value.map((e) => {
    const strength = Math.max(0, Math.min(5, Number(e.strength) || 0))
    return { a: e.source, b: e.target, strength, relationKind: e.relation_kind, strong: strength >= 4, weak: strength < 2, label: e.our_member_label }
  })
  for (const n of activeNodes.value) if (!organizationMode.value && n.kind === 'person' && n.unit_id) list.push({ a: n.id, b: n.unit_id, strength: 0, strong: false })
  return list
})
const edgeMeta = computed(() => {
  const m = new Map<string, CrmGraphEdge>()
  for (const e of activeEdges.value) m.set(e.target, e)
  return m
})
const pathSet = computed(() => new Set(props.highlightPath))
const pathEdgeSet = computed(() => {
  const s = new Set<string>()
  for (let i = 0; i < props.highlightPath.length - 1; i++) s.add([props.highlightPath[i], props.highlightPath[i + 1]].sort().join('__'))
  return s
})

function visible(n: CrmGraphNode) {
  if (n.kind === 'self') return true
  if (props.hiddenTypes.includes(n.type)) return false
  if (!organizationMode.value && props.onlyGaps && n.kind === 'person') {
    const e = edgeMeta.value.get(n.id)
    return !e || e.strength <= 1 || e.decay_state === 'alarm'
  }
  return true
}
const visibleNodes = computed(() => activeNodes.value.filter(visible))
const visibleIds = computed(() => new Set(visibleNodes.value.map((n) => n.id)))
const visibleEdges = computed(() => edgeIndex.value.filter((e) => visibleIds.value.has(e.a) && visibleIds.value.has(e.b)))

// 邻居索引，用于悬停高亮
const neighbors = computed(() => {
  const m = new Map<string, Set<string>>()
  for (const e of edgeIndex.value) {
    if (!m.has(e.a)) m.set(e.a, new Set()); m.get(e.a)!.add(e.b)
    if (!m.has(e.b)) m.set(e.b, new Set()); m.get(e.b)!.add(e.a)
  }
  return m
})
const hoverDetail = computed(() => {
  const node = activeNodes.value.find(item => item.id === hoverId.value)
  if (!node) return null
  const relation = edgeMeta.value.get(node.id)
  return {
    node,
    line1: node.kind === 'person' ? (node.type || '客户联系人') : node.kind === 'self' ? '我方组织' : (node.type || '客户单位'),
    line2: relation ? `关系 L${relation.strength ?? 0} · ${relation.our_member_label || '未指派'}` : '暂无我方对接关系',
    line3: relation?.days_since_touch != null ? `最近互动 ${relation.days_since_touch} 天前` : '最近互动暂无记录',
  }
})

function ensurePositions() {
  const ids = new Set(activeNodes.value.map((n) => n.id))
  for (const id of pos.keys()) if (!ids.has(id)) pos.delete(id)
  let i = 0
  for (const n of activeNodes.value) {
    if (pos.has(n.id)) continue
    if (n.kind === 'self') { pos.set(n.id, { x: 0, y: 0, vx: 0, vy: 0, fixed: true }); continue }
    const ang = (i++ / Math.max(1, activeNodes.value.length)) * Math.PI * 2
    const r = n.kind === 'unit' ? 60 : 150
    pos.set(n.id, { x: Math.cos(ang) * r, y: Math.sin(ang) * r, vx: 0, vy: 0, fixed: false })
  }
}

function tick() {
  const nodes = simNodes.value
  const REPULSE = 4200, SPRING = 0.02, CENTER = 0.008, DAMP = 0.85
  // 斥力
  for (let i = 0; i < nodes.length; i++) {
    const a = pos.get(nodes[i].id)!; if (!a) continue
    for (let j = i + 1; j < nodes.length; j++) {
      const b = pos.get(nodes[j].id)!; if (!b) continue
      let dx = a.x - b.x, dy = a.y - b.y
      let d2 = dx * dx + dy * dy || 0.01
      const f = REPULSE / d2
      const d = Math.sqrt(d2)
      const fx = (dx / d) * f, fy = (dy / d) * f
      if (!a.fixed) { a.vx += fx; a.vy += fy }
      if (!b.fixed) { b.vx -= fx; b.vy -= fy }
    }
  }
  // 弹簧（边）
  for (const e of edgeIndex.value) {
    const a = pos.get(e.a), b = pos.get(e.b); if (!a || !b) continue
    const L = e.strong ? 70 : 120
    const dx = b.x - a.x, dy = b.y - a.y
    const d = Math.sqrt(dx * dx + dy * dy) || 0.01
    const f = (d - L) * SPRING
    const fx = (dx / d) * f, fy = (dy / d) * f
    if (!a.fixed) { a.vx += fx; a.vy += fy }
    if (!b.fixed) { b.vx -= fx; b.vy -= fy }
  }
  // 向心 + 积分
  for (const n of nodes) {
    const p = pos.get(n.id)!; if (!p || p.fixed || n.id === draggingId.value) continue
    p.vx -= p.x * CENTER; p.vy -= p.y * CENTER
    p.vx *= DAMP; p.vy *= DAMP
    p.x += p.vx * alpha; p.y += p.vy * alpha
  }
}

function loop() {
  if (alpha > 0.02) {
    tick(); tick()
    if (autoFit) fitView()
    alpha *= 0.985
    frame.value++
    raf = requestAnimationFrame(loop)
  } else { raf = 0 }
}
function reheat(a = 1) { if (organizationMode.value) return; alpha = a; if (!raf) raf = requestAnimationFrame(loop) }
watch(organizationMode, mode => { if (mode) { cancelAnimationFrame(raf); raf = 0 } else { autoFit = true; reheat() } })

watch(() => activeNodes.value, () => { pos.clear(); ensurePositions(); autoFit = true; reheat(1) }, { immediate: true, deep: false })
onBeforeUnmount(() => raf && cancelAnimationFrame(raf))

// 世界坐标 → 屏幕
const screen = (id: string) => {
  const p = pos.get(id); frame.value // 依赖 frame 触发重算
  if (!p) return { x: WIDTH / 2, y: HEIGHT / 2 }
  return { x: WIDTH / 2 + view.tx + (p.x * view.scale), y: HEIGHT / 2 + view.ty + (p.y * view.scale) }
}
function nodeRadius(n: CrmGraphNode) {
  if (n.kind === 'self') return 22
  if (n.kind === 'unit') return 8
  return 8 + Math.min(16, (n.influence || 0) / 6)
}
function nodeColor(n: CrmGraphNode) {
  if (n.kind === 'self') return '#f5c242'
  if (n.kind === 'staff') return '#f5c242'
  if (n.kind === 'group') return '#345f81'
  if (n.kind === 'unit') return '#4a5f8c'
  return props.typeColor[n.type] || '#8aa0c8'
}
function edgeColor(e: { a: string; b: string; strength: number; strong: boolean; relationKind?: string }) {
  if (organizationMode.value && e.relationKind === 'belongs') return '#709bc1'
  if (organizationMode.value && e.relationKind === 'reports') return '#b49aff'
  if (organizationMode.value && e.relationKind === 'contact') return '#23e0d0'
  const key = [e.a, e.b].sort().join('__')
  if (pathEdgeSet.value.has(key)) return '#f5c242'
  const meta = e.a === 'self' ? edgeMeta.value.get(e.b) : e.b === 'self' ? edgeMeta.value.get(e.a) : null
  if (meta) return meta.strength >= 4 ? '#f5c242' : meta.strength >= 2 ? '#23e0d0' : '#3a5a8c'
  return '#2a3a5c'
}
function edgeWidth(e: { strength: number; strong: boolean; relationKind?: string }) {
  if (organizationMode.value) return e.relationKind === 'reports' ? 1.7 : 1.15
  return [0.7, 1, 1.35, 1.75, 2.2, 2.7][e.strength] || 0.7
}
function edgeOpacity(e: { a: string; b: string; strength: number; relationKind?: string }) {
  if (dimmed(e.a) || dimmed(e.b)) return 0.12
  if (organizationMode.value) return e.relationKind === 'belongs' ? 0.48 : 0.72
  return [0.18, 0.3, 0.45, 0.65, 0.82, 1][e.strength] || 0.18
}
function dimmed(id: string) {
  if (props.highlightPath.length) return !pathSet.value.has(id)
  const focusId = selectedId.value || hoverId.value
  if (!focusId) return false
  return id !== focusId && !(neighbors.value.get(focusId)?.has(id))
}

// ---- 交互：缩放 / 平移 / 拖拽 ----
const svgRef = shallowRef<SVGSVGElement | null>(null)
let panning = false, lastX = 0, lastY = 0
function onWheel(ev: WheelEvent) {
  autoFit = false
  ev.preventDefault()
  const factor = ev.deltaY < 0 ? 1.12 : 0.89
  view.scale = Math.min(3, Math.max(0.35, view.scale * factor))
}
function toWorld(ev: MouseEvent) {
  const rect = svgRef.value!.getBoundingClientRect()
  const sx = (ev.clientX - rect.left) * (WIDTH / rect.width)
  const sy = (ev.clientY - rect.top) * (HEIGHT / rect.height)
  return { x: (sx - WIDTH / 2 - view.tx) / view.scale, y: (sy - HEIGHT / 2 - view.ty) / view.scale }
}
function onBgDown(ev: MouseEvent) { autoFit = false; panning = true; lastX = ev.clientX; lastY = ev.clientY }
function onMove(ev: MouseEvent) {
  if (draggingId.value) {
    const w = toWorld(ev); const p = pos.get(draggingId.value)
    if (p) { p.x = w.x; p.y = w.y; p.vx = 0; p.vy = 0; frame.value++ }
    reheat(0.6)
  } else if (panning) {
    view.tx += ev.clientX - lastX; view.ty += ev.clientY - lastY
    lastX = ev.clientX; lastY = ev.clientY
  }
}
function onUp() { panning = false; draggingId.value = '' }
function onNodeDown(ev: MouseEvent, id: string, fixed: boolean) { if (fixed) return; autoFit = false; ev.stopPropagation(); draggingId.value = id }
function fitView() {
  const points = [...pos.values()]
  if (!points.length) return
  const minX = Math.min(...points.map(p => p.x)), maxX = Math.max(...points.map(p => p.x))
  const minY = Math.min(...points.map(p => p.y)), maxY = Math.max(...points.map(p => p.y))
  view.scale = Math.min(1, (WIDTH - 160) / Math.max(1, maxX - minX), (HEIGHT - 100) / Math.max(1, maxY - minY))
  view.tx = -(minX + maxX) / 2 * view.scale
  view.ty = -(minY + maxY) / 2 * view.scale
}
function zoom(factor: number) { autoFit = false; view.scale = Math.min(3, Math.max(0.1, view.scale * factor)) }
function resetView() { autoFit = true; view.scale = 1; view.tx = 0; view.ty = 0; if (organizationMode.value) fitView() }
function relayout() { autoFit = true; for (const p of pos.values()) if (!p.fixed) { p.x *= 0.3; p.y *= 0.3 } ; reheat(1) }
function restoreGraph() { selectedId.value = ''; hoverId.value = ''; resetView() }
function onNodeClick(n: CrmGraphNode) {
  selectedId.value = selectedId.value === n.id ? '' : n.id
  if (n.kind !== 'group') emit('select', n.id, n.kind)
}
defineExpose({ resetView, relayout })
</script>

<template>
  <div class="rg-wrap">
    <div class="rg-toolbar">
      <el-button-group v-if="organizationGraph" aria-label="图谱视图切换">
        <el-button size="small" :type="organizationMode ? 'primary' : 'default'" :aria-pressed="organizationMode" @click="organizationMode = true; resetView()">分区层级</el-button>
        <el-button size="small" :disabled="activeNodes.length > 350" :title="activeNodes.length > 350 ? '节点较多，请先筛选区域、单位类型或搜索企业；层级视图仍展示全部数据' : '查看客户与我方对接关系'" :type="!organizationMode ? 'primary' : 'default'" :aria-pressed="!organizationMode" @click="organizationMode = false; resetView()">对接视图</el-button>
      </el-button-group>
      <span v-if="organizationGraph && activeNodes.length > 350" class="rg-tip">{{ activeNodes.length }} 个节点：使用完整层级视图；筛选至 350 个节点以内可切换对接视图。</span>
      <el-button-group v-if="!organizationMode">
        <el-button size="small" @click="zoom(1.15)">＋</el-button>
        <el-button size="small" @click="zoom(0.85)">－</el-button>
      </el-button-group>
      <el-button v-if="!organizationMode" size="small" @click="resetView">复位</el-button>
      <el-button v-if="!organizationMode" size="small" @click="relayout">重新布局</el-button>
      <el-button v-if="selectedId" size="small" @click="restoreGraph">恢复全图</el-button>
      <span v-if="!organizationMode" class="rg-tip">滚轮缩放 · 拖背景平移 · 拖节点移动 · 悬停看邻居 · 点击看详情</span>
    </div>
    <RadialOrganization v-if="organizationMode && organizationGraph" :graph="organizationGraph" @select="(id,kind)=>emit('select',id,kind)" />
    <svg v-else ref="svgRef" :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="rg-svg"
         @wheel="onWheel" @mousedown="onBgDown" @mousemove="onMove" @mouseup="onUp" @mouseleave="onUp">
      <defs><marker :id="markerId" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#b49aff" /></marker></defs>
      <g>
        <line v-for="(e, i) in visibleEdges" :key="'e' + i"
              :x1="screen(e.a).x" :y1="screen(e.a).y" :x2="screen(e.b).x" :y2="screen(e.b).y"
              :marker-end="organizationMode && e.relationKind === 'reports' ? `url(#${markerId})` : undefined" :stroke-dasharray="organizationMode ? e.relationKind === 'belongs' ? '3 4' : undefined : holographic && e.weak ? '5 5' : undefined" :stroke="edgeColor(e)" :stroke-width="pathEdgeSet.has([e.a, e.b].sort().join('__')) ? 3.2 : edgeWidth(e)"
              :opacity="edgeOpacity(e)"><title>{{ e.label ? '我方对接：' + e.label : '单位归属' }}</title></line>
      </g>
      <g v-for="n in visibleNodes" :key="n.id"
         :transform="`translate(${screen(n.id).x},${screen(n.id).y})`"
         :opacity="dimmed(n.id) ? 0.2 : 1"
         style="cursor:pointer"
         @mouseenter="hoverId = n.id" @mouseleave="hoverId = ''"
         @mousedown="onNodeDown($event, n.id, n.kind === 'self')"
         @click="onNodeClick(n)">
        <circle :r="nodeRadius(n) + (pathSet.has(n.id) || selectedId === n.id ? 3 : 0)" :fill="nodeColor(n)"
                :stroke="pathSet.has(n.id) || selectedId === n.id ? '#f5c242' : ((edgeMeta.get(n.id)?.decay_state === 'alarm' || holographic && !organizationMode && n.kind === 'person' && !edgeMeta.get(n.id)?.strength) ? '#ff5a5a' : 'rgba(255,255,255,0.25)')"
                :stroke-width="pathSet.has(n.id) || selectedId === n.id ? 3 : 1.4"
                :opacity="!organizationMode && n.kind === 'person' && (edgeMeta.get(n.id)?.strength ?? 0) <= 1 ? 0.55 : 0.95" />
        <text v-if="n.kind === 'self'" text-anchor="middle" dy="4" class="rg-self">我方</text>
        <text v-else-if="hoverId === n.id || pathSet.has(n.id) || n.kind !== 'unit' || organizationMode" text-anchor="middle"
              :dy="nodeRadius(n) + 12" class="rg-label">{{ n.label }}</text>
        <text v-if="holographic && !organizationMode && hoverId === n.id && n.kind === 'person'" text-anchor="middle" :dy="nodeRadius(n)+28" class="rg-label">{{ edgeMeta.get(n.id)?.days_since_touch != null ? '最近维系 ' + edgeMeta.get(n.id)?.days_since_touch + ' 天' : '尚未记录互动' }}</text>
      </g>
      <g v-if="hoverDetail && !draggingId" class="rg-tooltip" :transform="`translate(${Math.min(WIDTH - 166, screen(hoverDetail.node.id).x + 16)},${Math.max(10, screen(hoverDetail.node.id).y - 66)})`" pointer-events="none">
        <rect width="156" height="58" rx="6" /><text x="9" y="16" class="rg-tooltip__title">{{ hoverDetail.node.label }}</text><text x="9" y="32">{{ hoverDetail.line1 }} · {{ hoverDetail.line2 }}</text><text x="9" y="47">{{ hoverDetail.line3 }}</text>
      </g>
    </svg>
  </div>
</template>

<style scoped lang="scss">
.rg-wrap { position: relative; }
.rg-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;
  .rg-tip { color: #9fb0d0; font-size: 11px; } }
.rg-svg { width: 100%; height: auto; background: radial-gradient(circle at 50% 40%, #14294f, #0a1526); border-radius: 12px; user-select: none; }
.rg-self { fill: #0b1730; font-size: 12px; font-weight: 700; }
.rg-label { fill: #cdd8ee; font-size: 10px; }
.rg-tooltip rect{fill:#061a2ef2;stroke:#3c7fa2;stroke-width:1}.rg-tooltip text{fill:#a9c6dc;font-size:8px}.rg-tooltip .rg-tooltip__title{fill:#edf8ff;font-size:10px;font-weight:700}
.rg-org-legend{flex-shrink:0;color:#b7cfe3;font-size:11px;line-height:1.6;padding:6px 0}
</style>
