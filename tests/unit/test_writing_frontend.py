import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MENU = ROOT / "ai-office-assistant-web" / "src" / "layout" / "menu.ts"
WORKSPACE = ROOT / "ai-office-assistant-web" / "src" / "views" / "WorkspaceView" / "index.vue"
API = ROOT / "ai-office-assistant-web" / "src" / "services" / "personalWorkApi.ts"
VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "WritingAssistantView" / "index.vue"
STYLE = ROOT / "ai-office-assistant-web" / "src" / "views" / "WritingAssistantView" / "index.scss"


class WritingFrontendTest(unittest.TestCase):
    def test_menu_and_workspace_register_writing_assistant(self):
        menu = MENU.read_text(encoding="utf-8")
        workspace = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn("'writing'", menu)
        self.assertIn("智能写作", menu)
        self.assertIn("WritingAssistantView", workspace)
        self.assertIn("activeMenu === 'writing'", workspace)

    def test_writing_editor_autosaves_and_shows_content_stats(self):
        view = VIEW.read_text(encoding="utf-8")
        self.assertIn("WRITING_DRAFT_KEY", view)
        self.assertIn("authState.user?.username", view)
        self.assertIn("WRITING_DRAFT_KEY.value", view)
        self.assertIn("scheduleDraftSave", view)
        self.assertIn("restoreDraft", view)
        self.assertIn("contentStats", view)

    def test_api_helpers_exist(self):
        source = API.read_text(encoding="utf-8")
        for name in [
            "getWritingTemplates",
            "saveWritingTemplate",
            "getWritingHistory",
            "getWritingHistoryItem",
            "uploadWritingFile",
            "generateWritingOutline",
            "generateWritingDraft",
            "rewriteWritingDraft",
            "exportWritingDraft",
            "deleteWritingHistory",
        ]:
            self.assertIn(f"function {name}", source)

    def test_page_contains_core_controls(self):
        self.assertTrue(VIEW.exists())
        self.assertTrue(STYLE.exists())
        source = VIEW.read_text(encoding="utf-8")
        for text in ["智能写作", "参考知识库", "上传素材", "生成大纲", "生成正文", "文稿历史", "导出 Excel", "导出 Word", "保存模板"]:
            self.assertIn(text, source)
        self.assertIn("type=\"file\"", source)
        self.assertIn("multiple", source)

    def test_material_library_is_collapsed_and_requires_explicit_selection(self):
        source = VIEW.read_text(encoding="utf-8")
        self.assertIn("selectedMaterialIds", source)
        self.assertIn("visibleMaterials", source)
        self.assertIn("展开全部素材", source)
        self.assertIn("file_ids: selectedMaterialIds.value", source)

    def test_can_select_personal_weekly_or_trip_reports_as_references(self):
        source = VIEW.read_text(encoding="utf-8")
        self.assertIn("getReports", source)
        self.assertIn("selectedReportRefs", source)
        self.assertIn("report_refs: selectedReportRefs.value", source)
        self.assertIn("历史报告", source)
        self.assertIn("个人历史周报或出差报告", source)

    def test_history_uses_a_separate_writing_page(self):
        source = VIEW.read_text(encoding="utf-8")
        self.assertIn("activeWritingPage", source)
        self.assertIn("文稿历史", source)
        self.assertIn("writing-history-page", source)
        self.assertIn("activeWritingPage = 'editor'", source)
        self.assertIn("未命名文稿", source)
        self.assertIn("暂无正文预览", source)

    def test_history_cards_keep_readable_natural_height(self):
        style = STYLE.read_text(encoding="utf-8")
        self.assertIn("grid-auto-rows: minmax(108px, auto)", style)
        self.assertIn("grid-template-rows: auto auto minmax(0, 1fr)", style)
        self.assertIn("-webkit-line-clamp: 2", style)

    def test_editor_does_not_render_a_separate_source_excerpt_panel(self):
        source = VIEW.read_text(encoding="utf-8")
        self.assertNotIn('<h2>引用来源</h2>', source)


if __name__ == "__main__":
    unittest.main()
