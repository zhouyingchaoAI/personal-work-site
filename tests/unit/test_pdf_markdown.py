"""PDF 转 Markdown 工具的本地覆盖（不依赖 RAGFlow / Docker）。

只验证网关侧职责：上传解码、页面渲染、区域裁剪成单页 PDF、Markdown 存取、
以及非 RAGFlow 引擎时的清晰报错。真正的 DeepDoc OCR 走 RAGFlow，不在此测。
"""
import base64
import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:  # pragma: no cover - 仅在缺依赖的环境跳过
    HAS_FITZ = False


def _sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=420, height=300)
    page.insert_text((40, 80), "PDF to Markdown unit test", fontsize=20)
    page.insert_text((40, 200), "bottom region content 12345", fontsize=16)
    return doc.tobytes()


def _pdf_with_image() -> bytes:
    import io
    from PIL import Image

    img = Image.new("RGB", (200, 120), (30, 120, 220))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    doc = fitz.open()
    page = doc.new_page(width=420, height=400)
    page.insert_text((40, 60), "page with figure", fontsize=18)
    page.insert_image(fitz.Rect(60, 120, 300, 260), stream=buf.getvalue())
    return doc.tobytes()


@unittest.skipUnless(HAS_FITZ, "需要 PyMuPDF(fitz)")
class PdfMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_user_data_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name) / "user_data"
        rt.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.user = "tester"
        self.payload = {
            "filename": "unit.pdf",
            "data": base64.b64encode(_sample_pdf()).decode("ascii"),
        }

    def tearDown(self):
        rt.USER_DATA_DIR = self.old_user_data_dir
        self.tmp.cleanup()

    def test_create_renders_pages_and_provisional_markdown(self):
        res = rt.pdf_md_create(self.payload, self.user)
        job = res["job"]
        self.assertTrue(res["ok"])
        self.assertEqual(job["page_count"], 1)
        self.assertEqual(job["ocr_engine"], "fitz-text")
        self.assertFalse(job["ocr_done"])
        self.assertEqual(job["parse_status"], "idle")
        self.assertEqual(len(job["pages"]), 1)
        self.assertGreater(job["pages"][0]["width"], 0)
        # 文本层初稿应包含正文文字。
        self.assertIn("PDF to Markdown unit test", job["markdown"])
        # 页面 PNG 已渲染并可读取。
        name, raw = rt.pdf_md_page_image(job["id"], "1", self.user)
        self.assertTrue(name.endswith(".png"))
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")

    def test_create_extracts_figures_into_page_markdown_with_asset_url(self):
        res = rt.pdf_md_create({"filename": "fig.pdf", "data": base64.b64encode(_pdf_with_image()).decode("ascii")}, self.user)
        job = res["job"]

        self.assertIn("## 第 1 页", job["markdown"])
        self.assertIn(f"/personal-office-assistant/api/knowledge/pdf-md/asset?job_id={job['id']}&name=p1_1.png", job["markdown"])
        name, content_type, raw = rt.pdf_md_asset(job["id"], "p1_1.png", self.user)
        self.assertEqual(name, "p1_1.png")
        self.assertEqual(content_type, "image/png")
        self.assertGreater(len(raw), 0)

    def test_rejects_non_pdf_and_empty(self):
        with self.assertRaises(ValueError):
            rt.pdf_md_create({"filename": "a.txt", "data": self.payload["data"]}, self.user)
        with self.assertRaises(ValueError):
            rt.pdf_md_create({"filename": "a.pdf", "data": ""}, self.user)

    def test_region_pdf_is_single_page_image(self):
        job = rt.pdf_md_create(self.payload, self.user)["job"]
        job_dir = rt._pdfmd_job_dir(self.user, job["id"])
        region = rt._pdfmd_region_pdf(job_dir, 1, {"x0": 0.05, "y0": 0.5, "x1": 0.95, "y1": 0.85})
        out = fitz.open("pdf", region)
        self.assertEqual(out.page_count, 1)
        # 该单页由裁剪区域栅格化而来，尺寸为正。
        self.assertGreater(out[0].rect.width, 0)

    def test_region_rejects_tiny_selection(self):
        job = rt.pdf_md_create(self.payload, self.user)["job"]
        job_dir = rt._pdfmd_job_dir(self.user, job["id"])
        with self.assertRaises(ValueError):
            rt._pdfmd_region_pdf(job_dir, 1, {"x0": 0.5, "y0": 0.5, "x1": 0.501, "y1": 0.9})

    def test_region_ocr_appends_urls_for_images_inside_the_selection(self):
        job = rt.pdf_md_create({"filename": "fig.pdf", "data": base64.b64encode(_pdf_with_image()).decode("ascii")}, self.user)["job"]
        old_staging = rt._pdfmd_staging_dataset
        old_ocr = rt._pdfmd_deepdoc_ocr
        rt._pdfmd_staging_dataset = lambda username: ({}, "staging")
        rt._pdfmd_deepdoc_ocr = lambda settings, dataset_id, filename, raw, timeout=240: "识别出的区域文字"
        try:
            result = rt.pdf_md_region({
                "job_id": job["id"], "page": 1,
                "rect": {"x0": 0.1, "y0": 0.2, "x1": 0.8, "y1": 0.8},
            }, self.user)
        finally:
            rt._pdfmd_staging_dataset = old_staging
            rt._pdfmd_deepdoc_ocr = old_ocr

        self.assertIn("识别出的区域文字", result["markdown"])
        self.assertIn(
            f"/personal-office-assistant/api/knowledge/pdf-md/asset?job_id={job['id']}&name=p1_1.png",
            result["markdown"],
        )

    def test_save_get_list_delete_roundtrip(self):
        job = rt.pdf_md_create(self.payload, self.user)["job"]
        rt.pdf_md_save({"job_id": job["id"], "markdown": "# 校对后的标题\n\n正文"}, self.user)
        got = rt.pdf_md_get(job["id"], self.user)["job"]
        self.assertEqual(got["markdown"], "# 校对后的标题\n\n正文")
        listed = rt.pdf_md_list(self.user)["jobs"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], job["id"])
        rt.pdf_md_delete({"job_id": job["id"]}, self.user)
        self.assertEqual(rt.pdf_md_list(self.user)["jobs"], [])
        with self.assertRaises(ValueError):
            rt.pdf_md_get(job["id"], self.user)

    def test_ocr_requires_ragflow_engine(self):
        job = rt.pdf_md_create(self.payload, self.user)["job"]
        old = rt.kb_embedding_settings
        rt.kb_embedding_settings = lambda: {"provider": "builtin", "ragflow_api_key": ""}
        try:
            with self.assertRaises(ValueError):
                rt.pdf_md_parse({"job_id": job["id"]}, self.user)
            with self.assertRaises(ValueError):
                rt.pdf_md_region({"job_id": job["id"], "page": 1, "rect": {"x0": 0, "y0": 0, "x1": 1, "y1": 1}}, self.user)
        finally:
            rt.kb_embedding_settings = old

    def test_extract_figures_and_serve_asset(self):
        job = rt.pdf_md_create({"filename": "fig.pdf", "data": base64.b64encode(_pdf_with_image()).decode("ascii")}, self.user)["job"]
        job_dir = rt._pdfmd_job_dir(self.user, job["id"])
        doc = fitz.open(str(job_dir / "source.pdf"))
        try:
            figures = rt._pdfmd_extract_figures(doc, job_dir, 0)
        finally:
            doc.close()
        self.assertGreaterEqual(len(figures), 1)
        name, content_type, raw = rt.pdf_md_asset(job["id"], figures[0]["name"], self.user)
        self.assertTrue(content_type.startswith("image/"))
        self.assertGreater(len(raw), 0)
        # 资源名做过白名单校验，路径穿越应被拒。
        with self.assertRaises(ValueError):
            rt.pdf_md_asset(job["id"], "../meta.json", self.user)

    def test_layout_markdown_keeps_each_card_caption_with_its_image_url(self):
        """卡片页线性化后，每张图片 URL 后紧跟该卡片的文字说明。"""
        doc = fitz.open()
        try:
            page = doc.new_page(width=600, height=400)
            page.insert_text((20, 40), "Defect photo cards", fontsize=12)
            page.insert_textbox(fitz.Rect(140, 120, 300, 180), "Card one title", fontsize=12)
            page.insert_textbox(fitz.Rect(140, 185, 300, 245), "Card one detail", fontsize=12)
            page.insert_textbox(fitz.Rect(440, 120, 590, 180), "Card two title", fontsize=12)
            page.insert_textbox(fitz.Rect(440, 185, 590, 245), "Card two detail", fontsize=12)
            markdown = rt._pdfmd_page_layout_markdown(page, [
                {"name": "p1_1.jpeg", "order": 1, "bbox": [10, 100, 120, 250]},
                {"name": "p1_2.jpeg", "order": 2, "bbox": [310, 100, 420, 250]},
            ], "pmtest", 1)
        finally:
            doc.close()

        first_image = markdown.index("name=p1_1.jpeg")
        first_caption = markdown.index("Card one title")
        second_image = markdown.index("name=p1_2.jpeg")
        second_caption = markdown.index("Card two title")
        self.assertLess(first_image, first_caption)
        self.assertLess(first_caption, second_image)
        self.assertLess(second_image, second_caption)
        self.assertIn("- Card one title", markdown)
        self.assertIn("  - Card one detail", markdown)

    def test_user_isolation(self):
        job = rt.pdf_md_create(self.payload, self.user)["job"]
        # 另一个用户看不到、也读不到该任务。
        self.assertEqual(rt.pdf_md_list("other")["jobs"], [])
        with self.assertRaises(ValueError):
            rt.pdf_md_get(job["id"], "other")


if __name__ == "__main__":
    unittest.main()
