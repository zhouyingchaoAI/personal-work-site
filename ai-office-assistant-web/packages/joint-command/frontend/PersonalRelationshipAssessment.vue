<script setup lang="ts">
import {computed,ref,onMounted,watch} from 'vue'
import {Search} from '@element-plus/icons-vue'
import {crmQualitySettings,type CrmQualitySettings,type CrmUnit,type CrmPerson,type CrmRelation} from '../../../src/services/personalWorkApi'
import {personalRelationshipQuality,type PersonalRelationshipQuality} from './personalRelationshipQuality'
import PersonFlags from './PersonFlags.vue'
import {personalOrganizationQuality} from './personalOrganizationQuality'
import RadarChart from './charts/RadarChart.vue'
import ScoreGauge from './charts/ScoreGauge.vue'
import GradeBar from './charts/GradeBar.vue'
const props=defineProps<{units:CrmUnit[];people:CrmPerson[];relations:CrmRelation[];canManage:boolean;organizationMode?:boolean}>()
const emit=defineEmits<{navigate:[tab:'archive'|'relation']}>()
const settings=ref<CrmQualitySettings>(),error=ref(''),search=ref(''),member=ref(''),region=ref(''),type=ref(''),state=ref(''),selectedId=ref(''),drawer=ref(false)
let request=0
async function load(){const token=++request;try{const result=await crmQualitySettings();if(token===request){settings.value=result;error.value=''}}catch(e){if(token===request){settings.value=undefined;error.value=e instanceof Error?e.message:'加载失败'}}}
onMounted(load);watch(()=>props.relations,load)
const all=computed(()=>settings.value?personalRelationshipQuality(props.units,props.people,props.relations,settings.value.rules):[])
const members=computed(()=>[...new Map(all.value.map(r=>[r.memberKey,{key:r.memberKey,name:r.member,department:r.department}])).values()])
const regions=computed(()=>[...new Set(all.value.flatMap(r=>r.regions))].sort())
const types=computed(()=>[...new Set([...all.value.map(r=>r.unit?.type),...organizations.value.map(r=>r.unit?.type)].filter((t):t is string=>!!t))].sort())
const filtered=computed(()=>all.value.filter(r=>(!member.value||r.memberKey===member.value)&&(!region.value||r.regions.includes(region.value))&&(!type.value||r.unit?.type===type.value)&&(!state.value||(state.value==='pending'?r.score===null:state.value==='overdue'?r.days!==null&&r.days>r.cadence:r.risks.length>0))&&`${r.member} ${r.person.name} ${r.unit?.company_full_name||''} ${r.unit?.name||''}`.toLowerCase().includes(search.value.trim().toLowerCase())))
const organizations=computed(()=>settings.value?personalOrganizationQuality(all.value,props.units,settings.value.rules,region.value):[])
// Region scopes the source contacts first; text/status filters then select whole regional groups.
const filteredOrganizations=computed(()=>organizations.value.filter(r=>(!member.value||r.memberKey===member.value)&&(!region.value||r.regions.includes(region.value))&&(!type.value||r.unit?.type===type.value)&&(!state.value||(state.value==='pending'?r.assessed<r.contacts.length:state.value==='overdue'?r.overdue>0:r.risks.length>0))&&`${r.member} ${r.name} ${r.contacts.map(c=>c.person.name).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())))
const page=ref(1)
const paged=computed(()=>filtered.value.slice((page.value-1)*20,page.value*20))
const pagedOrganizations=computed(()=>filteredOrganizations.value.slice((page.value-1)*20,page.value*20))
watch(filteredOrganizations,()=>{page.value=1})
watch(filtered,()=>{page.value=1})
const stats=computed(()=>({members:new Set(filtered.value.map(r=>r.memberKey)).size,contacts:new Set(filtered.value.map(r=>r.person.id)).size,overdue:filtered.value.filter(r=>r.days!==null&&r.days>r.cadence).length,pending:filtered.value.filter(r=>r.score===null).length}))
const selected=computed(()=>all.value.find(r=>r.id===selectedId.value))
function inspect(r:PersonalRelationshipQuality){selectedId.value=r.id;drawer.value=true}
function reset(){search.value='';member.value='';region.value='';type.value='';state.value=''}
function navigate(tab:'archive'|'relation'){drawer.value=false;emit('navigate',tab)}
const tone=(r:PersonalRelationshipQuality)=>r.score===null?'pending':r.score>=settings.value!.rules.good_threshold?'good':r.score>=settings.value!.rules.fair_threshold?'fair':'weak'
const distribution=computed(()=>{if(!settings.value)return [];const g=settings.value.rules.good_threshold,f=settings.value.rules.fair_threshold,rows=props.organizationMode?filteredOrganizations.value:filtered.value as {score:number|null}[];return [{label:'较好',value:rows.filter(r=>r.score!==null&&r.score>=g).length,tone:'good' as const},{label:'一般',value:rows.filter(r=>r.score!==null&&r.score>=f&&r.score<g).length,tone:'fair' as const},{label:'待改善',value:rows.filter(r=>r.score!==null&&r.score<f).length,tone:'weak' as const},{label:'待评估',value:rows.filter(r=>r.score===null).length,tone:'pending' as const}]})
const grade=(s:number|null)=>s===null?'待评估':settings.value&&s>=settings.value.rules.good_threshold?'暂估较好':settings.value&&s>=settings.value.rules.fair_threshold?'暂估一般':'暂估待改善'
</script>
<template>
 <section :aria-label="organizationMode?'个人与客户组织评估':'个人与客户评估'" class="personal-assessment">
  <header><div><span class="pa-eyebrow">湖南承希科技有限公司 · {{organizationMode?'个人与客户组织':'个人关系维护'}}</span><h3>{{organizationMode?'一个人对一家客户，覆盖到哪里、关系有多稳':'谁在对接，关系如何，下一步做什么'}}</h3><p>仅汇总当前授权关系，不借用同事的互动记录，不按客户数量给个人排名。</p></div><div v-if="settings" class="pa-config"><span>规则 v{{settings.version}} · 暂估</span><small>规则维护已移至设置</small></div></header>
  <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="load">重新加载规则</el-button></el-alert>
  <p v-else-if="!settings">正在加载评估规则…</p>
  <template v-if="settings">
   <div v-if="organizationMode" class="pa-summary"><div><span>个人 × 客户组织</span><b>{{filteredOrganizations.length}}</b><small>按根组织合并下级</small></div><div><span>对接联系人次</span><b>{{filteredOrganizations.reduce((n,r)=>n+r.contacts.length,0)}}</b><small>同一人对同一联系人去重</small></div><div><span>有维系超期的组合</span><b class="amber">{{filteredOrganizations.filter(r=>r.overdue>0).length}}</b><small>展开定位需维护联系人</small></div><div><span>证据未齐的组合</span><b>{{filteredOrganizations.filter(r=>r.assessed<r.contacts.length).length}}</b><small>至少一位联系人尚待评估</small></div></div>
   <div v-else class="pa-summary"><div><span>当前对接人</span><b>{{stats.members}}</b><small>仅当前授权可见范围</small></div><div><span>客户联系人</span><b>{{stats.contacts}}</b><small>{{filtered.length}} 组个人与客户关系</small></div><div><span>维系超期</span><b class="amber">{{stats.overdue}}</b><small>先核实是否漏记互动</small></div><div><span>待评估关系</span><b>{{stats.pending}}</b><small>证据不足，不记零分</small></div></div>
   <div class="pa-distribution"><span class="pa-distribution-label">{{organizationMode?'组合评级分布':'关系评级分布'}}</span><GradeBar :segments="distribution"/></div>
   <div class="pa-tools" role="group" aria-label="个人评估筛选">
    <el-input v-model="search" :prefix-icon="Search" clearable aria-label="搜索个人关系" placeholder="搜索对接人、客户或组织"/>
    <el-select v-model="member" clearable filterable placeholder="全部我方对接人" aria-label="个人评估对接人"><el-option v-for="m in members" :key="m.key" :value="m.key" :label="m.department?`${m.name} · ${m.department}`:m.name"/></el-select>
    <el-select v-model="region" clearable placeholder="全部经营区域" aria-label="个人评估区域"><el-option v-for="r in regions" :key="r" :value="r" :label="r"/></el-select>
    <el-select v-model="type" clearable placeholder="全部组织类型" aria-label="个人评估组织类型"><el-option v-for="t in types" :key="t" :value="t" :label="t"/></el-select>
    <el-select v-model="state" clearable placeholder="全部评估状态" aria-label="个人评估状态"><el-option label="待评估" value="pending"/><el-option label="维系超期" value="overdue"/><el-option label="需核实 / 改善" value="risk"/></el-select>
    <el-button :disabled="!(search||member||region||type||state)" @click="reset">重置</el-button>
   </div>
   <p class="pa-note">区域按客户单位登记区域筛选，不代表我方人员所属区域。{{region?`当前仅评估${region}客户关系。`:''}}个人模型：关系质量 {{settings.rules.personal_weights[0]}}% · 有效互动 {{settings.rules.personal_weights[1]}}% · 维系及时性 {{settings.rules.personal_weights[2]}}%。公司岗位覆盖和多人备份不纳入个人评分；客户立场取自共享档案，非对个人的认可度。</p>
   <template v-if="organizationMode">
    <p class="pa-note">组织汇总分 = 本人名下已可评联系人的暂估分等权平均；待评估联系人不计零分，同时展示可评人数。该分仅代表已登记关系，不等于整家客户组织的覆盖分；建议岗位只展示覆盖事实，不额外加分。</p>
    <el-table :data="pagedOrganizations" row-key="id" class="pa-org-table" empty-text="暂无匹配的个人与客户组织关系">
     <el-table-column type="expand"><template #default="{row:org}"><div class="pa-org-detail"><h4>{{org.member}} → {{org.name}} · 联系人评分依据</h4><el-table :data="org.contacts"><el-table-column label="客户联系人" prop="person.name" min-width="130"/><el-table-column label="客户部门 / 职务" min-width="170"><template #default="{row}">{{[row.person.department,row.person.title].filter(Boolean).join(' / ')||'待补充'}}</template></el-table-column><el-table-column label="个人关系暂估" width="130"><template #default="{row}">{{row.score===null?'待评估':`${row.score} 分`}}</template></el-table-column><el-table-column label="最近互动" min-width="130" prop="lastTouch"/><el-table-column label="操作" width="120"><template #default="{row}"><el-button link type="primary" @click="inspect(row)">评分与建议</el-button></template></el-table-column></el-table></div></template></el-table-column>
     <el-table-column label="我方对接人" min-width="130"><template #default="{row}"><b>{{row.member}}</b><div class="pa-sub">{{row.department||'部门待补充'}}</div></template></el-table-column>
     <el-table-column label="客户组织" min-width="230"><template #default="{row}"><b>{{row.name}}</b><div class="pa-sub">{{row.unit?.type||'类型待补充'}} · {{row.regions.join('、')}}</div></template></el-table-column>
     <el-table-column label="本人关系汇总" width="140"><template #default="{row}"><span class="pa-score">{{row.score===null?'待评估':`${row.score} 分 · 暂估`}}</span><div class="pa-sub">可评 {{row.assessed}} / {{row.contacts.length}} 人</div></template></el-table-column>
     <el-table-column label="建议岗位覆盖" width="135"><template #default="{row}">{{row.roles.length?`${row.coveredRoles.length} / ${row.roles.length}`:'模板待定'}}<div class="pa-sub">{{row.coveredRoles.join('、')||'尚未登记'}}</div></template></el-table-column>
     <el-table-column label="联系人 / 超期" width="130"><template #default="{row}">{{row.contacts.length}} 人 / {{row.overdue}} 人</template></el-table-column>
     <el-table-column label="最近登记互动" min-width="135"><template #default="{row}">{{row.lastTouch?row.lastTouch.slice(0,10):'暂无记录'}}</template></el-table-column>
     <el-table-column label="证据完整度" width="120"><template #default="{row}">{{row.completeness}}%<div class="pa-sub">联系人证据均值</div></template></el-table-column>
    </el-table>
    <el-pagination v-if="filteredOrganizations.length>20" v-model:current-page="page" :page-size="20" :total="filteredOrganizations.length" layout="prev, pager, next, total" class="crm-pagination"/>
   </template>
   <el-table v-else :data="paged" row-key="id" class="pa-table" empty-text="暂无匹配的个人对接关系，请调整筛选或在关系维系中登记">
    <el-table-column label="我方对接人" min-width="140"><template #default="{row}"><b>{{row.member}}</b><div class="pa-sub">{{row.department||'部门待补充'}}</div></template></el-table-column>
    <el-table-column label="客户联系人 / 组织" min-width="200"><template #default="{row}"><b>{{row.person.name}}</b><div class="pa-sub">{{row.unit?.company_full_name||row.unit?.name||'组织待补充'}}</div></template></el-table-column>
    <el-table-column label="关系暂估" width="125"><template #default="{row}"><span class="pa-score" :data-tone="tone(row)">{{row.score===null?'待评估':`${row.score} 分 · 暂估`}}</span><div class="pa-sub">可评权重 {{row.evidenceWeight}}%</div></template></el-table-column>
    <el-table-column label="客户立场" width="120"><template #default="{row}"><PersonFlags field="support" :support="row.person.support_level"/></template></el-table-column>
    <el-table-column label="最近登记互动" width="135"><template #default="{row}">{{row.lastTouch?row.lastTouch.slice(0,10):'暂无记录'}}<div class="pa-sub">维系周期 {{row.cadence}} 天</div></template></el-table-column>
    <el-table-column label="核实与改善" min-width="190"><template #default="{row}"><span class="pa-risk" v-for="r in row.risks" :key="r">{{r}}</span><span v-if="!row.risks.length">按当前节奏持续维护</span></template></el-table-column>
    <el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" @click="inspect(row)">评分与建议</el-button></template></el-table-column>
   </el-table>
   <el-pagination v-if="!organizationMode&&filtered.length>20" v-model:current-page="page" :page-size="20" :total="filtered.length" layout="prev, pager, next, total" class="crm-pagination"/>
  </template>
  <el-drawer v-model="drawer" :title="selected?`${selected.member} → ${selected.person.name}`:'个人评估'" size="min(780px, 100vw)" class="personal-assessment-drawer" destroy-on-close>
   <template v-if="selected&&settings">
    <el-alert title="个人关系暂估，不是绩效考核结论" type="info" :closable="false" description="只使用这组对接关系的证据；资料缺失、客户整体立场及未录入互动均可能影响结论，请先核实。"/>
    <div class="pa-detail-viz">
     <ScoreGauge :score="selected.score" :grade="grade(selected.score)" :caption="`有据维度权重 ${selected.evidenceWeight}%`"/>
     <RadarChart :axes="selected.dimensions.map(d=>({name:d.name,score:d.score,weight:d.weight}))" :reference="settings.rules.good_threshold" :size="220" accent="#4a86bd"/>
    </div>
    <p class="pa-note">证据完整度 {{selected.completeness}}%：检查重要程度、客户立场、最近互动日期、客户部门/职务、窗口内互动记录五项；不代表资料已核实。</p>
    <p class="pa-note">至少 {{settings.rules.personal_min_dimensions}} 个启用维度有据可评，再按已有权重折算。评级沿用规则 v{{settings.version}}：{{settings.rules.good_threshold}} 分起较好，{{settings.rules.fair_threshold}} 分起一般。</p>
    <article v-for="d in selected.dimensions" :key="d.name" class="pa-dimension"><h4>{{d.name}} <small>权重 {{d.weight}}%</small><strong>{{d.score===null?'待评估':`${d.score} / 100`}}</strong></h4><p>{{d.evidence}}</p><div>下一步：{{d.advice}}</div></article>
    <div class="pa-detail-actions"><el-button type="primary" plain @click="navigate('relation')">查看关系维系</el-button><el-button @click="navigate('archive')">查看客户信息</el-button></div>
    <h4>该对接人的互动证据 · {{selected.actions.length}} 条</h4>
    <el-table :data="selected.actions" max-height="300" empty-text="暂无有效日期的真实互动记录"><el-table-column label="日期" prop="happened_at" min-width="120"/><el-table-column label="类型" prop="type" min-width="100"/><el-table-column label="反馈 / 情报" prop="intel" min-width="200" show-overflow-tooltip/><el-table-column label="有效 / 双向" width="130"><template #default="{row}">{{row.effective?'有效':'未标有效'}} / {{row.bidirectional?'双向':'未标双向'}}</template></el-table-column></el-table>
   </template>
  </el-drawer>
 </section>
</template>
<style scoped>
.pa-org-detail{padding:12px 20px;background:#f7f9fc}.pa-org-detail h4{margin:0 0 12px;color:#294f78}.pa-org-table :deep(th.el-table__cell){background:#f3f6fb;color:#4d6886}.pa-org-table :deep(td.el-table__cell){padding:14px 0}
.personal-assessment header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin:6px 0 20px}.pa-eyebrow{color:#4775a1;font-size:12px}.personal-assessment h3{color:#254e7b;font-size:20px;margin:10px 0}.personal-assessment header p,.pa-note{color:#728298;font-size:13px;line-height:1.7}.pa-config{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:#728298}.pa-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0}.pa-summary>div{padding:18px;border:1px solid #e3eaf3;border-radius:12px;background:linear-gradient(130deg,#f4f8fe,#fff)}.pa-summary span,.pa-summary small{display:block;font-size:12px;color:#728298}.pa-summary b{display:block;font-size:30px;color:#294f78;line-height:1.6}.pa-summary b.amber{color:#aa711e}.pa-tools{display:flex;gap:10px;flex-wrap:wrap;background:#f6f8fb;border:1px solid #e7edf5;padding:12px;border-radius:10px}.pa-tools .el-input{width:280px;max-width:100%}.pa-tools .el-select{width:170px}.pa-tools .el-button{margin:0}.pa-sub{font-size:12px;color:#7c8c9f;margin-top:5px;line-height:1.6}.pa-score{display:inline-block;padding:3px 8px;border-radius:6px;background:#eef2f6;color:#576d83;font-size:12px}.pa-score[data-tone=good]{background:#e7f5ef;color:#267558}.pa-score[data-tone=fair]{background:#fff3db;color:#91620b}.pa-score[data-tone=weak]{background:#fbecec;color:#ae4646}.pa-risk{display:inline-block;background:#fff8eb;color:#8d661e;border:1px solid #f0dfbb;border-radius:5px;margin:2px;padding:2px 6px;font-size:12px}.pa-table :deep(td.el-table__cell){padding:15px 0}.pa-table :deep(th.el-table__cell){background:#f3f6fb;color:#4d6886}.pa-dimension{border:1px solid #e3eaf3;padding:14px;border-radius:10px;margin:12px 0}.pa-dimension h4{color:#294f78;margin:0 0 10px}.pa-dimension small{font-weight:400;color:#728298}.pa-dimension strong{float:right}.pa-dimension p,.pa-dimension div{color:#677c91;font-size:13px;line-height:1.7}.pa-dimension div{background:#f3f7fc;padding:8px;border-radius:6px}.pa-detail-actions{margin:16px 0;display:flex;gap:8px;flex-wrap:wrap}.pa-distribution{display:flex;align-items:center;gap:16px;background:#f6f8fb;border:1px solid #e7edf5;border-radius:10px;padding:12px 16px;margin:14px 0}.pa-distribution-label{font-size:12px;color:#6c7d90;font-weight:600;white-space:nowrap}.pa-distribution :deep(.gradebar){flex:1}.pa-detail-viz{display:flex;align-items:center;gap:24px;flex-wrap:wrap;justify-content:center;margin:16px 0;padding:14px;border:1px solid #eef2f7;border-radius:12px;background:linear-gradient(150deg,#f7fafe,#fff)}@media(max-width:750px){.personal-assessment header{flex-direction:column}.pa-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.pa-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.pa-tools .el-input{grid-column:1/-1;width:100%}.pa-tools .el-select{width:100%;min-width:0}}
</style>
