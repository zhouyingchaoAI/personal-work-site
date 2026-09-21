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
        r.crm_person_save({**person,'department':'测试部门'},'preview')
        other=r.crm_person_save({'name':'待删除部门联系人','unit_id':root['id'],'department':'待删除部门'},'preview')['person']
        before={k:r.crm_load('preview',k) for k in ['relations','actions']}
        server = r.ThreadingHTTPServer(('127.0.0.1',0),r.Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True,args=['--no-sandbox'])

                from playwright.sync_api import expect
                context=browser.new_context(viewport={'width':1600,'height':1100})
                context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=context.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base+'/workspace/crm')
                page.get_by_role('tab',name='组织架构',exact=True).click()
                page.get_by_role('button',name='调整架构画布',exact=True).click()
                dialog=page.get_by_role('dialog',name='调整客户组织架构',exact=True)
                department=dialog.locator('.oe-node.department').filter(has_text='测试部门')
                expect(department).to_be_visible()
                department.locator('strong').click()
                expect(department.locator('.oe-node-quick-actions button')).to_have_count(2)
                dialog.screenshot(path=str(artifacts/'部门叶子节点-选中显示增删.png'),animations='disabled')
                department.locator('.oe-node-add').click()
                prompt=page.get_by_role('dialog',name='新增下级节点',exact=True)
                prompt.locator('input').fill('部门下的项目组')
                prompt.get_by_role('button',name='创建节点',exact=True).click()
                expect(dialog.locator('.oe-node.selected strong')).to_have_text('部门下的项目组',timeout=20000)
                saved_units=r.crm_load('preview','units')
                saved_child=next(u for u in saved_units.values() if u['name']=='部门下的项目组')
                saved_department=saved_units[saved_child['parent_unit_id']]
                assert saved_department['name']=='测试部门'
                assert r.crm_load('preview','people')[person['id']]['unit_id']==saved_department['id']
                for k in before: assert before[k]==r.crm_load('preview',k)
                dialog.get_by_role('button',name='适应画布',exact=True).click()
                department=dialog.locator('.oe-node.department').filter(has_text='待删除部门')
                department.locator('strong').click()
                expect(department.locator('.oe-node-quick-actions button')).to_have_count(2)
                department.locator('.oe-node-delete').click()
                confirm=page.get_by_role('dialog',name='删除部门节点',exact=True)
                confirm.get_by_role('button',name='取消',exact=True).click()
                assert r.crm_load('preview','people')[other['id']]['department']=='待删除部门'
                department.locator('.oe-node-delete').click()
                confirm.get_by_role('button',name='删除节点并保留联系人',exact=True).click()
                expect(dialog.locator('.oe-node.department > strong').filter(has_text='待删除部门')).to_have_count(0)
                assert r.crm_load('preview','people')[other['id']]['department']==''
                assert r.crm_load('preview','people')[other['id']]['unit_id']==root['id']
                dialog.get_by_role('button',name='适应画布',exact=True).click()
                dialog.screenshot(path=str(artifacts/'部门下新增组织-完成.png'),animations='disabled')
                assert not errors,errors
                print('PASS department leaf shows both buttons, add persists nested organization, delete cancellation and confirmation preserve contacts and relations',flush=True)
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()

