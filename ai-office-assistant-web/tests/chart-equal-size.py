from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/profit-layout.html')
    page.wait_for_selector('.chart-layout-tools')
    panels = page.locator('.be-profit-panel')

    def resize(panel, edge, delta):
        handle = panel.locator('.edge-' + edge).bounding_box()
        horizontal = handle['x'] + handle['width'] / 2
        vertical = handle['y'] + handle['height'] / 2
        page.mouse.move(horizontal, vertical)
        page.mouse.down()
        page.mouse.move(horizontal + (delta if edge == 'right' else 0), vertical + (delta if edge == 'bottom' else 0), steps=8)
        page.mouse.up()
        page.wait_for_timeout(150)

    resize(panels.nth(0), 'right', -110)
    target = panels.nth(0).bounding_box()
    current = panels.nth(1).bounding_box()
    resize(panels.nth(1), 'right', target['width'] - current['width'] + 5)
    assert abs(panels.nth(1).bounding_box()['width'] - target['width']) < 1
    resize(panels.nth(0), 'bottom', 90)
    target = panels.nth(0).bounding_box()
    current = panels.nth(1).bounding_box()
    resize(panels.nth(1), 'bottom', target['height'] - current['height'] + 5)
    for action in [lambda: None, lambda: page.get_by_text('切换编辑').click(), lambda: page.reload()]:
        action()
        page.wait_for_timeout(250)
        first = panels.nth(0).bounding_box()
        second = panels.nth(1).bounding_box()
        assert abs(first['width'] - second['width']) < 1, (first, second)
        assert abs(first['height'] - second['height']) < 1, (first, second)
        assert abs(first['y'] - second['y']) < 1, (first, second)
    print('PASS equal-size snapping, row alignment, finish editing and reload')
    browser.close()
