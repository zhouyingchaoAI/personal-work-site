"""Real browser + temporary backend/config; never changes production accounts."""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as r

artifacts = Path(os.environ.get('CRM_ARTIFACT_DIR', '/home/chency/.remote-agent-studio/artifacts/c_1784103461949_70xc/m_1789195229913_5flajl'))
artifacts.mkdir(parents=True, exist_ok=True)

class QuietHandler(r.Handler):
    def log_message(self, *args): pass

with tempfile.TemporaryDirectory(prefix='internal-organization-') as tmp:
    config_path = Path(tmp)/'config.json'
    initial = {'users':[
        {'username':'preview','name':'组织测试管理员','role':'superadmin','company':'承希科技'},
        {'username':'alice','name':'张工','employee_id':'E001','role':'member','company':'承希科技','department':'交付中心 / 工程部','position':'工程师','assistant_permissions':{'crm':True}},
        {'username':'bob','name':'李工','employee_id':'E002','role':'member','company':'承希科技','department':'研发中心','position':'研发经理'},
        {'username':'carol','name':'王工','employee_id':'E003','role':'member','company':'区域公司','department':'经营部'}]}
    initial['users'].extend({'username':f'engineer{i}','name':f'工程人员{i}','role':'member','company':'承希科技','department':'交付中心 / 工程部'} for i in range(7))
    initial['users'].append({'username':'unassigned','name':'待分配人员','role':'member'})
    config_path.write_text(json.dumps(initial, ensure_ascii=False))
    with patch.object(r,'CONFIG_PATH',config_path), patch.object(r,'USER_DATA_DIR',Path(tmp)), patch.object(r,'SESSIONS',{'preview':'preview','alice':'alice'}), patch.object(r,'crm_on_change'):
        unit=r.crm_unit_save({'name':'保留客户','type':'业主单位'},'preview')['unit']
        person=r.crm_person_save({'name':'保留联系人','unit_id':unit['id']},'preview')['person']
        relation=r.crm_relation_save({'person_id':person['id'],'our_member':'E001'},'preview')['relation']
        r.crm_action_add({'relation_id':relation['id'],'type':'拜访','record_kind':'plan','next_step':'保留跟进'},'preview')
        before={k:r.crm_collection_path('preview',k).read_bytes() for k in ('units','people','relations','actions')}
        server=r.ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':1600,'height':1100})
                context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/workspace/usermanage')
                page.get_by_role('button',name='调整我方组织画布',exact=True).click()
                dialog=page.get_by_role('dialog',name='调整我方组织架构',exact=True)
                expect(dialog.locator('.org-editor')).to_be_visible()
                dialog.locator('.oe-toolbar .el-select').first.click()
                page.get_by_role('option',name='承希科技',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(4)
                department_card=dialog.locator('.oe-node').filter(has=page.locator('strong',has_text='工程部'))
                expect(department_card.locator('.oe-node-names span')).to_have_count(6)
                expect(department_card.locator('.oe-more-names')).to_contain_text('另有 2 人')
                expect(dialog.locator('[data-person-id="unassigned"]')).to_have_class(__import__('re').compile('unassigned'))
                expect(dialog.locator('[data-person-id="unassigned"]')).to_contain_text('未分配组织')
                root=dialog.locator('.oe-node').filter(has=page.locator('strong',has_text='承希科技'))
                # Node child insertion stays a draft until explicit save.
                root.get_by_role('button',name='＋ 下级',exact=True).click()
                edit=page.get_by_role('dialog',name='新增下级部门',exact=True)
                edit.get_by_label('组织节点名称').fill('技术中心')
                edit.get_by_role('button',name='加入草稿',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(5)
                def root_centered():
                    return dialog.locator('.oe-node').evaluate_all('''es => {
                      const cards=es.map(e=>({x:parseFloat(e.style.left),y:parseFloat(e.style.top)}));
                      const top=Math.min(...cards.map(c=>c.y)), root=cards.find(c=>c.y===top);
                      const level=Math.min(...cards.filter(c=>c.y>top).map(c=>c.y));
                      const children=cards.filter(c=>c.y===level).map(c=>c.x);
                      return Math.abs(root.x-(Math.min(...children)+Math.max(...children))/2)<1;
                    }''')
                assert root_centered(), 'adding a child must automatically refresh the centered tree layout'
                assert 'internal_organization' not in json.loads(config_path.read_text())
                # Real HTML5 person drag, including a person from another company.
                snapshot=r.internal_organization_get('preview')
                bob=snapshot['members'][2]
                data_transfer=page.evaluate_handle('new DataTransfer()')
                source=dialog.locator('[data-person-id="carol"]')
                source.dispatch_event('dragstart',{'dataTransfer':data_transfer})
                target=dialog.locator('.oe-node').filter(has=page.locator('strong',has_text='技术中心'))
                target.dispatch_event('drop',{'dataTransfer':data_transfer})
                source.dispatch_event('dragend',{'dataTransfer':data_transfer})
                # Move an entire departmental branch via the explicit parent control.
                department=dialog.locator('.oe-node').filter(has=page.locator('strong',has_text='交付中心'))
                department.click()
                dialog.locator('.oe-properties .el-select').click()
                page.get_by_role('option',name='研发中心',exact=True).click()
                dialog.get_by_role('button',name='修改上级',exact=True).click()
                dialog.get_by_role('button',name='自动排版',exact=True).click()
                dialog.get_by_role('button',name='保存组织调整（未保存）',exact=True).click()
                expect(dialog.get_by_role('button',name='保存组织调整',exact=True)).to_be_disabled()
                updated=json.loads(config_path.read_text())
                assert updated['users'][1]['department']=='研发中心 / 交付中心 / 工程部'
                assert updated['users'][3]['company']=='承希科技' and updated['users'][3]['department']=='技术中心'
                for index,user in enumerate(updated['users']):
                    for key,value in initial['users'][index].items():
                        if key not in ('company','department'): assert user[key]==value
                page.screenshot(path=str(artifacts/'用户管理-我方组织画布.png'),full_page=False)
                dialog.get_by_role('button',name='关闭画布',exact=True).click()
                page.goto(base+'/workspace/crm')
                page.get_by_role('tab',name='组织架构',exact=True).click()
                page.get_by_text('我方组织',exact=True).click()
                page.get_by_role('button',name='调整我方组织画布',exact=True).click()
                expect(dialog.locator('.org-editor')).to_be_visible()
                dialog.locator('.oe-toolbar .el-select').first.click()
                page.get_by_role('option',name='承希科技',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(5)
                expect(dialog.locator('[data-person-id="carol"]')).to_contain_text('技术中心')
                expect(page.get_by_role('option',name='承希科技',exact=True)).not_to_be_visible()
                page.screenshot(path=str(artifacts/'客户经营-我方组织画布.png'),full_page=False)
                for key,value in before.items(): assert r.crm_collection_path('preview',key).read_bytes()==value
                ordinary=browser.new_context()
                ordinary.add_cookies([{'name':'pws_session','value':'alice','url':base}])
                for method in ('get','post'):
                    response=getattr(ordinary.request,method)(base+'/api/admin-organization/canvas',**({'data':{}} if method=='post' else {}))
                    assert response.status==403
                assert not errors, errors
                browser.close()
                print('PASS: shared entries, drafts, branch move, cross-company drag, identity/data preservation, API authorization')
        finally:
            server.shutdown();server.server_close()
