import os,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend.runtime as r
with tempfile.TemporaryDirectory(prefix='crm-assignment-') as tmp:
 users=[{'username':'admin','role':'superadmin','name':'管理员'},{'username':'old','name':'原经理','employee_id':'E1'},{'username':'new','name':'新经理','employee_id':'E2'}]
 with patch.object(r,'USER_DATA_DIR',Path(tmp)),patch.object(r,'read_config',return_value={'users':users}),patch.object(r,'SESSIONS',{'test':'admin'}),patch.object(r,'crm_on_change'),patch.object(r,'crm_audit'):
  unit=r.crm_unit_save({'name':'测试客户','type':'业主单位'},'admin')['unit']
  person=r.crm_person_save({'name':'测试联系人','unit_id':unit['id']},'admin')['person']
  relation=r.crm_relation_save({'person_id':person['id'],'our_member':'E1'},'admin')['relation']
  class Handler(r.Handler):
   def log_message(self,*args):pass
  server=r.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000})
    base=f'http://127.0.0.1:{server.server_port}';page.context.add_cookies([{'name':'pws_session','value':'test','url':base}])
    page.goto(base+'/workspace/crm');page.get_by_role('tab',name='客户',exact=True).click();page.get_by_role('tab').filter(has_text='责任统筹').click()
    panel=page.locator('.simple-assignment');expect(panel).to_be_visible(timeout=5000)
    panel.get_by_label('客户组织',exact=True).select_option(unit['id'])
    target=panel.get_by_role('combobox',name='目标对接人',exact=True)
    target.fill('新经理')
    page.locator('li[role="option"]').filter(has_text='新经理').click()
    expect(panel.get_by_role('textbox',name='搜索我方人员',exact=True)).to_have_count(0)
    panel.get_by_role('button',name='确认指派',exact=True).click()
    expect(panel).to_contain_text('操作完成')
    assert {x['our_member'] for x in r.crm_load('admin','relations').values()}=={'E1','E2'}
    panel.get_by_role('button',name='关系转移',exact=True).click()
    panel.get_by_label('原对接人',exact=True).select_option('E1')
    target.fill('E2')
    page.locator('li[role="option"]').filter(has_text='新经理').click()
    panel.get_by_role('button',name='确认添加',exact=True).click()
    expect(panel).to_contain_text('操作完成')
    assert len(r.crm_load('admin','relations'))==2
    out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'assignment-desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
    if page.locator('.mobile-nav-backdrop').is_visible():page.get_by_role('button',name='关闭导航',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'assignment-mobile.png'),full_page=True)
    browser.close();print('PASS organization assignment, preserve original, person handoff additive deduplication, mobile')
  finally:server.shutdown();server.server_close()
