import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'

export function useCanvasScale(target: Ref<HTMLElement | null>, width: number, height: number, enabled: Ref<boolean>) {
  const scale = ref(1)
  let observer: ResizeObserver | null = null

  function update() {
    const el = target.value
    if (!el || !enabled.value) return
    const remPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 10
    const designWidth = width / 10 * remPx
    const next = el.clientWidth / designWidth
    scale.value = Number.isFinite(next) && next > 0 ? next : 1
  }

  function observe() {
    observer?.disconnect()
    observer = null
    if (!target.value || !enabled.value || typeof ResizeObserver === 'undefined') return
    observer = new ResizeObserver(update)
    observer.observe(target.value)
  }

  onMounted(() => { observe(); update(); window.addEventListener('resize', update) })
  onBeforeUnmount(() => { observer?.disconnect(); window.removeEventListener('resize', update) })
  watch([target, enabled], () => { observe(); update() }, { flush: 'post' })

  const style = computed(() => enabled.value
    ? { width: `${width / 10}rem`, height: `${height / 10}rem`, transform: `scale(${scale.value})` }
    : undefined)

  const frameStyle = computed(() => enabled.value
    ? { height: `calc(${height / 10}rem * ${scale.value})` }
    : undefined)

  return { scale, style, frameStyle, update }
}
