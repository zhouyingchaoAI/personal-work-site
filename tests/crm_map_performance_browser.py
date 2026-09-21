"""Isolated browser regression with a large synthetic staff directory."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

with tempfile.TemporaryDirectory(prefix='crm-map-perf-') as tmp:
    users = [{'username': 'preview', 'role': 'superadmin'}]
    with patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': users}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_on_change'), patch.object(r, 'crm_audit'):
        for region in ('东区', '西区'):
            unit = r.crm_unit_save({'name': region + '测试客户', 'type': '业主单位', 'business_regions': [region]}, 'preview')['unit']
            person = r.crm_person_save({'name': '测试联系人', 'unit_id': unit['id']}, 'preview')['person']
            r.crm_relation_save({'person_id': person['id'], 'our_member': 'E1'}, 'preview')
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1512, 'height': 900})
                page.context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                staff = [{'id': f's{i}', 'member_key': f'E{i}', 'name': f'测试人员{i}', 'department': '东区', 'company': '测试', 'title': '经理'} for i in range(21202)]
                page.route('**/api/crm/staff', lambda route: route.fulfill(json={'ok': True, 'staff': staff}))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                errors = []
                page.on('pageerror', lambda err: errors.append(str(err)))
                start = time.perf_counter()
                page.goto(base + '/workspace/crm')
                deck = page.locator('.map-cockpit')
                expect(deck).to_be_visible(timeout=20000)
                expect(page.locator('.crm-main > .el-loading-mask')).to_have_count(0)
                loaded = time.perf_counter() - start
                timings = []
                for name in ('东区', '西区', '东区', '西区'):
                    start = time.perf_counter()
                    deck.locator('select[aria-label="地图区域"]').select_option(name)
                    expect(deck.locator('.map-cockpit__scope h3')).to_contain_text(name)
                    expect(deck.locator('.region-map__card.selected')).to_contain_text(name)
                    timings.append(round((time.perf_counter() - start) * 1000))
                assert not errors, errors
                assert max(timings) < 2000, timings
                print(json.dumps({'staff': len(staff), 'first_visible_seconds': round(loaded, 2), 'region_switch_ms': timings, 'mode': 'local fixture, fallback map; external Gaode network excluded'}))
                browser.close()
        finally:
            server.shutdown()
