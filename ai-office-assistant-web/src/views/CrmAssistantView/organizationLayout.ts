export const ORGANIZATION_NODE_WIDTH = 230
export const ORGANIZATION_NODE_HEIGHT = 180

/** Place leaves left-to-right, then center each parent over its outer children.
 * Iterative postorder avoids a recursion limit for user-defined hierarchies. */
export function layoutOrganization(nodes: { id: string; parent: string }[]) {
  const result: Record<string, { x: number; y: number }> = {}
  const ids = new Set(nodes.map(n => n.id))
  const children = new Map<string, string[]>()
  for (const n of nodes) children.set(n.parent, [...(children.get(n.parent) || []), n.id])
  const visited = new Set<string>()
  let leaf = 0
  const roots = [...nodes.filter(n => !ids.has(n.parent)), ...nodes]
  for (const root of roots) {
    if (visited.has(root.id)) continue
    const stack = [{ id: root.id, depth: 0, exit: false, children: [] as string[] }]
    while (stack.length) {
      const item = stack.pop()!
      if (item.exit) {
        const points = item.children.map(id => result[id]).filter(p => !!p)
        result[item.id] = { x: points.length ? (points[0]!.x + points[points.length - 1]!.x) / 2 : leaf++ * 290, y: item.depth * 200 }
      } else {
        if (visited.has(item.id)) continue
        visited.add(item.id)
        const next = (children.get(item.id) || []).filter(id => !visited.has(id))
        stack.push({ ...item, exit: true, children: next })
        for (const id of [...next].reverse()) stack.push({ id, depth: item.depth + 1, exit: false, children: [] })
      }
    }
  }
  return result
}
