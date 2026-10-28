import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[2]


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root.parent / (self.root.name + '.json')
        self.config.write_text('{"users": []}')
        self.addCleanup(self.config.unlink)
        self.ns = {"USER_DATA_DIR": self.root, "CONFIG_PATH": self.config,
                   "crmdb_enabled": lambda: True, "crm_configuration_in_db": lambda: True,
                   "datetime": datetime, "read_config": lambda: {"users": []}}
        for name in ('assistant_permissions.py', 'data_center_dataflow.py', 'data_center_ownership.py',
                     'data_center_browse.py', 'data_center_storage.py', 'data_center_api.py'):
            exec(compile((ROOT / 'backend' / name).read_text(), name, 'exec'), self.ns)

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_directory_contains_every_assistant_and_one_platform(self):
        subjects = self.ns['dcstorage_overview']()['subjects']
        self.assertEqual({item['id'] for item in subjects}, set(self.ns['ASSISTANT_IDS']) | {'platform'})
        self.assertEqual(len(subjects), len(self.ns['ASSISTANT_IDS']) + 1)
        platform = next(item for item in subjects if item['id'] == 'platform')
        self.assertIn('agent', platform['group_ids'])
        self.assertNotIn('crm', platform['group_ids'])
        self.assertTrue(any('登录会话' in row['data'] for row in platform['items']))

    def test_api_catalog_ownership_covers_all_datasets(self):
        owned = {key for keys in self.ns['DC_OWNER_DATASETS'].values() for key in keys}
        self.assertEqual(owned, set(self.ns['DAPI_INDEX']))

    def test_future_assistant_remains_visible_with_unknown_storage(self):
        self.ns['ASSISTANT_IDS'] += ('future',)
        owner = next(item for item in self.ns['dcstorage_overview']()['subjects'] if item['id'] == 'future')
        self.assertEqual(owner['items'][0]['mode'], 'unknown')
        self.assertEqual(owner['instances'], [])

    def test_browse_filters_before_pagination_and_excludes_empty_user_navigation(self):
        self.write('alice/crm/units.json', {})
        self.write('bob/cashflow_history.json', {})
        self.write('_forum/topics.json', [])
        self.ns['DC_LIST_LIMIT'] = 1
        listing = self.ns['datacenter_browse']('', 'cashflow')
        self.assertEqual([item['path'] for item in listing['entries']], ['bob'])
        self.assertFalse(listing['truncated'])
        listing = self.ns['datacenter_browse']('bob', 'cashflow')
        self.assertEqual([item['name'] for item in listing['entries']], ['cashflow_history.json'])

    def test_platform_config_is_not_listed_as_crm_file(self):
        self.assertEqual(self.ns['datacenter_browse']('', 'crm')['entries'], [])
        self.assertEqual(self.ns['datacenter_browse']('', 'platform')['entries'][0]['name'], 'config.json')
        with self.assertRaises(ValueError):
            self.ns['datacenter_browse']('', 'invalid')
        with self.assertRaises(PermissionError):
            self.ns['datacenter_browse']('../', 'crm')

    def test_shared_reports_paths_do_not_include_other_report_kind(self):
        self.write('alice/reports/weekly/report.docx', {})
        self.write('alice/reports/trip/report.docx', {})
        listing = self.ns['datacenter_browse']('alice/reports', 'weekly')
        self.assertEqual([item['name'] for item in listing['entries']], ['weekly'])

    def test_legacy_reports_and_generated_reports_keep_their_owner(self):
        self.write('alice/reports/工作周报2026.xlsx', {})
        self.write('alice/reports/出差报告2026.docx', {})
        self.write('alice/generated/weekly/report.xlsx', {})
        self.write('alice/generated/trip/report.docx', {})
        listing = self.ns['datacenter_browse']('alice/reports', 'weekly')
        self.assertEqual([item['name'] for item in listing['entries']], ['工作周报2026.xlsx'])
        listing = self.ns['datacenter_browse']('alice/generated', 'weekly')
        self.assertEqual([item['name'] for item in listing['entries']], ['weekly'])

    def test_crm_live_api_ignores_frozen_files(self):
        self.write('alice/crm/units.json', {'old': {'id': 'old'}})
        self.ns['_dapi_owner_root'] = lambda owner: self.root / owner
        self.ns['crmdb_load'] = Mock(return_value={'new': {'id': 'new'}})
        self.assertEqual(self.ns['_dapi_crm']('alice', 'units.json'), [{'id': 'new'}])
        self.ns['crmdb_enabled'] = lambda: False
        self.assertEqual(self.ns['_dapi_crm']('alice', 'units.json'), [{'id': 'old'}])

    def test_crm_catalog_describes_database_primary(self):
        catalog = self.ns['dapi_catalog']()['datasets']
        crm = next(item for item in catalog if item['key'] == 'crm.units')
        self.assertIn('office-postgres', crm['source'])
        self.assertIn('已切库', next(item for item in crm['params'] if item['name'] == 'source')['desc'])

    def test_crm_dashboard_counts_current_database(self):
        self.write('alice/crm/units.json', {'old': {}})
        connection = Mock()
        connection.run.return_value = [[42]]
        class Pool:
            def __enter__(self):
                return connection
            def __exit__(self, *args):
                return False
        self.ns['_crmdb_conn'] = Pool
        data = self.ns['datacenter_dashboard'](True)
        self.assertEqual(data['records']['客户单位'], 42)
        self.assertEqual(connection.run.call_count, 5)

    def test_platform_related_tables_exclude_crm_and_ledger(self):
        self.ns['_dcdb_inst'] = lambda ident: {'id': ident, 'kind': 'postgres'}
        self.ns['dcdb_objects'] = lambda *args: {'objects': [{'name': name} for name in
            ('auth.users', 'agentic.sessions', 'collab.tickets', 'crm.units', 'ledger.items')]}
        result = self.ns['dcflow_tables']('platform', 'office-postgres', 'tester')
        self.assertEqual([item['name'] for item in result['objects']], ['auth.users', 'agentic.sessions', 'collab.tickets'])

    def test_knowledge_sqlite_shared_counts_are_not_assigned_to_assistant(self):
        self.ns['_dcdb_inst'] = lambda ident: {'id': ident, 'kind': 'sqlite'}
        self.ns['dcdb_objects'] = lambda *args: {'objects': [{'name': 'agent_messages', 'rows': 100, 'size': 4000}]}
        result = self.ns['dcflow_tables']('knowledge', 'sqlite-app', 'tester')
        self.assertIsNone(result['objects'][0]['rows'])


if __name__ == '__main__':
    unittest.main()
