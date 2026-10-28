<script setup lang="ts">
import { computed, onActivated, onDeactivated, onMounted, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDatacenterDbFlow, type DcFlowSnapshot } from '../../services/personalWorkApi'
import { useSubjectScope } from './subjectScope'
import { scopeFlowSnapshot } from './flowScope'
import RelationGraph from './RelationGraph.vue'

const scope = useSubjectScope()
const rawSnapshot = ref<DcFlowSnapshot | null>(null)
const snap = computed(() => scopeFlowSnapshot(rawSnapshot.value, scope.selected.value, scope.subjects.value))
const loading = ref(false)
const selectedAssistant = ref<string | null>(scope.scoped.value ? scope.selected.value : null)
const selectedInstanceId = ref<string | null>(null)
const selectedInstance = computed(() => snap.value?.instances.find(item => item.id === selectedInstanceId.value) || null)
let timer = 0
let alive = true

async function load() {
  if (!alive) return
  loading.value = !snap.value
  try {
    rawSnapshot.value = await getDatacenterDbFlow()
  } catch (e) {
    if (!snap.value) ElMessage.error(e instanceof Error ? e.message : '读取数据流向失败')
  } finally {
    loading.value = false
  }
}

const assistantCount = computed(() => snap.value?.assistants.filter(a => a.node_type === 'assistant').length || 0)
const instanceLabels = computed(() => new Map(snap.value?.instances.map(inst => [inst.id, inst.label]) || []))

const summary = computed(() => {
  const list = snap.value?.instances || []
  return {
    up: list.filter(i => i.status === 'up').length, total: list.length,
    active: list.filter(i => i.active).length,
    connections: list.reduce((s, i) => s + (Number(i.gauges['连接数']) || 0), 0),
    alerts: snap.value?.alerts_active.length || 0,
  }
})

function pickPair(assistantId: string, instanceId: string) {
  selectedAssistant.value = assistantId
  selectedInstanceId.value = instanceId
}

function start() { alive = true; load(); timer = window.setInterval(load, 5000) }
function stop() { alive = false; if (timer) window.clearInterval(timer); timer = 0 }
onMounted(start)
onBeforeUnmount(stop)
onActivated(() => { if (!timer) start() })
onDeactivated(stop)
</script>

<template>
  <div class="fl" v-loading="loading">
    <section class="fl-card fl-summary" v-if="snap">
      <div><b>{{ snap.assistants.length }}</b><span>当前管理对象</span></div>
      <div><b>{{ summary.up }}/{{ summary.total }}</b><span>实例在线</span></div>
      <div><b>{{ summary.active }}</b><span>正在交互</span></div>
      <div><b>{{ summary.connections }}</b><span>活跃连接</span></div>
      <div :class="{ 'fl-bad': summary.alerts }"><b>{{ summary.alerts }}</b><span>当前异常</span></div>
      <em>实时采样 · 每 5 秒刷新 · 上次 {{ snap.sampled_at.replace('T', ' ') }}</em>
    </section>

    <section class="fl-card" v-if="snap">
      <h4 class="fl-h4">助手与数据库关联图<span class="fl-muted">上排助手 · 下排数据库实例</span></h4>
      <RelationGraph :snap="snap" v-model:assistant="selectedAssistant" v-model:instance="selectedInstanceId" />
    </section>

    <section class="fl-card" v-if="snap">
      <h4 class="fl-h4">{{ scope.label.value }} · {{ assistantCount }} 个助手 / {{ snap.assistants.length - assistantCount }} 个{{ scope.scoped.value ? '平台' : '支撑系统' }}</h4>
      <p class="fl-muted">关联库的连接数、速率与告警是整库指标，不是该助手独占流量；主存储与定时镜像分别标注。未接入监测不等于无数据。</p>
      <div class="fl-mapping">
        <table>
          <thead><tr><th>助手 / 系统</th><th>关联数据库（点击查看）</th><th>数据对应情况</th></tr></thead>
          <tbody>
            <tr v-for="a in snap.assistants" :key="a.id" :class="{ 'mapping-selected': selectedAssistant === a.id }">
              <td><button class="fl-map-button" @click="selectedAssistant = selectedAssistant === a.id ? null : a.id; selectedInstanceId = null">{{ a.label }}</button><small>{{ a.node_type === 'assistant' ? '助手' : '支撑系统' }}</small></td>
              <td>
                <button v-for="id in a.instances" :key="id" class="fl-map-button" @click="pickPair(a.id, id)">
                  {{ instanceLabels.get(id) }}<small>{{ a.mirror_instances.includes(id) ? '定时镜像 / 索引' : '业务存储' }}</small>
                </button>
                <span v-if="!a.instances.length">尚未接入监测</span>
                <small v-if="a.unregistered_instances.length">未注册：{{ a.unregistered_instances.join('、') }}</small>
              </td>
              <td>{{ a.storage_note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="fl-card fl-detail" v-if="selectedInstance">
      <h4>{{ selectedInstance.label }}
        <el-tag size="small" :type="selectedInstance.status === 'up' ? 'success' : 'danger'">
          {{ selectedInstance.status === 'up' ? '在线' : selectedInstance.status === 'down' ? '不可达' : '采样失败' }}</el-tag>
      </h4>
      <div class="fl-detail-grid">
        <div>
          <h5>谁在连接（数据库端实时可见）</h5>
          <p v-if="!selectedInstance.clients.length" class="fl-muted">该类型不提供连接来源明细，以活动指标为准。</p>
          <ul>
            <li v-for="c in selectedInstance.clients" :key="c.label">{{ c.label }}<b>{{ c.count }} 连接</b></li>
          </ul>
        </div>
        <div>
          <h5>实时指标</h5>
          <ul>
            <li v-for="(v, k) in selectedInstance.rates" :key="`r${k}`">{{ k }}<b>{{ v }}/s</b></li>
            <li v-for="(v, k) in selectedInstance.deltas" :key="`d${k}`">{{ k }}<b>{{ v }}</b></li>
            <li v-for="(v, k) in selectedInstance.gauges" :key="`g${k}`">{{ k }}<b>{{ v }}</b></li>
          </ul>
        </div>
      </div>
    </section>

    <section class="fl-card" v-if="snap">
      <h4 class="fl-h4">当前异常（{{ snap.alerts_active.length }} 条）</h4>
      <p v-if="!snap.alerts_active.length" class="fl-ok">
        本次采样未发现异常。历史告警保留供追溯，不代表当前仍有故障。</p>
      <el-table v-else :data="snap.alerts_active"
                size="small" max-height="240">
        <el-table-column label="时间" width="170"><template #default="{ row }">{{ row.at.replace('T', ' ') }}</template></el-table-column>
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.level === 'critical' ? 'danger' : 'warning'">
              {{ row.level === 'critical' ? '严重' : '警告' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="实例" prop="instance" width="170" />
        <el-table-column label="说明" prop="message" min-width="300" />
      </el-table>
      <details class="fl-history" v-if="snap.alerts_recent.length">
        <summary>查看历史告警（最近 {{ snap.alerts_recent.length }} 条，非当前故障清单）</summary>
        <el-table :data="snap.alerts_recent" size="small" max-height="300">
          <el-table-column label="发生时间" width="170"><template #default="{ row }">{{ row.at.replace('T', ' ') }}</template></el-table-column>
          <el-table-column label="当时级别" width="90"><template #default="{ row }">{{ row.level === 'critical' ? '严重' : '警告' }}</template></el-table-column>
          <el-table-column label="实例" prop="instance" width="170" />
          <el-table-column label="历史事件" prop="message" min-width="300" />
        </el-table>
      </details>
    </section>
  </div>
</template>

<style scoped lang="scss">
.fl { display: flex; flex-direction: column; gap: 12px; }
.fl-history { margin-top: 12px; color: #64748b; font-size: 12px;
  summary { cursor: pointer; padding: 8px 0; }
}
.fl-mapping { max-height: 420px; overflow: auto;
  table { border-collapse: collapse; width: 100%; font-size: 12px; text-align: left; }
  th { position: sticky; top: 0; background: #edf3fc; color: #15499c; z-index: 1; }
  td, th { padding: 9px 12px; border-bottom: 1px solid #e5edf8; }
  td:first-child { min-width: 160px; }
  td:nth-child(2) { min-width: 210px; }
  td:last-child { min-width: 260px; color: #52617a; }
  small { display: block; color: #74829a; font-size: 11px; }
  .mapping-selected { background: #eef5ff; }
}
.fl-map-button { display: block; border: 0; background: transparent; color: #15499c; text-align: left; cursor: pointer; padding: 3px 0; font: inherit;
  &:hover { text-decoration: underline; }
  &:focus-visible { outline: 2px solid #3a7bd5; }
}
.fl-card { background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; padding: 14px 16px; }
.fl-summary { display: flex; align-items: center; gap: 34px;
  div { display: flex; flex-direction: column; b { font-size: 22px; color: #0b2458; } span { font-size: 12px; color: #64748b; } }
  .fl-bad b { color: #d43c3c; }
  em { margin-left: auto; font-style: normal; font-size: 12px; color: #8c9ab3; } }
.fl-detail h4 { font-size: 14px; color: #0b2458; margin-bottom: 10px; display: flex; gap: 10px; align-items: center; }
.fl-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
  h5 { font-size: 12.5px; color: #476299; margin-bottom: 6px; }
  ul { list-style: none; display: flex; flex-direction: column; gap: 4px; max-height: 220px; overflow: auto;
    li { display: flex; justify-content: space-between; font-size: 12.5px; color: #14213d; padding: 3px 8px; background: #f6f9fe; border-radius: 6px;
      b { color: #15499c; } } } }
.fl-muted { font-size: 12px; color: #8c9ab3; }
.fl-h4 { font-size: 14px; color: #0b2458; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; .fl-muted { font-weight: 400; } }
.fl-ok { font-size: 12.5px; color: #1f8f5f; background: #eefaf3; border-radius: 8px; padding: 10px 12px; }
@media (max-width: 1100px) { .fl-detail-grid { grid-template-columns: 1fr; } }
</style>
