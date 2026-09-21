"""A liaison belongs to one staff region even when their customers span regions."""
import sys, tempfile, threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

class QuietHandler(r.Handler):
    def log_message(self, *args): pass

with tempfile.TemporaryDirectory(prefix='liaison-region-') as tmp:
    users=[{'username':'admin','name':'管理员','role':'superadmin'},
           {'username':'dongtao','employee_id':'170141','name':'董涛','company':'我方公司','department':'联合指挥中心 / 东区作战平台','position':'副总经理'}]
    with patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':users}), patch.object(r,'SESSIONS',{'preview':'admin'}), patch.object(r,'crm_on_change'), patch.object(r,'crm_audit'):
        r.crm_staff_save({'name':'董涛','member_key':'170141','company':'我方公司','department':'联合指挥中心 / 东区作战平台','title':'副总经理','business_region':'东区'},'admin')
        for region in ('东区','西区'):
            unit=r.crm_unit_save({'name':f'{region}客户','type':'业主单位','business_regions':[region]},'admin')['unit']
            person=r.crm_person_save({'name':f'{region}联系人','unit_id':unit['id']},'admin')['person']
            r.crm_relation_save({'person_id':person['id'],'our_member':'170141'},'admin')
        server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':1366,'height':768})
                context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=context.new_page();page.goto(base+'/workspace/crm')
                page.get_by_role('tab',name='我方对接人员',exact=True).click()
                directory=page.get_by_label('我方对接人员快捷列表',exact=True)
                expect(directory.locator('aside button')).to_have_count(1)
                expect(directory.locator('aside button')).to_contain_text('2 个组织 · 2 位客户 · 2 条链路')
                region=directory.get_by_label('对接人员区域',exact=True)
                directory.locator('.ld-tools .el-select').click()
                expect(page.get_by_role('option',name='东区',exact=True)).to_be_visible()
                expect(page.get_by_role('option',name='西区',exact=True)).to_have_count(0)
                page.get_by_role('option',name='东区',exact=True).click();expect(directory.locator('aside button')).to_have_count(1)
                page.get_by_role('tab',name='安全权限',exact=True).click()
                tree=page.locator('.org-tree')
                tree.get_by_text('东区',exact=True).click();expect(page.locator('.detail-stats')).to_contain_text('总人数1')
                tree.get_by_text('西区',exact=True).click();expect(page.locator('.detail-stats')).to_contain_text('总人数0')
                browser.close()
                print('PASS: cross-region customers do not duplicate one liaison across staff regions')
        finally:
            server.shutdown();server.server_close()
