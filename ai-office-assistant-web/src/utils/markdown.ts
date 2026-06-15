import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/** 把 LLM 输出的 Markdown 渲染成净化后的 HTML（表格/列表/代码块/加粗等）。 */
export function renderMarkdown(text: string): string {
  const html = marked.parse(String(text || ''), { async: false }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
