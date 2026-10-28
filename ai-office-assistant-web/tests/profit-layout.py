from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/profit-layout.html')
    page.wait_for_selector('.be-profit-panel > .chart-layout-tools')
    assert page.locator('.be-profit-panel > .chart-layout-tools').count() == 4
    assert page.locator('.br-visual-unit > .chart-layout-tools').count() == 0
    panel = page.locator('.be-profit-panel').first
    before = panel.bounding_box()
    original_zoom = panel.evaluate('element => getComputedStyle(element).zoom')
    handle = panel.locator('.edge-right').bounding_box()
    page.mouse.move(handle['x'] + handle['width'] / 2, handle['y'] + handle['height'] / 2)
    page.mouse.down()
    page.mouse.move(handle['x'] - 100, handle['y'] + handle['height'] / 2, steps=10)
    page.mouse.up()
    page.wait_for_timeout(300)
    resized = panel.bounding_box()
    assert panel.evaluate('element => getComputedStyle(element).zoom') == original_zoom
    assert resized['width'] < before['width'] - 30, (before, resized)
    bottom = panel.locator('.edge-bottom').bounding_box()
    page.mouse.move(bottom['x'] + bottom['width'] / 2, bottom['y'] + bottom['height'] / 2)
    page.mouse.down()
    page.mouse.move(bottom['x'] + bottom['width'] / 2, bottom['y'] + 80, steps=10)
    page.mouse.up()
    page.wait_for_timeout(300)
    resized = panel.bounding_box()
    assert resized['height'] > before['height'] + 30
    page.get_by_text('切换编辑', exact=True).click()
    page.wait_for_timeout(300)
    assert abs(panel.bounding_box()['width'] - resized['width']) < 2
    assert abs(panel.bounding_box()['height'] - resized['height']) < 2
    page.reload()
    page.wait_for_selector('.be-profit-panel > .chart-layout-tools')
    assert abs(page.locator('.be-profit-panel').first.bounding_box()['width'] - resized['width']) < 2
    assert abs(page.locator('.be-profit-panel').first.bounding_box()['height'] - resized['height']) < 2
    print('PASS profit panels: outer editing, independent width, preview and reload persistence')
    browser.close()
