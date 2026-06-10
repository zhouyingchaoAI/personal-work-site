"""Tests for backend account password hashing (pbkdf2) and legacy migration."""
import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
