<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Delete, Document, Plus, Calendar, Check } from '@element-plus/icons-vue'
import { OPPORTUNITY_STAGES, OPPORTUNITY_STAGE_STATUS } from './opportunityStages'
import { uploadForumAttachment, crmOpportunityStageSave, type CrmOpportunity, type CrmPerson, type ForumAttachment, type CrmStageContact } from '../../../src/services/personalWorkApi'

const props = defineProps<{ opportunity: CrmOpportunity; people: CrmPerson[]; canEdit: boolean }>()
const emit = defineEmits<{ saved: [] }>()

const today = new Date().toISOString().slice(0, 10)

// 每个阶段的本地编辑态：从机会点已存进展初始化，保存后由父组件刷新重建。
interface StageDraft {
  attachments: ForumAttachment[]; contacts: CrmStageContact[]; picker: string
  status: string; planned_start: string; planned_end: string; work_done: string[]
  busy: boolean; uploading: boolean
}
const drafts = reactive<Record<string, StageDraft>>({})
for (const stage of OPPORTUNITY_STAGES) {
  const saved = props.opportunity.stage_progress?.[stage.name]
  drafts[stage.name] = {
    attachments: saved ? [...saved.attachments] : [],
    contacts: saved ? saved.contacts.map(c => ({ ...c })) : [],
    status: saved?.status || '',
    planned_start: saved?.planned_start || '',
    planned_end: saved?.planned_end || '',
    work_done: saved?.work_done ? [...saved.work_done] : [],
    picker: '', busy: false, uploading: false,
  }
}

const activeNames = ref<string[]>([OPPORTUNITY_STAGES[0].name])
const peopleOptions = computed(() => props.people.map(p => ({ value: p.id, label: `${p.name}${p.department ? ' · ' + p.department : ''}${p.title ? ' · ' + p.title : ''}` })))

function statusTone(name: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const d = drafts[name]
  if (d.status === '已完成') return 'success'
  if (d.status === '已暂停') return 'info'
  if (d.planned_end && d.planned_end < today && d.status !== '已完成') return 'danger'
  if (d.status === '进行中') return 'warning'
  return ''
}
function statusText(name: string) {
  const d = drafts[name]
  if (d.planned_end && d.planned_end < today && d.status !== '已完成') return '已逾期'
  return d.status || '未开始'
}

function stageSummary(name: string) {
  const d = drafts[name]
  const meta = OPPORTUNITY_STAGES.find(s => s.name === name)!
  return { files: d.attachments.length, contacts: d.contacts.length, works: d.work_done.length, totalWorks: meta.works.length }
}

function toggleWork(name: string, work: string, checked: boolean) {
  const d = drafts[name]
  if (checked) { if (!d.work_done.includes(work)) d.work_done.push(work) }
  else d.work_done = d.work_done.filter(w => w !== work)
}

async function pickFiles(name: string, event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  const draft = drafts[name]
  draft.uploading = true
  try {
    for (const file of files) {
      if (draft.attachments.length >= 8) { ElMessage.warning('每个阶段最多 8 个材料'); break }
      const res = await uploadForumAttachment(file)
      if (res.ok && res.attachment) draft.attachments.push(res.attachment)
      else ElMessage.error('“' + file.name + '”上传失败')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败，请重试')
  } finally {
    draft.uploading = false
  }
}

function removeFile(name: string, id: string) { drafts[name].attachments = drafts[name].attachments.filter(a => a.id !== id) }

function addContact(name: string, personId: string) {
  if (!personId) return
  const draft = drafts[name]
  if (draft.contacts.some(c => c.person_id === personId)) { draft.picker = ''; return }
  const person = props.people.find(p => p.id === personId)
  if (!person) return
  draft.contacts.push({ person_id: person.id, name: person.name, department: person.department || '', role: person.decision_role || '' })
  draft.picker = ''
}

function removeContact(name: string, index: number) { drafts[name].contacts.splice(index, 1) }

async function save(name: string) {
  const draft = drafts[name]
  if (draft.busy) return
  if (draft.planned_start && draft.planned_end && draft.planned_end < draft.planned_start) {
    ElMessage.warning('计划完成日期不能早于计划开始日期'); return
  }
  draft.busy = true
  try {
    const res = await crmOpportunityStageSave({
      id: props.opportunity.id,
      code: props.opportunity.code,
      stage: name,
      status: draft.status,
      planned_start: draft.planned_start,
      planned_end: draft.planned_end,
      work_done: draft.work_done,
      attachments: draft.attachments.map(a => ({ id: a.id, name: a.name, type: a.type, size: a.size })),
      contacts: draft.contacts.map(c => ({ person_id: c.person_id, name: c.name, role: c.role, department: c.department })),
    })
    if (res.ok) { ElMessage.success(name + ' 已保存'); emit('saved') }
    else ElMessage.error(res.error || '保存失败')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败，请重试')
  } finally {
    draft.busy = false
  }
}
</script>

<template>
  <div class="osp">
    <p class="osp-intro">按轨道交通项目全生命周期六阶段维护：<b>时间管控</b>（计划起止 + 状态）、<b>主要工作</b>（勾选进度）、<b>证明 / 输出材料</b>（上传交付成果）与阶段关系人。前三段“定义项目”，后三段“赢得项目”。</p>
    <el-collapse v-model="activeNames" class="osp-collapse">
      <el-collapse-item v-for="stage in OPPORTUNITY_STAGES" :key="stage.name" :name="stage.name">
        <template #title>
          <div class="osp-head">
            <span class="osp-phase" :class="stage.group === 'define' ? 'is-define' : 'is-win'">{{ stage.phase }}</span>
            <strong>{{ stage.name }}</strong>
            <span class="osp-cycle"><el-icon><Calendar /></el-icon>{{ stage.cycle }}</span>
            <el-tag :type="statusTone(stage.name) || 'info'" size="small" effect="light" class="osp-status-tag">{{ statusText(stage.name) }}</el-tag>
            <span class="osp-counts">工作 {{ stageSummary(stage.name).works }}/{{ stageSummary(stage.name).totalWorks }} · 材料 {{ stageSummary(stage.name).files }} · 关系人 {{ stageSummary(stage.name).contacts }}</span>
          </div>
        </template>
        <div class="osp-body">
          <!-- 时间管控 -->
          <section class="osp-block osp-block--first">
            <header><h5><el-icon><Calendar /></el-icon> 时间管控</h5><span class="osp-ref">参考周期：{{ stage.cycle }}</span></header>
            <div class="osp-time">
              <label>计划开始<el-date-picker v-model="drafts[stage.name].planned_start" type="date" value-format="YYYY-MM-DD" :disabled="!canEdit" placeholder="选择日期" size="default" /></label>
              <label>计划完成<el-date-picker v-model="drafts[stage.name].planned_end" type="date" value-format="YYYY-MM-DD" :disabled="!canEdit" placeholder="选择日期" size="default" /></label>
              <label>阶段状态<el-select v-model="drafts[stage.name].status" :disabled="!canEdit" placeholder="未开始" size="default" clearable style="width:130px"><el-option v-for="s in OPPORTUNITY_STAGE_STATUS" :key="s" :label="s" :value="s" /></el-select></label>
            </div>
          </section>

          <!-- 主要工作 -->
          <section class="osp-block">
            <header><h5><el-icon><Check /></el-icon> 主要工作</h5><span class="osp-ref">勾选已完成事项</span></header>
            <ul class="osp-works">
              <li v-for="w in stage.works" :key="w">
                <el-checkbox :model-value="drafts[stage.name].work_done.includes(w)" :disabled="!canEdit" @change="(v: any) => toggleWork(stage.name, w, !!v)">{{ w }}</el-checkbox>
              </li>
            </ul>
          </section>

          <!-- 证明 / 输出材料 -->
          <section class="osp-block">
            <header><h5><el-icon><Document /></el-icon> 证明 / 输出材料</h5>
              <label v-if="canEdit" class="osp-upload-btn">
                <el-icon><UploadFilled /></el-icon>{{ drafts[stage.name].uploading ? '上传中…' : '上传材料' }}
                <input type="file" multiple hidden :disabled="drafts[stage.name].uploading" @change="e => pickFiles(stage.name, e)" />
              </label>
            </header>
            <p class="osp-outputs">应交付成果：<span v-for="o in stage.outputs" :key="o" class="osp-output-chip">{{ o }}</span></p>
            <ul v-if="drafts[stage.name].attachments.length" class="osp-files">
              <li v-for="file in drafts[stage.name].attachments" :key="file.id">
                <a :href="file.url" target="_blank" rel="noopener">{{ file.name }}</a>
                <el-button v-if="canEdit" link type="danger" :icon="Delete" @click="removeFile(stage.name, file.id)" />
              </li>
            </ul>
            <p v-else class="osp-empty">暂无材料，上传上述交付成果作为证明；支持 PDF / Word / Excel / 图片 / 压缩包等，单个不超过 20MB。</p>
          </section>

          <!-- 阶段关系人 -->
          <section class="osp-block">
            <header><h5><el-icon><Plus /></el-icon> 阶段关系人</h5>
              <el-select-v2 v-if="canEdit" v-model="drafts[stage.name].picker" :options="peopleOptions" filterable clearable placeholder="搜索并添加客户联系人" style="width:260px" @change="(id: string) => addContact(stage.name, id)" />
            </header>
            <div v-if="drafts[stage.name].contacts.length" class="osp-contacts">
              <span v-for="(c, i) in drafts[stage.name].contacts" :key="c.person_id || c.name + i" class="osp-contact">
                <b>{{ c.name }}</b><small v-if="c.role || c.department">{{ [c.role, c.department].filter(Boolean).join(' · ') }}</small>
                <el-icon v-if="canEdit" class="osp-contact-x" @click="removeContact(stage.name, i)"><Delete /></el-icon>
              </span>
            </div>
            <p v-else class="osp-empty">暂无关系人，从客户联系人中选择本阶段参与 / 影响决策的人。</p>
          </section>

          <footer v-if="canEdit" class="osp-foot">
            <el-button type="primary" :loading="drafts[stage.name].busy" @click="save(stage.name)">保存本阶段</el-button>
          </footer>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style scoped>
.osp-intro { font-size:13px; color:#64748b; line-height:1.7; margin:0 0 12px; }
.osp-intro b { color:#15499c; }
.osp-collapse { border-top:none; }
.osp-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; width:100%; }
.osp-phase { font-size:12px; padding:2px 8px; border-radius:20px; color:#fff; }
.osp-phase.is-define { background:#15499c; } .osp-phase.is-win { background:#1f8a72; }
.osp-head strong { font-size:15px; color:#1f3350; }
.osp-cycle { font-size:12px; color:#8a94a6; display:inline-flex; align-items:center; gap:3px; }
.osp-status-tag { flex:none; }
.osp-counts { margin-left:auto; font-size:12px; color:#5e7690; }
.osp-body { padding:4px 2px 8px; }
.osp-block { border-top:1px dashed #e5eaf1; padding:12px 0; }
.osp-block--first { border-top:none; }
.osp-block header { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
.osp-block h5 { margin:0; font-size:14px; color:#15499c; display:flex; align-items:center; gap:6px; }
.osp-ref { font-size:12px; color:#8a94a6; }
.osp-time { display:flex; flex-wrap:wrap; gap:16px; }
.osp-time label { display:flex; flex-direction:column; gap:6px; font-size:12.5px; color:#5e7690; }
.osp-works { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px 18px; }
.osp-works :deep(.el-checkbox) { height:auto; white-space:normal; }
.osp-works :deep(.el-checkbox__label) { white-space:normal; line-height:1.5; }
.osp-outputs { margin:0 0 10px; font-size:12.5px; color:#64748b; display:flex; align-items:center; flex-wrap:wrap; gap:6px; }
.osp-output-chip { background:#eef4ff; color:#24558b; border-radius:6px; padding:2px 8px; font-size:12px; }
.osp-upload-btn { display:inline-flex; align-items:center; gap:5px; font-size:13px; color:#1e6bff; cursor:pointer; padding:6px 12px; border:1px solid #b7d0f2; border-radius:7px; }
.osp-upload-btn:hover { background:#eef4ff; }
.osp-files { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }
.osp-files li { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 12px; background:#f7faff; border-radius:8px; }
.osp-files a { color:#216bbb; text-decoration:none; overflow-wrap:anywhere; }
.osp-files a:hover { text-decoration:underline; }
.osp-empty { margin:0; font-size:12.5px; color:#94a3b8; line-height:1.6; }
.osp-contacts { display:flex; flex-wrap:wrap; gap:8px; }
.osp-contact { display:inline-flex; align-items:center; gap:6px; padding:6px 10px; background:#eef4ff; border-radius:20px; font-size:13px; color:#1f3350; }
.osp-contact small { color:#64789a; font-size:12px; }
.osp-contact-x { cursor:pointer; color:#c0563f; }
.osp-foot { margin-top:12px; }
@media (max-width:560px) { .osp-works { grid-template-columns:1fr; } .osp-time { gap:12px; } }
</style>
