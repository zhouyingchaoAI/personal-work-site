"""Visual regression for the opportunity analytics information hierarchy."""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


def main():
    with tempfile.TemporaryDirectory() as tmp, \
         patch.object(runtime, 'USER_DATA_DIR', Path(tmp)), \
         patch.object(runtime, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), \
         patch.object(runtime, 'SESSIONS', {'preview': 'preview'}), \
         patch.object(runtime, 'crm_audit'), \
         patch.object(runtime.Handler, 'log_message'):
        server = runtime.ThreadingHTTPServer(('127.0.0.1', 0), runtime.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/workspace/crm')
                page.get_by_role('tab', name='商机管理', exact=True).click(timeout=60000)
                statistics_tab = page.get_by_role('tab', name='统计分析', exact=True)
                list_tab = page.get_by_role('tab', name='商机清单', exact=True)
                expect(statistics_tab).to_have_attribute('aria-selected', 'true')
                page.locator('.opp-analytics').wait_for()
                list_tab.click()
                expect(list_tab).to_have_attribute('aria-selected', 'true')
                expect(page.locator('.om-filters')).to_be_visible()
                expect(page.locator('.opp-analytics')).to_have_count(0)
                statistics_tab.click()
                expect(statistics_tab).to_have_attribute('aria-selected', 'true')
                page.locator('.opp-analytics').wait_for()

                kpis = page.locator('.oa-kpis')
                donuts = page.locator('.oa-donut-grid')
                assert kpis.locator('.oa-kpi').count() == 5, 'Expected five top-level opportunity KPIs'
                assert donuts.locator('.oa-donut-card').count() >= 3, 'Expected at least three opportunity donut charts'
                assert kpis.bounding_box()['y'] < donuts.bounding_box()['y'], 'KPIs must appear before donut charts'
                assert donuts.bounding_box()['y'] < page.locator('.growth-analytics').bounding_box()['y'], 'Summary charts must appear before detailed growth analysis'
                assert page.locator('.oa-donut-card [role="img"]').count() >= 3, 'Donut charts need accessible summaries'
                assert page.locator('.opp-analytics').evaluate('(e) => e.scrollWidth <= e.clientWidth + 2'), 'Analytics has horizontal overflow'
                assert not errors, errors

                if len(sys.argv) > 1:
                    out = Path(sys.argv[1])
                    out.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(out / 'opportunity-analytics-1440.png'), full_page=True)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
