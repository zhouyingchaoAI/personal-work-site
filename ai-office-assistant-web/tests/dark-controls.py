from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/dark-controls.html')
    page.wait_for_selector('.el-alert')
    for selector in ['.el-button', '.el-select__wrapper', '.el-alert']:
        dark = page.locator('.is-dark ' + selector).evaluate('element=>getComputedStyle(element).backgroundColor')
        light = page.locator('section:not(.is-dark) ' + selector).evaluate('element=>getComputedStyle(element).backgroundColor')
        assert dark != light, (selector, dark, light)
        assert dark in ['rgb(16, 43, 77)', 'rgb(19, 47, 74)'], (selector, dark)
    print('PASS cockpit buttons, selects and notices use dark backgrounds; light theme unchanged')
    browser.close()
