"""Chart workspace regression: topic paging, enlarged charts, tables and original data."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from verify_business_analysis_dashboard import fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backend.runtime as r

def main():
    out = Path(sys.argv[1]) if len(sys.argv)>1 and not sys.argv[1].startswith('--') else None
    if out: out.mkdir(parents=True, exist_ok=True)
    data = fixture()
    if '--real' in sys.argv:
        data = json.loads((ROOT/'user_data/_crm_business_analysis.json').read_text())
        data['dashboard'] = r.crm_compute_dashboard_data(data['sheets'])
    data['version'] = 'preview'
    with tempfile.TemporaryDirectory() as tmp, patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[{'username':'preview','role':'superadmin'}]}), patch.object(r,'SESSIONS',{'preview':'preview'}), patch.object(r,'crm_audit'), patch.object(r.Handler,'log_message'):
        server=r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1920,'height':1080})
                errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
                base=f'http://127.0.0.1:{server.server_port}'
                page.context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page.route('**/api/crm/business-analysis*',lambda route:route.fulfill(json={'ok':True,'versions':[],'data':data}))
                page.route('**/api/crm/security/amap-settings',lambda route:route.fulfill(json={'enabled':False}))
                page.goto(base+'/workspace/crm')
                page.get_by_role('button',name='进入联合指挥驾驶舱').click(timeout=60000)
                page.get_by_role('button',name='全屏作战大屏',exact=True).click()
                shell_style="e=>{const s=getComputedStyle(e);return {background:s.backgroundImage,logo:getComputedStyle(e.querySelector('.map-cockpit__logo')).height,title:getComputedStyle(e.querySelector('.map-cockpit__brand h2')).fontSize,nav:getComputedStyle(e.querySelector('.command-navigation')).backgroundImage}}"
                overview_shell=page.locator('.map-cockpit').evaluate(shell_style)
                page.locator('.command-navigation').get_by_role('button',name='经营分析',exact=True).click()
                page.locator('.br-workspace').wait_for()
                assert page.locator('.map-cockpit').evaluate(shell_style)==overview_shell,'经营分析必须沿用总体信息的背景、页头和导航样式'
                assert page.locator('.business-analysis').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgba(0, 0, 0, 0)','不能用整块实色遮住驾驶舱背景'
                assert page.locator('.br-kpi').count()==6
                if out: page.screenshot(path=str(out/'workspace-overview.png'))
                assert page.locator('.br-workspace .br-section').count()==6, '六个分析分区必须同时存在，不拆页'
                assert page.locator('.ba-hero').count()==0, '经营洞察横幅已按用户要求移除'
                assert page.locator('.ba-topic-nav button').count()==0
                assert page.get_by_role('button',name='下一页',exact=True).count()==0
                assert page.locator('.br-workspace [data-chart-kind="donut"]').count()>0
                assert page.locator('.br-workspace [data-chart-kind="pie"]').count()>0
                checked=set(); charts=0
                for dimension in ['公司整体','经营结构','区域经营','产业经营','经营基础','项目监测']:
                    page.locator('.ba-dashboard-nav').get_by_role('button',name=dimension,exact=True).click()
                    page.wait_for_timeout(900)
                    key={'公司整体':'overall','经营结构':'structure','区域经营':'region','产业经营':'industry','经营基础':'foundation','项目监测':'projects'}[dimension]
                    section=page.locator(f'.br-workspace [data-section="{key}"]')
                    for i in range(section.locator('.br-chart-card').count()):
                        assert page.locator('.br-workspace table').count()==0
                        card=section.locator('.br-chart-card').nth(i)
                        if not card.count(): continue
                        assert card.count()==1
                        charts+=1
                        assert card.locator('[data-chart-step]').count()==0
                        row_counts=card.locator('.br-plot-bars,.br-heat').evaluate_all("charts=>charts.map(c=>{const rows=[...c.querySelectorAll('.br-plot-row,.br-heat-row')];return [rows.length,rows.filter(r=>!r.hidden).length]})")
                        assert all(visible==min(total,5) for total,visible in row_counts),row_counts
                        if out and i==0: page.screenshot(path=str(out/f'workspace-{dimension}.png'))
                        card.locator('header').click()
                        page.get_by_role('dialog').wait_for()
                        assert page.locator('.ba-detail-tabs button.active').inner_text()=='放大图表'
                        assert page.locator('.br-enlarged-chart').is_visible()
                        restored=page.locator('.br-enlarged-chart .br-plot-bars,.br-enlarged-chart .br-heat').evaluate_all("charts=>charts.map(c=>[...c.querySelectorAll('.br-plot-row,.br-heat-row')].filter(r=>!r.hidden).length)")
                        assert restored==[total for total,_ in row_counts],(restored,row_counts)
                        if out and dimension=='产业经营' and i==0:
                            page.wait_for_timeout(300)
                            page.screenshot(path=str(out/'enlarged-chart.png'))
                        page.locator('.ba-detail-tabs').get_by_role('button',name='数据表',exact=True).click()
                        if page.locator('.br-enlarged-data').count(): assert page.locator('.br-enlarged-data').is_visible()
                        page.locator('.ba-detail-tabs').get_by_role('button',name='原始数据',exact=True).click()
                        for raw in page.locator('.br-modal-sources .br-raw').all():
                            key=raw.get_attribute('data-source-sheet'); checked.add(key)
                            source=next(s for s in data['sheets'] if s['key']==key)
                            assert raw.locator('tbody tr').count()==len(source['rows'])
                        page.locator('.ba-raw-dialog .el-dialog__headerbtn').click()
                        page.get_by_role('dialog').wait_for(state='hidden'); page.wait_for_timeout(250)
                assert charts>=19,charts
                assert len(checked)==19,checked
                page.locator('.ba-dashboard-nav').get_by_role('button',name='区域经营',exact=True).click()
                page.locator('[data-region-series="0"]').click()
                regional=page.locator('[data-chart-title="区域经营结果"]')
                assert regional.locator('.br-chart-legend>span:not([hidden])').inner_text()=='收入'
                assert regional.locator('.br-plot-row').first.locator('.br-series-row:not([hidden])').count()==1
                page.locator('[data-region-series="-1"]').click()
                assert regional.locator('.br-chart-legend>span:not([hidden])').count()==3
                page.locator('.ba-data-center').click()
                assert page.locator('.br-modal-sources .br-raw').count()==19
                page.locator('.ba-raw-dialog .el-dialog__headerbtn').click()
                page.get_by_role('dialog').wait_for(state='hidden')
                for width,height in [(1920,1080),(2560,1440),(1440,900),(1366,768),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
                    page.locator('.ba-dashboard-nav').get_by_role('button',name='公司整体',exact=True).click()
                    page.locator('.command-content').evaluate('(e)=>e.scrollTop=0')
                    page.wait_for_timeout(900)
                    assert page.locator('.business-analysis').evaluate('(e)=>e.scrollWidth<=e.clientWidth+2'),width
                    assert page.locator('.business-analysis').bounding_box()['width']<=1801,width
                    assert page.locator('.br-chart-card').evaluate_all('(els)=>els.every(e=>e.scrollWidth<=e.clientWidth+2)'),width
                    if out: page.screenshot(path=str(out/f'workspace-{width}.png'))
                if out:
                    page.set_viewport_size({'width':1920,'height':1080})
                    page.evaluate('''() => {
                        const board=document.querySelector('.business-analysis');const width=board.getBoundingClientRect().width;
                        for(let p=board.parentElement;p;p=p.parentElement) for(const [k,v] of Object.entries({height:'auto','max-height':'none',overflow:'visible',position:'relative',transform:'none',flex:'none'}))p.style.setProperty(k,v,'important');
                        board.style.width=width+'px';document.querySelector('.ba-dashboard-nav').style.position='static';
                    }''')
                    page.locator('.business-analysis').screenshot(path=str(out/'business-bi-full.png'),timeout=60000)
                assert not errors,errors
                browser.close()
        finally: server.shutdown();server.server_close()
    print('PASS continuous multi-chart dashboard, pie/donut, enlarged chart/table/source switching, 19 source sheets, responsive')

if __name__=='__main__': main()
