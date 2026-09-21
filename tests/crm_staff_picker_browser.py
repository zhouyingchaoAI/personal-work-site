"""Real picker: missing profile fields must not become fake job labels."""
import os, sys, tempfile, threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

with tempfile.TemporaryDirectory(prefix='staff-picker-') as tmp:
    user = {'username': 'preview', 'name': '测试', 'role': 'superadmin'}
    with patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [user]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_on_change'):
        r.crm_staff_save({'name': '简资料人员', 'member_key': 'E001'}, 'preview')
        r.crm_staff_save({'name': '完整人员', 'member_key': 'E002', 'company': '测试公司', 'department': '技术部', 'title': '工程师'}, 'preview')
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base + '/workspace/crm')
                page.get_by_role('tab', name='关系维系', exact=True).click()
                page.get_by_role('button', name='新建关系', exact=True).click()
                dialog = page.get_by_role('dialog').filter(has=page.get_by_text('我方对接人', exact=True))
                picker = dialog.locator('.el-select').filter(has=page.get_by_role('combobox', name='我方对接人', exact=True))
                picker.click()
                sparse = page.get_by_role('option').filter(has_text='简资料人员')
                expect(sparse).to_be_visible()
                expect(sparse).not_to_contain_text('待补充')
                expect(sparse).not_to_contain_text('未填')
                expect(sparse).not_to_contain_text('/')
                expect(sparse).to_contain_text('E001')
                artifact = Path(os.environ['CRM_ARTIFACT_DIR'])
                artifact.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(artifact / '负责人选择-优化.png'), animations='disabled')
                sparse.click()
                expect(picker).to_contain_text('简资料人员')
                expect(dialog).not_to_contain_text('岗位待补充')
                picker.click()
                picker.locator('input').fill('工程师')
                full = page.get_by_role('option').filter(has_text='完整人员')
                expect(full).to_be_visible()
                expect(full).to_contain_text('测试公司')
                expect(full).to_contain_text('技术部')
                full.click()
                expect(picker).to_contain_text('完整人员')
                expect(dialog).to_contain_text('工程师')
                picker.hover()
                picker.locator('.el-select__clear').click()
                expect(picker).not_to_contain_text('完整人员')
                assert not errors, errors
                browser.close()
                print('PASS sparse/full profile rendering, job search, selection and clear')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
