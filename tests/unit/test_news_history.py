import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class NewsHistoryTests(unittest.TestCase):
    def test_normalize_exporter_wechat_articles_keeps_push_window_article_links(self):
        now = datetime(2026, 7, 22, 9, 0, 0)
        in_window = datetime(2026, 7, 21, 8, 31, 0)
        payload = {
            "ok": True,
            "account": "新智元",
            "articles": [{
                "title": "昨日推送后发布的大模型动态",
                "link": "https://mp.weixin.qq.com/s/example",
                "digest": "最新模型发布摘要",
                "create_time": int(in_window.timestamp()),
            }],
        }

        source = rt.normalize_exporter_wechat_articles(payload, "新智元", "08:30", now)

        self.assertEqual(source["name"], "新智元")
        self.assertEqual(source["links"][0]["title"], "昨日推送后发布的大模型动态")
        self.assertEqual(source["links"][0]["url"], "https://mp.weixin.qq.com/s/example")
        self.assertIn("发布时间：", source["text"])

    def test_push_window_excludes_previous_cutoff_and_includes_current_cutoff(self):
        now = datetime(2026, 7, 22, 9, 0, 0)
        start, end = rt.news_collection_window("08:30", now)
        self.assertEqual(start, datetime(2026, 7, 21, 8, 30, 0))
        self.assertEqual(end, datetime(2026, 7, 22, 8, 30, 0))
        self.assertFalse(rt.in_news_collection_window(int(start.timestamp()), "08:30", now))
        self.assertTrue(rt.in_news_collection_window(int((start + timedelta(minutes=1)).timestamp()), "08:30", now))
        self.assertTrue(rt.in_news_collection_window(int(end.timestamp()), "08:30", now))
        self.assertFalse(rt.in_news_collection_window(int((end + timedelta(seconds=1)).timestamp()), "08:30", now))

    def test_search_wechat_accounts_prefers_logged_in_exporter(self):
        original = rt.search_exporter_wechat_accounts
        try:
            rt.search_exporter_wechat_accounts = lambda query: {
                "ok": True,
                "query": query,
                "candidates": [{"name": "新智元", "account_id": "AI_era", "source": "已登录公众号后台"}],
                "notice": "已通过登录微信公众号后台检索。",
            }
            result = rt.search_wechat_accounts("新智元")
            self.assertEqual(result["candidates"][0]["source"], "已登录公众号后台")
        finally:
            rt.search_exporter_wechat_accounts = original

    def test_extract_wechat_account_candidates_uses_search_result_cards(self):
        html = '''
        <li class="b_algo"><h2><a href="https://example.com/xz">新智元 - 人工智能资讯</a></h2>
        <p>微信公众号新智元，微信号 AI_era，关注人工智能前沿。</p></li>
        '''

        candidates = rt.extract_wechat_account_candidates(html, "新智元")

        self.assertEqual(candidates[0]["name"], "新智元")
        self.assertEqual(candidates[0]["account_id"], "AI_era")
        self.assertEqual(candidates[0]["url"], "https://example.com/xz")

    def test_extract_sogou_candidates_requires_query_bound_wechat_id(self):
        html = '''
        <div class="vrwrap"><h3><a href="/link?url=account">新智元介绍</a></h3>
        <div class="fz-mid">新智元微信号AI_era，智能+中国主平台。</div></div>
        <div class="vrwrap"><h3><a href="/link?url=hr">加入新智元</a></h3>
        <div class="fz-mid">添加 HR 微信号：Dr-wly。</div></div>
        '''
        candidates = rt.extract_sogou_wechat_account_candidates(html, "新智元")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["account_id"], "AI_era")

    def test_clean_news_sources_preserves_wechat_account(self):
        sources = rt.clean_news_sources([{
            "kind": "wechat_account",
            "name": "新智元",
            "url": "https://mp.weixin.qq.com/s/example",
        }])

        self.assertEqual(sources[0]["kind"], "wechat_account")
        self.assertEqual(sources[0]["name"], "新智元")
        with self.assertRaisesRegex(ValueError, "公众号入口"):
            rt.clean_news_sources([{
                "kind": "wechat_account",
                "name": "新智元",
                "url": "https://example.com/article",
            }])

    def test_wechat_article_parser_extracts_article_content(self):
        article = rt.extract_wechat_article('<h1 id="activity-name">新智元测试文章</h1><span id="js_name">新智元</span><div id="js_content"><p>公众号正文内容</p></div>', 'https://mp.weixin.qq.com/s/example')
        self.assertEqual(article['title'], '新智元测试文章')
        self.assertEqual(article['account'], '新智元')
        self.assertIn('公众号正文', article['content'])

    def test_save_latest_and_list_history_by_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_user_data_dir = rt.USER_DATA_DIR
            try:
                rt.USER_DATA_DIR = Path(tmp)
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

                item = issue["items"][0]
                rt.add_news_favorite({"item": item}, "alice")
                rt.add_news_favorite({"item": item}, "bob")
                self.assertEqual(len(rt.read_news_favorites("alice")), 1)
                self.assertEqual(rt.news_favorite_count(item), 2)
                self.assertEqual(sorted(rt.rebuild_news_stats()[rt.favorite_match_key(item)]), ["alice", "bob"])
                rt.remove_news_favorite({"title": item["title"], "url": item["url"]}, "bob")
                self.assertEqual(rt.news_favorite_count(item), 1)
            finally:
                rt.USER_DATA_DIR = old_user_data_dir

    def test_empty_issue_is_not_listed_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_user_data_dir = rt.USER_DATA_DIR
            try:
                rt.USER_DATA_DIR = Path(tmp)
                empty_issue = {
                    "date": "2026-05-22",
                    "title": "2026-05-22 每日资讯",
                    "summary": "没有解析到可用资讯条目。",
                    "items": [],
                }
                rt.office_doc_write("news", rt.news_dir() / "2026-05-22.json", empty_issue)

                self.assertEqual(rt.news_history(directory=rt.news_dir()), [])
            finally:
                rt.USER_DATA_DIR = old_user_data_dir

    def test_local_generation_without_items_does_not_persist_empty_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_user_data_dir = rt.USER_DATA_DIR
            try:
                rt.USER_DATA_DIR = Path(tmp)
                result = rt.local_news_issue([], [], "", False, "tester", rt.news_dir())

                self.assertTrue(result["ok"])
                self.assertTrue(result["skipped"])
                self.assertIsNone(result["issue"])
                self.assertIsNone(rt.latest_news_issue())
                self.assertEqual(rt.office_doc_list("news", rt.news_dir()), [])
            finally:
                rt.USER_DATA_DIR = old_user_data_dir


NewsHistoryTestsDbMode = db_variant(NewsHistoryTests)


if __name__ == "__main__":
    unittest.main()
