import sys, tempfile, threading, os
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

with tempfile.TemporaryDirectory() as tmp:
    user={'username':'preview','role':'superadmin'}
    with patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'read_config',return_value={'users':[user]}), patch.object(r,'SESSIONS',{'preview':'preview'}), patch.object(r,'crm_on_change'):
        root=r.crm_unit_save({'name':'宽树测试','organization_level':'company','type':'业主单位'},'preview')['unit']
        branches=[]
        for i in range(7):
            unit=r.crm_unit_save({'name':f'分支{i}','organization_level':'unit','parent_unit_id':root['id'],'type':'业主单位'},'preview')['unit']
            branches.append(unit['id'])
            for j in range(8):
                r.crm_person_save({'name':f'人员{i}-{j}','unit_id':unit['id'],'department':f'部门{j}'},'preview')
        server=r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                b=p.chromium.launch(headless=True,args=['--no-sandbox'])
                ctx=b.new_context(viewport={'width':1800,'height':1100})
                base=f'http://127.0.0.1:{server.server_port}'
                ctx.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=ctx.new_page();page.goto(base+'/workspace/crm')
                page.get_by_role('tab',name='组织架构',exact=True).click()
                page.get_by_role('button',name='调整架构画布',exact=True).click()
                d=page.get_by_role('dialog',name='调整客户组织架构',exact=True)
                d.locator('.oe-toolbar .el-select').first.click()
                page.get_by_role('option',name='宽树测试',exact=True).click()
                expect(d.locator('.oe-node')).to_have_count(64)
                for ident in branches:
                    d.locator(f'[data-node-id="{ident}"]').get_by_role('button',name='收起下级',exact=True).evaluate('(e)=>e.click()')
                expect(d.locator('.oe-node')).to_have_count(8)
                page.wait_for_function('''() => {
                    const es=[...document.querySelectorAll('.oe-node')];
                    const xs=es.filter(e=>e.style.top==='200px').map(e=>parseFloat(e.style.left)).sort((a,b)=>a-b);
                    return es.length===8 && xs.length===7 && xs.every((x,i)=>!i||x-xs[i-1]===290);
                }''')
                xs=sorted(d.locator('.oe-node').evaluate_all('(es)=>es.filter(e=>e.style.top==="200px").map(e=>parseFloat(e.style.left))'))
                assert len(xs)==7 and all(b-a==290 for a,b in zip(xs,xs[1:])),xs
                assert int(d.locator('.oe-toolbar>b').inner_text().replace('%',''))>=70
                out=Path(os.environ['CRM_ARTIFACT_DIR']);out.mkdir(parents=True,exist_ok=True)
                d.screenshot(path=str(out/'多分支收起紧凑排版.png'),animations='disabled')
                for ident in branches[:3]:
                    button=d.locator(f'[data-node-id="{ident}"]').get_by_role('button',name='展开下级',exact=True)
                    button.evaluate('(e)=>e.click()')
                    expect(d.locator('.oe-node')).to_have_count(16)
                    xs=d.locator('.oe-node').evaluate_all('(es)=>es.filter(e=>e.style.top==="400px").map(e=>parseFloat(e.style.left)).sort((a,b)=>a-b)')
                    assert len(xs)==8 and all(b-a==290 for a,b in zip(xs,xs[1:]))
                    d.locator(f'[data-node-id="{ident}"]').get_by_role('button',name='收起下级',exact=True).evaluate('(e)=>e.click()')
                    expect(d.locator('.oe-node')).to_have_count(8)
                    xs=d.locator('.oe-node').evaluate_all('(es)=>es.filter(e=>e.style.top==="200px").map(e=>parseFloat(e.style.left)).sort((a,b)=>a-b)')
                    assert all(b-a==290 for a,b in zip(xs,xs[1:]))
                print('PASS automatic compact layout on repeated collapse/expand without layout button')
                for width,height in [(1800,1100),(1366,768),(1024,768)]:
                    page.set_viewport_size({'width':width,'height':height})
                    page.wait_for_timeout(100)
                    box=d.bounding_box()
                    assert box['y']>=0 and box['y']+box['height']<=height+1
                    assert d.evaluate('(e)=>e.scrollHeight<=e.clientHeight+1')
                    assert d.locator('.el-dialog__body').evaluate('(e)=>e.scrollHeight<=e.clientHeight+1')
                    assert d.locator('.oe-stage').bounding_box()['height']>=120
                    assert d.locator('.oe-people').bounding_box()['y']+d.locator('.oe-people').bounding_box()['height']<=height
                print('PASS one-screen dialog and visible personnel panel at 1800,1366,1024 widths')
                d.screenshot(path=str(out/'组织架构一屏工作区.png'),animations='disabled')
                b.close()
        finally:
            server.shutdown();server.server_close()
