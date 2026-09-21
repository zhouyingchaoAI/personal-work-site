<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  Calendar,
  CollectionTag,
  Delete,
  Document,
  MagicStick,
  Plus,
  Reading,
  Refresh,
  Search,
  Setting,
  Star,
  StarFilled,
  User,
  WarningFilled,
} from '@element-plus/icons-vue'
import { authState } from '../../services/authSession'
import {
  addNewsFavorite,
  fetchLatestNews,
  fetchNewsFavorites,
  fetchNewsHistory,
  fetchPersonalNews,
  fetchPersonalNewsHistory,
  generateNewsIssue,
  generatePersonalNewsIssue,
  removeNewsFavorite,
  saveNewsConfig,
  savePersonalNewsConfig,
  searchWechatAccounts,
  type NewsConfig,
  type NewsFavorite,
  type NewsHistoryItem,
  type NewsIssue,
  type NewsItem,
  type NewsSource,
  type WechatAccountCandidate,
} from '../../services/personalWorkApi'
import './index.scss'

type Scope = 'public' | 'personal' | 'favorites'

interface ScopeState {
  issue: NewsIssue | null
  history: NewsHistoryItem[]
  activeDate: string
  config: NewsConfig
  configLoaded: boolean
  loaded: boolean
}

function emptyConfig(): NewsConfig {
  return {
    sources: [{ name: '', url: '', kind: 'web' }],
    search_query: '',
    auto_search: true,
    auto_push: true,
    push_time: '08:30',
  }
}

function createState(autoPushDefault: boolean): ScopeState {
  return {
    issue: null,
    history: [],
    activeDate: '',
    config: { ...emptyConfig(), auto_push: autoPushDefault },
    configLoaded: false,
    loaded: false,
  }
}

const scope = ref<Scope>('public')
const activePanel = ref<'reader' | 'config'>('reader')
const pub = reactive<ScopeState>(createState(true))
const per = reactive<ScopeState>(createState(false))

const loading = reactive({
  latest: false,
  history: false,
  saveConfig: false,
  generate: false,
})
const wechatSearch = reactive({ query: '', loading: false, candidates: [] as WechatAccountCandidate[], notice: '' })
const wechatManual = reactive({ name: '', url: '', saving: false })
const wechatExporterUrl = `${window.location.origin}/personal-office-assistant/wechat-article/`
const advancedOpen = ref(false)

const user = computed(() => authState.user)
const isSuperadmin = computed(() => !!user.value?.is_superadmin)
// 公共资讯仅超级管理员可配置；个人资讯所有账号都能配置自己的来源；收藏夹无配置。
const canConfig = computed(() => scope.value === 'personal' || (scope.value === 'public' && isSuperadmin.value))

const state = computed<ScopeState>(() => (scope.value === 'personal' ? per : pub))
const config = computed(() => state.value.config)
const subscribedWechatSources = computed(() =>
  config.value.sources
    .map((source, index) => ({ source, index }))
    .filter(({ source }) => source.kind === 'wechat_account' && source.name.trim()),
)

// 个人收藏夹：跨公共/个人资讯，看到感兴趣的条目可收藏，支持搜索。
const favorites = ref<NewsFavorite[]>([])
const favoriteKeys = ref<Set<string>>(new Set())
const favoriteSearch = ref('')
const favoritesLoaded = ref(false)
const loadingFav = reactive({ list: false, mutate: false })

function favoriteKey(item: { url?: string; title?: string }) {
  // 与后端一致：标题+链接组合，避免同源不同条的资讯撞键。
  const title = (item.title || '').trim().toLowerCase()
  const url = (item.url || '').trim().toLowerCase()
  return `${title}|${url}`
}

function isFavorited(item: { url?: string; title?: string }) {
  return favoriteKeys.value.has(favoriteKey(item))
}

function syncFavoriteKeys(list: NewsFavorite[]) {
  favoriteKeys.value = new Set(list.map((item) => favoriteKey(item)))
}

const issue = computed(() => state.value.issue)
const history = computed(() => state.value.history)
const activeDate = computed(() => state.value.activeDate)
const issueItems = computed(() => issue.value?.items || [])
const issueKeywords = computed(() => issue.value?.keywords || [])
const issueErrors = computed(() => issue.value?.errors || [])
const issueTitle = computed(() => issue.value?.title || (scope.value === 'public' ? '暂无每日资讯' : '暂无个人资讯'))
const issueSummary = computed(() => issue.value?.summary || '暂无摘要。')
const issueMeta = computed(() => {
  if (!issue.value) return canConfig.value ? '配置资讯源后生成简报。' : '暂无今日简报，请稍后刷新。'
  return [issue.value.date, formatDateTime(issue.value.generated_at), issue.value.generated_by].filter(Boolean).join(' · ')
})
const historyMeta = computed(() => (history.value.length ? `已保存 ${history.value.length} 期资讯` : '暂无历史资讯'))
const emptyHint = computed(() =>
  canConfig.value ? '可以配置资讯源后生成简报。' : '暂无今日简报，请稍后刷新。',
)

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

function formatDateTime(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function normalizeSources(sources: NewsSource[]): NewsSource[] {
  const normalized: NewsSource[] = sources.map((source) => ({
    name: source.name || '',
    url: source.url || '',
    kind: source.kind === 'wechat_account' ? 'wechat_account' : 'web',
  }))
  return normalized.length ? normalized : [{ name: '', url: '', kind: 'web' }]
}

function applyConfig(target: ScopeState, payload?: NewsConfig) {
  if (!payload) return
  target.config = {
    sources: normalizeSources(payload.sources || []),
    search_query: payload.search_query || '',
    auto_search: !!payload.auto_search,
    auto_push: !!payload.auto_push,
    push_time: payload.push_time || '08:30',
  }
  target.configLoaded = true
}

function configPayload(): NewsConfig {
  const current = state.value.config
  return {
    sources: current.sources
      .map((source) => ({
        name: source.name.trim(),
        url: source.url.trim(),
        kind: source.kind === 'wechat_account' ? 'wechat_account' as const : 'web' as const,
      }))
      .filter((source) => source.url || (source.kind === 'wechat_account' && source.name)),
    search_query: current.search_query.trim(),
    auto_search: current.auto_search,
    auto_push: current.auto_push,
    push_time: current.push_time || '08:30',
  }
}

function switchScope(next: Scope) {
  if (scope.value === next) return
  scope.value = next
  if (!canConfig.value) activePanel.value = 'reader'
  if (next === 'favorites') {
    loadFavorites()
  } else if (!state.value.loaded) {
    loadLatestNews()
  }
}

function switchPanel(panel: 'reader' | 'config') {
  activePanel.value = panel
}

function addSource(kind: NewsSource['kind'] = 'web') {
  state.value.config.sources.push({ name: '', url: '', kind: kind || 'web' })
}

async function handleWechatAccountSearch() {
  const query = wechatSearch.query.trim()
  if (query.length < 2 || wechatSearch.loading) {
    if (query.length < 2) ElMessage.warning('请输入至少两个字的公众号名称')
    return
  }
  wechatSearch.loading = true
  wechatSearch.candidates = []
  try {
    const result = await searchWechatAccounts(query)
    wechatSearch.candidates = result.candidates || []
    wechatSearch.notice = result.notice || ''
  } catch (error) {
    wechatSearch.notice = errorMessage(error)
  } finally {
    wechatSearch.loading = false
  }
}

async function subscribeWechatAccount(candidate: WechatAccountCandidate) {
  const duplicate = state.value.config.sources.some((source) =>
    source.kind === 'wechat_account' && source.name.trim().toLowerCase() === candidate.name.trim().toLowerCase(),
  )
  if (duplicate) {
    ElMessage.info('该公众号已在订阅列表中')
    return
  }
  state.value.config.sources.push({ name: candidate.name, url: '', kind: 'wechat_account' })
  await handleSaveConfig()
  wechatSearch.query = ''
  wechatSearch.candidates = []
  wechatSearch.notice = `已订阅「${candidate.name}」，可直接生成个人资讯。`
}

// 搜索无结果时的兜底：按名称手动订阅公众号，可选附一篇 mp.weixin.qq.com/s/ 文章入口。
async function subscribeWechatManual() {
  const name = wechatManual.name.trim()
  const url = wechatManual.url.trim()
  if (!name) {
    ElMessage.warning('请填写公众号名称')
    return
  }
  if (url && !/^https?:\/\/mp\.weixin\.qq\.com\/s\//i.test(url)) {
    ElMessage.warning('文章入口需为 mp.weixin.qq.com/s/... 的链接；如无可留空')
    return
  }
  const duplicate = state.value.config.sources.some((source) =>
    source.kind === 'wechat_account' && source.name.trim().toLowerCase() === name.toLowerCase(),
  )
  if (duplicate) {
    ElMessage.info('该公众号已在订阅列表中')
    return
  }
  wechatManual.saving = true
  try {
    state.value.config.sources.push({ name, url, kind: 'wechat_account' })
    await handleSaveConfig()
    wechatManual.name = ''
    wechatManual.url = ''
    wechatSearch.notice = `已订阅「${name}」，可直接生成个人资讯。`
  } finally {
    wechatManual.saving = false
  }
}

function removeSource(index: number) {
  const sources = state.value.config.sources
  sources.splice(index, 1)
  if (!sources.length) addSource()
}

function openSource(url: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadFavorites(keepKeys = false) {
  if (loadingFav.list) return
  loadingFav.list = true
  try {
    const result = await fetchNewsFavorites(favoriteSearch.value.trim())
    favorites.value = result.favorites || []
    // 仅在未筛选时同步「是否已收藏」的全量键，避免搜索结果污染星标状态。
    if (!keepKeys && !favoriteSearch.value.trim()) syncFavoriteKeys(favorites.value)
    favoritesLoaded.value = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingFav.list = false
  }
}

function searchFavorites() {
  loadFavorites(true)
}

function clearFavoriteSearch() {
  if (!favoriteSearch.value) return
  favoriteSearch.value = ''
  loadFavorites()
}

async function toggleFavorite(item: NewsItem) {
  if (loadingFav.mutate) return
  loadingFav.mutate = true
  try {
    if (isFavorited(item)) {
      const result = await removeNewsFavorite({ url: item.url, title: item.title })
      favorites.value = result.favorites || []
      syncFavoriteKeys(favorites.value)
      item.fav_count = result.fav_count ?? Math.max(0, (item.fav_count || 1) - 1)
      ElMessage.success('已移出收藏夹')
    } else {
      const result = await addNewsFavorite({
        title: item.title,
        source: item.source,
        url: item.url,
        impact: item.impact,
        action: item.action,
        scope: scope.value,
        issue_date: issue.value?.date || '',
        issue_title: issue.value?.title || '',
      })
      favorites.value = result.favorites || favorites.value
      syncFavoriteKeys(favorites.value)
      item.fav_count = result.fav_count ?? (item.fav_count || 0) + (result.already ? 0 : 1)
      ElMessage.success(result.already ? '该资讯已在收藏夹中' : '已加入收藏夹')
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingFav.mutate = false
  }
}

async function removeFavorite(fav: NewsFavorite) {
  if (loadingFav.mutate) return
  loadingFav.mutate = true
  try {
    const result = await removeNewsFavorite({ id: fav.id, url: fav.url, title: fav.title })
    syncFavoriteKeys(result.favorites || [])
    // 若正在搜索，保留筛选结果（直接从当前列表移除该项），否则展示全量。
    if (favoriteSearch.value.trim()) {
      favorites.value = favorites.value.filter((item) => item.id !== fav.id)
    } else {
      favorites.value = result.favorites || []
    }
    ElMessage.success('已移出收藏夹')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loadingFav.mutate = false
  }
}

async function loadLatestNews() {
  if (loading.latest) return
  loading.latest = true
  const target = state.value
  try {
    if (scope.value === 'public') {
      const result = await fetchLatestNews()
      target.issue = result.issue
      target.history = result.history || []
      target.activeDate = result.issue?.date || ''
      if (isSuperadmin.value) applyConfig(target, result.config)
    } else {
      const result = await fetchPersonalNews()
      target.issue = result.issue
      target.history = result.history || []
      target.activeDate = result.issue?.date || ''
      applyConfig(target, result.config)
    }
    target.loaded = true
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.latest = false
  }
}

async function loadNewsByDate(date: string) {
  if (!date || loading.history) return
  loading.history = true
  const target = state.value
  try {
    const result =
      scope.value === 'public' ? await fetchNewsHistory(date) : await fetchPersonalNewsHistory(date)
    target.issue = result.issue || null
    target.history = result.history || []
    target.activeDate = result.issue?.date || date
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.history = false
  }
}

async function handleSaveConfig() {
  if (!canConfig.value || loading.saveConfig) return
  loading.saveConfig = true
  const target = state.value
  try {
    const payload = configPayload()
    const result =
      scope.value === 'public' ? await saveNewsConfig(payload) : await savePersonalNewsConfig(payload)
    applyConfig(target, result.config)
    if (result.issue) {
      target.issue = result.issue
      target.activeDate = result.issue.date
      const latest = scope.value === 'public' ? await fetchNewsHistory() : await fetchPersonalNewsHistory()
      target.history = latest.history || []
      ElMessage.success('配置已保存，今日资讯已更新')
    } else {
      ElMessage.success(result.refresh_error ? '资讯配置已保存，自动刷新失败，可点击生成资讯重试' : '资讯配置已保存')
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveConfig = false
  }
}

async function handleGenerateNews() {
  if (!canConfig.value || loading.generate) return
  loading.generate = true
  const target = state.value
  try {
    const result =
      scope.value === 'public'
        ? await generateNewsIssue(target.config.search_query, target.config.auto_search)
        : await generatePersonalNewsIssue(target.config.search_query, target.config.auto_search)
    if (result.issue) {
      target.issue = result.issue
      target.activeDate = result.issue.date
    }
    const latest =
      scope.value === 'public' ? await fetchNewsHistory() : await fetchPersonalNewsHistory()
    target.history = latest.history || []
    ElMessage.success(
      result.skipped
        ? (result.message || '没有可用资讯，本次未生成简报')
        : (scope.value === 'public' ? '今日资讯已生成' : '个人资讯已生成'),
    )
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.generate = false
  }
}

watch(canConfig, (value) => {
  if (!value) activePanel.value = 'reader'
})

onMounted(() => {
  loadLatestNews()
  // 预加载收藏键，使简报里的星标状态从一开始就正确。
  loadFavorites()
})
</script>

<template>
  <section class="workspace-main news-main">
    <header class="news-page-head">
      <div class="news-page-actions">
        <div class="news-page-tabs" role="tablist" aria-label="资讯范围">
          <button :class="{ active: scope === 'public' }" type="button" @click="switchScope('public')">公共资讯</button>
          <button :class="{ active: scope === 'personal' }" type="button" @click="switchScope('personal')">个人资讯</button>
          <button :class="{ active: scope === 'favorites' }" type="button" @click="switchScope('favorites')">我的收藏</button>
        </div>
        <div v-if="canConfig" class="news-page-tabs" role="tablist" aria-label="资讯视图">
          <button :class="{ active: activePanel === 'reader' }" type="button" @click="switchPanel('reader')">资讯简报</button>
          <button :class="{ active: activePanel === 'config' }" type="button" @click="switchPanel('config')">资讯配置</button>
        </div>
        <button
          v-if="scope === 'favorites'"
          class="news-button news-button--ghost"
          type="button"
          :disabled="loadingFav.list"
          @click="loadFavorites()"
        >
          <el-icon><Refresh /></el-icon>
          {{ loadingFav.list ? '刷新中' : '刷新' }}
        </button>
        <button v-else class="news-button news-button--ghost" type="button" :disabled="loading.latest" @click="loadLatestNews">
          <el-icon><Refresh /></el-icon>
          {{ loading.latest ? '刷新中' : '刷新' }}
        </button>
        <button
          v-if="canConfig"
          class="news-button news-button--primary"
          type="button"
          :disabled="loading.generate"
          @click="handleGenerateNews"
        >
          <el-icon><MagicStick /></el-icon>
          {{ loading.generate ? '生成中' : '立即生成' }}
        </button>
      </div>
    </header>

    <div class="news-workspace">
      <aside class="news-history-column">
        <section v-if="scope === 'favorites'" class="news-card news-history-card">
          <div class="news-card-head">
            <span class="news-card-icon"><el-icon><Star /></el-icon></span>
            <div>
              <h2>我的收藏夹</h2>
              <p>{{ favorites.length ? `共 ${favorites.length} 条收藏` : '暂无收藏' }}</p>
            </div>
          </div>
          <div class="news-side-empty">
            <el-icon><Star /></el-icon>
            <strong>收藏你关心的资讯</strong>
            <span>在公共/个人简报里点击星标即可收藏，支持关键词搜索。</span>
          </div>
        </section>
        <section v-else class="news-card news-history-card">
          <div class="news-card-head">
            <span class="news-card-icon"><el-icon><Reading /></el-icon></span>
            <div>
              <h2>{{ scope === 'public' ? '公共历史资讯' : '个人历史资讯' }}</h2>
              <p>{{ historyMeta }}</p>
            </div>
          </div>

          <div v-if="history.length" class="news-history-list">
            <button
              v-for="item in history"
              :key="item.date"
              :class="['news-history-item', { active: item.date === activeDate }]"
              type="button"
              :disabled="loading.history"
              @click="loadNewsByDate(item.date)"
            >
              <time>{{ item.date }}</time>
              <span>
                <strong>{{ item.title || item.date || '每日资讯' }}</strong>
                <em>{{ item.summary || '暂无摘要。' }}</em>
              </span>
              <small>{{ item.item_count || 0 }} 条</small>
            </button>
          </div>
          <div v-else class="news-side-empty">
            <el-icon><Reading /></el-icon>
            <strong>暂无历史资讯</strong>
            <span>生成资讯后会在这里保留历史记录。</span>
          </div>
        </section>
      </aside>

      <main class="news-reader-column">
        <article v-if="scope !== 'favorites' && activePanel === 'reader'" class="news-card news-issue-card" :class="{ 'is-loading': loading.latest || loading.history }">
          <div class="news-issue-head">
            <div>
              <span class="news-issue-label">
                <el-icon><component :is="scope === 'public' ? Document : User" /></el-icon>
                {{ scope === 'public' ? '公共简报' : '个人简报' }}
              </span>
              <h2>{{ issueTitle }}</h2>
              <p>{{ issueMeta }}</p>
            </div>
            <strong>{{ issueItems.length }} 条</strong>
          </div>

          <section class="news-summary-panel">
            <span class="news-date-pill">
              <el-icon><Calendar /></el-icon>
              {{ issue?.date || '今日' }}
            </span>
            <p>{{ issueSummary }}</p>
          </section>

          <div v-if="issueKeywords.length" class="news-keywords" aria-label="关键词">
            <span v-for="keyword in issueKeywords" :key="keyword">{{ keyword }}</span>
          </div>

          <div v-if="issueErrors.length && canConfig" class="news-warning">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ issueErrors.slice(0, 2).join('；') }}</span>
          </div>

          <div class="news-section-title">
            <span><el-icon><Document /></el-icon></span>
            <h4>资讯条目</h4>
          </div>

          <div v-if="issueItems.length" class="news-item-list">
            <article v-for="(item, index) in issueItems" :key="`${item.title}-${index}`" class="news-item-card">
              <span class="news-item-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div class="news-item-main">
                <div class="news-item-top">
                  <span>
                    <el-icon><CollectionTag /></el-icon>
                    {{ item.source || '未注明来源' }}
                  </span>
                  <span class="news-fav-count" :class="{ active: (item.fav_count || 0) > 0 }">
                    <el-icon><StarFilled /></el-icon>
                    {{ item.fav_count || 0 }} 人收藏
                  </span>
                </div>
                <h3>{{ item.title || '未命名资讯' }}</h3>
                <p class="news-item-impact">
                  <strong>影响/价值</strong>
                  {{ item.impact || '暂无' }}
                </p>
                <div class="news-item-action-row">
                  <p>
                    <strong>建议动作</strong>
                    {{ item.action || '暂无' }}
                  </p>
                </div>
                <div class="news-item-source-row">
                  <button
                    type="button"
                    class="news-fav-toggle"
                    :class="{ active: isFavorited(item) }"
                    :disabled="loadingFav.mutate"
                    @click="toggleFavorite(item)"
                  >
                    <el-icon><component :is="isFavorited(item) ? StarFilled : Star" /></el-icon>
                    {{ isFavorited(item) ? '已收藏' : '收藏' }}
                  </button>
                  <button v-if="item.url" type="button" @click="openSource(item.url)">
                    来源链接
                    <el-icon><ArrowRight /></el-icon>
                  </button>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="news-empty">
            <el-icon><Reading /></el-icon>
            <strong>暂无资讯条目</strong>
            <span>{{ emptyHint }}</span>
          </div>
        </article>

        <article v-else-if="scope !== 'favorites'" class="news-card news-config-page">
          <div class="news-config-page-head">
            <div>
              <span class="news-date-pill">
                <el-icon><Setting /></el-icon>
                {{ scope === 'public' ? '公共资讯配置' : '个人资讯配置' }}
              </span>
              <h3>订阅与更新</h3>
              <p>
                {{ scope === 'public'
                  ? '订阅公众号后，每日自动生成全站共享资讯。'
                  : '订阅感兴趣的公众号，每日自动为你更新最新资讯。' }}
              </p>
            </div>
            <span v-if="state.configLoaded" class="news-config-status">已读取</span>
          </div>

          <div class="news-config-form news-config-form--page">
            <div class="news-source-editor">
              <div class="news-source-title">
                <strong>订阅公众号</strong>
                <span>搜索后点击订阅，最新文章会自动进入资讯。</span>
              </div>
              <div class="news-wechat-subscribe">
                <strong>订阅微信公众号</strong>
                <label class="news-wechat-label" for="news-wechat-search">搜索公众号</label>
                <div class="news-wechat-search-row">
                  <input id="news-wechat-search" v-model="wechatSearch.query" type="search" placeholder="输入公众号名称，例如：新智元" @keyup.enter="handleWechatAccountSearch" />
                  <button class="news-source-add-wechat" type="button" :disabled="wechatSearch.loading" @click="handleWechatAccountSearch">
                    <el-icon><Search /></el-icon>{{ wechatSearch.loading ? '搜索中' : '搜索公众号' }}
                  </button>
                </div>
                <p v-if="wechatSearch.notice" class="news-source-help">{{ wechatSearch.notice }}</p>
                <div v-if="wechatSearch.candidates.length" class="news-wechat-candidates">
                  <article v-for="candidate in wechatSearch.candidates" :key="`${candidate.name}-${candidate.url}`">
                    <div><strong>{{ candidate.name }}</strong><span>{{ candidate.account_type || '公众号' }}<template v-if="candidate.account_id"> · 微信号：{{ candidate.account_id }}</template></span><span v-if="candidate.original_count || candidate.updated_text">{{ candidate.original_count ? `${candidate.original_count} 篇原创内容` : '' }}{{ candidate.original_count && candidate.updated_text ? ' · ' : '' }}{{ candidate.updated_text }}</span><span v-if="candidate.source">核验来源：{{ candidate.source }}</span><p>{{ candidate.description }}</p></div>
                    <button type="button" @click="subscribeWechatAccount(candidate)">订阅</button>
                  </article>
                </div>
                <div class="news-wechat-manual">
                  <span class="news-wechat-manual__hint">搜不到？按名称手动订阅，或补一篇文章入口链接作为抓取回退。</span>
                  <div class="news-wechat-manual__row">
                    <input v-model="wechatManual.name" type="text" placeholder="公众号名称" />
                    <input v-model="wechatManual.url" type="url" placeholder="文章入口（可选，mp.weixin.qq.com/s/...）" @keyup.enter="subscribeWechatManual" />
                    <button type="button" :disabled="wechatManual.saving" @click="subscribeWechatManual">订阅</button>
                  </div>
                </div>
              </div>
              <div v-if="subscribedWechatSources.length" class="news-wechat-subscribed">
                <div class="news-wechat-subscribed__head">
                  <div><strong>已订阅公众号</strong><span>{{ subscribedWechatSources.length }} 个</span></div>
                  <p>仅收录当天新发布的文章；未更新账号会在简报中明确提示。</p>
                </div>
                <div class="news-wechat-subscribed__list">
                  <button v-for="item in subscribedWechatSources" :key="`${item.source.name}-${item.index}`" type="button" @click="removeSource(item.index)">
                    <span>{{ item.source.name }}</span><el-icon title="取消订阅"><Delete /></el-icon>
                  </button>
                </div>
              </div>
              <div v-if="isSuperadmin" class="news-wechat-exporter">
                <div class="news-wechat-exporter__copy">
                  <span class="news-wechat-exporter__badge">系统管理</span>
                  <strong>采集历史库（本浏览器）</strong>
                  <span>仅显示在采集器中手动导入并同步历史的账号。资讯助手订阅独立生效，无需在此重复添加。</span>
                </div>
                <a :href="wechatExporterUrl" target="_blank" rel="noopener noreferrer">打开历史库</a>
              </div>
            </div>

            <div class="news-simple-schedule">
              <span>每日更新</span>
              <label><input v-model="config.auto_push" type="checkbox" /> 自动生成</label>
              <input v-model="config.push_time" type="time" :disabled="!config.auto_push" />
              <button type="button" @click="advancedOpen = !advancedOpen">{{ advancedOpen ? '收起高级设置' : '高级设置' }}</button>
            </div>

            <div v-if="advancedOpen" class="news-advanced-settings">
              <label class="news-field news-field--full">
                <span>补充搜索关键词</span>
                <textarea v-model="config.search_query" rows="2" placeholder="例如：人工智能 OR 大模型 OR 机器人"></textarea>
              </label>
              <label class="news-check-row"><input v-model="config.auto_search" type="checkbox" /><span>允许大模型补充全网最新资讯</span></label>
              <div class="news-source-title"><strong>其他网页来源</strong><button type="button" @click="addSource('web')"><el-icon><Plus /></el-icon> 添加网页</button></div>
              <div class="news-source-list">
                <div v-for="(source, index) in config.sources" v-show="source.kind === 'web'" :key="index" class="news-source-row news-source-row--web">
                  <label><span>来源名称</span><input v-model="source.name" type="text" placeholder="可选，例如行业官网" /></label>
                  <label><span>网址</span><input v-model="source.url" type="url" placeholder="https://" /></label>
                  <button class="news-source-remove" type="button" :aria-label="`删除第 ${index + 1} 个来源`" @click="removeSource(index)"><el-icon><Delete /></el-icon></button>
                </div>
              </div>
            </div>

            <div class="news-config-actions news-config-actions--page">
              <button class="news-button news-button--ghost" type="button" :disabled="loading.saveConfig" @click="handleSaveConfig">
                <el-icon><Setting /></el-icon>
                {{ loading.saveConfig ? '保存中' : '保存配置' }}
              </button>
              <button class="news-button news-button--primary" type="button" :disabled="loading.generate" @click="handleGenerateNews">
                <el-icon><MagicStick /></el-icon>
                {{ loading.generate ? '生成中' : '生成资讯' }}
              </button>
            </div>
          </div>
        </article>

        <article v-else class="news-card news-favorites-page">
          <div class="news-config-page-head">
            <div>
              <span class="news-date-pill">
                <el-icon><StarFilled /></el-icon>
                我的收藏
              </span>
              <h3>个人收藏夹</h3>
              <p>这里汇总你从公共/个人资讯里收藏的条目，可按关键词搜索标题、来源或内容。</p>
            </div>
            <span class="news-config-status">{{ favorites.length }} 条</span>
          </div>

          <div class="news-fav-search">
            <el-icon><Search /></el-icon>
            <input
              v-model="favoriteSearch"
              type="search"
              placeholder="搜索收藏夹：标题 / 来源 / 关键词"
              @keyup.enter="searchFavorites"
            />
            <button v-if="favoriteSearch" type="button" class="news-fav-search-clear" @click="clearFavoriteSearch">清空</button>
            <button type="button" class="news-button news-button--primary" :disabled="loadingFav.list" @click="searchFavorites">
              <el-icon><Search /></el-icon>
              {{ loadingFav.list ? '搜索中' : '搜索' }}
            </button>
          </div>

          <div v-if="favorites.length" class="news-item-list">
            <article v-for="fav in favorites" :key="fav.id" class="news-item-card">
              <span class="news-item-index"><el-icon><StarFilled /></el-icon></span>
              <div class="news-item-main">
                <div class="news-item-top">
                  <span>
                    <el-icon><CollectionTag /></el-icon>
                    {{ fav.source || '未注明来源' }}
                  </span>
                  <span class="news-fav-meta">
                    <template v-if="fav.issue_date">{{ fav.issue_date }} · {{ fav.scope === 'personal' ? '个人资讯' : '公共资讯' }} · </template>
                    {{ fav.fav_count || 0 }} 人收藏
                  </span>
                </div>
                <h3>{{ fav.title || '未命名资讯' }}</h3>
                <p v-if="fav.impact" class="news-item-impact">
                  <strong>影响/价值</strong>
                  {{ fav.impact }}
                </p>
                <div v-if="fav.action" class="news-item-action-row">
                  <p>
                    <strong>建议动作</strong>
                    {{ fav.action }}
                  </p>
                </div>
                <div class="news-item-source-row">
                  <button v-if="fav.url" type="button" @click="openSource(fav.url)">
                    来源链接
                    <el-icon><ArrowRight /></el-icon>
                  </button>
                  <button type="button" class="news-fav-toggle active" :disabled="loadingFav.mutate" @click="removeFavorite(fav)">
                    <el-icon><Delete /></el-icon>
                    移出收藏
                  </button>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="news-empty">
            <el-icon><Star /></el-icon>
            <strong>{{ favoriteSearch ? '没有匹配的收藏' : '收藏夹还是空的' }}</strong>
            <span>{{ favoriteSearch ? '换个关键词再试试。' : '在公共/个人简报里点击条目上的星标即可加入收藏。' }}</span>
          </div>
        </article>
      </main>
    </div>
  </section>
</template>
