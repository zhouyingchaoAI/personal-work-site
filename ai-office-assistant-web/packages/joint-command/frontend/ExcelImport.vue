<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  crmImportExcel,
  crmRetryExcelRows,
  resourceUrl,
  type CrmExcelResult,
} from "../../../src/services/personalWorkApi";
const props = defineProps<{ canImport: boolean }>();
const emit = defineEmits<{ imported: [] }>();
const picker = ref<HTMLInputElement | null>(null);
const busy = ref(false);
const open = ref(false);
const result = ref<CrmExcelResult | null>(null);
const retrying = ref(false);
const overwrite = ref(false);
const hasConflict = computed(() =>
  editableErrors.value.some((item) => /不一致/.test(item.error || "")),
);
const unitTypes = [
  "主管单位",
  "业主单位",
  "总包单位",
  "设计单位",
  "厂商",
];
const editableErrors = computed(
  () =>
    result.value?.errors.filter(
      (item) => item.headers?.length && item.values,
    ) || [],
);
async function upload(event: Event) {
  if (!props.canImport) return ElMessage.warning("没有批量导入权限");
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  input.value = "";
  if (!file.name.toLowerCase().endsWith(".xlsx"))
    return ElMessage.warning("请选择 .xlsx 文件");
  if (file.size > 5 * 1024 * 1024) return ElMessage.warning("文件不能超过5MB");
  busy.value = true;
  result.value = null;
  try {
    result.value = await crmImportExcel(file);
    open.value = true;
    emit("imported");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "导入失败");
  } finally {
    busy.value = false;
  }
}
async function retryErrors() {
  if (!editableErrors.value.length) return;
  if (overwrite.value) {
    try {
      await ElMessageBox.confirm(
        "将以本次上传的内容覆盖已有档案中不一致的单位类型 / 经营区域（原值会保留历史版本，可在客户档案中追溯）。确认继续？",
        "确认覆盖已有档案",
        { type: "warning", confirmButtonText: "确认覆盖", cancelButtonText: "取消" },
      );
    } catch {
      return;
    }
  }
  retrying.value = true;
  try {
    result.value = await crmRetryExcelRows(editableErrors.value, overwrite.value);
    if (result.value.created) emit("imported");
    ElMessage.success(
      result.value.errors.length
        ? "已保存可通过的记录，请继续修正标红项"
        : "标红记录已全部导入",
    );
  } catch (error) {
    ElMessage.error(
      error instanceof Error ? error.message : "修正记录提交失败",
    );
  } finally {
    retrying.value = false;
  }
}
</script>
<template>
  <div class="crm-excel-tools">
    <a
      :href="resourceUrl('/api/crm/excel/template?v=20260911-no-subsidiary')"
      class="el-button"
      download
      >下载客户经营收集表</a
    >
    <el-button
      :loading="busy"
      :disabled="busy || !canImport"
      @click="picker?.click()"
      >上传 Excel 自动录入</el-button
    >
    <input ref="picker" type="file" accept=".xlsx" hidden @change="upload" />
    <el-button v-if="result" text @click="open = true">查看导入结果</el-button>
    <small
      >一行一位联系人 · 公司全称、姓名、单位类型齐全才入库 · 缺项自动推送补充 · 兼容旧模板</small
    >
    <el-dialog v-model="open" title="Excel 导入结果" width="min(780px,94vw)">
      <template v-if="result">
        <el-alert
          :closable="false"
          :type="result.errors.length ? 'warning' : 'success'"
          :title="`新增/补全 ${result.created} 行，待补充 ${result.pending || 0} 行，跳过已有 ${result.skipped} 行，失败 ${result.errors.length} 行`"
          description="公司全称、姓名、单位类型齐全的行已自动录入；缺少关键项的行未入库，已推送给“我方姓名”对应账号补充。错误行可按下方行号修改原表后重新上传。已有记录默认不覆盖，如单位类型 / 经营区域与档案不一致，可勾选下方“确认覆盖”后重新导入。"
        />
        <el-table
          :data="
            Object.entries(result.sheets).map(([sheet, counts]) => ({
              sheet,
              ...counts,
            }))
          "
          style="margin: 16px 0"
        >
          <el-table-column prop="sheet" label="工作表" /><el-table-column
            prop="created"
            label="新增/补全行"
          /><el-table-column prop="pending" label="待补充" /><el-table-column prop="skipped" label="跳过" /><el-table-column
            prop="failed"
            label="失败"
          />
        </el-table>
        <el-table
          v-if="result.errors.length && !editableErrors.length"
          :data="result.errors"
          max-height="300"
        >
          <el-table-column
            prop="sheet"
            label="工作表"
            width="110"
          /><el-table-column
            prop="row"
            label="Excel行号"
            width="100"
          /><el-table-column prop="error" label="修正提示" min-width="220" />
        </el-table>
        <section v-if="editableErrors.length" class="crm-import-errors">
          <div class="crm-import-errors__head">
            <div>
              <b>发现 {{ editableErrors.length }} 条需修正记录</b
              ><span>红色卡片中的字段可直接修改；只会重试这些失败行。</span>
              <el-checkbox
                v-if="hasConflict"
                v-model="overwrite"
                class="crm-overwrite-toggle"
                >存在与现有档案不一致的行，勾选后以本次上传覆盖已有单位类型 /
                经营区域（原值保留历史版本）</el-checkbox
              >
            </div>
            <el-button type="danger" :loading="retrying" @click="retryErrors"
              >{{ overwrite ? "覆盖并重新导入" : "修正后重新导入" }}</el-button
            >
          </div>
          <article
            v-for="item in editableErrors"
            :key="`${item.sheet}-${item.row}`"
            class="crm-import-error-row"
          >
            <div class="crm-import-error-row__title">
              <el-tag type="danger"
                >{{ item.sheet }} · 第 {{ item.row }} 行</el-tag
              ><b>{{ item.error }}</b>
            </div>
            <div class="crm-import-error-row__fields">
              <label
                v-for="header in item.headers"
                :key="header"
                :class="{ required: header.endsWith('*') }"
                ><span>{{ header }}</span
                ><el-select
                  v-if="header === '单位类型' || header === '单位类型*'"
                  v-model="item.values![header]"
                  placeholder="请选择单位类型"
                  ><el-option
                    v-for="type in unitTypes"
                    :key="type"
                    :label="type"
                    :value="type" /></el-select
                ><el-input
                  v-else
                  v-model="item.values![header]"
                  :placeholder="header.endsWith('*') ? '必填' : '可留空'"
              /></label>
            </div>
          </article>
        </section>
      </template>
      <template #footer
        ><el-button type="primary" @click="open = false"
          >完成</el-button
        ></template
      >
    </el-dialog>
  </div>
</template>
<style scoped>
.crm-excel-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 12px 0;
}
.crm-excel-tools .el-button {
  margin-left: 0;
  text-decoration: none;
}
.crm-excel-tools small {
  color: #667890;
  font-size: 12px;
}
.crm-import-errors {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid #fecaca;
  border-radius: 10px;
  background: #fff7f7;
}
.crm-import-errors__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.crm-import-errors__head div {
  display: grid;
  gap: 3px;
}
.crm-import-errors__head b {
  color: #b42318;
}
.crm-import-errors__head span {
  color: #9a5b55;
  font-size: 12px;
}
.crm-overwrite-toggle {
  height: auto;
  margin-top: 6px;
  white-space: normal;
}
.crm-overwrite-toggle :deep(.el-checkbox__label) {
  white-space: normal;
  line-height: 1.4;
  color: #a15a12;
  font-size: 12px;
}
.crm-import-error-row {
  padding: 12px;
  margin-top: 10px;
  border: 1px solid #f5b8b1;
  border-left: 4px solid #dc2626;
  border-radius: 8px;
  background: #fff;
}
.crm-import-error-row__title {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #a62a22;
  font-size: 13px;
}
.crm-import-error-row__fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
  margin-top: 11px;
}
.crm-import-error-row__fields label {
  display: grid;
  gap: 4px;
  color: #6d7780;
  font-size: 11px;
}
.crm-import-error-row__fields label.required span {
  color: #c3221a;
  font-weight: 700;
}
.crm-import-error-row__fields :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f6c3bd inset !important;
  background: #fffafb;
}
@media (max-width: 640px) {
  .crm-import-errors__head {
    align-items: flex-start;
    flex-direction: column;
  }
  .crm-import-error-row__fields {
    grid-template-columns: 1fr;
  }
}
</style>
