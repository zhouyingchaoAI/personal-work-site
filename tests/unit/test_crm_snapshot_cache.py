import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import backend.runtime as r

class SnapshotCache(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.users=[{'username':'admin','role':'superadmin'},{'username':'alice','employee_id':'E1','assistant_permissions':{'crm':True}}]
        for p in (patch.object(r,'USER_DATA_DIR',Path(self.tmp.name)),patch.object(r,'read_config',return_value={'users':self.users})):
            p.start();self.addCleanup(p.stop)
        r.CRM_SNAPSHOT_CACHE.clear()
        r.crm_store('admin','units',{'u':{'id':'u','name':'before'}})
        r.crm_store('admin','people',{'p':{'id':'p','unit_id':'u'}})
        r.crm_store('admin','relations',{'r':{'id':'r','person_id':'p','our_member':'E1'}})

    def test_parallel_reads_build_once_and_results_are_isolated(self):
        with patch.object(r,'_crm_build_snapshot',wraps=r._crm_build_snapshot) as build:
            with ThreadPoolExecutor(max_workers=6) as pool:
                values=list(pool.map(lambda _:r.crm_read_snapshot(self.users[0]),range(6)))
            self.assertEqual(build.call_count,1)
            values[0]['units'][0]['name']='mutated'
            self.assertEqual(r.crm_read_snapshot(self.users[0])['units'][0]['name'],'before')
            self.assertEqual(values[1]['units'][0]['name'],'before')

    def test_external_write_delete_and_grant_change_invalidate(self):
        r.crm_read_snapshot(self.users[1])
        path=r.crm_collection_path('admin','relations')
        path.write_text('{"r":{"id":"r","person_id":"p","our_member":"admin"}}')
        self.assertEqual(r.crm_read_snapshot(self.users[1])['relations'],[])
        with patch.object(r,'crm_capabilities',return_value={'read':True,'manage':True,'data_scope':'all'}):
            self.assertEqual(len(r.crm_read_snapshot(self.users[1])['relations']),1)
        self.assertEqual(r.crm_read_snapshot(self.users[1])['relations'],[])
        path.unlink()
        self.assertEqual(r.crm_read_snapshot(self.users[0])['relations'],[])

    def test_projection_copies_only_requested_collections_and_isolates_misses(self):
        first = r.crm_read_snapshot(self.users[0], ('units',))
        self.assertEqual(set(first), {'units'})
        first['units'][0]['name'] = 'changed'
        with patch.object(r.crm_copy, 'deepcopy', wraps=r.crm_copy.deepcopy) as copy:
            again = r.crm_read_snapshot(self.users[0], ('units',))
            self.assertEqual(set(copy.call_args.args[0]), {'units'})
        self.assertEqual(again['units'][0]['name'], 'before')
        again['units'].clear()
        self.assertEqual(len(r.crm_read_snapshot(self.users[0])['units']), 1)

    def test_expiry_and_disabled_access(self):
        r.crm_read_snapshot(self.users[0])
        key=next(iter(r.CRM_SNAPSHOT_CACHE));sig,at,value=r.CRM_SNAPSHOT_CACHE[key]
        r.CRM_SNAPSHOT_CACHE[key]=(sig,at-11,value)
        with patch.object(r,'_crm_build_snapshot',wraps=r._crm_build_snapshot) as build:
            r.crm_read_snapshot(self.users[0]);self.assertEqual(build.call_count,1)
        with patch.object(r,'crm_capabilities',return_value={'read':False,'data_scope':'all'}):
            self.assertEqual(r.crm_read_snapshot(self.users[0])['relations'],[])

if __name__=='__main__':unittest.main()
