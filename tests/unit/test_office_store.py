"""统一存储层（backend/office_store.py）测试。

- 文件模式：开关缺失/关闭时按原路径读写；
- 数据库模式：设置 OFFICE_STORE_TEST_CONFIG=<office_db.json，database 指向一次性测试库>
  后运行（scripts/office_db_setup.py --test-db office_test 生成）。
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_store(user_data_dir, db=False):
    ns = {"USER_DATA_DIR": Path(user_data_dir), "__file__": str(ROOT / "app.py")}
    code = (ROOT / "backend" / "office_store.py").read_text(encoding="utf-8")
    exec(compile(code, "office_store.py", "exec"), ns)
    if db:
        target = Path(user_data_dir) / "_datacenter"
        target.mkdir(exist_ok=True)
        config = json.loads(Path(os.environ["OFFICE_STORE_TEST_CONFIG"]).read_text())
        assert config.get("database") != "office", "禁止对生产库跑测试"
        (target / "office_db.json").write_text(json.dumps({**config, "modules": {"all": True}}))
        with ns["_officedb_conn"]() as conn:
            for table in ("documents", "blobs", "events"):
                conn.run(f"DELETE FROM app.{table}")
    return ns


class OfficeStoreFileModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ns = load_store(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_disabled_without_config(self):
        self.assertFalse(self.ns["officedb_enabled"]("ledger"))
        self.assertEqual(self.ns["officedb_enabled_modules"](), [])

    def test_doc_roundtrip_on_disk(self):
        path = self.root / "alice" / "operating_ledger.json"
        self.assertEqual(self.ns["office_doc_read"]("ledger", path, []), [])
        self.ns["office_doc_write"]("ledger", path, [{"id": "a", "v": 1}])
        self.assertTrue(path.is_file())
        self.assertEqual(json.loads(path.read_text()), [{"id": "a", "v": 1}])
        self.assertEqual(self.ns["office_doc_read"]("ledger", path), [{"id": "a", "v": 1}])
        self.assertTrue(self.ns["office_doc_delete"]("ledger", path))
        self.assertFalse(path.exists())

    def test_doc_list_and_blob(self):
        base = self.root / "alice" / "diary"
        self.ns["office_doc_write"]("diary", base / "2026-01-02.json", {"d": 2})
        self.ns["office_doc_write"]("diary", base / "2026-01-01.json", {"d": 1})
        (base / "note.txt").write_text("x")
        names = sorted(name for name, _, _ in self.ns["office_doc_list"]("diary", base))
        self.assertEqual(names, ["2026-01-01.json", "2026-01-02.json"])
        blob = self.root / "_forum" / "attachments" / "abc.png"
        self.ns["office_blob_write"]("forum", blob, b"\x89PNG")
        self.assertEqual(self.ns["office_blob_read"]("forum", blob), b"\x89PNG")
        self.assertEqual([n for n, _, _ in self.ns["office_blob_list"]("forum", blob.parent, prefix="abc")], ["abc.png"])
        with self.ns["office_blob_local"]("forum", blob) as local:
            self.assertEqual(local, blob)
        self.assertTrue(self.ns["office_blob_delete"]("forum", blob))
        self.assertIsNone(self.ns["office_blob_read"]("forum", blob))

    def test_key_and_owner(self):
        self.assertEqual(self.ns["office_store_key"](self.root / "bob" / "x.json"), "bob/x.json")
        self.assertEqual(self.ns["office_store_owner"]("bob/x.json"), "bob")
        self.assertEqual(self.ns["office_store_owner"]("_forum/topics.json"), "")
        self.assertEqual(self.ns["office_store_owner"]("projects/projects.json"), "")
        with self.assertRaises(ValueError):
            self.ns["office_store_key"](Path("/etc/passwd"))


@unittest.skipUnless(os.getenv("OFFICE_STORE_TEST_CONFIG"), "requires disposable test database")
class OfficeStoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ns = load_store(self.root, db=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_enabled_via_all(self):
        self.assertTrue(self.ns["officedb_enabled"]("ledger"))
        self.assertIn("ledger", self.ns["officedb_enabled_modules"]())

    def test_doc_roundtrip_keeps_order_and_leaves_no_file(self):
        path = self.root / "alice" / "operating_ledger.json"
        value = [{"zeta": 1, "alpha": {"b": 2, "a": 1}}]
        self.ns["office_doc_write"]("ledger", path, value)
        self.assertFalse(path.exists())
        got = self.ns["office_doc_read"]("ledger", path)
        self.assertEqual(json.dumps(got, ensure_ascii=False), json.dumps(value, ensure_ascii=False))
        self.ns["office_doc_write"]("ledger", path, [])
        self.assertEqual(self.ns["office_doc_read"]("ledger", path), [])
        self.assertTrue(self.ns["office_doc_exists"]("ledger", path))
        self.assertTrue(self.ns["office_doc_delete"]("ledger", path))
        self.assertFalse(self.ns["office_doc_delete"]("ledger", path))
        self.assertEqual(self.ns["office_doc_read"]("ledger", path, "dflt"), "dflt")

    def test_doc_list_prefix_isolation(self):
        base = self.root / "alice" / "diary"
        self.ns["office_doc_write"]("diary", base / "2026-01-02.json", {"d": 2})
        self.ns["office_doc_write"]("diary", base / "2026-01-01.json", {"d": 1})
        self.ns["office_doc_write"]("diary", base / "sub" / "x.json", {"d": 3})
        self.ns["office_doc_write"]("diary", self.root / "alice" / "diary_other" / "y.json", {"d": 4})
        self.ns["office_doc_write"]("diary", self.root / "bob" / "diary" / "2026-01-01.json", {"d": 9})
        names = sorted(name for name, _, _ in self.ns["office_doc_list"]("diary", base))
        self.assertEqual(names, ["2026-01-01.json", "2026-01-02.json"])
        names = sorted(name for name, _, _ in self.ns["office_doc_list"]("diary", base, recursive=True))
        self.assertEqual(names, ["2026-01-01.json", "2026-01-02.json", "sub/x.json"])
        self.assertEqual(sorted(self.ns["office_doc_owners"]("diary")), ["alice", "bob"])
        # 模块隔离
        self.assertEqual(self.ns["office_doc_list"]("weekly", base), [])

    def test_blob_roundtrip_stat_list_local(self):
        blob = self.root / "_forum" / "attachments" / "abc.png"
        self.ns["office_blob_write"]("forum", blob, b"\x89PNG\x00data", content_type="image/png")
        self.assertFalse(blob.exists())
        self.assertEqual(self.ns["office_blob_read"]("forum", blob), b"\x89PNG\x00data")
        stat = self.ns["office_blob_stat"]("forum", blob)
        self.assertEqual(stat["size"], 9)
        self.assertEqual(len(stat["sha256"]), 64)
        self.assertEqual([n for n, _, _ in self.ns["office_blob_list"]("forum", blob.parent, prefix="abc")], ["abc.png"])
        with self.ns["office_blob_local"]("forum", blob) as local:
            self.assertTrue(local.is_file())
            self.assertEqual(local.read_bytes(), b"\x89PNG\x00data")
        self.assertFalse(local.exists())
        self.ns["office_blob_write"]("forum", blob, b"new")
        self.assertEqual(self.ns["office_blob_read"]("forum", blob), b"new")
        self.assertEqual(self.ns["office_blob_delete_tree"]("forum", blob.parent), 1)
        self.assertIsNone(self.ns["office_blob_read"]("forum", blob))

    def test_events(self):
        self.assertTrue(self.ns["office_event_append"]("datacenter", "access", {"a": 1}, owner="root"))
        self.ns["office_event_append"]("datacenter", "access", {"a": 2})
        recent = self.ns["office_event_recent"]("datacenter", "access", limit=10)
        self.assertEqual([e["a"] for e in recent], [2, 1])
        self.assertEqual(self.ns["office_event_count"]("datacenter", "access"), 2)

    def test_import_verify_export_tree(self):
        # 先在文件模式写好文件，再切数据库模式导入
        (self.root / "_datacenter" / "office_db.json").unlink()
        self.ns["officedb_config"]()
        base = self.root / "alice" / "meetings"
        self.ns["office_doc_write"]("meeting", base / "m1.json", {"id": "m1"})
        self.ns["office_blob_write"]("meeting", base / "m1.mp3", b"audio")
        (base / "bad.json").write_text("{not json")
        self.ns = load_store(self.root, db=True)
        summary = self.ns["office_store_import_tree"]("meeting", base)
        self.assertEqual((summary["documents"], summary["blobs"]), (1, 1))
        self.assertEqual(len(summary["skipped"]), 1)
        verify = self.ns["office_store_verify_tree"]("meeting", base)
        self.assertEqual((verify["checked"], verify["mismatch"]), (2, []))
        counts = self.ns["office_store_counts"]("meeting")
        self.assertEqual((counts["documents"], counts["blobs"]), (1, 1))
        out = self.root / "export"
        self.assertEqual(self.ns["office_store_export_tree"]("meeting", base, out), 2)
        self.assertEqual(json.loads((out / "alice/meetings/m1.json").read_text()), {"id": "m1"})
        self.assertEqual((out / "alice/meetings/m1.mp3").read_bytes(), b"audio")


if __name__ == "__main__":
    unittest.main()
