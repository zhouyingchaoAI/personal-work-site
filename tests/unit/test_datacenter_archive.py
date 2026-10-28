import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.datacenter_archive import inventory, safe_destination, snapshot_project, restore_project

class ArchiveUnitTests(unittest.TestCase):
    def test_user_data_is_not_excluded_by_developer_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ['node_modules/rebuild.txt','user_data/node_modules/data.bin','.env','assets/template.xlsx']:
                f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'data')
            files={str(r) for _,r,k,_ in inventory(p) if k=='file'}
            self.assertNotIn('node_modules/rebuild.txt',files)
            self.assertIn('user_data/node_modules/data.bin',files)
            self.assertIn('.env',files)
            self.assertIn('assets/template.xlsx',files)
    def test_restore_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['/etc/passwd','../outside','project/../../outside']:
                with self.assertRaises(ValueError):safe_destination(tmp,name)
            (Path(tmp)/'link').symlink_to('/tmp')
            with self.assertRaises(ValueError):safe_destination(tmp,'link/escape')

@unittest.skipUnless(os.getenv('DC_ARCHIVE_TEST_DB'), 'requires a dedicated disposable PostgreSQL database')
class ArchivePostgresTests(unittest.TestCase):
    def test_complete_round_trip_incremental_and_failure(self):
        from backend.datacenter_db import db_connect
        assert os.getenv('OFFICE_PG_DB','').startswith('dc_archive_test_')
        conn=db_connect()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';root.mkdir()
                payload=os.urandom(1024*1024+127)
                (root/'file.bin').write_bytes(payload)
                (root/'copy.bin').write_bytes(payload)
                (root/'.env').write_text('TEST_SECRET=fixture-only\n');os.chmod(root/'.env',0o600)
                (root/'empty').mkdir()
                with sqlite3.connect(root/'app.db') as db:
                    db.execute('create table records (id text)');db.execute("insert into records values ('wf_1')")
                first=snapshot_project(conn,{'project':root})
                chunks=conn.run('SELECT count(*) FROM archive.chunks')[0][0]
                second=snapshot_project(conn,{'project':root})
                self.assertEqual(conn.run('SELECT count(*) FROM archive.chunks')[0][0],chunks)
                target=Path(tmp)/'restored'
                result=restore_project(conn,target,second['id'])
                self.assertEqual(result['files'],4)
                self.assertEqual((target/'project/file.bin').read_bytes(),payload)
                self.assertEqual((target/'project/.env').stat().st_mode&0o777,0o600)
                self.assertTrue((target/'project/empty').is_dir())
                with sqlite3.connect(target/'project/app.db') as db:
                    self.assertEqual(db.execute('select id from records').fetchone()[0],'wf_1')
                with self.assertRaises(FileExistsError):restore_project(conn,target)
                with self.assertRaises(ValueError):snapshot_project(conn,{'missing':root/'missing'})
                latest=conn.run("SELECT id FROM archive.runs WHERE state='complete' ORDER BY finished_at DESC LIMIT 1")[0][0]
                self.assertEqual(latest,second['id'])
                conn.run("UPDATE archive.entries SET sha256='corrupt' WHERE run_id=:r AND path='project/file.bin'",r=first['id'])
                with self.assertRaises(ValueError):restore_project(conn,Path(tmp)/'bad',first['id'])
        finally:conn.close()

if __name__=='__main__':unittest.main()
