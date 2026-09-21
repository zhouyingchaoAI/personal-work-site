/** 知识库助手独立 API 客户端；默认兼容办公助手的 /personal-work-api 前缀。 */
const backendUrl = import.meta.env.VITE_PERSONAL_WORK_BACKEND_URL?.replace(/\/$/, '') || ''
const apiBase = backendUrl ? `${backendUrl}/api` : '/personal-work-api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...options, credentials: 'include' })
  const raw = await response.text()
  let data: unknown = {}
  try { data = raw ? JSON.parse(raw) : {} } catch { /* 非 JSON 统一按请求失败处理 */ }
  if (!response.ok) {
    const message = typeof data === 'object' && data && 'error' in data ? String(data.error) : `请求失败（${response.status}）`
    throw new Error(message)
  }
  return data as T
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export interface User { username: string; name: string; role: 'member' | 'admin' | 'superadmin'; is_admin: boolean; is_superadmin: boolean }
export interface SessionResponse { authenticated: boolean; user: User | null; assistant_prompt: string }
export function session() { return request<SessionResponse>('/session') }

export interface KnowledgeConfig {
  ok: boolean; provider: 'builtin' | 'ragflow'; api_url: string; model: string; vector_store: 'local' | 'qdrant'; qdrant_url: string
  rerank_model: string; ragflow_url: string; ragflow_public_url?: string; api_key_masked?: string; ragflow_api_key_masked?: string
}
export interface KnowledgeConfigPayload {
  provider?: string; api_url: string; api_key: string; model: string; vector_store?: string; qdrant_url?: string; rerank_model?: string
  ragflow_url?: string; ragflow_public_url?: string; ragflow_api_key?: string; api_key_clear?: boolean; ragflow_api_key_clear?: boolean
}
export interface KnowledgeDoc {
  id: string; name: string; uploaded_by: string; created_at: string; chars: number; chunk_count: number; embedding_model: string
  status?: string; progress?: number; progress_msg?: string
}
export interface KnowledgeKb {
  id: string; name: string; parent_id?: string; root_type?: string; shared: boolean; default: boolean; document_count: number; chunk_count: number
}
export interface KnowledgeSearchResult { doc_id: string; dataset_id?: string; doc_name: string; chunk_index: number; text: string; score: number; page?: number }
export interface KnowledgeAskSource { index: number; doc_id?: string; dataset_id?: string; doc_name: string; score: number; text: string; page?: number }
export interface KnowledgeChatMessage { role: 'user' | 'assistant'; content: string; sources?: KnowledgeAskSource[]; failed?: boolean }
export interface KnowledgeChatSession { id: string; title: string; created_at: string; updated_at: string; message_count: number; selected_kb_ids?: string[] }
export interface RagflowDatasetOverview { id: string; name: string; document_count: number; chunk_count: number; chunk_method: string }
export interface RagflowStatus {
  ok: boolean; configured: boolean; reachable: boolean; version?: string; error?: string; datasets: RagflowDatasetOverview[]
  chunk_methods: { id: string; label: string }[]; chunk_method: string; chunk_token_num: number; layout_recognize?: string; admin_email?: string; sso_available?: boolean
}
export interface KnowledgeExternalApiInfo {
  ok: boolean; provider: string; public_url: string; ready: boolean; chat_id: string; base_url: string; completion_url: string; dataset_count: number
  api_key_masked?: string; hint?: string
}

export function getKnowledgeConfig() { return request<KnowledgeConfig>('/knowledge-config') }
export function saveKnowledgeConfig(payload: KnowledgeConfigPayload) { return post<KnowledgeConfig>('/knowledge-config', payload) }
export function testKnowledgeEmbedding(payload: Partial<KnowledgeConfigPayload>) { return post<{ ok: boolean; model: string; dimensions: number; qdrant?: string; rerank?: string; ragflow?: string }>('/knowledge-test', payload) }
export function listKnowledgeKbs() { return request<{ ok: boolean; provider: string; kbs: KnowledgeKb[] }>('/knowledge/kbs') }
export function manageKnowledgeKb(payload: { action: 'create' | 'delete'; name?: string; id?: string }) { return post<{ ok: boolean; id?: string; name?: string }>('/knowledge/kbs', payload) }
export function listKnowledgeDocs(scope = 'mine') { return request<{ ok: boolean; docs: KnowledgeDoc[]; embedding_model: string; stale_docs: string[]; can_manage?: boolean; provider?: string }>(`/knowledge/list?scope=${encodeURIComponent(scope)}`) }
export function uploadKnowledgeDoc(filename: string, data: string, scope = 'mine') { return post<{ ok: boolean; doc: KnowledgeDoc }>('/knowledge/upload', { filename, data, scope }) }
export function deleteKnowledgeDoc(id: string, scope = 'mine') { return post<{ ok: boolean }>('/knowledge/delete', { id, scope }) }
export function reparseKnowledgeDoc(id: string, scope = 'mine') { return post<{ ok: boolean }>('/knowledge/reparse', { id, scope }) }
export function searchKnowledge(query: string, topK = 5, kbIds: string[] = []) { return post<{ ok: boolean; results: KnowledgeSearchResult[]; warning?: string }>('/knowledge/search', { query, top_k: topK, kb_ids: kbIds }) }
export function askKnowledge(question: string, topK = 5, kbIds: string[] = []) { return post<{ ok: boolean; answer: string; sources: KnowledgeAskSource[]; warning?: string }>('/knowledge/ask', { question, top_k: topK, kb_ids: kbIds }) }
export function getKnowledgeChatHistory(sessionId?: string) { return request<{ ok: boolean; session?: KnowledgeChatSession; messages: KnowledgeChatMessage[] }>(`/knowledge/chat-history${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''}`) }
export function listKnowledgeChatSessions() { return post<{ ok: boolean; sessions: KnowledgeChatSession[] }>('/knowledge/chat-sessions', { action: 'list' }) }
export function createKnowledgeChatSession(title?: string, kbIds: string[] = []) { return post<{ ok: boolean; session: KnowledgeChatSession }>('/knowledge/chat-sessions', { action: 'create', title, kb_ids: kbIds }) }
export function getKnowledgeChatSession(sessionId: string) { return post<{ ok: boolean; session: KnowledgeChatSession; messages: KnowledgeChatMessage[] }>('/knowledge/chat-sessions', { action: 'get', session_id: sessionId }) }
export function clearKnowledgeChat(sessionId?: string) { return post<{ ok: boolean }>('/knowledge/chat-clear', { session_id: sessionId }) }
export function knowledgeAskStreamUrl() { return `${apiBase}/knowledge/ask-stream` }
export function knowledgeDocFileUrl(datasetId: string, docId: string) { return `${apiBase}/knowledge/doc-file?dataset_id=${encodeURIComponent(datasetId)}&doc_id=${encodeURIComponent(docId)}` }
export function getKnowledgeDocChunks(datasetId: string, docId: string) { return request<{ ok: boolean; name: string; total: number; chunks: string[] }>(`/knowledge/doc-chunks?dataset_id=${encodeURIComponent(datasetId)}&doc_id=${encodeURIComponent(docId)}`) }
export function getKnowledgeExternalApiInfo() { return request<KnowledgeExternalApiInfo>('/knowledge/external-info') }
export function getRagflowStatus() { return request<RagflowStatus>('/ragflow/status') }
export function bootstrapRagflow(payload: { email?: string; password?: string } = {}) { return post<{ ok: boolean; steps: string[] }>('/ragflow/bootstrap', payload) }
export function saveRagflowChunkConfig(payload: { chunk_method: string; chunk_token_num: number; layout_recognize?: string }) { return post<{ ok: boolean; updated: string[]; warning?: string; hint?: string }>('/ragflow/chunk-config', payload) }
export function getRagflowSso() { return request<{ ok: boolean; auth: string; email: string; url: string }>('/ragflow/sso') }
export function getDigitalHumanKbConfig() { return request<{ ok: boolean; enabled: boolean; kb_ids: string[] }>('/digital-human/kb-config') }
export function saveDigitalHumanKbConfig(payload: { enabled: boolean; kb_ids: string[] }) { return post<{ ok: boolean; enabled: boolean; kb_ids: string[] }>('/digital-human/kb-config', payload) }
