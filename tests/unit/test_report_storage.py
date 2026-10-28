import base64
import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt
from tests.unit.officedb_testing import db_variant


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
        rt.office_blob_write("reports", source, b"new")
        rt.office_blob_write("reports", target, b"old")

        promoted = rt.promote_sent_report(name, "yilujian")

        self.assertEqual(promoted["path"], str(target))
        self.assertFalse(rt.office_blob_exists("reports", source))
        self.assertEqual(rt.office_blob_read("reports", target), b"new")

    def test_weekly_period_filename_drops_leading_zeroes(self):
        self.assertEqual(
            rt.normalize_report_period_name("2026.05.18-2026.05.22"),
            "2026.5.18-2026.5.22",
        )

    def test_legacy_auto_numbered_history_files_are_hidden(self):
        base = rt.user_report_dir("yilujian")
        visible = base / "易鲁剑工作周报2026.5.18-2026.5.22.xlsx"
        legacy = base / "易鲁剑工作周报2026.5.18-2026.5.22-生成1.xlsx"
        rt.office_blob_write("reports", visible, b"visible")
        rt.office_blob_write("reports", legacy, b"legacy")

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

            self.assertTrue(html.endswith('<div class="email-signature">易鲁剑</div>'))
            self.assertEqual(html.count("易鲁剑"), 2)
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

            self.assertTrue(rt.office_blob_exists("reports", path))
            self.assertEqual(path.name, "新用户工作周报2026.5.18-2026.5.22.xlsx")
            self.assertEqual(path.parent, rt.user_generated_kind_dir("newuser", "weekly"))
        finally:
            rt.read_config = old_read_config
            rt.newest_any = old_newest_any

    def test_generate_weekly_reuses_same_period_output_without_copying_file_onto_itself(self):
        """再次生成同一周期周报时，已生成文件不能同时充当复制源和目标。"""
        from openpyxl import Workbook

        old_read_config = rt.read_config
        old_newest_any = rt.newest_any
        old_newest = rt.newest
        try:
            rt.read_config = lambda: {
                "users": [{"username": "zhouyingchao", "password": "x", "role": "member", "name": "周颖超"}],
                "user_mail_settings": {},
            }
            output = rt.generated_report_path("周颖超工作周报2026.8.17-2026.8.21.xlsx", "zhouyingchao", "weekly")
            buffer = __import__("io").BytesIO()
            Workbook().save(buffer)
            rt.office_blob_write("reports", output, buffer.getvalue())
            # 报告列表只剩当前已经生成的同名文件，正是邮件发送页再次生成会遇到的情况。
            rt.newest_any = lambda *args, **kwargs: {"path": str(output)}
            rt.newest = lambda *args, **kwargs: {"path": str(output)}

            result = rt.generate_weekly(
                {"period": "2026.8.17-2026.8.21", "weekly_summary": [], "weekly_follow": [], "weekly_next": []},
                "zhouyingchao",
            )

            self.assertEqual(result, output)
            self.assertTrue(rt.office_blob_exists("reports", result))
        finally:
            rt.read_config = old_read_config
            rt.newest_any = old_newest_any
            rt.newest = old_newest

    def test_generated_weekly_mail_contains_only_current_editor_rows(self):
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
                    "period": "2026.09.07-2026.09.11",
                    # “已删除项目任务”模拟已在编辑页移除，因此不出现在提交数组中。
                    "weekly_summary": [{"category": "保留项目", "content": "完成联调", "status": "完成", "plan": ""}],
                    "weekly_follow": [],
                    "weekly_next": [],
                },
                "newuser",
            )
            draft = rt.compose_draft("weekly", path.name, "newuser")
            mail_content = f"{draft.get('body', '')}\n{draft.get('body_html', '')}"

            self.assertIn("保留项目", mail_content)
            self.assertNotIn("已删除项目任务", mail_content)
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

            self.assertTrue(rt.office_blob_exists("reports", path))
            self.assertEqual(path.name, "出差报告-20260518-0520-新用户.docx")
            self.assertEqual(path.parent, rt.user_generated_kind_dir("newuser", "trip"))
            with rt.office_blob_local("reports", path) as local:
                preview = rt.preview_docx(local)
            draft = rt.compose_draft("trip", path.name, "newuser")
            self.assertIn("首次出差", draft["preview"])
            self.assertEqual(draft["attachment"], path.name)
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
        self.assertEqual(rt.office_blob_read("reports", path), raw)
        info = rt.report_template_info("newuser")
        self.assertTrue(info["templates"]["weekly"]["configured"])
        self.assertEqual(rt.configured_template_path("weekly", "newuser"), path)

        deleted = rt.delete_report_template({"kind": "weekly"}, "newuser")
        self.assertFalse(rt.office_blob_exists("reports", rt.report_template_path("weekly")))
        self.assertIsNone(rt.configured_template_path("weekly", "newuser"))
        self.assertFalse(deleted["templates"]["weekly"]["configured"])


ReportStorageDbModeTests = db_variant(ReportStorageTests)


if __name__ == "__main__":
    unittest.main()
