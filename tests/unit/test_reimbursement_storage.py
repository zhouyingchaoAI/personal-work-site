"""报销助手存储：搜索记录、发票缓存、输出文件在文件/数据库模式下行为一致。"""
import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt
from tests.unit.officedb_testing import db_variant


class ReimbursementStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_search_records_roundtrip(self):
        saved = rt.save_reimbursement_search("alice", {"start": "2026-09-01", "end": "2026-09-30",
                                                      "items": [{"key": "k1", "filename": "a.pdf", "invoice_amount": "12.00"}]})
        record_id = saved["record"]["id"]
        again = rt.save_reimbursement_search("alice", {"id": record_id, "items": [{"key": "k2", "filename": "b.pdf", "invoice_amount": "3.50"}]})
        self.assertEqual(again["record"]["item_count"], 2)
        listed = rt.list_reimbursement_searches("alice")["records"]
        self.assertEqual([r["id"] for r in listed], [record_id])
        self.assertEqual(rt.get_reimbursement_search("alice", record_id)["record"]["item_count"], 2)
        self.assertEqual(rt.list_reimbursement_searches("bob")["records"], [])
        with self.assertRaises(ValueError):
            rt.get_reimbursement_search("bob", record_id)

    def test_cache_files_and_outputs(self):
        path = rt._save_cache("alice", "abc123", "发票 A.pdf", b"%PDF-1.4 test")
        self.assertTrue(path.is_file())
        found = rt._cache_path_for_key("alice", "abc123")
        self.assertIsNotNone(found)
        self.assertEqual(found.read_bytes(), b"%PDF-1.4 test")
        self.assertEqual(rt.get_reimbursement_attachment("alice", "abc123").name, found.name)
        self.assertIsNone(rt._cache_path_for_key("alice", "missing"))
        self.assertIsNone(rt._cache_path_for_key("alice", "../"))
        result = rt.download_reimbursement_invoices_zip("alice", [{"key": "abc123", "invoice_type": "其他"}], "批量")
        self.assertEqual(result["count"], 1)
        out_path, raw = rt.get_reimbursement_output("alice", result["filename"])
        self.assertTrue(raw.startswith(b"PK"))
        second = rt.download_reimbursement_invoices_zip("alice", [{"key": "abc123"}], "批量")
        self.assertEqual(second["filename"], "批量_1.zip")
        self.assertIsNone(rt.get_reimbursement_output("alice", "nope.pdf"))


ReimbursementStorageDbModeTests = db_variant(ReimbursementStorageTests)


if __name__ == "__main__":
    unittest.main()
