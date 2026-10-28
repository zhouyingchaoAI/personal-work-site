import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


def test_personnel_visibility():
    with tempfile.TemporaryDirectory(prefix='organization-visibility-') as temporary:
        config = Path(temporary) / 'config.json'
        users = [{'username': 'preview', 'name': '测试管理员', 'role': 'superadmin', 'company': '测试公司'}]
        users.extend({'username': f'employee{index}', 'name': f'测试人员{index}', 'role': 'member', 'company': '测试公司', 'department': f'研发部{index % 20} / 研发小组'} for index in range(100))
        original = json.dumps({'users': users}, ensure_ascii=False)
        config.write_text(original)
        with patch.object(runtime, 'CONFIG_PATH', config), patch.object(runtime, 'USER_DATA_DIR', Path(temporary)), patch.object(runtime, 'SESSIONS', {'preview': 'preview'}):
            server = runtime.ThreadingHTTPServer(('127.0.0.1', 0), runtime.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
                    context = browser.new_context()
                    base = f'http://127.0.0.1:{server.server_port}'
                    context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base + '/workspace/usermanage')
                    page.get_by_role('button', name='调整我方组织画布', exact=True).click()
                    dialog = page.get_by_role('dialog', name='调整我方组织架构', exact=True)
                    expect(dialog.locator('[data-person-id]')).to_have_count(101)
                    page.set_viewport_size({'width': 1366, 'height': 768})
                    dialog.get_by_role('button', name='适应画布', exact=True).click()
                    initial_zoom = dialog.locator('.oe-world').evaluate('element => new DOMMatrix(getComputedStyle(element).transform).a')
                    dialog.locator('.oe-toolbar .el-select').nth(1).click()
                    page.get_by_role('option', name='研发部19', exact=True).click()
                    page.wait_for_function('''() => {
                        const stage = document.querySelector('.internal-organization-dialog .oe-stage');
                        const card = stage?.querySelector('.oe-node.selected');
                        if (!card) return false;
                        const area = stage.getBoundingClientRect(), node = card.getBoundingClientRect();
                        const scale = new DOMMatrix(getComputedStyle(stage.querySelector('.oe-world')).transform).a;
                        return Math.abs(node.x + node.width / 2 - area.x - area.width / 2) < 2
                            && Math.abs(node.y + node.height / 2 - area.y - area.height / 2) < 2 && scale >= 1.19;
                    }''')
                    expect(dialog.locator('.oe-node.selected strong')).to_have_text('研发部19')
                    focused_zoom = dialog.locator('.oe-world').evaluate('element => new DOMMatrix(getComputedStyle(element).transform).a')
                    assert focused_zoom > initial_zoom
                    page.wait_for_timeout(350)
                    assert dialog.locator('.oe-world').evaluate('element => new DOMMatrix(getComputedStyle(element).transform).a') == focused_zoom
                    for width, height in [(1600, 900), (1366, 768), (1280, 600), (390, 844)]:
                        page.set_viewport_size({'width': width, 'height': height})
                        first = dialog.locator('[data-person-id="preview"]')
                        first.scroll_into_view_if_needed()
                        expect(first).to_be_in_viewport()
                        last = dialog.locator('[data-person-id="employee99"]')
                        last.scroll_into_view_if_needed()
                        expect(last).to_be_in_viewport()
                        expect(dialog.get_by_role('button', name='关闭画布', exact=True)).to_be_in_viewport()
                        last.click()
                        person_dialog = page.get_by_role('dialog', name='匹配人员归属', exact=True)
                        expect(person_dialog).to_be_visible()
                        person_dialog.get_by_role('button', name='取消', exact=True).click()
                        expect(person_dialog).not_to_be_visible()
                        search = dialog.get_by_label('搜索待匹配人员')
                        search.fill('测试人员99')
                        expect(dialog.locator('[data-person-id]')).to_have_count(1)
                        expect(last).to_be_in_viewport()
                        if os.environ.get('CRM_ARTIFACT_DIR'):
                            artifacts = Path(os.environ['CRM_ARTIFACT_DIR'])
                            artifacts.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(artifacts / f'organization-{width}x{height}.png'))
                        search.fill('')
                    assert config.read_text() == original
                    assert not errors, errors
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    test_personnel_visibility()
    print('PASS: personnel scrolling, search, assignment dialog and footer across four viewports; accounts unchanged')
