// 轨道交通项目型销售全生命周期阶段。前三段“定义项目”、后三段“赢得项目”，
// 与后端 OPPORTUNITY_STAGES 保持一致（顺序、名称完全对应）。
export interface OpportunityStageMeta {
  name: string
  phase: string
  cycle: string
  cycleMonths: number // 预计周期（月），用于时间管控推算；0 表示不明确
  works: string[]     // 主要工作（可勾选完成）
  outputs: string[]   // 主要输出（证明材料的交付项）
  group: 'define' | 'win'
}

export const OPPORTUNITY_STAGES: OpportunityStageMeta[] = [
  { name: '立项阶段', phase: '阶段一', cycle: '不明确', cycleMonths: 0, group: 'define',
    works: ['项目建议书', '可研', '立项批复', '初步设计', '需求 / 技术路线 / 投资估算前期论证'],
    outputs: ['方向性技术方案', '五大论证', '深度控制'] },
  { name: '初设阶段', phase: '阶段二', cycle: '约 1 个月', cycleMonths: 1, group: 'define',
    works: ['初步设计', '项目估算 / 概算', '送审', '初步设计评审'],
    outputs: ['初步设计方案', '项目概算报告', '评审意见'] },
  { name: '招标（深化）设计', phase: '阶段三', cycle: '约 8 个月', cycleMonths: 8, group: 'define',
    works: ['用户需求书引导（深化设计）', '控制价确认', '招标时间确认'],
    outputs: ['用户需求书 / 招标图', '招标控制价', '招标时间计划', '概价 / 总概表'] },
  { name: '招标执行', phase: '阶段四', cycle: '约 2 个月', cycleMonths: 2, group: 'win',
    works: ['招标公示', '招投标', '中标谈判（第三方造价）'],
    outputs: ['公示公告', '投标文件 + 报价', '谈判结果'] },
  { name: '设计联络阶段', phase: '阶段五', cycle: '约 3 个月', cycleMonths: 3, group: 'win',
    works: ['合同谈判', '设计联络（三次）'],
    outputs: ['合同谈判纪要', '设计联络纪要'] },
  { name: '合同签订', phase: '阶段六', cycle: '约 2 个月', cycleMonths: 2, group: 'win',
    works: ['合同条款沟通', '合同签订'],
    outputs: ['合同草签', '正式合同'] },
]

export const OPPORTUNITY_STAGE_NAMES = OPPORTUNITY_STAGES.map(s => s.name)
export const OPPORTUNITY_STAGE_STATUS = ['未开始', '进行中', '已完成', '已暂停'] as const
export type OpportunityStageStatus = (typeof OPPORTUNITY_STAGE_STATUS)[number]
