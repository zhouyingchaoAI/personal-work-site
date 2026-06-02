import { h, ref } from 'vue'

interface MailSendConfirmMessageOptions {
  intro: string
  subject: string
  toRecipients: string[]
  ccRecipients: string[]
}

function canToggleRecipients(toRecipients: string[], ccRecipients: string[]) {
  return toRecipients.length > 2 || ccRecipients.length > 2 || [...toRecipients, ...ccRecipients].join('').length > 160
}

function createRecipientGroup(label: string, recipients: string[], expanded: boolean) {
  return h('section', { class: 'mail-send-confirm__group' }, [
    h('div', { class: 'mail-send-confirm__group-head' }, [
      h('span', { class: 'mail-send-confirm__label' }, label),
      h('span', { class: 'mail-send-confirm__count' }, `${recipients.length} 人`),
    ]),
    h(
      'div',
      {
        class: ['mail-send-confirm__recipients', expanded && 'is-expanded'],
      },
      recipients.length
        ? recipients.map((item) => h('span', { class: 'mail-send-confirm__recipient', title: item }, item))
        : h('span', { class: 'mail-send-confirm__empty' }, '无'),
    ),
  ])
}

export function createMailSendConfirmMessage(options: MailSendConfirmMessageOptions) {
  return h({
    name: 'MailSendConfirmMessage',
    setup() {
      const expanded = ref(false)
      const canToggle = canToggleRecipients(options.toRecipients, options.ccRecipients)
      return () =>
        h('div', { class: ['mail-send-confirm', expanded.value && 'is-expanded'] }, [
          h('p', { class: 'mail-send-confirm__intro' }, options.intro),
          h('div', { class: 'mail-send-confirm__subject' }, [
            h('span', { class: 'mail-send-confirm__label' }, '主题'),
            h('span', { class: 'mail-send-confirm__subject-text' }, options.subject),
          ]),
          createRecipientGroup('收件人', options.toRecipients, expanded.value),
          createRecipientGroup('抄送', options.ccRecipients, expanded.value),
          canToggle
            ? h(
                'button',
                {
                  class: 'mail-send-confirm__toggle',
                  type: 'button',
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation()
                    expanded.value = !expanded.value
                  },
                },
                expanded.value ? '收起' : '展开全部',
              )
            : null,
        ])
    },
  })
}
