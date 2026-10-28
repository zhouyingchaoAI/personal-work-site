import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import runtime as rt


class LoginSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user = {'username': 'session-test', 'password': 'salted-password-hash', 'role': 'member'}
        self.patches = [patch.object(rt, 'USER_DATA_DIR', Path(self.tmp.name)),
                        patch.object(rt, 'SESSIONS', {}),
                        patch.object(rt, 'find_user', lambda username: self.user if username == self.user['username'] else None)]
        for change in self.patches:
            change.start()

    def tearDown(self):
        for change in reversed(self.patches):
            change.stop()
        self.tmp.cleanup()

    def test_session_survives_memory_reset_without_storing_raw_token(self):
        token = rt.create_login_session(self.user)
        rt.SESSIONS.clear()
        self.assertEqual(rt.login_session_user(token)['username'], self.user['username'])
        path = Path(self.tmp.name) / '.auth/sessions.sqlite3'
        self.assertNotIn(token.encode(), path.read_bytes())
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_logout_revokes_persistent_session(self):
        token = rt.create_login_session(self.user)
        rt.delete_login_session(token)
        self.assertIsNone(rt.login_session_user(token))

    def test_session_is_valid_in_new_python_process(self):
        token = rt.create_login_session(self.user)
        program = """import json, sys
from pathlib import Path
from backend import runtime as rt
data = json.load(sys.stdin)
rt.USER_DATA_DIR = Path(data['root'])
rt.find_user = lambda username: data['user'] if username == data['user']['username'] else None
assert not rt.SESSIONS
assert rt.login_session_user(data['token'])['username'] == data['user']['username']
"""
        process = subprocess.run([sys.executable, '-c', program], input=json.dumps({'root': self.tmp.name, 'token': token, 'user': self.user}), text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_password_change_invalidates_persistent_session(self):
        token = rt.create_login_session(self.user)
        self.user['password'] = 'new-password-hash'
        self.assertIsNone(rt.login_session_user(token))

    def test_expired_and_unknown_sessions_rejected(self):
        token = rt.create_login_session(self.user)
        with patch.object(rt.time, 'time', return_value=rt.time.time() + rt.LOGIN_SESSION_TTL + 1):
            self.assertIsNone(rt.login_session_user(token))
        self.assertIsNone(rt.login_session_user('unknown-token'))
        self.assertIsNone(rt.login_session_user(''))


if __name__ == '__main__':
    unittest.main()
