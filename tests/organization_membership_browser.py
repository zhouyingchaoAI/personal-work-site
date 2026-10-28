import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.runtime as runtime


with tempfile.TemporaryDirectory(prefix='membership-browser-') as temporary:
    config = Path(temporary) / 'config.json'
    users = [{'username':'preview','name':'管理员','role':'superadmin','company':'测试公司'},
             {'username':'alice','name':'张工','employee_id':'E001','role':'member','company':'测试公司','department':'工程部'},
             {'username':'bob','name':'李工','role':'member','company':'测试公司','department':'研发部'}]
    config.write_text(json.dumps({'users':users}))
    with patch.object(runtime,'CONFIG_PATH',config), patch.object(runtime,'USER_DATA_DIR',Path(temporary)), patch.object(runtime,'SESSIONS',{'preview':'preview'}), patch.object(runtime,'crm_on_change'):
        root=runtime.crm_unit_save({'name':'测试客户','organization_level':'company'},'preview')['unit']
        child=runtime.crm_unit_save({'name':'研发组织','organization_level':'unit','parent_unit_id':root['id']},'preview')['unit']
        person=runtime.crm_person_save({'name':'客户张工','unit_id':root['id'],'title':'专家'},'preview')['person']
        server=runtime.ThreadingHTTPServer(('127.0.0.1',0),runtime.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':1366,'height':900})
                base=f'http://127.0.0.1:{server.server_port}'
                context.add_cookies([{'name':'pws_session','value':'preview','url':base}])
                page=context.new_page()
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))

                def select_node(dialog, name):
                    dialog.locator('.oe-toolbar .el-select').nth(1).click()
                    page.get_by_role('option',name=name,exact=True).click()
                    dialog.get_by_role('button',name='添加已有人员',exact=True).click()
                    return page.get_by_role('dialog',name=f'添加人员 · {name}',exact=True)

                def customer_canvas():
                    page.goto(base+'/workspace/crm')
                    page.get_by_role('tab',name='五位一体',exact=True).click()
                    page.get_by_text('客户组织架构',exact=True).click()
                    page.get_by_role('button',name='调整架构画布',exact=True).click()
                    return page.get_by_role('dialog',name='调整客户组织架构',exact=True)

                dialog=customer_canvas()
                picker=select_node(dialog,'研发组织')
                picker.get_by_label('快速索引人员').fill('客户张工')
                with page.expect_response(lambda response:'/crm/person/save' in response.url) as pending:
                    picker.get_by_role('button',name='添加人员',exact=True).click()
                response=pending.value.json()
                assert response.get('ok'), response
                assert response['person'].get('unit_ids')==[child['id']], response
                expect(picker.get_by_role('button',name='移除兼任',exact=True)).to_be_visible()
                picker.get_by_role('button',name='完成',exact=True).click()
                expect(picker).not_to_be_visible()
                for node in (root,child):
                    expect(dialog.locator(f'[data-node-id="{node["id"]}"] .oe-node-names')).to_contain_text('客户张工')
                if os.environ.get('CRM_ARTIFACT_DIR'):
                    artifacts=Path(os.environ['CRM_ARTIFACT_DIR']);artifacts.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(artifacts/'customer-multiple-organizations.png'),animations='disabled')
                dialog=customer_canvas()
                picker=select_node(dialog,'研发组织')
                picker.get_by_label('快速索引人员').fill('客户张工')
                picker.get_by_role('button',name='移除兼任',exact=True).click()
                expect(picker.get_by_role('button',name='添加人员',exact=True)).to_be_visible()
                saved=runtime.crm_load('preview','people')[person['id']]
                assert saved['unit_id']==root['id'] and saved['unit_ids']==[]
                assert len(runtime.crm_load('preview','people'))==1

                page.goto(base+'/workspace/usermanage')
                page.get_by_role('button',name='调整我方组织画布',exact=True).click()
                dialog=page.get_by_role('dialog',name='调整我方组织架构',exact=True)
                picker=select_node(dialog,'研发部')
                picker.get_by_label('快速索引人员').fill('E001')
                expect(picker.locator('.oe-membership-list article')).to_have_count(1)
                picker.get_by_role('button',name='添加人员',exact=True).click()
                expect(picker.get_by_role('button',name='移除兼任',exact=True)).to_be_visible()
                assert 'internal_organization' not in json.loads(config.read_text())
                picker.get_by_role('button',name='完成',exact=True).click()
                dialog.get_by_role('button',name='保存组织调整（未保存）',exact=True).click()
                expect(dialog.get_by_role('button',name='保存组织调整',exact=True)).to_be_disabled()
                assert json.loads(config.read_text())['users']==users
                snapshot=runtime.internal_organization_get('preview')
                member=next(member for member in snapshot['members'] if member['username']=='alice')
                assert len(member['node_ids'])==1 and member['node_id']!=member['node_ids'][0]
                page.reload()
                page.get_by_role('button',name='调整我方组织画布',exact=True).click()
                picker=select_node(dialog,'研发部')
                picker.get_by_label('快速索引人员').fill('E001')
                expect(picker.get_by_role('button',name='移除兼任',exact=True)).to_be_visible()
                if os.environ.get('CRM_ARTIFACT_DIR'):
                    page.screenshot(path=str(artifacts/'internal-organization-member-search.png'),animations='disabled')
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();server.server_close()

print('PASS: customer/internal membership search, add, remove, persistence, drafts, identity and account permissions unchanged')
