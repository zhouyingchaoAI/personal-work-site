import tempfile
import json
import unittest
import http.client
import threading
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        config=Path(self.tmp.name)/'config.json'
        config.write_text(json.dumps({'users':[{'username':'root','role':'superadmin'},{'username':'alice','role':'member','assistant_permissions':{'crm':True},'employee_id':'120001','company':'承希科技','department':'服务解决方案中心 / 服务交付部','position':'交付工程师'},{'username':'manager','role':'admin'}]}))
        self.patches=[patch.object(r,'USER_DATA_DIR',Path(self.tmp.name)/'data'),patch.object(r,'CONFIG_PATH',config),patch.object(r,'SESSIONS',{'root':'root','alice':'alice','manager':'manager'})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def grant(self,role,expires=''):
        r.crm_security_grant({'username':'manager','role':'disabled','manager':True},r.find_user('root'),mode='appoint')
        return r.crm_security_grant({'username':'alice','role':role,'expires_on':expires},r.find_user('manager'))
    def test_default_and_expiry(self):
        self.assertEqual(r.crm_capabilities(r.find_user('alice'))['role'],'viewer')
        self.assertFalse(r.crm_capabilities(r.find_user('alice'))['write'])
        self.grant('importer');self.assertTrue(r.crm_capabilities(r.find_user('alice'))['import'])
        self.grant('editor','2000-01-01');self.assertFalse(r.assistant_permissions(r.find_user('alice'))['crm'])
        self.grant('disabled');self.assertFalse(r.crm_capabilities(r.find_user('alice'))['read'])
    def test_permission_directory_includes_personnel_organization(self):
        person=next(user for user in r.crm_security_users(r.find_user('root'))['users'] if user['username']=='alice')
        self.assertEqual(person['employee_id'],'120001')
        self.assertEqual(person['company'],'承希科技')
        self.assertEqual(person['department'],'服务解决方案中心 / 服务交付部')
        self.assertEqual(person['position'],'交付工程师')

    def test_battle_roster_saves_three_levels_and_exact_unit_scope(self):
        roster = {
            'version': 0,
            'management': ['manager'],
            'units': [
                {'id': 'east-zhejiang-north', 'leaders': ['alice'], 'roles': {'客户经理/销售工程师': ['alice']}},
            ],
        }
        saved = r.crm_battle_roster_save(roster, r.find_user('root'))
        self.assertEqual(saved['version'], 1)
        self.assertEqual(r.crm_capabilities(r.find_user('manager'))['data_scope'], 'all')
        alice = r.crm_capabilities(r.find_user('alice'))
        self.assertEqual(alice['data_scope'], 'regions')
        self.assertEqual(alice['battle_units'], ['east-zhejiang-north'])
        self.assertEqual(r.crm_battle_roster_level('alice'), 'region')
        self.assertEqual(r.crm_battle_roster_level('manager'), 'company')

    def test_battle_roster_rejects_unknown_accounts_and_non_superadmin(self):
        payload = {'version': 0, 'management': [], 'units': [{'id': 'east-zhejiang-north', 'leaders': ['missing'], 'roles': {}}]}
        with self.assertRaises(ValueError):
            r.crm_battle_roster_save(payload, r.find_user('root'))
        payload['units'][0]['leaders'] = ['alice']
        with self.assertRaises(PermissionError):
            r.crm_battle_roster_save(payload, r.find_user('manager'))

    def test_liaison_region_override_can_be_set_to_region_non_region_and_reset(self):
        root = r.find_user('root')
        r.crm_liaison_region_save({'username':'alice','region':'广东区'}, root)
        person = next(user for user in r.crm_security_users(root)['users'] if user['username']=='alice')
        self.assertEqual(person['liaison_region_override'], '广东区')
        r.crm_liaison_region_save({'username':'alice','region':'非区域人员'}, root)
        self.assertEqual(r.crm_liaison_region_overrides()['alice'], '非区域人员')
        r.crm_liaison_region_save({'username':'alice','region':''}, root)
        self.assertNotIn('alice', r.crm_liaison_region_overrides())
        with self.assertRaises(ValueError):
            r.crm_liaison_region_save({'username':'alice','region':'华南区'}, root)
    def test_manager_can_batch_grant_selected_organization_without_touching_managers(self):
        self.grant('viewer')
        result=r.crm_security_batch_grant({'company':'承希科技','departments':['服务解决方案中心'],'role':'importer','expires_on':''},r.find_user('manager'))
        self.assertEqual(result['updated'],1)
        self.assertEqual(r.crm_capabilities(r.find_user('alice'))['role'],'importer')
        self.assertTrue(r.crm_capabilities(r.find_user('manager'))['manage'])
    def test_batch_grant_sets_data_scope_and_rejects_aggregation_scopes(self):
        self.grant('viewer')
        result = r.crm_security_batch_grant({'company':'承希科技','departments':['服务解决方案中心'],'role':'editor','data_scope':'team','expires_on':''}, r.find_user('manager'))
        self.assertEqual(result['updated'], 1)
        caps = r.crm_capabilities(r.find_user('alice'))
        self.assertEqual(caps['role'], 'editor')
        self.assertEqual(caps['data_scope'], 'team')
        with self.assertRaises(ValueError):
            r.crm_security_batch_grant({'company':'承希科技','departments':[],'role':'viewer','data_scope':'all','expires_on':''}, r.find_user('manager'))

    def test_business_manager_can_configure_a_region_manager(self):
        r.crm_security_grant({'username':'manager','role':'disabled','manager':True},r.find_user('root'),mode='appoint')
        r.crm_security_grant({'username':'alice','role':'regional_manager','data_scope':'regions','regions':['东区'],'expires_on':''},r.find_user('manager'))
        caps=r.crm_capabilities(r.find_user('alice'))
        self.assertEqual(caps['role'],'regional_manager')
        self.assertEqual(caps['data_scope'],'regions')
        self.assertEqual(caps['regions'],['东区'])
        self.assertTrue(caps['batch_assign'])
        self.assertTrue(caps['supervise'])
        self.assertFalse(caps['manage'])
        with self.assertRaises(ValueError):
            r.crm_security_grant({'username':'alice','role':'regional_manager','data_scope':'self','regions':[],'expires_on':''},r.find_user('manager'))
        with self.assertRaises(ValueError):
            r.crm_security_batch_grant({'company':'承希科技','departments':[],'role':'regional_manager','data_scope':'self','expires_on':''},r.find_user('manager'))

    def test_regional_assignment_endpoint_uses_dedicated_permission(self):
        self.assertEqual(r.crm_security_operation('/api/crm/relations/batch-assign','POST'),'batch_assign')
    def test_manager_cannot_grant_and_bad_policy_fails_closed(self):
        with self.assertRaises(PermissionError):r.crm_security_grant({'username':'alice','role':'importer'},r.find_user('manager'))
        self.grant('editor')
        r.crm_security_path('policies.json').write_text('broken')
        self.assertFalse(r.crm_capabilities(r.find_user('alice'))['read'])
    def test_http_read_write_import_and_revocation(self):
        server=r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,method='GET',body=None,token='alice'):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port)
            c.request(method,path,json.dumps(body or {}) if method=='POST' else None,{'Cookie':'pws_session='+token,'Content-Type':'application/json'})
            resp=c.getresponse();data=resp.read();code=resp.status;c.close();return code,json.loads(data)
        try:
            self.assertEqual(request('/api/crm/security/me')[0],200)
            self.assertEqual(request('/api/crm/security/users')[0],403)
            self.assertEqual(request('/api/crm/security/users',token='root')[0],200)
            self.assertEqual(request('/api/crm/security/grant','POST',{'username':'alice','role':'editor'},token='root')[0],200)
            self.assertEqual(request('/api/crm/security/appoint','POST',{'username':'manager','role':'disabled','manager':True},token='root')[0],200)
            self.assertEqual(request('/api/crm/security/appoint','POST',{'username':'alice','role':'disabled','manager':True},token='manager')[0],403)
            self.assertEqual(request('/api/crm/security/grant','POST',{'username':'alice','role':'viewer'},token='manager')[0],200)
            self.assertEqual(request('/api/crm/quick-create','POST',{})[0],403)
            self.grant('editor')
            with patch.object(r,'crm_quick_create',return_value={'ok':True}),patch.object(r,'crm_excel_import',return_value={'ok':True}):
                self.assertEqual(request('/api/crm/quick-create','POST',{'name':'SECRET_CONTENT'})[0],200)
                self.assertEqual(request('/api/crm/excel/import','POST',{})[0],403)
                self.grant('importer');self.assertEqual(request('/api/crm/excel/import','POST',{})[0],200)
                self.grant('disabled');self.assertEqual(request('/api/crm/security/me')[0],403)
            code,body=request('/api/crm/security/audit',token='manager')
            self.assertEqual(code,200);self.assertTrue(body['events'])
            self.assertNotIn('SECRET_CONTENT',r.crm_security_path('audit.jsonl').read_text())
            self.assertEqual(request('/personal-office-assistant/api/crm/people')[0],403)
        finally:server.shutdown();server.server_close();thread.join()
    def test_explicit_grant_opens_module_without_old_toggle(self):
        self.assertTrue(r.assistant_permissions(r.find_user('manager'))['crm'])
        r.crm_security_grant({'username':'alice','role':'disabled','manager':True},r.find_user('root'),mode='appoint')
        r.crm_security_grant({'username':'manager','role':'viewer'},r.find_user('alice'))
        self.assertTrue(r.assistant_permissions(r.find_user('manager'))['crm'])
        self.assertFalse(r.crm_capabilities(r.find_user('manager'))['manage'])

    def test_deleted_account_does_not_inherit_grant(self):
        self.grant('importer')
        original=r.read_config()
        with patch.object(r,'openclaw_sync_deleted_username'),patch.object(r,'_revoke_gateway_key'):
            r.delete_user({'username':'alice'},'root')
        self.assertEqual(r.crm_security_policies()['alice']['role'],'disabled')
        r.write_config(original)  # simulate a newly created account with the same name
        self.assertFalse(r.crm_capabilities(r.find_user('alice'))['read'])

    def test_delegation_boundaries_and_revocation(self):
        root=r.find_user('root'); manager=r.find_user('manager')
        r.crm_security_grant({'username':'alice','role':'editor'},root)
        self.assertEqual(r.crm_capabilities(r.find_user('alice'))['role'],'editor')
        with self.assertRaises(PermissionError):
            r.crm_security_grant({'username':'alice','role':'disabled','manager':True},manager,mode='appoint')
        self.grant('editor')
        self.assertTrue(r.crm_capabilities(manager)['manage'])
        with self.assertRaises(PermissionError):
            r.crm_security_grant({'username':'manager','role':'disabled'},manager)
        r.crm_security_grant({'username':'manager','role':'disabled','manager':False},root,mode='appoint')
        self.assertFalse(r.crm_capabilities(manager)['manage'])
        with self.assertRaises(PermissionError):
            r.crm_security_grant({'username':'alice','role':'viewer'},manager)
        self.assertEqual(r.crm_capabilities(r.find_user('alice'))['role'],'editor')

    def test_region_leader_reads_only_authorized_region_while_admin_reads_all(self):
        config = r.read_config()
        config['users'].extend([
            {'username':'bob','role':'member','assistant_permissions':{'crm':True}},
            {'username':'leader','role':'member','assistant_permissions':{'crm':True}},
        ])
        r.write_config(config)
        r.crm_store('alice', 'units', {'east': {'id':'east','name':'跨区客户','business_region':'中区','business_regions':['中区','东区']}})
        r.crm_store('bob', 'units', {'west': {'id':'west','name':'西区客户','business_region':'西区'}})
        r.crm_security_grant({'username':'leader','role':'viewer','expires_on':'','regions':['东区']}, r.find_user('root'))
        leader_units = r.crm_read_units(r.find_user('leader'))['units']
        admin_units = r.crm_read_units(r.find_user('manager'))['units']
        self.assertEqual([item['name'] for item in leader_units], ['跨区客户'])
        self.assertEqual({item['name'] for item in admin_units}, {'跨区客户', '西区客户'})

    def test_org_scope_includes_selected_department_descendants(self):
        config = r.read_config()
        config['users'].extend([
            {'username':'bob','role':'member','assistant_permissions':{'crm':True},'company':'承希科技','department':'销售中心 / 华东组'},
            {'username':'leader','role':'member','assistant_permissions':{'crm':True},'company':'承希科技','department':'销售中心'},
        ])
        r.write_config(config)
        r.crm_store('bob', 'units', {'east': {'id':'east','name':'华东客户','business_region':'东区'}})
        r.crm_security_grant({'username':'leader','role':'viewer','expires_on':'','data_scope':'team'}, r.find_user('root'))
        self.assertEqual([item['name'] for item in r.crm_read_units(r.find_user('leader'))['units']], ['华东客户'])

    def test_audit_visibility_is_private_except_for_administrators(self):
        config = r.read_config()
        config['users'].append({'username':'bob','role':'member','assistant_permissions':{'crm':True}})
        config['users'].append({'username':'leader','role':'member','assistant_permissions':{'crm':True}})
        r.write_config(config)
        r.crm_store('bob','units',{'e':{'id':'e','name':'东区客户','business_region':'东区'}})
        r.crm_audit('alice','write','/api/crm/quick-create',200)
        r.crm_audit('bob','write','/api/crm/quick-create',200)
        r.crm_audit('leader','read','/api/crm/people',200)
        # Every CRM user sees the audit path, but ordinary users only see their own traces.
        self.assertEqual(r.crm_security_operation('/api/crm/security/audit','GET'),'read')
        alice = r.crm_security_audit(r.find_user('alice'))
        self.assertEqual(alice['scope'],'limited')
        self.assertEqual({e['actor'] for e in alice['events']},{'alice'})
        r.crm_security_grant({'username':'leader','role':'viewer','expires_on':'','regions':['东区']}, r.find_user('root'))
        leader_actors = {e['actor'] for e in r.crm_security_audit(r.find_user('leader'))['events']}
        self.assertEqual(leader_actors, {'leader'})
        manager = r.crm_security_audit(r.find_user('manager'))
        self.assertEqual(manager['scope'],'all')
        self.assertTrue({'alice','bob','leader'} <= {e['actor'] for e in manager['events']})

    def test_assignee_can_complete_a_routed_import_task_without_broad_write_access(self):
        self.grant('viewer')
        caps = r.crm_capabilities(r.find_user('alice'))
        self.assertFalse(caps['write'])
        self.assertTrue(caps['complete_import_task'])
        self.assertEqual(r.crm_security_operation('/api/crm/import-completion/complete', 'POST'), 'complete_import_task')

    def test_owner_changes_keep_the_previous_record_version(self):
        r.crm_store('alice', 'units', {'u1': {'id':'u1','name':'旧客户'}})
        r.crm_store('alice', 'units', {'u1': {'id':'u1','name':'新客户'}})
        history = r.crm_record_versions('alice', 'units', 'u1')
        self.assertEqual(history[0]['record']['name'], '旧客户')
