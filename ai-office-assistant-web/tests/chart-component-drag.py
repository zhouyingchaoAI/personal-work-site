from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/chart-component-drag.html')
    page.wait_for_selector('.chart-layout-tools')
    assert page.locator('.chart-layout-tools').count() == 4
    assert page.locator('.br-visual-unit .chart-layout-resize').count() == 0
    cards = page.locator('.br-chart-card')
    source = cards.nth(3).locator('.chart-layout-tools').bounding_box()
    target = cards.nth(0).bounding_box()
    page.mouse.move(source['x'] + source['width'] - 20, source['y'] + 10)
    page.mouse.down()
    page.mouse.move(target['x'] + 20, target['y'] + 50, steps=10)
    assert page.locator('.chart-layout-drop-target').count() == 1
    page.mouse.up()
    assert cards.nth(3).evaluate('element=>element.style.order') == '1'
    bounds = [cards.nth(index).bounding_box() for index in range(4)]
    assert bounds[3]['y'] == bounds[0]['y']
    assert bounds[2]['y'] > bounds[3]['y']
    handle = cards.nth(3).locator('.edge-right').bounding_box()
    page.mouse.move(handle['x'] + 4, handle['y'] + 10)
    page.mouse.down()
    page.mouse.move(handle['x'] + 5, handle['y'] + 10)
    assert page.locator('.chart-layout-guide.vertical').evaluate('element=>element.style.display') == 'block'
    page.mouse.up()
    print('PASS component-only handles, occupied-row insertion, resize guides')
    page.locator('main').evaluate('''element => {
        const panel = document.createElement('details');
        panel.className = 'be-disclosure';
        panel.innerHTML = '<summary>来源与核对口径</summary><article class="br-chart-card">内部明细</article>';
        element.append(panel);
    }''')
    source_panel = page.locator('details.be-disclosure')
    source_panel.locator('summary > .chart-layout-tools').wait_for(state='visible')
    assert not source_panel.evaluate('element => element.open')
    assert source_panel.locator('article .chart-layout-tools').count() == 0
    assert source_panel.locator(':scope > .chart-layout-resize').count() == 3
    print('PASS collapsed component drag controls and component-level resize handles')
    browser.close()
