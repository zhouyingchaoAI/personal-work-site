<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Aim, FolderRemove, Search } from '@element-plus/icons-vue'
import type { CrmOpportunity, CrmSalesContract, CrmUnit, CrmPerson, CrmPlaybook } from '../../../src/services/personalWorkApi'
import StaffPicker from './StaffPicker.vue'
import { opportunityKey, opportunityTasks, opportunityTaskIndex, opportunityContacts } from './opportunityDetail'
import { associationCandidates } from './crmCompletion'
import { OPPORTUNITY_STAGE_NAMES } from './opportunityStages'
import OpportunityStagePanel from './OpportunityStagePanel.vue'
import OpportunityAnalytics from './OpportunityAnalytics.vue'
import SalesContractManagement from './SalesContractManagement.vue'
import { opportunityProbability, opportunityVerifyUrl, PROBABILITY_SUPPORT_LABEL } from './opportunityProbability'
const props = defineProps<{ active?: boolean; focus?: {code: string; key?: string; sequence: number; unitId?: string}; opportunities: CrmOpportunity[]; contracts: CrmSalesContract[]; units: CrmUnit[]; people: CrmPerson[]; followups: CrmPlaybook['followups']; canImport: boolean; canExport: boolean; canEdit: boolean; saveOpportunity: (opportunity: Partial<CrmOpportunity>) => Promise<boolean> }>()
const emit = defineEmits<{ import: []; contractImport: []; template: []; battle: [code: string]; save: [opportunity: Partial<CrmOpportunity>]; refresh: []; export: [filters: { state: 'all' | 'active' | 'archived'; stage: string; region: string; sales_stage: string; keyword: string }] }>()
const query = ref(''), state = ref<'all' | 'active' | 'archived'>('all'), stage = ref('all'), region=ref('all'), salesStage=ref('all')
const unlinkedOnly=ref(false)
const visibleUnits=computed(()=>new Set(props.units.map(u=>u.id)))
const unlinkedCount=computed(()=>props.opportunities.filter(o=>!o.owner_unit_id || !visibleUnits.value.has(o.owner_unit_id)).length)
const stages = computed(() => [...new Set(props.opportunities.map(item => item.stage).filter(Boolean))])
const regions=['东区','西区','中区','广东区']
const salesStages=computed(()=>[...new Set([...OPPORTUNITY_STAGE_NAMES,...props.opportunities.map(o=>o.sales_stage?.trim()).filter(Boolean)])])
const scoped = computed(() => props.opportunities.filter(item => (!unlinkedOnly.value || !item.owner_unit_id || !visibleUnits.value.has(item.owner_unit_id)) && (stage.value === 'all' || (item.stage?.trim() || '__missing__') === stage.value) && (region.value==='all' || (item.region?.trim() || '__missing__')===region.value) && (salesStage.value==='all' || (item.sales_stage?.trim() || '__missing__')===salesStage.value) && `${item.code} ${item.name} ${item.owner_unit} ${item.manager}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const filtered=computed(()=>scoped.value.filter(item=>state.value==='all'||(state.value==='active'?!item.cancelled:item.cancelled)))
const active = computed(() => scoped.value.filter(item => !item.cancelled).length)
const archived = computed(() => scoped.value.filter(item => item.cancelled).length)
const editing = ref(false)
const form = ref<Partial<CrmOpportunity>>({})
const candidates=computed(()=>associationCandidates(form.value.owner_unit||'',props.units))
const pending = ref(false)
const page = ref(1)
const pageRows = computed(() => filtered.value.slice((page.value-1)*20,page.value*20))
watch([query, state, stage, region, salesStage, unlinkedOnly, () => props.opportunities], () => { page.value = 1 })
const outcomeLabels = { open: '进行中', won: '赢单', lost: '输单', cancelled: '取消' }
function fmtDate(value?: string) { const s = String(value || '').trim(); if (!s) return '待定'; const m = s.match(/(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})/); return m ? `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}` : s.slice(0, 10) }
const listView = ref<'list' | 'analytics' | 'contracts'>('analytics')
const followupCount = computed(() => { const m = new Map<string, number>(); for (const f of props.followups || []) if (f.project_id && !f.completed_at) { const key = JSON.stringify([(f as { _owner?: string })._owner || '', f.project_id]); m.set(key, (m.get(key) || 0) + 1) }; return m })
function probFor(o: CrmOpportunity) { return opportunityProbability(o, followupCount.value.get(JSON.stringify([o._owner || '', o.code])) || 0) }
function probTone(p: number) { return p >= 70 ? '#1f9d63' : p >= 40 ? '#d98921' : '#d64545' }
function verifyOnline(o: CrmOpportunity) { window.open(opportunityVerifyUrl(o), '_blank', 'noopener') }
const nextTasks = computed(() => opportunityTaskIndex(props.opportunities,props.followups))
const detailKey = ref(''), showAllContacts = ref(false)
const detail = computed(() => props.opportunities.find(item => opportunityKey(item) === detailKey.value))
const detailOpen = computed({get:()=>!!detail.value,set:(value:boolean)=>{if(!value)detailKey.value=''}})
const detailTasks = computed(() => detail.value ? opportunityTasks(detail.value,props.followups) : [])
const detailContacts = computed(() => detail.value ? opportunityContacts(detail.value,props.units,props.people) : [])
function viewDetail(item: CrmOpportunity) { detailKey.value=opportunityKey(item);showAllContacts.value=false }
function editDetail() { if(detail.value){openEdit(detail.value);detailKey.value=''} }
function battleFor(item: CrmOpportunity) {
  if (props.opportunities.filter(o=>o.code===item.code).length!==1) return ElMessage.warning('存在同编号商机，暂不能唯一定位推进建议；请先核对编号归属')
  detailKey.value='';emit('battle',item.code)
}
watch(() => props.active, value => { if(value===false)detailKey.value='' })
function create(unitId = '') { if(!props.canEdit)return; const unit=props.units.find(u=>u.id===unitId); form.value = { code: `OPP-${crypto.randomUUID()}`, name: '', owner_unit: unit?.name || '', owner_unit_id: unit?.id || '', manager: '', sales_stage: OPPORTUNITY_STAGE_NAMES[0], outcome: 'open', win_rate: '' }; editing.value = true }
function openEdit(item: CrmOpportunity) { form.value = { ...item, outcome: item.outcome || (item.cancelled ? 'cancelled' : 'open') }; editing.value = true }
async function saveEdit() {
  if (pending.value) return
  if (!form.value.name?.trim() || !form.value.owner_unit?.trim()) return
  if (!form.value.id && (!form.value.owner_unit_id || !form.value.manager)) return ElMessage.warning('请选择客户和负责人')
  pending.value = true
  try { if (await props.saveOpportunity({ ...form.value, amount: Number(form.value.amount || 0) })) editing.value = false }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '保存失败，请重试') }
  finally { pending.value = false }
}
watch(() => props.focus?.sequence, () => {
  query.value = props.focus?.code || ''; state.value = 'all'; stage.value = 'all'; region.value='all';salesStage.value='all'; detailKey.value='';unlinkedOnly.value=false
  if(props.focus?.unitId)create(props.focus.unitId)
  else if(props.focus?.key) {
    const item=props.opportunities.find(o=>opportunityKey(o)===props.focus?.key)
    if(item)viewDetail(item)
    else ElMessage.warning('该商机已不在当前可见范围，请刷新后重试')
  }
}, {immediate:true})
</script>
<template>
 <section class="opportunity-management">
  <div class="om-toolbar"><div class="om-viewtabs" role="tablist" aria-label="商机视图"><button type="button" role="tab" :aria-selected="listView==='list'" :class="{active:listView==='list'}" @click="listView='list'">商机清单</button><button type="button" role="tab" :aria-selected="listView==='analytics'" :class="{active:listView==='analytics'}" @click="listView='analytics'">统计分析</button><button type="button" role="tab" :aria-selected="listView==='contracts'" :class="{active:listView==='contracts'}" @click="listView='contracts'">销售合同</button></div><div class="om-actions"><el-button @click="emit('template')">下载模板</el-button><el-button :disabled="!canExport || unlinkedOnly" :title="unlinkedOnly?'请取消待核对筛选后导出':''" @click="emit('export',{state,stage,region,sales_stage:salesStage,keyword:query})">导出</el-button><el-button :disabled="!canImport" @click="emit('import')">导入商机</el-button><el-button :disabled="!canImport" @click="emit('contractImport')">导入销售合同</el-button><el-button type="primary" :disabled="!canEdit" @click="create()">新建商机</el-button></div></div>
  <OpportunityAnalytics v-if="listView==='analytics'" :opportunities="opportunities" :contracts="contracts" :followups="followups" @select="viewDetail" />
  <SalesContractManagement v-else-if="listView==='contracts'" :contracts="contracts" :opportunities="opportunities" />
  <template v-else>
  <div class="om-kpis" role="group" aria-label="机会点状态筛选">
<button :class="{active:state==='all'}" @click="state='all'"><span class="om-ic om-ic--blue"><el-icon><Collection/></el-icon></span><span class="om-body"><span class="om-label">全部机会点</span><b>{{scoped.length}}</b></span></button>
   <button :class="{active:state==='active'}" @click="state='active'"><span class="om-ic om-ic--green"><el-icon><Aim/></el-icon></span><span class="om-body"><span class="om-label">有效机会点</span><b class="om-green">{{active}}</b></span></button>
   <button :class="{active:state==='archived'}" @click="state='archived'"><span class="om-ic om-ic--grey"><el-icon><FolderRemove/></el-icon></span><span class="om-body"><span class="om-label">作废归档</span><b class="om-grey">{{archived}}</b></span></button>
  </div>
  <div class="om-filters"><el-input v-model="query" :prefix-icon="Search" clearable placeholder="搜索编号、机会点、业主单位或客户经理"/><el-select v-model="region" aria-label="商机区域"><el-option label="全部区域" value="all"/><el-option v-for="r in regions" :key="r" :label="r" :value="r"/><el-option label="区域待补充" value="__missing__"/></el-select><el-select v-model="salesStage" aria-label="项目阶段筛选"><el-option label="全部项目阶段" value="all"/><el-option v-for="s in salesStages" :key="s" :label="s" :value="s"/><el-option label="阶段待确认" value="__missing__"/></el-select><el-select v-if="stages.length" v-model="stage" aria-label="阶段备注筛选"><el-option label="全部阶段备注" value="all"/><el-option label="备注待补充" value="__missing__"/><el-option v-for="item in stages" :key="item" :label="item" :value="item"/></el-select><el-button @click="query='';region='all';salesStage='all';stage='all';state='all';unlinkedOnly=false">重置筛选</el-button></div>
  <el-checkbox v-model="unlinkedOnly">仅看客户关联待核对（{{unlinkedCount}}）</el-checkbox>
  <p v-if="unlinkedOnly" class="om-association-note">仅推荐当前可见组织，不自动迁移历史数据。原关联不在可见范围时也会列入核对，请勿仅凭名称覆盖。此视图暂不支持导出。</p>
  <div class="om-result-note">当前显示 <b>{{ filtered.length }}</b> 条；导出会包含当前筛选下的完整业务字段。</div>
  <el-table :data="pageRows" empty-text="暂无匹配机会点" max-height="560">
   <el-table-column label="商机 / 客户" min-width="280"><template #default="{row}"><el-button link type="primary" @click="viewDetail(row)">{{row.name}}</el-button><small>{{row.code}}</small><small>{{row.owner_unit || '业主待补充'}}</small></template></el-table-column>
   <el-table-column label="项目归属 / 客户经理" min-width="140"><template #default="{row}"><span>{{row.region || '归属待补充'}}</span><small>{{row.manager || '客户经理待补充'}}</small></template></el-table-column>
   <el-table-column label="项目阶段" min-width="130"><template #default="{row}"><span>{{row.sales_stage || '待确认'}}</span><small v-if="row.stage">备注：{{row.stage}}</small></template></el-table-column>
   <el-table-column label="可参与份额 / 投资规模" min-width="150" align="right"><template #default="{row}"><strong class="om-amount">{{ row.amount ? Number(row.amount).toLocaleString('zh-CN') + ' 万' : '待补充' }}</strong><small>投资 {{ row.investment ? Number(row.investment).toLocaleString('zh-CN') + ' 万' : '—' }} · 赢率 {{ row.win_rate || '—' }}</small></template></el-table-column>
   <el-table-column label="成单概率" min-width="120"><template #default="{row}"><template v-if="!row.cancelled && (!row.outcome || row.outcome==='open')"><strong :style="{color:probTone(probFor(row).probability)}" class="om-prob">{{ probFor(row).probability }}%</strong><small>{{ PROBABILITY_SUPPORT_LABEL[probFor(row).support] }}</small></template><span v-else class="om-dim">{{ row.outcome==='won'?'已赢单':row.outcome==='lost'?'已输单':'已作废' }}</span></template></el-table-column>
   <el-table-column label="关键时间" min-width="170"><template #default="{row}"><span :class="{'om-dim':!row.bid_date}">招标 {{ fmtDate(row.bid_date) }}</span><small :class="{'om-dim':!row.contract_date}">签约 {{ fmtDate(row.contract_date) }}</small><el-button link type="primary" size="small" class="om-verify" @click="verifyOnline(row)">联网核对</el-button></template></el-table-column>
   <el-table-column label="下一步 / 日期" min-width="200"><template #default="{row}"><span>{{nextTasks.get(opportunityKey(row))?.next_step || '尚未安排跟进'}}</span><small>{{nextTasks.get(opportunityKey(row))?.due_date || '日期待补充'}}</small></template></el-table-column>
   <el-table-column label="成交结果" min-width="120"><template #default="{row}"><el-tag :type="row.cancelled?'info':'success'">{{outcomeLabels[row.outcome as keyof typeof outcomeLabels] || (row.cancelled ? '取消' : '进行中')}}</el-tag><small v-if="row.cancelled">{{row.cancel_reason || '未填写取消原因'}}</small></template></el-table-column>
   <el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click="battleFor(row)">推进建议</el-button><el-button link :disabled="!canEdit" @click="openEdit(row)">编辑</el-button></template></el-table-column>
  </el-table>
  <el-pagination v-if="filtered.length > 20" v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next, total" />
  </template>
  <el-drawer v-model="detailOpen" title="商机详情" size="min(720px,96vw)" append-to-body destroy-on-close>
   <section v-if="detail" class="om-detail">
    <h2>{{ detail.name }}</h2><p>{{ detail.owner_unit || '客户待确认' }} · {{ detail.code }}</p>
    <dl><div><dt>项目阶段</dt><dd>{{ detail.sales_stage || '待确认' }}</dd></div><div><dt>区域</dt><dd>{{ detail.region || '待补充' }}</dd></div><div><dt>负责人</dt><dd>{{ detail.manager || '待指派' }}</dd></div><div><dt>成交结果</dt><dd>{{ detail.cancelled ? '取消' : outcomeLabels[detail.outcome || 'open'] }}</dd></div><div><dt>可参与份额</dt><dd>{{ detail.amount ? Number(detail.amount).toLocaleString('zh-CN') + ' 万元' : '待补充' }}</dd></div><div><dt>赢率</dt><dd>{{ detail.win_rate || '待补充' }}</dd></div><div><dt>实际签约</dt><dd>{{ fmtDate(detail.contract_date) }}</dd></div><div><dt>销售合同</dt><dd>{{ detail.contract_count ? `${detail.contract_count} 份 · ${Number(detail.contract_amount_yuan || 0).toLocaleString('zh-CN')} 元` : '暂无匹配合同' }}</dd></div></dl>
    <div class="om-detail-actions"><el-button type="primary" @click="battleFor(detail)">推进建议 / 安排跟进</el-button><el-button :disabled="!canEdit" @click="editDetail">编辑商机</el-button><el-button @click="verifyOnline(detail)">联网核对时间点</el-button></div>
    <section v-if="!detail.cancelled && (!detail.outcome || detail.outcome==='open')" class="om-prob-panel">
      <div class="om-prob-head"><div class="om-prob-ring" :style="{'--p':probFor(detail).probability, '--c':probTone(probFor(detail).probability)}"><b :style="{color:probTone(probFor(detail).probability)}">{{ probFor(detail).probability }}%</b></div><div><h3>成单概率</h3><p>{{ PROBABILITY_SUPPORT_LABEL[probFor(detail).support] }} · 综合所处阶段、登记赢率与动作/材料支撑判定</p></div></div>
      <div class="om-prob-cols">
        <div><h4>判断依据（动作 / 材料支撑）</h4><ul><li v-for="(r,i) in probFor(detail).reasons" :key="'r'+i">{{ r }}</li></ul></div>
        <div v-if="probFor(detail).gaps.length"><h4>待补强</h4><ul class="om-prob-gaps"><li v-for="(g,i) in probFor(detail).gaps" :key="'g'+i">{{ g }}</li></ul></div>
      </div>
      <p class="om-prob-tip">提示：商机时间点（招标 / 签约）建议点“联网核对时间点”用真实招标/中标公告确认，防止商机有误。</p>
    </section>
    <h3>下一步 · {{ detailTasks.length }}</h3><p v-if="!detailTasks.length">尚未安排商机跟进，可通过推进建议选择联系人并安排。</p>
    <article v-for="task in detailTasks" :key="task.id"><strong>{{ task.next_step }}</strong><p>{{ task.person_name }} · {{ task.owner_label || task.owner || '负责人待补充' }} · {{ task.due_date || '日期待补充' }}<el-tag v-if="task.overdue" type="danger" size="small">逾期</el-tag></p></article>
    <h3>客户联系人 · {{ detailContacts.length }}</h3><p>按已登记决策角色优先展示，项目关键人仍需核实。</p>
    <p v-if="!detail.owner_unit_id">尚未明确关联客户，请先编辑商机确认；不会按名称自动匹配。</p>
    <p v-else-if="!detailContacts.length">关联客户暂无可见联系人。</p>
    <article v-for="person in (showAllContacts ? detailContacts : detailContacts.slice(0,8))" :key="person.id"><strong>{{ person.name }}</strong><p>{{ person.decision_role || '决策角色待确认' }} · {{ person.department || person.title || '岗位待补充' }}</p></article>
    <el-button v-if="detailContacts.length>8" link type="primary" @click="showAllContacts=!showAllContacts">{{ showAllContacts ? '收起' : `查看全部 ${detailContacts.length} 位联系人` }}</el-button>
    <h3>阶段进展 · 时间管控 / 主要工作 / 证明材料</h3>
    <OpportunityStagePanel :key="detail.id + ':' + detail.version" :opportunity="detail" :people="people" :can-edit="canEdit" @saved="emit('refresh')" />
    <details><summary>更多项目资料</summary><p>项目阶段：{{ detail.stage || '待补充' }}</p><p>可参与份额：{{ detail.amount ?? '待补充' }} 万元（不等同于预计收入）</p><p>赢率：{{ detail.win_rate || '待补充' }}</p><p v-if="detail.cancelled">取消原因：{{ detail.cancel_reason || '待补充' }}</p></details>
   </section>
  </el-drawer>
  <el-dialog v-model="editing" :title="form.id ? '编辑商机' : '新建商机'" :close-on-click-modal="!pending" :close-on-press-escape="!pending" :show-close="!pending" width="min(760px,94vw)" append-to-body>
   <el-form label-position="top" class="om-editor" :disabled="pending">
    <el-form-item label="商机名称"><el-input v-model="form.name" placeholder="填写商机名称" /></el-form-item>
    <el-form-item label="关联客户"><el-select v-model="form.owner_unit_id" filterable clearable placeholder="选择客户组织" @change="(id: string) => { if (id) form.owner_unit = units.find(u => u.id === id)?.name || form.owner_unit }"><el-option v-for="u in units" :key="u.id" :value="u.id" :label="`${u.name} · ${u.company_full_name || u.type}`" /></el-select><small v-if="!form.owner_unit_id">旧记录可暂保留业主名称，选择客户后建立明确关联。</small></el-form-item>
    <div v-if="form.id && (!form.owner_unit_id || !visibleUnits.has(form.owner_unit_id))" class="om-candidates"><p>客户关联待核对：以下只是名称候选，选择后仍需保存确认。</p><div v-for="candidate in candidates" :key="candidate.unit.id"><el-button :disabled="pending" @click="form.owner_unit_id=candidate.unit.id;form.owner_unit=candidate.unit.name">{{candidate.unit.name}} · {{candidate.exact?'名称一致':'名称相近'}}</el-button><small>{{candidate.unit.company_full_name || candidate.unit.type || '类型待补充'}} · 上级：{{units.find(u=>u.id===candidate.unit.parent_unit_id)?.name || '无可见上级'}} · ID：{{candidate.unit.id}}</small></div><p v-if="!candidates.length">没有可靠的名称候选，请在上方手动选择客户。</p></div>
    <el-form-item label="负责人"><StaffPicker v-model="form.manager" /></el-form-item>
    <el-row :gutter="14"><el-col :span="12"><el-form-item label="项目阶段"><el-select v-model="form.sales_stage" clearable><el-option v-for="s in OPPORTUNITY_STAGE_NAMES" :key="s" :label="s" :value="s" /></el-select></el-form-item></el-col><el-col :span="12"><el-form-item label="成交结果"><el-select v-model="form.outcome"><el-option v-for="s in [{value:'open',label:'进行中'},{value:'won',label:'赢单'},{value:'lost',label:'输单'},{value:'cancelled',label:'取消'}]" :key="s.value" :label="s.label" :value="s.value" /></el-select></el-form-item></el-col></el-row>
    <details><summary>更多信息：项目阶段、金额、日期</summary>
    <el-form-item label="商机编号"><el-input v-model="form.code" disabled /></el-form-item>
    <el-form-item label="业主名称"><el-input v-model="form.owner_unit" :disabled="!!form.owner_unit_id" /></el-form-item>
    <el-row :gutter="14"><el-col :span="8"><el-form-item label="项目归属 / 区域"><el-input v-model="form.region"/></el-form-item></el-col><el-col :span="8"><el-form-item label="阶段备注（选填）"><el-input v-model="form.stage" placeholder="补充说明，可留空"/></el-form-item></el-col><el-col :span="8"><el-form-item label="赢率"><el-input v-model="form.win_rate" placeholder="例如：60%"/></el-form-item></el-col></el-row>
    <el-row :gutter="14"><el-col :span="12"><el-form-item label="预计招标时间"><el-date-picker v-model="form.bid_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col><el-col :span="12"><el-form-item label="预计签约时间"><el-date-picker v-model="form.contract_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col></el-row>
    <el-row :gutter="14"><el-col :span="12"><el-form-item label="可参与份额（万元）"><el-input-number v-model="form.amount" :min="0" :precision="2" style="width:100%"/></el-form-item></el-col><el-col :span="12"><el-form-item label="业务状态"><el-input v-model="form.status" placeholder="例如：跟进中"/></el-form-item></el-col></el-row>
    </details>
    <el-form-item v-if="form.outcome === 'cancelled'" label="取消原因"><el-input v-model="form.cancel_reason" type="textarea" :rows="2"/></el-form-item>
   </el-form>
   <template #footer><el-button :disabled="pending" @click="editing=false">取消</el-button><el-button type="primary" :loading="pending" :disabled="!form.name?.trim() || !form.owner_unit?.trim()" @click="saveEdit">保存</el-button></template>
  </el-dialog>
 </section>
</template>
<style scoped>
.om-association-note,.om-candidates p{font-size:13px;color:#64748b;line-height:1.7}.om-candidates{margin-bottom:16px}.om-candidates .el-button{max-width:100%;height:auto;white-space:normal;margin:4px 6px 4px 0;padding:8px;overflow-wrap:anywhere}
.om-detail{color:#173656;overflow-wrap:anywhere}.om-detail h2{font-size:20px;margin:0 0 10px}.om-detail h3{font-size:16px;margin:24px 0 10px}.om-detail p,.om-detail dt{color:#64748b;font-size:13px;line-height:1.7}.om-detail dl{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 0}.om-detail dd{margin:5px 0 0}.om-detail article{border-bottom:1px solid #e5eaf1;padding:12px 0}.om-detail-actions{display:flex;gap:8px;flex-wrap:wrap}.om-detail-actions .el-button{margin:0}.om-detail details{margin-top:24px}.om-detail summary{cursor:pointer}.om-detail .el-tag{margin-left:8px}
.opportunity-management{color:#31506d}
.om-amount{color:#15499c;font-variant-numeric:tabular-nums;font-weight:600}
.om-prob{font-size:16px;font-variant-numeric:tabular-nums}
.om-dim{color:#b0bccd}
.om-verify{display:block;margin-top:4px;padding:0}
.om-viewtabs{display:inline-flex;gap:4px;background:#eef3fb;border-radius:9px;padding:3px}
.om-viewtabs button{font:inherit;font-size:14px;border:0;background:transparent;color:#5e7690;border-radius:7px;padding:7px 18px;cursor:pointer}
.om-viewtabs button.active{background:#fff;color:#15499c;font-weight:600;box-shadow:0 2px 8px -4px rgba(21,73,156,.5)}
.om-prob-panel{margin:18px 0 4px;padding:16px;border:1px solid #e1e9f4;border-radius:12px;background:linear-gradient(135deg,#fff,#f7faff)}
.om-prob-head{display:flex;align-items:center;gap:16px;margin-bottom:14px}
.om-prob-ring{flex:none;width:76px;height:76px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--c) calc(var(--p)*1%),#e8eef7 0)}
.om-prob-ring b{width:58px;height:58px;border-radius:50%;background:#fff;display:grid;place-items:center;font-size:17px;font-variant-numeric:tabular-nums}
.om-prob-head h3{margin:0;font-size:16px;color:#15499c}
.om-prob-head p{margin:4px 0 0;font-size:12.5px;color:#64789a;line-height:1.6}
.om-prob-cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.om-prob-cols h4{margin:0 0 6px;font-size:13px;color:#31506d}
.om-prob-cols ul{margin:0;padding-left:18px}
.om-prob-cols li{font-size:12.5px;color:#5e7690;line-height:1.8}
.om-prob-gaps li{color:#c0563f}
.om-prob-tip{margin:12px 0 0;font-size:12px;color:#8a94a6;line-height:1.6}
@media(max-width:650px){.om-prob-cols{grid-template-columns:1fr}}
.om-editor summary{cursor:pointer;margin:8px 0 18px;color:#426184}.om-editor .el-select{width:100%}
.om-toolbar{display:flex;justify-content:space-between;gap:14px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px}
.om-lead h3{margin:0;font-size:16px;color:#173656}
.om-lead span{display:block;margin-top:4px;color:#64789a;font-size:12.5px;line-height:1.6}
.om-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.om-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 16px}
.om-kpis button{display:flex;align-items:center;gap:14px;padding:14px 18px;border:1px solid var(--crm-line,#e4ecf6);border-radius:14px;background:linear-gradient(135deg,#fbfdff,#f4f8ff);color:#5e7690;cursor:pointer;font:inherit;text-align:left;transition:border-color .2s,box-shadow .2s,transform .2s}
.om-kpis button:hover{border-color:#b7d0f2;box-shadow:0 12px 26px -18px rgba(21,73,156,.55);transform:translateY(-1px)}
.om-kpis button:focus-visible{outline:2px solid #1e6bff;outline-offset:2px}
.om-kpis button.active{border-color:#15499c;background:linear-gradient(135deg,#eaf2ff,#f5f9ff);box-shadow:0 0 0 1px #15499c inset}
.om-ic{flex:0 0 auto;display:grid;place-items:center;width:42px;height:42px;border-radius:12px;font-size:21px}
.om-ic--blue{background:#eaf2ff;color:#1e6bff}.om-ic--green{background:#e7f6ef;color:#1f8a72}.om-ic--grey{background:#eef1f6;color:#8192a4}
.om-body{display:flex;flex-direction:column;gap:1px;min-width:0}
.om-label{font-size:12.5px;color:#7c8c9f}
.om-kpis b{font-size:26px;line-height:1.25;color:#216bbb;font-variant-numeric:tabular-nums;font-weight:700}
.om-kpis b.om-green{color:#1f8a72}.om-kpis b.om-grey{color:#8192a4}
.om-filters{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}.om-filters .el-input{max-width:420px}.om-filters .el-select{width:180px}
.om-result-note{margin:0 0 10px;color:#71869a;font-size:12px}.om-result-note b{color:#216bbb;font-weight:600}
.opportunity-management small{display:block;margin-top:5px;color:#8192a4;font-size:12px;line-height:1.45}
.om-editor{padding:0 4px}
@media(max-width:650px){.om-toolbar{align-items:stretch}.om-actions{display:grid;grid-template-columns:1fr 1fr;margin-top:4px;width:100%}.om-actions .el-button{width:100%;margin:0}.om-kpis{grid-template-columns:1fr}.om-filters{display:block}.om-filters .el-input,.om-filters .el-select{width:100%;max-width:none;margin-bottom:8px}.om-editor :deep(.el-col){max-width:100%;flex:0 0 100%}}
.om-kpis{display:flex;gap:8px;flex-wrap:wrap}.om-kpis button{padding:7px 12px;border-radius:7px;background:#fff;gap:8px}.om-kpis .om-ic{display:none}.om-body{flex-direction:row;align-items:center;gap:8px}.om-kpis b{font-size:14px}.om-result-note{display:none}
</style>
