import sys, tempfile, threading, os
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright
sys.path.insert(0, '/home/chency/zyc/workspace/personal-work-site')
import backend.runtime as r

artifacts = Path(os.environ.get('CRM_ARTIFACT_DIR','/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1789196616161_iy4xyu'))
artifacts.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='map-cockpit-') as tmp:
    user = {'username':'preview','name':'地图测试','role':'superadmin'}
    with patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users':[user]}), patch.object(r, 'SESSIONS', {'preview':'preview'}), patch.object(r, 'crm_on_change'):
        for region, count in [('东区',2),('中区',1)]:
            for i in range(count):
                unit = r.crm_unit_save({'name':f'{region}客户{i}','type':'业主单位','business_regions':[region]},'preview')['unit']
                saved_units=r.crm_load('preview','units')
                saved_units[unit['id']]['organization_level']=('company' if i == 0 else 'subsidiary') if region == '东区' else 'unit'
                r.crm_store('preview','units',saved_units)
                person = r.crm_person_save({'name':f'{region}联系人{i}','unit_id':unit['id']},'preview')['person']
                relation = r.crm_relation_save({'person_id':person['id'],'our_member':'preview'},'preview')['relation']
                r.crm_action_add({'relation_id':relation['id'],'type':'拜访','record_kind':'plan','next_step':f'{region}回访','due_date':'2026-09-20'},'preview')
        us=r.crm_load('preview','units')
        root=next(u for u in us.values() if u['name']=='东区客户0')
        child=next(u for u in us.values() if u['name']=='东区客户1')
        child['parent_unit_id']=root['id']
        r.crm_store('preview','units',us)
        person=next(p for p in r.crm_load('preview','people').values() if p['unit_id']==root['id'])
        before={k:r.crm_load('preview',k) for k in ['relations','actions']}
        server = r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True,args=['--no-sandbox'])
                context = browser.new_context(viewport={'width':1600,'height':1100})
                context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page = context.new_page(); errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base+'/workspace/crm')
                cockpit=page.locator('.map-cockpit');cockpit.wait_for()
                from playwright.sync_api import expect
                page.get_by_role('tab',name='组织架构',exact=True).click()
                page.get_by_role('button',name='调整架构画布',exact=True).click()
                dialog=page.get_by_role('dialog',name='调整客户组织架构',exact=True)
                expect(dialog.locator('.oe-node').filter(has_text='东区客户0').first).to_be_visible()
                expect(dialog.locator('.oe-node-quick-actions')).to_have_count(0)
                selected_root=dialog.locator('[data-node-id="'+root['id']+'"]')
                selected_root.locator('strong').click()
                expect(dialog.locator('.oe-node-quick-actions')).to_have_count(1)
                expect(selected_root.locator('.oe-node-quick-actions button')).to_have_count(2)
                dialog.screenshot(path=str(artifacts/'选中节点操作栏.png'),animations='disabled')
                dialog.locator('.oe-stage').click(position={'x':8,'y':8})
                expect(dialog.locator('.oe-node-quick-actions')).to_have_count(0)
                dialog.locator('.oe-toolbar .el-select').first.click()
                expect(page.get_by_role('option').filter(has_text='东区客户1')).to_have_count(0)
                page.get_by_role('option').filter(has_text='东区客户0').first.click()
                expect(dialog.locator('.oe-node').filter(has_text='东区客户0').first).to_be_visible()
                secondary=dialog.locator('.oe-toolbar .el-select').nth(1)
                secondary.click()
                expect(page.get_by_role('option',name='东区客户1',exact=True)).to_be_visible()
                page.get_by_role('option',name='东区客户1',exact=True).click()
                expect(dialog.locator('[data-node-id="'+root['id']+'"]')).to_have_count(0)
                expect(dialog.locator('[data-node-id="'+child['id']+'"]')).to_be_visible()
                expect(dialog.locator('.oe-node.department')).to_have_count(1)
                page.screenshot(path=str(artifacts/'组织架构-二级索引.png'),animations='disabled')
                secondary.hover()
                secondary.locator('.el-select__clear').click()
                expect(dialog.locator('[data-node-id="'+root['id']+'"]')).to_be_visible()
                cards=dialog.locator('.oe-node').evaluate_all('(es)=>es.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top)}))')
                top=min(c['y'] for c in cards)
                parent=next(c for c in cards if c['y']==top)
                child_y=min(c['y'] for c in cards if c['y']>top)
                siblings=[c['x'] for c in cards if c['y']==child_y]
                assert abs(parent['x']-(min(siblings)+max(siblings))/2)<1, 'parent is not centered over children'
                dialog.get_by_role('button',name='收起部门',exact=True).click()
                expect(dialog.locator('.oe-node.department')).to_have_count(0)
                root_node=dialog.locator('[data-node-id="'+root['id']+'"]')
                root_node.get_by_role('button',name='收起下级',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(1)
                page.wait_for_function("document.querySelector('.oe-node')?.style.left === '0px'")
                dialog.get_by_role('button',name='自动排版',exact=True).click()
                assert root_node.evaluate('(e)=>parseFloat(e.style.left)') == 0, 'collapsed descendants still reserve layout space'
                root_node.get_by_role('button',name='展开下级',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(2)
                dialog.get_by_role('button',name='显示部门',exact=True).click()
                expect(dialog.locator('.oe-node.department')).to_have_count(2)
                cards=dialog.locator('.oe-node').evaluate_all('(es)=>es.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top)}))')
                parent=next(c for c in cards if c['y']==0)
                children=[c['x'] for c in cards if c['y']==200]
                assert abs(parent['x']-(min(children)+max(children))/2)<1, 'hidden descendants not included in auto-layout'
                dialog.get_by_role('button',name='适应画布',exact=True).click()
                root_node.get_by_role('button',name='收起下级',exact=True).click()
                root_node.get_by_role('button',name='单独查看',exact=True).click()
                branch=page.get_by_role('dialog',name='子节点与人员',exact=True)
                expect(branch).to_be_visible()
                expect(branch.locator('.oe-branch-item')).to_have_count(2)
                branch.locator('.oe-branch-item').filter(has_text='东区客户1').click()
                expect(branch.locator('.oe-branch-title')).to_have_text('东区客户1')
                expect(branch.locator('.oe-branch-people')).to_contain_text('东区联系人1')
                branch.get_by_role('button',name='返回上级',exact=True).click()
                expect(branch.locator('.oe-branch-title')).to_have_text('东区客户0')
                branch.screenshot(path=str(artifacts/'子节点与人员弹框.png'))
                branch.locator('.oe-branch-item').filter(has_text='东区客户1').click()
                branch.get_by_role('button',name='定位到画布',exact=True).click()
                expect(branch).not_to_be_visible()
                expect(dialog.locator('[data-node-id="'+child['id']+'"]')).to_be_visible()
                expect(dialog.locator('.oe-node')).to_have_count(4)
                expect(dialog.locator('.oe-people [data-person-id]')).to_have_count(2)
                assert '中区客户0' not in dialog.locator('.oe-stage').inner_text()
                dialog.get_by_role('textbox',name='目标部门',exact=True).fill('信息中心')
                source=dialog.locator('[data-person-id="'+person['id']+'"]')
                target=dialog.locator('[data-node-id="'+child['id']+'"]')
                before_pos=target.evaluate('(e)=>({left:e.style.left,top:e.style.top})')
                handle=target.locator('small').first.bounding_box()
                page.mouse.move(handle['x']+10,handle['y']+5);page.mouse.down()
                page.mouse.move(handle['x']+90,handle['y']+45,steps=8);page.mouse.up()
                assert target.evaluate('(e)=>e.style.left')!=before_pos['left']
                dialog.get_by_role('button',name='撤销位置',exact=True).click()
                assert target.evaluate('(e)=>e.style.left')==before_pos['left']
                assert r.crm_load('preview','units')[child['id']]['parent_unit_id']==root['id']
                dialog.get_by_role('button',name='缩小',exact=True).click()
                dialog.get_by_role('button',name='适应画布',exact=True).click()
                source.drag_to(target)
                expect(dialog.locator('.oe-node.department').filter(has_text='信息中心')).to_be_visible(timeout=20000)
                stored=r.crm_load('preview','people')[person['id']]
                assert stored['unit_id']==child['id'] and stored['department']=='信息中心'
                for k in before: assert before[k]==r.crm_load('preview',k)
                cards=dialog.locator('.oe-node').evaluate_all('(es)=>es.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top)}))')
                for i,a in enumerate(cards):
                    for b in cards[i+1:]: assert abs(a['x']-b['x'])>=230 or abs(a['y']-b['y'])>=105, 'new node overlaps existing position'
                print('PASS independent node motion, position undo, zoom/fit, non-overlapping inserted nodes',flush=True)
                info=dialog.locator('.oe-node.department').filter(has_text='信息中心')
                info.locator('strong').first.click()
                expect(dialog.locator('.oe-people [data-person-id]')).to_have_count(1)
                # Another editor saves while this canvas still holds the old version.
                latest=r.crm_load('preview','people')[person['id']]
                updated=r.crm_person_save({**latest,'title':'更新后的职务'},'preview')
                assert updated['ok']
                dialog.get_by_role('button',name=f'将{person["name"]}移回未分配',exact=True).click()
                expect(dialog.locator('.oe-people [data-person-id="'+person['id']+'"]')).to_contain_text('未分部门')
                unassigned=dialog.locator('.oe-people [data-person-id="'+person['id']+'"]')
                page.mouse.move(0,0)
                colors=unassigned.evaluate('(e)=>({card:getComputedStyle(e.parentElement).backgroundColor,button:getComputedStyle(e).backgroundColor,text:getComputedStyle(e.querySelector("small")).color})')
                assert colors=={'card':'rgb(255, 237, 204)','button':'rgb(255, 237, 204)','text':'rgb(135, 85, 28)'},colors
                dialog.locator('.oe-people').screenshot(path=str(artifacts/'未分配人员整卡高亮.png'),animations='disabled')
                stored=r.crm_load('preview','people')[person['id']]
                assert stored['unit_id']==root['id'] and not stored['department']
                assert stored['title']=='更新后的职务'
                for k in before: assert before[k]==r.crm_load('preview',k)
                print('PASS selected department filtering and unassign preserves relations/actions',flush=True)
                dialog.get_by_role('button',name='自动排版',exact=True).click()
                dialog.screenshot(path=str(artifacts/'组织架构居中与折叠.png'))
                assert not errors,errors
                print('PASS single organization isolation, top-down hierarchy, real person drag/drop save, relationship/action preservation')
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()
