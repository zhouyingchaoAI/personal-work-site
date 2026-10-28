"""Regression: the joint command cockpit overview is a scaled 1754 × 897 big-screen canvas.

Runs against an isolated backend and the built frontend; never writes live CRM data.
Usage: python3 scripts/verify_command_overview.py [screenshot_dir]
"""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

DASHBOARD = {
    'P01_红绿灯': [
        {'指标': '订货', '实际': 11785.8, '全年目标': 55000, '全年完成率': .2143, 'Q3目标': 33000, 'Q3完成率': .357, '灯': 'red'},
        {'指标': '管理订货', '实际': 7766.7, '全年目标': 55000, '全年完成率': .1412, 'Q3目标': 33000, 'Q3完成率': .235, '灯': 'red'},
        {'指标': '财务收入', '实际': 12683.2, '全年目标': 33600, '全年完成率': .3775, 'Q3目标': 21800, 'Q3完成率': .581, '灯': 'amber'},
        {'指标': '回款', '实际': 9917.6, '全年目标': 38000, '全年完成率': .261, 'Q3目标': 24600, 'Q3完成率': .402, '灯': 'red'},
        {'指标': '毛利', '实际': 1183.3, '全年目标': 6750, 'Q3目标': 4050, 'Q3完成率': .292, '灯': 'red'},
    ],
    'P01_辅助': {'毛利率实际': .113, '毛利率目标': .165, '费效比实际': 1.44, '费效比目标': 5.26, '营业利润': -372},
}
REGIONS = [('东区', '杭州'), ('西区', '成都'), ('中区', '武汉'), ('广东区', '广州')]
TYPES = ['业主单位', '总包单位', '设计单位', '厂商', '主管单位']
STAGES = ['合同签订', '招标执行', '立项阶段', '初设阶段', '设计联络阶段']


def seed():
    relation_ids = []
    for index, (region, city) in enumerate(REGIONS):
        for t, kind in enumerate(TYPES):
            unit = r.crm_unit_save({'name': f'{city}{kind}{t + 1}', 'type': kind, 'region': city, 'business_regions': [region]}, 'preview')['unit']
            for p in range(2):
                person = r.crm_person_save({'name': f'{kind[:2]}联系人{index}{t}{p}', 'unit_id': unit['id'], 'title': '项目对接', 'decision_role': '定技术'}, 'preview')['person']
                if p == 1 and t == 4:
                    continue  # 留一位未建关系的联系人
                relation = r.crm_relation_save({'person_id': person['id'], 'our_member': f'客户经理{index + 1}' if p == 0 else '项目负责人'}, 'preview')['relation']
                relation_ids.append(relation['id'])
                happened = '2026-09-20' if (t + p) % 3 else '2025-06-01'
                r.crm_action_add({'relation_id': relation['id'], 'type': '拜访', 'intel': f'与{person["name"]}沟通{kind}进展', 'happened_at': happened, 'effective': True, 'bidirectional': True}, 'preview')
                if (t + p) % 2 == 0:
                    r.crm_action_add({'relation_id': relation['id'], 'record_kind': 'plan', 'next_step': f'跟进{person["name"]}资料', 'due_date': '2026-09-01' if p else '2026-09-23', 'project_id': 'OP-001', 'owner': '项目负责人'}, 'preview')
    opportunities = {}
    for index in range(12):
        code = f'OP-{index + 1:03d}'
        stage = STAGES[index % len(STAGES)]
        opportunities[code] = {
            'id': code, 'code': code, 'name': f'{REGIONS[index % 4][1]}轨道交通{index + 1}号线通信系统集成项目', 'owner_unit': f'{REGIONS[index % 4][1]}业主单位1',
            'sales_stage': stage, 'stage': stage, 'win_rate': str(15 + index * 7), 'status': '推进中', 'region': REGIONS[index % 4][0],
            'manager': '' if index == 5 else f'客户经理{index % 4 + 1}', 'bid_date': '', 'contract_date': '2027-06', 'amount': 600 + index * 900,
            'cancelled': False, 'outcome': 'open', 'created_at': f'2026-09-{10 + index:02d} 09:00:00', 'updated_at': f'2026-09-{10 + index:02d} 09:00:00',
            'stage_progress': {stage: {'attachments': ([{'name': '支撑材料'}] if index % 2 == 0 else []), 'contacts': ([{'name': '关键关系人'}] if index % 3 != 0 else [])}},
            'version': 1,
        }
    r.crm_store('preview', 'opportunities', opportunities)


def fits(page, inner, outer):
    return page.evaluate('''([inner, outer]) => {
      const a = document.querySelector(inner).getBoundingClientRect(), b = document.querySelector(outer).getBoundingClientRect()
      return a.left >= b.left - 1 && a.top >= b.top - 1 && a.right <= b.right + 1 && a.bottom <= b.bottom + 1 && a.width > 0 && a.height > 0
    }''', [inner, outer])


def main():
    with tempfile.TemporaryDirectory() as tmp, \
         patch.object(r, 'USER_DATA_DIR', Path(tmp)), \
         patch.object(r, 'read_config', return_value={'users': [{'username': 'preview', 'role': 'superadmin'}]}), \
         patch.object(r, 'SESSIONS', {'preview': 'preview'}), \
         patch.object(r, 'crm_audit'), \
         patch.object(r.Handler, 'log_message'):
        seed()
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        if out:
            out.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1920, 'height': 1080})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/api/crm/business-analysis*', lambda route: route.fulfill(json={'ok': True, 'versions': [{'version': 'v1', 'imported_at': '2026-09-23 14:00', 'imported_by': 'preview', 'filename': '经营数据.xlsx', 'sheets': 1}], 'data': {'version': 'v1', 'imported_at': '2026-09-23 14:00', 'imported_by': 'preview', 'filename': '经营数据.xlsx', 'dashboard': DASHBOARD, 'sheets': []}}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)

                screen = page.locator('.command-overview')
                screen.wait_for(timeout=10000)
                assert page.locator('.command-canvas-mode').count() == 1, 'Overview must render in canvas mode on desktop'
                assert page.locator('.command-overview .cv-region').count() == 0, 'Region cards now live in the integration board, not the overview'
                assert page.locator('.cv-panel').count() == 8, 'Expected eight dashboard panels (health, zones and layout merged into one)'
                assert page.locator('.cv-zone .zone-layout .zl-rows li').count() == 5, 'Merged zone panel must list the five customer types'
                for title in ['经营分析', '五位一体', '商机管理', '项目作战地图', '风险雷达', '五类客户 · 健康度与布局', '行动指挥台', '最近动态']:
                    assert page.locator('.cv-panel__title', has_text=title).count() == 1, f'Missing panel {title}'
                page.wait_for_timeout(1500)  # CountUp settles
                head = page.locator('.cv-biz .rows li.head').inner_text()
                for label in ['全年目标', '当前达成', '达成率']:
                    assert label in head, f'Business panel must label {label}, got {head!r}'
                first_row = page.locator('.cv-biz .rows li').nth(1)
                assert first_row.locator('.target .num').inner_text() == '55,000', 'Annual target must be an explicit number'
                assert first_row.locator('.value .num').inner_text() == '11,785.8', 'Current achieved must be an explicit number'
                assert page.locator('.cv-biz .rate .num').first.inner_text() == '21.4', 'Achievement rate must be the annual completion from imported data'
                gross_row = page.locator('.cv-biz .rows li').nth(5)
                assert gross_row.locator('.rate .num').inner_text() == '17.5', 'Missing annual rate must fall back to achieved / target'
                assert page.locator('.cv-opp .stats .num').first.inner_text() == '12', 'Talking opportunities must reflect seeded data'
                opp_box = page.locator('.cv-opp').bounding_box()
                five_box = page.locator('.cv-five').bounding_box()
                assert opp_box['x'] < five_box['x'], 'Opportunity panel must sit left of the five-in-one panel (swapped by user request)'
                assert page.locator('.cv-zone .cv-health-embedded .radar').count() == 1, 'Health radar must render inside the merged customer panel'
                import re
                legend = page.locator('.cv-zone .cv-health-embedded .legend li').first.inner_text()
                match = re.search(r'综合暂估 (\d+) 分 · (\d+)/(\d+) 家有据', legend)
                assert match, f'Health legend must expose the real composite average and evidence counts, got {legend!r}'
                assert int(match.group(3)) == 20 and int(match.group(2)) >= 1, legend
                assert page.locator('.cv-zone .cv-health-embedded .radar .avg').count() == 1, 'Average polygon must be drawn from real scores'

                for width, height in [(1920, 1080), (1366, 768), (1024, 768)]:
                    for expanded in [False, True]:
                        page.set_viewport_size({'width': width, 'height': height})
                        page.wait_for_timeout(250)
                        if expanded and page.get_by_role('button', name='全屏作战大屏', exact=True).count():
                            page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                            page.wait_for_timeout(250)
                        assert fits(page, '.command-canvas', '.command-viewport'), f'Canvas overflows its viewport at {width}x{height} expanded={expanded}'
                        box = page.locator('.command-canvas').bounding_box()
                        view = page.locator('.command-viewport').bounding_box()
                        assert abs(box['width'] / box['height'] - 1571 / 792) < 0.01, 'Canvas must keep the design aspect ratio'
                        assert abs(box['width'] - view['width']) < 2 or abs(box['height'] - view['height']) < 2, 'Canvas must fill the viewport on at least one axis'
                        assert page.locator('.map-cockpit').evaluate('(e) => e.scrollHeight <= e.clientHeight + 2 && e.scrollWidth <= e.clientWidth + 2'), f'Cockpit scrolls at {width}x{height}'
                        for selector in ['.cv-panel', '.command-canvas-footer']:
                            count = page.locator(selector).count()
                            for i in range(count):
                                el = page.locator(selector).nth(i)
                                assert el.evaluate('(e) => { const a = e.getBoundingClientRect(), b = document.querySelector(".command-canvas").getBoundingClientRect(); return a.left >= b.left - 1 && a.right <= b.right + 1 && a.top >= b.top - 1 && a.bottom <= b.bottom + 1 }'), f'{selector}[{i}] leaves the canvas at {width}x{height}'
                        for selector in ['.command-navigation', '.map-cockpit__header', '.command-viewport']:
                            assert fits(page, selector, '.map-cockpit'), f'{selector} leaves the cockpit at {width}x{height}'
                        if expanded:
                            assert page.locator('.map-cockpit').evaluate('(e) => getComputedStyle(e).position === "fixed"'), 'Expanded cockpit must stay fixed over the page'
                            assert fits(page, '.map-cockpit', 'body'), 'Expanded cockpit must sit inside the visible viewport'
                        if out and expanded:
                            page.screenshot(path=str(out / f'command-overview-{width}.png'))
                        elif out and width == 1920:
                            page.screenshot(path=str(out / 'command-overview-embedded-1920.png'))
                        if expanded:
                            page.get_by_role('button', name='退出大屏', exact=True).click()
                            page.wait_for_timeout(200)
                    print('PASS', width, height, flush=True)

                page.set_viewport_size({'width': 1920, 'height': 1080})
                page.wait_for_timeout(200)
                # 五类分区：点击光点弹出单位 / 联系人数，展开可进入关系网络
                page.get_by_role('button', name='业主单位分区').click()
                bubble = page.locator('.cv-zone .bubble')
                bubble.wait_for(timeout=3000)
                assert '单位 4' in bubble.inner_text(), bubble.inner_text()
                bubble.get_by_role('button', name='展开组织 ↗').click()
                page.get_by_role('dialog', name='区域关系网络').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                # 风险雷达与行动指挥台的明细弹窗仍可用
                # 合并面板：面板头「详情」进入关系网络；雷达点击打开健康度明细
                page.locator('.cv-zone').get_by_role('button', name='详情').click()
                page.get_by_role('dialog', name='区域关系网络').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                page.locator('.cv-zone .radar-btn').click()
                page.get_by_role('dialog', name='公司层五维健康度').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(300)
                # 布局行点击进入该类组织的关系网络
                page.locator('.cv-zone .zl-rows li').last.locator('button').click()
                page.get_by_role('dialog', name='区域关系网络').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                page.get_by_role('button', name='查看预警').click()
                page.get_by_role('dialog', name='全部预警').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                page.get_by_role('button', name='全部待办').click()
                page.get_by_role('dialog', name='全部待办').wait_for(timeout=5000)
                page.keyboard.press('Escape')
                page.wait_for_timeout(200)
                # 头部与侧栏是驾驶舱固定外壳：切换专题看板后位置、尺寸、条目完全一致
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                page.wait_for_timeout(300)
                shell = lambda: page.evaluate('''() => {
                  const box = s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(v => Math.round(v)) }
                  return { nav: box('.command-navigation'), header: box('.map-cockpit__header'),
                    items: [...document.querySelectorAll('.command-navigation button')].map(b => { const r = b.getBoundingClientRect(); return [b.textContent.trim(), Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)].join(':') }) }
                }''')
                baseline = shell()
                assert baseline['nav'][2] >= 150, f'Side navigation must keep the big-screen width, got {baseline["nav"]}'
                assert len(baseline['items']) == 6, baseline['items']
                for label, marker in [('商机管理', '.command-opportunity-dashboard'), ('经营分析', '.command-business'), ('五位一体', '.integration-map-layout'), ('项目作战地图', '.command-table'), ('总体信息', '.command-overview')]:
                    page.locator('.command-navigation').get_by_role('button', name=label, exact=True).click()
                    page.locator(marker).wait_for(timeout=10000)
                    page.wait_for_timeout(200)
                    current = shell()
                    assert current == baseline, f'Shell changed on {label}: {current} vs {baseline}'
                    assert (page.locator('.command-canvas-mode').count() == 1) == (label == '总体信息'), 'Canvas mode must only apply to the overview'
                page.get_by_role('button', name='退出大屏', exact=True).click()
                page.wait_for_timeout(200)
                screen.wait_for(timeout=5000)

                # 区域卡移入五位一体：四张卡渲染真实区域数据，点击选中该区域，再点取消
                page.locator('.command-navigation').get_by_role('button', name='五位一体', exact=True).click()
                page.locator('.integration-map-layout').wait_for(timeout=10000)
                cards = page.locator('.map-cockpit__regions .cv-region')
                assert cards.count() == 4, 'Integration board must show the four region cards'
                page.wait_for_timeout(1400)
                east = cards.first
                assert east.locator('.cv-region__name').inner_text().startswith('东区'), 'First region card must be 东区'
                east_units = east.locator('.cv-region__col .num').first.inner_text()
                assert east_units == '5', f'Region card must show real regional units, got {east_units!r}'
                east.click()
                page.wait_for_timeout(300)
                assert '东区' in page.locator('.map-cockpit__scope h3').inner_text(), 'Clicking a region card must focus that region'
                assert 'is-selected' in (east.get_attribute('class') or '')
                east.click()
                page.wait_for_timeout(300)
                assert '全部区域' in page.locator('.map-cockpit__scope h3').inner_text(), 'Clicking the selected card must clear the region filter'
                page.locator('.command-navigation').get_by_role('button', name='总体信息', exact=True).click()
                screen.wait_for(timeout=5000)

                # 窄屏：不缩放，纵向流式，无横向溢出
                page.set_viewport_size({'width': 390, 'height': 844})
                page.wait_for_timeout(400)
                assert page.locator('.command-canvas-mode').count() == 0, 'Narrow screens must use the flow layout'
                assert page.locator('.command-overview.is-flow').count() == 1
                assert page.locator('.command-overview .cv-region').count() == 0, 'Flow overview must not render region cards either'
                assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1'), 'Horizontal overflow on mobile'
                assert page.locator('.map-cockpit').evaluate('(e) => e.scrollWidth <= e.clientWidth + 1'), 'Cockpit horizontal overflow on mobile'
                if page.locator('.mobile-sidebar-close').count():
                    page.locator('.mobile-sidebar-close').click()
                    page.wait_for_timeout(300)
                if out:
                    page.screenshot(path=str(out / 'command-overview-390.png'), full_page=False)
                    page.locator('.map-cockpit .command-content').evaluate('(e) => e.scrollTo(0, e.scrollHeight / 2)')
                    page.wait_for_timeout(200)
                    page.screenshot(path=str(out / 'command-overview-390-scrolled.png'), full_page=False)
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
    print('PASS: command overview canvas, panels, interactions, responsive fallback')


if __name__ == '__main__':
    main()
