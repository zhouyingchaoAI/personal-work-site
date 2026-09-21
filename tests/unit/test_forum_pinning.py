import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
FORUM_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "ForumView" / "index.vue"


class ForumPinningTests(unittest.TestCase):
    def test_manual_pinning_requires_superadmin_in_route_and_ui(self):
        server = SERVER.read_text(encoding="utf-8")
        pin_route = server.split('elif parsed.path == "/api/forum/pin":', 1)[1].split('elif parsed.path == "/api/forum/ai-topic":', 1)[0]
        self.assertIn("self.require_superadmin()", pin_route)
        self.assertNotIn("self.require_admin()", pin_route)
        view = FORUM_VIEW.read_text(encoding="utf-8")
        self.assertIn("authState.user?.is_superadmin", view)
        self.assertIn("!isPlatformTicket(selectedTopic.value)", view)

    def test_topic_can_be_pinned_and_unpinned_and_is_listed_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_dir = rt.USER_DATA_DIR
            original_find_user = rt.find_user
            try:
                rt.USER_DATA_DIR = Path(tmp)
                rt.find_user = lambda username: {"name": username}
                first = rt.forum_create_topic({"title": "普通话题", "body": "内容"}, "admin")["topic"]
                second = rt.forum_create_topic({"title": "待置顶话题", "body": "内容"}, "admin")["topic"]

                pinned = rt.forum_set_topic_pinned({"topic_id": second["id"], "pinned": True}, "admin")["topic"]
                self.assertTrue(pinned["pinned"])
                self.assertEqual(rt.forum_list_topics("admin")["topics"][0]["id"], second["id"])

                unpinned = rt.forum_set_topic_pinned({"topic_id": second["id"], "pinned": False}, "admin")["topic"]
                self.assertFalse(unpinned["pinned"])
                self.assertFalse(any(topic["id"] == second["id"] and topic.get("pinned") for topic in rt.forum_list_topics("admin")["topics"]))
                self.assertNotEqual(first["id"], "")
            finally:
                rt.USER_DATA_DIR = original_dir
                rt.find_user = original_find_user

    def test_forum_no_longer_creates_or_lists_platform_tickets(self):
        """工单已拆分到独立工单系统：论坛不再创建或展示 platform_ticket。"""
        with tempfile.TemporaryDirectory() as tmp:
            original_dir = rt.USER_DATA_DIR
            original_find_user = rt.find_user
            try:
                rt.USER_DATA_DIR = Path(tmp)
                rt.find_user = lambda username: {"name": username}
                created = rt.forum_create_topic({
                    "title": "本应是话题", "body": "内容", "preset": "platform_ticket",
                }, "admin")["topic"]
                # preset 被强制清空，作为普通话题创建，且不会自动置顶。
                self.assertNotEqual(created.get("preset"), "platform_ticket")
                self.assertFalse(created.get("pinned"))
            finally:
                rt.USER_DATA_DIR = original_dir
                rt.find_user = original_find_user
