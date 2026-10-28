<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { TrendCharts, Warning, PieChart } from '@element-plus/icons-vue'
import { crmQualitySettings, type CrmQualitySettings, type CrmUnit, type CrmPerson, type CrmRelation } from '../../../src/services/personalWorkApi'
import { organizationQuality } from './organizationQuality'
import { personalRelationshipQuality } from './personalRelationshipQuality'
import { personalOrganizationQuality } from './personalOrganizationQuality'
import { assessmentOverview } from './assessmentOverview'
import RadarChart from './charts/RadarChart.vue'
import ScoreGauge from './charts/ScoreGauge.vue'
import GradeBar from './charts/GradeBar.vue'
import DimensionBars from './charts/DimensionBars.vue'
import FunnelSteps from './charts/FunnelSteps.vue'

const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[]; relations: CrmRelation[]; canManage: boolean }>()
const emit = defineEmits<{ navigate: [tab: 'archive' | 'relation']; layer: [mode: 'company' | 'personal' | 'personal-organization']; focus: [id: string] }>()
const settings = ref<CrmQualitySettings>(), error = ref(''), region = ref('')
let request = 0
async function load() { const token = ++request; try { const value = await crmQualitySettings(); if (token === request) { settings.value = value; error.value = '' } } catch (e) { if (token === request) { settings.value = undefined; error.value = e instanceof Error ? e.message : '规则加载失败' } } }
onMounted(load); watch(() => props.relations, load)
const rules = computed(() => settings.value?.rules)
const orgs = computed(() => rules.value ? organizationQuality(props.units, props.people, props.relations, Date.now(), rules.value, region.value) : [])
const personal = computed(() => rules.value ? personalRelationshipQuality(props.units, props.people, props.relations, rules.value) : [])
const scopedPersonal = computed(() => region.value ? personal.value.filter(p => p.regions.includes(region.value)) : personal.value)
const personalOrgs = computed(() => rules.value ? personalOrganizationQuality(personal.value, props.units, rules.value, region.value) : [])
const data = computed(() => rules.value ? assessmentOverview(orgs.value, scopedPersonal.value, personalOrgs.value, rules.value) : null)
const regions = computed(() => [...new Set(orgs.value.flatMap(o => o.regions))].filter(r => r && r !== '未分区').sort())

const grade = (s: number | null) => s === null ? '待评估' : rules.value && s >= rules.value.good_threshold ? '暂估较好' : rules.value && s >= rules.value.fair_threshold ? '暂估一般' : '暂估待改善'
const dist = (d: { good: number; fair: number; weak: number; pending: number }) => [
  { label: '较好', value: d.good, tone: 'good' as const }, { label: '一般', value: d.fair, tone: 'fair' as const },
  { label: '待改善', value: d.weak, tone: 'weak' as const }, { label: '待评估', value: d.pending, tone: 'pending' as const },
]
const maxRegionAvg = 100
</script>
<template>
 <section class="ao" aria-label="关系评估总览">
  <div class="ao-head">
   <div><span class="ao-eyebrow">湖南承希科技有限公司 · 关系资产总览</span><h3>三层关系一眼看清：公司覆盖、个人维系、组织渗透</h3><p>汇总「公司与客户」「个人与客户」「个人与客户组织」三层暂估结果，识别薄弱与依赖单点的关系。所有分数均为试行暂估，不作考核结论；项目推进仍在「项目作战地图」。</p></div>
   <div class="ao-head-tools">
    <el-select v-model="region" clearable placeholder="全部经营区域" aria-label="总览经营区域" style="width:160px"><el-option v-for="r in regions" :key="r" :value="r" :label="r"/></el-select>
   </div>
  </div>
  <el-alert v-if="error" type="error" :closable="false" :title="`无法加载统一评估规则：${error}`"><el-button @click="load">重新加载</el-button></el-alert>
  <p v-else-if="!data">正在加载评估数据…</p>
  <template v-if="data && rules">
   <p class="ao-note">规则 v{{ settings?.version }} · 评级线 {{ rules.good_threshold }} / {{ rules.fair_threshold }} 分 · 互动窗口 {{ rules.recent_days }} 天。{{ region ? `当前仅统计 ${region} 客户。` : '当前统计全部区域。' }}缺证据的对象计入「待评估」，不记零分。</p>

   <div class="ao-layers">
    <button class="ao-layer" @click="emit('layer','company')">
     <div class="ao-layer-top"><span><el-icon><PieChart/></el-icon> 公司与客户</span><small>{{ data.company.scored }}/{{ data.company.count }} 家可评</small></div>
     <ScoreGauge :score="data.company.avg" :grade="grade(data.company.avg)" caption="客户组织平均暂估（不含待评估）"/>
     <GradeBar :segments="dist(data.company.distribution)"/>
     <span class="ao-layer-link">查看公司层评估 →</span>
    </button>
    <button class="ao-layer" @click="emit('layer','personal')">
     <div class="ao-layer-top"><span><el-icon><TrendCharts/></el-icon> 个人与客户</span><small>{{ data.personal.scored }}/{{ data.personal.count }} 组可评</small></div>
     <ScoreGauge :score="data.personal.avg" :grade="grade(data.personal.avg)" caption="对接人—联系人平均暂估"/>
     <GradeBar :segments="dist(data.personal.distribution)"/>
     <span class="ao-layer-link">查看个人层评估 →</span>
    </button>
    <button class="ao-layer" @click="emit('layer','personal-organization')">
     <div class="ao-layer-top"><span><el-icon><TrendCharts/></el-icon> 个人与客户组织</span><small>{{ data.personalOrg.count }} 个组合</small></div>
     <ScoreGauge :score="data.personalOrg.avg" :grade="grade(data.personalOrg.avg)" caption="每位对接人对客户组织的渗透暂估"/>
     <div class="ao-layer-note">{{ data.personal.overdue }} 组个人关系维系超期，需优先安排联络。</div>
     <span class="ao-layer-link">查看个人 × 组织 →</span>
    </button>
   </div>

   <div class="ao-grid">
    <div class="ao-card ao-card--radar">
     <h4>公司层五维健康度</h4><p class="ao-card-sub">各维度在客户组织间的平均暂估；虚线为评级参考线 {{ rules.good_threshold }} 分。</p>
     <div class="ao-radar-wrap">
      <RadarChart :axes="data.company.dimensions.map(d => ({ name: d.name, score: d.score, weight: d.weight }))" :reference="rules.good_threshold" :size="248"/>
      <DimensionBars :rows="data.company.dimensions.map(d => ({ name: d.name, weight: d.weight, score: d.score, hint: `${d.count}/${data!.company.count} 家有据可评` }))"/>
     </div>
    </div>
    <div class="ao-card">
     <h4>客户组织覆盖漏斗</h4><p class="ao-card-sub">从范围内组织到关键岗位覆盖达标，逐级观察对接渗透与流失。</p>
     <FunnelSteps :steps="data.penetration"/>
    </div>
   </div>

   <div class="ao-grid">
    <div class="ao-card">
     <div class="ao-card-head"><h4>各区域关系健康</h4><small>按客户登记区域，颜色示意评级</small></div>
     <table class="ao-region"><tbody>
      <tr v-for="r in data.regions" :key="r.name">
       <th>{{ r.name }}</th>
       <td class="ao-region-bar"><span :style="{ width: `${(r.avg ?? 0) / maxRegionAvg * 100}%`, background: r.avg === null ? '#c9d3de' : r.avg >= rules.good_threshold ? '#2f9e6f' : r.avg >= rules.fair_threshold ? '#d99a1c' : '#cf5d5b' }"/></td>
       <td class="ao-region-val">{{ r.avg === null ? '待评估' : `${r.avg} 分` }}</td>
       <td class="ao-region-meta">{{ r.orgs }} 家 · <em v-if="r.risk">{{ r.risk }} 家需关注</em><span v-else>无提示</span></td>
      </tr>
      <tr v-if="!data.regions.length"><td class="ao-empty">暂无区域数据</td></tr>
     </tbody></table>
    </div>
    <div class="ao-card ao-card--fragile">
     <div class="ao-card-head"><h4><el-icon><Warning/></el-icon> 单点依赖 · 需加固</h4><small>关系暂估尚可，却依赖单一对接人或主备待核实</small></div>
     <ul class="ao-list">
      <li v-for="f in data.fragile.slice(0, 6)" :key="f.id">
       <button :title="f.name" @click="emit('focus', f.id)"><b>{{ f.name }}</b><span class="ao-tag ao-tag--warn">{{ f.reason }}</span></button>
       <span class="ao-list-score">{{ f.score }} 分 · {{ f.liaisons }} 人对接</span>
      </li>
      <li v-if="!data.fragile.length" class="ao-empty-li">暂未发现明显单点依赖，仍建议核实关键岗位主备。</li>
     </ul>
    </div>
   </div>

   <div class="ao-card">
    <div class="ao-card-head"><h4>优先关注清单</h4><small>按登记提示数量、评分由弱到强排序，点名进入公司层评分依据</small></div>
    <div class="ao-attention">
     <button v-for="a in data.attention" :key="a.id" class="ao-attn" :title="a.name" @click="emit('focus', a.id)">
      <span class="ao-attn-name"><i class="ao-attn-dot" :data-tone="a.score === null ? 'pending' : a.score >= rules.fair_threshold ? 'fair' : 'weak'"/><b>{{ a.name }}</b></span>
      <small><em :style="{ color: a.score === null ? '#9aa8b8' : a.score >= rules.fair_threshold ? '#c98a2a' : '#cf5d5b' }">{{ a.score === null ? '待评估' : `${a.score} 分` }}</em> · {{ a.reason }}<template v-if="a.risks > 1"> 等 {{ a.risks }} 项</template></small>
     </button>
     <p v-if="!data.attention.length" class="ao-empty">当前范围内暂无需重点关注的组织。</p>
    </div>
    <div class="ao-actions"><el-button type="primary" plain @click="emit('navigate','relation')">前往关系维系</el-button><el-button @click="emit('navigate','archive')">查看客户信息</el-button></div>
   </div>
  </template>
 </section>
</template>
<style scoped>
.ao{padding-bottom:8px}
.ao-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin:6px 0 16px}
.ao-eyebrow{font-size:12px;color:#4775a1;letter-spacing:.5px}
.ao-head h3{margin:10px 0;color:#203b58;font-size:20px}
.ao-head p,.ao-note{color:#728298;font-size:13px;line-height:1.7}
.ao-head-tools{display:flex;gap:8px;flex-shrink:0}
.ao-note{margin:0 0 16px;background:#f6f9fd;border:1px solid #e7edf5;border-radius:8px;padding:10px 12px}
.ao-layers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:16px}
.ao-layer{text-align:left;border:1px solid #e3eaf3;border-radius:14px;background:linear-gradient(150deg,#f5f9ff,#fff);padding:18px 18px 14px;cursor:pointer;display:flex;flex-direction:column;gap:12px;align-items:center;transition:box-shadow .2s,transform .2s,border-color .2s;font:inherit}
.ao-layer:hover{box-shadow:0 10px 26px rgba(37,78,123,.12);transform:translateY(-2px);border-color:#c9daed}
.ao-layer-top{width:100%;display:flex;justify-content:space-between;align-items:center;color:#294f78;font-weight:600;font-size:15px}
.ao-layer-top span{display:inline-flex;align-items:center;gap:6px}.ao-layer-top .el-icon{color:#4775a1}
.ao-layer-top small{color:#8493a5;font-weight:500;font-size:12px}
.ao-layer :deep(.gauge){margin:2px 0}
.ao-layer-note{width:100%;background:#fff8eb;border-radius:8px;padding:8px 10px;color:#8d661e;font-size:12px;line-height:1.6}
.ao-layer-link{width:100%;color:#3f74ab;font-size:12px;font-weight:600}
.ao-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
.ao-card{border:1px solid #e3eaf3;border-radius:14px;background:#fff;padding:18px 20px}
.ao-card h4{margin:0;color:#294f78;font-size:15px;display:inline-flex;align-items:center;gap:6px}
.ao-card h4 .el-icon{color:#c98a2a}
.ao-card-sub{color:#8493a5;font-size:12px;margin:6px 0 14px;line-height:1.6}
.ao-card-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.ao-card-head small{color:#93a1b2;font-size:12px}
.ao-radar-wrap{display:grid;grid-template-columns:260px 1fr;gap:20px;align-items:center}
.ao-region{width:100%;border-collapse:collapse}
.ao-region th{text-align:left;font-weight:600;color:#4d6480;font-size:13px;padding:7px 8px 7px 0;white-space:nowrap;width:64px}
.ao-region td{padding:7px 0}
.ao-region-bar{width:40%}
.ao-region-bar span{display:block;height:9px;border-radius:5px;min-width:3px}
.ao-region-val{width:64px;text-align:right;font-variant-numeric:tabular-nums;color:#294f78;font-size:13px;padding-right:12px!important}
.ao-region-meta{color:#8493a5;font-size:12px;padding-left:12px!important}
.ao-region-meta em{font-style:normal;color:#aa711e}
.ao-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.ao-list li{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;border-top:1px solid #eef2f7}
.ao-list li:first-child{border-top:0}
.ao-list button{background:none;border:0;padding:0;cursor:pointer;font:inherit;display:inline-flex;align-items:center;gap:8px;color:#254e7b;text-align:left;min-width:0;flex:1}
.ao-list button b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.ao-list button:hover b{text-decoration:underline}
.ao-list-score{color:#8493a5;font-size:12px;white-space:nowrap;flex-shrink:0}
.ao-tag{border-radius:5px;padding:2px 7px;font-size:11.5px;font-weight:500;white-space:nowrap;flex-shrink:0}
.ao-tag--warn{background:#fff8eb;color:#8d661e;border:1px solid #f0dfbb}
.ao-empty-li{color:#93a1b2;font-size:12.5px;padding:12px 0}
.ao-attention{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.ao-attn{display:flex;flex-direction:column;gap:5px;align-items:stretch;border:1px solid #e7edf5;border-radius:10px;padding:11px 13px;background:#fafcff;cursor:pointer;font:inherit;text-align:left;transition:border-color .2s,background .2s;min-width:0}
.ao-attn:hover{border-color:#c9daed;background:#f3f8ff}
.ao-attn-name{display:flex;align-items:center;gap:7px;min-width:0}
.ao-attn-name b{color:#294f78;font-size:13px;line-height:1.4;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ao-attn small{color:#8493a5;font-size:12px;line-height:1.5;padding-left:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ao-attn small em{font-style:normal;font-weight:600;font-variant-numeric:tabular-nums}
.ao-attn-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;background:#9aa8b8}
.ao-attn-dot[data-tone=fair]{background:#d99a1c}.ao-attn-dot[data-tone=weak]{background:#cf5d5b}
.ao-actions{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}.ao-actions .el-button{margin:0}
.ao-empty{color:#93a1b2;font-size:12.5px;padding:6px 0}
@media(max-width:900px){.ao-layers{grid-template-columns:1fr}.ao-grid{grid-template-columns:1fr}.ao-radar-wrap{grid-template-columns:1fr;justify-items:center}.ao-head{flex-direction:column}}
</style>
