"""PDF 页面与 Markdown 预览同步的前端回归检查。"""
import unittest
from pathlib import Path


STUDIO = Path(__file__).resolve().parents[2] / "ai-office-assistant-web" / "src" / "views" / "KnowledgeBaseView" / "PdfMarkdownStudio.vue"


class PdfMarkdownFrontendTests(unittest.TestCase):
    def test_page_changes_scroll_markdown_preview_to_matching_page_heading(self):
        source = STUDIO.read_text(encoding="utf-8")

        self.assertIn("const mdPreviewRef = ref<HTMLElement | null>(null)", source)
        self.assertIn("function syncMarkdownPreview(page: number)", source)
        self.assertIn("`第 ${page} 页`", source)
        self.assertIn("preview.scrollTo({ top", source)
        self.assertIn('ref="mdPreviewRef"', source)
        self.assertIn("syncMarkdownPreview(currentPage.value)", source)


if __name__ == "__main__":
    unittest.main()
