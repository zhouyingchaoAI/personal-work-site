"""Tests for the AI-native Agent Runtime.

Covers: session CRUD, message persistence, memory context injection,
Skill execution with audit, and unified response protocol.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import db
from backend import agent_runtime as art
from backend import memory as mem


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        db.init_db(self.db_path)
        # Patch agent_runtime to use our test db
        art._db_connect = lambda: db.connect(self.db_path)
        art._init_db = lambda: db.init_db(self.db_path)
        mem._db_connect = lambda: db.connect(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_get_session(self):
        sess = art.create_session("zhouyingchao", kind="weekly", title="测试会话")
        self.assertTrue(sess["id"].startswith("sess_"))
        self.assertEqual(sess["user_id"], "zhouyingchao")
        self.assertEqual(sess["kind"], "weekly")

        fetched = art.get_session(sess["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], sess["id"])
        self.assertEqual(fetched["status"], "active")

    def test_list_sessions(self):
        s1 = art.create_session("zhouyingchao", kind="weekly")
        s2 = art.create_session("zhouyingchao", kind="diary")
        sessions = art.list_sessions("zhouyingchao", limit=10)
        self.assertEqual(len(sessions), 2)
        ids = [s["id"] for s in sessions]
        self.assertIn(s1["id"], ids)
        self.assertIn(s2["id"], ids)

    def test_update_session(self):
        sess = art.create_session("zhouyingchao", kind="weekly")
        art.update_session(sess["id"], title="新标题", status="paused")
        fetched = art.get_session(sess["id"])
        self.assertEqual(fetched["title"], "新标题")
        self.assertEqual(fetched["status"], "paused")

    def test_add_and_get_messages(self):
        sess = art.create_session("zhouyingchao", kind="weekly")
        art.add_message(sess["id"], "user", "帮我写周报")
        art.add_message(sess["id"], "assistant", "好的，请提供工作内容")
        msgs = art.get_messages(sess["id"])
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_memory_context_injection(self):
        # Save a preference
        mem.remember_memory(
            user_id="zhouyingchao",
            memory_type="preference",
            content="周报编号清晰、体现工作量",
        )
        ctx = mem.get_memory_context("zhouyingchao", query="周报", limit=5)
        self.assertIn("周报编号清晰", ctx)

    def test_agent_chat_without_api_returns_error(self):
        """When no AI API is configured, agent_chat should return an error."""
        result = art.agent_chat(
            {"kind": "weekly", "messages": [{"role": "user", "content": "test"}]},
            username="zhouyingchao",
        )
        self.assertFalse(result["ok"])
        self.assertIn("未配置 AI 接口", result["error"])

    def test_build_agent_response_structure(self):
        resp = art.build_agent_response(
            session_id="sess_123",
            reply="测试回复",
            actions=[{"type": "skill_call", "name": "utils.get_date"}],
            ui_patches=[{"op": "show_card", "card_type": "preview"}],
            memory_updates=[{"action": "remember", "type": "event"}],
        )
        self.assertEqual(resp["session_id"], "sess_123")
        self.assertEqual(resp["reply"], "测试回复")
        self.assertEqual(len(resp["actions"]), 1)
        self.assertEqual(len(resp["ui_patches"]), 1)
        self.assertEqual(len(resp["memory_updates"]), 1)
        self.assertFalse(resp["requires_confirmation"])
        self.assertEqual(resp["protocol_version"], "ai-native.v1")
        self.assertTrue(resp["trace_id"].startswith("trace_"))

    def test_agent_events_api_returns_session_events(self):
        sess = art.create_session("zhouyingchao", kind="weekly")
        event_id = art.record_agent_event(
            "zhouyingchao",
            sess["id"],
            "agent.turn.completed",
            source="unit-test",
            payload={"reply_chars": 6},
        )

        result = art.agent_sessions_api({"action": "events", "session_id": sess["id"]}, "zhouyingchao")

        self.assertTrue(result["ok"])
        self.assertEqual(result["events"][0]["id"], event_id)
        self.assertEqual(result["events"][0]["payload"], {"reply_chars": 6})

    def test_agent_chat_without_api_records_error_event(self):
        result = art.agent_chat(
            {"kind": "weekly", "messages": [{"role": "user", "content": "test"}]},
            username="zhouyingchao",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("session_id", "").startswith("sess_"))
        events = art.list_agent_events("zhouyingchao", session_id=result["session_id"])
        self.assertTrue(any(e["event_type"] == "agent.error" for e in events))

    def test_agent_chat_returns_immediately_after_skill_call(self):
        calls = []
        old_settings = getattr(art, "assistant_settings", None)
        old_request = getattr(art, "request_json", None)
        old_skill_defs = getattr(art, "skill_defs", None)
        old_parse = getattr(art, "parse_skill_call_skill", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.assistant_settings = lambda: {"url": "http://llm.local", "key": "k", "model": "m"}
            art.skill_defs = lambda: [{"name": "reports.list", "safe": True, "description": "查询报告列表"}]
            art.parse_skill_call_skill = lambda text: json.loads(text)["skill_call"]
            art.execute_skill = lambda name, args, username: {"message": "报告列表已查询", "reports": []}

            def fake_request_json(*args, **kwargs):
                calls.append(args)
                return {"choices": [{"message": {"content": json.dumps({
                    "reply": "我先查询报告列表。",
                    "skill_call": {"name": "reports.list", "arguments": {"kind": "all"}}
                }, ensure_ascii=False)}}]}

            art.request_json = fake_request_json

            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "帮我查一下有哪些文件"}]},
                username="zhouyingchao",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["skill_calls"][0]["name"], "reports.list")
            self.assertIn("0 条报告记录", result["reply"])
        finally:
            for name, value in {
                "assistant_settings": old_settings,
                "request_json": old_request,
                "skill_defs": old_skill_defs,
                "parse_skill_call_skill": old_parse,
                "execute_skill": old_execute,
            }.items():
                if value is None:
                    try:
                        delattr(art, name)
                    except AttributeError:
                        pass
                else:
                    setattr(art, name, value)

    def test_agent_chat_direct_date_skill_does_not_call_llm(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("direct date skill should not call LLM")
            art.execute_skill = lambda name, args, username: {"today": "2026.05.20", "weekday": "星期三", "week_range": "2026.05.18-2026.05.22"}
            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "今天几号？调用系统日期skill"}]},
                username="zhouyingchao",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["skill_calls"][0]["name"], "utils.get_date")
            self.assertIn("2026.05.20", result["reply"])
            self.assertTrue(any(p.get("op") == "show_timeline" for p in result.get("ui_patches", [])))
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_direct_reports_list_does_not_call_llm(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("direct report list should not call LLM")
            def fake_execute(name, args, username):
                self.assertEqual(name, "reports.list")
                self.assertEqual(args.get("kind"), "weekly")
                return {"ok": True, "reports": [{"kind": "weekly", "name": "周报1.xlsx"}]}
            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "查询周报历史报告列表\n\n[系统提示：当前页面上下文]\n本周工作总结"}]},
                username="zhouyingchao",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["skill_calls"][0]["name"], "reports.list")
            self.assertIn("1 条报告记录", result["reply"])
            self.assertTrue(any(p.get("op") == "show_timeline" for p in result.get("ui_patches", [])))
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_direct_history_weekly_routes_to_reports_list(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("history weekly should not call LLM")

            def fake_execute(name, args, username):
                self.assertEqual(name, "reports.list")
                self.assertEqual(args.get("kind"), "weekly")
                return {"ok": True, "reports": [{"kind": "weekly", "name": "周报历史.xlsx"}]}

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "看看历史周报"}]},
                username="zhouyingchao",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["skill_calls"][0]["name"], "reports.list")
            self.assertIn("1 条报告记录", result["reply"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_direct_history_trip_routes_to_reports_list(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("history trip should not call LLM")

            def fake_execute(name, args, username):
                self.assertEqual(name, "reports.list")
                self.assertEqual(args.get("kind"), "trip")
                return {"ok": True, "reports": [{"kind": "trip", "name": "出差报告-历史.docx"}]}

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "trip", "messages": [{"role": "user", "content": "看看历史出差报告"}]},
                username="zhouyingchao",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["skill_calls"][0]["name"], "reports.list")
            self.assertIn("出差报告 1 条", result["reply"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_greeting_replies_immediately_without_llm(self):
        old_request = getattr(art, "request_json", None)
        try:
            art.request_json = lambda *a, **k: self.fail("greeting should not call LLM")
            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "在吗"}]},
                username="zhouyingchao",
            )
            self.assertTrue(result["ok"])
            self.assertIn("在的", result["reply"])
            self.assertEqual(result["skill_calls"], [])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request

    def test_agent_chat_weekly_material_runs_date_and_compose_in_one_turn(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        calls = []
        try:
            art.request_json = lambda *a, **k: self.fail("direct weekly compose should not call outer LLM")

            def fake_execute(name, args, username):
                calls.append((name, args))
                if name == "utils.get_date":
                    return {
                        "ok": True,
                        "today": "2026.05.21",
                        "weekday": "星期四",
                        "week_range": "2026.05.18-2026.05.24",
                        "week_start": "2026.05.18",
                        "week_end": "2026.05.24",
                    }
                if name == "weekly.compose":
                    self.assertEqual(args.get("period"), "2026.05.18-2026.05.24")
                    return {
                        "ok": True,
                        "draft": {
                            "weekly_summary": [{"category": "架构", "content": "重构智能助手 agent 架构", "status": "已完成", "plan": ""}],
                            "weekly_follow": [],
                            "weekly_next": [],
                        },
                    }
                raise AssertionError(name)

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "weekly", "messages": [{"role": "user", "content": "本周工作总结，本周重构了智能助手agent架构，设计改善记忆机制"}]},
                username="zhouyingchao",
            )

            self.assertTrue(result["ok"])
            self.assertEqual([c[0] for c in calls], ["utils.get_date", "weekly.compose"])
            self.assertIn("2026.05.18-2026.05.24", result["reply"])
            self.assertEqual([c["name"] for c in result["skill_calls"]], ["utils.get_date", "weekly.compose"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_trip_context_generates_document_in_one_turn(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        calls = []
        context = {
            "reporter": "周颖超",
            "department": "场景研究院",
            "location": "长沙",
            "trip_start": "2026-05-18",
            "trip_end": "2026-05-20",
            "purpose": "项目现场调研",
            "itinerary": "现场沟通需求",
            "details": "完成系统部署问题排查",
            "issues": "",
            "suggestions": "持续跟进验收",
        }
        try:
            art.request_json = lambda *a, **k: self.fail("direct trip generation should not call LLM")

            def fake_execute(name, args, username):
                calls.append((name, args))
                if name == "utils.get_date":
                    return {"ok": True, "today": "2026.05.21"}
                if name == "document.generate":
                    self.assertEqual(args.get("kind"), "trip")
                    self.assertEqual(args.get("location"), "长沙")
                    self.assertEqual(args.get("trip_start"), "2026-05-18")
                    return {"ok": True, "file": "出差报告-20260518-0520-周颖超.docx", "draft": {"subject": "【出差报告】测试"}}
                raise AssertionError(name)

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {
                    "kind": "trip",
                    "messages": [{
                        "role": "user",
                        "content": "生成出差报告给我看看\n\n[系统提示：当前页面上下文]\n" + json.dumps(context, ensure_ascii=False),
                    }],
                },
                username="zhouyingchao",
            )

            self.assertTrue(result["ok"])
            self.assertEqual([c[0] for c in calls], ["utils.get_date", "document.generate"])
            self.assertIn("2026-05-18 至 2026-05-20", result["reply"])
            self.assertEqual([c["name"] for c in result["skill_calls"]], ["utils.get_date", "document.generate"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_direct_diary_list_includes_dates_and_previews(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("direct diary list should not call LLM")

            def fake_execute(name, args, username):
                self.assertEqual(name, "diary.list")
                self.assertGreaterEqual(args.get("limit", 0), 10)
                return {"ok": True, "diaries": [
                    {"date": "2026-05-20", "today_work_preview": "完成日记助手链路排查"},
                    {"date": "2026-05-19", "today_work_preview": "整理周报素材"},
                ]}

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "diary", "messages": [{"role": "user", "content": "查看日记列表"}]},
                username="zhouyingchao",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["skill_calls"][0]["name"], "diary.list")
            self.assertIn("2 条工作日记记录", result["reply"])
            self.assertIn("2026-05-20", result["reply"])
            self.assertIn("完成日记助手链路排查", result["reply"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_chat_direct_diary_colloquial_list_queries(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            setattr(art, "request_json", lambda *a, **k: self.fail("colloquial diary list should not call LLM"))

            def fake_execute(name, args, username):
                self.assertEqual(name, "diary.list")
                self.assertGreaterEqual(args.get("limit", 0), 10)
                return {"ok": True, "diaries": [
                    {"date": "2026-05-20", "today_work_preview": "口语化查询也要返回日记内容"},
                ]}

            setattr(art, "execute_skill", fake_execute)
            for text in ("看看日记", "看下日记", "看一下日记", "查下日记", "日记记录", "看看我的日记", "列表呢", "我需要看列表"):
                with self.subTest(text=text):
                    result = art.agent_chat(
                        {"kind": "diary", "messages": [{"role": "user", "content": text}]},
                        username="zhouyingchao",
                    )
                    self.assertTrue(result["ok"])
                    self.assertEqual(result["skill_calls"][0]["name"], "diary.list")
                    self.assertIn("口语化查询也要返回日记内容", result["reply"])
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                setattr(art, "request_json", old_request)
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                setattr(art, "execute_skill", old_execute)

    def test_agent_chat_direct_diary_save_with_today_does_not_route_to_date_skill(self):
        old_request = getattr(art, "request_json", None)
        old_execute = getattr(art, "execute_skill", None)
        try:
            art.request_json = lambda *a, **k: self.fail("explicit diary save should not call LLM")
            captured = {}

            def fake_execute(name, args, username):
                captured["name"] = name
                captured["args"] = args
                return {"ok": True, "diary": {**args, "date": args.get("date", "2026-05-20")}}

            art.execute_skill = fake_execute
            result = art.agent_chat(
                {"kind": "diary", "messages": [{"role": "user", "content": "帮我记录今天的工作日记：今天完成日记助手问题复现；明天继续完善自动化测试；想法是让列表直接展示详情。"}]},
                username="zhouyingchao",
            )

            self.assertTrue(result["ok"])
            self.assertEqual(captured["name"], "diary.save")
            self.assertIn("日记助手问题复现", captured["args"].get("today_work", ""))
            self.assertIn("自动化测试", captured["args"].get("tomorrow_plan", ""))
            self.assertIn("列表直接展示详情", captured["args"].get("thoughts", ""))
            self.assertIn("已保存", result["reply"])
            self.assertNotEqual(result["skill_calls"][0]["name"], "utils.get_date")
        finally:
            if old_request is None:
                try:
                    delattr(art, "request_json")
                except AttributeError:
                    pass
            else:
                art.request_json = old_request
            if old_execute is None:
                try:
                    delattr(art, "execute_skill")
                except AttributeError:
                    pass
            else:
                art.execute_skill = old_execute

    def test_agent_sessions_api_list(self):
        art.create_session("zhouyingchao", kind="weekly")
        result = art.agent_sessions_api({"action": "list"}, "zhouyingchao")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["sessions"]), 1)

    def test_agent_sessions_api_crud(self):
        # Create
        r1 = art.agent_sessions_api({"action": "create", "kind": "diary", "title": "日记测试"}, "zhouyingchao")
        self.assertTrue(r1["ok"])
        sid = r1["session"]["id"]

        # Get
        r2 = art.agent_sessions_api({"action": "get", "session_id": sid}, "zhouyingchao")
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["session"]["kind"], "diary")

        # Update
        r3 = art.agent_sessions_api({"action": "update", "session_id": sid, "title": "已更新"}, "zhouyingchao")
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["session"]["title"], "已更新")


class MemorySkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        db.init_db(self.db_path)
        mem._db_connect = lambda: db.connect(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_memory_remember_and_search(self):
        r1 = mem.memory_remember_skill(
            {"content": "偏好：周报编号清晰", "type": "preference"},
            "zhouyingchao",
        )
        self.assertTrue(r1["ok"])
        mid = r1["memory"]["id"]

        r2 = mem.memory_search_skill({"query": "周报", "limit": 5}, "zhouyingchao")
        self.assertTrue(r2["ok"])
        self.assertGreaterEqual(r2["count"], 1)
        self.assertTrue(any(m["id"] == mid for m in r2["memories"]))

    def test_memory_forget(self):
        r1 = mem.memory_remember_skill({"content": "临时记忆"}, "zhouyingchao")
        mid = r1["memory"]["id"]

        r2 = mem.memory_forget_skill({"id": mid}, "zhouyingchao")
        self.assertTrue(r2["ok"])

        r3 = mem.memory_search_skill({"query": "临时记忆"}, "zhouyingchao")
        self.assertEqual(r3["count"], 0)

    def test_memory_summarize(self):
        mem.memory_remember_skill({"content": "事件1", "type": "event"}, "zhouyingchao")
        mem.memory_remember_skill({"content": "事件2", "type": "event"}, "zhouyingchao")
        r = mem.memory_summarize_skill({"type": "event"}, "zhouyingchao")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(r["count"], 2)
        self.assertIn("event", r["types"])


if __name__ == "__main__":
    unittest.main()
