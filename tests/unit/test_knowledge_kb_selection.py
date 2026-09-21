import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt


class KnowledgeKbSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_kb_dir = rt._kb_dir
        self.old_request = rt._ragflow_request
        self.old_account = rt._ragflow_user_account
        self.old_shared = rt._ragflow_shared_dataset_id
        self.old_named = rt._ragflow_named_dataset
        rt._kb_dir = lambda: Path(self.tmp.name)
        rt._ragflow_user_account = lambda settings, username: {"api_key": "user-key"}
        rt._ragflow_shared_dataset_id = lambda settings: "shared"
        rt._ragflow_named_dataset = lambda settings, name, cache_key, permission="": "personal"

    def tearDown(self):
        rt._kb_dir = self.old_kb_dir
        rt._ragflow_request = self.old_request
        rt._ragflow_user_account = self.old_account
        rt._ragflow_shared_dataset_id = self.old_shared
        rt._ragflow_named_dataset = self.old_named
        self.tmp.cleanup()

    def test_selected_dataset_ids_default_to_personal_first_then_shared(self):
        def fake_request(settings, method, path, body=None, **kwargs):
            if path.startswith("/api/v1/datasets"):
                return [
                    {"id": "shared", "chunk_count": 10},
                    {"id": "personal", "chunk_count": 20},
                    {"id": "empty", "chunk_count": 0},
                ]
            raise AssertionError(path)

        rt._ragflow_request = fake_request

        user_settings, dataset_ids = rt._ragflow_selected_query_datasets({}, "zhaoqinglin", [])

        self.assertEqual(user_settings["ragflow_api_key"], "user-key")
        self.assertEqual(dataset_ids, ["personal", "shared"])

    def test_selected_dataset_ids_filters_to_manual_selection(self):
        def fake_request(settings, method, path, body=None, **kwargs):
            if path.startswith("/api/v1/datasets"):
                return [
                    {"id": "shared", "chunk_count": 10},
                    {"id": "personal", "chunk_count": 20},
                ]
            raise AssertionError(path)

        rt._ragflow_request = fake_request

        _, dataset_ids = rt._ragflow_selected_query_datasets({}, "zhaoqinglin", ["personal"])

        self.assertEqual(dataset_ids, ["personal"])

    def test_ragflow_retrieval_uses_minimum_page_size_then_honors_requested_limit(self):
        """RAGFlow returns no chunks for a page size of one on this deployment."""
        captured = {}

        def fake_request(settings, method, path, body=None, **kwargs):
            self.assertEqual((method, path), ("POST", "/api/v1/retrieval"))
            captured.update(body)
            return {
                "chunks": [
                    {"document_id": "doc-1", "dataset_id": "shared", "document_keyword": "制度.pdf", "content": "第一条", "similarity": 0.9},
                    {"document_id": "doc-2", "dataset_id": "shared", "document_keyword": "制度.pdf", "content": "第二条", "similarity": 0.8},
                ]
            }

        rt._ragflow_request = fake_request
        result = rt._ragflow_search("报销制度", 1, {"ragflow_api_key": "service-key"}, ["shared"])

        self.assertEqual(captured["page_size"], 2)
        self.assertEqual([item["doc_id"] for item in result["results"]], ["doc-1"])

    def test_chat_cache_key_is_isolated_by_dataset_selection(self):
        settings = {"ragflow_api_key": "user-key"}
        created = []

        def fake_request(settings, method, path, body=None, **kwargs):
            if path.startswith("/api/v1/chats?page"):
                return []
            if method == "POST" and path == "/api/v1/chats":
                created.append(body)
                return {"id": f"chat-{len(created)}"}
            if method == "PUT" and path.startswith("/api/v1/chats/") and body.get("prompt"):
                return {"id": path.rsplit("/", 1)[-1]}
            raise AssertionError((method, path, body))

        rt._ragflow_request = fake_request

        all_chat = rt._ragflow_user_chat_id(settings, "zhaoqinglin", ["personal", "shared"])
        personal_chat = rt._ragflow_user_chat_id(settings, "zhaoqinglin", ["personal"])
        all_chat_again = rt._ragflow_user_chat_id(settings, "zhaoqinglin", ["shared", "personal"])

        self.assertEqual(all_chat, "chat-1")
        self.assertEqual(personal_chat, "chat-2")
        self.assertEqual(all_chat_again, "chat-1")
        self.assertEqual(created[0]["dataset_ids"], ["personal", "shared"])
        self.assertEqual(created[1]["dataset_ids"], ["personal"])

    def test_ragflow_ask_generation_uses_direct_retrieval_sources(self):
        old_search = rt._ragflow_search
        old_llm = rt._meeting_llm_chat
        try:
            rt._ragflow_search = lambda query, top_k, settings, dataset_ids: {"ok": True, "results": [
                {"doc_id": "d1", "dataset_id": "personal", "doc_name": "车门培训教材.pdf", "score": 0.42, "text": "车门维护界面显示每个车门状态、故障以及车门列车线状态。", "page": 3}
            ]}
            rt._meeting_llm_chat = lambda system, user, temperature=0.2: "# 车门系统新员工考试试卷\n一、单选题：车门维护界面可查看什么？"
            def fake_request(settings, method, path, body=None, **kwargs):
                if path.startswith("/api/v1/datasets"):
                    return [{"id": "personal", "chunk_count": 10}]
                self.fail("generation fallback should not call chat completion")
            rt._ragflow_request = fake_request

            result = rt._ragflow_ask(
                "你能帮我生成一份关于车门系统的试卷吗，我要给新员工考试",
                5,
                "zhaoqinglin",
                {"ragflow_api_key": "user-key"},
                selected_kb_ids=["personal"],
            )

            self.assertIn("车门系统新员工考试试卷", result["answer"])
            self.assertEqual(result["sources"][0]["dataset_id"], "personal")
        finally:
            rt._ragflow_search = old_search
            rt._meeting_llm_chat = old_llm

    def test_ragflow_ask_normalizes_large_reference_ids_to_returned_sources(self):
        chunks = [
            {"document_id": f"d{i}", "dataset_id": "personal", "document_name": "无关.pdf", "similarity": 0.1, "content": "无关片段"}
            for i in range(101)
        ]
        chunks[100] = {
            "document_id": "brake-case",
            "dataset_id": "personal",
            "document_name": "2019年年度车辆部故障台账-检修13车间.xlsx",
            "similarity": 0.57,
            "content": "1302 信号屏出现不明原因紧制，红手掌红方框，车辆屏显示牵引封锁。",
        }

        def fake_request(settings, method, path, body=None, **kwargs):
            if path.startswith("/api/v1/datasets"):
                return [{"id": "personal", "chunk_count": 10}]
            if path.startswith("/api/v1/chats?page"):
                return []
            if method == "POST" and path == "/api/v1/chats":
                return {"id": "chat-1"}
            if method == "PUT" and path == "/api/v1/chats/chat-1":
                return {"id": "chat-1"}
            if method == "POST" and path == "/api/v1/chats/chat-1/sessions":
                return {"id": "session-1"}
            if method == "POST" and path == "/api/v1/chats/chat-1/completions":
                return {
                    "answer": "制动系统通信问题案例见 [ID:100]。",
                    "reference": {"chunks": chunks},
                }
            raise AssertionError((method, path, body))

        rt._ragflow_request = fake_request

        result = rt._ragflow_ask(
            "车辆紧急制动有没有故障案例",
            5,
            "zhaoqinglin",
            {"ragflow_api_key": "user-key"},
            selected_kb_ids=["personal"],
        )

        self.assertEqual(result["answer"], "制动系统通信问题案例见 [ID:0]。")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["doc_id"], "brake-case")
        self.assertEqual(result["sources"][0]["index"], 1)

    def test_ragflow_ask_maps_large_reference_ids_when_reference_contains_only_returned_chunks(self):
        chunks = [
            {"document_id": "c1", "dataset_id": "personal", "document_name": "故障台账.xlsx", "similarity": 0.52, "content": "1332 古镇口上行进站紧制。"},
            {"document_id": "c2", "dataset_id": "personal", "document_name": "故障台账.xlsx", "similarity": 0.49, "content": "1301 泊里站台门打开导致紧制。"},
            {"document_id": "c3", "dataset_id": "personal", "document_name": "故障台账.xlsx", "similarity": 0.47, "content": "1302 网络与车载信号系统通信传输问题。"},
        ]

        answer, sources = rt._ragflow_normalize_answer_sources(
            "信号触发见 [ID:68]，站台门见 [ID:69]，通信问题见 ##70$$。",
            {"chunks": chunks},
            5,
        )

        self.assertEqual(answer, "信号触发见 [ID:0]，站台门见 [ID:1]，通信问题见 [ID:2]。")
        self.assertEqual([source["doc_id"] for source in sources], ["c1", "c2", "c3"])
        self.assertEqual([source["index"] for source in sources], [1, 2, 3])

    def test_existing_chat_reorders_datasets_when_order_changes(self):
        settings = {"ragflow_api_key": "user-key"}
        calls = []

        def fake_request(settings, method, path, body=None, **kwargs):
            calls.append((method, path, body))
            if method == "PUT" and path == "/api/v1/chats/chat-existing":
                return {"id": "chat-existing"}
            raise AssertionError((method, path, body))

        rt._ragflow_request = fake_request
        rt._kb_mapping_save("ragflow_tenant_chats.json", {
            rt._ragflow_chat_cache_key("zhaoqinglin", ["personal", "shared"]): {"id": "chat-existing", "datasets": ["shared", "personal"]}
        })

        chat_id = rt._ragflow_user_chat_id(settings, "zhaoqinglin", ["personal", "shared"])

        self.assertEqual(chat_id, "chat-existing")
        self.assertEqual(calls[0][2]["dataset_ids"], ["personal", "shared"])

    def test_existing_chat_prompt_is_refreshed_for_relevant_limited_content(self):
        settings = {"ragflow_api_key": "user-key"}
        calls = []

        def fake_request(settings, method, path, body=None, **kwargs):
            calls.append((method, path, body))
            if method == "PUT" and path == "/api/v1/chats/chat-existing":
                return {"id": "chat-existing"}
            raise AssertionError((method, path, body))

        rt._ragflow_request = fake_request
        rt._kb_mapping_save("ragflow_tenant_chats.json", {
            rt._ragflow_chat_cache_key("zhaoqinglin", ["personal"]): {"id": "chat-existing", "datasets": ["personal"]}
        })

        chat_id = rt._ragflow_user_chat_id(settings, "zhaoqinglin", ["personal"])

        self.assertEqual(chat_id, "chat-existing")
        put_body = calls[0][2]
        prompt = put_body["prompt"]["prompt"]
        self.assertIn("资料片段相关但不完整", prompt)
        self.assertIn("基于现有资料", prompt)
        self.assertIn("只有当资料片段全部无关时", prompt)


if __name__ == "__main__":
    unittest.main()
