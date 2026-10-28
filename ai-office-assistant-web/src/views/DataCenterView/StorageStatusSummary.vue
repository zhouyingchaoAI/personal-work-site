<script setup lang="ts">
import { computed } from 'vue'
import { useSubjectScope } from './subjectScope'
import { STORAGE_STATUSES, storageStatus } from './storageStatus'

const emit = defineEmits<{ inspect: [id: string] }>()
const scope = useSubjectScope()
const entries = computed(() => scope.subjects.value
  .filter(subject => !scope.scoped.value || subject.id === scope.selected.value)
  .map(subject => ({ ...subject, status: storageStatus(subject.items) })))
const assistants = computed(() => entries.value.filter(subject => subject.id !== 'platform'))
const platform = computed(() => entries.value.find(subject => subject.id === 'platform'))
const buckets = computed(() => STORAGE_STATUSES.map(status => ({ ...status,
  entries: assistants.value.filter(subject => subject.status.key === status.key),
})))
</script>

<template>
  <section class="storage-progress" aria-label="助手入库进度">
    <header><h2>助手入库进度</h2><span>{{ assistants.length }} 个助手 · {{ assistants.filter(subject => subject.status.local > 0).length }} 个仍有本地文件 · 按业务实际主存储判断，镜像与备份不算切库</span></header>
    <div v-if="assistants.length" class="progress-buckets">
      <article v-for="bucket in buckets" :key="bucket.key" :data-storage-status="bucket.key" :class="bucket.key">
        <h3>{{ bucket.label }} <strong>{{ bucket.entries.length }}</strong></h3>
        <p>{{ bucket.note }}</p>
        <div class="progress-names">
        <button v-for="subject in bucket.entries" :key="subject.id" :data-status-owner="subject.id" :title="`数据库 ${subject.status.database} 类 · 文件 ${subject.status.local} 类` + (subject.status.object ? ` · 对象 ${subject.status.object} 类` : '') + (subject.status.unverified ? ` · 待核验 ${subject.status.unverified} 类` : '')" @click="emit('inspect', subject.id)">
          <b>{{ subject.label }}</b>
          <small><i class="database" v-if="subject.status.database">{{ subject.status.database }}</i><i class="file" v-if="subject.status.local">{{ subject.status.local }}</i><i class="object" v-if="subject.status.object">{{ subject.status.object }}</i><i class="unverified" v-if="subject.status.unverified">{{ subject.status.unverified }}</i></small>
        </button>
        </div>
        <span v-if="!bucket.entries.length" class="empty">暂无</span>
      </article>
    </div>
    <div v-if="platform" class="platform-status">
      <b>平台本身（单独统计）：{{ platform.status.label }}</b>
      <span>数据库 {{ platform.status.database }} 类 · 本地文件 {{ platform.status.local }} 类（config.json 等引导配置） · 待核验 {{ platform.status.unverified }} 类</span>
      <button data-status-owner="platform" @click="emit('inspect', 'platform')">查看平台明细 →</button>
      <em>点击任一助手可查看具体数据的存储位置与镜像证据</em>
    </div>
  </section>
</template>

<style scoped lang="scss">
.storage-progress { padding: 14px 16px; border: 1px solid #e3ebf7; border-radius: 14px; background: #fff; color: #233858;
  header { display: flex; gap: 12px; flex-wrap: wrap; align-items: baseline; margin-bottom: 10px; } h2 { font-size: 15px; margin: 0; color: #0b2458; } header span { color: #8c9ab3; font-size: 12px; }
  > p { color: #67778c; font-size: 12px; line-height: 1.7; margin: 8px 0; }
}
.progress-buckets { display: flex; flex-direction: column; gap: 8px;
  article { display: grid; grid-template-columns: 210px 1fr; gap: 6px 16px; align-items: start; border: 1px solid #e6edf7; border-left: 4px solid #94a3b8; padding: 10px 14px; border-radius: 10px; background: #f8fafc; &.database { border-left-color: #129567; } &.managed { border-left-color: #397cd4; } &.mixed { border-left-color: #bd8717; } &.file { border-left-color: #cf734b; } &.unknown { border-left-color: #94a3b8; } }
  h3 { font-size: 13px; margin: 0; display: flex; align-items: baseline; gap: 8px; color: #0b2458; } strong { font-size: 18px; color: #0b2458; }
  > article > p { grid-column: 1; grid-row: 2; font-size: 11.5px; color: #8c9ab3; margin: 0; line-height: 1.5; }
  .progress-names { grid-column: 2; grid-row: 1 / span 2; }
  .empty { grid-column: 2; grid-row: 1 / span 2; font-size: 12px; color: #8896a8; align-self: center; }
  button { display: inline-flex; align-items: center; gap: 8px; }
  small { display: inline-flex; gap: 4px; i { font-style: normal; font-size: 10.5px; line-height: 16px; min-width: 16px; padding: 0 5px; border-radius: 99px; text-align: center; font-weight: 700;
    &.database { background: #e3f4ec; color: #12805c; } &.file { background: #fff1de; color: #a8610e; } &.object { background: #e5f4f1; color: #247b64; } &.unverified { background: #ece8f3; color: #6f5a95; } } }
}
.progress-names { display: flex; flex-wrap: wrap; gap: 6px; }
button { cursor: pointer; background: #fff; border: 1px solid #e3ebf7; border-radius: 8px; padding: 5px 10px; color: #24436c; font-size: 12.5px; transition: border-color .15s, background .15s; &:hover { border-color: #397cd4; background: #f0f6ff; } }
.platform-status { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 12px; border-top: 1px dashed #e3ebf7; padding-top: 10px; font-size: 12px; span { color: #64748b; }
  button { border: 0; background: transparent; color: #15499c; font-weight: 600; padding: 0; &:hover { text-decoration: underline; background: transparent; } }
  em { margin-left: auto; font-style: normal; color: #8c9ab3; } }
</style>
