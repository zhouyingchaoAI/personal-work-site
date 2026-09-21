import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class DepartmentNodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)); p.start(); self.addCleanup(p.stop)
        p = patch.object(r, 'crm_on_change'); p.start(); self.addCleanup(p.stop)
        self.root = r.crm_unit_save({'name':'集团'}, 'alice')['unit']
        self.person = r.crm_person_save({'name':'联系人','unit_id':self.root['id'],'department':'技术部','mobile':'123'}, 'alice')['person']
        self.relation = r.crm_relation_save({'person_id':self.person['id'],'our_member':'alice'}, 'alice')['relation']

    def test_add_materializes_department_and_preserves_contacts_and_relations(self):
        before = r.crm_load('alice', 'relations')
        result = r.crm_department_node({'unit_id':self.root['id'],'department':'技术部','action':'add','name':'项目组'}, 'alice')
        self.assertTrue(result['ok'])
        units = r.crm_load('alice', 'units')
        department = units[result['unit']['parent_unit_id']]
        self.assertEqual(department['name'], '技术部')
        self.assertEqual(department['parent_unit_id'], self.root['id'])
        person = r.crm_load('alice','people')[self.person['id']]
        self.assertEqual(person['unit_id'], department['id'])
        self.assertEqual(person['department'], '')
        self.assertEqual(person['mobile'], '123')
        self.assertEqual(before, r.crm_load('alice','relations'))

    def test_delete_clears_department_without_deleting_people(self):
        result = r.crm_department_node({'unit_id':self.root['id'],'department':'技术部','action':'delete'}, 'alice')
        self.assertTrue(result['ok'])
        person = r.crm_load('alice','people')[self.person['id']]
        self.assertEqual(person['unit_id'],self.root['id'])
        self.assertEqual(person['department'],'')
        self.assertIn(self.relation['id'],r.crm_load('alice','relations'))

    def test_rejects_foreign_owner_stale_and_invalid_requests_without_writes(self):
        before = {c:r.crm_load('alice',c) for c in ['people','units']}
        payload = {'unit_id':self.root['id'],'department':'技术部','action':'add','name':'项目组'}
        self.assertFalse(r.crm_department_node(payload,'bob')['ok'])
        self.assertFalse(r.crm_department_node({**payload,'department':'不存在'},'alice')['ok'])
        self.assertFalse(r.crm_department_node({**payload,'name':''},'alice')['ok'])
        self.assertEqual(before,{c:r.crm_load('alice',c) for c in before})
