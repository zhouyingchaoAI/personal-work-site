import { reactive } from 'vue'
import { getNavPrefs, saveNavPrefs } from '../services/personalWorkApi'
import { isMenuId, type MenuId, type SidebarMenuItem } from './menu'

// 每个用户的导航个性化偏好：助手排序与暂时隐藏，保存在后端账号下，换设备仍生效。
export const navPrefsState = reactive({
  order: [] as MenuId[],
  hidden: [] as MenuId[],
  loaded: false,
  saving: false,
})

export async function loadNavPrefs(force = false) {
  if (navPrefsState.loaded && !force) return
  try {
    const prefs = await getNavPrefs()
    navPrefsState.order = prefs.order.filter(isMenuId)
    navPrefsState.hidden = prefs.hidden.filter(isMenuId)
  } catch {
    // 偏好读取失败时回落到默认导航，不阻塞进入工作台。
  } finally {
    navPrefsState.loaded = true
  }
}

// 全部可个性化助手按用户保存顺序排列（含隐藏项）；
// 新上线的助手不在 order 里时按默认顺序追加，保证可被发现。
export function orderedAllCustomItems(items: SidebarMenuItem[]) {
  const custom = items.filter((item) => item.group === 'main' && !item.fixed)
  const ordered: SidebarMenuItem[] = []
  for (const id of navPrefsState.order) {
    const found = custom.find((item) => item.id === id)
    if (found && !ordered.includes(found)) ordered.push(found)
  }
  for (const item of custom) {
    if (!ordered.includes(item)) ordered.push(item)
  }
  return ordered
}

export function orderedCustomItems(items: SidebarMenuItem[]) {
  return orderedAllCustomItems(items).filter((item) => !navPrefsState.hidden.includes(item.id))
}

// 按用户偏好重排主导航：固定入口保持原位，其余助手按保存顺序排列并过滤隐藏项。
export function applyNavPrefs(items: SidebarMenuItem[]) {
  const fixedMain = items.filter((item) => item.group === 'main' && item.fixed)
  const footer = items.filter((item) => item.group === 'footer')
  return [...fixedMain, ...orderedCustomItems(items), ...footer]
}

// 拖拽只调整可见项顺序；隐藏项保持原有相对位置追加在后，恢复显示时不丢排序。
export function reorderVisibleAssistants(visibleIds: MenuId[], items: SidebarMenuItem[]) {
  const rest = orderedAllCustomItems(items)
    .map((item) => item.id)
    .filter((id) => !visibleIds.includes(id))
  return setNavOrder([...visibleIds, ...rest])
}

async function persistNavPrefs() {
  navPrefsState.saving = true
  try {
    await saveNavPrefs({ order: navPrefsState.order, hidden: navPrefsState.hidden })
  } finally {
    navPrefsState.saving = false
  }
}

export function setNavOrder(ids: MenuId[]) {
  navPrefsState.order = ids.filter(isMenuId)
  return persistNavPrefs()
}

export function hideAssistant(id: MenuId) {
  if (!navPrefsState.hidden.includes(id)) navPrefsState.hidden = [...navPrefsState.hidden, id]
  return persistNavPrefs()
}

export function showAssistant(id: MenuId) {
  navPrefsState.hidden = navPrefsState.hidden.filter((item) => item !== id)
  return persistNavPrefs()
}

export function resetNavPrefs() {
  navPrefsState.order = []
  navPrefsState.hidden = []
  return persistNavPrefs()
}
