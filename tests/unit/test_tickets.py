import json
import tempfile
import unittest
from pathlib import Path

from backend import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
MENU = ROOT / "ai-office-assistant-web" / "src" / "layout" / "menu.ts"
WORKSPACE = ROOT / "ai-office-assistant-web" / "src" / "views" / "WorkspaceView" / "index.vue"
WORKORDER = ROOT / "ai-office-assistant-web" / "src" / "views" / "WorkOrderView" / "index.vue"


class TicketSplitTests(unittest.TestCase):
    def _with_env(self):
        self._orig_dir = rt.USER_DATA_DIR
        self._orig_find = rt.find_user
        rt.find_user = lambda username: {"name": username}

    def _restore(self):
        rt.USER_DATA_DIR = self._orig_dir
        rt.find_user = self._orig_find

    def test_migration_moves_legacy_tickets_out_of_forum_and_keeps_ideas(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._with_env()
            try:
                rt.USER_DATA_DIR = Path(tmp)
                forum_dir = Path(tmp) / "_forum"
                forum_dir.mkdir(parents=True)
                seed = [
                    {"id": "idea1", "title": "金点子", "body": "x", "preset": "", "comments": []},
                    {"id": "t1", "title": "工单甲", "body": "请处理", "preset": "platform_ticket",
                     "comments": [{"id": "c1", "content": "受理", "status": "accepted"}]},
                    {"id": "t2", "title": "工单乙", "body": "请处理", "preset": "platform_ticket",
                     "comments": [{"id": "c2", "content": "修复", "status": "resolved"}]},
                ]
                (forum_dir / "topics.json").write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

                # Forum keeps only the idea; tickets are removed.
                forum_titles = [t["title"] for t in rt.forum_list_topics("admin")["topics"]]
                self.assertEqual(forum_titles, ["金点子"])

                tl = rt.ticket_list("admin")
                self.assertEqual(tl["summary"], {"total": 2, "open": 1, "closed": 1})
                # Open ticket (accepted, not resolved) pins above the resolved one.
                self.assertEqual(tl["tickets"][0]["title"], "工单甲")
                self.assertTrue(tl["tickets"][0]["pinned"])
                self.assertFalse(tl["tickets"][1]["pinned"])

                # A backup of the original forum store is written before rewriting.
                self.assertTrue(list(forum_dir.glob("topics.json.bak-before-ticket-split-*")))

                # No data is lost across the split.
                self.assertEqual(len(rt.load_tickets()) + len(rt.forum_list_topics("admin")["topics"]), 3)
            finally:
                self._restore()

    def test_ticket_lifecycle_autopins_until_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._with_env()
            try:
                rt.USER_DATA_DIR = Path(tmp)
                t = rt.ticket_create({"title": "新工单", "body": "内容", "module": "邮件助手"}, "admin")["ticket"]
                self.assertTrue(t["pinned"])
                self.assertFalse(t["resolved"])
                self.assertEqual(t["status"], "open")

                accepted = rt.ticket_add_comment({"topic_id": t["id"], "content": "已受理", "status": "accepted"}, "admin")["ticket"]
                self.assertTrue(accepted["pinned"])
                self.assertEqual(accepted["status"], "accepted")

                resolved = rt.ticket_add_comment({"topic_id": t["id"], "content": "已修复", "status": "resolved"}, "admin")["ticket"]
                self.assertFalse(resolved["pinned"])
                self.assertTrue(resolved["resolved"])
                self.assertEqual(resolved["status"], "resolved")
            finally:
                self._restore()

    def test_rejected_ticket_is_closed_and_unpinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._with_env()
            try:
                rt.USER_DATA_DIR = Path(tmp)
                t = rt.ticket_create({"title": "工单", "body": "内容", "module": "知识库"}, "admin")["ticket"]
                rejected = rt.ticket_add_comment({"topic_id": t["id"], "content": "暂不采纳", "status": "rejected"}, "admin")["ticket"]
                self.assertEqual(rejected["status"], "rejected")
                self.assertTrue(rejected["closed"])
                self.assertFalse(rejected["resolved"])
                self.assertFalse(rejected["pinned"])
                self.assertEqual(rt.ticket_list("admin")["summary"], {"total": 1, "open": 0, "closed": 1})
            finally:
                self._restore()

    def test_ticket_requires_and_stores_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._with_env()
            try:
                rt.USER_DATA_DIR = Path(tmp)
                with self.assertRaisesRegex(ValueError, "助手"):
                    rt.ticket_create({"title": "无模块", "body": "内容"}, "admin")
                t = rt.ticket_create({"title": "邮件问题", "body": "内容", "module": "邮件助手"}, "admin")["ticket"]
                self.assertEqual(t["module"], "邮件助手")
                self.assertEqual(rt.ticket_list("admin")["tickets"][0]["module"], "邮件助手")
            finally:
                self._restore()

    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._with_env()
            try:
                rt.USER_DATA_DIR = Path(tmp)
                forum_dir = Path(tmp) / "_forum"
                forum_dir.mkdir(parents=True)
                (forum_dir / "topics.json").write_text(json.dumps([
                    {"id": "t1", "title": "工单", "body": "x", "preset": "platform_ticket", "comments": []},
                ], ensure_ascii=False), encoding="utf-8")
                rt.ensure_tickets_migrated()
                rt.ensure_tickets_migrated()
                self.assertEqual(len(rt.load_tickets()), 1)
            finally:
                self._restore()

    def test_server_and_frontend_wire_up_the_ticket_module(self):
        server = SERVER.read_text(encoding="utf-8")
        self.assertIn('/api/tickets', server)
        self.assertIn("ticket_list(", server)
        self.assertIn("ticket_create(", server)
        self.assertIn("ticket_add_comment(", server)
        menu = MENU.read_text(encoding="utf-8")
        self.assertIn("workorder", menu)
        workspace = WORKSPACE.read_text(encoding="utf-8")
        self.assertIn("WorkOrderView", workspace)
        self.assertIn("activeMenu === 'workorder'", workspace)

    def test_workorder_entry_is_in_topbar_not_sidebar(self):
        # 工单系统是跨助手的反馈工具，入口在顶栏；不作为侧边栏导航功能项，但路由仍有效。
        menu = MENU.read_text(encoding="utf-8")
        workorder_line = next(line for line in menu.splitlines() if "id: 'workorder'" in line)
        self.assertIn("showInSidebar: false", workorder_line)
        header = (ROOT / "ai-office-assistant-web" / "src" / "layout" / "components" / "AppHeader" / "index.vue").read_text(encoding="utf-8")
        self.assertIn("emit('navigate', 'workorder')", header)
        layout = (ROOT / "ai-office-assistant-web" / "src" / "layout" / "AppLayout" / "index.vue").read_text(encoding="utf-8")
        self.assertIn("'workorder'", layout)

    def test_wide_workorder_content_remains_vertically_scrollable(self):
        """长工单页在小视口中不能由全宽布局裁掉页头的提交操作。"""
        styles = (ROOT / "ai-office-assistant-web" / "src" / "layout" / "AppLayout" / "index.scss").read_text(encoding="utf-8")
        wide_section = styles.split('.app-layout--wide {', 1)[1].split('\n}', 1)[0]
        self.assertIn('overflow-y: auto;', wide_section)

    def test_workorder_has_a_persistent_toolbar_create_action(self):
        view = WORKORDER.read_text(encoding="utf-8")
        self.assertIn('class="wo-toolbar-create"', view)
        self.assertIn('>新建工单</el-button>', view)

    def test_pending_ticket_images_render_as_thumbnails(self):
        view = WORKORDER.read_text(encoding="utf-8")
        self.assertGreaterEqual(view.count('v-if="a.is_image"'), 4)
        self.assertIn('点击查看原图', view)

    def test_workorder_description_and_reply_accept_pasted_images(self):
        view = WORKORDER.read_text(encoding="utf-8")
        self.assertIn("function clipboardImageFiles", view)
        self.assertIn('@paste="handleCreatePaste"', view)
        self.assertIn('@paste="handleReplyPaste"', view)
        self.assertIn("uploadTicketAttachment(file)", view)


if __name__ == "__main__":
    unittest.main()
