import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class InternalOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'config.json'
        self.initial = {'users': [
            {'username':'root', 'role':'superadmin'},
            {'username':'alice', 'role':'member', 'employee_id':'E001', 'company':'甲公司', 'department':'中心/工程部', 'position':'经理', 'password':'unchanged', 'assistant_permissions':{'crm':True}},
            {'username':'bob', 'role':'admin', 'company':'乙公司', 'department':'销售部'},
        ], 'unrelated': {'preserved': True}}
        self.path.write_text(json.dumps(self.initial))
        self.addCleanup(patch.stopall)
        patch.object(r, 'CONFIG_PATH', self.path).start()
        patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)).start()

    def draft(self):
        d = r.internal_organization_get('root')
        return {'revision':d['revision'], 'nodes':d['nodes'], 'assignments':{m['username']:m['node_id'] for m in d['members']}}

    def test_snapshot_is_readonly_and_minimal(self):
        before = self.path.read_bytes()
        d = r.internal_organization_get('root')
        self.assertEqual(before, self.path.read_bytes())
        self.assertNotIn('password', json.dumps(d))
        self.assertEqual(len(d['members']), 3)

    def test_multiple_memberships_preserve_accounts_and_validate_targets(self):
        draft = self.draft()
        target = next(node['id'] for node in draft['nodes'] if node['name']=='乙公司')
        draft['memberships'] = {'alice': [target, target, draft['assignments']['alice']]}
        saved = r.internal_organization_save(draft, 'root')
        member = next(member for member in saved['members'] if member['username']=='alice')
        self.assertEqual(member['node_ids'], [target])
        self.assertEqual(json.loads(self.path.read_text())['users'], self.initial['users'])
        with self.assertRaises(ValueError):
            r.internal_organization_save(draft, 'root')
        bad = self.draft()
        bad['memberships'] = {'alice': ['own:missing']}
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            r.internal_organization_save(bad, 'root')
        self.assertEqual(self.path.read_bytes(), before)
        retained = r.internal_organization_save(self.draft(), 'root')
        self.assertEqual(next(member for member in retained['members'] if member['username']=='alice')['node_ids'], [target])
        remove = self.draft()
        remove['memberships'] = {'alice': []}
        r.internal_organization_save(remove, 'root')
        self.assertEqual(json.loads(self.path.read_text())['users'], self.initial['users'])

    def test_save_deep_hierarchy_empty_nodes_and_identity(self):
        d = self.draft()
        parent = next(n['id'] for n in d['nodes'] if n['name']=='乙公司')
        for i in range(6):
            ident = f'own:extra{i}'
            d['nodes'].append({'id':ident,'name':f'层{i}','parent_id':parent})
            parent = ident
        d['nodes'].append({'id':'own:empty','name':'空部门','parent_id':parent})
        d['assignments']['alice'] = parent
        result = r.internal_organization_save(d, 'root')
        self.assertEqual(result['updated_members'], 1)
        updated = json.loads(self.path.read_text())
        expected = copy.deepcopy(self.initial['users'][1])
        expected.update(company='乙公司', department=' / '.join(f'层{i}' for i in range(6)))
        self.assertEqual(updated['users'][1], expected)
        self.assertEqual(updated['users'][0], self.initial['users'][0])
        self.assertEqual(updated['unrelated'], self.initial['unrelated'])
        self.assertTrue(any(n['id']=='own:empty' for n in r.internal_organization_get('root')['nodes']))
        records={'s':{'id':'s','member_key':'E001','company':'过时','department':'旧部门','title':'原岗位','version':7}}
        resolved = r.internal_organization_staff(records)
        self.assertEqual(resolved['s']['department'],expected['department'])
        self.assertEqual(resolved['s']['version'],7)
        self.assertEqual(resolved['s']['title'],'原岗位')
        self.assertEqual(records['s']['company'],'过时')

    def test_permission_conflict_and_invalid_graph_do_not_write(self):
        d = self.draft(); before = self.path.read_bytes()
        for username in ('alice','bob'):
            with self.assertRaises(PermissionError): r.internal_organization_get(username)
            with self.assertRaises(PermissionError): r.internal_organization_save(d,username)
        with self.assertRaises(ValueError): r.internal_organization_save(dict(d,revision='old'),'root')
        broken = copy.deepcopy(d)
        broken['nodes'][0]['parent_id'] = broken['nodes'][0]['id']
        with self.assertRaises(ValueError): r.internal_organization_save(broken,'root')
        broken = copy.deepcopy(d); del broken['assignments']['alice']
        with self.assertRaises(ValueError): r.internal_organization_save(broken,'root')
        broken = copy.deepcopy(d); broken['assignments']['alice']='missing'
        with self.assertRaises(ValueError): r.internal_organization_save(broken,'root')
        self.assertEqual(before,self.path.read_bytes())

    def test_reparent_updates_entire_subtree_and_external_edit_conflicts(self):
        d=self.draft()
        center=next(n for n in d['nodes'] if n['name']=='中心')
        center['parent_id']=next(n['id'] for n in d['nodes'] if n['name']=='乙公司')
        r.internal_organization_save(d,'root')
        alice=json.loads(self.path.read_text())['users'][1]
        self.assertEqual((alice['company'],alice['department']),('乙公司','中心 / 工程部'))
        d=self.draft(); config=r.read_config();config['users'][1]['department']='新部门';r.write_config(config)
        with self.assertRaises(ValueError):r.internal_organization_save(d,'root')


if __name__=='__main__': unittest.main()
