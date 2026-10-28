"""数据中台新版界面验收（只读，对本机运行中的服务执行；结束后撤销测试会话）。

覆盖：头部对象下拉 + 单一操作菜单、KPI 条、7 个细页签、数据库页签内的实例/流向切换、
助手入库进度点击进入存储对应、专项视角与返回全局。截图写到参数目录。
"""
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def container_python(source):
    return subprocess.check_output(['docker', 'exec', '-i', 'personal-work-site', 'python', '-'],
                                   input=source, text=True).strip()


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    token = container_python("from backend import runtime as runtime\n"
                             "user = next(user for user in runtime.read_config()['users'] if user.get('role') == 'superadmin')\n"
                             "print(runtime.create_login_session(user))\n")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1600, 'height': 1150})
            base = 'http://127.0.0.1:8765'
            context.add_cookies([{'name': 'pws_session', 'value': token, 'url': base}])
            page = context.new_page()
            errors, failures = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: failures.append((response.status, response.url.split('?')[0]))
                    if response.status >= 400 and '/api/datacenter/' in response.url else None)
            page.goto(base + '/workspace/datacenter')
            expect(page.locator('.dc-kpis .dc-kpi')).to_have_count(4, timeout=30000)
            expect(page.locator('.dc-tabs button')).to_have_count(7)
            expect(page.locator('[data-status-owner]')).to_have_count(18, timeout=30000)
            expect(page.locator('.dc-levels')).to_be_visible()
            # 头部只保留一个操作入口
            expect(page.locator('.dc-head__tools .el-button')).to_have_count(1)
            page.locator('[data-testid="dc-actions"]').click()
            expect(page.get_by_role('menuitem', name='备份整个平台')).to_be_visible()
            page.keyboard.press('Escape')
            page.screenshot(path=str(output / 'overview.png'))

            # 助手 ↔ 数据库关联图：上排助手、下排实例；点助手高亮并列出库，点库出相关表；点库反查助手
            graph = page.locator('[data-testid="dc-graph"]')
            expect(graph.locator('[data-graph-assistant]')).to_have_count(22, timeout=30000)
            expect(graph.locator('[data-graph-instance]')).to_have_count(17)
            top = graph.locator('[data-graph-assistant="crm"] rect').bounding_box()
            bottom = graph.locator('[data-graph-instance="office-postgres"] rect').first.bounding_box()
            assert top['y'] < bottom['y'], '助手应在上、数据库在下'
            graph.locator('[data-graph-assistant="crm"]').click()
            expect(graph.locator('[data-testid="rg-panel"]')).to_contain_text('联指经营助手')
            expect(graph.locator('[data-graph-instance="office-postgres"]')).to_have_class(re.compile(r'related'))
            graph.locator('[data-graph-instance="office-postgres"]').click()
            expect(graph.locator('.rg-tab-item').first).to_be_visible(timeout=30000)
            expect(graph.locator('.rg-tab-item')).to_contain_text(['crm.'])
            graph.screenshot(path=str(output / 'graph-crm.png'))
            graph.locator('[data-graph-assistant="crm"]').click()  # 取消
            graph.locator('[data-graph-instance="fastgpt-redis"]').click()
            expect(graph.locator('[data-testid="rg-panel"]')).to_contain_text('使用「')
            graph.screenshot(path=str(output / 'graph-instance.png'))
            graph.locator('[data-graph-instance="fastgpt-redis"]').click()  # 取消

            def tab(key):
                page.locator(f'.dc-tabs button[data-tab="{key}"]').click()

            # 入库进度点击进入存储对应（专项视角）
            page.locator('[data-status-owner="crm"]').click()
            expect(page.locator('[data-testid="dc-scope"]')).to_contain_text('联指经营助手')
            expect(page.locator('.storage-group')).to_have_count(1, timeout=20000)
            expect(page.locator('.storage-badge.database')).to_have_count(9)
            page.screenshot(path=str(output / 'crm-storage.png'))
            page.locator('[data-testid="dc-scope"] button').click()
            expect(page.locator('[data-testid="dc-scope"]')).to_have_count(0)

            for key in ('dashboard', 'browse', 'api'):
                tab(key)
                page.wait_for_timeout(1500)
                page.screenshot(path=str(output / f'{key}.png'))
            tab('databases')
            expect(page.locator('.dbx-inst')).to_have_count(17, timeout=20000)
            page.locator('.dc-switch button').nth(1).click()
            expect(page.locator('.fl-summary')).to_be_visible(timeout=20000)
            page.screenshot(path=str(output / 'dataflow.png'))
            tab('ops')
            expect(page.locator('.dc-banner')).to_be_visible()
            expect(page.locator('.dc-copies .dc-copy')).to_have_count(3)
            page.screenshot(path=str(output / 'ops.png'))

            # 下拉选择平台本身
            page.locator('[data-testid="dc-subject-select"]').click()
            page.get_by_role('option', name='平台本身').click()
            expect(page.locator('[data-testid="dc-scope"]')).to_contain_text('平台本身')
            tab('storage')
            expect(page.locator('.storage-group')).to_have_count(1, timeout=20000)
            page.screenshot(path=str(output / 'platform-storage.png'))
            assert not errors, errors
            assert not failures, failures
            print('datacenter ui v2 verified:', sorted(p.name for p in output.iterdir()))
            browser.close()
    finally:
        container_python("from backend import runtime as runtime\n"
                         f"runtime.delete_login_session('{token}')\n")


if __name__ == '__main__':
    main()
