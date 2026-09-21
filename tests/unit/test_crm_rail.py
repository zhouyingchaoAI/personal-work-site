import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend.runtime as r

class RailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(r, 'USER_DATA_DIR', Path(self.tmp.name)), patch.object(r, 'crm_on_change'), patch.object(r, 'crm_graph_shortest_path', return_value=None)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()
    def person(self):
        u = r.crm_unit_save({'name':'业主A','type':'业主单位'},'alice')['unit']
        p = r.crm_person_save({'name':'工程联系人','unit_id':u['id']},'alice')['person']
        return p
    def test_coverage_unique_cells(self):
        p=self.person()
        r.crm_store('alice','relations',{'r':{'id':'r','person_id':p['id'],'strength':3}})
        for _ in range(2):
            r.crm_link_save({'project_id':'P','person_id':p['id'],'decision_node':'验收'},'alice')
        c=r.crm_decision_coverage('alice','P')
        self.assertEqual(c['l3_plus'],1)
        self.assertEqual(r.crm_decision_coverage('alice', ' P ')['covered'], c['covered'])
        self.assertFalse(c['matrix']['设计单位']['付款']['applicable'])
        self.assertLess(c['should_cover'],len(c['nodes'])*5)

    def test_all_unit_types_have_a_rail_definition(self):
        defined = {item['type'] for item in r.CRM_ORGANIZATIONS}
        self.assertEqual(r.CRM_UNIT_TYPES, ["主管单位", "业主单位", "总包单位", "设计单位", "厂商"])
        self.assertEqual(defined, set(r.CRM_UNIT_TYPES))
    def test_followup_isolation_and_close(self):
        p=self.person()
        rel=r.crm_relation_save({'person_id':p['id']},'alice')['relation']
        a=r.crm_action_add({'relation_id':rel['id'],'next_step':'提交接口清单','due_date':'2026-09-30','owner':'张工','project_id':'P'},'alice')['action']
        self.assertEqual(r.crm_followups('alice')[0]['next_step'],'提交接口清单')
        self.assertEqual(r.crm_followups('bob'),[])
        self.assertFalse(r.crm_followup_complete({'id':a['id']},'bob')['ok'])
        self.assertTrue(r.crm_followup_complete({'id':a['id']},'alice')['ok'])
        self.assertEqual(r.crm_followups('alice'),[])
    def test_stage_specific_battle(self):
        p=self.person()
        result=r.crm_battle_map_generate({'target_person_id':p['id'],'stage':'验收'},'alice')
        self.assertIn('验收',result['battle_map']['first_step'])
        self.assertNotIn('成功率',str(result['pipeline']))

    def test_battle_map_scopes_opportunity_to_owner_organization_tree(self):
        root = r.crm_unit_save({'name':'城市地铁集团有限公司','type':'业主单位','organization_level':'company'}, 'alice')['unit']
        branch = r.crm_unit_save({'name':'建设分公司','type':'业主单位','organization_level':'unit','parent_unit_id':root['id']}, 'alice')['unit']
        target = r.crm_person_save({'name':'李总','unit_id':branch['id']}, 'alice')['person']
        bridge = r.crm_person_save({'name':'王工','unit_id':root['id']}, 'alice')['person']
        relation = r.crm_relation_save({'person_id':bridge['id'],'our_member':'E100'}, 'alice')['relation']
        for _ in range(3):
            r.crm_action_add({'relation_id':relation['id'], 'type':'拜访', 'effective':True,
                              'bidirectional':True, 'intel':'业主组织引荐线索',
                              'happened_at':r.crm_now()[:10]}, 'alice')
        r.crm_store('alice', 'opportunities', {'OPP-1':{
            'id':'OPP-1','code':'OPP-1','name':'地铁信号项目','owner_unit':'城市地铁集团',
            'stage':'招标','cancelled':False,
        }})

        result = r.crm_battle_map_generate({'project_id':'OPP-1','target_person_id':target['id']}, 'alice')

        self.assertTrue(result['ok'])
        context = result['opportunity_context']
        self.assertEqual(context['owner_unit'], '城市地铁集团')
        self.assertEqual(context['matched_people'], 2)
        self.assertEqual(context['strong_relations'], 1)
        self.assertIn('同一业主组织线索', result['battle_map']['route'])
    def test_no_colleague_inference_without_unit(self):
        a=r.crm_person_save({'name':'A'},'alice')['person']
        b=r.crm_person_save({'name':'B'},'alice')['person']
        r.crm_relation_save({'person_id':a['id']},'alice')
        self.assertEqual(r.crm_path_to_person('alice',b['id'])['hops'],0)
