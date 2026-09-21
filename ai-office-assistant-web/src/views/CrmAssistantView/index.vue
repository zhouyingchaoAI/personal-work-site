<script setup lang="ts">
import LiaisonDirectory from './RelationshipAssessment.vue'
import ScopeFilters from './ScopeFilters.vue'
import PersonFlags from './PersonFlags.vue'
import { managerReviewOptions } from './managerReview'
import { computed, defineAsyncComponent, onActivated, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
// 仅在对应页签/弹窗首次打开时才加载的重组件，按需切分独立 chunk，缩小首屏主包解析耗时。
const RelationshipWorkbench = defineAsyncComponent(() => import('./RelationshipWorkbench.vue'))
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Warning, Connection, Aim, Refresh, QuestionFilled, Upload, DataBoard, Search, Postcard, Odometer, Share, FolderAdd, ChatDotRound, Tickets, User, Key, DocumentChecked } from '@element-plus/icons-vue'
import {
  crmStaff, type CrmStaff, crmOverview, crmUnits, crmPeople, crmRelations, crmSaveUnit, crmDeleteUnit, crmSavePerson, crmDepartmentNode,
  crmSecurityMe, crmSaveRelation, crmAddAction, crmSaveLink, crmBattleMap, crmGraphPath, crmPlaybook, crmCompleteFollowup, crmProjectMap, crmImportOpportunities, crmSaveOpportunity, crmExportOpportunities, crmOpportunities,
  type CrmPlaybook, type CrmCoverage, crmManagerDirectory, type CrmManagerView, crmExportRelationships, crmExportCustomerOrganization,
  type CrmOverview, type CrmUnit, type CrmPerson, type CrmRelation, type CrmAction, type CrmBattleMap, type CrmCapabilities, type CrmOpportunity,
} from '../../services/personalWorkApi'
const RelationGraph = defineAsyncComponent(() => import('./RelationGraph.vue'))
import { organizationGraph } from './organizationGraph'
const ExcelImport = defineAsyncComponent(() => import('./ExcelImport.vue'))
const OpportunityManagement = defineAsyncComponent(() => import('./OpportunityManagement.vue'))
const ImportCompletionTasks = defineAsyncComponent(() => import('./ImportCompletionTasks.vue'))
import QuickCapture from './QuickCapture.vue'
import OrganizationTree from './OrganizationTree.vue'
import { organizationRoot, assignmentKey, departmentOptions as buildDepartmentOptions } from './personOrganization'
import { filterOrganizationByRegion } from './organizationRegionFilter'
const OrganizationCanvas = defineAsyncComponent(() => import('./OrganizationEditor.vue'))
import RelationshipLinks from './RelationshipLinks.vue'
const OwnOrganization = defineAsyncComponent(() => import('./OwnOrganization.vue'))
import StaffPicker from './StaffPicker.vue'
import { authState } from '../../services/authSession'
const organizationCanvasOpen = ref(false)
const organizationCanvasRoot = ref('')
const organizationCanvasSelected = ref('')
function openOrganizationCanvas(unit?: CrmUnit) {
  organizationCanvasSelected.value = ''
  organizationCanvasRoot.value = unit?.id || ''
  organizationCanvasOpen.value = true
}
const SecurityPanel = defineAsyncComponent(() => import('./SecurityPanel.vue'))
import RegionSettings from './RegionSettings.vue'
import { crmRegionSettings } from '../../services/personalWorkApi'
import { REGION_PROVINCES, REGION_CITIES } from './dashboard/chinaMapData'
const AuditTrail = defineAsyncComponent(() => import('./AuditTrail.vue'))
import Cockpit from './Cockpit.vue'
const HolographicBoard = defineAsyncComponent(() => import('./HolographicBoard.vue'))
const holographicOpen = ref(false)
const cockpitFullscreen = ref(false)
import UsageGuide from './UsageGuide.vue'
const usageGuideOpen = ref(false)
const canManage = computed(() => capabilities.value.manage || capabilities.value.appoint)
const capabilities = ref<CrmCapabilities>({ manage:false, appoint:false, read:false, write:false, register_action:false, import:false, expires_on:'', expired:false, role:'disabled', data_scope:'self', regions:[] })
function permitWrite() { if (capabilities.value.write) return true; ElMessage.warning('当前为只读权限，请联系客户经营管理员授权编辑'); return false }
function permitAction() { if (capabilities.value.register_action) return true; ElMessage.warning('当前没有登记动作权限，请联系客户经营管理员授权'); return false }
function openQuick() { if (permitWrite()) quickCapture.value?.open() }
const quickCapture = ref<InstanceType<typeof QuickCapture> | null>(null)
import './index.scss'

type CrmTab = 'cockpit' | 'security' | 'customers' | 'relation' | 'opportunities' | 'battle'
const activeTab = ref<CrmTab>('cockpit')
const customerView = ref<'contacts' | 'organization' | 'own'>('contacts')
const customerRelationSection = ref<'archive' | 'assessment' | 'coordination' | 'completion'>('archive')
const customerRelationTabs = [
  { value: 'archive', label: '客户档案', desc: '维护客户组织、部门与联系人资料', icon: Postcard },
  { value: 'assessment', label: '关系评估', desc: '诊断三层关系强弱与单点风险', icon: Odometer },
  { value: 'coordination', label: '责任统筹', desc: '指派负责人、转移关系并交接计划', icon: Share },
  { value: 'completion', label: '资料补充', desc: '补齐缺项资料，通过后并入客户库', icon: FolderAdd },
] as const
const loading = ref(false)
const lastLoadAt = ref(0)
const importDialog = ref(false)
const archivePage = ref(1)
const relationPage = ref(1)
const relationTaskPage = ref(1)
const warningPage = ref(1)
const relationView = ref<'relations' | 'tasks'>('relations')
const relationshipOverviewMode = ref('workbench')
const securityView = ref<'permissions' | 'audit'>('permissions')
const battleSection = ref('map')
const relationQuery = ref('')
const relationState = ref('')
const relationRegion = ref('')
const relationAttention = ref(false)
function resetRelationFilters() { relationRegion.value = ''; relationQuery.value = ''; relationState.value = ''; relationAttention.value = false }
const pageGuide = computed(() => ({
 liaisons:['关系评估','先看总览掌握三层关系全貌与薄弱点，再进入公司与客户、个人与客户、个人与客户组织逐层查看评分、证据和改善建议。'],
 customers:['客户关系','统一维护客户资料、评估关系质量、统筹负责人并补齐资料。'],
 relation:['关系维系','日常维系主阵地：盯住维系状态、登记真实互动、安排下一步跟进；历史互动与未来计划分开记录。'],
 opportunities:['机会点管理','机会点定义要打的仗和业主单位；从这里进入作战地图，系统会带入对应客户组织与关系资产。'],
 battle:['项目作战地图','不用研究关系图：按下面 3 步选好机会点、要联系的人和阶段，系统就会给出“谁去联系、通过谁、这次做什么”。'],
 security:['安全权限', capabilities.value.appoint ? '指定客户经营管理员，由其负责日常授权与审计。' : '管理客户经营访问权限、有效期及操作审计。'],
 cockpit:['经营驾驶舱','']
})[activeTab.value])
function navigateUsageGuide(tab: 'cockpit' | 'organization' | 'archive' | 'relation' | 'battle') {
  usageGuideOpen.value = false
  if (tab === 'archive' || tab === 'organization') {
    customerRelationSection.value = 'archive'
    customerView.value = tab === 'organization' ? 'organization' : 'contacts'
    activeTab.value = 'customers'
    return
  }
  activeTab.value = tab
}
const mobileTabOptions = computed<{ value: CrmTab; label: string }[]>(() => {
  const options: { value: CrmTab; label: string }[] = [
    { value: 'cockpit', label: '经营驾驶舱' },
    { value: 'customers', label: '客户关系' },
    { value: 'relation', label: '关系维系' },
    { value: 'opportunities', label: '机会点管理' },
    { value: 'battle', label: '项目作战地图' },
  ]
  if (canManage.value) options.push({ value: 'security', label: '安全权限' })
  return options
})
const roleLabel = computed(() => capabilities.value.appoint ? '超级管理员' : capabilities.value.manage ? '客户经营管理员' : capabilities.value.import ? '编辑与导入' : capabilities.value.write ? '可编辑' : '只读')
const saving = ref(false)
const playbook = shallowRef<CrmPlaybook | null>(null)
const archiveQuery = ref('')
const archiveType = ref('')
const archiveImportance = ref(''), archiveSupport = ref('')
const matchesContactLevel = (value: string | undefined, filter: string) => !filter || (filter === '__empty__' ? !value?.trim() : value === filter)
const businessRegion = ref('')
const businessRegions = ['东区','西区','中区','广东区']
const customerUnits = (items: CrmUnit[]) => items.filter(unit => !unit.organization_level || unit.organization_level === 'unit')
const unitRegions = (unit: CrmUnit) => {
  const regions = Array.isArray(unit.business_regions) ? unit.business_regions.filter(Boolean) : []
  if (regions.length) return [...new Set(regions)]
  return unit.business_region ? [unit.business_region] : ['未分区']
}
const unitRegionLabel = (unit: CrmUnit) => unitRegions(unit).join('、')
const matchesRegion = (u: CrmUnit) => !businessRegion.value || unitRegions(u).includes(businessRegion.value)
const filteredPeople = computed(() => people.value.filter(p => matchesContactLevel(p.importance, archiveImportance.value) && matchesContactLevel(p.support_level, archiveSupport.value) && (!businessRegion.value || units.value.some(u => u.id === p.unit_id && matchesRegion(u))) && (!archiveType.value || units.value.find(u => u.id === p.unit_id)?.type === archiveType.value) && `${p.name} ${p.organization_path || ''} ${p.company_full_name || ''} ${p.subsidiary_full_name || ''} ${p.organization_unit_name || ''} ${p.department || ''} ${p.title} ${p.support_level || ''} ${(p.career_track || []).join(' ')}`.toLowerCase().includes(archiveQuery.value.trim().toLowerCase())))
function searchCockpit(query: string) {
  const keyword = query.trim()
  if (!keyword) return
  const normalized = keyword.toLowerCase()
  const matchesArchive = [...units.value, ...people.value].some(item => JSON.stringify(item).toLowerCase().includes(normalized))
  if (matchesArchive) {
    customerRelationSection.value = 'archive'; customerView.value = 'contacts'; archiveQuery.value = keyword; archivePage.value = 1; activeTab.value = 'customers'
    return
  }
  projectId.value = keyword; activeTab.value = 'battle'
  ElMessage.info('未匹配客户或联系人，已将关键词带入项目作战地图。')
}
async function safely(task: () => Promise<unknown>) {
  if (saving.value) return
  saving.value = true
  try { await task() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '操作失败，请重试') } finally { saving.value = false }
}
async function closeFollowup(id: string) {
  if (playbook.value?.followups.find(a => a.id === id)?.can_complete === false) return ElMessage.warning('当前没有完成该事项的权限，请联系跟进负责人')
  const result = await crmCompleteFollowup(id)
  if (!result.ok) return ElMessage.error(result.error || '操作失败')
  await loadAll()
}
function actOnWarning(id: string) { const relation = relations.value.find(r => r.id === id); if (relation) openAction(relation) }

// Server snapshots are replaced on refresh; editors use separate form objects.
// Avoid deeply proxying thousands of read-only records on every map calculation.
const overview = shallowRef<CrmOverview | null>(null)
const units = shallowRef<CrmUnit[]>([])
const people = shallowRef<CrmPerson[]>([])
const relations = shallowRef<CrmRelation[]>([])
const opportunities = shallowRef<CrmOpportunity[]>([])
const staff = shallowRef<CrmStaff[]>([])
const ourDepartment = ref('')
const ourPerson = ref('')
type CockpitMode = 'manager' | 'regional' | 'joint'
const cockpitMode = ref<CockpitMode>('manager')
const cockpitRegion = ref('')
const cockpitModeInitialized = ref(false)
const managerDirectory = ref<CrmManagerView[]>([])
const reviewingManager = ref('')
const canReviewManagers = computed(() => capabilities.value.read && capabilities.value.data_scope === 'all' &&
  (canManage.value || authState.user?.role === 'admin'))
const relationScopeLabel = computed(() => canReviewManagers.value ? '管理员 · 全部客户关系维系' : capabilities.value.data_scope === 'regions' ? `区域负责人 · ${(capabilities.value.regions || []).join('、')}，以及本人跨区对接关系` : '个人账号 · 仅本人对接的客户关系维系（按账号 / 工号 / 唯一姓名匹配）')
const canEditRelation = (relation: CrmRelation) => capabilities.value.write && (!relation._owner || relation._owner === authState.user?.username || relation.our_staff?.username === authState.user?.username)
const managerSelectionRegion = ref('')
const allManagerOptions = computed(() => canReviewManagers.value ? managerReviewOptions(managerDirectory.value,staff.value,relations.value,people.value,units.value) : [])
const managerSelectionRegions = computed(() => [...new Set([...businessRegions,...allManagerOptions.value.flatMap(m=>m.regions)])])
const managerOptions = computed(() => allManagerOptions.value.filter(m=>!managerSelectionRegion.value || (managerSelectionRegion.value==='__unassigned__' ? !m.regions.length : m.regions.includes(managerSelectionRegion.value))))
const reviewedManager = computed(() => allManagerOptions.value.find(m => m.username === reviewingManager.value))
const managerLabel = computed(() => reviewedManager.value ? `${reviewedManager.value.name}（${reviewedManager.value.member_keys[0]}）` : managerSelectionRegion.value ? '该区域暂无对接人员' : '本人')
function setManagerSelectionRegion(region:string) {
  managerSelectionRegion.value=region
  setReviewingManager(managerOptions.value[0]?.username || '')
}
function setReviewingManager(username: string) {
  if (username && !managerOptions.value.some(m => m.username === username)) return
  reviewingManager.value = username
  cockpitRegion.value = ''; businessRegion.value = ''
}
const cockpitModes = computed(() => {
  const options: { value: CockpitMode; label: string; description: string }[] = [{ value: 'manager', label: '客户经理形态', description: '仅看本人负责的客户与行动' }]
  if (capabilities.value.data_scope === 'regions' || capabilities.value.data_scope === 'all') options.push({ value: 'regional', label: '区域指挥形态', description: '查看指定经营区域全量信息' })
  if (capabilities.value.data_scope === 'all') options.push({ value: 'joint', label: '联合指挥形态', description: '查看全部已授权经营信息' })
  return options
})
type ExportLevel = 'all' | 'region' | 'manager'
const exportDialog = ref(false)
const exportLevel = ref<ExportLevel>('all')
const exportRegion = ref('')
const exportManager = ref('')
const exporting = ref(false)
const organizationExporting = ref(false)
const exportManagerOptions = computed(() => allManagerOptions.value.filter(manager => manager.count > 0 &&
  (!exportRegion.value || manager.regions.includes(exportRegion.value))))
watch(exportRegion, () => {
  if (exportLevel.value === 'manager' && !exportManagerOptions.value.some(manager => manager.username === exportManager.value)) {
    exportManager.value = exportManagerOptions.value[0]?.username || ''
  }
})
const exportLevels: { value: ExportLevel; label: string; hint: string }[] = [
  { value: 'all', label: '联合指挥 · 全部', hint: '导出全部已授权客户关系' },
  { value: 'region', label: '区域指挥 · 区域', hint: '按经营区域导出该区域客户关系' },
  { value: 'manager', label: '客户经理 · 个人', hint: '先按经营区域查找客户对接人，再导出其在该区域的客户关系' },
]
function openExportDialog() {
  if (!canReviewManagers.value) { ElMessage.warning('只有客户经营管理员可导出客户关系表'); return }
  exportLevel.value = cockpitMode.value === 'regional' ? 'region' : cockpitMode.value === 'manager' ? 'manager' : 'all'
  exportRegion.value = cockpitRegion.value || businessRegions[0]
  exportManager.value = exportManagerOptions.value.some(manager => manager.username === reviewingManager.value)
    ? reviewingManager.value : exportManagerOptions.value[0]?.username || ''
  exportDialog.value = true
}
async function runExport() {
  if (exportLevel.value === 'region' && !exportRegion.value) { ElMessage.warning('请选择要导出的经营区域'); return }
  if (exportLevel.value === 'manager' && !exportRegion.value) { ElMessage.warning('请选择经营区域，以查找客户对接人'); return }
  if (exportLevel.value === 'manager' && !exportManager.value) { ElMessage.warning('请选择要导出的客户经理'); return }
  const target = exportLevel.value === 'region' ? exportRegion.value : exportLevel.value === 'manager' ? exportManager.value : ''
  exporting.value = true
  try {
    const { blob, name } = await crmExportRelationships(exportLevel.value, target, exportLevel.value === 'manager' ? exportRegion.value : '')
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = name; document.body.appendChild(link); link.click()
    link.remove(); URL.revokeObjectURL(url)
    ElMessage.success('客户关系表已导出')
    exportDialog.value = false
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}
async function runOrganizationExport() {
  if (!canReviewManagers.value) { ElMessage.warning('只有客户经营管理员可导出客户组织架构'); return }
  organizationExporting.value = true
  try {
    const { blob, name } = await crmExportCustomerOrganization()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = name; document.body.appendChild(link); link.click()
    link.remove(); URL.revokeObjectURL(url)
    ElMessage.success('客户组织架构已导出')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    organizationExporting.value = false
  }
}
const currentMemberKeys = computed(() => {
  if (reviewedManager.value) return new Set(reviewedManager.value.member_keys)
  if (canReviewManagers.value && managerSelectionRegion.value) return new Set<string>()
  const username = authState.user?.username || ''
  const resolvedLegacyKeys = relations.value
    .filter(r => r.our_staff?.username === username)
    .map(r => r.our_member)
  return new Set([username, authState.user?.employee_id || '', ...staff.value.filter(p => p.username === username).map(p => p.member_key), ...resolvedLegacyKeys].filter(Boolean))
})
const cockpitRegionOptions = computed(() => {
  // The command deck is an authorization view, not a data-derived filter. Keep
  // a permitted region visible even before its first customer record exists.
  const configuredRegions = capabilities.value.data_scope === 'regions'
    ? (capabilities.value.regions || [])
    : businessRegions
  const populatedRegions = units.value.flatMap(unitRegions)
  return [...new Set([...configuredRegions, ...populatedRegions])].filter(name =>
    cockpitMode.value === 'manager' || capabilities.value.data_scope !== 'regions' || configuredRegions.includes(name)
  )
})
function setCockpitMode(mode: CockpitMode) {
  if (!cockpitModes.value.some(option => option.value === mode)) return
  cockpitMode.value = mode
  if (mode === 'manager') { cockpitRegion.value = ''; businessRegion.value = '' }
  if (mode === 'regional' && !cockpitRegion.value) cockpitRegion.value = cockpitRegionOptions.value[0] || ''
}
function selectDefaultCockpitMode() {
  // A refresh must not discard a user's explicit switch, unless that form is no
  // longer authorized.  The initial form always follows the highest authority.
  if (cockpitModeInitialized.value && cockpitModes.value.some(option => option.value === cockpitMode.value)) return
  const data_scope = capabilities.value.data_scope
  if (data_scope === 'all') setCockpitMode('joint')
  else if (data_scope === 'regions') setCockpitMode('regional')
  else setCockpitMode('manager')
  cockpitModeInitialized.value = true
}
function setCockpitRegion(region: string) {
  cockpitRegion.value = region
  businessRegion.value = region
}
const departmentOptions = computed(() => [...new Set(staff.value.map(p => p.department).filter(Boolean))])
const scopedStaff = computed(() => staff.value.filter(p => !ourDepartment.value || p.department === ourDepartment.value))
const scopedKeys = computed(() => ourPerson.value ? [ourPerson.value] : ourDepartment.value ? scopedStaff.value.map(p => p.member_key) : null)
const memberLabel = (key?: string) => { const p = staff.value.find(p => p.member_key === key); return p ? [p.name,p.department,p.title].filter(Boolean).join(' · ') : key || '—' }
watch(ourDepartment, () => { ourPerson.value = '' })
watch([ourDepartment, ourPerson], () => { archivePage.value = 1; relationPage.value = 1; warningPage.value = 1; battle.value = null; highlightPath.value = []; targetPerson.value = '' })
const unitTypes = ['主管单位', '业主单位', '总包单位', '设计单位', '厂商']
const decisionNodes = ['立项', '设计', '招标', '定标', '履约', '联调试运行', '验收', '初期运营', '付款']
const roles = ['定标', '定技术', '签验收', '批付款', '影响者', '需求提出', '采购经办', '运营接管', '安全评估协调']
const typeColor: Record<string, string> = { 主管单位: '#7c6bff', 业主单位: '#f5c242', 总包单位: '#23e0d0', 设计单位: '#1e6bff', 厂商: '#f97316', 我方: '#f5c242' }

const regionalSummary = computed(() => cockpitRegionOptions.value.map(name => {
  const us = units.value.filter(u => unitRegions(u).includes(name))
  const ids = new Set(us.map(u => u.id))
  const ps = people.value.filter(p => ids.has(p.unit_id))
  const personIds = new Set(ps.map(p => p.id))
  const rs = relations.value.filter(r => personIds.has(r.person_id))
  const relationIds = new Set(rs.map(r => r.id))
  return { name, units: customerUnits(us).length, people: ps.length, warnings: rs.filter(r => r.decay_state !== 'normal').length,
    followups: playbook.value?.followups.filter(a => relationIds.has(a.relation_id)).length || 0 }
}))

const cockpitData = computed(() => {
  let visibleUnits = units.value
  // Keep authorized map data complete; the cockpit scopes detail panels to the selected region.
  let visibleRelations = relations.value
  if (cockpitMode.value === 'manager') visibleRelations = visibleRelations.filter(r => currentMemberKeys.value.has(r.our_member))
  let unitIds = new Set(visibleUnits.map(u => u.id))
  let visiblePeople = people.value.filter(p => unitIds.has(p.unit_id))
  if (cockpitMode.value === 'manager') {
    visiblePeople = visiblePeople.filter(p => visibleRelations.some(r => r.person_id === p.id))
    unitIds = new Set(visiblePeople.map(p => p.unit_id))
    visibleUnits = visibleUnits.filter(u => unitIds.has(u.id))
  }
  const personIds = new Set(visiblePeople.map(p => p.id))
  visibleRelations = visibleRelations.filter(r => personIds.has(r.person_id))
  const relationIds = new Set(visibleRelations.map(r => r.id))
  const nodeIds = new Set(['self', ...unitIds, ...personIds])
  const source = overview.value
  return {
    units: visibleUnits, people: visiblePeople, relations: visibleRelations,
    playbook: playbook.value ? { ...playbook.value, followups: playbook.value.followups.filter(a => relationIds.has(a.relation_id)) } : null,
    overview: source ? { ...source,
      stats: { units: customerUnits(visibleUnits).length, people: visiblePeople.length, relations: visibleRelations.length, trusted: visibleRelations.filter(r => r.strength >= 3).length, warnings: visibleRelations.filter(r => r.decay_state !== 'normal').length, single_point: visibleRelations.filter(r => r.single_point_risk).length },
      warnings: source.warnings.filter(w => relationIds.has(w.relation_id)),
      graph: { nodes: source.graph.nodes.filter(n => nodeIds.has(n.id)), edges: source.graph.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target)) },
    } : null,
  }
})

const regionData = computed(() => {
  const memberKeys = scopedKeys.value
  const allowedRelations = relations.value.filter(r => !memberKeys || memberKeys.includes(r.our_member))
  const allowedTasks = (playbook.value?.followups || []).filter(a => !memberKeys || memberKeys.includes(a.owner || ''))
  const taskRelationIds = new Set(allowedTasks.map(a => a.relation_id))
  const allowedPeople = new Set([...allowedRelations, ...relations.value.filter(r => taskRelationIds.has(r.id))].map(r => r.person_id))
  const us = units.value.filter(u => matchesRegion(u) && (!memberKeys || people.value.some(p => p.unit_id === u.id && allowedPeople.has(p.id))))
  const unitIds = new Set(us.map(u => u.id))
  const ps = people.value.filter(p => (!businessRegion.value || unitIds.has(p.unit_id)) && (!memberKeys || allowedPeople.has(p.id)))
  const personIds = new Set(ps.map(p => p.id))
  const rs = allowedRelations.filter(r => personIds.has(r.person_id))
  const relationIds = new Set(rs.map(r => r.id))
  const nodeIds = new Set(['self', ...unitIds, ...personIds])
  const ov = overview.value
  return { units: us, people: ps, relations: rs,
    playbook: playbook.value ? {...playbook.value, followups: allowedTasks.filter(a => relations.value.some(r => r.id === a.relation_id && personIds.has(r.person_id)))} : null,
    overview: ov ? {...ov, stats: {units: customerUnits(us).length, people: ps.length, relations: rs.length, trusted: rs.filter(r => r.strength >= 3).length, warnings: rs.filter(r => r.decay_state !== 'normal').length, single_point: rs.filter(r => r.single_point_risk).length},
      warnings: ov.warnings.filter(w => relationIds.has(w.relation_id)), graph: {nodes: ov.graph.nodes.filter(n => nodeIds.has(n.id)), edges: ov.graph.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target) && (!memberKeys || memberKeys.includes(e.our_member || '')))}} : null }
})

// The organization view needs the ancestors too: a matching regional unit
// without its company would render as an unrelated root in both the tree and
// the mind-map canvas.
const organizationRegionUnits = computed(() => filterOrganizationByRegion(units.value, businessRegion.value))
const organizationRegionUnitIds = computed(() => new Set(organizationRegionUnits.value.map(unit => unit.id)))
const organizationRegionPeople = computed(() => people.value.filter(person => organizationRegionUnitIds.value.has(person.unit_id)))

const visibleRelations = computed(() => {
  const unitIds = new Set(units.value.filter(u => !relationRegion.value || unitRegions(u).includes(relationRegion.value)).map(u => u.id))
  const personIds = new Set(people.value.filter(p => unitIds.has(p.unit_id)).map(p => p.id))
  return relations.value.filter(r => (!relationRegion.value || personIds.has(r.person_id)) && (!relationState.value || r.decay_state === relationState.value) && (!relationAttention.value || r.decay_state !== 'normal') && `${r.person_name} ${memberLabel(r.our_member)} ${r.source}`.toLowerCase().includes(relationQuery.value.trim().toLowerCase()))
})
const listPageSize = 10
const pagedRelations = computed(() => visibleRelations.value.slice((relationPage.value - 1) * listPageSize, relationPage.value * listPageSize))
const relationFollowups = computed(() => {
  const relationIds = new Set(visibleRelations.value.map(relation => relation.id))
  return [...(playbook.value?.followups || [])]
    .filter(item => relationIds.has(item.relation_id))
    .sort((a, b) => Number(b.overdue) - Number(a.overdue) || (a.due_date || '9999-12-31').localeCompare(b.due_date || '9999-12-31'))
})
const pagedRelationFollowups = computed(() => relationFollowups.value.slice((relationTaskPage.value - 1) * listPageSize, relationTaskPage.value * listPageSize))
function showMyTasks() { resetRelationFilters(); relationView.value = 'tasks'; relationTaskPage.value = 1 }
function showRelationForTask(relationId: string) {
  const relation = relations.value.find(item => item.id === relationId)
  relationView.value = 'relations'
  relationQuery.value = relation?.person_name || ''
  relationPage.value = 1
}
function navigateCockpit(tab: 'archive' | 'overview' | 'workflow' | 'battle' | 'relation' | 'cockpit' | 'customers' | 'opportunities' | 'security') {
  if (tab === 'workflow') { showMyTasks(); activeTab.value = 'relation'; return }
  if (tab === 'archive') { customerRelationSection.value = 'archive'; activeTab.value = 'customers'; return }
  if (tab === 'overview') { customerRelationSection.value = 'coordination'; activeTab.value = 'customers'; return }
  activeTab.value = tab
}
function navigateCustomerRelation(tab: 'archive' | 'relation' | 'battle') {
  if (tab === 'archive') { customerRelationSection.value = 'archive'; customerView.value = 'contacts'; activeTab.value = 'customers'; return }
  activeTab.value = tab
}
const relationSummary = computed(() => {
  const month = new Date().toISOString().slice(0, 7)
  const rels = visibleRelations.value
  let monthActions = 0, followups = 0
  for (const r of rels) for (const a of (r.actions || []) as (CrmAction & { record_kind?: string })[]) {
    if (a.record_kind === 'plan') { if (!a.completed_at) followups++ }
    else if ((a.happened_at || '').startsWith(month)) monthActions++
  }
  return { total: rels.length, maintain: rels.filter(r => r.decay_state !== 'normal').length, alarm: rels.filter(r => r.decay_state === 'alarm').length, singlePoint: rels.filter(r => r.single_point_risk).length, monthActions, followups }
})
watch([relationQuery, relationState, relationRegion, relationAttention, businessRegion, relations], () => { relationPage.value = 1; relationTaskPage.value = 1; warningPage.value = 1 })
const pagedPeople = computed(() => filteredPeople.value.slice((archivePage.value - 1) * listPageSize, archivePage.value * listPageSize))
watch([archiveQuery,archiveType,archiveImportance,archiveSupport,businessRegion], () => { archivePage.value = 1 })
watch(() => visibleRelations.value.length, count => { relationPage.value = Math.min(relationPage.value, Math.max(1, Math.ceil(count / listPageSize))) })
watch(() => filteredPeople.value.length, count => { archivePage.value = Math.min(archivePage.value, Math.max(1, Math.ceil(count / listPageSize))) })
watch(businessRegion, () => { clearPath(); targetPerson.value = ''; battle.value = null })

async function loadAll() {
  battle.value = null
  coverage.value = null
  loading.value = true
  try {
    const [ov, u, p, guide, security, team, regionSettings, r, importedOpportunities] = await Promise.all([crmOverview(), crmUnits(), crmPeople(), crmPlaybook(), crmSecurityMe(), crmStaff(), crmRegionSettings(), crmRelations(), crmOpportunities()])
    Object.assign(REGION_PROVINCES, regionSettings.regions)
    Object.assign(REGION_CITIES, regionSettings.cities)
    staff.value = team.staff
    capabilities.value = security.capabilities
    if (canReviewManagers.value) {
      try { managerDirectory.value = (await crmManagerDirectory()).managers }
      catch { managerDirectory.value = []; ElMessage.warning('客户经理名单加载失败，请刷新重试') }
    } else managerDirectory.value = []
    if (!managerOptions.value.some(m => m.username === reviewingManager.value)) reviewingManager.value = managerSelectionRegion.value ? managerOptions.value[0]?.username || '' : ''
    playbook.value = guide
    overview.value = ov; units.value = u.units; people.value = p.people; relations.value = r.relations; opportunities.value = importedOpportunities.opportunities
    selectDefaultCockpitMode()
    lastLoadAt.value = Date.now()
    if (projectId.value.trim()) await loadCoverage()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '客户经营数据加载失败') } finally { loading.value = false }
}
onMounted(loadAll)
// 切到「客户对接人」时，仅在数据陈旧（>30s）时才整表刷新，避免每次切页都重发 8 个接口造成卡顿；后台定时器负责持续保鲜。
watch(activeTab, tab => { if (tab === 'customers' && Date.now() - lastLoadAt.value > 30000) void loadAll() })
const liaisonRefreshTimer = window.setInterval(() => { if (activeTab.value === 'customers' && !loading.value && !document.hidden) void loadAll() }, 60000)
onUnmounted(() => window.clearInterval(liaisonRefreshTimer))
onActivated(() => { activeTab.value = 'cockpit' })

const unitName = (id: string) => units.value.find((u) => u.id === id)?.name || ''
// 虚拟化下拉的选项数组：联系人可达上千，用 el-select-v2 + 预算标签，避免每次挂载渲染上千个 DOM 选项。
const personOption = (p: CrmPerson) => ({ value: p.id, label: `${p.name}（${p.unit_name || unitName(p.unit_id)}）` })
const allPeopleOptions = computed(() => people.value.map(personOption))
const regionPeopleOptions = computed(() => regionData.value.people.map(personOption))
const organizationUnitPath = (unit?: CrmUnit) => {
  const path: string[] = []; let cursor = unit; const seen = new Set<string>()
  while (cursor && !seen.has(cursor.id)) { seen.add(cursor.id); path.unshift(cursor.name); cursor = units.value.find(item => item.id === cursor?.parent_unit_id) }
  return path.join(' / ')
}
const decayText: Record<string, string> = { normal: '正常', warning: '待维系', alarm: '告警' }
const decayType: Record<string, string> = { normal: 'success', warning: 'warning', alarm: 'danger' }

// ---- 交互式网络图谱状态 ----
const organizationNetwork = computed(() => {
 const selected = scopedKeys.value ? staff.value.filter(p => scopedKeys.value!.includes(p.member_key)) : staff.value
 const included = new Map(selected.map(p => [p.id,p]))
 for (const p of selected) { let id=p.manager_id;const seen=new Set<string>();while(id&&!seen.has(id)){seen.add(id);const parent=staff.value.find(p=>p.id===id);if(!parent)break;included.set(id,parent);id=parent.manager_id} }
 return organizationGraph(regionData.value.units,regionData.value.people,[...included.values()],regionData.value.relations)
})
// 关系统筹为自成一体的独立视图：不受全局区域/责任人筛选影响，始终基于全部授权数据，
// 由面板内的区域 / 单位类型 / 引荐路径等控件统一筛选，避免与全局筛选条重复。
const overviewNetwork = computed(() => organizationGraph(units.value, people.value, staff.value, relations.value))
const graphNodes = computed(() => overview.value?.graph.nodes || [])
const graphEdges = computed(() => overview.value?.graph.edges || [])
const overviewWarnings = computed(() => overview.value?.warnings || [])
const hiddenTypes = ref<string[]>([])
const onlyGaps = ref(false)
const highlightPath = ref<string[]>([])
const pathTarget = ref('')
const pathHint = ref('')
function toggleType(t: string) {
  hiddenTypes.value = hiddenTypes.value.includes(t) ? hiddenTypes.value.filter((x) => x !== t) : [...hiddenTypes.value, t]
}
async function highlightIntroPath() {
  if (!pathTarget.value) { highlightPath.value = []; pathHint.value = ''; return }
  try {
    const target = pathTarget.value
    const res = await crmGraphPath(target)
    if (target !== pathTarget.value) return
    if (!res.ok || !res.ids.length) { highlightPath.value = []; pathHint.value = '暂无可达路径，建议先建立一条关系'; return }
    highlightPath.value = res.ids
    pathHint.value = `${res.names.join(' → ')}（${res.hops} 跳 · ${res.hops > 1 ? '同单位线索，需核实引荐意愿' : '已登记直接关系'}）`
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '路径查询失败') }
}
function clearPath() { highlightPath.value = []; pathTarget.value = ''; pathHint.value = '' }

// ---- 节点详情抽屉 ----
const detailOpen = ref(false)
const detailNode = ref<{ id: string; kind: string } | null>(null)
const detailStaff = computed(() => detailNode.value?.kind === 'staff' ? staff.value.find(p => p.id === detailNode.value?.id) : null)
const detailUnit = computed(() => detailNode.value?.kind === 'unit' ? units.value.find((u) => u.id === detailNode.value!.id) : null)
const detailPerson = computed(() => detailNode.value?.kind === 'person' ? people.value.find((p) => p.id === detailNode.value!.id) : null)
const detailRelation = computed(() => detailPerson.value ? relations.value.find((r) => r.person_id === detailPerson.value!.id) : null)
function onGraphSelect(id: string, kind: string) {
  if (kind === 'self' || kind === 'group') return
  detailNode.value = { id, kind }; detailOpen.value = true
}

// ---- 建档对话框 ----
const unitDialog = ref(false)
const unitForm = reactive<Partial<CrmUnit>>({})
function openUnit(u?: CrmUnit) { if (!permitWrite()) return;  for (const key of Object.keys(unitForm)) delete unitForm[key as keyof typeof unitForm]; Object.assign(unitForm, u ? { ...u, business_regions: unitRegions(u).filter(region => region !== '未分区') } : { id: '', parent_unit_id: '', organization_level: 'company', name: '', type: '业主单位', region: '', business_region: '', business_regions: [], line_scale: '', bid_preference: '', history: '', win_rate: '', version: 0 }); unitDialog.value = true }
function openCanvasUnit(level: 'company' | 'subsidiary' | 'unit', parentId = '') {
  if (!permitWrite()) return
  openUnit()
  unitForm.organization_level = level
  unitForm.parent_unit_id = parentId
  const parent = units.value.find(u => u.id === parentId)
  if (parent) { unitForm.type = parent.type; unitForm.business_regions = [...unitRegions(parent)].filter(r => r !== '未分区'); unitForm.region = parent.region }
}
async function quickAddCanvasUnit(_level: 'company' | 'subsidiary' | 'unit', parentId = '') {
  if (!permitWrite()) return
  const parent = units.value.find(u => u.id === parentId)
  try {
    const { value } = await ElMessageBox.prompt(parent ? `上级组织：${parent.name}` : '创建一个新的组织架构', parent ? '新增下级节点' : '新增根节点', {
      inputPlaceholder: '输入组织或部门名称', confirmButtonText: '创建节点', cancelButtonText: '取消',
      inputValidator: (value: string) => !!value?.trim() || '请输入节点名称', closeOnClickModal: false,
    })
    const response = await crmSaveUnit({ name: value.trim(), parent_unit_id: parentId,
      organization_level: parent ? 'unit' : 'company', type: parent?.type || '业主单位',
      business_regions: parent ? unitRegions(parent).filter(r => r !== '未分区') : businessRegion.value && businessRegion.value !== '未分区' ? [businessRegion.value] : [],
      region: parent?.region || '', version: 0,
    })
    if (!response.ok || !response.unit) return ElMessage.error(response.error || '创建失败')
    await loadAll()
    organizationCanvasSelected.value = response.unit.id
    ElMessage.success('节点已创建，可继续添加下级')
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error instanceof Error ? error.message : '创建失败') }
}
// 组织树节点上的「新增」：下级组织自动继承上级层级/类型/区域；联系人预置所属单位。
function addChildUnit(parent: CrmUnit) { openCanvasUnit(parent.organization_level === 'company' ? 'subsidiary' : 'unit', parent.id) }
function openPersonForUnit(unit: CrmUnit) { openPerson(); personForm.unit_id = unit.id }
async function editCanvasDepartment(unitId: string, department: string, action: 'add' | 'delete') {
  if (!permitWrite()) return
  try {
    let name = ''
    if(action === 'add') {
      const answer = await ElMessageBox.prompt(
        `在“${department || '未分部门'}”下面新建节点。该部门将登记为组织节点，现有联系人保留并归入该部门。`,
        '新增下级节点', { inputPlaceholder:'输入下级节点名称', confirmButtonText:'创建节点', cancelButtonText:'取消', inputValidator:(v:string)=>!!v?.trim() || '请输入节点名称', closeOnClickModal:false })
      name=answer.value.trim()
    } else {
      if(!department)return ElMessage.info('未分部门是人员归属提示，请先将联系人移入具体组织或部门')
      await ElMessageBox.confirm(`删除“${department}”部门节点？联系人将保留在上级组织，部门归属清空；关系与行动记录保留。`, '删除部门节点', {confirmButtonText:'删除节点并保留联系人',cancelButtonText:'取消',type:'warning'})
    }
    const result=await crmDepartmentNode({unit_id:unitId,department,action,name})
    if(!result.ok)return ElMessage.error(result.error || '操作失败')
    await loadAll()
    organizationCanvasSelected.value=result.unit?.id || unitId
    ElMessage.success(action === 'add' ? '已新增下级节点' : '部门节点已删除，联系人已保留')
  } catch(error) {if(error !== 'cancel' && error !== 'close')ElMessage.error(error instanceof Error ? error.message : '操作失败')}
}
async function moveCanvasUnit(unit: CrmUnit, parentId: string) {
  if (!permitWrite()) return
  const response = await crmSaveUnit({ ...unit, parent_unit_id: parentId })
  if (!response.ok) return ElMessage.error(response.error || '组织归属调整失败')
  ElMessage.success(`已调整“${unit.name}”的组织归属`)
  await loadAll()
}
const movingCanvasPeople = new Set<string>()
async function moveCanvasPerson(person: CrmPerson, unitId: string, department: string) {
  if (!permitWrite()) return
  if (movingCanvasPeople.has(person.id)) return
  movingCanvasPeople.add(person.id)
  try {
    let response = await crmSavePerson({ ...person, unit_id: unitId, department })
    if (!response.ok && response.error === '人物已被更新，请刷新后重试') {
      const latest = (await crmPeople()).people.find(item => item.id === person.id)
      if (!latest) return ElMessage.error('该人员已不在当前可见范围，请刷新画布')
      response = await crmSavePerson({ ...latest, unit_id: unitId, department })
    }
    if (!response.ok) return ElMessage.error(response.error || '人员匹配失败')
    const index = people.value.findIndex(item => item.id === person.id)
    if (index >= 0) people.value[index] = { ...people.value[index], ...response.person }
    ElMessage.success(department ? `已匹配“${person.name}”，原有关系和行动记录保留` : `已将“${person.name}”移至未分部门，原有关系和行动记录保留`)
    await loadAll()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '人员匹配失败，请刷新后重试') }
  finally { movingCanvasPeople.delete(person.id) }
}
async function deleteCanvasUnit(unit: CrmUnit) {
  if (!permitWrite()) return
  try {
    await ElMessageBox.confirm(`确定删除“${unit.name}”吗？仅无下级组织且没有联系人的空组织可以删除。`, '删除组织', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  const response = await crmDeleteUnit(unit.id)
  if (!response.ok) return ElMessage.error(response.error || '组织删除失败')
  ElMessage.success('组织已删除')
  await loadAll()
}
async function saveUnit() {
  if (!unitForm.name?.trim()) return ElMessage.warning('请填写单位名称')
  const regions = Array.isArray(unitForm.business_regions) ? unitForm.business_regions : []
  const res = await crmSaveUnit({ ...unitForm, business_region: regions[0] || '', business_regions: regions })
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('单位已保存'); unitDialog.value = false; await loadAll()
}

const personDialog = ref(false)
const personForm = reactive<Partial<CrmPerson> & { career_text?: string }>({})
const personDepartmentOptions = computed(() => buildDepartmentOptions(units.value, people.value, personForm.unit_id || ''))
const personManagerOptions = computed(() => {
  const unitId = personForm.unit_id
  if (!unitId || !units.value.some(u => u.id === unitId)) return []
  const root = organizationRoot(units.value, unitId)
  return people.value.filter(p => p.id !== personForm.id && p.unit_id && organizationRoot(units.value, p.unit_id) === root)
})
function clearInvalidPersonManager() {
  if (personForm.manager_id && !personManagerOptions.value.some(p => p.id === personForm.manager_id)) personForm.manager_id = ''
}
watch([() => personForm.unit_id, () => personForm.manager_id, personManagerOptions], clearInvalidPersonManager)
const personDepartmentSelection = computed({
  get: () => {
    const id = personForm.unit_id || ''
    return personForm.department || (id && organizationRoot(units.value, id) !== id) ? assignmentKey(id, personForm.department || '') : ''
  },
  set: (value: string | undefined) => {
    if (!value) {
      personForm.unit_id = organizationRoot(units.value, personForm.unit_id || '')
      personForm.department = ''
      return
    }
    const [id, department] = JSON.parse(value) as [string, string]
    personForm.unit_id = id; personForm.department = department
  },
})
function openPerson(p?: CrmPerson) { if (!permitWrite()) return; 
  for (const key of Object.keys(personForm)) delete personForm[key as keyof typeof personForm]
  Object.assign(personForm, p ? { ...p, career_text: (p.career_track || []).join(' → ') } : { id: '', department: '', manager_id: '', responsibilities: '', name: '', unit_id: '', title: '', mobile: '', office_phone: '', email: '', wechat: '', decision_role: '', power_radius: '', influence: 50, stance: '未知', career_text: '', rotation_window: '', version: 0 })
  personDialog.value = true
}
async function savePerson() {
  if (!personForm.name?.trim()) return ElMessage.warning('请填写姓名')
  clearInvalidPersonManager()
  const res = await crmSavePerson({ ...personForm, career_track: (personForm.career_text || '').split('→').map((s) => s.trim()).filter(Boolean) })
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('人物已保存'); personDialog.value = false; await loadAll()
}

// ---- 关系维系 ----
const relDialog = ref(false)
const relForm = reactive<Partial<CrmRelation>>({})
const canReassignRelation = computed(() => !relForm.id || !relForm._owner || relForm._owner === authState.user?.username || capabilities.value.batch_assign)
function openRelation(r?: CrmRelation) { if (!permitWrite()) return;  Object.assign(relForm, r || { id: '', person_id: '', our_member: '', source: '', intro_path: '', version: 0 }); relDialog.value = true }
function openRelationFor(personId: string) { if (!permitWrite()) return;  Object.assign(relForm, { id: '', person_id: personId, our_member: '', source: '', intro_path: '', version: 0 }); relDialog.value = true }
async function saveRelation() {
  if (!relForm.person_id) return ElMessage.warning('请选择关联客户人')
  const res = await crmSaveRelation(relForm)
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('关系已保存'); relDialog.value = false; await loadAll()
}
function clearRelationMember() {
  relForm.our_member = ''
}

const actionDialog = ref(false)
const actionForm = reactive<Partial<CrmAction>>({})
function openAction(r: CrmRelation) { if (!permitAction()) return;  Object.assign(actionForm, { next_step: '', due_date: '', owner: r.our_member, project_id: projectId.value, relation_id: r.id, type: '拜访', level: '', intel: '', cost: '', effective: false, bidirectional: false, decision_node: '', happened_at: new Date().toISOString().slice(0, 10) }); actionDialog.value = true }
async function saveAction() {
  const res = await crmAddAction(actionForm)
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('动作已留痕，关系强度已重算'); actionDialog.value = false; await loadAll()
}

// ---- 项目作战地图 ----
const projectId = ref('')
const opportunityOptions = computed(() => opportunities.value.map(item => ({ value: item.code, label: `${item.code} · ${item.name}${item.owner_unit ? `（${item.owner_unit}）` : ''}${item.cancelled ? ' · 已作废' : ''}` })))
const selectedOpportunity = computed(() => opportunities.value.find(item => item.code === projectId.value))
const normalizeOrganizationName = (value = '') => value.toLowerCase().replace(/[（）()\s·、，,./\\-]/g, '').replace(/(有限责任公司|股份有限公司|有限公司|集团公司|集团)$/g, '')
const opportunityUnitIds = computed(() => {
  const owner = normalizeOrganizationName(selectedOpportunity.value?.owner_unit)
  if (!owner) return new Set<string>()
  const byId = new Map(units.value.map(unit => [unit.id, unit]))
  const matched = new Set(units.value.filter(unit => {
    const names = [unit.name, unit.company_full_name, unit.subsidiary_full_name].map(normalizeOrganizationName).filter(Boolean)
    return names.some(name => name === owner || (name.length >= 4 && (name.includes(owner) || owner.includes(name))))
  }).map(unit => unit.id))
  let changed = true
  while (changed) { changed = false; for (const unit of units.value) if (unit.parent_unit_id && matched.has(unit.parent_unit_id) && !matched.has(unit.id)) { matched.add(unit.id); changed = true } }
  return new Set([...matched].filter(id => byId.has(id)))
})
const opportunityPeople = computed(() => regionData.value.people.filter(person => opportunityUnitIds.value.has(person.unit_id)).sort((a, b) => {
  const relationScore = (person: CrmPerson) => Math.max(...relations.value.filter(relation => relation.person_id === person.id).map(relation => relation.score || 0), -1)
  return relationScore(b) - relationScore(a) || b.influence - a.influence
}))
const opportunityPeopleOptions = computed(() => opportunityPeople.value.map(personOption))
const battleTargetOptions = computed(() => selectedOpportunity.value && opportunityUnitIds.value.size ? opportunityPeopleOptions.value : regionPeopleOptions.value)
const opportunityRelations = computed(() => relations.value.filter(relation => opportunityPeople.value.some(person => person.id === relation.person_id)))
const opportunityRelationCount = computed(() => opportunityRelations.value.length)
const opportunityStrongRelationCount = computed(() => opportunityRelations.value.filter(relation => relation.strength >= 3).length)
const opportunitySinglePointCount = computed(() => opportunityRelations.value.filter(relation => relation.single_point_risk).length)
const opportunityProjectActionCount = computed(() => opportunityRelations.value.flatMap(relation => relation.actions || []).filter(action => action.project_id === projectId.value).length)
const opportunityReadiness = computed(() => {
  if (!selectedOpportunity.value) return ''
  if (!opportunityUnitIds.value.size) return '待建档'
  if (!opportunityPeople.value.length) return '待补关键人'
  if (!opportunityStrongRelationCount.value) return '关系待加固'
  return '可制定行动方案'
})
const battleEmptyDescription = computed(() => {
  if (selectedOpportunity.value && !opportunityUnitIds.value.size) return '先在客户信息中补充业主组织或联系人，系统即可自动纳入作战范围。'
  if (selectedOpportunity.value && !opportunityPeople.value.length) return '业主组织已匹配，但尚无联系人；请先补充关键人后生成方案。'
  if (selectedOpportunity.value && !targetPerson.value) return '从已匹配的业主联系人中选择关键人，生成可执行的关系路径与第一步动作。'
  return '选择机会点与目标客户人，生成「打谁 / 谁去 / 走哪条路 / 第一步」。'
})
function alignOpportunityStage(opportunity?: CrmOpportunity) {
  if (!opportunity?.stage) return
  const stage = playbook.value?.stages.find(item => item.id.includes(opportunity.stage) || opportunity.stage.includes(item.id) ||
    (/(投标|招标|定标)/.test(opportunity.stage) && /招标|定标/.test(item.id)) || (/(实施|履约|执行)/.test(opportunity.stage) && /履约/.test(item.id)))
  if (stage) stageId.value = stage.id
}
watch(() => selectedOpportunity.value?.code, () => { targetPerson.value = ''; alignOpportunityStage(selectedOpportunity.value) })
const opportunityInput = ref<HTMLInputElement | null>(null)
function chooseOpportunityFile() { opportunityInput.value?.click() }
async function importOpportunities(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  try { const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.onerror = () => reject(new Error('文件读取失败')); reader.readAsDataURL(file) }); const result = await crmImportOpportunities({ filename: file.name, data }); if (!result.ok) return ElMessage.error(result.error || '导入失败'); await loadAll(); ElMessage.success(`已导入 ${result.imported} 条机会点；有效 ${result.active} 条，作废归档 ${result.archived} 条`) } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导入失败') } finally { (event.target as HTMLInputElement).value = '' }
}
async function exportOpportunities(filters: { state: 'all' | 'active' | 'archived'; stage: string; keyword: string }) {
  try {
    const { blob, name } = await crmExportOpportunities(filters)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = name; anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${filters.state === 'all' ? '当前筛选' : filters.state === 'active' ? '有效机会点' : '作废归档'}结果`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导出失败') }
}
async function saveOpportunity(payload: Partial<CrmOpportunity>) {
  if (!permitWrite()) return
  const result = await crmSaveOpportunity(payload)
  if (!result.ok) return ElMessage.error(result.error || '保存失败')
  await loadAll()
  ElMessage.success('机会点已更新')
}
const stageId = ref('设计')
const coverage = ref<CrmCoverage | null>(null)
const selectedStage = computed(() => playbook.value?.stages.find(s => s.id === stageId.value))
async function loadCoverage() {
  if (!projectId.value.trim()) return ElMessage.warning('请先填写项目编号 / 名称')
  const current = projectId.value
  const result = await crmProjectMap(current)
  if (current === projectId.value) coverage.value = result.coverage
}
function fillGap(node: string, type: string) { if (!permitWrite()) return; 
  Object.assign(linkForm, { project_id: projectId.value, decision_node: node, our_member: ourPerson.value, person_id: regionData.value.people.find(p => units.value.find(u => u.id === p.unit_id)?.type === type)?.id || '' })
  linkDialog.value = true
}

const targetPerson = ref('')
const battle = ref<CrmBattleMap | null>(null)
watch([projectId, targetPerson, stageId], () => { battle.value = null })
watch(projectId, () => { coverage.value = null })
const linkDialog = ref(false)
const linkForm = reactive({ project_id: '', decision_node: '定标', person_id: '', our_member: '' })
function openLink() { if (!permitWrite()) return;  Object.assign(linkForm, { project_id: projectId.value, decision_node: '定标', person_id: '', our_member: ourPerson.value }); linkDialog.value = true }
async function saveLink() {
  if (!linkForm.project_id.trim() || !linkForm.person_id) return ElMessage.warning('请填写项目编号并选择客户人')
  const res = await crmSaveLink(linkForm)
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('决策链已登记'); linkDialog.value = false; battle.value = null; if (linkForm.project_id === projectId.value) await loadCoverage()
}
async function genBattle() {
  if (!projectId.value.trim()) return ElMessage.warning('请先填写项目编号 / 名称')
  if (!targetPerson.value) return ElMessage.warning('请选择目标客户人')
  const key = [projectId.value, targetPerson.value, stageId.value, ourDepartment.value, ourPerson.value].join('|')
  const res = await crmBattleMap({ project_id: projectId.value, target_person_id: targetPerson.value, stage: stageId.value, ...(scopedKeys.value ? {our_members:scopedKeys.value} : {}) })
  if (key !== [projectId.value, targetPerson.value, stageId.value, ourDepartment.value, ourPerson.value].join('|')) return
  if (!res.ok) return ElMessage.error('生成失败，请检查目标客户与项目数据')
  battle.value = res; coverage.value = res.coverage
}
const cellColor = (c?: { covered: boolean; strength: number; applicable?: boolean }) => {
  if (c?.applicable === false) return '#e7edf5'
  if (!c || !c.covered) return '#0e1f3c'
  const s = c.strength
  return s >= 4 ? '#f5c242' : s >= 3 ? '#23e0d0' : s >= 1 ? '#1e6bff' : '#274a80'
}
</script>

<template>
  <section class="workspace-main crm-main crm-workspace-compact" :class="{ 'crm-fullscreen-workspace': cockpitFullscreen }" v-loading="loading">
    <header class="crm-head">
      <div class="crm-head-brand"><h1>客户经营助手 <el-tag size="small" effect="plain">{{ roleLabel }}</el-tag></h1></div>
      <div class="crm-head-actions">
        <div class="crm-head-secondary">
          <el-button :icon="QuestionFilled" @click="usageGuideOpen = true">使用说明</el-button>
          <RegionSettings :can-edit="canManage" compact />
          <el-button :loading="loading" :icon="Refresh" @click="loadAll">刷新</el-button>
          <el-button :icon="Upload" @click="importDialog = true">Excel 收集</el-button>
          <el-button :icon="DataBoard" @click="cockpitFullscreen = !cockpitFullscreen" :disabled="!overview">{{ cockpitFullscreen ? '退出全屏' : '全屏模式' }}</el-button>
        </div>
        <el-button class="crm-head-primary" type="primary" :icon="Plus" @click="openQuick" :disabled="!capabilities.write">信息收集</el-button>
      </div>
    </header>

    <HolographicBoard :organization-graph="organizationNetwork" v-if="holographicOpen && regionData.overview" :overview="regionData.overview" :scope="`${businessRegion || '全部区域'} · ${ourPerson ? memberLabel(ourPerson) : ourDepartment || '全部部门与人员'}`" :initial-project="projectId" :can-write="capabilities.write" @close="holographicOpen = false" @select="(id,kind) => { holographicOpen = false; onGraphSelect(id,kind) }" @gap="(project,node,type) => { holographicOpen = false; projectId = project; fillGap(node,type) }" />
    <QuickCapture ref="quickCapture" :units="units" :people="people" @saved="loadAll" />
    <el-dialog v-model="usageGuideOpen" title="使用说明" width="min(1120px,96vw)" top="5vh" class="crm-usage-dialog" destroy-on-close>
      <UsageGuide :can-write="capabilities.write" @navigate="navigateUsageGuide" @create="openQuick" />
    </el-dialog>
    <el-alert v-if="!capabilities.write" title="当前为只读模式，可查看本人数据；编辑与导入需单独授权。" type="info" :closable="false" />
    <div class="crm-mobile-tab-switch">
      <span>当前模块</span>
      <el-select v-model="activeTab" aria-label="切换客户经营模块">
        <el-option v-for="item in mobileTabOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </div>
    <nav class="crm-module-nav" role="tablist" aria-label="客户经营模块">
      <button v-for="item in mobileTabOptions" :key="item.value" type="button" role="tab" :aria-selected="activeTab === item.value" :aria-controls="`pane-${item.value}`" @click="activeTab = item.value">{{ item.label }}</button>
    </nav>
    <el-tabs v-model="activeTab" class="crm-tabs crm-content-tabs">
      <el-tab-pane label="经营驾驶舱" name="cockpit"><Cockpit :organization-units="units" :manager-selection-region="managerSelectionRegion" :manager-selection-regions="managerSelectionRegions" @manager-region="setManagerSelectionRegion" :manager-options="managerOptions" :manager-id="reviewingManager" :manager-label="managerLabel" :can-review-managers="canReviewManagers" :can-export="canReviewManagers" @manager="setReviewingManager" v-if="cockpitData.overview" :mode="cockpitMode" :modes="cockpitModes" :overview="cockpitData.overview" :units="cockpitData.units" :people="cockpitData.people" :relations="cockpitData.relations" :playbook="cockpitData.playbook" :region="cockpitRegion" :regions="regionalSummary" :staff="staff" :responsibility="cockpitMode === 'manager' ? '本人负责客户' : cockpitMode === 'regional' ? `${cockpitRegion || '指定区域'}全部客户` : '全部已授权部门与区域'" @mode="setCockpitMode" @showcase="holographicOpen = true" @department="d => ourDepartment = d" @region="setCockpitRegion" :can-write="capabilities.write" @navigate="navigateCockpit" @create="openQuick" @refresh="loadAll" @select="onGraphSelect" @search="searchCockpit" @export="openExportDialog" /></el-tab-pane>
      <el-tab-pane label="客户关系" name="customers" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">客户关系</span>
          <h2>把“客户是谁、关系怎么样、谁来负责”一处理清</h2>
          <p>建档 → 诊断 → 指派 → 补齐，四步覆盖客户关系全生命周期；点选下方卡片进入对应工作台。</p>
        </header>
        <nav class="crm-relation-guide" role="tablist" aria-label="客户关系功能">
          <button v-for="(item, i) in customerRelationTabs" :key="item.value" type="button" role="tab" :aria-selected="customerRelationSection === item.value" :class="{ 'is-active': customerRelationSection === item.value }" @click="customerRelationSection = item.value">
            <span class="crg-step">{{ i + 1 }}</span>
            <el-icon class="crg-icon"><component :is="item.icon" /></el-icon>
            <span class="crg-text"><strong>{{ item.label }}</strong><small>{{ item.desc }}</small></span>
          </button>
        </nav>
        <section v-if="customerRelationSection === 'archive'">
        <div class="crm-organization-tabs">
          <el-radio-group v-model="customerView" class="crm-subnav" aria-label="客户信息视图">
            <el-radio-button value="contacts">联系人档案</el-radio-button>
            <el-radio-button value="organization">客户组织架构</el-radio-button>
            <el-radio-button value="own">我方组织</el-radio-button>
          </el-radio-group>
          <div v-if="customerView !== 'own'" class="crm-organization-actions">
            <el-button v-if="canReviewManagers" :loading="organizationExporting" @click="runOrganizationExport">导出客户组织架构</el-button>
            <el-button @click="openOrganizationCanvas()">调整架构画布</el-button>
          </div>
        </div>
        <OwnOrganization v-if="customerView === 'own'" :read-only="!capabilities.write" @changed="loadAll" />
        <template v-else-if="customerView === 'organization'"><OrganizationTree :read-only="!capabilities.write" :units="organizationRegionUnits" :people="organizationRegionPeople" @edit-unit="openUnit" @edit-person="openPerson" @adjust-canvas="openOrganizationCanvas" @add-child="addChildUnit" @add-person="openPersonForUnit" @delete-unit="(u) => safely(() => deleteCanvasUnit(u))"><template #filters><div role="group" aria-label="组织区域筛选"><ScopeFilters v-model:region="businessRegion" v-model:department="ourDepartment" v-model:member="ourPerson" :regions="businessRegions" :departments="departmentOptions" :members="scopedStaff.map(p => ({ value: p.member_key, label: memberLabel(p.member_key) }))" region-only /></div></template></OrganizationTree></template>
        <template v-else>
        <div class="crm-battle-bar crm-contact-filters" role="group" aria-label="联系人筛选">
          <ScopeFilters v-model:region="businessRegion" v-model:department="ourDepartment" v-model:member="ourPerson" :regions="businessRegions" :departments="departmentOptions" :members="scopedStaff.map(p => ({ value: p.member_key, label: memberLabel(p.member_key) }))" region-only />
          <el-input v-model="archiveQuery" :prefix-icon="Search" clearable placeholder="搜索组织、部门、姓名或职务" aria-label="搜索客户联系人" />
          <el-select v-model="archiveType" clearable placeholder="全部组织类型" style="width:180px"><el-option v-for="t in unitTypes" :key="t" :label="t" :value="t" /></el-select>
          <el-select v-model="archiveImportance" clearable placeholder="全部重要程度" aria-label="联系人重要程度筛选" style="width:160px"><el-option v-for="t in ['重要','一般']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select>
          <el-select v-model="archiveSupport" clearable placeholder="全部支持程度" aria-label="联系人支持程度筛选" style="width:170px"><el-option v-for="t in ['反对','中立','支持','积极支持']" :key="t" :label="t" :value="t"/><el-option label="待补充" value="__empty__"/></el-select>
          <el-button v-if="archiveImportance || archiveSupport" @click="archiveImportance=''; archiveSupport=''">清除程度筛选</el-button>
        </div>
        <div class="crm-archive-switch"><strong>联系人（{{ filteredPeople.length }}）</strong><span>当前筛选结果 · 切换上方视图查看组织层级</span></div>
        <div class="crm-archive">
          <div class="crm-block">
            <div class="crm-block-head"><h3>客户联系人</h3><el-button size="small" :icon="Plus" @click="openQuick" :disabled="!capabilities.write">新增联系人</el-button></div>
            <el-table class="crm-person-archive" :data="pagedPeople" empty-text="暂无客户联系人">
              <el-table-column label="联系人" min-width="110"><template #default="{ row }"><b>{{ row.name }}</b></template></el-table-column>
              <el-table-column label="组织归属" min-width="250" show-overflow-tooltip><template #default="{ row }">{{ row.company_full_name || row.unit_name || unitName(row.unit_id) }}</template></el-table-column>
              <el-table-column label="联系方式" min-width="180"><template #default="{ row }"><span :class="{'crm-dim':!(row.mobile || row.office_phone || row.email || row.wechat)}">{{ row.mobile || row.office_phone || row.email || row.wechat || '待补全' }}</span></template></el-table-column>
              <el-table-column label="我方对接人" min-width="170" show-overflow-tooltip><template #default="{row}"><span :class="{'crm-dim':!relations.some(r => r.person_id === row.id)}">{{ [...new Set(relations.filter(r => r.person_id === row.id).map(r => memberLabel(r.our_member)))].join('；') || '尚未建立关系' }}</span></template></el-table-column>
              <el-table-column label="维系周期" width="110"><template #default="{row}"><span :class="{'crm-dim':!row.maintenance_days}">{{ row.maintenance_days ? `${row.maintenance_days} 天` : '待确认' }}</span></template></el-table-column>
              <el-table-column label="重要程度" width="100"><template #default="{row}"><PersonFlags field="importance" :importance="row.importance" /></template></el-table-column>
              <el-table-column label="支持程度" width="110"><template #default="{row}"><PersonFlags field="support" :support="row.support_level" /></template></el-table-column>
              <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="onGraphSelect(row.id, 'person')">详情</el-button><el-button v-if="capabilities.write" link type="primary" @click="openPerson(row)">编辑</el-button></template></el-table-column>
            </el-table>
          </div>
        </div>
      <el-pagination v-if="filteredPeople.length > listPageSize" v-model:current-page="archivePage" :page-size="listPageSize" :total="filteredPeople.length" layout="prev, pager, next, total" class="crm-pagination" />
        </template>
      </section>
      <el-dialog v-model="exportDialog" title="导出客户关系表" width="min(560px,94vw)" append-to-body>
        <p class="crm-hint">经营管理员可按联合指挥、区域指挥、客户经理三级导出客户关系；表格含重要程度与支持程度。</p>
        <el-form label-position="top">
          <el-form-item label="导出层级">
            <el-radio-group v-model="exportLevel">
              <el-radio-button v-for="lvl in exportLevels" :key="lvl.value" :value="lvl.value">{{ lvl.label }}</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="exportLevel === 'region' || exportLevel === 'manager'" :label="exportLevel === 'manager' ? '经营区域（先按区域查找对接人员）' : '经营区域'">
            <el-select v-model="exportRegion" style="width:100%" placeholder="选择要导出的区域"><el-option v-for="area in businessRegions" :key="area" :label="area" :value="area" /></el-select>
          </el-form-item>
          <el-form-item v-if="exportLevel === 'manager'" label="客户经理">
            <el-select v-model="exportManager" filterable style="width:100%" placeholder="选择该区域的客户对接人"><el-option v-for="m in exportManagerOptions" :key="m.username" :label="`${m.name} · ${m.count} 位联系人`" :value="m.username" /></el-select>
          </el-form-item>
          <p class="crm-hint">{{ exportLevels.find(l => l.value === exportLevel)?.hint }}</p>
        </el-form>
        <template #footer><el-button @click="exportDialog = false">取消</el-button><el-button type="primary" :loading="exporting" @click="runExport">导出 Excel</el-button></template>
      </el-dialog>
      <section v-if="customerRelationSection === 'assessment'">
        <LiaisonDirectory :relations="relations" :people="people" :units="units" :can-manage="canManage" @refresh="loadAll" @navigate="navigateCustomerRelation" />
      </section>
      <template v-if="false">
        <div class="crm-page-intro"><h2>{{ pageGuide[0] }}</h2><p>{{ pageGuide[1] }}</p></div>
        <div class="crm-relation-summary" aria-label="关系维系概览">
          <div class="crs-tile"><span class="crs-label">在维系关系</span><b>{{ relationSummary.total }}</b><small>当前范围可见</small></div>
          <button class="crs-tile crs-tile--btn" :class="{ 'is-active': relationAttention }" @click="relationAttention = !relationAttention"><span class="crs-label">待维系 / 告警</span><b class="crs-amber">{{ relationSummary.maintain }}</b><small>{{ relationSummary.alarm }} 条已告警，点按只看需维系</small></button>
          <div class="crs-tile"><span class="crs-label">单点风险</span><b class="crs-red">{{ relationSummary.singlePoint }}</b><small>仅 1 位我方对接人的客户联系人</small></div>
          <div class="crs-tile"><span class="crs-label">本月登记互动</span><b class="crs-teal">{{ relationSummary.monthActions }}</b><small>真实沟通，不含未来计划</small></div>
          <button class="crs-tile crs-tile--btn" :class="{ 'is-active': relationView === 'tasks' }" @click="showMyTasks"><span class="crs-label">我的待办</span><b class="crs-blue">{{ relationSummary.followups }}</b><small>已排期、尚未完成的下一步</small></button>
        </div>
        <el-radio-group v-model="relationView" class="crm-subnav" aria-label="关系维系视图"><el-radio-button value="relations">联系人维系</el-radio-button><el-radio-button value="tasks">我的待办 <el-tag size="small" round>{{ relationFollowups.length }}</el-tag></el-radio-button></el-radio-group>
        <template v-if="relationView === 'relations'">
        <div class="crm-relation-tools" role="group" aria-label="关系维系筛选">
          <el-select v-model="relationRegion" clearable placeholder="全部经营区域" aria-label="关系经营区域"><el-option v-for="r in businessRegions" :key="r" :label="r" :value="r" /></el-select>
          <el-input v-model="relationQuery" :prefix-icon="Search" clearable placeholder="搜索联系人、对接人或认识渠道" aria-label="搜索关系" />
          <el-select v-model="relationState" clearable placeholder="全部维系状态" aria-label="关系维系状态"><el-option v-for="(label,key) in decayText" :key="key" :label="label" :value="key" /></el-select>
          <el-button :disabled="!(relationRegion || relationQuery || relationState || relationAttention)" @click="resetRelationFilters">重置</el-button>
          <el-button class="crm-relation-create" type="primary" :icon="Plus" @click="openRelation()" :disabled="!capabilities.write">新建关系</el-button>
        </div>
        <div class="crm-relation-meta"><strong>{{ visibleRelations.length }} 条关系</strong><span>展开行查看互动与计划</span><el-tooltip :content="`${relationScopeLabel}。本人负责的客户关系可维护；变更我方对接人由区域负责人或客户经营管理员统一分配。`"><span class="crm-relation-scope" aria-label="关系维系可见范围">{{ relationScopeLabel }}</span></el-tooltip></div>
        <RelationshipLinks :relations="visibleRelations" :people="people" />
        <el-table class="crm-relations-table" :data="pagedRelations" row-key="id" empty-text="当前没有匹配的关系，可重置筛选或新建关系">
          <el-table-column type="expand"><template #default="{row}"><div class="crm-action-history"><h3>互动与计划</h3><p v-if="!row.actions?.length">暂无记录，实际沟通后登记动作；未来安排通过信息收集记录。</p><article v-for="a in row.actions || []" :key="a.id"><el-tag size="small" :type="a.record_kind === 'plan' ? 'warning' : 'info'">{{ a.record_kind === 'plan' ? '计划' : '已记录互动' }}</el-tag><strong>{{ a.type }}</strong><span>{{ a.record_kind === 'plan' ? a.due_date || '日期待定' : a.happened_at }}</span><p>{{ a.intel || a.next_step || '未补充内容' }}</p><small v-if="a.next_step">下一步：{{ a.next_step }} · {{ memberLabel(a.owner) }} · {{ a.completed_at ? '已完成' : '待跟进' }}</small></article></div></template></el-table-column>
          <el-table-column label="客户联系人" min-width="160"><template #default="{ row }"><strong>{{ row.person_name }}</strong><el-tag v-if="row.single_point_risk" class="crm-single-point-tag" type="danger" effect="dark" size="small">单点风险</el-tag></template></el-table-column>
          <el-table-column label="强度" width="130"><template #default="{ row }"><el-tag :class="{ 'crm-strength-entry': row.strength === 1 || row.strength === 2 }" :type="row.strength >= 4 ? 'success' : row.strength >= 1 ? 'primary' : 'info'" size="small">L{{ row.strength }} {{ row.strength_label }}</el-tag></template></el-table-column>
          <el-table-column label="我方对接人" min-width="130"><template #default="{row}"><strong>{{ row.our_staff?.name || row.our_member_label || memberLabel(row.our_member) }}</strong></template></el-table-column>
          <el-table-column label="部门 / 岗位" min-width="200" show-overflow-tooltip><template #default="{row}"><span :title="row.our_staff?.company">{{ row.our_staff?.department || '部门待补充' }}</span><div class="crm-relation-job">{{ row.our_staff?.title || '岗位待补充' }}</div></template></el-table-column><el-table-column label="最近互动" width="120"><template #default="{row}">{{ row.last_touch || '尚未记录' }}</template></el-table-column>
          <el-table-column label="维系状态" width="140"><template #default="{ row }"><el-tag :type="decayType[row.decay_state]" size="small">{{ decayText[row.decay_state] }} · {{ row.days_since_touch === null ? '未触达' : row.days_since_touch + '天' }}</el-tag></template></el-table-column>
          <el-table-column prop="action_count" label="实际互动" width="80" />
          <el-table-column label="单点风险" width="90"><template #default="{ row }"><el-tag v-if="row.single_point_risk" type="danger" size="small">单点</el-tag><span v-else>-</span></template></el-table-column>
          <el-table-column label="操作" width="150"><template #default="{ row }"><el-button link type="primary" @click="openAction(row)" :disabled="!capabilities.register_action">登记动作</el-button><el-button link @click="openRelation(row)" :disabled="!canEditRelation(row)">编辑</el-button></template></el-table-column>
        </el-table>
        <el-pagination v-if="visibleRelations.length > listPageSize" v-model:current-page="relationPage" :page-size="listPageSize" :total="visibleRelations.length" layout="prev, pager, next, total" class="crm-pagination" />
        </template>
        <section v-else class="crm-relation-followups" aria-label="我的待办">
          <header><div><h3>我的待办 <el-tag>{{ relationFollowups.length }}</el-tag></h3><p>来自联系人维系中登记的“下一步事项”；逾期事项优先显示。</p></div><el-button @click="relationView = 'relations'">去登记互动</el-button></header>
          <el-empty v-if="!relationFollowups.length" description="暂无待办；在联系人维系中登记动作时填写下一步事项和跟进日期" :image-size="64" />
          <el-table v-else :data="pagedRelationFollowups" class="crm-followup-table" empty-text="暂无待办">
            <el-table-column label="待办事项" min-width="260"><template #default="{row}"><strong>{{ row.next_step || '跟进客户关系' }}</strong><small>{{ row.person_name }} · {{ row.project_id || '未关联项目' }}</small></template></el-table-column>
            <el-table-column label="负责人" min-width="120"><template #default="{row}">{{ row.owner_label || memberLabel(row.owner) || '待指派' }}</template></el-table-column>
            <el-table-column label="跟进日期" min-width="130"><template #default="{row}"><el-tag :type="row.overdue ? 'danger' : 'info'">{{ row.overdue ? '已逾期 · ' : '' }}{{ row.due_date || '未定日期' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="180" fixed="right"><template #default="{row}"><el-button link @click="showRelationForTask(row.relation_id)">查看关系</el-button><el-button link type="primary" :disabled="!capabilities.write || row.can_complete === false" :loading="saving" @click="safely(() => closeFollowup(row.id))">{{ row.can_complete === false ? '仅可查看' : '标记完成' }}</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-if="relationFollowups.length > listPageSize" v-model:current-page="relationTaskPage" :page-size="listPageSize" :total="relationFollowups.length" layout="prev, pager, next, total" class="crm-pagination" />
        </section>
      </template>
      <section v-if="customerRelationSection === 'coordination'">
        <div class="crm-overview-purpose" aria-label="关系统筹使用说明"><div><strong>日常维系 → 关系维系</strong><span>登记沟通、查看互动与安排下一步。</span></div><div><strong>责任统筹 → 当前页面</strong><span>筛出待指派关系并批量明确负责人；人员变化时转移关系，同步交接未完成计划。</span></div></div>
        <el-radio-group v-model="relationshipOverviewMode" style="margin-bottom:12px"><el-radio-button value="workbench">关系指派 / 转移</el-radio-button><el-radio-button value="graph">关系网络 / 引荐</el-radio-button></el-radio-group>
        <RelationshipWorkbench v-if="overview && relationshipOverviewMode==='workbench'" :units="units" :people="people" :relations="relations" :staff="staff" :playbook="playbook" :can-write="capabilities.write" :can-register-action="!!capabilities.register_action" :can-batch-assign="!!capabilities.batch_assign" @select="onGraphSelect" @action="actOnWarning" @refresh="loadAll"/>
        <div v-if="overview && relationshipOverviewMode==='graph'" class="crm-overview">
          <div class="crm-graph-card">
            <h3><el-icon><Connection /></el-icon> 关系网络图谱</h3>
            <div class="crm-graph-controls">
              <span class="cgc-label">筛选单位：</span>
              <el-check-tag v-for="t in overview.unit_types" :key="t" :checked="!hiddenTypes.includes(t)" @change="toggleType(t)">{{ t }}</el-check-tag>
              <el-checkbox v-model="onlyGaps" size="small" style="margin-left:8px">只看缺口/告警</el-checkbox>
            </div>
            <div class="crm-graph-controls">
              <span class="cgc-label">引荐路径：</span>
              <el-select-v2 v-model="pathTarget" :options="allPeopleOptions" placeholder="选目标客户人" filterable clearable size="small" style="width:190px" @change="highlightIntroPath" />
              <el-button v-if="highlightPath.length" size="small" @click="clearPath">清除高亮</el-button>
              <span v-if="pathHint" class="cgc-path">{{ pathHint }}</span>
            </div>
            <RelationGraph :organization-graph="overviewNetwork" :nodes="graphNodes" :edges="graphEdges" :highlight-path="highlightPath"
              :type-color="typeColor" :hidden-types="hiddenTypes" :only-gaps="onlyGaps" @select="onGraphSelect" />
            <div class="crm-legend">
              <span><i style="background:#f5c242"></i>紧密 L4+</span><span><i style="background:#23e0d0"></i>一般 L2-3</span>
              <span><i style="background:#3a5a8c"></i>待建立</span><span><i style="background:#4a5f8c"></i>单位</span><span><i class="ring"></i>缺口 / 告警</span>
            </div>
          </div>
          <div class="crm-warn-card">
            <h3><el-icon><Warning /></el-icon> 关系衰减预警</h3>
            <p class="crm-hint">优先按联系人维系周期预警；未设置时按高层90天、中层45天、基层21天。支持程度与系统关系强度分别记录。</p>
            <el-empty v-if="!overviewWarnings.length" description="暂无待维系关系" :image-size="70" />
            <ul v-else class="crm-warn-list">
              <li v-for="w in overviewWarnings.slice((warningPage-1)*3,warningPage*3)" :key="w.relation_id">
                <div><strong>{{ w.person_name }}</strong><small>{{ w.unit_name }} · {{ w.tier }} · L{{ w.strength }}</small></div>
                <el-button size="small" text @click="actOnWarning(w.relation_id)" :disabled="!capabilities.register_action">登记维系</el-button>
                <el-tag :type="decayType[w.decay_state]" size="small">{{ decayText[w.decay_state] }} · {{ w.days_since_touch ?? '-' }}天</el-tag>
              </li>
            </ul>
            <el-pagination v-if="overviewWarnings.length > 3" v-model:current-page="warningPage" :page-size="3" :total="overviewWarnings.length" layout="prev, pager, next" />
          </div>
        </div>
      </section>
      <section v-if="customerRelationSection === 'completion'">
        <ImportCompletionTasks :can-manage="canManage" @completed="loadAll" />
      </section>
      </el-tab-pane>
      <el-tab-pane label="关系维系" name="relation" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">关系维系</span>
          <h2>盯住每一段客户关系，别让它冷掉</h2>
          <p>登记真实互动、跟进下一步、及时处理告警与单点风险；历史互动与未来计划分开记录。</p>
        </header>
        <div class="crm-relation-summary crm-relation-summary--kpi" aria-label="关系维系概览">
          <div class="crs-tile"><span class="crs-ic crs-ic--blue"><el-icon><Connection /></el-icon></span><div class="crs-body"><span class="crs-label">在维系关系</span><b>{{ relationSummary.total }}</b><small>当前范围可见</small></div></div>
          <button class="crs-tile crs-tile--btn" :class="{ 'is-active': relationAttention }" @click="relationAttention = !relationAttention"><span class="crs-ic crs-ic--amber"><el-icon><Warning /></el-icon></span><div class="crs-body"><span class="crs-label">待维系 / 告警</span><b class="crs-amber">{{ relationSummary.maintain }}</b><small>{{ relationSummary.alarm }} 条已告警 · 点按只看需维系</small></div></button>
          <div class="crs-tile"><span class="crs-ic crs-ic--red"><el-icon><User /></el-icon></span><div class="crs-body"><span class="crs-label">单点风险</span><b class="crs-red">{{ relationSummary.singlePoint }}</b><small>仅一位我方对接人的联系人</small></div></div>
        </div>
        <nav class="crm-relation-guide crm-relation-guide--pair" role="tablist" aria-label="关系维系视图">
          <button type="button" role="tab" :aria-selected="relationView === 'relations'" :class="{ 'is-active': relationView === 'relations' }" @click="relationView = 'relations'"><el-icon class="crg-icon"><ChatDotRound /></el-icon><span class="crg-text"><strong>联系人维系</strong><small>登记互动、查看关系与安排下一步</small></span></button>
          <button type="button" role="tab" :aria-selected="relationView === 'tasks'" :class="{ 'is-active': relationView === 'tasks' }" @click="showMyTasks"><el-icon class="crg-icon"><Tickets /></el-icon><span class="crg-text"><strong>我的待办</strong><small>来自互动登记的下一步，逾期优先</small></span><el-tag class="crg-badge" size="small" round>{{ relationFollowups.length }}</el-tag></button>
        </nav>
        <template v-if="relationView === 'relations'">
          <div class="crm-relation-tools"><el-select v-model="relationRegion" clearable placeholder="全部经营区域"><el-option v-for="r in businessRegions" :key="r" :label="r" :value="r" /></el-select><el-input v-model="relationQuery" :prefix-icon="Search" clearable placeholder="搜索联系人、对接人或认识渠道"/><el-select v-model="relationState" clearable placeholder="全部维系状态"><el-option v-for="(label,key) in decayText" :key="key" :label="label" :value="key" /></el-select><el-button :disabled="!(relationRegion || relationQuery || relationState || relationAttention)" @click="resetRelationFilters">重置</el-button><el-button type="primary" :icon="Plus" @click="openRelation()" :disabled="!capabilities.write">新建关系</el-button></div>
          <RelationshipLinks :relations="visibleRelations" :people="people" />
          <el-table class="crm-relations-table" :data="pagedRelations" row-key="id" empty-text="当前没有匹配关系">
            <el-table-column label="客户联系人" min-width="170"><template #default="{row}"><strong>{{ row.person_name }}</strong><el-tag v-if="row.single_point_risk" type="danger" size="small">单点风险</el-tag></template></el-table-column><el-table-column label="关系强度" width="120"><template #default="{row}"><el-tag>L{{ row.strength }} {{ row.strength_label }}</el-tag></template></el-table-column><el-table-column label="我方对接人" min-width="140"><template #default="{row}">{{ row.our_staff?.name || row.our_member_label || memberLabel(row.our_member) }}</template></el-table-column><el-table-column label="最近互动" width="125"><template #default="{row}">{{ row.last_touch || '尚未记录' }}</template></el-table-column><el-table-column label="维系状态" width="140"><template #default="{row}"><el-tag :type="decayType[row.decay_state]">{{ decayText[row.decay_state] }} · {{ row.days_since_touch === null ? '未触达' : row.days_since_touch + '天' }}</el-tag></template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openAction(row)" :disabled="!capabilities.register_action">登记动作</el-button><el-button link @click="openRelation(row)" :disabled="!canEditRelation(row)">编辑</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-if="visibleRelations.length > listPageSize" v-model:current-page="relationPage" :page-size="listPageSize" :total="visibleRelations.length" layout="prev, pager, next, total" class="crm-pagination" />
        </template>
        <section v-else class="crm-relation-followups"><header><div><h3>我的待办 <el-tag>{{ relationFollowups.length }}</el-tag></h3><p>来自联系人维系中登记的下一步事项，逾期优先。</p></div><el-button @click="relationView = 'relations'">去登记互动</el-button></header><el-empty v-if="!relationFollowups.length" description="暂无待办；登记动作时填写下一步事项和跟进日期" :image-size="64"/><el-table v-else :data="pagedRelationFollowups" class="crm-followup-table"><el-table-column label="待办事项" min-width="280"><template #default="{row}"><strong>{{ row.next_step || '跟进客户关系' }}</strong><small>{{ row.person_name }} · {{ row.project_id || '未关联项目' }}</small></template></el-table-column><el-table-column label="负责人" min-width="120"><template #default="{row}">{{ row.owner_label || memberLabel(row.owner) || '待指派' }}</template></el-table-column><el-table-column label="跟进日期" min-width="130"><template #default="{row}"><el-tag :type="row.overdue ? 'danger' : 'info'">{{ row.overdue ? '已逾期 · ' : '' }}{{ row.due_date || '未定日期' }}</el-tag></template></el-table-column><el-table-column label="操作" width="180" fixed="right"><template #default="{row}"><el-button link @click="showRelationForTask(row.relation_id)">查看关系</el-button><el-button link type="primary" :disabled="!capabilities.write || row.can_complete === false" :loading="saving" @click="safely(() => closeFollowup(row.id))">{{ row.can_complete === false ? '仅可查看' : '标记完成' }}</el-button></template></el-table-column></el-table><el-pagination v-if="relationFollowups.length > listPageSize" v-model:current-page="relationTaskPage" :page-size="listPageSize" :total="relationFollowups.length" layout="prev, pager, next, total" class="crm-pagination"/></section>
      </el-tab-pane>
      <el-tab-pane label="机会点管理" name="opportunities" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">机会点管理</span>
          <h2>管好每一个要打的项目机会</h2>
          <p>集中维护项目机会、业主单位与阶段信息；从任一机会点一键进入项目作战地图，系统自动带出对应客户组织与关系资产。</p>
        </header>
        <OpportunityManagement :opportunities="opportunities" :can-import="capabilities.import" :can-export="capabilities.read" :can-edit="capabilities.write" @import="chooseOpportunityFile" @save="saveOpportunity" @export="exportOpportunities" @battle="code => { projectId = code; activeTab = 'battle' }"/>
      </el-tab-pane>
      <el-tab-pane label="项目作战地图" name="battle" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">项目作战地图</span>
          <h2>三步排出：这次该找谁、由谁去、怎么去</h2>
          <p>不用研究复杂关系图 —— 选机会点、选要联系的人、选阶段，系统自动给出可执行的下一步行动与决策链覆盖。</p>
        </header>
        <section class="crm-battle-console" aria-label="作战准备台">
          <div class="crm-battle-scope" role="group" aria-label="当前模块数据筛选"><span class="cbs-label">数据范围</span><ScopeFilters v-model:region="businessRegion" v-model:department="ourDepartment" v-model:member="ourPerson" :regions="businessRegions" :departments="departmentOptions" :members="scopedStaff.map(p => ({ value: p.member_key, label: memberLabel(p.member_key) }))" /></div>
          <div class="crm-battle-steps" aria-label="作战地图使用步骤">
            <div class="is-active" :class="{ 'is-done': !!projectId }"><b>1</b><span><strong>选机会点</strong><small>确定这次要推进哪个项目</small></span></div>
            <div :class="{ 'is-active': !!projectId, 'is-done': !!targetPerson }"><b>2</b><span><strong>选要联系的人</strong><small>系统只展示该业主单位的联系人</small></span></div>
            <div :class="{ 'is-active': !!targetPerson }"><b>3</b><span><strong>拿行动建议</strong><small>得到谁去、通过谁、做什么</small></span></div>
          </div>
          <div class="crm-battle-bar crm-project-bar">
            <label class="crm-project-field"><span>第 1 步 · 这次推进哪个机会点？</span><el-select-v2 v-model="projectId" :options="opportunityOptions" filterable allow-create clearable placeholder="选择机会点" style="width:260px" /></label>
            <label class="crm-project-field"><span>第 2 步 · 这次重点联系谁？</span><el-select-v2 v-model="targetPerson" :options="battleTargetOptions" :placeholder="selectedOpportunity && opportunityUnitIds.size ? '从业主联系人中选择' : '先选择机会点'" filterable clearable style="width:220px" /></label>
            <label class="crm-project-field"><span>第 3 步 · 项目正处于哪一阶段？</span><el-select v-model="stageId" style="width:190px"><el-option v-for="s in playbook?.stages || []" :key="s.id" :label="s.title" :value="s.id" /></el-select></label>
            <div class="crm-battle-actions">
              <el-button size="large" :loading="saving" @click="battleSection = 'coverage'; safely(loadCoverage)" :disabled="!projectId.trim()">检查关键岗位</el-button>
              <el-button size="large" type="primary" :icon="Aim" :loading="saving" @click="battleSection = 'map'; safely(genBattle)" :disabled="!projectId.trim() || !targetPerson">生成下一步行动</el-button>
            </div>
          </div>
          <div class="crm-battle-utility">
            <span class="cbu-hint">缺关键岗位联系人或还没导入机会点？</span>
            <el-button text bg :icon="Plus" @click="openLink" :disabled="!capabilities.write">补充关键岗位联系人</el-button>
            <el-button text bg :icon="Upload" @click="chooseOpportunityFile" :disabled="!capabilities.import">导入机会点</el-button><input ref="opportunityInput" type="file" accept=".xlsx,.xlsm" hidden @change="importOpportunities" />
          </div>
        </section>

        <section v-if="selectedOpportunity" class="crm-opportunity-card" aria-label="当前机会点详情">
          <header><div><span>当前机会点</span><h3>{{ selectedOpportunity.name || '名称待补充' }}</h3><small>{{ selectedOpportunity.code }} · {{ selectedOpportunity.owner_unit || '业主单位待补充' }}</small></div><el-tag :type="selectedOpportunity.cancelled ? 'info' : 'success'" effect="light">{{ selectedOpportunity.cancelled ? '已作废' : selectedOpportunity.status || '进行中' }}</el-tag></header>
          <div class="crm-opportunity-meta"><span><b>阶段</b>{{ selectedOpportunity.stage || '—' }}</span><span><b>赢率</b>{{ selectedOpportunity.win_rate || '—' }}</span><span><b>客户经理</b>{{ selectedOpportunity.manager || '—' }}</span><span><b>预计招标</b>{{ selectedOpportunity.bid_date || '—' }}</span><span><b>预计签约</b>{{ selectedOpportunity.contract_date || '—' }}</span><span><b>可参与份额</b>{{ selectedOpportunity.amount || '—' }} 万元</span></div>
          <div v-if="selectedOpportunity.owner_unit" class="crm-opportunity-bridge" :class="{ 'is-unmatched': !opportunityUnitIds.size }"><template v-if="opportunityUnitIds.size"><b>系统已找到这家客户</b><span>“{{ selectedOpportunity.owner_unit }}”下有 {{ opportunityPeople.length }} 位联系人；下一步只需从中选出这次最该联系的人。</span></template><template v-else><b>系统还没找到这家客户</b><span>“{{ selectedOpportunity.owner_unit }}”尚未在客户信息中建档；先补充组织或联系人，才可以生成可靠的联系建议。</span></template></div>
          <div class="crm-opportunity-readiness" aria-label="机会点关系准备度">
            <div><span>现在能不能开始？</span><strong :class="{ 'is-ready': opportunityReadiness === '可制定行动方案', 'is-waiting': opportunityReadiness !== '可制定行动方案' }">{{ opportunityReadiness }}</strong><small>{{ opportunityUnitIds.size ? `${opportunityUnitIds.size} 个组织节点` : '还没有客户档案' }}</small></div>
            <div><span>谁可以帮忙联系？</span><strong>{{ opportunityStrongRelationCount }} <small>/ {{ opportunityRelationCount }} 条</small></strong><small>有较稳定联系的关系数</small></div>
            <div><span>怕不怕人走关系断？</span><strong :class="{ 'is-waiting': opportunitySinglePointCount }">{{ opportunitySinglePointCount ? `${opportunitySinglePointCount} 条单点` : '暂无单点' }}</strong><small>单点关系建议补一位备份</small></div>
            <div><span>这个项目做过什么？</span><strong>{{ opportunityProjectActionCount }} 项</strong><small>已经登记的互动和跟进</small></div>
          </div>
          <p v-if="selectedOpportunity.cancelled" class="crm-opportunity-archive">已作废，仅用于历史作战与关系覆盖回溯<span v-if="selectedOpportunity.cancel_reason">：{{ selectedOpportunity.cancel_reason }}</span></p>
        </section>

        <div v-if="selectedStage" class="crm-stage-brief"><strong>{{ selectedStage.title }} · 阶段建议</strong><p>{{ selectedStage.action }}</p><span>应留存：{{ selectedStage.deliverable }}</span></div>
        <el-radio-group v-if="battle || coverage" v-model="battleSection" class="crm-subnav"><el-radio-button value="map">行动方案</el-radio-button><el-radio-button value="coverage">决策链覆盖</el-radio-button></el-radio-group>
        <div v-if="battle && battleSection === 'map'" class="crm-battle">
          <div class="crm-battle-map">
            <div class="bm-cell"><span>这次联系谁</span><strong>{{ battle.battle_map.target }}</strong></div>
            <div class="bm-cell"><span>建议由谁联系</span><strong>{{ battle.battle_map.who_goes }}</strong></div>
            <div class="bm-cell"><span>建议怎么联系 <el-tag size="small" :type="battle.graph_source === 'neo4j' ? 'success' : 'info'" effect="dark">{{ (battle.graph_path?.hops || 0) > 1 ? '先核实' : '已有记录' }}</el-tag></span><strong>{{ battle.battle_map.route }}</strong></div>
            <div class="bm-cell"><span>这次先做什么</span><strong>{{ battle.battle_map.first_step }}</strong></div>
          </div>
          <details><summary>查看六步分析依据</summary><div class="crm-pipeline">
            <div v-for="s in battle.pipeline" :key="s.step" class="pipe"><b>{{ s.step }}</b><span>{{ s.detail }}</span></div>
          </div></details>
        </div>
          <div v-if="coverage && battleSection === 'coverage'" class="crm-heatmap">
            <h3>决策链覆盖度：应覆盖 {{ coverage.should_cover }} · 已覆盖 {{ coverage.covered }} · L3以上 {{ coverage.l3_plus }}</h3>
            <p class="crm-hint">浅灰：参考模板非必需 · 深蓝：待覆盖 · 青金：已建立关系。点击格子补充节点；按项目实际职责登记的额外格子将纳入统计。</p>
            <table>
              <thead><tr><th></th><th v-for="n in coverage.nodes" :key="n">{{ n }}</th></tr></thead>
              <tbody><tr v-for="ut in coverage.unit_types" :key="ut"><td>{{ ut }}</td><td v-for="n in coverage.nodes" :key="n"><button type="button" class="hm" @click="fillGap(n, ut)" :aria-label="`${ut} · ${n}：登记或补充联系人`" :style="{ background: cellColor(coverage.matrix[ut][n]), color: coverage.matrix[ut][n]?.applicable === false || coverage.matrix[ut][n]?.strength >= 3 ? '#173656' : '#fff' }" :disabled="!capabilities.write" :title="coverage.matrix[ut][n]?.covered ? 'L' + coverage.matrix[ut][n].strength : coverage.matrix[ut][n]?.applicable === false ? '参考模板非必需，可登记补充' : '待覆盖，点击登记'">{{ coverage.matrix[ut][n]?.covered ? 'L' + coverage.matrix[ut][n].strength : coverage.matrix[ut][n]?.applicable === false ? '选填' : '待补' }}</button></td></tr></tbody>
            </table>
          </div>
        <el-empty v-if="battleSection === 'map' ? !battle : !coverage" :description="battleEmptyDescription" />
      </el-tab-pane>
      <el-tab-pane v-if="canManage" label="安全权限" name="security" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">安全权限</span>
          <h2>谁能进、能改什么、能看谁的数据，一处配清</h2>
          <p>「功能权限」决定能做什么、「数据范围」决定能看见谁的数据，两者分开设置；每一次授权与操作都会留痕，可随时追溯。</p>
        </header>
        <nav class="crm-relation-guide crm-relation-guide--pair" role="tablist" aria-label="安全权限功能">
          <button type="button" role="tab" :aria-selected="securityView === 'permissions'" :class="{ 'is-active': securityView === 'permissions' }" @click="securityView = 'permissions'"><el-icon class="crg-icon"><Key /></el-icon><span class="crg-text"><strong>权限管理</strong><small>按组织架构配置功能与数据范围、指派管理员</small></span></button>
          <button v-if="capabilities.read" type="button" role="tab" :aria-selected="securityView === 'audit'" :class="{ 'is-active': securityView === 'audit' }" @click="securityView = 'audit'"><el-icon class="crg-icon"><DocumentChecked /></el-icon><span class="crg-text"><strong>操作留痕</strong><small>谁在何时做了什么，授权变更全程可追溯</small></span></button>
        </nav>
        <SecurityPanel v-if="securityView === 'permissions'" :relations="relations" :people="people" :units="units" :appoint="capabilities.appoint" :manage="capabilities.manage" @changed="loadAll" />
        <AuditTrail v-else-if="capabilities.read" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="importDialog" title="Excel 资料收集" width="min(780px,94vw)" class="crm-editor-dialog"><p class="crm-import-intro">下载模板 → 一行填写一位联系人 → 上传查看结果。公司全称、姓名、单位类型齐全的行自动录入；缺项行会推送给“我方姓名”对应账号补齐，补齐后才会并入客户库。</p><ExcelImport :can-import="capabilities.import" @imported="loadAll" /><el-alert v-if="!capabilities.import" title="当前可下载模板；上传需客户经营管理员授予导入权限。" type="info" :closable="false" /></el-dialog>

    <!-- 客户组织对话框 -->
    <el-dialog class="crm-editor-dialog" v-model="unitDialog" :title="unitForm.id ? '编辑客户组织' : '新增客户组织'" width="min(600px,94vw)">
      <el-form label-position="top"><el-row :gutter="14">
        <el-col :span="8"><el-form-item label="组织类别（非固定层数）"><el-select v-model="unitForm.organization_level" style="width:100%"><el-option label="公司" value="company" /><el-option label="子公司" value="subsidiary" /><el-option label="单位" value="unit" /></el-select></el-form-item></el-col>
        <el-col :span="16"><el-form-item :label="({ company: '公司名称', subsidiary: '子公司名称', unit: '单位名称' } as Record<string, string>)[unitForm.organization_level || 'unit']"><el-input v-model="unitForm.name" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="类型"><el-select v-model="unitForm.type" style="width:100%"><el-option v-for="t in unitTypes" :key="t" :label="t" :value="t" /></el-select></el-form-item></el-col>
        <el-col :span="16"><el-form-item label="上级组织"><el-select v-model="unitForm.parent_unit_id" clearable filterable style="width:100%" :placeholder="unitForm.organization_level === 'company' ? '公司为最高层，留空' : '选择上级组织，可继续增加层级'"><el-option v-for="u in units.filter(u => u.id !== unitForm.id)" :key="u.id" :label="organizationUnitPath(u)" :value="u.id" /></el-select></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="经营区域"><el-select v-model="unitForm.business_regions" multiple clearable collapse-tags placeholder="可选择多个经营区域，留空为未分区" style="width:100%"><el-option v-for="area in businessRegions" :key="area" :label="area" :value="area" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="驻地城市"><el-input v-model="unitForm.region" :disabled="unitForm.organization_level === 'company'" :placeholder="unitForm.organization_level === 'company' ? '由下级组织维护' : '例如：广州'" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="线网规模"><el-input v-model="unitForm.line_scale" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="历史中标率"><el-input v-model="unitForm.win_rate" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="招标偏好"><el-input v-model="unitForm.bid_preference" type="textarea" :rows="2" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="历史合作"><el-input v-model="unitForm.history" type="textarea" :rows="2" /></el-form-item></el-col>
      </el-row></el-form>
      <template #footer><el-button @click="unitDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(saveUnit)">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="organizationCanvasOpen" title="调整客户组织架构" width="min(1500px,96vw)" top="4vh" class="crm-organization-canvas-dialog" :close-on-click-modal="false" destroy-on-close>
      <OrganizationCanvas :initial-root-id="organizationCanvasRoot" :selected-id="organizationCanvasSelected" :units="organizationRegionUnits" :people="organizationRegionPeople" :read-only="!capabilities.write" @add-unit="quickAddCanvasUnit" @add-department-child="(id, department) => editCanvasDepartment(id, department, 'add')" @delete-department="(id, department) => editCanvasDepartment(id, department, 'delete')" @edit-unit="openUnit" @edit-person="openPerson" @move-unit="moveCanvasUnit" @move-person="moveCanvasPerson" @delete-unit="deleteCanvasUnit" />
    </el-dialog>

    <!-- 人物对话框 -->
    <el-dialog class="crm-editor-dialog" v-model="personDialog" :title="personForm.id ? '编辑人物' : '新增人物'" width="min(640px,94vw)">
      <el-form label-position="top"><el-row :gutter="14">
        <el-col :span="8"><el-form-item label="姓名"><el-input v-model="personForm.name" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="所属单位"><el-select v-model="personForm.unit_id" filterable style="width:100%" @change="personForm.department = ''"><el-option v-for="u in units" :key="u.id" :label="organizationUnitPath(u)" :value="u.id" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="职务"><el-input v-model="personForm.title" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="手机（选填）"><el-input v-model="personForm.mobile" inputmode="tel" maxlength="40" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="办公电话（选填）"><el-input v-model="personForm.office_phone" inputmode="tel" maxlength="60" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="邮箱（选填）"><el-input v-model="personForm.email" inputmode="email" maxlength="160" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="微信 / 其他联系（选填）"><el-input v-model="personForm.wechat" maxlength="100" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="决策角色"><el-select v-model="personForm.decision_role" clearable style="width:100%"><el-option v-for="r in roles" :key="r" :label="r" :value="r" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="立场"><el-select v-model="personForm.stance" style="width:100%"><el-option v-for="s in ['支持', '中立', '反对', '未知']" :key="s" :label="s" :value="s" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="影响力"><el-slider v-model="personForm.influence" :max="100" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="所属部门"><el-tree-select v-model="personDepartmentSelection" :data="personDepartmentOptions" check-strictly filterable clearable :render-after-expand="false" placeholder="未分配人员" aria-label="所属部门" style="width:100%" :disabled="!personForm.unit_id" empty-text="暂无部门，请先在组织架构中新增" /><small class="crm-hint">按组织架构选择；清空后归为上级组织的未分配人员。</small></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="直接上级"><el-select v-model="personForm.manager_id" clearable filterable aria-label="直接上级" :disabled="!personForm.unit_id" :placeholder="personForm.unit_id ? '请选择本组织人员' : '请先选择所属单位'" no-data-text="本组织暂无其他人员" style="width:100%"><el-option v-for="p in personManagerOptions" :key="p.id" :label="`${p.name} · ${p.unit_name || unitName(p.unit_id)} · ${p.title}`" :value="p.id" /></el-select><small class="crm-hint">仅限当前客户组织及其下级单位的人员，不含本人。</small></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="重要程度"><el-select v-model="personForm.importance" clearable><el-option label="重要" value="重要" /><el-option label="一般" value="一般" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="支持程度"><el-select v-model="personForm.support_level" clearable><el-option v-for="code in ['反对','中立','支持','积极支持']" :key="code" :label="code" :value="code" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="维系周期（天，选填）"><el-input v-model="personForm.maintenance_days" placeholder="1–365；留空按层级" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="收集表跟进轨迹（原文）"><el-input v-model="personForm.imported_history" type="textarea" :rows="3" maxlength="2000" placeholder="已发生的业务跟进原文，不会自动拆分或计为有效动作" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="负责事项"><el-input v-model="personForm.responsibilities" type="textarea" :rows="2" placeholder="描述职责范围；项目决策角色仍在项目决策链中单独登记" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="权力半径"><el-input v-model="personForm.power_radius" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="轮岗窗口"><el-input v-model="personForm.rotation_window" placeholder="如 2026年内可能调动" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="职业轨迹（用 → 分隔，本行业金矿）"><el-input v-model="personForm.career_text" placeholder="设计院 → 业主 → 总包" /></el-form-item></el-col>
      </el-row></el-form>
      <template #footer><el-button @click="personDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(savePerson)">保存</el-button></template>
    </el-dialog>

    <!-- 关系对话框 -->
    <el-dialog class="crm-editor-dialog" v-model="relDialog" :title="relForm.id ? '编辑关系' : '新建关系'" width="min(560px,94vw)">
      <el-form label-position="top">
        <el-form-item label="关联客户人"><el-select-v2 v-model="relForm.person_id" :options="regionPeopleOptions" filterable style="width:100%" :disabled="!!relForm.id" /></el-form-item>
        <el-form-item label="我方对接人"><template v-if="canReassignRelation"><StaffPicker v-model="relForm.our_member" /><div style="display:flex;align-items:center;justify-content:space-between;width:100%;margin-top:6px;font-size:12px;color:#70839a"><span>{{ relForm.our_member ? '可重新选择，或删除当前对接人；关系与互动记录会保留。' : '暂不设置对接人，后续可随时编辑指派。' }}</span><el-button v-if="relForm.our_member" link type="danger" @click="clearRelationMember">删除对接人</el-button></div></template><template v-else><span>{{ relForm.our_staff?.name || relForm.our_member_label || relForm.our_member }}</span><p class="crm-hint">变更对接人请联系区域负责人或客户经营管理员。</p></template></el-form-item>
        <el-form-item label="关系来源"><el-input v-model="relForm.source" placeholder="如 技术交流 / 老同事引荐" /></el-form-item>
        <el-form-item label="引荐路径"><el-input v-model="relForm.intro_path" /></el-form-item>
        <el-alert type="info" :closable="false" title="单点风险由系统自动判断"><template #default>同一客户联系人仅有 1 位已指派我方对接人时标记为单点；新增并指派不同对接人会自动解除。未指派关系单列为待分配，不计为单点。</template></el-alert>
      </el-form>
      <template #footer><el-button @click="relDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(saveRelation)">保存</el-button></template>
    </el-dialog>

    <!-- 动作对话框 -->
    <el-dialog class="crm-editor-dialog" v-model="actionDialog" title="登记动作留痕" width="min(560px,94vw)">
      <el-form label-position="top"><el-row :gutter="14">
        <el-col :span="12"><el-form-item label="动作类型"><el-select v-model="actionForm.type" style="width:100%"><el-option v-for="t in ['拜访', '电话', '需求澄清', '技术交流', '方案汇报', '联调协调', '验收移交', '回款跟进', '微信沟通']" :key="t" :label="t" :value="t" /></el-select></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="发生日期"><el-input v-model="actionForm.happened_at" placeholder="YYYY-MM-DD" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="关联决策节点"><el-select v-model="actionForm.decision_node" clearable style="width:100%"><el-option v-for="n in decisionNodes" :key="n" :label="n" :value="n" /></el-select></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="投入成本"><el-input v-model="actionForm.cost" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="情报产出"><el-input v-model="actionForm.intel" type="textarea" :rows="2" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="下一步事项"><el-input v-model="actionForm.next_step" placeholder="例如：确认信号系统接口清单并取得书面回复" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="项目编号"><el-input v-model="actionForm.project_id" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="负责人"><StaffPicker v-model="actionForm.owner" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="跟进日期"><el-date-picker v-model="actionForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item><el-checkbox v-model="actionForm.effective">有效动作</el-checkbox></el-form-item></el-col>
        <el-col :span="12"><el-form-item><el-checkbox v-model="actionForm.bidirectional">客户主动（权重×3）</el-checkbox></el-form-item></el-col>
      </el-row></el-form>
      <template #footer><el-button @click="actionDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(saveAction)">保存并重算</el-button></template>
    </el-dialog>

    <!-- 决策链登记 -->
    <el-dialog class="crm-editor-dialog" v-model="linkDialog" title="登记项目决策链节点" width="min(520px,94vw)">
      <el-form label-position="top">
        <el-form-item label="项目编号 / 名称"><el-input v-model="linkForm.project_id" /></el-form-item>
        <el-form-item label="我方对接人"><StaffPicker v-model="linkForm.our_member" /></el-form-item><el-form-item label="决策节点"><el-select v-model="linkForm.decision_node" style="width:100%"><el-option v-for="n in decisionNodes" :key="n" :label="n" :value="n" /></el-select></el-form-item>
        <el-form-item label="负责该节点的客户人"><el-select-v2 v-model="linkForm.person_id" :options="regionPeopleOptions" filterable style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="linkDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(saveLink)">保存</el-button></template>
    </el-dialog>

    <!-- 节点详情抽屉 -->
    <el-drawer v-model="detailOpen" :title="detailStaff?.name || detailPerson?.name || detailUnit?.name || '详情'" size="min(440px,96vw)">
      <div v-if="detailStaff" class="crm-detail"><p>我方人员 · {{ detailStaff.member_key }}</p><div class="cd-row"><span>公司</span><b>{{ detailStaff.company || '待补充' }}</b></div><div class="cd-row"><span>部门 / 岗位</span><b>{{ detailStaff.department || '待补充' }} / {{ detailStaff.title || '待补充' }}</b></div><div class="cd-row"><span>直接上级</span><b>{{ staff.find(p => p.id === detailStaff?.manager_id)?.name || '未登记' }}</b></div><p>{{ detailStaff.responsibilities }}</p><el-divider>客户对接</el-divider><p v-for="r in relations.filter(r=>r.our_member===detailStaff?.member_key)" :key="r.id">{{ r.person_name }} · L{{ r.strength }}</p></div>
      <div v-if="detailPerson" class="crm-detail">
        <p class="cd-sub">{{ detailPerson.unit_name || unitName(detailPerson.unit_id) }} · {{ detailPerson.title || '—' }}</p>
        <div class="cd-row"><span>手机</span><b>{{ detailPerson.mobile || '待补充' }}</b></div>
        <div class="cd-row"><span>办公电话</span><b>{{ detailPerson.office_phone || '待补充' }}</b></div>
        <div class="cd-row"><span>邮箱</span><b>{{ detailPerson.email || '待补充' }}</b></div>
        <div class="cd-row"><span>微信 / 其他联系</span><b>{{ detailPerson.wechat || '待补充' }}</b></div>
        <div class="cd-row"><span>所属部门</span><b>{{ detailPerson.department || '待补充' }}</b></div>
        <div class="cd-row"><span>直接上级</span><b>{{ people.find(p => p.id === detailPerson?.manager_id)?.name || '未登记' }}</b></div>
        <div class="cd-row"><span>负责事项</span><b>{{ detailPerson.responsibilities || '待补充' }}</b></div>
        <div class="cd-row"><span>决策角色</span><b>{{ detailPerson.decision_role || '—' }}</b></div>
        <div class="cd-row"><span>重要 / 支持程度</span><b>{{ detailPerson.importance || '未填' }} / {{ detailPerson.support_level || '未填' }}</b></div>
        <div class="cd-row"><span>维系周期</span><b>{{ detailPerson.maintenance_days ? detailPerson.maintenance_days + '天' : '按人员层级' }}</b></div>
        <div v-if="detailPerson.imported_history" class="cd-row"><span>历史跟进原文</span><p style="white-space:pre-wrap">{{ detailPerson.imported_history }}</p></div>
        <div class="cd-row"><span>立场</span><b>{{ detailPerson.stance }}</b></div>
        <div class="cd-row"><span>影响力</span><el-progress :percentage="detailPerson.influence" :stroke-width="8" style="flex:1" /></div>
        <div class="cd-row"><span>职业轨迹</span><b>{{ (detailPerson.career_track || []).join(' → ') || '—' }}</b></div>
        <template v-if="detailRelation">
          <el-divider>关系</el-divider>
          <div class="cd-row"><span>强度</span><el-tag :class="{ 'crm-strength-entry': detailRelation.strength === 1 || detailRelation.strength === 2 }" :type="detailRelation.strength >= 4 ? 'success' : detailRelation.strength >= 1 ? 'primary' : 'info'" size="small">L{{ detailRelation.strength }} {{ detailRelation.strength_label }}</el-tag></div>
          <div class="cd-row"><span>我方对接</span><b>{{ memberLabel(detailRelation.our_member) }}</b></div><div class="cd-row"><span>评分 / 双向</span><b>{{ detailRelation.score }} · {{ detailRelation.radar?.双向性 ?? 0 }}</b></div>
          <div class="cd-row"><span>衰减</span><el-tag :type="decayType[detailRelation.decay_state]" size="small">{{ decayText[detailRelation.decay_state] }} · {{ detailRelation.days_since_touch ?? '-' }}天</el-tag></div>
          <el-button size="small" type="primary" plain style="margin-top:10px" @click="detailOpen = false; openAction(detailRelation!)" :disabled="!capabilities.register_action">登记动作留痕</el-button>
        </template>
        <template v-else>
          <el-divider>关系</el-divider>
          <el-empty description="尚未建立关系" :image-size="60" />
          <el-button size="small" type="primary" plain @click="detailOpen = false; openRelationFor(detailPerson.id)" :disabled="!capabilities.write">建立关系</el-button>
        </template>
        <el-divider>我方责任分工</el-divider><p v-for="r in relations.filter(r => r.person_id === detailPerson?.id)" :key="r.id">{{ memberLabel(r.our_member) }} · L{{ r.strength }}</p><el-divider>近期动作</el-divider>
        <ul class="cd-actions">
          <li v-for="a in (detailRelation?.actions || []).slice(0, 6)" :key="a.id">
            <b>{{ a.happened_at }}</b> {{ a.type }}<span v-if="a.decision_node"> · {{ a.decision_node }}</span><small v-if="a.intel">{{ a.intel }}</small>
          </li>
          <li v-if="!detailRelation?.actions?.length" class="cd-empty">暂无动作</li>
        </ul>
      </div>
      <div v-else-if="detailUnit" class="crm-detail">
        <p class="cd-sub">{{ detailUnit.type }} · {{ unitRegionLabel(detailUnit) }} · {{ detailUnit.region || '—' }}</p>
        <div class="cd-row"><span>线网规模</span><b>{{ detailUnit.line_scale || '—' }}</b></div>
        <div class="cd-row"><span>中标率</span><b>{{ detailUnit.win_rate || '—' }}</b></div>
        <div class="cd-row"><span>招标偏好</span><b>{{ detailUnit.bid_preference || '—' }}</b></div>
        <div class="cd-row"><span>历史合作</span><b>{{ detailUnit.history || '—' }}</b></div>
        <el-divider>该单位联系人</el-divider>
        <ul class="cd-actions">
          <li v-for="p in people.filter((x) => x.unit_id === detailUnit!.id)" :key="p.id"><b>{{ p.name }}</b> {{ p.title }}</li>
        </ul>
      </div>
    </el-drawer>
  </section>
</template>
