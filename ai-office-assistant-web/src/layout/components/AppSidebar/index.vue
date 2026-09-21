<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Menu as MenuIcon } from '@element-plus/icons-vue'
import sidebarLogo from '../../../assets/logo.png'
import type { MenuId, SidebarMenuItem } from '../../menu'

const props = defineProps<{
  activeMenu: MenuId
  items: SidebarMenuItem[]
}>()

const emit = defineEmits<{
  select: [value: MenuId]
  reorder: [ids: MenuId[]]
}>()

const mainItems = computed(() => props.items.filter((item) => item.group === 'main'))
const footerItems = computed(() => props.items.filter((item) => item.group === 'footer'))
const mobileOpen = ref(false)
const isMobileViewport = ref(false)
let mobileQuery: MediaQueryList | null = null

function syncMobileViewport() {
  const wasMobileViewport = isMobileViewport.value
  isMobileViewport.value = Boolean(mobileQuery?.matches)
  if (!isMobileViewport.value) mobileOpen.value = false
  else if (!wasMobileViewport) mobileOpen.value = true
}

function isActive(item: SidebarMenuItem) {
  if (item.id === 'config') return ['config', 'mailconfig', 'skills', 'usermanage', 'mcp'].includes(props.activeMenu)
  return props.activeMenu === item.id
}

function selectMenu(item: SidebarMenuItem) {
  emit('select', item.id)
  mobileOpen.value = false
}

// 非固定的助手入口支持拖拽调整顺序，插入位置用蓝色插入线提示（与周报条目排序一致）。
const draggingId = ref<MenuId | ''>('')
const dropTargetId = ref<MenuId | ''>('')
const dropPosition = ref<'before' | 'after'>('before')

function canDrag(item: SidebarMenuItem) {
  return item.group === 'main' && !item.fixed
}

function handleNavDragStart(event: DragEvent, item: SidebarMenuItem) {
  if (!canDrag(item)) return
  draggingId.value = item.id
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', item.id)
  }
}

function handleNavDragOver(event: DragEvent, item: SidebarMenuItem) {
  if (!draggingId.value || !canDrag(item) || item.id === draggingId.value) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  dropTargetId.value = item.id
  dropPosition.value = event.clientY - rect.top < rect.height / 2 ? 'before' : 'after'
}

function handleNavDrop(event: DragEvent, item: SidebarMenuItem) {
  if (!draggingId.value || !canDrag(item) || item.id === draggingId.value) return
  event.preventDefault()
  const ids = mainItems.value.filter(canDrag).map((entry) => entry.id)
  const from = ids.indexOf(draggingId.value)
  let to = ids.indexOf(item.id)
  if (from < 0 || to < 0) return
  ids.splice(from, 1)
  to = ids.indexOf(item.id)
  if (dropPosition.value === 'after') to += 1
  ids.splice(to, 0, draggingId.value)
  emit('reorder', ids)
  handleNavDragEnd()
}

function handleNavDragEnd() {
  draggingId.value = ''
  dropTargetId.value = ''
}

function dragClasses(item: SidebarMenuItem) {
  return {
    'nav-item--dragging': draggingId.value === item.id,
    'nav-item--drop-before': dropTargetId.value === item.id && dropPosition.value === 'before',
    'nav-item--drop-after': dropTargetId.value === item.id && dropPosition.value === 'after',
  }
}

onMounted(() => {
  mobileQuery = window.matchMedia('(max-width: 900px)')
  syncMobileViewport()
  mobileQuery.addEventListener('change', syncMobileViewport)
})

onUnmounted(() => mobileQuery?.removeEventListener('change', syncMobileViewport))
</script>

<template>
  <button :class="['mobile-nav-toggle', { 'is-open': mobileOpen }]" type="button" :aria-expanded="mobileOpen" aria-controls="mobile-workspace-navigation" @click="mobileOpen = !mobileOpen">
    <el-icon><MenuIcon /></el-icon><span>导航</span>
  </button>
  <div v-if="mobileOpen" class="mobile-nav-backdrop" aria-hidden="true" @click="mobileOpen = false" />
  <aside id="mobile-workspace-navigation" :class="['app-sidebar', { 'is-mobile-open': mobileOpen }]" :aria-hidden="isMobileViewport && !mobileOpen ? 'true' : undefined" :inert="isMobileViewport && !mobileOpen ? true : undefined">
    <div class="sidebar-brand">
      <img class="brand-logo" :src="sidebarLogo" alt="CHENCY" />
      <button class="mobile-sidebar-close" type="button" aria-label="关闭导航" @click="mobileOpen = false">×</button>
    </div>

    <div class="sidebar-menu-scroll">
      <nav class="sidebar-nav sidebar-nav--main" aria-label="工作台导航">
        <button
          v-for="item in mainItems"
          :key="item.id"
          :class="['nav-item', `nav-item--${item.iconTone}`, { active: isActive(item) }, dragClasses(item)]"
          type="button"
          :aria-current="isActive(item) ? 'page' : undefined"
          :draggable="canDrag(item)"
          :title="canDrag(item) ? '拖动可调整顺序' : undefined"
          @click="selectMenu(item)"
          @dragstart="handleNavDragStart($event, item)"
          @dragover="handleNavDragOver($event, item)"
          @drop="handleNavDrop($event, item)"
          @dragend="handleNavDragEnd"
        >
          <span class="nav-item__icon">
            <span v-if="item.iconText" class="nav-item__icon-text">{{ item.iconText }}</span>
            <el-icon v-else-if="item.icon"><component :is="item.icon" /></el-icon>
          </span>
          <span class="nav-item__label">{{ item.label }}</span>
          <span v-if="item.statusDot" class="nav-item__status" aria-hidden="true"></span>
        </button>
      </nav>
    </div>

    <nav v-if="footerItems.length" class="sidebar-nav sidebar-nav--footer" aria-label="辅助导航">
      <button
        v-for="item in footerItems"
        :key="item.id"
        :class="['nav-item', `nav-item--${item.iconTone}`, { active: isActive(item) }]"
        type="button"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="selectMenu(item)"
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
