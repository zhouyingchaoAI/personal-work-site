import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


with tempfile.TemporaryDirectory(prefix='customer-organization-focus-') as temporary:
    user = {'username': 'preview', 'name': '测试管理员', 'role': 'superadmin'}
    with patch.object(runtime, 'USER_DATA_DIR', Path(temporary)), patch.object(runtime, 'read_config', return_value={'users': [user]}), patch.object(runtime, 'SESSIONS', {'preview': 'preview'}), patch.object(runtime, 'crm_on_change'):
        root = runtime.crm_unit_save({'name': '定位测试客户', 'type': '业主单位', 'organization_level': 'company'}, 'preview')['unit']
        for index in range(20):
            child = runtime.crm_unit_save({'name': f'测试子公司{index}', 'type': '业主单位', 'organization_level': 'subsidiary', 'parent_unit_id': root['id']}, 'preview')['unit']
        original = runtime.crm_collection_path('preview', 'units').read_bytes()
        server = runtime.ThreadingHTTPServer(('127.0.0.1', 0), runtime.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1366, 'height': 768})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/workspace/crm')
                page.get_by_role('tab', name='五位一体', exact=True).click()
                page.get_by_text('客户组织架构', exact=True).click()
                page.get_by_role('button', name='调整架构画布', exact=True).click()
                dialog = page.get_by_role('dialog', name='调整客户组织架构', exact=True)
                expect(dialog.locator('.oe-node')).to_have_count(21)
                for collapsed in (False, True):
                    dialog.get_by_role('button', name='适应画布', exact=True).click()
                    if collapsed:
                        dialog.locator(f'[data-node-id="{root["id"]}"]').get_by_role('button', name='收起下级', exact=True).click()
                        expect(dialog.locator('.oe-node')).to_have_count(1)
                    dialog.locator('.oe-toolbar .el-select').nth(1).click()
                    page.get_by_role('option', name='测试子公司19', exact=True).click()
                    expect(dialog.locator('.oe-node')).to_have_count(21)
                    expect(dialog.locator('.oe-node.selected strong')).to_have_text('测试子公司19')
                    page.wait_for_function('''() => {
                        const stage = document.querySelector('.crm-organization-canvas-dialog .oe-stage');
                        const card = stage?.querySelector('.oe-node.selected');
                        if (!card) return false;
                        const area = stage.getBoundingClientRect(), node = card.getBoundingClientRect();
                        const scale = new DOMMatrix(getComputedStyle(stage.querySelector('.oe-world')).transform).a;
                        return Math.abs(node.x + node.width / 2 - area.x - area.width / 2) < 2
                            && Math.abs(node.y + node.height / 2 - area.y - area.height / 2) < 2 && scale >= 1.19;
                    }''')
                    dialog.locator('.oe-toolbar .el-select').nth(1).hover()
                    dialog.locator('.oe-toolbar .el-select').nth(1).locator('.el-select__clear').click()
                if os.environ.get('CRM_ARTIFACT_DIR'):
                    artifacts = Path(os.environ['CRM_ARTIFACT_DIR'])
                    artifacts.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(artifacts / 'customer-organization-focus.png'), animations='disabled')
                assert runtime.crm_collection_path('preview', 'units').read_bytes() == original
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()

print('PASS: customer organization selection centers and magnifies nodes, expands hidden ancestors, leaves data unchanged')
