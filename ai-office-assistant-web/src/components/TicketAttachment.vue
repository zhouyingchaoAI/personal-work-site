<script setup lang="ts">
import type { ForumAttachment } from '../services/personalWorkApi'
defineProps<{ attachment: ForumAttachment }>()
</script>

<template>
  <el-image v-if="attachment.is_image" class="ticket-attachment-preview" :src="attachment.url" :alt="attachment.name" fit="contain" :preview-src-list="[attachment.url]" preview-teleported hide-on-click-modal title="点击放大截图" />
  <a v-else :href="attachment.url" target="_blank" rel="noopener noreferrer">📎 {{ attachment.name }}</a>
</template>

<style scoped>
.ticket-attachment-preview { width:120px;height:90px;max-width:100%;display:block;border:1px solid #e4ecf6;border-radius:8px;background:#f5f8fc;cursor:zoom-in; }
</style>
