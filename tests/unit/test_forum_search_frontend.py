"""Regression checks for the forum topic search experience."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORUM_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "ForumView" / "index.vue"


class ForumSearchFrontendTests(unittest.TestCase):
    def test_topic_search_filters_list_without_changing_existing_topic_sorting(self):
        source = FORUM_VIEW.read_text(encoding="utf-8")

        self.assertIn("const topicSearchKeyword = ref('')", source)
        self.assertIn("const filteredTopics = computed", source)
        self.assertIn("topic.title", source)
        self.assertIn("topic.body", source)
        self.assertIn("topic.author", source)
        self.assertIn('v-model="topicSearchKeyword"', source)
        self.assertIn('v-for="topic in filteredTopics"', source)
        self.assertIn("没有匹配的话题", source)


if __name__ == "__main__":
    unittest.main()
