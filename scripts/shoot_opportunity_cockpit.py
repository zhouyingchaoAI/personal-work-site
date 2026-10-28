"""Screenshot the cockpit 商机管理 board with the real opportunity snapshot (isolated backend).
Usage: python3 scripts/shoot_opportunity_cockpit.py <out_dir> [width height]
"""
import json, sys, tempfile, threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
import backend.runtime as r
from verify_command_overview import seed

def main():
    out = Path([a for a in sys.argv[1:] if not a.startswith('--')][0]); out.mkdir(parents=True, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    width, height = (int(args[1]), int(args[2])) if len(args) > 2 else (1920, 1080)
    SECTION = '项目作战地图' if '--battle' in sys.argv else '五位一体' if '--integration' in sys.argv else '商机管理'
    real = json.loads((ROOT / 'user_data/liuxiaochun/crm/opportunities.json').read_text())
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        seed()
        r.crm_store('preview', 'opportunities', real)
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': width, 'height': height})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.locator('.command-overview').wait_for(timeout=10000)
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.locator('.command-navigation').get_by_role('button', name=SECTION, exact=True).click()
                page.locator({'商机管理': '.command-opportunity-dashboard', '项目作战地图': '.command-summary', '五位一体': '.integration-map-layout'}[SECTION]).wait_for(timeout=15000)
                page.wait_for_timeout(1500)
                page.screenshot(path=str(out / ({'商机管理': f'opportunity-cockpit-{width}.png', '项目作战地图': f'battle-cockpit-{width}.png', '五位一体': f'integration-cockpit-{width}.png'}[SECTION])))
                fits = page.locator('.command-summary' if SECTION != '五位一体' else '.integration-map-layout').evaluate('(e) => [e.scrollHeight, e.clientHeight, e.scrollWidth, e.clientWidth]')
                print('dashboard scroll/client', fits)
                browser.close()
                assert not errors, errors
        finally:
            server.shutdown(); server.server_close()
    print('saved to', out)

if __name__ == '__main__':
    main()
