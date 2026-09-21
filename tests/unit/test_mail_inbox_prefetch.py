import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

import backend.runtime as rt


class MailInboxPrefetchTests(unittest.TestCase):
    def test_html_mail_preview_removes_leaked_css_rules(self):
        message = EmailMessage()
        message.set_content(
            'table.customTableClassName {margin-bottom: 10px;border-collapse: collapse;display: table;}'
            '.customTableClassName td {border: 1px solid #ddd;}<p>欢迎新同事加入我们大家庭！</p>',
            subtype="html",
        )

        preview = rt.extract_mail_text(message, 180)

        self.assertEqual(preview, "欢迎新同事加入我们大家庭！")

    def test_imap_fetch_flags_distinguish_read_and_unread_messages(self):
        self.assertTrue(rt.mail_fetch_meta_is_read("963 (UID 963 FLAGS (\\Seen) BODY[HEADER])"))
        self.assertFalse(rt.mail_fetch_meta_is_read("964 (UID 964 FLAGS () BODY[HEADER])"))

    def test_inbox_offset_returns_a_later_page_and_indicates_more_mail(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username

                class FakeBox:
                    def logout(self):
                        pass

                page = [{"uid": str(index), "attachments": []} for index in range(21, 41)]
                with patch.object(rt, "imap_connect", return_value=FakeBox()), patch.object(
                    rt, "_fetch_folder_summaries", return_value=(page, 61)
                ) as fetch:
                    result = rt.list_inbox_messages("member", 20, refresh=True, offset=20)

                self.assertEqual(result["messages"][0]["uid"], "21")
                self.assertTrue(result["has_more"])
                self.assertEqual(result["total"], 61)
                self.assertEqual(fetch.call_args.args[6], 20)
            finally:
                rt.user_root = original_user_root

    def test_inbox_read_status_is_forwarded_to_the_imap_list_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username

                class FakeBox:
                    def logout(self):
                        pass

                with patch.object(rt, "imap_connect", return_value=FakeBox()), patch.object(
                    rt, "_fetch_folder_summaries", return_value=([{"uid": "3", "is_read": False, "attachments": []}], 1)
                ) as fetch:
                    result = rt.list_inbox_messages("member", 20, refresh=True, read_status="unread")

                self.assertEqual(result["messages"][0]["uid"], "3")
                self.assertEqual(fetch.call_args.kwargs["read_status"], "unread")
            finally:
                rt.user_root = original_user_root

    def test_unread_tab_discards_cached_rows_that_have_been_marked_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", "inbox_v2_inbox_unread_20_0_", {
                    "messages": [{"uid": "stale", "is_read": True, "attachments": []}],
                    "total": 1,
                    "counts": {"all": 3, "unread": 1, "read": 2},
                })

                class FakeBox:
                    def logout(self):
                        pass

                fresh = [{"uid": "fresh", "is_read": False, "attachments": []}]
                with patch.object(rt, "schedule_user_inbox_prefetch"), patch.object(
                    rt, "imap_connect", return_value=FakeBox()
                ), patch.object(rt, "_fetch_folder_summaries", return_value=(fresh, 1)) as fetch, patch.object(
                    rt, "_inbox_read_counts", return_value={"all": 3, "unread": 1, "read": 2}
                ):
                    result = rt.list_inbox_messages("member", 20, refresh=False, read_status="unread")

                self.assertEqual([item["uid"] for item in result["messages"]], ["fresh"])
                self.assertTrue(all(item["is_read"] is False for item in result["messages"]))
                fetch.assert_called_once()
            finally:
                rt.user_root = original_user_root

    def test_inbox_response_includes_all_unread_and_read_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username

                class FakeBox:
                    def logout(self):
                        pass

                with patch.object(rt, "imap_connect", return_value=FakeBox()), patch.object(
                    rt, "_fetch_folder_summaries", return_value=([{"uid": "3", "is_read": False, "attachments": []}], 4)
                ), patch.object(rt, "_inbox_read_counts", return_value={"all": 12, "unread": 3, "read": 9}, create=True):
                    result = rt.list_inbox_messages("member", 20, refresh=True)

                self.assertEqual(result["counts"], {"all": 12, "unread": 3, "read": 9})
                self.assertEqual(result["unread_count"], 3)
                self.assertEqual(result["read_count"], 9)
            finally:
                rt.user_root = original_user_root

    def test_month_snapshot_is_used_before_opening_imap(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [{"uid": "3"}, {"uid": "2"}, {"uid": "1"}],
                    "period_start": "2026-07-20",
                })
                with patch.object(rt, "imap_connect", side_effect=AssertionError("不应连接 IMAP")):
                    result = rt.list_inbox_messages("member", 2, refresh=False)

                self.assertTrue(result["cached"])
                self.assertTrue(result["background_sync"])
                self.assertEqual([item["uid"] for item in result["messages"]], ["3", "2"])
            finally:
                rt.user_root = original_user_root

    def test_unread_tab_uses_recent_snapshot_when_filtered_cache_is_stale_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [
                        {"uid": "3", "is_read": False},
                        {"uid": "2", "is_read": True},
                        {"uid": "1", "is_read": False},
                    ],
                    "total": 3,
                    "counts": {"all": 3, "unread": 2, "read": 1},
                    "period_start": "2026-07-20",
                })
                # A transient IMAP search used to leave this cache entry behind,
                # causing the unread tab to show a false empty state for 30 minutes.
                rt.write_mail_cache("member", "inbox_v2_inbox_unread_20_0_", {
                    "messages": [],
                    "total": 0,
                    "counts": {"all": 0, "unread": 0, "read": 0},
                })
                with patch.object(rt, "schedule_user_inbox_prefetch") as schedule, patch.object(
                    rt, "imap_connect", side_effect=AssertionError("不应连接 IMAP")
                ):
                    result = rt.list_inbox_messages("member", 20, refresh=False, read_status="unread")

                self.assertEqual([item["uid"] for item in result["messages"]], ["3", "1"])
                self.assertEqual(result["counts"], {"all": 3, "unread": 2, "read": 1})
                self.assertEqual(result["total"], 2)
                self.assertTrue(result["cached"])
                schedule.assert_called_once_with("member")
            finally:
                rt.user_root = original_user_root

    def test_opening_cached_inbox_schedules_current_users_detail_prefetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [{"uid": "3"}],
                    "period_start": "2026-07-20",
                })
                with patch.object(rt, "schedule_user_inbox_prefetch") as schedule:
                    result = rt.list_inbox_messages("member", 20, refresh=False)

                self.assertTrue(result["cached"])
                schedule.assert_called_once_with("member")
            finally:
                rt.user_root = original_user_root

    def test_marking_an_inbox_message_read_updates_imap_and_local_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [{"uid": "3", "is_read": False}, {"uid": "2", "is_read": True}],
                    "total": 2,
                    "unread_count": 1,
                    "read_count": 1,
                    "counts": {"all": 2, "unread": 1, "read": 1},
                })

                class FakeBox:
                    def __init__(self):
                        self.selected = None
                        self.store_call = None

                    def select(self, folder, readonly=False):
                        self.selected = (folder, readonly)
                        return "OK", []

                    def uid(self, command, uid, flag, value):
                        self.store_call = (command, uid, flag, value)
                        return "OK", []

                    def logout(self):
                        pass

                box = FakeBox()
                with patch.object(rt, "imap_connect", return_value=box):
                    result = rt.mark_inbox_message_read("member", "3")

                self.assertTrue(result["ok"])
                self.assertEqual(box.selected, ("INBOX", False))
                self.assertEqual(box.store_call, ("store", "3", "+FLAGS.SILENT", "(\\Seen)"))
                cached = rt.read_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, 0)
                self.assertTrue(cached["messages"][0]["is_read"])
                self.assertEqual(cached["unread_count"], 0)
                self.assertEqual(cached["read_count"], 2)
                self.assertEqual(cached["counts"], {"all": 2, "unread": 0, "read": 2})
            finally:
                rt.user_root = original_user_root

    def test_cached_inbox_includes_ready_details_for_first_visible_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [{"uid": "3", "subject": "摘要"}],
                    "period_start": "2026-07-20",
                })
                rt.write_mail_cache("member", "detail_inbox_3", {
                    "message": {
                        "uid": "3",
                        "subject": "完整主题",
                        "body": "已缓存的邮件正文",
                        "attachments": [],
                    },
                })
                with patch.object(rt, "schedule_user_inbox_prefetch"):
                    result = rt.list_inbox_messages("member", 20, refresh=False)

                self.assertEqual(result["messages"][0]["body"], "已缓存的邮件正文")
                self.assertEqual(result["messages"][0]["subject"], "完整主题")
            finally:
                rt.user_root = original_user_root

    def test_cached_html_detail_uses_clean_text_for_list_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {
                    "messages": [{"uid": "3", "subject": "欢迎邮件"}],
                })
                rt.write_mail_cache("member", "detail_inbox_3", {
                    "message": {
                        "uid": "3",
                        "preview": "table.customTableClassName {display: table;}",
                        "body_html": "table.customTableClassName {display: table;}<p>欢迎新同事</p>",
                        "attachments": [],
                    },
                })
                with patch.object(rt, "schedule_user_inbox_prefetch"):
                    result = rt.list_inbox_messages("member", 20, refresh=False)

                self.assertEqual(result["messages"][0]["preview"], "欢迎新同事")
            finally:
                rt.user_root = original_user_root

    def test_cached_inbox_includes_ready_details_beyond_first_five_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                messages = [{"uid": str(index), "subject": f"摘要 {index}"} for index in range(1, 7)]
                rt.write_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, {"messages": messages})
                rt.write_mail_cache("member", "detail_inbox_6", {
                    "message": {"uid": "6", "body": "第六封正文", "attachments": []},
                })
                with patch.object(rt, "schedule_user_inbox_prefetch"):
                    result = rt.list_inbox_messages("member", 20, refresh=False)

                self.assertEqual(result["messages"][5]["body"], "第六封正文")
            finally:
                rt.user_root = original_user_root

    def test_prefetch_reads_recent_month_and_writes_shared_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_user_root = rt.user_root
            try:
                rt.user_root = lambda username: Path(tmp) / username
                with patch.object(rt, "imap_settings", return_value={"host": "imap.example.com", "user": "u", "password": "p"}), patch.object(
                    rt, "list_inbox_messages", return_value={"ok": True, "messages": [{"uid": "latest"}]}
                ) as list_mail, patch.object(rt, "prefetch_inbox_message_details", return_value=1):
                    result = rt.prefetch_user_inbox_recent_month("member")

                self.assertTrue(result["ok"])
                self.assertEqual(list_mail.call_args.kwargs["limit"] if "limit" in list_mail.call_args.kwargs else list_mail.call_args.args[1], rt.MAILBOX_RECENT_MONTH_LIMIT)
                cached = rt.read_mail_cache("member", rt.MAILBOX_RECENT_MONTH_CACHE, 0)
                self.assertEqual(cached["messages"][0]["uid"], "latest")
            finally:
                rt.user_root = original_user_root

    def test_local_mail_part_urls_are_valid_detail_cache_entries(self):
        cached = {
            "message": {
                "body_html": '<img src="/api/mailbox-part?uid=1&part=part1">',
                "attachments": [{"name": "附件.pdf", "download_url": "/api/mailbox-part?uid=1&part=part1&download=1"}],
            },
        }
        self.assertFalse(rt.mail_detail_cache_is_stale(cached))

    def test_server_starts_the_mail_prefetch_worker(self):
        server = (Path(__file__).resolve().parents[2] / "backend" / "server.py").read_text(encoding="utf-8")
        self.assertIn("threading.Thread(target=mail_inbox_auto_worker, daemon=True).start()", server)


if __name__ == "__main__":
    unittest.main()
