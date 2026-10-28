<script setup lang="ts">
defineProps<{ title?: string; icon?: string; more?: string }>()
defineEmits<{ more: [] }>()
</script>

<template>
  <section class="cv-panel">
    <header v-if="title" class="cv-panel__head" :class="{ 'has-icon': icon }">
      <img v-if="icon" class="cv-panel__icon" :src="icon" alt="" />
      <h3 class="cv-panel__title">{{ title }}</h3>
      <slot name="extra">
        <button v-if="more" type="button" class="cv-more" @click="$emit('more')">{{ more }}</button>
      </slot>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.cv-panel {
  position: absolute;
  box-sizing: border-box;
  border-radius: 9px;
  border: 1px solid rgba(74, 138, 214, 0.38);
  background:
    linear-gradient(180deg, rgba(38, 86, 150, 0.22), rgba(10, 26, 54, 0) 90px),
    linear-gradient(180deg, rgba(11, 29, 58, 0.9), rgba(7, 21, 45, 0.92));
  box-shadow:
    inset 0 1px 0 rgba(120, 180, 255, 0.18),
    inset 0 0 24px rgba(40, 110, 200, 0.12),
    0 4px 18px rgba(0, 0, 0, 0.35);
  padding: 0 18px;
  color: var(--cv-text);
}
.cv-panel__head {
  display: flex;
  align-items: center;
  height: 44px;
}
.cv-panel__head.has-icon {
  height: 42px;
  margin-top: 2px;
}
.cv-panel__icon {
  width: 28px;
  height: 28px;
  object-fit: contain;
  margin-right: 14px;
}
.cv-panel__title {
  flex: 1;
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #f3f8ff;
}
.has-icon .cv-panel__title {
  font-size: 18px;
}
</style>
