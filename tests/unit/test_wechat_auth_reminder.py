"""公众号采集授权状态必须可供智能办公平台展示提醒。"""
import io
import json
import unittest

from backend import runtime as rt


class _Response:
    headers = type("Headers", (), {"get_content_charset": lambda self: "utf-8"})()

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class WechatAuthReminderTests(unittest.TestCase):
    def test_expired_exporter_session_is_exposed_as_platform_reminder(self):
        original = rt.urllib.request.build_opener

        class Opener:
            def open(self, *_args, **_kwargs):
                return _Response({"ok": False, "error": "微信公众号后台登录已过期，请重新扫码登录"})

        rt.urllib.request.build_opener = lambda *_args: Opener()
        try:
            result = rt.wechat_auth_status()
        finally:
            rt.urllib.request.build_opener = original

        self.assertFalse(result["ok"])
        self.assertTrue(result["expired"])
        self.assertIn("重新扫码", result["message"])


if __name__ == "__main__":
    unittest.main()
