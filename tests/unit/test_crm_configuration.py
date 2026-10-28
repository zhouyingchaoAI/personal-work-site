import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import runtime as runtime


class ConfigurationFileTests(unittest.TestCase):
    def test_file_mode_and_corrupt_policy_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(runtime, 'USER_DATA_DIR', Path(temporary)):
            self.assertFalse(runtime.crm_configuration_in_db())
            runtime.crm_configuration_save('policies', {'alice': {'role': 'viewer'}})
            self.assertEqual(runtime.crm_security_policies()['alice']['role'], 'viewer')
            (Path(temporary) / '.crm-security/policies.json').write_text('invalid')
            with self.assertRaises(ValueError):
                runtime.crm_security_policies()


@unittest.skipUnless(os.getenv('CRM_CONFIGURATION_TEST_DATABASE'), 'isolated PostgreSQL required')
class ConfigurationDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ['CRM_CONFIGURATION_TEST_DATABASE']
        if not database.startswith('crm_configuration_test_'):
            raise ValueError('Requires disposable test database')
        config = dict(runtime.crmdb_config(), database=database, configuration_enabled=True)
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        (root / '_datacenter').mkdir()
        (root / '_datacenter/crm_db.json').write_text(json.dumps(config))
        cls.root_patch = patch.object(runtime, 'USER_DATA_DIR', root)
        cls.root_patch.start()
        runtime._crmdb_state['config_mtime'] = None

    @classmethod
    def tearDownClass(cls):
        while not runtime._crmdb_pool.empty():
            runtime._crmdb_pool.get_nowait().close()
        cls.root_patch.stop()
        runtime._crmdb_state['config_mtime'] = None
        cls.temporary.cleanup()

    def setUp(self):
        with runtime._crmdb_conn() as connection:
            connection.run('DELETE FROM crm.configuration')
            connection.run('DELETE FROM crm.security_events')

    def test_config_roundtrip_and_optimistic_version(self):
        runtime.crm_configuration_save('regions', {'version': 1, 'regions': {'东区': ['浙江']}})
        self.assertEqual(runtime.crm_configuration_load('regions')['version'], 1)
        with self.assertRaises(ValueError):
            runtime.crm_configuration_save('regions', {'version': 1})
        self.assertFalse((runtime.USER_DATA_DIR / '.crm-region-settings.json').exists())

    def test_policy_conflicts_do_not_overwrite_another_grant(self):
        runtime.crm_configuration_save('policies', {'alice': {}}, {})
        with self.assertRaises(ValueError):
            runtime.crm_configuration_save('policies', {'bob': {}}, {})
        self.assertEqual(runtime.crm_security_policies(), {'alice': {}})

    def test_audit_is_structured_ordered_and_actor_scoped(self):
        runtime.crm_audit('alice', 'read', '/api/crm', 200)
        runtime.crm_audit('bob', 'write', '/api/crm', 403)
        self.assertEqual([event['actor'] for event in runtime.crmdb_audit_recent(None)], ['bob', 'alice'])
        self.assertEqual([event['actor'] for event in runtime.crmdb_audit_recent({'alice'})], ['alice'])
        self.assertEqual(runtime.crmdb_audit_recent(set()), [])
        self.assertFalse((runtime.USER_DATA_DIR / '.crm-security/audit.jsonl').exists())
        with runtime._crmdb_conn() as connection:
            self.assertEqual(connection.run("SELECT status FROM crm.security_events WHERE actor='bob'")[0][0], 403)

    def test_map_storage_and_proxy_preserve_secret(self):
        storage = runtime.crm_configuration_amap_storage()
        result = runtime.crm_amap.save_settings(runtime.USER_DATA_DIR, {'version': 0, 'key': 'a'*32, 'security_code': 'b'*32, 'enabled': True}, storage)
        self.assertTrue(result['has_security_code'])
        self.assertNotIn('security_code', result)
        url = runtime.crm_amap.proxy_url(runtime.USER_DATA_DIR, '/v3/config/district', 'key=bad', storage)
        self.assertIn('jscode=' + 'b'*32, url)
        self.assertFalse((runtime.USER_DATA_DIR / '.crm-amap-settings.json').exists())

    def test_export_includes_configurations_and_audit(self):
        runtime.crm_configuration_save('policies', {'alice': {'role': 'viewer'}})
        runtime.crm_audit('alice', 'read', '/api/crm', 200)
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(runtime.crm_configuration_export(temporary), 2)
            root = Path(temporary)
            self.assertEqual(json.loads((root / '.crm-security/policies.json').read_text())['alice']['role'], 'viewer')
            self.assertEqual(json.loads((root / '.crm-security/audit.jsonl').read_text())['actor'], 'alice')
