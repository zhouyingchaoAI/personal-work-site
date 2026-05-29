export interface User {
  username: string
  role: 'member' | 'admin' | 'superadmin'
  name: string
  avatar_url: string
  bio: string
  hobbies: string[]
  is_admin: boolean
  is_superadmin: boolean
}

export interface SessionResponse {
  authenticated: boolean
  user: User | null
  assistant_prompt: string
}

export interface LoginResponse {
  ok: boolean
  user: User
  assistant_prompt: string
}

export interface ProfilePayload {
  name: string
  bio: string
  hobbies: string
  avatar_data?: string
  avatar_preset?: string
}

export interface ProfileSaveResponse {
  ok: boolean
  user: User
}

export interface ReportFile {
  name: string
  kind: 'weekly' | 'trip'
  generated: boolean
  mtime: number
  deletable?: boolean
}

export interface ReportsResponse {
  reports: ReportFile[]
  latest_weekly: string
  latest_trip: string
}

export interface UploadedReportFile {
  name: string
  path: string
  size: number
}

export interface UploadHistoryResponse {
  ok: boolean
  uploaded: UploadedReportFile[]
}

export interface ReportTemplateItem {
  kind: 'weekly' | 'trip'
  configured: boolean
  name: string
  mtime: number | null
  download_url: string
}

export interface ReportTemplatesResponse {
  ok: boolean
  templates: Record<'weekly' | 'trip', ReportTemplateItem>
}

export interface SaveReportTemplateResponse {
  ok: boolean
  template: {
    kind: 'weekly' | 'trip'
    name: string
    path: string
    mtime: number
  }
}

export interface DeleteReportTemplateResponse {
  ok: boolean
  deleted: string[]
  templates: Record<'weekly' | 'trip', ReportTemplateItem>
}

export interface WeeklyRowPayload {
  category?: string
  content?: string
  status?: string
  progress?: string
  plan?: string
  difficulty?: string
}

export interface WeeklyPrefillResponse {
  weekly_summary?: string
  weekly_follow?: string
  weekly_next?: string
  summary_rows?: WeeklyRowPayload[]
  follow_rows?: WeeklyRowPayload[]
  next_rows?: WeeklyRowPayload[]
  source?: string
  error?: string
}

export interface TripPayload {
  reporter?: string
  department?: string
  location?: string
  trip_start?: string
  trip_end?: string
  trip_date_text?: string
  purpose?: string
  itinerary?: string
  details?: string
  issues?: string
  suggestions?: string
}

export interface TripPrefillResponse extends TripPayload {
  source?: string
  error?: string
}

export interface DraftResponse {
  kind?: string
  subject?: string
  body?: string
  body_html?: string
  to?: string
  cc?: string
  attachment?: string
  attachment_path?: string
  download_url?: string
  preview?: string
  preview_html?: string
}

export interface GenerateWeeklyPayload {
  kind: 'weekly'
  period: string
  weekly_summary: WeeklyRowPayload[]
  weekly_follow: WeeklyRowPayload[]
  weekly_next: WeeklyRowPayload[]
}

export interface GenerateTripPayload extends TripPayload {
  kind: 'trip'
}

export interface GenerateResponse {
  ok: boolean
  file: string
  path: string
  draft: DraftResponse
}

export interface OptimizeResponse {
  ok: boolean
  mode?: string
  text: string
  warning?: string
}

export interface DiarySummaryResponse {
  ok: boolean
  mode?: string
  summary?: string
  warning?: string
  error?: string
}

export interface DiaryEntry {
  date: string
  today_work: string
  tomorrow_plan: string
  thoughts: string
  today_work_preview?: string
  created_at?: string
  updated_at?: string
}

export interface DiaryListParams {
  limit?: number
  start?: string
  end?: string
  keyword?: string
}

export interface DiaryListResponse {
  ok: boolean
  diaries: DiaryEntry[]
}

export interface DiaryGetResponse {
  ok: boolean
  diary: DiaryEntry | null
}

export interface DiarySavePayload {
  date: string
  today_work: string
  tomorrow_plan: string
  thoughts: string
}

export interface DiarySaveResponse {
  ok: boolean
  diary: DiaryEntry
}

export interface ForumComment {
  id: string
  parent_id: string
  author: string
  content: string
  created_at: string
}

export interface ForumTopic {
  id: string
  title: string
  body: string
  source: 'user' | 'ai' | string
  author: string
  created_at: string
  updated_at: string
  view_count: number
  heat: number
  like_count: number
  comment_count: number
  liked?: boolean
  comments?: ForumComment[]
}

export interface ForumTopicsResponse {
  ok: boolean
  topics: ForumTopic[]
}

export interface ForumTopicResponse {
  ok: boolean
  topic: ForumTopic
}

export interface ForumAiTopicFile {
  name: string
  data: string
}

export interface NewsSource {
  name: string
  url: string
}

export interface NewsItem {
  title: string
  source: string
  url: string
  impact: string
  action: string
}

export interface NewsIssue {
  date: string
  title: string
  summary: string
  generated_at: string
  generated_by: string
  item_count?: number
  items: NewsItem[]
  keywords: string[]
  errors?: string[]
}

export interface NewsHistoryItem {
  date: string
  title: string
  summary: string
  generated_at: string
  generated_by: string
  item_count: number
  keywords: string[]
}

export interface NewsConfig {
  sources: NewsSource[]
  search_query: string
  auto_search: boolean
  auto_push: boolean
  push_time: string
}

export interface NewsLatestResponse {
  ok: boolean
  issue: NewsIssue | null
  history: NewsHistoryItem[]
  config?: NewsConfig
}

export interface NewsHistoryResponse {
  ok: boolean
  issue?: NewsIssue | null
  history: NewsHistoryItem[]
  error?: string
}

export interface NewsConfigResponse {
  ok: boolean
  config: NewsConfig
}

export interface NewsGenerateResponse {
  ok: boolean
  issue: NewsIssue
}

export interface SendMailPayload {
  to: string
  cc: string
  subject: string
  body: string
  body_html?: string
  attachment?: string
  attachments?: MailAttachmentPayload[]
}

export interface SendMailResponse {
  ok: boolean
  mode: 'sent' | 'draft'
  message: string
}

export interface MailAttachment {
  index?: number
  name: string
  size?: number
  type?: string
  download_url?: string
}

export interface MailAttachmentPayload {
  name: string
  type: string
  content: string
}

export interface MailMessage {
  uid: string
  subject: string
  from: string
  to: string
  date: string
  preview: string
  body?: string
  body_html?: string
  has_html?: boolean
  attachments: MailAttachment[]
}

export interface MailboxResponse {
  ok: boolean
  messages: MailMessage[]
  cached?: boolean
}

export interface MailDetailResponse {
  ok: boolean
  message: MailMessage
  cached?: boolean
}

export interface MailConfig {
  user_email: string
  weekly_to: string
  weekly_cc: string
  trip_to: string
  trip_cc: string
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password?: string
  smtp_password_masked?: string
  smtp_from: string
  smtp_tls: boolean
  smtp_ssl: boolean
  imap_host: string
  imap_port: number
  imap_user: string
  imap_password?: string
  imap_password_masked?: string
  imap_ssl: boolean
  email_signature: string
  reference?: Partial<MailConfig>
}

export interface MailConfigResponse extends MailConfig {}

export interface MailConfigSaveResponse {
  ok: boolean
  mail_config: MailConfig
}

export interface MailConfigTestResponse {
  ok: boolean
  message: string
}

export interface AdminConfig {
  assistant_api_url: string
  assistant_model: string
  assistant_prompt: string
  assistant_api_key?: string
  assistant_api_key_masked?: string
  smtp_host: string
  smtp_port: number
  smtp_tls: boolean
  smtp_ssl: boolean
  imap_host: string
  imap_port: number
  imap_ssl: boolean
  users?: User[]
}

export interface AdminConfigResponse extends AdminConfig {}

export interface AdminConfigSaveResponse {
  ok: boolean
  config: AdminConfig
}

export interface AdminModelsResponse {
  ok: boolean
  mode: string
  models: string[]
  warning?: string
}

export interface AdminModelTestResponse {
  ok: boolean
  model: string
  message: string
}

export interface AdminUsersResponse {
  ok: boolean
  users: User[]
}

export interface SkillDefinition {
  name: string
  module: string
  title: string
  description: string
  safe: boolean
  parameters?: Record<string, string>
  detail?: {
    call_example?: unknown
    parameters?: unknown
    [key: string]: unknown
  }
}

export interface SkillsResponse {
  ok: boolean
  skills: SkillDefinition[]
  markdown: string
}

export interface AgentConfig {
  prompts?: Record<string, string>
  workflows?: Record<string, string>
}

export interface AgentConfigResponse {
  ok: boolean
  config: AgentConfig
}

export interface AgentConfigSaveResponse {
  ok: boolean
  message: string
}

export interface AgentOrchestrationResponse {
  ok: boolean
  agents: Record<string, string>
  workflows: Record<string, string>
  skills: SkillDefinition[]
  skill_mode_suffix: string
}

export interface SkillTestResponse {
  ok: boolean
  skill: string
  model: string
  arguments: Record<string, unknown>
  result: unknown
}

export interface AgentMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AgentSkillCall {
  name: string
  arguments?: Record<string, unknown>
  result?: Record<string, unknown>
}

export interface AgentUiPatch {
  op: string
  selector?: string
  value?: unknown
  data?: unknown
  [key: string]: unknown
}

export interface AgentChatResponse {
  ok: boolean
  reply?: string
  error?: string
  skill_calls?: AgentSkillCall[]
  ui_patches?: AgentUiPatch[]
}

export interface OpenClawSsoResponse {
  ok: boolean
  token?: string
  user?: unknown
  url?: string
  error?: string
}

export interface McpConfigResponse {
  ok: boolean
  enabled: boolean
  mcp_secret_masked: string
  protocol_version: string
  server_name: string
  server_version: string
  skill_count: number
  endpoint_hint: string
}

export interface McpConfigSavePayload {
  generate?: boolean
  clear?: boolean
  mcp_secret?: string
}

export interface McpConfigSaveResponse {
  ok: boolean
  message?: string
  mcp_secret?: string
}

export interface LobsterAgent {
  agent_id: number
  agent_name: string
  provider?: string
  model?: string
  status?: string
  mcp_services?: Array<{ name?: string }>
}

export interface LobsterListResponse {
  ok: boolean
  agents: LobsterAgent[]
  error?: string
}

export interface McpLobsterInstallResponse {
  ok: boolean
  error?: string
  detail?: string
}

export type AgentKind = 'weekly' | 'trip' | 'diary' | 'mailassistant' | 'news' | 'forum' | 'dashboard'

const backendUrl = import.meta.env.VITE_PERSONAL_WORK_BACKEND_URL?.replace(/\/$/, '') || ''
const backendOrigin = backendUrl ? new URL(backendUrl).origin : ''
const backendBasePath = backendUrl ? new URL(backendUrl).pathname.replace(/\/$/, '') : ''
const defaultBackendBasePath = '/personal-office-assistant'
const passthroughResourcePattern = /^(https?:|\/\/|data:|blob:|mailto:|tel:|cid:|#)/i
const sessionFreePaths = new Set(['/login', '/logout', '/session'])
let loginRedirecting = false

function normalizeResourcePath(path: string) {
  const value = String(path || '').trim()
  if (!value || passthroughResourcePattern.test(value)) return value
  const basePath = backendBasePath || defaultBackendBasePath
  const withoutBase = basePath && value.startsWith(`${basePath}/`) ? value.slice(basePath.length) : value
  return withoutBase.startsWith('/') ? withoutBase : `/${withoutBase}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(backendUrl ? `${backendUrl}/api${path}` : `/personal-work-api${path}`, {
    ...options,
    credentials: 'include',
  })
  const rawText = await response.text()
  let data: unknown = {}
  if (rawText) {
    data = JSON.parse(rawText)
  }
  if (!response.ok) {
    const message = typeof data === 'object' && data && 'error' in data ? String(data.error) : `请求失败（${response.status}）`
    if (response.status === 401) redirectToLoginOnUnauthorized(path)
    throw new Error(message)
  }
  return data as T
}

export function redirectToLoginOnUnauthorized(apiPath: string) {
  if (typeof window === 'undefined' || loginRedirecting || sessionFreePaths.has(apiPath) || window.location.pathname === '/login') return
  loginRedirecting = true
  const redirect = `${window.location.pathname}${window.location.search}${window.location.hash}`
  window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function login(username: string, password: string) {
  return post<LoginResponse>('/login', { username, password })
}

export function logout() {
  return post<{ ok: boolean }>('/logout', {})
}

export function session() {
  return request<SessionResponse>('/session')
}

export function saveProfile(payload: ProfilePayload) {
  return post<ProfileSaveResponse>('/profile', payload)
}

export function changePassword(oldPassword: string, newPassword: string) {
  return post<{ ok: boolean }>('/change-password', { old_password: oldPassword, new_password: newPassword })
}

export function getReports() {
  return request<ReportsResponse>('/reports')
}

export function getDraft(kind: 'weekly' | 'trip', file: string) {
  const query = new URLSearchParams({ kind, file })
  return request<DraftResponse>(`/draft?${query.toString()}`)
}

export function getWeeklyPrefill() {
  return request<WeeklyPrefillResponse>('/weekly-prefill')
}

export function getTripPrefill() {
  return request<TripPrefillResponse>('/trip-prefill')
}

export function generateWeekly(payload: GenerateWeeklyPayload) {
  return post<GenerateResponse>('/generate', payload)
}

export function generateTrip(payload: GenerateTripPayload) {
  return post<GenerateResponse>('/generate', payload)
}

export function optimizeText(text: string, prompt: string) {
  return post<OptimizeResponse>('/optimize', { text, prompt })
}

export function summarizeDiaries(startDate: string, endDate: string) {
  return post<DiarySummaryResponse>('/diary/summarize', { start_date: startDate, end_date: endDate })
}

export function listDiaries(params: DiaryListParams = {}) {
  const query = new URLSearchParams()
  if (params.limit) query.set('limit', String(params.limit))
  if (params.start) query.set('start', params.start)
  if (params.end) query.set('end', params.end)
  if (params.keyword) query.set('keyword', params.keyword)
  return request<DiaryListResponse>(`/diary/list?${query.toString()}`)
}

export function getDiary(date: string) {
  return request<DiaryGetResponse>(`/diary/get?${new URLSearchParams({ date }).toString()}`)
}

export function saveDiary(payload: DiarySavePayload) {
  return post<DiarySaveResponse>('/diary/save', payload)
}

export function deleteDiary(date: string) {
  return post<{ ok: boolean }>('/diary/delete', { date })
}

export function listForumTopics() {
  return request<ForumTopicsResponse>('/forum/topics')
}

export function getForumTopic(id: string) {
  return request<ForumTopicResponse>(`/forum/topic?${new URLSearchParams({ id }).toString()}`)
}

export function createForumTopic(title: string, body: string) {
  return post<ForumTopicResponse>('/forum/create', { title, body })
}

export function addForumComment(topicId: string, content: string, parentId = '') {
  return post<ForumTopicResponse>('/forum/comment', { topic_id: topicId, content, parent_id: parentId })
}

export function toggleForumLike(topicId: string) {
  return post<ForumTopicResponse>('/forum/like', { topic_id: topicId })
}

export function createForumAiTopic(seed: string, chat: string, files: ForumAiTopicFile[]) {
  return post<ForumTopicResponse>('/forum/ai-topic', { seed, chat, files })
}

export function createForumAiComment(topicId: string) {
  return post<ForumTopicResponse>('/forum/ai-comment', { topic_id: topicId })
}

export function fetchLatestNews() {
  return request<NewsLatestResponse>('/news/latest')
}

export function fetchNewsHistory(date?: string, limit = 200) {
  const query = new URLSearchParams()
  if (date) query.set('date', date)
  if (limit) query.set('limit', String(limit))
  const suffix = query.toString()
  return request<NewsHistoryResponse>(`/news/history${suffix ? `?${suffix}` : ''}`)
}

export function saveNewsConfig(payload: NewsConfig) {
  return post<NewsConfigResponse>('/news/config', payload)
}

export function generateNewsIssue(searchQuery: string, autoSearch: boolean) {
  return post<NewsGenerateResponse>('/news/generate', { search_query: searchQuery, auto_search: autoSearch })
}

export function sendMail(payload: SendMailPayload) {
  return post<SendMailResponse>('/send', payload)
}

export function listMailbox(limit: string, refresh = false) {
  const query = new URLSearchParams({ limit })
  if (refresh) query.set('refresh', '1')
  return request<MailboxResponse>(`/mailbox?${query.toString()}`)
}

export function getMailboxDetail(uid: string, refresh = false) {
  const query = new URLSearchParams({ uid })
  if (refresh) query.set('refresh', '1')
  return request<MailDetailResponse>(`/mailbox-detail?${query.toString()}`)
}

export function mailboxAttachmentDownloadUrl(path: string) {
  const value = normalizeResourcePath(path)
  if (!value || passthroughResourcePattern.test(value)) return value
  if (value.startsWith('/api/')) return backendUrl ? `${backendUrl}${value}` : value.replace(/^\/api/, '/personal-work-api')
  return resourceUrl(value)
}

export function sendAssistantMail(payload: SendMailPayload) {
  return post<SendMailResponse>('/mail-send', payload)
}

export function getMailConfig() {
  return request<MailConfigResponse>('/mail-config')
}

export function saveMailConfig(payload: Partial<MailConfig>) {
  return post<MailConfigSaveResponse>('/mail-config', payload)
}

export function testMailConfig() {
  return post<MailConfigTestResponse>('/test-mail-config', {})
}

export function getAdminConfig() {
  return request<AdminConfigResponse>('/admin-config')
}

export function saveAdminConfig(payload: Partial<AdminConfig>) {
  return post<AdminConfigSaveResponse>('/admin-config', payload)
}

export function saveServerConfig(payload: Partial<AdminConfig>) {
  return post<AdminConfigSaveResponse>('/server-config', payload)
}

export function listAdminModels(payload: Partial<AdminConfig>) {
  return post<AdminModelsResponse>('/admin-models', payload)
}

export function testAdminModel(payload: Partial<AdminConfig>) {
  return post<AdminModelTestResponse>('/admin-test-model', payload)
}

export function listAdminUsers() {
  return request<AdminUsersResponse>('/admin-users-list')
}

export function addAdminUser(payload: { username: string; password: string; name: string; role?: User['role'] }) {
  return post<AdminUsersResponse>('/admin-users', payload)
}

export function updateAdminUser(payload: { username: string; name?: string; password?: string; role?: User['role'] }) {
  return post<AdminUsersResponse>('/admin-users-update', payload)
}

export function deleteAdminUser(username: string) {
  return post<AdminUsersResponse>('/admin-users-delete', { username })
}

export function listSkills() {
  return request<SkillsResponse>('/skills')
}

export function getAgentOrchestration() {
  return request<AgentOrchestrationResponse>('/agent-orchestration')
}

export function getAgentConfig() {
  return request<AgentConfigResponse>('/agent-config')
}

export function saveAgentConfig(payload: AgentConfig) {
  return post<AgentConfigSaveResponse>('/agent-config', payload)
}

export function runSkillTest(payload: { name: string; arguments: Record<string, unknown>; instruction: string; confirm_unsafe: boolean }) {
  return post<SkillTestResponse>('/skill-test', payload)
}

export function agentChat(kind: AgentKind, messages: AgentMessage[]) {
  return post<AgentChatResponse>('/agent', { kind, messages })
}

export function openclawSso() {
  return request<OpenClawSsoResponse>('/openclaw-sso')
}

export function getMcpConfig() {
  return request<McpConfigResponse>('/mcp-config')
}

export function saveMcpConfig(payload: McpConfigSavePayload) {
  return post<McpConfigSaveResponse>('/mcp-config', payload)
}

export function listMyLobsters() {
  return request<LobsterListResponse>('/my-lobsters')
}

export function installMcpToLobster(agentId: number) {
  return post<McpLobsterInstallResponse>('/install-mcp-to-lobster', { agent_id: agentId })
}

export function deleteReport(name: string) {
  return post<{ ok: boolean; deleted: string }>('/delete-report', { name })
}

export function deleteHistory(name: string) {
  return post<{ ok: boolean; deleted: string }>('/delete-history', { name })
}

export function uploadHistoryReports(kind: 'weekly' | 'trip', files: Array<{ name: string; data: string }>) {
  return post<UploadHistoryResponse>('/upload-history', { kind, files })
}

export function getReportTemplates() {
  return post<ReportTemplatesResponse>('/report-templates', {})
}

export function saveReportTemplate(kind: 'weekly' | 'trip', file: { name: string; data: string }) {
  return post<SaveReportTemplateResponse>('/report-template', { kind, file })
}

export function deleteReportTemplate(kind: 'weekly' | 'trip') {
  return post<DeleteReportTemplateResponse>('/report-template-delete', { kind })
}

export function downloadUrl(path: string) {
  return backendUrl ? path.replace(/^\/download/, `${backendUrl}/download`) : path.replace(/^\/download/, '/personal-work-download')
}

export function templateDownloadUrl(kind: 'weekly' | 'trip') {
  return backendUrl ? `${backendUrl}/download-template?kind=${kind}` : `/personal-work-resource/download-template?kind=${kind}`
}

export function resourceUrl(path: string) {
  const value = normalizeResourcePath(path)
  if (!value || passthroughResourcePattern.test(value)) return value
  return backendUrl ? `${backendUrl}${value}` : `/personal-work-resource${value}`
}

export function mcpEndpointUrl() {
  // MCP 客户端需要访问后端公开路径，不能使用前端开发代理地址。
  const basePath = backendBasePath || defaultBackendBasePath
  if (backendOrigin) return `${backendOrigin}${basePath}/mcp`
  return `${window.location.origin}${basePath}/mcp`
}

export function openclawPlatformUrl(path: string) {
  if (/^https?:\/\//.test(path)) return path
  return backendOrigin && path.startsWith('/') ? `${backendOrigin}${path}` : path
}
