"""Static regression checks for forum composer draft persistence."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORUM_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "ForumView" / "index.vue"
DRAFT_UTIL = ROOT / "ai-office-assistant-web" / "src" / "utils" / "forumDrafts.ts"


class ForumDraftFrontendTests(unittest.TestCase):
    def test_forum_draft_utility_defines_namespaced_keys(self):
        source = DRAFT_UTIL.read_text(encoding="utf-8")
        self.assertIn("forum-draft:create", source)
        self.assertIn("forum-draft:ai", source)
        self.assertIn("forum-draft:comment:${topicId}", source)

    def test_forum_view_persists_and_restores_drafts(self):
        source = FORUM_VIEW.read_text(encoding="utf-8")
        self.assertIn("loadForumCreateDraft", source)
        self.assertIn("saveForumCreateDraft", source)
        self.assertIn("loadForumAiDraft", source)
        self.assertIn("saveForumAiDraft", source)
        self.assertIn("loadForumCommentDraft(selectedTopicId.value)", source)
        self.assertIn("saveForumCommentDraft(selectedTopicId.value", source)


    def test_forum_view_reopens_create_drawer_when_draft_exists(self):
        source = FORUM_VIEW.read_text(encoding="utf-8")
        self.assertIn("hasForumCreateDraft", source)
        self.assertIn("hasForumAiDraft", source)
        self.assertIn("createOpen = ref(hasForumCreateDraft() || hasForumAiDraft())", source)

    def test_forum_view_clears_drafts_after_successful_submit(self):
        source = FORUM_VIEW.read_text(encoding="utf-8")
        self.assertIn("clearForumCreateDraft()", source)
        self.assertIn("clearForumAiDraft()", source)
        self.assertIn("clearForumCommentDraft(selectedTopic.value.id)", source)


if __name__ == "__main__":
    unittest.main()
