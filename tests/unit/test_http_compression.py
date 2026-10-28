"""JSON and static asset responses are gzipped for clients that accept it."""
import gzip
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import backend.runtime as r


class QuietHandler(r.Handler):
    def log_message(self, *args):
        pass


def fetch(base, path, gzip_ok=True):
    req = urllib.request.Request(base + path, headers={'Cookie': 'pws_session=test', **({'Accept-Encoding': 'gzip'} if gzip_ok else {})})
    with urllib.request.urlopen(req) as resp:
        return resp.status, dict(resp.headers), resp.read()


class HttpCompressionTests(unittest.TestCase):
    def test_json_and_assets_are_gzipped_only_when_accepted(self):
        users = [{'username': 'root', 'name': '管理员', 'role': 'superadmin'}]
        with tempfile.TemporaryDirectory(prefix='pws-gzip-') as tmp:
            frontend = Path(tmp) / 'dist'
            (frontend / 'assets').mkdir(parents=True)
            (frontend / 'index.html').write_text('<html></html>', encoding='utf-8')
            big_js = ('console.log("x");\n' * 400).encode()
            (frontend / 'assets' / 'index-ABCD1234.js').write_bytes(big_js)
            (frontend / 'assets' / 'logo-ABCD1234.png').write_bytes(b'\x89PNG' + b'\0' * 4000)
            with patch.object(r, 'USER_DATA_DIR', Path(tmp) / 'users'), patch.object(r, 'FRONTEND_DIR', frontend), \
                 patch.object(r, 'read_config', return_value={'users': users}), patch.object(r, 'SESSIONS', {'test': 'root'}), \
                 patch.object(r, 'crm_on_change'), patch.object(r, 'crm_audit'):
                for i in range(40):
                    r.crm_unit_save({'name': f'客户单位{i}', 'type': '业主单位', 'organization_level': 'company'}, 'root')
                server = r.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    status, headers, body = fetch(base, '/api/crm/units')
                    self.assertEqual(status, 200)
                    self.assertEqual(headers.get('Content-Encoding'), 'gzip')
                    self.assertEqual(headers.get('Vary'), 'Accept-Encoding')
                    payload = json.loads(gzip.decompress(body))
                    self.assertEqual(len(payload['units']), 40)
                    self.assertLess(len(body), len(json.dumps(payload, ensure_ascii=False).encode()) // 3)

                    status, headers, body = fetch(base, '/api/crm/units', gzip_ok=False)
                    self.assertIsNone(headers.get('Content-Encoding'))
                    self.assertEqual(len(json.loads(body)['units']), 40)

                    # Tiny responses stay uncompressed: the gzip header would outweigh the body.
                    status, headers, body = fetch(base, '/api/crm/security/me')
                    self.assertIsNone(headers.get('Content-Encoding'))
                    self.assertTrue(json.loads(body)['ok'])

                    status, headers, body = fetch(base, '/assets/index-ABCD1234.js')
                    self.assertEqual(headers.get('Content-Encoding'), 'gzip')
                    self.assertEqual(gzip.decompress(body), big_js)
                    self.assertIn('immutable', headers.get('Cache-Control', ''))
                    # Second hit is served from the compressed cache with identical bytes.
                    self.assertEqual(fetch(base, '/assets/index-ABCD1234.js')[2], body)

                    status, headers, body = fetch(base, '/assets/logo-ABCD1234.png')
                    self.assertIsNone(headers.get('Content-Encoding'))
                    self.assertEqual(len(body), 4004)
                finally:
                    server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()
