import { cartesianChart } from './businessCartesianChart'

type Row = Record<string, any>
type Column = [string, string, string?]
const escape = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!))
const valid = (v: unknown) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v))
// 系列色固定顺序取自 --series-N（浅/深色各自经色板校验），状态色（danger 等）不复用为系列色。
const colors = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']
export const businessChartTheme = { lineWidth:2, areaOpacity:0.1, compositionColors:[...colors, 'var(--series-5)', 'var(--series-6)'] }
function value(v: unknown, kind?: string) {
  if (!valid(v)) return '未提供'
  if (kind === 'percent') return `${(Number(v)*100).toFixed(1)}%`
  return Number(v).toLocaleString('zh-CN', {maximumFractionDigits:kind === 'ratio' ? 2 : 1})
}

/** Charts keep the full dataset in the drill-down table; every plotted mark has a visible value. */
export function reportChart(data: Row[], columns: Column[], label: string, domain?: [number, number]): string {
  return `<div data-chart-model="${escape(JSON.stringify({ data, columns, label, domain }))}">${renderReportChart(data, columns, label, domain)}</div>`
}

export function renderReportChart(data: Row[], columns: Column[], label: string, domain?: [number, number], mode = 'auto'): string {
  if (!data.length) return '<p class="br-empty">暂无该项数据</p>'
  const configured: Record<string, string[]> = {
    '本次区域经营对比':['订货','财务收入','回款'],
    '公司目标完成与预测':['全年目标','实际'], '区域任务令':['目标','实际'], '产业目标贡献':['订货目标','订货'],
    '区域经营结果':['收入','毛利','最终利润'], '公司完整损益':['公司', '利润核算角度'],
    '区域预算':['Q3费用目标','已使用'], '公司费用预算':['Q3费用目标','已使用'],
    '平台分摊':['合计','管理平台分摊','销售平台分摊'], '全部省份':['订货','现金流'],
    '产业毛利去向':['解决方案毛利','公司留存毛利','差额'], '产业效率':['产业毛利','合计费用','产业贡毛'],
    '滚动冲刺':['可参与份额-总额'], '年初预算承接':['可参与份额-总额(万元)'],
    '已完成订单':['销售合同金额(未税)','当期毛利'],
    '预付条款':['有预付金额占比','预付≥30%金额占比'],
    '项目年份现金流':['经营现金流','累计项目现金流'], '区域现金流':['经营现金流','累计项目现金流'],
    '机会储备':['可参与份额','预估毛利'], '机会阶段':['可参与份额'], '区域机会储备':['可参与份额'],
    '子产业':['订货','毛利'], '项目属性':['订货','毛利'],
    '订单质量':['达标数量占比','达标金额占比','目标毛利率','实际毛利率'],
    '公司年度目标进度':['年度目标','1-10月完成'], '本月任务令兑现':['本月任务令','本月完成'],
    '区域任务推进':['任务令','合计完成'], '责任人任务推进':['任务令','合计完成'],
  }
  const numeric = columns.filter(c => c[2] !== 'text')
  const chosen = configured[label]
  const series = chosen ? chosen.map(key => numeric.find(c => c[0]===key)).filter((c): c is Column => !!c) : numeric.slice(0,3)
  if (!series.length) return `<div class="br-records">${data.map(row => `<dl class="br-record">${columns.map(([key, title, kind]) => `<div><dt>${escape(title)}</dt><dd>${kind === 'text' ? escape(row[key] ?? '未提供') : value(row[key], kind)}</dd></div>`).join('')}</dl>`).join('')}</div>`
  const nameKeys = columns.filter(c => c[2]==='text').map(c => c[0])
  const identityKeys = ['责任人', '负责人', '客户经理', '项目名称', '项目', '名称']
  const labelKeys = [...nameKeys.filter(key => identityKeys.includes(key)), ...nameKeys.filter(key => !identityKeys.includes(key))]
  const name = (r: Row) => labelKeys.map(key => String(r[key] ?? '')).filter(Boolean).join(' · ')
  const legend = `<div class="br-chart-legend">${series.map((c,i)=>`<span><i style="background:${colors[i%4]}"></i>${escape(c[1])}</span>`).join('')}</div>`
  const shown = data
  const count = `<p class="br-chart-count">全部 ${data.length} 项</p>`
  if (mode === 'table') return `<table class="br-table"><thead><tr>${columns.map(column => `<th>${escape(column[1])}</th>`).join('')}</tr></thead><tbody>${data.map(row => `<tr>${columns.map(column => `<td>${column[2] === 'text' ? escape(row[column[0]]) : value(row[column[0]], column[2])}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  if (['bar', 'line', 'points'].includes(mode)) {
    const kinds = new Set(series.map(column => column[2] || 'money'))
    if (kinds.size > 1) return `<p class="br-note">包含不同单位，保留原图避免共用坐标误导。</p>${renderReportChart(data, columns, label, domain)}`
    const kind = series[0]?.[2] || 'money'
    const unit = kind === 'percent' ? '%' : kind === 'number' ? '个' : kind === 'ratio' ? '比值' : '万元'
    const chartRows = data.map(row => Object.fromEntries([['category', name(row)], ...series.map(column => [column[0], valid(row[column[0]]) ? Number(row[column[0]]) * (kind === 'percent' ? 100 : 1) : null])]))
    const chartDomain: [number, number] | undefined = domain && kind === 'percent' ? [domain[0] * 100, domain[1] * 100] : domain
    return `${legend}${cartesianChart(chartRows, series.map((column,index) => ({ key:column[0], label:column[1], color:colors[index%4]! })), { name:'category', title:label, unit, domain: chartDomain, line: mode !== 'bar', points: mode === 'points' })}${count}`
  }
  // Composition: true circumference arcs, with an adjacent numeric legend.
  const compositionKey = label === '费用构成' ? '金额' : label === '机会阶段' ? '可参与份额' : ''
  let parts = data.filter(r => !nameKeys.some(k => /^(合计|总计|全部)$/.test(String(r[k] ?? ''))))
  if (['pie','donut'].includes(mode) && (!compositionKey || !parts.length || parts.some(row => !valid(row[compositionKey]) || Number(row[compositionKey]) < 0) || !parts.some(row => Number(row[compositionKey]) > 0))) return `<p class="br-note">构成图要求完整、非负且合计大于零的数据，当前保留原图。</p>${renderReportChart(data, columns, label, domain)}`
  if (compositionKey && parts.length && (parts.length <= 6 || ['pie','donut'].includes(mode)) && parts.every(r=>valid(r[compositionKey]) && Number(r[compositionKey])>=0) && parts.some(r=>Number(r[compositionKey])>0)) {
    const total = parts.reduce((s,r)=>s+Number(r[compositionKey]),0)
    const pie = mode === 'pie' || (mode === 'auto' && label === '机会阶段')
    let offset=0
    const palette = businessChartTheme.compositionColors
    const arcs=parts.map((r,i)=>{const pct=Number(r[compositionKey])/total*100;const arc=`<circle cx="80" cy="80" r="${pie?29:58}" fill="none" stroke="${palette[i%palette.length]}" stroke-width="${pie?58:22}" pathLength="100" stroke-dasharray="${pct} ${100-pct}" stroke-dashoffset="${-offset}" transform="rotate(-90 80 80)"/>`;offset+=pct;return arc}).join('')
    return `<div class="br-chart br-donut" data-chart-kind="${pie?'pie':'donut'}"><svg viewBox="0 0 160 160" role="img" aria-label="${escape(label)}">${arcs}${pie?'':`<text x="80" y="78" text-anchor="middle" fill="var(--text)" font-size="16" font-weight="700">${value(total)}</text><text x="80" y="97" text-anchor="middle" fill="var(--text-sub)" font-size="11">实际费用 · 万元</text>`}</svg><div>${pie?`<p>份额合计 <b>${value(total)} 万元</b></p>`:''}${parts.map((r,i)=>`<p><i style="background:${palette[i%palette.length]}"></i>${escape(name(r))}<b>${value(r[compositionKey])} · ${value(r[compositionKey]/total,'percent')}</b></p>`).join('')}</div></div><p class="br-chart-count">组成占比按全部有效明细计算 · 点击查看完整数据</p>`
  }
  // Historical series use a shared percentage axis. Missing points break the line.
  if (['预付条款','回款转化'].includes(label) && shown.length <= 6) {
    const width=460,height=200,L=50,R=36,T=22,B=30,pw=width-L-R,ph=height-T-B
    const values=shown.flatMap(r=>series.map(c=>valid(r[c[0]]) ? Number(r[c[0]]) : 0))
    const ymax=Math.max(1,...values), ymin=Math.min(0,...values), span=ymax-ymin
    const X=(i:number)=>L+(shown.length>1 ? i*pw/(shown.length-1) : pw/2)
    const Y=(v:number)=>T+ph-(v-ymin)/span*ph
    let svg=Array.from({length:5},(_,i)=>{const n=ymin+span*i/4;return `<line x1="${L}" x2="${width-R}" y1="${Y(n)}" y2="${Y(n)}" stroke="var(--tint-line)"/><text x="${L-8}" y="${Y(n)+4}" text-anchor="end" fill="var(--text-muted)" font-size="12">${value(n,'percent')}</text>`}).join('')
    series.forEach((c,si)=>{
      let path='',active=false
      const segments:number[][]=[]
      shown.forEach((r,i)=>{if(!valid(r[c[0]])){active=false;return}if(!active)segments.push([]);segments[segments.length-1]!.push(i);path+=`${active?'L':'M'}${X(i)},${Y(Number(r[c[0]]))} `;active=true})
      segments.forEach(segment=>{if(segment.length<2)return;const first=segment[0]!,last=segment[segment.length-1]!;const outline=segment.map(i=>`L${X(i)},${Y(Number(shown[i]![c[0]]))}`).join(' ');svg+=`<path d="M${X(first)},${Y(0)} ${outline} L${X(last)},${Y(0)} Z" fill="${colors[si%4]}" opacity="${businessChartTheme.areaOpacity}"/>`})
      svg+=`<path d="${path}" fill="none" stroke="${colors[si%4]}" stroke-width="${businessChartTheme.lineWidth}"/>`
      shown.forEach((r,i)=>{if(valid(r[c[0]]))svg+=`<circle cx="${X(i)}" cy="${Y(Number(r[c[0]]))}" r="3.5" fill="${colors[si%4]}" stroke="var(--br-card-bg,#fff)" stroke-width="1.5"/><text x="${X(i)}" y="${Y(Number(r[c[0]]))+(si%2 ? 17 : -9)}" text-anchor="${i===0&&shown.length>1?'start':i===shown.length-1&&shown.length>1?'end':'middle'}" fill="var(--text)" font-size="12.5" font-weight="600" stroke="var(--br-card-bg,#fff)" stroke-width="3" paint-order="stroke">${value(r[c[0]],c[2])}</text>`})
    })
    svg+=shown.map((r,i)=>`<text x="${X(i)}" y="${height-10}" fill="var(--text-sub)" text-anchor="middle" font-size="13">${escape(name(r))}</text>`).join('')
    return `${legend}<div class="br-chart" data-chart-kind="line"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(label)}">${svg}</svg></div>${count}`
  }
  if (label === '订单质量' || label === '区域费用率' || label === '产业回款' || label === '产业预付') {
    const cells=series.filter(c=>c[2]==='percent')
    const used=cells.length ? cells : series
    return `<div class="br-chart br-heat" data-chart-kind="heatmap" style="--heat-cols:${used.length}"><div class="br-heat-head"><span>范围</span>${used.map(c=>`<span>${escape(c[1])}</span>`).join('')}</div>${shown.map(r=>`<div class="br-heat-row"><span>${escape(name(r))}</span>${used.map(c=>`<span style="background:color-mix(in srgb,var(--primary) ${valid(r[c[0]]) ? Math.min(65,Math.max(5,Number(r[c[0]])*65)) : 0}%,transparent)">${value(r[c[0]],c[2])}</span>`).join('')}</div>`).join('')}</div>${count}`
  }
  // Zero-centred grouped bars preserve negative profits/cash flow rather than hiding them.
  const maximum=domain?.[1] ?? Math.max(1,...shown.flatMap(r=>series.map(c=>valid(r[c[0]]) ? Math.abs(Number(r[c[0]])) : 0)))
  const negative=shown.some(r=>series.some(c=>valid(r[c[0]]) && Number(r[c[0]])<0))
  // Short category names → vertical grouped columns with values on top; long project names stay as a horizontal list.
  if (!domain && !/滚动冲刺|年初预算承接|已完成订单/.test(label) && shown.length <= 8 && shown.every(row => name(row).length <= 18)) {
    const unit = series.every(column => column[2] === 'percent') ? '%' : series.every(column => column[2] === 'number') ? '个' : series.some(column => column[2] === 'ratio') ? '比值' : '万元'
    const chartRows = shown.map(row => Object.fromEntries([['category', name(row)], ...series.map(column => [column[0], valid(row[column[0]]) ? Number(row[column[0]]) * (column[2] === 'percent' ? 100 : 1) : null])]))
    return `${legend}<div class="br-chart" data-chart-kind="${negative?'diverging':'grouped-bars'}">${cartesianChart(chartRows, series.map((column,index) => ({ key:column[0], label:column[1], color:colors[index%4]! })), { name:'category', title:label, unit, domain })}</div>${count}`
  }
  const minimum=domain?.[0] ?? Math.min(0,...shown.flatMap(row=>series.map(column=>valid(row[column[0]])?Number(row[column[0]]):0)))
  const span=maximum-minimum
  const zero=-minimum/span*100
  const axis=`<div class="br-comparison-head"><span>分类</span><div class="br-horizontal-axis">${[0,.25,.5,.75,1].map(tick=>`<span>${value(minimum+tick*span,series[0]?.[2])}</span>`).join('')}</div><span>数值</span></div>`
  return `${legend}<div class="br-chart br-plot-bars br-comparison" data-chart-kind="${negative?'diverging':'grouped-bars'}">${axis}${shown.map(row=>`<div class="br-plot-row"><span class="br-plot-name">${escape(name(row))}</span><div class="br-comparison-series">${series.map((column,index)=>{const amount=valid(row[column[0]])?Number(row[column[0]]):0;return `<div class="br-series-row"><div class="br-series-track" style="--comparison-zero:${zero}%"><i style="left:${(Math.min(0,amount)-minimum)/span*100}%;width:${Math.abs(amount)/span*100}%;background:${colors[index%4]}"></i></div><b>${value(row[column[0]],column[2])}</b></div>`}).join('')}</div></div>`).join('')}</div>${count}`
}
