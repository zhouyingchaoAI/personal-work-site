from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.add_init_script('''if (!localStorage.getItem('seeded')) {
        localStorage.setItem('industry-layout-test', JSON.stringify({'目标': {pixelWidth: 300,pixelHeight: 250,contentZoom: .6}, '毛利': {pixelWidth: 650,pixelHeight: 450,contentZoom: 1.3}}));
        localStorage.setItem('seeded', '1');
    }''')
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/industry-layout.html')
    page.wait_for_selector('.chart-layout-tools')
    page.get_by_text('统一产业图表尺寸').click()
    for reload in [False, True]:
        if reload:
            page.reload()
        page.wait_for_selector('.chart-layout-tools')
        sizes = page.locator('.br-chart-card').evaluate_all('(cards) => cards.map(card => ({width:card.getBoundingClientRect().width,height:card.getBoundingClientRect().height,top:card.getBoundingClientRect().top,zoom:getComputedStyle(card).zoom}))')
        for field in ['width', 'height', 'top']:
            assert max(item[field] for item in sizes) - min(item[field] for item in sizes) < 1, sizes
        assert all(item['zoom'] == '1' for item in sizes)
    print('PASS industry saved unequal sizes and zoom reset, persist after reload')
    browser.close()
