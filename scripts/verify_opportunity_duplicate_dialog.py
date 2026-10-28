"""Browser regression: duplicate opportunity imports require an explicit choice."""
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook
from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


def main():
    with tempfile.TemporaryDirectory() as tmp, \
         patch.object(runtime, 'USER_DATA_DIR', Path(tmp)), \
         patch.object(runtime, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), \
         patch.object(runtime, 'SESSIONS', {'preview': 'preview'}), \
         patch.object(runtime, 'crm_audit'), \
         patch.object(runtime.Handler, 'log_message'):
        runtime.crm_store('preview', 'opportunities', {
            'OPP-DUP': {'id': 'OPP-DUP', 'code': 'OPP-DUP', 'name': '原有商机', 'owner_unit': '原有客户',
                        'amount': 100, 'cancelled': False, 'version': 1}
        })
        source = Path(tmp) / '重复机会点.xlsx'
        book = Workbook(); sheet = book.active
        sheet.append(['机会点编码', '机会点名称', '业主单位'])
        sheet.append(['OPP-DUP', '导入商机', '导入客户'])
        sheet.append(['OPP-NEW', '新增商机', '新增客户'])
        book.save(source); book.close()

        server = runtime.ThreadingHTTPServer(('127.0.0.1', 0), runtime.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1280, 'height': 900})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                page.goto(base + '/workspace/crm')
                page.locator('input[type="file"][accept=".xlsx,.xlsm"]').first.set_input_files(str(source))
                dialog = page.locator('.el-message-box')
                dialog.wait_for(timeout=15000)
                assert '发现 1 条重复商机' in dialog.inner_text()
                assert page.get_by_role('button', name='去重导入（保留现有）').is_visible()
                assert page.get_by_role('button', name='覆盖更新').is_visible()
                if len(sys.argv) > 1:
                    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(out / 'opportunity-duplicate-dialog.png'), full_page=True)
                # Close is a true abort: neither existing nor new records are changed.
                page.locator('.el-message-box__headerbtn').click()
                page.wait_for_timeout(300)
                stored = runtime.crm_load('preview', 'opportunities')
                assert stored['OPP-DUP']['name'] == '原有商机'
                assert 'OPP-NEW' not in stored
                browser.close()
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
