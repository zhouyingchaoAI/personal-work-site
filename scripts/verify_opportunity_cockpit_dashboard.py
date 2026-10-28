"""Regression: the opportunity cockpit is a compact analytics dashboard.

Runs against an isolated backend and the built frontend; never writes live CRM data.
"""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


def main():
    with tempfile.TemporaryDirectory() as tmp, \
         patch.object(runtime, 'USER_DATA_DIR', Path(tmp)), \
         patch.object(runtime, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), \
         patch.object(runtime, 'SESSIONS', {'preview': 'preview'}), \
         patch.object(runtime, 'crm_audit'), \
         patch.object(runtime.Handler, 'log_message'):
        stages = ['立项阶段', '初设阶段', '招标（深化）设计', '招标执行', '设计联络阶段', '合同签订']
        regions = ['东区', '中区', '西区', '广东区']
        opportunities = {}
        for index in range(10):
            code = f'OP-{index + 1:03d}'
            stage = stages[index % len(stages)]
            opportunities[code] = {
                'id': code, 'code': code, 'name': f'示范商机 {index + 1}', 'owner_unit': f'客户单位 {index + 1}',
                'sales_stage': stage, 'stage': stage, 'win_rate': str(18 + index * 8), 'status': '推进中',
                'region': regions[index % len(regions)], 'manager': f'负责人 {index % 3 + 1}', 'bid_date': '',
                'contract_date': '2027-06', 'amount': 1200 + index * 730, 'cancelled': False, 'outcome': 'open',
                'stage_progress': {stage: {'attachments': ([{'name': '支撑材料'}] if index % 2 == 0 else []), 'contacts': ([{'name': '关键关系人'}] if index % 3 != 0 else [])}},
                'version': 1,
            }
        runtime.crm_store('preview', 'opportunities', opportunities)
        server = runtime.ThreadingHTTPServer(('127.0.0.1', 0), runtime.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1920, 'height': 1080})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.locator('.command-navigation').get_by_role('button', name='商机管理', exact=True).click()
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()

                dashboard = page.locator('.command-opportunity-dashboard')
                dashboard.wait_for(timeout=5000)
                assert dashboard.locator('.command-opportunity-kpis > div').count() == 5, 'Expected five top-level opportunity KPIs'
                assert dashboard.locator('.command-analysis-card').count() >= 6, 'Expected at least four opportunity analysis modules'
                assert dashboard.locator('.command-opportunity-priority tbody tr').count() <= 5, 'Priority list must remain compact'
                assert dashboard.locator('.command-table').count() == 0, 'Full opportunity table must not dominate the cockpit'
                assert not errors, errors

                for width, height in [(1920, 1080), (1366, 768)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(150)
                    assert page.locator('.cockpit-expanded').evaluate('(e) => e.scrollHeight <= e.clientHeight + 2 && e.scrollWidth <= e.clientWidth + 2'), f'Cockpit overflows at {width}x{height}'
                    assert dashboard.evaluate('(e) => e.scrollHeight <= e.clientHeight + 2 && e.scrollWidth <= e.clientWidth + 2'), f'Opportunity dashboard needs scrolling at {width}x{height}'

                if len(sys.argv) > 1:
                    out = Path(sys.argv[1])
                    out.mkdir(parents=True, exist_ok=True)
                    page.set_viewport_size({'width': 1920, 'height': 1080})
                    page.screenshot(path=str(out / 'opportunity-cockpit-1920.png'))
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
