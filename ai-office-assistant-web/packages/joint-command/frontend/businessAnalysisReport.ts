import type { BusinessSheet } from '../../../src/services/personalWorkApi'
import { renderReportChart } from './businessReportCharts'
import { bizIcon, KPI_ICONS, cardIcon, SECTION_ICONS } from './businessIcons'
import { taskEvidence } from './businessDataQuality'

type Row = Record<string, any>
type Column = [key: string, label: string, kind?: 'money' | 'percent' | 'number' | 'text' | 'ratio']
const esc = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!))
const present = (v: unknown) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v))
const money = (v: unknown) => present(v) ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '未提供'
const integerMoney = (v: unknown) => present(v) ? Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 }) : '未提供'
const percent = (v: unknown) => present(v) ? `${(Number(v) * 100).toFixed(1)}%` : '未提供'
const ratio = (v: unknown) => present(v) ? Number(v).toFixed(2) : '未提供'
const divide = (a: unknown, b: unknown) => present(a) && present(b) && Number(b) > 0 ? Number(a) / Number(b) : null
const difference = (a: unknown, b: unknown) => present(a) && present(b) ? Number(a) - Number(b) : null
const rows = (v: unknown): Row[] => Array.isArray(v) ? v : []
const text = (v: unknown) => v === null || v === undefined || v === '' ? '未提供' : esc(v)

function table(data: Row[], columns: Column[], label: string, chartColumns = columns, domain?: [number, number], chartMode = 'auto') {
  if (!data.length) return '<p class="br-empty">该项暂无导入数据。</p>'
  return `<div class="br-visual-unit"><h4 class="br-visual-title">${esc(label)}</h4>${renderReportChart(data, chartColumns, label, domain, chartMode)}</div><template data-analysis-table><h4>${esc(label)}</h4><div class="br-table-scroll" tabindex="0" role="region" aria-label="${esc(label)}，可横向滚动"><table class="br-table"><thead><tr>${columns.map(([, name]) => `<th scope="col">${esc(name)}</th>`).join('')}</tr></thead><tbody>${data.map(row => `<tr>${columns.map(([key, , kind = 'money'], i) => {
    const value = row[key]
    const formatted = kind === 'text' ? text(value) : kind === 'percent' ? percent(value) : kind === 'ratio' ? ratio(value) : kind === 'number' ? (present(value) ? Number(value).toLocaleString('zh-CN') : '未提供') : money(value)
    return `<${i ? 'td' : 'th scope="row"'}${present(value) && Number(value) < 0 && kind !== 'text' ? ' class="br-negative"' : ''}>${formatted}</${i ? 'td' : 'th'}>`
  }).join('')}</tr>`).join('')}</tbody></table></div></template>`
}

export function businessGroups(data: Row[]) {
  const industryNames = ['集成', '服务', '场研', '其他', '产业待确认']
  const regionNames = ['东区', '西区', '中区', '广东区', '区域待确认']
  const groups = new Map<string, { industry: string; region: string; rows: Row[] }>()
  for (const row of data) {
    const rawIndustry = String(row.大产业 || row.产业 || '').trim()
    const industry = rawIndustry.startsWith('服务') ? '服务' : ['集成', '场研', '其他'].includes(rawIndustry) ? rawIndustry : rawIndustry || '产业待确认'
    const rawRegion = String(row.区域 || row.项目归属 || row['*项目归属'] || row.区域组织 || '').trim()
    const region = /^(东区|西区|中区)(作战平台|[-—－/]|$)/.exec(rawRegion)?.[1] || (/^广东(区|作战平台|[-—/]|$)/.test(rawRegion) ? '广东区' : '归属待核验')
    const key = JSON.stringify([industry, region])
    if (!groups.has(key)) groups.set(key, { industry, region, rows: [] })
    groups.get(key)!.rows.push(row)
  }
  const order = (names: string[], name: string) => names.includes(name) ? names.indexOf(name) : names.length
  return [...groups.values()].sort((left, right) => order(industryNames, left.industry)-order(industryNames, right.industry) || left.industry.localeCompare(right.industry, 'zh-CN') || order(regionNames, left.region)-order(regionNames, right.region) || left.region.localeCompare(right.region, 'zh-CN'))
}

function groupedTable(data: Row[], columns: Column[], label: string) {
  if (label === '区域任务推进' || label === '责任人任务推进') return regionalOwnerTable(data, columns, label)
  if (!data.length) return table(data, columns, label)
  let previousIndustry = ''
  return `<div class="br-grouped-report">${businessGroups(data).map(group => {
    const heading = group.industry !== previousIndustry ? `<h3>${esc(group.industry)}</h3>` : ''
    previousIndustry = group.industry
    const metrics = [...new Set(group.rows.map(row => String(row.指标 || row.类型 || '全部')))]
    return `${heading}<section class="br-region-group"><h4>${esc(group.region)} · ${group.rows.length}条</h4>${metrics.map(metric => `<div class="br-metric-group"><h5>${esc(metric)}</h5>${table(group.rows.filter(row => String(row.指标 || row.类型 || '全部') === metric), columns, label)}</div>`).join('')}</section>`
  }).join('')}</div>`
}

function regionalOwnerTable(data: Row[], columns: Column[], label: string) {
  if (!data.length) return table(data, columns, label)
  const totals = data.filter(row => ['合计', '总计', '全部'].includes(String(row.区域 || '').trim()))
  const details = data.filter(row => !totals.includes(row))
  const amounts = details.flatMap(row => ['任务令', '合计完成'].filter(key => present(row[key])).map(key => Number(row[key])))
  const domain: [number, number] = [Math.min(0, ...amounts), Math.max(1, ...amounts)]
  const overview = totals.length ? `<section class="br-task-overview"><h3>${label === '责任人任务推进' ? '责任人任务总体进度' : '区域任务总体进度'}</h3><p class="br-note">使用原表合计行，区域与子区域不重复相加；单位：万元。</p><div class="br-task-totals">${totals.map(row => {
    const rate = divide(row.合计完成, row.任务令)
    return `<article><h4>${esc(row.指标)}</h4><strong>${money(row.合计完成)}<small> / ${money(row.任务令)}</small></strong><p>累计完成 / 任务目标</p><div class="br-total-track"><i style="width:${rate === null ? 0 : Math.max(0,Math.min(100,rate*100))}%"></i></div><span>完成率 ${rate === null ? '未提供' : percent(rate)}</span></article>`
  }).join('')}</div></section>` : ''
  const regions = new Map<string, Row[]>()
  businessGroups(details).forEach(group => regions.set(group.region, [...(regions.get(group.region) || []), ...group.rows]))
  return `<div class="br-grouped-report br-regional-tasks">${overview}${[...regions].map(([region, items]) => {
    const regionalTotals = label === '区域任务推进' ? items.filter(row => {
      const raw = String(row.区域 || '').trim().replace(/作战平台$/, '')
      return (raw === '广东' ? '广东区' : raw) === region
    }) : []
    const personalItems = items.filter(row => !regionalTotals.includes(row))
    const meters = regionalTotals.map(row => {
      const rate = present(row.完成率) ? Number(row.完成率) : divide(row.合计完成, row.任务令)
      return `<div class="be-task-meter"><header><strong>${esc(row.指标)}</strong><b>${rate === null ? '未提供' : percent(rate)}</b></header><p><b>${money(row.合计完成)}</b><span> / ${money(row.任务令)} 万元</span></p><div class="br-total-track"><i style="width:${rate === null ? 0 : Math.max(0, Math.min(100, rate * 100))}%"></i></div><small>累计完成 / 任务令</small></div>`
    }).join('')
    const regionalOverview = `<section class="br-region-overview"><h4>${esc(region)}总体</h4>${regionalTotals.length ? `<div class="be-regional-meters">${meters}</div><details class="be-disclosure be-method"><summary><strong>区域进度对比与明细</strong><span>点击展开</span></summary>${table(regionalTotals, columns, label, columns, domain)}</details>` : '<p class="br-note">原表未提供独立区域总体行，暂不将个人明细相加，避免重复统计。</p>'}<p class="br-note">区域总体与下方个人明细分层展示，不重复相加。</p></section>`
    const owners = new Map<string, Row[]>()
    personalItems.forEach(row => {
      const owner = String(row.责任人 || row.负责人 || '责任人待确认').trim() || '责任人待确认'
      owners.set(owner, [...(owners.get(owner) || []), row])
    })
    return `<section class="br-region-group"><h3>${esc(region)}</h3>${regionalOverview}<h4>个人 / 子区域任务</h4><div class="br-owner-grid">${[...owners].map(([owner, records]) => {
      const chartColumns = columns.filter(([key]) => key !== '责任人' && key !== '负责人')
      const ordered = [...records].sort((left, right) => {
        const names = ['订货', '管理订货', '回款', '财务收入', '毛利']
        const rank = (row: Row) => names.includes(row.指标) ? names.indexOf(row.指标) : names.length
        return rank(left)-rank(right)
      })
      return `<article class="br-owner-panel"><h4>${esc(owner)}</h4>${table(ordered, columns, label, chartColumns, domain)}<p class="br-note">按原表区域及子区域逐项列示，不叠加汇总。</p></article>`
    }).join('')}</div></section>`
  }).join('')}</div>`
}

function profitOverview(data: Row[]) {
  if (!data.length) return '<p class="br-empty">暂无损益数据</p>'
  const revenue = data.filter(row => row.科目 === '财务收入')
  const comparison = data.filter(row => row.科目 !== '财务收入')
  const amounts = comparison.flatMap(row => ['公司', '利润核算角度'].filter(key => present(row[key])).map(key => Number(row[key])))
  const domain: [number, number] = [Math.min(0, ...amounts), Math.max(1, ...amounts)]
  return `<div class="br-profit-overview"><div class="br-profit-revenue">${revenue.map(row => `<span>财务收入（经营规模，非利润）：公司口径 <b>${money(row.公司)}</b> 万元 · 利润核算角度 <b>${money(row.利润核算角度)}</b> 万元</span>`).join('')}</div>${table(comparison, [['科目', '损益科目', 'text'], ['公司', '公司口径'], ['利润核算角度', '利润核算角度']], '公司完整损益', undefined, domain)}<p class="br-note">所有损益科目在同一坐标轴对比。平台费用明细仅展开原表科目，不与费用汇总重复相加；营业利润沿用原表，不重新推算。缺失值不视为零。</p></div>`
}

function expenseOverview(data: Row[]) {
  const items = data.filter(row => !['合计', '总计', '全部'].includes(String(row.科目 || '').trim()))
  if (!items.length) return '<p class="br-empty">暂无费用明细</p>'
  const known = items.filter(row => present(row.金额))
  const total = known.reduce((sum, row) => sum + Number(row.金额), 0)
  const complete = known.length === items.length
  const positive = complete && total > 0 && known.every(row => Number(row.金额) >= 0)
  const sorted = [...items].sort((left, right) => (present(right.金额) ? Number(right.金额) : -Infinity)-(present(left.金额) ? Number(left.金额) : -Infinity))
  const largest = sorted.find(row => present(row.金额))
  const ranked = sorted.map(row => ({ ...row, 占比: positive ? Number(row.金额)/total : null,
    展示科目: `${row.科目 || '未命名科目'}${positive ? ' · ' + percent(Number(row.金额)/total) : ''}` }))
  const domain: [number, number] = [Math.min(0, ...known.map(row => Number(row.金额))), Math.max(1, ...known.map(row => Number(row.金额)))]
  return `<div class="br-expense-overview"><div class="br-expense-summary"><article><span>${complete ? '实际费用合计' : '已提供费用小计'}</span><strong>${known.length ? money(total) : '未提供'}<small> 万元</small></strong></article><article><span>最大费用项</span><strong>${largest ? esc(largest.科目) : '未提供'}</strong><p>${largest ? money(largest.金额) + ' 万元' : ''}</p></article><article><span>最大费用项占比</span><strong>${positive && largest ? percent(Number(largest.金额)/total) : '不适用'}</strong></article></div>${table(ranked, [['科目','费用科目','text'], ['金额','实际费用（万元）'], ['占比','费用占比','percent']], '费用金额排序', [['展示科目','费用科目与占比','text'], ['金额','实际费用（万元）']], domain)}${positive ? `<div class="be-expense-share"><h4>费用占比</h4>${renderReportChart(ranked, [['科目', '费用科目', 'text'], ['金额', '实际费用']], '费用构成', undefined, 'donut')}</div>` : ''}<p class="br-note">按金额从高到低排列，同一刻度直接比较；金额单位：万元。${positive ? '占比按全部费用明细合计计算。' : '存在负数、缺失值或合计非正数时不计算构成占比。'}不与其他期间或口径的费用叠加。</p></div>`
}

function compactRegionalComparison(data: Row[], columns: Column[], label: string) {
  const task = label === '区域任务令'
  const keys = task ? ['目标', '实际'] : ['订货', '现金流']
  const amounts = data.flatMap(row => keys.filter(key => present(row[key])).map(key => Number(row[key])))
  const domain: [number, number] = [Math.min(0, ...amounts), Math.max(1, ...amounts)]
  const ordered = [...data].sort((left, right) => task ? String(left.平台 || '').localeCompare(String(right.平台 || ''), 'zh-CN') : (present(right.订货) ? Number(right.订货) : -Infinity)-(present(left.订货) ? Number(left.订货) : -Infinity))
  const display = ordered.map(row => ({ ...row, 对比对象: task
    ? `${row.平台 || '未提供'} · ${row.指标 || ''} · 达成率 ${present(row.达成率) ? percent(row.达成率) : '未提供'} · 缺口 ${money(row.缺口)}万元`
    : String(row.省份 || '未提供') }))
  return `<div class="br-compact-comparison">${table(display, columns, label, [['对比对象', '对比对象', 'text'], ...columns.filter(([key]) => keys.includes(key))], domain)}</div>`
}

function card(title: string, note: string, content: string, source = '', _secondary = false) {
  const related: Record<string,string> = {
    '费用构成与预算执行':'03,06', '现金与收入支撑：按项目年份看':'11,12',
    '合同质量：预付条款与回款转化':'13,14', '区域费用、分摊与预算':'03,06,07',
    '区域现金流与机会储备':'11,16', '毛利去向与产业投入效率':'04,08',
    '子产业与项目属性':'04,15', '产业合同条款与回款质量':'13,14',
  }
  const sourceKey = /^\d{2}_/.test(source) ? source.slice(0, 2) : source
  return `<article class="br-card br-chart-card" role="button" tabindex="0" aria-label="放大图表：${esc(title)}" data-chart-title="${esc(title)}" data-chart-sources="${related[title] || sourceKey}"><header><i class="br-card-icon">${bizIcon(cardIcon(title))}</i><span class="br-card-title">${esc(title)}</span><span class="br-source">${bizIcon('zoom')}放大</span></header><p class="br-note">${esc(note)}</p>${content}</article>`
}

export function sheetRows(sheet?: BusinessSheet): Row[] {
  return sheet ? sheet.rows.map(row => Object.fromEntries(sheet.headers.map((h, i) => [h, row[i]]))) : []
}

// Formatting is based on the field meaning: 达标订单量 is a count, not a percentage.
export function formatBusinessCell(value: unknown, header: string): string {
  if (value === null || value === undefined || value === '') return '未提供'
  if (typeof value !== 'number') return String(value)
  if (/费效比|专项\/解决方案贡毛|资占\/解决方案贡毛/.test(header)) return ratio(value)
  if (/率|占比|赢率|环比|专项毛利比/.test(header)) return percent(value)
  return value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function rawSheets(sheets: BusinessSheet[], ids: string[], title: string) {
  const selected = sheets.filter(s => ids.includes(s.key.slice(0, 2)))
  if (!selected.length) return ''
  return `<button type="button" class="br-source-group" data-source-ids="${ids.join(',')}">${bizIcon('database')}<span>${esc(title)} · ${selected.length} 张来源表</span></button>`
}

function progressList(data: Row[], nameKey: string, actualKey: string, targetKey: string, reverse = false) {
  return `<template><div class="br-bars">${data.map(row => {
    const rate = divide(row[actualKey], row[targetKey])
    const adverse = rate !== null && (reverse ? rate > 1 : rate < 0.6)
    return `<div class="br-bar-row"><div><strong>${text(row[nameKey])}</strong><span>目标 ${money(row[targetKey])} · ${reverse ? '已使用' : '当前'} ${money(row[actualKey])}</span></div><div class="br-bar-track"><i style="width:${rate === null ? 0 : Math.max(0, Math.min(100, rate * 100))}%;background:var(${adverse ? '--danger' : '--primary'})"></i></div><b>${reverse ? '使用率' : '达成率'} ${percent(rate)}</b></div>`
  }).join('')}</div></template>`
}

function regionalComparison(rows: Row[]): string {
  const valid = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
  const amounts = rows.flatMap(row => ['目标', '实际', '差额'].map(key => row[key]).filter(valid))
  const minimum = Math.min(0, ...amounts), maximum = Math.max(1, ...amounts)
  const lower = Math.floor(minimum / 1000) * 1000, upper = Math.ceil(maximum / 1000) * 1000
  const rateMax = Math.max(1, ...rows.map(row => valid(row['完成率']) ? row['完成率'] : 0)) * 1.15
  const axisY = (value: number) => 65 + (upper - value) / (upper - lower) * 235
  const rateY = (value: number) => 65 + (1 - value / rateMax) * 235
  const center = (index: number) => 85 + (index + .5) * 530 / Math.max(1, rows.length)
  const colors = ['#f6ad72', '#009b89', '#dc5252']
  let svg = '<text x="18" y="24" fill="currentColor">万元</text><text x="610" y="24" fill="currentColor">完成率</text>'
  for (let index = 0; index <= 4; index++) {
    const amount = lower + (upper - lower) * index / 4, height = axisY(amount)
    svg += `<line x1="85" x2="615" y1="${height}" y2="${height}" stroke="currentColor" opacity=".15"/><text x="77" y="${height + 4}" text-anchor="end" fill="currentColor">${money(amount)}</text><text x="625" y="${height + 4}" fill="currentColor">${(rateMax * index / 4 * 100).toFixed(0)}%</text>`
  }
  svg += `<line x1="85" x2="615" y1="${axisY(0)}" y2="${axisY(0)}" stroke="currentColor" opacity=".6"/>`
  let path = '', previous: {x: number; y: number} | null = null
  rows.forEach((row, index) => {
    const position = center(index)
    ;['目标', '实际', '差额'].forEach((key, series) => {
      const amount = row[key]
      if (!valid(amount)) return
      const horizontal = position + (series - 1) * 27, vertical = axisY(amount)
      svg += `<rect x="${horizontal - 11}" y="${Math.min(vertical, axisY(0))}" width="22" height="${Math.abs(vertical - axisY(0))}" fill="${colors[series]}"><title>${esc(row['区域'])} ${key}：${money(amount)}万元</title></rect>`
    })
    if (valid(row['完成率'])) {
      const height = rateY(row['完成率'])
      path += previous ? ` C${(previous.x + position) / 2},${previous.y} ${(previous.x + position) / 2},${height} ${position},${height}` : ` M${position},${height}`
      previous = {x: position, y: height}
      svg += `<circle cx="${position}" cy="${height}" r="4" fill="#df9b00"/><text x="${position}" y="${height - 12}" text-anchor="middle" fill="currentColor">${(row['完成率'] * 100).toFixed(1)}%</text>`
    } else previous = null
    svg += `<text x="${position}" y="327" text-anchor="middle" fill="currentColor">${esc(row['区域'])}</text>`
  })
  svg += `<path d="${path}" fill="none" stroke="#df9b00" stroke-width="2.5"/>`
  return '<p class="br-note">🟠 目标　🟢 实际　🔴 差额（实际−目标）　🟡 完成率（右轴）</p>' +
    `<svg viewBox="0 0 700 350" style="width:100%;display:block;font-size:12px" role="img" aria-label="区域目标、实际、差额及完成率双轴组合图">${svg}</svg>` +
    '<table class="br-table"><thead><tr><th>区域 / 负责人</th><th>目标</th><th>实际</th><th>差额</th><th>完成率</th><th>排名</th></tr></thead><tbody>' +
    rows.map(row => `<tr><td>${esc(row['区域'])} / ${esc(row['负责人'])}</td>${['目标', '实际', '差额'].map(key => `<td>${money(row[key])}</td>`).join('')}<td>${valid(row['完成率']) ? (row['完成率'] * 100).toFixed(1) + '%' : '未提供'}</td><td>${esc(row['排名'] ?? '未提供')}</td></tr>`).join('') + '</tbody></table>'
}

function executiveRegions(sheets: BusinessSheet[], annual: Row[]): string {
  const period = String(annual[0]?.['期间'] || '全年')
  const metrics = ['订货', '管理订货', '财务收入', '回款', '毛利']
  const regions = ['东区', '西区', '中区', '广东区'].filter(region => annual.some(row => row['区域'] === region))
  const records = (key: string) => sheetRows(sheets.find(sheet => sheet.key === '区域经营_' + key))
  const sum = (items: Row[], key: string) => items.length && items.every(row => present(row[key])) ? items.reduce((total, row) => total + Number(row[key]), 0) : null
  const summary = metrics.map(metric => {
    const items = annual.filter(row => row['指标'] === metric)
    const actual = sum(items, '实际'), target = sum(items, '目标')
    return { metric, actual, target, rate: divide(actual, target) }
  })
  const overview = `<div class="rx-heading"><div><span>REGIONAL BUSINESS OVERVIEW</span><h2>${esc(period)} · 区域经营总览</h2><p>仅汇总当前可见的${regions.length}个区域，不含公司其他及历史上海独立目标。单位：万元</p></div><b>结果 → 区域 → 趋势</b></div>`
  const metricIcons = ['order', 'conversion', 'income', 'receipt', 'profit']
  const kpis = '<div class="rx-kpis">' + summary.map((item, index) => `<article class="br-kpi rx-kpi"><img class="rx-design-icon" src="/personal-office-assistant/region-${metricIcons[index]}.png" alt="" width="36" height="36"/><span>${item.metric === '毛利' ? '预计毛利' : item.metric}</span><strong>${money(item.actual)}<small>万元</small></strong><p>${present(item.target) ? '期间目标 ' + money(item.target) : '本期间未提供目标'}</p><div class="rx-progress"><i style="width:${item.rate === null ? 0 : Math.max(0, Math.min(100, item.rate * 100))}%"></i></div><footer>${item.rate === null ? '完成率不计算' : '完成率 <b>' + percent(item.rate) + '</b>'}</footer>${index === 0 ? '<div class="rx-kpi-conversion" aria-hidden="true">→<small>折算</small></div>' : ''}</article>`).join('') + '</div>'
  const matrix = '<p class="br-note">订货与管理订货成组展示，管理订货遵循原表折算口径。进度满格100%，超额保留真实百分比。</p><table class="rx-matrix rx-designed-matrix"><colgroup><col style="width:10%"><col style="width:18%"><col style="width:18%"><col style="width:18%"><col style="width:18%"><col style="width:18%"></colgroup><thead><tr><th rowspan="2">区域 / 负责人</th><th colspan="2">订货 → 管理订货（折算后）</th>' + metrics.slice(2).map(metric => `<th rowspan="2">${metric === '毛利' ? '预计毛利' : metric}</th>`).join('') + '</tr><tr><th>订货</th><th>管理订货</th></tr></thead><tbody>' + regions.map(region => {
    const items = annual.filter(row => row['区域'] === region)
    const orderActual = items.find(row => row['指标'] === '订货')?.['实际']
    const managedActual = items.find(row => row['指标'] === '管理订货')?.['实际']
    const conversionRate = divide(managedActual, orderActual)
    const renderMetric = (metric: string) => {
      const item = items.find(row => row['指标'] === metric) || {}
      const rate = present(item['完成率']) ? Number(item['完成率']) : null
      const status = rate !== null && rate >= 1 ? 'achieved' : rate !== null && rate < 0 ? 'negative' : ''
      const meter = rate === null ? '' : `role="meter" aria-label="${esc(region)}${esc(metric)}完成率" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0, Math.min(100, rate * 100))}" aria-valuetext="${percent(rate)}"`
      const gap = present(item['差额']) ? (Number(item['差额']) >= 0 ? '超额 ' : '缺口 ') + money(Math.abs(Number(item['差额']))) : '差额 —'
      return `<div class="rx-rate rx-overlay rx-design-meter ${status}" ${meter}><div class="rx-design-numbers"><strong>${money(item['实际'])}</strong><b class="${rate === null ? 'rx-rate-missing' : ''}">${rate === null ? '完成率 —' : percent(rate) + (rate >= 1 ? ' · 达标' : '')}</b></div><div class="rx-design-track">${rate === null ? '' : `<i class="rx-overlay-fill" style="width:${Math.max(0, Math.min(100, rate * 100))}%"></i>`}</div><div class="rx-design-caption"><small>目标 ${money(item['目标'])}</small><small class="${present(item['差额']) && Number(item['差额']) >= 0 ? 'rx-good' : ''}">${gap}</small></div></div>`
    }
    return `<tr><th><span>${esc(region)}</span><small>${esc(items[0]?.['负责人'])}</small></th><td class="rx-order-cell" data-metric="订货">${renderMetric('订货')}</td><td class="rx-managed-cell" data-metric="管理订货">${renderMetric('管理订货')}<small class="rx-conversion-ratio" title="实际折算比例：管理订货实际 ÷ 订货实际">折算比 ${conversionRate === null ? '—' : percent(conversionRate)}</small></td>` + metrics.slice(2).map(metric => `<td data-metric="${metric === '毛利' ? '预计毛利' : metric}">${renderMetric(metric)}</td>`).join('') + '</tr>'
  }).join('') + '</tbody></table>'
  const comparisonRows = regions.map(region => Object.fromEntries([['区域', region], ...['订货', '财务收入', '回款'].map(metric => [metric, annual.find(row => row['区域'] === region && row['指标'] === metric)?.['实际']])]))
  const monthly = records('月度实绩').filter(row => regions.includes(row['区域']))
  const shipments = records('月度拆解').filter(row => regions.includes(row['区域']) && row['指标'] === '设备发货及服务验收' && row['记录层级'] === '区域')
  const trends = ['订货', '财务收入', '回款', ...(shipments.length ? ['设备发货及服务验收'] : [])].map(metric => {
    const items = Array.from({ length: 12 }, (_, index) => {
      const month = `${index + 1}月`
      return { 月份: month, [metric]: metric === '设备发货及服务验收' ? sum(shipments.filter(row => row['期间'] === month && row['单位'] === '万元'), '金额') : sum(monthly.filter(row => row['月份'] === month), metric) }
    })
    return card(metric + ' · 全年趋势', '1—12月，当前可见区域合计；不随上方期间截断。', renderReportChart(items, [['月份', '月份', 'text'], [metric, metric]], metric + '月度趋势', undefined, 'line'), '区域经营_月度实绩')
  }).join('')
  return `<div class="rx-dashboard rx-from-design">${overview}${kpis}${card('四区域经营一览', '单位：万元。缺失目标保留未提供，不补零。', matrix, '区域经营_期间指标')}<div class="rx-design-lower"><div class="rx-two">${card('订货 · 收入 · 回款对比', '当前期间实际金额，统一坐标，不混入计划。', table(comparisonRows, [['区域', '区域', 'text'], ['订货', '订货'], ['财务收入', '财务收入'], ['回款', '回款']], '四区域实际对比'), '区域经营_期间指标')}</div><div class="rx-trends">${trends}</div></div>${rawSheets(sheets, ['区域经营'], '完整数据与来源：期间指标、业务明细、历史计划及应收存量')}</div>`
}

function authoritativeRegions(sheets: BusinessSheet[]): string {
  const records = (key: string) => sheetRows(sheets.find(sheet => sheet.key === '区域经营_' + key))
  const annual = records('年度指标')
  if (!annual.length) return ''
  if (records('期间指标').length) return executiveRegions(sheets, annual)
  const period = String(annual[0]?.['期间'] || '年度')
  const periodSource = records('期间指标').length > 0
  const comparison = '<div class="br-owner-grid" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr))">' + ['订货', '管理订货', '财务收入', '回款', '毛利'].map(metric => {
    const rows = annual.filter(row => row['指标'] === metric)
    return rows.length ? card(metric + ' · 区域' + period + '目标与完成', '金额：万元。柱形使用左轴，完成率使用右轴；负差额为未完成目标。' + (rows[0]?.['指标口径说明'] || ''), regionalComparison(rows) + (periodSource ? '<p class="br-note">' + rows.map(row => esc(row['区域']) + '：' + esc(row['目标说明'])).join('；') + '</p>' : ''), '区域经营_期间指标,区域经营_年度指标') : ''
  }).join('') + '</div>'
  return comparison + [...new Set(annual.map(row => String(row['区域'])))].map(region => {
    const subset = (key: string) => records(key).filter(row => row['区域'] === region)
    return `<section class="br-region-group"><h3>${esc(region)}</h3><div class="br-owner-grid">` +
      card('1—12月实际趋势', '单位：万元。保留材料原始月度值，不包含预计回款。', table(subset('月度实绩'), [
        ['月份', '月份', 'text'], ['订货', '订货'], ['财务收入', '财务收入'], ['回款', '回款'],
      ], '月度趋势'), '区域经营_月度实绩') +
      (subset('回款计划').length ? card('3月回款计划（非实际）', '历史计划，单位：万元。不计入累计完成。', table(subset('回款计划'), [
        ['计划月份', '月份', 'text'], ['预计回款', '预计回款'], ['电汇', '电汇'], ['银承', '银承'], ['往月应收款', '往月应收款'], ['本月应收款', '本月应收款'],
      ], '回款计划'), '区域经营_回款计划') : '') +
      card('应收款性质', periodSource ? '金额：万元；数量沿用原表口径。存量时点未明确，不随期间分摊。' : '金额沿用原表，单位待核验；数量单位：笔。公司与区域差额不分摊。',
        '<table class="br-table"><thead><tr><th>性质</th><th>' + (periodSource ? '金额（万元）' : '原表金额（单位待核验）') + '</th><th>数量（原表口径）</th></tr></thead><tbody>' +
        subset('应收款结构').map(row => `<tr><td>${esc(row['性质'])}</td><td>${money(row['应收款'])}</td><td>${esc(row['数量'] ?? '未提供')}</td></tr>`).join('') + '</tbody></table>', '区域经营_应收款结构') + '</div></section>'
  }).join('') + rawSheets(sheets, ['区域经营'], '三份材料来源与口径')
}

export function renderScopedBusinessReport(sheets: BusinessSheet[], level: 'region' | 'personal'): string {
  const personal = level === 'personal'
  const prefix = personal ? '我的' : '区域'
  const records = (key: string) => sheetRows(sheets.find(sheet => sheet.key === key))
  const opportunities = records('16_机会点清单')
  const orders = records('19_已完成订单明细')
  const total = (items: Row[], key: string, divisor = 1) => {
    const values = items.filter(item => present(item[key]))
    return values.length ? values.reduce((sum, item) => sum + Number(item[key]) / divisor, 0) : null
  }
  const summary = [
    { label: '可见机会记录', value: opportunities.length ? String(opportunities.length) : '未提供', unit: '条', icon: 'opportunity' },
    { label: '机会可参与份额', value: money(total(opportunities, '可参与份额-总额(万元)')), unit: '万元', icon: 'progress' },
    { label: '已签订单明细', value: orders.length ? String(orders.length) : '未提供', unit: '条', icon: 'results' },
    { label: '订单含税金额', value: money(total(orders, '销售合同金额', 10000)), unit: '万元', icon: 'budget' },
  ]
  const section = (key: string, title: string, content: string) => `<section class="br-section" data-section="${key}"><div class="br-section-head"><div><h3>${esc(title)}</h3></div></div>${content || '<p class="br-empty">当前版本暂无明确归属的数据，请联系管理员核对负责人或区域字段。</p>'}</section>`
  const summaryHtml = sheets.length ? `<div class="br-kpis">${summary.map(item => `<article class="br-kpi"><i class="br-metric-icon">${bizIcon(item.icon)}</i><span>${item.label}</span><strong>${item.value}<em>${item.unit}</em></strong><p>当前版本可见记录 · 非年度累计口径</p></article>`).join('')}</div>` : ''
  const tasks = [
    ...(personal ? [] : ['任务令区域进度']),
    '任务令责任人进度',
  ].map(key => {
    const items = records(key)
    return items.length ? card(key === '任务令区域进度' ? '区域任务进度' : prefix + '责任人任务进度', '单位：万元。仅展示授权范围内的任务，保留原任务期间。', groupedTable(items, [
      ['指标', '指标', 'text'], ['区域', '区域', 'text'], ['责任人', '负责人', 'text'],
      ['任务令', '任务目标'], ['合计完成', '累计完成'], ['完成率', '完成率', 'percent'], ['缺口', '缺口'],
    ], '区域任务推进'), key) : ''
  }).join('')
  const taskDetails = ['订货任务令', '回款任务令', '财务收入任务令'].map(key => {
    const sheet = sheets.find(item => item.key === key)
    return sheet?.rows.length ? `<button type="button" class="br-source-group" data-source-ids="${key}">${key} · ${sheet.rows.length}条明细</button>` : ''
  }).join('')
  const regional = records('本次区域经营汇总')
  const regionHtml = regional.length ? card('授权区域经营结果', '单位：万元。沿用本版本区域统计口径，不包含公司合计。', table(regional, [
    ['区域', '区域', 'text'], ['订货', '订货'], ['管理订货', '管理订货'], ['财务收入', '收入'], ['回款', '回款'], ['毛利', '毛利'],
  ], '本次区域经营对比'), '本次区域经营汇总') : ''
  const projects = [
    opportunities.length ? card(prefix + '机会储备', '单位：万元。机会份额是储备，不计入实际订货。', table(opportunities, [
      ['机会点名称', '机会点', 'text'], ['客户经理', '负责人', 'text'], ['赢率', '预估赢率', 'percent'],
      ['可参与份额-总额(万元)', '可参与份额'], ['机会点阶段', '阶段', 'text'],
    ], '机会份额', [['机会点名称', '机会点', 'text'], ['可参与份额-总额(万元)', '可参与份额']]), '16_机会点清单') : '',
    orders.length ? card(prefix + '已签订单', '单位：元。逐订单明细展示，条数不等于独立项目数。', table(orders, [
      ['销售项目名称', '项目', 'text'], ['客户经理', '负责人', 'text'], ['签订时间', '签订时间', 'text'], ['销售合同金额', '合同金额'],
    ], '订单金额'), '19_已完成订单明细') : '',
  ].join('')
  return `<div class="br-report">${section('overall', prefix + '经营总览', summaryHtml)}
    ${section('taskOrder', prefix + '任务执行', tasks + taskDetails)}
    ${personal ? '' : section('region', '授权区域经营', authoritativeRegions(sheets) || regionHtml)}
    ${section('projects', prefix + '项目与机会', projects)}</div>`
}

export function renderBusinessReport(data: Row | null, sheets: BusinessSheet[] = [], level: 'company' | 'region' | 'personal' = 'company', profitBasis: '公司' | '利润核算角度' | 'both' = 'both'): string {
  if (level !== 'company') return renderScopedBusinessReport(sheets, level)
  const d = data || {}
  const raw = (prefix: string) => sheetRows(sheets.find(s => s.key.startsWith(prefix + '_')))
  const k = rows(d.P01_红绿灯), aux = d.P01_辅助 || {}
  const ind = rows(d.P05_产业), platforms = rows(d.P02_平台), targets = rows(d.P04_目标达成)
  const core: Row[] = k.map(r => ({ ...r, 年度达成: present(r.全年完成率) ? r.全年完成率 : divide(r.实际, r.全年目标), 季度达成: present(r.Q3完成率) ? r.Q3完成率 : divide(r.实际, r.Q3目标), 剩余: present(r.全年缺口) ? r.全年缺口 : difference(r.全年目标, r.实际) }))
  const scope = d._meta?.口径 || aux.统计口径 || '以当前导入表的统计期间与范围为准'
  const company = core.find(r => r.指标 === '订货')
  const indTotal = ind.find(r => r.产业 === '合计')
  const scopeGap = difference(indTotal?.订货, company?.实际)
  const scopeNote = scopeGap !== null && Math.abs(scopeGap) > 0.1
    ? `公司核心订货 ${money(company?.实际)}，产业表合计 ${money(indTotal?.订货)}，相差 ${money(scopeGap)} 万元。两表统计范围不同，分别展示，不跨表相加。`
    : '各分析沿用所属来源表口径；公司、区域与产业合计不可直接相加。'

  const tiles = core.map((r, i) => {
    const reverse = !!r.逆向指标
    return `<article class="br-kpi" data-kpi="${i}"><i class="br-metric-icon">${bizIcon(KPI_ICONS[String(r.指标)] || 'results')}</i><span>${text(r.指标)}<small>${reverse ? '费用控制 · 预算使用' : '年度达成 · 万元'}</small></span><strong>${integerMoney(r.实际)}<em>万元</em></strong><p>全年${reverse ? '预算' : '目标'} <b>${integerMoney(r.全年目标)}</b></p><div class="br-bar-track"><i style="width:${Math.max(0, Math.min(100, Number(r.年度达成 || 0) * 100))}%"></i></div><footer><span>${reverse ? '预算使用率' : '达成率'} <b>${percent(r.年度达成)}</b></span><span class="br-kpi-gap ${!reverse && Number(r.剩余) > 0 ? 'be-gap-warning' : ''}">${reverse ? '余额' : Number(r.剩余) < 0 ? '超额' : '缺口 ↓ −'} ${integerMoney(Number(r.剩余) < 0 && !reverse ? -Number(r.剩余) : r.剩余)}</span></footer></article>`
  }).join('')
  const execution = [
    `<div class="be-project-flow">${[['16', '机会储备'], ['17', '滚动冲刺'], ['18', '预算承接'], ['19', '已完成订单']].map(([prefix, name]) => `<article><span>${name}</span><strong>${raw(prefix!).length}<small> 条来源记录</small></strong><small>独立来源口径，不跨阶段相加</small></article>`).join('')}</div>`,
    card('滚动冲刺：待签项目与推进进度', '金额单位：万元。按原表逐项目列示储备、预计签约与实际签订，不将储备当成完成。', table(raw('17'), [['项目归属', '区域', 'text'], ['机会点名称', '机会点', 'text'], ['客户经理', '负责人', 'text'], ['赢率', '赢率', 'percent'], ['可参与份额-总额', '可参与份额'], ['合同预计签订时间', '预计签约', 'text'], ['机会点阶段', '阶段', 'text'], ['项目具体进度说明', '具体进度', 'text'], ['实际签订金额', '实际签订金额'], ['实际签订时间', '实际签订时间', 'text']], '滚动冲刺'), '17_滚动冲刺机会点', true),
    card('年初全预算承接：计划有没有落地', '机会份额单位：万元；订货金额原表单位：元，单独标注。原预计月份与实际签订月份并列。', table(raw('18'), [['区域归属', '区域', 'text'], ['机会点名称', '机会点', 'text'], ['可参与份额-总额(万元)', '预算份额（万元）'], ['当前机会点金额', '当前机会金额'], ['订货金额（元）', '订货金额（元）'], ['原预计月份', '原预计月份', 'text'], ['签订年份', '签订年份', 'text'], ['签订月份', '签订月份', 'text']], '年初预算承接'), '18_年初全预算承接', true),
    card('已完成订单：合同、成本与毛利', '金额单位：元。逐销售子项目列示含税 / 未税合同、预估成本及当期毛利；行数不等于独立合同数。', table(raw('19'), [['项目归属', '区域', 'text'], ['客户经理', '客户经理', 'text'], ['销售子项目名称', '销售子项目', 'text'], ['签订时间', '签订时间', 'text'], ['销售合同金额', '含税合同金额'], ['销售合同金额(未税)', '未税合同金额'], ['预估成本合计', '预估成本'], ['预估毛利', '预估毛利'], ['预估毛利率', '预估毛利率', 'percent'], ['当期发生成本合计-未税', '当期未税成本'], ['当期毛利', '当期毛利'], ['当期毛利率-未税', '当期毛利率', 'percent']], '已完成订单'), '19_已完成订单明细', true),
  ].join('')
  const overall = [
    rawSheets(sheets, ['01'], '核心指标来源明细'),
    card('利润从哪里产生、被哪些费用消耗', '单位：万元。公司损益与利润核算角度并列，收入毛利、订货毛利分别遵循原表定义。', profitOverview(rows(d.P04_损益全表)), '10_公司损益', true),
    card('费用构成', '单位：万元。按费用明细展示公司各类实际费用。', expenseOverview(rows(d.P06_费用构成)), '06_费用明细', true),
    card('现金与收入支撑：按项目年份看', '现金流汇总单位：万元；收入支撑表保留原表金额单位（元）。年份是项目归属年，不是本期经营年度。', table(rows(d.P07_现金流年份), [['项目年份', '项目年份', 'text'], ['回款', '回款'], ['合同付款', '合同付款'], ['经营现金流', '经营现金流'], ['累计项目现金流', '累计项目现金流']], '项目年份现金流') + table(raw('12'), [['项目年份', '项目年份', 'text'], ['东区', '东区（元）'], ['西区', '西区（元）'], ['广东', '广东（元）'], ['中区', '中区（元）'], ['合计', '收入支撑合计（元）']], '收入支撑'), '12_收入支撑构成', true),
    card('合同质量：预付条款与回款转化', '按签约年份比较历史表现。预付≥30%是条款分档，不是经营目标；数量占比与金额占比分开看。', table(rows(d.P07_预付趋势), [['年份', '签约年', 'text'], ['项目数', '项目数', 'number'], ['合同额万元', '合同额（万元）'], ['有预付数量占比', '有预付数量占比', 'percent'], ['有预付金额占比', '有预付金额占比', 'percent'], ['预付≥30%数量占比', '预付≥30%数量占比', 'percent'], ['预付≥30%金额占比', '预付≥30%金额占比', 'percent']], '预付条款') + table(rows(d.P07_账龄).filter(r => r.产业 === '合计'), [['年份', '签约年', 'text'], ['M1', '1个月回款率', 'percent'], ['M3', '3个月回款率', 'percent'], ['M6', '6个月回款率', 'percent']], '回款转化'), '14_预付条款分析', true),
    card('后续增长：机会储备与转化阶段', '金额单位：万元。赢率分档互不包含，不构成逐层转化漏斗；份额与预估毛利属于储备，不是已完成订单。', table(rows(d.P08_漏斗), [['赢率区间', '赢率分档', 'text'], ['机会点数', '机会点数', 'number'], ['可参与份额', '可参与份额'], ['预估毛利', '预估毛利']], '机会储备') + table(rows(d.P08_阶段), [['阶段', '当前阶段', 'text'], ['机会点数', '机会点数', 'number'], ['可参与份额', '可参与份额']], '机会阶段'), '16_机会点清单', true),
  ]
  const profitRows = rows(d.P04_损益全表)
  const profitColumns: Column[] = [['科目', '科目', 'text'], ...(profitBasis === 'both' ? [['公司', '公司口径'], ['利润核算角度', '利润核算角度']] as Column[] : [[profitBasis, profitBasis === '公司' ? '公司口径' : '利润核算角度']] as Column[])]
  const sourceNames = profitRows.filter(row => row.科目 === '财务收入毛利' || String(row.科目).startsWith('战略补贴')).map(row => row.科目)
  const expenseNames = ['销售费用', '销售平台费用', '管理费用', '研发费用', '财务费用', '返点'].sort((first, second) => {
    const key = profitBasis === '利润核算角度' ? profitBasis : '公司'
    const value = (name: string) => { const row = profitRows.find(item => item.科目 === name); return present(row?.[key]) ? Number(row![key]) : -Infinity }
    return value(second) - value(first)
  })
  const platformNames = ['公司销售平台', '集成产业平台', '服务产业平台']
  const knownNames = [...sourceNames, ...expenseNames, ...platformNames, '财务收入', '营业利润']
  const comparisonPanel = (title: string, names: string[], tone: string, note: string) => {
    if (tone === 'be-platform') {
      const entries = names.map(name => ({ 科目: `${name}费用`, 金额: profitRows.find(item => item.科目 === name)?.[profitBasis === '利润核算角度' ? profitBasis : '公司'] })).sort((first, second) => Number(second.金额 || 0) - Number(first.金额 || 0))
      return `<section class="be-profit-panel ${tone}"><header><h4>${esc(title)}</h4><span>万元 · ${profitBasis === '利润核算角度' ? '利润核算角度' : '公司口径'}</span></header><div class="be-profit-chart">${renderReportChart(entries, [['科目', '平台', 'text'], ['金额', '金额']], '费用构成', undefined, 'donut')}</div><p>${esc(note)}</p></section>`
    }
    if (['be-combined', ''].includes(tone)) {
      const entries: Row[] = names.map(name => ({ ...(profitRows.find(item => item.科目 === name) || {}), 科目: name }))
      const plotted = entries.filter(row => present(row.公司) || present(row.利润核算角度))
      const missing = entries.filter(row => !present(row.公司) && !present(row.利润核算角度)).map(row => row.科目)
      const chartRows = plotted.map(row => ({ ...row, 科目: row.科目.startsWith('战略补贴') ? '战略补贴' : row.科目 === '销售平台费用' ? '销售平台' : row.科目 === '财务收入毛利' ? '收入毛利' : row.科目 }))
      return `<section class="be-profit-panel ${tone}"><header><h4>${esc(title)}</h4><span>万元</span></header><div class="be-profit-chart">${renderReportChart(chartRows, profitColumns, title, undefined, 'bar')}</div>${missing.length ? `<p class="be-missing-note">未提供：${missing.map(esc).join('、')}（不补零）</p>` : ''}<p>${esc(note)}</p></section>`
    }
    return `<section class="be-profit-panel ${tone}"><header><h4>${esc(title)}</h4><span>万元</span></header><div class="be-profit-line be-profit-labels"><span>科目</span><span>公司口径</span><span>利润核算角度</span></div>${names.map(name => {
    const row = profitRows.find(item => item.科目 === name) || {}
    return `<div class="be-profit-line"><span>${esc(name)}</span>${['公司', '利润核算角度'].map(key => `<b class="${present(row[key]) && Number(row[key]) < 0 ? 'be-loss' : ''}">${money(row[key])}</b>`).join('')}</div>`
  }).join('')}<p>${esc(note)}</p></section>`
  }
  const executiveCharts = `<div class="be-management-board"><header class="be-profit-heading"><h3>利润从哪里产生、被哪些费用消耗</h3><p>先看毛利与补贴，再看期间费用，最后核对原表营业利润。两列是核算口径，不是同比。</p></header><div class="be-profit-flow">${comparisonPanel('利润来源 · 费用消耗 · 营业利润', [...sourceNames, ...expenseNames, '营业利润'], 'be-combined', '财务收入毛利与订货毛利不可混用；费用按原表符号展示，不是利润增量。营业利润直接采用原表结果，不凭展示科目重新推算。')}</div>${comparisonPanel('销售平台费用明细', platformNames, 'be-platform', '这三个平台是销售平台费用的明细，仅供解释消耗去向，不再扣减一次。')}${profitRows.some(row => !knownNames.includes(row.科目)) ? comparisonPanel('其他原表科目', profitRows.filter(row => !knownNames.includes(row.科目)).map(row => row.科目), '', '保留原表科目，未擅自纳入利润计算。') : ''}</div>`
  const currentRegions = sheetRows(sheets.find(sheet => sheet.key === '本次区域经营汇总'))
  const regionalOverview = currentRegions.length ? card('本次导入 · 区域经营对比', '单位：万元。比较各区域订货、收入与回款；管理订货、毛利等完整数据可点击图表查看，不与公司核心口径混加。', table(currentRegions, [
    ['区域', '区域', 'text'], ['订货', '订货'], ['管理订货', '管理订货'], ['财务收入', '财务收入'], ['回款', '回款'], ['毛利', '毛利'],
  ], '本次区域经营对比'), '本次区域经营汇总') : ''

  const taskRows = targets.flatMap(r => [
    ['管理订货', 'Q3订货任务令', '管理订货'], ['财务收入', 'Q3收入任务令', '已完成收入'], ['回款', 'Q3回款任务令', '已完成回款'], ['毛利（含变更）', 'Q3毛利任务令', '已完成毛利'],
  ].map(([metric, target, actual]) => ({ 平台: r.平台, 指标: metric, 目标: r[target], 实际: r[actual], 达成率: divide(r[actual], r[target]), 缺口: difference(r[target], r[actual]) })))
  const region = [
    card('区域经营结果', '单位：万元。先看收入、毛利、费用和最终利润；负责人随区域列示。', table(platforms, [['平台', '作战平台', 'text'], ['区总', '负责人', 'text'], ['订货', '实际订货'], ['收入', '收入'], ['毛利', '订货毛利'], ['毛利率', '订货毛利率', 'percent'], ['销售费用', '销售费用'], ['贡献毛利', '贡献毛利'], ['分摊费用', '分摊费用'], ['最终利润', '最终利润']], '区域经营结果'), '02_作战平台经营结果'),
    card('区域任务令：目标、完成、差距', '单位：万元。Q3管理订货任务令对应管理订货；不以实际订货替代。任务令与公司核心表Q3目标是两套口径。', compactRegionalComparison(taskRows, [['平台', '平台', 'text'], ['指标', '考核指标', 'text'], ['目标', 'Q3任务令'], ['实际', '当前完成'], ['达成率', '达成率', 'percent'], ['缺口', '剩余缺口（负数为超额）']], '区域任务令'), '03_作战平台目标达成'),
    card('区域费用、分摊与预算', '金额单位：万元；费用率按原表定义。预算使用率不是业绩达成率，超100%表示超支。', table(rows(d.P06_预算执行), [['平台', '平台', 'text'], ['Q3费用目标', 'Q3费用预算'], ['已使用', '已使用'], ['剩余', '余额'], ['使用率', '使用率', 'percent'], ['费效比', '实际费效比', 'ratio']], '区域预算') + table(rows(d.P06_平台费用), [['平台', '平台', 'text'], ['合计', '费用合计'], ['订货毛利', '订货毛利'], ['费效比', '费效比', 'ratio'], ['管理平台分摊', '管理平台分摊'], ['销售平台分摊', '销售平台分摊']], '平台分摊') + table(raw('07'), [['区域', '区域', 'text'], ['销售费用率(费用/未税订货)', '销售费用率', 'percent'], ['综合费用率', '综合费用率', 'percent'], ['分摊占比', '分摊占比', 'percent']], '区域费用率'), '07_费用率', true),
    card('订单质量：数量达标与金额达标', '订单量单位：个。大订单是否达标应看金额占比，不能用数量占比替代。毛利率目标来自订单质量表。', table(rows(d.P09_订单质量), [['平台', '平台', 'text'], ['整体订单量', '订单数', 'number'], ['达标订单量', '达标订单数', 'number'], ['达标数量占比', '达标数量占比', 'percent'], ['达标金额占比', '达标金额占比', 'percent'], ['目标毛利率', '目标毛利率', 'percent'], ['实际毛利率', '实际毛利率', 'percent']], '订单质量'), '09_订单质量', true),
    card('省份全量经营对比', '金额单位：万元。展示全部省份，包括零订货与负现金流；无省份专项目标时只展示实际，不套用公司目标。', compactRegionalComparison(rows(d.P08_省份), [['省份', '省份', 'text'], ['订货', '订货'], ['毛利', '毛利'], ['毛利率', '毛利率', 'percent'], ['收入金额', '收入'], ['收入转化率', '收入转化率', 'percent'], ['回款金额', '回款'], ['回款转化率', '回款转化率', 'percent'], ['现金流', '现金流']], '全部省份'), '05_省份分布', true),
    card('区域现金流与机会储备', '金额单位：万元。现金流表为2026年项目口径；机会储备来自机会点清单，不与已完成业绩相加。', table(rows(d.P07_现金流区域), [['区域', '区域', 'text'], ['回款', '回款'], ['合同付款', '合同付款'], ['经营现金流', '经营现金流'], ['累计项目现金流', '累计项目现金流']], '区域现金流') + table(rows(d.P08_机会点按平台), [['平台', '平台', 'text'], ['机会点数', '机会点数', 'number'], ['可参与份额', '储备可参与份额']], '区域机会储备'), '11_现金流构成', true),
  ].join('')

  const industryKeys = ['P05_产业', 'P05_毛利流失', 'P06_产业费效', 'P05_子产业', 'P09_项目属性', 'P07_预付分产业', 'P07_账龄']
  const industryGroup = (row: Row) => {
    const name = String(row.大产业 || row.产业 || '').trim()
    if (name === '集成') return '集成'
    if (name.startsWith('服务')) return '服务'
    if (name === '场研') return '场研'
    return name === '合计' ? '合计' : '其他'
  }
  const industryCards = (d: Row) => {
    const ind = rows(d.P05_产业)
    return [
    card('产业目标与经营贡献', '单位：万元。目标取产业结构表“产业订货目标”，零目标不计算达成率；产业合计沿用原表范围。', progressList(ind.filter(r => r.产业 !== '合计'), '产业', '订货', '订货目标') + table(ind.map(r => ({ ...r, 达成率: Number(r.订货目标) > 0 ? (present(r.订货完成率) ? r.订货完成率 : divide(r.订货, r.订货目标)) : null, 缺口: difference(r.订货目标, r.订货) })), [['产业', '产业', 'text'], ['订货目标', '订货目标'], ['订货', '当前订货'], ['达成率', '达成率', 'percent'], ['缺口', '目标缺口'], ['未税订货', '未税订货'], ['毛利', '公司毛利'], ['毛利率', '毛利率', 'percent'], ['专项预算', '专项预算']], '产业目标贡献'), '04_产业结构'),
    card('毛利去向与产业投入效率', '单位：万元。解决方案毛利与公司留存毛利的差额单独展示；费效比保留两位小数。', table(rows(d.P05_毛利流失).map(r => ({ ...r, 差额: difference(r.解决方案毛利, r.公司留存毛利) })), [['产业', '产业', 'text'], ['解决方案毛利', '解决方案毛利'], ['公司留存毛利', '公司留存'], ['差额', '差额'], ['流失率', '差额占比', 'percent']], '产业毛利去向') + table(rows(d.P06_产业费效), [['产业', '产业', 'text'], ['合计费用', '费用合计'], ['产业毛利', '产业毛利'], ['产业贡毛', '产业贡献毛利'], ['费效比', '实际费效比', 'ratio']], '产业效率'), '08_产业费用构成'),
  ].join('')
  }
  const industryRegions = (name: string) => {
    const fields: Record<string, string[]> = { 集成: ['可参与份额-集成产业(万元)'], 服务: ['可参与份额-服务2.0(万元)', '可参与份额-服务1.0(含配套件)(万元)'], 场研: ['可参与份额-场研产业(万元)'], 其他: ['可参与份额-其他(万元)'] }
    const allocated = sheetRows(sheets.find(sheet => sheet.key === '16_机会点清单')).flatMap(row => {
      const amounts = (fields[name] || []).filter(key => present(row[key])).map(key => Number(row[key]))
      const amount = amounts.reduce((sum, value) => sum + value, 0)
      return amounts.length && amount !== 0 ? [{ ...row, 产业: name, 产业份额: amount }] : []
    })
    const grouped = businessGroups(allocated)
    if (!grouped.length) return ''
    const domain: [number, number] = [Math.min(0, ...allocated.map(row => row.产业份额)), Math.max(1, ...allocated.map(row => row.产业份额))]
    return `<div class="br-industry-regions">${grouped.map(group => card(`${name} · ${group.region}`, '机会储备口径：仅使用机会点表明确拆分的产业可参与份额（万元），不是已签订货或任务完成额；跨产业项目按原表份额拆分，不重复使用项目总额。', table(group.rows, [['客户经理', '客户经理', 'text'], ['机会点名称', '项目名称', 'text'], ['产业份额', '产业可参与份额（万元）']], '产业区域机会储备', undefined, domain), '16_机会点清单')).join('')}</div>`
  }
  const industryComparison = `<div class="be-industry-comparison">${
    card('产业订货目标与完成', '单位：万元。服务1.0与服务2.0按原表分别列示；合计不作为独立产业重复比较。', table(rows(d.P05_产业).filter(row => row.产业 !== '合计'), [['产业', '产业', 'text'], ['订货目标', '订货目标'], ['订货', '实际订货']], '产业订货对比', undefined, undefined, 'bar'), '04_产业结构') +
    card('产业毛利留存对比', '单位：万元。解决方案毛利与公司留存毛利对比，不跨口径相加。', table(rows(d.P05_毛利流失).filter(row => row.产业 !== '合计'), [['产业', '产业', 'text'], ['解决方案毛利', '解决方案毛利'], ['公司留存毛利', '公司留存毛利']], '产业毛利留存对比', undefined, undefined, 'bar'), '08_产业费用构成') +
    card('产业投入与贡献', '单位：万元。费用、产业毛利与产业贡献毛利各自沿用原表定义，不推算未提供值。', table(rows(d.P06_产业费效).filter(row => row.产业 !== '合计'), [['产业', '产业', 'text'], ['合计费用', '费用合计'], ['产业毛利', '产业毛利'], ['产业贡毛', '产业贡献毛利']], '产业投入与贡献', undefined, undefined, 'bar'), '08_产业费用构成')
  }</div>`
  const subIndustries = rows(d.P05_子产业).filter(row => row.子产业 !== '合计' && row.大产业 !== '合计')
  const projectAttributes = rows(d.P09_项目属性).filter(row => row.产业 !== '合计' && row.属性 !== '合计')
  const industryPrepayments = rows(d.P07_预付分产业).filter(row => row.产业 !== '合计')
  const industryCollections = rows(d.P07_账龄).filter(row => row.产业 !== '合计')
  const industryQuality = `<div class="be-industry-quality">${[
    subIndustries.length ? card('子产业订货与毛利贡献', '单位：万元。同一坐标横向对比全部子产业；毛利是订货对应的收益指标，不与订货相加。毛利率保留在明细。', table(subIndustries, [['大产业', '大产业', 'text'], ['子产业', '子产业', 'text'], ['订货', '订货'], ['毛利', '毛利'], ['毛利率', '毛利率', 'percent']], '子产业贡献对比', [['大产业', '大产业', 'text'], ['子产业', '子产业', 'text'], ['订货', '订货'], ['毛利', '毛利']]), '04_产业结构') : '',
    projectAttributes.length ? card('项目属性：规模与资金质量', '金额单位：万元。按产业与项目属性逐项比较，不汇总重复行；金额和转化率分图展示，负现金流保留。', table(projectAttributes, [['产业', '产业', 'text'], ['属性', '项目属性', 'text'], ['订货', '订货'], ['毛利', '毛利'], ['现金流', '现金流']], '项目属性金额对比') + table(projectAttributes, [['产业', '产业', 'text'], ['属性', '项目属性', 'text'], ['毛利率', '毛利率', 'percent'], ['回款转化率', '回款转化率', 'percent'], ['收入转化率', '收入转化率', 'percent']], '项目属性质量对比'), '15_项目属性分布') : '',
    industryPrepayments.length || industryCollections.length ? card('合同质量：预付与回款周期', '同一产业、签约年份横向比较。预付≥30%金额占比是合同条款分档，M1 / M3 / M6是签约后回款率，不能相加或视为同一指标；缺失不补零。', (industryPrepayments.length ? table(industryPrepayments, [['产业', '产业', 'text'], ['年份', '签约年', 'text'], ['预付≥30%金额占比', '预付≥30%金额占比', 'percent']], '各产业预付条款对比') : '') + (industryCollections.length ? table(industryCollections, [['产业', '产业', 'text'], ['年份', '签约年', 'text'], ['M1', '1个月回款率', 'percent'], ['M3', '3个月回款率', 'percent'], ['M6', '6个月回款率', 'percent']], '各产业回款周期对比') : ''), '13_回款转化率') : '',
  ].join('')}</div>`
  const industry = industryComparison + industryQuality + ['集成', '服务', '场研', '其他'].map(name => {
    const scoped = Object.fromEntries(industryKeys.map(key => [key, rows(d[key]).filter(row => industryGroup(row) === name)]))
    const regionalContent = industryRegions(name)
    if (!industryKeys.some(key => rows(scoped[key]).length) && !regionalContent) return ''
    return `<div class="br-industry-group" data-industry="${name}"><h3>${name}产业${name === '服务' ? ' · 服务1.0 / 服务2.0分别列示' : ''}</h3>${industryCards(scoped)}${regionalContent}</div>`
  }).join('')
  const taskSheet = (name: string) => sheets.find(sheet => sheet.key === name || sheet.key.includes(name))
  const taskValue = (row: Row, ...keys: string[]) => keys.map(key => row[key]).find(value => value !== undefined && value !== null && value !== '')
  const taskRowsFor = (name: string, kind: string) => sheetRows(taskSheet(name)).map(row => {
    const rawAmount = kind === '订货'
      ? taskValue(row, '可参与份额-总额(万元)', '*可参与份额-总额(万元)', '管理订货(万元)', '管理订货')
      : kind === '回款'
        ? taskValue(row, '计划回款金额(元)', '本月计划回款金额')
        : taskValue(row, '收入金额(含税/元)', '收入金额（含税）', '不含税金额(元)', '不含税金额')
    const amount = Number(rawAmount || 0) / (kind === '订货' ? 1 : 10000)
    return {
      类型: kind,
      产业: taskValue(row, '大产业', '产业') || '',
      区域: taskValue(row, '区域', '*项目归属', '项目归属', '区域组织') || '未填写',
      负责人: taskValue(row, '确认主要责任人', '主要责任人', '项目经理', '*客户经理', '客户经理') || '未填写',
      项目编码: taskValue(row, '子项目编码', '销售子项目编码', '*销售子项目编码', '机会点/子项目编码') || '',
      项目名称: taskValue(row, '机会点名称', '*机会点名称', '销售子项目名称', '*销售子项目名称/机会点名称', '机会点/子项目名称') || '',
      任务动作: taskValue(row, '任务令作战部署的目标/动作', '回款条件', '*合同约定回款方式') || '',
      标签: taskValue(row, '任务令标签', '10月任务令标签', '保底/冲刺') || '未填写',
      月份: taskValue(row, '月份', '月度') || '',
      任务金额: amount,
      已完成: taskEvidence(row, kind),
    }
  })
  const orderTasks = taskRowsFor('订货任务令', '订货')
  const receiptTasks = taskRowsFor('回款任务令', '回款')
  const revenueTasks = taskRowsFor('财务收入任务令', '财务收入')
  const allTasks = [...orderTasks, ...receiptTasks, ...revenueTasks]
  const taskSummary = [orderTasks, receiptTasks, revenueTasks].map((items, index) => ({
    类型: ['订货', '回款', '财务收入'][index],
    任务数: items.length,
    任务金额: items.reduce((sum, row) => sum + Number(row.任务金额 || 0), 0),
    待核验: items.filter(row => row.已完成 !== '未提供完成证据').length,
    保底: items.filter(row => row.标签 === '保底').length,
    冲刺: items.filter(row => row.标签 === '冲刺').length,
  }))
  const companyProgress = sheetRows(taskSheet('任务令公司进度'))
  const regionProgress = sheetRows(taskSheet('任务令区域进度'))
  const ownerProgress = sheetRows(taskSheet('任务令责任人进度'))
  const rawProgressSheet = taskSheet('任务令进度总表原表')
  const rawProgress = sheetRows(rawProgressSheet)
  const taskContent = [
    card('公司年度目标进度', '单位：万元。对照年度目标与1—10月累计完成，年度缺口沿用任务进度总表口径。', table(companyProgress, [['指标', '经营指标', 'text'], ['年度目标', '年度目标'], ['1-10月完成', '1—10月完成'], ['年度完成率', '年度完成率', 'percent'], ['年度缺口', '年度缺口']], '公司年度目标进度'), '任务令公司进度'),
    card('本月任务令兑现', '单位：万元。展示本月冲刺任务、当前完成、完成率、排名与剩余缺口。', table(companyProgress, [['指标', '经营指标', 'text'], ['本月任务令', '本月任务令'], ['本月完成', '本月完成'], ['本月完成率', '本月完成率', 'percent'], ['本月排名', '进度排名', 'number'], ['本月缺口', '本月缺口']], '本月任务令兑现'), '任务令公司进度'),
    card('区域任务推进', '单位：万元。按指标与区域比较任务令、分周完成、累计完成、进度和缺口。', groupedTable(regionProgress, [['指标', '指标', 'text'], ['区域', '区域', 'text'], ['责任人', '责任人', 'text'], ['任务令', '任务令'], ['第一周完成', '第一周'], ['第二周完成', '第二周'], ['第三周完成', '第三周'], ['第四周完成', '第四周'], ['合计完成', '累计完成'], ['完成率', '完成率', 'percent'], ['排名', '排名', 'number'], ['缺口', '缺口']], '区域任务推进'), '任务令区域进度'),
    card('责任人任务推进', '单位：万元。按客户经理、BD与项目经理查看个人任务、累计完成、排名和缺口。', groupedTable(ownerProgress, [['角色', '角色', 'text'], ['指标', '指标', 'text'], ['区域', '区域', 'text'], ['责任人', '责任人', 'text'], ['任务令', '任务令'], ['合计完成', '累计完成'], ['完成率', '完成率', 'percent'], ['排名', '排名', 'number'], ['缺口', '缺口']], '责任人任务推进'), '任务令责任人进度'),
    card('任务令总览', '金额统一折算为万元。手工完成标记和填写金额仅作为待核验线索，不直接计为完成。', table(taskSummary, [['类型', '任务类型', 'text'], ['任务数', '任务数', 'number'], ['任务金额', '任务金额（万元）'], ['待核验', '待核验', 'number'], ['保底', '保底任务', 'number'], ['冲刺', '冲刺任务', 'number']], '任务令汇总'), '订货任务令,回款任务令,财务收入任务令'),
    card('任务令项目明细', '逐项展示负责人、区域、目标动作和证据状态；待核验不代表已经完成。', groupedTable(allTasks, [['类型', '类型', 'text'], ['区域', '区域', 'text'], ['负责人', '负责人', 'text'], ['项目编码', '项目编码', 'text'], ['项目名称', '项目名称', 'text'], ['任务动作', '任务动作', 'text'], ['标签', '任务标签', 'text'], ['月份', '月份', 'text'], ['任务金额', '任务金额（万元）'], ['已完成', '证据状态', 'text']], '任务令项目明细'), '订货任务令,回款任务令,财务收入任务令'),
    rawProgress.length ? '<button type="button" class="br-source-group" data-source-ids="任务令进度总表原表">查看任务进度总表完整原表（下钻核对）</button>' : '',
  ].join('')
  const group = (key: string, no: string, title: string, desc: string, content: string) => `<section class="br-section" data-section="${key}"><div class="br-section-head"><span class="br-section-badge">${bizIcon(SECTION_ICONS[key] || 'overview')}</span><div><h3><small>${no}</small>${title}</h3><p>${desc}</p></div></div>${content}</section>`
  return `<div class="br-report"><div class="br-scope"><b>统计范围</b> ${esc(scope)}<p>${esc(scopeNote)}</p><small>空值显示“未提供”；历史趋势不虚设目标。所有金额表均标明单位，来源明细保留完整行列。</small></div>
    ${group('overall', '01', '核心经营总览', '年度目标与当前达成，先识别经营结果与关键差距。', `<div class="br-kpis">${tiles}</div>${executiveCharts}${overall[0]}`)}
    ${group('taskOrder', '02', '任务令执行', '统一查看订货、回款与财务收入任务，跟踪责任、目标和兑现。', taskContent)}
    ${group('structure', '03', '经营结构分析', '集中查看公司各类实际费用构成。', overall[2])}
    ${group('region', '04', '区域经营对标', '四区域年度目标、月度实际与回款计划分口径展示。', authoritativeRegions(sheets) || regionalOverview + region + rawSheets(sheets, ['02', '03', '05', '06', '07', '09', '11'], '区域来源明细'))}
    ${group('industry', '05', '产业经营分析', '从产业贡献到毛利留存，观察结构与投入效率。', industry + rawSheets(sheets, ['04', '08', '13', '14', '15'], '产业来源明细'))}
    ${group('foundation', '06', '经营发展基础', '基于已导入的现金、收入支撑、合同条款与回款数据，不虚设基础设施指标。', `${overall[3]}${overall[4]}${rawSheets(sheets, ['12','13','14'], '经营基础来源明细')}`)}
    ${group('projects', '07', '项目监测与兑现', '区分机会储备、预算承接和已完成订单，跟踪计划到结果。', overall[5] + execution + rawSheets(sheets, ['16','17','18','19'], '项目来源明细'))}
    </div>`
}
