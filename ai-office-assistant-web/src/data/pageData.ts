import homeDiaryIcon from '../assets/home-feature-diary.png'
import homeForumIcon from '../assets/home-feature-forum.png'
import homeMailIcon from '../assets/home-feature-mail.png'
import homeNewsIcon from '../assets/home-feature-news.png'
import homeTripIcon from '../assets/home-feature-trip.png'
import homeWeeklyIcon from '../assets/home-feature-weekly.png'
import quickFocus from '../assets/quick-focus.png'
import type { MenuId } from '../layout/menu'

export type HomeFeatureTone = 'blue' | 'purple' | 'green' | 'orange' | 'navy' | 'mail'
export type HomeRecordTone = 'word' | 'excel' | 'diary' | 'idea' | 'mail'
export type HomeCapabilityIcon = 'report' | 'forum' | 'news' | 'mail'

export interface HomeFeatureItem {
  id: string
  label: string
  description: string
  image: string
  tone: HomeFeatureTone
  menuId: MenuId
}

export interface HomeAssistantAction {
  id: string
  label: string
  menuId?: MenuId
}

export interface HomeCapabilityItem {
  id: string
  title: string
  description: string
  icon: HomeCapabilityIcon
}

export const homeFeatures: HomeFeatureItem[] = [
  {
    id: 'weekly',
    label: '周报助手',
    description: '智能生成专业周报',
    image: homeWeeklyIcon,
    tone: 'blue',
    menuId: 'weekly',
  },
  {
    id: 'trip',
    label: '出差报告助手',
    description: '一键生成出差报告',
    image: homeTripIcon,
    tone: 'purple',
    menuId: 'trip',
  },
  {
    id: 'diary',
    label: '工作日记',
    description: '记录每天工作点滴',
    image: homeDiaryIcon,
    tone: 'green',
    menuId: 'diary',
  },
  {
    id: 'forum',
    label: '金点子论坛',
    description: '创新想法共创共享',
    image: homeForumIcon,
    tone: 'orange',
    menuId: 'forum',
  },
  {
    id: 'news',
    label: '每日资讯',
    description: '行业资讯每日精选',
    image: homeNewsIcon,
    tone: 'navy',
    menuId: 'news',
  },
  {
    id: 'mail',
    label: '邮件助手',
    description: '智能撰写与回复邮件',
    image: homeMailIcon,
    tone: 'mail',
    menuId: 'mailassistant',
  },
]

export const homeCapabilities: HomeCapabilityItem[] = [
  {
    id: 'report',
    title: '报告只在专属模块生成',
    description: '“按标准模板生成文件”仅在周报助手和出差报告助手中出现。',
    icon: 'report',
  },
  {
    id: 'forum',
    title: '论坛以浏览评论为主',
    description: '发起话题默认收起，历史话题展示热度、点赞、评论和浏览。',
    icon: 'forum',
  },
  {
    id: 'news',
    title: '资讯配置受权限保护',
    description: '普通用户只看每日资讯，只有超级管理员能配置来源和立即生成。',
    icon: 'news',
  },
  {
    id: 'mail',
    title: '邮件读取已缓存',
    description: '收件箱列表优先读缓存，点击刷新才强制重新拉取最新邮件。',
    icon: 'mail',
  },
]

export const homeAssistantActions: HomeAssistantAction[] = [
  { id: 'weekly', label: '帮我生成本周工作周报', menuId: 'weekly' },
  { id: 'meeting', label: '总结一下今天的会议要点' },
  { id: 'mail', label: '帮我写一封项目跟进邮件', menuId: 'mailassistant' },
  { id: 'news', label: '查询最新行业资讯', menuId: 'news' },
]

export const promptQuestions = [
  '帮我写一封项目启动邮件',
  '总结本周的工作重点',
  '记录今天的工作日记',
  '生成一份出差总结报告',
]

export const focusMomentImage = quickFocus
