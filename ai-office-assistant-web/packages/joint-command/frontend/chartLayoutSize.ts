export function gridSpan(width: number, tracks: number[], gap: number) {
  let available = 0
  for (let index = 0; index < tracks.length; index++) {
    available += tracks[index]! + (index ? gap : 0)
    if (width <= available + 1) return index + 1
  }
  return Math.max(1, tracks.length)
}

export function resizeChart(width: number, height: number, deltaX: number, deltaY: number, edge: 'right' | 'bottom' | 'corner') {
  return {
    width: Math.max(180, width + (edge === 'bottom' ? 0 : deltaX)),
    height: Math.max(100, height + (edge === 'right' ? 0 : deltaY)),
  }
}

export function contentZoom(width: number, height: number, nextWidth: number, nextHeight: number, zoom: number, edge: 'right' | 'bottom' | 'corner') {
  if (edge === 'right') return zoom
  const ratio = edge === 'bottom' ? nextHeight / height : Math.min(nextWidth / width, nextHeight / height)
  return Math.max(0.5, Math.min(2.5, zoom * ratio))
}
