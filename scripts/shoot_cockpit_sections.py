"""Screenshot every cockpit section in fullscreen (isolated backend, seeded demo data).
Usage: python3 scripts/shoot_cockpit_sections.py <out_dir> [width height]
"""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r
from verify_command_overview import DASHBOARD, seed

def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    width, height = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1920, 1080)
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        seed()
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': width, 'height': height})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                page.route('**/api/crm/business-analysis*', lambda route: route.fulfill(json={'ok': True, 'versions': [{'version': 'v1', 'imported_at': '2026-09-23 14:00', 'imported_by': 'preview', 'filename': '经营数据.xlsx', 'sheets': 1}], 'data': {'version': 'v1', 'imported_at': '2026-09-23 14:00', 'imported_by': 'preview', 'filename': '经营数据.xlsx', 'dashboard': DASHBOARD, 'sheets': [{'key': '01_核心指标总览', 'title': '核心指标总览', 'source': '测试数据', 'headers': ['指标', '实际'], 'rows': [['订货', 11785.8]]}]}}))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.locator('.command-overview').wait_for(timeout=10000)
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.wait_for_timeout(400)
                for label, marker, name in [('总体信息', '.command-overview', 'overview'), ('经营分析', '.bd-scope', 'dashboard'), ('五位一体', '.integration-map-layout', 'integration'), ('商机管理', '.command-opportunity-dashboard', 'opportunities'), ('项目作战地图', '.command-table', 'battle')]:
                    page.locator('.command-navigation').get_by_role('button', name=label, exact=True).click()
                    page.locator(marker).wait_for(timeout=15000)
                    page.wait_for_timeout(1500)
                    page.screenshot(path=str(out / f'cockpit-{name}-{width}.png'))
                    if name == 'dashboard':
                        page.locator('.command-business').evaluate('(e) => e.scrollTo(0, e.scrollHeight)')
                        page.wait_for_timeout(400)
                        page.screenshot(path=str(out / f'cockpit-{name}-{width}-bottom.png'))
                browser.close()
        finally:
            server.shutdown(); server.server_close()
    print('shots saved to', out)

if __name__ == '__main__':
    main()
