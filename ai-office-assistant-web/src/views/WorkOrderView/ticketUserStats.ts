import type { Ticket } from '../../services/personalWorkApi'

export function ticketUserKey(ticket: Ticket) {
  return ticket.author_username ? `user:${ticket.author_username}` : `legacy:${ticket.author || '未记录提交人'}`
}

export function ticketUserStats(tickets: Ticket[]) {
  const users = new Map<string, { key: string; name: string; username: string; total: number; open: number; closed: number; modules: Map<string, number> }>()
  for (const ticket of tickets) {
    const key = ticketUserKey(ticket)
    const user = users.get(key) || { key, name: ticket.author || '未记录提交人', username: ticket.author_username || '', total: 0, open: 0, closed: 0, modules: new Map<string, number>() }
    user.total += 1
    if (ticket.closed) user.closed += 1
    else user.open += 1
    const module = ticket.module || '未指定'
    user.modules.set(module, (user.modules.get(module) || 0) + 1)
    users.set(key, user)
  }
  return [...users.values()].sort((left, right) => right.total - left.total || left.name.localeCompare(right.name, 'zh-CN')).map(user => ({
    ...user, modules: [...user.modules].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN')),
  }))
}
