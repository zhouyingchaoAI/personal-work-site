"""Tests for at-rest encryption of mailbox SMTP/IMAP credentials."""
import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime


class SecretCryptoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_user_data = runtime.USER_DATA_DIR
        self._orig_cfg = runtime.CONFIG_PATH
        runtime.USER_DATA_DIR = Path(self._tmp.name)
        runtime.CONFIG_PATH = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        runtime.USER_DATA_DIR = self._orig_user_data
        runtime.CONFIG_PATH = self._orig_cfg
        self._tmp.cleanup()

    # crypto primitives -----------------------------------------------------
    def test_roundtrip(self):
        enc = runtime.encrypt_secret("authcode-9921")
        self.assertTrue(enc.startswith("enc:v1$"))
        self.assertNotIn("authcode-9921", enc)
        self.assertEqual(runtime.decrypt_secret(enc), "authcode-9921")

    def test_nonce_is_random(self):
        self.assertNotEqual(runtime.encrypt_secret("x"), runtime.encrypt_secret("x"))

    def test_empty_stays_empty(self):
        self.assertEqual(runtime.encrypt_secret(""), "")
        self.assertEqual(runtime.decrypt_secret(""), "")

    def test_decrypt_legacy_plaintext_passthrough(self):
        self.assertEqual(runtime.decrypt_secret("oldPlainCode"), "oldPlainCode")

    def test_double_encrypt_is_noop(self):
        once = runtime.encrypt_secret("abc")
        self.assertEqual(runtime.encrypt_secret(once), once)

    def test_tampered_ciphertext_fails_closed(self):
        enc = runtime.encrypt_secret("secret")
        tampered = enc[:-3] + ("aa" if not enc.endswith("aa") else "bb") + enc[-1]
        self.assertEqual(runtime.decrypt_secret(tampered), "")

    def test_unicode_secret(self):
        enc = runtime.encrypt_secret("授权码密码123")
        self.assertEqual(runtime.decrypt_secret(enc), "授权码密码123")

    # end-to-end via mail config -------------------------------------------
    def test_save_stores_ciphertext_read_returns_plaintext(self):
        runtime.save_user_mail_config("u1", {"user_email": "u1@x.com", "smtp_password": "authcode123", "imap_password": "imapcode456"})
        raw = json.loads(runtime.CONFIG_PATH.read_text(encoding="utf-8"))
        stored = raw["user_mail_settings"]["u1"]
        # On disk: encrypted, no plaintext present
        self.assertTrue(stored["smtp_password"].startswith("enc:v1$"))
        self.assertNotIn("authcode123", json.dumps(raw))
        self.assertNotIn("imapcode456", json.dumps(raw))
        # In use: decrypted back to the original
        cfg = runtime.user_mail_config("u1")
        self.assertEqual(cfg["smtp_password"], "authcode123")
        self.assertEqual(cfg["imap_password"], "imapcode456")

    def test_legacy_plaintext_config_still_usable(self):
        # Simulate an old config with plaintext passwords
        runtime.CONFIG_PATH.write_text(json.dumps({
            "user_mail_settings": {"u1": {"smtp_password": "legacyplain", "user_email": "u1@x.com"}}
        }), encoding="utf-8")
        cfg = runtime.user_mail_config("u1")
        self.assertEqual(cfg["smtp_password"], "legacyplain")

    def test_migration_encrypts_existing_plaintext(self):
        runtime.CONFIG_PATH.write_text(json.dumps({
            "user_mail_settings": {
                "u1": {"smtp_password": "p1", "imap_password": "p2"},
                "u2": {"personal_smtp_password": "p3"},
            }
        }), encoding="utf-8")
        out = runtime.encrypt_existing_mail_secrets()
        self.assertEqual(out["encrypted_fields"], 3)
        raw = json.loads(runtime.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertTrue(raw["user_mail_settings"]["u1"]["smtp_password"].startswith("enc:v1$"))
        # Still decrypts to the originals, and migration is idempotent
        self.assertEqual(runtime.user_mail_config("u1")["smtp_password"], "p1")
        self.assertEqual(runtime.encrypt_existing_mail_secrets()["encrypted_fields"], 0)


if __name__ == "__main__":
    unittest.main()
