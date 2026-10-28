"""邮件助手本地存储：附件分片、已发记录、MCP 下载链接、缓存清理。"""
import tempfile
import time
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class MailStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_parts_save_get_clear(self):
        saved = rt.save_mail_part("alice", "42", "part2", "发票.pdf", b"%PDF")
        self.assertEqual(saved.name, "part2__发票.pdf")
        path, raw = rt.get_mail_part_content("alice", "42", "part2")
        self.assertEqual((path.name, raw), ("part2__发票.pdf", b"%PDF"))
        self.assertIsNone(rt.mail_part_path("alice", "42", "part3"))
        self.assertIsNone(rt.mail_part_path("bob", "42", "part2"))
        rt.clear_mail_part_dir("alice", "42")
        self.assertIsNone(rt.mail_part_path("alice", "42", "part2"))

    def test_mcp_link_roundtrip_and_expiry(self):
        rt.save_mail_part("alice", "7", "part1", "a.txt", b"hello")
        url = rt.create_mcp_mail_attachment_link("alice", "7", "part1", expires_seconds=3600)
        token = url.split("token=", 1)[1]
        info = rt.resolve_mcp_mail_attachment_link(token)
        self.assertEqual((info["username"], info["uid"], info["part"]), ("alice", "7", "part1"))
        self.assertEqual(rt.get_mail_part_content(info["username"], info["uid"], info["part"])[1], b"hello")
        expired = rt.create_mcp_mail_attachment_link("alice", "7", "part1", expires_seconds=60)
        expired_token = expired.split("token=", 1)[1]
        rt.office_doc_write("mailassistant", rt.mcp_mail_attachment_token_path(expired_token),
                            {"username": "alice", "uid": "7", "part": "part1", "expires_at": time.time() - 1})
        with self.assertRaises(ValueError):
            rt.resolve_mcp_mail_attachment_link(expired_token)
        with self.assertRaises(ValueError):
            rt.resolve_mcp_mail_attachment_link("unknown")

    def test_cache_and_sent_store_are_separate(self):
        rt.write_mail_cache("alice", "inbox_v2_inbox_all_20_0_", {"messages": [{"uid": "1", "is_read": False}], "unread_count": 1, "total": 1})
        rt.save_sent_mail_store("alice", [{"uid": "sent-1"}])
        rt._update_cached_mail_read_state("alice", "1")
        cached = rt.read_mail_cache("alice", "inbox_v2_inbox_all_20_0_", 0)
        self.assertTrue(cached["messages"][0]["is_read"])
        self.assertEqual(cached["unread_count"], 0)
        rt.clear_mail_cache("alice")
        self.assertIsNone(rt.read_mail_cache("alice", "inbox_v2_inbox_all_20_0_", 0))
        self.assertEqual([m["uid"] for m in rt.load_sent_mail_store("alice")], ["sent-1"])
        self.assertEqual(rt.load_sent_mail_store("bob"), [])


MailStorageDbModeTests = db_variant(MailStorageTests)


if __name__ == "__main__":
    unittest.main()
