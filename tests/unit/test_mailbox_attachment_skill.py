"""Tests for the mailbox.attachment skill that lets MCP/Agent read attachments
without a browser session cookie."""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime
from tests.unit.officedb_testing import db_variant


class MailboxAttachmentSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_get_part = runtime.get_mail_part
        self._orig_user_data_dir = runtime.USER_DATA_DIR
        runtime.USER_DATA_DIR = Path(self._tmp.name) / "user_data"
        runtime.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        runtime.get_mail_part = self._orig_get_part
        runtime.USER_DATA_DIR = self._orig_user_data_dir
        self._tmp.cleanup()

    def _fake_part(self, content: bytes, saved_name="part2__invoice.pdf"):
        path = Path(self._tmp.name) / saved_name
        path.write_bytes(content)
        runtime.get_mail_part = lambda username, uid, part: path
        return path

    def test_returns_base64_content(self):
        self._fake_part(b"%PDF-1.4 fake invoice bytes")
        # 默认只回下载链接；显式 include_base64=true 才内联 base64。
        out = runtime.mailbox_attachment_skill({"uid": "42", "part": "part2", "include_base64": True}, "u1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["encoding"], "base64")
        self.assertEqual(base64.b64decode(out["content_base64"]), b"%PDF-1.4 fake invoice bytes")
        self.assertEqual(out["name"], "invoice.pdf")
        self.assertEqual(out["mime"], "application/pdf")
        self.assertEqual(out["size"], len(b"%PDF-1.4 fake invoice bytes"))

    def test_defaults_to_download_link_without_base64(self):
        self._fake_part(b"%PDF-1.4 fake invoice bytes")
        out = runtime.mailbox_attachment_skill({"uid": "42", "part": "part2"}, "u1")
        self.assertTrue(out["ok"])
        self.assertFalse(out["base64_included"])
        self.assertNotIn("content_base64", out)
        self.assertTrue(out["download_url"])
        self.assertTrue(out["download_url_absolute"])

    def test_requires_uid_and_part(self):
        with self.assertRaises(ValueError):
            runtime.mailbox_attachment_skill({"uid": "42"}, "u1")
        with self.assertRaises(ValueError):
            runtime.mailbox_attachment_skill({"part": "part2"}, "u1")

    def test_accepts_part_key_alias(self):
        self._fake_part(b"data", saved_name="part3__a.txt")
        out = runtime.mailbox_attachment_skill({"uid": "1", "part_key": "part3"}, "u1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["name"], "a.txt")

    def test_size_cap_skips_inline(self):
        self._fake_part(b"X" * 2048)
        # 请求内联 base64 但超过 max_bytes：仍成功返回下载链接，只是省略 base64 并说明原因。
        out = runtime.mailbox_attachment_skill(
            {"uid": "1", "part": "part2", "include_base64": True, "max_bytes": 1024}, "u1"
        )
        self.assertTrue(out["ok"])
        self.assertFalse(out["base64_included"])
        self.assertTrue(out["content_omitted"])
        self.assertIn("超过", out["omit_reason"])
        self.assertNotIn("content_base64", out)
        self.assertEqual(out["size"], 2048)

    def test_name_without_key_prefix(self):
        self._fake_part(b"d", saved_name="plainname.bin")
        out = runtime.mailbox_attachment_skill({"uid": "1", "part": "part0"}, "u1")
        self.assertEqual(out["name"], "plainname.bin")

    def test_registered_and_dispatched(self):
        names = {s["name"] for s in runtime.skill_defs()}
        self.assertIn("mailbox.attachment", names)
        self._fake_part(b"hello")
        out = runtime.execute_skill("mailbox.attachment", {"uid": "1", "part": "part2", "include_base64": True}, "u1")
        self.assertEqual(base64.b64decode(out["content_base64"]), b"hello")

    def test_exposed_as_mcp_tool(self):
        tool_names = {t["name"] for t in runtime._mcp_tools_list()}
        self.assertIn("mailbox.attachment", tool_names)

    def test_clearing_inbox_cache_keeps_sent_mail_history(self):
        original_user_root = runtime.user_root
        try:
            runtime.user_root = lambda username: Path(self._tmp.name) / username
            cache_dir = runtime.user_mail_cache_dir("u1")
            runtime.save_sent_mail_store("u1", [{"uid": "sent-1"}])
            runtime.write_mail_cache("u1", "inbox_inbox_20", {"messages": []})

            runtime.clear_mail_cache("u1")

            self.assertEqual([m["uid"] for m in runtime.load_sent_mail_store("u1")], ["sent-1"])
            self.assertIsNone(runtime.read_mail_cache("u1", "inbox_inbox_20", 0))
            self.assertFalse((cache_dir / "inbox_inbox_20.json").exists())
        finally:
            runtime.user_root = original_user_root

    def test_sent_mail_list_includes_archived_platform_reports(self):
        original_report_files = runtime.report_files
        original_compose_draft = runtime.compose_draft
        try:
            runtime.report_files = lambda username: [{
                "kind": "weekly",
                "name": "张三工作周报2026.8.3-2026.8.7.xlsx",
                "path": "/reports/weekly/张三工作周报2026.8.3-2026.8.7.xlsx",
                "mtime": 1786000000,
            }]
            runtime.compose_draft = lambda kind, name, username: {
                "body": "领导您好：\n\n本周完成平台升级。",
                "body_html": "<p>领导您好：</p><table><tr><td>本周完成平台升级</td></tr></table>",
                "to": "leader@example.com",
                "cc": "",
            }

            result = runtime.list_sent_messages("u1", 20)

            self.assertEqual(len(result["messages"]), 1)
            message = result["messages"][0]
            self.assertEqual(message["subject"], "【周报】张三工作周报2026.8.3-2026.8.7.xlsx")
            self.assertEqual(message["source"], "platform_report")
            detail = runtime.get_sent_message("u1", message["uid"])
            self.assertIn("本周完成平台升级", detail["message"]["body"])
            self.assertIn("<table>", detail["message"]["body_html"])
        finally:
            runtime.report_files = original_report_files
            runtime.compose_draft = original_compose_draft


MailboxAttachmentSkillDbModeTests = db_variant(MailboxAttachmentSkillTests)


if __name__ == "__main__":
    unittest.main()
