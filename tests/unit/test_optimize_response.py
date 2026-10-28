import ast
import json
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch


class OptimizeResponseTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / "backend"
        self.namespace = {"json": json, "urllib": urllib}
        for filename, names in (
            ("core.py", {"assistant_generation_payload"}),
            ("text_tools.py", {"optimize_text", "normalize_assistant_output"}),
        ):
            tree = ast.parse((root / filename).read_text())
            tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
            exec(compile(tree, filename, "exec"), self.namespace)
        self.namespace["assistant_settings"] = lambda: {
            "url": "https://example.test", "key": "test", "model": "MiniMax-M2.7", "prompt": "润色",
        }
        self.namespace["local_optimize_text"] = lambda text: text

    def optimize(self, response):
        mocked = MagicMock()
        mocked.__enter__.return_value.read.return_value = json.dumps(response).encode()
        with patch("urllib.request.urlopen", return_value=mocked):
            return self.namespace["optimize_text"]({"text": "完成联调"})

    def test_minimax_supported_reasoning_level(self):
        build = self.namespace["assistant_generation_payload"]
        self.assertEqual(build({}, {"model": "MiniMax-M2.7"})["reasoning_effort"], "low")
        self.assertEqual(build({}, {"model": "MiniMax-M2.7", "reasoning_effort": "high"})["reasoning_effort"], "high")
        self.assertEqual(build({}, {"model": "other"})["reasoning_effort"], "off")

    def test_success_preserves_text(self):
        result = self.optimize({"choices": [{"message": {"content": "完成接口联调。"}}]})
        self.assertEqual(result["mode"], "api")
        self.assertEqual(result["text"], "完成接口联调。")

    def test_provider_error_is_reported(self):
        result = self.optimize({"base_resp": {"status_code": 2013, "status_msg": "invalid params"}, "choices": None})
        self.assertEqual(result["mode"], "local_fallback")
        self.assertIn("invalid params", result["warning"])

    def test_missing_or_empty_answers_use_fallback(self):
        for response in (None, {}, {"choices": None}, {"choices": []}, {"choices": [None]}, {"choices": [{"message": None}]}, {"choices": [{"message": {"content": " "}}]}):
            with self.subTest(response=response):
                result = self.optimize(response)
                self.assertEqual(result["mode"], "local_fallback")
                self.assertNotIn("NoneType", result["warning"])


if __name__ == "__main__":
    unittest.main()
