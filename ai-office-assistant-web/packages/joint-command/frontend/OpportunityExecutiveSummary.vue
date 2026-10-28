<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CrmOpportunity, CrmSalesContract } from '../../../src/services/personalWorkApi'
const props = defineProps<{ opportunities: CrmOpportunity[]; contracts: CrmSalesContract[] }>()
const emit = defineEmits<{ select: [item: CrmOpportunity] }>()
const selected = ref<CrmOpportunity[]>([])
const title = ref('')
const opened = ref(false)
const format = (value: number) => value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const contracted = (item: CrmOpportunity) => Number(item.contract_count || 0) > 0 || item.outcome_source === 'sales_contract'
const open = (item: CrmOpportunity) => !item.cancelled && (!item.outcome || item.outcome === 'open') && !contracted(item)
const rate = (item: CrmOpportunity) => {
  const text = String(item.win_rate ?? '').trim().replace(/%$/, '')
  return text !== '' && Number.isFinite(Number(text)) ? Number(text) : null
}
const bands = computed(() => [100, 75, 50, 25].map(expected => {
  const items = props.opportunities.filter(item => rate(item) === expected)
  const wins = items.filter(contracted)
  return { expected, items, wins, actual: items.length ? (wins.length / items.length * 100).toFixed(1) : null }
}))
const otherCount = computed(() => props.opportunities.filter(item => ![100, 75, 50, 25].includes(rate(item) ?? -1)).length)
const summary = computed(() => {
  const codes = new Set(props.opportunities.map(item => item.code))
  return {
    amount: props.contracts.reduce((sum, item) => sum + Number(item.amount_yuan || 0), 0) / 10000,
    matched: props.opportunities.filter(contracted),
    unmatched: new Set(props.contracts.filter(item => !codes.has(item.project_code)).map(item => item.project_code)).size,
  }
})
const risks = computed(() => {
  const active = props.opportunities.filter(open)
  const today = new Date()
  const cutoff = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  return [
    { name: '预计签约已逾期', items: active.filter(item => { const date = Date.parse(item.contract_date); return Number.isFinite(date) && date < cutoff }) },
    { name: '高预估尚未成单', items: active.filter(item => (rate(item) ?? 0) >= 75) },
    { name: '负责人待明确', items: active.filter(item => !item.manager?.trim()) },
    { name: '阶段材料待补充', items: active.filter(item => !Object.values(item.stage_progress || {}).some(stage => stage.attachments?.length)) },
  ]
})
function inspect(label: string, items: CrmOpportunity[]) {
  title.value = label
  selected.value = [...items].sort((first, second) => Number(second.amount || 0) - Number(first.amount || 0))
  opened.value = true
}
</script>
<template>
  <section class="executive-summary">
    <header><h2>商机经营总览</h2><p>当前权限内全部历史数据 · 金额统一为万元 · 点击成单数、胜率档位或风险卡片查看商机</p></header>
    <div class="executive-grid">
      <article><span>销售合同总额</span><strong>{{ format(summary.amount) }}</strong><small>{{ contracts.length }} 条合同记录；含未匹配商机的合同</small></article>
      <button @click="inspect('合同确认成单商机', summary.matched)"><span>合同确认成单</span><strong>{{ summary.matched.length }} 个</strong><small>按商机去重，多个合同仅计一个商机</small></button>
      <article><span>合同项目待关联</span><strong>{{ summary.unmatched }} 个</strong><small>尚无对应商机，未纳入胜率分母</small></article>
    </div>
    <h3>预估胜率 → 截至目前合同兑现率</h3>
    <p>按当前保留的登记赢率分组；兑现率＝已匹配合同商机数 ÷ 该档全部商机数。历史预测快照尚未建立，数据会随登记值变化。</p>
    <div class="executive-bands">
      <button v-for="band in bands" :key="band.expected" @click="inspect(`登记赢率 ${band.expected}% 的商机`, band.items)">
        <span>预估 {{ band.expected }}%</span><strong>{{ band.actual === null ? '暂无样本' : `${band.actual}%` }}</strong>
        <progress :value="Number(band.actual || 0)" max="100" :aria-label="`预估${band.expected}%合同兑现率`" />
        <small>{{ band.wins.length }} 个已成单 / {{ band.items.length }} 个商机</small>
      </button>
    </div>
    <p>其他或未登记胜率：{{ otherCount }} 个。未匹配合同不代表输单；仍在谈、已输单及取消项目需结合成交结果分别判断。</p>
    <h3>优先跟进事项</h3>
    <div class="executive-bands">
      <button v-for="risk in risks" :key="risk.name" @click="inspect(risk.name, risk.items)"><span>{{ risk.name }}</span><strong>{{ risk.items.length }} 个</strong><small>查看项目及负责人 →</small></button>
    </div>
    <el-drawer v-model="opened" :title="title" size="min(1000px,96vw)" append-to-body>
      <p>共 {{ selected.length }} 个，按可参与份额降序；点击项目查看详情。</p>
      <el-table :data="selected" max-height="650">
        <el-table-column label="商机" min-width="240"><template #default="{row}"><el-button link type="primary" @click="opened=false;emit('select',row)">{{ row.name }}</el-button><div>{{ row.code }}</div></template></el-table-column>
        <el-table-column prop="region" label="区域" width="100"/>
        <el-table-column prop="manager" label="负责人" width="120"/>
        <el-table-column prop="win_rate" label="登记赢率" width="100"/>
        <el-table-column label="合同成单" width="110"><template #default="{row}">{{ contracted(row) ? '已成单' : '未匹配合同' }}</template></el-table-column>
        <el-table-column prop="contract_date" label="签约日期" min-width="140"/>
      </el-table>
    </el-drawer>
  </section>
</template>
<style scoped>
.executive-summary{margin-bottom:24px;color:#274665}.executive-summary header{background:linear-gradient(120deg,#edf5ff,#eaf8f5);padding:20px;border-radius:12px}.executive-summary h2{margin:0 0 8px}.executive-summary p{font-size:12px;color:#657b92;line-height:1.8}.executive-grid,.executive-bands{display:grid;gap:12px;margin:16px 0;grid-template-columns:repeat(3,minmax(0,1fr))}.executive-bands{grid-template-columns:repeat(4,minmax(0,1fr))}.executive-summary article,.executive-summary button{padding:18px;border:1px solid #dce7f3;border-radius:10px;background:white;color:inherit;text-align:left;font:inherit}.executive-summary button{cursor:pointer}.executive-summary button:hover{border-color:#2584ca}.executive-summary strong{display:block;font-size:26px;color:#156a9c;margin:10px 0}.executive-summary small{display:block;color:#71849a;font-size:12px;line-height:1.6}.executive-summary progress{width:100%;height:10px;accent-color:#19a28c}.executive-summary button:focus-visible{outline:2px solid #2584ca}@media(max-width:1000px){.executive-grid,.executive-bands{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.executive-grid,.executive-bands{grid-template-columns:1fr}}
</style>
