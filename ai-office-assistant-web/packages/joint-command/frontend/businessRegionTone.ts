export const businessRegionLabels = { east: '东区', west: '西区', central: '中区', guangdong: '广东区' } as const

export function businessRegionTone(value: unknown): keyof typeof businessRegionLabels | '' {
  const text = String(value ?? '').trim()
  const regions = [...text.matchAll(/(?:^|[\s·/（(])(东区|西区|中区|广东区|广东)(?=作战平台|[\s·/—\-）)]|$)/g)].map(match => match[1])
  const tones = [...new Set(regions.map(region => ({ 东区: 'east', 西区: 'west', 中区: 'central', 广东区: 'guangdong', 广东: 'guangdong' } as const)[region as '东区' | '西区' | '中区' | '广东区' | '广东']))]
  return tones.length === 1 ? tones[0]! : ''
}
