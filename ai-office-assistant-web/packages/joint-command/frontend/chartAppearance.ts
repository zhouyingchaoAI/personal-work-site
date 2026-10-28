export type ChartAppearance = {
  fontSize?: number; titleSize?: number; valueSize?: number; padding?: number; radius?: number
  textColor?: string; titleColor?: string; background?: string; borderColor?: string
  align?: 'left' | 'center' | 'right'; weight?: '400' | '500' | '600' | '700'
  shadow?: 'none' | 'soft' | 'raised'
  fontFamily?: 'system' | 'serif' | 'mono'
  chartType?: 'auto' | 'bar' | 'line' | 'points' | 'pie' | 'donut' | 'table'
}

export function cleanAppearance(input: unknown): ChartAppearance {
  if (!input || typeof input !== 'object') return {}
  const source = input as Record<string, unknown>
  const result: Record<string, unknown> = {}
  for (const [key, minimum, maximum] of [['fontSize', 10, 24], ['titleSize', 12, 32], ['valueSize', 18, 56], ['padding', 0, 40], ['radius', 0, 28]] as const) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) result[key] = Math.max(minimum, Math.min(maximum, value))
  }
  for (const key of ['textColor', 'titleColor', 'background', 'borderColor']) {
    if (typeof source[key] === 'string' && /^#[0-9a-f]{6}$/i.test(source[key])) result[key] = source[key]
  }
  for (const [key, values] of Object.entries({ chartType: ['auto', 'bar', 'line', 'points', 'pie', 'donut', 'table'], align: ['left', 'center', 'right'], weight: ['400', '500', '600', '700'], shadow: ['none', 'soft', 'raised'], fontFamily: ['system', 'serif', 'mono'] })) {
    if (values.includes(String(source[key]))) result[key] = source[key]
  }
  return result as ChartAppearance
}

export const appearancePresets: Record<string, { label: string; style: ChartAppearance }> = {
  clean: { label: '清爽商务', style: { fontSize: 14, titleSize: 17, valueSize: 30, textColor: '#334155', titleColor: '#17365d', background: '#ffffff', borderColor: '#dbe7f4', padding: 16, radius: 12, shadow: 'soft', align: 'left', weight: '500' } },
  compact: { label: '紧凑报表', style: { fontSize: 12, titleSize: 14, valueSize: 26, textColor: '#334155', titleColor: '#17365d', background: '#ffffff', borderColor: '#cbd5e1', padding: 8, radius: 6, shadow: 'none', align: 'left', weight: '500' } },
  presentation: { label: '会议展示', style: { fontSize: 17, titleSize: 22, valueSize: 38, textColor: '#334155', titleColor: '#134e8e', background: '#f8fbff', borderColor: '#93bce8', padding: 22, radius: 16, shadow: 'raised', align: 'left', weight: '600' } },
}

export function appearanceVariables(input: unknown): Record<string, string> {
  const style = cleanAppearance(input)
  const fonts = { system: 'system-ui, "Microsoft YaHei", sans-serif', serif: '"Noto Serif SC", SimSun, serif', mono: 'ui-monospace, Consolas, monospace' }
  return Object.fromEntries(Object.entries(style).map(([key, value]) => [`--editor-${key}`, key === 'fontFamily' ? fonts[value as keyof typeof fonts] : typeof value === 'number' ? `${value}px` : String(value)]))
}

export function contrastRatio(foreground?: string, background?: string): number | null {
  if (![foreground, background].every(color => color && /^#[0-9a-f]{6}$/i.test(color))) return null
  const luminance = (hex: string) => {
    const channels = [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16) / 255).map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    return channels[0]! * 0.2126 + channels[1]! * 0.7152 + channels[2]! * 0.0722
  }
  const first = luminance(foreground!), second = luminance(background!)
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}
