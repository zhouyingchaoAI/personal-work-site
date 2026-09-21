import unittest
from unittest.mock import patch
import backend.runtime as r

class MemberOrganizationTests(unittest.TestCase):
    def test_blank_contact_does_not_match_nameless_account(self):
        with patch.object(r,'read_config',return_value={'users':[{'username':'admin','department':'Ops'}]}), patch.object(r,'crm_load',return_value={}):
            self.assertIsNone(r.crm_member_resolver()('uploader','')[0])

    def test_current_account_organization_and_identity_aliases(self):
        users=[{'username':'alice','employee_id':'E1','name':'张三','company':'新公司','department':'中心 / 部门','position':'经理','password':'secret'},
               {'username':'dup1','name':'同名'}, {'username':'dup2','name':'同名'}]
        staff={'old':{'member_key':'张三','name':'张三','department':'旧部门','title':'旧岗位'}}
        with patch.object(r,'read_config',return_value={'users':users}), patch.object(r,'crm_load',return_value=staff):
            resolve=r.crm_member_resolver()
            for key in ('alice','E1','张三'):
                profile,label=resolve('uploader',key)
                self.assertIsNotNone(profile)
                self.assertEqual(profile['department'],'中心 / 部门')
                self.assertEqual(profile['title'],'经理')
                self.assertEqual(profile['username'],'alice')
                self.assertNotIn('password',profile)
            self.assertIsNone(resolve('uploader','同名')[0])
            self.assertEqual(staff['old']['department'],'旧部门')
