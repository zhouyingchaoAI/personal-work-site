import type { BusinessSheet } from '../../../src/services/personalWorkApi'

export function taskEvidence(row: Record<string, any>, kind: string) {
  const fields = kind === '订货'
    ? ['合同签订金额(万元)', '合同签订金额']
    : kind === '回款' ? ['实际回款金额（元）', '已回款金额（元）', '实际回款金额'] : ['确认收入金额', '已确认收入金额']
  const amount = fields.map(key => row[key]).find(value => value !== null && value !== undefined && value !== '' && typeof value !== 'boolean' && Number.isFinite(Number(value)))
  const dateFields = kind === '订货' ? ['合同签订时间', '合同签订日期'] : kind === '回款' ? ['回款日期', '回款时间'] : ['收入确认日期', '业务日期']
  const codeFields = kind === '订货' ? ['销售合同编码', '销售合同编号', '合同编号'] : kind === '回款' ? ['到账流水号', '回款凭证号', '单据编号'] : ['单据编号', '收入确认单号']
  const hasDate = dateFields.some(key => /^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(String(row[key] || '')))
  const hasCode = codeFields.some(key => String(row[key] || '').trim())
  const flags = ['是否已签合同', '是否已回款', '是否已确认收入'].some(key => [true, 1, '1', '是', '已完成', '已回款'].includes(row[key]))
  if (amount !== undefined && Number(amount) > 0 && hasDate && hasCode) return '待核验凭证'
  return flags || (amount !== undefined && Number(amount) > 0) ? '待补证据' : '未提供完成证据'
}

export function businessDataQuality(sheets: BusinessSheet[]) {
  const issues: { source: string; row: number; item: string; detail: string; action: string }[] = []
  const records = (key: string) => {
    const sheet = sheets.find(item => item.key === key)
    return sheet?.rows.map(row => Object.fromEntries(sheet.headers.map((header, index) => [header, row[index]]))) || []
  }
  const number = (value: unknown) => value !== null && value !== undefined && value !== '' && typeof value !== 'boolean' && Number.isFinite(Number(value)) ? Number(value) : null
  for (const sheet of sheets) {
    if (/历史版本|沿用历史/.test(sheet.source || '')) issues.push({ source: sheet.key, row: 0, item: '历史来源', detail: sheet.source, action: '核对统计截止日期，不与最新累计混算' })
    const kind = ({ 订货任务令: '订货', 回款任务令: '回款', 财务收入任务令: '财务收入' } as Record<string,string>)[sheet.key]
    sheet.rows.forEach((values, index) => {
      const row = Object.fromEntries(sheet.headers.map((header, column) => [header, values[column]]))
      if (['区域', '项目归属', '*项目归属', '区域归属', '区域组织', '平台'].some(key => row[key] === '归属待核验')) {
        issues.push({ source: sheet.key, row: index + 1, item: '旧区域归属待核验', detail: String(row['原区域归属'] || '未确定'), action: '确认东区（浙北/浙南/江苏）、西区、中区或广东区归属；保留金额，不凭名称分摊' })
      }
      if (kind && taskEvidence(row, kind) !== '未提供完成证据') issues.push({ source: sheet.key, row: index + 1, item: taskEvidence(row, kind), detail: String(row['*机会点名称'] || row['销售子项目名称'] || row['机会点/子项目名称'] || '任务记录'), action: '核对合同/到账/收入凭证、实际金额及日期；不按勾选状态认定完成' })
      if (sheet.key === '16_机会点清单' || sheet.key.startsWith('19_')) {
        const region = String(row['项目归属'] || '').trim()
        if (!/^(东区|西区|中区|广东|上海|铁路先遣队|公司[-－]?其他)/.test(region)) issues.push({ source: sheet.key, row: index + 1, item: '区域待确认', detail: region || '区域为空', action: '按项目归属映射区域；产业标签不能替代区域' })
      }
      if (sheet.key.startsWith('19_') && !row['销售合同编码']) issues.push({ source: sheet.key, row: index + 1, item: '合同关联缺失', detail: String(row['销售项目名称'] || row['销售子项目名称'] || '订单记录'), action: '补齐唯一合同编码后逐笔对账，不按名称自动合并' })
    })
  }
  const task = records('任务令公司进度')
  const comparisons = records('01_核心指标总览').flatMap(row => {
    const match = task.find(item => item['指标'] === row['指标'])
    const actual = number(row['实际完成']), other = number(match?.['1-10月完成'])
    return actual === null || other === null ? [] : [{ metric: String(row['指标']), actual, task: other, difference: actual - other }]
  })
  const differences = comparisons.filter(row => Math.abs(row.difference) > .01)
  for (const row of differences) issues.push({ source: '核心指标 / 任务令公司进度', row: 0, item: '累计值待对账', detail: `${row.metric}差异 ${row.difference.toFixed(2)} 万元`, action: '先确认统计期间和范围，再核对调整项；不自动取较大值' })
  return { issues, comparisons }
}
