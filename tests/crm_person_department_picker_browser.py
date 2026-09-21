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
        deep=r.crm_unit_save({'name':'深层技术部','parent_unit_id':child['id'],'organization_level':'unit','type':'业主单位'},'preview')['unit']
        r.crm_person_save({'name':'部门样例人员','unit_id':root['id'],'department':'办公室'},'preview')
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
                source=dialog.locator('[data-person-id="'+person['id']+'"]')
                expect(source).to_contain_text('未分配人员')
                source.click()
                editor=page.get_by_role('dialog',name='编辑人物',exact=True)
                manager=editor.locator('.el-select').filter(has=page.get_by_role('combobox',name='直接上级',exact=True))
                manager.click()
                expect(page.get_by_role('option',name='东区联系人1',exact=False)).to_be_visible()
                expect(page.get_by_role('option',name='部门样例人员',exact=False)).to_be_visible()
                expect(page.get_by_role('option',name='中区联系人0',exact=False)).to_have_count(0)
                expect(page.get_by_role('option',name='东区联系人0',exact=False)).to_have_count(0)
                page.get_by_role('option',name='东区联系人1',exact=False).click()
                picker=editor.locator('.el-select').filter(has=page.get_by_role('combobox',name='所属部门',exact=True))
                expect(picker).to_contain_text('未分配人员')
                picker.click()
                page.locator('.el-select-dropdown:visible input').count()
                picker.locator('input').fill('深层技术部')
                page.get_by_role('treeitem',name='深层技术部',exact=True).click()
                expect(picker).to_contain_text('深层技术部')
                editor.screenshot(path=str(artifacts/'所属部门-架构选择.png'),animations='disabled')
                editor.get_by_role('button',name='保存',exact=True).click()
                expect(editor).not_to_be_visible()
                stored=r.crm_load('preview','people')[person['id']]
                assert stored['unit_id']==deep['id'] and stored['department']==''
                assert stored['manager_id']==next(p['id'] for p in r.crm_load('preview','people').values() if p['name']=='东区联系人1')
                expect(source).not_to_contain_text('未分配人员')
                source.click()
                expect(picker).to_contain_text('深层技术部')
                picker.hover()
                picker.locator('.el-select__clear').click()
                expect(picker).to_contain_text('未分配人员')
                editor.get_by_role('button',name='保存',exact=True).click()
                expect(editor).not_to_be_visible()
                expect(source).to_contain_text('未分配人员')
                stored=r.crm_load('preview','people')[person['id']]
                assert stored['unit_id']==root['id'] and stored['department']==''
                source.click()
                picker.click()
                picker.locator('input').fill('办公室')
                page.get_by_role('treeitem',name='办公室',exact=True).click()
                editor.get_by_role('button',name='保存',exact=True).click()
                expect(editor).not_to_be_visible()
                stored=r.crm_load('preview','people')[person['id']]
                assert stored['unit_id']==root['id'] and stored['department']=='办公室'
                source.click()
                expect(manager).to_contain_text('东区联系人1')
                editor.locator('.el-select').filter(has=page.get_by_role('combobox',name='所属单位',exact=True)).click()
                page.get_by_role('option',name='中区客户0',exact=True).click()
                expect(manager).to_contain_text('请选择本组织人员')
                manager.click()
                expect(page.get_by_role('option',name='中区联系人0',exact=False)).to_be_visible()
                expect(page.get_by_role('option',name='东区联系人1',exact=False)).to_have_count(0)
                page.keyboard.press('Escape')
                editor.screenshot(path=str(artifacts/'直接上级-组织范围筛选.png'),animations='disabled')
                editor.get_by_role('button',name='保存',exact=True).click()
                expect(editor).not_to_be_visible()
                assert r.crm_load('preview','people')[person['id']]['manager_id']==''
                for k in before: assert before[k]==r.crm_load('preview',k)
                assert not errors,errors
                print('PASS department picker and organization-scoped managers: excludes self/other customers, preserves same-tree manager, clears manager across roots, saves and preserves relations',flush=True)
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()
