import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "provision_crm_staff_accounts.py"


class StaffAccountProvisioningTests(unittest.TestCase):
    def test_provision_creates_pinyin_account_and_enriches_matched_account(self):
        spec = importlib.util.spec_from_file_location("staff_provision", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / "config.json"
            directory_path = root / "staff.json"
            config_path.write_text(json.dumps({"users": [{
                "username": "existing-admin", "password": "keep", "role": "admin", "name": "张三"
            }]}, ensure_ascii=False), encoding="utf-8")
            directory_path.write_text(json.dumps({
                "first": {"member_key": "120001", "name": "张三", "company": "湖南承希科技有限公司", "department": "运营管理部", "title": ""},
                "second": {"member_key": "120002", "name": "李四", "company": "承希交通科技（湖南）有限公司", "department": "交付部", "title": "工程师"},
            }, ensure_ascii=False), encoding="utf-8")

            result = module.provision(config_path, directory_path, {"张三": "zhangsan", "李四": "lisi"}.get)
            users = json.loads(config_path.read_text(encoding="utf-8"))["users"]
            by_username = {item["username"]: item for item in users}

            self.assertEqual(result, {"created": 1, "enriched": 1, "unchanged": 0})
            self.assertEqual(by_username["existing-admin"]["employee_id"], "120001")
            self.assertEqual(by_username["existing-admin"]["role"], "admin")
            self.assertTrue(runtime.verify_password("123456", by_username["lisi"]["password"]))
            self.assertEqual(by_username["lisi"]["department"], "交付部")
