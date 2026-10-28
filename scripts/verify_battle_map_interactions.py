"""Battle-map interaction regression on real opportunity data (isolated backend, read-only copy).
Usage: python3 scripts/verify_battle_map_interactions.py [screenshot_dir]
Every KPI / legend / province / stage / target control must change what is shown, and a selected
target must open the intel panel whose actions navigate away from the cockpit.
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
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out: out.mkdir(parents=True, exist_ok=True)
    real = json.loads((ROOT / 'user_data/liuxiaochun/crm/opportunities.json').read_text())
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        seed()
        r.crm_store('preview', 'opportunities', real)
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1920, 'height': 1080})
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                base = f'http://127.0.0.1:{server.server_port}'
                page.context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.locator('.command-navigation').get_by_role('button', name='项目作战地图', exact=True).click()
                battle = page.locator('.battle'); battle.wait_for(timeout=15000); page.wait_for_timeout(1300)
                rows = battle.locator('.target-list li:not(.empty)')
                total = rows.count(); assert total > 0, 'no targets'
                shot = lambda name: out and page.screenshot(path=str(out / f'{name}.png'))
                shot('01-全部')

                # KPI: 预计签约已逾期
                battle.locator('button.k-red').click(); page.wait_for_timeout(200)
                overdue = rows.count(); assert 0 < overdue < total, (overdue, total)
                assert battle.locator('.chips').inner_text().startswith('预计签约已逾期')
                assert battle.locator('.target-list .late').count() == overdue
                shot('02-签约逾期')
                battle.locator('button.k-cyan').click(); page.wait_for_timeout(200)
                assert rows.count() == total and battle.locator('.chips').count() == 0

                # Province from TOP6 ranking, then map dims other provinces
                first = battle.locator('.theater-rank li button').first
                prov = first.locator('span').inner_text(); first.click(); page.wait_for_timeout(200)
                in_prov = rows.count(); assert 0 < in_prov <= total
                assert battle.locator('.prov.picked').count() == 1 and battle.locator('.prov.faded').count() > 10
                assert all(prov in t for t in rows.locator('.t-main small').all_inner_texts())
                shot('03-战区筛选')

                # Stage line narrows further; clearing restores
                stage_btn = battle.locator('.front-line button:not([disabled])').first
                stage_btn.click(); page.wait_for_timeout(200)
                assert rows.count() <= in_prov and battle.locator('.chips button').count() == 3
                battle.locator('.chips .clear').click(); page.wait_for_timeout(200)
                assert rows.count() == total

                # Legend tier toggle
                battle.locator('.legend button.mid').click(); page.wait_for_timeout(200)
                assert all(c == 'mid' or 'mid' in c for c in rows.evaluate_all('els => els.map(e => e.className)'))
                battle.locator('.legend button.mid').click(); page.wait_for_timeout(200)

                # Select target from list → intel panel; map marker locked; row highlighted
                rows.first.click(); page.wait_for_timeout(300)
                intel = battle.locator('.intel'); intel.wait_for()
                text = intel.inner_text()
                for label in ['可参与份额', '项目投资规模', '预计签约', '负责人', '进入作战部署']:
                    assert label in text, label
                assert battle.locator('.mk.sel').count() == 1 and battle.locator('.target-list li.sel').count() == 1
                shot('04-目标情报')
                # Select from map marker instead
                intel.locator('.x').click(); page.wait_for_timeout(150)
                battle.locator('.mk:not(.off)').nth(2).click(force=True); page.wait_for_timeout(300)
                assert battle.locator('.intel').count() == 1 and battle.locator('.target-list li.sel').count() == 1

                # Primary action leaves the cockpit for the battle workspace
                chosen = battle.locator('.intel > header small').inner_text().split(' · ')[0].strip()
                battle.locator('.intel footer .primary').click(); page.wait_for_timeout(1400)
                assert page.locator('.cockpit-expanded').count() == 0, 'cockpit should close after entering battle deployment'
                target = page.locator(f'[data-project-code="{chosen}"]')
                assert target.locator('.is-active').count() > 0 or 'is-active' in (target.get_attribute('class') or ''), 'chosen project must be expanded'
                assert target.evaluate('e => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight }'), 'chosen project must be scrolled into view'
                shot('05-进入作战部署')
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown(); server.server_close()
    print('PASS battle map: KPI/province/stage/legend filters, list↔map selection, intel panel, battle navigation')


if __name__ == '__main__':
    main()
