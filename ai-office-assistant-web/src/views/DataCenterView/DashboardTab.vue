<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDatacenterDashboard, type DatacenterDashboard } from '../../services/personalWorkApi'
import { useSubjectScope } from './subjectScope'

const scope = useSubjectScope()
const data = ref<DatacenterDashboard | null>(null)
const loading = ref(false)

function fmtBytes(n?: number | null) {
  if (!n && n !== 0) return '—'
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(n / 1024)} KB`
}

const recordGroups = computed(() => {
  const r = data.value?.records || {}
  const pick = (keys: string[]) => keys.filter(k => k in r).map(k => ({ label: k, value: r[k] }))
  if (!scope.scoped.value) return [
    { name: '客户经营', items: pick(['客户单位', '客户联系人', '客户关系', '跟进动作', '商机']) },
    { name: '经营与资金', items: pick(['历史回款节点', '台账项目', '平台账号']) },
    { name: '协作与智能体', items: pick(['工单', '论坛主题', '智能体会话', '智能体消息', '技能调用']) },
  ]
  return scope.subjects.value.filter(item => !scope.scoped.value || item.id === scope.selected.value)
    .map(item => ({ name: item.label, items: pick(item.metrics) }))
})

// 容量趋势面积图（单色，按 dataviz 规范：量级用单一色相）
const trend = computed(() => {
  const hist = data.value?.history || []
  if (!hist.length) return null
  const W = 640, H = 190, P = 34
  const max = Math.max(...hist.map(h => h.total_bytes), 1)
  const x = (i: number) => hist.length === 1 ? W / 2 : P + (i * (W - P * 2)) / (hist.length - 1)
  const y = (v: number) => H - 26 - (v / max) * (H - 60)
  const pts = hist.map((h, i) => `${x(i)},${y(h.total_bytes)}`)
  return {
    W, H, max,
    line: `M${pts.join(' L')}`,
    area: `M${x(0)},${H - 26} L${pts.join(' L')} L${x(hist.length - 1)},${H - 26} Z`,
    dots: hist.map((h, i) => ({ cx: x(i), cy: y(h.total_bytes), label: h.date.slice(5), v: h.total_bytes })),
    last: hist[hist.length - 1],
  }
})

const extBars = computed(() => {
  const exts = data.value?.extensions || []
  const max = Math.max(...exts.map(e => e.count), 1)
  return exts.map(e => ({ ...e, pct: (e.count / max) * 100 }))
})

const moduleBars = computed(() => {
  const mods = data.value?.top_modules || []
  const max = Math.max(...mods.map(m => m.bytes), 1)
  return mods.map(m => ({ ...m, pct: (m.bytes / max) * 100 }))
})

const backupRate = computed(() => {
  const b = data.value?.backup
  return b && b.total ? Math.round((b.ok / b.total) * 100) : null
})

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getDatacenterDashboard()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '看板加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="db" v-loading="loading">
    <template v-if="data">
      <section v-for="g in recordGroups" :key="g.name" class="db-card db-group">
        <h4>{{ g.name }}</h4>
        <div class="db-tiles">
          <div v-for="item in g.items" :key="item.label" class="db-tile">
            <strong>{{ item.value.toLocaleString() }}</strong><span>{{ item.label }}</span>
          </div>
        </div>
        <p v-if="!g.items.length" class="db-note">尚未提供该对象的独立业务数量统计，不等于没有数据；存储对应与数据库页可查看已登记数据。</p>
      </section>
      <p class="db-note">业务数据规模：{{ data.records_note }}。统计于 {{ data.generated_at.replace('T', ' ') }}。</p>

      <p class="db-note">以下容量趋势、备份健康与文件分布为全平台指标，不归算到当前助手。</p>
      <div class="db-row">
        <section class="db-card db-chart">
          <h4>存储容量趋势<em v-if="trend">（当前 {{ fmtBytes(trend.last.total_bytes) }}，逐日采样）</em></h4>
          <svg v-if="trend" :viewBox="`0 0 ${trend.W} ${trend.H}`" class="db-svg">
            <path :d="trend.area" fill="#2a78d6" opacity="0.14" />
            <path :d="trend.line" fill="none" stroke="#2a78d6" stroke-width="2" />
            <g v-for="(d, i) in trend.dots" :key="i">
              <circle :cx="d.cx" :cy="d.cy" r="4" fill="#2a78d6" stroke="#fff" stroke-width="1.5" />
              <text :x="d.cx" :y="trend.H - 8" text-anchor="middle" class="db-axis">{{ d.label }}</text>
              <text v-if="trend.dots.length <= 8 || i === trend.dots.length - 1" :x="d.cx" :y="d.cy - 10" text-anchor="middle" class="db-val">{{ fmtBytes(d.v) }}</text>
            </g>
          </svg>
          <p v-if="(data.history || []).length < 2" class="db-note">历史每天记录一个点，运行数日后趋势会逐渐成形。</p>
        </section>
        <section class="db-card db-chart">
          <h4>备份健康度<em v-if="backupRate !== null">（近 {{ data.backup.total }} 次成功率 {{ backupRate }}%）</em></h4>
          <div class="db-strip">
            <i v-for="r in data.backup.recent" :key="r.id" :class="r.ok ? 'ok' : 'bad'"
               :title="`${r.finished_at} · ${r.ok ? '成功' : '失败'} · ${fmtBytes(r.bytes)}`" />
          </div>
          <p class="db-note">每格一次备份，绿色成功、红色失败；悬停查看时间与大小。</p>
        </section>
      </div>

      <div class="db-row">
        <section class="db-card db-chart">
          <h4>模块占用 Top 10</h4>
          <div v-for="m in moduleBars" :key="m.module" class="db-bar">
            <span class="db-bar__label">{{ m.module }}</span>
            <div class="db-bar__track"><i :style="{ width: m.pct + '%', background: '#2a78d6' }" /></div>
            <b>{{ fmtBytes(m.bytes) }}</b>
          </div>
        </section>
        <section class="db-card db-chart">
          <h4>文件类型分布（个数）</h4>
          <div v-for="e in extBars" :key="e.ext" class="db-bar">
            <span class="db-bar__label">{{ e.ext }}</span>
            <div class="db-bar__track"><i :style="{ width: e.pct + '%', background: '#1baf7a' }" /></div>
            <b>{{ e.count.toLocaleString() }}</b>
          </div>
          <p v-if="data.extensions_other" class="db-note">其余类型合计 {{ data.extensions_other.toLocaleString() }} 个文件。</p>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.db { display: flex; flex-direction: column; gap: 12px; }
.db-card { background: #fff; border: 1px solid #e3ebf7; border-radius: 14px; padding: 14px 16px; }
.db-group h4, .db-chart h4 { font-size: 14px; color: #0b2458; margin-bottom: 10px; em { font-style: normal; color: #64748b; font-weight: 400; margin-left: 8px; font-size: 12px; } }
.db-tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.db-tile { background: #f6f9fe; border: 1px solid #e5eefa; border-radius: 12px; padding: 10px 14px;
  strong { display: block; font-size: 24px; color: #0b2458; font-variant-numeric: tabular-nums; }
  span { font-size: 12px; color: #64748b; } }
.db-note { font-size: 12px; color: #8c9ab3; }
.db-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.db-svg { width: 100%; height: auto; }
.db-axis { font-size: 11px; fill: #8c9ab3; }
.db-val { font-size: 11px; fill: #0b2458; font-weight: 700; }
.db-strip { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 0;
  i { width: 22px; height: 22px; border-radius: 6px; &.ok { background: #12805c; } &.bad { background: #d14343; } } }
.db-bar { display: grid; grid-template-columns: 150px 1fr 90px; align-items: center; gap: 10px; padding: 3px 0;
  &__label { font-size: 12.5px; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &__track { height: 12px; background: #eef2f9; border-radius: 0 4px 4px 0;
    i { display: block; height: 100%; border-radius: 0 4px 4px 0; min-width: 2px; } }
  b { font-size: 12.5px; color: #0b2458; text-align: right; font-variant-numeric: tabular-nums; } }
@media (max-width: 1100px) { .db-row { grid-template-columns: 1fr; } .db-tiles { grid-template-columns: repeat(2, 1fr); } }
</style>
