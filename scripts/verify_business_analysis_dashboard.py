"""Business report regression. Optional: output directory and --real (read-only snapshot)."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backend.runtime as r


def fixture():
    dashboard = {
        'P01_红绿灯': [{'指标': name, '实际': 40, '全年目标': 100, 'Q3目标': 60, '全年完成率': .4, '全年缺口': 60, '逆向指标': name == '刚性费用'} for name in ['订货', '管理订货', '财务收入', '回款', '毛利', '刚性费用']],
        'P01_辅助': {'毛利率实际': .14, '毛利率目标': .165, '费效比实际': .76, '费效比目标': 5.26, '营业利润': -390.8},
        'P04_目标达成': [{'平台': '东区', 'Q3订货任务令': 100, '实际订货': 80, '管理订货': 30}],
        'P05_产业': [{'产业': '集成', '订货目标': 50000, '订货': 10250, '毛利': 960}, {'产业': '合计', '订货': 50}],
        'P08_省份': [{'省份': f'省份{i}', '订货': i*10, '现金流': -10} for i in range(12)],
    }
    names = ['核心指标总览', '作战平台经营结果', '作战平台目标达成', '产业结构', '省份分布', '费用明细', '费用率', '产业费用构成', '订单质量', '公司损益', '现金流构成', '收入支撑构成', '回款转化率', '预付条款分析', '项目属性分布', '机会点清单', '滚动冲刺机会点', '年初全预算承接', '已完成订单明细']
    sheets = [{'key': f'{i+1:02}_{name}', 'title': name, 'source': '测试数据', 'headers': ['名称', '达标订单量', '毛利率'], 'rows': [[f'末行{i+1}', 8, .2]]} for i, name in enumerate(names)]
    return {'version': 'preview', 'filename': '经营分析验证.xlsx', 'imported_at': '2026-09-24 10:00', 'dashboard': dashboard, 'sheets': sheets}


def main():
    real = '--real' in sys.argv
    out_arg = next((arg for arg in sys.argv[1:] if not arg.startswith('--')), None)
    out = Path(out_arg) if out_arg else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    data = fixture()
    if real:
        data = json.loads((ROOT / 'user_data/_crm_business_analysis.json').read_text())
        data['dashboard'] = r.crm_compute_dashboard_data(data['sheets'])
        data['version'] = 'preview'
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                def close_dialog():
                    page.locator('.ba-raw-dialog .el-dialog__headerbtn').click()
                    page.get_by_role('dialog').wait_for(state='hidden')
                    page.wait_for_timeout(250)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                base = f'http://127.0.0.1:{server.server_port}'
                page.context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                payload = {'ok': True, 'versions': [{'version': 'preview', 'filename': data['filename'], 'imported_at': data['imported_at'], 'sheets': len(data['sheets'])}], 'data': data}
                page.route('**/api/crm/business-analysis*', lambda route: route.fulfill(json=payload))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('tab', name='经营分析', exact=True).click(timeout=60000)
                page.locator('.br-report').wait_for()
                assert page.locator('.br-section-head h3').all_inner_texts() == ['公司整体经营', '区域经营', '产业经营']
                assert page.locator('.ba-dashboard-nav button').all_inner_texts() == ['公司整体', '区域经营', '产业经营']
                assert page.locator('.br-kpi').count() == 6
                assert page.locator('.br-report table').count() == 0, '主页面不得直接渲染数据表'
                assert page.locator('.br-chart-card').count() >= 15
                assert page.locator('[data-chart-kind="grouped-bars"]').count() > 0
                if real:
                    for kind in ['donut', 'line', 'heatmap', 'diverging']:
                        assert page.locator(f'[data-chart-kind="{kind}"]').count() > 0, kind
                assert '5.26' in page.locator('.br-quality').inner_text()
                if not real:
                    page.locator('[data-chart-title="区域任务令：目标、完成、差距"]').click()
                    assert '30.0%' in page.locator('.br-enlarged-data').inner_text()
                    close_dialog()
                    page.locator('[data-chart-title="产业目标与经营贡献"]').click()
                    assert '50,000.0' in page.locator('.br-enlarged-data').inner_text()
                    assert '20.5%' in page.locator('.br-enlarged-data').inner_text()
                    close_dialog()
                # Every chart opens its full analysis table; raw data remains folded initially.
                for chart in page.locator('.br-chart-card').all():
                    chart.click()
                    page.get_by_role('dialog').wait_for()
                    assert page.locator('.br-modal-sources').get_attribute('open') is None
                    assert page.locator('.br-enlarged-data table').count() > 0 or '暂无该图表数据' in page.get_by_role('dialog').inner_text() or page.locator('.br-modal-sources summary').is_visible()
                    close_dialog()
                # All 19 original sheets are accessible via the grouped directory, without truncation.
                checked = set()
                for button in page.locator('[data-source-ids]').all():
                    ids = button.get_attribute('data-source-ids').split(',')
                    button.click()
                    for sheet in data['sheets']:
                        if sheet['key'][:2] not in ids:
                            continue
                        raw = page.locator(f'.ba-raw-dialog [data-source-sheet="{sheet["key"]}"]')
                        raw.locator('summary').click()
                        assert raw.locator('tbody tr').count() == len(sheet['rows'])
                        assert raw.locator('thead th').count() == len(sheet['headers'])
                        checked.add(sheet['key'])
                    close_dialog()
                assert len(checked) == 19
                # Keyboard activation opens the same data table.
                page.locator('.br-chart-card').first.focus()
                page.locator('.br-chart-card').first.press('Enter')
                page.get_by_role('dialog').wait_for()
                page.wait_for_timeout(350)
                assert page.locator('.br-enlarged-data table').count() > 0
                if out:
                    page.screenshot(path=str(out / 'chart-data-dialog.png'))
                    page.locator('.br-modal-sources > summary').click()
                    page.locator('.br-modal-sources .br-raw > summary').first.click()
                    page.locator('.br-modal-sources .br-raw').first.scroll_into_view_if_needed()
                    page.screenshot(path=str(out / 'chart-source-expanded.png'))
                close_dialog()
                page.locator('.ba-dashboard-nav button').last.click()
                assert '产业经营' in page.locator('.ba-dashboard-nav button.active').inner_text()
                for width, height in [(1440, 1000), (1024, 768), (390, 844)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    page.wait_for_timeout(250)
                    close = page.get_by_role('button', name='关闭导航', exact=True)
                    if close.is_visible():
                        close.click()
                    assert page.locator('.business-analysis').evaluate('(e) => e.scrollWidth <= e.clientWidth + 2'), f'overflow {width}'
                    if out:
                        page.locator('.ba-dashboard-nav button').first.click()
                        page.wait_for_timeout(400)
                        page.locator('.br-section-head').first.scroll_into_view_if_needed()
                        page.screenshot(path=str(out / f'report-light-{width}.png'))
                page.set_viewport_size({'width': 1920, 'height': 1080})
                page.get_by_role('tab', name='工作台', exact=True).click()
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=10000)
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.locator('.command-navigation').get_by_role('button', name='经营分析', exact=True).click()
                page.locator('.bd-dark .br-report').wait_for()
                for label, key in [('公司整体', 'overall'), ('区域经营', 'region'), ('产业经营', 'industry')]:
                    page.locator('.ba-dashboard-nav').get_by_role('button', name=label, exact=True).click()
                    page.wait_for_timeout(500)
                    if out:
                        page.screenshot(path=str(out / f'report-dark-{key}.png'))
                        if key == 'overall':
                            page.locator('[data-chart-title="利润从哪里产生、被哪些费用消耗"]').scroll_into_view_if_needed()
                            page.screenshot(path=str(out / 'report-dark-company-charts.png'))
                            page.locator('[data-chart-title="合同质量：预付条款与回款转化"]').scroll_into_view_if_needed()
                            page.screenshot(path=str(out / 'report-dark-trends.png'))
                page.locator('[data-chart-title="毛利去向与产业投入效率"]').click()
                page.get_by_role('dialog').wait_for()
                assert page.locator('.ba-dialog-dark .br-enlarged-data table').count() == 2
                page.locator('.br-modal-sources > summary').click()
                assert page.locator('.br-modal-sources .br-raw').count() == 2
                if out:
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(out / 'chart-dark-data-dialog.png'))
                close_dialog()
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print('PASS: chart-first view, all charts open tables, all 19 source sheets, keyboard, targets, 1440/1024/390 and dark cockpit', 'real snapshot' if real else 'fixture')


if __name__ == '__main__':
    from verify_business_workspace import main as verify_workspace
    verify_workspace()
