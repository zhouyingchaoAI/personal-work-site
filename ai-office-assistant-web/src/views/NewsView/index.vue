<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
  Setting,
  WarningFilled,
} from '@element-plus/icons-vue'
import { authState } from '../../services/authSession'
import {
  fetchLatestNews,
  fetchNewsHistory,
  generateNewsIssue,
  saveNewsConfig,
  type NewsConfig,
  type NewsHistoryItem,
  type NewsIssue,
  type NewsSource,
} from '../../services/personalWorkApi'
import './index.scss'

const issue = ref<NewsIssue | null>(null)
const history = ref<NewsHistoryItem[]>([])
const activeDate = ref('')
const activePanel = ref<'reader' | 'config'>('reader')
const configLoaded = ref(false)
const config = reactive<NewsConfig>({
  sources: [{ name: '', url: '' }],
  search_query: '',
  auto_search: true,
  auto_push: true,
  push_time: '08:30',
})
const loading = reactive({
  latest: false,
  history: false,
  saveConfig: false,
  generate: false,
})

const user = computed(() => authState.user)
const isSuperadmin = computed(() => !!user.value?.is_superadmin)
const issueItems = computed(() => issue.value?.items || [])
const issueKeywords = computed(() => issue.value?.keywords || [])
const issueErrors = computed(() => issue.value?.errors || [])
const issueTitle = computed(() => issue.value?.title || '暂无每日资讯')
const issueSummary = computed(() => issue.value?.summary || '暂无摘要。')
const issueMeta = computed(() => {
  if (!issue.value) return isSuperadmin.value ? '配置资讯源后生成今日简报。' : '暂无今日简报，请稍后刷新。'
  return [issue.value.date, formatDateTime(issue.value.generated_at), issue.value.generated_by].filter(Boolean).join(' · ')
})
const historyMeta = computed(() => (history.value.length ? `已保存 ${history.value.length} 期每日资讯` : '暂无历史资讯'))

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

function normalizeSources(sources: NewsSource[]) {
  const normalized = sources.map((source) => ({
    name: source.name || '',
    url: source.url || '',
  }))
  return normalized.length ? normalized : [{ name: '', url: '' }]
}

function applyConfig(payload?: NewsConfig) {
  if (!payload) return
  config.sources = normalizeSources(payload.sources || [])
  config.search_query = payload.search_query || ''
  config.auto_search = !!payload.auto_search
  config.auto_push = !!payload.auto_push
  config.push_time = payload.push_time || '08:30'
  configLoaded.value = true
}

function configPayload(): NewsConfig {
  return {
    sources: config.sources
      .map((source) => ({
        name: source.name.trim(),
        url: source.url.trim(),
      }))
      .filter((source) => source.url),
    search_query: config.search_query.trim(),
    auto_search: config.auto_search,
    auto_push: config.auto_push,
    push_time: config.push_time || '08:30',
  }
}

function switchPanel(panel: 'reader' | 'config') {
  activePanel.value = panel
}

function addSource() {
  config.sources.push({ name: '', url: '' })
}

function removeSource(index: number) {
  config.sources.splice(index, 1)
  if (!config.sources.length) addSource()
}

function openSource(url: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadLatestNews() {
  if (loading.latest) return
  loading.latest = true
  try {
    const result = await fetchLatestNews()
    issue.value = result.issue
    history.value = result.history || []
    activeDate.value = result.issue?.date || ''
    if (isSuperadmin.value) applyConfig(result.config)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.latest = false
  }
}

async function loadNewsByDate(date: string) {
  if (!date || loading.history) return
  loading.history = true
  try {
    const result = await fetchNewsHistory(date)
    issue.value = result.issue || null
    history.value = result.history || []
    activeDate.value = result.issue?.date || date
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.history = false
  }
}

async function handleSaveConfig() {
  if (!isSuperadmin.value || loading.saveConfig) return
  loading.saveConfig = true
  try {
    const result = await saveNewsConfig(configPayload())
    applyConfig(result.config)
    ElMessage.success('资讯配置已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.saveConfig = false
  }
}

async function handleGenerateNews() {
  if (!isSuperadmin.value || loading.generate) return
  loading.generate = true
  try {
    const result = await generateNewsIssue(config.search_query, config.auto_search)
    issue.value = result.issue
    activeDate.value = result.issue.date
    const latest = await fetchNewsHistory()
    history.value = latest.history || []
    ElMessage.success('今日资讯已生成')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.generate = false
  }
}

onMounted(loadLatestNews)
</script>

<template>
  <section class="workspace-main news-main">
    <header class="news-page-head">
      <div class="news-title-block">
        <h1>每日资讯助手</h1>
        <p>查看轨道交通关键资讯，支持 AI 生成、配置来源与历史简报回看。</p>
      </div>
      <div class="news-page-actions">
        <div v-if="isSuperadmin" class="news-page-tabs" role="tablist" aria-label="每日资讯页面">
          <button :class="{ active: activePanel === 'reader' }" type="button" @click="switchPanel('reader')">资讯简报</button>
          <button :class="{ active: activePanel === 'config' }" type="button" @click="switchPanel('config')">资讯配置</button>
        </div>
        <button class="news-button news-button--ghost" type="button" :disabled="loading.latest" @click="loadLatestNews">
          <el-icon><Refresh /></el-icon>
          {{ loading.latest ? '刷新中' : '刷新' }}
        </button>
        <button
          v-if="isSuperadmin"
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
        <section class="news-card news-history-card">
          <div class="news-card-head">
            <span class="news-card-icon"><el-icon><Reading /></el-icon></span>
            <div>
              <h2>历史资讯</h2>
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
            <span>生成每日资讯后会在这里保留历史记录。</span>
          </div>
        </section>
      </aside>

      <main class="news-reader-column">
        <article v-if="activePanel === 'reader'" class="news-card news-issue-card" :class="{ 'is-loading': loading.latest || loading.history }">
          <div class="news-issue-head">
            <div>
              <span class="news-issue-label">
                <el-icon><Document /></el-icon>
                今日简报
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

          <div v-if="issueErrors.length && isSuperadmin" class="news-warning">
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
                <div v-if="item.url" class="news-item-source-row">
                  <button type="button" @click="openSource(item.url)">
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
            <span>{{ isSuperadmin ? '可以配置资讯源后生成今日简报。' : '暂无今日简报，请稍后刷新。' }}</span>
          </div>
        </article>

        <article v-else class="news-card news-config-page">
          <div class="news-config-page-head">
            <div>
              <span class="news-date-pill">
                <el-icon><Setting /></el-icon>
                资讯配置
              </span>
              <h3>来源与自动生成配置</h3>
              <p>维护抓取网页、搜索关键词和每日自动更新规则。</p>
            </div>
            <span v-if="isSuperadmin && configLoaded" class="news-config-status">已读取</span>
          </div>

          <div v-if="!isSuperadmin" class="news-permission-card">
            <el-icon><WarningFilled /></el-icon>
            <strong>当前账号没有资讯配置权限</strong>
            <span>请使用超级管理员账号维护资讯来源、自动搜索和定时更新配置。</span>
          </div>

          <div v-else class="news-config-form news-config-form--page">
            <label class="news-field news-field--full">
              <span>搜索关键词</span>
              <textarea v-model="config.search_query" rows="3" placeholder="轨道交通 OR 城市轨道 OR 地铁 OR 智慧轨交"></textarea>
            </label>

            <div class="news-source-editor">
              <div class="news-source-title">
                <strong>资讯网页</strong>
                <button type="button" @click="addSource">
                  <el-icon><Plus /></el-icon>
                  新增网页
                </button>
              </div>
              <div class="news-source-list">
                <div v-for="(source, index) in config.sources" :key="index" class="news-source-row">
                  <label>
                    <span>名称</span>
                    <input v-model="source.name" type="text" placeholder="来源名称" />
                  </label>
                  <label>
                    <span>网址</span>
                    <input v-model="source.url" type="url" placeholder="https://example.com/news" />
                  </label>
                  <button class="news-source-remove" type="button" :aria-label="`删除第 ${index + 1} 个来源`" @click="removeSource(index)">
                    <el-icon><Delete /></el-icon>
                  </button>
                </div>
              </div>
            </div>

            <div class="news-config-grid">
              <div class="news-check-row">
                <label>
                  <input v-model="config.auto_search" type="checkbox" />
                  <span>允许大模型自动网络搜索</span>
                </label>
                <label>
                  <input v-model="config.auto_push" type="checkbox" />
                  <span>每日自动更新推送</span>
                </label>
              </div>

              <label class="news-field">
                <span>推送时间</span>
                <input v-model="config.push_time" type="time" />
              </label>
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
      </main>
    </div>
  </section>
</template>
