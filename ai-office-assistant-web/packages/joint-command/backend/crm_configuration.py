"""CRM configuration and security audit storage with an explicit cutover gate."""

CRM_CONFIG_PATHS = {
    'policies': '.crm-security/policies.json',
    'liaison_regions': '.crm-security/liaison-regions.json',
    'battle_roster': '.crm-security/battle-roster.json',
    'regions': '.crm-region-settings.json',
    'quality': '.crm-quality-settings.json',
    'amap': '.crm-amap-settings.json',
}


def crm_configuration_in_db():
    return crmdb_enabled() and (crmdb_config() or {}).get('configuration_enabled') is True


def crm_configuration_load(name, default=None):
    if name not in CRM_CONFIG_PATHS:
        raise ValueError('未知CRM配置')
    if crm_configuration_in_db():
        with _crmdb_conn() as connection:
            rows = connection.run('SELECT payload FROM crm.configuration WHERE key=:key', key=name)
        value = rows[0][0] if rows else default
    else:
        path = USER_DATA_DIR / CRM_CONFIG_PATHS[name]
        value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    if value is not None and not isinstance(value, dict):
        raise ValueError('CRM配置格式异常，请联系管理员')
    return value


def crm_configuration_save(name, value, expected=None):
    if name not in CRM_CONFIG_PATHS or not isinstance(value, dict):
        raise ValueError('CRM配置格式异常')
    if crm_configuration_in_db():
        with _crmdb_conn() as connection:
            rows = connection.run('INSERT INTO crm.configuration (key,payload) VALUES (:key,:payload::jsonb) '
                                  'ON CONFLICT (key) DO UPDATE SET payload=EXCLUDED.payload, updated_at=now() '
                                  'WHERE (:check_expected::boolean = false OR crm.configuration.payload=:expected::jsonb) AND ('
                                  "NOT (EXCLUDED.payload ? 'version') OR "
                                  "coalesce((crm.configuration.payload->>'version')::bigint,0) = (EXCLUDED.payload->>'version')::bigint-1) "
                                  'RETURNING key', key=name, payload=json.dumps(value, ensure_ascii=False),
                                  check_expected=expected is not None, expected=json.dumps(expected))
            if not rows:
                raise ValueError('配置已被其他人更新，请重新加载后编辑')
        return
    path = USER_DATA_DIR / CRM_CONFIG_PATHS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def crm_configuration_amap_storage():
    if not crm_configuration_in_db():
        return None
    return {'load': lambda: crm_configuration_load('amap', {}),
            'save': lambda value: crm_configuration_save('amap', value)}


def crmdb_audit_append(event):
    with _crmdb_conn() as connection:
        connection.run('INSERT INTO crm.security_events (payload) VALUES (:payload::jsonb)',
                       payload=json.dumps(event, ensure_ascii=False))


def crmdb_audit_recent(scope):
    with _crmdb_conn() as connection:
        rows = connection.run('WITH recent AS (SELECT seq,actor,payload FROM crm.security_events '
                              'ORDER BY seq DESC LIMIT 5000) SELECT payload FROM recent '
                              'WHERE :all_events::boolean OR actor IN (SELECT jsonb_array_elements_text(:actors::jsonb)) '
                              'ORDER BY seq DESC LIMIT 200', all_events=scope is None,
                              actors=json.dumps(sorted(scope or [])))
    return [row[0] for row in rows]


def crm_configuration_export(directory):
    directory = Path(directory)
    with _crmdb_conn() as connection:
        configurations = connection.run('SELECT key,payload FROM crm.configuration')
        events = connection.run('SELECT payload FROM crm.security_events ORDER BY seq')
    for key, value in configurations:
        destination = directory / CRM_CONFIG_PATHS[key]
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    destination = directory / '.crm-security/audit.jsonl'
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        for event, in events:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    return len(configurations) + 1
