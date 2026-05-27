<script setup lang="ts">
import type { AgentMessage } from '../../services/personalWorkApi'
import './index.scss'

withDefaults(
  defineProps<{
    open: boolean
    avatar: string
    title?: string
    messages: AgentMessage[]
    quickActions: string[]
    input: string
    loading?: boolean
  }>(),
  {
    title: '犇犇',
    loading: false,
  },
)

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:input': [value: string]
  send: [value?: string]
}>()

function updateInput(event: Event) {
  emit('update:input', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <section v-if="open" class="assistant-chat-float">
    <section class="assistant-chat-window">
      <header>
        <span><img :src="avatar" alt="" /> {{ title }}</span>
        <button type="button" aria-label="关闭助手聊天" @click="emit('update:open', false)">×</button>
      </header>

      <div class="assistant-chat-messages">
        <div v-for="(message, index) in messages" :key="index" :class="['assistant-chat-message', message.role]">
          {{ message.content }}
        </div>
        <div v-if="loading" class="assistant-chat-message assistant">正在思考...</div>
      </div>

      <div class="assistant-chat-actions">
        <button v-for="item in quickActions" :key="item" type="button" @click="emit('send', item)">
          {{ item }}
        </button>
      </div>

      <div class="assistant-chat-input">
        <textarea
          :value="input"
          placeholder="输入消息...（Ctrl+Enter 发送）"
          @input="updateInput"
          @keydown.ctrl.enter.prevent="emit('send')"
          @keydown.meta.enter.prevent="emit('send')"
        ></textarea>
        <button type="button" :disabled="loading" @click="emit('send')">发送</button>
      </div>
    </section>
  </section>
</template>
