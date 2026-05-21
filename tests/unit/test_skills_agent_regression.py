import unittest

import backend.runtime as rt


class SkillDefinitionRegressionTests(unittest.TestCase):
    def test_skill_names_are_unique_and_have_required_fields(self):
        skills = rt.skill_defs()
        names = [item.get("name") for item in skills]

        self.assertGreaterEqual(len(skills), 10)
        self.assertEqual(len(names), len(set(names)))

        required = {"name", "module", "title", "description", "parameters", "safe"}
        for skill in skills:
            with self.subTest(skill=skill.get("name")):
                self.assertTrue(required.issubset(skill.keys()))
                self.assertIsInstance(skill["parameters"], dict)
                self.assertIsInstance(skill["safe"], bool)

    def test_parse_skill_call_supports_plain_and_markdown_json(self):
        raw = '{"reply":"准备获取日期","skill_call":{"name":"utils.get_date","arguments":{"format":"YYYY-MM-DD"}}}'
        wrapped = "```json\n" + raw + "\n```"

        for text in (raw, wrapped):
            with self.subTest(text=text[:12]):
                call = rt.parse_skill_call(text)
                self.assertEqual(call["reply"], "准备获取日期")
                self.assertEqual(call["name"], "utils.get_date")
                self.assertEqual(call["arguments"], {"format": "YYYY-MM-DD"})

    def test_parse_skill_call_returns_none_for_plain_answer(self):
        self.assertIsNone(rt.parse_skill_call("这只是普通回答，不需要调用 Skill。"))

    def test_execute_get_date_skill_returns_expected_keys(self):
        result = rt.execute_skill("utils.get_date", {"format": "YYYY-MM-DD"}, "tester")

        self.assertTrue(result["ok"])
        for key in ("today", "weekday", "week_range", "week_start", "week_end", "year"):
            self.assertIn(key, result)

    def test_unknown_skill_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "未知 Skill"):
            rt.execute_skill("missing.skill", {}, "tester")

    def test_report_names_use_current_user_display_name(self):
        old_read_config = rt.read_config
        try:
            rt.read_config = lambda: {
                "sender_name": "默认发件人",
                "users": [
                    {"username": "alice", "password": "x", "role": "member", "name": "李雷"},
                ],
            }
            self.assertEqual(rt.display_name_for_user("alice"), "李雷")
            self.assertEqual(rt.safe_display_name("alice"), "李雷")
        finally:
            rt.read_config = old_read_config


if __name__ == "__main__":
    unittest.main()
