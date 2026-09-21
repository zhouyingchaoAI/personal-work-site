import unittest
from pathlib import Path


KNOWLEDGE_VIEW = Path(__file__).resolve().parents[2] / "ai-office-assistant-web" / "src" / "views" / "KnowledgeBaseView" / "index.vue"


class KnowledgeCitationFrontendTests(unittest.TestCase):
    def setUp(self):
        self.source = KNOWLEDGE_VIEW.read_text(encoding="utf-8")

    def test_citation_popover_matches_source_index_before_array_offset(self):
        self.assertIn("function citationSourceIndex", self.source)
        self.assertIn("source.index === citeNumber", self.source)
        self.assertIn("citeNumber - 1", self.source)
        self.assertIn("data-cite-index", self.source)

    def test_large_unmatched_citations_fallback_to_source_order(self):
        self.assertIn("fallbackCitationIndexes", self.source)
        self.assertIn("fallbackNextSourceIndex", self.source)
        self.assertIn("fallbackCitationIndexes.set(citeNumber, fallbackNextSourceIndex)", self.source)
        self.assertIn("sourceIndex = fallbackCitationIndexes.get(citeNumber) ?? -1", self.source)

    def test_chat_input_uses_readable_multiline_textarea(self):
        self.assertIn("function handleQueryKeydown", self.source)
        self.assertIn("event.shiftKey", self.source)
        self.assertIn("<textarea", self.source)
        self.assertIn('rows="2"', self.source)
        self.assertIn('@keydown.enter="handleQueryKeydown"', self.source)

    def test_clear_chat_has_an_explicit_secondary_confirmation(self):
        self.assertIn("async function clearChat()", self.source)
        self.assertIn("'清空当前对话'", self.source)
        self.assertIn("'确认清空'", self.source)
        self.assertIn("`将永久清空", self.source)
        self.assertIn('kb-btn--danger kb-clear-chat', self.source)

    def test_citation_event_recovers_invalid_large_cite_indexes(self):
        self.assertIn("function resolveCitationSourceIndex", self.source)
        self.assertIn("target.closest('.kb-markdown')", self.source)
        self.assertIn("fallbackByCite.set(itemNumber, nextFallback)", self.source)
        self.assertIn('@click="handleCiteClick($event, msg)"', self.source)


if __name__ == "__main__":
    unittest.main()
