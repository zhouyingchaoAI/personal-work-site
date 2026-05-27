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

export interface HomeFeatureItem {
  id: string
  label: string
  description: string
  image: string
  tone: HomeFeatureTone
  menuId: MenuId
}

export interface HomeTodoItem {
  id: string
  title: string
  time: string
  checked?: boolean
}

export interface HomeRecordItem {
  id: string
  title: string
  tag: string
  time: string
  iconText: string
  tone: HomeRecordTone
  menuId: MenuId
}

export interface HomeAssistantAction {
  id: string
  label: string
  menuId?: MenuId
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

export const homeTodos: HomeTodoItem[] = [
  { id: 'weekly', title: '完成周报撰写', time: '09:30' },
  { id: 'trip', title: '出差行程确认', time: '10:00' },
  { id: 'project', title: '项目周例会', time: '14:00' },
  { id: 'schedule', title: '日程提交审核', time: '16:00' },
  { id: 'news', title: '查看每日资讯', time: '17:00' },
]

export const homeRecords: HomeRecordItem[] = [
  { id: 'weekly-19', title: '第 19 周工作周报', tag: '周报助手', time: '今天 09:28', iconText: 'W', tone: 'word', menuId: 'weekly' },
  { id: 'trip-shanghai', title: '上海出差报告_2024.05.16-05.18', tag: '出差报告助手', time: '昨天 18:42', iconText: 'X', tone: 'excel', menuId: 'trip' },
  { id: 'diary-0516', title: '5月16日 工作日记', tag: '工作日记', time: '昨天 17:15', iconText: 'W', tone: 'word', menuId: 'diary' },
  { id: 'forum-ai', title: '关于推进智能化项目的金点子', tag: '金点子论坛', time: '昨天 15:33', iconText: 'Ai', tone: 'idea', menuId: 'forum' },
  { id: 'mail-meeting', title: '会议纪要确认与跟进事项', tag: '邮件助手', time: '5月15日 16:07', iconText: '', tone: 'mail', menuId: 'mailassistant' },
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
