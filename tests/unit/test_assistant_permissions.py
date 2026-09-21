import copy
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r


class AssistantPermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp.name) / 'config.json'
        self.config_path.write_text(json.dumps({'users': [
            {'username': 'root', 'role': 'superadmin'},
            {'username': 'manager', 'role': 'admin'},
            {'username': 'member', 'role': 'member'},
        ]}))
        self.patches = [patch.object(r, 'CONFIG_PATH', self.config_path),
                        patch.object(r, 'USER_DATA_DIR', Path(self.temp.name) / 'data'),
                        patch.object(r, 'openclaw_sync_user'),
                        patch.object(r, 'SESSIONS', {'root': 'root', 'manager': 'manager', 'member': 'member'})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_existing_and_new_account_defaults(self):
        for role in ('member', 'admin'):
            permissions = r.assistant_permissions({'role': role})
            self.assertEqual({k for k, v in permissions.items() if not v}, {'crm', 'ledger', 'cashflow'})
        self.assertTrue(all(r.assistant_permissions({'role': 'superadmin', 'assistant_permissions': {'crm': False}}).values()))

    def test_grant_revoke_persist_and_reset(self):
        r.update_user({'username': 'member', 'assistant_permissions': {'crm': True, 'weekly': False}}, 'root')
        user = r.public_user(r.find_user('member'))
        self.assertTrue(user['assistant_permissions']['crm'])
        self.assertFalse(user['assistant_permissions']['weekly'])
        r.require_assistant_access('member', 'crm')
        r.update_user({'username': 'member', 'assistant_permissions': {}}, 'root')
        with self.assertRaises(PermissionError):
            r.require_assistant_access('member', 'crm')

    def test_only_superadmin_can_manage(self):
        original = self.config_path.read_text()
        for caller in ('member', 'manager', 'unknown'):
            for action in (r.update_user, r.add_user, r.delete_user):
                with self.assertRaises(PermissionError):
                    action({'username': 'member', 'assistant_permissions': {'crm': True}}, caller)
        self.assertEqual(self.config_path.read_text(), original)

    def test_reject_invalid_and_last_superadmin_demotion(self):
        for value in ({'crm': 'true'}, {'fake': True}, ['crm'], None):
            with self.assertRaises(ValueError):
                r.update_user({'username': 'member', 'assistant_permissions': value}, 'root')
        with self.assertRaises(ValueError):
            r.update_user({'username': 'root', 'role': 'member'}, 'root')

    def test_skill_cannot_bypass(self):
        with patch.object(r, '_LEGACY_EXECUTE_SKILL') as execute:
            with self.assertRaises(PermissionError):
                r.execute_skill_raw('crm.overview', {}, 'member')
            execute.assert_not_called()

    def test_http_protection_and_immediate_revocation(self):
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path, token='member', method='GET', payload=None):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            body = json.dumps(payload) if payload is not None else None
            conn.request(method, path, body, {'Cookie': 'pws_session=' + token, 'Content-Type': 'application/json'})
            response = conn.getresponse()
            status = response.status
            response.read()
            conn.close()
            return status
        try:
            for prefix in ('', r.APP_RELATIVE_PATH):
                for path in ('/api/crm/overview', '/api/crm/playbook', '/api/crm/excel/template', '/api/ledger', '/api/contracts'):
                    self.assertEqual(request(prefix + path), 403)
                self.assertEqual(request(prefix + '/api/crm/person/save', method='POST', payload={}), 403)
                self.assertEqual(request(prefix + '/api/crm/excel/import', method='POST', payload={}), 403)
                self.assertEqual(request(prefix + '/api/crm/quick-create', method='POST', payload={}), 403)
            self.assertEqual(request('/api/crm/overview', token='missing'), 401)
            self.assertEqual(request('/api/admin-users-update', token='manager', method='POST', payload={'username': 'member'}), 403)
            with patch.object(r, 'crm_overview', return_value={'ok': True}):
                self.assertEqual(request('/api/crm/overview', token='root'), 200)
                self.assertEqual(request('/api/admin-users-update', token='root', method='POST', payload={'username': 'member', 'assistant_permissions': {'crm': True}}), 200)
                self.assertEqual(request('/api/crm/overview'), 200)
                r.update_user({'username': 'member', 'assistant_permissions': {'crm': False}}, 'root')
                self.assertEqual(request('/api/crm/overview'), 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
