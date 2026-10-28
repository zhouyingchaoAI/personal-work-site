import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class StorageGuideTests(unittest.TestCase):
    def setUp(self):
        self.sync = {}
        self.live = True
        self.ns = {"crmdb_enabled": lambda: self.live, "crm_configuration_in_db": lambda: False, "USER_DATA_DIR": ROOT,
                   "officedb_enabled": lambda module: False, "officedb_enabled_modules": lambda: [],
                   "office_store_module": lambda ident: {"weekly": "reports", "trip": "reports"}.get(ident, ident),
                   "OFFICE_STORE_MODULES": ("ledger", "cashflow", "project", "diary", "workorder", "forum", "meeting", "writing",
                                            "news", "reports", "reimbursement", "mailassistant", "knowledge", "datacenter", "platform"),
                   "datacenter_dir": lambda root: root,
                   "read_json": lambda *args: self.sync}
        for name in ('assistant_permissions.py', 'data_center_dataflow.py', 'data_center_ownership.py', 'data_center_storage.py'):
            exec(compile((ROOT / 'backend' / name).read_text(), name, 'exec'), self.ns)

    def overview(self):
        return self.ns['dcstorage_overview']()

    def groups(self):
        return {group['id']: group['items'] for group in self.overview()['assistants']}

    def test_all_assistants_have_explicit_data_and_live_source(self):
        groups = self.groups()
        for ident in self.ns['ASSISTANT_IDS']:
            self.assertIn(ident, groups)
            self.assertTrue(all(row['data'] and row['primary'] for row in groups[ident]))
            self.assertTrue(all(row['mode'] != 'unknown' for row in groups[ident]))

    def test_crm_switch_controls_business_storage_but_not_audit(self):
        self.assertEqual(self.groups()['crm'][0]['mode'], 'database')
        audit = next(row for row in self.groups()['crm'] if row['data'] == '操作审计')
        self.assertEqual(audit['mode'], 'file')
        self.live = False
        self.assertEqual(self.groups()['crm'][0]['mode'], 'file')
        self.assertFalse(self.overview()['crm_live'])

    def test_full_cutover_includes_configuration_audit_and_map(self):
        self.ns['crm_configuration_in_db'] = lambda: True
        self.assertTrue(all(row['mode'] == 'database' for row in self.groups()['crm']))

    def test_mirror_does_not_change_live_storage_and_zero_rows_is_preserved(self):
        self.sync = {'last': {'ok': True, 'tables': [
            {'table': 'cashflow.scenarios', 'rows': 0, 'match': True}
        ]}}
        row = next(row for row in self.groups()['cashflow'] if row['data'] == '测算方案')
        self.assertEqual(row['mode'], 'file')
        self.assertEqual(row['mirror_evidence'], [{'table': 'cashflow.scenarios', 'verified': True, 'rows': 0}])
        self.sync['last']['ok'] = False
        row = next(row for row in self.groups()['cashflow'] if row['data'] == '测算方案')
        self.assertFalse(row['mirror_evidence'][0]['verified'])

    def test_missing_evidence_and_external_storage_are_not_declared_migrated(self):
        self.assertTrue(all(not evidence['verified'] for group in self.groups().values()
                            for row in group for evidence in row['mirror_evidence']))
        self.assertTrue(all(row['mode'] == 'external' for row in self.groups()['lobsterbase']))
        self.assertIsNone(self.overview()['sync']['archive_ok'])
        self.assertEqual(self.groups()['agent'][0]['mode'], 'database')

    def test_future_assistant_is_kept_as_unknown(self):
        self.ns['ASSISTANT_IDS'] += ('future-assistant',)
        self.assertEqual(self.groups()['future-assistant'][0]['mode'], 'unknown')


if __name__ == '__main__':
    unittest.main()
