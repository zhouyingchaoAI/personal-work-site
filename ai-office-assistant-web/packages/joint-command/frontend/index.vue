<script setup lang="ts">
import MonthlyBattle from './MonthlyBattle.vue'
import { personOrganizations } from './organizationMembership'
import { isActiveOpportunity, countedAmount, isCustomerUnit } from './command/commandOverview'
import LiaisonDirectory from './RelationshipAssessment.vue'
import ScopeFilters from './ScopeFilters.vue'
import PersonFlags from './PersonFlags.vue'
import { managerReviewOptions } from './managerReview'
import { LIAISON_REGION_ORDER } from './liaisonRegions'
import { computed, defineAsyncComponent, h, onActivated, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
// 仅在对应页签/弹窗首次打开时才加载的重组件，按需切分独立 chunk，缩小首屏主包解析耗时。
const RelationshipWorkbench = defineAsyncComponent(() => import('./RelationshipWorkbench.vue'))
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Warning, Connection, Refresh, QuestionFilled, Upload, DataBoard, Search, Postcard, Odometer, Share, FolderAdd, ChatDotRound, Tickets, User, Setting, ArrowDown } from '@element-plus/icons-vue'
import {
  crmStaff, type CrmStaff, crmOverview, crmUnits, crmPeople, crmRelations, crmSaveUnit, crmDeleteUnit, crmSavePerson, crmDepartmentNode,
  crmSecurityMe, crmSaveRelation, crmAddAction, crmSaveLink, crmGraphPath, crmPlaybook, crmCompleteFollowup, crmImportOpportunities, crmImportSalesContracts, crmSaveOpportunity, crmExportOpportunities, crmOpportunities, crmSalesContracts,
  type CrmPlaybook, crmManagerDirectory, type CrmManagerView, crmExportRelationships, crmExportCustomerOrganization,
  type CrmOverview, type CrmUnit, type CrmPerson, type CrmRelation, type CrmAction, type CrmCapabilities, type CrmOpportunity, type CrmSalesContract,
  crmBusinessAnalysis, crmBusinessImport, crmBusinessTemplate, crmTaskOrderImport, crmTaskOrderTemplate, type BusinessAnalysisData, type BusinessVersion, crmOpportunityTemplate,
} from '../../../src/services/personalWorkApi'
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
import StaffPicker from './StaffPicker.vue'
import { authState } from '../../../src/services/authSession'
const organizationCanvasOpen = ref(false)
const organizationCanvasRoot = ref('')
const organizationCanvasSelected = ref('')
function openOrganizationCanvas(unit?: CrmUnit) {
  organizationCanvasSelected.value = ''
  organizationCanvasRoot.value = unit?.id || ''
  organizationCanvasOpen.value = true
}
const CrmSettings = defineAsyncComponent(() => import('./CrmSettings.vue'))
import { crmRegionSettings } from '../../../src/services/personalWorkApi'
import { REGION_PROVINCES, REGION_CITIES } from './dashboard/chinaMapData'
import Cockpit from './Cockpit.vue'
import Workbench from './Workbench.vue'
import BoardOverview from './BoardOverview.vue'
const BusinessAnalysis = defineAsyncComponent(() => import('./BusinessAnalysis.vue'))
import CustomerWorkspace from './CustomerWorkspace.vue'
import { opportunityKey } from './opportunityDetail'
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

type CrmTab = 'cockpit' | 'dashboard' | 'security' | 'customers' | 'relation' | 'opportunities' | 'battle' | 'monthlyBattle'
const activeTab = ref<CrmTab>('cockpit')
const homeView = ref<'tasks' | 'map'>('map')
const customerView = ref<'overview' | 'contacts' | 'organization'>('overview')
// 关系维系并入“五位一体（客户）”，作为其第五个子模块；此前指向独立“跟进”页签的入口统一改走这里。
function goMaintenance(view: 'relations' | 'tasks' = 'relations') {
  if (view === 'tasks') showMyTasks(); else relationView.value = 'relations'
  customerRelationSection.value = 'maintenance'
  activeTab.value = 'customers'
}
const opportunityFocus = ref<{code:string;key?:string;sequence:number;unitId?:string}>({ code: '', sequence: 0 })
function focusOpportunity(item: CrmOpportunity | null) { opportunityFocus.value = { code: item?.code || '', key:item ? opportunityKey(item) : '', sequence: opportunityFocus.value.sequence + 1 }; activeTab.value = 'opportunities' }
function createCustomerOpportunity(unitId: string) { opportunityFocus.value = { code:'', sequence:opportunityFocus.value.sequence+1, unitId }; activeTab.value='opportunities' }
const customerRelationSection = ref<'archive' | 'assessment' | 'maintenance' | 'coordination' | 'completion'>('archive')
const customerRelationTabs = [
  { value: 'archive', label: '客户档案', desc: '维护客户组织、部门与联系人资料', icon: Postcard },
  { value: 'assessment', label: '关系评估', desc: '诊断三层关系强弱与单点风险', icon: Odometer },
  { value: 'maintenance', label: '关系维系', desc: '登记互动、跟进下一步与我的待办', icon: ChatDotRound },
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
const relationQuery = ref('')
const relationState = ref('')
const relationRegion = ref('')
const relationAttention = ref(false)
function resetRelationFilters() { relationRegion.value = ''; relationQuery.value = ''; relationState.value = ''; relationAttention.value = false }
function navigateUsageGuide(tab: 'cockpit' | 'organization' | 'archive' | 'relation' | 'battle') {
  usageGuideOpen.value = false
  if (tab === 'archive' || tab === 'organization') {
    customerRelationSection.value = 'archive'
    customerView.value = tab === 'organization' ? 'organization' : 'contacts'
    activeTab.value = 'customers'
    return
  }
  if (tab === 'relation') { goMaintenance('relations'); return }
  activeTab.value = tab
}
const mobileTabOptions = computed<{ value: CrmTab; label: string }[]>(() => {
  const options: { value: CrmTab; label: string }[] = [
    { value: 'cockpit', label: '工作台' },
    { value: 'dashboard', label: '经营分析' },
    { value: 'customers', label: '五位一体' },
    { value: 'opportunities', label: '商机管理' },
    { value: 'battle', label: '项目作战地图' },
    { value: 'monthlyBattle', label: '月度任务令作战地图' },
  ]
  if (capabilities.value.read && activeTab.value === 'security') options.push({ value: 'security', label: '设置' })
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
// 客户数口径：顶级客户组织（无上级）。与「客户总览」及驾驶舱保持一致，避免同一数据在不同页面显示不同客户数。
const customerUnits = (items: CrmUnit[]) => items.filter(isCustomerUnit)
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
const salesContracts = shallowRef<CrmSalesContract[]>([])
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
const managerSelectionRegions = [...LIAISON_REGION_ORDER]
const managerOptions = computed(() => allManagerOptions.value.filter(m=>!managerSelectionRegion.value || m.regions.includes(managerSelectionRegion.value)))
const reviewedManager = computed(() => allManagerOptions.value.find(m => m.username === reviewingManager.value))
const managerLabel = computed(() => reviewedManager.value ? `${reviewedManager.value.name}（${reviewedManager.value.member_keys[0]}）` : canReviewManagers.value ? '当前范围暂无区域客户经理' : '本人')
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
  if (canReviewManagers.value) return new Set<string>()
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
watch([ourDepartment, ourPerson], () => { archivePage.value = 1; relationPage.value = 1; warningPage.value = 1; highlightPath.value = []; targetPerson.value = '' })
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
const organizationRegionPeople = computed(() => people.value.filter(person => personOrganizations(person).some(id=>organizationRegionUnitIds.value.has(id))))

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
  if (tab === 'workflow') { goMaintenance('tasks'); return }
  if (tab === 'relation') { goMaintenance('relations'); return }
  if (tab === 'archive') { customerRelationSection.value = 'archive'; activeTab.value = 'customers'; return }
  if (tab === 'overview') { customerRelationSection.value = 'coordination'; activeTab.value = 'customers'; return }
  activeTab.value = tab
}
function navigateCustomerRelation(tab: 'archive' | 'relation' | 'battle') {
  if (tab === 'archive') { customerRelationSection.value = 'archive'; customerView.value = 'contacts'; activeTab.value = 'customers'; return }
  if (tab === 'relation') { goMaintenance('relations'); return }
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
// 联系人 → 我方对接人姓名（优先后端解析的我方人员资料，未指派显示“待指派”），一次建索引避免每行扫描全部关系。
const relationMemberName = (r: CrmRelation) => r.our_staff?.name || r.our_member_label || (r.our_member ? memberLabel(r.our_member) : '待指派')
const contactMembers = computed(() => { const m = new Map<string, string[]>(); for (const r of relations.value) { const list = m.get(r.person_id) || []; const name = relationMemberName(r); if (!list.includes(name)) list.push(name); m.set(r.person_id, list) } return new Map([...m].map(([id, names]) => [id, names.join('；')])) })
// 公司全称之下的下级组织 / 部门，便于在联系人表里区分同一集团的不同部门。
const contactSubPath = (p: CrmPerson) => [p.subsidiary_full_name, p.organization_unit_name, p.department].filter((x, i, arr) => x && x !== p.company_full_name && x !== arr[i - 1]).join(' / ')
watch([archiveQuery,archiveType,archiveImportance,archiveSupport,businessRegion], () => { archivePage.value = 1 })
watch(() => visibleRelations.value.length, count => { relationPage.value = Math.min(relationPage.value, Math.max(1, Math.ceil(count / listPageSize))) })
watch(() => filteredPeople.value.length, count => { archivePage.value = Math.min(archivePage.value, Math.max(1, Math.ceil(count / listPageSize))) })
watch(businessRegion, () => { clearPath(); targetPerson.value = '' })

async function loadAll() {
  loading.value = true
  try {
    const [ov, u, p, guide, security, team, regionSettings, r, importedOpportunities, importedContracts] = await Promise.all([crmOverview(), crmUnits(), crmPeople(), crmPlaybook(), crmSecurityMe(), crmStaff(), crmRegionSettings(), crmRelations(), crmOpportunities(), crmSalesContracts()])
    Object.assign(REGION_PROVINCES, regionSettings.regions)
    Object.assign(REGION_CITIES, regionSettings.cities)
    staff.value = team.staff
    capabilities.value = security.capabilities
    if (canReviewManagers.value) {
      try { managerDirectory.value = (await crmManagerDirectory()).managers }
      catch { managerDirectory.value = []; ElMessage.warning('客户经理名单加载失败，请刷新重试') }
    } else managerDirectory.value = []
    if (!managerOptions.value.some(m => m.username === reviewingManager.value)) reviewingManager.value = managerOptions.value[0]?.username || ''
    playbook.value = guide
    overview.value = ov; units.value = u.units; people.value = p.people; relations.value = r.relations; opportunities.value = importedOpportunities.opportunities; salesContracts.value = importedContracts.contracts
    selectDefaultCockpitMode()
    lastLoadAt.value = Date.now()
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '客户经营数据加载失败') } finally { loading.value = false }
}
onMounted(loadAll)
onMounted(loadBusinessAnalysis)
watch(activeTab, tab => { if (tab === 'dashboard' && !businessData.value) void loadBusinessAnalysis() })
// 切到「客户对接人」时，仅在数据陈旧（>30s）时才整表刷新，避免每次切页都重发 8 个接口造成卡顿；后台定时器负责持续保鲜。
// 进入“五位一体”仅在数据明显过期(>5分钟)时才后台刷新，避免每次切入都全量重载导致的卡顿。
watch(activeTab, tab => { if (tab === 'customers' && Date.now() - lastLoadAt.value > 300000) void loadAll() })
const liaisonRefreshTimer = window.setInterval(() => { if (activeTab.value === 'customers' && !loading.value && !document.hidden && Date.now() - lastLoadAt.value > 300000) void loadAll() }, 300000)
onUnmounted(() => window.clearInterval(liaisonRefreshTimer))
onActivated(() => { activeTab.value = 'cockpit'; homeView.value = 'map' })

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
async function changeCanvasMembership(person: CrmPerson, unitId: string, remove: boolean) {
  if (!permitWrite() || movingCanvasPeople.has(person.id) || person.unit_id===unitId) return
  movingCanvasPeople.add(person.id)
  try {
    const memberships=remove?(person.unit_ids||[]).filter(id=>id!==unitId):[...new Set([...(person.unit_ids||[]),unitId])]
    const response=await crmSavePerson({...person,unit_ids:memberships})
    if(!response.ok)return ElMessage.error(response.error||'兼任关系保存失败')
    people.value=people.value.map(item=>item.id===person.id?{...item,...response.person}:item)
    ElMessage.success(remove?'已移除兼任，主归属和历史记录保留':'已添加兼任，原组织任职保留')
  } catch(error) { ElMessage.error(error instanceof Error?error.message:'兼任关系保存失败') }
  finally { movingCanvasPeople.delete(person.id) }
}
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
const actionIsPlan = ref(false)
const actionAdvanced = ref(false)
const actionForm = reactive<Partial<CrmAction>>({})
function openAction(r: CrmRelation) { if (!permitAction()) return; actionIsPlan.value = false; actionAdvanced.value = false; Object.assign(actionForm, { next_step: '', due_date: '', owner: r.our_member, project_id: '', relation_id: r.id, type: '拜访', level: '', intel: '', cost: '', effective: false, bidirectional: false, decision_node: '', happened_at: new Date().toLocaleDateString('sv-SE') }); actionDialog.value = true }
const planRelations = computed(() => relations.value.filter(r => r.person_id === targetPerson.value))
async function saveAction() {
  if (!actionForm.relation_id) return ElMessage.warning('请选择对接关系')
  if (!actionIsPlan.value && !actionForm.intel?.trim()) return ElMessage.warning('请填写沟通结果')
  if ((actionIsPlan.value || actionForm.next_step?.trim()) && (!actionForm.next_step?.trim() || !actionForm.owner || !actionForm.due_date)) return ElMessage.warning('请补齐下一步、负责人和跟进日期')
  const res = await crmAddAction({ ...actionForm, ...(actionIsPlan.value ? { record_kind: 'plan', happened_at: '', effective: false, bidirectional: false } : {}) })
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success(actionIsPlan.value ? '已加入跟进待办' : '跟进已记录'); actionDialog.value = false; await loadAll()
}

// ---- 项目作战地图 ----
const projectId = ref('')
// 重点作战项目：金额巨大的在谈关键商机单独拎出，按可参与份额降序，可展开监控重点管控。
const keyProjectThreshold = ref(1000)
const keyProjects = computed(() => opportunities.value
  .filter(o => isActiveOpportunity(o) && countedAmount(o) >= keyProjectThreshold.value)
  .sort((a, b) => countedAmount(b) - countedAmount(a)))
// 若从商机列表“推进建议”定位了某机会点，即便低于阈值也纳入监控列表并自动展开。
const monitorProjects = computed(() => {
  const list = [...keyProjects.value]
  if (projectId.value && !list.some(o => o.code === projectId.value)) {
    const focused = opportunities.value.find(o => o.code === projectId.value)
    if (focused) list.unshift(focused)
  }
  return list
})
const expandedKeyProjects = ref<string[]>([])
watch(projectId, code => { if (code && !expandedKeyProjects.value.includes(code)) expandedKeyProjects.value = [code, ...expandedKeyProjects.value] })
// 从驾驶舱「进入作战部署」跳入时，展开并滚动到该项目，避免落在清单顶部找不到。
watch([projectId, activeTab], ([code, tab]) => {
  if (!code || tab !== 'battle') return
  setTimeout(() => document.querySelector(`[data-project-code="${CSS.escape(code)}"]`)?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 350)
})
function keyProjectStageProgress(o: CrmOpportunity) {
  const done = Object.values(o.stage_progress || {}).filter(s => s.status === '已完成').length
  return { done, total: 6 }
}
function keyProjectFollowups(code: string) { return (playbook.value?.followups || []).filter(f => f.project_id === code) }
const OpportunityStagePanel = defineAsyncComponent(() => import('./OpportunityStagePanel.vue'))
// 经营分析：整份联指经营数据集，按标准模板导入后按日期归档为历史版本。
const businessData = ref<BusinessAnalysisData | null>(null)
const businessView = ref<import('../../../src/services/personalWorkApi').BusinessView>({ view: 'company' })
const businessViewOptions = ref<import('../../../src/services/personalWorkApi').BusinessViewOptions | null>(null)
const businessLoading = ref(false)
let businessRequest = 0
async function changeBusinessView(selection: import('../../../src/services/personalWorkApi').BusinessView) {
  businessView.value = selection
  await loadBusinessAnalysis(businessData.value?.version)
}
const businessVersions = ref<BusinessVersion[]>([])
const businessInput = ref<HTMLInputElement | null>(null)
const taskOrderInput = ref<HTMLInputElement | null>(null)
async function loadBusinessAnalysis(version?: string) {
  const requestId = ++businessRequest
  businessLoading.value = true
  businessData.value = null
  businessVersions.value = []
  try {
    const res = await crmBusinessAnalysis(version, businessViewOptions.value ? businessView.value : undefined)
    if (requestId !== businessRequest) return
    if (!res.ok) throw new Error(res.error || '读取经营分析失败')
    businessData.value = res.data
    businessVersions.value = res.versions || []
    businessViewOptions.value = res.view_options || null
  } catch (error) {
    if (requestId === businessRequest) ElMessage.error(error instanceof Error ? error.message : '读取经营分析失败')
  } finally {
    if (requestId === businessRequest) businessLoading.value = false
  }
}
function chooseBusinessFile() { if (!permitWrite()) return; businessInput.value?.click() }
async function importBusinessData(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  try {
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.onerror = () => reject(new Error('文件读取失败')); reader.readAsDataURL(file) })
    const result = await crmBusinessImport({ filename: file.name, data })
    if (!result.ok) return ElMessage.error(result.error || '导入失败')
    await loadBusinessAnalysis()
    ElMessage.success(`经营数据已导入：${result.sheets} 张子表`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导入失败') } finally { (event.target as HTMLInputElement).value = '' }
}
async function downloadBusinessTemplate(blocks?: string[]) {
  try { const { blob, name } = await crmBusinessTemplate(businessData.value?.version, blocks); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '下载模板失败') }
}
function chooseTaskOrderFile() { if (!permitWrite()) return; taskOrderInput.value?.click() }
async function importTaskOrderData(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  try {
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.onerror = () => reject(new Error('文件读取失败')); reader.readAsDataURL(file) })
    const result = await crmTaskOrderImport({ filename: file.name, data })
    if (!result.ok) return ElMessage.error(result.error || '任务令导入失败')
    await loadBusinessAnalysis()
    ElMessage.success(`任务令已导入：${result.sheets} 张表、${result.rows} 条任务`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '任务令导入失败') } finally { (event.target as HTMLInputElement).value = '' }
}
async function downloadTaskOrderTemplate() {
  try { const { blob, name } = await crmTaskOrderTemplate(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '下载任务令模板失败') }
}
const opportunityInput = ref<HTMLInputElement | null>(null)
const salesContractInput = ref<HTMLInputElement | null>(null)
function chooseOpportunityFile() { opportunityInput.value?.click() }
function chooseSalesContractFile() { salesContractInput.value?.click() }
async function importSalesContracts(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  try {
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.onerror = () => reject(new Error('文件读取失败')); reader.readAsDataURL(file) })
    const result = await crmImportSalesContracts({ filename: file.name, data })
    if (!result.ok) return ElMessage.error(result.error || '销售合同导入失败')
    await loadAll()
    ElMessage.success(`销售合同已导入：${result.contracts || 0} 份，确认 ${result.matched_opportunities || 0} 个商机赢单，${result.unmatched_projects || 0} 个项目待匹配`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '销售合同导入失败') }
  finally { (event.target as HTMLInputElement).value = '' }
}
async function downloadOpportunityTemplate() {
  try { const { blob, name } = await crmOpportunityTemplate(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '下载模板失败') }
}
async function importOpportunities(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  try {
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || ''); reader.onerror = () => reject(new Error('文件读取失败')); reader.readAsDataURL(file) })
    const preview = await crmImportOpportunities({ filename: file.name, data, mode: 'preview' })
    if (!preview.ok) return ElMessage.error(preview.error || '文件校验失败')
    let mode: 'skip' | 'update' = 'update'
    if (preview.duplicate_count) {
      const shown = (preview.duplicates || []).slice(0, 12)
      const content = h('div', { style: 'text-align:left' }, [
        h('p', { style: 'margin:0 0 10px;color:#536b87;line-height:1.6' }, `文件共 ${preview.total || 0} 行，其中 ${preview.new_count || 0} 条为新商机。请选择重复项处理方式：`),
        h('div', { style: 'max-height:240px;overflow:auto;border:1px solid #e1e9f4;border-radius:8px;background:#f7faff;padding:6px 10px' }, shown.map(item =>
          h('div', { style: 'padding:7px 0;border-bottom:1px solid #e7eef7;font-size:12px' }, [
            h('b', { style: 'color:#15499c;margin-right:8px' }, item.code),
            h('span', item.name || item.existing_name || '未命名商机'),
            h('small', { style: 'display:block;color:#8795a8;margin-top:3px' }, `${item.owner_unit || '客户待补充'} · ${item.reason}`),
          ])
        )),
        preview.duplicates_truncated ? h('p', { style: 'margin:8px 0 0;color:#8a94a6;font-size:12px' }, '仅展示前 100 条重复记录。') : null,
        h('p', { style: 'margin:10px 0 0;color:#8a6a35;font-size:12px;line-height:1.6' }, '去重导入会保留系统中的原记录，仅导入新编码；覆盖更新会保留已维护的阶段材料、关系人与成交结果。'),
      ])
      try {
        await ElMessageBox.confirm(content, `发现 ${preview.duplicate_count} 条重复商机`, {
          confirmButtonText: '覆盖更新', cancelButtonText: '去重导入（保留现有）',
          distinguishCancelAndClose: true, closeOnClickModal: false, type: 'warning', customClass: 'opportunity-duplicate-dialog',
        })
      } catch (action) {
        if (action === 'cancel') mode = 'skip'
        else return
      }
    }
    const result = await crmImportOpportunities({ filename: file.name, data, mode })
    if (!result.ok) return ElMessage.error(result.error || '导入失败')
    await loadAll()
    ElMessage.success(`导入完成：新增 ${result.created || 0} 条，更新 ${result.updated || 0} 条，跳过重复 ${result.skipped || 0} 条`)
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '导入失败') }
  finally { (event.target as HTMLInputElement).value = '' }
}
async function exportOpportunities(filters: { state: 'all' | 'active' | 'archived'; stage: string; region: string; sales_stage: string; keyword: string }) {
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
  if (!permitWrite()) return false
  const result = await crmSaveOpportunity(payload)
  if (!result.ok) { ElMessage.error(result.error || '保存失败'); return false }
  await loadAll()
  ElMessage.success('机会点已更新')
  return true
}
const targetPerson = ref('')
const linkDialog = ref(false)
const linkForm = reactive({ project_id: '', decision_node: '定标', person_id: '', our_member: '' })
async function saveLink() {
  if (!linkForm.project_id.trim() || !linkForm.person_id) return ElMessage.warning('请填写项目编号并选择客户人')
  const res = await crmSaveLink(linkForm)
  if (!res.ok) return ElMessage.error(res.error || '保存失败')
  ElMessage.success('决策链已登记'); linkDialog.value = false
}
</script>

<template>
  <section class="workspace-main crm-main crm-workspace-compact" :class="{ 'crm-fullscreen-workspace': cockpitFullscreen }" v-loading="loading">
    <header class="crm-head">
      <div class="crm-head-brand"><h1>联指经营助手 <el-tag size="small" effect="plain">{{ roleLabel }}</el-tag></h1></div>
      <div class="crm-head-actions">
        <el-button v-if="capabilities.read" :icon="Setting" @click="activeTab = 'security'">设置</el-button>
        <el-popover placement="bottom-end" :width="212" trigger="click" popper-class="crm-more-popper"><template #reference><el-button>更多<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button></template>
          <div class="crm-more-menu">
            <button type="button" @click="usageGuideOpen = true"><el-icon><QuestionFilled /></el-icon>使用说明</button>
            <button type="button" :disabled="loading" @click="loadAll"><el-icon :class="{ 'is-loading': loading }"><Refresh /></el-icon>刷新数据</button>
            <button type="button" @click="importDialog = true"><el-icon><Upload /></el-icon>Excel 收集</button>
            <button type="button" :disabled="!overview" @click="cockpitFullscreen = !cockpitFullscreen"><el-icon><DataBoard /></el-icon>{{ cockpitFullscreen ? '退出全屏' : '全屏模式' }}</button>
          </div>
        </el-popover>
        <el-button class="crm-head-primary" type="primary" :icon="Plus" @click="openQuick" :disabled="!capabilities.write">信息收集</el-button>
      </div>
    </header>

    <HolographicBoard :organization-graph="organizationNetwork" v-if="holographicOpen && regionData.overview" :overview="regionData.overview" :scope="`${businessRegion || '全部区域'} · ${ourPerson ? memberLabel(ourPerson) : ourDepartment || '全部部门与人员'}`" :initial-project="projectId" :can-write="capabilities.write" @close="holographicOpen = false" @select="(id,kind) => { holographicOpen = false; onGraphSelect(id,kind) }" @gap="(project,node,_type) => { holographicOpen = false; projectId = project; Object.assign(linkForm, { project_id: project, decision_node: node, person_id: '', our_member: ourPerson }); linkDialog = true }" />
    <QuickCapture ref="quickCapture" :units="units" :people="people" @saved="loadAll" />
    <el-dialog v-model="usageGuideOpen" title="使用说明" width="min(1120px,96vw)" top="5vh" class="crm-usage-dialog" destroy-on-close>
      <UsageGuide :can-write="capabilities.write" @navigate="navigateUsageGuide" @create="openQuick" />
    </el-dialog>
    <el-alert v-if="!capabilities.write" title="当前为只读模式，可查看授权范围内的数据；编辑与导入需单独授权。" type="info" :closable="false" />
    <div class="crm-mobile-tab-switch">
      <span>当前模块</span>
      <el-select v-model="activeTab" aria-label="切换客户经营模块">
        <el-option v-for="item in mobileTabOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </div>
    <nav class="crm-module-nav" role="tablist" aria-label="客户经营模块">
      <button v-for="item in mobileTabOptions" :key="item.value" type="button" role="tab" :aria-selected="activeTab === item.value" :aria-controls="`pane-${item.value}`" @click="activeTab = item.value">{{ item.label }}</button>
    </nav>
    <!-- 机会点导入文件选择器置于页签之外，确保在任意页签（含惰性加载的作战地图）下都已挂载可用。 -->
    <input ref="opportunityInput" type="file" accept=".xlsx,.xlsm" hidden @change="importOpportunities" />
    <input ref="salesContractInput" type="file" accept=".xlsx,.xlsm" hidden @change="importSalesContracts" />
    <input ref="businessInput" type="file" accept=".xlsx,.xlsm" hidden @change="importBusinessData" />
    <input ref="taskOrderInput" type="file" accept=".xlsx,.xlsm" hidden @change="importTaskOrderData" />
    <el-tabs v-model="activeTab" class="crm-tabs crm-content-tabs" :class="{ 'crm-task-home': homeView === 'tasks' }">
      <div v-if="activeTab === 'cockpit' && homeView === 'map'" class="crm-home-switch"><el-button @click="homeView='tasks'">返回工作台</el-button></div>
      <BoardOverview v-if="activeTab === 'cockpit' && homeView === 'tasks'" :business="businessData" :units="units" :people="people" :relations="relations" :opportunities="opportunities" :followups="playbook?.followups || []" @navigate="t => { activeTab = t as any }" @cockpit="homeView = 'map'" />
      <Workbench :staff="staff" v-if="activeTab === 'cockpit' && homeView === 'tasks'" :can-record="!!capabilities.register_action" :manager-view="canManage || canReviewManagers" :opportunities="opportunities" @opportunity="focusOpportunity" :followups="playbook?.followups || []" :relations="relations" :can-write="capabilities.write" :busy="saving" @map="homeView = 'map'" @all="navigateCockpit('workflow')" @relation="id => { resetRelationFilters(); showRelationForTask(id); goMaintenance('relations') }" @record="openAction" @complete="id => safely(() => closeFollowup(id))" />
      <el-tab-pane label="工作台" name="cockpit"><Cockpit :business="businessData" :opportunities="opportunities" :summary-people="people" :summary-relations="relations" :summary-followups="playbook?.followups || []" @opportunity="(item, battle) => { if (battle) { projectId = item.code; activeTab = 'battle' } else focusOpportunity(item) }" :organization-units="units" :manager-selection-region="managerSelectionRegion" :manager-selection-regions="managerSelectionRegions" @manager-region="setManagerSelectionRegion" :manager-options="managerOptions" :manager-id="reviewingManager" :manager-label="managerLabel" :can-review-managers="canReviewManagers" :can-export="canReviewManagers" @manager="setReviewingManager" v-if="cockpitData.overview && homeView === 'map' && activeTab === 'cockpit'" :mode="cockpitMode" :modes="cockpitModes" :overview="cockpitData.overview" :units="cockpitData.units" :people="cockpitData.people" :relations="cockpitData.relations" :playbook="cockpitData.playbook" :region="cockpitRegion" :regions="regionalSummary" :staff="staff" :responsibility="cockpitMode === 'manager' ? '本人负责客户' : cockpitMode === 'regional' ? `${cockpitRegion || '指定区域'}全部客户` : '全部已授权部门与区域'" @mode="setCockpitMode" @showcase="holographicOpen = true" @department="d => ourDepartment = d" @region="setCockpitRegion" :can-write="capabilities.write" @navigate="navigateCockpit" @create="openQuick" @refresh="loadAll" @select="onGraphSelect" @search="searchCockpit" @export="openExportDialog" ><template #business><BusinessAnalysis theme="dark" :data="businessData" :versions="businessVersions" :view-options="businessViewOptions" :selection="businessView" :loading="businessLoading" @view="changeBusinessView" :can-import="capabilities.write" @import="chooseBusinessFile" @download="downloadBusinessTemplate" @task-import="chooseTaskOrderFile" @task-download="downloadTaskOrderTemplate" @version="v => loadBusinessAnalysis(v)" /></template></Cockpit></el-tab-pane>
      <el-tab-pane label="经营分析" name="dashboard" lazy>
        <BusinessAnalysis v-if="activeTab === 'dashboard'" :data="businessData" :versions="businessVersions" :view-options="businessViewOptions" :selection="businessView" :loading="businessLoading" @view="changeBusinessView" :can-import="capabilities.write" @import="chooseBusinessFile" @download="downloadBusinessTemplate" @task-import="chooseTaskOrderFile" @task-download="downloadTaskOrderTemplate" @version="v => loadBusinessAnalysis(v)" />
      </el-tab-pane>
      <el-tab-pane label="五位一体" name="customers" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">五位一体</span>
          <h2>客户</h2>
          <p>档案 → 评估 → 维系 → 统筹 → 补齐，五位一体覆盖客户关系全生命周期；点选下方卡片进入对应工作台。</p>
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
            <el-radio-button value="overview">客户总览</el-radio-button>
            <el-radio-button value="contacts">联系人档案</el-radio-button>
            <el-radio-button value="organization">客户组织架构</el-radio-button>
          </el-radio-group>
          <div v-if="customerView === 'organization'" class="crm-organization-actions">
            <el-button v-if="canReviewManagers" :loading="organizationExporting" @click="runOrganizationExport">导出客户组织架构</el-button>
            <el-button @click="openOrganizationCanvas()">调整架构画布</el-button>
          </div>
        </div>
        <CustomerWorkspace v-if="customerView === 'overview'" :can-write="capabilities.write" @create-opportunity="createCustomerOpportunity" :units="units" :people="people" :relations="relations" :opportunities="opportunities" :followups="playbook?.followups || []" :can-record="!!capabilities.register_action" @person="id => onGraphSelect(id,'person')" @record="openAction" @opportunity="focusOpportunity" />
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
              <el-table-column label="组织归属" min-width="250" show-overflow-tooltip><template #default="{ row }"><span>{{ row.company_full_name || row.unit_name || unitName(row.unit_id) }}</span><div v-if="contactSubPath(row)" class="crm-relation-job">{{ contactSubPath(row) }}</div></template></el-table-column>
              <el-table-column label="联系方式" min-width="180"><template #default="{ row }"><span :class="{'crm-dim':!(row.mobile || row.office_phone || row.email || row.wechat)}">{{ row.mobile || row.office_phone || row.email || row.wechat || '待补全' }}</span></template></el-table-column>
              <el-table-column label="我方对接人" min-width="170" show-overflow-tooltip><template #default="{row}"><span :class="{'crm-dim':!contactMembers.get(row.id)}">{{ contactMembers.get(row.id) || '尚未建立关系' }}</span></template></el-table-column>
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
      <section v-if="customerRelationSection === 'maintenance'">
        <p class="crm-overview-purpose crm-overview-purpose--single">登记真实互动、跟进下一步、及时处理告警与单点风险；历史互动与未来计划分开记录。</p>
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
          <div class="crm-relation-meta"><strong>{{ visibleRelations.length }} 条关系</strong><span>本人负责的关系可登记与编辑；变更我方对接人请到「责任统筹」</span><el-tooltip :content="relationScopeLabel"><span class="crm-relation-scope" aria-label="关系维系可见范围">{{ relationScopeLabel }}</span></el-tooltip></div>
          <RelationshipLinks :relations="visibleRelations" :people="people" />
          <el-table class="crm-relations-table" :data="pagedRelations" row-key="id" empty-text="当前没有匹配关系">
            <el-table-column label="客户联系人" min-width="170"><template #default="{row}"><strong>{{ row.person_name }}</strong><el-tag v-if="row.single_point_risk" class="crm-single-point-tag" type="danger" size="small">单点风险</el-tag></template></el-table-column><el-table-column label="关系强度" width="120"><template #default="{row}"><el-tag>L{{ row.strength }} {{ row.strength_label }}</el-tag></template></el-table-column><el-table-column label="我方对接人" min-width="140"><template #default="{row}">{{ row.our_staff?.name || row.our_member_label || memberLabel(row.our_member) }}</template></el-table-column><el-table-column label="最近互动" width="125"><template #default="{row}">{{ row.last_touch || '尚未记录' }}</template></el-table-column><el-table-column label="维系状态" width="140"><template #default="{row}"><el-tag :type="decayType[row.decay_state]">{{ decayText[row.decay_state] }} · {{ row.days_since_touch === null ? '未触达' : row.days_since_touch + '天' }}</el-tag></template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click="openAction(row)" :disabled="!capabilities.register_action">登记动作</el-button><el-button link @click="openRelation(row)" :disabled="!canEditRelation(row)">编辑</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-if="visibleRelations.length > listPageSize" v-model:current-page="relationPage" :page-size="listPageSize" :total="visibleRelations.length" layout="prev, pager, next, total" class="crm-pagination" />
        </template>
        <section v-else class="crm-relation-followups"><header><div><h3>我的待办 <el-tag>{{ relationFollowups.length }}</el-tag></h3><p>来自联系人维系中登记的下一步事项，逾期优先。</p></div><el-button @click="relationView = 'relations'">去登记互动</el-button></header><el-empty v-if="!relationFollowups.length" description="暂无待办；登记动作时填写下一步事项和跟进日期" :image-size="64"/><el-table v-else :data="pagedRelationFollowups" class="crm-followup-table"><el-table-column label="待办事项" min-width="280"><template #default="{row}"><strong>{{ row.next_step || '跟进客户关系' }}</strong><small>{{ row.person_name }} · {{ row.project_id || '未关联项目' }}</small></template></el-table-column><el-table-column label="负责人" min-width="120"><template #default="{row}">{{ row.owner_label || memberLabel(row.owner) || '待指派' }}</template></el-table-column><el-table-column label="跟进日期" min-width="130"><template #default="{row}"><el-tag :type="row.overdue ? 'danger' : 'info'">{{ row.overdue ? '已逾期 · ' : '' }}{{ row.due_date || '未定日期' }}</el-tag></template></el-table-column><el-table-column label="操作" width="180" fixed="right"><template #default="{row}"><el-button link @click="showRelationForTask(row.relation_id)">查看关系</el-button><el-button link type="primary" :disabled="!capabilities.write || row.can_complete === false" :loading="saving" @click="safely(() => closeFollowup(row.id))">{{ row.can_complete === false ? '仅可查看' : '标记完成' }}</el-button></template></el-table-column></el-table><el-pagination v-if="relationFollowups.length > listPageSize" v-model:current-page="relationTaskPage" :page-size="listPageSize" :total="relationFollowups.length" layout="prev, pager, next, total" class="crm-pagination"/></section>
      </section>
      </el-tab-pane>
      <el-tab-pane label="商机管理" name="opportunities" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">商机管理</span>
          <h2>商机</h2>
          <p>集中维护项目机会、业主单位与阶段信息；从任一机会点一键进入项目作战地图，系统自动带出对应客户组织与关系资产。</p>
        </header>
        <OpportunityManagement :active="activeTab === 'opportunities'" :people="people" :focus="opportunityFocus" :followups="playbook?.followups || []" :units="units" :save-opportunity="saveOpportunity" :opportunities="opportunities" :contracts="salesContracts" :can-import="capabilities.import" :can-export="capabilities.read" :can-edit="capabilities.write" @import="chooseOpportunityFile" @contract-import="chooseSalesContractFile" @template="downloadOpportunityTemplate" @export="exportOpportunities" @refresh="loadAll" @battle="code => { projectId = code; activeTab = 'battle' }"/>
      </el-tab-pane>
      <el-tab-pane label="月度任务令作战地图" name="monthlyBattle" lazy><MonthlyBattle v-if="activeTab === 'monthlyBattle'" /></el-tab-pane>
      <el-tab-pane label="项目作战地图" name="battle" lazy>
        <header class="crm-relation-hero">
          <span class="crh-eyebrow">项目作战地图</span>
          <h2>重点项目监控 <el-button link type="primary" @click="activeTab = 'opportunities'">返回商机</el-button></h2>
          <p>把金额巨大的关键项目单独拎出来重点管控：展开任一项目，监控其六阶段时间管控、主要工作、证明材料、关系人与下一步。</p>
        </header>
        <section class="crm-key-projects" aria-label="重点项目监控">
          <header class="ckp-head">
            <div><h3>重点作战项目</h3><p>金额巨大的在谈关键商机单独聚焦监控；按可参与份额降序，展开任一项目即可重点管控。</p></div>
            <label class="ckp-threshold">可参与份额 ≥ <el-input-number v-model="keyProjectThreshold" :min="0" :step="500" :controls="false" style="width:96px" size="small" /> 万元<span class="ckp-count">共 {{ keyProjects.length }} 个</span></label>
          </header>
          <el-collapse v-if="monitorProjects.length" v-model="expandedKeyProjects" class="ckp-collapse">
            <el-collapse-item v-for="o in monitorProjects" :key="o.code" :name="o.code" :data-project-code="o.code" style="scroll-margin-top: 110px">
              <template #title>
                <div class="ckp-row">
                  <b class="ckp-amount">{{ Number(o.amount || 0).toLocaleString('zh-CN') }} 万</b>
                  <div class="ckp-row-main"><strong class="ckp-name">{{ o.name }}</strong><small class="ckp-owner">{{ o.owner_unit || '业主待补充' }}</small></div>
                  <span class="ckp-region">{{ o.region || '区域待补充' }}</span>
                  <span class="ckp-stage">{{ o.sales_stage || '阶段待确认' }}</span>
                  <span class="ckp-prog">阶段完成 {{ keyProjectStageProgress(o).done }}/6</span>
                </div>
              </template>
              <div class="ckp-monitor">
                <dl class="ckp-summary">
                  <div><dt>可参与份额</dt><dd>{{ o.amount ? Number(o.amount).toLocaleString('zh-CN') + ' 万元' : '待补充' }}</dd></div>
                  <div><dt>赢率</dt><dd>{{ o.win_rate || '待补充' }}</dd></div>
                  <div><dt>客户经理</dt><dd>{{ o.manager || '待指派' }}</dd></div>
                  <div><dt>成交结果</dt><dd>{{ o.cancelled ? '取消' : ({ open: '进行中', won: '赢单', lost: '输单', cancelled: '取消' }[o.outcome || 'open']) }}</dd></div>
                  <div><dt>预计招标</dt><dd>{{ o.bid_date || '待定' }}</dd></div>
                  <div><dt>预计签约</dt><dd>{{ o.contract_date || '待定' }}</dd></div>
                </dl>
                <div class="ckp-next">
                  <h4>下一步 · {{ keyProjectFollowups(o.code).length }}</h4>
                  <p v-if="!keyProjectFollowups(o.code).length" class="ckp-empty-note">暂无跟进计划；可在下方阶段进展或关系维系中登记。</p>
                  <ul v-else class="ckp-next-list"><li v-for="t in keyProjectFollowups(o.code).slice(0, 5)" :key="t.id"><strong>{{ t.next_step }}</strong><span>{{ t.person_name }} · {{ t.owner_label || t.owner || '负责人待补充' }} · {{ t.due_date || '日期待补充' }}</span><el-tag v-if="t.overdue" type="danger" size="small">逾期</el-tag></li></ul>
                </div>
                <h4 class="ckp-stage-title">阶段进展 · 时间管控 / 主要工作 / 证明材料 / 关系人</h4>
                <OpportunityStagePanel v-if="expandedKeyProjects.includes(o.code)" :key="o.code + ':' + o.version" :opportunity="o" :people="people" :can-edit="capabilities.write" @saved="loadAll" />
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-else :description="`暂无可参与份额 ≥ ${keyProjectThreshold} 万元的在谈商机，可下调阈值`" :image-size="60" />
        </section>
      </el-tab-pane>
      <el-tab-pane v-if="capabilities.read" label="设置" name="security" lazy>
        <CrmSettings v-if="activeTab==='security'" :relations="relations" :people="people" :units="units" :appoint="capabilities.appoint" :manage="capabilities.manage" :write="capabilities.write" @changed="loadAll"/>
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
      <OrganizationCanvas :initial-root-id="organizationCanvasRoot" :selected-id="organizationCanvasSelected" :units="organizationRegionUnits" :people="organizationRegionPeople" :read-only="!capabilities.write" @add-unit="quickAddCanvasUnit" @add-department-child="(id, department) => editCanvasDepartment(id, department, 'add')" @delete-department="(id, department) => editCanvasDepartment(id, department, 'delete')" @edit-unit="openUnit" @edit-person="openPerson" @move-unit="moveCanvasUnit" @move-person="moveCanvasPerson" @membership="changeCanvasMembership" @delete-unit="deleteCanvasUnit" />
    </el-dialog>

    <!-- 人物对话框 -->
    <el-dialog class="crm-editor-dialog crm-person-dialog" v-model="personDialog" :title="personForm.id ? '编辑人物' : '新增人物'" width="min(640px,94vw)">
      <el-form label-position="top"><el-row :gutter="14">
        <el-col :span="12"><el-form-item label="姓名"><el-input v-model="personForm.name" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="职位 / 职务"><el-input v-model="personForm.title" aria-label="职位 / 职务" placeholder="如：部门经理、通信专工" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="所属单位"><el-select v-model="personForm.unit_id" filterable style="width:100%" @change="personForm.department = ''"><el-option v-for="u in units" :key="u.id" :label="organizationUnitPath(u)" :value="u.id" /></el-select></el-form-item></el-col>
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
    <el-dialog class="crm-editor-dialog" v-model="actionDialog" :title="actionIsPlan ? '安排跟进' : '记录跟进'" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" width="min(560px,94vw)">
      <el-form label-position="top" :disabled="saving"><el-row :gutter="14">
        <el-col v-if="actionIsPlan" :span="24"><el-form-item label="对接关系"><el-select v-model="actionForm.relation_id" @change="(id: string) => actionForm.owner = planRelations.find(r => r.id === id)?.our_member || ''"><el-option v-for="r in planRelations" :key="r.id" :value="r.id" :label="`${r.person_name} · ${r.our_staff?.name || r.our_member_label || r.our_member || '未指派'}`" /></el-select></el-form-item></el-col>
        <el-col v-if="!actionIsPlan" :span="12"><el-form-item label="沟通方式"><el-select v-model="actionForm.type" style="width:100%"><el-option v-for="t in ['拜访', '电话', '需求澄清', '技术交流', '方案汇报', '联调协调', '验收移交', '回款跟进', '微信沟通']" :key="t" :label="t" :value="t" /></el-select></el-form-item></el-col>
        <el-col v-if="!actionIsPlan" :span="12"><el-form-item label="发生日期"><el-date-picker v-model="actionForm.happened_at" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        <el-col v-if="!actionIsPlan" :span="24"><el-form-item label="沟通结果"><el-input v-model="actionForm.intel" type="textarea" :rows="3" placeholder="沟通了什么，客户反馈如何？" /></el-form-item></el-col>
        <el-col :span="24"><el-form-item label="下一步事项"><el-input v-model="actionForm.next_step" placeholder="例如：确认信号系统接口清单并取得书面回复" /></el-form-item></el-col>
        <el-col v-if="actionIsPlan || actionForm.next_step" :span="12"><el-form-item label="负责人"><StaffPicker v-model="actionForm.owner" /></el-form-item></el-col>
        <el-col v-if="actionIsPlan || actionForm.next_step" :span="12"><el-form-item label="跟进日期"><el-date-picker v-model="actionForm.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        <el-col :span="24"><el-button link @click="actionAdvanced = !actionAdvanced">{{ actionAdvanced ? '收起补充信息' : '补充项目、成本等信息' }}</el-button></el-col>
        <template v-if="actionAdvanced"><el-col :span="24"><el-form-item label="项目编号"><el-input v-model="actionForm.project_id" :disabled="actionIsPlan" /></el-form-item></el-col><el-col v-if="!actionIsPlan" :span="12"><el-form-item label="关联决策节点"><el-select v-model="actionForm.decision_node" clearable><el-option v-for="n in decisionNodes" :key="n" :label="n" :value="n" /></el-select></el-form-item></el-col><el-col v-if="!actionIsPlan" :span="12"><el-form-item label="投入成本"><el-input v-model="actionForm.cost" /></el-form-item></el-col><el-col v-if="!actionIsPlan" :span="24"><el-checkbox v-model="actionForm.effective">有效沟通</el-checkbox><el-checkbox v-model="actionForm.bidirectional">客户主动</el-checkbox></el-col></template>
      </el-row></el-form>
      <template #footer><el-button :disabled="saving" @click="actionDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="safely(saveAction)">{{ actionIsPlan ? '加入待办' : '保存跟进' }}</el-button></template>
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
