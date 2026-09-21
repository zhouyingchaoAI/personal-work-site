<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Hide, Plus, Rank, RefreshLeft, TopRight } from '@element-plus/icons-vue'
import { authState } from '../../services/authSession'
import {
  assistantCategories,
  customizableMenuItems,
  type MenuId,
  type SidebarMenuItem,
} from '../../layout/menu'
import {
  hideAssistant,
  navPrefsState,
  orderedCustomItems,
  reorderVisibleAssistants,
  resetNavPrefs,
  showAssistant,
} from '../../layout/navPrefs'
import './index.scss'

const router = useRouter()
const user = computed(() => authState.user)
const catalog = computed<SidebarMenuItem[]>(() => (user.value ? customizableMenuItems(user.value) : []))
const visibleItems = computed(() => orderedCustomItems(catalog.value))
const hiddenItems = computed(() => catalog.value.filter((item) => navPrefsState.hidden.includes(item.id)))
const categoryGroups = computed(() =>
  assistantCategories
    .map((category) => ({ category, items: catalog.value.filter((item) => item.category === category) }))
    .filter((group) => group.items.length),
)

function isHidden(item: SidebarMenuItem) {
  return navPrefsState.hidden.includes(item.id)
}

function openAssistant(id: MenuId) {
  router.push(`/workspace/${id}`)
}

async function toggleAssistant(item: SidebarMenuItem) {
  try {
    if (isHidden(item)) {
      await showAssistant(item.id)
      ElMessage.success(`已把「${item.label}」添加到导航`)
    } else {
      await hideAssistant(item.id)
      ElMessage.success(`已暂时隐藏「${item.label}」，可随时在助手中心恢复`)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存导航偏好失败')
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('将恢复默认的助手顺序，并重新显示所有隐藏的助手。', '恢复默认导航', {
      confirmButtonText: '恢复默认',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await resetNavPrefs()
    ElMessage.success('已恢复默认导航')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存导航偏好失败')
  }
}

// 「我的导航」列表内的拖拽排序，插入位置用蓝色插入线提示。
const draggingId = ref<MenuId | ''>('')
const dropTargetId = ref<MenuId | ''>('')
const dropPosition = ref<'before' | 'after'>('before')

function handleRowDragStart(event: DragEvent, item: SidebarMenuItem) {
  draggingId.value = item.id
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', item.id)
  }
}

function handleRowDragOver(event: DragEvent, item: SidebarMenuItem) {
  if (!draggingId.value || item.id === draggingId.value) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  dropTargetId.value = item.id
  dropPosition.value = event.clientY - rect.top < rect.height / 2 ? 'before' : 'after'
}

async function handleRowDrop(event: DragEvent, item: SidebarMenuItem) {
  if (!draggingId.value || item.id === draggingId.value) return
  event.preventDefault()
  const ids = visibleItems.value.map((entry) => entry.id)
  const from = ids.indexOf(draggingId.value)
  let to = ids.indexOf(item.id)
  if (from < 0 || to < 0) return
  const dragged = draggingId.value
  ids.splice(from, 1)
  to = ids.indexOf(item.id)
  if (dropPosition.value === 'after') to += 1
  ids.splice(to, 0, dragged)
  handleRowDragEnd()
  try {
    await reorderVisibleAssistants(ids, catalog.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存导航偏好失败')
  }
}

function handleRowDragEnd() {
  draggingId.value = ''
  dropTargetId.value = ''
}

function rowClasses(item: SidebarMenuItem) {
  return {
    'is-dragging': draggingId.value === item.id,
    'drop-before': dropTargetId.value === item.id && dropPosition.value === 'before',
    'drop-after': dropTargetId.value === item.id && dropPosition.value === 'after',
  }
}
</script>

<template>
  <section class="workspace-main assistant-center">
    <header class="assistant-center__hero">
      <div class="assistant-center__hero-copy">
        <span class="assistant-center__hero-tag">智能体工厂</span>
        <h1>助手中心</h1>
        <p>像逛工厂车间一样挑选你的办公智能体：添加常用的、隐藏用不到的、拖拽排出你自己的导航。</p>
      </div>
      <div class="assistant-center__hero-stats">
        <div>
          <strong>{{ visibleItems.length }}</strong>
          <span>已启用</span>
        </div>
        <div>
          <strong>{{ hiddenItems.length }}</strong>
          <span>已隐藏</span>
        </div>
        <div>
          <strong>{{ catalog.length }}</strong>
          <span>全部助手</span>
        </div>
      </div>
    </header>

    <section class="assistant-center__panel" aria-label="我的导航">
      <div class="assistant-center__panel-head">
        <h2>我的导航</h2>
        <span class="assistant-center__panel-hint">拖到蓝色插入线处调整顺序，导航栏与此保持一致</span>
        <el-button text :icon="RefreshLeft" @click="handleReset">恢复默认</el-button>
      </div>
      <ul class="assistant-center__nav-list">
        <li
          v-for="(item, index) in visibleItems"
          :key="item.id"
          :class="['assistant-center__nav-row', rowClasses(item)]"
          draggable="true"
          @dragstart="handleRowDragStart($event, item)"
          @dragover="handleRowDragOver($event, item)"
          @drop="handleRowDrop($event, item)"
          @dragend="handleRowDragEnd"
        >
          <span class="assistant-center__nav-order">{{ index + 1 }}</span>
          <el-icon class="assistant-center__nav-grip"><Rank /></el-icon>
          <span :class="['assistant-center__nav-icon', `assistant-center__nav-icon--${item.iconTone}`]">
            <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
          </span>
          <strong>{{ item.label }}</strong>
          <div class="assistant-center__nav-actions">
            <el-button text size="small" :icon="TopRight" @click="openAssistant(item.id)">打开</el-button>
            <el-button text size="small" :icon="Hide" @click="toggleAssistant(item)">隐藏</el-button>
          </div>
        </li>
      </ul>
      <p v-if="!visibleItems.length" class="assistant-center__empty">导航里还没有助手，从下方「已隐藏的助手」或助手目录里添加吧。</p>

      <div v-if="hiddenItems.length" class="assistant-center__hidden-block">
        <h3>已隐藏的助手（{{ hiddenItems.length }}）</h3>
        <ul class="assistant-center__nav-list">
          <li v-for="item in hiddenItems" :key="item.id" class="assistant-center__nav-row is-muted">
            <span :class="['assistant-center__nav-icon', `assistant-center__nav-icon--${item.iconTone}`]">
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            </span>
            <strong>{{ item.label }}</strong>
            <div class="assistant-center__nav-actions">
              <el-button text size="small" :icon="TopRight" @click="openAssistant(item.id)">打开</el-button>
              <el-button size="small" type="primary" :icon="Plus" @click="toggleAssistant(item)">添加到导航</el-button>
            </div>
          </li>
        </ul>
      </div>
    </section>

    <section
      v-for="group in categoryGroups"
      :key="group.category"
      class="assistant-center__panel"
      :aria-label="group.category"
    >
      <div class="assistant-center__panel-head">
        <h2>{{ group.category }}</h2>
      </div>
      <div class="assistant-center__card-grid">
        <article
          v-for="item in group.items"
          :key="item.id"
          :class="['assistant-center__card', { 'is-hidden': isHidden(item) }]"
        >
          <div class="assistant-center__card-head">
            <span :class="['assistant-center__nav-icon', `assistant-center__nav-icon--${item.iconTone}`]">
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            </span>
            <strong>{{ item.label }}</strong>
            <em v-if="isHidden(item)">已隐藏</em>
            <em v-else class="is-active">已启用</em>
          </div>
          <p>{{ item.description }}</p>
          <div class="assistant-center__card-actions">
            <el-button size="small" type="primary" plain :icon="TopRight" @click="openAssistant(item.id)">
              打开
            </el-button>
            <el-button
              v-if="isHidden(item)"
              size="small"
              type="primary"
              :icon="Plus"
              @click="toggleAssistant(item)"
            >
              添加到导航
            </el-button>
            <el-button v-else size="small" :icon="Hide" @click="toggleAssistant(item)">暂时隐藏</el-button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>
