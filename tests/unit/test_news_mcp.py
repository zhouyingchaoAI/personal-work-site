"""Regression tests for the news / WeChat official-account skills exposed over MCP.

These drive the real MCP JSON-RPC surface (``mcp_handle_post``) rather than the
internal skill dispatcher, so they cover tool discovery, argument schema exposure,
tool execution and Bearer-token auth end to end.
"""
import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt


NEWS_TOOLS = {
    "news.latest",
    "news.personal",
    "news.sources",
    "news.search_wechat",
    "news.subscribe_wechat",
    "news.unsubscribe",
    "news.generate",
}


class NewsMcpTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # 隔离配置与用户数据目录，避免污染真实 config.json / user_data。
        self._orig_config_path = rt.CONFIG_PATH
        self._orig_user_data_dir = rt.USER_DATA_DIR
        rt.CONFIG_PATH = tmp / "config.json"
        rt.USER_DATA_DIR = tmp / "user_data"
        rt.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        # 启用 MCP：写入密钥。
        self._secret = "x" * 32
        cfg = rt.read_config()
        cfg["mcp_secret"] = self._secret
        rt.write_config(cfg)
        self._auth = "Bearer " + self._secret
        self._user = "tester"

    def tearDown(self):
        rt.CONFIG_PATH = self._orig_config_path
        rt.USER_DATA_DIR = self._orig_user_data_dir
        self._tmp.cleanup()

    def _post(self, obj, auth=None):
        status, body = rt.mcp_handle_post(
            self._auth if auth is None else auth,
            self._user,
            json.dumps(obj).encode(),
        )
        return status, body

    def _call(self, name, arguments):
        status, body = self._post({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        self.assertEqual(status, 200)
        result = body["result"]
        payload = json.loads(result["content"][0]["text"])
        return payload, bool(result.get("isError"))

    def test_news_tools_registered_in_tools_list(self):
        status, body = self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(status, 200)
        names = {t["name"] for t in body["result"]["tools"]}
        self.assertTrue(NEWS_TOOLS.issubset(names), NEWS_TOOLS - names)

    def test_subscribe_wechat_schema_exposes_name_and_url(self):
        status, body = self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tool = next(t for t in body["result"]["tools"] if t["name"] == "news.subscribe_wechat")
        props = tool["inputSchema"]["properties"]
        self.assertIn("name", props)
        self.assertIn("url", props)

    def test_subscribe_then_list_via_mcp_call(self):
        payload, is_error = self._call("news.subscribe_wechat", {"name": "新智元"})
        self.assertFalse(is_error)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["subscribed"], "新智元")
        self.assertFalse(payload["already_subscribed"])

        sources, _ = self._call("news.sources", {})
        self.assertEqual(sources["count"], 1)
        self.assertEqual(sources["wechat_accounts"][0]["name"], "新智元")

    def test_subscribe_is_idempotent(self):
        self._call("news.subscribe_wechat", {"name": "新智元"})
        payload, _ = self._call("news.subscribe_wechat", {"name": "新智元"})
        self.assertTrue(payload["already_subscribed"])

    def test_subscribe_rejects_non_wechat_entry_url(self):
        payload, is_error = self._call("news.subscribe_wechat", {"name": "某号", "url": "https://example.com/x"})
        # execute_skill 抛错会被 MCP 封装为 isError 文本结果。
        self.assertTrue(is_error)
        self.assertFalse(payload["ok"])
        self.assertIn("mp.weixin.qq.com", payload["error"])

    def test_unsubscribe_removes_source(self):
        self._call("news.subscribe_wechat", {"name": "新智元"})
        removed, _ = self._call("news.unsubscribe", {"target": "新智元"})
        self.assertTrue(removed["ok"])
        self.assertEqual(removed["removed"], 1)
        sources, _ = self._call("news.sources", {})
        self.assertEqual(sources["count"], 0)

    def test_unsubscribe_missing_target_fails_gracefully(self):
        payload, _ = self._call("news.unsubscribe", {"target": "不存在的号"})
        self.assertFalse(payload["ok"])
        self.assertIn("没有找到", payload["error"])

    def test_bad_bearer_token_is_rejected(self):
        status, _ = self._post(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            auth="Bearer wrong-token",
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
