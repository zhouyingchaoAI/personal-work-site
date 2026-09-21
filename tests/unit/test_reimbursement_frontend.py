import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REIMBURSEMENT_VIEW = ROOT / "ai-office-assistant-web" / "src" / "views" / "ReimbursementView" / "index.vue"


class ReimbursementFrontendTests(unittest.TestCase):
    def setUp(self):
        self.source = REIMBURSEMENT_VIEW.read_text(encoding="utf-8")

    def test_merge_payload_includes_invoice_metadata_for_backend_sorting_and_grouping(self):
        start = self.source.index("async function handleMerge()")
        end = self.source.index("// ──────────── 预览", start)
        body = self.source[start:end]

        self.assertIn("invoice_type: i.invoice_type", body)
        self.assertIn("invoice_date: i.invoice_date", body)
        self.assertIn("invoice_amount: i.invoice_amount", body)


    def test_search_record_ui_loads_saves_and_appends_scan_results(self):
        self.assertIn("listReimbursementSearches", self.source)
        self.assertIn("saveReimbursementSearch", self.source)
        self.assertIn("loadReimbursementSearch", self.source)
        self.assertIn("currentSearchId", self.source)
        self.assertIn("await persistCurrentSearch", self.source)
        self.assertIn("搜索记录", self.source)

    def test_scan_chunks_retry_once_before_marking_failed(self):
        self.assertIn("scanInvoiceAttachmentsWithRetry", self.source)
        self.assertIn("retry = 1", self.source)
        self.assertIn("正在重试", self.source)

    def test_batch_download_uses_selected_invoice_metadata(self):
        self.assertIn("downloadReimbursementInvoicesZip", self.source)
        self.assertIn("handleBatchDownload", self.source)
        self.assertIn("批量下载", self.source)
        start = self.source.index("async function handleBatchDownload()")
        end = self.source.index("// ──────────── 预览", start)
        body = self.source[start:end]
        for field in ["invoice_type", "invoice_date", "invoice_amount", "invoice_location", "invoice_from", "invoice_to"]:
            self.assertIn(field + ": i." + field, body)

    def test_manual_retry_chunk_uses_retrying_scan_helper(self):
        start = self.source.index("async function retryScanChunk")
        end = self.source.index("function toggleFilteredItems", start)
        body = self.source[start:end]
        self.assertIn("scanSingleChunk(chunk", body)
        self.assertIn("正在重扫", body)
        self.assertIn("scanInvoiceAttachmentsWithRetry(chunk.start, chunk.end, account.value", self.source)
        self.assertIn("正在重试", self.source)

    def test_invoice_type_filter_limits_visible_rows_and_selects_filtered_type(self):
        self.assertIn("invoiceTypeFilter", self.source)
        self.assertIn("filteredItems", self.source)
        self.assertIn("v-for=\"(item, index) in filteredItems\"", self.source)
        self.assertIn("function toggleFilteredItems", self.source)
        self.assertIn("filteredItems.value.forEach", self.source)
        self.assertIn("全选当前类型", self.source)
        self.assertIn("指定类型", self.source)


    def test_api_request_handles_non_json_html_response_before_parsing(self):
        api_source = (ROOT / "ai-office-assistant-web" / "src" / "services" / "personalWorkApi.ts").read_text(encoding="utf-8")
        self.assertIn("content-type", api_source)
        self.assertIn("rawText.trim().startsWith(\"<\")", api_source)
        self.assertIn("返回了页面内容", api_source)


    def test_search_record_persists_and_restores_scan_chunks(self):
        self.assertIn("scan_chunks?: ScanChunkState[]", self.source)
        self.assertIn("scanChunks.value = (record.scan_chunks || []).map", self.source)
        self.assertIn("scan_chunks: scanChunks.value", self.source)
        self.assertIn("await persistCurrentSearch(chunk.start, chunk.end, chunk.total_scanned || 0, true)", self.source)

    def test_retry_multi_day_chunk_splits_into_daily_chunks(self):
        start = self.source.index("async function retryScanChunk")
        end = self.source.index("function toggleFilteredItems", start)
        body = self.source[start:end]
        self.assertIn("splitDateRange(chunk.start, chunk.end, 1)", body)
        self.assertIn("scanDailySubChunks", body)
        self.assertIn("replaceScanChunk", body)


    def test_stale_scanning_chunks_can_be_retried_after_history_load(self):
        self.assertIn("上次扫描中断，可重扫", self.source)
        self.assertIn("chunk.status === 'failed' || chunk.status === 'scanning'", self.source)

    def test_page_load_does_not_resume_or_start_a_scan_automatically(self):
        mounted_start = self.source.index("onMounted(async () => {")
        mounted_end = self.source.index("function chunkKey", mounted_start)
        mounted_body = self.source[mounted_start:mounted_end]
        self.assertIn("await refreshSearchRecords()", mounted_body)
        self.assertNotIn("scanInvoiceAttachments", mounted_body)
        self.assertNotIn("scanChunkQueue", mounted_body)
        self.assertNotIn("resumeInterruptedScan", self.source)


    def test_default_scan_chunks_are_weekly_before_daily_fallback(self):
        self.assertIn("const SCAN_CHUNK_DAYS = 7", self.source)

    def test_initial_scan_failed_multi_day_chunk_auto_splits_into_daily_chunks(self):
        # handleScan 委托 scanChunkQueue，逐片扫描；失败的多日切片自动拆成按日重扫。
        start = self.source.index("async function handleScan")
        end = self.source.index("async function retryScanChunk", start)
        body = self.source[start:end]
        self.assertIn("await scanChunkQueue(nextChunks)", body)
        self.assertIn("liveChunk.status === \"failed\"", body)
        self.assertIn("await scanDailySubChunks(liveChunk)", body)


if __name__ == "__main__":
    unittest.main()
