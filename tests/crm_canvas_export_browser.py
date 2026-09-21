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
                import struct
                import xml.etree.ElementTree as ET
                expect(dialog.locator('.oe-node')).to_have_count(4)
                def download(format, filename):
                    dialog.get_by_role('button',name='导出架构图',exact=True).click()
                    with page.expect_download() as info:
                        page.get_by_role('menuitem',name='PNG 图片' if format=='png' else 'SVG 矢量图',exact=True).click()
                    item=info.value
                    assert item.suggested_filename.endswith('.'+format)
                    assert item.failure() is None
                    item.save_as(str(artifacts/filename))
                    return artifacts/filename
                svg=download('svg','完整组织架构.svg')
                data=ET.parse(svg).getroot()
                ns={'s':'http://www.w3.org/2000/svg'}
                titles=[n.text for n in data.findall('.//s:title',ns)]
                assert '东区客户0' in titles and '东区客户1' in titles
                assert len(data.findall('.//s:rect',ns))==5
                assert '单独查看' not in svg.read_text()
                png=download('png','完整组织架构.png')
                content=png.read_bytes()
                assert content[:8]==bytes([137,80,78,71,13,10,26,10])
                width,height=struct.unpack('>II',content[16:24])
                assert width>0 and height>0 and len(content)>5000
                assert width==int(float(data.attrib['width'])*2)
                assert height==int(float(data.attrib['height'])*2)
                stage=dialog.locator('.oe-stage')
                bounds=stage.bounding_box()
                page.mouse.move(bounds['x']+10,bounds['y']+10)
                page.mouse.down();page.mouse.move(bounds['x']+400,bounds['y']+200);page.mouse.up()
                shifted=download('svg','平移后完整组织架构.svg')
                assert shifted.read_text()==svg.read_text(), 'viewport must not clip exported nodes'
                dialog.get_by_role('button',name='适应画布',exact=True).click()
                dialog.locator('[data-node-id="'+root['id']+'"]').get_by_role('button',name='收起下级',exact=True).click()
                expect(dialog.locator('.oe-node')).to_have_count(1)
                folded=download('svg','折叠组织架构.svg')
                assert len(ET.parse(folded).getroot().findall('.//s:rect',ns))==2
                assert '下级已折叠' in folded.read_text()
                assert not errors,errors
                print('PASS PNG and valid SVG downloads, full geometry independent of viewport, collapse scope, no editing controls',flush=True)
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()

