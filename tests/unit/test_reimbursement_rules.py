import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt
from tests.unit.officedb_testing import db_variant


class ReimbursementRuleExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = rt.USER_DATA_DIR
        rt.USER_DATA_DIR = Path(self.tmp.name)

    def tearDown(self):
        rt.USER_DATA_DIR = self.original_dir
        self.tmp.cleanup()

    def test_single_train_ticket_uses_quarter_page_layout_when_grouping(self):
        import re
        import uuid

        import pypdf
        from PIL import Image

        username = "unit_train_merge"
        key = "train_" + uuid.uuid4().hex
        image = Image.new("RGB", (200, 100), "white")
        pdf_buffer = __import__("io").BytesIO()
        image.save(pdf_buffer, format="PDF")
        rt._save_cache(username, key, "train-ticket.pdf", pdf_buffer.getvalue())

        result = rt.merge_reimbursement_pdf(
            username,
            [{"key": key, "invoice_type": "火车"}],
            "single-train-quarter-layout",
            merge_train_tickets=True,
        )

        out_path, out_raw = rt.get_reimbursement_output(username, result["filename"])
        self.assertEqual(out_path.name, result["filename"])
        self.assertEqual([f["filename"] for f in rt.list_reimbursement_outputs(username)], [result["filename"]])
        reader = pypdf.PdfReader(__import__("io").BytesIO(out_raw))
        content = reader.pages[0].get_contents().get_data().decode("latin1", errors="ignore")
        scales = [float(value) for value in re.findall(r"q\s+([0-9.]+)\s+0\.0\s+0\.0\s+[0-9.]+\s+", content)]

        self.assertEqual(result["train_ticket_count"], 1)
        self.assertEqual(result["train_ticket_groups"], 1)
        self.assertTrue(scales, content)
        self.assertLess(max(scales), 3.0)

    def test_extracts_vat_invoice_fields_from_pdf_text(self):
        candidate = {
            "key": "hotel",
            "filename": "dzfp.pdf",
            "email_subject": "电子发票",
            "_content": (
                "电子发票（增值税专用发票） 价税合计（大写） （小写） "
                "¥282.18 ¥2.82 贰佰捌拾伍圆整 ¥ 285.00 "
                "26332000004021069771 2026年05月15日 "
                "湖南承希科技有限公司 杭州欧诺酒店有限公司 "
                "*住宿服务*住宿费"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_type"], "住宿")
        self.assertEqual(meta["invoice_date"], "2026-05-15")
        self.assertEqual(meta["invoice_amount"], "¥285.00")
        self.assertEqual(meta["invoice_location"], "杭州欧诺酒店")

    def test_extracts_telecom_invoice_fields_without_using_large_numbers(self):
        candidate = {
            "key": "tel",
            "filename": "DZFP.pdf",
            "email_subject": "中国移动电子发票",
            "_content": (
                "开票日期：2026年04月03日 名称：中国移动通信集团湖南有限公司长沙分公司 "
                "*电信服务*通信服务费 1 117.9 117.90 合 计 ¥113.90 "
                "价税合计（大写） 壹佰壹拾叁圆玖角整 （小写）¥113.90 "
                "银行账号：43001710661050003739"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_type"], "通讯费")
        self.assertEqual(meta["invoice_date"], "2026-04-03")
        self.assertEqual(meta["invoice_amount"], "¥113.90")


    def test_telecom_usage_report_is_not_invoice_email(self):
        self.assertFalse(rt._is_invoice_email(
            "【139邮箱使用报告】您的2026年5月使用报告已生成，快来看看！",
            "中国移动139邮箱 <mail139@139.com>",
        ))
        self.assertTrue(rt._is_invoice_email(
            "【移动发票】您的电子发票已送达，敬请查阅！",
            "10086@139.com",
        ))

    def test_extracts_flight_receipt_fields_and_ignores_table_header(self):
        candidate = {
            "key": "flight",
            "filename": "行程校验单.pdf",
            "email_subject": "机票",
            "_content": (
                "姓名: 周颖超 总价: 1240.0 类别: 机票 序号 日期 航班号 出发/到达 "
                "1 2026-04-17CZ5822 青岛胶东/长沙黄花 7842175538585M "
                "1240.0（1070.0+50.0+120.0）已使用"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_type"], "机票")
        self.assertEqual(meta["invoice_date"], "2026-04-17")
        self.assertEqual(meta["invoice_amount"], "¥1240.00")
        self.assertEqual(meta["invoice_from"], "青岛胶东")
        self.assertEqual(meta["invoice_to"], "长沙黄花")

    def test_extracts_air_ticket_cny_amount_and_route(self):
        candidate = {
            "key": "air",
            "filename": "invoice.ofd",
            "email_subject": "航空运输电子客票行程单",
            "_content": (
                "电子发票（航空运输电子客票行程单） 航班号 座位等级 日期 时间 "
                "客票级别/客票类别 南航 CZ3694 E 2026年06月05日 17:15 "
                "自： TSN 天津 至： CSX 长沙 票价 燃油附加费 合计 "
                "CNY 431.19 CNY 155.96 CNY 50.00 CNY 690.00"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_type"], "机票")
        self.assertEqual(meta["invoice_date"], "2026-06-05")
        self.assertEqual(meta["invoice_amount"], "¥690.00")
        self.assertEqual(meta["invoice_from"], "天津")
        self.assertEqual(meta["invoice_to"], "长沙")

    def test_air_ticket_total_does_not_use_masked_id_suffix_as_amount(self):
        candidate = {
            "key": "air-ticket-id-suffix",
            "filename": "电子行程单.pdf",
            "email_subject": "电子行程单",
            "_content": (
                "票价 燃油附加费 增值税税率 增值税税额 民航发展基金 其他税费 合计 "
                "电子客票号码: 验证码: 提示信息: 保险费: 购买方名称: 统一社会信用代码/纳税人识别号: "
                "26468880111050895967 周颖超 362424********5911 "
                "CNY 688.07 CNY 91.74 9% CNY 70.19 CNY 50.00 CNY 0.00 CNY 900.00"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_amount"], "¥900.00")

    def test_extracts_railway_ofd_route_and_amount(self):
        candidate = {
            "key": "rail",
            "filename": "ticket.ofd",
            "email_subject": "铁路电子客票",
            "_content": (
                "电子发票（铁路电子客票） 售 衢州 Quzhou 长沙南 Changshanan "
                "G2347 2026-05-15 19:30 二等座 票价: ￥ 330.00 "
                "网上购票系统/电子发票通知"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_type"], "火车")
        self.assertEqual(meta["invoice_date"], "2026-05-15")
        self.assertEqual(meta["invoice_amount"], "¥330.00")
        self.assertEqual(meta["invoice_from"], "衢州")
        self.assertEqual(meta["invoice_to"], "长沙南")

    def test_extracts_usd_invoice_date_and_amount(self):
        candidate = {
            "key": "usd",
            "filename": "Invoice-563483.pdf",
            "email_subject": "Invoice",
            "_content": (
                "Invoice #563483 Invoice Date: 03/06/2026 Due Date: 03/06/2026 "
                "Description Total V2Ray-Mini $1.90 USD Sub Total $1.90 USD "
                "Credit $0.00 USD Total $1.90 USD Balance $1.90 USD"
            ),
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_date"], "2026-06-03")
        self.assertEqual(meta["invoice_amount"], "$1.90 USD")

    def test_extracts_airport_terminal_route(self):
        candidate = {
            "key": "terminal",
            "filename": "ticket.ofd",
            "email_subject": "机票",
            "_content": "电子发票（航空运输电子客票行程单） 长沙 黄花 T2 天津 滨海 T2 海航 HU7797 CNY 670.00",
            "_email_body": "",
        }

        meta = rt._rule_analyze_candidate(candidate)

        self.assertEqual(meta["invoice_from"], "长沙")
        self.assertEqual(meta["invoice_to"], "天津")
        self.assertEqual(meta["invoice_amount"], "¥670.00")

    def test_missing_invoice_amount_is_filled_from_vision_model(self):
        calls = []
        original_cfg = rt.merged_assistant_config
        original_request = rt.request_json
        original_image = getattr(rt, "_invoice_vision_image_data", None)
        try:
            rt.merged_assistant_config = lambda payload=None: {
                "url": "http://vision.example",
                "key": "test-key",
                "model": "MiniMax-M2.7",
            }
            rt._invoice_vision_image_data = lambda path: ("image/png", b"fake-image")

            def fake_request(url, api_key, body=None, method="GET", timeout=20):
                calls.append({"url": url, "api_key": api_key, "body": body, "method": method, "timeout": timeout})
                return {"choices": [{"message": {"content": '{"amount": "92.00"}'}}]}

            rt.request_json = fake_request
            candidate = {"invoice_type": "火车", "invoice_amount": "", "filename": "ticket.pdf"}

            amount = rt._fill_missing_invoice_amount_from_vision(candidate, "/tmp/ticket.pdf")

            self.assertEqual(amount, "¥92.00")
            self.assertEqual(calls[0]["body"]["model"], "MiniMax-M3")
            self.assertIn("data:image/png;base64,", calls[0]["body"]["messages"][0]["content"][1]["image_url"]["url"])
        finally:
            rt.merged_assistant_config = original_cfg
            rt.request_json = original_request
            if original_image is None:
                try:
                    delattr(rt, "_invoice_vision_image_data")
                except AttributeError:
                    pass
            else:
                rt._invoice_vision_image_data = original_image

    def test_missing_invoice_amount_vision_retries_with_focused_prompt(self):
        calls = []
        responses = ["amount empty", "票价金额 16.00 元"]
        original_cfg = rt.merged_assistant_config
        original_request = rt.request_json
        original_image = getattr(rt, "_invoice_vision_image_data", None)
        try:
            rt.merged_assistant_config = lambda payload=None: {"url": "http://vision.example", "key": "test-key", "model": "MiniMax-M2.7"}
            rt._invoice_vision_image_data = lambda path: ("image/png", b"fake-image")

            def fake_request(url, api_key, body=None, method="GET", timeout=20):
                calls.append(body)
                return {"choices": [{"message": {"content": responses.pop(0)}}]}

            rt.request_json = fake_request

            amount = rt._fill_missing_invoice_amount_from_vision({"invoice_type": "火车", "invoice_amount": ""}, "/tmp/ticket.pdf")

            self.assertEqual(amount, "¥16.00")
            self.assertEqual(len(calls), 2)
            self.assertIn("票价", calls[1]["messages"][0]["content"][0]["text"])
        finally:
            rt.merged_assistant_config = original_cfg
            rt.request_json = original_request
            if original_image is None:
                try:
                    delattr(rt, "_invoice_vision_image_data")
                except AttributeError:
                    pass
            else:
                rt._invoice_vision_image_data = original_image

    def test_reimbursement_items_sort_by_invoice_date_then_email_date(self):
        items = [
            {"key": "late", "invoice_date": "2026-06-10", "email_date": "2026-07-02 10:00"},
            {"key": "fallback", "invoice_date": "", "email_date": "2026-06-03 09:00"},
            {"key": "early", "invoice_date": "2026-06-01", "email_date": "2026-07-01 10:00"},
        ]

        ordered = rt._sort_reimbursement_items(items)

        self.assertEqual([item["key"] for item in ordered], ["early", "fallback", "late"])

    def test_train_ticket_zero_amount_from_llm_is_cleared_when_rules_have_no_amount(self):
        candidate = {
            "key": "rail-zero",
            "filename": "ticket.pdf",
            "email_subject": "铁路电子客票",
            "_content": "电子发票（铁路电子客票） 2026-06-21 邵阳北 长沙南",
            "_email_body": "",
        }

        meta = rt._merge_rule_meta(candidate, {
            "is_invoice": True,
            "invoice_type": "火车",
            "invoice_date": "2026-06-21",
            "invoice_amount": "¥0.00",
            "invoice_from": "邵阳北",
            "invoice_to": "长沙南",
        })

        self.assertEqual(meta["invoice_type"], "火车")
        self.assertEqual(meta["invoice_amount"], "")

    def test_ticket_rule_fields_override_llm_guess(self):
        candidate = {
            "key": "air-override",
            "filename": "invoice.ofd",
            "email_subject": "航空运输电子客票行程单",
            "_content": (
                "电子发票（航空运输电子客票行程单） 南航 CZ3694 E "
                "2026年06月05日 17:15 自： TSN 天津 至： CSX 长沙 "
                "合计 CNY 431.19 CNY 155.96 CNY 50.00 CNY 690.00 "
                "填开日期：2026年06月09日"
            ),
            "_email_body": "",
        }

        meta = rt._merge_rule_meta(candidate, {
            "is_invoice": True,
            "invoice_type": "机票",
            "invoice_date": "2026-06-09",
            "invoice_amount": "¥720.00",
            "invoice_from": "",
            "invoice_to": "",
        })

        self.assertEqual(meta["invoice_date"], "2026-06-05")
        self.assertEqual(meta["invoice_amount"], "¥690.00")
        self.assertEqual(meta["invoice_from"], "天津")
        self.assertEqual(meta["invoice_to"], "长沙")


    def test_reimbursement_search_records_append_dedupe_and_sort_items(self):
        import uuid

        username = "unit_search_record_" + uuid.uuid4().hex
        first = rt.save_reimbursement_search(
            username,
            {
                "account": "personal",
                "start": "2026-06-01",
                "end": "2026-06-30",
                "items": [
                    {"key": "late", "filename": "late.pdf", "invoice_date": "2026-06-20", "email_date": "2026-06-21"},
                    {"key": "early", "filename": "early.pdf", "invoice_date": "2026-06-03", "email_date": "2026-06-04"},
                ],
            },
        )

        updated = rt.save_reimbursement_search(
            username,
            {
                "id": first["record"]["id"],
                "account": "personal",
                "start": "2026-07-01",
                "end": "2026-07-02",
                "items": [
                    {"key": "early", "filename": "early-copy.pdf", "invoice_date": "2026-06-03"},
                    {"key": "middle", "filename": "middle.pdf", "invoice_date": "2026-06-10"},
                ],
            },
        )
        loaded = rt.get_reimbursement_search(username, first["record"]["id"])
        listed = rt.list_reimbursement_searches(username)

        self.assertTrue(first["ok"])
        self.assertTrue(updated["ok"])
        self.assertEqual([item["key"] for item in loaded["record"]["items"]], ["early", "middle", "late"])
        self.assertEqual(loaded["record"]["ranges"], [
            {"start": "2026-06-01", "end": "2026-06-30"},
            {"start": "2026-07-01", "end": "2026-07-02"},
        ])
        self.assertEqual(loaded["record"]["item_count"], 3)
        self.assertEqual(listed["records"][0]["id"], first["record"]["id"])
        self.assertNotIn("items", listed["records"][0])


    def test_reimbursement_search_records_persist_scan_chunks_and_total_from_chunks(self):
        import uuid

        username = "unit_search_chunks_" + uuid.uuid4().hex
        first = rt.save_reimbursement_search(username, {
            "account": "personal",
            "start": "2026-07-01",
            "end": "2026-07-03",
            "total_scanned": 60,
            "scan_chunks": [
                {"start": "2026-07-01", "end": "2026-07-03", "status": "failed", "total_scanned": 60, "item_count": 0, "message": "扫描失败"},
            ],
            "items": [],
        })
        updated = rt.save_reimbursement_search(username, {
            "id": first["record"]["id"],
            "account": "personal",
            "scan_chunks": [
                {"start": "2026-07-01", "end": "2026-07-01", "status": "done", "total_scanned": 20, "item_count": 3, "message": "完成"},
                {"start": "2026-07-02", "end": "2026-07-02", "status": "done", "total_scanned": 25, "item_count": 4, "message": "完成"},
                {"start": "2026-07-03", "end": "2026-07-03", "status": "pending", "total_scanned": 0, "item_count": 0, "message": "等待扫描"},
            ],
            "items": [
                {"key": "july-1", "filename": "july-1.pdf", "invoice_date": "2026-07-01"},
            ],
        })
        loaded = rt.get_reimbursement_search(username, first["record"]["id"])
        listed = rt.list_reimbursement_searches(username)

        self.assertTrue(updated["ok"])
        self.assertEqual(loaded["record"]["scan_chunks"], [
            {"start": "2026-07-01", "end": "2026-07-01", "status": "done", "total_scanned": 20, "item_count": 3, "message": "完成"},
            {"start": "2026-07-02", "end": "2026-07-02", "status": "done", "total_scanned": 25, "item_count": 4, "message": "完成"},
            {"start": "2026-07-03", "end": "2026-07-03", "status": "pending", "total_scanned": 0, "item_count": 0, "message": "等待扫描"},
        ])
        self.assertEqual(loaded["record"]["total_scanned"], 45)
        self.assertEqual(listed["records"][0]["scan_chunks"][0]["start"], "2026-07-01")

    def test_saving_search_record_repairs_zero_train_ticket_amount_from_vision(self):
        import uuid

        username = "unit_search_repair_" + uuid.uuid4().hex
        original_fill = rt._fill_missing_invoice_amount_from_vision
        original_path = rt._cache_path_for_key
        calls = []
        try:
            rt._cache_path_for_key = lambda user, key: f"/tmp/{key}.pdf"

            def fake_fill(candidate, path):
                calls.append((candidate.get("key"), candidate.get("invoice_amount"), path))
                return "¥42.50"

            rt._fill_missing_invoice_amount_from_vision = fake_fill
            saved = rt.save_reimbursement_search(username, {
                "account": "personal",
                "items": [{
                    "key": "zero-train",
                    "filename": "ticket.pdf",
                    "invoice_type": "火车",
                    "invoice_date": "2026-06-10",
                    "invoice_amount": "¥0.00",
                }],
            })

            self.assertEqual(saved["record"]["items"][0]["invoice_amount"], "¥42.50")
            self.assertEqual(calls, [("zero-train", "¥0.00", "/tmp/zero-train.pdf")])
        finally:
            rt._fill_missing_invoice_amount_from_vision = original_fill
            rt._cache_path_for_key = original_path

    def test_train_ticket_route_prefers_ticket_text_over_email_body_route(self):
        candidate = {
            "key": "rail-route",
            "filename": "26329130497001220803.pdf",
            "email_subject": "铁路电子客票",
            "_content": (
                "电子发票（铁路电子客票） Wuxi G7003 2026 年 05 月 19 日 "
                "票价 : ￥ 21.00 Suzhou 苏州 站无锡 站 中国铁路祝您旅途愉快"
            ),
            "_email_body": "邮件正文里还有另一张票：无锡东 至 长沙南",
        }

        meta = rt._merge_rule_meta(candidate, {
            "is_invoice": True,
            "invoice_type": "火车",
            "invoice_from": "无锡东",
            "invoice_to": "长沙南",
        })

        self.assertEqual(meta["invoice_from"], "无锡")
        self.assertEqual(meta["invoice_to"], "苏州")

    def test_subway_and_taxi_are_city_transport_not_train(self):
        subway = {
            "key": "subway",
            "filename": "metro.pdf",
            "email_subject": "轨道交通电子发票",
            "_content": "长沙市轨道交通集团 地铁 乘车票 票价 ￥4.00 尖山 开福寺",
            "_email_body": "",
        }
        taxi = {
            "key": "taxi",
            "filename": "taxi.pdf",
            "email_subject": "出租车发票",
            "_content": "出租汽车客运发票 金额 ￥35.00",
            "_email_body": "",
        }

        subway_meta = rt._rule_analyze_candidate(subway)
        taxi_meta = rt._rule_analyze_candidate(taxi)

        self.assertEqual(subway_meta["invoice_type"], "市内交通")
        self.assertEqual(taxi_meta["invoice_type"], "市内交通")
        self.assertEqual(subway_meta["invoice_from"], "")
        self.assertEqual(subway_meta["invoice_to"], "")

    def test_city_railway_ticket_is_city_transport_not_train(self):
        candidate = {
            "key": "city-rail",
            "filename": "26439165205000017671.pdf",
            "email_subject": "铁路电子客票",
            "_content": (
                "Jianshan S7817 2026 年 05 月 27 日 电子发票（铁路电子客票） "
                "17:55 开 不对号入座 票价 : ￥ 4.00 二等座 Kaifusi 开福寺 站尖山 站"
            ),
            "_email_body": "",
        }

        meta = rt._merge_rule_meta(candidate, {
            "is_invoice": True,
            "invoice_type": "火车",
            "invoice_from": "尖山",
            "invoice_to": "开福寺",
        })

        self.assertEqual(meta["invoice_type"], "市内交通")
        self.assertEqual(meta["invoice_from"], "")
        self.assertEqual(meta["invoice_to"], "")

    def test_batch_download_zip_uses_invoice_metadata_file_names(self):
        import uuid
        import zipfile

        username = "unit_batch_download_" + uuid.uuid4().hex
        train_key = "train_" + uuid.uuid4().hex
        hotel_key = "hotel_" + uuid.uuid4().hex
        same_key = "same_" + uuid.uuid4().hex
        rt._save_cache(username, train_key, "raw-train.pdf", b"train")
        rt._save_cache(username, hotel_key, "raw-hotel.pdf", b"hotel")
        rt._save_cache(username, same_key, "raw-same.pdf", b"same")

        result = rt.download_reimbursement_invoices_zip(username, [
            {"key": train_key, "invoice_type": "火车", "invoice_date": "2026-06-24", "invoice_amount": "¥21.00", "invoice_from": "无锡", "invoice_to": "苏州"},
            {"key": hotel_key, "invoice_type": "住宿", "invoice_date": "2026-06-25", "invoice_amount": "¥285.00", "invoice_location": "杭州欧诺酒店"},
            {"key": same_key, "invoice_type": "住宿", "invoice_date": "2026-06-25", "invoice_amount": "¥285.00", "invoice_location": "杭州欧诺酒店"},
        ], "批量发票")

        _, zip_raw = rt.get_reimbursement_output(username, result["filename"])
        with zipfile.ZipFile(__import__("io").BytesIO(zip_raw)) as zf:
            names = sorted(zf.namelist())
            self.assertEqual(names, [
                "住宿_2026-06-25_¥285.00_杭州欧诺酒店.pdf",
                "住宿_2026-06-25_¥285.00_杭州欧诺酒店_2.pdf",
                "火车_2026-06-24_¥21.00_无锡-苏州.pdf",
            ])
            self.assertEqual(zf.read("火车_2026-06-24_¥21.00_无锡-苏州.pdf"), b"train")

ReimbursementRuleExtractionDbModeTests = db_variant(ReimbursementRuleExtractionTests)


if __name__ == "__main__":
    unittest.main()
