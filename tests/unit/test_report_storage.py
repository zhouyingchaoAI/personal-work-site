import base64
import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt


class ReportStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_user_data_dir = rt.USER_DATA_DIR
        self.old_report_dir = rt.REPORT_DIR
        self.old_generated_dir = rt.GENERATED_DIR
        base = Path(self.tmp.name)
        rt.USER_DATA_DIR = base / "user_data"
        rt.REPORT_DIR = base / "shared_reports"
        rt.GENERATED_DIR = base / "generated"

    def tearDown(self):
        rt.USER_DATA_DIR = self.old_user_data_dir
        rt.REPORT_DIR = self.old_report_dir
        rt.GENERATED_DIR = self.old_generated_dir
        self.tmp.cleanup()

    def test_generated_report_path_uses_kind_temp_dir_and_overwrites_name(self):
        name = "易鲁剑工作周报2026.5.18-2026.5.22.xlsx"
        first = rt.generated_report_path(name, "yilujian", "weekly")
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_text("old", encoding="utf-8")

        second = rt.generated_report_path(name, "yilujian", "weekly")

        self.assertEqual(first, second)
        self.assertEqual(second.parent, rt.user_generated_kind_dir("yilujian", "weekly"))
        self.assertNotIn("-生成", second.name)

    def test_history_upload_path_uses_kind_history_dir_and_overwrites_name(self):
        name = "出差报告-20260518-0520-易鲁剑.docx"
        first = rt.unique_report_path(name, "yilujian")
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_text("old", encoding="utf-8")

        second = rt.unique_report_path(name, "yilujian")

        self.assertEqual(first, second)
        self.assertEqual(second.parent, rt.user_report_kind_dir("yilujian", "trip"))
        self.assertNotIn("-上传", second.name)

    def test_promote_sent_report_moves_temp_file_to_history_and_replaces_same_name(self):
        name = "易鲁剑工作周报2026.5.18-2026.5.22.xlsx"
        source = rt.user_generated_kind_dir("yilujian", "weekly") / name
        target = rt.user_report_kind_dir("yilujian", "weekly") / name
        source.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("new", encoding="utf-8")
        target.write_text("old", encoding="utf-8")

        promoted = rt.promote_sent_report(name, "yilujian")

        self.assertEqual(promoted["path"], str(target))
        self.assertFalse(source.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_weekly_period_filename_drops_leading_zeroes(self):
        self.assertEqual(
            rt.normalize_report_period_name("2026.05.18-2026.05.22"),
            "2026.5.18-2026.5.22",
        )

    def test_legacy_auto_numbered_history_files_are_hidden(self):
        base = rt.user_report_dir("yilujian")
        base.mkdir(parents=True, exist_ok=True)
        visible = base / "易鲁剑工作周报2026.5.18-2026.5.22.xlsx"
        legacy = base / "易鲁剑工作周报2026.5.18-2026.5.22-生成1.xlsx"
        visible.write_text("visible", encoding="utf-8")
        legacy.write_text("legacy", encoding="utf-8")

        names = [item["name"] for item in rt.report_files("yilujian")]

        self.assertIn(visible.name, names)
        self.assertNotIn(legacy.name, names)

    def test_build_message_appends_current_user_signature(self):
        old_read_config = rt.read_config
        try:
            rt.read_config = lambda: {
                "users": [{"username": "yilujian", "password": "x", "role": "member", "name": "易鲁剑"}],
                "user_mail_settings": {
                    "yilujian": {
                        "user_email": "yilujian@example.com",
                        "email_signature": "易鲁剑\nE-mail: yilujian@example.com",
                    }
                },
            }

            msg = rt.build_message(
                {"to": "leader@example.com", "subject": "测试", "body": "正文"},
                "yilujian",
            )

            body = msg.get_content()
            self.assertIn("正文", body)
            self.assertIn("易鲁剑", body)
            self.assertIn("E-mail: yilujian@example.com", body)
        finally:
            rt.read_config = old_read_config

    def test_html_signature_check_does_not_match_attachment_name(self):
        old_read_config = rt.read_config
        try:
            rt.read_config = lambda: {
                "users": [{"username": "yilujian", "password": "x", "role": "member", "name": "易鲁剑"}],
                "user_mail_settings": {
                    "yilujian": {
                        "user_email": "yilujian@example.com",
                        "email_signature": "易鲁剑",
                    }
                },
            }

            html = rt.append_email_signature_html("<p>附件：易鲁剑工作周报.xlsx</p>", "yilujian")

            self.assertTrue(html.endswith("<p>易鲁剑</p>"))
        finally:
            rt.read_config = old_read_config

    def test_generate_weekly_without_existing_template_creates_initial_workbook(self):
        old_read_config = rt.read_config
        old_newest_any = rt.newest_any
        try:
            rt.read_config = lambda: {
                "users": [{"username": "newuser", "password": "x", "role": "member", "name": "新用户"}],
                "user_mail_settings": {},
            }
            rt.newest_any = lambda *args, **kwargs: None

            path = rt.generate_weekly(
                {
                    "period": "2026.05.18-2026.05.22",
                    "weekly_summary": [{"category": "测试", "content": "首次生成", "status": "完成", "plan": ""}],
                    "weekly_follow": [],
                    "weekly_next": [],
                },
                "newuser",
            )

            self.assertTrue(path.exists())
            self.assertEqual(path.name, "新用户工作周报2026.5.18-2026.5.22.xlsx")
            self.assertEqual(path.parent, rt.user_generated_kind_dir("newuser", "weekly"))
        finally:
            rt.read_config = old_read_config
            rt.newest_any = old_newest_any

    def test_generate_trip_without_existing_template_creates_initial_docx(self):
        old_read_config = rt.read_config
        old_newest = rt.newest
        try:
            rt.read_config = lambda: {
                "users": [{"username": "newuser", "password": "x", "role": "member", "name": "新用户"}],
                "user_mail_settings": {},
            }
            rt.newest = lambda *args, **kwargs: None

            path = rt.generate_trip(
                {
                    "department": "场景研究院",
                    "location": "长沙",
                    "trip_start": "2026-05-18",
                    "trip_end": "2026-05-20",
                    "purpose": "首次出差",
                    "itinerary": "客户现场",
                    "details": "完成沟通",
                    "work_approach": "先试点再推广",
                    "issues": "无",
                    "suggestions": "持续跟进",
                },
                "newuser",
            )

            self.assertTrue(path.exists())
            self.assertEqual(path.name, "出差报告-20260518-0520-新用户.docx")
            self.assertEqual(path.parent, rt.user_generated_kind_dir("newuser", "trip"))
            preview = rt.preview_docx(path)
            self.assertIn("新用户", preview)
            self.assertIn("首次出差", preview)
            self.assertIn("工作思路", preview)
            self.assertIn("先试点再推广", preview)
        finally:
            rt.read_config = old_read_config
            rt.newest = old_newest

    def test_weekly_prefill_new_user_ignores_global_template(self):
        raw = b"template bytes"
        payload = {
            "kind": "weekly",
            "file": {
                "name": "edited.xlsx",
                "data": base64.b64encode(raw).decode("ascii"),
            },
        }
        rt.save_report_template(payload, "zhouyingchao")

        prefill = rt.weekly_prefill("newuser")

        self.assertEqual(prefill["weekly_summary"], "")
        self.assertEqual(prefill["summary_rows"], [])
        self.assertEqual(prefill["source"], "")

    def test_trip_prefill_new_user_ignores_other_users_reports(self):
        prefill = rt.trip_prefill("newuser")

        self.assertEqual(prefill["source"], "")
        self.assertNotIn("work_approach", prefill)

    def test_report_template_upload_and_delete_are_global(self):
        raw = b"template bytes"
        payload = {
            "kind": "weekly",
            "file": {
                "name": "edited.xlsx",
                "data": base64.b64encode(raw).decode("ascii"),
            },
        }

        saved = rt.save_report_template(payload, "newuser")
        path = Path(saved["template"]["path"])

        self.assertEqual(path, rt.report_template_path("weekly"))
        self.assertEqual(path.read_bytes(), raw)
        info = rt.report_template_info("newuser")
        self.assertTrue(info["templates"]["weekly"]["configured"])

        deleted = rt.delete_report_template({"kind": "weekly"}, "newuser")
        self.assertFalse(rt.report_template_path("weekly").exists())
        self.assertFalse(deleted["templates"]["weekly"]["configured"])


if __name__ == "__main__":
    unittest.main()
