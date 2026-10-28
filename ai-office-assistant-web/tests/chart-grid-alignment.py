from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/profit-layout.html')
    page.wait_for_selector('.chart-layout-tools')
    page.locator('main').evaluate('''element => {
        element.style.width = '1001px';
        const header = document.createElement('header');
        header.textContent = '经营基础';
        header.style.gridColumn = '1 / -1';
        element.prepend(header);
    }''')
    page.wait_for_timeout(200)
    panels = page.locator('.be-profit-panel')
    handle = panels.first.locator('.edge-bottom').bounding_box()
    page.mouse.move(handle['x'] + 10, handle['y'] + 4)
    page.mouse.down()
    page.mouse.move(handle['x'] + 10, handle['y'] + 65, steps=8)
    page.mouse.up()
    for toggle in [False, True, True]:
        if toggle:
            page.get_by_text('切换编辑').click()
        page.wait_for_timeout(200)
        first = panels.nth(0).bounding_box()
        second = panels.nth(1).bounding_box()
        assert abs(first['y'] - second['y']) < 1, (first, second)
    print('PASS fractional grid width: resize and finish do not push aligned cards into next row')
    browser.close()
