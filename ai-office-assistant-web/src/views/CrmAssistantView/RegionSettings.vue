<script setup lang="ts">
import { computed, ref } from 'vue'
import AmapSettings from './AmapSettings.vue'
import { ElMessage } from 'element-plus'
import { crmRegionSettings, crmSaveRegionSettings } from '../../services/personalWorkApi'
import { PROVINCES, REGION_COLORS, REGION_PROVINCES, REGION_CITIES } from './dashboard/chinaMapData'

defineProps<{ canEdit: boolean; compact?: boolean }>()
const visible = ref(false)
const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const draft = ref<Record<string, string[]>>({})
const cityDraft = ref<Record<string, string[][]>>({})
const cityOptions = ref<{ value: string; label: string; children: { value: string; label: string }[] }[]>([])
const version = ref(0)
const updatedAt = ref('')
const names = ['东区', '中区', '西区', '广东区']
const provinces = PROVINCES.map(p => p.n)
const shared = computed(() => provinces.filter(p => names.filter(n => draft.value[n]?.includes(p)).length > 1))
const uncovered = computed(() => provinces.filter(p => !names.some(n => draft.value[n]?.includes(p))))
async function reload() {
  loading.value = true
  loaded.value = false
  try {
    const result = await crmRegionSettings()
    draft.value = structuredClone(result.regions)
    cityDraft.value = Object.fromEntries(names.map(name => [name, (result.cities[name] || []).map(c => [c.province, c.city])]))
    cityOptions.value = Object.entries(result.city_options).map(([province, cities]) => ({ value: province, label: province, children: cities.map(city => ({ value: city, label: city })) }))
    version.value = result.version
    updatedAt.value = result.updated_at
    Object.assign(REGION_PROVINCES, result.regions)
    Object.assign(REGION_CITIES, result.cities)
    loaded.value = true
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '区域设置加载失败') }
  finally { loading.value = false }
}
async function open() { visible.value = true; await reload() }
async function save() {
  saving.value = true
  try {
    const cities = Object.fromEntries(names.map(name => [name, (cityDraft.value[name] || []).map(([province, city]) => ({ province: province!, city: city! }))]))
    const result = await crmSaveRegionSettings({ regions: draft.value, cities, version: version.value })
    Object.assign(REGION_PROVINCES, result.regions)
    Object.assign(REGION_CITIES, result.cities)
    version.value = result.version
    updatedAt.value = result.updated_at
    ElMessage.success('标准区域已保存，地图已更新')
    visible.value = false
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '保存失败，请重试') }
  finally { saving.value = false }
}
</script>

<template>
  <div class="region-settings-entry" :class="{compact}"><el-button @click="open">区域设置</el-button><small v-if="!compact">省份区域绑定 · 城市绑定</small></div>
  <el-dialog v-model="visible" title="标准区域设置" width="min(880px,94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving">
    <el-alert title="省份绑定覆盖全省，城市绑定仅覆盖所选城市，二者合并为区域覆盖范围，可跨区绑定。不会修改客户实际所在地或经营归属。" type="info" :closable="false" />
    <p v-if="!canEdit">当前为查看模式。客户经营管理员或超级管理员可编辑。</p>
    <div v-loading="loading" class="region-settings-grid">
      <section v-for="name in names" :key="name" :style="{ borderTopColor: REGION_COLORS[name] }">
        <h3>{{ name }} <small>{{ draft[name]?.length || 0 }} 个省份</small></h3>
        <p class="binding-label">省份区域绑定（整省）</p>
        <el-select v-if="loaded" v-model="draft[name]" multiple filterable :disabled="!canEdit || saving" :aria-label="`${name}覆盖省份`" placeholder="选择省份，可跨区多选" style="width:100%">
          <el-option v-for="p in provinces" :key="p" :label="p" :value="p" />
        </el-select>
        <p class="binding-label">城市绑定（按省份选择城市）</p>
        <el-cascader v-if="loaded" v-model="cityDraft[name]" :options="cityOptions" :props="{ multiple: true }" filterable clearable :disabled="!canEdit || saving" :aria-label="`${name}城市绑定`" placeholder="选择省份 → 城市，可多选" style="width:100%" />
        <p class="city-count">已单独绑定 {{ cityDraft[name]?.length || 0 }} 个城市。已绑定整省内的城市无需重复选择。</p>
      </section>
    </div>
    <template v-if="loaded">
      <p>跨区省份：{{ shared.join('、') || '无' }}。全图主色按东区、中区、西区、广东区顺序显示，选中区域可查看其全部省份。</p>
      <p>未整省绑定：{{ uncovered.join('、') || '无' }}（其中城市可单独绑定）</p>
      <p>地图省界描边表示整省绑定；城市绑定不会将整个省份着色。</p>
      <small>{{ updatedAt ? `上次保存：${updatedAt}` : '当前使用初始标准划分' }}</small>
    </template>
    <AmapSettings v-if="visible" :can-edit="canEdit" />
    <template #footer>
      <el-button :disabled="saving || loading" @click="reload">重新加载</el-button>
      <el-button :disabled="saving" @click="visible = false">取消</el-button>
      <el-button v-if="canEdit" type="primary" :loading="saving" :disabled="!loaded || loading" @click="save">保存区域设置</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.region-settings-entry { display:flex; align-items:center; gap:12px; margin:12px 0; }
.region-settings-entry.compact { margin:0; }
.region-settings-entry small { color:var(--el-text-color-secondary); }
.region-settings-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin:20px 0; }
.region-settings-grid section { border:1px solid var(--el-border-color); border-top:3px solid; border-radius:8px; padding:16px; }
.region-settings-grid h3 { margin:0 0 14px; }
.binding-label { margin:16px 0 8px; font-size:14px; }
.city-count { font-size:12px; color:var(--el-text-color-secondary); line-height:1.6; }
.region-settings-grid small { font-size:12px; font-weight:normal; color:var(--el-text-color-secondary); }
@media (max-width:600px) { .region-settings-grid { grid-template-columns:1fr; } }
</style>
