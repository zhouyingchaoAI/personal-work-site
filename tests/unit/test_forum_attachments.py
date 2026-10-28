"""论坛附件与话题存储：文件模式与数据库模式行为一致。"""
import base64
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class ForumAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        self.original_find_user = rt.find_user
        rt.USER_DATA_DIR = Path(self.tmp.name)
        rt.find_user = lambda username: {"name": username}

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        rt.find_user = self.original_find_user
        self.tmp.cleanup()

    def test_upload_reuse_and_serve_attachment(self):
        uploaded = rt.forum_upload_attachment({"name": "截图.png", "type": "image/png",
                                              "data": base64.b64encode(b"\x89PNG-bytes").decode()}, "admin")["attachment"]
        self.assertTrue(uploaded["is_image"])
        path, raw = rt.forum_attachment_content(uploaded["id"])
        self.assertEqual(raw, b"\x89PNG-bytes")
        self.assertTrue(path.name.startswith(uploaded["id"]))
        topic = rt.forum_create_topic({"title": "带附件", "body": "内容",
                                       "attachments": [{"id": uploaded["id"], "name": "截图.png"}]}, "admin")["topic"]
        self.assertEqual(topic["attachments"][0]["size"], len(b"\x89PNG-bytes"))
        listed = rt.forum_list_topics("admin")["topics"]
        self.assertEqual(listed[0]["attachments"][0]["url"], uploaded["url"])
        self.assertIsNone(rt.forum_attachment_content("missing-id"))
        self.assertIsNone(rt.forum_attachment_content("../etc"))

    def test_comment_and_like_persist(self):
        topic = rt.forum_create_topic({"title": "话题", "body": "内容"}, "admin")["topic"]
        rt.forum_add_comment({"topic_id": topic["id"], "content": "回复"}, "bob")
        rt.forum_toggle_like({"topic_id": topic["id"]}, "bob")
        got = rt.forum_get_topic({"id": topic["id"]}, "admin")["topic"]
        self.assertEqual(len(got["comments"]), 1)
        self.assertEqual(got["view_count"], 1)


ForumAttachmentDbModeTests = db_variant(ForumAttachmentTests)


if __name__ == "__main__":
    unittest.main()
