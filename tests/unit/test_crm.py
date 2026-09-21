import tempfile
import unittest
from pathlib import Path

import backend.runtime as runtime


class CrmAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original = runtime.USER_DATA_DIR
        runtime.USER_DATA_DIR = Path(self.temporary.name)

    def tearDown(self):
        runtime.USER_DATA_DIR = self.original
        self.temporary.cleanup()

    def _build_relation(self, user="alice"):
        unit = runtime.crm_unit_save({"name": "某地铁业主", "type": "业主单位", "region": "长沙"}, user)["unit"]
        person = runtime.crm_person_save({"name": "张工", "unit_id": unit["id"], "title": "机电部经理", "decision_role": "定技术", "influence": 80}, user)["person"]
        relation = runtime.crm_relation_save({"person_id": person["id"], "source": "技术交流"}, user)["relation"]
        return unit, person, relation

    def test_relation_scoring_and_level(self):
        _, _, relation = self._build_relation()
        # 新关系无动作，L0
        self.assertEqual(relation["strength"], 0)
        # 加多次有效、双向、关键节点动作后升级
        for i in range(3):
            runtime.crm_action_add({
                "relation_id": relation["id"], "type": "拜访", "effective": True,
                "bidirectional": True, "intel": f"情报{i}", "decision_node": "定标",
                "happened_at": runtime.crm_now()[:10],
            }, "alice")
        updated = runtime.relations_get("alice", relation["id"])
        self.assertGreaterEqual(updated["strength"], 3)
        self.assertGreaterEqual(updated["radar"]["双向性"], 90)
        self.assertEqual(updated["decay_state"], "normal")

    def test_decay_warning_for_stale_high_tier(self):
        _, _, relation = self._build_relation()
        # 高层：机电部经理算中层，用200天前动作触发告警
        runtime.crm_action_add({
            "relation_id": relation["id"], "type": "拜访", "effective": True,
            "happened_at": "2024-01-01",
        }, "alice")
        updated = runtime.relations_get("alice", relation["id"])
        self.assertEqual(updated["decay_state"], "alarm")

    def test_overview_and_cross_user_isolation(self):
        self._build_relation("alice")
        overview = runtime.crm_overview("alice")
        self.assertTrue(overview["ok"])
        self.assertEqual(overview["stats"]["units"], 1)
        self.assertEqual(overview["stats"]["people"], 1)
        # bob 看不到 alice 的数据
        self.assertEqual(runtime.crm_overview("bob")["stats"]["units"], 0)

    def test_unassigned_relation_has_no_graph_connection_or_intro_path(self):
        unit = runtime.crm_unit_save({"name": "空白区域客户", "type": "业主单位"}, "alice")["unit"]
        person = runtime.crm_person_save({"name": "未指派联系人", "unit_id": unit["id"]}, "alice")["person"]
        runtime.crm_relation_save({"person_id": person["id"], "our_member": ""}, "alice")
        overview = runtime.crm_overview("alice", use_cache=False)
        self.assertTrue(any(node["id"] == person["id"] for node in overview["graph"]["nodes"]))
        self.assertFalse(any(edge["target"] == person["id"] for edge in overview["graph"]["edges"]))
        self.assertEqual(runtime.crm_path_to_person("alice", person["id"])["hops"], 0)

    def test_single_point_risk_is_derived_from_distinct_assigned_liaisons(self):
        unit = runtime.crm_unit_save({"name": "自动判定客户", "type": "业主单位"}, "alice")["unit"]
        person = runtime.crm_person_save({"name": "李工", "unit_id": unit["id"]}, "alice")["person"]

        primary = runtime.crm_relation_save({"person_id": person["id"], "our_member": "alice"}, "alice")["relation"]
        self.assertTrue(primary["single_point_risk"])

        backup = runtime.crm_relation_save({"person_id": person["id"], "our_member": "bob"}, "alice")["relation"]
        relations = runtime.crm_load("alice", "relations")
        self.assertFalse(relations[primary["id"]]["single_point_risk"])
        self.assertFalse(relations[backup["id"]]["single_point_risk"])

        runtime.crm_relation_save({**backup, "our_member": ""}, "alice")
        self.assertTrue(runtime.crm_load("alice", "relations")[primary["id"]]["single_point_risk"])

    def test_battle_map_recommends_direct_contact(self):
        unit, person, relation = self._build_relation()
        for _ in range(3):
            runtime.crm_action_add({"relation_id": relation["id"], "type": "拜访", "effective": True, "bidirectional": True, "decision_node": "定标", "happened_at": runtime.crm_now()[:10]}, "alice")
        result = runtime.crm_battle_map_generate({"target_person_id": person["id"]}, "alice")
        self.assertTrue(result["ok"])
        self.assertEqual(result["battle_map"]["who_goes"], "alice")
        self.assertEqual(len(result["pipeline"]), 6)
        self.assertGreaterEqual(len(result["candidates"]), 1)

    def test_decision_coverage_matrix(self):
        unit, person, relation = self._build_relation()
        runtime.crm_link_save({"project_id": "p1", "decision_node": "定标", "person_id": person["id"]}, "alice")
        cov = runtime.crm_decision_coverage("alice", "p1")
        self.assertEqual(cov["should_cover"], 30)  # 五类单位适用阶段合计（3+9+6+6+6），不强制所有组织覆盖每一阶段
        self.assertEqual(cov["covered"], 1)
        self.assertTrue(cov["matrix"]["业主单位"]["定标"]["covered"])

    def test_path_memory_bfs_via_colleague(self):
        # 无 Neo4j 时内存 BFS：我方→陈工(强关系)→王总(同单位、无直接关系)
        unit = runtime.crm_unit_save({"name": "某集团", "type": "业主单位"}, "alice")["unit"]
        bridge = runtime.crm_person_save({"name": "陈工", "unit_id": unit["id"]}, "alice")["person"]
        target = runtime.crm_person_save({"name": "王总", "unit_id": unit["id"]}, "alice")["person"]
        runtime.crm_relation_save({"person_id": bridge["id"]}, "alice")
        path = runtime.crm_path_to_person("alice", target["id"])
        self.assertTrue(path["ok"])
        self.assertEqual(path["names"], ["我方", "陈工", "王总"])
        self.assertEqual(path["hops"], 2)
        self.assertEqual(path["source"], "memory")

    def test_version_conflict_rejected(self):
        unit = runtime.crm_unit_save({"name": "单位A", "type": "总包单位"}, "alice")["unit"]
        stale = dict(unit)
        runtime.crm_unit_save({**unit, "name": "单位B"}, "alice")  # bumps version
        conflict = runtime.crm_unit_save({**stale, "name": "单位C"}, "alice")
        self.assertFalse(conflict["ok"])


if __name__ == "__main__":
    unittest.main()
