import { renderReportChart } from './businessReportCharts'
import { cartesianChart } from './businessCartesianChart'

export function applyChartTypes(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>('[data-chart-model],[data-cartesian-model]').forEach(element => {
    if (element.parentElement?.closest('[data-chart-model],[data-cartesian-model]')) return
    const mode = element.closest('[data-editor-charttype]')?.getAttribute('data-editor-charttype') || 'auto'
    if (element.dataset.renderedMode === mode || (!element.dataset.renderedMode && mode === 'auto')) return
    try {
      if (element.dataset.chartModel) {
        const model = JSON.parse(element.dataset.chartModel)
        const composition = ['费用构成', '机会阶段'].includes(model.label)
        const restricted = ['pie', 'donut'].includes(mode) && !composition
        element.innerHTML = (restricted ? '<p class="br-note">此图不是已确认的构成数据，保留原图；饼图和环图仅适用于费用构成、机会阶段份额。</p>' : '') + renderReportChart(model.data, model.columns, model.label, model.domain, restricted ? 'auto' : mode)
      } else {
        const model = JSON.parse(element.dataset.cartesianModel!)
        const options = { ...model.options }
        const supported = ['auto', 'bar', 'line', 'points'].includes(mode)
        if (mode !== 'auto' && supported) { options.line = mode !== 'bar'; options.points = mode === 'points' }
        const temporary = document.createElement('div')
        temporary.innerHTML = cartesianChart(model.rows, model.series, options)
        element.innerHTML = (supported ? '' : '<p class="br-note">月度趋势保留时间轴，不转换为构成图或明细表。</p>') + temporary.firstElementChild!.innerHTML
      }
      element.dataset.renderedMode = mode
    } catch {
      element.dataset.renderedMode = mode
    }
  })
}
