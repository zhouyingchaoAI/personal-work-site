import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from backend import crm_amap
import backend.runtime as r


class AmapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = dict(key='k' * 32, security_code='s' * 32, enabled=True, version=0)

    def test_secret_never_returned_and_file_private(self):
        result = crm_amap.save_settings(self.root, self.payload)
        self.assertNotIn('security_code', result)
        self.assertNotIn('s' * 32, str(result))
        self.assertTrue(result['has_security_code'])
        self.assertEqual((self.root / '.crm-amap-settings.json').stat().st_mode & 0o777, 0o600)
        crm_amap.save_settings(self.root, dict(self.payload, version=1, security_code=''))
        self.assertEqual(crm_amap.load_settings(self.root)['security_code'], 's' * 32)

    def test_validation_and_conflict(self):
        with self.assertRaises(ValueError):
            crm_amap.save_settings(self.root, dict(self.payload, security_code=''))
        with self.assertRaises(ValueError):
            crm_amap.save_settings(self.root, dict(self.payload, key='https://attacker/'))
        crm_amap.save_settings(self.root, self.payload)
        with self.assertRaises(ValueError):
            crm_amap.save_settings(self.root, self.payload)

    def test_proxy_fixed_hosts_and_server_credentials(self):
        crm_amap.save_settings(self.root, self.payload)
        url = urlsplit(crm_amap.proxy_url(self.root, '/v3/config/district', 'keywords=湖南&key=evil&jscode=evil'))
        self.assertEqual(url.netloc, 'restapi.amap.com')
        self.assertEqual(parse_qs(url.query)['jscode'], ['s' * 32])
        self.assertEqual(parse_qs(url.query)['key'], ['k' * 32])
        self.assertEqual(urlsplit(crm_amap.proxy_url(self.root, '/v4/map/styles', '')).netloc, 'webapi.amap.com')
        for path in ['/v3/../secret', '//evil.com', '/v3/%2e%2e', '/v3/a?host=evil']:
            with self.assertRaises(ValueError): crm_amap.proxy_url(self.root, path, '')

    def test_permissions_and_disabled_proxy(self):
        with patch.object(r, 'USER_DATA_DIR', self.root), patch.object(r, 'crm_capabilities', return_value={'read': True}):
            with self.assertRaises(PermissionError): r.crm_amap_settings_save(self.payload, {'username': 'member'})
        self.assertEqual(r.crm_security_operation('/api/crm/security/amap-settings', 'GET'), 'read')
        self.assertEqual(r.crm_security_operation('/api/crm/security/amap-settings', 'POST'), 'manage')
        with self.assertRaises(ValueError): crm_amap.proxy_url(self.root, '/v3/config/district', '')
