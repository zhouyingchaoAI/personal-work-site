"""Gaode credentials and a fixed-host security proxy; never expose securityJsCode."""
import json
import os
import re
import urllib.parse
import urllib.request


def load_settings(directory):
    path = directory / '.crm-amap-settings.json'
    return json.loads(path.read_text()) if path.exists() else {}


def public_settings(directory):
    value = load_settings(directory)
    return {'ok': True, 'key': value.get('key', ''), 'enabled': value.get('enabled', False),
            'has_security_code': bool(value.get('security_code')), 'version': value.get('version', 0)}


def save_settings(directory, payload):
    previous = load_settings(directory)
    if type(payload.get('version')) is not int or payload['version'] != previous.get('version', 0):
        raise ValueError('高德配置已更新，请重新打开设置')
    key = str(payload.get('key', '')).strip()
    secret = str(payload.get('security_code', '')).strip() or previous.get('security_code', '')
    if any(value and not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', value) for value in (key, secret)):
        raise ValueError('高德 Key 或安全密钥格式不正确')
    enabled = payload.get('enabled') is True
    if enabled and not (key and secret):
        raise ValueError('启用高德需要 Web 端 JS API Key 和安全密钥')
    value = {'key': key, 'security_code': secret, 'enabled': enabled, 'version': previous.get('version', 0) + 1}
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / '.crm-amap-settings.json'
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(temporary, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
    temporary.replace(path)
    return public_settings(directory)


def proxy_url(directory, path, query):
    # Reject encoded paths, traversal, arbitrary hosts and unneeded service versions.
    if not re.fullmatch(r'/v[345]/[A-Za-z0-9_/-]+', path) or '//' in path:
        raise ValueError('不支持的地图服务路径')
    settings = load_settings(directory)
    if not settings.get('enabled') or not settings.get('key') or not settings.get('security_code'):
        raise ValueError('高德地图尚未配置')
    pairs = [(k, v) for k, v in urllib.parse.parse_qsl(query, keep_blank_values=True)
             if k.lower() not in ('key', 'jscode')]
    pairs.extend([('key', settings['key']), ('jscode', settings['security_code'])])
    host = 'webapi.amap.com' if path == '/v4/map/styles' else 'restapi.amap.com'
    return 'https://' + host + path + '?' + urllib.parse.urlencode(pairs)


def fetch_proxy(directory, path, query):
    # No redirects: credentials cannot be forwarded to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with urllib.request.build_opener(NoRedirect).open(proxy_url(directory, path, query), timeout=15) as response:
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise ValueError('地图响应过大')
        return body, response.headers.get('Content-Type', 'application/json')
