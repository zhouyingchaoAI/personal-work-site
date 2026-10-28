<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BusinessSheet } from '../../../src/services/personalWorkApi'
import { businessDataQuality } from './businessDataQuality'
const props = defineProps<{ sheets: BusinessSheet[] }>()
const result = computed(() => businessDataQuality(props.sheets))
const page = ref(1)
watch(() => props.sheets, () => { page.value = 1 })
const visibleIssues = computed(() => result.value.issues.slice((page.value - 1) * 20, page.value * 20))
const sourceCounts = computed(() => {
  const counts = new Map<string, number>()
  result.value.issues.forEach(item => counts.set(item.source, (counts.get(item.source) || 0) + 1))
  return [...counts].sort((left, right) => right[1] - left[1])
})
const differenceCount = computed(() => result.value.comparisons.filter(item => Math.abs(item.difference) >= 0.01).length)
function download() {
  const escape = (value: unknown) => `"${String(value ?? '').replace(/^[=+\-@\t\r]/, "'$&").replace(/"/g, '""')}"`
  const rows = [['来源表', '数据行序号', '问题', '内容', '处理建议'], ...result.value.issues.map(item => [item.source, item.row || '', item.item, item.detail, item.action])]
  const url = URL.createObjectURL(new Blob(['\uFEFF' + rows.map(row => row.map(escape).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url; link.download = '经营分析_当前权限数据核验.csv'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <section class="quality-panel be-page be-quality">
    <header><div class="be-quality-heading"><img class="be-page-icon" :src="'/personal-office-assistant/management-quality.png'" alt="" /><div><h3>数据核验</h3><p>当前版本 · 当前权限 · 原始记录不自动修改</p></div></div><el-button @click="download">下载核验清单</el-button></header>
    <div class="be-quality-stats">
      <article><span>待核验项</span><strong>{{ result.issues.length }}</strong><small>规则发现的线索，不等同已确认错误</small></article>
      <article><span>涉及来源</span><strong>{{ sourceCounts.length }}</strong><small>当前可见数据中的问题来源表</small></article>
      <article><span>存在差异的对账指标</span><strong>{{ differenceCount }} / {{ result.comparisons.length }}</strong><small>按显示精度0.01万元核对</small></article>
    </div>
    <details class="be-disclosure be-method"><summary><strong>核验规则与统计限制</strong><span>点击查看口径</span></summary>
    <el-alert title="不同范围、不同截止日期的数值不能直接相加；没有完成证据不等于业务没有完成。公式错误若已在导入时转为空值，本页无法恢复识别。" type="info" :closable="false" />
    <p>行序号是导入后的数据行，不是原Excel行号。</p></details>
    <div class="be-quality-main"><div><h4>待核验项来源分布</h4>
      <div v-for="[source, count] in sourceCounts" :key="source" class="be-quality-category"><header><span>{{ source }}</span><b>{{ count }} 项</b></header><progress :value="count" :max="Math.max(1, result.issues.length)" :aria-label="source + '待核验项数'" /></div>
      <p v-if="!sourceCounts.length">当前规则未发现待核验项，不代表已完成财务审计。</p>
    </div><div>
    <h4 v-if="result.comparisons.length">核心指标与任务令累计对账（万元）</h4>
    <el-table v-if="result.comparisons.length" :data="result.comparisons">
      <el-table-column prop="metric" label="指标" />
      <el-table-column label="核心指标"><template #default="{row}">{{ row.actual.toFixed(2) }}</template></el-table-column>
      <el-table-column label="任务累计"><template #default="{row}">{{ row.task.toFixed(2) }}</template></el-table-column>
      <el-table-column label="差异"><template #default="{row}">{{ row.difference.toFixed(2) }}</template></el-table-column>
    </el-table>
    </div></div>
    <details class="be-disclosure"><summary><strong>核验问题明细</strong><span>{{ result.issues.length }} 项 · 点击展开逐项处理</span></summary>
    <el-table :data="visibleIssues" empty-text="当前规则未发现待核验项；不代表已完成财务审计" style="margin-top:20px">
      <el-table-column prop="source" label="来源表" min-width="170" />
      <el-table-column prop="row" label="数据行序号（0为表级）" width="160" />
      <el-table-column prop="item" label="问题" min-width="130" />
      <el-table-column prop="detail" label="内容" min-width="220" />
      <el-table-column prop="action" label="处理建议" min-width="260" />
    </el-table>
    <el-pagination v-model:current-page="page" :total="result.issues.length" :page-size="20" layout="prev, pager, next, total" />
    </details>
  </section>
</template>
<style scoped>
.quality-panel{padding:18px;background:var(--bi-panel,#fff);border:1px solid var(--bi-line,#dbe6f3);border-radius:12px;color:var(--bi-text,#203c57)}header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}h3{margin:0}p{font-size:13px;line-height:1.7}.el-pagination{margin-top:16px}.quality-panel :deep(.el-table){--el-table-bg-color:var(--bi-panel,#fff);--el-table-tr-bg-color:var(--bi-panel,#fff);--el-table-header-bg-color:var(--bi-panel,#fff);--el-table-text-color:var(--bi-text,#203c57);--el-table-header-text-color:var(--bi-secondary,#56728b);--el-table-border-color:var(--bi-line,#dbe6f3)}
</style>
