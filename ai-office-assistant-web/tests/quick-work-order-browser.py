import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--artifacts', required=True)
args = parser.parse_args()
output = Path(args.artifacts)
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    uploads = []
    tickets = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def upload(route):
        uploads.append(route.request.post_data_buffer)
        route.fulfill(json={'ok': True, 'attachment': {'id':'shot','name':'截图.png','type':'image/png','size':123,'url':'/fixture.png','is_image':True}})
    def submit(route):
        tickets.append(route.request.post_data_json)
        if len(tickets) == 1:
            route.fulfill(status=500, json={'error':'测试失败重试'})
        else:
            route.fulfill(json={'ok':True,'ticket':{'id':'test'}})
    page.route('**/forum/attachment', upload)
    page.route('**/tickets/create', submit)
    page.goto('http://127.0.0.1:5179/personal-office-assistant/tests/fixtures/quick-work-order.html')
    page.get_by_role('button', name='截图并快速提交工单').click()
    canvas = page.locator('.quick-ticket-canvas canvas')
    canvas.wait_for(timeout=30000)
    assert canvas.evaluate('(element) => element.width') == 1440
    assert canvas.evaluate('''element => {
        const pixels = element.getContext('2d').getImageData(0, 0, element.width, element.height).data;
        const colors = new Set();
        for (let index = 0; index < pixels.length; index += 400) colors.add(`${pixels[index]},${pixels[index+1]},${pixels[index+2]}`);
        return colors.size > 10;
    }'''), '现代颜色页面应生成有内容的截图，而不是空白画布'
    assert '产业经营' in page.locator('.quick-ticket-location').first.inner_text()
    assert not uploads and not tickets
    assert not page.get_by_role('button', name='截图并快速提交工单').is_visible()
    bounds = canvas.bounding_box()
    page.mouse.move(bounds['x']+30, bounds['y']+30)
    page.mouse.down()
    page.mouse.move(bounds['x']+170, bounds['y']+90)
    page.mouse.up()
    assert page.get_by_role('button', name='撤销', exact=True).is_enabled()
    page.get_by_role('button', name='撤销', exact=True).click()
    assert page.get_by_role('button', name='撤销', exact=True).is_disabled()
    assert page.get_by_text('画笔', exact=True).count() == 0
    assert page.get_by_role('textbox', name='截图标记文字').count() == 0
    page.mouse.move(bounds['x']+170, bounds['y']+90)
    page.mouse.down()
    page.mouse.move(bounds['x']+30, bounds['y']+30)
    page.mouse.up()
    assert page.locator('.quick-ticket-crops figure').count() == 1
    assert page.locator('.quick-ticket-crops img').evaluate('(img) => img.naturalWidth > 0 && img.naturalWidth < 1440')
    page.get_by_role('textbox', name='问题描述').fill('图表宽度没有对齐，请统一。')
    page.screenshot(path=str(output/'quick-ticket-desktop.png'), full_page=True)
    page.get_by_role('button', name='提交工单', exact=True).click()
    page.get_by_text('测试失败重试', exact=False).first.wait_for()
    assert len(uploads) == 2
    assert tickets[0]['module'] == '联指经营助手'
    assert '产业经营' in tickets[0]['body']
    assert len(tickets[0]['attachments']) == 2
    page.get_by_role('button', name='提交工单', exact=True).click()
    page.wait_for_function("!document.querySelector('.quick-ticket-dialog') || document.querySelector('.quick-ticket-dialog').getBoundingClientRect().height === 0")
    assert len(uploads) == 2 and len(tickets) == 2
    original_path = page.evaluate('window.testRouter.currentRoute.value.fullPath')
    page.get_by_role('button', name='查看工单', exact=True).click()
    assert page.evaluate('window.testRouter.currentRoute.value.fullPath') == original_path
    page.evaluate("window.testRouter.push('/workspace/weekly')")
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button', name='截图并快速提交工单').click()
    canvas.wait_for(timeout=30000)
    assert '周报助手' in page.locator('.quick-ticket-location').first.inner_text()
    page.get_by_role('button', name='移除截图', exact=True).click()
    assert canvas.count() == 0
    page.get_by_role('textbox', name='问题描述').fill('周报内容不正确')
    page.wait_for_timeout(3200)
    page.screenshot(path=str(output/'quick-ticket-mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='提交工单', exact=True).click()
    page.wait_for_timeout(500)
    assert len(tickets) == 3 and len(uploads) == 2
    assert tickets[-1]['module'] == '周报助手' and not tickets[-1]['attachments']
    assert not errors, errors
    browser.close()
    print('PASS screenshot, annotation, navigation, upload-on-submit, retry, mobile')
