"""Restart-safe login sessions; only token digests are stored on disk."""
import sqlite3 as _login_sqlite
from contextlib import contextmanager as _login_contextmanager

LOGIN_SESSION_TTL = 7 * 24 * 60 * 60


@_login_contextmanager
def _login_session_db():
    directory = Path(USER_DATA_DIR) / '.auth'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'sessions.sqlite3'
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    connection = _login_sqlite.connect(str(path), timeout=10)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS login_sessions (digest TEXT PRIMARY KEY, username TEXT NOT NULL, credential TEXT NOT NULL, expires REAL NOT NULL)')
        with connection:
            yield connection
    finally:
        connection.close()


def _login_digest(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


def create_login_session(user):
    user = find_user(user['username'])
    if not user:
        raise ValueError('用户不存在，无法创建登录会话')
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _login_session_db() as connection:
        connection.execute('DELETE FROM login_sessions WHERE expires <= ?', (now,))
        connection.execute('INSERT INTO login_sessions VALUES (?, ?, ?, ?)',
                           (_login_digest(token), user['username'], _login_digest(user.get('password', '')), now + LOGIN_SESSION_TTL))
    return token


def login_session_user(token):
    if not token or len(token) > 128:
        return None
    username = SESSIONS.get(token)
    if username:
        return find_user(username)
    with _login_session_db() as connection:
        row = connection.execute('SELECT username, credential, expires FROM login_sessions WHERE digest = ?',
                                 (_login_digest(token),)).fetchone()
    if not row:
        return None
    user = find_user(row[0])
    if row[2] <= time.time() or not user or not hmac.compare_digest(row[1], _login_digest(user.get('password', ''))):
        delete_login_session(token)
        return None
    return user


def delete_login_session(token):
    SESSIONS.pop(token, None)
    if token:
        with _login_session_db() as connection:
            connection.execute('DELETE FROM login_sessions WHERE digest = ?', (_login_digest(token),))
