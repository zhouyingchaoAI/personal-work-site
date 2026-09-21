import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class ManagerReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.users = [{'username': 'admin', 'role': 'superadmin'},
                      {'username': 'alice', 'name': '同名', 'employee_id': 'E001'},
                      {'username': 'bob', 'name': '同名'}]
        for p in [patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)),
                  patch.object(r, 'read_config', return_value={'users': self.users})]:
            p.start(); self.addCleanup(p.stop)
        r.crm_store('bob', 'units', {'u': {'id': 'u', 'business_regions': ['西区']}})
        r.crm_store('bob', 'people', {'p': {'id': 'p', 'unit_id': 'u', 'name': '客户'}})
        r.crm_store('bob', 'relations', {
            'ra': {'id': 'ra', 'person_id': 'p', 'our_member': 'E001'},
            'rb': {'id': 'rb', 'person_id': 'p', 'our_member': 'bob'}})
        r.crm_store('bob', 'actions', {
            'a': {'id': 'a', 'relation_id': 'ra', 'next_step': '甲计划', 'owner': 'E001'},
            'b': {'id': 'b', 'relation_id': 'rb', 'next_step': '乙计划', 'owner': 'bob'},
            'done': {'id': 'done', 'relation_id': 'ra', 'next_step': '已完成', 'completed_at': '2026-01-01'}})

    def test_admin_directory_has_distinct_account_keys_not_names(self):
        self.assertTrue(hasattr(r, 'crm_manager_directory'), 'missing manager review directory')
        result = r.crm_manager_directory(self.users[0])
        accounts = {item['username']: item for item in result['managers']}
        self.assertEqual(accounts['alice']['member_keys'], ['alice', 'E001'])
        self.assertEqual(accounts['bob']['member_keys'], ['bob'])
        self.assertNotIn('password', accounts['alice'])

    def test_non_admin_even_all_scope_cannot_read_manager_directory(self):
        self.assertTrue(hasattr(r, 'crm_manager_directory'), 'missing permission boundary')
        for caps in [{'read': True, 'data_scope': 'self'}, {'read': True, 'data_scope': 'all'}]:
            with patch.object(r, 'crm_capabilities', return_value=caps):
                with self.assertRaises(PermissionError):
                    r.crm_manager_directory(self.users[1])

    def test_followups_match_authorized_cross_owner_relations(self):
        self.assertTrue(hasattr(r, 'crm_read_playbook'), 'missing scoped followup reader')
        self.assertEqual({a['id'] for a in r.crm_read_playbook(self.users[0])['followups']}, {'a', 'b'})
        with patch.object(r, 'crm_capabilities', return_value={'read': True, 'data_scope': 'self'}):
            self.assertEqual([a['id'] for a in r.crm_read_playbook(self.users[1])['followups']], ['a'])

    def test_disabled_user_cannot_read_followups(self):
        self.assertTrue(hasattr(r, 'crm_read_playbook'), 'missing scoped followup reader')
        with self.assertRaises(PermissionError):
            r.crm_read_playbook(self.users[1])

    def test_cross_owner_followups_are_explicitly_read_only(self):
        for action in r.crm_read_playbook(self.users[0])['followups']:
            self.assertIs(action.get('can_complete'), False)
        with patch.object(r, 'crm_capabilities', return_value={'read': True, 'write': True, 'data_scope': 'self'}):
            self.assertTrue(all(a['can_complete'] for a in r.crm_read_playbook(self.users[2])['followups']))
