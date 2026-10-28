"""Real read-only PostgreSQL queries through an isolated HTTP server and browser."""
import json,os,sys,tempfile,threading,subprocess,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
for line in (ROOT/'.env').read_text().splitlines():
 if line.startswith('OFFICE_QUERY_PASSWORD='):os.environ['OFFICE_QUERY_PASSWORD']=line.split('=',1)[1]
info=json.loads(subprocess.check_output(['docker','inspect','office-postgres'],text=True))[0]
os.environ['OFFICE_QUERY_HOST']=info['NetworkSettings']['Networks']['openclaw-net']['IPAddress']
import backend.runtime as r
OUT=Path(sys.argv[1]);OUT.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'user_data';root.mkdir();cfg=Path(tmp)/'config.json'
 (root/'zhouyingchao').mkdir()
 (root/'zhouyingchao'/'cashflow_history.json').write_text(json.dumps({'records':[{'id':'live-fixture','region':'fixture','project_name':'fixture'}]}))
 cfg.write_text(json.dumps({'users':[{'username':'preview','role':'superadmin'},{'username':'member','role':'member','assistant_permissions':{'datacenter':True}}]}))
 with patch.object(r,'USER_DATA_DIR',root),patch.object(r,'CONFIG_PATH',cfg),patch.object(r,'SESSIONS',{'preview':'preview','member':'member'}),patch.object(r.Handler,'log_message'):
  server=r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  base=f'http://127.0.0.1:{server.server_port}'
  def get(path,cookie):
   req=urllib.request.Request(base+path,headers={'Cookie':'pws_session='+cookie} if cookie else {})
   try:
    with urllib.request.urlopen(req) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as e:return e.code,json.load(e)
  try:
   path='/api/datacenter/data?dataset=cashflow.history&owner=zhouyingchao&source=database&limit=2&summary=1'
   assert get(path,None)[0]==401
   assert get(path,'member')[0]==403
   code,res=get(path,'preview');assert code==200 and res['source']=='postgresql' and res['synced_at']
   assert len(res['items'])<=2 and 'summary' in res
   assert get(path+'&date_from=invalid','preview')[0]==400
   with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1800,'height':1400},device_scale_factor=1)
    context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/workspace/datacenter')
    page.get_by_role('button',name='数据接口',exact=False).click(timeout=30000)
    page.locator('.ap-nav').get_by_role('button',name='历史回款节点').click()
    page.get_by_role('button',name='发送请求',exact=True).click()
    page.locator('.ap-meta').filter(has_text='PostgreSQL 镜像').wait_for(timeout=15000)
    assert 'HTTP 200' in page.locator('.ap-meta').filter(has_text='PostgreSQL 镜像').inner_text()
    page.locator('.ap-result').evaluate("e=>e.style.display='none'")
    page.locator('.ap-doc > .ap-card').nth(1).screenshot(path=str(OUT/'datacenter-structured-query.png'))
    region_input=page.get_by_placeholder('仅 database：精确匹配 region',exact=True)
    region_input.fill('数据库专用过滤')
    page.locator('.ap-form .el-select').click()
    page.get_by_role('option',name='实时原存储',exact=True).click()
    assert region_input.is_disabled()
    page.get_by_role('button',name='发送请求',exact=True).click()
    live_meta=page.locator('.ap-meta').filter(has_text='实时原存储 · HTTP 200')
    live_meta.wait_for(timeout=10000)
    assert '共 1 条' in live_meta.inner_text()
    assert not errors,errors
    browser.close()
   print('Real SQL HTTP query / summary / timestamp / 401 / 403 / 400 and browser online test PASS')
  finally:server.shutdown();server.server_close()
