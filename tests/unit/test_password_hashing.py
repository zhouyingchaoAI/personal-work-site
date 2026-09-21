"""Tests for backend account password hashing (pbkdf2) and legacy migration."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import runtime  # loads all modules into one namespace


class PasswordHashingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self._tmp.name) / "config.json"
        # Point core.CONFIG_PATH at a temp file so read_config/write_config are isolated.
        self._orig_cfg = runtime.CONFIG_PATH
        runtime.CONFIG_PATH = self.cfg_path

    def tearDown(self):
        runtime.CONFIG_PATH = self._orig_cfg
        self._tmp.cleanup()

    def _write_users(self, users):
        self.cfg_path.write_text(json.dumps({"users": users}, ensure_ascii=False), encoding="utf-8")

    def _read_users(self):
        return json.loads(self.cfg_path.read_text(encoding="utf-8"))["users"]

    def test_hash_roundtrip(self):
        h = runtime.hash_password("s3cret")
        self.assertTrue(h.startswith("pbkdf2_sha256$"))
        self.assertTrue(runtime.verify_password("s3cret", h))
        self.assertFalse(runtime.verify_password("wrong", h))

    def test_hash_is_salted(self):
        self.assertNotEqual(runtime.hash_password("x"), runtime.hash_password("x"))

    def test_verify_legacy_plaintext(self):
        self.assertTrue(runtime.verify_password("admin123", "admin123"))
        self.assertFalse(runtime.verify_password("nope", "admin123"))

    def test_find_user_with_hashed_password(self):
        self._write_users([{"username": "u1", "password": runtime.hash_password("pw12345"), "role": "member"}])
        self.assertIsNotNone(runtime.find_user("u1", "pw12345"))
        self.assertIsNone(runtime.find_user("u1", "bad"))

    def test_legacy_login_auto_upgrades_to_hash(self):
        self._write_users([{"username": "admin", "password": "admin123", "role": "admin"}])
        # Successful legacy login returns the user...
        self.assertIsNotNone(runtime.find_user("admin", "admin123"))
        # ...and the stored password is now a hash, while still verifying.
        stored = self._read_users()[0]["password"]
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertTrue(runtime.verify_password("admin123", stored))
        self.assertIsNotNone(runtime.find_user("admin", "admin123"))

    def test_wrong_legacy_password_does_not_upgrade(self):
        self._write_users([{"username": "admin", "password": "admin123", "role": "admin"}])
        self.assertIsNone(runtime.find_user("admin", "wrong"))
        self.assertEqual(self._read_users()[0]["password"], "admin123")

    def test_find_user_without_password_returns_user(self):
        self._write_users([{"username": "u1", "password": runtime.hash_password("pw12345")}])
        self.assertIsNotNone(runtime.find_user("u1"))

    def test_change_password_stores_hash(self):
        self._write_users([{"username": "u1", "password": "oldpass", "role": "member"}])
        runtime.change_password({"old_password": "oldpass", "new_password": "newpass1"}, "u1")
        stored = self._read_users()[0]["password"]
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertTrue(runtime.verify_password("newpass1", stored))
        self.assertFalse(runtime.verify_password("oldpass", stored))

    def test_public_user_exposes_organization_profile_without_password(self):
        account = {
            "username": "zhangsan",
            "password": runtime.hash_password("123456"),
            "role": "member",
            "name": "张三",
            "employee_id": "120001",
            "company": "湖南承希科技有限公司",
            "department": "服务解决方案中心 / 服务交付部",
            "position": "交付工程师",
        }
        result = runtime.public_user(account)
        self.assertEqual(result["employee_id"], "120001")
        self.assertEqual(result["company"], "湖南承希科技有限公司")
        self.assertEqual(result["department"], "服务解决方案中心 / 服务交付部")
        self.assertEqual(result["position"], "交付工程师")
        self.assertNotIn("password", result)

    def test_add_user_persists_optional_organization_profile(self):
        self._write_users([{"username": "root", "password": runtime.hash_password("rootpass"), "role": "superadmin"}])
        payload = {
            "username": "newmember",
            "password": "123456",
            "name": "新增成员",
            "role": "member",
            "employee_id": "900001",
            "company": "湖南承希科技有限公司",
            "department": "服务解决方案中心 / 服务交付部",
            "position": "交付工程师",
        }
        with patch.object(runtime, "_provision_gateway_key", return_value=None), patch.object(runtime, "openclaw_sync_user"):
            runtime.add_user(payload, "root")
        created = next(item for item in self._read_users() if item["username"] == "newmember")
        self.assertEqual(created["employee_id"], "900001")
        self.assertEqual(created["company"], "湖南承希科技有限公司")
        self.assertEqual(created["department"], "服务解决方案中心 / 服务交付部")
        self.assertEqual(created["position"], "交付工程师")
        self.assertEqual(created["email"], "newmember@chencytech.com")

    def test_batch_permissions_updates_selected_department_and_delegates_crm_policy(self):
        self._write_users([
            {"username": "root", "password": runtime.hash_password("rootpass"), "role": "superadmin"},
            {"username": "a", "password": "x", "role": "member", "company": "承希科技", "department": "交付部"},
            {"username": "b", "password": "x", "role": "member", "company": "承希科技", "department": "销售部"},
        ])
        with patch.object(runtime, "openclaw_sync_user"), patch.object(runtime, "crm_security_batch_grant") as crm_grant:
            result = runtime.batch_update_assistant_permissions({
                "company": "承希科技", "departments": ["交付部"], "assistant_ids": ["knowledge", "crm"], "enabled": False,
            }, "root")
        users = {item["username"]: item for item in self._read_users()}
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["assistant_ids"], ["knowledge", "crm"])
        self.assertFalse(users["a"]["assistant_permissions"]["knowledge"])
        self.assertNotIn("crm", users["a"].get("assistant_permissions", {}))
        self.assertNotIn("assistant_permissions", users["b"])
        crm_grant.assert_called_once()

    def test_selected_users_can_have_one_assistant_revoked_together(self):
        self._write_users([
            {"username": "root", "password": "x", "role": "superadmin"},
            {"username": "a", "password": "x", "role": "member", "assistant_permissions": {"knowledge": True}},
            {"username": "b", "password": "x", "role": "member", "assistant_permissions": {"knowledge": True}},
        ])
        with patch.object(runtime, "openclaw_sync_user"):
            result = runtime.batch_update_assistant_users({"assistant_id": "knowledge", "usernames": ["a", "b"], "enabled": False}, "root")
        self.assertEqual(result["updated"], 2)
        self.assertFalse(next(item for item in self._read_users() if item["username"] == "a")["assistant_permissions"]["knowledge"])

    def test_selected_users_can_enable_crm_through_its_special_policy(self):
        self._write_users([
            {"username": "root", "password": "x", "role": "superadmin"},
            {"username": "a", "password": "x", "role": "member"},
        ])
        with patch.object(runtime, "crm_security_grant") as crm_grant, patch.object(runtime, "openclaw_sync_user"):
            result = runtime.batch_update_assistant_users({"assistant_id": "crm", "usernames": ["a"], "enabled": True}, "root")
        self.assertEqual(result["updated"], 1)
        self.assertEqual(crm_grant.call_args.args[0]["role"], "viewer")


if __name__ == "__main__":
    unittest.main()
