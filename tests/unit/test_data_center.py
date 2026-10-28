"""数据中台：资产分级扫描与元数据读写的单元测试（python3 -m unittest）。"""
import json
import tempfile
import unittest
from pathlib import Path

from backend.datacenter_lib import (
    classify_shared, read_json, save_scan_snapshot, scan_user_data, write_json_atomic,
)


def _write(path, size=10):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


class DataCenterScanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _seed(self):
        _write(self.root / "app.db", 100)
        _write(self.root / "_forum" / "topics.json", 50)
        _write(self.root / "_news" / "cache.json", 30)
        _write(self.root / "alice" / "crm" / "units.json", 40)
        _write(self.root / "alice" / "mail_cache" / "inbox.json", 1000)
        _write(self.root / "alice" / "operating_ledger.json", 20)
        _write(self.root / "alice" / "reports" / "weekly" / "a.docx", 60)
        _write(self.root / "bob" / "cashflow_history.json", 70)

    def test_classify_shared(self):
        self.assertEqual(classify_shared("_forum"), ("金点子论坛", "A"))
        self.assertEqual(classify_shared("config.json.backup-x"), ("其他共享数据", "B"))
        self.assertIsNone(classify_shared("zhangsan"))

    def test_scan_levels_and_users(self):
        self._seed()
        scan = scan_user_data(self.root)
        by_module = {m["module"]: m for m in scan["modules"]}
        self.assertEqual(by_module["联指经营助手"]["bytes"], 40)
        self.assertEqual(by_module["邮件缓存"]["level"], "D")
        self.assertEqual(by_module["项目管理台账"]["level"], "A")
        # A 级：app.db 100 + forum 50 + crm 40 + ledger 20 + cashflow 70 = 280
        self.assertEqual(scan["levels"]["A"]["bytes"], 280)
        self.assertEqual(scan["levels"]["D"]["bytes"], 1030)
        self.assertEqual(scan["user_count"], 2)
        self.assertEqual(scan["users_top"][0]["user"], "alice")
        self.assertEqual(scan["total_files"], 8)

    def test_extra_files_counted_as_level_a(self):
        self._seed()
        cfg = self.root.parent / "config.json"
        _write(cfg, 500)
        scan = scan_user_data(self.root, extra_files=[("账号与平台配置", "A", cfg)])
        self.assertEqual({m["module"]: m["bytes"] for m in scan["modules"]}["账号与平台配置"], 500)

    def test_snapshot_history_dedupes_same_day(self):
        self._seed()
        first = save_scan_snapshot(self.root, scan_user_data(self.root))
        _write(self.root / "bob" / "diary" / "d.json", 5)
        second = save_scan_snapshot(self.root, scan_user_data(self.root))
        self.assertEqual(len(second["history"]), 1)  # 同一天覆盖，不重复累计
        self.assertGreater(second["history"][0]["total_bytes"], first["history"][0]["total_bytes"] - 1)
        on_disk = read_json(self.root / "_datacenter" / "scan.json", {})
        self.assertEqual(on_disk["total_bytes"], second["total_bytes"])

    def test_write_json_atomic_leaves_no_tmp(self):
        target = self.root / "_datacenter" / "backups.json"
        write_json_atomic(target, [{"id": "1"}])
        self.assertEqual(json.loads(target.read_text())[0]["id"], "1")
        self.assertFalse(list(target.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()


class DataCenterBrowseTest(unittest.TestCase):
    """原始数据浏览：越界、脱敏、审计（依赖 runtime 共享命名空间）。"""

    @classmethod
    def setUpClass(cls):
        import backend.runtime as r
        cls.r = r

    def test_traversal_blocked(self):
        for bad in ("../config.json", "..", "a/../../etc/passwd"):
            with self.assertRaises(PermissionError):
                self.r.dc_resolve(bad)

    def test_mask_sensitive_keys(self):
        masked = self.r.dc_mask({"smtp_password": "abc", "name": "ok",
                                 "nested": [{"api_key": "k", "value": 1}]})
        self.assertEqual(masked["smtp_password"], "••• 已脱敏")
        self.assertEqual(masked["name"], "ok")
        self.assertEqual(masked["nested"][0]["api_key"], "••• 已脱敏")
        self.assertEqual(masked["nested"][0]["value"], 1)

    def test_mask_truncates_long_arrays(self):
        out = self.r.dc_mask(list(range(500)))
        self.assertEqual(len(out), 201)
        self.assertIn("共 500 项", out[-1])

    def test_config_preview_masked_and_not_downloadable(self):
        preview = self.r.datacenter_preview("config.json", "unittest")
        self.assertEqual(preview["kind"], "json")
        self.assertFalse(preview["downloadable"])
        self.assertTrue(str(preview["data"]["users"][0]["password"]).startswith("•••"))
        with self.assertRaises(PermissionError):
            self.r.datacenter_download("config.json", "unittest")

    def test_secret_files_blocked(self):
        with self.assertRaises(PermissionError):
            self.r.datacenter_preview(".app_secret_key", "unittest")
        with self.assertRaises(PermissionError):
            self.r.datacenter_download(".app_secret_key", "unittest")


class DataApiTest(unittest.TestCase):
    """数据访问接口：目录、必填校验、分页与密钥生命周期。"""

    @classmethod
    def setUpClass(cls):
        import backend.runtime as r
        cls.r = r

    def test_catalog_matches_implementations(self):
        for d in self.r.dapi_catalog()["datasets"]:
            self.assertIn("params", d)
            self.assertTrue(d["fields"], d["key"])

    def test_required_owner_enforced(self):
        with self.assertRaises(ValueError):
            self.r.dapi_query("crm.units", {}, "unittest")

    def test_unknown_dataset_rejected(self):
        with self.assertRaises(ValueError):
            self.r.dapi_query("no.such", {}, "unittest")

    def test_limit_capped_at_500(self):
        q = self.r.dapi_query("agent.skill_invocations", {"limit": "9999"}, "unittest")
        self.assertEqual(q["limit"], 500)

    def test_key_lifecycle(self):
        import secrets
        name = "unittest-" + secrets.token_hex(4)
        created = self.r.dapi_create_key({"name": name}, "unittest")
        token = created["token"]
        self.assertTrue(token.startswith("dck_"))
        self.assertEqual(self.r.dapi_auth_key(token), name)
        key_id = next(k["id"] for k in self.r.dapi_list_keys()["keys"] if k["name"] == name)
        self.r.dapi_revoke_key({"id": key_id}, "unittest")
        self.assertIsNone(self.r.dapi_auth_key(token))
        self.assertNotIn("hash", json.dumps(self.r.dapi_list_keys()))


class DataCenterDbRowsTest(unittest.TestCase):
    """入库同步的纯函数行构造。"""

    @classmethod
    def setUpClass(cls):
        from backend import datacenter_db
        cls.m = datacenter_db

    def test_build_config_rows(self):
        users, perms, mails, platform = self.m.build_config_rows({
            "users": [{"username": "u1", "role": "member", "name": "甲",
                       "assistant_permissions": {"crm": True, "cashflow": False}}],
            "user_mail_settings": {"u1": {"smtp_host": "x"}},
            "leader_email": "a@b.c",
        })
        self.assertEqual(users[0][:3], ["u1", "member", "甲"])
        self.assertEqual({(p[0], p[1], p[2]) for p in perms}, {("u1", "crm", True), ("u1", "cashflow", False)})
        self.assertEqual(mails[0][0], "u1")
        self.assertIn("leader_email", [p[0] for p in platform])
        self.assertNotIn("users", [p[0] for p in platform])

    def test_rows_from_keyed_json(self):
        rows = self.m.rows_from_keyed_json({"a": {"id": "a", "name": "N"}}, owner="o", name_key="name")
        self.assertEqual(rows[0][:3], ["o", "a", "N"])
        rows = self.m.rows_from_keyed_json([{"id": "x"}, {"no_id": 1}])
        self.assertEqual([r[0] for r in rows], ["x", "row-1"])
