<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatLineRound,
  CircleCheckFilled,
  Close,
  Delete,
  MagicStick,
  Plus,
  Refresh,
  Upload,
  View,
} from '@element-plus/icons-vue'
import {
  addForumComment,
  createForumAiComment,
  createForumAiTopic,
  createForumTopic,
  getForumTopic,
  listForumTopics,
  resourceUrl,
  toggleForumLike,
  type ForumAiTopicFile,
  type ForumComment,
  type ForumTopic,
} from '../../services/personalWorkApi'
import { authState } from '../../services/authSession'
import './index.scss'

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
const commentText = ref('')
const replyTarget = ref<ForumComment | null>(null)
const commentPage = ref(1)
const commentsCollapsed = ref(false)
const createOpen = ref(false)
const forumNotice = ref('')
const aiFiles = ref<File[]>([])
const commentInputRef = ref<HTMLTextAreaElement | null>(null)
const aiFileInputRef = ref<HTMLInputElement | null>(null)
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
})

const pageSize = 8

const sortedTopics = computed(() => {
  return [...topics.value].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
})
const selectedTopic = computed(() => detailTopic.value || topics.value.find((topic) => topic.id === selectedTopicId.value) || null)
const topicComments = computed(() => detailTopic.value?.comments || [])
// 评论按 parent_id 分组，顶层评论分页展示，二级回复跟随父评论展示。
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
const currentUserName = computed(() => authState.user?.name || authState.user?.username || '成员')
const currentUserAvatar = computed(() => (authState.user?.avatar_url ? resourceUrl(authState.user.avatar_url) : ''))
const currentUserInitial = computed(() => authorInitial(currentUserName.value))

function sourceName(source: string) {
  return source === 'ai' ? '智能体' : '成员发起'
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || '暂无时间'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function formatCommentTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || '暂无时间'
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

function authorInitial(author: string) {
  return author.trim().slice(0, 1) || '佚'
}

function isAiAuthor(author: string) {
  return /AI|智能|助手|潜水员/i.test(author)
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败'
}

function showNotice(message: string) {
  forumNotice.value = message
}

function closeNotice() {
  forumNotice.value = ''
}

async function refreshTopicList() {
  loading.list = true
  try {
    const result = await listForumTopics()
    topics.value = result.topics
    // 列表刷新后保持当前选中项，避免详情区和历史列表展示不同话题。
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
  commentsCollapsed.value = false
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
    createOpen.value = false
    selectedTopicId.value = result.topic.id
    detailTopic.value = result.topic
    showNotice('话题已发布')
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
  if (aiFileInputRef.value) aiFileInputRef.value.value = ''
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
    clearAiFiles()
    createOpen.value = false
    selectedTopicId.value = result.topic.id
    detailTopic.value = result.topic
    showNotice('智能话题已发布')
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
    commentsCollapsed.value = false
    showNotice('讨论已发布')
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
    commentsCollapsed.value = false
    showNotice('AI 评论已发布')
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

onMounted(loadInitialTopics)
</script>

<template>
  <section class="forum-main">
    <header class="forum-page-head">
      <h1>金点子论坛</h1>
      <p>围绕创意、改进和机会发起话题，团队成员一起讨论和沉淀观点。</p>
    </header>

    <section v-if="forumNotice" class="forum-notice" role="status">
      <span>
        <el-icon><CircleCheckFilled /></el-icon>
        {{ forumNotice }}
      </span>
      <button type="button" aria-label="关闭提示" @click="closeNotice">
        <el-icon><Close /></el-icon>
      </button>
    </section>

    <section class="forum-workspace">
      <section class="forum-card forum-topic-panel">
        <header class="forum-list-head">
          <div class="forum-list-title">
            <h2>全部历史话题</h2>
            <span>{{ sortedTopics.length }} 个话题</span>
          </div>
          <div class="forum-list-actions">
            <button type="button" class="forum-outline-button" @click="createOpen = !createOpen">
              <el-icon><Plus /></el-icon>
              {{ createOpen ? '收起发起' : '发起话题' }}
            </button>
            <button type="button" class="forum-ghost-button" :disabled="loading.list" @click="refreshTopicList">
              <el-icon><Refresh /></el-icon>
              刷新
            </button>
          </div>
        </header>

        <section v-if="createOpen" class="forum-create-drawer">
          <header class="forum-create-head">
            <h3>发起金点子话题</h3>
            <button type="button" aria-label="收起发起话题" @click="createOpen = false">
              <el-icon><Close /></el-icon>
            </button>
          </header>

          <div class="forum-create-block">
            <div class="forum-step-title">
              <span>1</span>
              <strong>手动发起话题</strong>
            </div>
            <label class="forum-field forum-field--line">
              <span>话题标题</span>
              <input v-model="createForm.title" maxlength="60" type="text" placeholder="输入一个清晰的标题，便于大家讨论和搜索" />
            </label>
            <label class="forum-field">
              <span>话题内容</span>
              <div class="forum-control">
                <textarea
                  v-model="createForm.body"
                  maxlength="1000"
                  placeholder="详细描述你的想法、问题或改进建议，越具体越有助于讨论..."
                ></textarea>
                <small>{{ createForm.body.length }} / 1000</small>
              </div>
            </label>
            <div class="forum-create-actions">
              <button type="button" class="forum-primary-button" :disabled="loading.create" @click="submitTopic">
                发布话题
              </button>
            </div>
          </div>

          <div class="forum-create-block forum-create-block--ai">
            <div class="forum-step-title">
              <span>2</span>
              <strong>智能体每日起题</strong>
            </div>
            <label class="forum-field">
              <span>输入信息</span>
              <div class="forum-control">
                <textarea
                  v-model="aiForm.seed"
                  maxlength="800"
                  placeholder="输入今天的工作背景、灵感、项目机会或想让大家讨论的方向..."
                ></textarea>
                <small>{{ aiForm.seed.length }} / 800</small>
              </div>
            </label>
            <label class="forum-field">
              <span>聊天内容</span>
              <div class="forum-control">
                <textarea
                  v-model="aiForm.chat"
                  maxlength="2000"
                  placeholder="可粘贴群聊、会议纪要、用户反馈等内容..."
                ></textarea>
                <small>{{ aiForm.chat.length }} / 2000</small>
              </div>
            </label>
            <div class="forum-field forum-field--line">
              <span>传入文档</span>
              <label class="forum-file-input">
                <input
                  ref="aiFileInputRef"
                  type="file"
                  multiple
                  accept=".txt,.md,.csv,.docx,.xlsx"
                  @change="updateAiFiles"
                />
                <em>
                  <el-icon><Upload /></el-icon>
                  {{ aiFiles.length ? `已选择 ${aiFiles.length} 个文件` : '点击或拖拽文件到此处上传（.txt / .md / .csv / .docx / .xlsx）' }}
                </em>
              </label>
            </div>
            <div v-if="aiFiles.length" class="forum-file-list">
              <span v-for="file in aiFiles" :key="file.name">{{ file.name }}</span>
              <button type="button" aria-label="清空上传文件" @click="clearAiFiles">
                <el-icon><Delete /></el-icon>
              </button>
            </div>
            <div class="forum-create-actions">
              <button type="button" class="forum-primary-button" :disabled="loading.aiTopic" @click="submitAiTopic">
                <el-icon><MagicStick /></el-icon>
                智能生成话题
              </button>
            </div>
          </div>
        </section>

        <div class="forum-topic-list">
          <button
            v-for="topic in sortedTopics"
            :key="topic.id"
            type="button"
            :class="['forum-topic-item', { active: topic.id === selectedTopicId }]"
            @click="openTopic(topic.id)"
          >
            <span class="forum-topic-row">
              <strong>{{ topic.title }}</strong>
              <em :class="['forum-source', topic.source === 'ai' ? 'ai' : 'user']">{{ sourceName(topic.source) }}</em>
            </span>
            <span class="forum-topic-meta">
              <span>{{ topic.author }}</span>
              <i></i>
              <time>{{ formatTime(topic.created_at) }}</time>
            </span>
            <span class="forum-topic-stats">
              <em title="热度">
                <svg class="forum-stat-icon forum-hot-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M8.6 1.5c.3 2.4 2.7 3.1 2.7 5.4 0 .9-.3 1.6-.8 2.2.1-1.5-.8-2.4-1.7-3.2-.8 1.5-3.1 2.2-3.1 4.6 0 2 1.5 3.5 3.7 3.5 2.6 0 4.5-1.8 4.5-4.7 0-3.3-3-5-5.3-7.8Z" />
                  <path d="M6.9 8.9c-.8.8-1.3 1.5-1.3 2.5 0 1.4 1.1 2.6 2.8 2.6 1.5 0 2.5-.9 2.5-2.2 0-1.1-.8-1.8-1.7-2.6-.2 1-.8 1.6-1.5 2-.1-.8-.4-1.5-.8-2.3Z" />
                </svg>
                {{ topic.heat }}
              </em>
              <em :class="{ liked: topic.liked }" title="点赞">
                <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    v-if="topic.liked"
                    d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z"
                  />
                  <path v-if="topic.liked" d="M2.3 6.8h2v6h-2z" />
                  <path
                    v-else
                    d="M5.5 6.5 7.6 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.4c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.5V6.5Zm-3.2.2h2v6h-2v-6Z"
                    fill="none"
                    stroke="currentColor"
                    stroke-linejoin="round"
                    stroke-width="1.3"
                  />
                </svg>
                {{ topic.like_count }}
              </em>
              <em title="评论"><el-icon><ChatLineRound /></el-icon>{{ topic.comment_count }}</em>
              <em title="浏览"><el-icon><View /></el-icon>{{ topic.view_count }}</em>
            </span>
          </button>
          <div v-if="!sortedTopics.length && !loading.list" class="forum-empty-state forum-empty-state--topics">
            <span class="forum-empty-art forum-empty-art--topic">
              <i></i>
              <b></b>
            </span>
            <strong>暂无话题，先发起一个金点子吧</strong>
            <p>分享你的创意或改进建议，和团队一起讨论并沉淀有价值的观点。</p>
            <div>
              <button type="button" class="forum-primary-button" @click="createOpen = true">
                <el-icon><Plus /></el-icon>
                发起话题
              </button>
              <button type="button" class="forum-outline-button" @click="createOpen = true">
                <el-icon><MagicStick /></el-icon>
                智能体每日起题
              </button>
            </div>
          </div>
          <div v-if="loading.list" class="forum-empty">正在加载话题...</div>
        </div>
      </section>

      <section class="forum-card forum-detail-panel">
        <template v-if="selectedTopic">
          <header class="forum-detail-head">
            <div>
              <h2>{{ selectedTopic.title }}</h2>
            </div>
            <button
              type="button"
              :class="['forum-like-cta', { liked: selectedTopic.liked }]"
              :disabled="loading.like"
              @click="likeTopic"
            >
              <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  v-if="selectedTopic.liked"
                  d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z"
                />
                <path v-if="selectedTopic.liked" d="M2.3 6.8h2v6h-2z" />
                <path
                  v-else
                  d="M5.5 6.5 7.6 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.4c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.5V6.5Zm-3.2.2h2v6h-2v-6Z"
                  fill="none"
                  stroke="currentColor"
                  stroke-linejoin="round"
                  stroke-width="1.3"
                />
              </svg>
              点赞
            </button>
          </header>

          <div class="forum-detail-scroll">
            <div class="forum-detail-meta">
              <span>来源：<em :class="['forum-source', selectedTopic.source === 'ai' ? 'ai' : 'user']">{{ sourceName(selectedTopic.source) }}</em></span>
              <span>作者：{{ selectedTopic.author }}</span>
              <span>创建时间：{{ formatTime(selectedTopic.created_at) }}</span>
              <span>
                <svg class="forum-stat-icon forum-hot-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path d="M8.6 1.5c.3 2.4 2.7 3.1 2.7 5.4 0 .9-.3 1.6-.8 2.2.1-1.5-.8-2.4-1.7-3.2-.8 1.5-3.1 2.2-3.1 4.6 0 2 1.5 3.5 3.7 3.5 2.6 0 4.5-1.8 4.5-4.7 0-3.3-3-5-5.3-7.8Z" />
                </svg>
                热度 {{ selectedTopic.heat }}
              </span>
              <span :class="{ liked: selectedTopic.liked }">
                <svg class="forum-stat-icon forum-like-icon" viewBox="0 0 16 16" aria-hidden="true">
                  <path
                    v-if="selectedTopic.liked"
                    d="M5.6 6.6 7.7 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.3c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.6V6.6Z"
                  />
                  <path v-if="selectedTopic.liked" d="M2.3 6.8h2v6h-2z" />
                  <path
                    v-else
                    d="M5.5 6.5 7.6 2c.3-.6 1.2-.5 1.3.2l.2 2.6h3.4c.8 0 1.4.7 1.2 1.5l-1 5.4c-.1.7-.7 1.2-1.4 1.2H5.5V6.5Zm-3.2.2h2v6h-2v-6Z"
                    fill="none"
                    stroke="currentColor"
                    stroke-linejoin="round"
                    stroke-width="1.3"
                  />
                </svg>
                {{ selectedTopic.like_count }}
              </span>
              <span><el-icon><ChatLineRound /></el-icon>{{ selectedTopic.comment_count }}</span>
              <span><el-icon><View /></el-icon>{{ selectedTopic.view_count }}</span>
            </div>

            <article class="forum-detail-body">{{ selectedTopic.body }}</article>

            <section class="forum-discussion">
              <header class="forum-discussion-head">
                <h3>讨论区 <span>（{{ topicComments.length }} 条评论）</span></h3>
                <div class="forum-discussion-tools">
                  <span v-if="loading.aiComment" class="forum-ai-reading">
                    <i></i>
                    AI 潜水员正在读帖...
                  </span>
                  <button type="button" class="forum-collapse-button" @click="commentsCollapsed = !commentsCollapsed">
                    {{ commentsCollapsed ? '展开评论' : '收起评论' }}
                    <span>{{ commentsCollapsed ? '⌄' : '⌃' }}</span>
                  </button>
                </div>
              </header>

              <div v-if="commentsCollapsed" class="forum-comments-collapsed">评论已收起，展开后查看讨论内容。</div>
              <div v-else class="forum-comment-list">
                <template v-if="pagedComments.length">
                  <article
                    v-for="comment in pagedComments"
                    :key="comment.id"
                    :class="['forum-comment', { 'forum-comment--ai': isAiAuthor(comment.author) }]"
                  >
                    <span class="forum-avatar">{{ isAiAuthor(comment.author) ? 'AI' : authorInitial(comment.author) }}</span>
                    <div class="forum-comment-body">
                      <header>
                        <strong>{{ comment.author }}</strong>
                      </header>
                      <p>{{ comment.content }}</p>
                      <footer class="forum-comment-footer">
                        <time>{{ formatCommentTime(comment.created_at) }}</time>
                        <button type="button" @click="replyTo(comment)">
                          <el-icon><ChatLineRound /></el-icon>
                          回复
                        </button>
                      </footer>

                      <article
                        v-for="child in commentsByParent[comment.id] || []"
                        :key="child.id"
                        :class="['forum-comment forum-comment--reply', { 'forum-comment--ai': isAiAuthor(child.author) }]"
                      >
                        <span class="forum-avatar">{{ isAiAuthor(child.author) ? 'AI' : authorInitial(child.author) }}</span>
                        <div class="forum-comment-body">
                          <header>
                            <strong>{{ child.author }}</strong>
                          </header>
                          <p>{{ child.content }}</p>
                          <footer class="forum-comment-footer">
                            <time>{{ formatCommentTime(child.created_at) }}</time>
                            <button type="button" @click="replyTo(child)">
                              <el-icon><ChatLineRound /></el-icon>
                              回复
                            </button>
                          </footer>
                        </div>
                      </article>
                    </div>
                  </article>
                </template>
                <article v-if="loading.aiComment" class="forum-comment forum-comment--pending forum-comment--ai">
                  <span class="forum-avatar">AI</span>
                  <div class="forum-comment-body">
                    <header>
                      <strong>AI 潜水员</strong>
                      <time>正在回复</time>
                    </header>
                    <p>正在阅读话题和已有讨论，整理一条可继续推进的评论。</p>
                  </div>
                </article>
                <div v-if="!pagedComments.length && !loading.detail && !loading.aiComment" class="forum-empty-state forum-empty-state--discussion">
                  <span class="forum-empty-art forum-empty-art--chat">
                    <i></i>
                    <b></b>
                  </span>
                  <strong>还没有讨论，来发表第一个观点吧</strong>
                </div>
                <div v-if="loading.detail" class="forum-empty">正在读取话题详情...</div>
              </div>
            </section>
          </div>

          <section class="forum-comment-composer">
            <span class="forum-avatar forum-avatar--me" :title="currentUserName">
              <img v-if="currentUserAvatar" :src="currentUserAvatar" :alt="currentUserName" />
              <template v-else>{{ currentUserInitial }}</template>
            </span>
            <div class="forum-composer-main">
              <div v-if="replyTarget" class="forum-reply-pill">
                正在回复 {{ replyTarget.author }}
                <button type="button" @click="cancelReply">取消</button>
              </div>
              <textarea
                ref="commentInputRef"
                v-model="commentText"
                maxlength="500"
                placeholder="写下你的观点、建议、经验或提出下一步行动..."
              ></textarea>
            </div>
            <div class="forum-composer-actions">
              <button class="forum-primary-button" type="button" :disabled="!canSubmitComment" @click="submitComment">
                发布讨论
              </button>
              <button class="forum-outline-button forum-ai-comment-button" type="button" :disabled="loading.aiComment || loading.detail" @click="submitAiComment">
                <el-icon><MagicStick /></el-icon>
                {{ loading.aiComment ? 'AI 正在评论' : 'AI 潜水评论' }}
              </button>
            </div>
          </section>

          <footer v-if="!commentsCollapsed" class="forum-pagination">
            <button type="button" :disabled="commentPage <= 1" @click="changeCommentPage(-1)">‹ 上一页</button>
            <span>第 {{ commentPage }} / {{ totalCommentPages }} 页 · 共 {{ topicComments.length }} 条评论</span>
            <button type="button" :disabled="commentPage >= totalCommentPages" @click="changeCommentPage(1)">下一页 ›</button>
          </footer>
        </template>

        <div v-else class="forum-empty-state forum-empty-state--large">
          <span class="forum-empty-art forum-empty-art--search">
            <i></i>
            <b></b>
          </span>
          <strong>选择一个话题查看详情和讨论</strong>
          <p>点击左侧的话题，查看详细内容并参与讨论；或者发起你的第一个金点子，开启团队共创。</p>
        </div>
      </section>
    </section>
  </section>
</template>
