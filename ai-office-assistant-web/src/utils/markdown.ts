import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/** 把 LLM 输出的 Markdown 渲染成净化后的 HTML（表格/列表/代码块/加粗等）。 */
export function renderMarkdown(text: string): string {
  const html = marked.parse(String(text || ''), { async: false }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

/**
 * 渲染知识库引用片段。RAGFlow 对表格输出 HTML，但大表格可能被切成片段，
 * 单个片段只有 <tr>/<td> 而缺少 <table> 外壳，浏览器会丢弃孤立的行；这里补上外壳再渲染。
 */
export function renderChunk(text: string): string {
  let s = String(text || '')
  if (/<tr[\s>]/i.test(s) && !/<table[\s>]/i.test(s)) {
    s = `<table>${s}</table>`
  }
  return renderMarkdown(s)
}

/**
 * 把切片里的原始 HTML（常见是表格 <table>/<tr>/<td>）压成可读纯文本，
 * 用于原生 title、列表摘要等无法渲染 HTML、否则会暴露标签源码的场景。
 */
export function htmlToText(text: string): string {
  return String(text || '')
    .replace(/<\/(tr|p|div|h[1-6]|li|ul|ol)>/gi, '\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(td|th)>/gi, '\t')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&amp;/gi, '&')
    .replace(/[ \t]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
