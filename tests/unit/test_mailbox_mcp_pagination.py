import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.runtime as rt
from backend.text_tools import DEFAULT_AGENT_WORKFLOWS


class MailboxMcpPaginationTests(unittest.TestCase):
    def setUp(self):
        self.original_user_root = rt.user_root
        self.tmp = tempfile.TemporaryDirectory()
        rt.user_root = lambda username: Path(self.tmp.name) / username

    def tearDown(self):
        rt.user_root = self.original_user_root
        self.tmp.cleanup()

    def test_cursor_pages_every_message_from_one_fixed_snapshot(self):
        rows = [
            {"uid": str(index), "folder": "收件箱", "subject": "出差报告", "attachments": []}
            for index in range(11, 0, -1)
        ]
        query = {"folder": "inbox", "keyword": "出差报告", "since": "2026-07-20", "before": "2026-07-21", "limit": 4}
        with patch.object(rt, "_mailbox_mcp_snapshot_messages", return_value=rows) as collect:
            first = rt.list_mailbox_mcp("member", query)
            second = rt.list_mailbox_mcp("member", {**query, "cursor": first["next_cursor"]})
            third = rt.list_mailbox_mcp("member", {**query, "cursor": second["next_cursor"]})

        self.assertEqual(first["total"], 11)
        self.assertTrue(first["has_more"])
        self.assertEqual(len(first["messages"]), 4)
        self.assertEqual(len(second["messages"]), 4)
        self.assertFalse(third["has_more"])
        self.assertIsNone(third["next_cursor"])
        self.assertEqual({item["uid"] for item in first["messages"] + second["messages"] + third["messages"]}, {str(i) for i in range(1, 12)})
        self.assertEqual(collect.call_count, 1)

    def test_cursor_rejects_changed_query(self):
        rows = [
            {"uid": "2", "folder": "收件箱", "attachments": []},
            {"uid": "1", "folder": "收件箱", "attachments": []},
        ]
        with patch.object(rt, "_mailbox_mcp_snapshot_messages", return_value=rows):
            first = rt.list_mailbox_mcp("member", {"folder": "inbox", "limit": 1})

        with self.assertRaisesRegex(ValueError, "查询条件"):
            rt.list_mailbox_mcp("member", {"folder": "archive", "limit": 1, "cursor": first["next_cursor"]})

    def test_mailbox_skill_dispatches_to_cursor_pagination(self):
        args = {"folder": "inbox", "limit": 100, "cursor": "opaque"}
        with patch.object(rt, "list_mailbox_mcp", return_value={"ok": True, "messages": []}) as page:
            result = rt.execute_skill("mailbox.list", args, "member", source="mcp")

        self.assertTrue(result["ok"])
        page.assert_called_once_with("member", args)

    def test_mcp_consumers_are_instructed_to_follow_cursor_pages(self):
        mailbox_list = next(item for item in rt._mcp_tools_list() if item["name"] == "mailbox.list")
        description = mailbox_list["description"]

        self.assertIn("next_cursor", description)
        self.assertIn("has_more", description)
        self.assertIn("page/offset", description)
        self.assertIn("next_cursor", DEFAULT_AGENT_WORKFLOWS["mailassistant"])
        self.assertIn("has_more", DEFAULT_AGENT_WORKFLOWS["mailassistant"])
        self.assertIn("page/offset", DEFAULT_AGENT_WORKFLOWS["mailassistant"])


if __name__ == "__main__":
    unittest.main()
