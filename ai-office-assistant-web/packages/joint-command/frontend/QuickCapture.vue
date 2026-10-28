<script setup lang="ts">
import CompanyFields from "./CompanyFields.vue";
import { computed, nextTick, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type InputInstance } from "element-plus";
import {
  crmQuickCreate,
  resourceUrl,
  type CrmUnit,
  type CrmPerson,
} from "../../../src/services/personalWorkApi";
import StaffPicker from "./StaffPicker.vue";
const props = defineProps<{ units: CrmUnit[]; people: CrmPerson[] }>();
const emit = defineEmits<{ saved: [] }>();
const visible = ref(false);
const busy = ref(false);
const newStaff = ref(false);
function switchStaffMode() {
  form.our_member = "";
  form.our_name = "";
  form.our_company = "";
  form.our_department = "";
  form.our_position = "";
}
const error = ref("");
const sections = ref<string[]>([]);
const formRef = ref<FormInstance>();
const nameInput = ref<InputInstance>();
const empty = () => ({
  business_region: "",
  company_full_name: "",
  subsidiary_full_name: "",
  unit_name: "",
  department: "",
  title: "",
  name: "",
  mobile: "",
  office_phone: "",
  email: "",
  wechat: "",
  importance: "",
  support_level: "",
  history: "",
  last_interaction: "",
  weekly_plan: "",
  due_date: "",
  our_member: "",
  our_name: "",
  our_company: "",
  our_department: "",
  our_position: "",
  unit_type: "业主单位",
  city: "",
  maintenance_days: "",
  manager_id: "",
  responsibilities: "",
  role: "",
  source: "",
});
const form = reactive(empty());
const types = [
  "主管单位",
  "业主单位",
  "总包单位",
  "设计单位",
  "厂商",
];
const roles = [
  "定标",
  "定技术",
  "签验收",
  "批付款",
  "影响者",
  "需求提出",
  "采购经办",
  "运营接管",
  "安全评估协调",
];
const companyOptions = computed(() => {
  const names = new Map<string, CrmUnit>();
  for (const unit of props.units) {
    const name = (unit.organization_level === "company"
      ? unit.name
      : unit.company_full_name || "").trim();
    if (name && !names.has(name)) names.set(name, unit);
  }
  return [...names.entries()]
    .map(([name, unit]) => ({ name, unit }))
    .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
});
const existingCompany = computed(() =>
  companyOptions.value.find(
    (item) => item.name === form.company_full_name.trim(),
  ),
);
const availableUnits = computed(() => {
  const units = props.units.filter(
    (unit) => !unit.organization_level || unit.organization_level === "unit",
  );
  const company = form.company_full_name.trim();
  if (!company || !existingCompany.value) return units;
  return units.filter((unit) => unit.company_full_name === company);
});
const existing = computed(() =>
  availableUnits.value.find((u) => u.name === form.unit_name.trim()),
);
const existingPerson = computed(
  () =>
    existing.value &&
    props.people.find(
      (p) => p.unit_id === existing.value!.id && p.name === form.name.trim(),
    ),
);
const cadenceHint = computed(() =>
  form.importance === "重要"
    ? "留空按14天"
    : form.importance === "一般"
      ? "留空按21天"
      : "留空按人员层级",
);
function chooseUnit() {
  form.unit_type = existing.value?.type || "业主单位";
  form.company_full_name = existing.value?.company_full_name || form.company_full_name;
  form.subsidiary_full_name = existing.value?.subsidiary_full_name || form.subsidiary_full_name;
  if (existing.value)
    form.business_region = existing.value.business_region || "";
  form.city = existing.value?.region || "";
  form.manager_id = "";
  form.department = "";
  error.value = "";
}
function chooseCompany() {
  form.company_full_name = form.company_full_name.trim();
  if (
    form.unit_name &&
    !availableUnits.value.some((unit) => unit.name === form.unit_name)
  ) {
    form.unit_name = "";
    form.department = "";
    form.manager_id = "";
  }
  const company = existingCompany.value?.unit;
  if (company?.business_region) form.business_region = company.business_region;
  error.value = "";
}
function open() {
  newStaff.value = false;
  Object.assign(form, empty());
  sections.value = [];
  error.value = "";
  visible.value = true;
  nextTick(() => formRef.value?.clearValidate());
}
defineExpose({ open });
async function save(another: boolean) {
  if (busy.value || !(await formRef.value?.validate().catch(() => false)))
    return;
  busy.value = true;
  error.value = "";
  try {
    const result = await crmQuickCreate({ ...form, format: "business" });
    if (!result.ok) {
      error.value = result.error || "保存失败";
      return;
    }
    emit("saved");
    ElMessage.success(
      result.status === "skipped"
        ? "已有内容已跳过，未重复录入"
        : "收集信息已保存，历史互动与计划分别入库",
    );
    if (another) {
      const context = {
        business_region: form.business_region,
        company_full_name: form.company_full_name,
        subsidiary_full_name: form.subsidiary_full_name,
        unit_name: form.unit_name,
        unit_type: form.unit_type,
        city: form.city,
        our_member: form.our_member,
      };
      newStaff.value = false;
      Object.assign(form, empty(), context);
      await nextTick();
      formRef.value?.clearValidate();
      nameInput.value?.focus();
    } else visible.value = false;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "保存失败，请重试";
  } finally {
    busy.value = false;
  }
}
const rules = {
  unit_name: [
    {
      required: true,
      whitespace: true,
      message: "请选择或输入单位全称",
      trigger: "change",
    },
  ],
  name: [
    {
      required: true,
      whitespace: true,
      message: "请填写姓名",
      trigger: "blur",
    },
  ],
};
</script>
<template>
  <el-dialog
    v-model="visible"
    title="客户经营信息收集"
    width="min(860px,94vw)"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
    :show-close="!busy"
    class="crm-collection-dialog"
  >
    <div class="collect-intro">
      <div>
        <b>与 Excel 同字段、同规则</b>
        <p>
          单位、姓名必填；手机、电话、邮箱和微信等联系方式均可选填。单位类型默认“业主单位”；批量资料可使用同版模板上传。
        </p>
      </div>
      <a
        :href="resourceUrl('/api/crm/excel/template?v=20260911-no-subsidiary')"
        download
        >下载收集表 ↗</a
      >
    </div>
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      :disabled="busy"
      @submit.prevent="save(false)"
    >
      <section class="collect-basic">
        <h3>01 组织与联系人</h3>
        <div class="collect-grid">
          <el-form-item label="区域"
            ><el-select
              v-model="form.business_region"
              clearable
              :disabled="!!existing"
              placeholder="按公司划分选择"
              ><el-option
                v-for="area in ['东区', '西区', '中区', '广东区']"
                :key="area"
                :label="area"
                :value="area" /></el-select
          ></el-form-item>
          <el-form-item label="公司全称" class="collect-wide">
            <el-select
              v-model="form.company_full_name"
              filterable
              allow-create
              default-first-option
              clearable
              placeholder="模糊搜索已有公司，或输入新公司全称"
              aria-label="公司全称"
              @change="chooseCompany"
            >
              <el-option
                v-for="company in companyOptions"
                :key="company.name"
                :label="company.name"
                :value="company.name"
              />
            </el-select>
            <small class="company-match-hint">
              {{
                existingCompany
                  ? "已匹配已有公司，单位列表已按该公司筛选。"
                  : form.company_full_name.trim()
                    ? "未匹配已有公司，保存时将自动创建公司。"
                    : "支持按名称模糊搜索；没有匹配项可直接输入并创建。"
              }}
            </small>
          </el-form-item>
          <el-form-item label="单位" prop="unit_name" class="collect-wide"
            ><el-select
              v-model="form.unit_name"
              filterable
              allow-create
              default-first-option
              placeholder="公司下属业务单位；搜索已有单位或输入名称"
              @change="chooseUnit"
              ><el-option
                v-for="u in availableUnits"
                :key="u.id"
                :label="u.company_full_name ? `${u.name} · ${u.company_full_name}` : u.name"
                :value="u.name" /></el-select
          ></el-form-item>
          <el-form-item label="部门"
            ><el-input
              v-model="form.department"
              placeholder="例如：设备部"
              maxlength="100"
          /></el-form-item>
          <el-form-item label="职务"
            ><el-input
              v-model="form.title"
              placeholder="例如：技术负责人"
              maxlength="100"
          /></el-form-item>
          <el-form-item label="姓名" prop="name"
            ><el-input
              ref="nameInput"
              v-model="form.name"
              placeholder="联系人姓名"
              maxlength="100"
          /></el-form-item>
          <el-form-item label="手机（选填）"
            ><el-input
              v-model="form.mobile"
              inputmode="tel"
              placeholder="例如：13800000000"
              maxlength="40"
          /></el-form-item>
          <el-form-item label="办公电话（选填）"
            ><el-input
              v-model="form.office_phone"
              inputmode="tel"
              placeholder="例如：020-12345678"
              maxlength="60"
          /></el-form-item>
          <el-form-item label="邮箱（选填）"
            ><el-input
              v-model="form.email"
              inputmode="email"
              placeholder="例如：name@example.com"
              maxlength="160"
          /></el-form-item>
          <el-form-item label="微信 / 其他联系（选填）"
            ><el-input
              v-model="form.wechat"
              placeholder="例如：企业微信、微信号"
              maxlength="100"
          /></el-form-item>
        </div>
        <p class="collect-note">
          {{
            existing
              ? "已匹配单位，保留已有区域、城市和类型；调整请到客户档案编辑。"
              : "新单位随联系人一起保存，无需重复建档。"
          }}
        </p>
        <p v-if="existingPerson" class="collect-note">
          该联系人已存在：只补充空缺资料，已有非空内容不覆盖；新互动和新计划仍可登记。
        </p>
      </section>
      <el-collapse v-model="sections">
        <el-collapse-item
          name="history"
          title="02 关系判断与历史 · 重要程度、支持程度、跟进轨迹"
        >
          <div class="collect-grid">
            <el-form-item label="重要程度"
              ><el-select
                v-model="form.importance"
                clearable
                placeholder="暂不确定可留空"
                ><el-option label="重要" value="重要" /><el-option
                  label="一般"
                  value="一般" /></el-select
            ></el-form-item>
            <el-form-item label="支持程度"
              ><el-select
                v-model="form.support_level"
                clearable
                placeholder="选择支持程度，不确定可留空"
                ><el-option
                  v-for="code in ['反对', '中立', '支持', '积极支持']"
                  :key="code"
                  :label="code"
                  :value="code" /></el-select
            ></el-form-item>
            <div class="collect-note">
              用中文记录支持程度；不确定可留空，不自动换算为系统关系强度。
            </div>
            <el-form-item label="跟进轨迹" class="collect-all"
              ><el-input
                v-model="form.history"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
                placeholder="分行记录已发生的业务跟进；原文留存，不自动拆分成多次有效动作"
            /></el-form-item>
            <el-form-item label="上次互动时间" class="collect-wide"
              ><el-date-picker
                v-model="form.last_interaction"
                type="date"
                value-format="YYYY-MM-DD"
                :disabled-date="(date: Date) => date.getTime() > Date.now()"
                placeholder="真实发生日期，不确定留空"
            /></el-form-item>
          </div>
          <p class="collect-note">
            填写上次日期会登记一次历史互动，不默认认定为有效动作或客户主动。
          </p>
        </el-collapse-item>
        <el-collapse-item
          name="plan"
          title="03 本周互动计划 · 下一步、日期与对接人"
        >
          <div class="collect-grid">
            <el-form-item label="本周互动计划" class="collect-all"
              ><el-input
                v-model="form.weekly_plan"
                type="textarea"
                :rows="2"
                maxlength="500"
                placeholder="例如：确认项目接口资料，约定技术交流时间"
            /></el-form-item>
            <el-form-item label="计划跟进日期" class="collect-wide"
              ><el-date-picker
                v-model="form.due_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择实际日期，可留空待定"
            /></el-form-item>
            <div class="collect-all">
              <el-form-item label="我方对接人"
                ><el-radio-group v-model="newStaff" @change="switchStaffMode"
                  ><el-radio-button :value="false">选择已有人员</el-radio-button
                  ><el-radio-button :value="true"
                    >补录新人员</el-radio-button
                  ></el-radio-group
                ></el-form-item
              >
              <StaffPicker v-if="!newStaff" v-model="form.our_member" />
              <div v-else class="collect-grid">
                <p class="collect-all collect-note">
                  随本次信息一起保存人员档案，公司和部门直接选择。
                </p>
                <el-form-item
                  label="我方姓名"
                  prop="our_name"
                  :rules="[
                    {
                      required: true,
                      message: '请填写新人员姓名',
                      trigger: 'blur',
                    },
                  ]"
                  ><el-input
                    v-model="form.our_name"
                    maxlength="80" /></el-form-item
                ><el-form-item label="工号 / 对接标识（选填）"
                  ><el-input
                    v-model="form.our_member"
                    maxlength="80"
                    placeholder="同名人员请填写不同工号"
                /></el-form-item>
                <div class="collect-all">
                  <CompanyFields
                    v-model:company="form.our_company"
                    v-model:department="form.our_department"
                    v-model:position="form.our_position"
                  />
                </div>
              </div>
            </div>
          </div>
          <p class="collect-note">
            保存后进入待办，不计作已发生互动。对接人同时作为本条计划负责人。
          </p>
        </el-collapse-item>
        <el-collapse-item
          name="extra"
          title="04 补充资料 · 单位类型、城市、维系周期"
        >
          <div class="collect-grid">
            <el-form-item label="单位类型"
              ><el-select
                v-model="form.unit_type"
                :disabled="!!existing"
                placeholder="默认业主单位"
                ><el-option
                  v-for="t in types"
                  :key="t"
                  :label="t"
                  :value="t" /></el-select
            ></el-form-item>
            <el-form-item label="城市"
              ><el-input
                v-model="form.city"
                :disabled="!!existing"
                maxlength="100"
                placeholder="与经营区域分开填写"
            /></el-form-item>
            <el-form-item label="维系周期（天）"
              ><el-input
                v-model="form.maintenance_days"
                :placeholder="cadenceHint"
                maxlength="3"
                inputmode="numeric"
            /></el-form-item>
          </div>
          <p class="collect-note">
            周期为1–365天，达到周期预警、两倍周期告警。留空时重要默认14天、一般默认21天。
          </p>
          <details>
            <summary>更多组织信息（页面补充）</summary>
            <div class="collect-grid">
              <el-form-item label="直接上级" class="collect-wide"
                ><el-select
                  v-model="form.manager_id"
                  clearable
                  filterable
                  placeholder="选择已建档人员"
                  ><el-option
                    v-for="p in people"
                    :key="p.id"
                    :label="`${p.name} · ${p.unit_name || '未归属单位'} · ${p.title || ''}`"
                    :value="p.id" /></el-select
              ></el-form-item>
              <el-form-item label="决策角色"
                ><el-select v-model="form.role" clearable
                  ><el-option
                    v-for="role in roles"
                    :key="role"
                    :label="role"
                    :value="role" /></el-select
              ></el-form-item>
              <el-form-item label="负责事项" class="collect-wide"
                ><el-input v-model="form.responsibilities" maxlength="500"
              /></el-form-item>
              <el-form-item label="认识渠道"
                ><el-input v-model="form.source" maxlength="500"
              /></el-form-item>
            </div>
          </details>
        </el-collapse-item>
      </el-collapse>
    </el-form>
    <template #footer
      ><div class="quick-footer">
        <el-button :disabled="busy" @click="visible = false">取消</el-button
        ><el-button :loading="busy" @click="save(true)"
          >保存并收集下一人</el-button
        ><el-button type="primary" :loading="busy" @click="save(false)"
          >保存收集信息</el-button
        >
      </div></template
    >
  </el-dialog>
</template>
<style scoped lang="scss">
.collect-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: #edf5ff;
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 18px;
  b {
    color: #194e83;
  }
  p {
    font-size: 12px;
    line-height: 1.7;
    margin: 6px 0 0;
  }
  a {
    flex-shrink: 0;
    color: #1d5ca1;
    font-size: 12px;
  }
}
.collect-basic {
  border-top: 3px solid #1e6baf;
  padding: 14px 0;
}
h3 {
  font-size: 15px;
  color: #174b91;
  margin: 0 0 16px;
}
.collect-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 16px;
  :deep(.el-select),
  :deep(.el-date-editor) {
    width: 100%;
  }
}
.collect-wide {
  grid-column: span 2;
}
.collect-all {
  grid-column: 1/-1;
}
.collect-note {
  font-size: 12px;
  color: #62768d;
  line-height: 1.7;
  margin: 0 0 12px;
}
.company-match-hint {
  display: block;
  width: 100%;
  margin-top: 6px;
  color: #62768d;
  font-size: 11px;
  line-height: 1.5;
}
details {
  margin-top: 16px;
  summary {
    cursor: pointer;
    color: #21558c;
    font-size: 13px;
    margin-bottom: 14px;
  }
}
.quick-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  .el-button {
    margin: 0;
  }
}
:deep(.el-collapse-item__header) {
  font-weight: 600;
  color: #174b91;
}
:deep(.el-collapse-item__content) {
  padding: 14px 0;
}
@media (max-width: 600px) {
  .collect-grid {
    grid-template-columns: 1fr;
  }
  .collect-wide,
  .collect-all {
    grid-column: 1;
  }
  .collect-intro {
    flex-direction: column;
    align-items: flex-start;
  }
  :deep(.el-collapse-item__header) {
    line-height: 1.6;
    height: auto;
    min-height: 48px;
  }
}
</style>
