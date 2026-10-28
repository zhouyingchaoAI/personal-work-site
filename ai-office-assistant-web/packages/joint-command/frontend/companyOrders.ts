import type { BusinessSheet } from '../../../src/services/personalWorkApi'
function records(sheet?: BusinessSheet) {
  return sheet?.rows.map(row => Object.fromEntries(sheet.headers.map((header, index) => [header, row[index]]))) || []
}
function dateParts(value: unknown) {
  const match = String(value ?? '').match(/^(\d{4})[-/年](\d{1,2})(?:[-/月]|$)/)
  if (!match || Number(match[2]) < 1 || Number(match[2]) > 12) return null
  return { year: Number(match[1]), month: Number(match[2]) }
}
function numeric(value: unknown) {
  if (value === null || value === undefined || String(value).trim() === '') return null
  const number = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(number) ? number : null
}
export function companyCashFlow(sheets: BusinessSheet[], year: number) {
  const source = records(sheets.find(sheet => sheet.key === '公司月度现金流'))
  const months = Array.from({ length: 12 }, (_, index) => {
    const matches = source.filter(row => numeric(row['年份']) === year && numeric(String(row['月份']).replace('月', '')) === index + 1)
    return { month: index + 1, cash: matches.length === 1 ? numeric(matches[0]!['经营现金流（万元）']) : null }
  })
  const supplied = months.filter(row => row.cash !== null)
  return { months, total: supplied.length ? supplied.reduce((total, row) => total + row.cash!, 0) : null, count: supplied.length, positive: supplied.filter(row => row.cash! > 0).length, negative: supplied.filter(row => row.cash! < 0).length }
}
export function companyReceipts(sheets: BusinessSheet[], year: number) {
  const detail = sheets.find(sheet => sheet.key === '实际回款明细')
  const monthly = sheets.find(sheet => sheet.key === '公司月度回款')
  const mapped = [
    { key: '19_回款', headers: ['销售项目编码', '销售项目名称', '项目归属', '签订时间', '销售合同金额'], rows: records(detail).map(row => [row['项目编码'], row['项目名称'], row['区域'], row['回款日期'], row['实际回款金额（元）']]) },
    { key: '公司月度订货', headers: ['年份', '月份', '订货（万元）'], rows: records(monthly).map(row => [row['年份'], row['月份'], row['实际回款（万元）']]) },
  ]
  return companyOrders(mapped as BusinessSheet[], year)
}
export function companyOrders(sheets: BusinessSheet[], year: number) {
  const orders = records(sheets.find(sheet => sheet.key.startsWith('19_')))
  const monthly = records(sheets.find(sheet => sheet.key === '公司月度订货'))
  const years = [...new Set([...orders.map(row => dateParts(row['签订时间'])?.year), ...monthly.map(row => numeric(row['年份']))].filter((value): value is number => value != null))].sort((first, second) => second - first)
  const months = Array.from({ length: 12 }, (_, index) => ({ month: index + 1, order: null as number | null, managed: null as number | null }))
  const projects = new Map<string, { name: string; regions: Set<string>; amount: number; months: Set<number>; eligible: boolean }>()
  let invalidDates = 0
  for (const row of orders) {
    const date = dateParts(row['签订时间'])
    if (!date) { invalidDates++; continue }
    if (date.year !== year) continue
    const amount = numeric(row['销售合同金额'])
    if (amount === null) continue
    const month = months[date.month - 1]!
    month.order = (month.order ?? 0) + amount / 10000
    const name = String(row['销售项目名称'] || row['销售子项目名称'] || '项目名称待补充')
    const key = String(row['销售项目编码'] || name)
    const project = projects.get(key) || { name, regions: new Set<string>(), amount: 0, months: new Set<number>(), eligible: true }
    const rawRegion = String(row['项目归属'] || '').trim()
    const region = /^(东区|西区|中区)(?:作战平台|[-—－/]|$)/.exec(rawRegion)?.[1] || (/^广东(?:区|作战平台|[-—－/]|$)/.test(rawRegion) ? '广东' : '')
    project.eligible = project.eligible && Boolean(region)
    project.amount += amount / 10000
    project.regions.add(region || '归属待核验')
    project.months.add(date.month)
    projects.set(key, project)
  }
  for (const row of monthly) {
    if (numeric(row['年份']) !== year) continue
    const month = months[Number(String(row['月份']).replace('月', '')) - 1]
    if (!month) continue
    const order = numeric(row['订货（万元）'])
    if (order !== null) month.order = order
    month.managed = numeric(row['管理订货（万元）'])
  }
  const eligibleProjects = [...projects.entries()].filter(([, item]) => item.eligible)
  const rankingTotal = eligibleProjects.reduce((total, [, item]) => total + item.amount, 0)
  const top = eligibleProjects.map(([code, item]) => ({ code, name: item.name, region: [...item.regions].join('、'), amount: item.amount, months: [...item.months].sort((first, second) => first - second).join('、') + '月' })).sort((first, second) => second.amount - first.amount).slice(0, 10)
  const topTotal = top.reduce((total, item) => total + item.amount, 0)
  const cutoffMonth = Math.max(0, ...eligibleProjects.flatMap(([, item]) => [...item.months]))
  return { months, years, top, invalidDates, rankingTotal, topTotal, cutoffMonth, excludedProjects: projects.size - eligibleProjects.length }
}
