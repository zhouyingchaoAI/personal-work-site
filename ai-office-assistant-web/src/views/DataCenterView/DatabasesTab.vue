<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretRight, Refresh, Search } from '@element-plus/icons-vue'
import {
  getDatacenterDatabases, getDatacenterDbObjects, getDatacenterDbRows, runDatacenterDbQuery, getDatacenterDbFlowTables,
  type DatacenterDbInstance, type DatacenterDbObjects, type DatacenterDbRows,
} from '../../services/personalWorkApi'
import { DB_CATEGORIES, DB_CATEGORY_ORDER, dbCategory } from './dbCategories'
import { useSubjectScope } from './subjectScope'

const scope = useSubjectScope()
const visibleInstances = computed(() => instances.value.filter(item => !scope.scoped.value || scope.subject.value?.instances.includes(item.id)))
const ownershipNote = ref('')
let objectRequest = 0
let rowsRequest = 0
const instances = ref<DatacenterDbInstance[]>([])
const loadingInstances = ref(false)
const current = ref<DatacenterDbInstance | null>(null)
const objects = ref<DatacenterDbObjects | null>(null)
const loadingObjects = ref(false)
const db = ref('')
const pattern = ref('*')
const objectName = ref('')
const rowsData = ref<DatacenterDbRows | null>(null)
const loadingRows = ref(false)
const page = ref(0)
const mongoFilter = ref('')
const sql = ref('')
const sqlResult = ref<DatacenterDbRows | null>(null)
const runningSql = ref(false)

const KIND_NAMES: Record<string, string> = {
  postgres: 'PostgreSQL', mysql: 'MySQL', sqlite: 'SQLite', mongodb: 'MongoDB', redis: 'Redis',
  elasticsearch: 'Elasticsearch', qdrant: 'Qdrant', neo4j: 'Neo4j',
}
const systems = computed(() => {
  const groups = new Map<string, DatacenterDbInstance[]>()
  for (const inst of visibleInstances.value) {
    if (!groups.has(inst.system)) groups.set(inst.system, [])
    groups.get(inst.system)!.push(inst)
  }
  return [...groups.entries()]
})

function fmtBytes(n?: number | null) {
  if (!n && n !== 0) return ''
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(n / 1024)} KB`
}

async function loadInstances() {
  loadingInstances.value = true
  try {
    instances.value = (await getDatacenterDatabases()).instances
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '读取实例清单失败')
  } finally {
    loadingInstances.value = false
  }
}

async function openInstance(inst: DatacenterDbInstance, keepDb = false) {
  const requestId = ++objectRequest
  ++rowsRequest
  current.value = inst
  objects.value = null
  ownershipNote.value = ''
  loadingObjects.value = false
  loadingRows.value = false
  if (!keepDb) { db.value = ''; pattern.value = '*' }
  objectName.value = ''
  rowsData.value = null
  sqlResult.value = null
  if (inst.status !== 'up' || inst.kind === 'minio') { objects.value = null; return }
  loadingObjects.value = true
  try {
    if (scope.scoped.value) {
      const result = await getDatacenterDbFlowTables(scope.selected.value, inst.id)
      if (requestId !== objectRequest) return
      objects.value = { ok: true, databases: [], objects: result.objects, rows_label: result.rows_label }
      ownershipNote.value = result.note
    } else {
      const result = await getDatacenterDbObjects(inst.id, db.value, pattern.value)
      if (requestId !== objectRequest) return
      objects.value = result
    }
    if (objects.value.current_db) db.value = objects.value.current_db
  } catch (e) {
    if (requestId !== objectRequest) return
    objects.value = null
    ElMessage.error(e instanceof Error ? e.message : '读取对象清单失败')
  } finally {
    if (requestId === objectRequest) loadingObjects.value = false
  }
}

async function openObject(name: string, toPage = 0) {
  if (!current.value) return
  const requestId = ++rowsRequest
  objectName.value = name
  page.value = toPage
  loadingRows.value = true
  try {
    const result = await getDatacenterDbRows(current.value.id, db.value, name, toPage, 50, mongoFilter.value)
    if (requestId === rowsRequest) rowsData.value = result
  } catch (e) {
    if (requestId !== rowsRequest) return
    rowsData.value = null
    ElMessage.error(e instanceof Error ? e.message : '读取数据失败')
  } finally {
    if (requestId === rowsRequest) loadingRows.value = false
  }
}

async function runSql() {
  if (!current.value || !sql.value.trim()) return
  runningSql.value = true
  try {
    sqlResult.value = await runDatacenterDbQuery(current.value.id, db.value, sql.value)
  } catch (e) {
    sqlResult.value = null
    ElMessage.error(e instanceof Error ? e.message : '查询失败')
  } finally {
    runningSql.value = false
  }
}

function cellText(value: unknown) {
  if (value === null || value === undefined) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

onMounted(loadInstances)
</script>

<template>
  <div class="dbx">
    <section class="dbx-card" v-loading="loadingInstances">
      <header class="dbx-head">
        <h4>{{ scope.label.value }} · 关联实例（{{ visibleInstances.length }} 个 · 只读）</h4>
        <el-button size="small" :icon="Refresh" @click="loadInstances">刷新状态</el-button>
      </header>
      <div class="dbx-cats">
        <span v-for="key in DB_CATEGORY_ORDER" :key="key">
          <i :style="{ background: DB_CATEGORIES[key].color }" />{{ DB_CATEGORIES[key].label }}
        </span>
      </div>
      <p v-if="!visibleInstances.length" class="dbx-note">暂无已接入的关联数据库；请查看存储对应中的本地文件或外部服务。</p>
      <p class="dbx-note">{{ scope.scoped.value ? '仅列当前对象相关表；共享表内容仍可能跨助手，不等于行级隔离。' : '全局实例目录。选择助手后，只显示其关联实例与数据表。' }}</p>
      <div v-for="[system, list] in systems" :key="system" class="dbx-group">
        <span class="dbx-sys">{{ system }}</span>
        <div class="dbx-insts">
        <button v-for="inst in list" :key="inst.id" class="dbx-inst"
                :class="{ active: current?.id === inst.id, down: inst.status !== 'up' }"
                :style="{ borderLeft: `4px solid ${dbCategory(inst.category).color}` }"
                @click="openInstance(inst)">
          <i class="dbx-dot" :class="inst.status" />
          <b>{{ inst.label }}</b>
          <span>{{ inst.version || KIND_NAMES[inst.kind] || inst.kind }}<template v-if="inst.detail"> · {{ inst.detail }}</template></span>
          <em>{{ inst.location }}</em>
          <u class="dbx-cat" :style="{ color: dbCategory(inst.category).color }">{{ dbCategory(inst.category).label }}</u>
        </button>
        </div>
      </div>
      <p class="dbx-note">密码等敏感字段自动脱敏；每次浏览与查询均写入访问留痕。SQL 查询仅支持只读语句（SELECT / SHOW / EXPLAIN）。</p>
    </section>

    <section v-if="current" class="dbx-card" v-loading="loadingObjects">
      <header class="dbx-head">
        <h4>{{ current.label }} <el-tag size="small">{{ KIND_NAMES[current.kind] || current.kind }}</el-tag></h4>
        <div class="dbx-tools">
          <el-select v-if="objects && objects.databases.length > 1" v-model="db" size="small" style="width: 160px"
                     @change="openInstance(current!, true)">
            <el-option v-for="d in objects.databases" :key="d" :label="d" :value="d" />
          </el-select>
          <template v-if="current.kind === 'redis' && !scope.scoped.value">
            <el-input v-model="pattern" size="small" placeholder="键名匹配，如 celery*" style="width: 200px"
                      @keyup.enter="openInstance(current!, true)" />
            <el-button size="small" :icon="Search" @click="openInstance(current!, true)">扫描</el-button>
          </template>
        </div>
      </header>
      <p v-if="current.status !== 'up'" class="dbx-warn">实例当前不可达（{{ current.status === 'auth-error' ? '连接或认证失败' : '端口探测失败' }}）。</p>
      <p v-else-if="current.kind === 'minio'" class="dbx-note">对象存储保存附件等文件本体，仅做健康探测，不提供内容浏览；文件索引可在「原始数据」页签查看。</p>
      <template v-else-if="objects">
        <p class="dbx-note">{{ ownershipNote }}</p>
        <div v-if="objects.summary" class="dbx-summary">
          <span v-for="(v, k) in objects.summary" :key="k">{{ k }}：<b>{{ v }}</b></span>
        </div>
        <div class="dbx-objects">
          <button v-for="o in objects.objects" :key="o.name" :class="{ active: objectName === o.name }"
                  @click="openObject(o.name)">
            {{ o.name }}
            <i v-if="o.rows !== null && o.rows !== undefined">{{ o.rows.toLocaleString() }}{{ objects.rows_label ? ' ' + objects.rows_label : '' }}</i>
            <i v-if="o.size">{{ fmtBytes(o.size) }}</i>
            <u v-if="o.kind_label && o.kind_label !== '表'">{{ o.kind_label }}</u>
          </button>
        </div>
        <p v-if="!objects.objects.length" class="dbx-note">没有可浏览的对象。</p>
      </template>

      <div v-if="objectName" class="dbx-rows" v-loading="loadingRows">
        <div v-if="current.kind === 'mongodb'" class="dbx-filter">
          <el-input v-model="mongoFilter" size="small" placeholder='过滤条件（JSON），如 {"status":"active"}'
                    @keyup.enter="openObject(objectName)" />
          <el-button size="small" @click="openObject(objectName)">应用</el-button>
        </div>
        <template v-if="rowsData">
          <el-table :data="rowsData.rows" size="small" max-height="420" border>
            <el-table-column v-for="c in rowsData.columns" :key="c" :label="c" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ cellText(row[c]) }}</template>
            </el-table-column>
          </el-table>
          <div class="dbx-page">
            <el-button size="small" :disabled="!page" @click="openObject(objectName, page - 1)">上一页</el-button>
            <span>第 {{ page + 1 }} 页<template v-if="rowsData.total !== null && rowsData.total !== undefined"> · 共 {{ rowsData.total.toLocaleString() }} 条</template></span>
            <el-button size="small" :disabled="rowsData.rows.length < 50" @click="openObject(objectName, page + 1)">下一页</el-button>
            <span v-if="rowsData.note" class="dbx-note">{{ rowsData.note }}</span>
          </div>
        </template>
      </div>

      <p v-if="scope.scoped.value && current.queryable" class="dbx-note">自由 SQL 可跨业务表，已在助手视角隐藏；如需查询整个实例，请切换“全局总览”。筛选不是权限边界。</p>
      <div v-if="!scope.scoped.value && current.queryable && current.status === 'up'" class="dbx-sql">
        <h5>只读 SQL 查询</h5>
        <el-input v-model="sql" type="textarea" :rows="3"
                  :placeholder="`例如：SELECT * FROM ${objects?.objects?.[0]?.name || 'table'} LIMIT 10`" />
        <div class="dbx-sqlbar">
          <el-button type="primary" size="small" :icon="CaretRight" :loading="runningSql" @click="runSql">执行</el-button>
          <span v-if="sqlResult">{{ sqlResult.rows.length }} 行<template v-if="sqlResult.truncated">（已截断，最多 200 行）</template> · {{ sqlResult.duration_ms }} ms</span>
        </div>
        <el-table v-if="sqlResult && sqlResult.rows.length" :data="sqlResult.rows" size="small" max-height="360" border>
          <el-table-column v-for="c in sqlResult.columns" :key="c" :label="c" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ cellText(row[c]) }}</template>
          </el-table-column>
        </el-table>
        <p v-else-if="sqlResult" class="dbx-note">查询成功，无返回行。</p>
      </div>
    </section>
    <section v-else class="dbx-card dbx-empty">点击上方任一实例开始浏览：支持 PostgreSQL、MySQL、SQLite、MongoDB、Redis、Elasticsearch、Qdrant、Neo4j。</section>
  </div>
</template>

<style scoped lang="scss">
.dbx { display: flex; flex-direction: column; gap: 12px; }
.dbx-card { background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; padding: 14px 16px; }
.dbx-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px;
  h4 { font-size: 14px; color: #0b2458; } }
.dbx-tools { display: flex; gap: 8px; align-items: center; }
.dbx-group { display: grid; grid-template-columns: 84px 1fr; align-items: start; gap: 8px; padding: 8px 0; border-top: 1px dashed #e8eefb;
  &:first-of-type { border-top: 0; } }
.dbx-insts { display: flex; flex-wrap: wrap; gap: 8px; }
.dbx-sys { font-size: 12px; font-weight: 700; color: #64748b; padding-top: 8px; }
.dbx-cats { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: #476299; margin-bottom: 10px;
  i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; } }
.dbx-cat { text-decoration: none; font-size: 11px; font-weight: 600; margin-top: 2px; }
.dbx-inst { display: flex; flex-direction: column; align-items: flex-start; border: 1px solid #dbe7fb; background: #f6f9fe;
  border-radius: 10px; padding: 6px 12px; cursor: pointer; position: relative; min-width: 170px;
  b { font-size: 12.5px; color: #14213d; }
  span { font-size: 11.5px; color: #476299; }
  em { font-style: normal; font-size: 11px; color: #9aa9c6; }
  &.active { background: #15499c; border-color: #15499c; b, span, em { color: #fff; } span { color: #cfe0fa; } em { color: #9db9e8; } }
  &.down { opacity: .6; } }
.dbx-dot { position: absolute; top: 8px; right: 8px; width: 8px; height: 8px; border-radius: 50%;
  &.up { background: #22b573; } &.down { background: #e15656; } &.auth-error { background: #e5a13c; } }
.dbx-note { font-size: 12px; color: #8c9ab3; margin-top: 8px; }
.dbx-warn { font-size: 12.5px; color: #c2571f; padding: 8px 0; }
.dbx-summary { display: flex; gap: 18px; font-size: 12.5px; color: #476299; margin-bottom: 8px; b { color: #0b2458; } }
.dbx-objects { display: flex; flex-wrap: wrap; gap: 8px; max-height: 220px; overflow: auto;
  button { border: 1px solid #dbe7fb; background: #f6f9fe; border-radius: 8px; padding: 4px 10px; font-size: 12.5px; color: #14213d; cursor: pointer;
    i { font-style: normal; color: #64748b; margin-left: 6px; font-size: 11.5px; }
    u { text-decoration: none; margin-left: 6px; font-size: 11px; color: #8a6bd1; }
    &.active { background: #15499c; color: #fff; border-color: #15499c; i, u { color: #cfe0fa; } } } }
.dbx-rows { margin-top: 12px; }
.dbx-filter { display: flex; gap: 8px; margin-bottom: 8px; }
.dbx-page { display: flex; align-items: center; gap: 12px; margin-top: 10px; font-size: 12.5px; color: #64748b; }
.dbx-sql { margin-top: 14px; border-top: 1px dashed #e8eefb; padding-top: 12px;
  h5 { font-size: 13px; color: #0b2458; margin-bottom: 8px; } }
.dbx-sqlbar { display: flex; align-items: center; gap: 12px; margin: 8px 0; font-size: 12.5px; color: #64748b; }
.dbx-empty { padding: 40px 20px; text-align: center; color: #8c9ab3; font-size: 13px; }
</style>
