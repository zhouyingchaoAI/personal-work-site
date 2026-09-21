import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.runtime as r


class CrmActionPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config = Path(self.tmp.name) / 'config.json'
        config.write_text(json.dumps({'users': [
            {'username': 'root', 'role': 'superadmin'},
            {'username': 'uploader', 'role': 'member', 'assistant_permissions': {'crm': True}},
            {'username': 'assignee', 'role': 'member', 'employee_id': 'A001', 'assistant_permissions': {'crm': True}},
            {'username': 'regional', 'role': 'member', 'assistant_permissions': {'crm': True}},
        ]}), encoding='utf-8')
        self.patches = [
            patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name) / 'data'),
            patch.object(r, 'CONFIG_PATH', config),
        ]
        for item in self.patches:
            item.start()
        r.crm_store('uploader', 'units', {
            'east': {'id': 'east', 'name': '东区客户', 'business_region': '东区'},
            'west': {'id': 'west', 'name': '西区客户', 'business_region': '西区'},
        })
        r.crm_store('uploader', 'people', {
            'pe': {'id': 'pe', 'unit_id': 'east', 'name': '东区联系人'},
            'pw': {'id': 'pw', 'unit_id': 'west', 'name': '西区联系人'},
        })
        r.crm_store('uploader', 'relations', {
            're': {'id': 're', 'person_id': 'pe', 'our_member': 'A001'},
            'rw': {'id': 'rw', 'person_id': 'pw', 'our_member': 'other'},
        })

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_assignee_with_action_permission_records_into_relation_owner_namespace(self):
        r.crm_security_grant({
            'username': 'assignee', 'role': 'viewer', 'data_scope': 'self',
            'register_action': True, 'expires_on': '',
        }, r.find_user('root'))

        result = r.crm_action_add_authorized({
            'relation_id': 're', 'type': '拜访', 'intel': '完成现场交流',
        }, r.find_user('assignee'))

        self.assertTrue(result['ok'])
        saved = next(iter(r.crm_load('uploader', 'actions').values()))
        self.assertEqual(saved['relation_id'], 're')
        self.assertEqual(saved['created_by'], 'assignee')
        self.assertFalse(r.crm_load('assignee', 'actions'))

    def test_action_permission_still_rejects_relations_outside_visible_region(self):
        r.crm_security_grant({
            'username': 'regional', 'role': 'regional_manager', 'data_scope': 'regions',
            'regions': ['东区'], 'register_action': True, 'expires_on': '',
        }, r.find_user('root'))

        self.assertTrue(r.crm_action_add_authorized(
            {'relation_id': 're', 'type': '电话沟通'}, r.find_user('regional'))['ok'])
        with self.assertRaises(PermissionError):
            r.crm_action_add_authorized(
                {'relation_id': 'rw', 'type': '电话沟通'}, r.find_user('regional'))

    def test_action_permission_is_independent_and_has_a_dedicated_route_operation(self):
        r.crm_security_grant({
            'username': 'assignee', 'role': 'editor', 'data_scope': 'self',
            'register_action': False, 'expires_on': '',
        }, r.find_user('root'))
        self.assertTrue(r.crm_capabilities(r.find_user('assignee'))['write'])
        self.assertFalse(r.crm_capabilities(r.find_user('assignee'))['register_action'])
        self.assertEqual(r.crm_security_operation('/api/crm/action/add', 'POST'), 'register_action')
        with self.assertRaises(PermissionError):
            r.crm_action_add_authorized(
                {'relation_id': 're', 'type': '拜访'}, r.find_user('assignee'))

    def test_business_manager_always_retains_action_permission(self):
        r.crm_security_grant({
            'username': 'regional', 'role': 'viewer', 'data_scope': 'self',
            'register_action': False, 'expires_on': '',
        }, r.find_user('root'))
        r.crm_security_grant({
            'username': 'regional', 'role': 'viewer', 'manager': True,
        }, r.find_user('root'), mode='appoint')
        self.assertTrue(r.crm_capabilities(r.find_user('regional'))['register_action'])


if __name__ == '__main__':
    unittest.main()
