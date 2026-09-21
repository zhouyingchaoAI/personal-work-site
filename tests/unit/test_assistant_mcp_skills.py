"""Regression coverage guarding assistant ↔ MCP skill parity.

Newer assistants (智能写作 / 会议 / 知识库 / 报销) must keep matching MCP skills so
the MCP surface never drifts behind the product. These tests assert the skills are
registered, expose valid MCP tool schemas, and that the read-only query skills
dispatch cleanly against an isolated, empty data directory.
"""
import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt


# 每个助手模块必须具备的 MCP skill（升级助手时同步更新这里，逼迫补齐 MCP）。
ASSISTANT_SKILLS = {
    "出差报告": ["trip.prefill", "trip.compose", "trip.preview", "trip.send_confirmed"],
    "智能写作": [
        "writing.uploads", "writing.templates", "writing.outline", "writing.generate",
        "writing.rewrite", "writing.history", "writing.get", "writing.export",
    ],
    "会议": ["meeting.list", "meeting.get", "meeting.summarize", "meeting.translate", "meeting.save", "meeting.delete"],
    "知识库": ["knowledge.datasets", "knowledge.docs", "knowledge.search", "knowledge.ask", "knowledge.delete"],
    "报销": [
        "reimbursement.searches", "reimbursement.search_detail", "reimbursement.outputs",
        "reimbursement.scan", "reimbursement.merge", "reimbursement.download_zip",
    ],
}

# 无需网络 / 大模型即可安全执行的只读查询 skill。
SAFE_QUERY_SKILLS = [
    "writing.uploads", "writing.templates", "writing.history",
    "meeting.list",
    "knowledge.datasets", "knowledge.docs",
    "reimbursement.searches", "reimbursement.outputs",
]


class AssistantMcpSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig_config_path = rt.CONFIG_PATH
        self._orig_user_data_dir = rt.USER_DATA_DIR
        rt.CONFIG_PATH = tmp / "config.json"
        rt.USER_DATA_DIR = tmp / "user_data"
        rt.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._user = "tester"

    def tearDown(self):
        rt.CONFIG_PATH = self._orig_config_path
        rt.USER_DATA_DIR = self._orig_user_data_dir
        self._tmp.cleanup()

    def test_all_assistant_skills_are_registered(self):
        names = {s["name"] for s in rt.skill_defs()}
        for module, skills in ASSISTANT_SKILLS.items():
            for skill in skills:
                self.assertIn(skill, names, f"{module} 缺少 MCP skill：{skill}")

    def test_every_skill_exposes_valid_mcp_tool_schema(self):
        tools = rt._mcp_tools_list()
        by_name = {t["name"]: t for t in tools}
        for skills in ASSISTANT_SKILLS.values():
            for skill in skills:
                self.assertIn(skill, by_name, skill)
                schema = by_name[skill]["inputSchema"]
                self.assertEqual(schema.get("type"), "object")
                self.assertIsInstance(schema.get("properties"), dict)
                self.assertTrue(by_name[skill]["description"])

    def test_safe_query_skills_dispatch_on_empty_data(self):
        for skill in SAFE_QUERY_SKILLS:
            result = rt.execute_skill(skill, {}, self._user, source="mcp")
            self.assertIsInstance(result, dict, skill)
            self.assertTrue(result.get("ok"), f"{skill} 未返回 ok：{result}")

    def test_skill_modules_cover_the_new_assistants(self):
        modules = {s.get("module") for s in rt.skill_defs()}
        for module in ASSISTANT_SKILLS:
            self.assertIn(module, modules)


if __name__ == "__main__":
    unittest.main()
