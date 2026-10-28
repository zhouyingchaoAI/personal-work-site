"""Position display/edit/save regression using isolated CRM data."""
import os, sys, tempfile, threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

with tempfile.TemporaryDirectory(prefix='crm-person-title-') as tmp:
 with patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[{'username':'preview','name':'测试管理员','role':'superadmin'}]}), patch.object(r,'SESSIONS',{'preview':'preview'}), patch.object(r,'crm_on_change'), patch.object(r,'crm_audit'):
  unit=r.crm_unit_save({'name':'测试客户集团','type':'业主单位','organization_level':'company'},'preview')['unit']
  person=r.crm_person_save({'name':'测试联系人','title':'通信专工','unit_id':unit['id']},'preview')['person']
  class QuietHandler(r.Handler):
   def log_message(self,*args):pass
  server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    base=f'http://127.0.0.1:{server.server_port}'
    page.context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
    page.route('**/api/crm/security/amap-settings',lambda route:route.fulfill(json={'enabled':False}))
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/workspace/crm')
    page.get_by_role('tab',name='客户',exact=True).click()
    page.get_by_text('客户组织架构',exact=True).click()
    page.get_by_role('button',name='调整架构画布',exact=True).click()
    canvas=page.get_by_role('dialog',name='调整客户组织架构',exact=True)
    card=canvas.locator('[data-person-id="'+person['id']+'"]')
    expect(card).to_contain_text('通信专工')
    expect(canvas.locator('.oe-node-names').first).to_contain_text('通信专工')
    card.click()
    editor=page.get_by_role('dialog',name='编辑人物',exact=True)
    field=editor.get_by_role('textbox',name='职位 / 职务',exact=True)
    expect(field).to_have_value('通信专工')
    field.fill('通信主管')
    editor.get_by_role('button',name='保存',exact=True).click()
    expect(editor).not_to_be_visible()
    assert r.crm_load('preview','people')[person['id']]['title']=='通信主管'
    expect(card).to_contain_text('通信主管')
    expect(canvas.locator('.oe-node-names').first).to_contain_text('通信主管')
    out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
    canvas.get_by_role('button',name='导出架构图',exact=True).click()
    with page.expect_download() as download:
     page.get_by_text('SVG 矢量图',exact=True).click()
    exported=out/'organization-position.svg'
    download.value.save_as(str(exported))
    assert '通信主管' in exported.read_text()
    card.click()
    expect(field).to_have_value('通信主管')
    body=editor.locator('.el-dialog__body')
    assert body.evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'desktop editor overflow'
    editor.screenshot(path=str(out/'person-title-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(400)
    assert body.evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'mobile editor overflow'
    expect(field).to_be_visible()
    editor.screenshot(path=str(out/'person-title-mobile.png'))
    assert not errors,errors
    browser.close()
    print('PASS canvas position, prefill, save persistence, refreshed cards and desktop/mobile editor overflow')
  finally:
   server.shutdown();server.server_close()
