"""数据中台「数据库直连」单元测试：只读守卫、标识符校验、脱敏与 SQLite 浏览。

网络型实例（PostgreSQL/MySQL/MongoDB/Redis/ES/Qdrant/Neo4j）的连通性在容器内
端到端验证；这里覆盖不依赖外部服务的安全与序列化逻辑。
"""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_module(base_dir, user_data_dir, audit_log):
    from backend.datacenter_lib import datacenter_dir, read_json
    from backend.data_center_browse import dc_mask
    ns = {"BASE_DIR": Path(base_dir), "USER_DATA_DIR": Path(user_data_dir),
          "__file__": str(ROOT / "app.py"), "read_json": read_json, "datacenter_dir": datacenter_dir,
          "dc_mask": dc_mask, "dc_audit": lambda *a: audit_log.append(a), "json": json}
    code = (ROOT / "backend" / "data_center_databases.py").read_text(encoding="utf-8")
    exec(compile(code, "data_center_databases.py", "exec"), ns)
    return ns


class DatabasesUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "user_data" / "_datacenter").mkdir(parents=True)
        db_path = base / "user_data" / "test.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, password TEXT)")
            conn.executemany("INSERT INTO accounts (name, password) VALUES (?, ?)",
                             [(f"user{i}", f"secret{i}") for i in range(7)])
        registry = {"instances": [{"id": "sqlite-test", "kind": "sqlite", "label": "测试库",
                                   "system": "测试", "level": "D", "path": "user_data/test.db"}]}
        (base / "user_data" / "_datacenter" / "db_connections.json").write_text(
            json.dumps(registry), encoding="utf-8")
        self.audit = []
        self.ns = load_module(base, base / "user_data", self.audit)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sql_guard_rejects_writes_and_multi_statements(self):
        for sql in ("DELETE FROM accounts", "UPDATE accounts SET name='x'", "DROP TABLE accounts",
                    "INSERT INTO accounts (name) VALUES ('x')", "SELECT 1; SELECT 2",
                    "PRAGMA journal_mode=DELETE", ""):
            with self.assertRaises(ValueError, msg=sql):
                self.ns["dcdb_query"]("sqlite-test", "", sql, "tester")

    def test_sqlite_readonly_blocks_writes_even_past_the_guard(self):
        inst = self.ns["_dcdb_inst"]("sqlite-test")
        with self.assertRaises(sqlite3.OperationalError):
            self.ns["_dcdb_sqlite_query"](inst, "", "INSERT INTO accounts (name) VALUES ('x')")

    def test_query_rows_and_pagination(self):
        result = self.ns["dcdb_query"]("sqlite-test", "", "SELECT count(*) AS c FROM accounts", "tester")
        self.assertEqual(result["rows"][0]["c"], 7)
        page = self.ns["dcdb_rows"]("sqlite-test", "", "accounts", 1, 5, "tester")
        self.assertEqual(page["total"], 7)
        self.assertEqual(len(page["rows"]), 2)

    def test_sensitive_columns_are_masked(self):
        page = self.ns["dcdb_rows"]("sqlite-test", "", "accounts", 0, 3, "tester")
        self.assertTrue(all(row["password"] == "••• 已脱敏" for row in page["rows"]))

    def test_object_name_validation(self):
        for bad in ("../etc/passwd", "a b", "x'; DROP TABLE accounts; --", ""):
            with self.assertRaises(ValueError, msg=bad):
                self.ns["dcdb_rows"]("sqlite-test", "", bad, 0, 5, "tester")

    def test_unknown_instance_and_missing_registry(self):
        with self.assertRaises(ValueError):
            self.ns["dcdb_rows"]("nope", "", "accounts", 0, 5, "tester")
        with tempfile.TemporaryDirectory() as empty:
            (Path(empty) / "_datacenter").mkdir()
            ns = load_module(empty, empty, [])
            with self.assertRaises(RuntimeError):
                ns["dcdb_instances"]()

    def test_access_is_audited(self):
        self.ns["dcdb_rows"]("sqlite-test", "", "accounts", 0, 5, "tester")
        self.ns["dcdb_query"]("sqlite-test", "", "SELECT 1 AS x", "tester")
        actions = [entry[1] for entry in self.audit]
        self.assertIn("db-rows", actions)
        self.assertIn("db-query", actions)

    def test_safe_serialization(self):
        import decimal
        from datetime import datetime
        safe = self.ns["_dcdb_safe"]
        self.assertEqual(safe(decimal.Decimal("1.50")), "1.50")
        self.assertEqual(safe(datetime(2026, 9, 30, 8, 0)), "2026-09-30T08:00:00")
        self.assertIn("二进制 3 字节", safe(b"\x00\x01\x02"))
        self.assertTrue(safe("x" * 3000).endswith("（共 3000 字符）"))

    def test_redis_resp_parser(self):
        client = object.__new__(self.ns["_DcdbRedis"])
        client.fh = io.BytesIO(b"+OK\r\n:42\r\n$5\r\nhello\r\n*2\r\n$1\r\na\r\n:7\r\n$-1\r\n-ERR boom\r\n")
        self.assertEqual(client._read(), "OK")
        self.assertEqual(client._read(), 42)
        self.assertEqual(client._read(), "hello")
        self.assertEqual(client._read(), ["a", 7])
        self.assertIsNone(client._read())
        with self.assertRaises(RuntimeError):
            client._read()

    def test_sql_queries_only_supported_for_sql_kinds(self):
        base = Path(self.tmp.name)
        registry = json.loads((base / "user_data" / "_datacenter" / "db_connections.json").read_text())
        registry["instances"].append({"id": "redis-x", "kind": "redis", "label": "r", "system": "t",
                                      "level": "D", "host": "127.0.0.1", "port": 1})
        (base / "user_data" / "_datacenter" / "db_connections.json").write_text(json.dumps(registry))
        with self.assertRaises(ValueError):
            self.ns["dcdb_query"]("redis-x", "", "SELECT 1", "tester")


if __name__ == "__main__":
    unittest.main()
