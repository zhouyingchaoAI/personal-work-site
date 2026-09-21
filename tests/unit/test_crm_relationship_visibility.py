import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class RelationshipVisibility(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.users=[{'username':'alice','employee_id':'E001'},{'username':'bob'},{'username':'root','role':'superadmin'}]
        for p in (patch.object(r,'USER_DATA_DIR',Path(self.tmp.name)),patch.object(r,'read_config',return_value={'users':self.users})):
            p.start();self.addCleanup(p.stop)
        for owner in ('alice','bob'):
            r.crm_store(owner,'units',{owner+'east':{'id':owner+'east','business_regions':['东区']},owner+'west':{'id':owner+'west','business_regions':['西区']}})
            r.crm_store(owner,'people',{owner+area:{'id':owner+area,'unit_id':owner+area} for area in ('east','west')})
            rs={owner+area+key:{'id':owner+area+key,'person_id':owner+area,'our_member':key} for area in ('east','west') for key in ('E001','bob')}
            r.crm_store(owner,'relations',rs)
            r.crm_store(owner,'actions',{key:{'id':key,'relation_id':key,'next_step':key} for key in rs})

    def snapshot(self,scope='self',**extra):
        with patch.object(r,'crm_capabilities',return_value={'read':True,'data_scope':scope,**extra}):
            snap=r.crm_read_snapshot(self.users[0])
            self.assertEqual({a['relation_id'] for a in snap['actions']},{rel['id'] for rel in snap['relations']})
            self.assertEqual({rel['id'] for rel in r.crm_read_relations(self.users[0])['relations']},{rel['id'] for rel in snap['relations']})
            self.assertEqual({a['relation_id'] for a in r.crm_read_playbook(self.users[0])['followups']},{rel['id'] for rel in snap['relations']})
            return snap

    def test_private_uploads_do_not_grant_access_to_peer_relationships(self):
        snap=self.snapshot()
        self.assertEqual(len(snap['relations']),4)
        self.assertTrue(all(rel['our_member']=='E001' for rel in snap['relations']))
        self.assertEqual({rel['_owner'] for rel in snap['relations']},{'alice','bob'})

    def test_broad_archive_grant_is_not_an_administrator(self):
        for scope in ('all','team','organization'):
            self.assertTrue(all(rel['our_member']=='E001' for rel in self.snapshot(scope)['relations']))

    def test_region_leader_gets_region_and_own_cross_region_assignments(self):
        snap=self.snapshot('regions',regions=['东区'])
        self.assertEqual(len(snap['relations']),6)
        self.assertFalse(any(rel['our_member']=='bob' and 'west' in rel['id'] for rel in snap['relations']))

    def test_admin_sees_all_and_disabled_sees_none(self):
        self.assertEqual(len(r.crm_read_snapshot(self.users[2])['relations']),8)
        self.assertEqual(len(self.snapshot('all',manage=True)['relations']),8)
        with patch.object(r,'crm_capabilities',return_value={'read':False,'data_scope':'all'}):
            self.assertEqual(r.crm_read_snapshot(self.users[0])['relations'],[])
            self.assertEqual(r.crm_read_snapshot(self.users[0])['actions'],[])

if __name__=='__main__':unittest.main()
