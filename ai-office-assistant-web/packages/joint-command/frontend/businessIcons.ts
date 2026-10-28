// 经营分析看板统一图标库：24×24 线性图标，stroke 走 currentColor，可随主题与强调色变化。
const PATHS: Record<string, string> = {
  // 核心指标
  order: 'M4 7h16l-1.5 12h-13zM8 7V5a4 4 0 0 1 8 0v2M9 11v2a3 3 0 0 0 6 0v-2',
  'manage-order': 'M9 4h6l1 2h3v14H5V6h3zM9 4v2h6V4M8.5 13l2.3 2.3L15.5 10.5',
  revenue: 'M3 17l5.5-5.5 3.5 3.5L20 7M15 7h5v5M3 21h18',
  receipt: 'M3 8h18v10H3zM12 15.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5M3 5h18M6 11.5v3M18 11.5v3',
  gross: 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5',
  cost: 'M12 3l8 3v6c0 4.5-3.4 7.8-8 9-4.6-1.2-8-4.5-8-9V6zM12 8v8M14.5 10a2.5 2 0 0 0-2.5-1.5c-1.4 0-2.5.7-2.5 1.75s1 1.5 2.5 1.75 2.5.8 2.5 1.75-1.1 1.75-2.5 1.75a2.5 2 0 0 1-2.5-1.5',
  // 质量指标
  margin: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M9 15l6-6M9.5 9.5h.01M14.5 14.5h.01',
  ratio: 'M12 4v16M4 20h16M6 8l-3 6h6zM18 8l-3 6h6zM6 8h12M12 4a1 1 0 1 0 0 .01',
  profit: 'M3 7h16a2 2 0 0 1 2 2v10H3zM3 7V5a1 1 0 0 1 1-1h13M16 13h5v4h-5a2 2 0 0 1 0-4',
  // 结论
  progress: 'M4 20V4M4 5h12l-2 3.5 2 3.5H4M4 20h16',
  budget: 'M12 3v9l6.4 6.4A9 9 0 1 1 12 3M12 3a9 9 0 0 1 9 9h-9',
  industry: 'M3 21V10l5 3v-3l5 3v-3l5 3v8zM3 21h18M7 17h2M11 17h2M15 17h2M16 10V4h3v6',
  // 分区
  overview: 'M4 4h7v7H4zM13 4h7v4h-7zM13 11h7v9h-7zM4 14h7v6H4z',
  structure: 'M12 3a9 9 0 1 0 9 9h-9zM14 2.5a9 9 0 0 1 7.5 7.5H14z',
  region: 'M12 21s6-5.6 6-11a6 6 0 0 0-12 0c0 5.4 6 11 6 11M12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5',
  foundation: 'M12 3l9 4.5-9 4.5-9-4.5zM3 12l9 4.5 9-4.5M3 16.5L12 21l9-4.5',
  projects: 'M4 8h16v12H4zM9 8V5h6v3M4 13h16M12 12v3',
  // 卡片主题
  target: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2M12 3v3M21 12h-3',
  bridge: 'M3 20h18M5 17V9M9 13v-3M13 17v-3M17 17V7M5 9h4M13 14h4',
  expense: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3',
  cash: 'M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11M9.5 14.5a2.5 2.5 0 0 0 5 0',
  contract: 'M7 3h7l4 4v14H7zM14 3v4h4M9.5 14.5l2 2 3.5-4',
  growth: 'M5 19l4-4 3 3 7-8M14 10h5v5M5 19h14',
  results: 'M4 20V10M10 20V4M16 20v-8M22 20H2',
  task: 'M5 6h14M5 12h14M5 18h9M3 6h.01M3 12h.01M3 18h.01',
  allocation: 'M12 4v5M6 20v-5M18 20v-5M6 15c0-3 2.5-4 6-6M18 15c0-3-2.5-4-6-6M12 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4',
  quality: 'M12 3l2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8zM12 21v-3',
  map: 'M9 4l6 2 6-2v14l-6 2-6-2-6 2V6zM9 4v14M15 6v14',
  reserve: 'M12 8c5 0 8-1.3 8-3s-3-3-8-3-8 1.3-8 3 3 3 8 3M4 5v14c0 1.7 3 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3 3 8 3s8-1.3 8-3',
  flow: 'M4 7h11l-3-3M20 17H9l3 3M4 7v3M20 17v-3',
  tree: 'M12 3v6M12 9c-4 0-7 2-7 5v7M12 9c4 0 7 2 7 5v7M5 21h4M15 21h4M10 3h4',
  terms: 'M6 3h12v18H6zM9 8h6M9 12h6M9 16h4M15 15l1.5 1.5L19 14',
  sprint: 'M14 3c3 0 7 4 7 7l-5 5-2-2-3 3H8l-3-3v-3l3-3-2-2zM14 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2M5 19l-2 2M7 21l-1 1',
  plan: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M9 15l2 2 4-4',
  done: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M8.5 12.5l2.5 2.5 4.5-5',
  // 通用
  zoom: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14M16 16l5 5M11 8v6M8 11h6',
  table: 'M4 5h16v14H4zM4 10h16M4 15h16M10 5v14',
  database: 'M12 8c5 0 8-1.3 8-3s-3-3-8-3-8 1.3-8 3 3 3 8 3M4 5v14c0 1.7 3 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3 3 8 3s8-1.3 8-3',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  file: 'M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5',
  scope: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M15.5 8.5l-2 5-5 2 2-5zM12 12h.01',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 11v5M12 8h.01',
  sheets: 'M4 4h11l5 5v11H4zM15 4v5h5M8 13h8M8 17h5',
  up: 'M6 15l6-6 6 6',
  down: 'M6 9l6 6 6-6',
  flag: 'M5 21V4M5 5h13l-2.5 3.5L18 12H5',
}

/** 返回内联 SVG 字符串；未知名称回退为信息图标，保证不出现空图标位。 */
export function bizIcon(name: string, cls = ''): string {
  const d = PATHS[name] || PATHS.info
  return `<svg class="bi-ic${cls ? ' ' + cls : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`
}

/** 核心指标（P01_红绿灯 指标名）→ 图标与强调色序号 */
export const KPI_ICONS: Record<string, string> = { 订货: 'order', 管理订货: 'manage-order', 财务收入: 'revenue', 回款: 'receipt', 毛利: 'gross', 刚性费用: 'cost' }

/** 分析卡片标题 → 图标；未命中时按标题关键词推断 */
const CARD_ICONS: [RegExp, string][] = [
  [/目标、完成与预测/, 'target'], [/利润从哪里产生/, 'bridge'], [/费用构成/, 'expense'], [/现金与收入支撑/, 'cash'],
  [/合同质量/, 'contract'], [/后续增长/, 'growth'], [/区域经营结果/, 'results'], [/区域任务令/, 'task'],
  [/区域费用、分摊/, 'allocation'], [/订单质量/, 'quality'], [/省份/, 'map'], [/区域现金流/, 'reserve'],
  [/产业目标/, 'target'], [/毛利去向/, 'flow'], [/子产业/, 'tree'], [/产业合同条款/, 'terms'],
  [/滚动冲刺/, 'sprint'], [/年初全预算/, 'plan'], [/已完成订单/, 'done'],
  [/现金/, 'cash'], [/费用/, 'expense'], [/毛利/, 'gross'], [/机会|储备/, 'growth'], [/订单|合同/, 'contract'],
]
export function cardIcon(title: string): string {
  return (CARD_ICONS.find(([re]) => re.test(title)) || [null, 'results'])[1] as string
}

export const SECTION_ICONS: Record<string, string> = { overall: 'overview', taskOrder: 'task', structure: 'structure', region: 'region', industry: 'industry', foundation: 'foundation', projects: 'projects' }
