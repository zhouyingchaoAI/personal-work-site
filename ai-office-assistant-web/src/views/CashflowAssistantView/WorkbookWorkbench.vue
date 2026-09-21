<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Download, Warning } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import {
  exportCashflowWorkbook,
  getCashflowWorkbook,
  saveCashflowWorkbook,
  type CashflowHistory,
  type CashflowWorkbookSheet,
} from "../../services/personalWorkApi";

const props = defineProps<{
  modelValue: boolean;
  history: CashflowHistory | null;
}>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();
const regions = ["东区", "西区", "中区", "广东区", "未分区"];
const loading = ref(false);
const saving = ref(false);
const activeSheet = ref("");
const sheets = ref<CashflowWorkbookSheet[]>([]);
const base = reactive({ project_name: "", customer: "", region: "未分区" });
const values = reactive<Record<string, Record<string, string>>>({});
const stages = [
  {
    label: "经营规则",
    names: [
      "核算框架",
      "销售项目经营管理流程节点",
      "数据来源",
      "各合成连年度目标",
    ],
  },
  {
    label: "售前概算",
    names: [
      "项目概算表模板",
      "项目情况确认",
      "2、项目概算表模板--成本",
      "1、项目概算表模板- 场解",
      "产品清单明细",
      "2、项目概算表模板-现金流",
      "假设清单风险清单",
    ],
  },
  {
    label: "合同预算",
    names: [
      "3、项目预算表模板--成本预算定稿",
      "3、项目预算表模板-现金流预算定稿",
      "人力成本明细表",
      "差旅成本明细表",
    ],
  },
  {
    label: "执行闭环",
    names: [
      "4、财经核决算表--项目执行进度表",
      "4、财经核决算表-现金流",
      "5、项目闭环勾勾表",
      "会议记录",
    ],
  },
];
const sheetGuides: Record<
  string,
  { purpose: string; inputs: string; output: string; advice: string }
> = {
  核算框架: {
    purpose: "统一内部拆分、项目成本与销售/管理费用口径。",
    inputs: "经营单元、产品分类、内部拆分价格和费用分摊。",
    output: "后续概算与预算统一使用的核算基线。",
    advice: "先确认产品归类与成本承担边界，避免后续毛利口径不一致。",
  },
  销售项目经营管理流程节点: {
    purpose: "明确概算、预算、核算、结算各阶段的责任人与交付文件。",
    inputs: "项目阶段、责任人、待落实事项及文件传递。",
    output: "跨岗位协同和审签责任清单。",
    advice: "对未确认回款条件、资金成本、供应商价格应明确责任人和完成时点。",
  },
  项目概算表模板: {
    purpose: "形成投标/立项前的销售额、成本、毛利和目标测算。",
    inputs: "客户、区域、销售金额、成本分类、税率与目标毛利。",
    output: "售前是否满足经营指标的总览。",
    advice: "区域毛利目标将影响是否需要专项审批；现金流风险不可只看毛利。",
  },
  项目情况确认: {
    purpose: "将销售、成本、税率、资金缺口和未确认事项一次确认。",
    inputs: "销售金额、成本、税率、资金成本、风险预留。",
    output: "管理层确认的项目经营假设。",
    advice: "把账期缺口、未定成本和回款前置条件写入备注，不能仅填金额。",
  },
  "2、项目概算表模板--成本": {
    purpose: "汇总售前阶段的详细成本概算。",
    inputs: "采购、专项、人力、差旅、交付等成本及责任信息。",
    output: "支撑概算主表的成本底稿。",
    advice: "对尚未锁价的外购项单独标记，并预留价格波动风险。",
  },
  "1、项目概算表模板- 场解": {
    purpose: "按产品、供应商和交付界面拆解成本来源。",
    inputs: "产品清单、数量、采购价、供应商、成本变动原因。",
    output: "可追溯的场景/产品成本结构。",
    advice: "采购价与供货边界是概算可信度核心，应和采购确认同步更新。",
  },
  产品清单明细: {
    purpose: "明确服务或产品的工作范围、单价和合价。",
    inputs: "分类、项点、工作内容、年度单价、服务范围。",
    output: "合同收入与服务范围依据。",
    advice: "将可验收的服务内容拆开，便于对应到货、验收与质保回款节点。",
  },
  "2、项目概算表模板-现金流": {
    purpose: "在售前阶段评估回款节奏、支出节奏、资金缺口和垫资成本。",
    inputs: "回款日期/比例、采购付款、专项、人员、报销、保函与利率。",
    output: "概算阶段累计现金流与资金成本。",
    advice: "回款日期优先采用客户 P75 账期；验收与质保款不要按理想日期前置。",
  },
  假设清单风险清单: {
    purpose: "记录项目从启动到收尾的假设、风险、影响和应对。",
    inputs: "假设/风险内容、阶段、概率影响、责任人、措施与状态。",
    output: "可跟踪的经营风险台账。",
    advice:
      "将供应商锁价、验收条件、客户付款审批等直接影响现金流的事项列为高优先级。",
  },
  "3、项目预算表模板--成本预算定稿": {
    purpose: "合同签订后固化成本预算与交付利润计划。",
    inputs: "合同口径成本、季度交付计划、预算责任人与版本。",
    output: "项目执行期的成本控制基线。",
    advice: "预算定稿应替换概算假设，不应继续混用估算价格。",
  },
  "3、项目预算表模板-现金流预算定稿": {
    purpose: "将合同付款条款和确定支出转为执行资金预算。",
    inputs: "合同回款节点、实际付款计划、保证金、资金利率。",
    output: "合同后资金缺口和垫资安排。",
    advice: "将客户画像建议折算系数用于保守场景，形成可用现金而非名义应收。",
  },
  "4、财经核决算表--项目执行进度表": {
    purpose: "按执行事实跟踪收入、成本、交付与预算偏差。",
    inputs: "实际进度、实际成本、预算差异、原因和纠偏动作。",
    output: "项目经营执行复盘。",
    advice: "偏差必须说明原因和动作，尤其是采购、人员和交付延期对回款的联动。",
  },
  "4、财经核决算表-现金流": {
    purpose: "用实际回款和实际支出核对资金预算执行。",
    inputs: "实际到账日、实际金额、实际付款与偏差原因。",
    output: "实际累计现金流、垫资成本和预测修正。",
    advice: "实际到账日期应及时回填，系统才能持续提升客户账期规律的可靠性。",
  },
  "5、项目闭环勾勾表": {
    purpose: "确认交付、验收、成本、库存、结算和资料全部闭环。",
    inputs: "完成状态、备注、责任人和遗留事项。",
    output: "项目退出与复盘清单。",
    advice: "未收质保款、未结供应商款和存货差异不得勾选闭环。",
  },
  人力成本明细表: {
    purpose: "按服务模块、岗位与月份编制人力投入和成本。",
    inputs: "服务模块、岗位职级、月度人力计划与成本。",
    output: "人力成本预算依据。",
    advice: "人力投入时间应与交付节点和验收节点对应，避免回款前长期垫付。",
  },
  差旅成本明细表: {
    purpose: "按服务模块和月份编制在途、住宿、交通及补助成本。",
    inputs: "服务模块、岗位、月度差旅金额。",
    output: "差旅成本预算依据。",
    advice: "现场服务密集期的差旅支出应提前落入现金流付款节点。",
  },
  会议记录: {
    purpose: "沉淀经营、交付、回款和风险事项的会议决议。",
    inputs: "时间、地点、参会人、议题、结论与跟进事项。",
    output: "可执行的项目经营跟进记录。",
    advice: "对每项回款或成本风险明确责任人、截止日期和下一次复盘节点。",
  },
  数据来源: {
    purpose: "维护产品、数量、金额等历史输入来源。",
    inputs: "年度、数量、金额及占比。",
    output: "价格和规模测算的可追溯依据。",
    advice: "重要单价与数量必须能回溯至合同、报价或历史项目。",
  },
  各合成连年度目标: {
    purpose: "维护区域毛利率和专项毛利比经营目标。",
    inputs: "区域、毛利率、专项毛利比和公司主体。",
    output: "概算表的区域经营目标引用。",
    advice: "目标变化后先更新此表，再复核概算表中的自动引用结果。",
  },
};
type SheetInteraction = {
  mode:
    "form" | "cost" | "cashflow" | "risk" | "monthly" | "meeting" | "checklist";
  title: string;
  fields: { label: string; ref: string; placeholder?: string }[];
};
// Every worksheet has its own entry model. Values are deliberately mapped to the
// source coordinates so the guided UI and the exported workbook stay one document.
const sheetInteractions: Record<string, SheetInteraction> = {
  核算框架: {
    mode: "form",
    title: "核算口径设置",
    fields: [
      { label: "经营单元", ref: "B4" },
      { label: "产品分类", ref: "B5" },
      { label: "内部结算规则", ref: "D8" },
    ],
  },
  销售项目经营管理流程节点: {
    mode: "checklist",
    title: "项目经营流程与责任清单",
    fields: [
      { label: "阶段责任人", ref: "C6" },
      { label: "待落实事项", ref: "F6" },
    ],
  },
  项目概算表模板: {
    mode: "form",
    title: "售前经营概览",
    fields: [
      { label: "项目名称", ref: "B2" },
      { label: "客户经理", ref: "B3" },
      { label: "区域", ref: "B5" },
    ],
  },
  项目情况确认: {
    mode: "form",
    title: "项目情况确认 · 回款与采购节点",
    fields: [
      { label: "设备销售金额", ref: "D4", placeholder: "含税金额" },
      { label: "设备采购成本", ref: "D7", placeholder: "含税金额" },
      { label: "服务采购成本", ref: "D8", placeholder: "含税金额" },
      { label: "资金占用费预留", ref: "D20", placeholder: "按历史账期测算" },
      { label: "预计签约时间", ref: "D29" },
      { label: "预付款回款时间", ref: "I32" },
    ],
  },
  "2、项目概算表模板--成本": {
    mode: "cost",
    title: "售前成本概算",
    fields: [
      { label: "项目名称", ref: "B4" },
      { label: "客户", ref: "E6" },
      { label: "区域", ref: "B7" },
    ],
  },
  "1、项目概算表模板- 场解": {
    mode: "cost",
    title: "产品与供应商成本拆解",
    fields: [
      { label: "项目名称", ref: "B4" },
      { label: "客户", ref: "E6" },
    ],
  },
  产品清单明细: {
    mode: "cost",
    title: "产品与服务清单",
    fields: [
      { label: "项目名称", ref: "B2" },
      { label: "客户", ref: "B3" },
    ],
  },
  "2、项目概算表模板-现金流": {
    mode: "cashflow",
    title: "概算现金流时间轴",
    fields: [{ label: "资金年化利率", ref: "N1", placeholder: "例如 0.06" }],
  },
  假设清单风险清单: { mode: "risk", title: "假设与风险台账", fields: [] },
  "3、项目预算表模板--成本预算定稿": {
    mode: "cost",
    title: "合同后成本预算定稿",
    fields: [
      { label: "项目名称", ref: "B4" },
      { label: "区域", ref: "B7" },
    ],
  },
  "3、项目预算表模板-现金流预算定稿": {
    mode: "cashflow",
    title: "合同后现金流预算",
    fields: [{ label: "资金年化利率", ref: "N1", placeholder: "例如 0.06" }],
  },
  "4、财经核决算表--项目执行进度表": {
    mode: "cost",
    title: "执行进度与经营偏差",
    fields: [
      { label: "项目名称", ref: "B4" },
      { label: "客户", ref: "E6" },
    ],
  },
  "4、财经核决算表-现金流": {
    mode: "cashflow",
    title: "实际回款与支出执行",
    fields: [{ label: "资金年化利率", ref: "N1", placeholder: "例如 0.06" }],
  },
  "5、项目闭环勾勾表": {
    mode: "checklist",
    title: "项目闭环检查清单",
    fields: [
      { label: "闭环责任人", ref: "B3" },
      { label: "遗留事项", ref: "F4" },
    ],
  },
  人力成本明细表: { mode: "monthly", title: "月度人力投入计划", fields: [] },
  差旅成本明细表: { mode: "monthly", title: "月度差旅成本计划", fields: [] },
  会议记录: {
    mode: "meeting",
    title: "经营例会纪要与跟办",
    fields: [
      { label: "会议时间", ref: "B3" },
      { label: "会议地点", ref: "B4" },
      { label: "参会人员", ref: "B5" },
      { label: "主持人", ref: "B6" },
    ],
  },
  数据来源: {
    mode: "cost",
    title: "测算数据来源与追溯",
    fields: [
      { label: "来源说明", ref: "B3" },
      { label: "维护人", ref: "G3" },
    ],
  },
  各合成连年度目标: {
    mode: "form",
    title: "区域年度经营目标",
    fields: [
      { label: "区域", ref: "B3" },
      { label: "毛利率目标", ref: "C3" },
      { label: "专项毛利比目标", ref: "D3" },
    ],
  },
};
const stage = ref(stages[0].label);
const stageSheets = computed(() =>
  sheets.value.filter((sheet) =>
    (stages.find((item) => item.label === stage.value)?.names || []).includes(
      sheet.name,
    ),
  ),
);
const sheet = computed(
  () =>
    sheets.value.find((item) => item.name === activeSheet.value) ||
    stageSheets.value[0],
);
const guide = computed(
  () =>
    sheetGuides[sheet.value?.name || ""] || {
      purpose: "填写该工作表并保留原有公式。",
      inputs: "按原表口径填写。",
      output: "导出为可继续编辑的测算底稿。",
      advice: "先补齐项目基础信息与回款条件。",
    },
);
const interaction = computed(
  () =>
    sheetInteractions[sheet.value?.name || ""] || {
      mode: "form",
      title: "原表字段填写",
      fields: [],
    },
);
const cashflowRows = computed(() =>
  Array.from({ length: 26 }, (_, index) => index + 4),
);
const riskRows = computed(() => [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24]);
const monthlyRows = computed(() =>
  Array.from(
    { length: sheet.value?.name === "差旅成本明细表" ? 19 : 24 },
    (_, index) => index + 6,
  ),
);
const costRows = computed(() =>
  Array.from(
    { length: Math.min(20, Math.max(8, (sheet.value?.rows || 0) - 8)) },
    (_, index) => index + 9,
  ),
);
const filledCells = computed(
  () =>
    Object.values(values[sheet.value?.name || ""] || {}).filter((value) =>
      String(value).trim(),
    ).length,
);
const customerProfile = computed(
  () =>
    props.history?.customer_profiles.find(
      (item) => item.name === base.customer.trim(),
    ) || null,
);
const regionStats = computed(
  () =>
    props.history?.by_region.find((item) => item.name === base.region) || null,
);
function sourceValue(refName: string) {
  const own = values[sheet.value?.name || ""]?.[refName];
  return own ?? String(sheet.value?.cells[refName]?.value ?? "");
}
function editable(refName: string) {
  const meta = sheet.value?.cells[refName];
  return !meta?.formula && (meta?.editable ?? true);
}
function setValue(refName: string, value: string) {
  const name = sheet.value?.name;
  if (!name) return;
  values[name] ||= {};
  values[name][refName] = value;
}
function cellPosition(refName: string) {
  const match = /^([A-Z]+)(\d+)$/.exec(refName);
  if (!match) return { row: 1, column: 1 };
  let column = 0;
  for (const char of match[1]) column = column * 26 + char.charCodeAt(0) - 64;
  return { row: Number(match[2]), column };
}
function mergedSpan(refName: string) {
  const range = sheet.value?.merged.find(
    (item) => item.split(":")[0] === refName,
  );
  if (!range?.includes(":")) return { rows: 1, columns: 1 };
  const [from, to] = range.split(":").map(cellPosition);
  return { rows: to.row - from.row + 1, columns: to.column - from.column + 1 };
}
const canvasCells = computed(() =>
  Object.entries(sheet.value?.cells || {}).map(([refName, meta]) => ({
    refName,
    meta,
    ...cellPosition(refName),
    ...mergedSpan(refName),
  })),
);
function cellStyle(item: (typeof canvasCells.value)[number]) {
  const align = ["left", "center", "right", "justify"].includes(
    item.meta.align || "",
  )
    ? (item.meta.align as "left" | "center" | "right" | "justify")
    : "left";
  return {
    gridColumn: `${item.column} / span ${item.columns}`,
    gridRow: `${item.row} / span ${item.rows}`,
    background: item.meta.fill || (item.meta.formula ? "#f4f6f7" : ""),
    textAlign: align,
  };
}
function switchStage(label: string) {
  stage.value = label;
  activeSheet.value = stageSheets.value[0]?.name || "";
}
async function load() {
  loading.value = true;
  try {
    const data = await getCashflowWorkbook();
    sheets.value = data.sheets;
    Object.assign(base, {
      project_name: data.project_name,
      customer: data.customer,
      region: data.region || "未分区",
    });
    Object.keys(values).forEach((key) => delete values[key]);
    Object.assign(values, data.cells);
    const current = sheets.value.find(
      (item) => item.name === activeSheet.value,
    );
    if (!current)
      activeSheet.value =
        stageSheets.value[0]?.name || sheets.value[0]?.name || "";
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "工作簿加载失败");
  } finally {
    loading.value = false;
  }
}
async function save() {
  saving.value = true;
  try {
    const result = await saveCashflowWorkbook({ ...base, cells: values });
    ElMessage.success(`已保存 ${result.filled_cells} 个填写单元格`);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "保存失败");
  } finally {
    saving.value = false;
  }
}
async function exportBook() {
  await save();
  try {
    const file = await exportCashflowWorkbook();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(file.blob);
    link.download = file.name;
    link.click();
    URL.revokeObjectURL(link.href);
    ElMessage.success("已导出原模板结构的资金测算表");
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : "导出失败");
  }
}
watch(
  () => props.modelValue,
  (value) => {
    if (value) load();
  },
);
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    fullscreen
    class="cashflow-workbook"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header
      ><div class="workbook-title">
        <div>
          <p>项目经营全流程工作簿</p>
          <h2>按原资金测算模板完成 19 张表，公式和版式将随导出保留</h2>
        </div>
        <div>
          <el-button :loading="saving" @click="save">保存填写</el-button
          ><el-button type="primary" :icon="Download" @click="exportBook"
            >导出测算表</el-button
          >
        </div>
      </div></template
    >
    <div v-loading="loading" class="workbook-layout">
      <aside class="workbook-nav">
        <el-button
          v-for="item in stages"
          :key="item.label"
          :type="stage === item.label ? 'primary' : 'default'"
          text
          @click="switchStage(item.label)"
          >{{ item.label }}</el-button
        >
        <div class="workbook-sheet-list">
          <button
            v-for="item in stageSheets"
            :key="item.name"
            :class="{ active: item.name === sheet?.name }"
            @click="activeSheet = item.name"
          >
            {{ item.name }}
          </button>
        </div>
      </aside>
      <main class="workbook-main">
        <section class="workbook-base">
          <el-input
            v-model="base.project_name"
            placeholder="项目名称（用于导出文件名）"
          /><el-input
            v-model="base.customer"
            placeholder="客户名称（关联历史画像）"
          /><el-select v-model="base.region"
            ><el-option
              v-for="item in regions"
              :key="item"
              :label="item"
              :value="item" /></el-select
          ><span>{{ sheet?.name }} · 已填写 {{ filledCells }} 格</span>
        </section>
        <section class="sheet-guide">
          <div>
            <p>本表目标</p>
            <h3>{{ guide.purpose }}</h3>
          </div>
          <div>
            <span>关键填写</span><b>{{ guide.inputs }}</b>
          </div>
          <div>
            <span>填写完成后得到</span><b>{{ guide.output }}</b>
          </div>
        </section>
        <section v-if="sheet" class="sheet-interaction">
          <div class="interaction-heading">
            <div>
              <p>专用录入界面</p>
              <h3>{{ interaction.title }}</h3>
            </div>
            <span>所有填写会回写原测算表</span>
          </div>
          <div v-if="interaction.fields.length" class="interaction-fields">
            <label v-for="field in interaction.fields" :key="field.ref"
              ><span>{{ field.label }}</span
              ><el-input
                :model-value="sourceValue(field.ref)"
                :placeholder="field.placeholder || '请输入'"
                @update:model-value="setValue(field.ref, $event)"
            /></label>
          </div>
          <div v-if="interaction.mode === 'cashflow'" class="cashflow-timeline">
            <div class="timeline-note">
              按时间顺序填写回款、采购、专项、人员和保证金；累计现金流与垫资成本由原表公式自动计算。
            </div>
            <table>
              <thead>
                <tr>
                  <th>日期</th>
                  <th>项目进度</th>
                  <th>回款比例</th>
                  <th>回款金额</th>
                  <th>采购付款</th>
                  <th>专项采购</th>
                  <th>人员支出</th>
                  <th>保证金/保函</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in cashflowRows" :key="row">
                  <td>
                    <el-input
                      :model-value="sourceValue(`A${row}`)"
                      placeholder="YYYY-MM-DD"
                      @update:model-value="setValue(`A${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`B${row}`)"
                      placeholder="节点名称"
                      @update:model-value="setValue(`B${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`C${row}`)"
                      placeholder="例如 10%"
                      @update:model-value="setValue(`C${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`D${row}`)"
                      placeholder="金额"
                      @update:model-value="setValue(`D${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`E${row}`)"
                      placeholder="金额"
                      @update:model-value="setValue(`E${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`F${row}`)"
                      placeholder="金额"
                      @update:model-value="setValue(`F${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`H${row}`)"
                      placeholder="金额"
                      @update:model-value="setValue(`H${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`K${row}`)"
                      placeholder="金额"
                      @update:model-value="setValue(`K${row}`, $event)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="interaction.mode === 'risk'" class="register-table">
            <p>
              上半部分填写项目假设，下半部分填写风险与应对策略；量化影响会直接指导现金流保守情景。
            </p>
            <table>
              <thead>
                <tr>
                  <th>编号</th>
                  <th>事项描述</th>
                  <th>可能性/依据</th>
                  <th>影响</th>
                  <th>量化影响</th>
                  <th>责任人与状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in riskRows" :key="row">
                  <td>{{ sourceValue(`A${row}`) || row }}</td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`B${row}`)"
                      @update:model-value="setValue(`B${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`C${row}`)"
                      @update:model-value="setValue(`C${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`D${row}`)"
                      @update:model-value="setValue(`D${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`E${row}`)"
                      @update:model-value="setValue(`E${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`G${row}`)"
                      @update:model-value="setValue(`G${row}`, $event)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-else-if="interaction.mode === 'monthly'"
            class="register-table monthly-plan"
          >
            <p>
              按服务模块、岗位和月份填投入计划，合计由原表自动汇总到成本与现金流。
            </p>
            <table>
              <thead>
                <tr>
                  <th>服务模块</th>
                  <th>岗位</th>
                  <th>职级</th>
                  <th v-for="month in 12" :key="month">{{ month }}月</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in monthlyRows" :key="row">
                  <td>
                    <el-input
                      :model-value="sourceValue(`A${row}`)"
                      @update:model-value="setValue(`A${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`B${row}`)"
                      @update:model-value="setValue(`B${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`C${row}`)"
                      @update:model-value="setValue(`C${row}`, $event)"
                    />
                  </td>
                  <td
                    v-for="column in [
                      'D',
                      'E',
                      'F',
                      'G',
                      'H',
                      'I',
                      'J',
                      'K',
                      'L',
                      'M',
                      'N',
                      'O',
                    ]"
                    :key="column"
                  >
                    <el-input
                      :model-value="sourceValue(`${column}${row}`)"
                      @update:model-value="setValue(`${column}${row}`, $event)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="interaction.mode === 'cost'" class="register-table">
            <p>
              按明细逐项登记产品/服务、供应商、数量、价格与备注；系统会回传概算和预算汇总。
            </p>
            <table>
              <thead>
                <tr>
                  <th>序号</th>
                  <th>类别 / 产品</th>
                  <th>供应商 / 交付界面</th>
                  <th>数量 / 说明</th>
                  <th>金额 / 单价</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in costRows" :key="row">
                  <td>{{ sourceValue(`A${row}`) || row - 8 }}</td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`B${row}`)"
                      @update:model-value="setValue(`B${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`C${row}`)"
                      @update:model-value="setValue(`C${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`D${row}`)"
                      @update:model-value="setValue(`D${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`F${row}`)"
                      @update:model-value="setValue(`F${row}`, $event)"
                    />
                  </td>
                  <td>
                    <el-input
                      :model-value="sourceValue(`G${row}`)"
                      @update:model-value="setValue(`G${row}`, $event)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="interaction.mode === 'meeting'" class="meeting-board">
            <p>
              请先填写会议基本信息，再围绕经营指标、交付、计划和风险记录结论与责任人。
            </p>
            <div
              v-for="row in [9, 10, 11, 12, 13]"
              :key="row"
              class="meeting-item"
            >
              <b>{{ sourceValue(`B${row}`) || `议题 ${row - 8}` }}</b
              ><span>{{ sourceValue(`C${row}`) }}</span
              ><el-input
                type="textarea"
                :rows="2"
                :model-value="sourceValue(`D${row}`)"
                placeholder="讨论结论、下一步动作、责任人和截止日期"
                @update:model-value="setValue(`D${row}`, $event)"
              />
            </div>
          </div>
          <div
            v-else-if="interaction.mode === 'checklist'"
            class="checklist-board"
          >
            <p>逐项确认完成状态；未闭环事项需填写责任人、截止日期和原因。</p>
            <div
              v-for="row in Array.from(
                { length: Math.max(1, (sheet?.rows || 8) - 3) },
                (_, index) => index + 4,
              )"
              :key="row"
              class="check-row"
            >
              <span>{{ sourceValue(`A${row}`) || `检查项 ${row - 3}` }}</span
              ><el-input
                :model-value="sourceValue(`B${row}`)"
                placeholder="完成状态 / 责任人"
                @update:model-value="setValue(`B${row}`, $event)"
              /><el-input
                :model-value="sourceValue(`F${row}`)"
                placeholder="备注或遗留问题"
                @update:model-value="setValue(`F${row}`, $event)"
              />
            </div>
          </div>
          <div v-else class="form-tip">
            请完成上方字段。该表的原始版式与所有可填写单元格保留在“原表对照”中，可随时核对。
          </div>
        </section>
        <el-collapse v-if="sheet" class="original-sheet"
          ><el-collapse-item
            title="展开原表对照（公式、口径与未覆盖字段）"
            name="source"
            ><section class="workbook-grid">
              <div
                class="workbook-canvas"
                :style="{
                  gridTemplateColumns: `repeat(${sheet.columns}, minmax(86px, 1fr))`,
                  gridTemplateRows: `repeat(${sheet.rows}, minmax(28px, auto))`,
                }"
              >
                <div
                  v-for="item in canvasCells"
                  :key="item.refName"
                  class="workbook-cell"
                  :class="{
                    formula: item.meta.formula,
                    locked: !editable(item.refName),
                    input: editable(item.refName),
                  }"
                  :style="cellStyle(item)"
                >
                  <el-input
                    v-if="editable(item.refName)"
                    size="small"
                    :model-value="sourceValue(item.refName)"
                    :placeholder="item.meta.fill ? '填写' : ''"
                    @update:model-value="setValue(item.refName, $event)"
                  /><span v-else>{{ sourceValue(item.refName) }}</span>
                </div>
              </div>
            </section>
          </el-collapse-item></el-collapse
        >
      </main>
      <aside class="workbook-advice">
        <h3>
          <el-icon><Warning /></el-icon> 智能填写建议
        </h3>
        <p class="sheet-advice">{{ guide.advice }}</p>
        <template v-if="customerProfile"
          ><b>{{ customerProfile.name }}</b>
          <p>
            账期 P50 / P75：{{
              customerProfile.median_collection_days ?? "—"
            }}
            / {{ customerProfile.p75_collection_days ?? "—" }} 天
          </p>
          <p>
            资金风险 {{ customerProfile.cashflow_risk_score }} 分 · 建议回款折算
            {{
              Math.round(customerProfile.recommended_collection_factor * 100)
            }}%
          </p>
          <p>{{ customerProfile.recommendation }}</p></template
        ><template v-else
          ><p>
            填写客户名称后，系统将展示该客户的账期分位数、风险分和建议回款折算系数。
          </p></template
        ><template v-if="regionStats"
          ><hr />
          <b>{{ regionStats.name }} 历史规律</b>
          <p>
            回款达成 {{ regionStats.received_rate }}%，待回
            {{ regionStats.unpaid.toLocaleString() }} 元。
          </p></template
        >
        <hr />
        <p>
          <i class="input-key"></i>
          高亮区域可直接填写；公式与原表口径已锁定，导出 Excel 后自动重算。
        </p>
      </aside>
    </div>
  </el-dialog>
</template>

<style scoped>
.workbook-title {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding-right: 35px;
}
.workbook-title p {
  margin: 0;
  color: #29815d;
  font-size: 12px;
  font-weight: 700;
}
.workbook-title h2 {
  margin: 4px 0 0;
  color: #29495b;
  font-size: 18px;
}
.workbook-layout {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr) 280px;
  height: calc(100vh - 100px);
  gap: 14px;
}
.workbook-nav,
.workbook-advice {
  padding: 12px;
  border: 1px solid #dbe9e1;
  border-radius: 12px;
  background: #fbfefc;
}
.workbook-nav > .el-button {
  display: block;
  width: 100%;
  margin: 0 0 5px;
  text-align: left;
}
.workbook-sheet-list {
  margin-top: 12px;
  border-top: 1px solid #e4eee8;
  padding-top: 8px;
}
.workbook-sheet-list button {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px;
  text-align: left;
  color: #5a7180;
  font-size: 12px;
  cursor: pointer;
}
.workbook-sheet-list button.active {
  border-radius: 7px;
  background: #e7f5ed;
  color: #277453;
  font-weight: 700;
}
.workbook-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.workbook-base {
  display: grid;
  grid-template-columns: 1.3fr 1.1fr 120px auto;
  gap: 9px;
  align-items: center;
  margin-bottom: 10px;
}
.workbook-base span {
  color: #718296;
  font-size: 12px;
}
.workbook-grid {
  min-height: 0;
  overflow: auto;
  border: 1px solid #dbe7e1;
  border-radius: 10px;
  background: #fff;
}
.workbook-grid table {
  border-collapse: collapse;
  min-width: max-content;
  font-size: 11px;
}
.workbook-grid th {
  position: sticky;
  left: 0;
  z-index: 1;
  width: 30px;
  background: #f4f8f5;
  color: #89969d;
}
.workbook-grid td,
.workbook-grid th {
  min-width: 110px;
  padding: 3px;
  border: 1px solid #edf1ef;
  vertical-align: middle;
}
.workbook-grid td.formula {
  background: #f4f6f7;
  color: #6f7f87;
}
.workbook-grid td.locked {
  background: #f7f9f8;
  color: #63727b;
  white-space: pre-wrap;
}
.workbook-advice {
  overflow: auto;
  color: #587081;
  font-size: 13px;
  line-height: 1.55;
}
.workbook-advice h3 {
  margin: 0 0 12px;
  color: #27674e;
}
.workbook-advice h3 .el-icon {
  color: #d69321;
}
.workbook-advice p {
  margin: 8px 0;
}
.workbook-advice b {
  color: #315a68;
}
.workbook-advice hr {
  border: 0;
  border-top: 1px solid #e1ece5;
  margin: 14px 0;
}
@media (max-width: 1000px) {
  .workbook-layout {
    grid-template-columns: 150px minmax(0, 1fr);
  }
  .workbook-advice {
    display: none;
  }
  .workbook-base {
    grid-template-columns: 1fr 1fr;
  }
  .workbook-title {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

<style scoped>
.workbook-grid {
  padding: 16px;
}
.workbook-canvas {
  display: grid;
  min-width: max-content;
  align-content: start;
  border: 1px solid #303940;
  font-size: 11px;
}
.workbook-cell {
  min-width: 0;
  min-height: 28px;
  display: flex;
  align-items: center;
  padding: 3px 6px;
  border-right: 1px solid #303940;
  border-bottom: 1px solid #303940;
  color: #172c36;
  white-space: pre-wrap;
  line-height: 1.25;
  overflow: hidden;
}
.workbook-cell:has(.el-input) {
  padding: 1px;
}
.workbook-cell.input {
  box-shadow: inset 0 0 0 1px rgba(33, 122, 83, 0.08);
}
.workbook-cell.input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  background: transparent;
  padding: 0 4px;
}
.workbook-cell.input :deep(.el-input__inner) {
  height: 24px;
  font-size: 11px;
  color: #1d4839;
}
.workbook-cell.formula {
  color: #52646b;
}
.workbook-cell.locked {
  font-weight: 600;
}
.input-key {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 5px;
  border-radius: 2px;
  background: #fff3a0;
  border: 1px solid #e1c869;
}
.sheet-interaction {
  min-height: 0;
  overflow: auto;
  border: 1px solid #dbe9e1;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
}
.interaction-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  border-bottom: 1px solid #e5eee9;
  padding-bottom: 12px;
}
.interaction-heading p {
  margin: 0;
  color: #27805a;
  font-size: 12px;
  font-weight: 700;
}
.interaction-heading h3 {
  margin: 4px 0 0;
  color: #29495b;
  font-size: 17px;
}
.interaction-heading > span {
  color: #7b8d96;
  font-size: 12px;
}
.interaction-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0;
}
.interaction-fields label {
  display: grid;
  gap: 6px;
  color: #607780;
  font-size: 12px;
}
.interaction-fields label span {
  font-weight: 700;
  color: #3b5d62;
}
.cashflow-timeline,
.register-table,
.meeting-board,
.checklist-board {
  margin-top: 12px;
}
.timeline-note,
.register-table > p,
.meeting-board > p,
.checklist-board > p,
.form-tip {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f3faf6;
  color: #4b7461;
  font-size: 12px;
  line-height: 1.5;
}
.cashflow-timeline table,
.register-table table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  min-width: 900px;
  font-size: 12px;
}
.cashflow-timeline {
  overflow: auto;
}
.register-table {
  overflow: auto;
}
.cashflow-timeline th,
.register-table th {
  padding: 9px 7px;
  background: #2f7356;
  color: #fff;
  text-align: left;
  white-space: nowrap;
}
.cashflow-timeline td,
.register-table td {
  padding: 4px;
  border-right: 1px solid #e2ebe6;
  border-bottom: 1px solid #e2ebe6;
  min-width: 95px;
}
.cashflow-timeline td:first-child,
.register-table td:first-child {
  border-left: 1px solid #e2ebe6;
}
.cashflow-timeline tr:nth-child(even) td,
.register-table tr:nth-child(even) td {
  background: #fbfdfc;
}
.cashflow-timeline :deep(.el-input__wrapper),
.register-table :deep(.el-input__wrapper) {
  box-shadow: none;
  background: transparent;
  padding: 0;
}
.monthly-plan table {
  min-width: 1280px;
}
.monthly-plan td {
  min-width: 60px;
}
.meeting-item {
  display: grid;
  grid-template-columns: 180px 1fr 1.5fr;
  gap: 10px;
  align-items: start;
  padding: 12px 0;
  border-bottom: 1px solid #e5eee9;
  font-size: 12px;
}
.meeting-item b {
  color: #315d50;
}
.meeting-item span {
  color: #72838a;
  line-height: 1.5;
}
.check-row {
  display: grid;
  grid-template-columns: 1.15fr 1fr 1.6fr;
  gap: 10px;
  align-items: center;
  padding: 9px;
  border-bottom: 1px solid #edf2ef;
  font-size: 12px;
}
.check-row span {
  color: #34544c;
  font-weight: 700;
}
.original-sheet {
  margin-top: 10px;
  border: 1px solid #dbe9e1;
  border-radius: 10px;
  padding: 0 10px;
}
.original-sheet :deep(.el-collapse-item__header) {
  color: #688083;
  font-size: 12px;
  border: 0;
}
.original-sheet :deep(.el-collapse-item__wrap) {
  border: 0;
}
.original-sheet .workbook-grid {
  max-height: 440px;
  margin-bottom: 10px;
}
.sheet-guide {
  display: grid;
  grid-template-columns: 1.25fr 1fr 1fr;
  gap: 10px;
  margin: 0 0 10px;
  padding: 11px 13px;
  border: 1px solid #dcebe4;
  border-radius: 10px;
  background: linear-gradient(90deg, #f5fbf7, #fff);
}
.sheet-guide p {
  margin: 0;
  color: #27805a;
  font-size: 11px;
  font-weight: 700;
}
.sheet-guide h3 {
  margin: 4px 0 0;
  color: #355968;
  font-size: 13px;
  line-height: 1.45;
}
.sheet-guide div:not(:first-child) {
  padding-left: 12px;
  border-left: 1px solid #dcebe4;
}
.sheet-guide span {
  display: block;
  color: #7b8d96;
  font-size: 11px;
}
.sheet-guide b {
  display: block;
  margin-top: 4px;
  color: #516d64;
  font-size: 12px;
  line-height: 1.5;
}
.workbook-advice .sheet-advice {
  padding: 9px;
  border-radius: 8px;
  background: #fff8e9;
  color: #876521;
}
@media (max-width: 1000px) {
  .sheet-guide {
    grid-template-columns: 1fr;
  }
  .sheet-guide div:not(:first-child) {
    padding: 8px 0 0;
    border-left: 0;
    border-top: 1px solid #dcebe4;
  }
}
</style>
