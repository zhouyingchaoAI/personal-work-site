"""Admin default supervision and personal assignment scope, isolated real APIs."""
import os
import sys
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

users = [{'username':'root','name':'管理员','role':'superadmin'},
         {'username':'east','name':'东区经理','role':'member','department':'东区作战平台'}]
with tempfile.TemporaryDirectory(prefix='crm-admin-workbench-') as tmp:
 with patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':users}), patch.object(r,'SESSIONS',{'test':'root'}), patch.object(r,'crm_on_change'), patch.object(r,'crm_audit'):
  unit=r.crm_unit_save({'name':'测试客户','type':'业主单位'},'root')['unit']
  person=r.crm_person_save({'name':'测试联系人','unit_id':unit['id']},'root')['person']
  relation=r.crm_relation_save({'person_id':person['id'],'our_member':'east'},'root')['relation']
  for owner, title in [('root','管理员自己的跟进'),('east','东区经理的逾期跟进')]:
   r.crm_action_add({'relation_id':relation['id'],'record_kind':'plan','next_step':title,'owner':owner,'due_date':(date.today()-timedelta(days=2)).isoformat()},'root')
  class QuietHandler(r.Handler):
   def log_message(self,*args): pass
  server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    base=f'http://127.0.0.1:{server.server_port}'
    page.context.add_cookies([{'name':'pws_session','value':'test','url':base}])
    page.route('**/api/crm/security/amap-settings',lambda route:route.fulfill(json={'enabled':False}))
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/workspace/crm')
    wb=page.locator('.crm-workbench')
    expect(wb.get_by_role('heading',name='需要你督办的事')).to_be_visible(timeout=20000)
    queue=wb.locator('.management-queue')
    expect(queue).to_contain_text('东区经理的逾期跟进')
    expect(queue).to_contain_text('管理员自己的跟进')
    region=queue.get_by_label('管控区域',exact=True)
    region.select_option('东区')
    expect(queue.locator('article')).to_have_count(1)
    expect(queue).to_contain_text('东区经理的逾期跟进')
    expect(queue).not_to_contain_text('管理员自己的跟进')
    expect(queue.get_by_role('radio',name='逾期 1',exact=True)).to_be_checked()
    region.select_option('广东区')
    expect(queue.locator('article')).to_have_count(0)
    region.select_option('未分区')
    expect(queue).to_contain_text('管理员自己的跟进')
    expect(queue).not_to_contain_text('东区经理的逾期跟进')
    region.select_option('')
    expect(wb.get_by_role('button',name='完成',exact=True)).to_have_count(0)
    out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'admin-management-desktop.png'),full_page=True)
    wb.get_by_role('button',name='我的跟进',exact=True).click()
    expect(wb.locator('.wb-task')).to_have_count(1)
    expect(wb).to_contain_text('管理员自己的跟进')
    expect(wb).not_to_contain_text('东区经理的逾期跟进')
    expect(wb).to_contain_text('仅分配给我的跟进')
    wb.get_by_role('button',name='管理待办',exact=True).click()
    queue.get_by_text('久未跟进 0',exact=True).click()
    expect(queue).to_contain_text('当前范围暂无此类事项')
    queue.get_by_text('逾期 2',exact=True).click()
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(400)
    if page.locator('.mobile-nav-backdrop').is_visible():
     page.get_by_role('button',name='关闭导航',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'mobile overflow'
    page.screenshot(path=str(out/'admin-management-mobile.png'),full_page=True)
    queue.get_by_role('button',name='查看处理',exact=True).first.click()
    expect(page.locator('.crm-workbench')).to_have_count(0)
    # Production-shaped case: unfinished followups exist, but none has a date.
    actions=r.crm_load('root','actions')
    for action in actions.values():
     action['due_date']=''
    sample=next(iter(actions.values()))
    for i in range(316):
     actions[f'undated-{i}']={**sample,'id':f'undated-{i}','next_step':f'待明确时间的跟进 {i}'}
    r.crm_store('root','actions',actions)
    page.reload()
    expect(wb).to_be_visible()
    page.wait_for_timeout(400)
    if page.locator('.mobile-nav-backdrop').is_visible():
     page.get_by_role('button',name='关闭导航',exact=True).click()
    expect(queue.get_by_role('radio',name='待定日期 318',exact=True)).to_be_checked()
    expect(queue.locator('article')).to_have_count(20)
    expect(queue.locator('.el-pagination')).to_be_visible()
    expect(queue).to_contain_text('不计为逾期')
    expect(queue).to_contain_text('东区经理的逾期跟进')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'undated mobile overflow'
    page.screenshot(path=str(out/'admin-undated-mobile.png'),full_page=True)
    queue.get_by_text('逾期 0',exact=True).click()
    expect(queue).to_contain_text('当前范围暂无此类事项')
    expect(queue.get_by_role('radio',name='逾期 0',exact=True)).to_be_checked()
    queue.get_by_text('待定日期 318',exact=True).click()
    page.set_viewport_size({'width':1440,'height':1000})
    page.screenshot(path=str(out/'admin-undated-desktop.png'),full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS admin default, team supervision, actual assignment scope, empty queue, mobile and action navigation')
  finally:
   server.shutdown();server.server_close()
