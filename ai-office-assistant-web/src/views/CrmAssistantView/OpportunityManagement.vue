<script setup lang="ts">
import { computed, ref } from 'vue'
import { Collection, Aim, FolderRemove, Search } from '@element-plus/icons-vue'
import type { CrmOpportunity } from '../../services/personalWorkApi'
const props = defineProps<{ opportunities: CrmOpportunity[]; canImport: boolean; canExport: boolean; canEdit: boolean }>()
const emit = defineEmits<{ import: []; battle: [code: string]; save: [opportunity: Partial<CrmOpportunity>]; export: [filters: { state: 'all' | 'active' | 'archived'; stage: string; keyword: string }] }>()
const query = ref(''), state = ref<'all' | 'active' | 'archived'>('all'), stage = ref('all')
const stages = computed(() => [...new Set(props.opportunities.map(item => item.stage).filter(Boolean))])
const filtered = computed(() => props.opportunities.filter(item => (state.value === 'all' || (state.value === 'active' ? !item.cancelled : item.cancelled)) && (stage.value === 'all' || item.stage === stage.value) && `${item.code} ${item.name} ${item.owner_unit} ${item.manager}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const active = computed(() => props.opportunities.filter(item => !item.cancelled).length)
const archived = computed(() => props.opportunities.filter(item => item.cancelled).length)
const editing = ref(false)
const form = ref<Partial<CrmOpportunity>>({})
function openEdit(item: CrmOpportunity) { form.value = { ...item }; editing.value = true }
function saveEdit() {
  if (!form.value.name?.trim() || !form.value.owner_unit?.trim()) return
  emit('save', { ...form.value, amount: Number(form.value.amount || 0) })
  editing.value = false
}
</script>
<template>
 <section class="opportunity-management">
  <div class="om-toolbar"><div class="om-lead"><h3>机会点清单</h3><span>点选下方分组只看有效或作废机会点，或搜索定位后一键进入作战。</span></div><div class="om-actions"><el-button :disabled="!canExport" @click="emit('export',{state,stage,keyword:query})">导出当前结果（{{ filtered.length }}）</el-button><el-button type="primary" :disabled="!canImport" @click="emit('import')">导入机会点</el-button></div></div>
  <div class="om-kpis" role="group" aria-label="机会点状态筛选">
   <button :class="{active:state==='all'}" @click="state='all'"><span class="om-ic om-ic--blue"><el-icon><Collection/></el-icon></span><span class="om-body"><span class="om-label">全部机会点</span><b>{{opportunities.length}}</b></span></button>
   <button :class="{active:state==='active'}" @click="state='active'"><span class="om-ic om-ic--green"><el-icon><Aim/></el-icon></span><span class="om-body"><span class="om-label">有效机会点</span><b class="om-green">{{active}}</b></span></button>
   <button :class="{active:state==='archived'}" @click="state='archived'"><span class="om-ic om-ic--grey"><el-icon><FolderRemove/></el-icon></span><span class="om-body"><span class="om-label">作废归档</span><b class="om-grey">{{archived}}</b></span></button>
  </div>
  <div class="om-filters"><el-input v-model="query" :prefix-icon="Search" clearable placeholder="搜索编号、机会点、业主单位或客户经理"/><el-select v-model="stage"><el-option label="全部阶段" value="all"/><el-option v-for="item in stages" :key="item" :label="item" :value="item"/></el-select></div>
  <div class="om-result-note">当前显示 <b>{{ filtered.length }}</b> 条；导出会包含当前筛选下的完整业务字段。</div>
  <el-table :data="filtered" empty-text="暂无匹配机会点" max-height="560">
   <el-table-column label="机会点 / 业主" min-width="280"><template #default="{row}"><strong>{{row.name}}</strong><small>{{row.code}}</small><small>{{row.owner_unit || '业主待补充'}}</small></template></el-table-column>
   <el-table-column label="区域 / 客户经理" min-width="140"><template #default="{row}"><span>{{row.region || '区域待补充'}}</span><small>{{row.manager || '客户经理待补充'}}</small></template></el-table-column>
   <el-table-column label="阶段 / 赢率" min-width="120"><template #default="{row}"><span>{{row.stage || '—'}}</span><small>{{row.win_rate || '赢率待补充'}}</small></template></el-table-column>
   <el-table-column label="关键时间" min-width="150"><template #default="{row}"><span>招标：{{row.bid_date || '待补充'}}</span><small>签约：{{row.contract_date || '待补充'}}</small></template></el-table-column>
   <el-table-column label="可参与份额" min-width="120" align="right"><template #default="{row}"><strong v-if="row.amount">{{row.amount}} 万元</strong><span v-else>待补充</span></template></el-table-column>
   <el-table-column label="状态 / 作废原因" min-width="150"><template #default="{row}"><el-tag :type="row.cancelled?'info':'success'">{{row.cancelled?'已作废':row.status||'进行中'}}</el-tag><small v-if="row.cancelled">{{row.cancel_reason || '未填写作废原因'}}</small></template></el-table-column>
   <el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click="emit('battle',row.code)">进入作战</el-button><el-button link :disabled="!canEdit" @click="openEdit(row)">编辑</el-button></template></el-table-column>
  </el-table>
  <el-dialog v-model="editing" title="编辑机会点" width="min(760px,94vw)" append-to-body>
   <el-form label-position="top" class="om-editor">
    <el-row :gutter="14"><el-col :span="12"><el-form-item label="机会点编码"><el-input v-model="form.code" disabled/></el-form-item></el-col><el-col :span="12"><el-form-item label="机会点名称 *"><el-input v-model="form.name"/></el-form-item></el-col></el-row>
    <el-form-item label="业主单位 *"><el-input v-model="form.owner_unit" placeholder="需与客户信息中的组织名称一致，便于带入联系人"/></el-form-item>
    <el-row :gutter="14"><el-col :span="8"><el-form-item label="项目归属 / 区域"><el-input v-model="form.region"/></el-form-item></el-col><el-col :span="8"><el-form-item label="机会点阶段"><el-input v-model="form.stage" placeholder="例如：招标"/></el-form-item></el-col><el-col :span="8"><el-form-item label="赢率"><el-input v-model="form.win_rate" placeholder="例如：60%"/></el-form-item></el-col></el-row>
    <el-row :gutter="14"><el-col :span="8"><el-form-item label="客户经理"><el-input v-model="form.manager"/></el-form-item></el-col><el-col :span="8"><el-form-item label="预计招标时间"><el-input v-model="form.bid_date" placeholder="YYYY-MM-DD"/></el-form-item></el-col><el-col :span="8"><el-form-item label="预计签约时间"><el-input v-model="form.contract_date" placeholder="YYYY-MM-DD"/></el-form-item></el-col></el-row>
    <el-row :gutter="14"><el-col :span="12"><el-form-item label="可参与份额（万元）"><el-input-number v-model="form.amount" :min="0" :precision="2" style="width:100%"/></el-form-item></el-col><el-col :span="12"><el-form-item label="业务状态"><el-input v-model="form.status" placeholder="例如：跟进中"/></el-form-item></el-col></el-row>
    <el-form-item><el-checkbox v-model="form.cancelled">该机会点已作废，仅保留用于历史复盘</el-checkbox></el-form-item>
    <el-form-item v-if="form.cancelled" label="作废原因"><el-input v-model="form.cancel_reason" type="textarea" :rows="2"/></el-form-item>
   </el-form>
   <template #footer><el-button @click="editing=false">取消</el-button><el-button type="primary" :disabled="!form.name?.trim() || !form.owner_unit?.trim()" @click="saveEdit">保存修改</el-button></template>
  </el-dialog>
 </section>
</template>
<style scoped>
.opportunity-management{color:#31506d}
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
.om-filters{display:flex;gap:10px;margin-bottom:10px}.om-filters .el-input{max-width:420px}.om-filters .el-select{width:180px}
.om-result-note{margin:0 0 10px;color:#71869a;font-size:12px}.om-result-note b{color:#216bbb;font-weight:600}
.opportunity-management small{display:block;margin-top:5px;color:#8192a4;font-size:12px;line-height:1.45}
.om-editor{padding:0 4px}
@media(max-width:650px){.om-toolbar{align-items:stretch}.om-actions{display:grid;grid-template-columns:1fr 1fr;margin-top:4px;width:100%}.om-actions .el-button{width:100%;margin:0}.om-kpis{grid-template-columns:1fr}.om-filters{display:block}.om-filters .el-input,.om-filters .el-select{width:100%;max-width:none;margin-bottom:8px}.om-editor :deep(.el-col){max-width:100%;flex:0 0 100%}}
</style>
