// 大屏素材索引：按名称取图，素材已按 2 倍显示尺寸压缩。
const files = import.meta.glob('./img/*.{png,jpg}', { eager: true, import: 'default' }) as Record<string, string>

export function img(name: string) {
  return files[`./img/${name}.png`] || files[`./img/${name}.jpg`] || ''
}
