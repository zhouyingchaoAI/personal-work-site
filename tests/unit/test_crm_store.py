"""联指经营助手数据库存储后端（crm_store.py）测试。

- 默认（无数据库）验证：开关关闭时不启用、配置缺失安全降级。
- DB 往返、顺序保留、历史语义、迁移/导出回滚：需要专用测试库，设置
  CRM_STORE_TEST_CONFIG=<crm_db.json 路径，database 指向一次性测试库> 后在
  容器内运行（参考 /tmp/crm_store_dbtest.py 的建表 SQL，或 scripts/crm_db_setup.py）。
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_store(user_data_dir):
    ns = {"USER_DATA_DIR": Path(user_data_dir), "__file__": str(ROOT / "app.py"),
          "json": json, "crm_now": lambda: "2026-01-01T00:00:00"}
    code = (ROOT / "backend" / "crm_store.py").read_text(encoding="utf-8")
    exec(compile(code, "crm_store.py", "exec"), ns)
    return ns


class CrmStoreOfflineTests(unittest.TestCase):
    def test_disabled_without_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = load_store(tmp)
            self.assertFalse(ns["crmdb_enabled"]())

    def test_disabled_flag_and_reload_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "_datacenter" / "crm_db.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"enabled": False, "password": "x"}))
            ns = load_store(tmp)
            self.assertFalse(ns["crmdb_enabled"]())
            path.write_text(json.dumps({"enabled": True, "password": "x"}))
            os.utime(path, ns=(1, 10**18))  # 保证 mtime 变化被感知
            self.assertTrue(ns["crmdb_enabled"]())

    def test_unknown_collection_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ns = load_store(tmp)
            with self.assertRaises(ValueError):
                ns["_crmdb_table"]("../evil")


@unittest.skipUnless(os.getenv("CRM_STORE_TEST_CONFIG"), "requires disposable test database")
class CrmStoreDatabaseTests(unittest.TestCase):
    """完整 DB 往返在容器内跑：cp tests 进容器后设 CRM_STORE_TEST_CONFIG 运行。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        target = Path(self.tmp.name) / "_datacenter"
        target.mkdir()
        config = json.loads(Path(os.environ["CRM_STORE_TEST_CONFIG"]).read_text())
        assert config.get("database") != "office", "禁止对生产库跑测试"
        (target / "crm_db.json").write_text(json.dumps({**config, "enabled": True}))
        self.ns = load_store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_order_and_history(self):
        ns = self.ns
        order = ["b", "a", "c"]
        records = {rid: {"id": rid, "name": rid.upper()} for rid in order}
        ns["crmdb_store"]("tester", "units", records)
        loaded = ns["crmdb_load"]("tester", "units")
        self.assertEqual(list(loaded), order)
        self.assertEqual(loaded, records)
        ns["crmdb_store"]("tester", "units", {"b": records["b"]})
        versions = ns["crmdb_record_versions"]("tester", "units", "a")
        self.assertEqual(versions[0]["record"]["name"], "A")
        ns["crmdb_store"]("tester", "units", {})


if __name__ == "__main__":
    unittest.main()
