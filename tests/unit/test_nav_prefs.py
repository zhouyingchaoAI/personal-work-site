import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt


class NavPrefsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_user_data_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name) / "user_data"

    def tearDown(self):
        rt.USER_DATA_DIR = self.old_user_data_dir
        self.tmp.cleanup()

    def test_save_then_load_round_trips_order_and_hidden(self):
        result = rt.save_nav_prefs({"order": ["weekly", "news", "writing"], "hidden": ["forum"]}, "zhouyc")
        self.assertTrue(result["ok"])
        prefs = rt.load_nav_prefs("zhouyc")
        self.assertEqual(prefs["order"], ["weekly", "news", "writing"])
        self.assertEqual(prefs["hidden"], ["forum"])

    def test_save_sanitizes_invalid_ids_and_deduplicates(self):
        result = rt.save_nav_prefs(
            {"order": ["weekly", "weekly", "../etc/passwd", "<script>", "", 42, "trip"], "hidden": "not-a-list"},
            "zhouyc",
        )
        self.assertEqual(result["prefs"]["order"], ["weekly", "trip"])
        self.assertEqual(result["prefs"]["hidden"], [])

    def test_load_returns_empty_prefs_for_missing_or_corrupt_file(self):
        self.assertEqual(rt.load_nav_prefs("nobody"), {"order": [], "hidden": []})
        path = rt.nav_prefs_path("zhouyc")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(rt.load_nav_prefs("zhouyc"), {"order": [], "hidden": []})

    def test_save_requires_login(self):
        with self.assertRaises(ValueError):
            rt.save_nav_prefs({"order": []}, "")


if __name__ == "__main__":
    unittest.main()
