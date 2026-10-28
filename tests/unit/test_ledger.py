"""项目管理台账（backend/ledger.py）：文件模式与数据库模式行为一致。"""
import tempfile
import unittest
from pathlib import Path

import backend.runtime as runtime
from tests.unit.officedb_testing import db_variant


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = runtime.USER_DATA_DIR
        runtime.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        runtime.USER_DATA_DIR = self.original
        self.tmp.cleanup()

    def test_save_list_delete_isolated_per_user(self):
        saved = runtime.ledger_save({"project_name": "轨道项目", "contract_amount": "100", "received_amount": 30,
                                     "document_checklist": [{"name": "合同", "completed": True}, {"name": "验收单"}]}, "alice")
        item = saved["item"]
        self.assertTrue(item["id"].startswith("ledger-"))
        listed = runtime.ledger_list("alice")
        self.assertEqual(listed["summary"]["total"], 1)
        self.assertEqual(listed["items"][0]["remaining_amount"], 70)
        self.assertEqual(listed["items"][0]["pending_document_count"], 1)
        self.assertEqual(runtime.ledger_list("bob")["items"], [])
        runtime.ledger_save({"id": item["id"], "project_name": "轨道项目二期", "contract_amount": 200}, "alice")
        self.assertEqual(runtime.ledger_list("alice")["items"][0]["project_name"], "轨道项目二期")
        self.assertEqual(runtime.ledger_list("alice")["summary"]["total"], 1)
        with self.assertRaises(ValueError):
            runtime.ledger_delete(item["id"], "bob")
        self.assertTrue(runtime.ledger_delete(item["id"], "alice")["ok"])
        self.assertEqual(runtime.ledger_list("alice")["items"], [])

    def test_overdue_marking(self):
        runtime.ledger_save({"project_name": "逾期项目", "payment_due": "2000-01-01"}, "alice")
        listed = runtime.ledger_list("alice")
        self.assertEqual(listed["items"][0]["status"], "逾期")
        self.assertEqual(listed["summary"]["overdue"], 1)


LedgerDbModeTests = db_variant(LedgerTests)


if __name__ == "__main__":
    unittest.main()
