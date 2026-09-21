import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class PersonalAssignments(unittest.TestCase):
    def test_legacy_chinese_name_assignment_resolves_to_unique_account(self):
        users = [
            {'username': 'chenzhengyun', 'name': '陈正云', 'employee_id': '240512'},
            {'username': 'uploader', 'name': '上传人'},
        ]
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r, 'USER_DATA_DIR', Path(tmp)), \
                patch.object(r, 'read_config', return_value={'users': users}), \
                patch.object(r, 'crm_capabilities', return_value={'read': True, 'data_scope': 'self'}):
            r.crm_store('uploader', 'units', {'u': {'id': 'u', 'business_regions': ['广东区']}})
            r.crm_store('uploader', 'people', {'p': {'id': 'p', 'unit_id': 'u'}})
            r.crm_store('uploader', 'relations', {
                'mine': {'id': 'mine', 'person_id': 'p', 'our_member': '陈正云'},
            })
            r.crm_store('uploader', 'actions', {
                'followup': {'id': 'followup', 'relation_id': 'mine', 'next_step': '补充客户关系'},
            })

            snapshot = r.crm_read_snapshot(users[0])
            self.assertEqual([item['id'] for item in snapshot['relations']], ['mine'])
            self.assertEqual([item['id'] for item in snapshot['actions']], ['followup'])
            self.assertEqual(
                [item['relation_id'] for item in r.crm_read_playbook(users[0])['followups']],
                ['mine'],
            )

    def test_ambiguous_chinese_name_does_not_grant_relationship_access(self):
        users = [
            {'username': 'alice', 'name': '同名人员', 'employee_id': 'E001'},
            {'username': 'alice2', 'name': '同名人员', 'employee_id': 'E002'},
            {'username': 'uploader', 'name': '上传人'},
        ]
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r, 'USER_DATA_DIR', Path(tmp)), \
                patch.object(r, 'read_config', return_value={'users': users}), \
                patch.object(r, 'crm_capabilities', return_value={'read': True, 'data_scope': 'self'}):
            r.crm_store('uploader', 'units', {'u': {'id': 'u'}})
            r.crm_store('uploader', 'people', {'p': {'id': 'p', 'unit_id': 'u'}})
            r.crm_store('uploader', 'relations', {
                'ambiguous': {'id': 'ambiguous', 'person_id': 'p', 'our_member': '同名人员'},
            })
            self.assertEqual(r.crm_read_snapshot(users[0])['relations'], [])

    def test_cross_owner_assignment_is_readable_without_peer_relations(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users':[{'username':'alice','employee_id':'E001'},{'username':'bob'}]}), patch.object(r, 'crm_capabilities', return_value={'read':True,'data_scope':'self'}):
            r.crm_store('bob','units',{'u':{'id':'u','business_regions':['西区']},'private':{'id':'private'}})
            r.crm_store('bob','people',{'p':{'id':'p','unit_id':'u'},'peer':{'id':'peer','unit_id':'u'}})
            r.crm_store('bob','relations',{'mine':{'id':'mine','person_id':'p','our_member':'E001'},'other':{'id':'other','person_id':'p','our_member':'bob'},'peer':{'id':'peer','person_id':'peer','our_member':'bob'}})
            r.crm_store('bob','actions',{'a':{'id':'a','relation_id':'mine'},'b':{'id':'b','relation_id':'other'}})
            user={'username':'alice'}
            snapshot=r.crm_read_snapshot(user)
            for name, ids in [('units',['u']),('people',['p']),('relations',['mine']),('actions',['a'])]:
                self.assertEqual([x['id'] for x in snapshot[name]],ids)
            self.assertEqual(snapshot['relations'][0]['_owner'],'bob')
            with patch.object(r,'crm_capabilities',return_value={'read':True,'data_scope':'regions','regions':['东区']}):
                self.assertEqual([x['id'] for x in r.crm_read_snapshot(user)['relations']],['mine'])
            records=r.crm_load('bob','relations');records['mine']['our_member']='alice';r.crm_store('bob','relations',records)
            self.assertEqual(len(r.crm_read_snapshot(user)['relations']),1)
            records['mine']['our_member']='bob';r.crm_store('bob','relations',records)
            self.assertEqual(r.crm_read_snapshot(user)['relations'],[])

    def test_disabled_caller_does_not_gain_assignment_access(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[{'username':'alice'},{'username':'bob'}]}), patch.object(r,'crm_capabilities',return_value={'read':False,'data_scope':'self'}):
            r.crm_store('bob','units',{'u':{'id':'u'}})
            r.crm_store('bob','people',{'p':{'id':'p','unit_id':'u'}})
            r.crm_store('bob','relations',{'r':{'id':'r','person_id':'p','our_member':'alice'}})
            self.assertEqual(r.crm_read_snapshot({'username':'alice'})['relations'],[])

    def test_assignee_can_edit_imported_relation_but_cannot_reassign_it(self):
        users = [
            {'username': 'alice', 'employee_id': 'E001'},
            {'username': 'bob', 'employee_id': 'E002'},
            {'username': 'uploader', 'name': '上传人'},
        ]
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r, 'USER_DATA_DIR', Path(tmp)), \
                patch.object(r, 'read_config', return_value={'users': users}), \
                patch.object(r, 'crm_capabilities', return_value={'read': True, 'write': True, 'data_scope': 'self'}), \
                patch.object(r, 'crm_on_change'):
            r.crm_store('uploader', 'units', {'u': {'id': 'u'}})
            r.crm_store('uploader', 'people', {'p': {'id': 'p', 'unit_id': 'u'}})
            r.crm_store('uploader', 'relations', {
                'r': {'id': 'r', 'person_id': 'p', 'our_member': 'E001', 'source': '导入', 'version': 1},
            })
            saved = r.crm_relation_save_authorized({
                'id': 'r', 'person_id': 'p', 'our_member': 'E001', 'source': '客户拜访', 'version': 1,
            }, users[0])
            self.assertTrue(saved['ok'])
            self.assertEqual(saved['relation']['created_by'], 'uploader')
            self.assertEqual(saved['relation']['updated_by'], 'alice')
            self.assertEqual(r.crm_load('uploader', 'relations')['r']['source'], '客户拜访')
            self.assertFalse(r.crm_relation_save_authorized({'id': 'r', 'source': '无版本'}, users[0])['ok'])
            with self.assertRaises(PermissionError):
                r.crm_relation_save_authorized({'id': 'r', 'person_id': 'other', 'version': 2}, users[0])
            patched = r.crm_relation_save_authorized({'id': 'r', 'version': saved['relation']['version'], 'source': '再次拜访'}, users[0])
            self.assertTrue(patched['ok'])
            self.assertEqual(patched['relation']['our_member'], 'E001')
            saved = patched
            with self.assertRaises(PermissionError):
                r.crm_relation_save_authorized({
                    'id': 'r', 'person_id': 'p', 'our_member': 'E002', 'version': saved['relation']['version'],
                }, users[0])
