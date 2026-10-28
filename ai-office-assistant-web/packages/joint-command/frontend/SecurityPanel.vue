<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmSecurityAppoint, crmSecurityUsers, crmSecurityGrant, crmSecurityBatchGrant, crmSaveLiaisonRegion, type CrmSecurityUser, type CrmRelation, type CrmPerson, type CrmUnit } from '../../../src/services/personalWorkApi'
import { LIAISON_REGION_ORDER, organizationLiaisonRegion, normalizeLiaisonRegion } from './liaisonRegions'
const props = defineProps<{ appoint: boolean; manage: boolean; relations?:CrmRelation[]; people?:CrmPerson[]; units?:CrmUnit[] }>()
const emit = defineEmits<{ changed: [] }>()
const users = ref<CrmSecurityUser[]>([])
const query = ref('')
const memberPage = ref(1)
const loading = ref(false)
const treeRef = ref<any>(null)

const scopeLabel = (value?: string) => ({self:'仅本人',team:'本人及下属',organization:'指定组织',regions:'指定区域',all:'全量'} as Record<string,string>)[value || ''] || ''

const roles = [
  { id:'disabled',label:'关闭访问',description:'不能进入联指经营助手' },
  { id:'viewer',label:'只读查看',description:'可查看客户、联系人、项目和看板，不能修改' },
  { id:'editor',label:'查看与编辑',description:'可维护客户、联系人、项目和跟进记录' },
  { id:'importer',label:'查看、编辑与批量导入',description:'在编辑基础上可导入客户经营表格' },
  { id:'regional_manager',label:'区域管理员',description:'管理指定区域，批量指派关系并配置维系监督' },
]
const batchRoles = computed(() => roles.filter(item => item.id !== 'regional_manager'))
const canManageGrants = computed(() => props.manage || props.appoint)

/* ---------- 组织架构树 ---------- */
type OrgNode = { key: string; type: 'root' | 'company' | 'dept' | 'liaisons'; label: string; company: string; deptPath: string; members?:string[]; virtualDept?: boolean; count: number; authorized: number; children?: OrgNode[] }
const isMember = (u: CrmSecurityUser) => !u.superadmin
const isAuthorized = (u: CrmSecurityUser) => !!u.capabilities.read
function matchNode(node: OrgNode, u: CrmSecurityUser): boolean {
  if (!isMember(u)) return false
  if (node.type === 'liaisons') return !!node.members?.includes(u.username)
  if (node.type === 'root') return true
  if ((u.company || '') !== node.company) return false
  if (node.type === 'company') return true
  const dept = u.department || ''
  if (node.virtualDept) return dept === ''
  return dept === node.deptPath || dept.startsWith(node.deptPath + ' / ')
}
function fillCounts(node: OrgNode, pool: CrmSecurityUser[]) {
  const scoped = pool.filter(u => matchNode(node, u))
  node.count = scoped.length
  node.authorized = scoped.filter(isAuthorized).length
  node.children?.forEach(child => fillCounts(child, pool))
}
const orgTree = computed<OrgNode[]>(() => {
  const pool = users.value.filter(isMember)
  const companyNames = [...new Set(pool.map(u => u.company || ''))]
    .sort((a, b) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b, 'zh')))
  const companies: OrgNode[] = []
  for (const company of companyNames) {
    const inCompany = pool.filter(u => (u.company || '') === company)
    const deptRoots: OrgNode[] = []
    const paths = [...new Set(inCompany.map(u => (u.department || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh'))
    for (const path of paths) {
      let siblings = deptRoots
      const parts = path.split(' / ').map(p => p.trim()).filter(Boolean)
      parts.forEach((label, index) => {
        const deptPath = parts.slice(0, index + 1).join(' / ')
        let node = siblings.find(item => item.deptPath === deptPath)
        if (!node) { node = { key: `d::${company}::${deptPath}`, type: 'dept', label, company, deptPath, count: 0, authorized: 0, children: [] }; siblings.push(node) }
        if (!node.children) node.children = []
        siblings = node.children
      })
    }
    const unregistered = inCompany.filter(u => !(u.department || '').trim())
    if (unregistered.length) deptRoots.push({ key: `d::${company}::__none__`, type: 'dept', label: '未登记部门', company, deptPath: '', virtualDept: true, count: 0, authorized: 0 })
    companies.push({ key: `c::${company}`, type: 'company', label: company || '未登记公司', company, deptPath: '', count: 0, authorized: 0, children: deptRoots.length ? deptRoots : undefined })
  }
  const liaisonRegion=new Map<string,string>()
  for(const relation of props.relations||[]){
    const key=relation.our_staff?.username||relation.our_member
    const matches=users.value.filter(u=>u.username===key||!!u.employee_id&&u.employee_id===key)
    if(matches.length!==1)continue
    const user=matches[0]!
    const manual=user.liaison_region_override==='非区域人员'?'非区域人员':normalizeLiaisonRegion(user.liaison_region_override)
    liaisonRegion.set(user.username,manual||organizationLiaisonRegion(user)||'非区域人员')
  }
  const assigned=new Map<string,Set<string>>()
  for(const [username,region] of liaisonRegion){const set=assigned.get(region)||new Set<string>();set.add(username);assigned.set(region,set)}
  const liaisonChildren=[...LIAISON_REGION_ORDER,'非区域人员'].map(region=>({key:`liaisons:${region}`,type:'liaisons' as const,label:region,company:'',deptPath:region,members:[...(assigned.get(region)||[])],count:0,authorized:0}))
  const liaison:OrgNode={key:'liaisons',type:'liaisons',label:'客户对接人',company:'',deptPath:'',members:[...new Set(liaisonChildren.flatMap(n=>n.members))],count:0,authorized:0,children:liaisonChildren}
  const root: OrgNode = { key: '__all__', type: 'root', label: '全部人员', company: '', deptPath: '', count: 0, authorized: 0, children: [liaison,...companies] }
  fillCounts(root, pool)
  return [root]
})
const selectedNode = ref<OrgNode | null>(null)
watch(orgTree, tree => {
  if (!tree.length) { selectedNode.value = null; return }
  const flat: OrgNode[] = []
  const walk = (node: OrgNode) => { flat.push(node); node.children?.forEach(walk) }
  tree.forEach(walk)
  const keep = selectedNode.value && flat.find(node => node.key === selectedNode.value!.key)
  const defaultNode = flat.find(node => node.key === 'liaisons') || tree[0]
  selectedNode.value = keep || defaultNode
  nextTick(() => treeRef.value?.setCurrentKey(selectedNode.value?.key))
}, { immediate: true })
function onNodeClick(node: OrgNode) { selectedNode.value = node; memberPage.value = 1 }
const memberSearchText = (user: CrmSecurityUser) => [user.name,user.username,user.employee_id,user.company,user.department,user.position].filter(Boolean).join(' ').toLowerCase()
const memberMatchesQuery = (user: CrmSecurityUser, value=query.value) => !value.trim() || memberSearchText(user).includes(value.trim().toLowerCase())
function filterTreeNode(value: string, data: OrgNode) {
  if (!value.trim()) return true
  const keyword=value.trim().toLowerCase()
  if (`${data.label} ${data.company} ${data.deptPath}`.toLowerCase().includes(keyword)) return true
  return users.value.some(user=>matchNode(data,user)&&memberMatchesQuery(user,value))
}
watch(query, value => {
  memberPage.value=1
  treeRef.value?.filter(value)
  const matches=users.value.filter(user=>isMember(user)&&memberMatchesQuery(user,value))
  if(!value.trim()||matches.length!==1)return
  const person=matches[0]!,flat:OrgNode[]=[]
  const walk=(node:OrgNode)=>{flat.push(node);node.children?.forEach(walk)}
  orgTree.value.forEach(walk)
  const target=flat.find(node=>node.type==='liaisons'&&!!node.deptPath&&matchNode(node,person))
    ||flat.filter(node=>node.type==='dept'&&matchNode(node,person)).sort((a,b)=>b.deptPath.length-a.deptPath.length)[0]
    ||flat.find(node=>node.type==='company'&&matchNode(node,person))
  if(target){selectedNode.value=target;nextTick(()=>treeRef.value?.setCurrentKey(target.key))}
})

/* ---------- 选中组织的成员 ---------- */
const showInactive = ref(true)
watch([selectedNode, showInactive], () => { memberPage.value = 1 })
const nodeMembers = computed(() => selectedNode.value ? users.value.filter(u => matchNode(selectedNode.value!, u) && (showInactive.value || isAuthorized(u))) : [])
const visibleMembers = computed(() => nodeMembers.value.filter(user=>memberMatchesQuery(user)))
const nodePath = computed(() => {
  const node = selectedNode.value
  if (!node) return '—'
  if (node.type === 'root') return '全部人员'
  if (node.type === 'liaisons') return '客户对接人'+(node.deptPath?' / '+node.deptPath:'')
  if (node.type === 'company') return node.label
  return `${node.company || '未登记公司'} › ${node.deptPath ? node.deptPath.replaceAll(' / ', ' › ') : node.label}`
})
const permissionText = (row: CrmSecurityUser) => row.superadmin ? '超级管理员（全量）' : row.capabilities.role === 'admin' ? '系统管理员（全量只读）' : row.capabilities.manage ? '客户经营管理员（全量）' : roles.find(r => r.id === row.capabilities.role)?.label || '关闭访问'
const automaticLiaisonRegion = (row: CrmSecurityUser) => organizationLiaisonRegion(row)||'非区域人员'
async function changeLiaisonRegion(row:CrmSecurityUser,region:string){
  loading.value=true
  try{await crmSaveLiaisonRegion({username:row.username,region});ElMessage.success(region?`已将${row.name}调整到${region}`:`${row.name}已恢复按组织架构自动归属`);await load();emit('changed')}
  catch(e){ElMessage.error(e instanceof Error?e.message:'人员区域调整失败')}
  finally{loading.value=false}
}

/* ---------- 批量授权（作用于当前组织节点及其下级） ---------- */
const batchRole = ref('viewer')
const batchScope = ref<'self' | 'team'>('self')
const batchRegisterAction = ref(false)
const batchExpires = ref('')
const batchTargets = computed(() => nodeMembers.value.filter(u => !u.superadmin && !u.capabilities.manage))
const batchable = computed(() => {
  const node = selectedNode.value
  if (!node || !canManageGrants.value) return false
  if (node.type === 'liaisons') return true
  if (node.type === 'root') return false
  if (!node.company) return false            // 未登记公司无法批量匹配
  if (node.type === 'dept' && node.virtualDept) return false  // 未登记部门无法批量匹配
  return true
})
const batchReason = computed(() => {
  const node = selectedNode.value
  if (!node || node.type === 'root') return '请选择具体公司或部门后批量授权'
  if (!node.company) return '未登记公司的人员需逐人授权'
  if (node.type === 'dept' && node.virtualDept) return '未登记部门的人员需逐人授权'
  return ''
})
async function batchSave() {
  const node = selectedNode.value
  if (!node || !batchable.value) return
  if (!batchTargets.value.length) return ElMessage.warning('该组织内没有可批量配置的普通人员')
  const departments = node.type === 'dept' ? [node.deptPath] : []
  const roleLabel = roles.find(item => item.id === batchRole.value)?.label
  try {
    await ElMessageBox.confirm(`将为「${nodePath.value}」及其下级组织的 ${batchTargets.value.length} 位普通人员设置“${roleLabel} · ${scopeLabel(batchScope.value)}”。客户经营管理员与超级管理员不受影响。`, '确认批量授权', { type: 'warning' })
    loading.value = true
    if(node.type==='liaisons'){
      const targets=[...batchTargets.value], failed:string[]=[]
      for(const user of targets){try{await crmSecurityGrant({username:user.username,role:batchRole.value,register_action:batchRegisterAction.value,data_scope:batchScope.value,expires_on:batchExpires.value||''})}catch{failed.push(user.name||user.username)}}
      if(failed.length)ElMessage.warning(`已更新 ${targets.length-failed.length} 人；失败：${failed.join('、')}`)
      else ElMessage.success(`已更新 ${targets.length} 位对接人员的权限`)
      await load();emit('changed');return
    }
    const result = await crmSecurityBatchGrant({ company: node.company, departments, role: batchRole.value, register_action: batchRegisterAction.value, data_scope: batchScope.value, expires_on: batchExpires.value || '' })
    ElMessage.success(`已更新 ${result.updated} 位人员的客户经营权限`)
    await load(); emit('changed')
  } catch (e) { if (e !== 'cancel' && e !== 'close') ElMessage.error(e instanceof Error ? e.message : '保存失败') } finally { loading.value = false }
}

/* ---------- 单人授权对话框 ---------- */
const grantDialogOpen = ref(false)
const selected = ref('')
const role = ref('viewer')
const registerAction = ref(false)
const expires = ref('')
const grantRegions = ref<string[]>([])
const dataScope = ref<'self' | 'team' | 'organization' | 'regions' | 'all'>('self')
const scopeCompany = ref('')
const scopeDepartments = ref<string[]>([])
const companies = computed(() => [...new Set(users.value.map(user => user.company || '').filter(Boolean))].sort())
const scopeDepartmentOptions = computed(() => [...new Set(users.value.filter(user => user.company === scopeCompany.value).map(user => user.department || '').filter(Boolean))].sort())
const grantCandidates = computed(() => users.value.filter(user => !user.superadmin && !user.capabilities.manage))
const selectedUser = computed(() => users.value.find(user => user.username === selected.value))
watch(role, value => { if (value === 'regional_manager') dataScope.value = 'regions' })
function openAddGrant() {
  const node = selectedNode.value
  selected.value = ''; role.value = 'viewer'; expires.value = ''; grantRegions.value = []
  dataScope.value = 'self'; scopeDepartments.value = []; registerAction.value = false
  scopeCompany.value = node && node.type !== 'root' ? node.company : ''
  grantDialogOpen.value = true
}
function edit(user: CrmSecurityUser) {
  selected.value = user.username; role.value = user.grant?.role || user.capabilities.role; expires.value = user.grant?.expires_on || ''
  grantRegions.value = [...(user.grant?.regions || [])]
  dataScope.value = user.grant?.data_scope || (grantRegions.value.length ? 'regions' : 'self')
  scopeCompany.value = user.grant?.scope_company || user.company || ''
  scopeDepartments.value = [...(user.grant?.scope_departments || [])]
  registerAction.value = !!user.capabilities.register_action
  grantDialogOpen.value = true
}
function closeGrantDialog() { grantDialogOpen.value = false; selected.value = ''; grantRegions.value = []; scopeDepartments.value = [] }
async function save() {
  if (!selected.value) return ElMessage.warning('请先选择需要授权的人员')
  if (dataScope.value === 'organization' && !scopeCompany.value) return ElMessage.warning('请先选择组织范围所属公司')
  if (dataScope.value === 'regions' && !grantRegions.value.length) return ElMessage.warning('请至少选择一个经营区域')
  loading.value = true
  try {
    await crmSecurityGrant({ username: selected.value, role: role.value, register_action: registerAction.value, expires_on: expires.value || '', data_scope: dataScope.value, scope_company: scopeCompany.value, scope_departments: scopeDepartments.value, regions: grantRegions.value })
    ElMessage.success('客户经营权限已生效'); closeGrantDialog(); await load(); emit('changed')
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '保存失败') } finally { loading.value = false }
}
async function appointUser(user: CrmSecurityUser) {
  loading.value = true
  try { await crmSecurityAppoint(user.username, !user.grant?.manager); ElMessage.success('客户经营管理员任命已更新'); await load(); emit('changed') }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '更新失败') } finally { loading.value = false }
}

async function load() {
  loading.value = true
  try { const u = await crmSecurityUsers(); users.value = u.users }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '加载失败') } finally { loading.value = false }
}
onMounted(load)
</script>
<template>
  <section v-loading="loading" class="crm-security">
    <p class="sec-howto"><b>操作方式</b>左侧选择公司 / 部门 / 对接区域节点，右侧查看该组织成员并配置权限；授权只控制可见范围，不改变原始客户数据归属。</p>

      <div class="permission-legend">
        <span class="legend-title">功能权限速览</span>
        <span v-for="item in roles" :key="item.id"><b>{{ item.label }}</b><i>{{ item.description }}</i></span>
      </div>
      <div class="org-console">
        <!-- 左：组织架构树 -->
        <aside class="org-tree-pane">
          <div class="pane-head"><strong>公司组织架构</strong><el-button link @click="load">刷新</el-button></div>
          <el-input v-model="query" clearable size="small" placeholder="搜索组织 / 姓名 / 账号 / 工号 / 岗位" aria-label="搜索组织或人员" />
          <el-tree ref="treeRef" class="org-tree" :data="orgTree" node-key="key" highlight-current :expand-on-click-node="false" :default-expand-level="2" default-expand-all :filter-node-method="filterTreeNode" :props="{ label: 'label', children: 'children' }" @node-click="onNodeClick">
            <template #default="{ data }">
              <span class="org-node">
                <span class="org-node-label">{{ data.label }}</span>
                <span class="org-node-badge" :class="{ zero: !data.count }">{{ data.authorized }}/{{ data.count }}</span>
              </span>
            </template>
          </el-tree>
          <p class="tree-hint">徽标为「已开通 / 总人数」，部门统计含其下级组织。</p>
        </aside>

        <!-- 右：成员与权限 -->
        <div class="org-detail-pane">
          <div class="detail-head">
            <div><span class="detail-crumb">当前组织</span><strong>{{ nodePath }}</strong></div>
            <div class="detail-stats">
              <span>总人数<b>{{ selectedNode?.count ?? 0 }}</b></span>
              <span>已开通<b class="ok">{{ selectedNode?.authorized ?? 0 }}</b></span>
              <span>未开通<b class="off">{{ (selectedNode?.count ?? 0) - (selectedNode?.authorized ?? 0) }}</b></span>
            </div>
          </div>

          <!-- 批量授权作用于当前组织节点 -->
          <div v-if="canManageGrants" class="batch-card">
            <div class="batch-card-head"><strong>批量授权本组织</strong><el-tag type="info" effect="plain" size="small">管理员与超级管理员不受影响</el-tag></div>
            <template v-if="batchable">
              <div class="batch-fields">
                <div class="field-group"><label>功能权限</label><el-select v-model="batchRole" size="small"><el-option v-for="item in batchRoles" :key="item.id" :label="item.label" :value="item.id"><div class="role-option"><strong>{{ item.label }}</strong><span>{{ item.description }}</span></div></el-option></el-select></div>
                <div class="field-group"><label>数据范围</label><el-select v-model="batchScope" size="small"><el-option label="仅本人：本人负责的关系" value="self" /><el-option label="本人及下属组织：按组织树含下级" value="team" /></el-select></div>
                <div class="field-group action-permission"><label>动作权限</label><el-switch v-model="batchRegisterAction" active-text="允许登记动作" /></div>
                <div class="field-group"><label>到期日 <small>选填</small></label><el-date-picker v-model="batchExpires" size="small" type="date" value-format="YYYY-MM-DD" clearable placeholder="长期有效" /></div>
                <div class="batch-apply"><span class="apply-count">影响 <b>{{ batchTargets.length }}</b> 人</span><el-button type="primary" size="small" :disabled="!batchTargets.length" @click="batchSave">应用到本组织</el-button></div>
              </div>
              <p class="batch-note">作用于「{{ nodePath }}」及其全部下级组织的普通人员；如需区域汇总 / 指定组织 / 全量等岗位数据范围，请对个人使用“设置权限”。</p>
            </template>
            <p v-else class="batch-disabled">{{ batchReason }}，可对下方成员逐人“设置权限”。</p>
          </div>

          <div class="member-toolbar">
            <el-switch v-model="showInactive" active-text="含未开通人员" />
            <el-button v-if="canManageGrants" type="primary" size="small" @click="openAddGrant">＋ 为个人授权</el-button>
          </div>

          <el-table :data="visibleMembers.slice((memberPage-1)*8, memberPage*8)" max-height="420" size="small" empty-text="当前范围未找到匹配人员">
            <el-table-column prop="name" label="姓名" min-width="96" />
            <el-table-column prop="username" label="账号" min-width="120" />
            <el-table-column label="组织信息" min-width="200"><template #default="{ row }"><div class="person-org"><span>{{ row.department || '未登记部门' }}<template v-if="row.position"> · {{ row.position }}</template></span><em v-if="row.employee_id">工号：{{ row.employee_id }}</em></div></template></el-table-column>
            <el-table-column label="当前权限" min-width="230"><template #default="{ row }"><span :class="{ 'perm-off': !row.capabilities.read }">{{ permissionText(row) }}</span><small v-if="row.grant?.data_scope"> · {{ scopeLabel(row.grant.data_scope) }}</small><small v-if="row.grant?.regions?.length">：{{ row.grant.regions.join('、') }}</small><el-tag v-if="row.capabilities.register_action" type="success" size="small">可登记动作</el-tag><el-tag v-if="row.capabilities.expired" type="warning" size="small">已到期</el-tag></template></el-table-column>
            <el-table-column label="到期日" width="112"><template #default="{ row }">{{ row.grant?.expires_on || '长期' }}</template></el-table-column>
            <el-table-column v-if="selectedNode?.type==='liaisons'" label="人员区域" width="165"><template #default="{ row }"><el-select :model-value="row.liaison_region_override||''" size="small" aria-label="调整人员区域" @change="(value:string)=>changeLiaisonRegion(row,value)"><el-option :label="`自动：${automaticLiaisonRegion(row)}`" value=""/><el-option v-for="area in [...LIAISON_REGION_ORDER,'非区域人员']" :key="area" :label="area" :value="area"/></el-select></template></el-table-column>
            <el-table-column label="操作" min-width="180"><template #default="{ row }"><el-button v-if="canManageGrants && !row.superadmin && !row.grant?.manager" link type="primary" @click="edit(row)">设置权限</el-button><el-button v-if="appoint && !row.superadmin" link :type="row.grant?.manager ? 'danger' : 'primary'" @click="appointUser(row)">{{ row.grant?.manager ? '撤销管理员' : '设为经营管理员' }}</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-if="visibleMembers.length > 8" v-model:current-page="memberPage" :page-size="8" :total="visibleMembers.length" layout="prev, pager, next, total" size="small" />
        </div>
      </div>

    <el-dialog :model-value="grantDialogOpen" @close="closeGrantDialog" title="设置个人客户经营权限" width="min(560px,94vw)" :close-on-click-modal="false">
      <p class="grant-dialog-note">功能权限和数据范围分开配置。数据范围只控制“能看见谁的数据”，不改变原始客户资料归属。</p>
      <el-form label-position="top">
        <el-form-item label="授权人员" required><el-select v-model="selected" filterable placeholder="搜索姓名、工号、部门或账号" style="width:100%"><el-option v-for="user in grantCandidates" :key="user.username" :label="`${user.name} · ${user.username}`" :value="user.username" /></el-select></el-form-item>
        <div v-if="selectedUser" class="selected-user"><strong>{{ selectedUser.name }} · {{ selectedUser.username }}</strong><span>{{ selectedUser.company || '未登记公司' }} / {{ selectedUser.department || '未登记部门' }}</span></div>
        <el-form-item label="功能权限"><el-select v-model="role" style="width:100%" @change="registerAction=['editor','importer','regional_manager'].includes(role)"><el-option v-for="r in roles" :key="r.id" :label="r.label" :value="r.id" /></el-select></el-form-item>
        <el-form-item label="登记动作权限"><el-switch v-model="registerAction" active-text="允许在可见客情关系中登记互动与维系动作" /></el-form-item>
        <el-form-item label="数据可见范围"><el-select v-model="dataScope" style="width:100%" :disabled="role==='regional_manager'"><el-option label="仅本人：只看自己上传的客户关系" value="self" /><el-option label="本人及下属组织：按组织树自动包含下级" value="team" /><el-option label="指定组织：选择公司及部门，可包含下级" value="organization" /><el-option label="指定区域：汇总所选经营区域数据" value="regions" /><el-option label="全部数据：仅适用于受控管理岗位" value="all" /></el-select></el-form-item>
        <template v-if="dataScope === 'organization'"><el-form-item label="所属公司" required><el-select v-model="scopeCompany" filterable placeholder="选择公司" style="width:100%" @change="scopeDepartments=[]"><el-option v-for="company in companies" :key="company" :label="company" :value="company" /></el-select></el-form-item><el-form-item label="部门范围（留空即全公司）"><el-select v-model="scopeDepartments" multiple filterable collapse-tags placeholder="选择部门，自动包含其下级" style="width:100%"><el-option v-for="department in scopeDepartmentOptions" :key="department" :label="department" :value="department" /></el-select></el-form-item></template>
        <el-form-item v-if="dataScope === 'regions'" label="可查看的区域" required><el-checkbox-group v-model="grantRegions"><el-checkbox v-for="area in ['东区','西区','中区','广东区']" :key="area" :label="area">{{ area }}</el-checkbox></el-checkbox-group></el-form-item>
        <el-form-item label="授权到期日（选填，当日仍有效）"><el-date-picker v-model="expires" type="date" value-format="YYYY-MM-DD" clearable placeholder="长期有效" /></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="loading" @click="closeGrantDialog">取消</el-button><el-button type="primary" :disabled="!selected" :loading="loading" @click="save">确认授权</el-button></template>
    </el-dialog>
  </section>
</template>
<style scoped>
.crm-security{display:grid;gap:14px}
.crm-subnav{margin-top:2px}
.sec-howto{display:flex;align-items:baseline;gap:10px;margin:0;padding:11px 14px;border:1px solid #e4ecf6;border-radius:11px;background:linear-gradient(135deg,#fbfdff,#f4f8ff);font-size:12.5px;line-height:1.6;color:#5a7189}
.sec-howto b{flex:0 0 auto;font-size:12px;font-weight:700;color:#15499c}
.permission-legend{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px}
.permission-legend .legend-title{display:flex;align-items:center;font-size:12px;font-weight:700;color:#15499c;padding:0 4px}
.permission-legend>span:not(.legend-title){display:grid;gap:3px;min-width:172px;flex:1;padding:9px 12px;border:1px solid #e4ecf6;border-radius:10px;background:#fff;transition:border-color .2s,box-shadow .2s}
.permission-legend>span:not(.legend-title):hover{border-color:#b7d0f2;box-shadow:0 8px 20px -16px rgba(21,73,156,.5)}
.permission-legend b{font-size:12.5px;color:#1f3350;font-weight:600}
.permission-legend i{font-size:11px;font-style:normal;color:#71839c;line-height:1.5}
.org-console{display:grid;grid-template-columns:288px 1fr;gap:14px;align-items:start}
.org-tree-pane{display:grid;gap:8px;padding:12px;border:1px solid #dce6f2;border-radius:10px;background:#fafcff;position:sticky;top:8px}
.pane-head{display:flex;align-items:center;justify-content:space-between}
.pane-head strong{font-size:13px;color:#1c4b87}
.org-tree{max-height:520px;overflow:auto;background:transparent;--el-tree-node-hover-bg-color:#eef5ff}
.org-tree :deep(.el-tree-node__content){height:30px}
.org-node{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;padding-right:6px}
.org-node-label{font-size:13px;color:#31517d;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.org-node-badge{flex:none;font-size:11px;color:#2a62b5;background:#e6f0ff;border-radius:10px;padding:0 7px;line-height:17px}
.org-node-badge.zero{color:#9aa7b8;background:#eef1f5}
.tree-hint{margin:0;font-size:11px;color:#8595a8}
.org-detail-pane{display:grid;gap:12px;min-width:0}
.detail-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:12px 14px;border:1px solid #dce6f2;border-radius:10px;background:linear-gradient(135deg,#f7fbff,#fff)}
.detail-crumb{display:block;font-size:11px;color:#6b7f99}
.detail-head strong{font-size:15px;color:#1c4b87}
.detail-stats{display:flex;gap:16px}
.detail-stats span{display:grid;font-size:11px;color:#6b7f99}
.detail-stats b{font-size:17px;color:#244b7e}
.detail-stats b.ok{color:#1558ac}
.detail-stats b.off{color:#c67714}
.batch-card{display:grid;gap:10px;padding:12px 14px;border:1px solid #b8d1f2;border-radius:10px;background:#f7fbff}
.batch-card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.batch-card-head strong{font-size:13px;color:#1c4b87}
.batch-fields{display:flex;gap:10px;align-items:end;flex-wrap:wrap}
.field-group{display:grid;gap:4px;min-width:190px;flex:1}
.field-group label{font-size:12px;font-weight:600;color:#415b7d}
.field-group small{font-size:11px;font-weight:400;color:#71839c}
.field-group :deep(.el-select),.field-group :deep(.el-date-editor){width:100%}
.batch-apply{display:flex;align-items:center;gap:10px}
.apply-count{font-size:12px;color:#527099}
.apply-count b{font-size:15px;color:#1558ac}
.batch-note{margin:0;font-size:11px;color:#71839c}
.batch-disabled{margin:0;font-size:12px;color:#a06316}
.role-option{display:grid;gap:2px;padding:3px 0}
.role-option strong{font-size:13px}
.role-option span{font-size:11px;color:#71839c}
.member-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.person-org{display:grid;gap:1px}
.person-org span,.person-org em{font-size:12px;color:#657991;font-style:normal}
.perm-off{color:#9aa7b8}
h3{margin-top:8px}
p{font-size:13px;color:#657991}
.grant-dialog-note{margin:0 0 14px}
.selected-user{display:grid;gap:3px;margin:-4px 0 14px;padding:10px 12px;border-radius:7px;background:#f3f8ff}
.selected-user strong{font-size:13px;color:#244b7e}
.selected-user span{font-size:12px;color:#657991}
@media (max-width:900px){.org-console{grid-template-columns:1fr}.org-tree-pane{position:static}.org-tree{max-height:280px}.field-group{min-width:100%}}
</style>
