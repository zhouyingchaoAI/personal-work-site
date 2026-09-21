import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class PersonMoveTests(unittest.TestCase):
    def test_move_preserves_identity_relations_actions_and_rejects_foreign_target(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[{'username':'alice'},{'username':'bob'}]}), patch.object(r,'crm_on_change'):
            a=r.crm_unit_save({'name':'公司A','type':'业主单位'},'alice')['unit']
            b=r.crm_unit_save({'name':'单位B','type':'业主单位'},'alice')['unit']
            person=r.crm_person_save({'name':'联系人','unit_id':a['id'],'department':'原部门'},'alice')['person']
            relation=r.crm_relation_save({'person_id':person['id'],'our_member':'alice'},'alice')['relation']
            r.crm_action_add({'relation_id':relation['id'],'type':'拜访','intel':'原有记录'},'alice')
            before={k:r.crm_load('alice',k) for k in ['relations','actions']}
            result=r.crm_person_save({**person,'unit_id':b['id'],'department':'新部门'},'alice')
            self.assertTrue(result['ok']);self.assertEqual(result['person']['id'],person['id'])
            self.assertEqual(result['person']['department'],'新部门')
            for k in before:self.assertEqual(r.crm_load('alice',k),before[k])
            self.assertFalse(r.crm_person_save({**person,'unit_id':a['id']},'alice')['ok'])
            foreign=r.crm_unit_save({'name':'其他账号组织'},'bob')['unit']
            self.assertFalse(r.crm_person_save({**result['person'],'unit_id':foreign['id']},'alice')['ok'])
