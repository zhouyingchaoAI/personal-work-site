"""平台本身：头像与导航偏好在文件/数据库模式下行为一致。"""
import base64
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class PlatformStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_nav_prefs_roundtrip(self):
        self.assertEqual(rt.load_nav_prefs("alice"), {"order": [], "hidden": []})
        saved = rt.save_nav_prefs({"order": ["crm", "Bad Id", "diary"], "hidden": ["news"]}, "alice")
        self.assertEqual(saved["prefs"], {"order": ["crm", "diary"], "hidden": ["news"]})
        self.assertEqual(rt.load_nav_prefs("alice"), {"order": ["crm", "diary"], "hidden": ["news"]})
        self.assertEqual(rt.load_nav_prefs("bob"), {"order": [], "hidden": []})

    def test_avatar_roundtrip(self):
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        avatar = rt.user_profile_dir("alice") / "avatar.png"
        rt.office_blob_write("platform", avatar, png, content_type="image/png")
        stat = rt.office_blob_stat("platform", avatar)
        self.assertEqual(stat["size"], len(png))
        self.assertEqual(rt.office_blob_read("platform", avatar), png)
        self.assertIsNone(rt.office_blob_read("platform", rt.user_profile_dir("bob") / "avatar.png"))


PlatformStorageDbModeTests = db_variant(PlatformStorageTests)


if __name__ == "__main__":
    unittest.main()
