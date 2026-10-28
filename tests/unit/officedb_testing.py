"""让现有单测类在数据库模式下再跑一遍的辅助工具。

设置 OFFICE_STORE_TEST_CONFIG=<一次性测试库配置> 后，db_variant(TestCase) 生成一个
子类：setUp 前把 runtime.officedb_config 换成测试库配置（modules.all=true）并清空
三张 app 表，tearDown 后还原。未设置环境变量时子类整体跳过。
"""
import json
import os
import unittest
from pathlib import Path

import backend.runtime as runtime

TEST_CONFIG_ENV = "OFFICE_STORE_TEST_CONFIG"


def test_config():
    path = os.getenv(TEST_CONFIG_ENV)
    if not path:
        return None
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    assert config.get("database") != "office", "禁止对生产库跑测试"
    return {**config, "enabled": True, "modules": {"all": True}}


def reset_tables():
    with runtime._officedb_conn() as conn:
        for table in ("documents", "blobs", "events"):
            conn.run(f"DELETE FROM app.{table}")


class OfficeDbModeMixin:
    def setUp(self):
        self._officedb_saved = runtime.officedb_config
        config = test_config()
        runtime.officedb_config = lambda: config
        runtime._officedb_drain_pool()
        reset_tables()
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            runtime.officedb_config = self._officedb_saved
            runtime._officedb_drain_pool()


def db_variant(test_class):
    name = test_class.__name__ + "DbMode"
    variant = type(name, (OfficeDbModeMixin, test_class), {"__module__": test_class.__module__})
    return unittest.skipUnless(os.getenv(TEST_CONFIG_ENV), "requires disposable test database")(variant)
