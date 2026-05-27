<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  ChatLineRound,
  CollectionTag,
  Delete,
  EditPen,
  MagicStick,
  MoreFilled,
  Paperclip,
  Plus,
  Promotion,
  Search,
  Share,
  Star,
  Upload,
  UserFilled,
  View,
} from '@element-plus/icons-vue'
import AssistantChat from '../../components/AssistantChat/index.vue'
import {
  addForumComment,
  agentChat,
  createForumAiComment,
  createForumAiTopic,
  createForumTopic,
  getForumTopic,
  listForumTopics,
  resourceUrl,
  toggleForumLike,
  type AgentMessage,
  type ForumAiTopicFile,
  type ForumComment,
  type ForumTopic,
} from '../../services/personalWorkApi'
import './index.scss'

type ForumSortMode = 'updated' | 'heat' | 'comments'

interface ForumCreateForm {
  title: string
  body: string
}

interface ForumAiForm {
  seed: string
  chat: string
}

const topics = ref<ForumTopic[]>([])
const selectedTopicId = ref('')
const detailTopic = ref<ForumTopic | null>(null)
const keyword = ref('')
const sortMode = ref<ForumSortMode>('updated')
const commentText = ref('')
const replyTarget = ref<ForumComment | null>(null)
const commentPage = ref(1)
const aiFiles = ref<File[]>([])
const assistantOpen = ref(false)
const assistantInput = ref('')
const assistantMessages = ref<AgentMessage[]>([
  {
    role: 'assistant',
    content: '你好，我可以帮你提炼话题、整理讨论观点，或根据当前话题补充一条自然评论。',
  },
])
const commentInputRef = ref<HTMLTextAreaElement | null>(null)
const createForm = reactive<ForumCreateForm>({ title: '', body: '' })
const aiForm = reactive<ForumAiForm>({ seed: '', chat: '' })
const loading = reactive({
  list: false,
  detail: false,
  create: false,
  aiTopic: false,
  comment: false,
  aiComment: false,
  like: false,
  assistant: false,
})

const assistantAvatar = resourceUrl('/assets/ai-assistant-avatar.png')
const assistantQuickActions = ['帮我总结当前话题', '补充一个可落地建议', '提炼争议点']
const participantAvatars = ['张', '李', '王', '赵', '陈']
const pageSize = 8

const filteredTopics = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const filtered = text
    ? topics.value.filter((topic) => {
        return [topic.title, topic.body, topic.author].some((value) => value.toLowerCase().includes(text))
      })
    : [...topics.value]
  return filtered.sort((a, b) => {
    if (sortMode.value === 'heat') return b.heat - a.heat
    if (sortMode.value === 'comments') return b.comment_count - a.comment_count
    return b.updated_at.localeCompare(a.updated_at)
  })
})

const selectedTopic = computed(() => detailTopic.value || topics.value.find((topic) => topic.id === selectedTopicId.value) || null)
const topicComments = computed(() => detailTopic.value?.comments || [])
// 评论按 parent_id 分组，详情区只分页顶层评论并保留二级回复。
const commentsByParent = computed(() => {
  return topicComments.value.reduce<Record<string, ForumComment[]>>((groups, comment) => {
    const key = comment.parent_id || ''
    if (!groups[key]) groups[key] = []
    groups[key].push(comment)
    return groups
  }, {})
})
const topComments = computed(() => commentsByParent.value[''] || [])
const totalCommentPages = computed(() => Math.max(1, Math.ceil(topComments.value.length / pageSize)))
const pagedComments = computed(() => topComments.value.slice((commentPage.value - 1) * pageSize, commentPage.value * pageSize))
const canSubmitComment = computed(() => !!selectedTopic.value && !!commentText.value.trim() && !loading.comment)

function sourceName(source: string) {
  return source === 'ai' ? '灵感起题' : '成员发起'
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || '暂无时间'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function topicPreview(topic: ForumTopic) {
  const text = topic.body.trim()
  return text.length > 80 ? `${text.slice(0, 80)}...` : text || '暂无话题说明'
}

function authorInitial(author: string) {
  return author.trim().slice(0, 1) || '佚'
}

function showStaticFeature(label: string) {
  ElMessage.info(`${label}暂未接入`)
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

async function refreshTopicList() {
  loading.list = true
  try {
    const result = await listForumTopics()
    topics.value = result.topics
    if (selectedTopicId.value && !result.topics.some((topic) => topic.id === selectedTopicId.value)) {
      selectedTopicId.value = result.topics[0]?.id || ''
      detailTopic.value = null
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.list = false
  }
}

async function openTopic(id: string) {
  selectedTopicId.value = id
  commentPage.value = 1
  replyTarget.value = null
  loading.detail = true
  try {
    const result = await getForumTopic(id)
    detailTopic.value = result.topic
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.detail = false
  }
}

async function loadInitialTopics() {
  await refreshTopicList()
  if (topics.value[0]) {
    await openTopic(topics.value[0].id)
  }
}

async function submitTopic() {
  const title = createForm.title.trim()
  const body = createForm.body.trim()
  if (!title) {
    ElMessage.warning('请填写话题标题')
    return
  }
  if (!body) {
    ElMessage.warning('请填写话题内容')
    return
  }
  loading.create = true
  try {
    const result = await createForumTopic(title, body)
    createForm.title = ''
    createForm.body = ''
    selectedTopicId.value = result.topic.id
    detailTopic.value = result.topic
    ElMessage.success('话题已发布')
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.create = false
  }
}

function updateAiFiles(event: Event) {
  aiFiles.value = Array.from((event.target as HTMLInputElement).files || [])
}

function clearAiFiles() {
  aiFiles.value = []
}

// 上传文件需转为 base64，后端会按文件类型提取文本。
function readFileAsBase64(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '')
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

async function submitAiTopic() {
  if (!aiForm.seed.trim() && !aiForm.chat.trim() && !aiFiles.value.length) {
    ElMessage.warning('请填写灵感信息、聊天内容，或上传参考文档')
    return
  }
  loading.aiTopic = true
  try {
    const files: ForumAiTopicFile[] = []
    for (const file of aiFiles.value) {
      files.push({ name: file.name, data: await readFileAsBase64(file) })
    }
    const result = await createForumAiTopic(aiForm.seed, aiForm.chat, files)
    aiForm.seed = ''
    aiForm.chat = ''
    aiFiles.value = []
    selectedTopicId.value = result.topic.id
    detailTopic.value = result.topic
    ElMessage.success('话题建议已发布')
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.aiTopic = false
  }
}

async function submitComment() {
  if (!selectedTopic.value) return
  const content = commentText.value.trim()
  if (!content) {
    ElMessage.warning('请先填写讨论内容')
    return
  }
  loading.comment = true
  try {
    const result = await addForumComment(selectedTopic.value.id, content, replyTarget.value?.id || '')
    detailTopic.value = result.topic
    commentText.value = ''
    replyTarget.value = null
    commentPage.value = totalCommentPages.value
    ElMessage.success('讨论已发布')
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.comment = false
  }
}

async function likeTopic() {
  if (!selectedTopic.value) return
  loading.like = true
  try {
    const result = await toggleForumLike(selectedTopic.value.id)
    detailTopic.value = result.topic
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.like = false
  }
}

async function submitAiComment() {
  if (!selectedTopic.value) return
  loading.aiComment = true
  try {
    const result = await createForumAiComment(selectedTopic.value.id)
    detailTopic.value = result.topic
    ElMessage.success('评论建议已发布')
    await refreshTopicList()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.aiComment = false
  }
}

async function replyTo(comment: ForumComment) {
  replyTarget.value = comment
  if (!commentText.value.trim()) {
    commentText.value = `回复 ${comment.author}：`
  }
  await nextTick()
  commentInputRef.value?.focus()
}

function cancelReply() {
  replyTarget.value = null
}

function changeCommentPage(delta: number) {
  commentPage.value = Math.min(totalCommentPages.value, Math.max(1, commentPage.value + delta))
}

async function sendAssistant(value?: string) {
  const content = (value || assistantInput.value).trim()
  if (!content || loading.assistant) return
  assistantMessages.value.push({ role: 'user', content })
  assistantInput.value = ''
  loading.assistant = true
  try {
    const messages = assistantMessages.value.slice(-8)
    const topic = selectedTopic.value
    if (topic) {
      const last = messages[messages.length - 1]
      messages[messages.length - 1] = {
        ...last,
        content: `${last.content}\n\n当前话题：${topic.title}\n话题内容：${topic.body}`,
      }
    }
    const result = await agentChat('forum', messages)
    assistantMessages.value.push({ role: 'assistant', content: result.reply || result.error || '我已经处理完了。' })
    await refreshTopicList()
  } catch (error) {
    assistantMessages.value.push({ role: 'assistant', content: errorMessage(error) })
  } finally {
    loading.assistant = false
  }
}

onMounted(loadInitialTopics)
</script>

<template>
  <section class="forum-main">
    <header class="forum-page-title">
      <h2>金点子论坛</h2>
    </header>

    <section class="forum-workspace">
      <section class="forum-card forum-topic-panel">
        <header class="forum-tabs">
          <button class="active" type="button">话题池</button>
          <button type="button" @click="showStaticFeature('我的关注')">我的关注</button>
        </header>

        <label class="forum-search">
          <el-icon><Search /></el-icon>
          <input v-model="keyword" type="search" placeholder="搜索话题标题或内容" />
        </label>

        <div class="forum-filter-row">
          <button type="button" :class="{ active: sortMode === 'updated' }" @click="sortMode = 'updated'">最新</button>
          <button type="button" :class="{ active: sortMode === 'heat' }" @click="sortMode = 'heat'">热门</button>
          <button type="button" :class="{ active: sortMode === 'comments' }" @click="sortMode = 'comments'">讨论</button>
          <button type="button" @click="showStaticFeature('待处理')">待处理</button>
          <button type="button" @click="showStaticFeature('已采纳')">已采纳</button>
        </div>

        <div class="forum-topic-list">
          <button
            v-for="topic in filteredTopics"
            :key="topic.id"
            type="button"
            :class="['forum-topic-item', { active: topic.id === selectedTopicId }]"
            @click="openTopic(topic.id)"
          >
            <span class="forum-topic-tags">
              <span :class="['forum-source', topic.source === 'ai' ? 'ai' : 'user']">{{ sourceName(topic.source) }}</span>
              <em v-if="topic.heat >= 20" class="forum-hot-chip">
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M8.6 1.5c.3 2.4 2.7 3.1 2.7 5.4 0 .9-.3 1.6-.8 2.2.1-1.5-.8-2.4-1.7-3.2-.8 1.5-3.1 2.2-3.1 4.6 0 2 1.5 3.5 3.7 3.5 2.6 0 4.5-1.8 4.5-4.7 0-3.3-3-5-5.3-7.8Z" />
                  <path d="M6.9 8.9c-.8.8-1.3 1.5-1.3 2.5 0 1.4 1.1 2.6 2.8 2.6 1.5 0 2.5-.9 2.5-2.2 0-1.1-.8-1.8-1.7-2.6-.2 1-.8 1.6-1.5 2-.1-.8-.4-1.5-.8-2.3Z" />
                </svg>
                热门
              </em>
            </span>
            <strong>{{ topic.title }}</strong>
            <p>{{ topicPreview(topic) }}</p>
            <span class="forum-topic-foot">
              <span class="forum-author">
                <i>{{ authorInitial(topic.author) }}</i>
                {{ topic.author }}
              </span>
              <time>{{ formatTime(topic.updated_at || topic.created_at) }}</time>
            </span>
            <span class="forum-topic-stats">
              <em title="热度">
                <svg class="forum-stat-icon forum-hot-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M8.6 1.5c.3 2.4 2.7 3.1 2.7 5.4 0 .9-.3 1.6-.8 2.2.1-1.5-.8-2.4-1.7-3.2-.8 1.5-3.1 2.2-3.1 4.6 0 2 1.5 3.5 3.7 3.5 2.6 0 4.5-1.8 4.5-4.7 0-3.3-3-5-5.3-7.8Z" />
                  <path d="M6.9 8.9c-.8.8-1.3 1.5-1.3 2.5 0 1.4 1.1 2.6 2.8 2.6 1.5 0 2.5-.9 2.5-2.2 0-1.1-.8-1.8-1.7-2.6-.2 1-.8 1.6-1.5 2-.1-.8-.4-1.5-.8-2.3Z" />
                </svg>
                {{ topic.heat }}
              </em>
              <em :class="{ liked: topic.liked }" :title="topic.liked ? '已点赞' : '未点赞'">
                <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z" />
                  <path d="M2.3 6.8h2v6h-2z" />
                </svg>
                {{ topic.like_count }}
              </em>
              <em title="评论"><el-icon><ChatLineRound /></el-icon>{{ topic.comment_count }}</em>
              <em title="浏览"><el-icon><View /></el-icon>{{ topic.view_count }}</em>
            </span>
          </button>
          <div v-if="!filteredTopics.length && !loading.list" class="forum-empty">暂无匹配话题。</div>
          <div v-if="loading.list" class="forum-empty">正在加载话题...</div>
        </div>
      </section>

      <section class="forum-card forum-detail-panel">
        <template v-if="selectedTopic">
          <header class="forum-detail-top">
            <div>
              <button class="forum-follow-button" type="button" @click="showStaticFeature('关注讨论')">关注讨论</button>
              <button class="forum-icon-button" type="button" @click="showStaticFeature('更多操作')">
                <el-icon><MoreFilled /></el-icon>
              </button>
            </div>
          </header>

          <article class="forum-detail-content">
            <span class="forum-topic-tags">
              <span :class="['forum-source', selectedTopic.source === 'ai' ? 'ai' : 'user']">
                {{ sourceName(selectedTopic.source) }}
              </span>
              <em v-if="selectedTopic.heat >= 20" class="forum-hot-chip">
                <svg viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M8.6 1.5c.3 2.4 2.7 3.1 2.7 5.4 0 .9-.3 1.6-.8 2.2.1-1.5-.8-2.4-1.7-3.2-.8 1.5-3.1 2.2-3.1 4.6 0 2 1.5 3.5 3.7 3.5 2.6 0 4.5-1.8 4.5-4.7 0-3.3-3-5-5.3-7.8Z" />
                  <path d="M6.9 8.9c-.8.8-1.3 1.5-1.3 2.5 0 1.4 1.1 2.6 2.8 2.6 1.5 0 2.5-.9 2.5-2.2 0-1.1-.8-1.8-1.7-2.6-.2 1-.8 1.6-1.5 2-.1-.8-.4-1.5-.8-2.3Z" />
                </svg>
                热门
              </em>
            </span>
            <h3>{{ selectedTopic.title }}</h3>
            <p class="forum-detail-meta">
              {{ selectedTopic.author }} · {{ formatTime(selectedTopic.created_at) }}
              <span><el-icon><View /></el-icon>{{ selectedTopic.view_count }} 次浏览</span>
            </p>
            <p class="forum-topic-body">{{ selectedTopic.body }}</p>
          </article>

          <section class="forum-topic-actionbar">
            <button
              type="button"
              :class="['forum-like-button', { liked: selectedTopic.liked }]"
              :disabled="loading.like"
              @click="likeTopic"
            >
              <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z" />
                <path d="M2.3 6.8h2v6h-2z" />
              </svg>
              {{ selectedTopic.like_count }}
            </button>
            <button type="button" @click="showStaticFeature('收藏')">
              <el-icon><Star /></el-icon>
              收藏
            </button>
            <button type="button" @click="showStaticFeature('分享')">
              <el-icon><Share /></el-icon>
              分享
            </button>
            <span class="forum-active-users">
              正在讨论 {{ Math.min(8, Math.max(1, topicComments.length + 1)) }} 人
              <span>
                <i v-for="avatar in participantAvatars" :key="avatar">{{ avatar }}</i>
                <b>+5</b>
              </span>
            </span>
          </section>

          <section class="forum-comment-section">
            <div class="forum-section-title">
              <div>
                <h4>讨论（{{ topicComments.length }}）</h4>
              </div>
              <div class="forum-section-actions">
                <button type="button" :disabled="loading.aiComment || loading.detail" @click="submitAiComment">
                  <el-icon><ChatDotRound /></el-icon>
                  辅助评论
                </button>
                <button type="button" @click="showStaticFeature('评论排序')">按时间</button>
              </div>
            </div>

            <div class="forum-comment-list">
              <article v-for="(comment, index) in pagedComments" :key="comment.id" class="forum-comment">
                <span class="forum-avatar">{{ authorInitial(comment.author) }}</span>
                <div class="forum-comment-body">
                  <header>
                    <strong>{{ comment.author }}</strong>
                    <time>{{ formatTime(comment.created_at) }}</time>
                    <button v-if="index === 0" type="button" @click="showStaticFeature('置顶评论')">置顶</button>
                  </header>
                  <p>{{ comment.content }}</p>
                  <div class="forum-comment-actions">
                    <button type="button" @click="showStaticFeature('评论点赞')">
                      <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                        <path d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z" />
                        <path d="M2.3 6.8h2v6h-2z" />
                      </svg>
                      {{ 6 + index }}
                    </button>
                    <button type="button" @click="replyTo(comment)">
                      <el-icon><EditPen /></el-icon>
                      回复
                    </button>
                    <button type="button" @click="showStaticFeature('更多评论操作')">
                      <el-icon><MoreFilled /></el-icon>
                    </button>
                  </div>

                  <article
                    v-for="child in commentsByParent[comment.id] || []"
                    :key="child.id"
                    class="forum-comment forum-comment--reply"
                  >
                    <span class="forum-avatar">{{ authorInitial(child.author) }}</span>
                    <div class="forum-comment-body">
                      <header>
                        <strong>{{ child.author }}</strong>
                        <time>{{ formatTime(child.created_at) }}</time>
                      </header>
                      <p>{{ child.content }}</p>
                    </div>
                  </article>
                </div>
              </article>
              <div v-if="!pagedComments.length && !loading.detail" class="forum-empty">还没有讨论，来写第一条观点。</div>
              <div v-if="loading.detail" class="forum-empty">正在读取话题详情...</div>
            </div>

            <div class="forum-pagination" v-if="topComments.length > pageSize">
              <button type="button" :disabled="commentPage <= 1" @click="changeCommentPage(-1)">上一页</button>
              <span>第 {{ commentPage }} / {{ totalCommentPages }} 页</span>
              <button type="button" :disabled="commentPage >= totalCommentPages" @click="changeCommentPage(1)">下一页</button>
            </div>
          </section>

          <section class="forum-comment-composer">
            <div v-if="replyTarget" class="forum-reply-pill">
              回复 {{ replyTarget.author }}
              <button type="button" @click="cancelReply">取消</button>
            </div>
            <textarea
              ref="commentInputRef"
              v-model="commentText"
              maxlength="500"
              placeholder="发表你的观点、@同事，输入 / 快捷插入"
            ></textarea>
            <div class="forum-composer-bar">
              <div>
                <button type="button" @click="showStaticFeature('同事提及')">
                  <el-icon><UserFilled /></el-icon>
                  同事
                </button>
                <button type="button" @click="showStaticFeature('上传附件')">
                  <el-icon><Paperclip /></el-icon>
                  上传附件
                </button>
                <button type="button" @click="showStaticFeature('表情')">表情</button>
              </div>
              <div>
                <button type="button" @click="showStaticFeature('AI 帮我润色')">
                  <el-icon><MagicStick /></el-icon>
                  AI 帮我润色
                </button>
                <button class="primary" type="button" :disabled="!canSubmitComment" @click="submitComment">发布讨论</button>
              </div>
            </div>
          </section>
        </template>

        <div v-else class="forum-empty forum-empty--large">选择一个话题查看详情和讨论。</div>
      </section>

      <aside class="forum-side-panel">
        <section class="forum-card forum-create-card">
          <header class="forum-side-title">
            <span><el-icon><EditPen /></el-icon></span>
            <h3>发起话题</h3>
          </header>
          <label>
            <input v-model="createForm.title" maxlength="60" type="text" placeholder="输入话题标题（10-60字）" />
          </label>
          <label>
            <textarea v-model="createForm.body" maxlength="500" placeholder="详细描述问题背景、现状和希望解决的方向"></textarea>
            <small>{{ createForm.body.length }}/500</small>
          </label>
          <button type="button" :disabled="loading.create" @click="submitTopic">
            <el-icon><Plus /></el-icon>
            发布话题
          </button>
        </section>

        <section class="forum-card forum-ai-card">
          <header class="forum-side-title">
            <span><el-icon><MagicStick /></el-icon></span>
            <h3>AI 灵感起题</h3>
          </header>
          <textarea v-model="aiForm.seed" placeholder="输入你的工作场景或遇到的问题"></textarea>
          <textarea v-model="aiForm.chat" placeholder="可粘贴群聊、会议纪要或用户反馈"></textarea>
          <label class="forum-file-input">
            <input type="file" multiple accept=".txt,.md,.csv,.docx,.xlsx" @change="updateAiFiles" />
            <span>
              <el-icon><Upload /></el-icon>
              {{ aiFiles.length ? `已选择 ${aiFiles.length} 个文件` : '上传参考文档（选填）' }}
            </span>
          </label>
          <div v-if="aiFiles.length" class="forum-file-list">
            <span v-for="file in aiFiles" :key="file.name">{{ file.name }}</span>
            <button type="button" @click="clearAiFiles">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
          <button type="button" :disabled="loading.aiTopic" @click="submitAiTopic">
            <el-icon><MagicStick /></el-icon>
            生成讨论建议
          </button>
        </section>

        <section class="forum-card forum-assistant-card">
          <header class="forum-assistant-title">
            <span><el-icon><ChatDotRound /></el-icon></span>
            <div>
              <h3>讨论助手</h3>
              <p>AI 帮你提炼发散参与讨论</p>
            </div>
          </header>
          <button type="button" @click="sendAssistant('帮我总结当前话题')">
            <el-icon><CollectionTag /></el-icon>
            帮我总结当前话题
          </button>
          <button type="button" @click="sendAssistant('补充一个可落地建议')">
            <el-icon><Promotion /></el-icon>
            补充一个可落地建议
          </button>
          <button type="button" @click="sendAssistant('提炼争议点')">
            <el-icon><ChatLineRound /></el-icon>
            提炼争议点
          </button>
          <button class="forum-outline-primary" type="button" @click="assistantOpen = true">打开讨论助手</button>
        </section>
      </aside>
    </section>

    <AssistantChat
      v-model:open="assistantOpen"
      v-model:input="assistantInput"
      :avatar="assistantAvatar"
      title="犇犇"
      :messages="assistantMessages"
      :quick-actions="assistantQuickActions"
      :loading="loading.assistant"
      @send="sendAssistant"
    />
  </section>
</template>
