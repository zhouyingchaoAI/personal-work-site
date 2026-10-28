import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class SimpleAssignmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.admin={'username':'admin','role':'superadmin'}
  self.users=[self.admin,{'username':'old','employee_id':'E1'},{'username':'new','employee_id':'E2'}]
  for p in [patch.object(r,'USER_DATA_DIR',Path(self.tmp.name)),patch.object(r,'read_config',return_value={'users':self.users}),patch.object(r,'crm_on_change'),patch.object(r,'crm_audit')]:
   p.start();self.addCleanup(p.stop)
  r.crm_store('admin','units',{'u':{'id':'u','business_regions':['东区']}})
  r.crm_store('admin','people',{'p':{'id':'p','name':'客户','unit_id':'u'},'p2':{'id':'p2','unit_id':'u'}})
  r.crm_store('admin','relations',{'r':{'id':'r','person_id':'p','our_member':'E1'}})
  r.crm_store('admin','actions',{'a':{'id':'a','relation_id':'r','record_kind':'plan','owner':'E1','next_step':'原计划'}})
 def test_add_preserves_original_and_is_idempotent(self):
  payload={'person_ids':['p','p2'],'our_member':'new','mode':'add'}
  result=r.crm_relation_batch_assign(payload,self.admin)
  self.assertEqual(result['updated'],2)
  rows=r.crm_load('admin','relations')
  self.assertEqual(rows['r']['our_member'],'E1')
  self.assertEqual(sum(x['our_member']=='E2' for x in rows.values()),2)
  self.assertEqual(r.crm_load('admin','actions')['a']['owner'],'E1')
  again=r.crm_relation_batch_assign(payload,self.admin)
  self.assertEqual(again['updated'],0)
  self.assertEqual(len(r.crm_load('admin','relations')),3)
 def test_invalid_person_cancels_entire_batch(self):
  with self.assertRaises(PermissionError):r.crm_relation_batch_assign({'person_ids':['p','invisible'],'our_member':'new','mode':'add'},self.admin)
  self.assertEqual(len(r.crm_load('admin','relations')),1)
 def test_no_manager_permission(self):
  with self.assertRaises(PermissionError):r.crm_relation_batch_assign({'person_ids':['p'],'our_member':'new','mode':'add'},self.users[1])
  with self.assertRaises(PermissionError):r.crm_assignment_directory(self.users[1])
 def test_regional_assignment_directory_without_local_staff(self):
  self.users.append({'username':'no-id','name':'无工号人员'})
  r.crm_security_grant({'username':'old','role':'regional_manager','data_scope':'regions','regions':['东区'],'expires_on':''},self.admin)
  directory=r.crm_assignment_directory(self.users[1])['people']
  self.assertIn('no-id',[p['member_key'] for p in directory])
  self.assertIn('E2',[p['member_key'] for p in directory])
 def test_legacy_staff_alias_is_not_duplicated(self):
  self.users[2]['name']='目标经理'
  r.crm_staff_save({'name':'目标经理','member_key':'LEGACY','company':'公司'},'admin')
  rows=r.crm_load('admin','relations');rows['r']['our_member']='LEGACY';r.crm_store('admin','relations',rows)
  result=r.crm_relation_batch_assign({'person_ids':['p'],'our_member':'new','mode':'add'},self.admin)
  self.assertEqual(result['updated'],0)
  self.assertEqual(len(r.crm_load('admin','relations')),1)
 def test_transfer_preserves_history_and_moves_pending(self):
  actions=r.crm_load('admin','actions');actions['history']={'id':'history','relation_id':'r','record_kind':'interaction','owner':'E1','intel':'历史交流'};r.crm_store('admin','actions',actions)
  r.crm_relation_batch_assign({'relation_ids':['r'],'our_member':'new','transfer':True},self.admin)
  self.assertEqual(r.crm_load('admin','relations')['r']['our_member'],'E2')
  self.assertEqual(r.crm_load('admin','actions')['a']['owner'],'E2')
  self.assertEqual(r.crm_load('admin','actions')['history'],actions['history'])
 def test_regional_manager_rejects_mixed_scope_without_partial_write(self):
  units=r.crm_load('admin','units');units['west']={'id':'west','business_regions':['西区']};r.crm_store('admin','units',units)
  people=r.crm_load('admin','people');people['west-person']={'id':'west-person','unit_id':'west'};r.crm_store('admin','people',people)
  r.crm_security_grant({'username':'old','role':'regional_manager','data_scope':'regions','regions':['东区'],'expires_on':''},self.admin)
  with self.assertRaises(PermissionError):r.crm_relation_batch_assign({'person_ids':['p','west-person'],'our_member':'new','mode':'add'},self.users[1])
  self.assertEqual(len(r.crm_load('admin','relations')),1)
  self.assertEqual(r.crm_relation_batch_assign({'person_ids':['p'],'our_member':'new','mode':'add'},self.users[1])['updated'],1)
