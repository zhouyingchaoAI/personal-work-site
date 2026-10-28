import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--data', required=True)
parser.add_argument('--artifacts', required=True)
args = parser.parse_args()
output = Path(args.artifacts)
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000})
    page.add_init_script('window.__REGION_DATA__=' + Path(args.data).read_text())
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/region-executive.html')
    for label in ['公司整体','任务令','区域经营','产业经营','经营结构','经营基础','项目监测']:
        page.locator('.ba-dashboard-nav button').filter(has_text=label).click()
        page.wait_for_timeout(300)
        badges = page.locator('.business-analysis .business-step')
        numbers = badges.all_text_contents()
        assert all(len(number.split('.')) <= 2 for number in numbers), (label,numbers)
        main = [number for number in numbers if '.' not in number]
        assert main == [str(index+1).zfill(2) for index in range(len(main))], (label, main)
        assert len(main) > 0, label
        if label == '公司整体':
            assert main == ['01','02','03','04','05','06'], main
        styles = badges.evaluate_all('(items) => items.map(item => {const style=getComputedStyle(item);return [style.fontSize,style.fontWeight,style.fontFamily,style.lineHeight].join("/")})')
        assert len(set(styles)) == 1, (label, styles)
        page.screenshot(path=str(output/(label+'-numbering.png')),full_page=True)
        print('PASS',label, json.dumps(numbers,ensure_ascii=False))
    browser.close()
