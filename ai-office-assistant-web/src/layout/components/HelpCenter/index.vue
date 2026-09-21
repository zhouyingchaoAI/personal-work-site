<script setup lang="ts">
import { computed, nextTick, ref, watch, type Component } from 'vue'
import {
  Compass,
  Grid,
  HomeFilled,
  Message,
  Search,
  Setting,
  Tools,
  UserFilled,
  Connection,
  QuestionFilled,
} from '@element-plus/icons-vue'
import { authState } from '../../../services/authSession'
import { assistantCategories, sidebarMenuItems, type MenuId, type SidebarIconTone } from '../../menu'
import './index.scss'

const emit = defineEmits<{
  navigate: [value: MenuId]
}>()

const open = ref(false)
const keyword = ref('')
const searchInput = ref<HTMLInputElement | null>(null)

function show() {
  open.value = true
}

defineExpose({ show })

watch(open, (value) => {
  if (value) {
    keyword.value = ''
    // 打开后自动聚焦搜索框，行为贴近 Launchpad。
    nextTick(() => searchInput.value?.focus())
  }
})

const user = computed(() => authState.user)

interface AppTile {
  id: MenuId
  label: string
  description: string
  icon: Component
  tone: SidebarIconTone
  category: string
}

const MANAGE_CATEGORY = '管理与配置'

// 基础导航入口，作为「常用」应用置顶展示。
const baseTiles = computed<AppTile[]>(() => {
  const assistants = sidebarMenuItems.find((item) => item.id === 'assistants')
  return [
    { id: 'dashboard', label: '首页', description: '工作台首页，汇总近期动态与常用入口。', icon: HomeFilled, tone: 'home', category: '常用' },
    {
      id: 'assistants',
      label: '助手中心',
      description: assistants?.description || '挑选、编排、管理你的专属办公智能体。',
      icon: Grid,
      tone: 'home',
      category: '常用',
    },
  ]
})

// 各业务助手，直接复用导航配置里的图标、色调与说明。
const assistantTiles = computed<AppTile[]>(() =>
  sidebarMenuItems
    .filter((item) => item.group === 'main' && item.showInSidebar !== false && item.category && item.description && item.icon)
    .map((item) => ({
      id: item.id,
      label: item.label,
      description: item.description as string,
      icon: item.icon as Component,
      tone: item.iconTone,
      category: item.category as string,
    })),
)

// 侧边栏隐藏的管理 / 配置模块，按当前账号权限展示，权限口径与「设置中心」一致。
const manageTiles = computed<AppTile[]>(() => {
  const isAdmin = !!user.value?.is_admin
  const isSuperadmin = !!user.value?.is_superadmin
  const all: Array<AppTile & { visible: boolean }> = [
    { id: 'mailconfig', label: '邮件配置', description: '配置企业 / 个人邮箱的 SMTP、IMAP 与签名，供各助手统一收发邮件。', icon: Message, tone: 'blue', category: MANAGE_CATEGORY, visible: true },
    { id: 'config', label: '系统配置', description: '维护大模型、语音、知识库等平台级参数，是各助手运行的基础配置。', icon: Setting, tone: 'line', category: MANAGE_CATEGORY, visible: isAdmin },
    { id: 'mcp', label: 'MCP 服务', description: '生成 MCP 密钥与接入配置，让 Claude 等客户端调用平台各助手能力。', icon: Connection, tone: 'purple', category: MANAGE_CATEGORY, visible: isAdmin },
    { id: 'skills', label: '系统 Skill', description: '查看与调试平台内置 Skill 能力，验证各业务模块的自动化技能。', icon: Tools, tone: 'line', category: MANAGE_CATEGORY, visible: isSuperadmin },
    { id: 'usermanage', label: '用户管理', description: '新增、编辑账号并分配成员 / 管理员权限，统一管理团队成员。', icon: UserFilled, tone: 'line', category: MANAGE_CATEGORY, visible: isSuperadmin },
  ]
  return all.filter((item) => item.visible).map(({ visible: _visible, ...tile }) => tile)
})

const allTiles = computed<AppTile[]>(() => [...baseTiles.value, ...assistantTiles.value, ...manageTiles.value])

const categoryOrder = computed(() => ['常用', ...assistantCategories, MANAGE_CATEGORY])

// 未搜索时按分类分组展示（App 资源库风格）。
const groupedTiles = computed(() =>
  categoryOrder.value
    .map((category) => ({ category, items: allTiles.value.filter((tile) => tile.category === category) }))
    .filter((group) => group.items.length > 0),
)

const searching = computed(() => keyword.value.trim().length > 0)

// 搜索时跨全部应用平铺匹配结果（Launchpad 搜索风格）。
const searchResults = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return []
  return allTiles.value.filter((tile) => `${tile.label} ${tile.description}`.toLowerCase().includes(q))
})

function launch(id: MenuId) {
  emit('navigate', id)
  open.value = false
}

interface FaqItem {
  question: string
  answer: string
}

const faqItems: FaqItem[] = [
  {
    question: '如何配置发送 / 接收邮件的邮箱？',
    answer: '进入「设置 → 邮件配置」，分别填写企业邮箱与个人邮箱的 SMTP / IMAP 信息并测试连接，周报、出差报告、邮件助手都会使用这里的账号。',
  },
  {
    question: '导航栏怎么调整顺序或找不到某个助手？',
    answer: '左侧导航支持拖拽排序，直接把助手拖到想要的位置即可；也可以在这里点击任意应用磁贴直接打开。',
  },
  {
    question: '知识库、会议、写作等功能需要先做什么？',
    answer: '首次使用建议先在「设置」中完成模型与相关服务的配置，再上传素材或录音，功能即可正常生成结果并带引用溯源。',
  },
  {
    question: '如何把办公助手接入 Claude / MCP 客户端？',
    answer: '管理员可在「设置 → MCP 服务」生成密钥并复制接入配置，按说明填入客户端后即可通过 MCP 调用各助手能力。',
  },
  {
    question: '忘记密码或需要开通账号怎么办？',
    answer: '账号由管理员统一开通与管理，如需重置密码或调整权限，请联系本平台的管理员处理。',
  },
]

const compassIcon = Compass
</script>

<template>
  <el-dialog
    v-model="open"
    class="help-center-dialog"
    fullscreen
    append-to-body
    :show-close="true"
  >
    <template #header>
      <div class="help-center__header">
        <div class="help-center__heading">
          <span class="help-center__badge"><el-icon><QuestionFilled /></el-icon></span>
          <div>
            <h2>帮助中心</h2>
            <p>浏览全部办公助手与管理模块，点击即可直达。</p>
          </div>
        </div>
        <div class="help-center__search">
          <el-icon class="help-center__search-icon"><Search /></el-icon>
          <input
            ref="searchInput"
            v-model="keyword"
            type="text"
            placeholder="搜索助手、功能或模块…"
            aria-label="搜索助手"
          />
          <button v-if="keyword" class="help-center__search-clear" type="button" aria-label="清空" @click="keyword = ''">×</button>
        </div>
      </div>
    </template>

    <div class="help-center__scroll">
      <div class="help-center__body">
        <!-- 搜索结果：跨分类平铺 -->
        <section v-if="searching" class="help-center__section">
          <h3 class="help-center__section-title">搜索结果 · {{ searchResults.length }}</h3>
          <div v-if="searchResults.length" class="help-grid">
            <button v-for="tile in searchResults" :key="tile.id" class="help-tile" :class="`help-tile--${tile.tone}`" type="button" @click="launch(tile.id)">
              <span class="help-tile__icon"><el-icon><component :is="tile.icon" /></el-icon></span>
              <span class="help-tile__label">{{ tile.label }}</span>
              <span class="help-tile__desc">{{ tile.description }}</span>
            </button>
          </div>
          <p v-else class="help-center__empty">没有找到匹配的助手，换个关键词试试。</p>
        </section>

        <!-- 默认：App 资源库分类视图 -->
        <template v-else>
          <section v-for="group in groupedTiles" :key="group.category" class="help-center__section">
            <h3 class="help-center__section-title">
              {{ group.category }}
              <span v-if="group.category === MANAGE_CATEGORY" class="help-center__section-tag">按权限展示</span>
            </h3>
            <div class="help-grid">
              <button v-for="tile in group.items" :key="tile.id" class="help-tile" :class="`help-tile--${tile.tone}`" type="button" @click="launch(tile.id)">
                <span class="help-tile__icon"><el-icon><component :is="tile.icon" /></el-icon></span>
                <span class="help-tile__label">{{ tile.label }}</span>
                <span class="help-tile__desc">{{ tile.description }}</span>
              </button>
            </div>
          </section>

          <section class="help-center__section">
            <h3 class="help-center__section-title">常见问题</h3>
            <el-collapse class="help-faq">
              <el-collapse-item v-for="(faq, index) in faqItems" :key="index" :name="index">
                <template #title>
                  <span class="help-faq__q">{{ faq.question }}</span>
                </template>
                <p class="help-faq__a">{{ faq.answer }}</p>
              </el-collapse-item>
            </el-collapse>
          </section>

          <section class="help-center__footer-tip">
            <el-icon><component :is="compassIcon" /></el-icon>
            <span>还有其他问题？可通过「金点子论坛」反馈，或联系平台管理员协助处理。</span>
          </section>
        </template>
      </div>
    </div>
  </el-dialog>
</template>
