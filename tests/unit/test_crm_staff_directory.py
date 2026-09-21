import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class DirectoryTests(unittest.TestCase):
 def test_directory_available_with_owner_override_and_other_collections_unchanged(self):
  with tempfile.TemporaryDirectory() as folder, patch.object(r,'USER_DATA_DIR',Path(folder)), patch.object(r,'crm_on_change'):
   record={'id':'staff_dir_01','name':'测试人员','member_key':'001','company':'测试公司','department':'中心 / 部门','title':'','manager_id':'','business_region':'','responsibilities':'','version':1}
   (Path(folder)/'_crm_staff_directory.json').write_text(json.dumps({record['id']:record}))
   self.assertEqual(r.crm_load('alice','staff')[record['id']]['department'],'中心 / 部门')
   self.assertEqual(r.crm_load('alice','people'),{})
   result=r.crm_staff_save({**record,'department':'另一部门'},'alice')
   self.assertTrue(result['ok'])
   self.assertEqual(r.crm_load('alice','staff')[record['id']]['department'],'另一部门')
   self.assertEqual(r.crm_load('bob','staff')[record['id']]['department'],'中心 / 部门')
   r.crm_store('bob','staff',{'legacy':{**record,'id':'legacy'}})
   self.assertEqual(list(r.crm_load('bob','staff')),['legacy'])
