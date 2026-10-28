import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DataflowMappingTests(unittest.TestCase):
    def setUp(self):
        self.ns = {}
        for name in ('assistant_permissions.py', 'data_center_dataflow.py'):
            exec(compile((ROOT / 'backend' / name).read_text(), name, 'exec'), self.ns)

    def test_all_assistants_and_future_entries_are_visible(self):
        self.ns['ASSISTANT_IDS'] += ('future-assistant',)
        groups = {group['id']: group for group in self.ns['_dcflow_topology']()}
        self.assertTrue(set(self.ns['ASSISTANT_IDS']) <= groups.keys())
        self.assertEqual(groups['future-assistant']['instances'], [])
        self.assertIn('待核实', groups['future-assistant']['storage_note'])
        self.assertEqual(groups['lobsterbase']['instances'], [])

    def test_mirrored_tables_do_not_include_other_assistants(self):
        self.ns['_dcdb_inst'] = lambda ident: {'id': ident, 'kind': 'postgres'}
        self.ns['dcdb_objects'] = lambda *args: {'objects': [
            {'name': name} for name in ('ledger.items', 'cashflow.scenarios', 'crm.units', 'collab.forum_topics')
        ]}
        result = self.ns['dcflow_tables']('ledger', 'office-postgres', 'tester')
        self.assertEqual([obj['name'] for obj in result['objects']], ['ledger.items'])
        self.assertIn('镜像', result['note'])
        with self.assertRaises(ValueError):
            self.ns['dcflow_tables']('ledger', 'crm-neo4j', 'tester')

    def test_shared_catalog_counts_are_not_attributed_to_one_assistant(self):
        self.ns['_dcdb_inst'] = lambda ident: {'id': ident, 'kind': 'postgres'}
        self.ns['dcdb_objects'] = lambda *args: {'objects': [
            {'name': 'files.catalog', 'rows': 999, 'size': 4096},
            {'name': 'crm.units', 'rows': 10},
        ]}
        result = self.ns['dcflow_tables']('weekly', 'office-postgres', 'tester')
        self.assertEqual([obj['name'] for obj in result['objects']], ['files.catalog'])
        self.assertIsNone(result['objects'][0]['rows'])
        self.assertIsNone(result['objects'][0]['size'])
        self.assertIn('共享', result['note'])


if __name__ == '__main__':
    unittest.main()
