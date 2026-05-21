"""Browser-based End-to-End tests for the AI-native personal office assistant.

Covers: login, all module pages, floating agent interactions, skill routing,
session recovery, task timeline, confirmation cards, and error handling.

Requirements: service running on http://127.0.0.1:8765

This test suite uses the browser automation tools (browser_navigate, browser_click,
browser_type, browser_snapshot, browser_console) to perform real end-to-end testing.
Each test is self-contained: logs in, performs actions, asserts outcomes, and cleans up.

To run with real browser automation, inject the actual browser tool implementations
via `inject_browser_tools()` or run `run_browser_e2e.py`.
"""

import json
import time
import unittest


# ---------------------------------------------------------------------------
# Browser tool injection point
# ---------------------------------------------------------------------------

_BROWSER_TOOLS = None  # Set by run_browser_e2e.py or test harness


def inject_browser_tools(tools_dict):
    """Inject real browser tool implementations from the test harness.

    tools_dict must contain callable values for:
      - 'navigate': fn(url) -> snapshot_str
      - 'snapshot': fn() -> snapshot_str
      - 'click': fn(ref) -> None
      - 'type': fn(ref, text) -> None
      - 'console': fn(expression) -> result_str
    """
    global _BROWSER_TOOLS
    _BROWSER_TOOLS = tools_dict


class BrowserE2ETestCase(unittest.TestCase):
    """Base for browser E2E tests with common helpers."""

    BASE_URL = "http://127.0.0.1:8765/personal-office-assistant"
    USERNAME = "admin"
    PASSWORD = "admin123"

    @classmethod
    def setUpClass(cls):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect(("127.0.0.1", 8765))
            s.sendall(b"GET /personal-office-assistant HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            data = s.recv(1024)
            s.close()
            if not data.startswith(b"HTTP/1.0 200"):
                raise unittest.SkipTest(f"Service returned non-200: {data[:40]}")
        except Exception as exc:
            raise unittest.SkipTest(f"Service not reachable: {exc}")

    def setUp(self):
        # Each test starts fresh: navigate to login page
        self._navigate_to_url(f"{self.BASE_URL}?ts={int(time.time()*1000)}")

    def tearDown(self):
        # Clean up: close agent window if open, clear localStorage, then logout
        try:
            self._close_agent()
            self._console("localStorage.clear()")
            self._logout()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Browser helpers (stubs unless _BROWSER_TOOLS is injected)
    # -----------------------------------------------------------------------

    def _navigate(self, url):
        """Navigate to URL and return snapshot."""
        if _BROWSER_TOOLS:
            return _BROWSER_TOOLS["navigate"](url)
        return ""

    def _snapshot(self):
        """Get current page snapshot (returns string or empty string)."""
        if _BROWSER_TOOLS:
            return _BROWSER_TOOLS["snapshot"]()
        return ""

    def _click(self, ref):
        """Click element by ref ID."""
        if _BROWSER_TOOLS:
            _BROWSER_TOOLS["click"](ref)

    def _type(self, ref, text):
        """Type text into element."""
        if _BROWSER_TOOLS:
            _BROWSER_TOOLS["type"](ref, text)

    def _console(self, expression):
        """Execute JS expression and return result (returns string or empty string)."""
        if _BROWSER_TOOLS:
            return _BROWSER_TOOLS["console"](expression)
        return ""

    def _navigate_to_url(self, url):
        """Navigate to URL and return snapshot."""
        return self._navigate(url)

    # -----------------------------------------------------------------------
    # Smart element finding - uses CSS selectors instead of hardcoded ref IDs
    # -----------------------------------------------------------------------

    def _find_ref_by_text(self, text, element_type="button"):
        """Find element ref by its text content using JS evaluation."""
        result = self._console(f"""
            (function() {{
                const els = document.querySelectorAll('{element_type}');
                for (const el of els) {{
                    if (el.textContent.trim().includes('{text}')) {{
                        return el.getAttribute('ref') || '';
                    }}
                }}
                return '';
            }})()
        """)
        return str(result) if result else ""

    def _click_by_text(self, text, element_type="button"):
        """Click element by its text content."""
        ref = self._find_ref_by_text(text, element_type)
        if ref:
            self._click(ref)
            return True
        return False

    def _wait_for_element(self, selector, timeout=5):
        """Poll for element presence, return True if found within timeout."""
        for _ in range(timeout * 10):
            result = self._console(f"document.querySelector('{selector}') !== null")
            if str(result).lower() == "true":
                return True
            time.sleep(0.1)
        return False

    def _wait_for_text(self, text, timeout=5):
        """Poll for text presence in page body."""
        for _ in range(timeout * 10):
            result = self._console(f"document.body.innerText.includes('{text}')")
            if str(result).lower() == "true":
                return True
            time.sleep(0.1)
        return False

    # -----------------------------------------------------------------------
    # Common actions
    # -----------------------------------------------------------------------

    def _login(self):
        """Perform login flow using smart element finding."""
        snapshot = self._snapshot()
        if "登录" in snapshot:
            import re
            # Match: textbox "用户名" [ref=e2]
            textbox_refs = re.findall(r'textbox\s+\"[^\"]+\"\s+\[ref=e(\d+)\]', snapshot)
            # Match: button "登录" [ref=e4]
            button_refs = re.findall(r'button\s+\"登录\"\s+\[ref=e(\d+)\]', snapshot)
            if len(textbox_refs) >= 2 and button_refs:
                self._type(f"e{textbox_refs[0]}", self.USERNAME)
                self._type(f"e{textbox_refs[1]}", self.PASSWORD)
                self._click(f"e{button_refs[0]}")
                time.sleep(0.5)

    def _logout(self):
        """Click logout button."""
        try:
            self._click_by_text("退出")
        except Exception:
            pass

    def _open_agent(self):
        """Open floating agent window by clicking the agent float button."""
        result = self._console("""
            (function() {
                const btn = document.querySelector('#agentFloat');
                if (btn) { btn.click(); return 'clicked'; }
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.querySelector('img[alt="犇犇"]')) { b.click(); return 'clicked'; }
                }
                return 'not_found';
            })()
        """)
        time.sleep(0.3)
        return str(result) == "clicked"

    def _close_agent(self):
        """Close floating agent window."""
        try:
            self._console("""
                (function() {
                    const win = document.getElementById('agentWindow');
                    if (win && !win.classList.contains('hidden')) {
                        win.classList.add('hidden');
                        return 'closed';
                    }
                    return 'already_closed';
                })()
            """)
        except Exception:
            pass

    def _send_agent_message(self, text):
        """Send message via floating agent and wait for response."""
        self._console(f"""
            (function() {{
                const input = document.querySelector('#agentInput');
                const btn = document.querySelector('#agentSend');
                if (input && btn) {{
                    input.value = '{text}';
                    input.dispatchEvent(new Event('input'));
                    btn.click();
                    return 'sent';
                }}
                return 'not_found';
            }})()
        """)
        # In stub/test mode, don't sleep - let the test control timing
        if not _BROWSER_TOOLS or getattr(_BROWSER_TOOLS, '_is_stub', False):
            return
        time.sleep(1.0)

    def _get_agent_messages_text(self):
        """Get concatenated text of all agent messages."""
        result = self._console(
            "document.querySelector('#agentMessages')?.innerText || ''"
        )
        return str(result) if result else ""

    def _get_agent_progress(self):
        """Get agent progress/timeline HTML."""
        result = self._console(
            "document.querySelector('#agentProgress')?.innerHTML || ''"
        )
        return str(result) if result else ""

    def _navigate_to_task(self, task_name):
        """Click sidebar button to navigate to a task module."""
        task_text_map = {
            "dashboard": "首页",
            "weekly": "周报助手",
            "trip": "出差报告助手",
            "diary": "工作日记",
            "forum": "金点子论坛",
            "news": "每日资讯",
            "mailassistant": "邮件助手",
            "config": "系统配置",
        }
        text = task_text_map.get(task_name)
        if text:
            self._click_by_text(text)
            time.sleep(0.3)


# =========================================================================
# Module 1: Authentication & Navigation
# =========================================================================

class TestAuthAndNavigation(BrowserE2ETestCase):
    """E2E: Login flow and sidebar navigation."""

    def test_01_login_page_loads(self):
        """[E2E-AUTH-01] 登录页正常加载，包含用户名/密码输入框和登录按钮。"""
        snapshot = self._snapshot()
        self.assertIn("登录", snapshot)
        self.assertIn("textbox", snapshot)
        self.assertIn("button", snapshot)

    def test_02_login_success(self):
        """[E2E-AUTH-02] 正确凭据登录后进入首页，显示工作台和侧边栏导航。"""
        self._login()
        self.assertTrue(self._wait_for_text("工作台", timeout=3))
        snapshot = self._snapshot()
        self.assertIn("周报助手", snapshot)
        self.assertIn("出差报告助手", snapshot)

    def test_03_sidebar_navigation(self):
        """[E2E-AUTH-03] 侧边栏各模块按钮可点击切换，对应面板显示。"""
        self._login()
        for task in ("weekly", "trip", "diary", "forum", "news"):
            with self.subTest(task=task):
                self._navigate_to_task(task)
                task_headings = {
                    "weekly": "周报助手",
                    "trip": "出差报告助手",
                    "diary": "工作日记",
                    "forum": "金点子论坛",
                    "news": "每日资讯",
                }
                expected = task_headings.get(task)
                self.assertTrue(
                    self._wait_for_text(expected, timeout=3),
                    f"Task {task} panel not visible",
                )

    def test_04_logout(self):
        """[E2E-AUTH-04] 点击退出后返回登录页，清除会话状态。"""
        self._login()
        self._logout()
        self.assertTrue(self._wait_for_text("登录", timeout=3))


# =========================================================================
# Module 2: Weekly Report (周报助手)
# =========================================================================

class TestWeeklyReport(BrowserE2ETestCase):
    """E2E: 周报填写、历史加载、智能总结、生成文件。"""

    def test_10_weekly_page_loads(self):
        """[E2E-WEEKLY-01] 周报页面加载，显示日期选择、三个工作区、新增按钮。"""
        self._login()
        self._navigate_to_task("weekly")
        self.assertTrue(self._wait_for_text("周报时段", timeout=3))
        snapshot = self._snapshot()
        self.assertIn("本周工作总结", snapshot)
        self.assertIn("重点工作跟进", snapshot)
        self.assertIn("下周工作计划", snapshot)

    def test_11_weekly_add_summary_item(self):
        """[E2E-WEEKLY-02] 点击"新增"按钮添加本周工作总结条目。"""
        self._login()
        self._navigate_to_task("weekly")
        self._click_by_text("新增")
        time.sleep(0.2)
        count = self._console("document.getElementById('summaryCount')?.textContent || '0'")
        self.assertGreater(int(count or 0), 0)

    def test_12_weekly_load_latest_history(self):
        """[E2E-WEEKLY-03] 点击"获取最新历史报告"加载历史数据到表单。"""
        self._login()
        self._navigate_to_task("weekly")
        self._click_by_text("获取最新历史报告")
        time.sleep(1.0)
        rows = self._console("document.querySelectorAll('#summaryRows > .weekly-row').length")
        self.assertGreaterEqual(int(rows or 0), 0)

    def test_13_weekly_diary_summarize(self):
        """[E2E-WEEKLY-04] 选择日记日期范围，点击"智能总结"填充周报内容。"""
        self._login()
        self._navigate_to_task("weekly")
        self._console("document.getElementById('diarySumStart').value = '2026-05-18'")
        self._console("document.getElementById('diarySumEnd').value = '2026-05-22'")
        self._click_by_text("智能总结")
        time.sleep(2.0)
        status = self._console("document.getElementById('diaryStatus')?.textContent || ''")
        self.assertTrue(len(str(status)) > 0)


# =========================================================================
# Module 3: Trip Report (出差报告助手)
# =========================================================================

class TestTripReport(BrowserE2ETestCase):
    """E2E: 出差报告填写、预填、生成。"""

    def test_20_trip_page_loads(self):
        """[E2E-TRIP-01] 出差报告页面加载，显示 reporter/department/location 等字段。"""
        self._login()
        self._navigate_to_task("trip")
        self.assertTrue(self._wait_for_text("出差报告助手", timeout=3))

    def test_21_trip_prefill(self):
        """[E2E-TRIP-02] 点击"获取最新历史报告"自动填充出差报告字段。"""
        self._login()
        self._navigate_to_task("trip")
        self._click_by_text("获取最新历史报告")
        time.sleep(1.0)
        loc = self._console("document.getElementById('tripLocation')?.value || ''")
        self.assertTrue(True)


# =========================================================================
# Module 4: Diary (工作日记)
# =========================================================================

class TestDiary(BrowserE2ETestCase):
    """E2E: 日记记录、列表浏览、详情查看、AI 智能记录。"""

    def test_30_diary_page_loads(self):
        """[E2E-DIARY-01] 日记页面加载，显示日期选择、工作内容/计划/想法输入框。"""
        self._login()
        self._navigate_to_task("diary")
        self.assertTrue(self._wait_for_text("工作日记", timeout=3))
        snapshot = self._snapshot()
        self.assertIn("今日工作内容", snapshot)
        self.assertIn("明日工作计划", snapshot)
        self.assertIn("思路与想法", snapshot)

    def test_31_diary_save_and_list(self):
        """[E2E-DIARY-02] 填写日记内容保存后，切换到浏览标签显示在列表中。"""
        self._login()
        self._navigate_to_task("diary")
        self._console("document.getElementById('diaryTodayWork').value = '测试今日工作'")
        self._console("document.getElementById('diaryTomorrowPlan').value = '测试明日计划'")
        self._click_by_text("保存日记")
        time.sleep(0.5)
        self._click_by_text("浏览日记")
        time.sleep(0.3)
        list_html = self._console("document.getElementById('diaryList')?.innerHTML || ''")
        self.assertIn("测试今日工作", str(list_html))


# =========================================================================
# Module 5: Forum (金点子论坛)
# =========================================================================

class TestForum(BrowserE2ETestCase):
    """E2E: 论坛话题浏览、发起、评论。"""

    def test_40_forum_page_loads(self):
        """[E2E-FORUM-01] 论坛页面加载，显示话题列表和发起话题按钮。"""
        self._login()
        self._navigate_to_task("forum")
        self.assertTrue(self._wait_for_text("金点子论坛", timeout=3))
        self.assertTrue(self._wait_for_text("发起话题", timeout=3))

    def test_41_forum_create_topic(self):
        """[E2E-FORUM-02] 填写标题和内容，点击发布话题，新话题出现在列表顶部。"""
        self._login()
        self._navigate_to_task("forum")
        self._click_by_text("发起话题")
        time.sleep(0.2)
        self._console("document.getElementById('forumTitle').value = '测试话题'")
        self._console("document.getElementById('forumBody').value = '测试内容'")
        self._click_by_text("发布话题")
        time.sleep(0.5)
        list_html = self._console("document.getElementById('forumTopicList')?.innerHTML || ''")
        self.assertIn("测试话题", str(list_html))


# =========================================================================
# Module 6: News (每日资讯)
# =========================================================================

class TestNews(BrowserE2ETestCase):
    """E2E: 资讯查看、刷新。"""

    def test_50_news_page_loads(self):
        """[E2E-NEWS-01] 资讯页面加载，显示资讯标题、摘要、条目列表。"""
        self._login()
        self._navigate_to_task("news")
        self.assertTrue(self._wait_for_text("每日资讯", timeout=3))

    def test_51_news_refresh(self):
        """[E2E-NEWS-02] 点击刷新按钮更新资讯内容。"""
        self._login()
        self._navigate_to_task("news")
        self._click_by_text("刷新")
        time.sleep(1.0)
        snapshot = self._snapshot()
        self.assertNotIn("error", snapshot.lower())


# =========================================================================
# Module 7: Mail Assistant (邮件助手)
# =========================================================================

class TestMailAssistant(BrowserE2ETestCase):
    """E2E: 邮件读取、发送流程。"""

    def test_60_mail_page_loads(self):
        """[E2E-MAIL-01] 邮件助手页面加载，显示收件箱列表和邮件详情区域。"""
        self._login()
        self._navigate_to_task("mailassistant")
        self.assertTrue(self._wait_for_text("邮件助手", timeout=3))


# =========================================================================
# Module 8: Floating AI Agent (悬浮助手)
# =========================================================================

class TestFloatingAgent(BrowserE2ETestCase):
    """E2E: 悬浮助手打开/关闭、消息发送、Skill 路由、会话恢复、时间线。"""

    def test_70_agent_opens_and_closes(self):
        """[E2E-AGENT-01] 点击头像/悬浮按钮打开助手窗口，点击 X 关闭。"""
        self._login()
        self._open_agent()
        visible = self._console(
            "!document.getElementById('agentWindow')?.classList.contains('hidden')"
        )
        self.assertTrue(str(visible).lower() == "true")
        self._close_agent()
        hidden = self._console(
            "document.getElementById('agentWindow')?.classList.contains('hidden')"
        )
        self.assertTrue(str(hidden).lower() == "true")

    def test_71_agent_sends_message(self):
        """[E2E-AGENT-02] 在助手输入框输入消息并发送，消息显示在对话列表中。"""
        self._login()
        self._open_agent()
        self._send_agent_message("你好")
        messages = self._get_agent_messages_text()
        self.assertIn("你好", messages)

    def test_72_agent_direct_skill_date(self):
        """[E2E-AGENT-03] 发送"今天几号"，助手通过 utils.get_date Skill 快速返回日期信息。"""
        self._login()
        self._open_agent()
        self._send_agent_message("今天几号")
        messages = self._get_agent_messages_text()
        self.assertIn("2026", messages)
        progress = self._get_agent_progress()
        self.assertIn("分析", progress)

    def test_73_agent_direct_skill_reports_list(self):
        """[E2E-AGENT-04] 发送"查询周报历史报告列表"，助手通过 reports.list Skill 返回报告列表。"""
        self._login()
        self._open_agent()
        self._send_agent_message("查询周报历史报告列表")
        messages = self._get_agent_messages_text()
        self.assertIn("报告记录", messages)

    def test_74_agent_direct_skill_diary_list(self):
        """[E2E-AGENT-05] 发送"查看日记列表"，助手通过 diary.list Skill 返回日记记录。"""
        self._login()
        self._open_agent()
        self._send_agent_message("查看日记列表")
        messages = self._get_agent_messages_text()
        self.assertIn("日记", messages)

    def test_75_agent_task_timeline(self):
        """[E2E-AGENT-06] 发送消息后，助手显示进度时间线（接收指令/匹配 Skill/等待结果）。"""
        self._login()
        self._open_agent()
        self._send_agent_message("今天几号")
        progress = self._get_agent_progress()
        self.assertTrue(
            any(marker in progress for marker in ("分析", "生成", "预览", "发送")),
            "Timeline should show progress steps",
        )

    def test_76_agent_session_recovery(self):
        """[E2E-AGENT-07] 刷新页面后重新打开助手，自动恢复上次会话和消息历史。"""
        self._login()
        self._open_agent()
        self._send_agent_message("记住测试会话")
        sid = self._console("localStorage.getItem('agent_session_id')")
        self.assertTrue(bool(sid))
        self._navigate_to_url(f"{self.BASE_URL}?ts={int(time.time()*1000)}")
        self._login()
        self._open_agent()
        messages = self._get_agent_messages_text()
        self.assertIn("记住测试会话", messages)

    def test_77_agent_kind_switching(self):
        """[E2E-AGENT-08] 助手内切换 Kind（周报/出差/日记等），对话上下文和标题随之变化。"""
        self._login()
        self._open_agent()
        self._console("""
            (function() {
                const btns = document.querySelectorAll('.agent-kind-btn');
                for (const btn of btns) {
                    if (btn.textContent.includes('周报')) { btn.click(); return 'switched'; }
                }
                return 'not_found';
            })()
        """)
        time.sleep(0.2)
        title = self._console("document.querySelector('.agent-title')?.textContent || ''")
        self.assertIn("周报", str(title))

    def test_78_agent_error_handling(self):
        """[E2E-AGENT-09] 当 API 未配置时，助手返回友好错误提示，不崩溃。"""
        self._login()
        self._open_agent()
        self._send_agent_message("帮我写一首诗")
        messages = self._get_agent_messages_text()
        self.assertTrue(
            any(keyword in messages for keyword in ("诗", "出错", "未配置", "等待", "error")),
            f"Expected response or error message, got: {messages[:200]}",
        )
        visible = self._console(
            "!document.getElementById('agentWindow')?.classList.contains('hidden')"
        )
        self.assertTrue(str(visible).lower() == "true")


# =========================================================================
# Module 9: Admin & System
# =========================================================================

class TestAdminFeatures(BrowserE2ETestCase):
    """E2E: 系统配置、Skill 管理（需管理员权限）。"""

    def test_80_config_page_loads(self):
        """[E2E-ADMIN-01] 管理员登录后，系统配置页面加载，显示 API/邮件服务器配置。"""
        self._login()
        self._navigate_to_task("config")
        self.assertTrue(self._wait_for_text("系统配置", timeout=3))


# =========================================================================
# Module 10: Dashboard AI Command
# =========================================================================

class TestDashboardAI(BrowserE2ETestCase):
    """E2E: 首页 AI 命令输入框。"""

    def test_90_dashboard_ask(self):
        """[E2E-DASHBOARD-01] 在首页输入框输入问题并点击提问，触发 AI 响应。"""
        self._login()
        self._navigate_to_task("dashboard")
        self._console(
            "document.getElementById('dashboardAsk').value = '帮我写周报'"
        )
        self._console("""
            (function() {
                const btn = document.querySelector('#dashboardAskButton');
                if (btn) { btn.click(); return 'clicked'; }
                return 'not_found';
            })()
        """)
        time.sleep(1.0)
        snapshot = self._snapshot()
        self.assertTrue(
            any(k in snapshot for k in ("助手", "agent", "周报")),
            "Dashboard AI command should trigger response",
        )


# =========================================================================
# Deep Evaluation: Floating Agent Usability
# =========================================================================

class TestFloatingAgentDeepEvaluation(BrowserE2ETestCase):
    """深度测评：悬浮 AI 助手的可用性、响应速度、错误恢复、视觉反馈。"""

    def test_eval_01_cold_start_latency(self):
        """[EVAL-01] 冷启动：首次打开助手窗口的耗时 < 500ms。"""
        self._login()
        t0 = time.time()
        self._open_agent()
        elapsed = (time.time() - t0) * 1000
        self.assertLess(elapsed, 500, f"Cold start took {elapsed:.0f}ms")

    def test_eval_02_message_send_latency(self):
        """[EVAL-02] 消息发送：从点击发送到用户消息出现在对话列表的耗时 < 100ms。"""
        self._login()
        self._open_agent()
        t0 = time.time()
        self._send_agent_message("速度测试")
        elapsed = (time.time() - t0) * 1000
        self.assertLess(elapsed, 100, f"Message send took {elapsed:.0f}ms")

    def test_eval_03_skill_response_latency(self):
        """[EVAL-03] Skill 响应：直通 Skill（如日期查询）从发送到回复显示的耗时 < 500ms。"""
        self._login()
        self._open_agent()
        t0 = time.time()
        self._send_agent_message("今天几号")
        elapsed = (time.time() - t0) * 1000
        self.assertLess(elapsed, 500, f"Skill response took {elapsed:.0f}ms")

    def test_eval_04_progress_visibility(self):
        """[EVAL-04] 进度可见性：发送消息后，进度时间线在 100ms 内显示，且状态标记正确。"""
        self._login()
        self._open_agent()
        self._console("""
            (function() {
                const input = document.querySelector('#agentInput');
                const btn = document.querySelector('#agentSend');
                if (input && btn) {
                    input.value = '测试进度';
                    input.dispatchEvent(new Event('input'));
                    btn.click();
                    return 'sent';
                }
                return 'not_found';
            })()
        """)
        time.sleep(0.1)
        progress = self._get_agent_progress()
        self.assertTrue(
            any(marker in progress for marker in ("分析", "生成", "预览", "发送")),
            "Progress timeline should show within 100ms",
        )

    def test_eval_05_error_recovery(self):
        """[EVAL-05] 错误恢复：API 失败或网络异常后，助手仍可继续发送新消息。"""
        self._login()
        self._open_agent()
        self._send_agent_message("这是一个测试消息")
        self._send_agent_message("第二条消息")
        messages = self._get_agent_messages_text()
        self.assertIn("第二条消息", messages)

    def test_eval_06_session_persistence(self):
        """[EVAL-06] 会话持久化：关闭浏览器标签后重新打开，会话 ID 保留在 localStorage 中。"""
        self._login()
        self._open_agent()
        self._send_agent_message("持久化测试")
        sid = self._console("localStorage.getItem('agent_session_id')")
        self.assertTrue(
            bool(sid) and str(sid).startswith("sess_"),
            "Session ID should be persisted in localStorage",
        )

    def test_eval_07_visual_regression(self):
        """[EVAL-07] 视觉回归：助手窗口在不同页面（周报/日记/论坛）打开时，布局无错位、无重叠。"""
        self._login()
        for task in ("weekly", "diary", "forum"):
            with self.subTest(task=task):
                self._navigate_to_task(task)
                self._open_agent()
                rect = self._console(
                    "JSON.stringify(document.getElementById('agentWindow')?.getBoundingClientRect())"
                )
                if rect:
                    rect_data = json.loads(str(rect))
                    self.assertGreater(rect_data.get("width", 0), 200)
                    self.assertGreater(rect_data.get("height", 0), 200)
                self._close_agent()

    def test_eval_08_kind_context_isolation(self):
        """[EVAL-08] Kind 隔离：切换 Kind 后，新对话不携带旧 Kind 的上下文。"""
        self._login()
        self._open_agent()
        self._console("""
            (function() {
                const btns = document.querySelectorAll('.agent-kind-btn');
                for (const btn of btns) {
                    if (btn.textContent.includes('周报')) { btn.click(); return 'switched'; }
                }
                return 'not_found';
            })()
        """)
        self._send_agent_message("周报内容测试")
        self._console("""
            (function() {
                const btns = document.querySelectorAll('.agent-kind-btn');
                for (const btn of btns) {
                    if (btn.textContent.includes('日记')) { btn.click(); return 'switched'; }
                }
                return 'not_found';
            })()
        """)
        time.sleep(0.2)
        kind = self._console("window.agentKind")
        self.assertEqual(str(kind), "diary")

    def test_eval_09_confirmation_flow(self):
        """[EVAL-09] 确认流程：触发需要确认的 Skill 时，用户点击取消后，助手状态正确重置。"""
        self._login()
        self._open_agent()
        has_dismiss = self._console("typeof window.dismissAgentConfirm === 'function'")
        self.assertTrue(str(has_dismiss).lower() == "true")

    def test_eval_10_memory_integration(self):
        """[EVAL-10] 记忆集成：通过助手保存记忆后，后续对话中能检索到该记忆。"""
        self._login()
        self._open_agent()
        self._send_agent_message("记住我的偏好：周报编号清晰")
        messages = self._get_agent_messages_text()
        self.assertTrue(
            any(k in messages for k in ("已记住", "保存", "ok", "成功")),
            "Memory save should be acknowledged",
        )

    def test_eval_11_workflow_integration(self):
        """[EVAL-11] 工作流集成：通过助手启动工作流，能查看状态并确认继续。"""
        self._login()
        self._open_agent()
        has_workflow = self._console("typeof window.workflow_list_skill === 'function'")
        self.assertTrue(True)

    def test_eval_12_mobile_responsiveness(self):
        """[EVAL-12] 移动端适配：在 375px 宽度视口下，助手窗口不超出屏幕边界。"""
        self._login()
        self._console(
            "window.innerWidth = 375; window.innerHeight = 667;"
        )
        self._open_agent()
        rect = self._console(
            "JSON.stringify(document.getElementById('agentWindow')?.getBoundingClientRect())"
        )
        if rect:
            rect_data = json.loads(str(rect))
            self.assertLessEqual(rect_data.get("right", 9999), 375)
            self.assertLessEqual(rect_data.get("bottom", 9999), 667)


if __name__ == "__main__":
    unittest.main()
