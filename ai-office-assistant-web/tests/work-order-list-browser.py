from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    records = [
        {'id':'own','title':'自己的工单','body':'我的完整描述','author':'本人','author_username':'me'},
        {'id':'other','title':'其他人的工单','body':'其他人描述','author':'本人','author_username':'someone-else'},
        {'id':'legacy','title':'历史工单','body':'历史描述','author':'本人'},
    ]
    for record in records:
        record.update(module='联指经营助手',status='open',comment_count=0,attachments=[])
    page.route('**/tickets', lambda route: route.fulfill(json={'tickets':records,'summary':{'total':3,'open':3,'closed':0}}))
    page.route('**/tickets/get?*', lambda route: route.fulfill(json={'ticket':{**records[0],'comments':[]}}))
    reminders = []
    def remind(route):
        reminders.append(route.request.post_data_json)
        route.fulfill(json={'ticket':{**records[0],'comment_count':1,'comments':[]}})
    page.route('**/tickets/comment', remind)
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/work-order-list.html')
    page.locator('.wo-card').first.wait_for()
    own = page.locator('.wo-card').filter(has_text='自己的工单')
    other = page.locator('.wo-card').filter(has_text='其他人的工单')
    legacy = page.locator('.wo-card').filter(has_text='历史工单')
    assert own.locator('.wo-card-body').is_visible()
    assert legacy.locator('.wo-card-body').is_visible()
    assert other.locator('.wo-card-body').count() == 0
    assert other.count() == 0
    assert page.locator('.wo-card').count() == 2
    own.get_by_role('button',name='催办',exact=True).click()
    page.get_by_role('button',name='已催办',exact=True).wait_for()
    assert len(reminders) == 1 and '催办' in reminders[0]['content']
    assert reminders[0]['status'] == ''
    assert page.get_by_role('region',name='提交人统计，可横向滚动').count() == 0
    page.evaluate("window.testAuth.user.role='superadmin'")
    stats = page.get_by_role('region',name='提交人统计，可横向滚动')
    stats.wait_for()
    assert stats.locator('tbody tr').count() == 3
    stats.locator('tbody tr').filter(has_text='someone-else').get_by_role('button',name='本人',exact=True).click()
    assert page.locator('.wo-card').count() == 1
    assert other.is_visible()
    page.get_by_role('button',name='清除用户筛选').click()
    assert page.locator('.wo-card').count() == 2
    page.get_by_role('button',name='展开其他人的工单列表（1）',exact=True).click()
    assert page.locator('.wo-card').count() == 3
    assert other.get_by_role('button',name='催办',exact=True).count() == 0
    page.evaluate("window.testAuth.user.role='member'")
    assert stats.count() == 0
    other.get_by_role('button', name='展开内容').click()
    assert other.locator('.wo-card-body').is_visible()
    own.get_by_role('button', name='收起内容').click()
    assert own.locator('.wo-card-body').count() == 0
    page.get_by_role('button', name='刷新', exact=True).click()
    assert own.locator('.wo-card-body').count() == 0
    page.evaluate("window.testRouter.push('/workspace/workorder?ticket=own')")
    page.get_by_role('dialog').wait_for()
    assert '我的完整描述' in page.get_by_role('dialog').inner_text()
    browser.close()
    print('PASS own/other defaults, legacy fallback, manual toggle, refresh and ticket deep link')
