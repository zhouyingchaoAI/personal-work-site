export type MailRecipientField = 'to' | 'cc'

const emailPattern = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi
const headerPattern = /(^|[\r\n])\s*(发件人|收件人|抄送|密送|From|To|Cc|Bcc)\s*[：:]/gi
const trimRecipientSeparatorsPattern = /^[\s,，;；]+|[\s,，;；]+$/g

const headerFieldMap: Record<string, MailRecipientField | 'from' | 'bcc'> = {
  发件人: 'from',
  收件人: 'to',
  抄送: 'cc',
  密送: 'bcc',
  from: 'from',
  to: 'to',
  cc: 'cc',
  bcc: 'bcc',
}

function headerField(label: string) {
  return headerFieldMap[label] || headerFieldMap[label.toLowerCase()] || ''
}

function fieldText(value: string, field?: MailRecipientField) {
  if (!field) return value
  const sections = Array.from(value.matchAll(headerPattern))
  if (!sections.length) return value
  const parts: string[] = []
  sections.forEach((section, index) => {
    if (headerField(section[2]) !== field) return
    const start = (section.index || 0) + section[0].length
    const end = sections[index + 1]?.index ?? value.length
    parts.push(value.slice(start, end))
  })
  // 带邮件头的粘贴内容只取当前字段，避免混入其他联系人。
  return parts.length ? parts.join('\n') : ''
}

function recipientLabel(source: string, match: RegExpExecArray) {
  const email = match[0].trim()
  const emailStart = match.index
  const emailEnd = emailStart + match[0].length
  const beforeEmail = source.slice(0, emailStart)
  const afterEmail = source.slice(emailEnd)
  const bracketStart = beforeEmail.search(/<\s*$/)
  if (bracketStart < 0 || !/^\s*>/.test(afterEmail)) return email
  const openIndex = beforeEmail.length - beforeEmail.match(/<\s*$/)![0].length
  const labelStart = Math.max(
    beforeEmail.lastIndexOf(',', openIndex),
    beforeEmail.lastIndexOf('，', openIndex),
    beforeEmail.lastIndexOf(';', openIndex),
    beforeEmail.lastIndexOf('；', openIndex),
    beforeEmail.lastIndexOf('\n', openIndex),
    beforeEmail.lastIndexOf('\r', openIndex),
  )
  const closeIndex = emailEnd + afterEmail.match(/^\s*>/)![0].length
  const label = source.slice(labelStart + 1, closeIndex).replace(trimRecipientSeparatorsPattern, '').trim()
  // 页面保留用户粘贴的联系人样式，发送时再单独提取邮箱。
  return label || email
}

function parseMailRecipientItems(value: string | string[], field?: MailRecipientField) {
  const inputs = Array.isArray(value) ? value : [value]
  const seen = new Set<string>()
  const recipients: Array<{ label: string; email: string }> = []
  inputs.forEach((item) => {
    const source = fieldText(String(item || ''), field)
    for (const match of source.matchAll(emailPattern)) {
      const email = match[0].trim()
      const key = email.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      recipients.push({ label: recipientLabel(source, match), email })
    }
  })
  return recipients
}

export function parseMailRecipients(value: string | string[], field?: MailRecipientField) {
  return parseMailRecipientItems(value, field).map((item) => item.label)
}

export function serializeMailRecipients(value: string | string[], field?: MailRecipientField) {
  return parseMailRecipients(value, field).join(';')
}

export function serializeMailRecipientEmails(value: string | string[], field?: MailRecipientField) {
  return parseMailRecipientItems(value, field).map((item) => item.email).join(';')
}
