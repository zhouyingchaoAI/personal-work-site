import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** 把 LLM 输出的 Markdown 渲染成净化后的 HTML（表格/列表/代码块/加粗等）。 */
export function renderMarkdown(text: string): string {
  const html = marked.parse(String(text || ''), { async: false }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}


function renderExcelLikeChunk(text: string): string {
  const rows = String(text || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!rows.length) return ''
  const parsed = rows.map((line) => {
    const cells = line
      .split(/[;；]/)
      .map((cell) => cell.trim())
      .filter(Boolean)
      .map((cell) => {
        const match = cell.match(/^([^：:]{0,40})[：:](.*)$/)
        if (!match) return { label: '', value: cell.trim() }
        const rawLabel = match[1].trim()
        return {
          label: rawLabel && rawLabel.toLowerCase() !== 'none' ? rawLabel : '',
          value: match[2].trim(),
        }
      })
      .filter((cell) => cell.value)
    return cells
  }).filter((cells) => cells.length >= 3)
  if (!parsed.length) return ''
  const totalCells = parsed.reduce((sum, cells) => sum + cells.length, 0)
  const noneLikeCount = parsed.reduce((sum, cells) => sum + cells.filter((cell) => !cell.label).length, 0)
  if (totalCells < 6 || noneLikeCount < Math.max(2, totalCells * 0.35)) return ''
  const body = parsed.map((cells) => {
    const head = cells.find((cell) => cell.label) || cells[0]
    const rest = cells.filter((cell) => cell !== head)
    const items = rest.map((cell, index) => {
      const label = cell.label || `字段 ${index + 1}`
      return `<li><span>${escapeHtml(label)}</span><em>${escapeHtml(cell.value)}</em></li>`
    }).join('')
    return `<article class="kb-excel-record"><header><span>${escapeHtml(head.label || '记录')}</span><strong>${escapeHtml(head.value)}</strong></header><ol>${items}</ol></article>`
  }).join('')
  return DOMPurify.sanitize(`<div class="kb-excel-chunk">${body}</div>`, { USE_PROFILES: { html: true } })
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
  if (!/<[a-z][\s\S]*>/i.test(s)) {
    const excelHtml = renderExcelLikeChunk(s)
    if (excelHtml) return excelHtml
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
