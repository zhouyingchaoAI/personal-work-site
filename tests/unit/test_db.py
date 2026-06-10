import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import db


class DatabaseFoundationTests(unittest.TestCase):
    def test_init_db_creates_ai_native_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"

            db.init_db(path)

            with sqlite3.connect(path) as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            table_names = {row[0] for row in rows}
            self.assertTrue(
                {
                    "agent_sessions",
                    "agent_messages",
                    "skill_invocations",
                    "agent_events",
                    "memory_items",
                }.issubset(table_names)
            )

    def test_record_agent_event_and_filter_by_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)

            event_id = db.record_agent_event(
                path,
                user_id="zhouyingchao",
                session_id="sess-1",
                event_type="agent.turn.completed",
                source="unit-test",
                payload={"reply_chars": 12, "skill_calls": 1},
            )
            db.record_agent_event(
                path,
                user_id="zhouyingchao",
                session_id="sess-2",
                event_type="agent.turn.completed",
                source="unit-test",
                payload={"reply_chars": 3},
            )

            events = db.list_agent_events(path, user_id="zhouyingchao", session_id="sess-1", limit=10)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["id"], event_id)
            self.assertEqual(events[0]["event_type"], "agent.turn.completed")
            self.assertEqual(events[0]["payload"], {"reply_chars": 12, "skill_calls": 1})

    def test_record_skill_invocation_and_fetch_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)

            invocation_id = db.record_skill_invocation(
                path,
                user_id="zhouyingchao",
                session_id="sess-1",
                skill_name="utils.get_date",
                source="test",
                arguments={"format": "YYYY-MM-DD"},
                result={"ok": True, "today": "2026-05-19"},
                status="success",
                safety_level="safe",
                confirmed=False,
            )
            recent = db.list_recent_skill_invocations(path, user_id="zhouyingchao", limit=5)

            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["id"], invocation_id)
            self.assertEqual(recent[0]["skill_name"], "utils.get_date")
            self.assertEqual(recent[0]["arguments"], {"format": "YYYY-MM-DD"})
            self.assertEqual(recent[0]["result"]["today"], "2026-05-19")

    def test_remember_and_list_memory_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)

            memory_id = db.remember(
                path,
                user_id="zhouyingchao",
                memory_type="preference",
                content="用户偏好周报编号清晰、体现工作量。",
                metadata={"source": "test"},
                source="unit-test",
                confidence=0.9,
            )
            items = db.list_memory_items(path, user_id="zhouyingchao", memory_type="preference")

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], memory_id)
            self.assertEqual(items[0]["content"], "用户偏好周报编号清晰、体现工作量。")
            self.assertEqual(items[0]["metadata"], {"source": "test"})
            self.assertAlmostEqual(items[0]["confidence"], 0.9)


class DatabaseExtraTests(unittest.TestCase):
    def test_utc_now_iso_format(self):
        now = db.utc_now()
        self.assertIn("T", now)
        self.assertTrue(now.endswith("+00:00"))

    def test_skill_invocations_user_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)
            db.record_skill_invocation(path, user_id="alice", session_id="s", skill_name="x", source="t", status="success")
            db.record_skill_invocation(path, user_id="bob", session_id="s", skill_name="y", source="t", status="success")
            alice = db.list_recent_skill_invocations(path, user_id="alice")
            self.assertEqual(len(alice), 1)
            self.assertEqual(alice[0]["skill_name"], "x")

    def test_list_agent_events_across_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)
            db.record_agent_event(path, user_id="u1", session_id="s1", event_type="e", source="t")
            db.record_agent_event(path, user_id="u1", session_id="s2", event_type="e", source="t")
            all_events = db.list_agent_events(path, user_id="u1", limit=10)
            self.assertEqual(len(all_events), 2)

    def test_remember_default_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            db.init_db(path)
            db.remember(path, user_id="u1", memory_type="note", content="c")
            items = db.list_memory_items(path, user_id="u1")
            self.assertAlmostEqual(items[0]["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
