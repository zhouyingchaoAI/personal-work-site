"""Regression: map fills its canvas, floating panels stay above the footer.

Runs an isolated backend and the built frontend; never writes live CRM data.
"""
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

def main():
    users = [{'username':'preview','role':'superadmin'}, {'username':'east-one','name':'东区客户经理甲','role':'member','department':'东区作战平台'}, {'username':'east-long','name':'客户经理姓名和负责团队特别长的测试人员','role':'member','department':'东区作战平台'}]
    with tempfile.TemporaryDirectory() as tmp, patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': users}), patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_audit'), patch.object(r.Handler, 'log_message'):
        server = r.ThreadingHTTPServer(('127.0.0.1', 0), r.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1920, 'height': 1080})
                base = f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                page.goto(base + '/workspace/crm')
                page.get_by_role('button', name='进入联合指挥驾驶舱').click(timeout=60000)
                page.locator('.command-navigation').get_by_role('button', name='五位一体', exact=True).click()
                page.get_by_role('button', name='全屏作战大屏', exact=True).click()
                assert page.locator('.integration-map-layout .map-cockpit__scope').count()==0, '顶部不再重复显示范围标题与操作说明'
                assert page.locator('.map-cockpit__review-context').count()==0, '删除当前查看范围提示栏'
                for width, height in [(1920,1080), (1366,768), (1024,768)]:
                    page.set_viewport_size({'width':width, 'height':height})
                    anchors=['.map-cockpit__modes','.map-cockpit__regions','.map-cockpit__stage']
                    baseline=None
                    for mode in ['区域指挥','客户经理','联合指挥','客户经理','区域指挥']:
                        page.locator('.map-cockpit__modes').get_by_role('button',name=mode,exact=True).click()
                        page.wait_for_timeout(350)
                        if mode=='客户经理':
                            picker=page.get_by_label('查看客户经理',exact=True)
                            picker.select_option('east-long')
                            page.wait_for_timeout(200)
                        measured=[page.locator(s).bounding_box() for s in anchors]
                        assert page.get_by_role('group', name='全区统计', exact=True).is_visible()
                        assert page.locator('.integration-summary b').count()==4
                        assert page.locator('.integration-assessment').count()==0
                        summary=page.locator('.integration-summary').bounding_box()
                        assert summary['height']<=36, '全区统计保持简洁单行'
                        assert summary['y']+summary['height']<=measured[2]['y']+1, '统计在地图上方'
                        head=page.locator('.map-cockpit__map-head').bounding_box()
                        assert measured[1]['y']-(head['y']+head['height'])<24, '区域卡前不能残留独立提示栏或占位空行'
                        if baseline is None: baseline=measured
                        for actual,expected in zip(measured,baseline):
                            assert abs(actual['x']-expected['x'])<2 and abs(actual['y']-expected['y'])<2, (width,mode,anchors,measured,baseline)
                        if len(sys.argv)>1 and mode=='客户经理':
                            out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
                            page.screenshot(path=str(out/f'manager-stable-{width}.png'))
                    for fallback in [True, False]:
                        # Exercise both layout variants without requiring external AMap credentials.
                        page.locator('.region-map').evaluate('(e, value)=>e.classList.toggle("region-map--fallback",value)', fallback)
                        page.wait_for_timeout(200)
                        boxes = [page.locator(s).bounding_box() for s in ['.region-map__left','.region-map__stage','.region-map__side']]
                        body = page.locator('.region-map__body').bounding_box()
                        assert abs(boxes[1]['width']-body['width'])<2 and abs(boxes[1]['height']-body['height'])<2, 'Map must fill the entire canvas'
                        assert abs(boxes[1]['x']-body['x'])<2 and abs(boxes[1]['y']-body['y'])<2, 'Map must start at canvas origin'
                        assert boxes[0]['x']+boxes[0]['width']<boxes[2]['x'], 'Floating panels leave no central map space'
                        for panel in [boxes[0],boxes[2]]:
                            assert panel['x']>=body['x'] and panel['x']+panel['width']<=body['x']+body['width']+1, 'Floating panel outside map'
                        assert page.locator('.region-map__side').evaluate('(e)=>getComputedStyle(e).pointerEvents')=='none', 'Overlay gaps must allow map interaction'
                        footer = page.locator('.map-cockpit__footer').bounding_box()
                        assert all(b['y']+b['height']<=footer['y']+1 for b in boxes), 'Panels overlap footer'
                        assert page.locator('.cockpit-expanded').evaluate('(e)=>e.scrollHeight<=e.clientHeight+2 && e.scrollWidth<=e.clientWidth+2'), 'Screen overflow'
                        print('PASS',width,height,'fallback' if fallback else 'online map shell',flush=True)
                    if len(sys.argv)>1:
                        out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(out/f'integration-{width}.png'))
                before=page.locator('.map-cockpit__modes').bounding_box()
                page.get_by_role('button',name='三层关系',exact=True).click()
                assessment=page.get_by_role('dialog',name='三层关系评估',exact=True)
                assessment.wait_for()
                assert assessment.get_by_text('三层关系一眼看清：公司覆盖、个人维系、组织渗透',exact=True).is_visible()
                assessment.locator('.ao-layer').first.wait_for()
                assert assessment.locator('.ao-layer').count()==3
                assessment.get_by_text('查看公司层评估 →',exact=True).click()
                assert assessment.locator('.ao').count()==0
                if len(sys.argv)>1:
                    assessment.locator('.assessment-tabs').get_by_text('总览',exact=True).click()
                    assessment.locator('.ao-layer').first.wait_for()
                    page.screenshot(path=str(Path(sys.argv[1])/'three-layer-overlay.png'))
                assessment.locator('.el-dialog__headerbtn').click()
                assessment.wait_for(state='hidden')
                assert page.locator('.map-cockpit__modes').bounding_box()==before
                assert page.locator('.cockpit-expanded').is_visible()
                page.get_by_role('button',name='三层关系',exact=True).click()
                assessment.wait_for()
                page.keyboard.press('Escape')
                assessment.wait_for(state='hidden')
                assert page.locator('.cockpit-expanded').is_visible(), 'Esc关闭关系浮层不能退出驾驶舱'
                page.get_by_role('button',name='数据明细',exact=True).click()
                page.get_by_role('dialog',name='区域数据明细').wait_for()
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()

if __name__ == '__main__':
    main()
