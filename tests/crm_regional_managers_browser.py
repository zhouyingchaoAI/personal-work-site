"""Regional manager selector regression against isolated real APIs."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

users=[{'username':'root','name':'系统管理员','role':'superadmin'},
       {'username':'east1','name':'东区甲','role':'member','department':'东区作战平台'},
       {'username':'east2','name':'东区乙','role':'member','department':'东区作战平台'},
       {'username':'gd','name':'广东甲','role':'member','department':'广东作战平台'},
       {'username':'hq','name':'总部支持','role':'member','department':'总部技术部'}]
with tempfile.TemporaryDirectory(prefix='crm-regional-managers-') as tmp:
 with patch.object(r,'USER_DATA_DIR',Path(tmp)),patch.object(r,'read_config',return_value={'users':users}),patch.object(r,'SESSIONS',{'test':'root'}),patch.object(r,'crm_on_change'),patch.object(r,'crm_audit'):
  unit=r.crm_unit_save({'name':'东区客户','type':'业主单位','business_regions':['东区']},'root')['unit']
  person=r.crm_person_save({'name':'客户联系人','unit_id':unit['id']},'root')['person']
  r.crm_relation_save({'person_id':person['id'],'our_member':'hq'},'root')
  class QuietHandler(r.Handler):
   def log_message(self,*args):pass
  server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1512,'height':982})
    base=f'http://127.0.0.1:{server.server_port}'
    page.context.add_cookies([{'name':'pws_session','value':'test','url':base}])
    page.route('**/api/crm/security/amap-settings',lambda route:route.fulfill(json={'enabled':False}))
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/workspace/crm')
    page.locator('.crm-workbench').get_by_role('button',name='经营总览',exact=True).click()
    deck=page.locator('.map-cockpit')
    expect(deck).to_be_visible()
    expect(page.locator('.crm-main > .el-loading-mask')).to_have_count(0)
    deck.get_by_role('button',name='客户经理',exact=True).click()
    managers=deck.get_by_label('查看客户经理',exact=True)
    areas=deck.get_by_label('人员所属区域',exact=True)
    expect(managers.locator('option')).to_have_count(3)
    expect(managers).not_to_contain_text('系统管理员')
    expect(managers).not_to_contain_text('总部支持')
    expect(managers).to_have_value('east1')
    deck.get_by_role('button',name='下一位',exact=True).click()
    expect(managers).to_have_value('east2')
    areas.select_option('广东区')
    expect(managers.locator('option')).to_have_count(1)
    expect(managers).to_have_value('gd')
    expect(deck.locator('.map-cockpit__scope h3')).to_contain_text('广东甲')
    areas.select_option('中区')
    expect(managers).to_be_disabled()
    expect(deck.get_by_role('button',name='下一位',exact=True)).to_be_disabled()
    expect(deck.get_by_role('button',name='上一位',exact=True)).to_be_disabled()
    expect(deck.locator('.map-cockpit__scope h3')).to_contain_text('暂无区域客户经理')
    areas.select_option('')
    expect(managers).to_have_value('east1')
    out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'regional-managers-desktop.png'),full_page=True,animations='disabled')
    assert not errors,errors
    browser.close()
    print('PASS four-region manager options, headquarters/client-geography exclusion, zero-client retention, default, next/previous, region switch and empty scope')
  finally:
   server.shutdown();server.server_close()
