import unittest
from pathlib import Path


class NewsSourceEditorFrontendTests(unittest.TestCase):
    def test_source_editor_exposes_a_search_then_subscribe_wechat_flow(self):
        source = Path("ai-office-assistant-web/src/views/NewsView/index.vue").read_text(encoding="utf-8")

        self.assertIn("function addSource(kind: NewsSource['kind'] = 'web')", source)
        self.assertIn('function handleWechatAccountSearch()', source)
        self.assertIn('function subscribeWechatAccount(candidate: WechatAccountCandidate)', source)
        self.assertIn('订阅微信公众号', source)
        self.assertIn('搜索公众号', source)
        self.assertIn('>订阅</button>', source)
        self.assertIn('核验来源：{{ candidate.source }}', source)
        self.assertIn('await handleSaveConfig()', source)
        self.assertIn("公众号名称", source)
        self.assertIn("文章入口", source)


if __name__ == "__main__":
    unittest.main()
