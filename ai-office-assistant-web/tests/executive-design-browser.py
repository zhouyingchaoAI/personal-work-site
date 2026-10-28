import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--data', required=True)
parser.add_argument('--artifacts', required=True)
args = parser.parse_args()
artifacts = Path(args.artifacts)
artifacts.mkdir(parents=True, exist_ok=True)
pages = [('overall', '公司整体'), ('taskOrder', '任务令'), ('structure', '经营结构'), ('industry', '产业经营'), ('foundation', '经营基础'), ('projects', '项目监测')]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1024})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('window.__REGION_DATA__=' + json.dumps(json.loads(Path(args.data).read_text())))
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/region-executive.html')
    page.locator('.ba-dashboard-nav').wait_for()
    assert page.locator('.ba-dashboard-nav button').filter(has_text='数据核验').count() == 0
    for key, label in pages:
        page.locator('.ba-dashboard-nav button').filter(has_text=label).click()
        page.locator('.be-page').wait_for(timeout=4000)
        page.wait_for_function("Array.from(document.querySelectorAll('.be-page-icon')).length > 0 && Array.from(document.querySelectorAll('.be-page-icon')).every(icon => icon.naturalWidth > 0)")
        disclosures = page.locator('.be-page details.be-disclosure')
        if key == 'industry':
            cards = page.locator('.be-industry-comparison > .br-chart-card')
            bounds = [card.bounding_box() for card in cards.all()]
            assert len(bounds) == 3
            assert max(item['width'] for item in bounds) - min(item['width'] for item in bounds) < 1
            assert max(item['y'] for item in bounds) - min(item['y'] for item in bounds) < 1
            assert cards.evaluate_all('(items) => items.every(item => item.dataset.layoutKey.startsWith("industry-comparison-v2:"))')
        source_directory = page.locator('.be-source-directory')
        if source_directory.count():
            assert not source_directory.evaluate('(node) => node.open')
            assert source_directory.bounding_box()['height'] < 70
            source_directory.evaluate('(node) => { node.style.height = "800px"; node.style.minHeight = "800px" }')
            assert source_directory.bounding_box()['height'] < 70, 'collapsed sources must ignore stale saved height'
            source_directory.evaluate('(node) => { node.style.height = ""; node.style.minHeight = "" }')
            assert source_directory.evaluate('(node) => node.nextElementSibling.classList.contains("ba-page-footer")')
            assert page.locator('.be-page .br-source-group').count() == 0
        if key == 'overall':
            assert disclosures.count() == 0
            assert page.locator('.be-target-matrix').count() == 0
            assert page.locator('.be-profit-icon').count() == 1
            page.wait_for_function("Array.from(document.querySelectorAll('.be-profit-icon')).every(icon => icon.naturalWidth > 0)")
            assert page.locator('.be-profit-flow > .be-platform').count() == 1
            assert page.locator('.be-combined .br-cartesian').count() == 1
            assert page.locator('.monthly-trends svg').count() == 2
            assert page.locator('.monthly-columns svg rect').count() > 0
            assert page.locator('.monthly-columns svg path[stroke-linejoin="round"]').count() == 0
            assert page.locator('.be-page .br-kpi .br-bar-track').count() == 5
            assert page.locator('.be-profit-panel').count() >= 2
            assert page.locator('.be-scale').count() == 0
            assert page.locator('.be-cash-kpi').count() == 1
            assert page.locator('.profit-basis-control select').input_value() == '公司'
            assert page.locator('.be-profit-final').bounding_box()['y'] > page.locator('.be-company-detail').last.bounding_box()['y']
            page.locator('.profit-basis-control select').select_option('利润核算角度')
            assert page.locator('.be-combined .br-chart-legend').inner_text().strip() == '利润核算角度'
            page.locator('.profit-basis-control select').select_option('公司')
        else:
            assert disclosures.count(), label + ': missing progressive disclosure'
        assert disclosures.evaluate_all('(items) => items.every(item => !item.open)'), label + ': details should start closed'
        page.wait_for_timeout(250)
        page.screenshot(path=str(artifacts / (key + '-desktop.png')), full_page=True)
        if disclosures.count():
            first = disclosures.first
            first.locator(':scope > summary').click()
            assert first.evaluate('(item) => item.open'), label + ': cannot expand'
            assert not page.locator('.el-dialog:visible').count(), label + ': expand opened chart dialog'
            first.locator(':scope > summary').click()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(200)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), label + ': mobile overflow'
        page.screenshot(path=str(artifacts / (key + '-mobile.png')), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1024})
        print('PASS', label, 'icons, disclosure, mobile overflow')
    page.locator('.ba-dashboard-nav button').filter(has_text='区域经营').click()
    assert page.locator('.rx-designed-matrix').count() == 1
    assert page.locator('.rx-conversion-cell').count() == 0
    assert '折算比' in page.locator('.rx-designed-matrix').inner_text()
    assert '管理订货' in page.locator('.rx-designed-matrix').inner_text()
    assert not errors, errors
    browser.close()
