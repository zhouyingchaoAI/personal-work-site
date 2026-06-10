"""Regression tests for the Memory Layer (backend/memory.py).

memory.py persists to the shared app DB via the runtime namespace's connect()
(no explicit path), so we redirect USER_DATA_DIR to a temp dir per test to keep
each case isolated from the real user_data/app.db.
"""
import tempfile
import unittest
from pathlib import Path

from backend import runtime


class MemoryLayerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_user_data = runtime.USER_DATA_DIR
        runtime.USER_DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        runtime.USER_DATA_DIR = self._orig_user_data
        self._tmp.cleanup()

    # remember / list -------------------------------------------------------
    def test_remember_returns_item_and_lists(self):
        item = runtime.remember_memory(
            user_id="u1", memory_type="preference",
            content="喜欢编号清晰的周报", metadata={"k": "v"}, source="test",
        )
        self.assertTrue(item["id"].startswith("mem_"))
        items = runtime.list_memories("u1")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "喜欢编号清晰的周报")
        self.assertEqual(items[0]["metadata"], {"k": "v"})

    def test_list_is_user_isolated(self):
        runtime.remember_memory(user_id="alice", memory_type="note", content="alice secret")
        runtime.remember_memory(user_id="bob", memory_type="note", content="bob secret")
        self.assertEqual(len(runtime.list_memories("alice")), 1)
        self.assertEqual(runtime.list_memories("alice")[0]["content"], "alice secret")

    def test_list_type_filter(self):
        runtime.remember_memory(user_id="u1", memory_type="preference", content="p")
        runtime.remember_memory(user_id="u1", memory_type="fact", content="f")
        self.assertEqual(len(runtime.list_memories("u1", memory_type="fact")), 1)
        self.assertEqual(runtime.list_memories("u1", memory_type="fact")[0]["content"], "f")

    # search ----------------------------------------------------------------
    def test_search_matches_content(self):
        runtime.remember_memory(user_id="u1", memory_type="note", content="weekly report formatting tips")
        runtime.remember_memory(user_id="u1", memory_type="note", content="unrelated content here")
        results = runtime.search_memory_items("u1", "weekly")
        self.assertTrue(any("weekly" in r["content"] for r in results))

    def test_search_chinese_substring(self):
        runtime.remember_memory(user_id="u1", memory_type="note", content="用户偏好出差报告精炼")
        results = runtime.search_memory_items("u1", "出差报告")
        self.assertEqual(len(results), 1)

    def test_search_empty_query_returns_all(self):
        runtime.remember_memory(user_id="u1", memory_type="note", content="a")
        runtime.remember_memory(user_id="u1", memory_type="note", content="b")
        self.assertEqual(len(runtime.search_memory_items("u1", "")), 2)

    def test_search_is_user_isolated(self):
        runtime.remember_memory(user_id="alice", memory_type="note", content="shared keyword apple")
        runtime.remember_memory(user_id="bob", memory_type="note", content="shared keyword apple")
        self.assertEqual(len(runtime.search_memory_items("alice", "apple")), 1)

    # forget ----------------------------------------------------------------
    def test_forget_deletes_owner_item(self):
        item = runtime.remember_memory(user_id="u1", memory_type="note", content="to delete")
        res = runtime.forget_memory("u1", item["id"])
        self.assertTrue(res["ok"])
        self.assertEqual(len(runtime.list_memories("u1")), 0)

    def test_forget_other_user_raises(self):
        item = runtime.remember_memory(user_id="alice", memory_type="note", content="alice only")
        with self.assertRaises(ValueError):
            runtime.forget_memory("bob", item["id"])
        # alice's memory survives the failed cross-user delete
        self.assertEqual(len(runtime.list_memories("alice")), 1)

    # skills ----------------------------------------------------------------
    def test_remember_skill_requires_content(self):
        with self.assertRaises(ValueError):
            runtime.memory_remember_skill({"content": "  "}, "u1")

    def test_search_skill_returns_count(self):
        runtime.memory_remember_skill({"content": "alpha beta", "type": "note"}, "u1")
        out = runtime.memory_search_skill({"query": "alpha"}, "u1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], len(out["memories"]))
        self.assertGreaterEqual(out["count"], 1)

    def test_forget_skill_requires_id(self):
        with self.assertRaises(ValueError):
            runtime.memory_forget_skill({}, "u1")

    def test_summarize_skill_groups_types(self):
        runtime.memory_remember_skill({"content": "c1", "type": "preference"}, "u1")
        runtime.memory_remember_skill({"content": "c2", "type": "fact"}, "u1")
        out = runtime.memory_summarize_skill({}, "u1")
        self.assertEqual(out["count"], 2)
        self.assertEqual(set(out["types"]), {"preference", "fact"})

    # context injection -----------------------------------------------------
    def test_get_memory_context_empty_when_none(self):
        self.assertEqual(runtime.get_memory_context("nobody", "anything"), "")

    def test_get_memory_context_formats_items(self):
        runtime.remember_memory(user_id="u1", memory_type="preference", content="编号清晰")
        ctx = runtime.get_memory_context("u1", "")
        self.assertIn("[用户记忆]", ctx)
        self.assertIn("编号清晰", ctx)


if __name__ == "__main__":
    unittest.main()
