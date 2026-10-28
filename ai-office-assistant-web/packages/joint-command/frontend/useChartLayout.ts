import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { resizeChart, contentZoom, gridSpan } from './chartLayoutSize'
import { appearanceVariables, cleanAppearance, type ChartAppearance } from './chartAppearance'
import { applyChartTypes } from './chartTypeEditor'

const primaryBlocks = '.br-chart-card,.company-orders,.br-industry-group,.br-region-group,.br-owner-panel,.br-metric-group,.br-visual-unit,.br-kpi,.br-task-overview,.monthly-trends,.project-ranking'
const additionalBlocks = '.br-task-totals > article,.br-expense-summary > article,.br-region-overview,.be-profit-panel,.rx-insights > article,.rx-kpi,.be-project-flow > article,.be-disclosure:not(.be-method),.region-details'
export const layoutBlocks = `${primaryBlocks.split(',').filter(selector => selector !== '.br-industry-group').join(',')},${additionalBlocks}`

export function useChartLayout(root: Ref<HTMLElement | null>, allowed: Ref<boolean>, key: Ref<string>) {
  const editing = ref(false)
  const message = ref('')
  const selected = ref<string[]>([])
  let observer: MutationObserver | undefined
  let cancelGesture: (() => void) | undefined
  type Size = { width?: string; height?: number; order?: number; x?: number; y?: number; scale?: number; pixelWidth?: number; pixelHeight?: number; contentZoom?: number; appearance?: ChartAppearance }
  let saved: Record<string, Size> = {}
  const history = ref<string[]>([])
  const historyIndex = ref(-1)
  const revision = ref(0)
  let historyKey = ''
  const selectedStyle = computed(() => { revision.value; return cleanAppearance(saved[selected.value[0] || '']?.appearance) })
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  function applyStyle(style: ChartAppearance | null) {
    if (!allowed.value || !editing.value || !selected.value.length) return
    for (const id of selected.value) saved[id] = { ...saved[id], appearance: style === null ? undefined : cleanAppearance({ ...saved[id]?.appearance, ...style }) }
    persist(); observer?.disconnect(); decorate(); observe()
  }
  function travel(direction: number) {
    if (!allowed.value || !editing.value) return
    const target = historyIndex.value + direction
    if (target < 0 || target >= history.value.length) return
    historyIndex.value = target
    saved = JSON.parse(history.value[target]!)
    persist(); observer?.disconnect(); decorate(); observe()
  }
  function selectAll() {
    if (!allowed.value) return
    selected.value = Array.from(root.value?.querySelectorAll<HTMLElement>(layoutBlocks) || []).filter(card => !card.parentElement?.closest('[data-layout-id]')).map(card => card.dataset.layoutId!)
    observer?.disconnect(); decorate(); observe()
  }
  function clearSelection() { selected.value = []; observer?.disconnect(); decorate(); observe() }
  function compact() {
    if (!root.value) return
    const parents = new Set(Array.from(root.value.querySelectorAll<HTMLElement>(layoutBlocks)).filter(card => !card.parentElement?.closest(layoutBlocks)).map(card => card.parentElement!))
    parents.forEach(parent => {
      const children = Array.from(parent.children).filter(element => element instanceof HTMLElement && getComputedStyle(element).display !== 'none') as HTMLElement[]
      const panelsOnly = children.length > 0 && children.every(child => child.matches(layoutBlocks))
      if (!children.some(child => saved[child.dataset.layoutId || '']?.pixelWidth)) parent.classList.remove('chart-layout-flow')
      if (panelsOnly && children.some(child => saved[child.dataset.layoutId || '']?.pixelWidth)) {
        const widths = children.map(child => child.offsetWidth)
        parent.classList.add('chart-layout-flow')
        children.forEach((child, index) => {
          child.style.gridRowEnd = ''
          child.style.flex = '0 0 auto'
          const zoom = saved[child.dataset.layoutId || '']?.contentZoom || 1
          child.style.maxWidth = `calc(100% / ${zoom})`
          const pixelWidth = saved[child.dataset.layoutId || '']?.pixelWidth
          child.style.width = `${pixelWidth ? pixelWidth / zoom : widths[index]!}px`
        })
      }
      const moved = children.filter(child => saved[child.dataset.layoutId || '']?.x || saved[child.dataset.layoutId || '']?.y)
      if (moved.length) {
        const panels = children.filter(child => child.matches(layoutBlocks)).sort((left, right) => {
          const first = left.getBoundingClientRect(); const second = right.getBoundingClientRect()
          return Math.abs(first.top - second.top) > 20 ? first.top - second.top : first.left - second.left
        })
        panels.forEach((child, index) => {
          const id = child.dataset.layoutId!
          saved[id] = { ...saved[id], x: 0, y: 0, order: index + 1 }
          child.style.order = String(index + 1)
          child.style.transform = 'none'
        })
        persist()
      }
      if (getComputedStyle(parent).display !== 'grid') return
      const parentStyle = getComputedStyle(parent)
      const tracks = parentStyle.gridTemplateColumns.split(' ').map(Number.parseFloat).filter(Number.isFinite)
      const gap = parseFloat(parentStyle.columnGap) || 0
      children.forEach(child => {
        child.style.gridRowEnd = ''; child.style.alignSelf = 'stretch'
        if (child.matches(layoutBlocks)) {
          const value = saved[child.dataset.layoutId || '']
          const zoom = value?.contentZoom || 1
          if (value?.pixelWidth) {
            const span = gridSpan(value.pixelWidth, tracks, gap)
            child.style.gridColumn = `span ${span}`
          }
          child.style.width = value?.pixelWidth ? `min(${value.pixelWidth / zoom}px, calc(100% / ${zoom}))` : `calc(100% / ${zoom})`
        }
      })
      parent.style.gridAutoRows = 'auto'
      parent.style.gridAutoFlow = 'row dense'
    })
  }
  function fitSelected() {
    const cards = Array.from(root.value?.querySelectorAll<HTMLElement>(layoutBlocks) || []).filter(card => selected.value.includes(card.dataset.layoutId || ''))
    if (!cards.length) return
    const parents = new Set(cards.map(card => card.parentElement!))
    if (parents.size !== 1) { message.value = '请选择同一层级的板块一起适配'; return }
    const parent = cards[0]!.parentElement!
    const gap = parseFloat(getComputedStyle(parent).columnGap) || 12
    const width = Math.max(180, (parent.clientWidth - gap * (cards.length - 1)) / cards.length)
    cards.forEach(card => {
      const id = card.dataset.layoutId!
      saved[id] = { ...saved[id], width: '', pixelWidth: width, pixelHeight: undefined, x: 0, y: 0, scale: 1 }
    })
    persist(); observer?.disconnect(); decorate(); compact(); observe()
  }
  function persist() {
    const snapshot = JSON.stringify(saved)
    if (history.value[historyIndex.value] !== snapshot) {
      history.value = [...history.value.slice(0, historyIndex.value + 1), snapshot].slice(-51)
      historyIndex.value = history.value.length - 1
    }
    revision.value++
    try { localStorage.setItem(key.value, snapshot); message.value = '布局与样式已保存到当前浏览器' }
    catch { message.value = '浏览器无法保存布局，本次调整仍有效' }
  }
  function decorate() {
    if (!root.value) return
    const blocks = [...root.value.querySelectorAll<HTMLElement>(primaryBlocks), ...root.value.querySelectorAll<HTMLElement>(additionalBlocks)].filter((card, index, all) => all.indexOf(card) === index)
    blocks.forEach((card, index) => {
      const id = card.dataset.layoutKey || `${card.dataset.chartTitle || card.querySelector('h3,h2')?.textContent || 'chart'}:${index}`
      const value = saved[id] || {}
      const zoom = Math.max(0.5, Math.min(2.5, value.contentZoom || 1))
      card.style.zoom = String(zoom)
      card.style.gridColumn = value.width || ''
      card.style.minHeight = value.pixelHeight || value.height ? `${(value.pixelHeight || value.height!) / zoom}px` : ''
      card.style.width = value.pixelWidth ? `${value.pixelWidth / zoom}px` : ''
      card.style.maxWidth = `calc(100% / ${zoom})`
      card.style.minWidth = '0'
      card.style.height = value.pixelHeight ? `${value.pixelHeight / zoom}px` : 'auto'
      card.style.boxSizing = 'border-box'
      card.style.order = value.order === undefined ? '' : String(value.order)
      card.style.transformOrigin = 'top left'
      value.scale = 1
      card.style.transform = `translate(${value.x || 0}px, ${value.y || 0}px)`
      card.style.position = 'relative'
      card.dataset.layoutId = id
      card.classList.toggle('chart-layout-selected', editing.value && selected.value.includes(id))
      for (const name of ['chartType', 'fontFamily', 'fontSize', 'titleSize', 'valueSize', 'padding', 'radius', 'textColor', 'titleColor', 'background', 'borderColor', 'align', 'weight', 'shadow']) {
        card.style.removeProperty(`--editor-${name}`)
        card.removeAttribute(`data-editor-${name}`)
      }
      const appearance = cleanAppearance(value.appearance)
      for (const [name, variable] of Object.entries(appearanceVariables(appearance))) card.style.setProperty(name, variable)
      for (const name of Object.keys(appearance)) card.setAttribute(`data-editor-${name}`, String(appearance[name as keyof ChartAppearance]))
      const parent = card.parentElement
      const nested = card.matches('.br-industry-group') || Boolean(parent?.closest(layoutBlocks))
      if (parent && !nested && (editing.value || value.order !== undefined)) {
        const display = getComputedStyle(parent).display
        if (display !== 'grid' && display !== 'flex') parent.classList.add('chart-layout-stack')
      }
      card.querySelector(':scope > .chart-layout-tools, :scope > summary > .chart-layout-tools')?.remove()
      card.querySelectorAll(':scope > .chart-layout-resize').forEach(element => element.remove())
      if (nested) {
        delete card.dataset.layoutId
        card.style.zoom = '1'
        card.style.transform = 'none'
        card.style.width = ''
        card.style.maxWidth = '100%'
        card.style.minHeight = ''
        card.style.gridColumn = ''
        card.style.gridRowEnd = ''
        card.style.order = ''
        card.classList.remove('chart-layout-selected')
        return
      }
      if (!allowed.value || !editing.value) return
      const tools = document.createElement('div')
      tools.className = 'chart-layout-tools'
      Object.assign(tools.style, { position: 'absolute', top: '0', left: '0', right: '0', zIndex: '2' })
      tools.addEventListener('click', event => event.stopPropagation())
      tools.addEventListener('keydown', event => event.stopPropagation())
      const selection = document.createElement('input')
      selection.type = 'checkbox'; selection.checked = selected.value.includes(id)
      selection.setAttribute('aria-label', '选择此板块编辑样式或布局')
      selection.onpointerdown = event => event.stopPropagation()
      selection.onchange = () => { selected.value = selection.checked ? [...selected.value, id] : selected.value.filter(value => value !== id); card.classList.toggle('chart-layout-selected', selection.checked) }
      tools.append(selection)
      const button = (label: string, action: () => void) => {
        const control = document.createElement('button')
        control.type = 'button'; control.textContent = label
        control.onclick = action; tools.append(control)
        return control
      }
      const gesture = (event: PointerEvent, resize: false | 'right' | 'bottom' | 'corner') => {
        if (event.button !== 0 || !allowed.value) return
        event.preventDefault(); event.stopPropagation()
        cancelGesture?.(); observer?.disconnect()
        const initial = { ...saved[id] }
        const rectangle = card.getBoundingClientRect()
        const peerRectangles = Array.from(card.parentElement!.children)
          .filter(element => element !== card && element.matches(layoutBlocks))
          .map(element => element.getBoundingClientRect())
        const initialZoom = initial.contentZoom || 1
        const ancestorScale = rectangle.width / (card.offsetWidth * initialZoom) || 1
        const elementWidth = card.offsetWidth * initialZoom
        const elementHeight = card.offsetHeight * initialZoom
        const startX = event.clientX; const startY = event.clientY
        const guides = ['vertical', 'horizontal'].map(axis => {
          const guide = document.createElement('div')
          guide.className = `chart-layout-guide ${axis}`
          guide.style.display = 'none'
          document.body.append(guide)
          return guide
        })
        const snap = (positions: number[], targets: number[]) => {
          let correction = 0; let distance = 9; let line: number | undefined
          for (const position of positions) for (const target of targets) {
            if (Math.abs(target - position) < distance) {
              distance = Math.abs(target - position); correction = target - position; line = target
            }
          }
          return { correction, line }
        }
        card.style.zIndex = '20'
        let dropTarget: HTMLElement | undefined
        let dropAfter = false
        const move = (pointer: PointerEvent) => {
          let deltaX = (pointer.clientX - startX) / ancestorScale
          let deltaY = (pointer.clientY - startY) / ancestorScale
          {
            const peers = peerRectangles
            const bounds = card.parentElement!.getBoundingClientRect()
            const horizontal = snap((resize === 'bottom' ? [] : resize ? [rectangle.right] : [rectangle.left, rectangle.left + rectangle.width / 2, rectangle.right]).map(value => value + deltaX * ancestorScale),
              [bounds.left, ...(!resize ? [bounds.left + bounds.width / 2] : []), bounds.right, ...peers.flatMap(peer => resize ? [rectangle.left + peer.width, peer.left, peer.right] : [peer.left, peer.left + peer.width / 2, peer.right])])
            const vertical = snap((resize === 'right' ? [] : resize ? [rectangle.bottom] : [rectangle.top, rectangle.top + rectangle.height / 2, rectangle.bottom]).map(value => value + deltaY * ancestorScale),
              [bounds.top, ...peers.flatMap(peer => resize ? [rectangle.top + peer.height, peer.top, peer.bottom] : [peer.top, peer.top + peer.height / 2, peer.bottom])])
            deltaX += horizontal.correction / ancestorScale
            deltaY += vertical.correction / ancestorScale
            ;[horizontal, vertical].forEach((match, index) => {
              const guide = guides[index]!
              guide.style.display = match.line === undefined ? 'none' : 'block'
              guide.style[index === 0 ? 'left' : 'top'] = `${match.line || 0}px`
            })
          }
          if (!resize) {
            dropTarget?.classList.remove('chart-layout-drop-target')
            dropTarget = Array.from(card.parentElement!.children).find(element => {
              if (element === card || !element.matches(layoutBlocks)) return false
              const bounds = element.getBoundingClientRect()
              return pointer.clientX >= bounds.left && pointer.clientX <= bounds.right && pointer.clientY >= bounds.top && pointer.clientY <= bounds.bottom
            }) as HTMLElement | undefined
            if (dropTarget) {
              const bounds = dropTarget.getBoundingClientRect()
              dropAfter = pointer.clientX > bounds.left + bounds.width / 2
              dropTarget.classList.add('chart-layout-drop-target')
            }
          }
          const dimensions = resize ? resizeChart(elementWidth, elementHeight, deltaX / (initial.scale || 1), deltaY / (initial.scale || 1), resize) : null
          if (dimensions) dimensions.width = Math.min(dimensions.width, card.parentElement!.clientWidth)
          const nextZoom = dimensions && resize && resize !== 'right' ? Math.min(contentZoom(elementWidth, elementHeight, dimensions.width, dimensions.height, initialZoom, resize), initialZoom * dimensions.width / elementWidth, initialZoom * dimensions.height / elementHeight) : initialZoom
          const change = dimensions
            ? { pixelWidth: dimensions.width, pixelHeight: dimensions.height, contentZoom: nextZoom }
            : { x: (initial.x || 0) + deltaX / initialZoom, y: (initial.y || 0) + deltaY / initialZoom }
          saved[id] = { ...initial, ...change }
          const current = saved[id]!
          if (dimensions) {
            const parent = card.parentElement!
            const parentStyle = getComputedStyle(parent)
            if (parentStyle.display === 'grid') {
              const tracks = parentStyle.gridTemplateColumns.split(' ').map(Number.parseFloat).filter(Number.isFinite)
              const gap = parseFloat(parentStyle.columnGap) || 0
              const span = gridSpan(dimensions.width, tracks, gap)
              saved[id]!.width = `span ${span}`
              card.style.gridColumn = `span ${span}`
            }
            card.style.zoom = String(nextZoom)
            card.style.maxWidth = `calc(100% / ${nextZoom})`
            card.style.width = `${dimensions.width / nextZoom}px`
            card.style.minHeight = `${dimensions.height / nextZoom}px`
            card.style.height = `${dimensions.height / nextZoom}px`
          }
          card.style.transform = `translate(${current.x || 0}px, ${current.y || 0}px) scale(${current.scale || 1})`
        }
        const finish = () => {
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', finish)
          window.removeEventListener('pointercancel', finish)
          guides.forEach(guide => guide.remove())
          if (!resize && dropTarget) {
            const panels = Array.from(card.parentElement!.children).filter(element => element.matches(layoutBlocks)) as HTMLElement[]
            panels.sort((left, right) => Number(left.style.order || 0) - Number(right.style.order || 0))
            panels.splice(panels.indexOf(card), 1)
            panels.splice(panels.indexOf(dropTarget) + Number(dropAfter), 0, card)
            panels.forEach((panel, index) => {
              const panelId = panel.dataset.layoutId!
              saved[panelId] = { ...saved[panelId], order: index + 1, x: 0, y: 0 }
              panel.style.order = String(index + 1)
              panel.style.transform = 'none'
            })
          }
          dropTarget?.classList.remove('chart-layout-drop-target')
          card.style.zIndex = ''; cancelGesture = undefined
          persist(); compact(); observe()
        }
        cancelGesture = finish
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', finish)
        window.addEventListener('pointercancel', finish)
      }
      tools.title = '拖动顶部移动板块，拉拽右侧或底部边缘缩放'
      tools.onpointerdown = event => { if (!(event.target as HTMLElement).closest('button')) gesture(event, false) }
      const update = (change: Size) => { saved[id] = { ...saved[id], ...change }; persist(); decorate() }
      button('复原', () => update({ x: 0, y: 0, scale: 1, contentZoom: 1, width: '', height: 0, order: undefined, pixelWidth: undefined, pixelHeight: undefined }))
      for (const edge of ['right', 'bottom', 'corner'] as const) {
        const resize = document.createElement('div')
        resize.className = `chart-layout-resize edge-${edge}`
        resize.title = '拉拽缩放整个板块'
        resize.onpointerdown = event => gesture(event, edge)
        resize.onclick = event => event.stopPropagation()
        card.append(resize)
      }
      const summary = card.matches('details') ? card.querySelector(':scope > summary') : null
      if (summary) {
        tools.onclick = event => { event.preventDefault(); event.stopPropagation() }
        summary.append(tools)
      } else card.prepend(tools)
    })
    applyChartTypes(root.value)
    compact()
  }
  async function refresh() {
    cancelGesture?.()
    observer?.disconnect()
    selected.value = []
    try { const parsed = JSON.parse(localStorage.getItem(key.value) || '{}'); saved = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {} } catch { saved = {} }
    if (historyKey !== key.value || !history.value.length) {
      historyKey = key.value; history.value = [JSON.stringify(saved)]; historyIndex.value = 0
    }
    revision.value++
    await nextTick()
    decorate()
    observer = new MutationObserver(() => { observer?.disconnect(); decorate(); observe() })
    observe()
  }
  function observe() { if (root.value) observer?.observe(root.value, { childList: true, subtree: true }) }
  watch([root, key, allowed, editing], refresh, { flush: 'post' })
  onBeforeUnmount(() => { cancelGesture?.(); observer?.disconnect() })
  function reset() { saved = {}; persist(); observer?.disconnect(); root.value?.querySelectorAll('.chart-layout-stack').forEach(element => element.classList.remove('chart-layout-stack')); decorate(); observe() }
  function resetIndustryComparison() {
    if (!allowed.value) return
    cancelGesture?.()
    observer?.disconnect()
    root.value?.querySelectorAll<HTMLElement>('.be-industry-comparison > .br-chart-card').forEach(card => {
      if (card.dataset.layoutId) delete saved[card.dataset.layoutId]
      card.style.flex = ''
    })
    root.value?.querySelector('.be-industry-comparison')?.classList.remove('chart-layout-flow', 'chart-layout-stack')
    selected.value = []
    persist(); decorate(); observe()
  }
  return { editing, message, reset, resetIndustryComparison, selected, fitSelected, compact, selectedStyle, applyStyle, canUndo, canRedo, undo: () => travel(-1), redo: () => travel(1), selectAll, clearSelection }
}
