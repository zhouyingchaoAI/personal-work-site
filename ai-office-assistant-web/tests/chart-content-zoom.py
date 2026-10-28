from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/chart-editor.html')
    page.wait_for_selector('.edge-right')
    card = page.locator('.br-kpi').first
    initial = card.locator(':scope > strong').bounding_box()['height']
    handle = card.locator('.edge-right')
    page.add_style_tag(content='.edge-right{top:32px!important;bottom:auto!important;height:80px!important;right:0!important;touch-action:none}.edge-bottom{left:0!important;right:auto!important}')
    handle.scroll_into_view_if_needed()
    position = handle.bounding_box()
    page.mouse.move(position['x'] + 5, position['y'] + 5)
    page.mouse.down()
    page.mouse.move(position['x'] + 85, position['y'] + 5, steps=8)
    page.mouse.up()
    page.wait_for_timeout(200)
    enlarged = card.locator(':scope > strong').bounding_box()['height']
    assert enlarged > initial * 1.05, (initial, enlarged)
    assert float(card.evaluate('element=>element.style.zoom')) > 1
    page.reload()
    page.wait_for_selector('.edge-right')
    assert card.locator(':scope > strong').bounding_box()['height'] > initial * 1.05
    card.get_by_role('button', name='复原', exact=True).click()
    assert float(card.evaluate('element=>element.style.zoom')) == 1
    print('PASS edge resize scales inner text, persists after reload and restores')
    browser.close()
