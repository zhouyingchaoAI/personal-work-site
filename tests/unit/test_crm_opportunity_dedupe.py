"""Cross-account opportunity duplicates must not double-count in shared views."""
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

import backend.runtime as r

USERS = {'users': [{'username': 'alice', 'role': 'superadmin'}, {'username': 'bob', 'role': 'user'}]}


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append(['机会点编码', '机会点名称', '业主单位', '可参与份额-总额(万元)'])
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return {'filename': 'test.xlsx', 'data': base64.b64encode(buffer.getvalue()).decode()}


class OpportunityDedupeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)), patch.object(r, 'crm_on_change'),
                        patch.object(r, 'read_config', return_value=USERS)]
        for p in self.patches:
            p.start()
        r.crm_store('bob', 'opportunities', {
            'SAME-1': {'id': 'SAME-1', 'code': 'SAME-1', 'name': '同一商机', 'owner_unit': '甲方', 'amount': 1000, 'cancelled': False, 'outcome': 'open', 'updated_at': '2026-09-23T15:01:10', 'version': 1},
            'BOB-ONLY': {'id': 'BOB-ONLY', 'code': 'BOB-ONLY', 'name': '仅鲍勃', 'owner_unit': '乙方', 'amount': 5, 'cancelled': False, 'outcome': 'open', 'updated_at': '2026-09-23T15:01:10', 'version': 1},
        })
        r.crm_store('alice', 'opportunities', {
            'SAME-1': {'id': 'SAME-1', 'code': 'SAME-1', 'name': '同一商机', 'owner_unit': '甲方', 'amount': 1000, 'cancelled': False, 'outcome': 'open', 'updated_at': '2026-09-23T14:58:10', 'version': 2, 'stage_progress': {'合同签订': {'attachments': [{'name': '材料'}], 'contacts': []}}},
        })

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_admin_view_counts_each_code_once_and_prefers_own_record(self):
        result = r.crm_read_opportunities(USERS['users'][0])
        codes = [item['code'] for item in result['opportunities']]
        self.assertEqual(sorted(codes), ['BOB-ONLY', 'SAME-1'], codes)
        same = next(item for item in result['opportunities'] if item['code'] == 'SAME-1')
        self.assertEqual(same['_owner'], 'alice', 'caller-owned record must win so its stage materials stay visible')
        self.assertEqual(same['_shared_owners'], ['bob'])
        self.assertEqual(sum(item['amount'] for item in result['opportunities']), 1005)

    def test_shared_record_falls_back_to_latest_update_when_caller_has_none(self):
        r.crm_store('alice', 'opportunities', {})
        r.crm_store('carol', 'opportunities', {'SAME-1': {'id': 'SAME-1', 'code': 'SAME-1', 'name': '同一商机', 'owner_unit': '甲方', 'amount': 1000, 'cancelled': False, 'outcome': 'open', 'updated_at': '2026-09-24T09:00:00', 'version': 1}})
        with patch.object(r, 'read_config', return_value={'users': [*USERS['users'], {'username': 'carol', 'role': 'user'}]}):
            result = r.crm_read_opportunities(USERS['users'][0])
        same = [item for item in result['opportunities'] if item['code'] == 'SAME-1']
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0]['_owner'], 'carol')

    def test_confirmed_duplicate_stays_archived_across_accounts(self):
        r.crm_store('alice', 'opportunities', {
            'DUP-1': {'id': 'DUP-1', 'code': 'DUP-1', 'name': '早期重复', 'owner_unit': '甲方', 'amount': 800, 'cancelled': True, 'outcome': 'cancelled', 'duplicate_of': 'KEEP-1', 'cancel_reason': '重复商机，已归并至 KEEP-1', 'updated_at': '2026-09-20T10:00:00', 'version': 3},
        })
        r.crm_store('bob', 'opportunities', {
            'DUP-1': {'id': 'DUP-1', 'code': 'DUP-1', 'name': '早期重复', 'owner_unit': '甲方', 'amount': 800, 'cancelled': False, 'outcome': 'open', 'updated_at': '2026-09-24T09:00:00', 'version': 1},
        })
        # 共享视图（管理员）里，人工确认的归并优先于任何账号的活跃副本。
        result = r.crm_read_opportunities(USERS['users'][0])
        dup = next(item for item in result['opportunities'] if item['code'] == 'DUP-1')
        self.assertTrue(dup['cancelled'], 'confirmed duplicate must stay archived in the shared view')
        self.assertEqual(dup['duplicate_of'], 'KEEP-1')
        # 个人范围账号仍只见自己名下的记录，这是授权边界而非重复计数。
        own = r.crm_read_opportunities(USERS['users'][1])['opportunities']
        self.assertEqual([item['_owner'] for item in own if item['code'] == 'DUP-1'], ['bob'])

    def test_import_preview_flags_codes_held_by_other_accounts(self):
        payload = workbook([['BOB-ONLY', '仅鲍勃', '乙方', 5], ['NEW-1', '新商机', '丙方', 7]])
        preview = r.crm_opportunity_import({**payload, 'mode': 'preview'}, 'alice')
        self.assertTrue(preview['preview'])
        self.assertEqual(preview['duplicate_count'], 1)
        self.assertEqual(preview['duplicates'][0]['code'], 'BOB-ONLY')
        self.assertIn('bob', preview['duplicates'][0]['reason'])
        self.assertEqual(preview['new_count'], 1)
        self.assertEqual(r.crm_load('alice', 'opportunities').get('BOB-ONLY'), None, 'preview must not write')

    def test_import_skip_mode_skips_codes_held_by_other_accounts(self):
        payload = workbook([['BOB-ONLY', '仅鲍勃', '乙方', 5], ['NEW-1', '新商机', '丙方', 7]])
        result = r.crm_opportunity_import({**payload, 'mode': 'skip'}, 'alice')
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['created'], 1)
        stored = r.crm_load('alice', 'opportunities')
        self.assertNotIn('BOB-ONLY', stored)
        self.assertIn('NEW-1', stored)
        total = r.crm_read_opportunities(USERS['users'][0])['opportunities']
        self.assertEqual(len(total), 3)


if __name__ == '__main__':
    unittest.main()
