<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { subjectScopeKey } from './subjectScope'
import { ElMessage } from 'element-plus'
import { ArrowDown, Coin, DataAnalysis, FolderOpened } from '@element-plus/icons-vue'
import DashboardTab from './DashboardTab.vue'
import BrowseTab from './BrowseTab.vue'
import ApiTab from './ApiTab.vue'
import DatabasesTab from './DatabasesTab.vue'
import DataFlowTab from './DataFlowTab.vue'
import StorageMapTab from './StorageMapTab.vue'
import StorageStatusSummary from './StorageStatusSummary.vue'
import RelationGraph from './RelationGraph.vue'
import { storageStatus } from './storageStatus'
import { scopeFlowSnapshot } from './flowScope'
import {
  getDatacenterFile, getDatacenterBackups, getDatacenterDbFlow, getDatacenterOverview, refreshDatacenterScan, runDatacenterBackup, runDatacenterDbSync,
  getDatacenterStorageMap, type DcFlowSnapshot, type DcStorageMap, type DatacenterBackups, type DatacenterOverview,
} from '../../services/personalWorkApi'

type Tab = 'overview' | 'storage' | 'dashboard' | 'browse' | 'api' | 'databases' | 'ops'
type DbView = 'instances' | 'flow'
const tab = ref<Tab>('overview')
const dbView = ref<DbView>('instances')
const route = useRoute()
const router = useRouter()
const selected = computed({
  get: () => String(route.query.subject || 'all'),
  set: value => { void router.replace({ query: { ...route.query, subject: value } }) },
})
const storage = ref<DcStorageMap | null>(null)
const scopeError = ref('')
const subjects = computed(() => storage.value?.subjects || [])
const subject = computed(() => subjects.value.find(item => item.id === selected.value))
const assistantOptions = computed(() => subjects.value.filter(item => item.id !== 'platform'))
const platformOption = computed(() => subjects.value.find(item => item.id === 'platform'))
const scoped = computed(() => selected.value !== 'all')
const subjectLabel = computed(() => subject.value?.label || '全局总览')
const scopeModules = computed(() => (overview.value?.scan.modules || []).filter(item => !scoped.value || subject.value?.modules.includes(item.module)))
const scopeServices = computed(() => (overview.value?.services || []).filter(item => !scoped.value || subject.value?.instances.includes(item.key) || (selected.value === 'platform' && item.key === 'datacenter-backup')))
const scopeTables = computed(() => {
  const names = new Set(subject.value?.items.flatMap(item => item.mirror_tables) || [])
  return (overview.value?.db_sync?.last?.tables || []).filter(item => !scoped.value || names.has(item.table))
})
provide(subjectScopeKey, { selected, snapshot: storage, subject, subjects })
async function loadScope() {
  scopeError.value = ''
  try {
    storage.value = await getDatacenterStorageMap()
    if (selected.value !== 'all' && !subject.value) selected.value = 'all'
  } catch (reason) { scopeError.value = reason instanceof Error ? reason.message : '助手目录加载失败' }
}
const overview = ref<DatacenterOverview | null>(null)
const backups = ref<DatacenterBackups | null>(null)
const loading = ref(false)
const busy = ref('')
const pgBackup = ref<{ state?: string; finished_at?: string; bytes?: number; file?: string } | null>(null)
let timer: number | undefined

const LEVEL_COLORS: Record<string, string> = { A: '#d14343', B: '#d9822b', C: '#2f7bea', D: '#64748b' }
const LEVEL_BACKUP: Record<string, string> = { A: '每日备份 + 完整性校验', B: '每日备份', C: '不备份 · 按流程重建', D: '不备份 · 可重新拉取' }

function fmtBytes(n?: number | null) {
  if (!n && n !== 0) return '—'
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(n / 1024)} KB`
}
function fmtTime(t?: string) { return t ? t.replace('T', ' ').slice(0, 16) : '—' }

const levelCards = computed(() => {
  const o = overview.value
  if (!o) return []
  return Object.entries(o.scan.levels).map(([lv, item]) => ({ lv, ...item, color: LEVEL_COLORS[lv], backup: LEVEL_BACKUP[lv] }))
})
const diskPercent = computed(() => {
  const d = overview.value?.disk
  return d ? Math.round(((d.used ?? d.total - d.free) / d.total) * 100) : 0
})
const migrationSteps = computed(() => overview.value?.migration || [])
const backupDisk = computed(() => backups.value?.status?.backup_disk || overview.value?.backup_disk || null)
const lastRun = computed(() => backups.value?.status?.last_run || backups.value?.runs?.[0] || null)
const backupHealthy = computed(() => !!lastRun.value?.ok)
const heartbeatOk = computed(() => {
  const t = backups.value?.status?.heartbeat_at
  return !!t && Date.now() - new Date(t).getTime() < 5 * 60 * 1000
})
const cutover = computed(() => {
  const assistants = subjects.value.filter(item => item.id !== 'platform')
  const done = assistants.filter(item => ['database', 'managed'].includes(storageStatus(item.items).key)).length
  return { done, total: assistants.length }
})
const servicesUp = computed(() => {
  const list = overview.value?.services || []
  return { up: list.filter(item => item.status === 'up').length, total: list.length }
})
const lastSync = computed(() => overview.value?.db_sync?.last || null)
const flowRaw = ref<DcFlowSnapshot | null>(null)
const flowSnap = computed(() => scopeFlowSnapshot(flowRaw.value, selected.value, subjects.value))
const graphAssistant = ref<string | null>(null)
const graphInstance = ref<string | null>(null)
watch(selected, value => { graphAssistant.value = value === 'all' ? null : value; graphInstance.value = null })
async function loadFlow() {
  try { flowRaw.value = await getDatacenterDbFlow() } catch { /* 关联图缺失不阻断总览 */ }
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const [o, b] = await Promise.all([getDatacenterOverview(), getDatacenterBackups()])
    overview.value = o
    backups.value = b
    try {
      pgBackup.value = (await getDatacenterFile('_datacenter/pg_backup.json')).data as typeof pgBackup.value
    } catch { pgBackup.value = null }
  } catch (e) {
    if (!silent) ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function onAction(command: string) {
  busy.value = command
  try {
    if (command === 'scan') { await refreshDatacenterScan(); await load(true); ElMessage.success('已重新扫描数据资产') }
    else if (command === 'sync') { const res = await runDatacenterDbSync(); ElMessage.success(res.message || '已发出同步指令') }
    else if (command === 'backup') { const res = await runDatacenterBackup(); ElMessage.success(res.message || '已发出备份指令'); await load(true) }
    else if (command === 'directory') { await loadScope(); ElMessage.success('助手目录已刷新') }
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  } finally {
    busy.value = ''
  }
}

function inspect(id: string) { selected.value = id; tab.value = 'storage' }

onMounted(() => {
  load()
  loadScope()
  loadFlow()
  timer = window.setInterval(() => { load(true); if (tab.value === 'overview') loadFlow() }, 30000)
})
onBeforeUnmount(() => { if (timer) window.clearInterval(timer) })

const tabs: { key: Tab; label: string; hint: string }[] = [
  { key: 'overview', label: '总览', hint: '资产规模、入库进度、分级' },
  { key: 'storage', label: '存储对应', hint: '每项数据存在哪里' },
  { key: 'dashboard', label: '数据看板', hint: '业务规模、趋势、备份健康' },
  { key: 'browse', label: '原始数据', hint: '只读浏览 · 脱敏 · 留痕' },
  { key: 'api', label: '数据接口', hint: '业务系统取数与密钥' },
  { key: 'databases', label: '数据库', hint: '实例浏览与实时流向' },
  { key: 'ops', label: '运维保障', hint: '备份、同步、容量、服务' },
]
</script>

<template>
  <section class="dc" v-loading="loading && !overview">
    <header class="dc-head">
      <div class="dc-head__title">
        <h1>数据中台</h1>
        <p>统一数据平台 · 业务数据只读 · 浏览与下载均留痕</p>
      </div>
      <div class="dc-head__tools">
        <el-select v-model="selected" filterable class="dc-subject" placeholder="选择助手或平台" aria-label="选择助手或平台" data-testid="dc-subject-select">
          <el-option label="全局总览 · 全部助手与平台" value="all" />
          <el-option-group label="助手">
            <el-option v-for="item in assistantOptions" :key="item.id" :label="item.label" :value="item.id" />
          </el-option-group>
          <el-option-group v-if="platformOption" label="平台">
            <el-option :label="platformOption.label" :value="platformOption.id" />
          </el-option-group>
        </el-select>
        <el-dropdown trigger="click" @command="onAction">
          <el-button type="primary" :loading="!!busy" data-testid="dc-actions">操作<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="scan">重新扫描数据资产</el-dropdown-item>
              <el-dropdown-item command="sync">立即同步入库（镜像层）</el-dropdown-item>
              <el-dropdown-item command="backup" divided>备份整个平台</el-dropdown-item>
              <el-dropdown-item command="directory" divided>刷新助手目录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>
    <p v-if="scopeError" class="dc-alert" role="alert">{{ scopeError }}，请通过「操作 › 刷新助手目录」重试。</p>
    <div v-if="scoped" class="dc-scope" data-testid="dc-scope">
      <span>当前视角</span><b>{{ subjectLabel }}</b><em>所有页签只显示与它相关的数据</em>
      <button type="button" @click="selected = 'all'">返回全局总览</button>
    </div>

    <div v-if="overview" class="dc-kpis">
      <article class="dc-kpi">
        <span>本地文件资产</span>
        <strong>{{ fmtBytes(overview.scan.total_bytes) }}</strong>
        <small>{{ overview.scan.total_files.toLocaleString() }} 个文件 · {{ overview.scan.user_count }} 个用户目录 · 不含数据库容量</small>
      </article>
      <article class="dc-kpi" :class="{ good: cutover.total && cutover.done === cutover.total }">
        <span>助手切库进度</span>
        <strong>{{ cutover.done }}<i>/ {{ cutover.total }}</i></strong>
        <small>业务主存储已在数据库 · 镜像与备份不算切库</small>
      </article>
      <article class="dc-kpi" :class="servicesUp.up === servicesUp.total ? 'good' : 'warn'">
        <span>数据服务在线</span>
        <strong>{{ servicesUp.up }}<i>/ {{ servicesUp.total }}</i></strong>
        <small>已登记的数据库与服务容器</small>
      </article>
      <article class="dc-kpi" :class="backupHealthy && lastSync?.ok ? 'good' : 'warn'">
        <span>备份 · 入库同步</span>
        <strong>{{ backupHealthy ? '正常' : lastRun ? '失败' : '暂无' }}</strong>
        <small>备份 {{ fmtTime(lastRun?.finished_at) }} · 同步 {{ lastSync ? (lastSync.ok ? '一致' : '有差异') : '暂无' }} {{ fmtTime(lastSync?.finished_at) }}</small>
      </article>
    </div>

    <nav class="dc-tabs" aria-label="数据中台页签">
      <button v-for="t in tabs" :key="t.key" type="button" :class="{ active: tab === t.key }" :title="t.hint" :data-tab="t.key" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <!-- ============ 总览 ============ -->
    <template v-if="tab === 'overview' && overview">
      <StorageStatusSummary v-if="storage" @inspect="inspect" />
      <section v-if="flowSnap" class="dc-card dc-graph" data-testid="dc-graph">
        <h3>助手与数据库关联图<small>上排助手 · 下排数据库实例 · 采样于 {{ fmtTime(flowSnap.sampled_at) }}</small><button type="button" @click="tab = 'databases'; dbView = 'flow'">实时流向与告警 →</button></h3>
        <RelationGraph :snap="flowSnap" v-model:assistant="graphAssistant" v-model:instance="graphInstance" />
      </section>
      <section v-if="scoped && subject" class="dc-card dc-owner" :data-owner="subject.id">
        <div>
          <h3>{{ subject.label }}</h3>
          <p>{{ subject.items.length }} 类已登记数据 · 数据库 {{ subject.items.filter(row => row.mode === 'database').length }} · 文件 {{ subject.items.filter(row => row.mode === 'file').length }} · 对象存储 {{ subject.items.filter(row => row.mode === 'object').length }} · 待核验 {{ subject.items.filter(row => ['external', 'unknown'].includes(row.mode)).length }} · 关联实例 {{ subject.instances.length }} 个</p>
        </div>
        <div class="dc-owner__links">
          <button type="button" @click="tab = 'storage'">查看数据对应 →</button>
          <button type="button" @click="tab = 'databases'">查看关联数据库 →</button>
        </div>
      </section>
      <div v-if="!scoped" class="dc-levels">
        <article v-for="c in levelCards" :key="c.lv" class="dc-card dc-level" :style="{ '--c': c.color }">
          <header><i>{{ c.lv }}</i><b>{{ c.name }}</b></header>
          <strong>{{ fmtBytes(c.bytes) }}</strong>
          <span>{{ c.files.toLocaleString() }} 个文件 · {{ c.modules }} 类</span>
          <em>{{ c.backup }}</em>
        </article>
        <article class="dc-card dc-level dc-level--sum">
          <header><b>本地文件合计</b></header>
          <strong>{{ fmtBytes(overview.scan.total_bytes) }}</strong>
          <span>{{ overview.scan.total_files.toLocaleString() }} 个文件</span>
          <em>扫描于 {{ fmtTime(overview.scan.generated_at) }} · 已切库助手的原目录为切换前快照</em>
        </article>
      </div>
      <div class="dc-grid">
        <section class="dc-card dc-table">
          <h3><el-icon><FolderOpened /></el-icon>相关本地模块<small>{{ scopeModules.length }} 类 · 文件扫描口径</small></h3>
          <el-table :data="scopeModules" size="small" max-height="440" empty-text="暂无独立文件统计；不表示没有数据，请查看存储对应">
            <el-table-column label="模块" prop="module" min-width="200" />
            <el-table-column label="级别" width="80">
              <template #default="{ row }"><span class="dc-lv" :style="{ background: LEVEL_COLORS[row.level] }">{{ row.level }}</span></template>
            </el-table-column>
            <el-table-column label="大小" width="110" align="right"><template #default="{ row }">{{ fmtBytes(row.bytes) }}</template></el-table-column>
            <el-table-column label="文件数" width="100" align="right"><template #default="{ row }">{{ row.files.toLocaleString() }}</template></el-table-column>
          </el-table>
        </section>
        <section v-if="!scoped" class="dc-card dc-table">
          <h3><el-icon><DataAnalysis /></el-icon>数据量最大的用户<small>含邮件缓存等 D 级数据 · 仅用于容量管理</small></h3>
          <el-table :data="overview.scan.users_top" size="small" max-height="440">
            <el-table-column label="用户目录" prop="user" min-width="140" />
            <el-table-column label="大小" width="110" align="right"><template #default="{ row }">{{ fmtBytes(row.bytes) }}</template></el-table-column>
            <el-table-column label="文件数" width="100" align="right"><template #default="{ row }">{{ row.files.toLocaleString() }}</template></el-table-column>
          </el-table>
        </section>
      </div>
    </template>

    <template v-if="storage">
      <StorageMapTab v-if="tab === 'storage'" :key="selected" />
      <DashboardTab v-if="tab === 'dashboard'" :key="selected" />
      <BrowseTab v-if="tab === 'browse'" :key="selected" />
      <ApiTab v-if="tab === 'api'" :key="selected" />
      <template v-if="tab === 'databases'">
        <div class="dc-switch" role="tablist">
          <button type="button" role="tab" :aria-selected="dbView === 'instances'" :class="{ active: dbView === 'instances' }" @click="dbView = 'instances'">实例浏览</button>
          <button type="button" role="tab" :aria-selected="dbView === 'flow'" :class="{ active: dbView === 'flow' }" @click="dbView = 'flow'">实时流向</button>
        </div>
        <DatabasesTab v-if="dbView === 'instances'" :key="selected" />
        <DataFlowTab v-else :key="selected" />
      </template>
    </template>

    <!-- ============ 运维保障 ============ -->
    <template v-if="tab === 'ops' && overview && backups">
      <div class="dc-banner" :class="backupHealthy ? 'ok' : 'warn'">
        <b>{{ backupHealthy ? '最近一次备份成功' : (lastRun ? '最近一次备份失败' : '尚无备份记录') }}</b>
        <template v-if="lastRun">
          <span>{{ fmtTime(lastRun.finished_at) }} · {{ fmtBytes(lastRun.bytes) }} · {{ lastRun.entries?.toLocaleString() }} 项 · 用时 {{ lastRun.duration_seconds }}s</span>
          <span v-if="lastRun.error" class="dc-err">{{ lastRun.error }}</span>
        </template>
        <span class="dc-banner__side">
          备份服务 <i :class="heartbeatOk ? 'up' : 'down'" />{{ heartbeatOk ? '在线' : '离线' }}
          · 每日 {{ backups.status.daily_at || '02:30' }} · 保留 {{ backups.status.keep || 14 }} 份
          <template v-if="backups.pending_trigger"> · 手动备份排队中…</template>
        </span>
      </div>
      <div class="dc-ops-grid">
        <section class="dc-card dc-disk">
          <h3>业务数据盘 <small>/home</small></h3>
          <el-progress :percentage="diskPercent" :stroke-width="12" :show-text="false" :color="diskPercent > 85 ? '#d14343' : '#15499c'" />
          <p><b>{{ fmtBytes((overview.disk.used ?? overview.disk.total - overview.disk.free)) }}</b> / {{ fmtBytes(overview.disk.total) }} · 剩余 {{ fmtBytes(overview.disk.free) }}</p>
        </section>
        <section class="dc-card dc-disk">
          <h3>备份盘 <small>/srv/office-backups</small></h3>
          <template v-if="backupDisk">
            <el-progress :percentage="Math.round(((backupDisk.total - backupDisk.free) / backupDisk.total) * 100)" :stroke-width="12" :show-text="false" color="#0e8f7e" />
            <p>剩余 <b>{{ fmtBytes(backupDisk.free) }}</b> · {{ backupDisk.archives ?? 0 }} 份归档（{{ fmtBytes(backupDisk.archives_bytes) }}）</p>
          </template>
          <p v-else class="dc-note">等待备份服务上报状态…</p>
        </section>
        <section class="dc-card dc-disk">
          <h3>统一库入库同步 <small>office-postgres 镜像层</small></h3>
          <p v-if="lastSync" :class="lastSync.ok ? 'dc-ok' : 'dc-warn'">
            {{ lastSync.ok ? '最近同步成功，行数核验一致' : '最近同步存在差异或失败' }}<br />
            <span>{{ fmtTime(lastSync.finished_at) }} · {{ lastSync.rows_total?.toLocaleString() }} 行 · {{ lastSync.duration_seconds }}s · 每日随备份自动同步</span>
          </p>
          <p v-else class="dc-warn">尚未同步</p>
          <p class="dc-note">PostgreSQL 原生备份：{{ pgBackup?.state === 'complete' ? `已完成 · ${fmtTime(pgBackup.finished_at)} · ${fmtBytes(pgBackup.bytes)}` : pgBackup?.state === 'running' ? '备份中…' : pgBackup?.state === 'failed' ? '失败，自动重试中' : '等待入库完成' }}</p>
        </section>
      </div>
      <div class="dc-copies">
        <article v-for="c in backups.copies" :key="c.name" class="dc-card dc-copy" :class="c.state">
          <b>{{ c.name }}</b>
          <span v-if="c.target">{{ c.target }}</span>
          <em>{{ c.note }}</em>
          <i>{{ c.state === 'enabled' ? '已启用' : '待接入' }}</i>
        </article>
      </div>
      <div class="dc-grid">
        <section class="dc-card dc-table">
          <h3><el-icon><Coin /></el-icon>备份记录</h3>
          <el-table :data="backups.runs" size="small" max-height="360">
            <el-table-column label="时间" width="150"><template #default="{ row }">{{ fmtTime(row.finished_at || row.started_at) }}</template></el-table-column>
            <el-table-column label="结果" width="70">
              <template #default="{ row }"><span class="dc-lv" :style="{ background: row.ok ? '#12805c' : '#d14343' }">{{ row.ok ? '成功' : '失败' }}</span></template>
            </el-table-column>
            <el-table-column label="触发" width="90">
              <template #default="{ row }">{{ row.reason === 'daily' ? '每日自动' : row.reason === 'startup' ? '启动补备' : row.reason?.startsWith('manual') ? '手动' : row.reason }}</template>
            </el-table-column>
            <el-table-column label="大小" width="90" align="right"><template #default="{ row }">{{ fmtBytes(row.bytes) }}</template></el-table-column>
            <el-table-column label="归档文件 / 错误" min-width="200">
              <template #default="{ row }"><span :class="{ 'dc-err': !row.ok }">{{ row.ok ? row.archive : row.error }}</span></template>
            </el-table-column>
          </el-table>
        </section>
        <section class="dc-card dc-table">
          <h3>{{ scoped ? '当前对象相关镜像表' : '镜像表核验' }}<small>共享表行数为全表值</small></h3>
          <el-table v-if="lastSync?.tables" :data="scopeTables" size="small" max-height="360" empty-text="暂无相关镜像表；数据库主存储见数据库页签">
            <el-table-column label="数据库表" prop="table" min-width="200" />
            <el-table-column label="入库行数" width="100" align="right"><template #default="{ row }">{{ row.rows.toLocaleString() }}</template></el-table-column>
            <el-table-column label="源记录数" width="100" align="right"><template #default="{ row }">{{ row.source.toLocaleString() }}</template></el-table-column>
            <el-table-column label="核验" width="80">
              <template #default="{ row }"><span class="dc-lv" :style="{ background: row.match ? '#12805c' : '#d14343' }">{{ row.match ? '一致' : '不一致' }}</span></template>
            </el-table-column>
          </el-table>
        </section>
      </div>
      <div class="dc-grid">
        <section class="dc-card dc-table">
          <h3>关联数据服务状态</h3>
          <el-table :data="scopeServices" size="small" empty-text="暂无已登记服务；不代表无本地或外部数据">
            <el-table-column label="服务" prop="key" width="170" />
            <el-table-column label="说明" prop="label" min-width="220" />
            <el-table-column label="级别" width="70">
              <template #default="{ row }"><span class="dc-lv" :style="{ background: LEVEL_COLORS[row.level] || '#64748b' }">{{ row.level }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><span class="dc-dot" :class="row.status" />{{ row.status === 'up' ? '运行中' : '不可达' }}</template>
            </el-table-column>
          </el-table>
        </section>
        <section class="dc-card dc-table">
          <h3>平台迁移路线</h3>
          <ol class="dc-steps">
            <li v-for="m in migrationSteps" :key="m.step" :class="m.status"><b>{{ m.step }}</b><span>{{ m.note }}</span></li>
          </ol>
        </section>
      </div>
      <details class="dc-fold">
        <summary>备份与同步口径说明</summary>
        <p>备份内容：核心业务数据（A）与用户文件（B）+ 账号配置 + 部署文件快照；不含邮件缓存等可重建数据，不含密钥文件。恢复在服务器上执行并先入沙箱核对，页面不提供在线恢复。</p>
        <p>备份记录、主机磁盘与整体同步结果是平台级信息，不是单个助手的独立备份或容量。外部服务（FastGPT、RAGFlow 等）须核验自身备份，在线不等于已备份。</p>
        <p>镜像层按表提交，不是全平台同一时点快照；已切库助手的业务主存储在 app.* 表，镜像表仅供统一查询。迁移副本含完整配置，仅供管理员受控导出与还原。</p>
        <p v-if="lastSync?.file_archive">可迁移文件快照：{{ lastSync.file_archive.files.toLocaleString() }} 个文件 · {{ fmtBytes(lastSync.file_archive.bytes) }} · {{ lastSync.file_archive.sqlite_snapshots }} 个 SQLite 一致性快照 · 版本 {{ lastSync.file_archive.id.slice(0, 12) }}</p>
        <p v-if="lastSync?.error" class="dc-warn">{{ lastSync.error }}</p>
        <p v-if="lastSync?.document_parse_errors" class="dc-warn">{{ lastSync.document_parse_errors }} 个原始文档无法解析为 JSON，已完整保存原始字节，待检查。</p>
      </details>
    </template>
  </section>
</template>

<style scoped lang="scss">
.dc { display: flex; flex-direction: column; gap: 14px; --dc-border: #e3ebf7; --dc-ink: #0b2458; --dc-muted: #6b7a93; }
.dc-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  &__title { h1 { font-size: 24px; color: var(--dc-ink); letter-spacing: .2px; } p { color: var(--dc-muted); font-size: 12.5px; margin-top: 2px; } }
  &__tools { display: flex; align-items: center; gap: 10px; }
}
.dc-subject { width: 260px; }
.dc-alert { font-size: 12.5px; color: #b42318; background: #fef3f2; border: 1px solid #fecdca; border-radius: 10px; padding: 8px 12px; }
.dc-scope { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 8px 14px; border-radius: 10px; background: #edf4ff; border: 1px solid #cddcf7; font-size: 12.5px;
  span { color: #4c6a99; } b { color: var(--dc-ink); font-size: 14px; } em { font-style: normal; color: var(--dc-muted); }
  button { margin-left: auto; border: 0; background: transparent; color: #15499c; font-weight: 600; cursor: pointer; font-size: 12.5px; &:hover { text-decoration: underline; } }
}
.dc-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.dc-kpi { background: #fff; border: 1px solid var(--dc-border); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; position: relative; overflow: hidden;
  &::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: #94a3b8; }
  &.good::before { background: #12805c; } &.warn::before { background: #d9822b; }
  span { font-size: 12px; color: var(--dc-muted); }
  strong { font-size: 24px; color: var(--dc-ink); font-variant-numeric: tabular-nums; line-height: 1.15; i { font-style: normal; font-size: 14px; color: var(--dc-muted); margin-left: 4px; font-weight: 500; } }
  small { font-size: 11.5px; color: #8c9ab3; line-height: 1.5; }
}
.dc-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--dc-border); overflow-x: auto;
  button { flex: none; border: 0; background: transparent; padding: 10px 14px; font-size: 14px; color: #4c5b75; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color .15s, border-color .15s;
    &:hover { color: var(--dc-ink); } &.active { color: #15499c; font-weight: 700; border-bottom-color: #15499c; } }
}
.dc-switch { display: inline-flex; padding: 3px; background: #edf1f8; border-radius: 10px; align-self: flex-start;
  button { border: 0; background: transparent; padding: 6px 16px; border-radius: 8px; font-size: 13px; color: #4c5b75; cursor: pointer;
    &.active { background: #fff; color: #15499c; font-weight: 700; box-shadow: 0 1px 4px rgba(15, 35, 72, .12); } }
}
.dc-card { background: #fff; border: 1px solid var(--dc-border); border-radius: 14px; }
.dc-graph { padding: 14px 16px;
  h3 { display: flex; align-items: center; gap: 8px; font-size: 14.5px; color: var(--dc-ink); margin-bottom: 10px; small { font-weight: 400; font-size: 12px; color: #8c9ab3; }
    button { margin-left: auto; border: 0; background: transparent; color: #15499c; font-weight: 600; cursor: pointer; font-size: 12.5px; &:hover { text-decoration: underline; } } } }
.dc-owner { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 18px;
  h3 { color: var(--dc-ink); font-size: 16px; } p { font-size: 12.5px; color: var(--dc-muted); margin-top: 4px; }
  &__links { display: flex; gap: 14px; button { border: 0; background: transparent; color: #15499c; font-weight: 600; cursor: pointer; font-size: 13px; &:hover { text-decoration: underline; } } }
}
.dc-levels { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.dc-level { padding: 14px 16px; border-top: 3px solid var(--c, #15499c);
  header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    i { width: 24px; height: 24px; border-radius: 7px; background: var(--c); color: #fff; font-style: normal; font-weight: 800; font-size: 12px; display: inline-flex; align-items: center; justify-content: center; }
    b { color: #14213d; font-size: 13.5px; } }
  strong { font-size: 22px; color: var(--dc-ink); }
  span { display: block; font-size: 12px; color: var(--dc-muted); margin-top: 2px; }
  em { display: block; font-style: normal; font-size: 11.5px; color: #8c9ab3; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #e8eef7; }
  &--sum { border-top-color: #15499c; background: linear-gradient(180deg, #f7faff, #fff); }
}
.dc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; > * { min-width: 0; } }
.dc-table { padding: 14px 16px;
  h3 { display: flex; align-items: center; gap: 8px; font-size: 14.5px; color: var(--dc-ink); margin-bottom: 10px; small { font-weight: 400; font-size: 12px; color: #8c9ab3; margin-left: 4px; } }
}
.dc-lv { display: inline-block; min-width: 26px; text-align: center; padding: 1px 8px; border-radius: 6px; color: #fff; font-size: 12px; font-weight: 700; }
.dc-note { margin-top: 8px; font-size: 12px; color: #8c9ab3; line-height: 1.6; }
.dc-ok { color: #0e7a55; font-size: 13px; font-weight: 600; span { font-weight: 400; color: var(--dc-muted); font-size: 12px; } }
.dc-warn { color: #a8610e; font-size: 13px; font-weight: 600; span { font-weight: 400; color: var(--dc-muted); font-size: 12px; } }
.dc-err { color: #d14343; }
.dc-banner { border-radius: 12px; padding: 12px 16px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; border: 1px solid;
  b { font-size: 15px; } span { font-size: 12.5px; color: #475569; }
  &.ok { background: #e9f7f0; border-color: #b9e3d0; b { color: #0e7a55; } }
  &.warn { background: #fdf3e6; border-color: #f0d3a3; b { color: #a8610e; } }
  &__side { margin-left: auto; i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin: 0 4px; &.up { background: #12805c; } &.down { background: #d14343; } } }
}
.dc-ops-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; > * { min-width: 0; } }
.dc-disk { padding: 14px 16px; h3 { font-size: 14px; color: var(--dc-ink); margin-bottom: 10px; small { font-weight: 400; color: #8c9ab3; font-family: monospace; font-size: 11.5px; margin-left: 6px; } } p { margin-top: 8px; font-size: 13px; color: #475569; b { color: var(--dc-ink); } } }
.dc-copies { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.dc-copy { padding: 12px 16px; position: relative;
  b { display: block; color: #14213d; font-size: 13.5px; } span { font-size: 12px; color: #15499c; font-family: monospace; }
  em { display: block; font-style: normal; font-size: 12px; color: var(--dc-muted); margin-top: 6px; }
  i { position: absolute; right: 14px; top: 12px; font-style: normal; font-size: 11.5px; font-weight: 700; padding: 2px 10px; border-radius: 99px; }
  &.enabled i { color: #0e7a55; background: #e2f4ec; }
  &.todo { opacity: .8; i { color: #55647e; background: #eef2f6; } }
}
.dc-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; &.up { background: #12805c; } &.down { background: #d14343; } }
.dc-steps { list-style: none; display: flex; flex-direction: column; gap: 8px;
  li { padding: 9px 14px; border-radius: 10px; background: #f6f9fe; border-left: 3px solid #c9d6ea;
    b { display: block; font-size: 13px; color: #14213d; } span { font-size: 12px; color: var(--dc-muted); }
    &.done { border-left-color: #12805c; background: #f0faf5; } }
}
.dc-fold { font-size: 12.5px; color: var(--dc-muted); padding: 4px 6px;
  summary { cursor: pointer; color: #15499c; font-weight: 600; } p { margin: 8px 0 0; line-height: 1.7; } }
@media (max-width: 1100px) { .dc-levels, .dc-kpis { grid-template-columns: repeat(2, 1fr); } .dc-grid, .dc-ops-grid, .dc-copies { grid-template-columns: 1fr; } .dc-subject { width: 200px; } }
</style>
