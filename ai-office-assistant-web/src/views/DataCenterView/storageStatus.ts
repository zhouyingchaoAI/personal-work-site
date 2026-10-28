import type { DcStorageItem } from '../../services/personalWorkApi'

export const STORAGE_STATUSES = [
  { key: 'database', label: '已完成数据库主存储', note: '已登记数据均直接读写数据库。' },
  { key: 'managed', label: '数据库 / 对象存储', note: '无已登记本地文件主存储；对象存储不等于结构化数据库。' },
  { key: 'mixed', label: '部分入库 · 仍有本地文件', note: '数据库或对象存储与本地文件混合，尚未全部切库。' },
  { key: 'file', label: '仍以本地文件存储', note: '已登记业务仍读写文件；镜像、归档不算完成切库。' },
  { key: 'unknown', label: '外部 / 待核验', note: '信息不完整，不能宣称已完成入库。' },
] as const

export function storageStatus(items: Pick<DcStorageItem, 'mode'>[]) {
  const local = items.filter(item => item.mode === 'file').length
  const database = items.filter(item => item.mode === 'database').length
  const object = items.filter(item => item.mode === 'object').length
  const unverified = items.filter(item => item.mode === 'external' || item.mode === 'unknown').length
  const key = local ? (database || object ? 'mixed' : 'file')
    : unverified || !items.length ? 'unknown' : object ? 'managed' : 'database'
  return { ...STORAGE_STATUSES.find(status => status.key === key)!, local, database, object, unverified }
}
