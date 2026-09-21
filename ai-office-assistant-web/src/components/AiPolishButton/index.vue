<script setup lang="ts">
import { computed } from 'vue'
import { CaretBottom, CaretTop } from '@element-plus/icons-vue'
import { AI_WRITING_STYLES, setWritingStyle, writingStyle } from '../../utils/aiWritingStyle'

const props = withDefaults(defineProps<{ loading?: boolean; disabled?: boolean }>(), {
  loading: false,
  disabled: false,
})
const emit = defineEmits<{ polish: [] }>()

const currentStyle = computed(() => AI_WRITING_STYLES.find((item) => item.value === writingStyle.value) || AI_WRITING_STYLES[1])

function switchStyle(step: number) {
  if (props.disabled || props.loading) return
  const currentIndex = Math.max(0, AI_WRITING_STYLES.findIndex((item) => item.value === writingStyle.value))
  const nextIndex = (currentIndex + step + AI_WRITING_STYLES.length) % AI_WRITING_STYLES.length
  setWritingStyle(AI_WRITING_STYLES[nextIndex].value)
}

function switchStyleByWheel(event: WheelEvent) {
  if (event.deltaY !== 0) switchStyle(event.deltaY > 0 ? 1 : -1)
}

function requestPolish() {
  if (!props.disabled && !props.loading) emit('polish')
}
</script>

<template>
  <div
    :class="['ai-polish-wheel', `ai-polish-wheel--${currentStyle.value}`]"
    :title="`当前：${currentStyle.label}。悬停后滚动鼠标滚轮或点击左侧箭头切换风格，单击右侧开始润色。`"
    @wheel.prevent="switchStyleByWheel"
  >
    <span class="ai-polish-wheel__arrows" aria-label="切换润色风格">
      <button type="button" :disabled="disabled || loading" aria-label="上一个润色风格" @click.stop="switchStyle(-1)"><el-icon><CaretTop /></el-icon></button>
      <button type="button" :disabled="disabled || loading" aria-label="下一个润色风格" @click.stop="switchStyle(1)"><el-icon><CaretBottom /></el-icon></button>
    </span>
    <button class="ai-polish-button" type="button" :disabled="disabled || loading" @click="requestPolish">
      <span aria-hidden="true">✦</span>
      {{ loading ? '润色中' : `AI 润色·${currentStyle.label}` }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.ai-polish-wheel {
  display: inline-flex;
  min-width: 160px;
  overflow: hidden;
  border-radius: 8px;
  color: #fff;
  box-shadow: 0 5px 12px rgba(37, 99, 235, 0.22);

  .ai-polish-button {
    flex: 1;
    min-width: 0;
    border-radius: 0;
    box-shadow: none;
  }

  &__arrows {
    display: grid;
    width: 24px;
    border-right: 1px solid rgba(255, 255, 255, 0.28);
  }

  &__arrows button {
    display: grid;
    min-height: 0;
    place-items: center;
    padding: 0;
    border: 0;
    color: inherit;
    background: rgba(0, 0, 0, 0.1);
    cursor: pointer;
  }

  &__arrows button + button { border-top: 1px solid rgba(255, 255, 255, 0.2); }
  &__arrows button:hover:not(:disabled) { background: rgba(255, 255, 255, 0.17); }
  &__arrows button:disabled { cursor: not-allowed; opacity: 0.58; }
  &__arrows .el-icon { font-size: 12px; }

  &--clear {
    background: #0f766e;
    box-shadow: 0 5px 12px rgba(15, 118, 110, 0.22);
    .ai-polish-button { background: #0f766e !important; }
  }

  &--concise {
    background: #2563eb;
    box-shadow: 0 5px 12px rgba(37, 99, 235, 0.22);
    .ai-polish-button { background: #2563eb !important; }
  }

  &--formal {
    background: #334155;
    box-shadow: 0 5px 12px rgba(51, 65, 85, 0.24);
    .ai-polish-button { background: #334155 !important; }
  }

  &--detailed {
    background: #7c3aed;
    box-shadow: 0 5px 12px rgba(124, 58, 237, 0.22);
    .ai-polish-button { background: #7c3aed !important; }
  }

  &:hover {
    filter: brightness(1.08);
  }
}
</style>
