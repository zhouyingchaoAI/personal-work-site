<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { CrmOpportunity, CrmSalesContract } from '../../../src/services/personalWorkApi'

const props = defineProps<{ contracts: CrmSalesContract[]; opportunities: CrmOpportunity[] }>()
const query = ref(''), industry = ref('all'), archived = ref('all'), page = ref(1), detail = ref<CrmSalesContract | null>(null)
const opportunityByCode = computed(() => new Map(props.opportunities.map(item => [item.code, item])))
const industries = computed(() => [...new Set(props.contracts.map(item => item.industry).filter(Boolean))].sort())
const filtered = computed(() => props.contracts.filter(item =>
  (industry.value === 'all' || item.industry === industry.value) &&
  (archived.value === 'all' || (archived.value === 'yes') === item.archived) &&
  `${item.contract_code} ${item.project_code} ${item.project_name} ${item.subproject_name} ${item.customer} ${item.owner_unit} ${item.account_manager}`.toLowerCase().includes(query.value.trim().toLowerCase())
))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * 20, page.value * 20))
watch([query, industry, archived, () => props.contracts], () => { page.value = 1 })
const totalAmount = computed(() => props.contracts.reduce((sum, item) => sum + Number(item.amount_yuan || 0), 0))
const projectCount = computed(() => new Set(props.contracts.map(item => item.project_code)).size)
const linkedCount = computed(() => new Set(props.contracts.filter(item => opportunityByCode.value.has(item.project_code)).map(item => item.project_code)).size)
const signedThisYear = computed(() => props.contracts.filter(item => String(item.signed_at || '').startsWith(String(new Date().getFullYear()))).length)
function number(value: number) { return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }
function percent(value: unknown) { const match = String(value || '').match(/[\d.]+/); return match ? Math.min(100, Number(match[0])) : null }
function fmtDate(value?: string) { const text = String(value || '').trim(); return text ? text.slice(0, 10) : '待补充' }
const probabilityBands = computed(() => {
  const bands = [
    { label: '原预估 100%', target: 100, color: '#138a5b' },
    { label: '原预估 75%', target: 75, color: '#2388c9' },
    { label: '原预估 50%', target: 50, color: '#d98921' },
    { label: '原预估 25%', target: 25, color: '#d64545' },
  ]
  return bands.map(band => {
    const items = props.opportunities.filter(item => percent(item.win_rate) === band.target)
    const won = items.filter(item => Number(item.contract_count || 0) > 0 || item.outcome_source === 'sales_contract')
    return { ...band, opportunities: items.length, won: won.length, actual: items.length ? Math.round(won.length * 1000 / items.length) / 10 : 0, amount: won.reduce((sum, item) => sum + Number(item.contract_amount_yuan || 0), 0) }
  })
})
</script>

<template>
  <section class="sales-contracts">
    <header><div><span>SALES CONTRACTS</span><h2>销售合同与商机关联</h2><p>按当前登记赢率查看合同匹配情况；未建立预测时点快照，不作为最终胜率校准。</p></div></header>
    <div class="sc-kpis">
      <article><small>销售合同</small><b>{{ contracts.length }}</b><span>共 {{ projectCount }} 个销售项目</span></article>
      <article><small>合同总金额</small><b>{{ number(totalAmount / 10000) }}</b><span>万元</span></article>
      <article><small>已关联成单商机</small><b>{{ linkedCount }}</b><span>按销售项目编码匹配</span></article>
      <article><small>本年签订</small><b>{{ signedThisYear }}</b><span>份合同</span></article>
    </div>
    <section class="sc-calibration">
      <div class="sc-title"><div><h3>当前登记赢率与合同匹配率</h3><p>按当前100%、75%、50%、25%四档分组；匹配率＝已匹配合同商机数÷该档商机数。未匹配不代表输单，不能解释为历史预测的最终实际胜率。</p></div></div>
      <div class="sc-bands">
        <article v-for="band in probabilityBands" :key="band.label" :style="{'--tone':band.color}">
          <header><b>{{ band.label }}</b><span>{{ band.opportunities }} 个样本</span></header>
          <div><strong>{{ band.actual }}%</strong><small>合同匹配率</small></div>
          <p>{{ band.won }} / {{ band.opportunities }} 个商机匹配到合同</p>
          <i><em :style="{width:`${band.actual}%`}" /></i>
          <footer>成单合同额 {{ number(band.amount / 10000) }} 万元</footer>
        </article>
      </div>
    </section>
    <div class="sc-filters">
      <el-input v-model="query" :prefix-icon="Search" clearable placeholder="搜索合同、项目、客户或客户经理" />
      <el-select v-model="industry"><el-option label="全部产业" value="all"/><el-option v-for="item in industries" :key="item" :label="item" :value="item"/></el-select>
      <el-select v-model="archived"><el-option label="全部归档状态" value="all"/><el-option label="已归档" value="yes"/><el-option label="未归档" value="no"/></el-select>
    </div>
    <div class="sc-result">当前显示 <b>{{ filtered.length }}</b> 份合同，金额 {{ number(filtered.reduce((sum,item)=>sum+Number(item.amount_yuan||0),0) / 10000) }} 万元</div>
    <el-table :data="pageRows" max-height="560" empty-text="暂无匹配销售合同">
      <el-table-column label="合同 / 销售项目" min-width="280"><template #default="{row}"><el-button link type="primary" @click="detail=row">{{ row.contract_code }}</el-button><small>{{ row.project_name || row.subproject_name || '项目名称待补充' }}</small><small>{{ row.project_code }} · {{ row.subproject_code }}</small></template></el-table-column>
      <el-table-column label="客户 / 业主" min-width="220"><template #default="{row}"><span>{{ row.customer || '客户待补充' }}</span><small>{{ row.owner_unit || '业主待补充' }}</small></template></el-table-column>
      <el-table-column label="合同金额" min-width="140" align="right"><template #default="{row}"><strong class="sc-money">{{ number(row.amount_yuan) }} 元</strong><small v-if="row.expected_margin_yuan != null">预计毛利 {{ number(row.expected_margin_yuan) }} 元</small></template></el-table-column>
      <el-table-column label="签订 / 归档" min-width="130"><template #default="{row}"><span>{{ fmtDate(row.signed_at) }}</span><small>{{ row.archived ? '已归档' : '未归档' }}</small></template></el-table-column>
      <el-table-column label="负责人" min-width="140"><template #default="{row}"><span>{{ row.account_manager || '客户经理待补充' }}</span><small>{{ row.project_manager || '项目经理待补充' }}</small></template></el-table-column>
      <el-table-column label="商机预估 → 最终" min-width="150"><template #default="{row}"><span>{{ opportunityByCode.get(row.project_code)?.win_rate || '未登记胜率' }}</span><small class="sc-won">已签合同 · 最终成单</small></template></el-table-column>
      <el-table-column label="操作" width="80" fixed="right"><template #default="{row}"><el-button link type="primary" @click="detail=row">详情</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-if="filtered.length>20" v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next, total" />
    <el-drawer :model-value="!!detail" title="销售合同详情" size="min(720px,96vw)" append-to-body destroy-on-close @close="detail=null">
      <section v-if="detail" class="sc-detail">
        <h2>{{ detail.contract_code }}</h2><p>{{ detail.project_name || detail.subproject_name }} · {{ detail.project_code }}</p>
        <div class="sc-final"><span>最终成单</span><b>{{ number(detail.amount_yuan) }} 元</b><small>合同已签订，商机结果按客观合同确认为赢单</small></div>
        <dl><div><dt>销售子项目</dt><dd>{{ detail.subproject_name || '待补充' }}</dd></div><div><dt>子项目编码</dt><dd>{{ detail.subproject_code || '待补充' }}</dd></div><div><dt>客户</dt><dd>{{ detail.customer || '待补充' }}</dd></div><div><dt>业主单位</dt><dd>{{ detail.owner_unit || '待补充' }}</dd></div><div><dt>合同签订日期</dt><dd>{{ fmtDate(detail.signed_at) }}</dd></div><div><dt>归档状态</dt><dd>{{ detail.archived ? '已归档' : '未归档' }}</dd></div><div><dt>客户经理</dt><dd>{{ detail.account_manager || '待补充' }}</dd></div><div><dt>项目经理</dt><dd>{{ detail.project_manager || '待补充' }}</dd></div><div><dt>所属产业</dt><dd>{{ detail.industry || '待补充' }}</dd></div><div><dt>商机预估胜率</dt><dd>{{ opportunityByCode.get(detail.project_code)?.win_rate || '未登记' }}</dd></div><div><dt>预计毛利</dt><dd>{{ detail.expected_margin_yuan == null ? '待补充' : number(detail.expected_margin_yuan)+' 元' }}</dd></div></dl>
        <h3>收款条件</h3><p class="sc-terms">{{ detail.payment_terms || '暂未登记收款条件' }}</p>
      </section>
    </el-drawer>
  </section>
</template>

<style scoped>
.sales-contracts{color:#29445f}.sales-contracts>header{padding:20px 22px;border-radius:14px;background:linear-gradient(115deg,#edf6ff,#effaf5);border:1px solid #d9e8f5}.sales-contracts>header span{font-size:11px;letter-spacing:1.8px;color:#188b7c}.sales-contracts h2{margin:6px 0;font-size:22px}.sales-contracts p{margin:0;color:#6a8197;font-size:12px;line-height:1.7}.sc-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}.sc-kpis article{padding:16px;border:1px solid #dce8f5;border-radius:12px;background:#fff}.sc-kpis small,.sc-kpis span{display:block;color:#71879c;font-size:11px}.sc-kpis b{display:block;margin:8px 0 4px;color:#164f93;font-size:26px}.sc-calibration{padding:18px;border:1px solid #dce8f5;border-radius:12px;background:#fff;margin-bottom:14px}.sc-title h3{margin:0 0 5px;font-size:16px}.sc-bands{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}.sc-bands article{padding:14px;border:1px solid #e0e9f3;border-top:3px solid var(--tone);border-radius:10px}.sc-bands header{display:flex;justify-content:space-between}.sc-bands header span,.sc-bands small,.sc-bands footer{font-size:11px;color:#74899e}.sc-bands div{display:flex;align-items:baseline;gap:8px;margin:12px 0 2px}.sc-bands strong{font-size:25px;color:var(--tone)}.sc-bands i{display:block;height:7px;background:#edf2f7;border-radius:4px;overflow:hidden}.sc-bands em{display:block;height:100%;background:var(--tone)}.sc-bands footer{margin-top:10px}.sc-filters{display:grid;grid-template-columns:minmax(260px,1fr) 180px 160px;gap:10px}.sc-result{margin:10px 0;color:#6a8197;font-size:12px}.el-table small{display:block;margin-top:4px;color:#7a8da0}.sc-money{color:#155a9c}.sc-won{color:#16865c!important}.sc-detail>p{color:#71869b}.sc-final{padding:18px;border-radius:12px;background:linear-gradient(110deg,#eaf8f1,#edf6ff);margin:16px 0}.sc-final span,.sc-final small{display:block}.sc-final span{color:#16865c;font-weight:700}.sc-final b{display:block;font-size:28px;color:#155a7d;margin:7px 0}.sc-final small{color:#678098}.sc-detail dl{display:grid;grid-template-columns:1fr 1fr;gap:10px}.sc-detail dl div{padding:12px;background:#f6f9fc;border-radius:8px}.sc-detail dt{font-size:11px;color:#7890a6}.sc-detail dd{margin:5px 0 0;font-size:13px}.sc-terms{padding:14px;background:#f6f9fc;border-radius:8px;white-space:pre-wrap}@media(max-width:900px){.sc-kpis{grid-template-columns:1fr 1fr}.sc-bands{grid-template-columns:1fr}.sc-filters{grid-template-columns:1fr}.sc-detail dl{grid-template-columns:1fr}}
.sc-bands{grid-template-columns:repeat(4,1fr)}
@media(max-width:1100px){.sc-bands{grid-template-columns:1fr 1fr}}
</style>
