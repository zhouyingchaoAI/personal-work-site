import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import runtime as runtime


class BusinessScopeTest(unittest.TestCase):
    def setUp(self):
        self.user = {'username': 'east', 'name': '东区经理', 'employee_id': 'E001'}
        self.data = {'dashboard': {'secret': 'company'}, 'sheets': [
            {'key': '01_核心指标总览', 'headers': ['指标', '全年目标', '实际完成'], 'rows': [['订货', 900, 800]]},
            {'key': '本次区域经营汇总', 'headers': ['区域', '订货', '毛利'], 'rows': [['东区作战平台', 100, 10], ['西区作战平台', 200, 20], ['联指', 300, 30]]},
            {'key': '19_已完成订单明细', 'headers': ['项目归属', '客户经理', '销售合同金额'], 'rows': [['东区', 'E001', 100], ['东区', '其他人', 200], ['西区', '其他人', 300]]},
            {'key': '03_作战平台目标达成', 'headers': ['指标', '联指', '东区作战平台', '西区作战平台'], 'rows': [['实际订货完成', 900, 100, 200]]},
            {'key': '未知底账', 'headers': ['区域', '备注'], 'rows': [['东区', 'company secret']]},
        ]}

    def scoped(self, level, regions=None, users=None):
        with patch.object(runtime, 'crm_capabilities', return_value={'data_scope': level, 'regions': regions or [], 'write': True}), patch.object(runtime, 'read_config', return_value={'users': users or [self.user]}):
            return runtime.crm_business_scope_data(self.data, self.user)

    def test_superadmin_preview_and_default(self):
        admin = {'username': 'root', 'role': 'superadmin'}
        with patch.object(runtime, 'read_config', return_value={'users': [admin, self.user]}), \
             patch.object(runtime, '_crm_business_versions', return_value=[{'version': 'test'}]), \
             patch.object(runtime, 'crmdb_enabled', return_value=True), \
             patch.object(runtime, 'crmdb_blob_get', side_effect=lambda _: copy.deepcopy(self.data)):
            default = runtime.crm_business_analysis(admin)
            self.assertEqual(default['scope']['level'], 'company')
            self.assertEqual(default['data']['sheets'], self.data['sheets'])
            regional = runtime.crm_business_analysis(admin, view='region', region='东区')
            self.assertEqual(regional['scope']['level'], 'region')
            orders = next(sheet for sheet in regional['data']['sheets'] if sheet['key'].startswith('19_'))
            self.assertEqual(len(orders['rows']), 2)
            personal = runtime.crm_business_analysis(admin, view='personal', manager='east')
            self.assertEqual(personal['data']['sheets'][0]['rows'], [['东区', 'E001', 100]])
            self.assertTrue(personal['view_options'])
            self.assertFalse(runtime.crm_business_analysis(admin, view='personal', manager='missing')['ok'])
            self.assertFalse(runtime.crm_business_analysis(admin, view='region', region='联指')['ok'])
            self.assertFalse(runtime.crm_business_analysis(admin, view='invalid')['ok'])

    def test_non_superadmin_cannot_override_scope(self):
        with patch.object(runtime, 'crm_capabilities', return_value={'read': True, 'data_scope': 'all'}):
            self.assertFalse(runtime.crm_business_analysis(self.user, view='company')['ok'])
            self.assertFalse(runtime.crm_business_analysis(self.user, manager='root')['ok'])
            with self.assertRaises(ValueError):
                runtime.crm_business_scope_data(self.data, self.user, ('company', None))

    def test_region_excludes_company_other_region_and_unknown(self):
        before = copy.deepcopy(self.data)
        result, scope = self.scoped('regions', ['东区'])
        self.assertEqual(scope['level'], 'region')
        self.assertFalse(scope['can_import'])
        sheets = {sheet['key']: sheet for sheet in result['sheets']}
        self.assertNotIn('01_核心指标总览', sheets)
        self.assertNotIn('未知底账', sheets)
        self.assertEqual(len(sheets['19_已完成订单明细']['rows']), 2)
        self.assertEqual(sheets['03_作战平台目标达成']['headers'], ['指标', '东区作战平台'])
        self.assertNotIn('secret', result['dashboard'])
        self.assertEqual(self.data, before)

    def test_personal_only_owner_no_region_aggregate(self):
        result, scope = self.scoped('self')
        self.assertEqual(scope['level'], 'personal')
        self.assertEqual([sheet['key'] for sheet in result['sheets']], ['19_已完成订单明细'])
        self.assertEqual(result['sheets'][0]['rows'], [['东区', 'E001', 100]])

    def test_company_keeps_complete_data(self):
        result, scope = self.scoped('all')
        self.assertEqual(result['sheets'], self.data['sheets'])
        self.assertTrue(scope['can_import'])

    def test_empty_region_fails_closed(self):
        result, _ = self.scoped('regions', [])
        self.assertEqual(result['sheets'], [])

    def test_region_child_alias_and_boundary(self):
        self.data['sheets'][2]['rows'] = [['东区-江苏', 'E001', 100], ['东区—浙北', 'other', 200], ['东区外部', 'other', 300]]
        result, _ = self.scoped('regions', ['东区'])
        orders = next(sheet for sheet in result['sheets'] if sheet['key'] == '19_已完成订单明细')
        self.assertEqual(len(orders['rows']), 2)

    def test_task_owner_does_not_fall_back_to_customer_manager(self):
        self.data['sheets'] = [{'key': '订货任务令', 'headers': ['客户经理', '确认主要责任人', '*机会点名称'],
                                'rows': [['E001', 'other', '不属于本人的任务'], ['other', 'E001', '本人任务']]}]
        result, _ = self.scoped('self')
        self.assertEqual(result['sheets'][0]['rows'], [['other', 'E001', '本人任务']])

    def test_duplicate_display_name_does_not_grant_access(self):
        self.data['sheets'][2]['rows'] = [['东区', '东区经理', 100]]
        result, _ = self.scoped('self', users=[self.user, {'username': 'other', 'name': '东区经理'}])
        self.assertEqual(result['sheets'], [])

    def test_historical_api_and_html_use_same_scope(self):
        with patch.object(runtime, 'crm_capabilities', return_value={'read': True, 'data_scope': 'self'}), patch.object(runtime, 'read_config', return_value={'users': [self.user]}), patch.object(runtime, '_crm_business_versions', return_value=[{'version': 'old', 'filename': 'sensitive-company.xlsx', 'imported_by': 'admin'}]), patch.object(runtime, 'crmdb_enabled', return_value=True), patch.object(runtime, 'crmdb_blob_get', return_value=copy.deepcopy(self.data)):
            result = runtime.crm_business_analysis(self.user, 'old')
            self.assertEqual(result['scope']['level'], 'personal')
            self.assertNotIn('filename', result['versions'][0])
            self.assertEqual(len(result['data']['sheets']), 1)
            html = runtime.crm_business_dashboard_html(self.user, 'old')
            self.assertNotIn('company secret', html)


if __name__ == '__main__':
    unittest.main()
