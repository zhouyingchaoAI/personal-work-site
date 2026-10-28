import os, sys, tempfile, threading, io
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import backend.runtime as r
with tempfile.TemporaryDirectory(prefix='crm-opp-filters-') as tmp:
 with patch.object(r,'USER_DATA_DIR',Path(tmp)),patch.object(r,'read_config',return_value={'users':[{'username':'preview','role':'superadmin'}]}),patch.object(r,'SESSIONS',{'preview':'preview'}),patch.object(r,'crm_on_change'),patch.object(r,'crm_audit'):
  for code,region,stage,sales in [('E','东区','设计','需求确认'),('G','广东区','设计','需求确认'),('E2','东区','招标','投标报价'),('U','','','')]:
   r.crm_opportunity_save({'code':code,'name':code+'项目','owner_unit':'测试客户','region':region,'stage':stage,'sales_stage':sales},'preview')
  class Handler(r.Handler):
   def log_message(self,*args):pass
  server=r.ThreadingHTTPServer(('127.0.0.1',0),Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    base=f'http://127.0.0.1:{server.server_port}'
    page.context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
    page.goto(base+'/workspace/crm')
    page.get_by_role('tab',name='商机',exact=True).click()
    panel=page.locator('.opportunity-management')
    def select(label,value):
     panel.locator('.el-select').filter(has=page.get_by_role('combobox',name=label,exact=True)).click()
     page.get_by_role('option',name=value,exact=True).click()
    select('商机区域','东区')
    expect(panel.locator('.el-table__row')).to_have_count(2)
    select('销售阶段筛选','需求确认')
    select('项目阶段筛选','设计')
    expect(panel.locator('.el-table__row')).to_have_count(1)
    expect(panel.locator('.om-toolbar')).to_contain_text('1 个商机')
    with page.expect_download() as dl:
     panel.get_by_role('button',name='导出',exact=True).click()
    book=load_workbook(io.BytesIO(Path(dl.value.path()).read_bytes()),read_only=True)
    rows=list(book.active.values);assert len(rows)==2 and rows[1][0]=='E',rows
    book.close()
    out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'opportunity-filters-desktop.png'),full_page=True)
    panel.get_by_role('button',name='重置筛选',exact=True).click()
    expect(panel.locator('.el-table__row')).to_have_count(4)
    select('商机区域','区域待补充')
    select('销售阶段筛选','销售阶段待确认')
    expect(panel.locator('.el-table__row')).to_have_count(1)
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
    if page.locator('.mobile-nav-backdrop').is_visible():page.get_by_role('button',name='关闭导航',exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'opportunity-filters-mobile.png'),full_page=True)
    browser.close()
    print('PASS combined region/sales/project filters, missing values, reset, scoped export and mobile')
  finally:server.shutdown();server.server_close()
