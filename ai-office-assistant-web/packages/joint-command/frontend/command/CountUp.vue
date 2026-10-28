<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatNumber } from './commandOverview'

const props = withDefaults(defineProps<{
  value: number | null | undefined
  decimals?: number
  // 小于 1000 时是否仍加千分位
  grouping?: boolean
  duration?: number
}>(), { decimals: 0, grouping: true, duration: 1200 })

const display = ref(0)
let raf = 0
const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function run(to: number) {
  cancelAnimationFrame(raf)
  if (reduced || typeof requestAnimationFrame === 'undefined') { display.value = to; return }
  const from = display.value
  const start = performance.now()
  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / props.duration)
    display.value = from + (to - from) * (1 - Math.pow(1 - t, 3))
    if (t < 1) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

watch(() => props.value, value => run(Number(value ?? 0)), { immediate: true })
onBeforeUnmount(() => cancelAnimationFrame(raf))

const text = computed(() => {
  if (props.value === null || props.value === undefined || !Number.isFinite(Number(props.value))) return '—'
  return props.grouping ? formatNumber(display.value, props.decimals) : display.value.toFixed(props.decimals)
})
</script>

<template>
  <span class="num" :data-value="value ?? ''">{{ text }}</span>
</template>
