import type { DcFlowSnapshot, DcSubject } from '../../services/personalWorkApi'

/** 按当前管理对象裁剪流向快照：全局原样返回；选中助手 / 平台只保留它和它关联的实例。 */
export function scopeFlowSnapshot(raw: DcFlowSnapshot | null, selected: string, subjects: DcSubject[]): DcFlowSnapshot | null {
  if (!raw) return null
  if (selected === 'all') return raw
  const platform = subjects.find(item => item.id === 'platform')
  const systems = raw.assistants.filter(item => item.node_type !== 'assistant')
  const platformNode = { id: 'platform', label: '平台本身', node_type: 'system' as const,
    instances: (platform?.instances || []).filter(id => raw.instances.some(item => item.id === id)),
    mirror_instances: platform?.mirror_instances || [], unregistered_instances: systems.flatMap(item => item.unregistered_instances),
    client_hints: systems.flatMap(item => item.client_hints), storage_note: '账号、会话、智能体基础服务、工单与平台支撑服务；共享实例指标为整库口径。' }
  const assistants = [...raw.assistants.filter(item => item.node_type === 'assistant'), platformNode].filter(item => item.id === selected)
  const related = new Set(assistants.flatMap(item => item.instances))
  return { ...raw, assistants, instances: raw.instances.filter(item => related.has(item.id)),
    alerts_active: raw.alerts_active.filter(item => related.has(item.instance)),
    alerts_recent: raw.alerts_recent.filter(item => related.has(item.instance)) }
}
