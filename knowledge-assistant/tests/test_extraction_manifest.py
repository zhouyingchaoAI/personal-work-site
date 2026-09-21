from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeAssistantExtractionTests(unittest.TestCase):
    def test_extraction_contains_reusable_source_bundle(self):
        expected_files = [
            "README.md",
            "backend/knowledge.py",
            "backend/http_routes.py",
            "backend/mcp_tools.py",
            "frontend/KnowledgeBaseView/index.vue",
            "frontend/KnowledgeBaseView/index.scss",
            "frontend/personalWorkApi.knowledge.ts",
            "tests/upstream/test_knowledge_kb_selection.py",
            "tests/upstream/test_knowledge_citations_frontend.py",
        ]

        missing = [path for path in expected_files if not (ROOT / path).is_file()]
        self.assertFalse(missing, f"知识库助手抽取不完整：{missing}")

    def test_extracted_bundle_has_no_fastgpt_integration(self):
        tracked_sources = [
            ROOT / "backend/knowledge.py",
            ROOT / "backend/mcp_tools.py",
            ROOT / "frontend/KnowledgeBaseView/index.vue",
            ROOT / "frontend/personalWorkApi.knowledge.ts",
        ]
        matches = [str(path.relative_to(ROOT)) for path in tracked_sources if "fastgpt" in path.read_text(encoding="utf-8").lower()]
        self.assertFalse(matches, f"抽取包不应包含 FastGPT 集成：{matches}")


if __name__ == "__main__":
    unittest.main()
