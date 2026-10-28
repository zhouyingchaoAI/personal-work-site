<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { crmSecurityAudit, type CrmAuditEvent } from '../../../src/services/personalWorkApi'
const events = ref<CrmAuditEvent[]>([])
const scope = ref<'all' | 'limited'>('limited')
const loading = ref(false)
const page = ref(1)
const query = ref('')
const roleLabel = (value?: string) => ({disabled:'关闭访问',viewer:'只读查看',editor:'查看与编辑',importer:'查看编辑与导入',manager:'客户经营管理员'} as Record<string,string>)[value || ''] || value || ''
const scopeLabel = (value?: string) => ({self:'仅本人',team:'本人及下属',organization:'指定组织',regions:'指定区域',all:'全量'} as Record<string,string>)[value || ''] || ''
const operationLabel = (value: string) => ({read:'查看数据',write:'维护数据',import:'批量导入',manage:'权限管理',appoint:'管理员任命',security_users:'查看授权名单',grant_requested:'申请授权变更',grant_applied:'授权已更新',appoint_requested:'申请任命变更',appoint_applied:'任命已更新',delete_requested:'注销授权',delete_applied:'授权已注销',batch_grant_requested:'申请批量授权',batch_grant_applied:'批量授权已更新'}[value] || value)
const filtered = computed(() => events.value.filter(e => `${e.actor} ${operationLabel(e.operation)} ${e.path} ${e.target || ''} ${e.outcome || ''}`.toLowerCase().includes(query.value.trim().toLowerCase())))
async function load() {
  loading.value = true
  try { const res = await crmSecurityAudit(); events.value = res.events; scope.value = res.scope || 'limited'; page.value = 1 }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '加载失败') } finally { loading.value = false }
}
onMounted(load)
</script>
<template>
  <section v-loading="loading" class="crm-audit">
    <p class="audit-scope"><el-tag :type="scope === 'all' ? 'success' : 'info'" effect="light" round>{{ scope === 'all' ? '全量可见' : '仅本人可见' }}</el-tag><span>{{ scope === 'all' ? '查看、维护、导入与授权变更全部留痕；你拥有全量数据范围，可查看所有人员的操作记录。' : '查看、维护、导入与授权变更全部留痕；你只能看到权限范围内（本人 / 所辖区域或组织）人员的记录，与数据可见范围一致。' }}</span></p>
    <div class="audit-toolbar">
      <el-input v-model="query" :prefix-icon="Search" clearable placeholder="搜索操作者、操作、接口或对象" style="max-width:360px" />
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>
    <el-table :data="filtered.slice((page-1)*10, page*10)" max-height="480" size="small" empty-text="暂无可见的操作记录">
      <el-table-column prop="at" label="时间" width="170" />
      <el-table-column prop="actor" label="操作者" width="120" />
      <el-table-column label="操作" width="140"><template #default="{ row }">{{ operationLabel(row.operation) }}</template></el-table-column>
      <el-table-column prop="path" label="接口 / 操作来源" min-width="210" />
      <el-table-column prop="target" label="授权对象" width="120" />
      <el-table-column prop="outcome" label="结果" width="90" />
      <el-table-column prop="status" label="结果码" width="80" />
      <el-table-column label="授权内容" min-width="170"><template #default="{ row }"><span v-if="row.grant">{{ roleLabel(row.grant.role) }}<template v-if="scopeLabel((row.grant as any).data_scope)"> · {{ scopeLabel((row.grant as any).data_scope) }}</template> · {{ row.grant.expires_on || '长期' }}</span></template></el-table-column>
    </el-table>
    <el-pagination v-if="filtered.length > 10" v-model:current-page="page" :page-size="10" :total="filtered.length" layout="prev, pager, next, total" size="small" />
  </section>
</template>
<style scoped>
.crm-audit{display:grid;gap:14px}
.audit-scope{display:flex;align-items:baseline;gap:10px;margin:0;padding:11px 14px;border:1px solid #e4ecf6;border-radius:11px;background:linear-gradient(135deg,#fbfdff,#f4f8ff);font-size:12.5px;line-height:1.6;color:#5a7189}
.audit-scope .el-tag{flex:0 0 auto;align-self:center}
.audit-toolbar{display:flex;gap:12px;flex-wrap:wrap}
</style>
