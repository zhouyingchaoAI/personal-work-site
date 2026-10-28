"""知识库本地记录与 RAGFlow 映射存储在文件/数据库模式下行为一致。"""
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt
from tests.unit.officedb_testing import db_variant


class KnowledgeStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_mapping_and_local_docs(self):
        self.assertEqual(rt._kb_mapping("ragflow_tenant_chats.json"), {})
        rt._kb_mapping_save("ragflow_tenant_chats.json", {"alice": {"id": "chat-1"}})
        self.assertEqual(rt._kb_mapping("ragflow_tenant_chats.json"), {"alice": {"id": "chat-1"}})
        rt.office_doc_write("knowledge", rt._kb_doc_path("doc_b"), {"id": "doc_b", "name": "b.txt", "uploaded_by": "alice", "chunks": []})
        rt.office_doc_write("knowledge", rt._kb_doc_path("doc_a"), {"id": "doc_a", "name": "a.txt", "uploaded_by": "alice", "chunks": []})
        self.assertEqual([stem for stem, _ in rt._kb_local_docs()], ["doc_b", "doc_a"])
        self.assertEqual(rt._kb_load_doc(rt._kb_doc_path("doc_a"))["name"], "a.txt")
        self.assertIsNone(rt._kb_load_doc(rt._kb_doc_path("doc_x")))
        with self.assertRaises(ValueError):
            rt._kb_doc_path("bad id!")
        self.assertTrue(rt.office_doc_delete("knowledge", rt._kb_doc_path("doc_a")))
        self.assertEqual([stem for stem, _ in rt._kb_local_docs()], ["doc_b"])


KnowledgeStorageDbModeTests = db_variant(KnowledgeStorageTests)


if __name__ == "__main__":
    unittest.main()
