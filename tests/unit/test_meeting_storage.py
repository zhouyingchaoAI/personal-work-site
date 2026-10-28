"""会议助手记录存储：文件模式与数据库模式行为一致。"""
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class MeetingStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original
        self.tmp.cleanup()

    def test_save_list_get_delete(self):
        saved = rt.meeting_save({"title": "周例会", "segments": [{"time": "00:01", "text": "开始"}], "duration": 60}, "alice")
        meeting_id = saved["id"]
        again = rt.meeting_save({"id": meeting_id, "summary": "纪要"}, "alice")
        self.assertEqual(again["meeting"]["title"], "周例会")
        self.assertEqual(again["meeting"]["segments"], [{"time": "00:01", "text": "开始", "translation": ""}])
        listed = rt.meeting_list("alice")["meetings"]
        self.assertEqual([m["id"] for m in listed], [meeting_id])
        self.assertTrue(listed[0]["has_summary"])
        self.assertEqual(rt.meeting_list("bob")["meetings"], [])
        self.assertEqual(rt.meeting_get(meeting_id, "alice")["meeting"]["summary"], "纪要")
        with self.assertRaises(ValueError):
            rt.meeting_get(meeting_id, "bob")
        with self.assertRaises(ValueError):
            rt.meeting_get("../x", "alice")
        rt.meeting_delete({"id": meeting_id}, "alice")
        self.assertEqual(rt.meeting_list("alice")["meetings"], [])


MeetingStorageDbModeTests = db_variant(MeetingStorageTests)


if __name__ == "__main__":
    unittest.main()
