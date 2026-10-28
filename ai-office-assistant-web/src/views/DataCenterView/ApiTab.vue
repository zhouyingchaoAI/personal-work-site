<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Key, VideoPlay } from '@element-plus/icons-vue'
import {
  createDatacenterApiKey, getDatacenterApiKeys, getDatacenterCatalog, revokeDatacenterApiKey, runDatacenterDataQuery,
  type DatacenterApiKeyInfo, type DatacenterCatalog, type DatacenterDataset,
} from '../../services/personalWorkApi'
import { useSubjectScope } from './subjectScope'

const scope = useSubjectScope()
const catalog = ref<DatacenterCatalog | null>(null)
const keys = ref<DatacenterApiKeyInfo[]>([])
const active = ref<DatacenterDataset | null>(null)
const paramValues = ref<Record<string, string>>({})
const result = ref('')
const resultMeta = ref('')
const running = ref(false)
const newKeyName = ref('')
const creating = ref(false)
const issuedToken = ref('')

const groups = computed(() => {
  const map = new Map<string, DatacenterDataset[]>()
  if (!scope.scoped.value) {
    for (const dataset of catalog.value?.datasets || []) {
      if (!map.has(dataset.group)) map.set(dataset.group, [])
      map.get(dataset.group)!.push(dataset)
    }
    return [...map.entries()].map(([group, items]) => ({ group, items }))
  }
  for (const owner of scope.subjects.value) {
    if (scope.scoped.value && owner.id !== scope.selected.value) continue
    const items = (catalog.value?.datasets || []).filter(item => owner.datasets.includes(item.key))
    if (items.length) map.set(owner.label, items)
  }
  return [...map.entries()].map(([group, items]) => ({ group, items }))
})

function select(d: DatacenterDataset) {
  active.value = d
  paramValues.value = Object.fromEntries(d.params.map(p => [p.name, p.name === 'owner' ? 'zhouyingchao' : p.name === 'limit' ? '20' : p.name === 'source' ? 'database' : '']))
  result.value = ''
  resultMeta.value = ''
}

const curlExample = computed(() => {
  if (!active.value) return ''
  const qs = ['dataset=' + active.value.key,
    ...active.value.params.filter(p => p.required || ['limit', 'source'].includes(p.name)).map(p => `${p.name}=${p.name === 'owner' ? '<用户名>' : p.name === 'limit' ? '20' : p.name === 'source' ? 'database' : '<值>'}`)]
  return `curl -H "X-Data-Api-Key: <你的密钥>" \\\n  "https://office.chencytech.com/api/datacenter/data?${qs.join('&')}"`
})

async function run() {
  if (!active.value) return
  running.value = true
  const started = performance.now()
  try {
    const params = Object.fromEntries(active.value.params
      .filter(p => paramValues.value.source !== 'live' || !p.desc.startsWith('仅 database'))
      .map(p => [p.name, paramValues.value[p.name] || '']))
    const res = await runDatacenterDataQuery(active.value.key, params)
    result.value = JSON.stringify(res, null, 2)
    const total = (res as { total?: number }).total
    const meta = res as { source?: string; synced_at?: string; storage_role?: string }
    resultMeta.value = `${meta.storage_role === 'primary' ? 'PostgreSQL 业务主库' : meta.source === 'postgresql' ? 'PostgreSQL 镜像 · 同步于 ' + meta.synced_at : '实时业务主存储'} · HTTP 200 · 服务端 ${(res as { took_ms?: number }).took_ms ?? '—'} ms · 端到端 ${Math.round(performance.now() - started)} ms${total !== undefined ? ` · 共 ${total} 条` : ''}`
  } catch (e) {
    result.value = e instanceof Error ? e.message : String(e)
    resultMeta.value = '请求失败'
  } finally {
    running.value = false
  }
}

async function loadKeys() { keys.value = (await getDatacenterApiKeys()).keys }

async function createKey() {
  if (!newKeyName.value.trim()) { ElMessage.warning('先给密钥取个名字（如：经营分析看板）'); return }
  creating.value = true
  try {
    const res = await createDatacenterApiKey(newKeyName.value.trim())
    issuedToken.value = res.token
    newKeyName.value = ''
    await loadKeys()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}

async function revoke(k: DatacenterApiKeyInfo) {
  await ElMessageBox.confirm(`吊销后使用「${k.name}」的业务系统将立即无法取数，确定吊销？`, '吊销密钥', { type: 'warning' })
  await revokeDatacenterApiKey(k.id)
  ElMessage.success('已吊销')
  await loadKeys()
}

function copy(text: string) { navigator.clipboard.writeText(text); ElMessage.success('已复制') }

onMounted(async () => {
  try {
    catalog.value = await getDatacenterCatalog()
    const first = groups.value[0]?.items[0]
    if (first) select(first)
    await loadKeys()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  }
})
</script>

<template>
  <div class="ap">
    <div class="ap-intro ap-card">
      <b>统一取数入口：</b>GET <code>/api/datacenter/data?dataset=…</code>，业务系统带请求头
      <code>X-Data-Api-Key</code> 调用。只读，单次最多 {{ catalog?.max_limit || 500 }} 条，敏感字段自动脱敏，每次调用留痕。
      当前对象：{{ scope.label.value }}。CRM 已切换主库；其他数据集的 database 模式可能是定时镜像，以接口来源说明为准。API 密钥属于平台级授权，不受此处的助手显示筛选限制。
    </div>

    <div class="ap-main">
      <aside class="ap-card ap-nav">
        <div v-for="g in groups" :key="g.group" class="ap-group">
          <p>{{ g.group }}</p>
          <button v-for="d in g.items" :key="d.key" :class="{ active: active?.key === d.key }" @click="select(d)">
            <b>{{ d.name }}</b><span>{{ d.key }}</span>
          </button>
        </div>
      </aside>
      <section v-if="!groups.length" class="ap-card">此对象尚无独立的统一取数接口，请查看存储对应或数据库。未提供接口不等于无数据。</section>

      <section v-if="active" class="ap-doc">
        <div class="ap-card">
          <header class="ap-h">
            <div><h3>{{ active.name }}<code>{{ active.key }}</code></h3><p>{{ active.desc }}</p></div>
          </header>
          <p class="ap-src">数据来源：{{ active.source }}<template v-if="active.note">　·　{{ active.note }}</template></p>
          <template v-if="active.typed_fields?.length">
            <h4>结构化表：{{ active.database_table }}</h4>
            <table class="ap-tb">
              <tr><th>查询列</th><th>数据库类型</th><th>原始字段</th></tr>
              <tr v-for="f in active.typed_fields" :key="f.name"><td>{{ f.name }}</td><td>{{ f.type }}</td><td>{{ f.source_field }}</td></tr>
            </table>
          </template>
          <div class="ap-cols">
            <div>
              <h4>请求参数</h4>
              <table class="ap-tb">
                <tr><th>参数</th><th>必填</th><th>说明</th></tr>
                <tr v-for="p in active.params" :key="p.name"><td><code>{{ p.name }}</code></td><td>{{ p.required ? '是' : '否' }}</td><td>{{ p.desc }}</td></tr>
                <tr v-if="!active.params.length"><td colspan="3">无参数</td></tr>
              </table>
            </div>
            <div>
              <h4>返回字段</h4>
              <table class="ap-tb">
                <tr><th>字段</th><th>说明</th></tr>
                <tr v-for="f in active.fields" :key="f[0]"><td><code>{{ f[0] }}</code></td><td>{{ f[1] }}</td></tr>
              </table>
            </div>
          </div>
          <h4>调用示例 <el-button text size="small" :icon="CopyDocument" @click="copy(curlExample)">复制</el-button></h4>
          <pre class="ap-code">{{ curlExample }}</pre>
        </div>

        <div class="ap-card">
          <h4 class="ap-try">在线测试<span>用当前登录身份直接调用，结果即真实返回</span></h4>
          <div class="ap-form">
            <label v-for="p in active.params" :key="p.name">
              <span>{{ p.name }}<i v-if="p.required">*</i></span>
              <el-select v-if="p.name === 'source'" v-model="paramValues[p.name]" size="small">
                <el-option label="数据库镜像（非实时）" value="database" /><el-option label="实时原存储" value="live" />
              </el-select>
              <el-input v-else v-model="paramValues[p.name]" size="small" :placeholder="p.desc" :disabled="paramValues.source === 'live' && p.desc.startsWith('仅 database')" />
            </label>
            <el-button type="primary" size="small" :icon="VideoPlay" :loading="running" @click="run">发送请求</el-button>
          </div>
          <p v-if="resultMeta" class="ap-meta">{{ resultMeta }}</p>
          <pre v-if="result" class="ap-code ap-result">{{ result }}</pre>
        </div>
      </section>

      <aside class="ap-side">
        <div class="ap-card">
          <h4 class="ap-try"><el-icon><Key /></el-icon> API 密钥（发给业务系统）</h4>
          <div class="ap-newkey">
            <el-input v-model="newKeyName" size="small" placeholder="密钥名称，如：经营分析看板" @keyup.enter="createKey" />
            <el-button type="primary" size="small" :loading="creating" @click="createKey">创建</el-button>
          </div>
          <div v-if="issuedToken" class="ap-token">
            <p>新密钥（只显示这一次，立即保存）：</p>
            <code>{{ issuedToken }}</code>
            <el-button text size="small" :icon="CopyDocument" @click="copy(issuedToken)">复制</el-button>
          </div>
          <div v-for="k in keys" :key="k.id" class="ap-key" :class="{ revoked: !!k.revoked_at }">
            <div>
              <b>{{ k.name }}</b>
              <span>{{ k.prefix }} · {{ k.calls || 0 }} 次调用<template v-if="k.last_used_at"> · 最近 {{ k.last_used_at.replace('T', ' ') }}</template></span>
            </div>
            <el-tag v-if="k.revoked_at" type="info" size="small">已吊销</el-tag>
            <el-button v-else text type="danger" size="small" @click="revoke(k)">吊销</el-button>
          </div>
          <p v-if="!keys.length" class="ap-meta">还没有密钥。业务系统接入前先在这里创建。</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss">
.ap { display: flex; flex-direction: column; gap: 12px; }
.ap-card { background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; padding: 14px 16px; }
.ap-intro { font-size: 13px; color: #475569; line-height: 1.7; b { color: #0b2458; }
  code { background: #eef4ff; color: #15499c; padding: 1px 7px; border-radius: 6px; font-size: 12px; } }
.ap-main { display: grid; grid-template-columns: 230px 1fr 320px; gap: 12px; align-items: start; }
.ap-nav { padding: 10px; }
.ap-group { p { font-size: 12px; color: #8c9ab3; font-weight: 700; padding: 8px 8px 4px; }
  button { display: block; width: 100%; text-align: left; border: 0; background: transparent; border-radius: 10px; padding: 7px 10px; cursor: pointer;
    b { display: block; font-size: 13.5px; color: #14213d; } span { font-size: 11.5px; color: #8c9ab3; font-family: monospace; }
    &:hover { background: #f2f7ff; }
    &.active { background: linear-gradient(135deg, #1d5cab, #15499c); b { color: #fff; } span { color: #b9d0f5; } } } }
.ap-doc { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.ap-h { h3 { font-size: 18px; color: #0b2458; display: flex; align-items: center; gap: 10px;
    code { font-size: 12.5px; background: #eef4ff; color: #15499c; padding: 2px 9px; border-radius: 8px; } }
  p { font-size: 13px; color: #64748b; margin-top: 2px; } }
.ap-src { font-size: 12px; color: #8c9ab3; margin: 8px 0 12px; }
.ap-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }
h4 { font-size: 13.5px; color: #0b2458; margin-bottom: 6px; }
.ap-tb { width: 100%; border-collapse: collapse; font-size: 12.5px;
  th { text-align: left; color: #8c9ab3; font-weight: 600; padding: 4px 8px; border-bottom: 1px solid #e5eefa; }
  td { padding: 5px 8px; border-bottom: 1px dashed #eef2f9; color: #334155; vertical-align: top;
    code { color: #15499c; } }
  i { color: #d14343; font-style: normal; } }
.ap-code { background: #0f2348; color: #d6e4fb; border-radius: 12px; padding: 10px 14px; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; }
.ap-result { max-height: 380px; overflow: auto; margin-top: 8px; }
.ap-try { display: flex; align-items: center; gap: 8px; span { font-size: 12px; color: #8c9ab3; font-weight: 400; } }
.ap-form { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; margin: 10px 0;
  label { display: flex; flex-direction: column; gap: 3px; width: 170px;
    span { font-size: 12px; color: #475569; i { color: #d14343; font-style: normal; } } } }
.ap-meta { font-size: 12px; color: #12805c; margin: 4px 0; }
.ap-side { display: flex; flex-direction: column; gap: 12px; }
.ap-newkey { display: flex; gap: 8px; margin: 8px 0 10px; }
.ap-token { background: #fcf0e2; border: 1px dashed #ecc98f; border-radius: 10px; padding: 8px 12px; margin-bottom: 10px;
  p { font-size: 12px; color: #a8610e; font-weight: 600; }
  code { display: block; font-size: 11.5px; word-break: break-all; color: #14213d; margin: 4px 0; } }
.ap-key { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 0; border-bottom: 1px dashed #eef2f9;
  b { display: block; font-size: 13px; color: #14213d; } span { font-size: 11.5px; color: #8c9ab3; }
  &.revoked b { text-decoration: line-through; color: #8c9ab3; } }
@media (max-width: 1250px) { .ap-main { grid-template-columns: 1fr; } }
</style>
