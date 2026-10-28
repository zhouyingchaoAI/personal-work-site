"""Restore every archived file from a disposable restored DB and verify bytes.
Set OFFICE_PG_DB=dc_archive_restore_*; run inside datacenter-backup.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.datacenter_db import db_connect
from backend.datacenter_archive import restore_project
assert os.getenv('OFFICE_PG_DB','').startswith('dc_archive_restore_'), 'Use an isolated restore database'
conn=db_connect()
try:
    with tempfile.TemporaryDirectory(prefix='datacenter-restore-',dir='/backup') as tmp:
        result=restore_project(conn,Path(tmp)/'restored')
        project=Path(tmp)/'restored/project'
        config=json.loads((project/'config.json').read_text())
        result['accounts_restored']=len(config.get('users',[]))
        result['environment_file_restored']=(project/'.env').is_file()
        with sqlite3.connect((project/'user_data/app.db').as_uri()+'?mode=ro',uri=True) as sq:
            result['sqlite_integrity']=sq.execute('PRAGMA integrity_check').fetchone()[0]
        assert result['sqlite_integrity']=='ok'
        print(json.dumps(result,ensure_ascii=False))
finally:
    conn.close()
