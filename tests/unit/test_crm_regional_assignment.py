import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.runtime as r


class RegionalRelationshipAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.users = [
            {'username': 'root', 'role': 'superadmin'},
            {'username': 'manager', 'name': '经营管理员', 'role': 'member'},
            {'username': 'regional', 'name': '东区管理员', 'employee_id': 'R001', 'role': 'member'},
            {'username': 'liaison', 'name': '对接人员', 'employee_id': 'L001', 'role': 'member'},
            {'username': 'uploader', 'name': '上传人', 'role': 'member'},
        ]
        patches = [
            patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)),
            patch.object(r, 'read_config', return_value={'users': self.users}),
            patch.object(r, 'crm_on_change'),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        r.crm_security_grant({'username': 'manager', 'role': 'disabled', 'manager': True}, self.users[0], mode='appoint')
        r.crm_security_grant({
            'username': 'regional', 'role': 'regional_manager', 'data_scope': 'regions',
            'regions': ['东区'], 'expires_on': '',
        }, self.users[1])
        r.crm_store('uploader', 'units', {
            'east': {'id': 'east', 'name': '东区客户', 'business_regions': ['东区']},
            'west': {'id': 'west', 'name': '西区客户', 'business_regions': ['西区']},
        })
        r.crm_store('uploader', 'people', {
            'pe': {'id': 'pe', 'name': '东区联系人', 'unit_id': 'east'},
            'pw': {'id': 'pw', 'name': '西区联系人', 'unit_id': 'west'},
        })
        r.crm_store('uploader', 'relations', {
            're': {'id': 're', 'person_id': 'pe', 'our_member': '', 'version': 1},
            'rw': {'id': 'rw', 'person_id': 'pw', 'our_member': '', 'version': 1},
        })

    def test_region_manager_assigns_authorized_relations_and_creates_supervision_plan(self):
        result = r.crm_relation_batch_assign({
            'relation_ids': ['re'],
            'our_member': 'L001',
            'supervision': {
                'next_step': '本周完成首次拜访并上传纪要',
                'due_date': '2026-09-20',
                'supervisor': 'R001',
            },
        }, self.users[2])
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['plans_created'], 1)
        self.assertEqual(r.crm_load('uploader', 'relations')['re']['our_member'], 'L001')
        plan = next(iter(r.crm_load('uploader', 'actions').values()))
        self.assertEqual(plan['record_kind'], 'plan')
        self.assertEqual(plan['type'], '维系监督')
        self.assertEqual(plan['owner'], 'L001')
        self.assertEqual(plan['supervisor'], 'R001')
        self.assertEqual(plan['next_step'], '本周完成首次拜访并上传纪要')
        self.assertEqual(plan['due_date'], '2026-09-20')

    def test_batch_is_atomic_and_rejects_any_relation_outside_authorized_regions(self):
        with self.assertRaises(PermissionError):
            r.crm_relation_batch_assign({
                'relation_ids': ['re', 'rw'], 'our_member': 'L001',
            }, self.users[2])
        relations = r.crm_load('uploader', 'relations')
        self.assertEqual(relations['re']['our_member'], '')
        self.assertEqual(relations['rw']['our_member'], '')
        self.assertFalse(r.crm_load('uploader', 'actions'))

    def test_ordinary_editor_cannot_batch_assign_cross_owner_relationships(self):
        with patch.object(r, 'crm_capabilities', return_value={
            'read': True, 'write': True, 'batch_assign': False, 'data_scope': 'regions', 'regions': ['东区'],
        }):
            with self.assertRaises(PermissionError):
                r.crm_relation_batch_assign({'relation_ids': ['re'], 'our_member': 'L001'}, self.users[3])


if __name__ == '__main__':
    unittest.main()
