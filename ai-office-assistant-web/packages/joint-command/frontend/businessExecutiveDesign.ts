const pageFocus: Record<string, [string, string]> = {
  overall: ['年度目标 · 利润结果 · 资金兑现', '先看达成与缺口，再核对损益构成；公司与产业口径不混加。'],
  taskOrder: ['目标兑现 · 区域总体 · 责任到人', '先看年度与本月，再展开区域个人任务；待核验不代表已完成。'],
  structure: ['费用规模 · 主要消耗 · 构成占比', '同一刻度比较费用，优先关注主要支出，不将费用占比当作业绩达成率。'],
  industry: ['经营贡献 · 毛利留存 · 投入效率', '按产业独立观察目标和贡献，子产业、合同质量与机会储备按需展开。'],
  foundation: ['现金缺口 · 收入支撑 · 合同质量', '区分万元与元；项目年份、签约年份不等于当前经营年度。'],
  projects: ['机会储备 · 计划承接 · 实际兑现', '储备不是完成；分档不是漏斗；逐项目追溯负责人、动作与结果。'],
}

function disclosure(doc: Document, node: Element, title: string, hint = '点击展开') {
  const details = doc.createElement('details')
  details.className = 'be-disclosure'
  const summary = doc.createElement('summary')
  const label = doc.createElement('strong')
  label.textContent = title
  const meta = doc.createElement('span')
  meta.textContent = hint
  summary.append(label, meta)
  details.append(summary)
  node.before(details)
  details.append(node)
  return details
}

export function applyExecutiveDesign(doc: Document, page: string) {
  const focus = pageFocus[page]
  const section = doc.querySelector<HTMLElement>(`[data-section="${page}"]`)
  if (!focus || !section) return
  section.classList.add('be-page', `be-${page}`)
  const badge = section.querySelector('.br-section-badge')
  const icon = doc.createElement('img')
  icon.src = `/personal-office-assistant/management-${page}.png`
  icon.className = 'be-page-icon'
  icon.alt = ''
  icon.width = 40
  icon.height = 40
  if (badge) badge.replaceChildren(icon)
  else section.querySelector('.br-section-head')?.prepend(icon)
  const brief = doc.createElement('div')
  brief.className = 'be-focus'
  const title = doc.createElement('strong')
  title.textContent = focus[0]
  const text = doc.createElement('span')
  text.textContent = focus[1]
  brief.append(title)
  section.querySelector('.br-section-head')?.after(brief)
  brief.append(text)
  disclosure(doc, text, '阅读口径', '').classList.add('be-method')

  const titles: Record<string, RegExp> = {
    taskOrder: /^(责任人任务推进|任务令项目明细|任务令总览)$/,
    industry: /^(子产业|项目属性|产业预付|产业回款|子产业与项目属性|产业合同条款与回款质量)$/,
    projects: /^(滚动冲刺|年初全预算承接|已完成订单)/,
  }
  section.querySelectorAll<HTMLElement>('.br-chart-card').forEach(card => {
    if (titles[page]?.test(card.dataset.chartTitle || '')) {
      disclosure(doc, card, card.dataset.chartTitle || '明细', '明细与来源 · 点击展开')
    }
  })
  if (page === 'taskOrder') {
    section.querySelectorAll('.br-owner-grid').forEach(grid => {
      const heading = grid.previousElementSibling
      if (heading?.tagName === 'H4') heading.remove()
      disclosure(doc, grid, '个人 / 子区域任务', `${grid.children.length} 位责任人 · 点击展开`)
    })
  }
  if (page === 'industry') {
    section.querySelectorAll<HTMLElement>('.be-industry-quality > .br-chart-card').forEach(card => {
      card.dataset.layoutKey = `industry-quality:${card.dataset.chartTitle}`
    })
    section.querySelectorAll<HTMLElement>('.be-industry-comparison > .br-chart-card').forEach(card => {
      card.dataset.layoutKey = `industry-comparison-v2:${card.dataset.chartTitle}`
    })
    section.querySelectorAll('.br-industry-regions').forEach(group => {
      disclosure(doc, group, '区域机会储备', '按区域查看项目与负责人')
    })
    section.querySelectorAll<HTMLElement>('.br-industry-group').forEach(group => {
      const heading = group.querySelector(':scope > h3')
      const details = disclosure(doc, group, heading?.textContent || '产业明细', '目标 · 毛利 · 费用 · 区域明细')
      details.classList.add('be-industry-detail')
      details.dataset.industry = group.dataset.industry
      heading?.remove()
    })
  }
  if (page === 'structure') {
    const template = section.querySelector<HTMLTemplateElement>('template[data-analysis-table]')
    if (template) {
      const detail = doc.createElement('div')
      detail.className = 'be-expense-records'
      detail.append(template.content.cloneNode(true))
      section.append(detail)
      disclosure(doc, detail, '费用明细', '金额与占比 · 点击展开')
    }
  }
  section.querySelectorAll<HTMLElement>('.br-chart-card > .br-note').forEach(note => {
    if ((note.textContent?.length || 0) < 20) return
    const units = note.textContent?.match(/(?:金额|现金流汇总|机会份额|订单量)?单位[：:]\s*[^。；]+/)
    disclosure(doc, note, units?.[0] || '统计口径', '说明').classList.add('be-method')
  })
  const sources = Array.from(section.querySelectorAll<HTMLElement>(':scope > .br-source-group'))
  if (sources.length) {
    const directory = doc.createElement('div')
    directory.className = 'be-source-list'
    section.append(directory)
    sources.forEach(source => directory.append(source))
    disclosure(doc, directory, '来源与核对口径', `${sources.length} 个入口 · 点击展开`)
  }
  if (page === 'overall') {
    const flow = section.querySelector('.be-profit-flow')
    const platform = section.querySelector('.be-platform')
    if (flow && platform) flow.append(platform)
    for (const name of ['combined']) {
      const header = flow?.querySelector(`.be-${name} > header`)
      if (!header) continue
      const image = doc.createElement('img')
      image.src = '/personal-office-assistant/profit-source.png'
      image.alt = ''
      image.className = 'be-profit-icon'
      image.width = 40
      image.height = 40
      header.prepend(image)
    }
    section.querySelectorAll('details.be-disclosure').forEach(details => {
      const panel = doc.createElement('section')
      panel.className = 'be-open-information'
      const summary = details.querySelector(':scope > summary')
      const heading = doc.createElement('h4')
      heading.textContent = summary?.querySelector('strong')?.textContent || ''
      summary?.remove()
      panel.append(heading, ...Array.from(details.childNodes))
      details.replaceWith(panel)
    })
  }
}

export function numberBusinessSections(doc: Document, page: string) {
  const section = doc.querySelector<HTMLElement>(`[data-section="${page}"]`)
  if (!section) return
  const heading = section.querySelector('.br-section-head h3')
  heading?.querySelector(':scope > small')?.remove()
  const badge = (target: Element, value: string) => {
    target.querySelectorAll(':scope > .business-step').forEach(element => element.remove())
    const number = doc.createElement('span')
    number.className = 'business-step'
    number.textContent = value
    target.prepend(number)
  }
  if (page === 'overall') {
    if (heading) badge(heading, '01')
    const profitHeading = section.querySelector('.be-profit-heading h3')
    if (profitHeading) badge(profitHeading, '06')
    section.querySelectorAll('.be-profit-panel > header h4').forEach((item, index) => badge(item, `06.${String(index + 1).padStart(2, '0')}`))
    return
  }
  const selectors = '.br-chart-card,.be-disclosure:not(.be-method),.br-region-group,.br-owner-panel,.br-task-overview'
  const numbers = new Map<Element, string>()
  const counters = new Map<Element, number>()
  section.querySelectorAll(selectors).forEach(block => {
    if (block.closest('.be-method,.br-source-group,.be-source-list')) return
    const label = block.querySelector(':scope > header h3,:scope > header .br-card-title,:scope > h3,:scope > h4,:scope > summary > strong')
    if (!label) return
    let numberedParent: Element = section
    for (let parent = block.parentElement; parent && parent !== section; parent = parent.parentElement) {
      if (numbers.has(parent)) numberedParent = parent
    }
    const count = (counters.get(numberedParent) || 0) + 1
    counters.set(numberedParent, count)
    const value = (numbers.get(numberedParent) ? numbers.get(numberedParent) + '.' : '') + String(count).padStart(2, '0')
    numbers.set(block, value)
    badge(label, value)
  })
}
