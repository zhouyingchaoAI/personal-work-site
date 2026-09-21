"""Password-reset tokens must be single-use and never disclose account existence."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import runtime


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self._tmp.name) / "config.json"
        self._orig_cfg = runtime.CONFIG_PATH
        self._orig_sessions = runtime.SESSIONS
        runtime.CONFIG_PATH = self.cfg_path
        runtime.SESSIONS = {"existing-session": "alice"}
        runtime.PASSWORD_RESET_TOKENS.clear()
        self.cfg_path.write_text(json.dumps({"users": [{
            "username": "alice",
            "password": runtime.hash_password("old-password"),
            "name": "Alice",
            "email": "alice@example.com",
            "role": "member",
        }]}, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        runtime.CONFIG_PATH = self._orig_cfg
        runtime.SESSIONS = self._orig_sessions
        runtime.PASSWORD_RESET_TOKENS.clear()
        self._tmp.cleanup()

    def _captcha_payload(self):
        captcha = runtime.create_password_reset_captcha()
        code = re.search(r">([A-Z0-9]{5})</text>", captcha["svg"]).group(1)
        return {"captcha_id": captcha["captcha_id"], "captcha": code}

    def test_bound_email_can_reset_password_and_invalidates_sessions(self):
        sent = []
        with patch.object(runtime, "send_password_reset_email", side_effect=lambda address, code: sent.append((address, code))):
            result = runtime.request_password_reset({"identifier": "alice@example.com", **self._captcha_payload()})
        self.assertTrue(result["ok"])
        self.assertEqual(sent[0][0], "alice@example.com")

        result = runtime.confirm_password_reset({
            "identifier": "alice@example.com", "code": sent[0][1], "new_password": "new-password",
        })
        self.assertTrue(result["ok"])
        self.assertIsNone(runtime.find_user("alice", "old-password"))
        self.assertIsNotNone(runtime.find_user("alice", "new-password"))
        self.assertNotIn("existing-session", runtime.SESSIONS)

    def test_request_for_unknown_identifier_has_generic_success_and_sends_nothing(self):
        with patch.object(runtime, "send_password_reset_email") as sender:
            result = runtime.request_password_reset({"identifier": "nobody@example.com", **self._captcha_payload()})
        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "如账号已绑定邮箱，验证码已发送，请查收。")
        sender.assert_not_called()

    def test_company_email_is_default_when_user_has_not_overridden_it(self):
        account = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        account["users"][0].pop("email")
        self.cfg_path.write_text(json.dumps(account), encoding="utf-8")
        sent = []
        with patch.object(runtime, "send_password_reset_email", side_effect=lambda address, code: sent.append((address, code))):
            runtime.request_password_reset({"identifier": "alice", **self._captcha_payload()})
        self.assertEqual(sent[0][0], "alice@chencytech.com")

    def test_configured_company_mailbox_is_preferred_as_reset_destination(self):
        config = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        config["users"][0].pop("email")
        config["user_mail_settings"] = {"alice": {"user_email": "alice.office@chencytech.com"}}
        self.cfg_path.write_text(json.dumps(config), encoding="utf-8")
        sent = []
        with patch.object(runtime, "send_password_reset_email", side_effect=lambda address, code: sent.append((address, code))):
            runtime.request_password_reset({"identifier": "alice", **self._captcha_payload()})
        self.assertEqual(sent[0][0], "alice.office@chencytech.com")

    def test_code_cannot_be_reused(self):
        sent = []
        with patch.object(runtime, "send_password_reset_email", side_effect=lambda _address, code: sent.append(code)):
            runtime.request_password_reset({"identifier": "alice", **self._captcha_payload()})
        runtime.confirm_password_reset({"identifier": "alice", "code": sent[0], "new_password": "new-password"})
        with self.assertRaisesRegex(ValueError, "验证码无效或已过期"):
            runtime.confirm_password_reset({"identifier": "alice", "code": sent[0], "new_password": "another-password"})


if __name__ == "__main__":
    unittest.main()
