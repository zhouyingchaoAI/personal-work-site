<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { archiveContract, contractOriginalUrl, extractContract, type ContractSummary } from '../../services/personalWorkApi'
import { ElMessage } from 'element-plus'
import { listContracts, getContract, uploadContract, saveContract, generateContractDocument, contractDocumentUrl, type ContractRecord } from '../../services/personalWorkApi'
const contracts = ref<ContractSummary[]>([])
const keyword = ref('')
const filter = ref('active')
const filteredContracts = computed(() => contracts.value.filter(entry => (filter.value === 'all' || entry.archived === (filter.value === 'archived')) && `${entry.filename} ${entry.contract_no} ${entry.customer}`.toLowerCase().includes(keyword.value.toLowerCase())))
function archive(entry: ContractSummary) {
  if (record.value?.id === entry.id && dirty.value) { ElMessage.warning('请先保存当前修改'); return }
  if (!window.confirm(entry.archived ? '恢复此合同？' : '归档后仍可下载原件和历史单据，恢复后可继续编辑。确认归档？')) return
  void run(async () => { const result = await archiveContract(entry.id, entry.revision, !entry.archived); if (record.value?.id === entry.id) accept(result.contract); await refresh(); ElMessage.success('合同状态已更新') })
}
const record = ref<ContractRecord | null>(null)
const detailTab = ref('basic')
const busy = ref(false)
const dirty = ref(false)
const selected = ref<string[]>([])
const quantities = ref<Record<string, string>>({})
const serials = ref<Record<string, string>>({})
const confirmed = ref(false)
const kind = ref('送货单')
watch(record, () => { dirty.value = true; confirmed.value = false }, { deep: true, flush: 'sync' })
function accept(value: ContractRecord) { record.value = value; dirty.value = false; selected.value = []; quantities.value = Object.fromEntries(value.lines.map(line => [line.id, line.quantity])); serials.value = {}; confirmed.value = false }
async function run(action: () => Promise<void>) { busy.value = true; try { await action() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '操作失败') } finally { busy.value = false } }
async function refresh() { contracts.value = (await listContracts()).contracts }
function load(id: string) { if (dirty.value && !window.confirm('放弃未保存的清单修改？')) return; void run(async () => accept((await getContract(id)).contract)) }
function extract() {
  if (!record.value || !window.confirm('将从原件重新提取候选内容，替换当前编辑区的识别字段和明细；保存后才会写入，不改原件。是否继续？')) return
  const current = record.value
  void run(async () => { accept((await extractContract(current.id, current.revision)).contract); dirty.value = true; ElMessage.success('结构化候选已提取，请核对后保存') })
}
function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 20 * 1024 * 1024) { ElMessage.warning('文件不能超过20MB'); input.value = ''; return }
  if (dirty.value && !window.confirm('放弃未保存的清单修改？')) { input.value = ''; return }
  void run(async () => {
    const encoded = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1] || ''); reader.onerror = reject; reader.readAsDataURL(file) })
    accept((await uploadContract(file.name, encoded)).contract); await refresh(); input.value = ''
  })
}
function save() { void run(async () => { if (record.value) { accept((await saveContract(record.value)).contract); await refresh(); ElMessage.success('清单已保存，请勾选本批次明细') } }) }
function generate() { void run(async () => {
  if (!record.value || dirty.value || !confirmed.value || !selected.value.length) return
  const result = await generateContractDocument({ id: record.value.id, revision: record.value.revision, kind: kind.value, confirmed: true, selections: selected.value.map(id => ({ id, quantity: quantities.value[id] || '', sn: serials.value[id] || '' })) })
  accept(result.contract); await refresh(); ElMessage.success('草稿已生成，可在下方下载')
}) }
onMounted(() => { void run(refresh) })
</script>
<template>
  <section class="contract-workbench" v-loading="busy">
    <h2>合同转单据工作台</h2>
    <details class="contract-library" :open="!record"><summary>我的合同 · {{ contracts.length }} 份 · 点击展开 / 收起</summary>
    <p>上传的原件、核对清单及生成单据持续保存，只有本人可访问。归档不删除文件。</p>
    <el-input v-model="keyword" placeholder="搜索文件名、合同编号、客户" clearable aria-label="搜索合同" />
    <p><el-radio-group v-model="filter"><el-radio-button value="active">在用</el-radio-button><el-radio-button value="archived">已归档</el-radio-button><el-radio-button value="all">全部</el-radio-button></el-radio-group><el-button :disabled="busy" @click="run(refresh)">刷新列表</el-button></p>
    <el-table :data="filteredContracts" empty-text="没有符合条件的合同">
      <el-table-column prop="filename" label="合同文件" min-width="230" />
      <el-table-column prop="created_at" label="上传时间" min-width="170" />
      <el-table-column prop="contract_no" label="合同编号" min-width="120" />
      <el-table-column prop="document_count" label="单据数" width="80" />
      <el-table-column label="状态" width="90"><template #default="{ row }">{{ row.archived ? '已归档' : '在用' }}</template></el-table-column>
      <el-table-column label="操作" min-width="230"><template #default="{ row }"><el-button link :disabled="busy" @click="load(row.id)">打开</el-button><a :href="contractOriginalUrl(row.id)">下载原件</a><el-button link :disabled="busy" @click="archive(row)">{{ row.archived ? '恢复' : '归档' }}</el-button></template></el-table-column>
    </el-table>
    </details>
    <fieldset :disabled="busy"><label>上传新合同（DOCX / PDF，20MB以内）<input type="file" accept=".docx,.pdf" @change="upload" /></label></fieldset>
    <template v-if="record">
      <h3>{{ record.filename }} · 版本 {{ record.revision }}</h3>
      <el-alert v-if="record.extraction" :title="record.extraction.mode === 'template' ? `模板匹配：${record.extraction.template_name} · 已按模板规则提取` : '未匹配模板 · 已自动启用通用文本/表格识别'" :type="record.extraction.mode === 'template' ? 'success' : 'info'" :closable="false" />
      <p v-if="record.extraction">{{ record.extraction.reason }}<span v-if="record.extraction.evidence.length">；匹配依据：{{ record.extraction.evidence.join('、') }}</span></p>
      <p v-else>此合同尚无模板匹配记录，可点击下方按钮按新流程重新识别。</p>
      <el-button :disabled="busy || record.archived" @click="extract">从原件提取结构化内容</el-button>
      <p>识别结果为候选：请确认甲乙方在本业务中的角色，区分服务范围设备与实际交付货物；付款条件未转换为日历日期，不会自动触发任务。</p>
      <el-alert v-if="record.archived" title="此合同已归档，可下载原件和历史单据；恢复后可继续编辑。" type="warning" :closable="false" />
      <el-tabs v-model="detailTab" class="contract-detail-tabs">
        <el-tab-pane label="1 · 基本信息" name="basic" />
        <el-tab-pane label="2 · 合同明细" name="lines" />
        <el-tab-pane label="3 · 付款与验收" name="payments" />
        <el-tab-pane label="4 · 单据生成" name="generate" />
      </el-tabs>
      <fieldset :disabled="busy || record.archived" class="contract-editor">
      <section v-show="detailTab === 'basic'">
      <div class="contract-columns"><details><summary>展开合同原文核对</summary><pre>{{ record.source_text }}</pre></details><el-form label-position="top" :disabled="busy || record.archived">
        <el-form-item label="合同编号（必填）"><el-input v-model="record.contract_no" /></el-form-item><el-form-item label="项目编码"><el-input v-model="record.project_code" /></el-form-item><el-form-item label="客户名称（必填）"><el-input v-model="record.customer" /></el-form-item><el-form-item label="交付地址"><el-input v-model="record.address" /></el-form-item>
        <el-form-item label="乙方 / 供应商（待核对）"><el-input v-model="record.supplier" /></el-form-item>
        <el-form-item label="含税总额（原文数值）"><el-input v-model="record.total_amount" /></el-form-item>
        <el-form-item label="税率"><el-input v-model="record.tax_rate" /></el-form-item>
      </el-form></div>
      </section>
      <section v-show="detailTab === 'payments'">
      <h3>付款节点与验收条件</h3>
      <p>比例、金额和支付天数为原文候选；空值、条件冲突需要核对，暂不据此自动计算应收日期。</p>
      <div class="contract-grid"><table><thead><tr><th>款项</th><th>比例 %</th><th>金额 元</th><th>支付天数（核对工作日口径）</th><th>前置条件 / 原文备注</th><th>操作</th></tr></thead><tbody><tr v-for="(payment, index) in record.payments || []" :key="index"><td><input v-model="payment.name" /></td><td><input v-model="payment.percentage" /></td><td><input v-model="payment.amount" /></td><td><input v-model="payment.days" /></td><td><textarea v-model="payment.condition" rows="3" /></td><td><el-button link @click="record.payments?.splice(index, 1)">移除</el-button></td></tr></tbody></table></div>
      <el-button @click="(record.payments ||= []).push({name: '', percentage: '', amount: '', days: '', condition: ''})">添加付款节点</el-button>
      <el-form label-position="top" :disabled="busy || record.archived">
        <el-form-item label="付款条款摘录（可补充）"><el-input v-model="record.payment_terms" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="验收 / 质保条款摘录（可补充）"><el-input v-model="record.acceptance_terms" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      </section>
      <section v-show="detailTab === 'lines'">
      <p>请核对名称、型号、单位及数量；无法识别的内容需补录，系统不会猜填。</p>
      <div class="contract-grid"><table><thead><tr><th>选择</th><th>名称</th><th>规格型号</th><th>单位</th><th>合同数量</th><th>本批次数量</th><th>SN/二维码文本</th><th>来源</th><th>操作</th><th>品牌 / 价格</th></tr></thead><tbody><tr v-for="(line, index) in record.lines" :key="line.id">
        <td><input v-model="selected" type="checkbox" :value="line.id" :disabled="dirty || busy" /></td><td><input v-model="line.name" :disabled="busy" aria-label="名称" /></td><td><input v-model="line.spec" :disabled="busy" aria-label="规格型号" /></td><td><input v-model="line.unit" :disabled="busy" aria-label="单位" /></td><td><input v-model="line.quantity" :disabled="busy" aria-label="合同数量" /></td><td><input v-model="quantities[line.id]" :disabled="dirty || busy" aria-label="本批次数量" /></td><td><input v-model="serials[line.id]" :disabled="dirty || busy" placeholder="粘贴或扫码输入" /></td><td>{{ line.source || '人工补录' }}</td><td><el-button :disabled="busy" link type="danger" @click="record.lines.splice(index, 1)">移除</el-button></td>
        <td><details><summary>{{ line.brand || '商务信息' }} · {{ line.amount || '金额待核对' }}</summary><label>品牌<input v-model="line.brand" :disabled="busy" /></label><label>原文单价（元）<input v-model="line.unit_price" :disabled="busy" /></label><label>原文合计（元）<input v-model="line.amount" :disabled="busy" /></label><label>备注<input v-model="line.remark" :disabled="busy" /></label><small>保留原文，不自动重算金额</small></details></td>
      </tr></tbody></table></div>
      <p><el-button :disabled="busy" @click="record.lines.push({ id: String(Date.now()), name: '', spec: '', unit: '', quantity: '', source: '人工补录' })">添加明细</el-button></p>
      </section>
      <section v-show="detailTab === 'generate'">
      <p>先在“合同明细”中保存并勾选本批次，再确认生成。已选 {{ selected.length }} 项。</p>
      <el-button @click="detailTab = 'lines'">前往选择明细</el-button>
      <p>导出为通用 Word 草稿，尚非公司正式模板；不代表已发货、签收或验收。</p>
      <el-select v-model="kind"><el-option v-for="entry in ['送货单', '到货签收单', '验收单']" :key="entry" :value="entry" :label="entry" /></el-select><el-checkbox v-model="confirmed" :disabled="dirty || busy">已核对合同与本批次数量</el-checkbox><el-button type="primary" :disabled="busy || dirty || !confirmed || !selected.length" @click="generate">生成 Word 草稿</el-button>
      </section>
      </fieldset>
      <section v-show="detailTab === 'generate'">
      <h3>单据历史（仅本人可下载）</h3><p v-if="!record.documents.length">尚未生成单据</p><p v-for="entry in record.documents.slice().reverse()" :key="entry.id"><a :href="contractDocumentUrl(record.id, entry.id)">{{ entry.kind }} · {{ entry.created_at }} · 合同版本 {{ entry.revision }} · 下载草稿</a></p>
      </section>
      <div class="contract-save-bar"><span>{{ record.archived ? '已归档 · 只读' : dirty ? '有未保存修改，请保存核对结果' : '当前记录已保存' }}</span><el-button :disabled="busy || record.archived" type="primary" @click="save">保存核对结果</el-button></div>
    </template>
  </section>
</template>
<style scoped>
.contract-library{border:1px solid #e2e8f0;border-radius:10px;padding:16px;background:#f8fafc}.contract-library summary{cursor:pointer;font-weight:600;color:#1e293b}.contract-detail-tabs{margin-top:22px}.contract-save-bar{position:sticky;bottom:0;background:#fff;border-top:1px solid #e2e8f0;padding:14px 0;display:flex;justify-content:space-between;gap:12px;align-items:center;z-index:2}.contract-save-bar span{color:#64748b;font-size:13px}.contract-editor section{padding:8px 0 20px}.contract-grid th{background:#f1f5f9;color:#334155}.contract-columns summary{cursor:pointer;color:#2563eb;padding:10px 0}
.contract-workbench fieldset.contract-editor{display:block;min-width:0}
.contract-workbench{background:white;border:1px solid #e8edf5;border-radius:12px;padding:20px;margin-bottom:20px}.contract-workbench p{color:#64748b}.contract-workbench fieldset{border:0;display:flex;gap:20px;flex-wrap:wrap;padding:12px 0}.contract-columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}.contract-columns pre{white-space:pre-wrap;overflow:auto;max-height:360px;font-size:13px;background:#f8fafc;padding:14px}.contract-grid{overflow:auto}.contract-grid table{border-collapse:collapse;width:100%;min-width:1000px}.contract-grid td,.contract-grid th{border:1px solid #ddd;padding:8px}.contract-grid input:not([type=checkbox]){width:110px;padding:7px;border:1px solid #ddd;border-radius:4px}.contract-workbench .el-checkbox{margin:12px}@media(max-width:800px){.contract-columns{grid-template-columns:1fr}}
</style>
