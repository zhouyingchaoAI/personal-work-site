import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.runtime as r


class FollowupAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.user = {'username': 'liaison', 'employee_id': 'E1'}
        self.caps = {'read': True, 'write': True, 'data_scope': 'self'}
        for item in (patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)),
                     patch.object(r, 'read_config', return_value={'users': [self.user, {'username': 'importer'}]}),
                     patch.object(r, 'crm_capabilities', side_effect=lambda _: self.caps),
                     patch.object(r, 'crm_on_change')):
            item.start()
            self.addCleanup(item.stop)
        r.crm_store('importer', 'units', {'u': {'id': 'u'}})
        r.crm_store('importer', 'people', {'p': {'id': 'p', 'unit_id': 'u'}})
        r.crm_store('importer', 'relations', {'r': {'id': 'r', 'person_id': 'p', 'our_member': 'E1'}})
        r.crm_store('importer', 'actions', {'a': {'id': 'a', 'relation_id': 'r', 'owner': 'E1', 'next_step': '回访'}})

    def test_assignee_can_complete_and_repeat_preserves_completion(self):
        self.assertTrue(r.crm_read_playbook(self.user)['followups'][0]['can_complete'])
        r.crm_followup_complete_authorized({'id': 'a', '_owner': 'fake'}, self.user)
        saved = r.crm_load('importer', 'actions')['a']
        self.assertEqual(saved['completed_by'], 'liaison')
        self.assertTrue(saved['completed_at'])
        r.crm_followup_complete_authorized({'id': 'a'}, self.user)
        self.assertEqual(saved, r.crm_load('importer', 'actions')['a'])
        self.assertEqual(r.crm_read_playbook(self.user)['followups'], [])
        self.assertEqual(r.crm_load('liaison', 'actions'), {})

    def test_readonly_and_revoked_assignment_cannot_complete(self):
        self.caps['write'] = False
        with self.assertRaises(PermissionError):
            r.crm_followup_complete_authorized({'id': 'a'}, self.user)
        self.caps['write'] = True
        r.crm_store('importer', 'relations', {'r': {'id': 'r', 'person_id': 'p', 'our_member': 'importer'}})
        with self.assertRaises(PermissionError):
            r.crm_followup_complete_authorized({'id': 'a'}, self.user)
        self.assertNotIn('completed_at', r.crm_load('importer', 'actions')['a'])

    def test_explicit_other_task_owner_is_readonly(self):
        r.crm_store('importer', 'actions', {'a': {'id': 'a', 'relation_id': 'r', 'owner': 'importer', 'next_step': '回访'}})
        self.assertFalse(r.crm_read_playbook(self.user)['followups'][0]['can_complete'])
        with self.assertRaises(PermissionError):
            r.crm_followup_complete_authorized({'id': 'a'}, self.user)
