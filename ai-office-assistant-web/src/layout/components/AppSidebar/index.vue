<script setup lang="ts">
import { computed } from 'vue'
import sidebarLogo from '../../../assets/logo.png'
import type { MenuId, SidebarMenuItem } from '../../menu'

const props = defineProps<{
  activeMenu: MenuId
  items: SidebarMenuItem[]
}>()

const emit = defineEmits<{
  select: [value: MenuId]
}>()

const mainItems = computed(() => props.items.filter((item) => item.group === 'main'))
const footerItems = computed(() => props.items.filter((item) => item.group === 'footer'))

function isActive(item: SidebarMenuItem) {
  if (item.id === 'config') return ['config', 'mailconfig', 'skills', 'usermanage', 'mcp'].includes(props.activeMenu)
  return props.activeMenu === item.id
}
</script>

<template>
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <img class="brand-logo" :src="sidebarLogo" alt="CHENCY" />
    </div>

    <nav class="sidebar-nav" aria-label="工作台导航">
      <button
        v-for="item in mainItems"
        :key="item.id"
        :class="['nav-item', `nav-item--${item.iconTone}`, { active: isActive(item) }]"
        type="button"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="emit('select', item.id)"
      >
        <span class="nav-item__icon">
          <span v-if="item.iconText" class="nav-item__icon-text">{{ item.iconText }}</span>
          <el-icon v-else-if="item.icon"><component :is="item.icon" /></el-icon>
        </span>
        <span class="nav-item__label">{{ item.label }}</span>
        <span v-if="item.statusDot" class="nav-item__status" aria-hidden="true"></span>
      </button>
    </nav>

    <nav v-if="footerItems.length" class="sidebar-nav sidebar-nav--footer" aria-label="辅助导航">
      <button
        v-for="item in footerItems"
        :key="item.id"
        :class="['nav-item', `nav-item--${item.iconTone}`, { active: isActive(item) }]"
        type="button"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="emit('select', item.id)"
      >
        <span class="nav-item__icon">
          <span v-if="item.iconText" class="nav-item__icon-text">{{ item.iconText }}</span>
          <el-icon v-else-if="item.icon"><component :is="item.icon" /></el-icon>
        </span>
        <span class="nav-item__label">{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>
