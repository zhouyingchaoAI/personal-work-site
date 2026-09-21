import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class QualitySettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = patch.object(r, 'USER_DATA_DIR', Path(directory.name))
        root.start()
        self.addCleanup(root.stop)
        audit = patch.object(r, 'crm_audit')
        self.audit = audit.start()
        self.addCleanup(audit.stop)
        self.admin = {'username': 'admin', 'role': 'superadmin'}

    def test_persist_version_audit_and_no_customer_mutation(self):
        r.crm_store('alice', 'people', {'p': {'name': 'original'}})
        before = r.crm_collection_path('alice', 'people').read_bytes()
        initial = r.crm_quality_settings(self.admin)
        self.assertEqual(initial['version'], 0)
        initial['rules']['recent_days'] = 30
        initial['rules']['weights'] = [40, 20, 20, 10, 10]
        saved = r.crm_quality_settings_save(initial, self.admin)
        self.assertEqual(saved['version'], 1)
        self.assertEqual(saved['updated_by'], 'admin')
        self.assertEqual(r.crm_quality_settings(self.admin)['rules']['recent_days'], 30)
        self.assertEqual(saved['defaults']['recent_days'], 90)
        self.assertEqual(r.crm_collection_path('alice', 'people').read_bytes(), before)
        self.assertEqual(self.audit.call_count, 2)
        self.assertEqual(self.audit.call_args.args[5]['before']['recent_days'], 90)
        with self.assertRaisesRegex(ValueError, '其他人更新'):
            r.crm_quality_settings_save(initial, self.admin)
        self.assertEqual(r.crm_quality_settings(self.admin)['version'], 1)

    def test_permissions(self):
        value = r.crm_quality_settings(self.admin)
        with patch.object(r, 'crm_capabilities', return_value={'read': True, 'write': True}):
            self.assertEqual(r.crm_quality_settings({'username': 'viewer'})['version'], 0)
            with self.assertRaises(PermissionError):
                r.crm_quality_settings_save(value, {'username': 'viewer'})
        with patch.object(r, 'crm_capabilities', return_value={}):
            with self.assertRaises(PermissionError):
                r.crm_quality_settings({'username': 'outsider'})
        with patch.object(r, 'crm_capabilities', return_value={'read': True, 'manage': True}):
            self.assertEqual(r.crm_quality_settings_save(value, {'username': 'manager'})['version'], 1)
        self.assertEqual(r.crm_security_operation('/api/crm/security/quality-settings', 'GET'), 'read')
        self.assertEqual(r.crm_security_operation('/api/crm/security/quality-settings', 'POST'), 'manage')

    def test_invalid_rules_never_persist(self):
        initial = r.crm_quality_settings(self.admin)
        mutations = [
            ('weights', [30, 25, 20, 15, 11]), ('weights', [True, 24, 30, 25, 20]),
            ('weights', [100, 0, 0, 0, 0]), ('weights', [25.5, 24.5, 20, 20, 10]),
            ('recent_days', 0), ('recent_days', 366), ('min_dimensions', None),
            ('good_threshold', 40), ('backup_count', 1), ('strength_weight', 101),
            ('support_scores', {'反对': 100, '中立': 40, '支持': 75, '积极支持': 100}),
            ('templates', {'厂商': ['定技术']}),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                payload = copy.deepcopy(initial)
                payload['rules'][key] = value
                with self.assertRaises(ValueError):
                    r.crm_quality_settings_save(payload, self.admin)
        for roles in [['定技术', '定技术'], ['随意角色'], [None]]:
            payload = copy.deepcopy(initial)
            payload['rules']['templates']['业主单位'] = roles
            with self.assertRaises(ValueError):
                r.crm_quality_settings_save(payload, self.admin)
        self.assertEqual(r.crm_quality_settings(self.admin)['version'], 0)
        self.audit.assert_not_called()

    def test_disabled_dimensions_and_empty_template_supported(self):
        initial = r.crm_quality_settings(self.admin)
        initial['rules']['weights'] = [0, 40, 30, 20, 10]
        initial['rules']['templates']['厂商'] = []
        saved = r.crm_quality_settings_save(initial, self.admin)
        self.assertEqual(saved['rules']['weights'][0], 0)
        self.assertEqual(saved['rules']['templates']['厂商'], [])

    def test_legacy_company_settings_gain_personal_defaults_without_writing(self):
        import json
        initial = r.crm_quality_settings(self.admin)
        for key in ('personal_weights', 'personal_min_dimensions', 'personal_maintenance_days'):
            initial['rules'].pop(key)
        initial['rules']['recent_days'] = 45
        initial['version'] = 7
        path = r.USER_DATA_DIR / '.crm-quality-settings.json'
        path.write_text(json.dumps(initial))
        before = path.read_bytes()
        loaded = r.crm_quality_settings(self.admin)
        self.assertEqual(loaded['rules']['personal_weights'], [45, 30, 25])
        self.assertEqual(loaded['rules']['recent_days'], 45)
        self.assertEqual(loaded['version'], 7)
        self.assertEqual(path.read_bytes(), before)

    def test_personal_rule_validation(self):
        for key, value in [('personal_weights', [100, 0, 0]), ('personal_weights', [30, 30, 30]), ('personal_min_dimensions', 4), ('personal_maintenance_days', 0)]:
            initial = r.crm_quality_settings(self.admin)
            initial['rules'][key] = value
            with self.assertRaises(ValueError):
                r.crm_quality_settings_save(initial, self.admin)
