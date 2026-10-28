<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CashflowInsightCustomer, CashflowInsights } from '../../services/personalWorkApi'

const props = withDefaults(defineProps<{ insights: CashflowInsights; part?: 'pattern' | 'credit' }>(), { part: 'pattern' })
const emit = defineEmits<{ useCustomer: [name: string] }>()

const wan = (v: number | null | undefined) => v == null ? '—' : `${(v / 10000).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}万`
const days = (v: number | null | undefined) => v == null ? '—' : `${v} 天`
const pctDiff = (ratio: number | null | undefined) => ratio == null ? '—' : `${ratio >= 1 ? '慢' : '快'} ${Math.abs(Math.round((ratio - 1) * 100))}%`
const ICONS: Record<string, string> = { amount: '档', customer: '客', credit: '评', model: '模' }

// ① 金额档位：条形长度按闭环中位天数相对最大值绘制，P75 用浅色延长段。
const tierMax = computed(() => Math.max(1, ...props.insights.tiers.map(t => t.p75_cycle_days || t.median_cycle_days || 0)))

// ② ③ 客户评级：可按等级筛选，默认先看 D、C。
const grades = ['全部', 'D', 'C', 'B', 'A', '样本不足'] as const
const grade = ref<(typeof grades)[number]>('全部')
const keyword = ref('')
const gradeCount = computed(() => props.insights.customers.reduce<Record<string, number>>((m, c) => { m[c.credit_grade] = (m[c.credit_grade] || 0) + 1; return m }, {}))
const customers = computed(() => props.insights.customers.filter(c =>
  (grade.value === '全部' ? c.credit_grade !== '样本不足' : c.credit_grade === grade.value) && (!keyword.value.trim() || c.name.includes(keyword.value.trim()))))
const occupiedTotal = computed(() => props.insights.customers.filter(c => c.credit_grade === 'C' || c.credit_grade === 'D').reduce((s, c) => s + c.funding_cost, 0))
const expanded = ref('')
const toggle = (c: CashflowInsightCustomer) => { expanded.value = expanded.value === c.name ? '' : c.name }

// ④ 标准回款模型
const STAGE_COLORS: Record<string, string> = { 前期款: '#2b8f64', 进度款: '#4c9a9a', 到货款: '#4478cc', '验收/开通款': '#d8902d', '结算/尾款': '#ac5eb7', 质保款: '#de6c5f', 服务期款: '#6b7fd7', 其他节点: '#94a3b8' }
const maxProb = computed(() => Math.max(1, ...props.insights.patterns.map(p => p.probability)))
</script>

<template>
  <section class="rp-insights" :class="`is-${part}`">
    <header v-if="part === 'pattern'" class="rp-head">
      <div><p>回款规律洞察 · 基于 {{ insights.project_count.toLocaleString() }} 个历史项目</p><h2>从历史回款中找规律，反哺合同谈判与新项目测算</h2></div>
      <span>项目闭环 = 合同日到最后一笔回款；未结清项目单独统计，不计入闭环周期</span>
    </header>

    <div v-if="part === 'pattern'" class="rp-conclusions">
      <article v-for="(c, i) in insights.conclusions" :key="c.key" :class="`k-${c.key}`">
        <i>{{ ICONS[c.key] || i + 1 }}</i><div><b>{{ i + 1 }}. {{ c.title }}</b><span>{{ c.text }}</span></div>
      </article>
    </div>

    <div v-if="part === 'pattern'" class="rp-grid">
      <!-- ① 金额档位回款基线 -->
      <section class="rp-card">
        <h3><em>1</em>按项目金额档位的回款基线</h3>
        <p class="rp-note">大额集成项目交付内容多、验收流程复杂，整体回款闭环更长；新项目先按金额档位取基线。</p>
        <div class="rp-tiers">
          <div v-for="t in insights.tiers" :key="t.name" class="rp-tier">
            <div class="rp-tier__top"><b>{{ t.name }}</b><span>{{ t.projects }} 个项目 · 已结清 {{ t.closed_projects }}</span></div>
            <div class="rp-bar"><i class="p75" :style="{ width: `${(t.p75_cycle_days || 0) / tierMax * 100}%` }"></i><i class="mid" :style="{ width: `${(t.median_cycle_days || 0) / tierMax * 100}%` }"></i></div>
            <div class="rp-tier__stats">
              <span>闭环中位 <b>{{ days(t.median_cycle_days) }}</b></span><span>P75 <b>{{ days(t.p75_cycle_days) }}</b></span>
              <span>首笔回款 <b>{{ days(t.median_first_days) }}</b></span><span>平均 <b>{{ t.avg_nodes ?? '—' }}</b> 个节点</span>
              <span>回款达成 <b>{{ t.received_rate }}%</b></span><span>未结清 <b>{{ t.open_projects }}</b> 个</span>
            </div>
          </div>
        </div>
        <p class="rp-legend"><i class="mid"></i>闭环中位　<i class="p75"></i>P75（保守测算用）</p>
      </section>

      <!-- ④ 标准回款模型 -->
      <section class="rp-card">
        <h3><em>4</em>标准化回款模型（概率 + 周期）</h3>
        <p class="rp-note">取计划回款覆盖合同额 90%–110% 的 {{ insights.pattern_sample }} 个完整项目，比例取整到 5%；天数为合同日到该节点回款的中位数。</p>
        <div class="rp-patterns">
          <article v-for="(p, i) in insights.patterns" :key="p.signature">
            <div class="rp-pattern__head"><b>#{{ i + 1 }}</b><span class="rp-prob"><i :style="{ width: `${p.probability / maxProb * 100}%` }"></i></span><strong>{{ p.probability }}%</strong><small>{{ p.projects }} 个项目 · 闭环中位 {{ days(p.median_cycle_days) }}</small></div>
            <div class="rp-split"><i v-for="n in p.nodes" :key="n.stage" :style="{ flex: n.share, background: STAGE_COLORS[n.stage] }" :title="`${n.stage} ${n.share}%`"></i></div>
            <div class="rp-nodes"><span v-for="n in p.nodes" :key="n.stage"><i :style="{ background: STAGE_COLORS[n.stage] }"></i>{{ n.stage }} {{ n.share }}%<em>约 {{ days(n.median_days) }}</em></span></div>
          </article>
        </div>
      </section>
    </div>

    <!-- ② ③ 总包客户回款质量与信用评级 -->
    <section v-if="part === 'credit'" class="rp-card rp-credit">
      <div class="rp-credit__head">
        <h3><em>2·3</em>总包客户回款质量与信用评级</h3>
        <span>C/D 级客户累计资金占用成本约 <b>{{ wan(occupiedTotal) }}</b>（按年化 {{ insights.funding_rate * 100 }}% 估算）</span>
      </div>
      <p class="rp-note">评级依据：同类回款节点账期相对公司水平（按金额加权）、每元回款资金占用时长、签约满一年仍未回占比、预付比例；历史项目少于 3 个或累计不足 100 万不评级。评级用于合同谈判与测算，不作为对外结论。</p>
      <div class="rp-toolbar">
        <div class="rp-grades"><button v-for="g in grades" :key="g" type="button" :class="[`g-${g}`, { on: grade === g }]" @click="grade = g">{{ g }}<em v-if="g !== '全部'">{{ gradeCount[g] || 0 }}</em></button></div>
        <el-input v-model="keyword" clearable size="small" placeholder="搜索客户" style="width:200px" />
      </div>
      <el-table :data="customers" max-height="460" size="small" row-key="name" @row-click="toggle" :expand-row-keys="expanded ? [expanded] : []">
        <el-table-column type="expand"><template #default="{ row }"><div class="rp-terms"><b>合同谈判建议</b><span>{{ row.terms }}</span><el-button size="small" type="primary" plain @click.stop="emit('useCustomer', row.name)">按该客户新建资金测算</el-button></div></template></el-table-column>
        <el-table-column label="评级" width="70" align="center"><template #default="{ row }"><span class="rp-grade" :class="`g-${row.credit_grade}`">{{ row.credit_grade === '样本不足' ? '—' : row.credit_grade }}</span></template></el-table-column>
        <el-table-column label="客户" min-width="220" show-overflow-tooltip><template #default="{ row }"><b>{{ row.name }}</b><small class="rp-sub">{{ row.projects }} 个项目 · {{ row.nodes }} 个节点</small></template></el-table-column>
        <el-table-column label="信用分" width="80" align="center"><template #default="{ row }">{{ row.credit_score ?? '—' }}</template></el-table-column>
        <el-table-column label="同类节点账期" width="120" align="center"><template #default="{ row }"><span :class="{ bad: (row.cycle_vs_company || 0) > 1.1, good: (row.cycle_vs_company || 1) < 0.9 }">{{ pctDiff(row.cycle_vs_company) }}</span></template></el-table-column>
        <el-table-column label="每元回款占用" width="120" align="center"><template #default="{ row }"><span :class="{ bad: row.occupancy_vs_company > 1.3 }">{{ row.occupancy_years }} 年</span></template></el-table-column>
        <el-table-column label="预付比例" width="90" align="center"><template #default="{ row }"><span :class="{ bad: row.prepay_share < 20 }">{{ row.prepay_share }}%</span></template></el-table-column>
        <el-table-column label="满一年未回" width="100" align="center"><template #default="{ row }"><span :class="{ bad: row.overdue_share > 10 }">{{ row.overdue_share }}%</span></template></el-table-column>
        <el-table-column label="计划回款" width="110" align="right"><template #default="{ row }">{{ wan(row.planned) }}</template></el-table-column>
        <el-table-column label="资金占用成本" width="120" align="right"><template #default="{ row }"><b>{{ wan(row.funding_cost) }}</b></template></el-table-column>
      </el-table>
      <p class="rp-foot">公司基准：同类节点账期指数 {{ insights.company_cycle_index }}，每元回款占用 {{ insights.company_occupancy_years }} 年。点击行查看谈判建议。</p>
    </section>
  </section>
</template>

<style scoped>
.rp-insights.is-credit{padding:0;border:0;background:none}.rp-insights.is-credit .rp-credit{padding:16px 18px;border-color:#d6e8df}
.rp-insights{margin:0 0 16px;padding:18px;border:1px solid #d6e8df;border-radius:14px;background:linear-gradient(135deg,#f5fbf8,#fff)}
.rp-head{display:flex;justify-content:space-between;gap:14px;align-items:end;margin-bottom:14px}.rp-head p{margin:0;color:#237253;font-size:12px;font-weight:700}.rp-head h2{margin:3px 0 0;color:#13384b;font-size:18px}.rp-head>span{color:#718296;font-size:12px}
.rp-conclusions{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
.rp-conclusions article{display:flex;gap:10px;padding:12px;border-radius:12px;background:#fff;border:1px solid #e3eee8}.rp-conclusions i{flex:none;width:32px;height:32px;border-radius:9px;display:grid;place-items:center;font-style:normal;font-weight:700;color:#fff;background:#2b8f64}
.rp-conclusions .k-customer i{background:#de6c5f}.rp-conclusions .k-credit i{background:#d8902d}.rp-conclusions .k-model i{background:#4478cc}
.rp-conclusions b{display:block;color:#13384b;font-size:13px}.rp-conclusions span{display:block;margin-top:4px;color:#4b5f70;font-size:12px;line-height:1.55}
.rp-grid{display:grid;grid-template-columns:1fr 1.25fr;gap:12px}
.rp-card{padding:14px 16px;border-radius:12px;background:#fff;border:1px solid #e3eee8}.rp-card h3{margin:0;display:flex;gap:8px;align-items:center;color:#13384b;font-size:15px}.rp-card h3 em{font-style:normal;font-size:12px;color:#fff;background:#237253;border-radius:6px;padding:1px 7px}
.rp-note{margin:6px 0 10px;color:#718296;font-size:12px;line-height:1.5}
.rp-tier{padding:10px 0;border-bottom:1px dashed #e3eee8}.rp-tier:last-child{border:0}.rp-tier__top{display:flex;justify-content:space-between;align-items:baseline}.rp-tier__top b{color:#13384b}.rp-tier__top span{font-size:12px;color:#718296}
.rp-bar{position:relative;height:10px;margin:8px 0;border-radius:99px;background:#eef3f0;overflow:hidden}.rp-bar i{position:absolute;left:0;top:0;bottom:0;border-radius:99px}.rp-bar .p75{background:#b7dccb}.rp-bar .mid{background:#2b8f64}
.rp-tier__stats{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 10px;font-size:12px;color:#718296}.rp-tier__stats b{color:#13384b}
.rp-legend{margin:6px 0 0;font-size:12px;color:#718296;display:flex;align-items:center;gap:4px}.rp-legend i{display:inline-block;width:14px;height:8px;border-radius:4px}.rp-legend .mid{background:#2b8f64}.rp-legend .p75{background:#b7dccb;margin-left:8px}
.rp-patterns{display:flex;flex-direction:column;gap:10px;max-height:420px;overflow:auto;padding-right:4px}
.rp-patterns article{padding:10px 12px;border-radius:10px;background:#f8fbfa;border:1px solid #e6efea}
.rp-pattern__head{display:flex;align-items:center;gap:8px}.rp-pattern__head b{color:#4478cc;font-size:12px}.rp-pattern__head strong{color:#13384b;font-size:14px}.rp-pattern__head small{margin-left:auto;color:#718296;font-size:12px}
.rp-prob{width:90px;height:6px;border-radius:99px;background:#e6edf5;overflow:hidden}.rp-prob i{display:block;height:100%;background:#4478cc}
.rp-split{display:flex;height:12px;border-radius:6px;overflow:hidden;margin:8px 0 6px;gap:2px}.rp-split i{display:block}
.rp-nodes{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:#4b5f70}.rp-nodes span{display:inline-flex;align-items:center;gap:5px}.rp-nodes i{width:8px;height:8px;border-radius:2px}.rp-nodes em{font-style:normal;color:#94a3b8}
.rp-credit__head{display:flex;justify-content:space-between;gap:12px;align-items:center}.rp-credit__head>span{font-size:12px;color:#718296}.rp-credit__head b{color:#de6c5f;font-size:14px}
.rp-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px}
.rp-grades{display:flex;gap:6px;flex-wrap:wrap}.rp-grades button{height:28px;padding:0 12px;border-radius:99px;border:1px solid #dbe5ee;background:#fff;color:#4b5f70;font:inherit;font-size:12px;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.rp-grades button em{font-style:normal;font-size:11px;color:#94a3b8}.rp-grades button.on{background:#237253;border-color:#237253;color:#fff}.rp-grades button.on em{color:#d7efe4}
.rp-grade{display:inline-grid;place-items:center;width:28px;height:24px;border-radius:6px;font-weight:700;font-size:13px;color:#fff;background:#94a3b8}
.rp-grade.g-A{background:#2b8f64}.rp-grade.g-B{background:#4478cc}.rp-grade.g-C{background:#d8902d}.rp-grade.g-D{background:#de6c5f}
.rp-sub{display:block;color:#94a3b8;font-size:11px}
.bad{color:#c2410c;font-weight:600}.good{color:#2b8f64;font-weight:600}
.rp-terms{display:flex;gap:12px;align-items:center;padding:6px 16px 6px 60px;font-size:13px}.rp-terms b{flex:none;color:#237253}.rp-terms span{flex:1;color:#334155;line-height:1.6}
.rp-foot{margin:8px 0 0;font-size:12px;color:#94a3b8}
@media(max-width:1100px){.rp-conclusions{grid-template-columns:1fr 1fr}.rp-grid{grid-template-columns:1fr}}
@media(max-width:650px){.rp-conclusions{grid-template-columns:1fr}.rp-head{flex-direction:column;align-items:flex-start}.rp-tier__stats{grid-template-columns:1fr 1fr}.rp-terms{flex-direction:column;align-items:flex-start;padding-left:16px}}
</style>
