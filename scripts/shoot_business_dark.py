"""Screenshot the cockpit 经营分析 (dark) with the real imported snapshot.
Usage: python3 scripts/shoot_business_dark.py <out_dir> [width] [--overview]
Produces <out>/business-dark-viewport.png and <out>/business-dark-full.png (long page).
"""
import json
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import backend.runtime as r
from verify_command_overview import seed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = Path(args[0]); out.mkdir(parents=True, exist_ok=True)
    width = int(args[1]) if len(args) > 1 else 1920
    data = json.loads((ROOT / 'user_data/_crm_business_analysis.json').read_text())
    data['dashboard'] = r.crm_compute_dashboard_data(data['sheets'])
    data['version'] = 'preview'
    payload = {'ok': True, 'versions': [{'version': 'preview', 'filename': data['filename'], 'imported_at': data['imported_at'], 'sheets': len(data['sheets'])}], 'data': data}
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        seed()
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': width, 'height': 1080}, device_scale_factor=1)
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('**/api/crm/business-analysis*', lambda route: route.fulfill(json=payload))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.locator('.command-overview').wait_for(timeout=10000)
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.wait_for_timeout(500)
                if '--overview' in sys.argv:
                    page.screenshot(path=str(out / f'overview-{width}.png'))
                page.locator('.command-navigation').get_by_role('button', name='经营分析', exact=True).click()
                page.locator('.bd-dark .br-report').wait_for(timeout=15000)
                page.wait_for_timeout(1200)
                page.screenshot(path=str(out / f'business-dark-viewport-{width}.png'))
                # Unclamp the scroll container so a single long screenshot captures the whole board.
                page.evaluate("""() => {
                  const deck = document.querySelector('.map-cockpit'); deck.style.height='auto'; deck.style.bottom='auto'; deck.style.minHeight='100vh';
                  const biz = document.querySelector('.command-business'); biz.style.overflow='visible'; biz.style.flex='none'; biz.style.height='auto';
                }""")
                page.wait_for_timeout(400)
                page.locator('.map-cockpit').screenshot(path=str(out / f'business-dark-full-{width}.png'))
                browser.close()
                assert not errors, errors
        finally:
            server.shutdown(); server.server_close()
    print('saved to', out)


if __name__ == '__main__':
    main()
