"""Opportunity import keeps project investment apart from our participable share, and derives outcomes."""
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

import backend.runtime as r

HEADERS = ['机会点编码', '机会点名称', '业主单位', '业务状态', '投资规模(万元)', '可参与份额-总额(万元)',
           '可参与份额-集成产业(万元)', '可参与份额-服务1.0(含配套件)(万元)', '生成销售项目次数']


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return {'filename': 'test.xlsx', 'data': base64.b64encode(buffer.getvalue()).decode()}


class OpportunityAmountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)), patch.object(r, 'crm_on_change'),
                        patch.object(r, 'read_config', return_value={'users': [{'username': 'alice', 'role': 'superadmin'}]})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_investment_and_share_are_stored_separately(self):
        r.crm_opportunity_import(workbook([['P1', '在谈', '甲', '正常', 30000, 6000, 5000, 1000, None]]), 'alice')
        item = r.crm_load('alice', 'opportunities')['P1']
        self.assertEqual((item['investment'], item['amount'], item['share_integration'], item['share_service']), (30000, 6000, 5000, 1000))
        self.assertEqual(item['outcome'], 'open')

    def test_signed_and_lost_rows_are_not_in_pipeline(self):
        result = r.crm_opportunity_import(workbook([
            ['W1', '已签约', '甲', '立项', 30, 30, 0, 30, 1],
            ['L1', '丢标', '乙', '丢标', 85000, 1500, 1500, 0, None],
            ['O1', '在谈', '丙', '正常', 12000, 3000, 3000, 0, None],
        ]), 'alice')
        stored = r.crm_load('alice', 'opportunities')
        self.assertEqual({k: v['outcome'] for k, v in stored.items()}, {'W1': 'won', 'L1': 'lost', 'O1': 'open'})
        self.assertEqual((result['active'], result['won'], result['lost']), (1, 1, 1))

    def test_manual_outcome_survives_reimport(self):
        r.crm_opportunity_import(workbook([['O1', '在谈', '丙', '正常', 12000, 3000, 3000, 0, None]]), 'alice')
        stored = r.crm_load('alice', 'opportunities')
        stored['O1'].update(outcome='won', outcome_source='manual')
        r.crm_store('alice', 'opportunities', stored)
        r.crm_opportunity_import(workbook([['O1', '在谈', '丙', '正常', 12000, 3000, 3000, 0, None]]), 'alice')
        self.assertEqual(r.crm_load('alice', 'opportunities')['O1']['outcome'], 'won')


if __name__ == '__main__':
    unittest.main()
