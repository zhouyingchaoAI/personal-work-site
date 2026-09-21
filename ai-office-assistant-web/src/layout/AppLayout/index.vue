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
  reorder: [ids: MenuId[]]
}>()

const fullWidthMenus: MenuId[] = ['assistants', 'weekly', 'trip', 'writing', 'diary', 'forum', 'workorder', 'news', 'mailassistant', 'reimbursement', 'lobsterbase', 'workflow', 'cashflow', 'config', 'mailconfig', 'skills', 'usermanage', 'mcp']
</script>

<template>
  <main :class="['app-layout', { 'app-layout--wide': fullWidthMenus.includes(activeMenu) }]">
    <AppSidebar
      :active-menu="activeMenu"
      :items="menuItems"
      @select="emit('update:activeMenu', $event)"
      @reorder="emit('reorder', $event)"
    />
    <AppHeader :user="user" @logout="emit('logout')" @navigate="emit('update:activeMenu', $event)" />
    <div class="app-layout__content">
      <slot />
    </div>
  </main>
</template>
