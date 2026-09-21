import base64
import tempfile
import unittest
from pathlib import Path

import backend.runtime as rt


class ProjectAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_user_data_dir = rt.USER_DATA_DIR
        self.old_read_config = rt.read_config
        rt.USER_DATA_DIR = Path(self.tmp.name) / "user_data"
        rt.read_config = lambda: {
            "project_admins": ["manager"],
            "users": [
                {"username": "root", "name": "超级管理员", "role": "superadmin"},
                {"username": "manager", "name": "项目管理员", "role": "member"},
                {"username": "member", "name": "项目成员", "role": "member"},
                {"username": "outsider", "name": "外部成员", "role": "member"},
            ],
        }

    def tearDown(self):
        rt.USER_DATA_DIR = self.old_user_data_dir
        rt.read_config = self.old_read_config
        self.tmp.cleanup()

    def test_project_admin_creates_project_and_assigns_members(self):
        created = rt.project_create(
            {
                "name": "客流预测项目",
                "description": "推进车站客流预测能力落地",
                "members": [{"username": "member", "roles": ["echo", "delta"]}],
            },
            "manager",
        )

        self.assertTrue(created["ok"])
        project = created["project"]
        self.assertEqual(project["name"], "客流预测项目")
        self.assertEqual({item["username"] for item in project["members"]}, {"manager", "member"})
        member = next(item for item in project["members"] if item["username"] == "member")
        self.assertEqual(member["roles"], ["echo", "delta"])
        self.assertTrue(rt.project_list("member")["projects"])
        self.assertFalse(rt.project_list("outsider")["projects"])

    def test_project_member_can_view_timeline_but_not_manage_project(self):
        project_id = rt.project_create({"name": "归档项目", "members": [{"username": "member", "role": "delta"}]}, "manager")["project"]["id"]
        with self.assertRaises(PermissionError):
            rt.project_update({"id": project_id, "description": "不应成功"}, "member")

        rt.save_diary(
            {"date": "2026-08-31", "today_work": "完成项目资料整理", "project_id": project_id, "replace": True},
            "member",
        )
        rt.save_diary(
            {"date": "2026-08-30", "today_work": "管理员完成项目计划", "project_id": project_id, "replace": True},
            "manager",
        )
        report_path = rt.user_generated_kind_dir("member", "weekly") / "归档项目周报.xlsx"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(b"weekly")
        report = rt.project_record_report(
            project_id,
            "weekly",
            report_path,
            "member",
            {"period": "2026.8.24-2026.8.28"},
        )
        timeline = rt.project_timeline(project_id, "member")["timeline"]

        self.assertEqual({item["type"] for item in timeline}, {"daily", "weekly"})
        self.assertTrue(any(item["author"] == "manager" and item["type"] == "daily" for item in timeline))
        report_name, report_content = rt.project_report_file(project_id, report["id"], "member")
        self.assertEqual(report_name, "归档项目周报.xlsx")
        self.assertEqual(report_content, b"weekly")

    def test_project_material_upload_is_visible_to_members_only(self):
        project_id = rt.project_create({"name": "资料项目", "members": [{"username": "member", "role": "delta"}]}, "manager")["project"]["id"]
        uploaded = rt.project_upload_file(
            {"id": project_id, "name": "项目说明.txt", "content_base64": base64.b64encode("项目资料".encode()).decode()},
            "manager",
        )

        self.assertEqual(uploaded["file"]["name"], "项目说明.txt")
        member_project = rt.project_get(project_id, "member")["project"]
        self.assertEqual(len(member_project["files"]), 1)
        self.assertEqual(next(item for item in member_project["members"] if item["username"] == "member")["roles"], ["delta"])
        with self.assertRaises(PermissionError):
            rt.project_get(project_id, "outsider")

    def test_project_manager_can_delete_project_and_its_uploaded_materials(self):
        project_id = rt.project_create(
            {"name": "待删除项目", "members": [{"username": "member", "role": "delta"}]},
            "manager",
        )["project"]["id"]
        rt.project_upload_file(
            {"id": project_id, "name": "临时资料.txt", "content_base64": base64.b64encode(b"temporary").decode()},
            "manager",
        )
        project_directory = rt.project_root_dir() / project_id
        self.assertTrue(project_directory.exists())

        result = rt.project_delete({"id": project_id}, "manager")

        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted_id"], project_id)
        self.assertFalse(project_directory.exists())
        self.assertFalse(rt.project_list("manager")["projects"])
        with self.assertRaises(ValueError):
            rt.project_get(project_id, "manager")

    def test_non_manager_cannot_delete_project(self):
        project_id = rt.project_create(
            {"name": "受保护项目", "members": [{"username": "member", "role": "echo"}]},
            "manager",
        )["project"]["id"]

        with self.assertRaises(PermissionError):
            rt.project_delete({"id": project_id}, "member")

        self.assertEqual(rt.project_get(project_id, "manager")["project"]["name"], "受保护项目")

    def test_deleting_project_keeps_member_reports(self):
        project_id = rt.project_create(
            {"name": "报告项目", "members": [{"username": "member", "role": "delta"}]},
            "manager",
        )["project"]["id"]
        report_path = rt.user_generated_kind_dir("member", "weekly") / "应保留周报.xlsx"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(b"keep-report")
        rt.project_record_report(project_id, "weekly", report_path, "member")

        rt.project_delete({"id": project_id}, "manager")

        self.assertTrue(report_path.exists())
        self.assertEqual(report_path.read_bytes(), b"keep-report")

    def test_only_superadmin_can_read_or_change_platform_project_admins(self):
        with self.assertRaises(PermissionError):
            rt.project_admins_payload("manager")
        with self.assertRaises(PermissionError):
            rt.project_save_admins({"admins": ["member"]}, "manager")

        settings = rt.project_admins_payload("root")
        self.assertTrue(settings["can_configure"])
        self.assertEqual(settings["admins"], ["manager"])

    def test_legacy_member_roles_are_exposed_as_echo_or_delta(self):
        legacy = rt.project_create({"name": "兼容项目", "members": [{"username": "member", "role": "member"}]}, "manager")["project"]
        self.assertEqual(next(item for item in legacy["members"] if item["username"] == "member")["roles"], ["echo"])

    def test_member_with_manager_and_business_roles_can_manage_project(self):
        project_id = rt.project_create(
            {"name": "多角色项目", "members": [{"username": "member", "roles": ["manager", "echo", "delta"]}]},
            "manager",
        )["project"]["id"]

        updated = rt.project_update({"id": project_id, "description": "成员可共同管理"}, "member")

        member = next(item for item in updated["project"]["members"] if item["username"] == "member")
        self.assertEqual(member["roles"], ["manager", "echo", "delta"])

    def test_one_diary_can_be_linked_to_multiple_projects(self):
        first_id = rt.project_create({"name": "项目甲", "members": [{"username": "member", "roles": ["echo"]}]}, "manager")["project"]["id"]
        second_id = rt.project_create({"name": "项目乙", "members": [{"username": "member", "roles": ["delta"]}]}, "manager")["project"]["id"]

        saved = rt.save_diary(
            {"date": "2026-08-31", "today_work": "同步推进两个项目", "project_ids": [first_id, second_id], "replace": True},
            "member",
        )

        self.assertEqual(saved["diary"]["project_ids"], [first_id, second_id])
        self.assertTrue(any(item["type"] == "daily" for item in rt.project_timeline(first_id, "member")["timeline"]))
        self.assertTrue(any(item["type"] == "daily" for item in rt.project_timeline(second_id, "member")["timeline"]))

    def test_project_diary_notes_are_saved_and_shown_on_the_matching_timeline(self):
        first_id = rt.project_create({"name": "项目甲", "members": [{"username": "member", "roles": ["echo"]}]}, "manager")["project"]["id"]
        second_id = rt.project_create({"name": "项目乙", "members": [{"username": "member", "roles": ["delta"]}]}, "manager")["project"]["id"]

        saved = rt.save_diary(
            {
                "date": "2026-08-31",
                "today_work": "处理行政事项",
                "project_ids": [first_id, second_id],
                "project_notes": {first_id: "完成项目甲接口联调", second_id: "梳理项目乙需求清单"},
                "replace": True,
            },
            "member",
        )

        self.assertEqual(saved["diary"]["project_notes"][first_id], "完成项目甲接口联调")
        first_daily = next(item for item in rt.project_timeline(first_id, "member")["timeline"] if item["type"] == "daily")
        second_daily = next(item for item in rt.project_timeline(second_id, "member")["timeline"] if item["type"] == "daily")
        self.assertEqual(first_daily["title"], "完成项目甲接口联调")
        self.assertEqual(second_daily["title"], "梳理项目乙需求清单")
