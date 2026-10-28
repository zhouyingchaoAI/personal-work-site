<script setup lang="ts">
import { computed } from 'vue'
import { appearancePresets, contrastRatio, type ChartAppearance } from './chartAppearance'
const props = defineProps<{ count: number; appearance: ChartAppearance }>()
const contrast = computed(() => contrastRatio(props.appearance.textColor, props.appearance.background))
const emit = defineEmits<{ change: [style: ChartAppearance | null]; selectAll: []; clear: [] }>()
function numberChange(key: keyof ChartAppearance, event: Event) {
  const value = (event.target as HTMLInputElement).value
  emit('change', { [key]: value === '' ? undefined : Number(value) })
}
const sizes = [
  { key: 'fontSize', label: '正文 / 坐标字号', min: 10, max: 24 },
  { key: 'titleSize', label: '标题字号', min: 12, max: 32 },
  { key: 'valueSize', label: '指标大数字', min: 18, max: 56 },
  { key: 'padding', label: '内边距', min: 0, max: 40 },
  { key: 'radius', label: '圆角', min: 0, max: 28 },
] as const
const colors = [
  { key: 'textColor', label: '正文颜色', fallback: '#334155' },
  { key: 'titleColor', label: '标题颜色', fallback: '#17365d' },
  { key: 'background', label: '卡片底色', fallback: '#ffffff' },
  { key: 'borderColor', label: '边框颜色', fallback: '#dbe7f4' },
] as const
</script>

<template>
  <details class="chart-style-editor" open>
    <summary>样式与排版 <span>已选 {{ count }} 个板块</span></summary>
    <div class="chart-style-actions">
      <button type="button" @click="emit('selectAll')">选择本页外层板块</button>
      <button type="button" :disabled="!count" @click="emit('clear')">取消选择</button>
      <button type="button" :disabled="!count" @click="emit('change', null)">恢复所选默认样式</button>
    </div>
    <p class="chart-style-help">{{ count ? '以下值以首个选中板块为参考；只将修改的选项应用到全部选中板块。' : '勾选卡片顶部复选框，再修改样式；也可一键选择本页外层板块。' }} 样式不改动数据、图例系列颜色和告警含义。</p>
    <fieldset :disabled="!count">
      <legend>展示预设</legend>
      <div class="chart-style-presets">
        <button v-for="(preset, key) in appearancePresets" :key="key" type="button" @click="emit('change', preset.style)">{{ preset.label }}</button>
      </div>
      <div class="chart-style-grid">
        <label>图表形式
          <select aria-label="图表形式" :value="appearance.chartType || 'auto'" @change="emit('change', { chartType: ($event.target as HTMLSelectElement).value as ChartAppearance['chartType'] })">
            <option value="auto">自动 / 原图</option><option value="bar">分组柱状图</option><option value="line">平滑折线图</option><option value="points">分类点图</option><option value="pie">饼图（构成数据）</option><option value="donut">环图（构成数据）</option><option value="table">明细表（分析图）</option>
          </select>
        </label>
        <label>字体
          <select aria-label="字体" :value="appearance.fontFamily || ''" @change="emit('change', { fontFamily: (($event.target as HTMLSelectElement).value || undefined) as ChartAppearance['fontFamily'] })">
            <option value="">原样式</option><option value="system">系统黑体</option><option value="serif">宋体 / 衬线</option><option value="mono">等宽字体</option>
          </select>
        </label>
        <label v-for="item in sizes" :key="item.key">{{ item.label }} <small>px</small>
          <input type="number" :aria-label="item.label" :min="item.min" :max="item.max" :value="appearance[item.key] ?? ''" placeholder="原样式" @change="numberChange(item.key, $event)">
        </label>
        <label>文字对齐
          <select aria-label="文字对齐" :value="appearance.align || ''" @change="emit('change', { align: (($event.target as HTMLSelectElement).value || undefined) as ChartAppearance['align'] })">
            <option value="">原样式</option><option value="left">左对齐</option><option value="center">居中</option><option value="right">右对齐</option>
          </select>
        </label>
        <label>标题字重
          <select aria-label="标题字重" :value="appearance.weight || ''" @change="emit('change', { weight: (($event.target as HTMLSelectElement).value || undefined) as ChartAppearance['weight'] })">
            <option value="">原样式</option><option value="400">常规</option><option value="500">中等</option><option value="600">半粗</option><option value="700">加粗</option>
          </select>
        </label>
        <label>卡片阴影
          <select aria-label="卡片阴影" :value="appearance.shadow || ''" @change="emit('change', { shadow: (($event.target as HTMLSelectElement).value || undefined) as ChartAppearance['shadow'] })">
            <option value="">原样式</option><option value="none">无阴影</option><option value="soft">柔和</option><option value="raised">突出</option>
          </select>
        </label>
        <label v-for="item in colors" :key="item.key">{{ item.label }}
          <el-color-picker :aria-label="item.label" :model-value="appearance[item.key]" :predefine="['#17365d','#4596ff','#23e0d0','#f97316','#9a8cff','#334155','#ffffff','#f8fbff']" @change="(value: string | null) => emit('change', { [item.key]: value || undefined })" />
        </label>
      </div>
    </fieldset>
    <p v-if="contrast !== null && contrast < 4.5" class="chart-style-warning" role="status">文字与底色对比偏低（{{ contrast.toFixed(1) }}:1），建议使用更深的文字或更浅的底色。</p>
    <p class="chart-style-help">可撤销最近 50 次操作。配置仅保存于当前浏览器，按账号、视图和分页隔离；不会同步修改其他用户。</p>
  </details>
</template>

<style scoped>
.chart-style-editor{margin:0 0 16px;padding:14px 18px;border:1px solid #c9dcf2;border-radius:12px;background:#f8fbff;color:#243f5f}
summary{font-size:15px;font-weight:600;cursor:pointer}summary span{font-size:12px;font-weight:400;margin-left:12px;color:#537191}
.chart-style-actions,.chart-style-presets{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
button{padding:6px 12px;border:1px solid #bed4ed;border-radius:6px;background:#fff;color:#245f9d;cursor:pointer}
button:disabled,fieldset:disabled{opacity:.5;cursor:default}
.chart-style-help{font-size:12px;line-height:1.6;color:#537191;margin:10px 0 0}
.chart-style-warning{padding:8px 12px;background:#fff5df;color:#8a4b00;border-radius:6px;font-size:12px}
fieldset{border:0;padding:0;margin-top:12px}legend{font-size:12px;font-weight:600}
.chart-style-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-top:14px}
label{font-size:12px;display:flex;flex-direction:column;gap:6px}label small{display:none}
input,select{min-width:0;width:100%;box-sizing:border-box;border:1px solid #bed4ed;border-radius:6px;padding:7px;background:#fff;color:#243f5f}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid #4596ff;outline-offset:2px}
</style>
