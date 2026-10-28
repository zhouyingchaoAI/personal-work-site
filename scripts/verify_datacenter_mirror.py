"""Run inside datacenter-backup; read-only checks plus connection-local TEMP table tests.

Usage: docker exec -w /app datacenter-backup python3 scripts/verify_datacenter_mirror.py
Never prints source payloads or credentials.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.datacenter_db import db_connect, _replace


def main():
    root = Path('/app/user_data')
    status = json.loads((root / '_datacenter/db_sync.json').read_text())['last']
    assert status['ok'], 'Latest sync failed'
    conn = db_connect()
    try:
        for table in status['tables']:
            count = conn.run(f"SELECT count(*) FROM {table['table']}")[0][0]
            assert count == table['rows'] == table['source'], table['table']
        corrupt = conn.run("SELECT count(*) FROM raw.documents WHERE sha256 <> encode(sha256(content), 'hex')")[0][0]
        assert corrupt == 0, 'Stored document checksum mismatch'
        source_changes = []
        cache_changes = 0
        levels = dict(conn.run("SELECT path, level FROM files.catalog"))
        verified = 0
        for path, digest in conn.run('SELECT path, sha256 FROM raw.documents'):
            if path.startswith('_datacenter/'):
                continue  # status/logs continue changing after the snapshot
            source = Path('/app/config.json') if path == '@config/config.json' else root / path
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                if levels.get(path) == "D":
                    cache_changes += 1
                else:
                    source_changes.append(path)
            else:
                verified += 1
        assert not source_changes, f'{len(source_changes)} documents changed since sync; resync before acceptance'
        missing = conn.run('SELECT count(*) FROM files.catalog WHERE sha256 IS NULL OR length(sha256) <> 64')[0][0]
        assert missing == 0, 'Incomplete file checksums'
        # Verify rollback against real PostgreSQL without touching any mirror table.
        conn.run('CREATE TEMP TABLE dc_verify_atomic (id text PRIMARY KEY, payload jsonb)')
        _replace(conn, 'dc_verify_atomic', ['id', 'payload'], [['original', '{"v":1}']], {'payload': '::jsonb'})
        failed = False
        try:
            _replace(conn, 'dc_verify_atomic', ['id', 'payload'], [['dup', '{}'], ['dup', '{}']], {'payload': '::jsonb'})
        except Exception:
            failed = True
        assert failed, 'Duplicate keys must fail'
        assert conn.run('SELECT id FROM dc_verify_atomic') == [['original']], 'Failed import lost last good data'
        for _ in range(2):
            _replace(conn, 'dc_verify_atomic', ['id', 'payload'], [['evt_text_id', '{}']], {'payload': '::jsonb'})
        assert conn.run('SELECT id FROM dc_verify_atomic') == [['evt_text_id']], 'Text IDs/idempotency failed'
        print(json.dumps({'tables_verified': len(status['tables']), 'rows': status['rows_total'],
                          'source_documents_verified': verified, 'cache_changes_since_snapshot': cache_changes,
                          'document_checksums': 'pass',
                          'rollback_and_idempotency': 'pass',
                          'document_parse_errors': status.get('document_parse_errors', 0)}, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
