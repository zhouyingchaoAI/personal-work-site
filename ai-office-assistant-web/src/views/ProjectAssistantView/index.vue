<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, FolderOpened, Plus, Upload, UserFilled } from '@element-plus/icons-vue'
import {
  createProject,
  deleteProject,
  getProjectAdmins,
  getProjectTimeline,
  listProjects,
  projectFileUrl,
  projectReportUrl,
  saveProjectAdmins,
  saveProjectMembers,
  updateProject,
  uploadProjectFile,
  type Project,
  type ProjectMember,
  type ProjectMemberRole,
  type ProjectTimelineItem,
} from '../../services/personalWorkApi'
import './index.scss'

const projects = ref<Project[]>([])
const selectedId = ref('')
const selectedProject = ref<Project | null>(null)
const timeline = ref<ProjectTimelineItem[]>([])
const canCreate = ref(false)
const canConfigureAdmins = ref(false)
const canManage = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const deleting = ref(false)
const createVisible = ref(false)
const manageVisible = ref(false)
const adminVisible = ref(false)
const projectForm = reactive({ name: '', description: '' })
const memberDraft = ref<ProjectMember[]>([])
const users = ref<{ username: string; name: string }[]>([])
const adminUsers = ref<string[]>([])
const uploadInput = ref<HTMLInputElement | null>(null)

const roleOptions: { label: string; value: ProjectMemberRole }[] = [
  { label: '项目管理员', value: 'manager' },
  { label: '回声', value: 'echo' },
  { label: '三角洲', value: 'delta' },
]

const selectedName = computed(() => selectedProject.value?.name || '未选择项目')

async function loadProjects(selectId = selectedId.value) {
  loading.value = true
  try {
    const result = await listProjects()
    projects.value = result.projects
    canCreate.value = result.can_create
    canConfigureAdmins.value = result.can_configure_admins
    const nextId = result.projects.some((item) => item.id === selectId) ? selectId : result.projects[0]?.id || ''
    selectedId.value = nextId
    if (nextId) await selectProject(nextId)
    else {
      selectedProject.value = null
      timeline.value = []
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '项目列表加载失败')
  } finally {
    loading.value = false
  }
}

async function selectProject(id: string) {
  selectedId.value = id
  if (!id) return
  detailLoading.value = true
  try {
    const result = await getProjectTimeline(id)
    selectedProject.value = result.project
    timeline.value = result.timeline
    canManage.value = result.can_manage
    users.value = result.users
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '项目详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

function openCreate() {
  projectForm.name = ''
  projectForm.description = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!projectForm.name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  try {
    const result = await createProject({ name: projectForm.name.trim(), description: projectForm.description.trim() })
    createVisible.value = false
    await loadProjects(result.project.id)
    ElMessage.success('项目已创建，可继续添加成员和资料')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建项目失败')
  }
}

function openManage() {
  if (!selectedProject.value) return
  projectForm.name = selectedProject.value.name
  projectForm.description = selectedProject.value.description
  memberDraft.value = selectedProject.value.members.map((item) => ({ ...item }))
  manageVisible.value = true
}

function addMember() {
  const candidate = users.value.find((item) => !memberDraft.value.some((member) => member.username === item.username))
  if (!candidate) {
    ElMessage.info('所有用户已添加到项目')
    return
  }
  memberDraft.value.push({ username: candidate.username, roles: ['echo'] })
}

function removeMember(index: number) {
  if (memberDraft.value[index]?.roles.includes('manager') && memberDraft.value.filter((item) => item.roles.includes('manager')).length === 1) {
    ElMessage.warning('项目至少保留一名项目管理员')
    return
  }
  memberDraft.value.splice(index, 1)
}

async function submitManage() {
  if (!selectedProject.value || !projectForm.name.trim()) return
  if (!memberDraft.value.some((item) => item.roles.includes('manager'))) {
    ElMessage.warning('请至少指定一名项目管理员')
    return
  }
  try {
    await updateProject({ id: selectedProject.value.id, name: projectForm.name.trim(), description: projectForm.description.trim() })
    await saveProjectMembers(selectedProject.value.id, memberDraft.value)
    manageVisible.value = false
    await loadProjects(selectedProject.value.id)
    ElMessage.success('项目配置已保存')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存项目配置失败')
  }
}

async function confirmDeleteProject() {
  const project = selectedProject.value
  if (!project || deleting.value) return
  try {
    const result = await ElMessageBox.prompt(
      `项目删除后无法恢复。项目内上传资料将被清理，成员日报、周报等个人资料仍会保留。请输入“${project.name}”确认删除。`,
      '删除项目',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
        inputPlaceholder: project.name,
        inputValidator: (value) => value === project.name || '请输入完整、准确的项目名称',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
    if (result.value !== project.name) return
    deleting.value = true
    await deleteProject(project.id)
    manageVisible.value = false
    await loadProjects('')
    ElMessage.success('项目已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error instanceof Error ? error.message : '删除项目失败')
  } finally {
    deleting.value = false
  }
}

function pickFile() {
  uploadInput.value?.click()
}

async function handleFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !selectedProject.value) return
  if (file.size > 30 * 1024 * 1024) {
    ElMessage.warning('项目资料不能超过 30MB')
    return
  }
  try {
    const raw = await file.arrayBuffer()
    const bytes = new Uint8Array(raw)
    let binary = ''
    bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
    await uploadProjectFile(selectedProject.value.id, file.name, btoa(binary))
    await selectProject(selectedProject.value.id)
    ElMessage.success('项目资料已上传')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传项目资料失败')
  } finally {
    ;(event.target as HTMLInputElement).value = ''
  }
}

async function openAdmins() {
  try {
    const result = await getProjectAdmins()
    users.value = result.users
    adminUsers.value = result.admins
    adminVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取项目管理员失败')
  }
}

async function submitAdmins() {
  try {
    await saveProjectAdmins(adminUsers.value)
    adminVisible.value = false
    await loadProjects()
    ElMessage.success('平台项目管理员已更新')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存项目管理员失败')
  }
}

function typeLabel(type: ProjectTimelineItem['type']) {
  return ({ daily: '日报', weekly: '周报', trip: '出差报告', material: '项目资料' })[type]
}

function formatTime(value: string) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

onMounted(() => { void loadProjects() })
</script>

<template>
  <section class="project-main">
    <header class="project-head">
      <div>
        <p class="project-eyebrow"><el-icon><FolderOpened /></el-icon> 项目协作</p>
        <h1>项目助手</h1>
        <span>统一沉淀项目成员、角色、资料及日报周报时间线。</span>
      </div>
      <div class="project-head-actions">
        <el-button v-if="canConfigureAdmins" @click="openAdmins">配置项目管理员</el-button>
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">创建项目</el-button>
      </div>
    </header>

    <section class="project-layout">
      <aside class="project-list-card">
        <header><strong>我的项目</strong><span>{{ projects.length }} 个</span></header>
        <button v-for="project in projects" :key="project.id" :class="['project-list-item', { active: project.id === selectedId }]" @click="selectProject(project.id)">
          <strong>{{ project.name }}</strong>
          <span>{{ project.members.length }} 位成员 · {{ project.status === 'active' ? '进行中' : '已归档' }}</span>
          <small>{{ project.description || '暂无项目描述' }}</small>
        </button>
        <div v-if="!loading && !projects.length" class="project-empty">暂无可访问项目<br><small>请联系项目管理员添加成员。</small></div>
      </aside>

      <main class="project-detail-card" v-loading="detailLoading">
        <template v-if="selectedProject">
          <header class="project-detail-head">
            <div>
              <p>项目概览</p>
              <h2>{{ selectedName }}</h2>
              <span>{{ selectedProject.description || '暂无项目描述' }}</span>
            </div>
            <div class="project-detail-actions">
              <input ref="uploadInput" type="file" hidden @change="handleFile" />
              <el-button v-if="canManage" :icon="Upload" @click="pickFile">上传项目资料</el-button>
              <el-button v-if="canManage" type="primary" :icon="UserFilled" @click="openManage">项目配置</el-button>
            </div>
          </header>

          <section class="project-members">
            <strong>项目成员</strong>
            <span v-for="member in selectedProject.members" :key="member.username" class="project-member-chip">{{ member.username }} · {{ member.role_name }}</span>
          </section>

          <section class="project-timeline">
            <header><div><h3>项目时间线</h3><span>日报、周报和项目资料按时间统一沉淀</span></div></header>
            <article v-for="item in timeline" :key="`${item.type}-${item.created_at}-${item.title}`" class="project-timeline-item">
              <span :class="['project-timeline-type', item.type]">{{ typeLabel(item.type) }}</span>
              <div>
                <strong>{{ item.title }}</strong>
                <p v-if="item.diary">{{ item.diary.today_work_preview || item.diary.today_work }}</p>
                <small>{{ item.author }} · {{ formatTime(item.created_at) }}</small>
              </div>
              <a v-if="item.file" :href="projectFileUrl(selectedProject.id, item.file.id)" target="_blank"><el-icon><Document /></el-icon> 查看资料</a>
              <a v-else-if="item.report" :href="projectReportUrl(selectedProject.id, item.report.id)" target="_blank"><el-icon><Document /></el-icon> 查看报告</a>
            </article>
            <div v-if="!timeline.length" class="project-empty">当前项目尚无关联日报、周报或资料。</div>
          </section>
        </template>
        <div v-else class="project-detail-empty"><el-icon><FolderOpened /></el-icon><strong>请选择一个项目</strong><span>选择左侧项目后查看成员、资料和项目工作时间线。</span></div>
      </main>
    </section>

    <el-dialog v-model="createVisible" title="创建项目" width="520px">
      <el-form label-position="top"><el-form-item label="项目名称"><el-input v-model="projectForm.name" maxlength="100" /></el-form-item><el-form-item label="项目描述"><el-input v-model="projectForm.description" type="textarea" :rows="5" maxlength="4000" /></el-form-item></el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" @click="submitCreate">创建并配置成员</el-button></template>
    </el-dialog>

    <el-dialog v-model="manageVisible" title="项目配置" width="min(920px, 94vw)">
      <el-form label-position="top"><el-form-item label="项目名称"><el-input v-model="projectForm.name" /></el-form-item><el-form-item label="项目描述"><el-input v-model="projectForm.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <div class="project-members-editor"><header><strong>项目成员与角色</strong><el-button link type="primary" @click="addMember">+ 添加成员</el-button></header><div v-for="(member, index) in memberDraft" :key="`${member.username}-${index}`" class="project-member-row"><el-select v-model="member.username" filterable><el-option v-for="user in users" :key="user.username" :label="`${user.name}（${user.username}）`" :value="user.username" /></el-select><el-select v-model="member.roles" class="project-member-role-select" multiple><el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" /></el-select><el-button link type="danger" @click="removeMember(index)">移除</el-button></div></div>
      <div class="project-danger-zone">
        <div><strong>删除项目</strong><span>清理项目及其上传资料，个人日报、周报仍会保留。</span></div>
        <el-button type="danger" plain :icon="Delete" :loading="deleting" @click="confirmDeleteProject">删除项目</el-button>
      </div>
      <template #footer><el-button @click="manageVisible = false">取消</el-button><el-button type="primary" @click="submitManage">保存项目配置</el-button></template>
    </el-dialog>

    <el-dialog v-model="adminVisible" title="平台项目管理员" width="520px">
      <p class="project-dialog-hint">项目管理员可创建项目；创建人自动成为该项目的项目管理员。</p>
      <el-select v-model="adminUsers" multiple filterable class="project-admin-select"><el-option v-for="user in users" :key="user.username" :label="`${user.name}（${user.username}）`" :value="user.username" /></el-select>
      <template #footer><el-button @click="adminVisible = false">取消</el-button><el-button type="primary" @click="submitAdmins">保存</el-button></template>
    </el-dialog>
  </section>
</template>
