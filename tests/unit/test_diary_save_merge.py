"""Regression coverage for incremental diary saves from OpenClaw/WeChat."""
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class DiarySaveMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_user_data_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name) / "user_data"
        rt.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        rt.USER_DATA_DIR = self.old_user_data_dir
        self.tmp.cleanup()

    def test_incremental_save_keeps_work_when_later_adding_tomorrow_plan(self):
        username = "wechat-user"
        date = "2026-08-11"
        rt.save_diary({"date": date, "today_work": "完成应急指挥平台技术文件"}, username)
        result = rt.save_diary({"date": date, "tomorrow_plan": "上午公司会议；下午沟通测试"}, username)

        diary = result["diary"]
        self.assertEqual(diary["today_work"], "完成应急指挥平台技术文件")
        self.assertEqual(diary["tomorrow_plan"], "上午公司会议；下午沟通测试")
        self.assertEqual(rt.get_diary(date, username)["diary"], diary)

    def test_wechat_parser_keeps_multi_part_plan_out_of_today_work(self):
        call = rt._direct_diary_save_call(
            "帮我记录今天的工作日记：明天上午公司会议；下午去轨道找客户沟通雷达方案测试"
        )

        self.assertEqual(call["arguments"].get("tomorrow_plan"), "明天上午公司会议；下午去轨道找客户沟通雷达方案测试")
        self.assertNotIn("today_work", call["arguments"])

    def test_replace_mode_keeps_web_editor_clear_field_behavior(self):
        username = "web-user"
        date = "2026-08-11"
        rt.save_diary({"date": date, "today_work": "旧内容", "tomorrow_plan": "旧计划"}, username)
        result = rt.save_diary({
            "date": date,
            "today_work": "",
            "tomorrow_plan": "新计划",
            "thoughts": "",
            "replace": True,
        }, username)

        self.assertEqual(result["diary"]["today_work"], "")
        self.assertEqual(result["diary"]["tomorrow_plan"], "新计划")


if __name__ == "__main__":
    unittest.main()


DiarySaveMergeTestsDbMode = db_variant(DiarySaveMergeTests)
