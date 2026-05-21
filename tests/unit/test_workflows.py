"""Tests for the Workflow Engine.

Covers: workflow definition loading, variable interpolation,
instance lifecycle, confirmation gates, error recovery, and persistence.
"""
import json
import tempfile
import unittest
from pathlib import Path

from backend import db
from backend import workflows as wf


class WorkflowEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        db.init_db(self.db_path)
        wf._db_connect = lambda: db.connect(self.db_path)
        wf._init_db = lambda: db.init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_workflows(self):
        workflows = wf.list_workflows()
        self.assertGreaterEqual(len(workflows), 2)
        ids = [w["id"] for w in workflows]
        self.assertIn("weekly.from_diary", ids)
        self.assertIn("mail.summarize_and_reply", ids)

    def test_get_workflow(self):
        w = wf.get_workflow("weekly.from_diary")
        self.assertIsNotNone(w)
        self.assertEqual(w["id"], "weekly.from_diary")
        self.assertIn("steps", w)
        self.assertGreaterEqual(len(w["steps"]), 4)

    def test_interpolate_simple(self):
        context = {"input": {"name": "周报"}, "step1": {"result": {"value": 42}}}
        args = wf.interpolate_arguments(
            {"title": "{{input.name}}", "count": "{{step1.result.value}}"},
            context,
        )
        self.assertEqual(args["title"], "周报")
        self.assertEqual(args["count"], 42)

    def test_interpolate_with_default(self):
        context = {"input": {}}
        args = wf.interpolate_arguments(
            {"tone": "{{input.tone|professional}}"},
            context,
        )
        self.assertEqual(args["tone"], "professional")

    def test_interpolate_nested_dict(self):
        context = {"step1": {"result": {"data": {"name": "测试"}}}}
        args = wf.interpolate_arguments(
            {"payload": {"name": "{{step1.result.data.name}}"}},
            context,
        )
        self.assertEqual(args["payload"]["name"], "测试")

    def test_interpolate_missing_raises(self):
        context = {"input": {}}
        with self.assertRaises(ValueError):
            wf.interpolate_arguments({"name": "{{input.missing}}"}, context)

    def test_instance_lifecycle(self):
        inst = wf.WorkflowInstance("weekly.from_diary", "zhouyingchao", {"key": "val"})
        self.assertTrue(inst.instance_id.startswith("wf_"))
        self.assertEqual(inst.status, "pending")
        self.assertEqual(inst.inputs, {"key": "val"})

        # Save and load
        wf._save_instance(inst)
        loaded = wf._load_instance(inst.instance_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.workflow_id, "weekly.from_diary")
        self.assertEqual(loaded.user_id, "zhouyingchao")
        self.assertEqual(loaded.status, "pending")

    def test_execute_workflow_not_found(self):
        result = wf.execute_workflow("nonexistent", "zhouyingchao")
        self.assertFalse(result["ok"])
        self.assertIn("不存在", result["error"])

    def test_execute_workflow_runs_to_completion(self):
        # Create a simple test workflow that calls utils.get_date
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.simple"] = {
            "id": "test.simple",
            "name": "测试工作流",
            "steps": [
                {"id": "get_date", "skill": "utils.get_date", "arguments": {}},
            ],
            "on_error": "pause",
            "requires_confirmation_at": [],
        }
        result = wf.execute_workflow("test.simple", "zhouyingchao")
        wf._BUILTIN_WORKFLOWS = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["instance"]["status"], "completed")
        self.assertIn("get_date", result["instance"]["step_results"])

    def test_execute_workflow_with_confirmation(self):
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.confirm"] = {
            "id": "test.confirm",
            "name": "测试确认门",
            "steps": [
                {"id": "step1", "skill": "utils.get_date", "arguments": {}},
                {"id": "step2", "skill": "utils.get_date", "arguments": {}},
            ],
            "on_error": "pause",
            "requires_confirmation_at": ["step2"],
        }
        result = wf.execute_workflow("test.confirm", "zhouyingchao")
        wf._BUILTIN_WORKFLOWS = original

        self.assertTrue(result["ok"])
        self.assertEqual(result["instance"]["status"], "paused")
        self.assertTrue(result["requires_confirmation"])
        self.assertEqual(result["confirmation_context"]["step_id"], "step2")
        # step1 should have been executed
        self.assertIn("step1", result["instance"]["step_results"])
        # step2 should not have been executed yet
        self.assertNotIn("step2", result["instance"]["step_results"])

    def test_confirm_and_resume(self):
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.resume"] = {
            "id": "test.resume",
            "name": "测试恢复",
            "steps": [
                {"id": "step1", "skill": "utils.get_date", "arguments": {}},
                {"id": "step2", "skill": "utils.get_date", "arguments": {}},
            ],
            "on_error": "pause",
            "requires_confirmation_at": ["step2"],
        }
        # Start workflow
        r1 = wf.execute_workflow("test.resume", "zhouyingchao")
        inst_id = r1["instance"]["instance_id"]

        # Confirm and resume
        r2 = wf.confirm_and_resume(inst_id, "zhouyingchao", confirmed=True)
        wf._BUILTIN_WORKFLOWS = original

        self.assertTrue(r2["ok"])
        self.assertEqual(r2["instance"]["status"], "completed")
        self.assertIn("step1", r2["instance"]["step_results"])
        self.assertIn("step2", r2["instance"]["step_results"])

    def test_confirm_cancel(self):
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.cancel"] = {
            "id": "test.cancel",
            "name": "测试取消",
            "steps": [
                {"id": "step1", "skill": "utils.get_date", "arguments": {}},
                {"id": "step2", "skill": "utils.get_date", "arguments": {}},
            ],
            "on_error": "pause",
            "requires_confirmation_at": ["step2"],
        }
        r1 = wf.execute_workflow("test.cancel", "zhouyingchao")
        inst_id = r1["instance"]["instance_id"]

        r2 = wf.confirm_and_resume(inst_id, "zhouyingchao", confirmed=False)
        wf._BUILTIN_WORKFLOWS = original

        self.assertFalse(r2["ok"])
        self.assertEqual(r2["instance"]["status"], "failed")

    def test_list_user_workflows(self):
        wf.execute_workflow("weekly.from_diary", "zhouyingchao")
        instances = wf.list_user_workflows("zhouyingchao")
        self.assertGreaterEqual(len(instances), 1)
        self.assertEqual(instances[0]["workflow_id"], "weekly.from_diary")

    def test_workflow_api_list(self):
        result = wf.workflows_api({"action": "list"}, "zhouyingchao")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["workflows"]), 2)

    def test_workflow_api_run(self):
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.api"] = {
            "id": "test.api",
            "name": "测试 API",
            "steps": [{"id": "s1", "skill": "utils.get_date", "arguments": {}}],
            "on_error": "pause",
            "requires_confirmation_at": [],
        }
        result = wf.workflows_api(
            {"action": "run", "workflow_id": "test.api", "inputs": {}},
            "zhouyingchao",
        )
        wf._BUILTIN_WORKFLOWS = original
        self.assertTrue(result["ok"])
        self.assertEqual(result["instance"]["status"], "completed")

    def test_workflow_api_status(self):
        original = wf._BUILTIN_WORKFLOWS.copy()
        wf._BUILTIN_WORKFLOWS["test.status"] = {
            "id": "test.status",
            "name": "测试状态",
            "steps": [{"id": "s1", "skill": "utils.get_date", "arguments": {}}],
            "on_error": "pause",
            "requires_confirmation_at": [],
        }
        r1 = wf.workflows_api(
            {"action": "run", "workflow_id": "test.status"},
            "zhouyingchao",
        )
        inst_id = r1["instance"]["instance_id"]
        r2 = wf.workflows_api(
            {"action": "status", "instance_id": inst_id},
            "zhouyingchao",
        )
        wf._BUILTIN_WORKFLOWS = original
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["instance"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
