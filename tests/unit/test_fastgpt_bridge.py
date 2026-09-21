"""Unit coverage for FastGPT provisioning without requiring Docker services."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import runtime as rt


class FastGptBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_config = rt.CONFIG_PATH
        rt.CONFIG_PATH = Path(self.tmp.name) / "config.json"
        cfg = rt.read_config()
        cfg.update({
            "mcp_secret": "m" * 32,
            "assistant_api_url": "https://models.example.test",
            "assistant_api_key": "test-key",
            "assistant_model": "test-model",
        })
        rt.write_config(cfg)

    def tearDown(self):
        rt.CONFIG_PATH = self.old_config
        self.tmp.cleanup()

    def test_fastgpt_internal_url_carries_identity_and_credential(self):
        url = rt.fastgpt_mcp_url("alice")
        self.assertIn("access_token=" + "m" * 32, url)
        self.assertIn("username=alice", url)

    def test_mcp_accepts_fastgpt_query_credential(self):
        status, body = rt.mcp_handle_post("", "alice", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode(), "m" * 32)
        self.assertEqual(status, 200)
        self.assertIn("tools", body["result"])

    def test_existing_collection_is_updated_not_duplicated(self):
        calls = []

        def request(path, payload, token, timeout=45):
            calls.append((path, payload))
            if path.endswith("getTools"):
                return [{"name": "utils.get_date"}]
            if path.endswith("/list"):
                return [{"_id": "existing-app", "name": "办公助手 MCP 工具", "type": "toolSet"}]
            return {}

        with patch.object(rt, "_fastgpt_token", return_value="token"), patch.object(rt, "_fastgpt_request", side_effect=request):
            result = rt.sync_fastgpt_mcp("alice")
        self.assertTrue(result["ok"])
        self.assertEqual(result["app_id"], "existing-app")
        self.assertTrue(any(path.endswith("mcpTools/update") for path, _ in calls))

    def test_model_metadata_uses_openai_compatible_endpoint(self):
        metadata = rt._model_metadata({"url": "https://models.example.test", "key": "k", "model": "m"})
        self.assertEqual(metadata["defaultConfig"]["baseUrl"], "https://models.example.test/v1")
        self.assertEqual(metadata["defaultConfig"]["apiKey"], "k")
        self.assertTrue(metadata["isActive"])

    def test_embedding_metadata_uses_platform_endpoint_and_local_marker(self):
        metadata = rt._fastgpt_embedding_metadata({
            "api_url": "http://embedding.example.test:9997",
            "api_key": "",
            "model": "platform-embedding",
        })
        self.assertEqual(metadata["type"], "embedding")
        self.assertEqual(metadata["defaultConfig"]["baseUrl"], "http://embedding.example.test:9997/v1")
        self.assertEqual(metadata["defaultConfig"]["apiKey"], "local-no-auth")
        self.assertTrue(metadata["isActive"])

    def test_tool_intro_explains_agent_connection_and_arguments(self):
        intro = rt._fastgpt_tool_intro({
            "name": "forum.create",
            "description": "创建论坛话题。",
            "inputSchema": {"properties": {"title": {"type": "string", "description": "标题"}}, "required": ["title"]},
        })
        self.assertIn("连接到 Agent 节点", intro)
        self.assertIn("title（string，必填）：标题", intro)
        self.assertIn("注意：", intro)

    def test_aiproxy_model_upsert_uses_fastgpt_visible_model_type(self):
        calls = []
        with patch.object(rt, "_aiproxy_request", side_effect=lambda *args, **kwargs: calls.append((args, kwargs))):
            rt._aiproxy_upsert_model("platform-embedding", 3, {"max_input_tokens": 8192})
        args, _ = calls[0]
        self.assertEqual(args[0], "model_config/platform-embedding")
        self.assertEqual(args[1], "POST")
        self.assertEqual(args[2]["type"], 3)
        self.assertEqual(args[2]["owner"], "办公助手平台")


if __name__ == "__main__":
    unittest.main()
