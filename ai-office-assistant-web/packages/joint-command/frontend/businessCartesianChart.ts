type Series = { key: string; label: string; color: string }
type Row = Record<string, unknown>
const escape = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]!))
const numeric = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

export function smoothLinePath(points: ({ x: number; y: number } | null)[]): string {
  let previous: { x: number; y: number } | null = null
  return points.map(point => {
    if (!point) { previous = null; return '' }
    const middle = previous ? (previous.x + point.x) / 2 : point.x
    const segment = previous ? `C${middle},${previous.y} ${middle},${point.y} ${point.x},${point.y}` : `M${point.x},${point.y}`
    previous = point
    return segment
  }).join(' ')
}

export function cartesianChart(rows: Row[], series: Series[], options: { name: string; title: string; unit: string; line?: boolean; points?: boolean; domain?: [number, number]; width?: number; decimals?: number }) {
  const format = (value: number) => value.toLocaleString('zh-CN', { maximumFractionDigits: options.decimals ?? 1 })
  const values = rows.flatMap(row => series.flatMap(item => numeric(row[item.key]) ? [row[item.key] as number] : []))
  const rawMinimum = options.domain?.[0] ?? Math.min(0, ...values)
  const rawMaximum = options.domain?.[1] ?? Math.max(1, ...values)
  const roughStep = (rawMaximum - rawMinimum || 1) / 4
  const magnitude = 10 ** Math.floor(Math.log10(roughStep))
  const step = ([1, 2, 5, 10].find(candidate => candidate * magnitude >= roughStep) || 10) * magnitude
  const minimum = Math.floor(rawMinimum / step) * step
  const maximum = Math.ceil(rawMaximum / step) * step
  const span = maximum - minimum || 1
  const width = options.width || 720, height = 340, left = 82, right = 28, top = 72, bottom = 72
  const plotWidth = width - left - right, plotHeight = height - top - bottom
  const positionY = (value: number) => top + (maximum - value) / span * plotHeight
  const positionX = (index: number) => left + (index + .5) * plotWidth / Math.max(1, rows.length)
  const ticks = Array.from({ length: Math.round(span / step) + 1 }, (_, index) => minimum + step * index)
  let content = `<text x="${left}" y="20" fill="currentColor" font-size="13">${escape(options.unit)}</text>`
  content += ticks.map(tick => `<line x1="${left}" x2="${width-right}" y1="${positionY(tick)}" y2="${positionY(tick)}" stroke="currentColor" opacity=".15"/><text x="${left-10}" y="${positionY(tick)+4}" text-anchor="end" fill="currentColor" font-size="12">${format(tick)}</text>`).join('')
  content += `<path d="M${left},${top} V${height-bottom} H${width-right}" fill="none" stroke="currentColor" opacity=".5"/><line x1="${left}" x2="${width-right}" y1="${positionY(0)}" y2="${positionY(0)}" stroke="currentColor" opacity=".5"/>`
  const placedLabels: { x: number; y: number; width: number }[] = []
  series.forEach((item, seriesIndex) => {
    if (options.line && !options.points) {
      const path = smoothLinePath(rows.map((row, index) => {
        const amount = row[item.key]
        return numeric(amount) ? { x: positionX(index), y: positionY(amount) } : null
      }))
      content += `<path d="${path}" fill="none" stroke="${item.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`
    }
    rows.forEach((row, index) => {
      const amount = row[item.key], center = positionX(index)
      const barWidth = Math.min(28, plotWidth / Math.max(1, rows.length) / (series.length+2))
      const position = options.line ? center : center + (seriesIndex-(series.length-1)/2)*(barWidth+4)
      if (!numeric(amount)) return
      const point = positionY(amount), baseline = positionY(0)
      content += `<g class="br-series-row" data-series-index="${seriesIndex}"><title>${escape(row[options.name])} · ${escape(item.label)}：${format(amount)} ${escape(options.unit)}</title>`
      content += options.line ? `<circle cx="${position}" cy="${point}" r="4" fill="${item.color}"/>` : `<rect x="${position-barWidth/2}" y="${Math.min(point, baseline)}" width="${barWidth}" height="${Math.abs(point-baseline)}" rx="2" fill="${item.color}"/>`
      const labelOffset = options.line && seriesIndex % 2 && point < height-bottom-24 ? 19 : -9-seriesIndex*13
      let labelY = (!options.line && amount < 0 ? baseline : point) + labelOffset
      const labelWidth = format(amount).length * 9
      if (!options.line) {
        while (placedLabels.some(label => Math.abs(label.x-position) < (label.width+labelWidth)/2+4 && Math.abs(label.y-labelY) < 19)) labelY -= 20
      }
      placedLabels.push({ x: position, y: labelY, width: labelWidth })
      content += `<text x="${position}" y="${labelY}" text-anchor="middle" fill="currentColor" font-size="12">${format(amount)}</text></g>`
    })
  })
  content += rows.map((row, index) => {
    const label = String(row[options.name] ?? '')
    const parts = label.match(/.{1,8}/gu) || ['']
    return `<g class="br-plot-row"><text x="${positionX(index)}" y="${height-bottom+22}" text-anchor="middle" fill="currentColor" font-size="12">${parts.map((part, partIndex) => `<tspan x="${positionX(index)}" dy="${partIndex ? 16 : 0}">${escape(part)}</tspan>`).join('')}</text></g>`
  }).join('')
  return `<div data-cartesian-model="${escape(JSON.stringify({ rows, series, options }))}"><svg class="br-cartesian" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(options.title)}，${escape(options.unit)}"><title>${escape(options.title)}</title>${content}</svg></div>`
}
