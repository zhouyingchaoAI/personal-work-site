import { apiTaskLabel, beginBackgroundTask, finishBackgroundTask } from '../utils/backgroundTasks'
export interface MonthlyBattleEvent { comments?: { id: string; at: string; author: string; content: string }[] }
export interface MonthlyBattleItem { can_comment?: boolean }
export function commentMonthlyBattle(id: string, event_id: string, content: string) { return post('/crm/monthly-battle/comment', { id, event_id, content }) }

export interface MonthlyBattleEvent { stage_reason?: string; id: string; at: string; author: string; from_stage: number; stage: number; completed: boolean; content: string; next_action: string; attachments: ForumAttachment[] }
export interface MonthlyBattleItem { conflicts: string[]; missing_code: boolean; sources: { sheet: string; row: number; values: Record<string, string> }[] }
export interface MonthlyBattleItem { id: string; month: string; code: string; name: string; owner: string; manager: string; region: string; target: string; target_stage: number; amount: number | string; tag: string; stage: number; completed: boolean; cadence: number; revision: number; events: MonthlyBattleEvent[]; stage_days: Record<string, number>; action_cycles: { status: 'green' | 'red' | 'gray'; label: string }[]; overdue: boolean; last_at: string; can_update: boolean; assignees: string[] }
export function getMonthlyBattle(selection: { view?: string; region?: string; manager?: string } = {}) { return request<{ ok: boolean; items: MonthlyBattleItem[]; stages: string[]; can_import: boolean; scope?: { level: string; label: string }; view_options?: { regions: string[]; users: { username: string; name: string }[] } | null }>('/crm/monthly-battle?' + new URLSearchParams(selection).toString()) }
export function importMonthlyBattle(data: string, month: string) { return post<{ ok: boolean; count: number; unassigned: number }>('/crm/monthly-battle/import', { data, month }) }
export function getMonthlyBattleTemplate() { return request<{ name: string; data: string }>('/crm/monthly-battle?template=1') }
export function saveMonthlyBattle(payload: { event_type?: string; stage_reason?: string; id: string; revision: number; stage: number; cadence: number; completed: boolean; content: string; next_action: string; attachments: ForumAttachment[] }) { return post<{ ok: boolean }>('/crm/monthly-battle/progress', payload) }

export interface InternalOrganizationNode { id: string; name: string; parent_id: string }
export interface InternalOrganizationMember { username: string; name: string; employee_id: string; position: string; node_id: string; node_ids?: string[] }
export interface InternalOrganizationData { ok: boolean; revision: string; nodes: InternalOrganizationNode[]; members: InternalOrganizationMember[]; updated_members?: number }
export function getInternalOrganization() { return request<InternalOrganizationData>('/admin-organization/canvas') }
export function saveInternalOrganization(payload: { revision: string; nodes: InternalOrganizationNode[]; assignments: Record<string,string>; memberships?: Record<string,string[]> }) { return post<InternalOrganizationData>('/admin-organization/canvas', payload) }
export interface CrmPerson { unit_ids?: string[] }
export interface CrmStaff { organization_memberships?: {company: string; department: string}[] }

export interface User {
  username: string
  role: 'member' | 'admin' | 'superadmin'
  name: string
  avatar_url: string
  bio: string
  hobbies: string[]
  employee_id?: string
  company?: string
  department?: string
  position?: string
  organization_check?: {
    status: 'present' | 'missing'
    checked_at: string
    source: string
  } | null
  email?: string
  is_admin: boolean
  is_superadmin: boolean
  assistant_permissions?: Record<string, boolean>
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
  work_approach?: string
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
  project_id?: string
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

export interface DiarySummaryRows {
  summary: WeeklyRowPayload[]
  follow: WeeklyRowPayload[]
  next: WeeklyRowPayload[]
}

export interface DiarySummaryResponse {
  ok: boolean
  mode?: string
  summary?: string
  rows?: DiarySummaryRows
  warning?: string
  error?: string
}

export interface DiaryEntry {
  date: string
  today_work: string
  tomorrow_plan: string
  thoughts: string
  project_id?: string
  project_ids?: string[]
  project_notes?: Record<string, string>
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
  project_id?: string
  project_ids?: string[]
  project_notes?: Record<string, string>
  /** 网页编辑器保存完整表单；Skill 调用默认按字段补充已有日记。 */
  replace?: boolean
}

export interface DiarySaveResponse {
  ok: boolean
  diary: DiaryEntry
}

export interface ForumAttachment {
  id: string
  name: string
  type: string
  size: number
  url: string
  is_image: boolean
}

export interface ForumComment {
  id: string
  parent_id: string
  author: string
  content: string
  status?: '' | 'accepted' | 'resolved' | 'rejected' | string
  created_at: string
  attachments?: ForumAttachment[]
}

export interface ForumTopic {
  id: string
  title: string
  body: string
  source: 'user' | 'ai' | string
  preset?: '' | 'platform_ticket' | string
  pinned?: boolean
  author: string
  created_at: string
  updated_at: string
  view_count: number
  heat: number
  like_count: number
  comment_count: number
  liked?: boolean
  attachments?: ForumAttachment[]
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

export interface ForumUploadFile extends ForumAiTopicFile {
  type?: string
  size?: number
}

export interface ForumAttachmentResponse {
  ok: boolean
  attachment: ForumAttachment
}

export interface Ticket {
  author_username?: string
  id: string
  title: string
  body: string
  module?: string
  source: 'user' | 'ai' | string
  author: string
  created_at: string
  updated_at: string
  view_count: number
  comment_count: number
  pinned?: boolean
  resolved?: boolean
  closed?: boolean
  status?: 'open' | 'accepted' | 'resolved' | 'rejected' | string
  attachments?: ForumAttachment[]
  comments?: ForumComment[]
}

export interface TicketListResponse {
  ok: boolean
  tickets: Ticket[]
  summary: { total: number; open: number; closed: number }
}

export interface TicketResponse {
  ok: boolean
  ticket: Ticket
}

export interface NewsSource {
  name: string
  url: string
  kind?: 'web' | 'wechat_account'
}

export interface WechatAccountCandidate {
  name: string
  account_id?: string
  account_type?: string
  original_count?: number
  updated_text?: string
  description?: string
  url: string
  source?: string
}

export interface NewsItem {
  title: string
  source: string
  url: string
  impact: string
  action: string
  fav_count?: number
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
  updated_at?: string
}

export interface NewsFavorite {
  id: string
  title: string
  source: string
  url: string
  impact: string
  action: string
  scope?: string
  issue_date?: string
  issue_title?: string
  saved_at: string
  fav_count?: number
}

export interface NewsFavoritesResponse {
  ok: boolean
  favorites: NewsFavorite[]
  already?: boolean
  removed?: number
  fav_count?: number
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
  issue?: NewsIssue | null
  refresh_error?: string
}

export interface NewsGenerateResponse {
  ok: boolean
  issue: NewsIssue | null
  skipped?: boolean
  message?: string
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
  promoted?: {
    kind: 'weekly' | 'trip' | string
    name: string
    path?: string
  }
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
  cc?: string
  date: string
  preview: string
  mailbox?: 'inbox' | 'sent' | string
  body?: string
  body_html?: string
  has_html?: boolean
  is_read?: boolean
  attachments: MailAttachment[]
}

export interface MailboxResponse {
  ok: boolean
  messages: MailMessage[]
  cached?: boolean
  background_sync?: boolean
  period_start?: string
  total?: number
  counts?: { all: number; unread: number; read: number }
  unread_count?: number
  read_count?: number
  has_more?: boolean
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
  personal_email: string
  personal_smtp_host: string
  personal_smtp_port: number
  personal_smtp_user: string
  personal_smtp_password?: string
  personal_smtp_password_masked?: string
  personal_smtp_ssl: boolean
  personal_smtp_tls: boolean
  personal_imap_host: string
  personal_imap_port: number
  personal_imap_user: string
  personal_imap_password?: string
  personal_imap_password_masked?: string
  personal_imap_ssl: boolean
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
  assistant_reasoning_effort?: string
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

export interface TtsVoiceOption {
  id: string
  label: string
}

export interface TtsConfig {
  ok: boolean
  voices: TtsVoiceOption[]
  provider: 'edge' | 'api'
  voice: string
  rate: string
  pitch: string
  api_url: string
  api_model: string
  api_voice: string
  api_key_masked?: string
}

export interface TtsConfigPayload {
  provider: 'edge' | 'api'
  voice: string
  rate: string
  pitch: string
  api_url?: string
  api_key?: string
  api_model?: string
  api_voice?: string
  api_key_clear?: boolean
}

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

export interface AgentSessionDetailResponse {
  ok: boolean
  session?: unknown
  messages?: AgentMessage[]
  error?: string
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
  session_id?: string
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
  created_at?: string
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

export interface LobsterModelOption {
  id: string
  owned_by?: string
  chat?: boolean
}

export interface LobsterModelOptionsResponse {
  models: LobsterModelOption[]
  count?: number
  api_base?: string
  error?: string
}

export interface LobsterModelUpdateResponse {
  ok: boolean
  restart_required?: boolean
  agent?: LobsterAgent
  error?: string
  detail?: string
}

export type AgentKind = 'weekly' | 'trip' | 'diary' | 'mailassistant' | 'news' | 'forum' | 'dashboard'

export interface ReimbursementItem {
  key: string
  email_uid?: string
  email_subject?: string
  email_date?: string
  email_from?: string
  filename: string
  size: number
  content_type?: string
  is_pdf: boolean
  is_image: boolean
  is_ofd?: boolean
  is_stub?: boolean
  source_url?: string
  email_body?: string
  source?: 'mail' | 'upload'
  included?: boolean
  invoice_type?: string
  invoice_date?: string
  invoice_amount?: string
  invoice_location?: string
  invoice_from?: string
  invoice_to?: string
}

export interface ReimbursementScanResponse {
  ok: boolean
  items: ReimbursementItem[]
  total_scanned: number
  error?: string
}


export interface ReimbursementScanChunk {
  start: string
  end: string
  status: "pending" | "scanning" | "done" | "failed"
  total_scanned: number
  item_count: number
  message: string
}

export interface ReimbursementSearchSummary {
  id: string
  title: string
  account: 'company' | 'personal'
  created_at: string
  updated_at: string
  ranges: { start: string; end: string }[]
  scan_chunks?: ReimbursementScanChunk[]
  item_count: number
  total_scanned: number
}

export interface ReimbursementSearchRecord extends ReimbursementSearchSummary {
  items: ReimbursementItem[]
}

export interface ReimbursementSearchListResponse {
  ok: boolean
  records: ReimbursementSearchSummary[]
  error?: string
}

export interface ReimbursementSearchResponse {
  ok: boolean
  record: ReimbursementSearchRecord
  error?: string
}

export interface ReimbursementMergeResponse {
  ok: boolean
  filename: string
  pages: number
  error?: string
}

export interface ReimbursementZipResponse {
  ok: boolean
  filename: string
  count: number
  error?: string
}

export interface ReimbursementUploadResponse extends ReimbursementItem {
  ok?: boolean
  error?: string
}

const backendUrl = import.meta.env.VITE_PERSONAL_WORK_BACKEND_URL?.replace(/\/$/, '') || ''
// 支持相对路径（如 /personal-office-assistant）：API 跟随当前访问域名（同源），
// office.chencytech.com / yfdemo / LAN IP 任一入口都不会跨域。
const backendUrlIsAbsolute = /^https?:\/\//i.test(backendUrl)
const backendOrigin = backendUrlIsAbsolute ? new URL(backendUrl).origin : ''
const backendBasePath = backendUrl ? new URL(backendUrl, 'http://relative-base').pathname.replace(/\/$/, '') : ''
const defaultBackendBasePath = '/personal-office-assistant'
const passthroughResourcePattern = /^(https?:|\/\/|data:|blob:|mailto:|tel:|cid:|#)/i
const sessionFreePaths = new Set(['/login', '/logout', '/session', '/password-reset/captcha', '/password-reset/request', '/password-reset/confirm'])
let loginRedirecting = false

function normalizeResourcePath(path: string) {
  const value = String(path || '').trim()
  if (!value || passthroughResourcePattern.test(value)) return value
  const basePath = backendBasePath || defaultBackendBasePath
  const withoutBase = basePath && value.startsWith(`${basePath}/`) ? value.slice(basePath.length) : value
  return withoutBase.startsWith('/') ? withoutBase : `/${withoutBase}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const label = apiTaskLabel(path, options?.method)
  const taskId = label ? beginBackgroundTask(label) : 0
  try {
  const response = await fetch(backendUrl ? backendUrl + "/api" + path : "/personal-work-api" + path, {
    ...options,
    credentials: "include",
  })
  const rawText = await response.text()
  const contentType = response.headers.get("content-type") || ""
  let data: unknown = {}
  const looksLikeHtml = rawText.trim().startsWith("<")
  if (rawText && contentType.includes("application/json") && !looksLikeHtml) {
    data = JSON.parse(rawText)
  } else if (rawText && !looksLikeHtml) {
    try {
      data = JSON.parse(rawText)
    } catch {
      data = {}
    }
  }
  if (!response.ok || looksLikeHtml) {
    const message = typeof data === "object" && data && "error" in data ? String(data.error) : looksLikeHtml ? "服务暂时不可用，请稍后重试" : "请求失败（" + response.status + "）"
    if (response.status === 401) redirectToLoginOnUnauthorized(path)
    throw new Error(message)
  }
  return data as T
  } finally {
    if (taskId) finishBackgroundTask(taskId)
  }
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

export function requestPasswordResetCaptcha() {
  return post<{ ok: boolean; captcha_id: string; svg: string }>('/password-reset/captcha', {})
}

export function requestPasswordReset(identifier: string, captchaId: string, captcha: string) {
  return post<{ ok: boolean; message: string }>('/password-reset/request', { identifier, captcha_id: captchaId, captcha })
}

export function confirmPasswordReset(identifier: string, code: string, newPassword: string) {
  return post<{ ok: boolean; message: string }>('/password-reset/confirm', {
    identifier, code, new_password: newPassword,
  })
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

export interface NavPrefs {
  order: string[]
  hidden: string[]
}

export function getNavPrefs() {
  return request<NavPrefs>('/nav-prefs')
}

export function saveNavPrefs(prefs: NavPrefs) {
  return post<{ ok: boolean; prefs: NavPrefs }>('/nav-prefs', prefs)
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

export function summarizeDiaries(
  startDate: string,
  endDate: string,
  categories?: string[],
  dates?: string[],
) {
  return post<DiarySummaryResponse>('/diary/summarize', {
    start_date: startDate,
    end_date: endDate,
    categories: categories && categories.length ? categories : undefined,
    dates: dates && dates.length ? dates : undefined,
  })
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

export type ProjectMemberRole = 'manager' | 'echo' | 'delta'

export interface ProjectMember {
  username: string
  roles: ProjectMemberRole[]
  role_name?: string
  joined_at?: string
}

export interface ProjectFile {
  id: string
  name: string
  size: number
  uploaded_by: string
  created_at: string
}

export interface ProjectReport {
  id: string
  type: 'weekly' | 'trip'
  name: string
  author: string
  period?: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'archived'
  creator: string
  members: ProjectMember[]
  files: ProjectFile[]
  reports: ProjectReport[]
  created_at: string
  updated_at: string
}

export interface ProjectTimelineItem {
  type: 'daily' | 'weekly' | 'trip' | 'material'
  title: string
  author: string
  created_at: string
  file?: ProjectFile
  report?: ProjectReport
  diary?: DiaryEntry
}

export function listProjects() {
  return request<{ ok: boolean; projects: Project[]; can_create: boolean; can_configure_admins: boolean }>('/projects')
}

export interface LedgerItem { id: string; project_name: string; project_code: string; customer: string; owner: string; stage: string; status: string; contract_amount: number; received_amount: number; contract_date: string; delivery_due: string; acceptance_due: string; payment_due: string; next_action: string; risk_note: string; updated_at: string }
export interface LedgerSummary { total: number; normal: number; attention: number; overdue: number; contract_amount: number; received_amount: number }
export function listLedger() { return request<{ ok: boolean; items: LedgerItem[]; summary: LedgerSummary }>('/ledger') }
export interface ContractLine { id: string; name: string; spec: string; unit: string; quantity: string; source: string; brand?: string; unit_price?: string; amount?: string; remark?: string }
export interface ContractPayment { name: string; percentage: string; amount: string; days: string; condition: string }
export interface ContractRecord { extraction?: { template_id: string; template_name: string; mode: 'template' | 'general'; reason: string; evidence: string[]; version: number } }
export interface ContractRecord { id: string; archived?: boolean; supplier?: string; total_amount?: string; tax_rate?: string; payment_terms?: string; acceptance_terms?: string; payments?: ContractPayment[]; filename: string; source_text: string; project_code: string; contract_no: string; customer: string; address: string; lines: ContractLine[]; revision: number; warning: string; documents: { id: string; kind: string; created_at: string; revision: number }[] }
export function extractContract(id: string, revision: number) { return post<{contract: ContractRecord}>('/contracts/extract', { id, revision }) }
export interface ContractSummary { id: string; filename: string; created_at: string; revision: number; contract_no: string; customer: string; archived: boolean; document_count: number }
export function listContracts() { return request<{ contracts: ContractSummary[] }>('/contracts') }
export function archiveContract(id: string, revision: number, archived: boolean) { return post<{ contract: ContractRecord }>('/contracts/archive', { id, revision, archived }) }
export function contractOriginalUrl(id: string) { return downloadUrl(`/contracts/original?${new URLSearchParams({ id })}`) }
export function getContract(id: string) { return request<{ contract: ContractRecord }>(`/contracts/get?id=${encodeURIComponent(id)}`) }
export function uploadContract(name: string, content_base64: string) { return post<{ contract: ContractRecord }>('/contracts/upload', { name, content_base64 }) }
export function saveContract(record: ContractRecord) { return post<{ contract: ContractRecord }>('/contracts/save', record) }
export function generateContractDocument(payload: { id: string; revision: number; kind: string; confirmed: boolean; selections: { id: string; quantity: string; sn: string }[] }) { return post<{ contract: ContractRecord }>('/contracts/generate', payload) }
export function contractDocumentUrl(id: string, document_id: string) { return downloadUrl(`/contracts/download?${new URLSearchParams({ id, document_id })}`) }
export function saveLedger(payload: Partial<LedgerItem>) { return post<{ ok: boolean; item: LedgerItem }>('/ledger/save', payload) }
export function deleteLedger(id: string) { return post<{ ok: boolean }>('/ledger/delete', { id }) }

export interface CashflowEntry { id: string; date: string; milestone: string; receivable: number; received: number; procurement: number; special_procurement: number; reimbursement: number; personnel: number; other: number; guarantee: number; payment?: number; net_cashflow?: number; cumulative_cashflow?: number; funding_cost?: number }
export interface CashflowScenario { id: string; project_name: string; project_code: string; region: string; customer: string; owner: string; annual_rate: number; note: string; entries: CashflowEntry[]; summary: { total_receivable: number; total_received: number; outstanding: number; total_payment: number; funding_gap: number; funding_cost: number; ending_cashflow: number }; updated_at: string }
export interface CashflowGroup { name: string; projects: number; receivable: number; received: number; outstanding: number; funding_gap: number }
export interface CashflowSummary { total: number; total_receivable: number; total_received: number; outstanding: number; funding_gap: number; funding_cost: number }

export interface DatacenterModule { module: string; level: string; files: number; bytes: number }
export interface DatacenterLevel { name: string; files: number; bytes: number; modules: number }
export interface DatacenterScan { generated_at: string; duration_seconds: number; total_files: number; total_bytes: number; user_count: number; levels: Record<string, DatacenterLevel>; modules: DatacenterModule[]; users_top: { user: string; files: number; bytes: number }[]; history?: { date: string; total_bytes: number; A: number; B: number; C: number; D: number }[] }
export interface DatacenterDisk { total: number; used?: number; free: number; mount: string; archives?: number; archives_bytes?: number }
export interface DatacenterService { key: string; label: string; level: string; status: 'up' | 'down' }
export interface DatacenterMigrationStep { step: string; status: 'done' | 'todo'; note: string }
export interface DatacenterSyncTable { table: string; rows: number; source: number; match: boolean }
export interface DatacenterSyncStatus { last?: { started_at: string; finished_at: string; ok: boolean; reason: string; rows_total: number; duration_seconds: number; error?: string; document_parse_errors?: number; file_archive?: { id: string; ok: boolean; files: number; entries: number; bytes: number; sqlite_snapshots: number }; tables: DatacenterSyncTable[]; mismatches?: string[] }; history?: { finished_at: string; ok: boolean; rows_total: number; reason: string }[] }
export function runDatacenterDbSync() { return post<{ ok: boolean; message: string }>('/datacenter/sync/run', {}) }
export interface DatacenterOverview { ok: boolean; scan: DatacenterScan; db_sync?: DatacenterSyncStatus; level_names: Record<string, string>; disk: DatacenterDisk; backup_disk: DatacenterDisk | null; services: DatacenterService[]; migration: DatacenterMigrationStep[] }
export interface DatacenterRun { id: string; reason: string; ok: boolean; started_at: string; finished_at?: string; duration_seconds?: number; bytes?: number; entries?: number; sha256?: string; archive?: string; error?: string; verified?: boolean }
export interface DatacenterBackups { ok: boolean; runs: DatacenterRun[]; pending_trigger: boolean; status: { last_ok_at?: string; next_scheduled?: string; daily_at?: string; keep?: number; heartbeat_at?: string; backup_disk?: DatacenterDisk; last_run?: DatacenterRun }; copies: { name: string; target: string; state: string; note: string }[] }
export interface DatacenterDashboard { ok: boolean; generated_at: string; records: Record<string, number>; records_note: string; history: { date: string; total_bytes: number }[]; top_modules: DatacenterModule[]; extensions: { ext: string; count: number }[]; extensions_other: number; backup: { total: number; ok: number; recent: { id: string; ok: boolean; bytes: number; finished_at: string }[] } }
export interface DatacenterBrowseEntry { name: string; path: string; dir: boolean; size: number | null; mtime: string; module: string; level: string }
export interface DatacenterBrowse { ok: boolean; path: string; entries: DatacenterBrowseEntry[]; truncated: boolean }
export interface DatacenterFilePreview { ok: boolean; kind: 'json' | 'jsonl' | 'text' | 'sqlite' | 'binary'; path: string; size: number; mtime: string; data?: unknown; summary?: { type: string; items?: number; keys?: number }; rows?: unknown[][] | unknown[]; columns?: string[]; tables?: { name: string; rows: number }[]; table?: string; offset?: number; total_lines?: number; text?: string; truncated?: boolean; note?: string; downloadable?: boolean }
export function getDatacenterDashboard() { return request<DatacenterDashboard>('/datacenter/dashboard') }
export function getDatacenterBrowse(path: string, subject = '') { return request<DatacenterBrowse>(`/datacenter/browse?path=${encodeURIComponent(path)}&subject=${encodeURIComponent(subject)}`) }
export function getDatacenterFile(path: string, table = '', offset = 0) { return request<DatacenterFilePreview>(`/datacenter/file?path=${encodeURIComponent(path)}&table=${encodeURIComponent(table)}&offset=${offset}`) }
export function getDatacenterAccessLog() { return request<{ ok: boolean; rows: { at: string; user: string; action: string; path: string; detail: string }[] }>('/datacenter/access-log') }
export function datacenterDownloadUrl(path: string) { return `/api/datacenter/download?path=${encodeURIComponent(path)}` }
export interface DatacenterDatasetParam { name: string; required: boolean; desc: string }
export interface DatacenterDataset { database_table?: string; typed_fields?: { name: string; type: string; source_field: string }[]; key: string; group: string; name: string; desc: string; params: DatacenterDatasetParam[]; fields: [string, string][]; source: string; note: string }
export interface DatacenterCatalog { ok: boolean; datasets: DatacenterDataset[]; base_url: string; auth: { header: string; note: string }; readonly: boolean; max_limit: number }
export interface DatacenterApiKeyInfo { id: string; name: string; prefix: string; created_by: string; created_at: string; last_used_at: string; calls: number; revoked_at: string }
export function getDatacenterCatalog() { return request<DatacenterCatalog>('/datacenter/datasets') }
export function getDatacenterApiKeys() { return request<{ ok: boolean; keys: DatacenterApiKeyInfo[] }>('/datacenter/apikeys') }
export function createDatacenterApiKey(name: string) { return post<{ ok: boolean; token: string }>('/datacenter/apikeys/create', { name }) }
export function revokeDatacenterApiKey(id: string) { return post<{ ok: boolean }>('/datacenter/apikeys/revoke', { id }) }
export function runDatacenterDataQuery(dataset: string, params: Record<string, string>) {
  const qs = new URLSearchParams({ dataset, ...Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '')) })
  return request<Record<string, unknown>>(`/datacenter/data?${qs}`)
}
export interface DatacenterDbInstance { id: string; kind: string; label: string; system: string; level: string; category?: string; note?: string; location: string; status: 'up' | 'down' | 'auth-error'; version?: string; detail?: string; queryable: boolean }
export interface DatacenterDbObject { name: string; rows: number | null; size: number | null; kind_label: string }
export interface DatacenterDbObjects { ok: boolean; databases: string[]; objects: DatacenterDbObject[]; rows_label: string; current_db?: string; summary?: Record<string, string | number>; truncated?: boolean }
export interface DatacenterDbRows { ok: boolean; columns: string[]; rows: Record<string, unknown>[]; total?: number | null; truncated?: boolean; duration_ms?: number; note?: string }
export function getDatacenterDatabases() { return request<{ ok: boolean; instances: DatacenterDbInstance[] }>('/datacenter/databases') }
export function getDatacenterDbObjects(instance: string, db = '', pattern = '*') { return request<DatacenterDbObjects>(`/datacenter/databases/objects?instance=${encodeURIComponent(instance)}&db=${encodeURIComponent(db)}&pattern=${encodeURIComponent(pattern)}`) }
export function getDatacenterDbRows(instance: string, db: string, object: string, page = 0, size = 50, filter = '') { return request<DatacenterDbRows>(`/datacenter/databases/rows?instance=${encodeURIComponent(instance)}&db=${encodeURIComponent(db)}&object=${encodeURIComponent(object)}&page=${page}&size=${size}&filter=${encodeURIComponent(filter)}`) }
export function runDatacenterDbQuery(instance: string, db: string, sql: string) { return post<DatacenterDbRows>('/datacenter/databases/query', { instance, db, sql }) }
export interface DcFlowClient { label: string; count: number }
export interface DcFlowInstance { id: string; label: string; kind: string; system: string; category?: string; status: 'up' | 'down' | 'auth-error'; gauges: Record<string, string | number>; rates: Record<string, number>; deltas: Record<string, number>; clients: DcFlowClient[]; active: boolean }
export interface DcFlowAssistant { id: string; label: string; instances: string[]; client_hints: string[]; node_type: 'assistant' | 'system'; storage_note: string; mirror_instances: string[]; unregistered_instances: string[] }
export interface DcFlowAlert { at: string; instance: string; level: 'critical' | 'warning'; code: string; message: string }
export interface DcFlowSnapshot { ok: boolean; sampled_at: string; assistants: DcFlowAssistant[]; instances: DcFlowInstance[]; alerts_active: DcFlowAlert[]; alerts_recent: DcFlowAlert[] }
export function getDatacenterDbFlow() { return request<DcFlowSnapshot>('/datacenter/databases/flow') }
export interface DcStorageItem { data: string; mode: 'database' | 'file' | 'object' | 'external' | 'unknown'; primary: string; note: string; mirror_tables: string[]; mirror_evidence: { table: string; verified: boolean; rows?: number | null }[] }
export interface DcSubject { id: string; label: string; group_ids: string[]; instances: string[]; mirror_instances: string[]; modules: string[]; datasets: string[]; metrics: string[]; items: (DcStorageItem & { owner_label: string })[] }
export interface DcStorageMap { ok: boolean; subjects: DcSubject[]; crm_live: boolean; scope_note: string; sync: { ok?: boolean; finished_at?: string; archive_ok?: boolean }; assistants: { id: string; label: string; node_type: 'assistant' | 'system'; items: DcStorageItem[] }[] }
export function getDatacenterStorageMap() { return request<DcStorageMap>('/datacenter/storage-map') }
export interface DcFlowTables { ok: boolean; assistant: string; instance: string; kind: string; objects: DatacenterDbObject[]; rows_label: string; note: string }
export function getDatacenterDbFlowTables(assistant: string, instance: string) { return request<DcFlowTables>(`/datacenter/databases/flow/tables?assistant=${encodeURIComponent(assistant)}&instance=${encodeURIComponent(instance)}`) }
export function getDatacenterOverview() { return request<DatacenterOverview>('/datacenter/overview') }
export function getDatacenterBackups() { return request<DatacenterBackups>('/datacenter/backups') }
export function runDatacenterBackup() { return post<{ ok: boolean; message: string }>('/datacenter/backup/run', {}) }
export function refreshDatacenterScan() { return post<{ ok: boolean; generated_at: string }>('/datacenter/refresh', {}) }

export function listCashflow() { return request<{ ok: boolean; items: CashflowScenario[]; summary: CashflowSummary; by_region: CashflowGroup[]; by_customer: CashflowGroup[] }>('/cashflow') }
export function saveCashflow(payload: Partial<CashflowScenario>) { return post<{ ok: boolean; item: CashflowScenario }>('/cashflow/save', payload) }
export function deleteCashflow(id: string) { return post<{ ok: boolean }>('/cashflow/delete', { id }) }
export interface CashflowWorkbookCell { value: string | number | boolean; formula: boolean; editable: boolean; fill?: string; bold?: boolean; align?: string; number_format?: string }
export interface CashflowWorkbookSheet { name: string; rows: number; columns: number; cells: Record<string, CashflowWorkbookCell>; merged: string[]; column_widths?: Record<string, number>; row_heights?: Record<string, number> }
export interface CashflowWorkbook { ok: boolean; template_name: string; sheets: CashflowWorkbookSheet[]; project_name: string; customer: string; region: string; cells: Record<string, Record<string, string>>; updated_at: string }
export function getCashflowWorkbook() { return request<CashflowWorkbook>('/cashflow/workbook') }
export function saveCashflowWorkbook(payload: { project_name: string; customer: string; region: string; cells: Record<string, Record<string, string>> }) { return post<{ ok: boolean; updated_at: string; filled_cells: number }>('/cashflow/workbook/save', payload) }
export async function exportCashflowWorkbook() { const response = await fetch(backendUrl ? backendUrl + '/api/cashflow/workbook/export' : '/personal-work-api/cashflow/workbook/export', { credentials: 'include' }); if (!response.ok) throw new Error('导出资金测算表失败'); return { blob: await response.blob(), name: decodeURIComponent((response.headers.get('content-disposition') || '').split("filename*=UTF-8''")[1] || '项目资金测算.xlsx') } }
export interface CashflowHistoryGroup { name: string; records: number; planned: number; received: number; unpaid: number; received_rate: number; difficult: number; long_term: number }
export interface CashflowProjectRisk extends CashflowHistoryGroup { project_code: string; customer: string; region: string }
export interface CashflowCustomerProfile extends CashflowHistoryGroup { average_collection_days: number | null; median_collection_days: number | null; p75_collection_days: number | null; p90_collection_days: number | null; collection_sample_count: number; on_time_collection_rate: number | null; median_schedule_variance_days: number | null; schedule_sample_count: number; cashflow_risk_score: number; cashflow_risk_level: string; recommended_collection_factor: number; traits: string[]; recommendation: string; payment_patterns: { name: string; amount: number; share: number }[]; stage_mix: { name: string; share: number }[] }
export interface CashflowInsightTier { name: string; projects: number; closed_projects: number; median_cycle_days: number | null; p75_cycle_days: number | null; median_first_days: number | null; avg_nodes: number | null; received_rate: number; open_projects: number }
export interface CashflowInsightCustomer { name: string; projects: number; nodes: number; planned: number; received: number; unpaid: number; received_rate: number; overdue_share: number; median_node_days: number | null; p75_node_days: number | null; cycle_index: number | null; occupancy_years: number; median_cycle_days: number | null; prepay_share: number; occupied_year: number; funding_cost: number; cycle_vs_company: number | null; occupancy_vs_company: number; credit_score: number | null; credit_grade: 'A' | 'B' | 'C' | 'D' | '样本不足'; terms: string }
export interface CashflowInsightPattern { signature: string; projects: number; probability: number; nodes: { stage: string; share: number; median_days: number | null; samples: number }[]; median_cycle_days: number | null; closed_projects: number; median_contract_amount: number | null }
export interface CashflowInsights { bucket_medians: Record<string, number>; funding_rate: number; company_cycle_index: number; company_occupancy_years: number; project_count: number; closed_projects: number; tiers: CashflowInsightTier[]; customers: CashflowInsightCustomer[]; patterns: CashflowInsightPattern[]; pattern_sample: number; conclusions: { key: string; title: string; text: string }[] }
export interface CashflowHistory { ok: boolean; source_name: string; imported_at: string; summary: { records: number; projects: number; planned_amount: number; received_amount: number; unpaid_amount: number; received_rate: number; average_collection_days: number | null }; by_region: CashflowHistoryGroup[]; by_customer: CashflowHistoryGroup[]; by_project_type: CashflowHistoryGroup[]; by_scale: CashflowHistoryGroup[]; by_status: CashflowHistoryGroup[]; by_year: CashflowHistoryGroup[]; customer_profiles: CashflowCustomerProfile[]; project_risks: CashflowProjectRisk[]; insights?: CashflowInsights }
export function listCashflowHistory() { return request<CashflowHistory>('/cashflow/history') }
export interface CashflowHistoryRecord { id: string; region: string; office: string; province: string; customer: string; project_code: string; project_name: string; project_type: string; contract_amount: number; planned_amount: number; received_amount: number; status: string; contract_date: string; planned_date: string; received_date: string; is_difficult: boolean; is_long_term: boolean }
export function listCashflowHistoryRecords(params: { keyword?: string; region?: string; page?: number; page_size?: number } = {}) { return request<{ ok: boolean; items: CashflowHistoryRecord[]; total: number; page: number; page_size: number }>(`/cashflow/history/records?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== '').map(([key, value]) => [key, String(value)]))}`) }
export function saveCashflowHistoryRecord(payload: Partial<CashflowHistoryRecord>) { return post<{ ok: boolean; item: CashflowHistoryRecord }>('/cashflow/history/save', payload) }
export function deleteCashflowHistoryRecord(id: string) { return post<{ ok: boolean }>('/cashflow/history/delete', { id }) }

// ---- 联指经营助手（CRM） ----
export interface CrmUnit { business_region?: string; business_regions?: string[]; parent_unit_id?: string; organization_level?: 'company' | 'subsidiary' | 'unit' | ''; company_full_name?: string; subsidiary_full_name?: string; unit_name?: string; id: string; name: string; type: string; region: string; line_scale: string; bid_preference: string; history: string; win_rate: string; source: string; version: number }
export interface CrmPerson { mobile?: string; office_phone?: string; email?: string; wechat?: string; importance?: string; support_level?: string; maintenance_days?: number | string; imported_history?: string; company_full_name?: string; subsidiary_full_name?: string; organization_unit_name?: string; organization_path?: string; department?: string; manager_id?: string; responsibilities?: string; id: string; name: string; unit_id: string; unit_name?: string; title: string; decision_role: string; power_radius: string; influence: number; stance: string; career_track: string[]; rotation_window: string; version: number }
export interface CrmAction { next_step?: string; due_date?: string; owner?: string; supervisor?: string; created_by?: string; project_id?: string; completed_at?: string; id: string; relation_id: string; type: string; level: string; intel: string; cost: string; effective: boolean; bidirectional: boolean; decision_node: string; happened_at: string }
export interface CrmRelation { _owner?: string; our_staff?: CrmStaff | null; our_member_label?: string; id: string; person_id: string; person_name?: string; our_member: string; source: string; intro_path: string; single_point_risk: boolean; strength: number; strength_label: string; score: number; radar: Record<string, number>; decay_state: 'normal' | 'warning' | 'alarm'; last_touch: string; days_since_touch: number | null; action_count: number; actions?: CrmAction[]; version: number }
export interface CrmGraphNode { id: string; label: string; kind: 'self' | 'unit' | 'person' | 'group' | 'staff'; type: string; unit_id?: string; influence?: number }
export interface CrmGraphEdge { relation_kind?: 'belongs' | 'reports' | 'contact'; our_member?: string; our_member_label?: string; source: string; target: string; strength: number; score: number; decay_state: string; days_since_touch: number | null; single_point_risk: boolean }
export interface CrmWarning { relation_id: string; person_id: string; person_name: string; unit_name: string; tier: string; decay_state: string; days_since_touch: number | null; strength: number }
export interface CrmInfra { redis: boolean; neo4j: boolean; redis_configured: boolean; neo4j_configured: boolean }
export interface CrmOverview { ok: boolean; stats: { units: number; people: number; relations: number; trusted: number; warnings: number; single_point: number }; graph: { nodes: CrmGraphNode[]; edges: CrmGraphEdge[] }; warnings: CrmWarning[]; unit_types: string[]; infra?: CrmInfra }
export interface CrmCoverageCell { applicable?: boolean; covered: boolean; strength: number }
export interface CrmCoverage { matrix: Record<string, Record<string, CrmCoverageCell>>; nodes: string[]; unit_types: string[]; should_cover: number; covered: number; l3_plus: number }
export interface CrmBattleMap { ok: boolean; battle_map: { target: string; who_goes: string; route: string; first_step: string; current_level: number; target_level: number }; candidates: { our_member: string; strength: number; score: number; path: string }[]; pipeline: { step: string; detail: string }[]; coverage: CrmCoverage | null; opportunity_context?: { code: string; name: string; owner_unit: string; stage: string; cancelled: boolean; matched_units: number; matched_people: number; relations: number; assigned_relations: number; strong_relations: number; single_point_risks: number }; graph_source?: 'neo4j' | 'memory'; graph_path?: { names: string[]; hops: number } | null }
export interface CrmStageContact { person_id?: string; name: string; role?: string; department?: string }
export interface CrmStageProgressEntry { attachments: ForumAttachment[]; contacts: CrmStageContact[]; status?: string; planned_start?: string; planned_end?: string; work_done?: string[]; updated_at?: string; updated_by?: string }
export interface CrmOpportunity { created_at?: string; updated_at?: string; owner_unit_id?: string; sales_stage?: string; outcome?: 'open' | 'won' | 'lost' | 'cancelled'; outcome_changed_at?: string; id: string; code: string; name: string; owner_unit: string; stage: string; win_rate: string; status: string; region: string; manager: string; bid_date: string; contract_date: string; amount: number; cancelled: boolean; cancel_reason: string; stage_progress?: Record<string, CrmStageProgressEntry>; version?: number; _owner?: string; investment?: number; share_integration?: number; share_service?: number; sales_projects?: number; contract_count?: number; contract_amount_yuan?: number; contract_codes?: string[]; business_date?: string; contractor?: string; products?: string; brand?: string; remark?: string; outcome_source?: string }
export interface CrmSalesContract { id: string; project_code: string; project_name: string; subproject_code: string; subproject_name: string; contract_code: string; customer: string; owner_unit: string; signed_at: string; amount_yuan: number; project_manager: string; account_manager: string; archived: boolean; industry: string; payment_terms: string; expected_margin_yuan?: number | null; imported_at?: string; imported_by?: string; _owner?: string }
export function crmOpportunityStageSave(payload: { id?: string; code?: string; stage: string; attachments: { id?: string; name?: string; type?: string; size?: number; data?: string }[]; contacts: CrmStageContact[]; status?: string; planned_start?: string; planned_end?: string; work_done?: string[] }) { return post<{ ok: boolean; opportunity?: CrmOpportunity; error?: string }>('/crm/opportunity/stage-save', payload) }

export function crmOverview() { return request<CrmOverview>('/crm/overview') }
export function crmUnits() { return request<{ ok: boolean; units: CrmUnit[]; types: string[] }>('/crm/units') }
export function crmPeople() { return request<{ ok: boolean; people: CrmPerson[]; roles: string[] }>('/crm/people') }
export function crmRelations() { return request<{ ok: boolean; relations: CrmRelation[]; levels: Record<string, string> }>('/crm/relations') }
export function crmOpportunities() { return request<{ ok: boolean; opportunities: CrmOpportunity[] }>('/crm/opportunities') }
export function crmSalesContracts() { return request<{ ok: boolean; contracts: CrmSalesContract[] }>('/crm/sales-contracts') }
export function crmSaveUnit(payload: Partial<CrmUnit>) { return post<{ ok: boolean; unit?: CrmUnit; error?: string }>('/crm/unit/save', payload) }
export function crmDeleteUnit(id: string) { return post<{ ok: boolean; deleted_id?: string; error?: string }>('/crm/unit/delete', { id }) }
export function crmDepartmentNode(payload: { unit_id: string; department: string; action: 'add' | 'delete'; name?: string }) { return post<{ ok: boolean; unit?: CrmUnit; error?: string }>('/crm/department/node', payload) }
export function crmSavePerson(payload: Partial<CrmPerson>) { return post<{ ok: boolean; person?: CrmPerson; error?: string }>('/crm/person/save', payload) }
export function crmSaveRelation(payload: Partial<CrmRelation>) { return post<{ ok: boolean; relation?: CrmRelation; error?: string }>('/crm/relation/save', payload) }
export function crmAddAction(payload: Partial<CrmAction>) { return post<{ ok: boolean; action?: CrmAction; relation?: CrmRelation; error?: string }>('/crm/action/add', payload) }
export function crmSaveLink(payload: { id?: string; project_id: string; decision_node: string; person_id: string; our_member?: string }) { return post<{ ok: boolean; error?: string }>('/crm/link/save', payload) }
export interface CrmOpportunityImportResult {
  ok: boolean
  preview?: boolean
  total?: number
  unique_count?: number
  new_count?: number
  duplicate_count?: number
  duplicates?: { code: string; name: string; owner_unit: string; existing_name: string; reason: string }[]
  duplicates_truncated?: boolean
  imported?: number
  created?: number
  updated?: number
  skipped?: number
  active?: number
  archived?: number
  error?: string
}
export function crmImportOpportunities(payload: { filename: string; data: string; mode?: 'preview' | 'skip' | 'update' }) { return post<CrmOpportunityImportResult>('/crm/opportunities/import', payload) }
export function crmImportSalesContracts(payload: { filename: string; data: string }) { return post<{ ok: boolean; contracts?: number; contract_projects?: number; matched_opportunities?: number; unmatched_projects?: number; won_opportunities?: number; error?: string }>('/crm/sales-contracts/import', payload) }
export async function crmOpportunityTemplate() {
  const base = backendUrl ? backendUrl + '/api/crm/opportunities/template' : '/personal-work-api/crm/opportunities/template'
  const response = await fetch(base, { credentials: 'include' })
  if (!response.ok) { let m = '下载模板失败'; try { m = (await response.json()).error || m } catch { /* non-JSON */ } throw new Error(m) }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '机会点导入模板.xlsx')
  return { blob: await response.blob(), name }
}
export function crmSaveOpportunity(payload: Partial<CrmOpportunity>) { return post<{ ok: boolean; opportunity?: CrmOpportunity; error?: string }>('/crm/opportunity/save', payload) }
export async function crmExportOpportunities(filters: { state?: 'all' | 'active' | 'archived'; stage?: string; region?: string; sales_stage?: string; keyword?: string } = {}) {
  const query = new URLSearchParams()
  if (filters.state && filters.state !== 'all') query.set('state', filters.state)
  if (filters.stage && filters.stage !== 'all') query.set('stage', filters.stage)
  if (filters.region && filters.region !== 'all') query.set('region', filters.region)
  if (filters.sales_stage && filters.sales_stage !== 'all') query.set('sales_stage', filters.sales_stage)
  if (filters.keyword?.trim()) query.set('keyword', filters.keyword.trim())
  const base = backendUrl ? backendUrl + '/api/crm/opportunities/export' : '/personal-work-api/crm/opportunities/export'
  const response = await fetch(`${base}?${query.toString()}`, { credentials: 'include' })
  if (!response.ok) {
    let message = '导出机会点表失败'
    try { message = (await response.json()).error || message } catch { /* non-JSON error */ }
    throw new Error(message)
  }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '机会点清单.xlsx')
  return { blob: await response.blob(), name }
}
export type BusinessCell = string | number | boolean
export interface BusinessSheet { key: string; title: string; source: string; headers: string[]; rows: BusinessCell[][] }
export interface BusinessAnalysisData { imported_at: string; imported_by: string; filename: string; sheets: BusinessSheet[]; version?: string; scope?: { level: 'company' | 'region' | 'personal'; label: string; regions: string[]; can_import: boolean } }
export interface BusinessVersion { version: string; imported_at: string; imported_by: string; filename: string; sheets: number }
export interface BusinessView { view: 'company' | 'region' | 'personal'; region?: string; manager?: string }
export interface BusinessViewOptions { regions: string[]; managers: { username: string; name: string }[] }
export function crmBusinessAnalysis(version?: string, selection?: BusinessView) {
  const query = new URLSearchParams()
  if (version) query.set('version', version)
  if (selection) Object.entries(selection).forEach(([key, value]) => { if (value) query.set(key, value) })
  return request<{ ok: boolean; error?: string; data: BusinessAnalysisData | null; versions: BusinessVersion[]; view_options?: BusinessViewOptions | null }>('/crm/business-analysis?' + query)
}
export function crmBusinessImport(payload: { filename: string; data: string }) { return post<{ ok: boolean; sheets?: number; imported_at?: string; error?: string }>('/crm/business-analysis/import', payload) }
export function crmTaskOrderImport(payload: { filename: string; data: string }) { return post<{ ok: boolean; sheets?: number; rows?: number; imported_at?: string; error?: string }>('/crm/business-analysis/task-order-import', payload) }
export function crmBusinessDashboardUrl(version?: string) {
  const base = backendUrl ? backendUrl + '/api/crm/business-analysis/dashboard' : '/personal-work-api/crm/business-analysis/dashboard'
  return base + (version ? `?version=${encodeURIComponent(version)}` : '')
}
export async function crmBusinessTemplate(version?: string, blocks?: string[]) {
  const base = backendUrl ? backendUrl + '/api/crm/business-analysis/template' : '/personal-work-api/crm/business-analysis/template'
  const query = new URLSearchParams()
  if (version) query.set('version', version)
  if (blocks?.length) query.set('blocks', blocks.join(','))
  const response = await fetch(base + '?' + query, { credentials: 'include' })
  if (!response.ok) { let m = '下载模板失败'; try { m = (await response.json()).error || m } catch { /* non-JSON */ } throw new Error(m) }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '2026联指经营数据_标准导入模板.xlsx')
  return { blob: await response.blob(), name }
}
export async function crmTaskOrderTemplate() {
  const base = backendUrl ? backendUrl + '/api/crm/business-analysis/task-order-template' : '/personal-work-api/crm/business-analysis/task-order-template'
  const response = await fetch(base, { credentials: 'include' })
  if (!response.ok) { let message = '下载任务令模板失败'; try { message = (await response.json()).error || message } catch { /* non-JSON */ } throw new Error(message) }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '联指经营助手_任务令数据导入模板.xlsx')
  return { blob: await response.blob(), name }
}
export function crmBulkUpdate(payload: { collection: 'units' | 'people' | 'relations'; ids: string[]; changes: Record<string, string | boolean | number> }) { return post<{ ok: boolean; updated: number }>('/crm/bulk-update', payload) }
export function crmBatchAssignRelations(payload: { relation_ids?: string[]; person_ids?: string[]; mode?: 'add'; our_member?: string; transfer?: boolean; supervision?: { next_step: string; due_date?: string; supervisor?: string } }) { return post<{ ok: boolean; updated: number; skipped?: number; plans_created: number; plans_transferred?: number; our_member: string; supervisor: string }>('/crm/relations/batch-assign', payload) }
export async function crmExportRelationships(level: 'all' | 'region' | 'manager', target = '', region = '') {
  const query = new URLSearchParams({ level, target })
  if (region) query.set('region', region)
  const base = backendUrl ? backendUrl + '/api/crm/excel/export' : '/personal-work-api/crm/excel/export'
  const response = await fetch(`${base}?${query.toString()}`, { credentials: 'include' })
  if (!response.ok) {
    let message = '导出客户关系表失败'
    try { message = (await response.json()).error || message } catch { /* binary or empty body */ }
    throw new Error(message)
  }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '客户关系.xlsx')
  return { blob: await response.blob(), name }
}
export async function crmExportCustomerOrganization() {
  const base = backendUrl ? backendUrl + '/api/crm/organization/export' : '/personal-work-api/crm/organization/export'
  const response = await fetch(base, { credentials: 'include' })
  if (!response.ok) {
    let message = '导出客户组织架构失败'
    try { message = (await response.json()).error || message } catch { /* binary or empty body */ }
    throw new Error(message)
  }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '客户组织架构.xlsx')
  return { blob: await response.blob(), name }
}
export function crmRecordVersions(collection: string, recordId: string) { return request<{ ok: boolean; versions: Array<{ at: string; record: Record<string, unknown> }> }>(`/crm/history?${new URLSearchParams({ collection, record_id: recordId })}`) }
export function crmProjectMap(projectId: string) { return request<{ ok: boolean; coverage: CrmCoverage }>(`/crm/project-map?project_id=${encodeURIComponent(projectId)}`) }
export interface CrmPath { ok: boolean; ids: string[]; names: string[]; hops: number; source: 'neo4j' | 'memory'; error?: string }
export function crmGraphPath(target: string) { return request<CrmPath>(`/crm/graph/path?target=${encodeURIComponent(target)}`) }
export function crmBattleMap(payload: { stage?: string; project_id?: string; target_person_id: string; our_members?: string[] }) { return post<CrmBattleMap>('/crm/battle-map/generate', payload) }
export function crmImportFromContract(contract_id: string) { return post<{ ok: boolean; unit?: CrmUnit; error?: string; note?: string }>('/crm/import-from-contract', { contract_id }) }

export function getProject(id: string) {
  return request<{ ok: boolean; project: Project; can_manage: boolean }>(`/projects/get?${new URLSearchParams({ id }).toString()}`)
}

export function getProjectTimeline(id: string) {
  return request<{ ok: boolean; project: Project; timeline: ProjectTimelineItem[]; can_manage: boolean; users: Pick<User, 'username' | 'name'>[] }>(`/projects/timeline?${new URLSearchParams({ id }).toString()}`)
}

export function createProject(payload: { name: string; description?: string; members?: ProjectMember[] }) {
  return post<{ ok: boolean; project: Project }>('/projects/create', payload)
}

export function updateProject(payload: { id: string; name?: string; description?: string; status?: 'active' | 'archived' }) {
  return post<{ ok: boolean; project: Project }>('/projects/update', payload)
}

export function deleteProject(id: string) {
  return post<{ ok: boolean; deleted_id: string }>('/projects/delete', { id })
}

export function saveProjectMembers(id: string, members: ProjectMember[]) {
  return post<{ ok: boolean; project: Project }>('/projects/members', { id, members })
}

export function uploadProjectFile(id: string, name: string, contentBase64: string) {
  return post<{ ok: boolean; file: ProjectFile; project: Project }>('/projects/upload', { id, name, content_base64: contentBase64 })
}

export function projectFileUrl(id: string, fileId: string) {
  return downloadUrl(`/projects/file?${new URLSearchParams({ id, file_id: fileId }).toString()}`)
}

export function projectReportUrl(id: string, reportId: string) {
  return downloadUrl(`/projects/report-file?${new URLSearchParams({ id, report_id: reportId }).toString()}`)
}

export function getProjectAdmins() {
  return request<{ ok: boolean; admins: string[]; users: Pick<User, 'username' | 'name'>[]; can_configure: boolean }>('/projects/admins')
}

export function saveProjectAdmins(admins: string[]) {
  return post<{ ok: boolean; admins: string[]; users: Pick<User, 'username' | 'name'>[]; can_configure: boolean }>('/projects/admins', { admins })
}

export function listForumTopics() {
  return request<ForumTopicsResponse>('/forum/topics')
}

export function getForumTopic(id: string) {
  return request<ForumTopicResponse>(`/forum/topic?${new URLSearchParams({ id }).toString()}`)
}

export function uploadForumAttachment(file: File) {
  const form = new FormData()
  form.append('file', file, file.name)
  return request<ForumAttachmentResponse>('/forum/attachment', {
    method: 'POST',
    body: form,
  })
}

export function createForumTopic(title: string, body: string, attachments: ForumAttachment[] = [], preset = '') {
  return post<ForumTopicResponse>('/forum/create', { title, body, attachments, preset })
}

export function addForumComment(topicId: string, content: string, parentId = '', attachments: ForumAttachment[] = [], status = '') {
  return post<ForumTopicResponse>('/forum/comment', { topic_id: topicId, content, parent_id: parentId, attachments, status })
}

export function toggleForumLike(topicId: string) {
  return post<ForumTopicResponse>('/forum/like', { topic_id: topicId })
}

export function setForumTopicPinned(topicId: string, pinned: boolean) {
  return post<ForumTopicResponse>('/forum/pin', { topic_id: topicId, pinned })
}

export function createForumAiTopic(seed: string, chat: string, files: ForumAiTopicFile[]) {
  return post<ForumTopicResponse>('/forum/ai-topic', { seed, chat, files })
}

export function createForumAiComment(topicId: string) {
  return post<ForumTopicResponse>('/forum/ai-comment', { topic_id: topicId })
}

// ===== 工单系统（自金点子论坛拆分，附件复用论坛上传接口）=====
export function listTickets() {
  return request<TicketListResponse>('/tickets')
}

export function getTicket(id: string) {
  return request<TicketResponse>(`/tickets/get?${new URLSearchParams({ id }).toString()}`)
}

export function createTicket(title: string, body: string, module: string, attachments: ForumAttachment[] = []) {
  return post<TicketResponse>('/tickets/create', { title, body, module, attachments })
}

export function addTicketComment(ticketId: string, content: string, status = '', parentId = '', attachments: ForumAttachment[] = []) {
  return post<TicketResponse>('/tickets/comment', { topic_id: ticketId, content, status, parent_id: parentId, attachments })
}

export function uploadTicketAttachment(file: File) {
  return uploadForumAttachment(file)
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

export function searchWechatAccounts(query: string) {
  return request<{ ok: boolean; query: string; candidates: WechatAccountCandidate[]; notice?: string }>(
    `/news/wechat-accounts?query=${encodeURIComponent(query)}`,
  )
}

export function fetchWechatAuthStatus() {
  return request<{ ok: boolean; expired: boolean; message: string }>('/news/wechat-auth-status')
}

export function saveNewsConfig(payload: NewsConfig) {
  return post<NewsConfigResponse>('/news/config', payload)
}

export function generateNewsIssue(searchQuery: string, autoSearch: boolean) {
  return post<NewsGenerateResponse>('/news/generate', { search_query: searchQuery, auto_search: autoSearch })
}

export function fetchPersonalNews() {
  return request<NewsLatestResponse>('/news/personal/latest')
}

export function fetchPersonalNewsHistory(date?: string, limit = 200) {
  const query = new URLSearchParams()
  if (date) query.set('date', date)
  if (limit) query.set('limit', String(limit))
  const suffix = query.toString()
  return request<NewsHistoryResponse>(`/news/personal/history${suffix ? `?${suffix}` : ''}`)
}

export function savePersonalNewsConfig(payload: NewsConfig) {
  return post<NewsConfigResponse>('/news/personal/config', payload)
}

export function generatePersonalNewsIssue(searchQuery: string, autoSearch: boolean) {
  return post<NewsGenerateResponse>('/news/personal/generate', { search_query: searchQuery, auto_search: autoSearch })
}

export function fetchNewsFavorites(query?: string) {
  const suffix = query ? `?q=${encodeURIComponent(query)}` : ''
  return request<NewsFavoritesResponse>(`/news/favorites${suffix}`)
}

export function addNewsFavorite(item: Record<string, unknown>) {
  return post<NewsFavoritesResponse>('/news/favorites', item)
}

export function removeNewsFavorite(payload: { id?: string; url?: string; title?: string }) {
  return post<NewsFavoritesResponse>('/news/favorites/delete', payload)
}

export function sendMail(payload: SendMailPayload) {
  return post<SendMailResponse>('/send', payload)
}

export function listMailbox(limit: string, refresh = false, offset = 0, readStatus: 'all' | 'unread' | 'read' = 'all', signal?: AbortSignal) {
  const query = new URLSearchParams({ limit })
  if (offset) query.set('offset', String(offset))
  if (readStatus !== 'all') query.set('read_status', readStatus)
  if (refresh) query.set('refresh', '1')
  return request<MailboxResponse>(`/mailbox?${query.toString()}`, { signal })
}

export function getMailboxDetail(uid: string, refresh = false) {
  const query = new URLSearchParams({ uid })
  if (refresh) query.set('refresh', '1')
  return request<MailDetailResponse>(`/mailbox-detail?${query.toString()}`)
}

export function markMailboxRead(uid: string) {
  return post<{ ok: boolean; uid: string; is_read: boolean }>('/mailbox-mark-read', { uid })
}

export function listSentMail(limit: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ limit })
  return request<MailboxResponse>(`/sent-mail?${query.toString()}`, { signal })
}

export function getSentMailDetail(uid: string) {
  const query = new URLSearchParams({ uid })
  return request<MailDetailResponse>(`/sent-mail-detail?${query.toString()}`)
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

export function testMailConfig(account: 'company' | 'personal' = 'company') {
  return post<MailConfigTestResponse>('/test-mail-config', { account })
}

export function getAdminConfig() {
  return request<AdminConfigResponse>('/admin-config')
}

export function saveAdminConfig(payload: Partial<AdminConfig>) {
  return post<AdminConfigSaveResponse>('/admin-config', payload)
}

export function getTtsConfig() {
  return request<TtsConfig>('/tts-config')
}

export function saveTtsConfig(payload: TtsConfigPayload) {
  return post<TtsConfig>('/tts-config', payload)
}

export function previewTts(text: string, payload: TtsConfigPayload) {
  return post<{ ok: boolean; audio: string }>('/tts', { text, ...payload })
}

export function probeTtsVoices(payload: { api_url?: string; api_key?: string; api_model?: string }) {
  return post<{ ok: boolean; voices: string[]; source: string }>('/tts-voices', payload)
}

export interface KnowledgeConfig {
  ok: boolean
  provider: 'builtin' | 'ragflow'
  api_url: string
  model: string
  vector_store: 'local' | 'qdrant'
  qdrant_url: string
  rerank_model: string
  ragflow_url: string
  ragflow_public_url?: string
  api_key_masked?: string
  ragflow_api_key_masked?: string
}

export interface KnowledgeConfigPayload {
  provider?: string
  api_url: string
  api_key: string
  model: string
  vector_store?: string
  qdrant_url?: string
  rerank_model?: string
  ragflow_url?: string
  ragflow_public_url?: string
  ragflow_api_key?: string
  api_key_clear?: boolean
  ragflow_api_key_clear?: boolean
}

export interface KnowledgeDoc {
  id: string
  name: string
  uploaded_by: string
  created_at: string
  chars: number
  chunk_count: number
  embedding_model: string
  status?: string
  progress?: number
  progress_msg?: string
}

export interface KnowledgeSearchResult {
  doc_id: string
  dataset_id?: string
  doc_name: string
  chunk_index: number
  text: string
  score: number
  page?: number
}

export interface KnowledgeAskSource {
  index: number
  doc_id?: string
  dataset_id?: string
  doc_name: string
  score: number
  text: string
  page?: number
}

export function getKnowledgeChatEmbed() {
  return request<{ ok: boolean; url: string; empty?: boolean; hint?: string }>('/knowledge/chat-embed')
}

export interface KnowledgeChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: KnowledgeAskSource[]
  failed?: boolean
}

export interface KnowledgeChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  selected_kb_ids?: string[]
}

export function getKnowledgeChatHistory(sessionId?: string) {
  const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  return request<{ ok: boolean; session?: KnowledgeChatSession; messages: KnowledgeChatMessage[] }>(`/knowledge/chat-history${suffix}`)
}

export function listKnowledgeChatSessions() {
  return post<{ ok: boolean; sessions: KnowledgeChatSession[] }>('/knowledge/chat-sessions', { action: 'list' })
}

export function createKnowledgeChatSession(title?: string, kbIds: string[] = []) {
  return post<{ ok: boolean; session: KnowledgeChatSession }>('/knowledge/chat-sessions', { action: 'create', title, kb_ids: kbIds })
}

export function getKnowledgeChatSession(sessionId: string) {
  return post<{ ok: boolean; session: KnowledgeChatSession; messages: KnowledgeChatMessage[] }>('/knowledge/chat-sessions', { action: 'get', session_id: sessionId })
}

export function clearKnowledgeChat(sessionId?: string) {
  return post<{ ok: boolean }>('/knowledge/chat-clear', { session_id: sessionId })
}

// SSE 流式问答（直接 fetch，不走统一 request 封装）
export function knowledgeAskStreamUrl() {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/knowledge/ask-stream`
}

export function knowledgeDocFileUrl(datasetId: string, docId: string) {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/knowledge/doc-file?dataset_id=${encodeURIComponent(datasetId)}&doc_id=${encodeURIComponent(docId)}`
}

export function getKnowledgeDocChunks(datasetId: string, docId: string) {
  return request<{ ok: boolean; name: string; total: number; chunks: string[] }>(
    `/knowledge/doc-chunks?dataset_id=${encodeURIComponent(datasetId)}&doc_id=${encodeURIComponent(docId)}`,
  )
}

// ---- PDF 解析成 Markdown（DeepDoc OCR + 绘图框取校准）----
export interface PdfMdPage {
  page: number
  width: number
  height: number
}
export interface PdfMdJob {
  id: string
  filename: string
  created_at: string
  page_count: number
  pages: PdfMdPage[]
  zoom: number
  ocr_engine: string
  ocr_done: boolean
  markdown: string
  parse_status: 'idle' | 'running' | 'done' | 'failed'
  parse_progress: number
  parse_page: number
  parse_error: string
}
export interface PdfMdJobBrief {
  id: string
  filename: string
  created_at: string
  page_count: number
  ocr_engine: string
  ocr_done: boolean
}

export function pdfMdPageImageUrl(jobId: string, page: number) {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/knowledge/pdf-md/page?job_id=${encodeURIComponent(jobId)}&page=${page}`
}

export function listPdfMdJobs() {
  return request<{ ok: boolean; jobs: PdfMdJobBrief[] }>('/knowledge/pdf-md/list')
}

export function getPdfMdJob(jobId: string) {
  return request<{ ok: boolean; job: PdfMdJob }>(`/knowledge/pdf-md/get?job_id=${encodeURIComponent(jobId)}`)
}

export function createPdfMdJob(filename: string, data: string) {
  return post<{ ok: boolean; job: PdfMdJob }>('/knowledge/pdf-md/create', { filename, data })
}

export function parsePdfMdJob(jobId: string) {
  return post<{ ok: boolean; status: string; job: PdfMdJob }>('/knowledge/pdf-md/parse', { job_id: jobId })
}

export function regionOcrPdfMd(jobId: string, page: number, rect: { x0: number; y0: number; x1: number; y1: number }) {
  return post<{ ok: boolean; markdown: string; page: number }>('/knowledge/pdf-md/region', { job_id: jobId, page, rect })
}

export function savePdfMdMarkdown(jobId: string, markdown: string) {
  return post<{ ok: boolean }>('/knowledge/pdf-md/save', { job_id: jobId, markdown })
}

export function deletePdfMdJob(jobId: string) {
  return post<{ ok: boolean }>('/knowledge/pdf-md/delete', { job_id: jobId })
}

export function pdfMdToKnowledge(jobId: string, markdown: string, scope: string) {
  return post<{ ok: boolean; doc: KnowledgeDoc }>('/knowledge/pdf-md/to-kb', { job_id: jobId, markdown, scope })
}

export function getKnowledgeConfig() {
  return request<KnowledgeConfig>('/knowledge-config')
}

export function saveKnowledgeConfig(payload: KnowledgeConfigPayload) {
  return post<KnowledgeConfig>('/knowledge-config', payload)
}

export function testKnowledgeEmbedding(payload: Partial<KnowledgeConfigPayload>) {
  return post<{ ok: boolean; model: string; dimensions: number; qdrant?: string; rerank?: string; ragflow?: string }>('/knowledge-test', payload)
}

export function uploadKnowledgeDoc(filename: string, data: string, scope = 'mine') {
  return post<{ ok: boolean; doc: KnowledgeDoc }>('/knowledge/upload', { filename, data, scope })
}

export interface KnowledgeKb {
  id: string
  name: string
  parent_id?: string
  root_type?: string
  shared: boolean
  default: boolean
  document_count: number
  chunk_count: number
}

export function getDigitalHumanKbConfig() {
  return request<{ ok: boolean; enabled: boolean; kb_ids: string[] }>('/digital-human/kb-config')
}

export function saveDigitalHumanKbConfig(payload: { enabled: boolean; kb_ids: string[] }) {
  return post<{ ok: boolean; enabled: boolean; kb_ids: string[] }>('/digital-human/kb-config', payload)
}

export function listKnowledgeKbs() {
  return request<{ ok: boolean; provider: string; kbs: KnowledgeKb[] }>('/knowledge/kbs')
}

export function manageKnowledgeKb(payload: { action: 'create' | 'delete'; name?: string; id?: string }) {
  return post<{ ok: boolean; id?: string; name?: string }>('/knowledge/kbs', payload)
}

export function listKnowledgeDocs(scope = 'mine') {
  return request<{ ok: boolean; docs: KnowledgeDoc[]; embedding_model: string; stale_docs: string[]; can_manage?: boolean; provider?: string }>(`/knowledge/list?scope=${scope}`)
}

export function deleteKnowledgeDoc(id: string, scope = 'mine') {
  return post<{ ok: boolean }>('/knowledge/delete', { id, scope })
}

export function reparseKnowledgeDoc(id: string, scope = 'mine') {
  return post<{ ok: boolean }>('/knowledge/reparse', { id, scope })
}

export interface RagflowDatasetOverview {
  id: string
  name: string
  document_count: number
  chunk_count: number
  chunk_method: string
}

export interface RagflowStatus {
  ok: boolean
  configured: boolean
  reachable: boolean
  version?: string
  error?: string
  datasets: RagflowDatasetOverview[]
  chunk_methods: { id: string; label: string }[]
  chunk_method: string
  chunk_token_num: number
  layout_recognize?: string
  admin_email?: string
  sso_available?: boolean
}

export function getRagflowStatus() {
  return request<RagflowStatus>('/ragflow/status')
}

export interface XinferenceConfig {
  ok: boolean
  api_url: string
  asr_model: string
  tts_model: string
  embedding_model: string
  current: {
    meeting: { api_url: string; model: string }
    tts: { provider: string; api_url: string; model: string }
    kb: { provider: string; api_url: string; model: string }
  }
}

export function getXinferenceConfig() {
  return request<XinferenceConfig>('/xinference-config')
}

export function probeXinference(apiUrl: string) {
  return post<{ ok: boolean; api_url: string; embedding: string[]; asr: string[]; tts: string[]; chat: string[] }>('/xinference-probe', { api_url: apiUrl })
}

export function applyXinference(payload: { api_url: string; asr_model?: string; tts_model?: string; embedding_model?: string }) {
  return post<{ ok: boolean; steps: string[]; warning?: string }>('/xinference-apply', payload)
}

export function getRagflowSso() {
  return request<{ ok: boolean; auth: string; email: string; url: string }>('/ragflow/sso')
}

export function bootstrapRagflow(payload: { email?: string; password?: string } = {}) {
  return post<{ ok: boolean; steps: string[] }>('/ragflow/bootstrap', payload)
}

export function saveRagflowChunkConfig(payload: { chunk_method: string; chunk_token_num: number; layout_recognize?: string }) {
  return post<{ ok: boolean; updated: string[]; warning?: string; hint?: string }>('/ragflow/chunk-config', payload)
}

export function searchKnowledge(query: string, topK = 5, kbIds: string[] = []) {
  return post<{ ok: boolean; results: KnowledgeSearchResult[]; warning?: string }>('/knowledge/search', { query, top_k: topK, kb_ids: kbIds })
}

export interface KnowledgeExternalApiInfo {
  ok: boolean
  provider: string
  public_url: string
  ready: boolean
  chat_id: string
  base_url: string
  completion_url: string
  dataset_count: number
  api_key_masked?: string
  hint?: string
}

export function getKnowledgeExternalApiInfo() {
  return request<KnowledgeExternalApiInfo>('/knowledge/external-info')
}

export function askKnowledge(question: string, topK = 5, kbIds: string[] = []) {
  return post<{ ok: boolean; answer: string; sources: KnowledgeAskSource[]; warning?: string }>('/knowledge/ask', { question, top_k: topK, kb_ids: kbIds })
}

export interface MeetingConfig {
  ok: boolean
  api_url: string
  model: string
  api_key_masked?: string
}

export interface MeetingSegment {
  time: string
  text: string
  translation: string
}

export interface MeetingRecord {
  id: string
  title: string
  created_at: string
  updated_at: string
  duration: number
  language: string
  translate_target: string
  segments: MeetingSegment[]
  summary: string
}

export interface MeetingListItem {
  id: string
  title: string
  created_at: string
  updated_at: string
  duration: number
  segment_count: number
  has_summary: boolean
}

export function getMeetingConfig() {
  return request<MeetingConfig>('/meeting-config')
}

export function testMeetingAsr(payload: { api_url?: string; api_key?: string; model?: string }) {
  return post<{ ok: boolean; model: string; text: string }>('/meeting-test', payload)
}

export function saveMeetingConfig(payload: { api_url: string; api_key: string; model: string; api_key_clear?: boolean }) {
  return post<MeetingConfig>('/meeting-config', payload)
}

export function transcribeMeetingAudio(audio: string, language: string) {
  return post<{ ok: boolean; text: string }>('/meeting/transcribe', { audio, language })
}

export function translateMeetingText(text: string, target: string) {
  return post<{ ok: boolean; text: string }>('/meeting/translate', { text, target })
}

export function summarizeMeeting(transcript: string, title: string) {
  return post<{ ok: boolean; summary: string }>('/meeting/summarize', { transcript, title })
}

export function saveMeeting(payload: Partial<MeetingRecord>) {
  return post<{ ok: boolean; id: string; meeting: MeetingRecord }>('/meeting/save', payload)
}

export function listMeetings() {
  return request<{ ok: boolean; meetings: MeetingListItem[] }>('/meeting/list')
}

export function getMeeting(id: string) {
  return request<{ ok: boolean; meeting: MeetingRecord }>(`/meeting/get?id=${encodeURIComponent(id)}`)
}

export function deleteMeeting(id: string) {
  return post<{ ok: boolean }>('/meeting/delete', { id })
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

export function addAdminUser(payload: { username: string; password: string; name: string; role?: User['role']; employee_id?: string; company?: string; department?: string; position?: string; email?: string }) {
  return post<AdminUsersResponse>('/admin-users', payload)
}

export function updateAdminUser(payload: { username: string; name?: string; password?: string; role?: User['role']; assistant_permissions?: Record<string, boolean>; email?: string }) {
  return post<AdminUsersResponse>('/admin-users-update', payload)
}

export function batchUpdateAdminUserPermissions(payload: { company: string; departments: string[]; assistant_ids: string[]; enabled: boolean }) {
  return post<AdminUsersResponse & { updated: number; assistant_ids: string[]; enabled: boolean }>('/admin-users-batch-permissions', payload)
}

export function batchUpdateUsersForAssistant(payload: { assistant_id: string; usernames: string[]; enabled: boolean }) {
  return post<AdminUsersResponse & { updated: number; assistant_id: string; enabled: boolean }>('/admin-users-assistant-batch', payload)
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

export function agentChat(kind: AgentKind, messages: AgentMessage[], sessionId?: string, fileIds: string[] = []) {
  return post<AgentChatResponse>('/agent', {
    kind,
    messages,
    ...(sessionId ? { session_id: sessionId } : {}),
    ...(fileIds.length ? { file_ids: fileIds } : {}),
  })
}

export function getAgentSession(sessionId: string, limit = 100) {
  return post<AgentSessionDetailResponse>('/agent/sessions', { action: 'get', session_id: sessionId, limit })
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

export function listLobsterModelOptions(agentId: number) {
  return post<LobsterModelOptionsResponse>('/lobster-model-options', { agent_id: agentId })
}

export function updateLobsterModel(agentId: number, modelName: string) {
  return post<LobsterModelUpdateResponse>('/update-lobster-model', { agent_id: agentId, model_name: modelName })
}

export interface BoundLobster {
  agent_id: number
  agent_name: string
}

export interface AssistantLobsterResponse {
  ok: boolean
  lobster: BoundLobster | null
  error?: string
}

export interface LobsterChatResponse {
  ok: boolean
  reply?: string
  error?: string
}

export function getAssistantLobster() {
  return request<AssistantLobsterResponse>('/assistant-lobster')
}

export function saveAssistantLobster(agentId: number | null, agentName = '') {
  return post<AssistantLobsterResponse>('/assistant-lobster', { agent_id: agentId, agent_name: agentName })
}

export function lobsterChat(message: string, sessionId?: string) {
  return post<LobsterChatResponse>('/lobster-chat', { message, session_id: sessionId })
}

export function restartLobster(agentId: number) {
  return post<{ ok: boolean; error?: string }>('/restart-lobster', { agent_id: agentId })
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

export function scanInvoiceAttachments(start: string, end: string, account: 'company' | 'personal') {
  return request<ReimbursementScanResponse>(`/reimbursement/scan?start=${start}&end=${end}&account=${account}`)
}

export function listReimbursementSearches() {
  return request<ReimbursementSearchListResponse>('/reimbursement/searches')
}

export function loadReimbursementSearch(id: string) {
  return request<ReimbursementSearchResponse>(`/reimbursement/search?id=${encodeURIComponent(id)}`)
}

export function saveReimbursementSearch(payload: {
  id?: string
  title?: string
  account: 'company' | 'personal'
  start?: string
  end?: string
  total_scanned?: number
  items: ReimbursementItem[]
  scan_chunks?: ReimbursementScanChunk[]
}) {
  return post<ReimbursementSearchResponse>('/reimbursement/search', payload)
}

export function uploadReimbursementFile(filename: string, dataB64: string) {
  return post<ReimbursementUploadResponse>('/reimbursement/upload', { filename, data: dataB64 })
}

export interface ReimbursementFetchUrlResponse extends Partial<ReimbursementItem> {
  ok: boolean
  spa?: boolean
  error?: string
}

export function fetchReimbursementUrl(url: string, hintSubject?: string, hintBody?: string) {
  return post<ReimbursementFetchUrlResponse>('/reimbursement/fetch-url', {
    url,
    hint_subject: hintSubject || '',
    hint_body: hintBody || '',
  })
}

export function mergeReimbursementPdf(items: Pick<ReimbursementItem, 'key' | 'invoice_type' | 'invoice_date' | 'invoice_amount'>[], outputName: string, mergeTrainTickets = false) {
  return post<ReimbursementMergeResponse>('/reimbursement/merge', {
    items,
    output_name: outputName,
    merge_train_tickets: mergeTrainTickets,
  })
}

export function downloadReimbursementInvoicesZip(items: Pick<ReimbursementItem, 'key' | 'invoice_type' | 'invoice_date' | 'invoice_amount' | 'invoice_location' | 'invoice_from' | 'invoice_to'>[], outputName: string) {
  return post<ReimbursementZipResponse>('/reimbursement/download-zip', {
    items,
    output_name: outputName,
  })
}

export interface ReimbursementEmailResponse {
  ok: boolean
  subject?: string
  from?: string
  date?: string
  html?: string
  attachments?: string[]
  error?: string
}

export function fetchReimbursementEmail(uid: string, account: 'company' | 'personal') {
  return request<ReimbursementEmailResponse>(
    `/reimbursement/email?uid=${encodeURIComponent(uid)}&account=${account}`,
  )
}

export function reimbursementAttachmentUrl(key: string, download = false) {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/reimbursement/attachment?key=${encodeURIComponent(key)}${download ? '&download=1' : ''}`
}

export function reimbursementOfdPreviewUrl(key: string) {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/reimbursement/ofd-preview?key=${encodeURIComponent(key)}`
}

export function reimbursementOutputUrl(filename: string) {
  const base = backendUrl ? `${backendUrl}/api` : '/personal-work-api'
  return `${base}/reimbursement/output?name=${encodeURIComponent(filename)}`
}

export interface WritingTemplate {
  id: string
  name: string
  writing_type: string
  prompt: string
  builtin?: boolean
  updated_at?: string
}

export interface WritingMaterial {
  id: string
  name: string
  size?: number
  text_preview?: string
  created_at?: string
}

export interface WritingSource {
  doc_name?: string
  dataset_name?: string
  text?: string
  score?: number
}

export interface WritingHistoryItem {
  id: string
  title: string
  writing_type: string
  requirements?: string
  outline?: string
  content?: string
  content_preview?: string
  materials?: WritingMaterial[]
  sources?: WritingSource[]
  action?: string
  created_at?: string
  updated_at?: string
}

export interface WritingGeneratePayload {
  id?: string
  title: string
  writing_type: string
  audience?: string
  tone?: string
  length?: string
  requirements?: string
  outline?: string
  content?: string
  rewrite_instruction?: string
  file_ids?: string[]
  files?: Array<{ name: string; data: string }>
  use_knowledge?: boolean
  kb_ids?: string[]
  knowledge_top_k?: number
}

export function getWritingTemplates() {
  return request<{ ok: boolean; templates: WritingTemplate[]; types: string[] }>('/writing/templates')
}

export function saveWritingTemplate(payload: Pick<WritingTemplate, 'name' | 'writing_type' | 'prompt'> & { id?: string }) {
  return post<{ ok: boolean; template: WritingTemplate }>('/writing/templates', payload)
}

export function getWritingHistory() {
  return request<{ ok: boolean; items: WritingHistoryItem[] }>('/writing/history')
}

export function getWritingHistoryItem(id: string) {
  return request<{ ok: boolean; item: WritingHistoryItem }>(`/writing/history-item?id=${encodeURIComponent(id)}`)
}

export function uploadWritingFile(files: Array<{ name: string; data: string }>) {
  return post<{ ok: boolean; files: WritingMaterial[] }>('/writing/upload', { files })
}

export function getWritingUploads() {
  return request<{ ok: boolean; files: WritingMaterial[] }>('/writing/uploads')
}

export function deleteWritingUpload(id: string) {
  return post<{ ok: boolean; deleted: string }>('/writing/upload-delete', { id })
}

export function generateWritingOutline(payload: WritingGeneratePayload) {
  return post<{ ok: boolean; outline: string; mode?: string; sources?: WritingSource[] }>('/writing/outline', payload)
}

export function generateWritingDraft(payload: WritingGeneratePayload) {
  return post<{ ok: boolean; mode?: string; item: WritingHistoryItem }>('/writing/generate', payload)
}

export function rewriteWritingDraft(payload: WritingGeneratePayload) {
  return post<{ ok: boolean; mode?: string; item: WritingHistoryItem }>('/writing/rewrite', payload)
}

export function exportWritingDraft(payload: { id?: string; title?: string; content?: string; format: 'md' | 'txt' | 'docx' | 'xlsx' }) {
  return post<{ ok: boolean; format: string; name: string; path: string; download_url: string }>('/writing/export', payload)
}

export function deleteWritingHistory(id: string) {
  return post<{ ok: boolean; deleted: string }>('/writing/delete', { id })
}

export function writingDownloadUrl(path: string) {
  if (!path) return ''
  if (/^https?:\/\//.test(path)) return path
  if (backendUrl) return path.startsWith('/api/') ? `${backendUrl}${path}` : `${backendUrl}/api${path}`
  return path.replace(/^\/api/, '/personal-work-api')
}

export interface CrmRailStage { id: string; title: string; action: string; deliverable: string; gate: string }
export interface CrmPlaybook { organizations: { type: string; label: string; departments: string; duty: string; evidence: string; stages: string[] }[]; stages: CrmRailStage[]; followups: (CrmAction & { person_name: string; can_complete?: boolean; owner_label?: string; owner_staff?: CrmStaff | null; overdue: boolean })[]; sources: { title: string; url: string }[] }
export function crmPlaybook() { return request<CrmPlaybook>('/crm/playbook') }
export function crmCompleteFollowup(id: string) { return post<{ ok: boolean; error?: string }>('/crm/followup/complete', { id }) }

export interface CrmExcelError { sheet: string; row: number; error: string; headers?: string[]; values?: Record<string, string> }
export interface CrmExcelResult { ok: boolean; created: number; skipped: number; pending?: number; errors: CrmExcelError[]; sheets: Record<string, { created: number; skipped: number; pending?: number; failed: number }> }
export async function crmImportExcel(file: File) {
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
  return post<CrmExcelResult>('/crm/excel/import', { filename: file.name, data })
}
export function crmRetryExcelRows(rows: CrmExcelError[], overwrite = false) { return post<CrmExcelResult>('/crm/excel/retry-rows', { rows, overwrite }) }
export interface CrmImportCompletionTask { id: string; status: 'pending' | 'completed'; uploader_username: string; uploader_name?: string; source_row: number; assignee_name: string; assignee_username: string; missing_fields: string[]; values: Record<string, string>; original_values: Record<string, string>; created_at: string; completed_at?: string; completed_by?: string }
export function crmImportCompletionTasks() { return request<{ ok: boolean; can_manage: boolean; pending: number; tasks: CrmImportCompletionTask[] }>('/crm/import-completion/tasks') }
export function crmCompleteImportCompletionTask(payload: { id: string; target_username?: string; values: { 公司全称: string; 姓名?: string; '姓名*'?: string; 单位类型: string; 部门?: string; 省份?: string; 城市?: string } }) { return post<{ ok: boolean; status: string; task: CrmImportCompletionTask }>('/crm/import-completion/complete', payload) }
export async function crmExportImportCompletion(region = '', manager = '') {
  const query = new URLSearchParams()
  if (region) query.set('region', region)
  if (manager) query.set('manager', manager)
  const base = backendUrl ? backendUrl + '/api/crm/import-completion/excel' : '/personal-work-api/crm/import-completion/excel'
  const response = await fetch(`${base}?${query.toString()}`, { credentials: 'include' })
  if (!response.ok) {
    let message = '导出资料补充表失败'
    try { message = (await response.json()).error || message } catch { /* binary or empty body */ }
    throw new Error(message)
  }
  const disposition = response.headers.get('content-disposition') || ''
  const name = decodeURIComponent(disposition.split("filename*=UTF-8''")[1] || '资料补充.xlsx')
  return { blob: await response.blob(), name }
}
export async function crmImportCompletionExcel(file: File) {
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
  return post<{ ok: boolean; completed: number; skipped: number; errors: { row: number; task_id?: string; error: string }[] }>('/crm/import-completion/excel', { filename: file.name, data })
}

export interface OrganizationExcelResult { ok: boolean; updated: number; skipped: number; imported?: number; pending?: number; created?: number; created_users?: {username: string; name: string}[]; notices?: { row: number; error: string }[]; errors: { row: number; error: string }[]; roster_check?: { applied: boolean; checked?: number; present?: number; missing?: number; checked_at?: string; source?: string; reason?: string; missing_users: { username: string; name: string; employee_id: string; company?: string; department?: string; position?: string }[] } }
export async function importOrganizationExcel(file: File, createUsers = false) {
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
    reader.onerror = () => reject(new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
  return post<OrganizationExcelResult>('/admin-organization/import', { filename: file.name, data, create_users: createUsers })
}

export function crmQuickCreate(payload: { format?: 'business'; company_full_name?: string; subsidiary_full_name?: string; importance?: string; support_level?: string; history?: string; last_interaction?: string; weekly_plan?: string; due_date?: string; maintenance_days?: string; business_region?: string; department?: string; manager_id?: string; responsibilities?: string; unit_name: string; unit_type: string; name: string; city: string; title: string; role: string; our_member: string; source: string }) {
  return post<{ ok: boolean; status?: 'created' | 'skipped'; error?: string }>('/crm/quick-create', payload)
}

export interface CrmCapabilities { role: string; read: boolean; write: boolean; register_action?: boolean; import: boolean; manage: boolean; appoint: boolean; batch_assign?: boolean; supervise?: boolean; expires_on: string; expired: boolean; data_scope?: 'self' | 'team' | 'organization' | 'regions' | 'all'; regions?: string[]; scope_company?: string; scope_departments?: string[] }
export interface CrmSecurityUser { username: string; name: string; employee_id?: string; company?: string; department?: string; position?: string; liaison_region_override?: string; superadmin: boolean; capabilities: CrmCapabilities; grant: { role: string; register_action?: boolean; expires_on: string; data_scope?: CrmCapabilities['data_scope']; scope_company?: string; scope_departments?: string[]; regions?: string[]; manager?: boolean } | null }
export interface CrmAuditEvent { outcome?: string; at: string; actor: string; operation: string; path: string; status: number; target: string; grant?: { role: string; expires_on: string } }
export function crmSecurityMe() { return request<{ ok: boolean; capabilities: CrmCapabilities }>('/crm/security/me') }
export interface CrmManagerView { username: string; name: string; department: string; member_keys: string[] }
export function crmAssignmentDirectory() { return request<{ok:boolean;people:{username:string;member_key:string;name:string;department:string;company:string}[]}>('/crm/assignment-directory') }
export function crmManagerDirectory() { return request<{ ok: boolean; managers: CrmManagerView[] }>('/crm/manager-directory') }
export type CrmRegionCity = { province: string; city: string }
export type CrmRegionSettings = { ok: boolean; regions: Record<string, string[]>; cities: Record<string, CrmRegionCity[]>; city_options: Record<string, string[]>; version: number; updated_at: string; updated_by: string }
export function crmRegionSettings() { return request<CrmRegionSettings>('/crm/security/region-settings') }
export interface CrmQualityRules {
  personal_weights: number[]; personal_min_dimensions: number; personal_maintenance_days: number;
  weights: number[]; good_threshold: number; fair_threshold: number; recent_days: number;
  min_dimensions: number; backup_count: number; completeness_threshold: number; strength_weight: number;
  support_scores: Record<string, number>; templates: Record<string, string[]>;
}
export interface CrmQualitySettings { ok: boolean; rules: CrmQualityRules; defaults: CrmQualityRules; roles: string[]; version: number; updated_at: string; updated_by: string }
export function crmQualitySettings() { return request<CrmQualitySettings>('/crm/security/quality-settings') }
export function crmSaveQualitySettings(payload: {rules: CrmQualityRules; version: number}) { return post<CrmQualitySettings>('/crm/security/quality-settings', payload) }
export type CrmAmapSettings = { ok: boolean; key: string; enabled: boolean; has_security_code: boolean; version: number }
export function crmAmapSettings() { return request<CrmAmapSettings>('/crm/security/amap-settings') }
export function crmSaveAmapSettings(payload: { key: string; enabled: boolean; security_code: string; version: number }) { return post<CrmAmapSettings>('/crm/security/amap-settings', payload) }
export function crmSaveRegionSettings(payload: { regions: Record<string, string[]>; cities?: Record<string, CrmRegionCity[]>; version: number }) { return post<CrmRegionSettings>('/crm/security/region-settings', payload) }
export function crmSecurityUsers() { return request<{ ok: boolean; users: CrmSecurityUser[] }>('/crm/security/users') }
export interface CrmBattleUnit { id:string; name:string; business_region:string; areas:string; leaders:string[]; roles:Record<string,string[]> }
export interface CrmBattleRoster { ok:boolean; version:number; updated_at:string; updated_by:string; management:string[]; units:CrmBattleUnit[] }
export function crmBattleRoster() { return request<CrmBattleRoster>('/crm/security/battle-roster') }
export function crmSaveBattleRoster(payload: Pick<CrmBattleRoster,'version'|'management'|'units'>) { return post<CrmBattleRoster>('/crm/security/battle-roster', payload) }
export function crmSecurityAudit() { return request<{ ok: boolean; events: CrmAuditEvent[]; scope?: 'all' | 'limited' }>('/crm/security/audit') }
export function crmSecurityGrant(payload: { username: string; role: string; register_action?: boolean; expires_on: string; data_scope?: CrmCapabilities['data_scope']; scope_company?: string; scope_departments?: string[]; regions?: string[] }) { return post<{ ok: boolean }>('/crm/security/grant', payload) }
export function crmSecurityBatchGrant(payload: { company: string; departments: string[]; role: string; register_action?: boolean; expires_on: string; data_scope?: 'self' | 'team' }) { return post<{ ok: boolean; updated: number; role: string; expires_on: string }>('/crm/security/batch-grant', payload) }
export function crmSaveLiaisonRegion(payload: { username: string; region: string }) { return post<{ ok: boolean; username: string; region: string }>('/crm/security/liaison-region', payload) }

export function crmSecurityAppoint(username: string, manager: boolean) { return post<{ ok: boolean }>('/crm/security/appoint', { username, manager, role: 'disabled' }) }

export interface CrmStaff { id: string; name: string; member_key: string; username?: string; company: string; department: string; title: string; manager_id: string; business_region: string; responsibilities: string; version: number }
export function crmStaff() { return request<{ok:boolean;staff:CrmStaff[]}>('/crm/staff') }
export function crmSaveStaff(payload: Partial<CrmStaff>) { return post<{ok:boolean;staff?:CrmStaff;error?:string}>('/crm/staff/save',payload) }
export interface MonthlyBattleEvent { event_type?: 'action' | 'stage_change' }
