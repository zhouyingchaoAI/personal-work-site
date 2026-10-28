export function opportunityResults(items: { outcome?: string }[]) {
  const won = items.filter(item => item.outcome === 'won').length
  const lost = items.filter(item => item.outcome === 'lost').length
  const closed = won + lost
  return { won, lost, closed, rate: closed ? won / closed * 100 : null }
}
