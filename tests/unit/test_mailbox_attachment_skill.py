"""Tests for the mailbox.attachment skill that lets MCP/Agent read attachments
without a browser session cookie."""
import base64
import tempfile
import unittest
from pathlib import Path

from backend import runtime


class MailboxAttachmentSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_get_part = runtime.get_mail_part

    def tearDown(self):
        runtime.get_mail_part = self._orig_get_part
        self._tmp.cleanup()

    def _fake_part(self, content: bytes, saved_name="part2__invoice.pdf"):
        path = Path(self._tmp.name) / saved_name
        path.write_bytes(content)
        runtime.get_mail_part = lambda username, uid, part: path
        return path

    def test_returns_base64_content(self):
        self._fake_part(b"%PDF-1.4 fake invoice bytes")
        out = runtime.mailbox_attachment_skill({"uid": "42", "part": "part2"}, "u1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["encoding"], "base64")
        self.assertEqual(base64.b64decode(out["content_base64"]), b"%PDF-1.4 fake invoice bytes")
        self.assertEqual(out["name"], "invoice.pdf")
        self.assertEqual(out["mime"], "application/pdf")
        self.assertEqual(out["size"], len(b"%PDF-1.4 fake invoice bytes"))

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
        out = runtime.mailbox_attachment_skill({"uid": "1", "part": "part2", "max_bytes": 1024}, "u1")
        self.assertFalse(out["ok"])
        self.assertIn("超过", out["error"])
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
        out = runtime.execute_skill("mailbox.attachment", {"uid": "1", "part": "part2"}, "u1")
        self.assertEqual(base64.b64decode(out["content_base64"]), b"hello")

    def test_exposed_as_mcp_tool(self):
        tool_names = {t["name"] for t in runtime._mcp_tools_list()}
        self.assertIn("mailbox.attachment", tool_names)


if __name__ == "__main__":
    unittest.main()
