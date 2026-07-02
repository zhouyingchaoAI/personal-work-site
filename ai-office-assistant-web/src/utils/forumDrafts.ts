export interface ForumCreateDraft {
  title: string
  body: string
  preset: string
}

export interface ForumAiDraft {
  seed: string
  chat: string
}

export interface ForumCommentDraft {
  text: string
  status: string
  replyToId: string
  replyToAuthor: string
}

const CREATE_DRAFT_KEY = 'forum-draft:create'
const AI_DRAFT_KEY = 'forum-draft:ai'
const commentDraftKey = (topicId: string) => `forum-draft:comment:${topicId}`

const EMPTY_CREATE_DRAFT: ForumCreateDraft = { title: '', body: '', preset: '' }
const EMPTY_AI_DRAFT: ForumAiDraft = { seed: '', chat: '' }
const EMPTY_COMMENT_DRAFT: ForumCommentDraft = { text: '', status: '', replyToId: '', replyToAuthor: '' }

function storageAvailable() {
  return typeof window !== 'undefined' && !!window.localStorage
}

function readJson<T>(key: string, fallback: T): T {
  if (!storageAvailable()) return fallback
  try {
    const value = window.localStorage.getItem(key)
    return value ? { ...fallback, ...JSON.parse(value) } : fallback
  } catch {
    return fallback
  }
}

function writeJson<T>(key: string, value: T) {
  if (!storageAvailable()) return
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Ignore quota or privacy-mode failures; draft saving is best effort.
  }
}

function removeKey(key: string) {
  if (!storageAvailable()) return
  try {
    window.localStorage.removeItem(key)
  } catch {
    // Ignore storage failures.
  }
}

export function loadForumCreateDraft(): ForumCreateDraft {
  return readJson(CREATE_DRAFT_KEY, EMPTY_CREATE_DRAFT)
}

export function hasForumCreateDraft() {
  const draft = loadForumCreateDraft()
  return !!(draft.title.trim() || draft.body.trim() || draft.preset)
}

export function saveForumCreateDraft(draft: ForumCreateDraft) {
  if (draft.title.trim() || draft.body.trim() || draft.preset) {
    writeJson(CREATE_DRAFT_KEY, draft)
  } else {
    clearForumCreateDraft()
  }
}

export function clearForumCreateDraft() {
  removeKey(CREATE_DRAFT_KEY)
}

export function loadForumAiDraft(): ForumAiDraft {
  return readJson(AI_DRAFT_KEY, EMPTY_AI_DRAFT)
}

export function hasForumAiDraft() {
  const draft = loadForumAiDraft()
  return !!(draft.seed.trim() || draft.chat.trim())
}

export function saveForumAiDraft(draft: ForumAiDraft) {
  if (draft.seed.trim() || draft.chat.trim()) {
    writeJson(AI_DRAFT_KEY, draft)
  } else {
    clearForumAiDraft()
  }
}

export function clearForumAiDraft() {
  removeKey(AI_DRAFT_KEY)
}

export function loadForumCommentDraft(topicId: string): ForumCommentDraft {
  if (!topicId) return EMPTY_COMMENT_DRAFT
  return readJson(commentDraftKey(topicId), EMPTY_COMMENT_DRAFT)
}

export function saveForumCommentDraft(topicId: string, draft: ForumCommentDraft) {
  if (!topicId) return
  if (draft.text.trim() || draft.status || draft.replyToId) {
    writeJson(commentDraftKey(topicId), draft)
  } else {
    clearForumCommentDraft(topicId)
  }
}

export function clearForumCommentDraft(topicId: string) {
  if (!topicId) return
  removeKey(commentDraftKey(topicId))
}
