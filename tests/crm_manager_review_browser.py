"""Run against the built frontend, isolated CRM data, no production writes."""
import sys, tempfile, threading, os
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

with tempfile.TemporaryDirectory(prefix='manager-review-') as tmp:
    users = [{'username':'admin','name':'管理员','role':'superadmin'},
             {'username':'alice','employee_id':'E001','name':'甲经理','assistant_permissions':{'crm':True}},
             {'username':'bob','name':'乙经理'}]
    with patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':users}), patch.object(r,'SESSIONS',{'preview':'admin','personal':'alice'}), patch.object(r,'crm_on_change'), patch.object(r,'crm_audit'):
        for key, region, count in [('E001','西区',2),('bob','东区',1)]:
            for i in range(count):
                unit_data={'name':f'{region}单位{i}','type':'业主单位','business_regions':[region]}
                if key == 'E001' and i == 0: unit_data['company_full_name']='示例轨道集团有限公司'
                u=r.crm_unit_save(unit_data,'admin')['unit']
                p=r.crm_person_save({'name':f'{region}人员{i}','unit_id':u['id']},'admin')['person']
                rel=r.crm_relation_save({'person_id':p['id'],'our_member':key},'admin')['relation']
                r.crm_action_add({'relation_id':rel['id'],'type':'拜访','record_kind':'plan','next_step':'回访计划','due_date':'2026-09-20'},'admin')
        class QuietHandler(r.Handler):
            def log_message(self,*args): pass
        server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
                ctx=browser.new_context(viewport={'width':1366,'height':768})
                ctx.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/workspace/crm')
                artifact=os.environ.get('CRM_ARTIFACT_DIR')
                if artifact: Path(artifact).mkdir(parents=True,exist_ok=True)
                deck=page.locator('.map-cockpit');deck.wait_for()
                heading=page.locator('.crm-head')
                assert heading.bounding_box()['height']<=100, 'CRM header wastes vertical space'
                assert deck.bounding_box()['y']-heading.bounding_box()['y']<=150, 'extra space above working area'
                heading.get_by_role('button',name='区域设置',exact=True).click()
                settings=page.get_by_role('dialog',name='标准区域设置',exact=True)
                expect(settings).to_be_visible()
                assert settings.bounding_box()['height']>200, 'settings dialog clipped by compact toolbar'
                page.keyboard.press('Escape');expect(settings).not_to_be_visible()
                heading.get_by_role('button',name='信息收集',exact=True).click()
                capture=page.get_by_role('dialog',name='客户经营信息收集',exact=True)
                company=capture.get_by_label('公司全称',exact=True)
                company.fill('示例轨道')
                expect(page.get_by_role('option',name='示例轨道集团有限公司',exact=True)).to_be_visible()
                page.get_by_role('option',name='示例轨道集团有限公司',exact=True).click()
                company_field=company.locator('xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," el-form-item ")]')
                expect(company_field).to_contain_text('示例轨道集团有限公司')
                expect(capture.get_by_text('已匹配已有公司',exact=False)).to_be_visible()
                company.fill('全新客户科技有限公司')
                page.keyboard.press('Enter')
                expect(company_field).to_contain_text('全新客户科技有限公司')
                expect(capture.get_by_text('保存时将自动创建公司',exact=False)).to_be_visible()
                if artifact:
                    capture.screenshot(path=str(Path(artifact)/'客户收集-公司模糊搜索与新增.png'))
                capture.get_by_role('button',name='取消',exact=True).click();expect(capture).not_to_be_visible()
                if artifact:
                    page.screenshot(path=str(Path(artifact)/'紧凑顶部与工作区.png'))
                print('Compact header height:',round(heading.bounding_box()['height']), 'workspace offset:',round(deck.bounding_box()['y']-heading.bounding_box()['y']))
                expect(deck.locator('.map-cockpit__support')).to_have_count(0)
                expect(deck.locator('.region-map__body .map-support')).to_have_count(2)
                for width,height in [(1366,768),(1024,900),(1920,1080)]:
                    page.set_viewport_size({'width':width,'height':height})
                    geometry=deck.locator('.region-map__body').evaluate('(e)=>({body:e.getBoundingClientRect().toJSON(),panels:[...e.querySelectorAll(".map-support")].map(p=>p.getBoundingClientRect().toJSON())})')
                    body=geometry['body']
                    for box in geometry['panels']:
                        assert box['x']>=body['x']-1 and box['x']+box['width']<=body['x']+body['width']+1
                        assert box['y']>=body['y']-1 and box['y']+box['height']<=body['y']+body['height']+1, f'normal-mode panel extends below map: {width=} {body=} {box=}'
                    assert deck.locator('.region-map__side').evaluate('(e)=>e.scrollHeight<=e.clientHeight+1'), 'normal side panels overflow'
                artifact=os.environ.get('CRM_ARTIFACT_DIR')
                if artifact:
                    Path(artifact).mkdir(parents=True,exist_ok=True)
                    deck.screenshot(path=str(Path(artifact)/'普通状态地图叠层.png'))
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile overflow'
                page.set_viewport_size({'width':1366,'height':768})
                filters=deck.locator('.region-map__filters')
                total=filters.get_by_role('button',name='全部类型',exact=False).locator('em')
                owners=filters.get_by_role('button',name='业主单位',exact=False).locator('em')
                expect(total).to_have_text('3')
                for region, count in [('东区','1'),('西区','2')]:
                    deck.get_by_label('地图区域',exact=True).select_option(region)
                    expect(total).to_have_text(count)
                    expect(owners).to_have_text(count)
                    for kind in ['主管单位','总包单位','设计单位','厂商']:
                        expect(filters.get_by_role('button',name=kind,exact=False).locator('em')).to_have_text('0')
                    filters.get_by_role('button',name='厂商',exact=False).click()
                    expect(deck.locator('.map-cockpit__metrics button').nth(0).locator('strong')).to_have_text('0')
                    filters.get_by_role('button',name='全部类型',exact=False).click()
                    expect(deck.locator('.map-cockpit__metrics button').nth(0).locator('strong')).to_have_text(count)
                deck.get_by_label('地图区域',exact=True).select_option('')
                expect(total).to_have_text('3')
                deck.get_by_role('button',name='客户经理',exact=True).click()
                selector=deck.get_by_label('查看客户经理',exact=True)
                expect(selector).to_be_visible()
                personnel_region=deck.get_by_label('人员所属区域',exact=True)
                personnel_region.select_option('东区')
                expect(selector).to_have_value('bob')
                expect(selector.locator('option')).to_have_count(1)
                expect(deck.locator('.map-cockpit__metrics button').nth(1).locator('strong')).to_have_text('1')
                personnel_region.select_option('西区')
                expect(selector).to_have_value('alice')
                expect(selector.locator('option')).to_have_count(1)
                expect(deck.get_by_label('地图区域',exact=True)).to_have_value('')
                expect(deck.locator('.map-cockpit__metrics button').nth(1).locator('strong')).to_have_text('2')
                expect(deck.get_by_role('button',name='下一位',exact=True)).to_be_disabled()
                personnel_region.select_option('中区')
                expect(selector).to_have_value('')
                expect(selector).to_contain_text('该区域暂无对接人员')
                expect(deck.locator('.map-cockpit__metrics button').nth(1).locator('strong')).to_have_text('0')
                personnel_region.select_option('西区')
                artifact=os.environ.get('CRM_ARTIFACT_DIR')
                if artifact:
                    Path(artifact).mkdir(parents=True,exist_ok=True)
                    deck.screenshot(path=str(Path(artifact)/'按区域选择客户经理.png'))
                personnel_region.select_option('')
                selector.select_option('alice')
                metric=deck.locator('.map-cockpit__metrics button').nth(1).locator('strong')
                expect(metric).to_have_text('2')
                expect(deck.locator('.map-cockpit__metrics button').nth(3).locator('strong')).to_have_text('2')
                deck.get_by_role('button',name='放大地图',exact=True).click()
                deck.locator('.region-map__card').filter(has=page.get_by_text('西区',exact=True)).click()
                expect(deck.locator('.map-cockpit__scope')).to_contain_text('西区')
                deck.locator('.region-map__filters button').filter(has_text='厂商').click()
                expect(metric).to_have_text('0')
                deck.get_by_role('button',name='下一位',exact=True).click()
                expect(selector).to_have_value('bob')
                expect(metric).to_have_text('1')
                expect(deck.locator('.map-cockpit__metrics button').nth(3).locator('strong')).to_have_text('1')
                expect(deck.locator('.map-cockpit__scope')).to_contain_text('全部区域')
                expect(deck.get_by_role('button',name='下一位',exact=True)).to_be_disabled()
                deck.get_by_role('button',name='上一位',exact=True).click()
                expect(metric).to_have_text('2')
                deck.locator('.map-cockpit__metrics button').nth(1).click()
                detail=page.get_by_role('dialog',name='区域数据明细',exact=True)
                expect(detail).to_be_visible()
                expect(detail.locator('.ri-region').filter(has=page.get_by_role('heading',name='西区',exact=True)).locator('.ri-region-total b').last).to_have_text('2')
                page.keyboard.press('Escape')
                assert deck.evaluate('(e)=>e.scrollHeight<=e.clientHeight+1'), 'large screen overflow'
                artifact=os.environ.get('CRM_ARTIFACT_DIR')
                if artifact:
                    Path(artifact).mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(Path(artifact)/'客户经理逐位巡看.png'))
                personal=browser.new_context(viewport={'width':1366,'height':768})
                personal.add_cookies([{'name':'pws_session','value':'personal','url':base}])
                assert personal.request.get(base+'/api/crm/manager-directory').status == 403
                own_page=personal.new_page();own_page.goto(base+'/workspace/crm')
                expect(own_page.locator('.map-cockpit__metrics button').nth(1).locator('strong')).to_have_text('2')
                expect(own_page.get_by_label('查看客户经理',exact=True)).to_have_count(0)
                own_page.get_by_role('tab',name='关系维系',exact=True).click()
                expect(own_page.get_by_label('关系维系可见范围')).to_contain_text('仅本人对接')
                own_panel=own_page.get_by_role('tabpanel',name='关系维系',exact=True)
                expect(own_panel.locator('.crm-result-count')).to_contain_text('2 条关系')
                expect(own_panel.locator('.el-table__body-wrapper')).not_to_contain_text('东区人员')
                page.goto(base+'/workspace/crm')
                page.get_by_role('tab',name='关系维系',exact=True).click()
                expect(page.get_by_label('关系维系可见范围')).to_contain_text('管理员 · 全部')
                expect(page.get_by_role('tabpanel',name='关系维系',exact=True).locator('.crm-result-count')).to_contain_text('3 条关系')
                if artifact:
                    own_page.screenshot(path=str(Path(artifact)/'个人账号-关系维系范围.png'))
                assert not errors,errors
                browser.close()
                print('PASS: account/employee ID filtering, previous/next bounds, reset region/type, followups, no-scroll expanded screen')
        finally:
            server.shutdown();server.server_close()
