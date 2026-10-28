<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CrmOpportunity, CrmPlaybook } from '../../../src/services/personalWorkApi'
import { opportunityProbability } from './opportunityProbability'
import { opportunityKey } from './opportunityDetail'
const props = defineProps<{ opportunities: CrmOpportunity[]; followups: CrmPlaybook['followups'] }>()
const emit = defineEmits<{ select: [item: CrmOpportunity] }>()
const open = (o: CrmOpportunity) => !o.cancelled && (!o.outcome || o.outcome === 'open')
const active = computed(() => props.opportunities.filter(open))
const plans = computed(() => {
 const m = new Map<string, number>()
 for (const f of props.followups) if (f.project_id && !f.completed_at) m.set(JSON.stringify([(f as { _owner?: string })._owner || '', f.project_id]), (m.get(JSON.stringify([(f as { _owner?: string })._owner || '', f.project_id])) || 0) + 1)
 return m
})
const assessed = computed(() => active.value.map(item => ({ item, model:opportunityProbability(item, plans.value.get(JSON.stringify([item._owner || '', item.code])) || 0) })))
const pct = (n:number, d:number) => d ? `${(100*n/d).toFixed(1)}%` : '—'
const amount = (items:CrmOpportunity[]) => items.reduce((sum,o)=>sum+Number(o.amount || 0),0)
const fmt = (n:number) => n.toLocaleString('zh-CN',{maximumFractionDigits:1})
const outcomes = computed(() => [
 { label:'赢单', color:'#1f9d63', items:props.opportunities.filter(o=>!o.cancelled && o.outcome==='won') },
 { label:'输单', color:'#da6464', items:props.opportunities.filter(o=>!o.cancelled && o.outcome==='lost') },
 { label:'取消', color:'#98a6bc', items:props.opportunities.filter(o=>o.cancelled || o.outcome==='cancelled') },
])
const closed = computed(()=>outcomes.value[0]!.items.length + outcomes.value[1]!.items.length)
const winRate = computed(()=>pct(outcomes.value[0]!.items.length,closed.value))
const ring = computed(()=>closed.value ? `conic-gradient(#1f9d63 ${100*outcomes.value[0]!.items.length/closed.value}%, #da6464 0)` : '#e6edf6')
function createdMonth(item:CrmOpportunity) {
 const text = item.created_at || ''
 const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text)
 if (!match || Number(match[2])<1 || Number(match[2])>12 || Number(match[3])<1 || Number(match[3])>31) return ''
 return text.slice(0,7)
}
const months = computed(()=>{
 const now=new Date()
 return Array.from({length:6},(_,i)=>{
  const d=new Date(now.getFullYear(),now.getMonth()-5+i,1)
  const key=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`
  const items=props.opportunities.filter(o=>createdMonth(o)===key)
  return {key,label:`${d.getMonth()+1}月`,items}
 })
})
const maxMonth = computed(()=>Math.max(1,...months.value.map(m=>m.items.length)))
const undated = computed(()=>props.opportunities.filter(o=>!createdMonth(o)).length)
const quality = computed(()=>[
 {label:'负责人明确',items:active.value.filter(o=>!!o.manager?.trim())},
 {label:'客户已关联',items:active.value.filter(o=>!!o.owner_unit_id)},
 {label:'金额已填写',items:active.value.filter(o=>Number(o.amount)>0)},
 {label:'有阶段材料',items:assessed.value.filter(x=>x.model.evidence.materials>0).map(x=>x.item)},
 {label:'有阶段关系人',items:assessed.value.filter(x=>x.model.evidence.contacts>0).map(x=>x.item)},
 {label:'有未完成计划',items:active.value.filter(o=>(plans.value.get(JSON.stringify([o._owner || '', o.code]))||0)>0)},
])
const supported = computed(()=>assessed.value.filter(x=>x.model.evidence.materials>0 && x.model.evidence.contacts>0 && (plans.value.get(JSON.stringify([x.item._owner || '', x.item.code]))||0)>0).length)
const matrix = computed(()=>['高概率 ≥70%','中概率 40–69%','低概率 <40%'].map((label,i)=>({label,cells:['weak','medium','strong'].map(s=>assessed.value.filter(x=>x.model.support===s && (i===0?x.model.probability>=70:i===1?x.model.probability>=40 && x.model.probability<70:x.model.probability<40)).map(x=>x.item))})))
const priorities = computed(()=>assessed.value.map(({item,model})=>{
 const gaps:string[]=[]
 if (!item.manager?.trim()) gaps.push('指派负责人')
 if (!item.owner_unit_id) gaps.push('关联客户')
 if (!model.evidence.contacts) gaps.push('补关键关系人')
 if (!model.evidence.materials) gaps.push('补阶段材料')
 if (!(plans.value.get(JSON.stringify([item._owner || '', item.code]))||0)) gaps.push('安排跟进计划')
 return {item,model,gaps,score:(model.probability>=70 && model.support==='weak'?20:0)+gaps.length}
}).filter(x=>x.gaps.length).sort((a,b)=>b.score-a.score || Number(b.item.amount||0)-Number(a.item.amount||0)))
const drill = ref<{title:string;items:CrmOpportunity[]}|null>(null)
const page = ref(1)
function inspect(title:string,items:CrmOpportunity[]) {page.value=1;drill.value={title,items}}
function select(item:CrmOpportunity) {drill.value=null;emit('select',item)}
</script>
<template>
 <section class="growth-analytics" aria-label="商机增长与赢率分析">
  <header class="growth-head"><div><span>获取数量 → 补强质量 → 提升赢率</span><h2>商机增长与赢单分析</h2><p>用实际结果衡量成交，用资料与行动覆盖识别下一步；分析范围为当前授权可见商机。</p></div><div class="growth-highlight"><small>材料 + 关系人 + 未完成计划均具备</small><b>{{ supported }}<em> / {{ active.length }} 条在谈</em></b></div></header>
  <div class="growth-grid">
   <article class="growth-card">
    <header><h3>获取数量 · 近六个月入库</h3><span>点击月份查看记录</span></header>
    <div class="growth-months"><button v-for="m in months" :key="m.key" :title="`${m.key} 入库 ${m.items.length} 条`" @click="inspect(`${m.key}入库商机`,m.items)"><b>{{ m.items.length }}</b><div><i :style="{height:100*m.items.length/maxMonth+'%'}"></i></div><span>{{ m.label }}</span></button></div>
    <p class="growth-note">按记录创建时间统计，包含导入；不等同真实获客日期或净新增。{{ undated }} 条缺少可用创建时间，未计入图表。来源渠道、历史阶段流转尚未记录，不推算渠道获客率或阶段转化率。</p>
   </article>
   <article class="growth-card">
    <header><h3>赢率结果 · 实际赢输</h3><span>已决标样本 {{ closed }} 条</span></header>
    <div class="growth-outcome"><div class="growth-ring" :style="{background:ring}"><div><b>{{ winRate }}</b><small>实际赢单率</small></div></div><div class="growth-results"><button v-for="o in outcomes" :key="o.label" @click="inspect(o.label+'商机',o.items)"><i :style="{background:o.color}"></i><span>{{ o.label }}</span><b>{{ o.items.length }} 条</b><small>{{ fmt(amount(o.items)) }} 万</small></button></div></div>
    <p class="growth-note">赢单率 = 赢单 /（赢单 + 输单），取消与在谈不计入分母。{{ closed ? '该指标为可见记录累计结果，不是预测概率。' : '暂无已决标样本，不能判断实际赢率。' }}</p>
   </article>
   <article class="growth-card">
    <header><h3>商机质量 · 六项覆盖</h3><span>在谈 {{ active.length }} 条</span></header>
    <div class="growth-quality"><button v-for="q in quality" :key="q.label" @click="inspect(q.label+'的在谈商机',q.items)"><span>{{ q.label }}</span><i><em :style="{width:(active.length?100*q.items.length/active.length:0)+'%'}"></em></i><b>{{ q.items.length }} · {{ pct(q.items.length,active.length) }}</b></button></div>
    <p class="growth-note">覆盖率代表已登记信息与行动支撑，不等同客户意愿或商机价值。客户关联按已填写关联标识计数。</p>
   </article>
   <article class="growth-card">
    <header><h3>赢率诊断 · 概率 × 支撑</h3><span>点击单元格查看商机</span></header>
    <div class="growth-matrix"><span></span><small>支撑不足</small><small>支撑一般</small><small>支撑充分</small><template v-for="(row,i) in matrix" :key="row.label"><span>{{ row.label }}</span><button v-for="(items,j) in row.cells" :key="j" :class="{risk:i===0 && j===0 && items.length,ready:j===2 && items.length}" @click="inspect(row.label+' · '+['支撑不足','支撑一般','支撑充分'][j],items)"><b>{{ items.length }}</b><small>{{ fmt(amount(items)) }} 万</small></button></template></div>
    <p class="growth-note">优先核实“高概率、支撑不足”的商机。预测沿用现有阶段、登记赢率与支撑规则，不能当作实际成交承诺。</p>
   </article>
   <article class="growth-card growth-wide">
    <header><h3>优先补强清单</h3><button class="growth-more" @click="inspect('全部待补强商机',priorities.map(x=>x.item))">查看全部 {{ priorities.length }} 条 →</button></header>
    <p class="growth-note">先列高概率但支撑不足的商机，再按缺项数量、金额排序；点击进入详情补齐资料或安排推进。</p>
    <div class="growth-actions"><button v-for="row in priorities.slice(0,5)" :key="opportunityKey(row.item)" @click="select(row.item)"><div><strong>{{ row.item.name || row.item.code }}</strong><small>{{ row.item.manager || '待指派' }} · {{ fmt(Number(row.item.amount||0)) }} 万 · 预测 {{ row.model.probability }}%</small></div><span>{{ row.gaps.join(' / ') }}</span><b>查看处理 →</b></button><p v-if="!priorities.length" class="growth-note">{{ active.length ? '当前在谈商机未发现上述待补强项。' : '暂无在谈商机，可先新建或导入。' }}</p></div>
   </article>
  </div>
  <el-drawer :model-value="!!drill" :title="drill?.title" size="min(780px,96vw)" append-to-body @close="drill=null">
   <p>共 {{ drill?.items.length || 0 }} 条，点击名称查看详情。</p>
   <el-table :data="drill?.items.slice((page-1)*20,page*20) || []" empty-text="暂无匹配商机"><el-table-column label="商机" min-width="200"><template #default="{row}"><el-button link type="primary" @click="select(row)">{{ row.name || row.code }}</el-button></template></el-table-column><el-table-column prop="manager" label="负责人" min-width="100"/><el-table-column label="金额（万）" min-width="110"><template #default="{row}">{{ fmt(Number(row.amount||0)) }}</template></el-table-column></el-table>
   <el-pagination v-if="(drill?.items.length || 0)>20" v-model:current-page="page" :page-size="20" :total="drill?.items.length || 0" layout="prev,pager,next,total"/>
  </el-drawer>
 </section>
</template>
<style scoped>
.growth-analytics{margin-bottom:24px;color:#274665}.growth-head{display:flex;justify-content:space-between;gap:20px;padding:22px;border:1px solid #dce7f7;border-radius:14px;background:linear-gradient(110deg,#edf5ff,#f2faf8);margin-bottom:16px}.growth-head span{font-size:12px;color:#287485}.growth-head h2{font-size:22px;margin:8px 0}.growth-head p{font-size:12px;color:#657d96;margin:0;line-height:1.6}.growth-highlight{display:flex;flex-direction:column;justify-content:center;flex:none}.growth-highlight small{color:#5e7893;font-size:11px}.growth-highlight b{font-size:30px;color:#117c83}.growth-highlight em{font-size:12px;font-style:normal;font-weight:400}.growth-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.growth-card{min-width:0;padding:20px;border:1px solid #dce7f4;background:#fff;border-radius:12px}.growth-card>header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.growth-card h3{margin:0;font-size:16px;color:#15499c}.growth-card header>span{font-size:11px;color:#7890a8}.growth-note{font-size:12px;line-height:1.7;color:#76899e;margin:14px 0 0}.growth-wide{grid-column:1/-1}.growth-card button{font:inherit;cursor:pointer}.growth-card button:focus-visible{outline:2px solid #2c69dc;outline-offset:2px}.growth-months{display:flex;gap:18px;height:155px}.growth-months button{flex:1;min-width:0;border:0;background:transparent;display:flex;flex-direction:column;align-items:center;color:#426388;font-size:12px;gap:6px}.growth-months button>div{height:110px;width:100%;display:flex;align-items:flex-end;background:#f7f9fd;border-bottom:1px solid #dce7f7}.growth-months i{display:block;width:75%;margin:auto auto 0;border-radius:5px 5px 0 0;background:linear-gradient(#70adff,#275ec0)}.growth-outcome{display:flex;align-items:center;gap:28px;min-height:155px}.growth-ring{border-radius:50%;width:140px;height:140px;display:grid;place-items:center;flex:none}.growth-ring>div{background:#fff;width:108px;height:108px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:5px}.growth-ring b{font-size:26px;color:#217555}.growth-ring small{color:#7890a8;font-size:11px}.growth-results{flex:1;display:flex;flex-direction:column;gap:10px}.growth-results button{display:flex;align-items:center;gap:8px;border:0;background:#f6f9fd;padding:10px;border-radius:7px;font-size:12px;color:#476481}.growth-results i{width:8px;height:8px;border-radius:50%}.growth-results small{margin-left:auto;color:#71849b}.growth-quality{display:flex;flex-direction:column;gap:12px}.growth-quality button{display:grid;grid-template-columns:110px 1fr 105px;gap:10px;align-items:center;border:0;background:transparent;padding:0;color:#486683;font-size:12px;text-align:left}.growth-quality i{height:9px;border-radius:6px;background:#edf3fa;overflow:hidden}.growth-quality em{display:block;height:100%;background:linear-gradient(90deg,#4d8cdc,#24a4a0)}.growth-quality b{text-align:right;font-size:12px}.growth-matrix{display:grid;grid-template-columns:120px repeat(3,1fr);gap:8px;align-items:center;text-align:center;font-size:12px}.growth-matrix>small{color:#7087a0}.growth-matrix>span{text-align:left}.growth-matrix button{display:flex;flex-direction:column;gap:4px;border:1px solid #e0e9f5;background:#f1f6fd;color:#39689b;padding:10px 4px;border-radius:8px}.growth-matrix b{font-size:20px}.growth-matrix small{font-size:10px}.growth-matrix .risk{background:#fff3eb;border-color:#f4d0b7;color:#b36a2d}.growth-matrix .ready{background:#eef9f5;color:#238367}.growth-more{border:0;background:transparent;color:#2267b4;font-size:12px}.growth-actions{margin-top:12px}.growth-actions>button{display:flex;width:100%;align-items:center;gap:20px;padding:14px 0;border:0;border-bottom:1px solid #e7eef7;background:transparent;text-align:left;color:#395873}.growth-actions>button>div{flex:1;min-width:0}.growth-actions strong{display:block;font-size:13px}.growth-actions small{display:block;font-size:11px;color:#7a8ea5;margin-top:5px}.growth-actions>button>span{flex:1;font-size:12px;color:#b27439;line-height:1.7}.growth-actions>button>b{font-size:12px;color:#2869b5;white-space:nowrap}
@media(max-width:1100px){.growth-grid{grid-template-columns:1fr}.growth-head{flex-wrap:wrap}}@media(max-width:600px){.growth-card{padding:14px}.growth-head{padding:16px}.growth-card>header{align-items:flex-start;flex-direction:column;gap:5px}.growth-quality button{grid-template-columns:88px 1fr 88px;gap:5px}.growth-matrix{grid-template-columns:90px repeat(3,1fr);gap:4px;font-size:10px}.growth-outcome{gap:12px;flex-wrap:wrap}.growth-actions>button{flex-wrap:wrap;gap:8px}.growth-actions>button>div{flex-basis:100%}.growth-months{gap:8px}.growth-ring{width:120px;height:120px}.growth-ring>div{width:94px;height:94px}}
</style>
