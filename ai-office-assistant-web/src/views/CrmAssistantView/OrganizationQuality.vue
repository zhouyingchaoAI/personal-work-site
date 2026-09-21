<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { CrmUnit, CrmPerson, CrmRelation } from '../../services/personalWorkApi'
import { crmQualitySettings, type CrmQualitySettings } from '../../services/personalWorkApi'
import QualityRuleSettings from './QualityRuleSettings.vue'
import { organizationQuality, type OrganizationQuality } from './organizationQuality'
import PersonFlags from './PersonFlags.vue'
import RadarChart from './charts/RadarChart.vue'
import ScoreGauge from './charts/ScoreGauge.vue'
import GradeBar from './charts/GradeBar.vue'
const props=defineProps<{units:CrmUnit[];people:CrmPerson[];relations:CrmRelation[];canManage:boolean;focusId?:string}>()
const emit=defineEmits<{navigate:[tab:'archive'|'relation']}>()
const search=ref(''),region=ref(''),type=ref(''),status=ref(''),risk=ref(''),selectedId=ref(''),drawer=ref(false)
const settings=ref<CrmQualitySettings>(),settingsError=ref(''),loadingRules=ref(false)
let requestId=0
async function loadRules(){const id=++requestId;loadingRules.value=true;try{const value=await crmQualitySettings();if(id===requestId){settings.value=value;settingsError.value=''}}catch(e){if(id===requestId){settingsError.value=e instanceof Error?e.message:'规则加载失败';settings.value=undefined}}finally{if(id===requestId)loadingRules.value=false}}
function savedRules(value:CrmQualitySettings){requestId++;settings.value=value;settingsError.value='';loadingRules.value=false}
onMounted(loadRules)
watch(()=>props.relations,loadRules)
const rules=computed(()=>settings.value?.rules)
const all=computed(()=>rules.value?organizationQuality(props.units,props.people,props.relations,Date.now(),rules.value):[])
const regional=computed(()=>region.value&&rules.value?organizationQuality(props.units,props.people,props.relations,Date.now(),rules.value,region.value):all.value)
const regions=computed(()=>[...new Set(all.value.flatMap(o=>o.regions))].sort())
const types=computed(()=>[...new Set(all.value.map(o=>o.type).filter(Boolean))].sort())
const risks=computed(()=>[...new Set(all.value.flatMap(o=>o.risks))])
const grade=(o:OrganizationQuality)=>o.score===null?'待评估':o.score>=rules.value!.good_threshold?'暂估较好':o.score>=rules.value!.fair_threshold?'暂估一般':'暂估待改善'
const color=(o:OrganizationQuality)=>o.score===null?'info':o.score>=rules.value!.good_threshold?'success':o.score>=rules.value!.fair_threshold?'warning':'danger'
const filtered=computed(()=>regional.value.filter(o=>(!type.value||o.type===type.value)&&(!status.value||grade(o)===status.value)&&(!risk.value||o.risks.includes(risk.value))&&`${o.name} ${o.members.join(' ')} ${o.people.map(p=>p.name).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())))
const selected=computed(()=>regional.value.find(o=>o.id===selectedId.value))
const page=ref(1)
const paged=computed(()=>filtered.value.slice((page.value-1)*20,page.value*20))
watch(filtered,()=>{page.value=1})
const hasFilters=computed(()=>!!(search.value||region.value||type.value||status.value||risk.value))
function reset(){search.value='';region.value='';type.value='';status.value='';risk.value=''}
function inspect(o:OrganizationQuality){selectedId.value=o.id;drawer.value=true}
function navigate(tab:'archive'|'relation'){drawer.value=false;emit('navigate',tab)}
const selectedActions=computed(()=>[...new Map((selected.value?.relations||[]).flatMap(r=>r.actions||[]).filter(a=>(a as typeof a & {record_kind?:string}).record_kind!=='plan').map(a=>[a.id,a])).values()].sort((a,b)=>b.happened_at.localeCompare(a.happened_at)))
const stats=computed(()=>({total:filtered.value.length,waiting:filtered.value.filter(o=>o.score===null).length,risk:filtered.value.filter(o=>o.risks.length).length,complete:filtered.value.length?Math.round(filtered.value.reduce((n,o)=>n+o.completeness,0)/filtered.value.length):null}))
const distribution=computed(()=>rules.value?[{label:'较好',value:filtered.value.filter(o=>o.score!==null&&o.score>=rules.value!.good_threshold).length,tone:'good' as const},{label:'一般',value:filtered.value.filter(o=>o.score!==null&&o.score>=rules.value!.fair_threshold&&o.score<rules.value!.good_threshold).length,tone:'fair' as const},{label:'待改善',value:filtered.value.filter(o=>o.score!==null&&o.score<rules.value!.fair_threshold).length,tone:'weak' as const},{label:'待评估',value:filtered.value.filter(o=>o.score===null).length,tone:'pending' as const}]:[])
const focusHandled=ref('')
watch([()=>props.focusId,regional],([id])=>{if(!id||id===focusHandled.value)return;const hit=regional.value.find(o=>o.id===id);if(hit){selectedId.value=id;drawer.value=true;focusHandled.value=id}},{immediate:true})
</script>
<template>
 <section class="quality" aria-label="组织对接质量评估">
  <div class="quality-heading"><div><span class="quality-eyebrow">湖南承希科技有限公司 · 公司与客户</span><h3>关键岗位是否覆盖，整体关系是否稳固</h3><p>按客户根组织汇总下级部门、全部可见对接人与互动证据；评估公司整体关系资产，不是个人得分的简单平均。项目关联与推进仍在「项目作战地图」。</p></div><div v-if="settings" class="quality-rule-tools"><el-tag effect="plain" type="info">规则 v{{settings.version}} · 全部为暂估</el-tag><QualityRuleSettings :settings="settings" :can-manage="canManage" @saved="savedRules" @reload="loadRules"/></div></div>
  <el-alert v-if="settingsError" type="error" :closable="false" :title="`无法加载统一评估规则：${settingsError}`"><el-button @click="loadRules">重新加载规则</el-button></el-alert>
  <p v-if="loadingRules">正在加载统一评估规则…</p>
  <template v-if="rules">
  <div class="quality-summary">
   <div><span>当前范围组织</span><b>{{stats.total}}</b><small>包含尚未登记对接的组织</small></div>
   <div><span>需核实 / 改善</span><b class="amber">{{stats.risk}}</b><small>资料提示不等同于关系风险</small></div>
   <div><span>待评估组织</span><b>{{stats.waiting}}</b><small>不足 {{rules.min_dimensions}} 个启用维度有据可评</small></div>
   <div><span>平均资料完整度</span><b>{{stats.complete===null?'—':`${stats.complete}%`}}</b><small>与关系质量分开衡量</small></div>
  </div>
  <div class="quality-distribution"><span class="quality-distribution-label">评级分布</span><GradeBar :segments="distribution"/></div>
  <div class="quality-tools" role="group" aria-label="组织质量筛选">
   <el-input v-model="search" clearable :prefix-icon="Search" placeholder="搜索组织、双方联系人" aria-label="搜索组织质量"/>
   <el-select v-model="region" clearable placeholder="全部经营区域" aria-label="质量经营区域"><el-option v-for="r in regions" :key="r" :value="r" :label="r"/></el-select>
   <el-select v-model="type" clearable placeholder="全部组织类型" aria-label="质量组织类型"><el-option v-for="t in types" :key="t" :value="t" :label="t"/></el-select>
   <el-select v-model="status" clearable placeholder="全部评估状态" aria-label="质量评估状态"><el-option v-for="s in ['待评估','暂估较好','暂估一般','暂估待改善']" :key="s" :value="s" :label="s"/></el-select>
   <el-select v-model="risk" clearable placeholder="全部改善提示" aria-label="质量改善提示"><el-option v-for="r in risks" :key="r" :value="r" :label="r"/></el-select>
   <el-button :disabled="!hasFilters" @click="reset">重置</el-button>
  </div>
  <div class="quality-note">区域按客户单位登记的经营区域筛选，与我方人员所属区域无关。{{region ? `当前仅汇总${region}客户的联系人、关系和互动。` : '当前汇总全部客户区域。'}}评分不按联系人数量累加，缺失维度不记零分，不用于组织排名或人员考核。</div>
  <el-table :data="paged" row-key="id" class="quality-table" empty-text="没有匹配的组织，请调整筛选条件">
   <el-table-column label="对接组织" min-width="240"><template #default="{row}"><button class="quality-org" @click="inspect(row)">{{row.name}}</button><div class="quality-meta">{{row.type||'类型待补充'}} · {{row.people.length}} 位联系人 · {{row.childCount}} 个下级组织</div></template></el-table-column>
   <el-table-column label="质量暂估" width="140"><template #default="{row}"><span class="quality-grade" :data-tone="color(row)">{{row.score===null?'待评估':`${row.score} 分 · 暂估`}}</span><div class="quality-meta">{{row.score===null?'证据不足':grade(row)}} · 权重 {{row.evidenceWeight}}%</div></template></el-table-column>
   <el-table-column label="关键岗位" width="110"><template #default="{row}"><b>{{row.roles.length?`${row.coveredRoles.length} / ${row.roles.length}`:'待定模板'}}</b><div class="quality-meta">已登记 / 建议</div></template></el-table-column>
   <el-table-column label="资料完整度" width="125"><template #default="{row}"><el-progress :percentage="row.completeness" :stroke-width="5" color="#527dab"/></template></el-table-column>
   <el-table-column label="最近登记互动" width="140"><template #default="{row}">{{row.lastTouch?row.lastTouch.slice(0,10):'暂无记录'}}</template></el-table-column>
   <el-table-column label="核实与改善提示" min-width="210"><template #default="{row}"><div class="quality-risks"><span v-for="r in row.risks.slice(0,2)" :key="r" class="quality-risk">{{r}}</span><span v-if="row.risks.length>2">另 {{row.risks.length-2}} 项</span><span v-if="!row.risks.length">需确认岗位模板与主备职责</span></div></template></el-table-column>
   <el-table-column label="我方对接人" min-width="140" show-overflow-tooltip><template #default="{row}">{{row.members.join('、')||'待登记'}}</template></el-table-column>
   <el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" @click="inspect(row)">评分与建议</el-button></template></el-table-column>
  </el-table>
  <el-pagination v-if="filtered.length>20" v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next, total" class="crm-pagination"/>
  <el-drawer v-model="drawer" :title="selected?.name||'评分依据'" size="min(860px, 100vw)" class="quality-drawer" destroy-on-close>
   <template v-if="selected">
    <el-alert type="info" :closable="false" title="试行评分，不是最终业务结论" description="岗位模板尚待业务确认；主责、主备和闭环质量尚无完整证据。各维度展示实际登记依据，不将未填写等同于关系差。"/>
    <div class="quality-detail-viz">
     <ScoreGauge :score="selected.score" :grade="grade(selected)" :caption="`有据维度权重 ${selected.evidenceWeight}%`"/>
     <RadarChart :axes="selected.dimensions.map(d=>({name:d.name,score:d.score,weight:d.weight}))" :reference="rules.good_threshold" :size="230"/>
    </div>
    <div class="quality-detail-summary"><span>资料完整度 {{selected.completeness}}% · 关键岗位 {{selected.roles.length?`${selected.coveredRoles.length}/${selected.roles.length}`:'模板待定'}} · {{selected.people.length}} 位联系人</span></div>
    <p class="quality-note">当前规则 v{{settings?.version}}：覆盖 {{rules.weights[0]}}% / 关系 {{rules.weights[1]}}% / 互动 {{rules.weights[2]}}% / 稳定 {{rules.weights[3]}}% / 责任 {{rules.weights[4]}}%。至少 {{rules.min_dimensions}} 个启用维度可评才折算总分；{{rules.good_threshold}} 分起暂估较好，{{rules.fair_threshold}}–{{rules.good_threshold-1}} 分暂估一般，其余暂估待改善。零权重维度不计入总分。</p>
    <div class="quality-detail-actions"><el-button type="primary" plain @click="navigate('relation')">查看关系维系</el-button><el-button @click="navigate('archive')">查看客户档案</el-button></div>
    <div class="quality-dimensions"><article v-for="d in selected.dimensions" :key="d.name"><div class="quality-dimension-title"><h4>{{d.name}} <small>权重 {{d.weight}}%</small></h4><strong>{{d.score===null?'待评估':`${d.score} / 100`}}</strong></div><el-progress v-if="d.score!==null" :percentage="d.score" :show-text="false" :stroke-width="6" color="#477aab"/><p>{{d.evidence}}</p><div class="quality-advice">下一步：{{d.advice}}</div></article></div>
    <h4>资料完整度口径</h4><p class="quality-note">每位联系人检查决策角色、重要程度、支持程度、部门或职务、我方对接人五项，按已填比例计算；不等同于资料已经核实。</p>
    <h4>双方对接记录 · {{selected.relations.length}} 条</h4>
    <el-table :data="selected.relations" empty-text="尚未登记对接关系，请在关系维系中补充">
     <el-table-column label="我方对接人" min-width="120"><template #default="{row}">{{row.our_staff?.name||row.our_member_label||row.our_member||'待补充'}}</template></el-table-column>
     <el-table-column label="客户联系人" min-width="120"><template #default="{row}">{{selected.people.find(p=>p.id===row.person_id)?.name||'待补充'}}</template></el-table-column>
     <el-table-column label="关键角色" min-width="100"><template #default="{row}">{{selected.people.find(p=>p.id===row.person_id)?.decision_role||'待补充'}}</template></el-table-column>
     <el-table-column label="支持程度" width="110"><template #default="{row}"><PersonFlags field="support" :support="selected.people.find(p=>p.id===row.person_id)?.support_level"/></template></el-table-column>
     <el-table-column label="强度" width="70"><template #default="{row}">L{{row.strength}}</template></el-table-column>
     <el-table-column label="最近登记互动" min-width="120"><template #default="{row}">{{row.last_touch||'暂无记录'}}</template></el-table-column>
    </el-table>
    <h4>互动证据 · {{selectedActions.length}} 条</h4>
    <el-table :data="selectedActions" max-height="300" empty-text="暂无互动记录，互动有效性暂不计分">
     <el-table-column label="登记日期" prop="happened_at" min-width="110"/>
     <el-table-column label="互动类型" prop="type" min-width="100"/>
     <el-table-column label="反馈 / 情报" prop="intel" min-width="200" show-overflow-tooltip/>
     <el-table-column label="有效 / 双向" min-width="110"><template #default="{row}">{{row.effective?'有效':'未标有效'}} / {{row.bidirectional?'双向':'未标双向'}}</template></el-table-column>
    </el-table>
   </template>
  </el-drawer>
  </template>
 </section>
</template>
<style scoped>
.quality-rule-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.quality-grade{display:inline-block;border-radius:6px;padding:3px 8px;background:#eef2f6;color:#576d83;font-size:12px;font-weight:600}.quality-grade[data-tone=success]{background:#e7f5ef;color:#267558}.quality-grade[data-tone=warning]{background:#fff3db;color:#91620b}.quality-grade[data-tone=danger]{background:#fbecec;color:#ae4646}.quality-risk{display:inline-block;background:#fff8eb;color:#8d661e;border:1px solid #f0dfbb;border-radius:5px;padding:2px 6px;font-size:12px;line-height:1.5}
.quality-detail-actions{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.quality-detail-actions .el-button{margin:0}
.quality-distribution{display:flex;align-items:center;gap:16px;background:#f6f8fb;border:1px solid #e7edf5;border-radius:10px;padding:12px 16px;margin-bottom:16px}.quality-distribution-label{font-size:12px;color:#6c7d90;font-weight:600;white-space:nowrap}.quality-distribution :deep(.gradebar){flex:1}
.quality-detail-viz{display:flex;align-items:center;gap:24px;flex-wrap:wrap;justify-content:center;margin:18px 0 8px;padding:14px;border:1px solid #eef2f7;border-radius:12px;background:linear-gradient(150deg,#f7fafe,#fff)}
.quality-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin:6px 0 20px}.quality-eyebrow{font-size:12px;color:#4775a1;letter-spacing:.5px}.quality-heading h3{margin:10px 0;color:#203b58;font-size:20px}.quality-heading p,.quality-note{color:#728298;font-size:13px;line-height:1.7}.quality-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:18px}.quality-summary>div{padding:18px 20px;border:1px solid #e3eaf3;border-radius:12px;background:linear-gradient(130deg,#f4f8fe,#fff)}.quality-summary span,.quality-summary small{display:block;color:#728298;font-size:12px}.quality-summary b{display:block;font-size:30px;line-height:1.6;color:#294f78;font-variant-numeric:tabular-nums}.quality-summary b.amber{color:#aa711e}.quality-tools{display:flex;gap:10px;flex-wrap:wrap;background:#f6f8fb;border:1px solid #e7edf5;padding:12px;border-radius:10px}.quality-tools .el-input{width:280px;max-width:100%}.quality-tools .el-select{width:150px}.quality-tools .el-button{margin:0}.quality-note{margin:12px 0}.quality-org{background:none;border:0;padding:0;color:#254e7b;font:inherit;font-weight:600;text-align:left;cursor:pointer;line-height:1.6}.quality-org:hover{text-decoration:underline}.quality-meta{color:#7c8c9f;font-size:12px;margin-top:5px;line-height:1.6}.quality-risks{display:flex;flex-wrap:wrap;gap:5px;font-size:12px;color:#7c8c9f}.quality-table :deep(td.el-table__cell){padding:15px 0}.quality-table :deep(th.el-table__cell){background:#f3f6fb;color:#4d6886}.quality-detail-summary{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:20px 0;color:#6c8097;font-size:13px}.quality-detail-summary strong{font-size:24px;color:#254e7b}.quality-dimensions{display:grid;gap:12px}.quality-dimensions article{border:1px solid #e3eaf3;padding:14px 16px;border-radius:10px}.quality-dimension-title{display:flex;justify-content:space-between;align-items:center;gap:12px}.quality-dimension-title h4{margin:0 0 12px;color:#294f78}.quality-dimension-title small{font-weight:400;color:#7c8c9f;margin-left:8px}.quality-dimension-title strong{color:#4775a1;white-space:nowrap}.quality-dimensions p,.quality-advice{font-size:13px;line-height:1.7;color:#677c91}.quality-advice{background:#f3f7fc;border-radius:6px;padding:8px 10px;color:#395d83}@media(max-width:750px){.quality-heading{flex-direction:column}.quality-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.quality-summary>div{padding:12px}.quality-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.quality-tools .el-input{grid-column:1/-1;width:100%}.quality-tools .el-select{width:100%;min-width:0}}
</style>
