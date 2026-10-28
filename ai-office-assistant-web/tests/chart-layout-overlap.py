from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    for width in [1440, 1000, 390]:
        page.set_viewport_size({"width": width, "height": 900})
        page.goto("http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/chart-layout-overlap.html")
        page.wait_for_selector('[data-layout-id]')
        for reload in [False, True]:
            if reload:
                page.reload()
                page.wait_for_selector('[data-layout-id]')
            rectangles = page.locator('.br-chart-card').evaluate_all('(items)=>items.map(element=>{const rect=element.getBoundingClientRect();return {left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom,height:rect.height}})')
            for index, rectangle in enumerate(rectangles):
                assert rectangle['height'] >= 300, rectangle
                assert rectangle['right'] <= width, rectangle
                for other in rectangles[index+1:]:
                    overlap = min(rectangle['right'],other['right'])-max(rectangle['left'],other['left']) > 1 and min(rectangle['bottom'],other['bottom'])-max(rectangle['top'],other['top']) > 1
                    assert not overlap, (width,rectangle,other)
    print('PASS no overlap with oversized saved widths, short saved heights, legacy scale, three viewport sizes and reload')
    browser.close()
