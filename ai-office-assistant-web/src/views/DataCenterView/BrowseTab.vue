<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Download, Folder, Lock } from '@element-plus/icons-vue'
import {
  datacenterDownloadUrl, getDatacenterAccessLog, getDatacenterBrowse, getDatacenterFile,
  type DatacenterBrowse, type DatacenterFilePreview,
} from '../../services/personalWorkApi'
import { useSubjectScope } from './subjectScope'

const scope = useSubjectScope()
const listing = ref<DatacenterBrowse | null>(null)
const preview = ref<DatacenterFilePreview | null>(null)
const accessLog = ref<{ at: string; user: string; action: string; path: string }[]>([])
const loadingList = ref(false)
const loadingFile = ref(false)
const path = ref('')

const crumbs = computed(() => {
  const parts = path.value ? path.value.split('/') : []
  return [{ label: 'user_data', path: '' }, ...parts.map((p, i) => ({ label: p, path: parts.slice(0, i + 1).join('/') }))]
})

function fmtBytes(n?: number | null) {
  if (!n && n !== 0) return ''
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(n / 1024)} KB`
}

async function openDir(p: string) {
  loadingList.value = true
  try {
    listing.value = await getDatacenterBrowse(p, scope.selected.value)
    path.value = p
    preview.value = null
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '读取失败')
  } finally {
    loadingList.value = false
  }
}

async function openFile(p: string, table = '', offset = 0) {
  loadingFile.value = true
  try {
    preview.value = await getDatacenterFile(p, table, offset)
    loadAccessLog()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '预览失败')
  } finally {
    loadingFile.value = false
  }
}

function onEntry(entry: { dir: boolean; path: string }) {
  if (entry.dir) openDir(entry.path)
  else openFile(entry.path)
}

async function loadAccessLog() {
  try {
    accessLog.value = (await getDatacenterAccessLog()).rows.slice(0, 20)
  } catch { /* 留痕列表失败不打断浏览 */ }
}

const jsonText = computed(() => preview.value?.kind === 'json' ? JSON.stringify(preview.value.data, null, 2) : '')

onMounted(() => { openDir(''); loadAccessLog() })
</script>

<template>
  <div class="br">
    <p class="br-note">{{ scope.label.value }} · 仅浏览相关本地路径。数据库主数据请到“数据库”；CRM 文件为切换前快照。用户目录只是导航，报告草稿及 SQLite 等可能由多个助手共享。访问留痕为平台级。</p>
    <div class="br-main">
      <section class="br-card br-list" v-loading="loadingList">
        <nav class="br-crumbs">
          <template v-for="(c, i) in crumbs" :key="c.path">
            <a @click="openDir(c.path)">{{ c.label }}</a><span v-if="i < crumbs.length - 1">/</span>
          </template>
        </nav>
        <el-table :data="listing?.entries || []" size="small" max-height="520" @row-click="onEntry" row-class-name="br-row" empty-text="此处没有已登记的相关文件；不表示数据库或外部存储无数据">
          <el-table-column label="名称" min-width="200">
            <template #default="{ row }">
              <el-icon class="br-ic"><Folder v-if="row.dir" /><Document v-else /></el-icon>{{ row.name }}
            </template>
          </el-table-column>
          <el-table-column label="模块" min-width="150">
            <template #default="{ row }"><span class="br-mod">{{ row.module }}</span></template>
          </el-table-column>
          <el-table-column label="级别" width="60">
            <template #default="{ row }">{{ row.level || '' }}</template>
          </el-table-column>
          <el-table-column label="大小" width="90" align="right">
            <template #default="{ row }">{{ row.dir ? '' : fmtBytes(row.size) }}</template>
          </el-table-column>
          <el-table-column label="修改时间" width="150">
            <template #default="{ row }">{{ row.mtime?.replace('T', ' ') }}</template>
          </el-table-column>
        </el-table>
        <p v-if="listing?.truncated" class="br-note">目录条目过多，仅显示前 400 项。</p>
      </section>

      <section class="br-card br-preview" v-loading="loadingFile">
        <template v-if="preview">
          <header class="br-ph">
            <div>
              <b>{{ preview.path }}</b>
              <span>{{ fmtBytes(preview.size) }} · {{ preview.mtime?.replace('T', ' ') }}</span>
            </div>
            <a v-if="preview.kind !== 'sqlite' && preview.downloadable !== false"
               :href="datacenterDownloadUrl(preview.path)" target="_blank">
              <el-button size="small" :icon="Download">下载原文件</el-button>
            </a>
            <el-tag v-else-if="preview.downloadable === false" type="warning" size="small">
              <el-icon><Lock /></el-icon>含密钥 · 仅脱敏预览
            </el-tag>
          </header>

          <template v-if="preview.kind === 'sqlite'">
            <div class="br-tables">
              <button v-for="t in preview.tables" :key="t.name" :class="{ active: preview.table === t.name }"
                      @click="openFile(preview.path, t.name)">{{ t.name }}<i>{{ t.rows }}</i></button>
            </div>
            <div v-if="preview.table" class="br-sql">
              <el-table :data="(preview.rows as unknown[][] || []).map(r => Object.fromEntries((preview!.columns || []).map((c, i) => [c, (r as unknown[])[i]])))"
                        size="small" max-height="380" border>
                <el-table-column v-for="c in preview.columns" :key="c" :prop="c" :label="c" min-width="120" show-overflow-tooltip />
              </el-table>
              <div class="br-page">
                <el-button size="small" :disabled="!preview.offset" @click="openFile(preview.path, preview.table, Math.max(0, (preview.offset || 0) - 50))">上一页</el-button>
                <span>第 {{ Math.floor((preview.offset || 0) / 50) + 1 }} 页</span>
                <el-button size="small" :disabled="(preview.rows || []).length < 50" @click="openFile(preview.path, preview.table, (preview.offset || 0) + 50)">下一页</el-button>
              </div>
            </div>
            <p v-else class="br-note">点击上方表名查看数据（每页 50 行）。</p>
          </template>

          <pre v-else-if="preview.kind === 'json'" class="br-code">{{ jsonText }}</pre>
          <template v-else-if="preview.kind === 'jsonl'">
            <p class="br-note">共 {{ preview.total_lines?.toLocaleString() }} 行，显示最近 200 行。</p>
            <pre class="br-code">{{ (preview.rows || []).map(r => JSON.stringify(r)).join('\n') }}</pre>
          </template>
          <pre v-else-if="preview.kind === 'text'" class="br-code">{{ preview.text }}</pre>
          <div v-else class="br-binary">{{ preview.note || '二进制文件' }}</div>
        </template>
        <div v-else class="br-empty">在左侧选择文件查看内容 · JSON 中的密码与密钥字段自动脱敏 · 每次查看与下载均有留痕</div>
      </section>
    </div>

    <section class="br-card">
      <h4 class="br-h4">最近访问留痕（谁看了什么）</h4>
      <el-table :data="accessLog" size="small" max-height="220">
        <el-table-column label="时间" width="170"><template #default="{ row }">{{ row.at?.replace('T', ' ') }}</template></el-table-column>
        <el-table-column label="操作人" prop="user" width="140" />
        <el-table-column label="操作" width="90"><template #default="{ row }">{{ row.action === 'download' ? '下载' : '查看' }}</template></el-table-column>
        <el-table-column label="路径" prop="path" min-width="300" />
      </el-table>
    </section>
  </div>
</template>

<style scoped lang="scss">
.br { display: flex; flex-direction: column; gap: 12px; }
.br-card { background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; padding: 14px 16px; }
.br-main { display: grid; grid-template-columns: minmax(430px, 46%) 1fr; gap: 12px; align-items: start; }
.br-crumbs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; font-size: 13px;
  a { color: #15499c; cursor: pointer; font-weight: 600; &:hover { text-decoration: underline; } }
  span { color: #b3bfd3; } }
.br-ic { vertical-align: -2px; margin-right: 6px; color: #15499c; }
.br-mod { font-size: 12px; color: #64748b; }
:deep(.br-row) { cursor: pointer; }
.br-note { font-size: 12px; color: #8c9ab3; margin-top: 8px; }
.br-h4 { font-size: 14px; color: #0b2458; margin-bottom: 8px; }
.br-preview { min-height: 300px; }
.br-ph { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px;
  b { display: block; color: #0b2458; font-size: 13.5px; word-break: break-all; }
  span { font-size: 12px; color: #8c9ab3; } }
.br-code { background: #0f2348; color: #d6e4fb; border-radius: 12px; padding: 12px 14px; font-size: 12px; line-height: 1.55;
  max-height: 470px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
.br-binary, .br-empty { padding: 40px 20px; text-align: center; color: #8c9ab3; font-size: 13px; }
.br-tables { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;
  button { border: 1px solid #dbe7fb; background: #f6f9fe; border-radius: 8px; padding: 4px 10px; font-size: 12.5px; color: #14213d; cursor: pointer;
    i { font-style: normal; color: #64748b; margin-left: 6px; }
    &.active { background: #15499c; color: #fff; border-color: #15499c; i { color: #cfe0fa; } } } }
.br-page { display: flex; align-items: center; gap: 12px; margin-top: 10px; font-size: 12.5px; color: #64748b; }
@media (max-width: 1100px) { .br-main { grid-template-columns: 1fr; } }
</style>
