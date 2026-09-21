import type { Component } from 'vue'
import {
  Calendar,
  Collection,
  Microphone,
  Connection,
  Grid,
  HomeFilled,
  Message,
  Notebook,
  Opportunity,
  Ship,
  Reading,
  Setting,
  Tools,
  UserFilled,
  Suitcase,
  Tickets,
  FolderOpened,
  Management,
  Coin,
} from '@element-plus/icons-vue'
import type { User } from '../services/personalWorkApi'

export type MenuId =
  | 'dashboard'
  | 'assistants'
  | 'weekly'
  | 'trip'
  | 'writing'
  | 'diary'
  | 'forum'
  | 'workorder'
  | 'news'
  | 'mailassistant'
  | 'meeting'
  | 'knowledge'
  | 'project'
  | 'crm'
  | 'ledger'
  | 'cashflow'
  | 'workflow'
  | 'reimbursement'
  | 'lobsterbase'
  | 'mailconfig'
  | 'config'
  | 'skills'
  | 'usermanage'
  | 'mcp'

export type SidebarIconTone = 'home' | 'blue' | 'purple' | 'green' | 'orange' | 'deep-blue' | 'line'
export type SidebarMenuGroup = 'main' | 'footer'

export interface SidebarMenuItem {
  id: MenuId
  label: string
  icon?: Component
  iconText?: string
  iconTone: SidebarIconTone
  group: SidebarMenuGroup
  roles: User['role'][]
  statusDot?: boolean
  showInSidebar?: boolean
  // 固定入口（首页、助手中心、设置）不参与个性化排序与隐藏。
  fixed?: boolean
  // 助手中心卡片展示用的能力说明与场景分类。
  description?: string
  category?: string
}

export const sidebarMenuItems: SidebarMenuItem[] = [
  { id: 'dashboard', label: '首页', icon: HomeFilled, iconTone: 'home', group: 'main', roles: ['member', 'admin', 'superadmin'], fixed: true },
  { id: 'assistants', label: '助手中心', icon: Grid, iconTone: 'home', group: 'footer', roles: ['member', 'admin', 'superadmin'], fixed: true, description: '挑选、编排、管理你的专属办公智能体' },
  { id: 'writing', label: '智能写作', icon: Notebook, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '报告与写作', description: '素材上传、提纲生成、内容生成改写与文档导出，可引用知识库辅助写作' },
  { id: 'weekly', label: '周报助手', icon: Calendar, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '报告与写作', description: '汇总一周工作，自动生成周报表格并支持编辑后邮件发送' },
  { id: 'trip', label: '出差报告助手', icon: Suitcase, iconTone: 'purple', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '报告与写作', description: '按模板生成出差报告，行程、成果一键成文并推送邮件' },
  { id: 'diary', label: '工作日记', icon: Notebook, iconTone: 'green', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '记录每日工作，支持按时间段汇总回顾，为周报提供素材' },
  { id: 'forum', label: '金点子论坛', icon: Opportunity, iconTone: 'orange', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '团队创意与建议的发布、讨论与沉淀空间' },
  // 工单系统是跨助手的反馈 / 支持工具，不作为导航功能项；入口放在顶栏，路由仍有效。
  { id: 'workorder', label: '工单系统', icon: Tickets, iconTone: 'deep-blue', group: 'main', roles: ['member', 'admin', 'superadmin'], showInSidebar: false },
  { id: 'news', label: '每日资讯', icon: Reading, iconTone: 'deep-blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '信息与沟通', description: '聚合行业站点与微信公众号，按主题定时生成资讯简报' },
  { id: 'mailassistant', label: '邮件助手', icon: Message, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '信息与沟通', description: '收发邮件、AI 摘要与回复草拟，多账户统一管理' },
  { id: 'meeting', label: '会议助手', icon: Microphone, iconTone: 'purple', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '知识与会议', description: '会议录音转写、翻译与纪要生成，一键归档' },
  { id: 'knowledge', label: '知识库', icon: Collection, iconTone: 'deep-blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '知识与会议', description: '上传文档构建个人知识库，检索问答带引用溯源' },
  { id: 'project', label: '项目助手', icon: FolderOpened, iconTone: 'purple', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '管理项目成员、角色、资料与项目日报周报时间线' },
  { id: 'crm', label: '客户经营助手', icon: Connection, iconTone: 'deep-blue', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '五层建模客户关系资产，关系强度评分、衰减预警与项目作战地图' },
  { id: 'ledger', label: '经营管理台账', icon: Management, iconTone: 'orange', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '集中管理项目合同、采购交付、验收回款与经营风险' },
  { id: 'cashflow', label: '资金测算助手', icon: Coin, iconTone: 'green', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '按区域、客户与项目测算回款节奏、资金缺口和垫资成本' },
  { id: 'workflow', label: '工作流中心', icon: Connection, iconTone: 'purple', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '流程编排', description: '可视化编排智能体工作流，把多步任务自动串起来' },
  { id: 'reimbursement', label: '报销助手', icon: Tickets, iconTone: 'orange', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '协作与效率', description: '发票收集识别、附件合并与报销材料一键整理' },
  { id: 'lobsterbase', label: '龙虾基地', icon: Ship, iconTone: 'green', group: 'main', roles: ['member', 'admin', 'superadmin'], category: '流程编排', description: '连接龙虾平台的自定义智能体，扩展更多自动化能力' },
  { id: 'config', label: '设置', icon: Setting, iconTone: 'line', group: 'footer', roles: ['member', 'admin', 'superadmin'], fixed: true },
  { id: 'mailconfig', label: '邮件配置', icon: Message, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'], showInSidebar: false },
  { id: 'skills', label: '系统 Skill', icon: Tools, iconTone: 'line', group: 'footer', roles: ['superadmin'], showInSidebar: false },
  { id: 'usermanage', label: '用户管理', icon: UserFilled, iconTone: 'line', group: 'footer', roles: ['superadmin'], showInSidebar: false },
  { id: 'mcp', label: 'MCP 服务', icon: Connection, iconTone: 'line', group: 'footer', roles: ['admin', 'superadmin'], showInSidebar: false },
]

export function isMenuId(value: string): value is MenuId {
  return sidebarMenuItems.some((item) => item.id === value)
}

export function hasAssistantPermission(menuId: string, user: User) {
  return user.role === 'superadmin' || (user.assistant_permissions?.[menuId] ?? !['crm', 'ledger', 'cashflow'].includes(menuId))
}

export function isMenuVisible(menuId: MenuId, user: User) {
  if (!hasAssistantPermission(menuId, user)) return false
  // 设置类隐藏路由进入设置页后再按 tab 权限渲染。
  if (['config', 'mailconfig', 'skills', 'usermanage', 'mcp'].includes(menuId)) return true
  return sidebarMenuItems.some((item) => item.id === menuId && item.roles.includes(user.role))
}

export function visibleMenuItems(user: User) {
  return sidebarMenuItems.filter((item) => item.roles.includes(user.role) && hasAssistantPermission(item.id, user) && item.showInSidebar !== false)
}

// 可被用户个性化（排序 / 隐藏）的助手：主导航里除固定入口外的全部条目。
export function customizableMenuItems(user: User) {
  return visibleMenuItems(user).filter((item) => item.group === 'main' && !item.fixed)
}

// 助手中心目录的场景分组展示顺序。
export const assistantCategories = ['报告与写作', '信息与沟通', '知识与会议', '流程编排', '协作与效率']

export function defaultMenuForUser(user: User) {
  return isMenuVisible('dashboard', user) ? 'dashboard' : visibleMenuItems(user)[0].id
}

// 记住最后访问的菜单，重新进入站点时恢复到上次操作的界面而不是固定页。
const LAST_MENU_KEY = 'ai-office-last-menu'

export function rememberLastMenu(menuId: MenuId) {
  try {
    localStorage.setItem(LAST_MENU_KEY, menuId)
  } catch {
    // localStorage 不可用（隐私模式等）时静默忽略
  }
}

export function lastVisitedMenu(): MenuId {
  try {
    const saved = localStorage.getItem(LAST_MENU_KEY) || ''
    if (isMenuId(saved)) return saved
  } catch {
    // ignore
  }
  return 'dashboard'
}
