<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getDatacenterStorageMap, type DcStorageItem } from '../../services/personalWorkApi'
import { useSubjectScope } from './subjectScope'

const scope = useSubjectScope()
const snapshot = scope.snapshot
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const mode = ref('all')
const labels: Record<DcStorageItem['mode'], string> = {
  database: '数据库主存储', file: '本地文件主存储', object: '对象存储', external: '外部存储 · 未核验', unknown: '待核实',
}
async function load() {
  loading.value = true
  error.value = ''
  try { snapshot.value = await getDatacenterStorageMap() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '读取存储对应失败' }
  finally { loading.value = false }
}
const groups = computed(() => (snapshot.value?.subjects || [])
  .filter(group => !scope.scoped.value || group.id === scope.selected.value)
  .map(group => ({ ...group, items: group.items.filter(item =>
    (mode.value === 'all' || mode.value === item.mode) &&
    `${group.label} ${item.data} ${item.primary} ${item.mirror_tables.join(' ')}`.toLowerCase().includes(keyword.value.trim().toLowerCase())) }))
  .filter(group => group.items.length))
const counts = computed(() => {
  const assistants = (snapshot.value?.subjects || []).filter(group => !scope.scoped.value || group.id === scope.selected.value)
  return { total: assistants.length,
    database: assistants.filter(group => group.items.some(item => item.mode === 'database')).length,
    file: assistants.filter(group => group.items.some(item => item.mode === 'file')).length,
    external: assistants.filter(group => group.items.some(item => item.mode === 'external' || item.mode === 'unknown')).length }
})
onMounted(load)
</script>

<template>
  <div class="storage-map" v-loading="loading">
    <p v-if="error" role="alert" class="storage-error">{{ error }} <button @click="load">重试</button></p>
    <template v-if="snapshot">
      <section class="storage-card storage-toolbar">
        <div class="storage-counts">
          <span><b>{{ counts.total }}</b>管理对象</span>
          <span><b>{{ counts.database }}</b>有数据库主数据</span>
          <span><b>{{ counts.file }}</b>仍有本地文件</span>
          <span><b>{{ counts.external }}</b>涉及未核验存储</span>
        </div>
        <div class="storage-filters">
          <input v-model="keyword" aria-label="搜索助手或数据" placeholder="搜索助手、数据名称、路径或表名" />
          <select v-model="mode" aria-label="存储类型"><option value="all">全部存储类型</option><option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option></select>
        </div>
        <div class="storage-definitions">
          <span><i class="database" />数据库主存储：业务直接读写数据库（含 SQLite）</span>
          <span><i class="file" />本地文件主存储：业务仍读写文件</span>
          <span><i class="object" />对象存储：文件本体在 MinIO 等服务</span>
          <span><i class="external" />外部 / 待核实</span>
          <span class="storage-sync">最近整体同步 {{ snapshot.sync.finished_at ? snapshot.sync.finished_at.replace('T', ' ').slice(0, 16) : '暂无' }} · {{ snapshot.sync.ok === true ? '成功' : snapshot.sync.ok === false ? '失败' : '未核验' }}</span>
        </div>
        <details class="storage-scope"><summary>口径说明</summary><p>先看“业务实际读写”：它决定日常新增、修改保存到哪里；“统一库副本”有镜像或归档不等于助手已切换数据库。{{ snapshot.scope_note }}</p></details>
      </section>
      <section v-for="group in groups" :key="group.id" class="storage-card storage-group" :data-assistant="group.id">
        <h3>{{ group.label }} <small>{{ group.items.length }} 类数据</small></h3>
        <div class="storage-table-wrap">
          <table>
            <thead><tr><th>具体数据</th><th>当前主存储</th><th>业务实际读写的位置</th><th>统一库副本 / 入库情况</th></tr></thead>
            <tbody><tr v-for="item in group.items" :key="item.data">
              <td><b>{{ item.data }}</b><p class="storage-note">{{ item.owner_label }}</p></td>
              <td><span class="storage-badge" :class="item.mode">{{ labels[item.mode] }}</span></td>
              <td><code>{{ item.primary }}</code><p v-if="item.note" class="storage-note">{{ item.note }}</p></td>
              <td>
                <template v-if="item.mirror_evidence.length">
                  <b class="storage-copy">{{ item.mode === 'file' ? '文件仍为主，另有同步目标' : '另有定时镜像' }}</b>
                  <div v-for="evidence in item.mirror_evidence" :key="evidence.table" class="storage-evidence">
                    <code>{{ evidence.table }}</code>
                    <small :class="{ 'storage-unverified': !evidence.verified }">{{ evidence.verified ? '最近同步已核对' : '最近同步未确认' }}<template v-if="evidence.verified && evidence.rows != null"> · 全表 {{ evidence.rows.toLocaleString() }} 行{{ evidence.rows === 0 ? '（空表，无记录）' : '' }}</template></small>
                  </div>
                </template>
                <span v-else-if="item.mode === 'database'">已配置为数据库主存储；见左侧数据库 / 表。</span>
                <span v-else-if="item.mode === 'object'">文件在对象存储；不等于存入统一业务库。</span>
                <span v-else>未确认已入库。</span>
              </td>
            </tr></tbody>
          </table>
        </div>
      </section>
      <p v-if="!groups.length" class="storage-card">没有符合筛选条件的数据。</p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.storage-map { display: grid; gap: 12px; color: #233858; }
.storage-card { padding: 14px 16px; background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; }
.storage-toolbar { display: grid; gap: 10px; }
h3 { margin: 0 0 10px; font-size: 15px; color: #0b2458; small { font-size: 12px; color: #74829a; margin-left: 10px; font-weight: 400; } }
p { font-size: 13px; line-height: 1.7; }
.storage-definitions, .storage-counts, .storage-filters { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; font-size: 12px; color: #4c5b75; }
.storage-definitions i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px;
  &.database { background: #3478d5; } &.file { background: #c47c14; } &.object { background: #248878; } &.external { background: #8b6db1; }
}
.storage-sync { margin-left: auto; color: #8c9ab3; }
.storage-scope { color: #67778c; font-size: 12px; summary { cursor: pointer; color: #15499c; } p { margin: 6px 0 0; font-size: 12px; } }
.storage-note { color: #67778c; font-size: 12px; }
.storage-counts { gap: 8px 26px; span { display: flex; align-items: baseline; gap: 6px; } b { font-size: 22px; color: #0b2458; font-variant-numeric: tabular-nums; } }
.storage-filters input:not([type=checkbox]), select { padding: 7px 10px; border: 1px solid #d5e0f1; border-radius: 8px; color: #24436c; background: #fff; font-size: 13px; }
.storage-filters input:not([type=checkbox]) { flex: 1; min-width: 240px; }
button { cursor: pointer; }
.storage-table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; table-layout: fixed; min-width: 850px; }
th { background: #f0f5fc; color: #42618c; }
td, th { padding: 12px; border-bottom: 1px solid #e8eef7; vertical-align: top; overflow-wrap: anywhere; line-height: 1.65; }
th:nth-child(1) { width: 18%; } th:nth-child(2) { width: 17%; } th:nth-child(3) { width: 33%; }
code { font-size: 12px; white-space: normal; }
.storage-badge { display: inline-block; padding: 3px 7px; border-radius: 5px; background: #f2f0f6; color: #776184;
  &.database { background: #eaf2ff; color: #2261ac; } &.file { background: #fff3df; color: #996313; } &.object { background: #e8f7f1; color: #247b64; }
}
.storage-copy { color: #81609f; font-weight: 500; }
.storage-evidence { margin-top: 6px; small { display: block; color: #43765e; } .storage-unverified { color: #a16d21; } }
.storage-error { color: #bd3333; }
</style>
