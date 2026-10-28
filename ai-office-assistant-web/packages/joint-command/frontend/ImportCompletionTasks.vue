<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  crmCompleteImportCompletionTask,
  crmExportImportCompletion,
  crmImportCompletionExcel,
  crmImportCompletionTasks,
  type CrmImportCompletionTask,
} from '../../../src/services/personalWorkApi'

const props = defineProps<{ canManage: boolean }>()
const emit = defineEmits<{ completed: [] }>()

const loading = ref(false)
const saving = ref(false)
const canManageTasks = ref(false)
const tasks = ref<CrmImportCompletionTask[]>([])
const current = ref<CrmImportCompletionTask | null>(null)
const dialogOpen = ref(false)
const form = reactive({ 公司全称: '', 姓名: '', 单位类型: '', target_username: '' })
const unitTypes = ['主管单位', '业主单位', '总包单位', '设计单位', '厂商']

const pendingTasks = computed(() => tasks.value.filter(task => task.status === 'pending'))
const selectedRegion = ref('')
const page = ref(1)
const pageSize = 50
const exporting = ref(false)
const uploading = ref(false)
const completionFile = ref<HTMLInputElement | null>(null)
const exportManager = ref('')
const isManager = computed(() => canManageTasks.value || props.canManage)
const regionNames = ['东区', '中区', '西区', '广东区', '未分区']
function taskRegion(task: CrmImportCompletionTask) { return taskValue(task, '区域') || taskValue(task, '经营区域') || '未分区' }
const regionCounts = computed(() => {
  const counts = new Map(regionNames.map(name => [name, 0]))
  for (const task of pendingTasks.value) {
    const name = taskRegion(task)
    counts.set(name, (counts.get(name) || 0) + 1)
  }
  return [...counts].map(([name, count]) => ({ name, count }))
})
const filteredTasks = computed(() => pendingTasks.value.filter(task => !isManager.value || !selectedRegion.value || taskRegion(task) === selectedRegion.value))
const managerOptions = computed(() => [...new Map(pendingTasks.value
  .filter(task => task.assignee_username)
  .map(task => [task.assignee_username, task.assignee_name || task.assignee_username])).entries()]
  .map(([username, name]) => ({ username, name })))
const pageTasks = computed(() => filteredTasks.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch(selectedRegion, () => { page.value = 1 })
watch(() => filteredTasks.value.length, count => { page.value = Math.min(page.value, Math.max(1, Math.ceil(count / pageSize))) })
const scopeLabel = computed(() => canManageTasks.value || props.canManage ? '管理员可查看全部待补充记录，并代为补充或指定接收人员。' : '这里只显示分派给你的待补充记录；补齐关键项后才会并入你的客户资料。')
const sourceFields = [
  '区域', '公司全称', '单位*', '部门', '职务', '姓名*', '手机', '办公电话', '邮箱', '微信 / 其他联系',
  '重要程度', '支持程度', '跟进轨迹', '上次互动时间', '本周互动计划', '计划跟进日期', '单位类型', '省份', '城市', '维系周期（天）', '我方姓名',
]

function asText(values: Record<string, string>, key: string) {
  return String(values[key] || '').trim()
}

function taskValue(task: CrmImportCompletionTask, key: string) {
  return asText(task.original_values, key) || asText(task.values, key)
}

function taskSourceEntries(task?: CrmImportCompletionTask | null) {
  if (!task) return []
  const fields = taskValue(task, '子公司全称') ? [...sourceFields.slice(0, 2), '子公司全称', ...sourceFields.slice(2)] : sourceFields
  return fields
    .map(label => ({ label, value: taskValue(task, label) }))
    .filter(entry => entry.value)
}

function taskPreview(task: CrmImportCompletionTask) {
  return taskSourceEntries(task)
    .filter(entry => !['公司全称', '姓名*', '单位类型'].includes(entry.label))
    .slice(0, 4)
}

async function load() {
  loading.value = true
  try {
    const result = await crmImportCompletionTasks()
    tasks.value = result.tasks || []
    canManageTasks.value = result.can_manage
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '待补充资料加载失败')
  } finally {
    loading.value = false
  }
}

function openTask(task: CrmImportCompletionTask) {
  current.value = task
  form.公司全称 = asText(task.original_values, '公司全称') || asText(task.values, '公司全称')
  form.姓名 = asText(task.values, '姓名*') || asText(task.original_values, '姓名*')
  form.单位类型 = asText(task.values, '单位类型') || asText(task.original_values, '单位类型')
  form.target_username = task.assignee_username || ''
  dialogOpen.value = true
}

async function submit() {
  if (!current.value) return
  if (!form.公司全称.trim() || !form.姓名.trim() || !form.单位类型) {
    ElMessage.warning('请补齐公司全称、姓名和单位类型')
    return
  }
  if (!current.value.assignee_username && !form.target_username.trim()) {
    ElMessage.warning('该记录尚未匹配到接收人员，请填写接收人员账号')
    return
  }
  saving.value = true
  try {
    await crmCompleteImportCompletionTask({
      id: current.value.id,
      target_username: form.target_username.trim() || undefined,
      values: { 公司全称: form.公司全称.trim(), '姓名*': form.姓名.trim(), 单位类型: form.单位类型 },
    })
    ElMessage.success('关键资料已补齐，记录已并入客户资料')
    dialogOpen.value = false
    await load()
    emit('completed')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '资料补充失败')
  } finally {
    saving.value = false
  }
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = name; document.body.appendChild(link); link.click()
  link.remove(); URL.revokeObjectURL(url)
}

async function exportTasks() {
  exporting.value = true
  try {
    const { blob, name } = await crmExportImportCompletion(selectedRegion.value, exportManager.value)
    download(blob, name)
    ElMessage.success('资料补充表已导出')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

async function uploadCompletion(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.xlsx')) { ElMessage.warning('请选择导出的 .xlsx 补充表'); return }
  uploading.value = true
  try {
    const result = await crmImportCompletionExcel(file)
    if (result.errors.length) ElMessage.warning(`已补全 ${result.completed} 条；${result.errors.length} 条仍待修正`)
    else ElMessage.success(`已补全 ${result.completed} 条，待补充列表已更新`)
    await load()
    emit('completed')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传补充表失败')
  } finally {
    uploading.value = false
    if (completionFile.value) completionFile.value.value = ''
  }
}

onMounted(load)
</script>

<template>
  <section class="crm-completion-tasks" v-loading="loading">
    <header class="crm-completion-tasks__header">
      <div>
        <h3>待补充资料</h3>
        <p>Excel 中公司全称、姓名*、单位类型缺任一项的行，不会直接写入客户库。</p>
        <small>{{ scopeLabel }}</small>
      </div>
      <div class="crm-completion-tasks__actions">
        <el-select v-if="isManager" v-model="exportManager" clearable filterable placeholder="全部客户经理" style="width:160px"><el-option v-for="manager in managerOptions" :key="manager.username" :label="manager.name" :value="manager.username" /></el-select>
        <el-button :loading="exporting" :disabled="!pendingTasks.length" @click="exportTasks">导出补充表</el-button>
        <input ref="completionFile" type="file" accept=".xlsx" class="crm-completion-file-input" @change="uploadCompletion" />
        <el-button :loading="uploading" @click="completionFile?.click()">上传补全表</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </header>

    <div v-if="isManager" class="crm-completion-regions" role="group" aria-label="按区域查看待补充资料">
      <button :class="{ selected: !selectedRegion }" :aria-pressed="!selectedRegion" @click="selectedRegion = ''"><span>全部区域</span><b>{{ pendingTasks.length }}</b></button>
      <button v-for="area in regionCounts" :key="area.name" :class="{ selected: selectedRegion === area.name }" :aria-pressed="selectedRegion === area.name" @click="selectedRegion = area.name"><span>{{ area.name }}</span><b>{{ area.count }}</b></button>
    </div>
    <p v-if="isManager" class="crm-completion-region-note">{{ selectedRegion || '全部区域' }}：{{ filteredTasks.length }} 条待补充。导出时可同时按当前区域与客户经理筛选；上传后会按任务编号自动回写并移除已补全记录。</p>
    <el-alert v-if="pendingTasks.length" :closable="false" type="warning" :title="`当前有 ${pendingTasks.length} 条资料待补充`" description="补齐三个关键项后，系统才会将该联系人及其已填写资料并入目标账号的客户库。" />
    <el-empty v-if="!filteredTasks.length" :description="pendingTasks.length ? '该区域暂无待补充资料' : '暂无待补充资料'" :image-size="76" />
    <el-table v-if="filteredTasks.length" :data="pageTasks" max-height="560" class="crm-completion-tasks__table">
      <el-table-column v-if="isManager" label="区域" width="90"><template #default="{ row }">{{ taskRegion(row) }}</template></el-table-column>
      <el-table-column label="联系人 / 公司" min-width="220">
        <template #default="{ row }"><b>{{ row.values['姓名*'] || '待补姓名' }}</b><small>{{ row.values['公司全称'] || row.original_values['公司全称'] || '待补公司全称' }}</small></template>
      </el-table-column>
      <el-table-column label="待补关键项" min-width="160"><template #default="{ row }"><el-tag v-for="field in row.missing_fields" :key="field" size="small" type="warning" effect="plain">{{ field }}</el-tag></template></el-table-column>
      <el-table-column label="已填资料" min-width="290">
        <template #default="{ row }">
          <div v-if="taskPreview(row).length" class="crm-completion-tasks__preview">
            <span v-for="entry in taskPreview(row)" :key="entry.label"><b>{{ entry.label }}</b> {{ entry.value }}</span>
          </div>
          <small v-else>该行暂未填写其他可用资料</small>
        </template>
      </el-table-column>
      <el-table-column label="接收人" min-width="150"><template #default="{ row }"><span>{{ row.assignee_name || '未匹配我方姓名' }}</span><small>{{ row.assignee_name ? '已关联平台人员' : '需管理员指定接收人员' }}</small></template></el-table-column>
      <el-table-column v-if="canManageTasks || canManage" label="上传人" min-width="120"><template #default="{ row }">{{ row.uploader_name || row.uploader_username || '未知' }}</template></el-table-column>
      <el-table-column label="来源" width="110"><template #default="{ row }">第 {{ row.source_row }} 行</template></el-table-column>
      <el-table-column label="操作" width="110" fixed="right"><template #default="{ row }"><el-button type="primary" link @click="openTask(row)">补充资料</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-if="filteredTasks.length > pageSize" v-model:current-page="page" :page-size="pageSize" :total="filteredTasks.length" layout="prev, pager, next" :pager-count="5" class="crm-completion-pagination" />

    <el-dialog v-model="dialogOpen" title="补充关键资料" width="min(780px,94vw)" append-to-body>
      <p class="crm-completion-tasks__dialog-tip">补齐后将写入 <b>{{ current?.assignee_name || '指定接收人员' }}</b> 的客户资料库。</p>
      <section class="crm-completion-tasks__source">
        <header><b>原始上传资料</b><small>以下信息将随本次补充一并写入客户资料库，可先核对再补齐关键项。</small></header>
        <dl v-if="taskSourceEntries(current).length" class="crm-completion-source-grid">
          <div v-for="entry in taskSourceEntries(current)" :key="entry.label"><dt>{{ entry.label }}</dt><dd>{{ entry.value }}</dd></div>
        </dl>
        <el-empty v-else description="该行没有其他已填写资料" :image-size="46" />
      </section>
      <el-form label-position="top" class="crm-completion-form-grid">
        <el-form-item label="公司全称" required><el-input v-model="form.公司全称" placeholder="请输入公司全称" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.姓名" placeholder="请输入联系人姓名" /></el-form-item>
        <el-form-item label="单位类型" required><el-select v-model="form.单位类型" placeholder="请选择单位类型" style="width:100%"><el-option v-for="type in unitTypes" :key="type" :label="type" :value="type" /></el-select></el-form-item>
        <el-form-item v-if="(canManageTasks || canManage) && !current?.assignee_username" label="接收人员账号" required><el-input v-model="form.target_username" placeholder="填写需关联人员的账号" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogOpen = false">取消</el-button><el-button type="primary" :loading="saving" @click="submit">确认并入客户库</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.crm-completion-tasks { display:grid; gap:14px; }
.crm-completion-regions { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px; }
.crm-completion-regions button { display:flex; align-items:center; justify-content:space-between; gap:12px; border:1px solid #dce6f2; border-radius:9px; padding:14px; background:#f8fbff; color:#526b86; cursor:pointer; font:inherit; }
.crm-completion-regions button.selected { border-color:#2463ce; background:#edf4ff; color:#164faa; box-shadow:inset 0 2px #2463ce; }
.crm-completion-regions button:focus-visible { outline:2px solid #2463ce; outline-offset:2px; }
.crm-completion-regions b { font-size:22px; font-variant-numeric:tabular-nums; }
.crm-completion-region-note { margin:0; font-size:13px; color:#667890; line-height:1.6; }
.crm-completion-pagination { justify-content:center; }
.crm-completion-tasks__header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.crm-completion-tasks__actions { display:flex; align-items:center; flex-wrap:wrap; justify-content:flex-end; gap:8px; }
.crm-completion-file-input { display:none; }
.crm-completion-tasks__header h3 { margin:0 0 5px; color:#18395b; }
.crm-completion-tasks__header p, .crm-completion-tasks__header small { margin:0; color:#667890; font-size:13px; line-height:1.55; }
.crm-completion-tasks__header small { display:block; margin-top:3px; color:#8a5b16; }
.crm-completion-tasks__table small { display:block; margin-top:3px; color:#708297; font-size:12px; }
.crm-completion-tasks__table .el-tag + .el-tag { margin-left:4px; }
.crm-completion-tasks__preview { display:grid; gap:3px; font-size:12px; line-height:1.5; color:#61748b; }
.crm-completion-tasks__preview span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.crm-completion-tasks__preview b { color:#405c78; font-weight:600; margin-right:4px; }
.crm-completion-tasks__dialog-tip { margin:0 0 16px; color:#667890; font-size:13px; }
.crm-completion-tasks__source { padding:12px; margin:0 0 18px; border:1px solid #e4ebf4; border-radius:10px; background:#f8fbff; }
.crm-completion-tasks__source > header { display:flex; align-items:baseline; flex-wrap:wrap; gap:9px; margin-bottom:10px; }
.crm-completion-source-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:0; width:100%; }
.crm-completion-source-grid>div { min-width:0; padding:10px 12px; background:white; border:1px solid #e2eaf3; border-radius:6px; }
.crm-completion-source-grid dt { font-size:12px; color:#71849a; margin-bottom:6px; }
.crm-completion-source-grid dd { margin:0; color:#294860; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; }
.crm-completion-form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:16px; }
.crm-completion-form-grid>.el-form-item:first-child { grid-column:1/-1; }
.crm-completion-tasks__source small { color:#708297; font-size:12px; line-height:1.5; }
@media (max-width: 700px) { .crm-completion-source-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width: 480px) { .crm-completion-source-grid,.crm-completion-form-grid { grid-template-columns:minmax(0,1fr); } }
@media (max-width: 700px) { .crm-completion-tasks__header { align-items:stretch; flex-direction:column; } .crm-completion-tasks__actions { justify-content:flex-start; } }
</style>
