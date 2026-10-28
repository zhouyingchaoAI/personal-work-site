import json
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    saved = {f'{name}:{index}': {"pixelWidth": 280, "pixelHeight": 300, "contentZoom": 1.2} for index, name in enumerate(['订货', '回款', '毛利'])}
    page.add_init_script(f"localStorage.setItem('editor-browser-fixture', JSON.stringify({json.dumps(saved)}))")
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/chart-editor.html')
    page.wait_for_selector('.chart-layout-tools')
    cards = page.locator('.br-kpi')
    before = [cards.nth(index).bounding_box() for index in range(3)]
    for bounds in before:
        assert abs(bounds['width'] - 280) < 2, bounds
    page.evaluate('window.editorTest.compact()')
    after = [cards.nth(index).bounding_box() for index in range(3)]
    for first, second in zip(before, after):
        assert abs(first['width'] - second['width']) < 1
        assert abs(first['height'] - second['height']) < 1
    assert cards.first.evaluate('element=>element.style.zoom') == '1.2'
    print('PASS compact preserves component widths, heights and content zoom')
    browser.close()
