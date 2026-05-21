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


if __name__ == "__main__":
    unittest.main()
