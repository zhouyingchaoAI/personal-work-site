"""Static regression checks for the legacy floating assistant frontend.

These tests guard the UX fixes that are difficult to exercise in plain unittest
without a real browser driver. The real browser dogfood pass still validates the
runtime behavior, while these checks prevent accidental removal of the core
protections.
"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIL_AGENT = ROOT / "frontend" / "js" / "mail-agent.js"


class FloatingAgentFrontendRegressionTests(unittest.TestCase):
    def setUp(self):
        self.source = MAIL_AGENT.read_text(encoding="utf-8")

    def test_send_has_function_level_pending_guard(self):
        self.assertIn("let agentIsSending = false", self.source)
        self.assertIn("if (agentIsSending)", self.source)

    def test_agent_chat_has_frontend_timeout(self):
        self.assertIn("AbortController", self.source)
        self.assertIn("AGENT_CHAT_TIMEOUT_MS", self.source)

    def test_render_messages_does_not_reset_custom_timeline(self):
        start = self.source.index("function renderAgentMessages()")
        end = self.source.index("function agentPayloadMessages()", start)
        body = self.source[start:end]
        self.assertNotIn("setAgentStage(state.agentStage", body)
        self.assertIn("box.scrollTop = box.scrollHeight", body)

    def test_context_payload_is_skipped_for_direct_queries(self):
        self.assertIn("function shouldAttachAgentContext", self.source)
        self.assertIn("function compactAgentContext", self.source)
        self.assertIn("shouldAttachAgentContext(cleanText, currentData)", self.source)

    def test_errors_render_as_structured_recoverable_cards(self):
        self.assertIn("function formatAgentError", self.source)
        self.assertIn("type: 'error'", self.source)
        self.assertIn("agent-msg-error", self.source)
        self.assertIn("handleAgentError(err)", self.source)

    def test_direct_skill_results_do_not_render_duplicate_generic_cards(self):
        self.assertIn("name === 'utils.get_date' || name === 'reports.list' || name === 'diary.list' || name === 'diary.save'", self.source)

    def test_diary_list_is_treated_as_direct_query_without_page_context(self):
        self.assertIn("日记列表", self.source)
        self.assertIn("查看日记", self.source)
        self.assertIn("看看日记", self.source)
        self.assertIn("看下日记", self.source)
        self.assertIn("日记记录", self.source)

    def test_dom_event_bindings_are_owned_by_boot_js(self):
        self.assertIn("DOM event bindings live in boot.js", self.source)
        self.assertNotIn("el('agentSend').addEventListener('click'", self.source)
        self.assertNotIn("el('agentInput').addEventListener('keydown'", self.source)


class DeskPetAssistantRegressionTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "数字人" / "index.html").read_text(encoding="utf-8")
        self.wrapper = (ROOT / "ai-office-assistant-web" / "src" / "components" / "DigitalHumanAssistant" / "index.scss").read_text(encoding="utf-8")

    def test_dialog_has_central_modal_and_file_upload(self):
        self.assertIn('id="fileInput"', self.source)
        self.assertIn('"/api/writing/upload"', self.source)
        self.assertIn('file_ids: attachedFiles.map', self.source)
        self.assertIn('position: fixed', self.wrapper)

    def test_dialog_offers_report_shortcuts_and_new_session(self):
        self.assertIn('请生成本周周报', self.source)
        self.assertIn('请写一份出差报告', self.source)
        self.assertIn('chatHistory', self.source)

    def test_avatar_and_voice_are_opt_in_and_upload_is_not_blocked_by_reply(self):
        self.assertIn('avatar-hidden', self.source)
        self.assertIn('let voiceEnabled = false', self.source)
        self.assertIn('fileBtn.disabled = false', self.source)

    def test_completed_weekly_draft_can_open_the_weekly_editor(self):
        self.assertIn('chengxi.weekly-ready', self.source)
        workspace = (ROOT / "ai-office-assistant-web" / "src" / "views" / "WorkspaceView" / "index.vue").read_text(encoding="utf-8")
        weekly = (ROOT / "ai-office-assistant-web" / "src" / "views" / "WeeklyReportView" / "index.vue").read_text(encoding="utf-8")
        self.assertIn('@weekly-ready="openWeeklyEditor"', workspace)
        self.assertIn('pendingWeeklyAgentDraft', workspace)
        self.assertIn('takePendingAgentDraft', weekly)

    def test_weekly_draft_requires_explicit_review_confirmation_before_handoff(self):
        self.assertIn('weekly_draft_review', self.source)
        self.assertIn('确认写入周报编辑页', self.source)
        self.assertIn('weeklyDraftReviewText', self.source)

    def test_long_weekly_history_is_compacted_before_follow_up_chat(self):
        backend = (ROOT / "backend" / "digital_human.py").read_text(encoding="utf-8")
        self.assertIn('history[-4:]', backend)
        self.assertIn('content[:220]', backend)
        self.assertIn('对话模型返回 {exc.code}', backend)

if __name__ == "__main__":
    unittest.main()
