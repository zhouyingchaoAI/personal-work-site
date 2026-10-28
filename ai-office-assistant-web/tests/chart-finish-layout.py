from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/chart-editor.html')
    page.wait_for_selector('.chart-layout-tools')
    measure = '''()=>{const parent=document.querySelector('.br-kpis').getBoundingClientRect();return [...document.querySelectorAll('.br-kpi')].map(element=>{const rect=element.getBoundingClientRect();return [rect.x-parent.x,rect.y-parent.y,rect.width,rect.height]})}'''
    before = page.evaluate(measure)
    page.get_by_role('button', name='预览切换', exact=True).click()
    page.wait_for_function("!document.querySelector('.chart-layout-tools')")
    after = page.evaluate(measure)
    assert before == after, (before, after)
    page.get_by_role('button', name='预览切换', exact=True).click()
    page.wait_for_selector('.chart-layout-tools')
    assert before == page.evaluate(measure)
    print('PASS finishing and reopening layout preserves all card dimensions and relative positions')
    browser.close()
