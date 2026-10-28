"""Full-page walkthrough of the CRM assistant with seeded demo data.

Starts an isolated in-process server (temp user data, superadmin 'preview'),
seeds units/people/relations/actions/opportunities, then screenshots every
module/sub-view at desktop and mobile widths. Also records API timings,
payload sizes, page errors and console errors.
"""
import json, os, sys, tempfile, threading, time
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backend.runtime as r

OUT = Path(os.environ.get('CRM_ARTIFACT_DIR', '/tmp/crm_walkthrough_shots'))
OUT.mkdir(parents=True, exist_ok=True)
MOBILE = os.environ.get('CRM_MOBILE', '1') == '1'
ONLY = set(filter(None, os.environ.get('CRM_ONLY', '').split(',')))
today = date.today()
d = lambda n: (today + timedelta(days=n)).isoformat()

users = [
    {'username': 'preview', 'name': '周演示', 'role': 'superadmin', 'company': '湖南承希科技有限公司', 'department': '联合指挥部', 'title': '总指挥'},
    {'username': 'east', 'name': '李东区', 'role': 'member', 'company': '湖南承希科技有限公司', 'department': '东区作战平台', 'title': '客户经理', 'employee_id': 'E001'},
    {'username': 'west', 'name': '王西区', 'role': 'member', 'company': '湖南承希科技有限公司', 'department': '西区作战平台', 'title': '客户经理', 'employee_id': 'W001'},
    {'username': 'gd', 'name': '陈广东', 'role': 'member', 'company': '湖南承希科技有限公司', 'department': '广东区作战平台', 'title': '区域总监', 'employee_id': 'G001'},
    {'username': 'mid', 'name': '赵中区', 'role': 'member', 'company': '湖南承希科技有限公司', 'department': '中区作战平台', 'title': '客户经理', 'employee_id': 'M001'},
]

def seed():
    U = lambda **kw: r.crm_unit_save(kw, 'preview')['unit']
    P = lambda **kw: r.crm_person_save(kw, 'preview')['person']
    R = lambda **kw: r.crm_relation_save(kw, 'preview')['relation']
    A = lambda **kw: r.crm_action_add(kw, 'preview')
    O = lambda **kw: r.crm_opportunity_save(kw, 'preview')
    # 业主单位：集团 → 子公司 → 单位
    grp = U(name='杭州地铁集团有限公司', type='业主单位', organization_level='company', business_regions=['东区'], region='杭州', line_scale='12 条线 500 km', win_rate='45%', bid_preference='综合评分法，重技术', history='3 号线信号、5 号线综合监控')
    ops = U(name='杭州地铁运营分公司', type='业主单位', organization_level='subsidiary', parent_unit_id=grp['id'], business_regions=['东区'], region='杭州')
    sig = U(name='信号与通信部', type='业主单位', organization_level='unit', parent_unit_id=ops['id'], business_regions=['东区'], region='杭州')
    cons = U(name='杭州地铁建设分公司', type='业主单位', organization_level='subsidiary', parent_unit_id=grp['id'], business_regions=['东区'], region='杭州')
    eng = U(name='机电工程部', type='业主单位', organization_level='unit', parent_unit_id=cons['id'], business_regions=['东区'], region='杭州')
    # 其他类型
    sup = U(name='浙江省轨道交通主管局', type='主管单位', organization_level='company', business_regions=['东区'], region='杭州')
    gc = U(name='中铁某局集团电务公司', type='总包单位', organization_level='company', business_regions=['东区', '中区'], region='武汉')
    design = U(name='某市轨道设计研究院', type='设计单位', organization_level='company', business_regions=['西区'], region='成都')
    vendor = U(name='某信号系统厂商', type='厂商', organization_level='company', business_regions=['广东区'], region='广州')
    gz = U(name='广州地铁集团', type='业主单位', organization_level='company', business_regions=['广东区'], region='广州')
    gz_u = U(name='广州地铁建设事业总部', type='业主单位', organization_level='unit', parent_unit_id=gz['id'], business_regions=['广东区'], region='广州')
    cd = U(name='成都轨道交通集团', type='业主单位', organization_level='company', business_regions=['西区'], region='成都')
    cd_u = U(name='成都轨道建设管理公司', type='业主单位', organization_level='unit', parent_unit_id=cd['id'], business_regions=['西区'], region='成都')

    people = {}
    def add(key, **kw):
        people[key] = P(**kw)
    add('zhang', name='张总', unit_id=sig['id'], title='部长', department='信号与通信部', decision_role='定技术', importance='重要', support_level='支持', influence=85, stance='支持', maintenance_days=30, responsibilities='信号系统技术选型与验收')
    add('liu', name='刘主任', unit_id=sig['id'], title='技术主任', department='信号与通信部', decision_role='签验收', importance='重要', support_level='积极支持', influence=70, stance='支持', manager_id=people['zhang']['id'])
    add('wang', name='王工', unit_id=sig['id'], title='通信专工', department='信号与通信部', importance='一般', support_level='中立', influence=40, stance='中立', manager_id=people['liu']['id'])
    add('chen', name='陈经理', unit_id=eng['id'], title='机电经理', department='机电工程部', decision_role='采购经办', importance='重要', support_level='', influence=60, stance='未知')
    add('zhao', name='赵副总', unit_id=ops['id'], title='副总经理', decision_role='定标', importance='重要', support_level='中立', influence=90, stance='中立', maintenance_days=60)
    add('sun', name='孙处长', unit_id=sup['id'], title='处长', decision_role='批付款', importance='重要', support_level='支持', influence=75)
    add('zhou', name='周项目', unit_id=gc['id'], title='项目经理', decision_role='需求提出', importance='一般', support_level='支持', influence=55)
    add('wu', name='吴总工', unit_id=design['id'], title='总工程师', decision_role='定技术', importance='重要', support_level='反对', influence=80)
    add('zheng', name='郑销售', unit_id=vendor['id'], title='销售总监', importance='一般', support_level='中立', influence=30)
    add('gz1', name='黄主任', unit_id=gz_u['id'], title='建设主任', decision_role='定标', importance='重要', support_level='支持', influence=82)
    add('gz2', name='林专工', unit_id=gz_u['id'], title='信号专工', importance='一般', support_level='', influence=35, manager_id=people['gz1']['id'])
    add('cd1', name='何部长', unit_id=cd_u['id'], title='工程部长', decision_role='定技术', importance='重要', support_level='中立', influence=78)

    rel = {}
    rel['zhang_e'] = R(person_id=people['zhang']['id'], our_member='east', source='老同事引荐', intro_path='刘主任 → 张总')
    rel['zhang_p'] = R(person_id=people['zhang']['id'], our_member='preview', source='高层互访')
    rel['liu_e'] = R(person_id=people['liu']['id'], our_member='east', source='技术交流')
    rel['wang_e'] = R(person_id=people['wang']['id'], our_member='east', source='现场联调')
    rel['chen_e'] = R(person_id=people['chen']['id'], our_member='east', source='招标答疑')
    rel['zhao_p'] = R(person_id=people['zhao']['id'], our_member='preview', source='行业峰会')
    rel['sun_m'] = R(person_id=people['sun']['id'], our_member='mid', source='主管单位调研')
    rel['zhou_m'] = R(person_id=people['zhou']['id'], our_member='mid', source='总包协调会')
    rel['wu_w'] = R(person_id=people['wu']['id'], our_member='west', source='设计联络')
    rel['zheng_none'] = R(person_id=people['zheng']['id'], our_member='', source='展会交换名片')
    rel['gz1_g'] = R(person_id=people['gz1']['id'], our_member='gd', source='老客户')
    rel['gz2_g'] = R(person_id=people['gz2']['id'], our_member='gd', source='现场服务')
    rel['cd1_w'] = R(person_id=people['cd1']['id'], our_member='west', source='方案汇报')

    # 真实互动（含历史、触发衰减）
    A(relation_id=rel['zhang_e']['id'], type='拜访', happened_at=d(-5), intel='汇报 7 号线信号方案，张总认可国产化路线，要求补充接口清单', effective=True, bidirectional=True, decision_node='设计', project_id='HZ-07-SIG', next_step='补充信号接口清单并取得书面回复', owner='east', due_date=d(2))
    A(relation_id=rel['zhang_e']['id'], type='电话', happened_at=d(-40), intel='沟通招标时间计划', effective=True)
    A(relation_id=rel['liu_e']['id'], type='技术交流', happened_at=d(-12), intel='联调测试大纲评审通过', effective=True, bidirectional=True, decision_node='联调试运行')
    A(relation_id=rel['wang_e']['id'], type='微信沟通', happened_at=d(-60), intel='确认现场勘查时间')
    A(relation_id=rel['chen_e']['id'], type='拜访', happened_at=d(-25), intel='了解机电采购计划，暂无明确需求', next_step='邀请参加产品发布会', owner='east', due_date=d(-3))
    A(relation_id=rel['zhao_p']['id'], type='方案汇报', happened_at=d(-100), intel='高层互访，达成战略合作意向', effective=True, bidirectional=True, next_step='安排高层回访', owner='preview', due_date=d(-10))
    A(relation_id=rel['sun_m']['id'], type='拜访', happened_at=d(-15), intel='沟通付款流程', effective=True, next_step='提交付款申请材料', owner='mid', due_date=d(0))
    A(relation_id=rel['zhou_m']['id'], type='联调协调', happened_at=d(-3), intel='协调总包进场计划', effective=True, bidirectional=True, project_id='WH-11-ISCS')
    A(relation_id=rel['wu_w']['id'], type='技术交流', happened_at=d(-70), intel='吴总工倾向竞品方案，需进一步说服', next_step='组织技术对标汇报', owner='west', due_date=d(7))
    A(relation_id=rel['gz1_g']['id'], type='拜访', happened_at=d(-8), intel='18 号线延伸段前期沟通', effective=True, bidirectional=True, project_id='GZ-18-EXT', next_step='提交可研阶段技术建议书', owner='gd', due_date=d(5))
    A(relation_id=rel['cd1_w']['id'], type='方案汇报', happened_at=d(-20), intel='方案汇报获得认可', effective=True, decision_node='立项', project_id='CD-27-SIG')
    # 计划（无日期）
    A(relation_id=rel['gz2_g']['id'], record_kind='plan', next_step='建立技术层面联系', owner='gd', due_date='')
    A(relation_id=rel['liu_e']['id'], record_kind='plan', next_step='邀请参加验收标准研讨', owner='east', due_date=d(14))

    opps = [
        dict(code='HZ-07-SIG', name='杭州地铁 7 号线信号系统', owner_unit='杭州地铁集团有限公司', owner_unit_id=grp['id'], amount=8600, region='东区', manager='李东区', sales_stage='初设阶段', win_rate='60%', bid_date=d(45), contract_date=d(120), outcome='open'),
        dict(code='WH-11-ISCS', name='武汉 11 号线综合监控', owner_unit='中铁某局集团电务公司', owner_unit_id=gc['id'], amount=3200, region='中区', manager='赵中区', sales_stage='招标执行', win_rate='45%', bid_date=d(10), contract_date=d(60), outcome='open'),
        dict(code='GZ-18-EXT', name='广州 18 号线延伸段信号', owner_unit='广州地铁集团', owner_unit_id=gz['id'], amount=12500, region='广东区', manager='陈广东', sales_stage='立项阶段', win_rate='30%', bid_date=d(200), contract_date=d(300), outcome='open'),
        dict(code='CD-27-SIG', name='成都 27 号线信号升级', owner_unit='成都轨道交通集团', owner_unit_id=cd['id'], amount=560, region='西区', manager='王西区', sales_stage='初设阶段', win_rate='50%', outcome='open'),
        dict(code='HZ-03-UPG', name='杭州 3 号线既有线改造', owner_unit='杭州地铁集团有限公司', owner_unit_id=grp['id'], amount=1500, region='东区', manager='', sales_stage='合同签订', win_rate='70%', outcome='won'),
        dict(code='SZ-01-LOST', name='深圳某线路综合监控', owner_unit='广州地铁集团', owner_unit_id=gz['id'], amount=2200, region='广东区', manager='陈广东', sales_stage='合同签订', win_rate='10%', outcome='lost'),
    ]
    for o in opps:
        res = O(**o)
        if not res.get('ok'): print('opportunity seed failed', o['code'], res)
    return {'units': 13, 'people': len(people), 'relations': len(rel), 'opportunities': len(opps)}


class Quiet(r.Handler):
    def log_message(self, *a): pass


def main():
    with tempfile.TemporaryDirectory(prefix='crm-walk-') as tmp:
        with patch.object(r, 'USER_DATA_DIR', Path(tmp)), patch.object(r, 'read_config', return_value={'users': users}), \
             patch.object(r, 'SESSIONS', {'preview': 'preview'}), patch.object(r, 'crm_on_change'), patch.object(r, 'crm_audit'), \
             patch.object(r, 'crm_infra_status', lambda: {'neo4j': False, 'redis': False, 'neo4j_configured': False, 'redis_configured': False}):
            counts = seed()
            print('seeded', counts)
            server = r.ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}'
            report = {'api': [], 'errors': [], 'console': [], 'shots': []}
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
                    ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1)
                    ctx.add_cookies([{'name': 'pws_session', 'value': 'preview', 'url': base}])
                    page = ctx.new_page()
                    page.set_default_timeout(8000)
                    page.route('**/api/crm/security/amap-settings', lambda route: route.fulfill(json={'enabled': False}))
                    page.on('pageerror', lambda e: report['errors'].append(str(e)))
                    page.on('console', lambda m: report['console'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
                    def on_response(resp):
                        url = resp.url
                        if '/api/crm/' in url:
                            try: size = len(resp.body())
                            except Exception: size = -1
                            report['api'].append({'url': url.replace(base, ''), 'status': resp.status, 'bytes': size, 'enc': resp.headers.get('content-encoding', '')})
                    page.on('response', on_response)

                    def shot(name, full=True, mobile=False):
                        path = OUT / f'{"m-" if mobile else ""}{name}.png'
                        page.wait_for_timeout(500)
                        page.screenshot(path=str(path), full_page=full)
                        report['shots'].append(path.name)
                        print('shot', path.name)

                    def tab(name):
                        page.get_by_role('tablist', name='客户经营模块', exact=True).get_by_role('tab', name=name, exact=True).click()
                        page.wait_for_timeout(600)

                    def subtab(group, name):
                        page.get_by_role('tablist', name=group, exact=True).get_by_role('tab', name=name, exact=True).click()
                        page.wait_for_timeout(500)

                    def close_dialogs():
                        page.keyboard.press('Escape'); page.wait_for_timeout(300)

                    t0 = time.perf_counter()
                    page.goto(base + '/workspace/crm')
                    page.wait_for_selector('.crm-workbench', timeout=30000)
                    page.wait_for_function("!document.querySelector('.crm-main > .el-loading-mask')", timeout=30000)
                    report['first_load_s'] = round(time.perf_counter() - t0, 2)
                    page.wait_for_timeout(800)

                    steps = []
                    def step(name, fn, full=True):
                        steps.append((name, fn, full))

                    step('01-home-workbench', lambda: None)
                    def home_personal():
                        btn = page.get_by_role('button', name='我的跟进', exact=True)
                        if btn.count(): btn.first.click()
                    step('02-home-personal', home_personal)
                    def home_management():
                        btn = page.get_by_role('button', name='管理待办', exact=True)
                        if btn.count(): btn.first.click()
                        head = page.locator('.wb-duty-head')
                        if head.count(): head.first.click()
                    step('03-home-management-open', home_management)
                    def home_map():
                        page.get_by_role('button', name='经营总览', exact=True).first.click(); page.wait_for_timeout(1500)
                    step('04-cockpit-overview', home_map, full=False)
                    def cockpit_section(label):
                        def fn():
                            loc = page.locator('.map-cockpit').get_by_text(label, exact=True)
                            if loc.count(): loc.first.click(); page.wait_for_timeout(900)
                        return fn
                    step('05-cockpit-dashboard', cockpit_section('经营分析'), full=False)
                    step('06-cockpit-integration', cockpit_section('五位一体'), full=False)
                    step('07-cockpit-opportunities', cockpit_section('商机管理'), full=False)
                    step('08-cockpit-battle', cockpit_section('项目作战地图'), full=False)
                    def back_home():
                        b = page.get_by_role('button', name='返回工作台', exact=True)
                        if b.count(): b.first.click(); page.wait_for_timeout(500)
                    step('09-dashboard-tab', lambda: (back_home(), tab('经营分析')))
                    step('10-customers-overview', lambda: tab('五位一体'))
                    def customer_detail():
                        row = page.locator('.crm-customer-workspace, .customer-workspace').first
                        link = page.get_by_role('button', name='查看详情').first if page.get_by_role('button', name='查看详情').count() else None
                        if link: link.click(); page.wait_for_timeout(600)
                    step('11-customers-overview-detail', customer_detail)
                    step('12-customers-contacts', lambda: (close_dialogs(), page.locator('.crm-subnav').get_by_text('联系人档案', exact=True).first.click(), page.wait_for_timeout(500)))
                    def contact_detail():
                        page.get_by_role('button', name='详情', exact=True).first.click(); page.wait_for_timeout(600)
                    step('13-contact-detail-drawer', contact_detail, full=False)
                    def contact_edit():
                        close_dialogs()
                        page.get_by_role('button', name='编辑', exact=True).first.click(); page.wait_for_timeout(600)
                    step('14-contact-edit-dialog', contact_edit, full=False)
                    step('15-customers-organization', lambda: (close_dialogs(), page.locator('.crm-subnav').get_by_text('客户组织架构', exact=True).first.click(), page.wait_for_timeout(600)))
                    def org_canvas():
                        page.get_by_role('button', name='调整架构画布', exact=True).click(); page.wait_for_timeout(1200)
                    step('16-organization-canvas', org_canvas, full=False)
                    step('17-assessment', lambda: (close_dialogs(), subtab('客户关系功能', '关系评估')))
                    def assessment_personal():
                        t = page.get_by_text('个人与客户', exact=True)
                        if t.count(): t.first.click(); page.wait_for_timeout(600)
                    step('18-assessment-personal', assessment_personal)
                    step('19-maintenance-relations', lambda: subtab('客户关系功能', '关系维系'))
                    def action_dialog():
                        page.get_by_role('button', name='登记动作', exact=True).first.click(); page.wait_for_timeout(600)
                    step('20-action-dialog', action_dialog, full=False)
                    step('21-maintenance-tasks', lambda: (close_dialogs(), page.get_by_role('tablist', name='关系维系视图', exact=True).get_by_role('tab', name='我的待办').first.click(), page.wait_for_timeout(500)))
                    step('22-coordination-workbench', lambda: subtab('客户关系功能', '责任统筹'))
                    step('23-coordination-graph', lambda: (page.get_by_text('关系网络 / 引荐', exact=True).click(), page.wait_for_timeout(1500)))
                    step('24-completion', lambda: subtab('客户关系功能', '资料补充'))
                    step('25-opportunities', lambda: tab('商机管理'))
                    def opp_detail():
                        b = page.locator('.el-tab-pane:visible, .crm-main').get_by_role('button', name='详情').first
                        if b.count(): b.click(); page.wait_for_timeout(700)
                    step('26-opportunity-detail', opp_detail, full=False)
                    step('27-battle', lambda: (close_dialogs(), tab('项目作战地图')))
                    def battle_expand():
                        item = page.locator('.ckp-collapse .el-collapse-item__header').first
                        if item.count(): item.click(); page.wait_for_timeout(900)
                    step('28-battle-expanded', battle_expand)
                    step('29-settings', lambda: page.locator('.crm-head').get_by_role('button', name='设置', exact=True).first.click())
                    def settings_each():
                        pass
                    step('30-quick-capture', lambda: (page.locator('.crm-head').get_by_role('button', name='信息收集', exact=True).first.click(), page.wait_for_timeout(700)), full=False)
                    step('31-usage-guide', lambda: (close_dialogs(), page.locator('.crm-head').get_by_role('button', name='更多').first.click(), page.wait_for_timeout(300), page.get_by_role('button', name='使用说明', exact=True).first.click(), page.wait_for_timeout(700)), full=False)
                    step('32-excel-import', lambda: (close_dialogs(), page.locator('.crm-head').get_by_role('button', name='更多').first.click(), page.wait_for_timeout(300), page.get_by_role('button', name='Excel 收集', exact=True).first.click(), page.wait_for_timeout(700)), full=False)

                    for name, fn, full in steps:
                        if ONLY and name not in ONLY: continue
                        try:
                            fn()
                        except Exception as e:
                            report['errors'].append(f'[step {name}] {type(e).__name__}: {str(e)[:300]}')
                            print('step failed', name, str(e)[:200])
                        shot(name, full=full)
                    close_dialogs()

                    if MOBILE:
                        page.goto(base + '/workspace/crm'); page.wait_for_selector('.crm-workbench', timeout=30000); page.wait_for_timeout(800)
                        # Mobile: switch module at wide width, then narrow the viewport (desktop tabs are hidden on narrow screens).
                        mobile_steps = [
                            ('01-home-workbench', lambda: (back_home(), tab('工作台'))),
                            ('10-customers-overview', lambda: (tab('五位一体'), subtab('客户关系功能', '客户档案'))),
                            ('12-customers-contacts', lambda: page.locator('.crm-subnav').get_by_text('联系人档案', exact=True).first.click()),
                            ('19-maintenance-relations', lambda: subtab('客户关系功能', '关系维系')),
                            ('25-opportunities', lambda: tab('商机管理')),
                            ('27-battle', lambda: tab('项目作战地图')),
                            ('04-cockpit-overview', lambda: (tab('工作台'), page.get_by_role('button', name='经营总览', exact=True).first.click(), page.wait_for_timeout(1200))),
                        ]
                        for name, fn in mobile_steps:
                            if ONLY and name not in ONLY: continue
                            try:
                                page.set_viewport_size({'width': 1440, 'height': 900}); page.wait_for_timeout(300)
                                fn(); page.wait_for_timeout(400)
                                page.set_viewport_size({'width': 390, 'height': 844}); page.wait_for_timeout(700)
                                closer = page.locator('.mobile-sidebar-close')
                                if closer.count() and closer.first.is_visible(): closer.first.click(); page.wait_for_timeout(300)
                                overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                                if overflow > 2: report['errors'].append(f'[mobile {name}] horizontal overflow {overflow}px')
                            except Exception as e:
                                report['errors'].append(f'[mobile {name}] {type(e).__name__}: {str(e)[:300]}')
                            shot(name, full=True, mobile=True)
                        page.set_viewport_size({'width': 1440, 'height': 900})
                    browser.close()
            finally:
                server.shutdown()
            (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
            print('first_load_s', report.get('first_load_s'))
            print('API calls:', len(report['api']), 'total bytes:', sum(a['bytes'] for a in report['api'] if a['bytes'] > 0))
            for a in sorted(report['api'], key=lambda x: -x['bytes'])[:12]: print('  ', a['status'], f"{a['bytes']/1024:8.1f}KB", a['url'][:90])
            print('page errors:', len(report['errors']))
            for e in report['errors']: print('  !', e[:300])
            print('console issues:', len(report['console']))
            for c in report['console'][:20]: print('  ?', c[:200])

if __name__ == '__main__':
    main()
