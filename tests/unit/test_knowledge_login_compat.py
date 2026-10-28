import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

from backend import runtime as rt


class KnowledgeLoginCompatibilityTests(unittest.TestCase):
    def test_management_endpoints_retry_new_routes(self):
        cases = [
            ('/v1/user/register', '/api/v1/users', 'POST'),
            ('/v1/system/new_token', '/api/v1/system/tokens', 'POST'),
            ('/v1/system/token_list', '/api/v1/system/tokens', 'GET'),
            ('/v1/user/tenant_info', '/api/v1/users/me/models', 'GET'),
            ('/v1/user/set_tenant_info', '/api/v1/users/me/models', 'PATCH'),
            ('/v1/tenant/team/user', '/api/v1/tenants/team/users', 'POST'),
            ('/v1/tenant/agree/team', '/api/v1/tenants/team', 'PATCH'),
        ]
        for legacy, target, method in cases:
            with self.subTest(legacy=legacy):
                response = io.BytesIO(b'{"code":0}')
                response.headers = {}
                opener = Mock()
                opener.open.side_effect = [urllib.error.HTTPError('http://test'+legacy, 404, '', {}, None), response]
                with patch.object(rt.urllib.request, 'build_opener', return_value=opener):
                    rt._ragflow_web_request({'ragflow_url': 'http://test'}, legacy, {'example': True}, auth='test-token')
                request = opener.open.call_args_list[1].args[0]
                self.assertEqual(request.full_url, 'http://test'+target)
                self.assertEqual(request.get_method(), method)
                self.assertEqual(request.get_header('Authorization'), 'test-token')
                self.assertEqual(json.loads(request.data), {'example': True})

    def test_failed_provisioning_keeps_password_for_retry(self):
        accounts = {}
        with patch.object(rt, '_kb_mapping', return_value=accounts), patch.object(rt, '_kb_mapping_save') as save, patch.object(rt, '_ragflow_encrypt_password', side_effect=lambda value: value), patch.object(rt, '_ragflow_web_request', side_effect=RuntimeError('temporary outage')):
            with self.assertRaises(RuntimeError):
                rt._ragflow_user_account({}, 'test-user')
            password = accounts['test-user']['password']
            with self.assertRaises(RuntimeError):
                rt._ragflow_user_account({}, 'test-user')
            self.assertEqual(accounts['test-user']['password'], password)
            self.assertEqual(save.call_count, 2)

    def test_removed_legacy_login_retries_new_endpoint(self):
        response = io.BytesIO(json.dumps({'code': 0}).encode())
        response.headers = {'Authorization': 'test-token'}
        opener = Mock()
        opener.open.side_effect = [urllib.error.HTTPError('http://test/v1/user/login', 404, '', {}, None), response]
        with patch.object(rt.urllib.request, 'build_opener', return_value=opener):
            data, headers = rt._ragflow_web_request({'ragflow_url': 'http://test'}, '/v1/user/login', {'email': 'test', 'password': 'encrypted'})
        self.assertEqual(data['code'], 0)
        self.assertEqual(headers['Authorization'], 'test-token')
        request = opener.open.call_args_list[1].args[0]
        self.assertEqual(request.full_url, 'http://test/api/v1/auth/login')
        self.assertEqual(request.get_method(), 'POST')

    def test_invalid_credentials_do_not_retry_another_route(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError('http://test/v1/user/login', 401, '', {}, None)
        with patch.object(rt.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(urllib.error.HTTPError):
                rt._ragflow_web_request({'ragflow_url': 'http://test'}, '/v1/user/login', {})
        self.assertEqual(opener.open.call_count, 1)
