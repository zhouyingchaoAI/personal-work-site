import base64
import copy
import io
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from openpyxl import Workbook
from backend import runtime as rt


class MonthlyBattleTests(unittest.TestCase):
    def setUp(self):
        self.data = {'items': []}
        self.admin = {'username': 'admin', 'name': '管理', 'role': 'admin'}
        self.member = {'username': 'me', 'name': '本人'}
        def caps(user):
            return {'read': True, 'write': True, 'register_action': True, 'data_scope': 'all' if user['username'] == 'admin' else 'self'}
        def store(value=None):
            if value is not None:
                self.data = copy.deepcopy(value)
            return copy.deepcopy(self.data)
        for target, value in [('crm_capabilities', caps), ('monthly_battle_store', store), ('read_config', lambda: {'users': [self.admin, self.member]}), ('crm_battle_roster', lambda: {'units': [], 'management': []})]:
            mock = patch.object(rt, target, side_effect=value)
            mock.start()
            self.addCleanup(mock.stop)

    def workbook(self, duplicate=False):
        book = Workbook()
        sheet = book.active
        sheet.append(['*机会点名称', '子项目编码', '确认主要责任人', '*项目归属', '任务令作战部署的目标/动作'])
        sheet.append(['测试项目', 'A1', '本人', '东区-江苏', '完成 【阶段11-合同签订】'])
        if duplicate:
            sheet.append(['重复项目', 'A1', '本人', '东区-江苏', ''])
        output = io.BytesIO()
        book.save(output)
        return {'month': '2026-11', 'data': base64.b64encode(output.getvalue()).decode()}

    def progress(self, stage=1, **extra):
        item = self.data['items'][0]
        return rt.monthly_battle_progress({'id': item['id'], 'revision': item['revision'], 'stage': stage, 'stage_reason': '客户确认进入下一阶段', 'content': '与客户沟通设计方案', 'next_action': '明日确认意见', **extra}, self.member)

    def test_import_uses_sheet_stage_as_actual_baseline_and_preserves_history(self):
        result = rt.monthly_battle_import(self.workbook(), self.admin)
        self.assertEqual(result['count'], 1)
        item = self.data['items'][0]
        self.assertEqual(item['stage'], 11)
        self.assertEqual(item['target_stage'], 11)
        self.assertEqual(item['assignees'], ['me'])
        self.progress(2)
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.assertEqual(len(self.data['items']), 1)
        self.assertEqual(self.data['items'][0]['stage'], 2)
        self.assertEqual(len(self.data['items'][0]['events']), 1)

    def test_manager_comment_persists_without_registering_action(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.progress(11)
        item = self.data['items'][0]
        revision = item['revision']
        payload = {'id': item['id'], 'event_id': item['events'][0]['id'], 'content': '请确认付款条件'}
        with self.assertRaises(PermissionError):
            rt.monthly_battle_comment(payload, self.member)
        rt.monthly_battle_comment(payload, self.admin)
        item = self.data['items'][0]
        self.assertEqual(len(item['events']), 1)
        self.assertEqual(item['revision'], revision + 1)
        comment = item['events'][0]['comments'][0]
        self.assertEqual(comment['content'], payload['content'])
        self.assertEqual(comment['username'], 'admin')
        self.assertTrue(comment['at'])
        with self.assertRaises(ValueError):
            rt.monthly_battle_comment({**payload, 'content': ' '}, self.admin)
        with self.assertRaises(ValueError):
            rt.monthly_battle_comment({**payload, 'event_id': 'missing'}, self.admin)

    def test_action_without_stage_change(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.progress(11, stage_reason='')
        self.assertEqual(self.data['items'][0]['stage'], 11)

    def test_stage_change_only_requires_reason(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.progress(7, event_type='stage_change', content='', next_action='', stage_reason='更正实际招标阶段')
        event = self.data['items'][0]['events'][-1]
        self.assertEqual(event['event_type'], 'stage_change')
        self.assertEqual(event['from_stage'], 11)
        self.assertEqual(event['stage_reason'], '更正实际招标阶段')
        with self.assertRaises(ValueError):
            self.progress(7, event_type='stage_change', content='', next_action='')

    def test_action_and_stage_history(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.progress(11, stage_reason='')
        self.assertEqual(self.data['items'][0]['events'][0]['stage_reason'], '')
        self.progress(2, stage_reason='确认概算')
        self.progress(2, stage_reason='')
        self.assertEqual(self.data['items'][0]['stage'], 2)
        with self.assertRaises(ValueError):
            self.progress(0, stage_reason='不能清除实际阶段')

    def test_stage_reason_required_and_logged(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        with self.assertRaises(ValueError):
            self.progress(2, stage_reason=' ')
        self.assertEqual(len(self.data['items'][0]['events']), 0)
        self.progress(2, stage_reason='客户确认概算范围')
        event = self.data['items'][0]['events'][0]
        self.assertEqual(event['stage_reason'], '客户确认概算范围')
        self.assertEqual((event['from_stage'], event['stage']), (11, 2))
        self.assertEqual(event['username'], 'me')
        self.assertTrue(event['at'])
        self.progress(2, stage_reason='')
        self.assertEqual(len(self.data['items'][0]['events']), 2)

    def test_unit_leader_only_sees_own_east_office(self):
        now = datetime.now().isoformat(timespec='seconds')
        self.data['items'] = [
            {'id':'jiangsu','month':'2026-11','code':'1','name':'江苏项目','owner':'本人','manager':'','assignees':['other'],'region':'东区-江苏','target':'','target_stage':1,'amount':1,'tag':'','missing_code':False,'sources':[],'conflicts':[],'created_at':now,'stage':1,'completed':False,'cadence':2,'revision':0,'events':[]},
            {'id':'zhebei','month':'2026-11','code':'2','name':'浙北项目','owner':'别人','manager':'','assignees':['other'],'region':'东区-浙北','target':'','target_stage':1,'amount':1,'tag':'','missing_code':False,'sources':[],'conflicts':[],'created_at':now,'stage':1,'completed':False,'cadence':2,'revision':0,'events':[]},
        ]
        roster = {'units':[{'id':'east-jiangsu','name':'东区-江苏办事处','leaders':['me']},{'id':'east-zhejiang-north','name':'东区-浙北办事处','leaders':[]}]}
        with patch.object(rt, 'crm_battle_roster', return_value=roster), patch.object(rt, 'crm_battle_roster_level', return_value='region'), patch.object(rt, 'crm_battle_roster_units', return_value=['east-jiangsu']):
            result = rt.monthly_battle_read(self.member)
        self.assertEqual([item['id'] for item in result['items']], ['jiangsu'])
        self.assertEqual(result['scope']['level'], 'region')

    def test_permissions_and_revision(self):
        with self.assertRaises(PermissionError):
            rt.monthly_battle_import(self.workbook(), self.member)
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.assertEqual(rt.monthly_battle_read({'username': 'other'})['items'], [])
        with self.assertRaises(ValueError):
            self.progress(revision=-1)
        with self.assertRaises(ValueError):
            self.progress(completed=True)
        with self.assertRaises(ValueError):
            self.progress(attachments=[{'id': '../bad'}])

    def test_elapsed_time_cadence_completion_and_rollback(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        self.progress(2)
        self.data['items'][0]['events'][0]['at'] = (datetime.now() - timedelta(days=3)).isoformat(timespec='seconds')
        result = rt.monthly_battle_read(self.member)['items'][0]
        self.assertTrue(result['overdue'])
        self.assertAlmostEqual(result['stage_days']['2'], 3, places=1)
        self.progress(1)
        self.assertEqual(self.data['items'][0]['events'][-1]['from_stage'], 2)
        self.progress(11, completed=True)
        self.assertFalse(rt.monthly_battle_read(self.member)['items'][0]['overdue'])

    def test_action_cycle_status_returns_seven_cadence_windows(self):
        now = datetime(2026, 10, 27, 12, 0, 0)
        item = {
            'created_at': (now - timedelta(days=20)).isoformat(timespec='seconds'),
            'cadence': 2,
            'events': [
                {'at': (now - timedelta(days=1)).isoformat(timespec='seconds'), 'event_type': 'action'},
                {'at': (now - timedelta(days=5)).isoformat(timespec='seconds'), 'event_type': 'action'},
                {'at': (now - timedelta(days=7)).isoformat(timespec='seconds'), 'event_type': 'stage_change'},
            ],
        }
        cycles = rt.monthly_battle_action_cycles(item, now)
        self.assertEqual(len(cycles), 7)
        self.assertEqual([cycle['status'] for cycle in cycles], ['red', 'red', 'red', 'red', 'green', 'red', 'green'])
        self.assertEqual(cycles[-1]['label'], '10/26-10/27')
        item['cadence'] = 1
        self.assertEqual(rt.monthly_battle_action_cycles(item, now), cycles)
        self.assertEqual(cycles[0]['label'], '10/14-10/15')
        item['events'] = [{'at': '2026-10-26T00:00:00', 'event_type': 'action'}]
        self.assertEqual(rt.monthly_battle_action_cycles(item, now)[-1]['status'], 'green')

    def test_duplicate_import_is_atomic(self):
        with self.assertRaises(ValueError):
            rt.monthly_battle_import(self.workbook(True), self.admin)
        self.assertEqual(self.data['items'], [])

    def test_three_scopes_and_superadmin_preview(self):
        rt.monthly_battle_import(self.workbook(), self.admin)
        original = self.data['items'][0]
        self.data['items'].extend([{**copy.deepcopy(original), 'id': 'west', 'region': '西区', 'assignees': ['other']}, {**copy.deepcopy(original), 'id': 'east', 'assignees': ['other']}])
        regional = {'username': 'me'}
        with patch.object(rt, 'crm_capabilities', return_value={'read': True, 'data_scope': 'regions', 'regions': ['西区']}):
            self.assertEqual(len(rt.monthly_battle_read(regional)['items']), 2)
        with patch.object(rt, 'crm_capabilities', return_value={'read': True, 'data_scope': 'all', 'role': 'account_manager'}):
            self.assertEqual(len(rt.monthly_battle_read(self.member)['items']), 1)
            with self.assertRaises(PermissionError):
                rt.monthly_battle_read(self.member, 'company')
        superuser = {**self.admin, 'role': 'superadmin'}
        self.assertEqual(len(rt.monthly_battle_read(superuser)['items']), 3)
        self.assertEqual(len(rt.monthly_battle_read(superuser, 'region', '西区')['items']), 1)
        self.assertEqual(len(rt.monthly_battle_read(superuser, 'personal', manager='me')['items']), 1)
        self.assertIsNone(rt.monthly_battle_read(self.member)['view_options'])

    def test_missing_code_and_duplicate_rows_are_retained(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['机会点名称', '子项目编码', '项目归属', '现：保底/冲刺/推进'])
        sheet.append(['测试项目', '', '东区-江苏', '推进'])
        sheet.append(['测试项目', '', '东区-江苏', '冲刺'])
        output = io.BytesIO(); book.save(output)
        result = rt.monthly_battle_import({'month': '2026-11', 'data': base64.b64encode(output.getvalue()).decode()}, self.admin)
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['source_rows'], 2)
        self.assertTrue(self.data['items'][0]['missing_code'])
        self.assertIn('tag', self.data['items'][0]['conflicts'])
