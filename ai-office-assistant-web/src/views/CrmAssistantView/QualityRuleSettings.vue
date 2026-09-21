<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmSaveQualitySettings, type CrmQualitySettings, type CrmQualityRules } from '../../services/personalWorkApi'
const props=defineProps<{settings:CrmQualitySettings;canManage:boolean}>()
const emit=defineEmits<{saved:[settings:CrmQualitySettings];reload:[]}>()
const open=ref(false),busy=ref(false),draft=ref<CrmQualityRules>(),version=ref(0),error=ref('')
const dimensions=['关键岗位覆盖','关系质量','互动有效性','对接稳定性','我方维护责任']
const supportLabels=['反对','中立','支持','积极支持']
const clone=(rules:CrmQualityRules)=>JSON.parse(JSON.stringify(rules)) as CrmQualityRules
function edit(){draft.value=clone(props.settings.rules);version.value=props.settings.version;error.value='';open.value=true}
const weightTotal=computed(()=>draft.value?.weights.reduce((sum,w)=>sum+(Number.isFinite(w)?w:0),0)||0)
const validation=computed(()=>{
 const d=draft.value;if(!d)return ''
 if(d.weights.some(w=>!Number.isInteger(w)||w<0||w>100)||weightTotal.value!==100)return '五项权重必须为 0–100 的整数，合计 100%；0 表示不参与总分。'
 if(d.personal_weights.some(w=>!Number.isInteger(w)||w<0||w>100)||d.personal_weights.reduce((a,b)=>a+b,0)!==100)return '个人模型三项权重必须为整数且合计 100%。'
 if(d.personal_min_dimensions>d.personal_weights.filter(w=>w>0).length)return '个人最低可评维度不能超过个人已启用维度数。'
 if(d.good_threshold<=d.fair_threshold)return '较好阈值必须大于一般阈值。'
 if(d.min_dimensions>d.weights.filter(w=>w>0).length)return '最低可评维度不能超过已启用维度数。'
 if(supportLabels.some((s,i)=>i>0&&d.support_scores[s]!<d.support_scores[supportLabels[i-1]!]!))return '支持程度分值应从反对到积极支持依次不降低。'
 return ''
})
async function save(){
 if(!draft.value||validation.value||!props.canManage||busy.value)return
 try{await ElMessageBox.confirm('保存后统一影响公司与客户、个人与客户的实时评分；不改写联系人、关系或历史业务记录。是否发布这版规则？','发布评估规则',{type:'warning'})}catch{return}
 busy.value=true;error.value=''
 try{const result=await crmSaveQualitySettings({rules:draft.value,version:version.value});emit('saved',result);open.value=false;ElMessage.success(`评估规则 v${result.version} 已保存并生效`)}catch(e){error.value=e instanceof Error?e.message:'保存失败，请重试'}finally{busy.value=false}
}
</script>
<template>
 <el-button @click="edit">{{canManage?'评估规则设置':'查看评估规则'}}</el-button>
 <el-drawer v-model="open" title="关系评估规则 · 公司与个人" size="min(800px, 100vw)" class="quality-rule-drawer" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close>
  <template v-if="draft">
   <el-alert type="info" :closable="false" title="全局统一口径 · 仅管理员可发布" :description="`当前版本 v${version}；${settings.updated_at ? `${settings.updated_by} 于 ${settings.updated_at} 更新` : '系统默认规则'}。分数仍为暂估，规则配置不等于业务证据已核实。`"/>
   <el-form label-position="top" :disabled="!canManage||busy" class="rule-form">
    <h4>公司与客户 · 五维权重 <span>合计 {{weightTotal}}% · 0 表示不参与总分</span></h4>
    <div class="rule-grid"><el-form-item v-for="(name,i) in dimensions" :key="name" :label="name"><el-input-number v-model="draft.weights[i]" :min="0" :max="100" :precision="0" :aria-label="`${name}权重`"/></el-form-item></div>
    <h4>个人与客户 · 独立模型</h4>
    <p>不使用公司岗位覆盖或主备协同给个人打分。关系质量、互动窗口及评级阈值采用下方共享口径；个人权重和最低证据门槛独立配置。</p>
    <div class="rule-grid"><el-form-item v-for="(name,i) in ['关系质量','互动有效性','维系及时性']" :key="name" :label="`个人 · ${name}`"><el-input-number v-model="draft.personal_weights[i]" :min="0" :max="100" :precision="0" :aria-label="`个人${name}权重`"/></el-form-item><el-form-item label="个人最低可评维度数"><el-input-number v-model="draft.personal_min_dimensions" :min="1" :max="3" :precision="0" aria-label="个人最低可评维度数"/></el-form-item><el-form-item label="个人默认维系周期（天）"><el-input-number v-model="draft.personal_maintenance_days" :min="1" :max="365" :precision="0" aria-label="个人默认维系周期"/></el-form-item></div>
    <p>个人维系周期优先采用客户档案设置，未填时采用默认周期；周期内 100 分，之后线性下降，达到两倍周期为 0 分。无互动日期不计分。</p>
    <h4>评级与证据门槛</h4>
    <div class="rule-grid">
     <el-form-item label="较好起评分"><el-input-number v-model="draft.good_threshold" :min="1" :max="100" :precision="0" aria-label="较好起评分"/></el-form-item>
     <el-form-item label="一般起评分"><el-input-number v-model="draft.fair_threshold" :min="0" :max="99" :precision="0" aria-label="一般起评分"/></el-form-item>
     <el-form-item label="最低可评维度数"><el-input-number v-model="draft.min_dimensions" :min="1" :max="5" :precision="0" aria-label="最低可评维度数"/></el-form-item>
     <el-form-item label="互动统计窗口（天）"><el-input-number v-model="draft.recent_days" :min="1" :max="365" :precision="0" aria-label="互动统计窗口"/></el-form-item>
     <el-form-item label="主备覆盖最低人数"><el-input-number v-model="draft.backup_count" :min="2" :max="10" :precision="0" aria-label="主备覆盖最低人数"/></el-form-item>
     <el-form-item label="资料完整度提示线（%）"><el-input-number v-model="draft.completeness_threshold" :min="0" :max="100" :precision="0" aria-label="资料完整度提示线"/></el-form-item>
    </div>
    <h4>关系质量分值</h4>
    <p>关系质量 = 强度标准分 × 强度占比 + 支持分 × 剩余占比；两项证据都具备才计分。</p>
    <div class="rule-grid"><el-form-item label="关系强度占比（%）"><el-input-number v-model="draft.strength_weight" :min="0" :max="100" :precision="0" aria-label="关系强度占比"/></el-form-item><el-form-item v-for="s in supportLabels" :key="s" :label="`${s}分值`"><el-input-number v-model="draft.support_scores[s]" :min="0" :max="100" :precision="0" :aria-label="`${s}分值`"/></el-form-item></div>
    <h4>各类组织关键岗位模板</h4><p>仅匹配联系人已登记的决策角色。清空某类模板表示该类岗位覆盖暂不计分，不代表覆盖已达标。</p>
    <el-form-item v-for="(_,type) in draft.templates" :key="type" :label="String(type)"><el-select v-model="draft.templates[type]" multiple clearable :aria-label="`${type}岗位模板`" placeholder="暂不评估岗位覆盖"><el-option v-for="role in settings.roles" :key="role" :label="role" :value="role"/></el-select></el-form-item>
   </el-form>
   <el-alert v-if="validation||error" :title="validation||error" type="error" :closable="false"/>
   <p class="rule-bottom-note">不可配置的底线：缺失证据不记零分；不计未来互动或计划事项；按已知维度权重折算；不扩大数据权限。主责确认、按时闭环仍需独立业务证据。</p>
  </template>
  <template #footer><div class="rule-footer"><el-button v-if="canManage" :disabled="busy" @click="draft=clone(settings.defaults);error=''">恢复默认到草稿</el-button><el-button :disabled="busy" @click="open=false;emit('reload')">关闭并刷新</el-button><el-button v-if="canManage" type="primary" :loading="busy" :disabled="!!validation" @click="save">保存并生效</el-button></div></template>
 </el-drawer>
</template>
<style scoped>
.rule-form{margin-top:20px}.rule-form h4{margin:20px 0 14px;color:#294f78}.rule-form h4 span{font-size:12px;font-weight:400;color:#728298;margin-left:10px}.rule-form p,.rule-bottom-note{font-size:13px;color:#728298;line-height:1.7}.rule-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 16px}.rule-grid .el-input-number{width:100%}.rule-footer{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px}.rule-footer .el-button{margin:0}@media(max-width:600px){.rule-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
