// 数据库类别配色：数据库页签与数据流向页签共用，保证同类同色。
export const DB_CATEGORIES: Record<string, { label: string; color: string }> = {
  relational: { label: '结构化数据库', color: '#3a7bd5' },
  document: { label: '文档数据库', color: '#22a06b' },
  vector: { label: '向量数据库', color: '#8a6bd1' },
  graph: { label: '图数据库', color: '#e08a00' },
  kv: { label: '缓存 · 键值', color: '#d4568a' },
  fulltext: { label: '全文检索', color: '#0aa2a2' },
  object: { label: '对象存储', color: '#64748b' },
}

export function dbCategory(id?: string) {
  return DB_CATEGORIES[id || 'relational'] || DB_CATEGORIES.relational
}

export const DB_CATEGORY_ORDER = ['relational', 'document', 'vector', 'graph', 'kv', 'fulltext', 'object']
