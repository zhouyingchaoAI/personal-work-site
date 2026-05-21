import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt


class NewsHistoryTests(unittest.TestCase):
    def test_save_latest_and_list_history_by_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_news_dir = rt.news_dir
            try:
                rt.news_dir = lambda: Path(tmp)
                issue = {
                    "date": "2026-05-21",
                    "generated_at": "2026-05-21T08:30:00",
                    "generated_by": "admin",
                    "title": "2026-05-21 每日资讯",
                    "summary": "今日轨交资讯摘要",
                    "items": [{"title": "测试资讯", "source": "来源", "url": "", "impact": "影响", "action": "动作"}],
                    "keywords": ["轨道交通"],
                    "sources": [],
                    "errors": [],
                }

                rt.save_news_issue(issue)

                latest = rt.news_latest()
                self.assertEqual(latest["issue"]["date"], "2026-05-21")
                self.assertEqual(latest["history"][0]["date"], "2026-05-21")
                self.assertEqual(latest["history"][0]["item_count"], 1)

                fetched = rt.news_history_api({"date": "2026-05-21"}, "admin")
                self.assertTrue(fetched["ok"])
                self.assertEqual(fetched["issue"]["summary"], "今日轨交资讯摘要")
            finally:
                rt.news_dir = old_news_dir


if __name__ == "__main__":
    unittest.main()
