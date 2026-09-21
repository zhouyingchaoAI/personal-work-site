"""Regression coverage for the Mail Assistant inbox/sent tab race."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIL_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "MailAssistantView" / "index.vue"


class MailAssistantSentMailFrontendTests(unittest.TestCase):
    def test_only_the_latest_mailbox_request_may_update_the_active_tab(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("let mailboxRequestVersion = 0", source)
        self.assertIn("let mailboxRequestController: AbortController | null = null", source)
        self.assertIn("mailboxRequestController?.abort()", source)
        self.assertIn("const requestController = new AbortController()", source)
        self.assertIn("if (error instanceof DOMException && error.name === 'AbortError') return", source)
        self.assertIn("const requestVersion = ++mailboxRequestVersion", source)
        self.assertIn("if (requestVersion !== mailboxRequestVersion || requestedMode !== mailboxMode.value) return", source)
        self.assertNotIn("if (loading.mailbox) return", source)

    def test_ready_detail_from_mailbox_list_is_shown_without_another_request(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("const readyDetail = messages.value.find((message) => message.uid === uid)", source)
        self.assertIn("if (readyDetail?.body || readyDetail?.body_html)", source)
        self.assertIn("detail.value = readyDetail", source)

    def test_mailbox_list_warms_inline_images_before_the_user_clicks(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("function warmMailInlineResources", source)
        self.assertIn("warmMailInlineResources(messages.value)", source)

    def test_inbox_can_load_older_mail_pages(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("async function loadMoreInbox", source)
        self.assertIn("加载更早邮件", source)

    def test_inbox_has_separate_all_unread_and_read_directories(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("type InboxReadStatus = 'all' | 'unread' | 'read'", source)
        self.assertIn("全部邮件", source)
        self.assertIn("未读邮件", source)
        self.assertIn("已读邮件", source)
        self.assertIn("switchInboxReadStatus", source)
        self.assertIn("inboxReadStatus.value", source)

    def test_unread_mail_has_a_distinct_visual_marker(self):
        style = (ROOT / "ai-office-assistant-web" / "src" / "views" / "MailAssistantView" / "index.scss").read_text(encoding="utf-8")
        self.assertIn("&.unread {", style)
        self.assertIn("border-left: 4px solid", style)
        self.assertIn("background: #edf5ff", style)

    def test_opening_inbox_mail_marks_it_read_and_shows_folder_counts(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("markMailboxRead", source)
        self.assertIn("message.is_read = true", source)
        self.assertIn("inboxCounts", source)
        self.assertIn("全部邮件 {{ inboxCounts.all }}", source)
        self.assertIn("未读邮件 {{ inboxCounts.unread }}", source)

    def test_cached_inbox_status_is_compact_and_does_not_compete_with_read_tabs(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        style = (ROOT / "ai-office-assistant-web" / "src" / "views" / "MailAssistantView" / "index.scss").read_text(encoding="utf-8")
        self.assertIn('近一个月邮件已缓存', source)
        self.assertNotIn('已快速加载近一个月邮件缓存', source)
        self.assertIn('class="mail-section-title"', source)
        self.assertIn('.mailbox-card .mail-section-head', style)
        self.assertIn('flex: 1 1 100%', style)

    def test_mail_detail_offers_reply_sender_and_reply_all(self):
        source = MAIL_VIEW.read_text(encoding="utf-8")
        self.assertIn("function startReply", source)
        self.assertIn("parseMailAddresses", source)
        self.assertIn("startReply('sender')", source)
        self.assertIn("startReply('all')", source)
        self.assertIn("回复发送方", source)
        self.assertIn("全部回复", source)


if __name__ == "__main__":
    unittest.main()
