"""Run in the app container with all CRM writers stopped; import, verify, then enable."""
import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import runtime as runtime


def migrate():
    config = runtime.crmdb_config()
    if not config or not config.get('enabled'):
        raise RuntimeError('CRM database backend must already be enabled')
    if config.get('configuration_enabled'):
        raise RuntimeError('Configuration already live; refusing to reimport frozen files')
    values = {}
    for key, relative in runtime.CRM_CONFIG_PATHS.items():
        path = runtime.USER_DATA_DIR / relative
        if path.exists():
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                raise ValueError('Invalid configuration: ' + key)
            values[key] = value
    path = runtime.USER_DATA_DIR / '.crm-security/audit.jsonl'
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
    if any(not isinstance(event, dict) for event in events):
        raise ValueError('Invalid audit event')
    backup = runtime.USER_DATA_DIR / '_datacenter' / 'crm-configuration-backups' / datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    for relative in [*runtime.CRM_CONFIG_PATHS.values(), '.crm-security/audit.jsonl', '_datacenter/crm_db.json']:
        source = runtime.USER_DATA_DIR / relative
        if source.exists():
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(source, destination)
            destination.chmod(0o600)
    with runtime._crmdb_conn() as connection:
        connection.run('BEGIN')
        try:
            for key, value in values.items():
                connection.run('INSERT INTO crm.configuration (key,payload) VALUES (:key,:value::jsonb) ON CONFLICT DO NOTHING',
                               key=key, value=json.dumps(value, ensure_ascii=False))
            connection.run('INSERT INTO crm.security_events (source_line,payload) '
                           'SELECT ordinal,entry FROM jsonb_array_elements(:events::jsonb) WITH ORDINALITY AS source(entry,ordinal) '
                           'ON CONFLICT (source_line) DO NOTHING', events=json.dumps(events, ensure_ascii=False))
            stored = dict(connection.run('SELECT key,payload FROM crm.configuration'))
            audit = [row[0] for row in connection.run('SELECT payload FROM crm.security_events ORDER BY source_line')]
            if stored != values or audit != events:
                raise ValueError('Migration verification failed; live switch remains off')
            connection.run('COMMIT')
        except Exception:
            connection.run('ROLLBACK')
            raise
    target = runtime._crmdb_config_path()
    ownership = target.stat()
    config['configuration_enabled'] = True
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.chmod(0o600)
    os.chown(temporary, ownership.st_uid, ownership.st_gid)
    temporary.replace(target)
    print(json.dumps({'ok': True, 'configuration_records': len(values), 'audit_events': len(events), 'verified': 'full payload equality'}, ensure_ascii=False))


if __name__ == '__main__':
    migrate()
