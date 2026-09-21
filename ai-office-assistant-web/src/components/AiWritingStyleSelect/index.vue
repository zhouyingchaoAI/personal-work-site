<script setup lang="ts">
import { AI_WRITING_STYLES, setWritingStyle, writingStyle, type AiWritingStyle } from '../../utils/aiWritingStyle'

const props = withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{ select: [style: AiWritingStyle] }>()

function changeStyle(value: AiWritingStyle) {
  setWritingStyle(value)
  emit('select', value)
}
</script>

<template>
  <el-select
    :model-value="writingStyle"
    class="ai-writing-style-select"
    size="small"
    aria-label="AI 润色行文风格"
    :disabled="props.disabled"
    @update:model-value="changeStyle"
  >
    <el-option v-for="item in AI_WRITING_STYLES" :key="item.value" :label="item.label" :value="item.value" />
  </el-select>
</template>

<style scoped lang="scss">
.ai-writing-style-select {
  width: 118px;
}
</style>
