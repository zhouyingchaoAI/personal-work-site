// 成单概率模型：以“所处阶段”为主基准，融合登记赢率，再由“动作 + 材料支撑”做调节。
// 目标是让概率可解释——每个数字都能说清依据（reasons）与缺口（gaps），而不是拍脑袋。
import type { CrmOpportunity } from '../../../src/services/personalWorkApi'
import { OPPORTUNITY_STAGES } from './opportunityStages'

// 各生命周期阶段的基准成单概率（越靠后越接近成单）。
const STAGE_BASE: Record<string, number> = {
  立项阶段: 10, 初设阶段: 25, '招标（深化）设计': 45, 招标执行: 65, 设计联络阶段: 82, 合同签订: 95,
}

export type ProbabilitySupport = 'strong' | 'medium' | 'weak'
export interface OpportunityProbability {
  probability: number
  stageBase: number
  winRate: number | null
  support: ProbabilitySupport
  evidence: { materials: number; contacts: number; followups: number; stagesWithEvidence: number; reachedStages: number }
  reasons: string[]
  gaps: string[]
}

function parseWinRate(v?: string): number | null {
  if (!v) return null
  const m = String(v).match(/(\d+(?:\.\d+)?)/)
  if (!m) return null
  return Math.max(0, Math.min(100, Number(m[1])))
}

export function opportunityProbability(o: CrmOpportunity, followupsCount = 0): OpportunityProbability {
  const stage = o.sales_stage || ''
  const stageIndex = OPPORTUNITY_STAGES.findIndex(s => s.name === stage)
  const stageBase = STAGE_BASE[stage] ?? 15
  const winRate = parseWinRate(o.win_rate)
  const prog = o.stage_progress || {}
  let materials = 0, contacts = 0, stagesWithEvidence = 0
  for (const s of Object.values(prog)) {
    const m = s.attachments?.length || 0
    const c = s.contacts?.length || 0
    materials += m; contacts += c
    if (m + c > 0) stagesWithEvidence++
  }
  const reachedStages = stageIndex >= 0 ? stageIndex + 1 : 1
  const coverage = reachedStages ? stagesWithEvidence / reachedStages : 0
  // 阶段基准为主(60%)、登记赢率为辅(40%)。
  let base = winRate != null ? stageBase * 0.6 + winRate * 0.4 : stageBase
  // 证据调节：动作/材料越充分越可信，反之打折。
  let adj = 0
  if (coverage >= 0.6) adj += 6
  else if (coverage < 0.2) adj -= 8
  if (materials === 0 && contacts === 0) adj -= 6
  if (followupsCount > 0) adj += 3
  let probability = Math.max(2, Math.min(98, Math.round(base + adj)))
  if (o.outcome === 'won') probability = 100
  if (o.outcome === 'lost' || o.cancelled) probability = 0

  const evidenceTotal = materials + contacts
  const support: ProbabilitySupport = coverage >= 0.6 && evidenceTotal >= 3 ? 'strong' : evidenceTotal > 0 ? 'medium' : 'weak'

  const reasons: string[] = []
  if (stage) reasons.push(`处于「${stage}」，阶段基准约 ${stageBase}%`)
  if (winRate != null) reasons.push(`登记赢率 ${winRate}%`)
  if (materials) reasons.push(`已上传 ${materials} 份证明 / 输出材料`)
  if (contacts) reasons.push(`已登记 ${contacts} 位阶段关系人`)
  if (followupsCount) reasons.push(`有 ${followupsCount} 项跟进在推进`)
  if (!reasons.length) reasons.push('信息不足，按阶段给出保守基准')

  const gaps: string[] = []
  if (materials === 0) gaps.push('尚无阶段证明材料，概率支撑不足')
  if (contacts === 0) gaps.push('尚无阶段关系人，决策链未覆盖')
  if (coverage < 0.5 && reachedStages > 1) gaps.push('已推进阶段的材料 / 关系人支撑不完整')
  if (winRate == null) gaps.push('未登记赢率')

  return { probability, stageBase, winRate, support, evidence: { materials, contacts, followups: followupsCount, stagesWithEvidence, reachedStages }, reasons, gaps }
}

// 联网核对时间点：构造一个面向招标/中标公告的检索链接，用真实互联网信息核对商机时间与真伪。
export function opportunityVerifyUrl(o: CrmOpportunity): string {
  const year = (o.bid_date || o.contract_date || '').match(/(\d{4})/)?.[1] || ''
  const query = [o.name, o.owner_unit, '招标 中标公告', year].filter(Boolean).join(' ')
  return `https://www.baidu.com/s?wd=${encodeURIComponent(query)}`
}

export const PROBABILITY_SUPPORT_LABEL: Record<ProbabilitySupport, string> = { strong: '支撑充分', medium: '支撑一般', weak: '支撑不足' }
