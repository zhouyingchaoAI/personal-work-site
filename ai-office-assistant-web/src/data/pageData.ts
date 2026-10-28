import homeDiaryIcon from '../assets/home-feature-diary.png'
import homeForumIcon from '../assets/home-feature-forum.png'
import homeMailIcon from '../assets/home-feature-mail.png'
import homeNewsIcon from '../assets/home-feature-news.png'
import homeTripIcon from '../assets/home-feature-trip.png'
import homeWeeklyIcon from '../assets/home-feature-weekly.png'
import homeWritingIcon from '../assets/home-assistants/writing.svg'
import homeMeetingIcon from '../assets/home-assistants/meeting.svg'
import homeKnowledgeIcon from '../assets/home-assistants/knowledge.svg'
import homeProjectIcon from '../assets/home-assistants/project.svg'
import homeCrmIcon from '../assets/home-assistants/crm.svg'
import homeLedgerIcon from '../assets/home-assistants/ledger.svg'
import homeCashflowIcon from '../assets/home-assistants/cashflow.svg'
import homeDatacenterIcon from '../assets/home-assistants/datacenter.svg'
import homeWorkflowIcon from '../assets/home-assistants/workflow.svg'
import homeReimbursementIcon from '../assets/home-assistants/reimbursement.svg'
import homeLobsterbaseIcon from '../assets/home-assistants/lobsterbase.svg'
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
  { id: 'writing', menuId: 'writing', label: '智能写作', description: '提纲成文，智能润色改写', image: homeWritingIcon, tone: 'blue' },
  { id: 'meeting', menuId: 'meeting', label: '会议助手', description: '录音转写，自动整理纪要', image: homeMeetingIcon, tone: 'blue' },
  { id: 'knowledge', menuId: 'knowledge', label: '知识库', description: '知识沉淀，问答有据可循', image: homeKnowledgeIcon, tone: 'blue' },
  { id: 'project', menuId: 'project', label: '项目助手', description: '汇集成员资料，协同项目推进', image: homeProjectIcon, tone: 'blue' },
  { id: 'crm', menuId: 'crm', label: '联指经营助手', description: '经营客户关系，把握商机进展', image: homeCrmIcon, tone: 'blue' },
  { id: 'ledger', menuId: 'ledger', label: '项目管理台账', description: '合同交付回款，一本台账掌握', image: homeLedgerIcon, tone: 'blue' },
  { id: 'cashflow', menuId: 'cashflow', label: '资金测算助手', description: '测算回款节奏，识别资金缺口', image: homeCashflowIcon, tone: 'blue' },
  { id: 'datacenter', menuId: 'datacenter', label: '数据中台', description: '统览数据资产，守护备份安全', image: homeDatacenterIcon, tone: 'blue' },
  { id: 'workflow', menuId: 'workflow', label: '工作流中心', description: '串联任务步骤，编排自动流程', image: homeWorkflowIcon, tone: 'blue' },
  { id: 'reimbursement', menuId: 'reimbursement', label: '报销助手', description: '识别归集发票，整理报销材料', image: homeReimbursementIcon, tone: 'blue' },
  { id: 'lobsterbase', menuId: 'lobsterbase', label: '龙虾基地', description: '连接专属智能体，扩展办公能力', image: homeLobsterbaseIcon, tone: 'blue' },
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
    title: '公共资讯与个人资讯',
    description: '公共资讯仅超级管理员配置、全站共享；个人资讯每个账号配置自己的来源并定期自动推送，两者分开展示。',
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
