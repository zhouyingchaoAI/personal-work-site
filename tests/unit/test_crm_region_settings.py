import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class RegionSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name))
        self.root.start()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.root.stop)
        self.admin = {'username': 'root', 'role': 'superadmin'}

    def test_save_persists_cross_region_provinces_without_changing_customers(self):
        r.crm_store('alice', 'units', {'u': {'province': '浙江', 'business_region': '东区'}})
        before = r.crm_collection_path('alice', 'units').read_bytes()
        initial = r.crm_region_settings()
        initial['regions']['东区'] = ['江苏', '湖南', '江苏']
        saved = r.crm_region_settings_save(initial, self.admin)
        self.assertEqual(saved['version'], 1)
        self.assertEqual(r.crm_region_settings()['regions']['东区'], ['江苏', '湖南'])
        self.assertIn('湖南', saved['regions']['西区'])
        self.assertEqual(r.crm_collection_path('alice', 'units').read_bytes(), before)
        with self.assertRaises(ValueError):
            r.crm_region_settings_save(initial, self.admin)

    def test_permissions_and_invalid_provinces(self):
        initial = r.crm_region_settings()
        with patch.object(r, 'crm_capabilities', return_value={'read': True, 'write': True}):
            with self.assertRaises(PermissionError):
                r.crm_region_settings_save(initial, {'username': 'alice'})
        initial['regions']['东区'] = ['未知省份']
        with self.assertRaises(ValueError):
            r.crm_region_settings_save(initial, self.admin)
        self.assertEqual(r.crm_region_settings()['version'], 0)
        self.assertEqual(r.crm_security_operation('/api/crm/security/region-settings', 'GET'), 'read')
        self.assertEqual(r.crm_security_operation('/api/crm/security/region-settings', 'POST'), 'manage')

    def test_manager_can_save_empty_region(self):
        initial = r.crm_region_settings()
        initial['regions']['广东区'] = []
        with patch.object(r, 'crm_capabilities', return_value={'manage': True}):
            r.crm_region_settings_save(initial, {'username': 'manager'})
        self.assertEqual(r.crm_region_settings()['regions']['广东区'], [])

    def test_city_bindings_validate_province_and_preserve_old_clients(self):
        initial = r.crm_region_settings()
        initial['cities']['西区'] = [{'province': '浙江', 'city': '杭州'}] * 2
        saved = r.crm_region_settings_save(initial, self.admin)
        self.assertEqual(saved['cities']['西区'], [{'province': '浙江', 'city': '杭州'}])
        self.assertNotIn('浙江', saved['regions']['西区'])
        saved.pop('cities')
        saved = r.crm_region_settings_save(saved, self.admin)
        self.assertEqual(saved['cities']['西区'], [{'province': '浙江', 'city': '杭州'}])
        saved['cities']['西区'] = [{'province': '广东', 'city': '杭州'}]
        with self.assertRaises(ValueError):
            r.crm_region_settings_save(saved, self.admin)
        self.assertEqual(r.crm_region_settings()['version'], 2)

    def test_existing_province_config_loads_without_city_migration(self):
        import json
        legacy = {'regions': r.CRM_STANDARD_REGIONS, 'version': 4}
        (Path(self.tmp.name) / '.crm-region-settings.json').write_text(json.dumps(legacy))
        self.assertEqual(r.crm_region_settings()['cities'], {n: [] for n in r.CRM_STANDARD_REGIONS})
