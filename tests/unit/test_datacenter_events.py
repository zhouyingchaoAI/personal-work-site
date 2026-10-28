"""数据中台留痕与告警：文件模式写 JSONL，数据库模式写 app.events，读取口径一致。"""
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class DatacenterEventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)
        rt._dcflow_alert_seen.clear()

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_access_log_roundtrip(self):
        rt.dc_audit("root", "preview", "alice/diary/2026-01-01.json", "detail")
        rt.dc_audit("root", "download", "alice/diary/2026-01-02.json")
        rows = rt.datacenter_access_log()["rows"]
        self.assertEqual([r["action"] for r in rows], ["download", "preview"])
        self.assertEqual(rows[0]["user"], "root")
        self.assertNotIn("seq", rows[0])

    def test_alerts_roundtrip_with_dedup(self):
        alert = {"at": "2026-09-30T10:00:00", "instance": "office-postgres", "level": "warn", "code": "conn", "message": "x"}
        rt._dcflow_persist_alerts([alert])
        rt._dcflow_persist_alerts([alert])  # 同实例同类型 10 分钟内去重
        rt._dcflow_persist_alerts([{**alert, "code": "other"}])
        recent = rt._dcflow_recent_alerts(limit=10)
        self.assertEqual([a["code"] for a in recent], ["other", "conn"])


DatacenterEventDbModeTests = db_variant(DatacenterEventTests)


if __name__ == "__main__":
    unittest.main()
