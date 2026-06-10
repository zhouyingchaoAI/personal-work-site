import unittest

import backend.runtime as rt


class ReimbursementRuleExtractionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
