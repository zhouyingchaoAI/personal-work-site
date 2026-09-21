import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class OrganizationDepthTests(unittest.TestCase):
    def test_eight_levels_and_cycle_rejection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[{'username':'editor'}]}), patch.object(r,'crm_on_change'):
            root=r.crm_unit_save({'name':'总部','organization_level':'company'},'editor')['unit']
            nodes=[root]
            for i in range(1,8):
                result=r.crm_unit_save({'name':f'第{i+1}层组织','organization_level':'unit','parent_unit_id':nodes[-1]['id']},'editor')
                self.assertTrue(result['ok'],result)
                nodes.append(result['unit'])
            snapshot=r.crm_load('editor','units')
            bad=r.crm_unit_save({**nodes[1],'parent_unit_id':nodes[-1]['id']},'editor')
            self.assertFalse(bad['ok'])
            self.assertEqual(snapshot,r.crm_load('editor','units'))
            moved=r.crm_unit_save({**nodes[-1],'parent_unit_id':root['id']},'editor')
            self.assertTrue(moved['ok']);self.assertEqual(moved['unit']['parent_unit_id'],root['id'])
