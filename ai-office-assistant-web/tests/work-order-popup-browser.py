from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    ticket = dict(id='own', title='自己的工单', body='问题内容', author='本人', author_username='me', status='accepted', module='联指经营助手', attachments=[], comments=[])
    ticket['attachments'] = [dict(id='image', name='截图.png', is_image=True, url='https://example.test/screenshot.svg')]
    page.route('https://example.test/screenshot.svg', lambda route: route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1600"><rect width="2400" height="1600" fill="blue"/></svg>'))
    page.route('**/tickets', lambda route: route.fulfill(json={'tickets': [ticket], 'summary': {'total': 1, 'open': 1, 'closed': 0}}))
    page.route('**/tickets/get?*', lambda route: route.fulfill(json={'ticket': ticket}))
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/work-order-popup.html')
    page.get_by_role('button', name='我的工单 · 查看进度').click()
    page.locator('.wo-card').wait_for()
    assert '问题内容' in page.locator('.wo-card').inner_text()
    assert page.evaluate('window.testRouter.currentRoute.value.fullPath') == '/workspace/crm?section=industry'
    page.locator('.el-dialog__headerbtn').first.click()
    page.locator('.wo-card').wait_for(state='hidden')
    page.evaluate("window.openTicket('own')")
    thumbnail = page.locator('.ticket-attachment-preview')
    thumbnail.wait_for()
    thumbnail.evaluate("element => Promise.all(element.getAnimations({subtree:true}).map(animation => animation.finished))")
    page.wait_for_timeout(500)
    bounds = thumbnail.bounding_box()
    assert bounds['width'] <= 200 and bounds['height'] <= 150, bounds
    thumbnail.click()
    page.locator('.el-image-viewer__wrapper').wait_for()
    page.locator('.el-image-viewer__close').click()
    page.locator('.el-image-viewer__wrapper').wait_for(state='hidden')
    assert page.evaluate('window.testRouter.currentRoute.value.fullPath') == '/workspace/crm?section=industry'
    browser.close()
    print('PASS popup list, close, ticket detail and unchanged navigation')
