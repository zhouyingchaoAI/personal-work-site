import type { Component } from 'vue'
import {
  Calendar,
  Connection,
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
} from '@element-plus/icons-vue'
import type { User } from '../services/personalWorkApi'

export type MenuId =
  | 'dashboard'
  | 'weekly'
  | 'trip'
  | 'diary'
  | 'forum'
  | 'news'
  | 'mailassistant'
  | 'lobsterbase'
  | 'help'
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
}

export const sidebarMenuItems: SidebarMenuItem[] = [
  { id: 'dashboard', label: '首页', icon: HomeFilled, iconTone: 'home', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'weekly', label: '周报助手', icon: Calendar, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'trip', label: '出差报告助手', icon: Suitcase, iconTone: 'purple', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'diary', label: '工作日记', icon: Notebook, iconTone: 'green', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'forum', label: '金点子论坛', icon: Opportunity, iconTone: 'orange', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'news', label: '每日资讯', icon: Reading, iconTone: 'deep-blue', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'mailassistant', label: '邮件助手', icon: Message, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'lobsterbase', label: '龙虾基地', icon: Ship, iconTone: 'green', group: 'main', roles: ['member', 'admin', 'superadmin'] },
  { id: 'config', label: '设置', icon: Setting, iconTone: 'line', group: 'footer', roles: ['member', 'admin', 'superadmin'] },
  // { id: 'help', label: '帮助与反馈', icon: QuestionFilled, iconTone: 'line', group: 'footer', roles: ['member', 'admin', 'superadmin'] },
  { id: 'mailconfig', label: '邮件配置', icon: Message, iconTone: 'blue', group: 'main', roles: ['member', 'admin', 'superadmin'], showInSidebar: false },
  { id: 'skills', label: '系统 Skill', icon: Tools, iconTone: 'line', group: 'footer', roles: ['superadmin'], showInSidebar: false },
  { id: 'usermanage', label: '用户管理', icon: UserFilled, iconTone: 'line', group: 'footer', roles: ['superadmin'], showInSidebar: false },
  { id: 'mcp', label: 'MCP 服务', icon: Connection, iconTone: 'line', group: 'footer', roles: ['admin', 'superadmin'], showInSidebar: false },
]

export function isMenuId(value: string): value is MenuId {
  return sidebarMenuItems.some((item) => item.id === value)
}

export function isMenuVisible(menuId: MenuId, user: User) {
  // 设置类隐藏路由进入设置页后再按 tab 权限渲染。
  if (['config', 'mailconfig', 'skills', 'usermanage', 'mcp'].includes(menuId)) return true
  return sidebarMenuItems.some((item) => item.id === menuId && item.roles.includes(user.role))
}

export function visibleMenuItems(user: User) {
  return sidebarMenuItems.filter((item) => item.roles.includes(user.role) && item.showInSidebar !== false)
}

export function defaultMenuForUser(user: User) {
  return isMenuVisible('weekly', user) ? 'weekly' : visibleMenuItems(user)[0].id
}
