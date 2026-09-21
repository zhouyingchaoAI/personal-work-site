import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SRC = ROOT / "ai-office-assistant-web" / "src"
MENU = WEB_SRC / "layout" / "menu.ts"
NAV_PREFS = WEB_SRC / "layout" / "navPrefs.ts"
SIDEBAR = WEB_SRC / "layout" / "components" / "AppSidebar" / "index.vue"
LAYOUT_STYLES = WEB_SRC / "layout" / "AppLayout" / "index.scss"
CENTER_VIEW = WEB_SRC / "views" / "AssistantCenterView" / "index.vue"
WORKSPACE_VIEW = WEB_SRC / "views" / "WorkspaceView" / "index.vue"
APP_HEADER = WEB_SRC / "layout" / "components" / "AppHeader" / "index.vue"
API = WEB_SRC / "services" / "personalWorkApi.ts"
BACKGROUND_TASKS = WEB_SRC / "utils" / "backgroundTasks.ts"
SERVER = ROOT / "backend" / "server.py"


class AssistantCenterFrontendTests(unittest.TestCase):
    def test_menu_declares_assistant_center_and_customizable_catalog(self):
        source = MENU.read_text(encoding="utf-8")
        self.assertIn("'assistants'", source)
        self.assertIn("label: '助手中心'", source)
        self.assertIn("export function customizableMenuItems", source)
        self.assertIn("export const assistantCategories", source)
        # 目录卡片需要每个助手的说明与分类
        self.assertIn("description:", source)
        self.assertIn("category:", source)

    def test_nav_prefs_store_supports_order_hide_and_reset(self):
        source = NAV_PREFS.read_text(encoding="utf-8")
        self.assertIn("export function applyNavPrefs", source)
        self.assertIn("export function reorderVisibleAssistants", source)
        self.assertIn("export function hideAssistant", source)
        self.assertIn("export function showAssistant", source)
        self.assertIn("export function resetNavPrefs", source)
        self.assertIn("saveNavPrefs", source)

    def test_sidebar_supports_drag_sorting_with_insert_line_feedback(self):
        source = SIDEBAR.read_text(encoding="utf-8")
        self.assertIn(':draggable="canDrag(item)"', source)
        self.assertIn("handleNavDragStart", source)
        self.assertIn("handleNavDragOver", source)
        self.assertIn("handleNavDrop", source)
        self.assertIn("'nav-item--drop-before'", source)
        self.assertIn("'nav-item--drop-after'", source)
        self.assertIn("emit('reorder', ids)", source)

    def test_mobile_navigation_has_a_touch_toggle_drawer_and_closes_after_selection(self):
        sidebar = SIDEBAR.read_text(encoding="utf-8")
        styles = LAYOUT_STYLES.read_text(encoding="utf-8")
        self.assertIn("mobileOpen", sidebar)
        self.assertIn("mobile-nav-toggle", sidebar)
        self.assertIn("mobile-nav-backdrop", sidebar)
        self.assertIn("mobile-sidebar-close", sidebar)
        self.assertIn("else if (!wasMobileViewport) mobileOpen.value = true", sidebar)
        self.assertIn("mobileOpen.value = false", sidebar)
        self.assertIn("transform: translateX", styles)
        self.assertIn("&.is-mobile-open", styles)

    def test_assistant_center_view_offers_add_hide_open_and_sorting(self):
        source = CENTER_VIEW.read_text(encoding="utf-8")
        self.assertIn("添加到导航", source)
        self.assertIn("暂时隐藏", source)
        self.assertIn("恢复默认", source)
        self.assertIn("handleRowDrop", source)
        self.assertIn("'drop-before'", source)
        self.assertIn("openAssistant", source)
        self.assertIn("智能体工厂", source)

    def test_hidden_assistants_are_listed_beside_my_nav_for_re_adding(self):
        # 隐藏的助手必须紧挨「我的导航」就地展示添加入口，不能只藏在页面底部的目录卡片里
        source = CENTER_VIEW.read_text(encoding="utf-8")
        self.assertIn("已隐藏的助手", source)
        self.assertIn('v-if="hiddenItems.length"', source)
        self.assertIn("assistant-center__hidden-block", source)

    def test_workspace_applies_prefs_and_renders_assistant_center(self):
        source = WORKSPACE_VIEW.read_text(encoding="utf-8")
        self.assertIn("applyNavPrefs(visibleMenuItems(user.value))", source)
        self.assertIn("loadNavPrefs()", source)
        self.assertIn("AssistantCenterView", source)
        self.assertIn("handleNavReorder", source)

    def test_workspace_keeps_visited_assistants_alive_when_switching_pages(self):
        source = WORKSPACE_VIEW.read_text(encoding="utf-8")
        self.assertIn("<KeepAlive>", source)
        for component in ["WeeklyReportView", "TripReportView", "DiaryView", "WritingAssistantView", "KnowledgeBaseView", "ReimbursementView"]:
            self.assertIn(f"<{component} v-if=", source)
            self.assertNotIn(f"<{component} v-else-if=", source)

    def test_active_operations_remain_visible_in_the_global_header(self):
        tasks = BACKGROUND_TASKS.read_text(encoding="utf-8")
        header = APP_HEADER.read_text(encoding="utf-8")
        api = API.read_text(encoding="utf-8")
        self.assertIn("beginBackgroundTask", tasks)
        self.assertIn("finishBackgroundTask", tasks)
        self.assertIn("activeBackgroundTaskCount", header)
        self.assertIn("切换页面不会中断这些任务", header)
        self.assertIn("beginBackgroundTask(label)", api)
        self.assertIn("finishBackgroundTask(taskId)", api)

    def test_backend_exposes_nav_prefs_routes(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn('if parsed.path == "/api/nav-prefs":', source)
        self.assertIn('elif parsed.path == "/api/nav-prefs":', source)
        self.assertIn("save_nav_prefs(payload, username)", source)


if __name__ == "__main__":
    unittest.main()
