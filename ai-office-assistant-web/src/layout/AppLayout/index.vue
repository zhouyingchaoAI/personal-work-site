<script setup lang="ts">
import AppHeader from '../components/AppHeader/index.vue'
import AppSidebar from '../components/AppSidebar/index.vue'
import type { User } from '../../services/personalWorkApi'
import type { MenuId, SidebarMenuItem } from '../menu'
import './index.scss'

defineProps<{
  activeMenu: MenuId
  user: User
  menuItems: SidebarMenuItem[]
}>()

const emit = defineEmits<{
  'update:activeMenu': [value: MenuId]
  logout: []
}>()

const fullWidthMenus: MenuId[] = ['weekly', 'trip', 'diary', 'forum', 'news', 'mailassistant', 'lobsterbase', 'config', 'mailconfig', 'skills', 'usermanage']
</script>

<template>
  <main :class="['app-layout', { 'app-layout--wide': fullWidthMenus.includes(activeMenu) }]">
    <AppSidebar :active-menu="activeMenu" :items="menuItems" @select="emit('update:activeMenu', $event)" />
    <AppHeader :user="user" @logout="emit('logout')" />
    <div class="app-layout__content">
      <slot />
    </div>
  </main>
</template>
