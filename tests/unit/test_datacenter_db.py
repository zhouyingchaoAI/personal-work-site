"""Mirror regressions, using temporary sources only."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import datacenter_db as db


class MirrorTests(unittest.TestCase):
    def test_file_catalog_has_content_checksum_and_skips_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.pdf").write_bytes(b"original-file")
            (root / "link.pdf").symlink_to("/etc/passwd")
            rows = db.build_files_catalog(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][-1], hashlib.sha256(b"original-file").hexdigest())

    def test_keyed_records_keep_natural_key(self):
        rows = db.rows_from_keyed_json({'stable-id': {'name': 'x'}})
        self.assertEqual(rows[0][0], 'stable-id')

    def test_invalid_source_is_not_silently_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'data.json'
            p.write_text('{broken')
            with self.assertRaises(ValueError):
                db.read_source_json(p, {})
            self.assertEqual(db.read_source_json(p.with_name('missing.json'), []), [])

    def test_documents_preserve_unknown_modules_and_invalid_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'alice').mkdir()
            (root / 'alice' / 'diary.json').write_text('{"entry":"hello"}')
            (root / 'alice' / 'broken.json').write_bytes(b'{bad\xff')
            (root / 'alice' / 'audit.jsonl').write_text('{"id":1}\n{bad\n')
            (root / 'outside.json').symlink_to('/etc/passwd')
            self.assertTrue(hasattr(db, 'build_document_rows'), 'Complete document mirror is missing')
            rows = {r[0]: r for r in db.build_document_rows(root)}
            self.assertEqual(len(rows), 3)
            for path, row in rows.items():
                original = (root / path).read_bytes()
                self.assertEqual(row[1], original)
                self.assertEqual(row[2], hashlib.sha256(original).hexdigest())
            self.assertEqual(json.loads(rows['alice/diary.json'][3]), {'entry': 'hello'})
            self.assertTrue(rows['alice/broken.json'][4])

    def test_sqlite_mirror_includes_workflows_and_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'app.db'
            with sqlite3.connect(p) as conn:
                conn.execute('create table workflow_instances (id text, body blob)')
                conn.execute('insert into workflow_instances values (?, ?)', ('wf-1', b'\x00\xff'))
            self.assertTrue(hasattr(db, 'build_sqlite_rows'), 'Complete SQLite mirror is missing')
            schema, rows = db.build_sqlite_rows(p)
            self.assertIn('workflow_instances', [s[0] for s in schema])
            payload = json.loads(rows[0][2])
            self.assertEqual(payload['id'], 'wf-1')
            self.assertEqual(payload['body'], {'__bytes_hex__': '00ff'})

    def test_connection_failure_records_failed_status_without_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(db, 'db_connect', side_effect=RuntimeError('password=secret-value')):
                with self.assertRaises(RuntimeError):
                    db.sync_all(tmp, Path(tmp) / 'config.json')
            status_path = Path(tmp) / '_datacenter' / 'db_sync.json'
            self.assertTrue(status_path.exists(), 'Connection errors must replace stale success')
            status = json.loads(status_path.read_text())
            self.assertFalse(status['last']['ok'])
            self.assertNotIn('secret-value', status_path.read_text())


if __name__ == '__main__':
    unittest.main()

class SQLiteSnapshotTests(unittest.TestCase):
    def test_wal_commits_are_preserved_and_source_is_unchanged(self):
        from backend.datacenter_lib import sqlite_consistent_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.db';dest=Path(tmp)/'snapshot.db'
            conn=sqlite3.connect(source)
            try:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA wal_autocheckpoint=0')
                conn.execute('CREATE TABLE records (id text)');conn.commit()
                conn.execute("INSERT INTO records VALUES ('in-wal')");conn.commit()
                paths=[source,Path(str(source)+'-wal')]
                before=[p.read_bytes() for p in paths]
                sqlite_consistent_snapshot(source,dest)
                self.assertEqual(before,[p.read_bytes() for p in paths])
                with sqlite3.connect(dest) as out:
                    self.assertEqual(out.execute('SELECT id FROM records').fetchone()[0],'in-wal')
                    self.assertEqual(out.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            finally:conn.close()
    def test_wal_mode_without_sidecars_does_not_create_source_files(self):
        from backend.datacenter_lib import sqlite_consistent_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.db'
            with sqlite3.connect(source) as c:
                c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE records (id text)')
                c.execute("INSERT INTO records VALUES ('checkpointed')")
            c.close()
            self.assertFalse(Path(str(source)+'-wal').exists())
            sqlite_consistent_snapshot(source,Path(tmp)/'snapshot.db')
            self.assertFalse(Path(str(source)+'-wal').exists())
            self.assertFalse(Path(str(source)+'-shm').exists())

if __name__ == "__main__":
    unittest.main()
