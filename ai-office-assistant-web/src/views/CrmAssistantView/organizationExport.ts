export interface OrganizationExportNode {
  id: string
  parent: string
  label: string
  category: string
  subtitle: string
  names: string[]
  department: boolean
  collapsed: boolean
  x: number
  y: number
}

const escape = (text: string) => text.replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&apos;' })[c]!)
function lines(text: string, limit: number, maxLines = 2): string[] {
  const result: string[] = []
  let line = '', width = 0
  for (const character of text) {
    const size = character.charCodeAt(0) > 255 ? 1 : .55
    if (width + size > limit) { result.push(line); line = ''; width = 0 }
    line += character; width += size
  }
  if (line) result.push(line)
  if (result.length > maxLines) result[maxLines - 1] = result[maxLines - 1]!.slice(0, -1) + '…'
  return result.slice(0, maxLines)
}

/** Export world coordinates, independent of the canvas viewport and zoom. */
export function organizationSvg(nodes: OrganizationExportNode[], title: string, nodeWidth: number, nodeHeight: number) {
  if (!nodes.length) throw new Error('当前没有可导出的节点')
  let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity
  for (const n of nodes) {
    if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) throw new Error('节点布局尚未就绪，请重试')
    left = Math.min(left, n.x); top = Math.min(top, n.y)
    right = Math.max(right, n.x + nodeWidth); bottom = Math.max(bottom, n.y + nodeHeight)
  }
  const width = Math.max(600, right - left + 80), height = bottom - top + 140
  const byId = new Map(nodes.map(n => [n.id, n]))
  const text = (x: number, y: number, value: string, size = 12, color = '#526b85', weight = '400') =>
    `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}">${escape(value)}</text>`
  const edges = nodes.map(n => {
    const parent = byId.get(n.parent)
    if (!parent) return ''
    const x = parent.x + nodeWidth / 2, y = parent.y + nodeHeight
    const nx = n.x + nodeWidth / 2, ny = n.y, mid = (y + ny) / 2
    return `<path d="M ${x} ${y} C ${x} ${mid} ${nx} ${mid} ${nx} ${ny}" fill="none" stroke="#9eb4cc" stroke-width="1.6"/>`
  }).join('')
  const cards = nodes.map(n => {
    const label = lines(n.label, 14)
    const content = [text(12, 19, n.category, 10, '#7c8fa5'),
      ...label.map((line, i) => text(12, 39 + i * 17, line, 14, '#243b53', '600')),
      text(12, 72, lines(n.subtitle, 26, 1)[0] || '', 11),
      text(12, 93, lines(n.names.slice(0, 2).join(' · '), 25, 1)[0] || '暂无直属人员', 11),
      text(12, nodeHeight - 12, `${n.names.length} 人${n.names.length > 2 ? '（姓名仅展示前 2 位）' : ''}${n.collapsed ? ' · 下级已折叠' : ''}`, 10, '#8493a5')].join('')
    return `<g transform="translate(${n.x},${n.y})"><title>${escape(n.label)}</title><rect width="${nodeWidth}" height="${nodeHeight}" rx="10" fill="white" stroke="#d8e2ed"/><path d="M 10 1 H ${nodeWidth - 10}" stroke="${n.department ? '#d9a448' : '#5089cf'}" stroke-width="2"/>${content}</g>`
  }).join('')
  const heading = lines(title, Math.floor((width - 80) / 20), 1)[0] || ''
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Noto Sans CJK SC,Microsoft YaHei,PingFang SC,sans-serif"><title>${escape(title)}</title><rect width="100%" height="100%" fill="#f7f9fc"/>${text(40, 40, heading, 20, '#243b53', '600')}${text(40, 63, `组织架构 · ${nodes.length} 个节点 · 按当前展开状态导出`, 12)}<g transform="translate(${40 - left},${96 - top})">${edges}${cards}</g></svg>`
  return { svg, width, height }
}

export async function downloadOrganizationDiagram(diagram: ReturnType<typeof organizationSvg>, title: string, format: 'png' | 'svg') {
  let blob = new Blob([diagram.svg], { type: 'image/svg+xml;charset=utf-8' })
  if (format === 'png') {
    const source = URL.createObjectURL(blob)
    try {
      const image = new Image()
      await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('图片生成失败，请尝试导出 SVG')); image.src = source })
      // Keep large hierarchies inside browser canvas limits; SVG stays lossless.
      const scale = Math.min(2, 16000 / diagram.width, 16000 / diagram.height, Math.sqrt(32_000_000 / (diagram.width * diagram.height)))
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.floor(diagram.width * scale)); canvas.height = Math.max(1, Math.floor(diagram.height * scale))
      const context = canvas.getContext('2d')
      if (!context) throw new Error('浏览器不支持图片导出，请导出 SVG')
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
      blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(result => result ? resolve(result) : reject(new Error('图片过大，请导出 SVG')), 'image/png'))
    } finally { URL.revokeObjectURL(source) }
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url; link.download = `${title.replace(/[\\/:*?"<>|\x00-\x1f]/g, '_').slice(0, 100) || '组织架构'}.${format}`
  document.body.appendChild(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
