<script setup lang="ts">
// 统一的“重要程度 / 支持程度”标签，供所有展示客户信息的板块复用，
// 保证色阶与文案一致，空值明确标记为“待补充”。
withDefaults(defineProps<{ importance?: string; support?: string; compact?: boolean; labelled?: boolean; field?: 'importance' | 'support' }>(), {
  importance: '', support: '', compact: false, labelled: false,
})
function importanceTone(value?: string) { return value === '重要' ? 'high' : value === '一般' ? 'normal' : 'empty' }
function supportTone(value?: string) { return value === '积极支持' ? 'strong' : value === '支持' ? 'positive' : value === '反对' ? 'negative' : value === '中立' ? 'neutral' : 'empty' }
</script>

<template>
  <div class="pf-flags" :class="{ 'pf-flags--compact': compact, 'pf-flags--single': !!field }">
    <span v-if="field !== 'support'" aria-label="客户重要程度" class="pf-importance" :data-tone="importanceTone(importance)">{{ field ? '' : labelled ? '重要程度：' : '重要度 · ' }}{{ importance || '待补充' }}</span>
    <span v-if="field !== 'importance'" aria-label="客户支持程度" class="pf-support" :data-tone="supportTone(support)">{{ field ? '' : labelled ? '支持程度：' : '支持度 · ' }}{{ support || '待补充' }}</span>
  </div>
</template>

<style scoped>
.pf-flags{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:4px 0}
.pf-flags span{display:inline-flex;align-items:center;width:auto;padding:2px 8px;border:1px solid transparent;border-radius:999px;font-size:11px;font-weight:600;line-height:1.35;white-space:nowrap}
.pf-flags--compact span{padding:1px 7px;font-size:10px}
.pf-flags--single{margin:0}
.pf-flags--single span{font-size:12px;padding:3px 9px}
.pf-importance[data-tone=high]{color:#9a5710;background:#fff1d4;border-color:#f3ce8c}
.pf-importance[data-tone=normal]{color:#576c82;background:#edf2f7;border-color:#d5e0e9}
.pf-support[data-tone=strong]{color:#087f75;background:#dcf7f1;border-color:#9addd2}
.pf-support[data-tone=positive]{color:#257248;background:#e6f5e9;border-color:#b7dfbf}
.pf-support[data-tone=neutral]{color:#58697b;background:#edf1f5;border-color:#d4dde6}
.pf-support[data-tone=negative]{color:#b13d3d;background:#fff0f0;border-color:#f0b8b8}
.pf-flags [data-tone=empty]{color:#78899a;background:#f2f5f8;border-color:#dbe3ea}
</style>
