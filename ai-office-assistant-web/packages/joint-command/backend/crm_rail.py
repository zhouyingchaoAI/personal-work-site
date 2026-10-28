"""轨交协作参考模板；不是项目审批权限或法定流程的自动判定。"""
CRM_ORGANIZATIONS = [
    {"type":"主管单位", "label":"主管与协调", "departments":"发改 / 住建 / 交通运输等主管部门", "duty":"规划审批、建设监管与运营监管分别确认职责；指挥部按实际授权登记。", "evidence":"建设规划及批复、属地职责清单", "stages":["立项","验收","初期运营"]},
    {"type":"业主单位", "label":"投资与建设", "departments":"建设管理 / 合约采购 / 技术 / 财务", "duty":"确认项目法人、采购主体、建设组织与合同支付责任；指挥部可作为业主执行机构。", "evidence":"采购公告、授权分工、合同及付款条款", "stages":["立项","设计","招标","定标","履约","联调试运行","验收","初期运营","付款"]},
    {"type":"总包单位", "label":"集成与交付", "departments":"项目部 / 商务采购 / 技术 / 现场交付", "duty":"按合同范围管理施工、设备集成和分包接口；非所有项目均设总包。", "evidence":"总分包界面、技术协议、交付计划", "stages":["设计","招标","履约","联调试运行","验收","付款"]},
    {"type":"设计单位", "label":"方案与接口", "departments":"总体总包 / 专业设计 / 设计代表", "duty":"明确设计需求、专业接口和变更依据，技术意见不等同于采购决策。", "evidence":"设计文件、接口清单、变更确认", "stages":["立项","设计","招标","履约","联调试运行","验收"]},
    {"type":"厂商", "label":"产品与技术供给", "departments":"产品 / 研发 / 解决方案 / 交付支持", "duty":"确认产品能力、供货周期、技术接口、授权与售后支持；厂商意见不替代业主采购决策。", "evidence":"产品清单、授权文件、供货承诺、技术澄清", "stages":["设计","招标","定标","履约","联调试运行","验收"]},
]
CRM_RAIL_STAGES = [
    {"id":"立项","title":"规划与可研","action":"核实线路、建设主体与运营需求，建立项目范围清单", "deliverable":"项目范围、公开批复与需求纪要", "gate":"确认立项依据与需求责任人"},
    {"id":"设计","title":"设计与技术接口","action":"组织技术需求澄清，核对设计接口与可维护性要求", "deliverable":"技术规格、接口清单、设计澄清记录", "gate":"形成经责任方确认的技术边界"},
    {"id":"招标","title":"采购与招标","action":"核对公告、资质、采购范围和澄清截止时间", "deliverable":"资格清单、响应计划、正式澄清文件", "gate":"按公告要求提交响应材料"},
    {"id":"定标","title":"结果与签约","action":"跟进公开采购结果，核实合同技术和商务条款", "deliverable":"结果公告、合同、技术协议", "gate":"确认合同主体、交付范围和支付条件"},
    {"id":"履约","title":"供货与施工","action":"协调设备到货、安装接口、设计变更及问题闭环", "deliverable":"交付计划、到货验收单、变更记录", "gate":"按合同完成相应交付节点"},
    {"id":"联调试运行","title":"联调与试运行","action":"对齐联调测试计划，跟进系统接口与缺陷整改", "deliverable":"联调记录、测试报告、问题闭环清单", "gate":"完成适用测试并记录问题处理结果"},
    {"id":"验收","title":"工程验收与移交","action":"核对验收条件、竣工资料、培训与设备移交清单", "deliverable":"验收记录、竣工资料、移交与培训凭证", "gate":"按适用工程验收程序确认完成情况"},
    {"id":"初期运营","title":"安全评估与运营","action":"配合运营前安全评估问题整改，核实接管和保障安排", "deliverable":"评估整改证据、接管资料、运维保障方案", "gate":"安全评估及运营手续由有权主体依法确认"},
    {"id":"付款","title":"计量结算与回款","action":"按合同付款节点核对计量、发票与审批资料", "deliverable":"计量确认、发票、支付申请及回款记录", "gate":"核实付款条件和到期日；付款可贯穿多个阶段"},
]


def crm_stage(stage):
    return next((s for s in CRM_RAIL_STAGES if s['id'] == stage), CRM_RAIL_STAGES[1])


def crm_followups(username):
    people = crm_load(username, 'people')
    relations = crm_load(username, 'relations')
    today = crm_now()[:10]
    result = []
    for action in crm_load(username, 'actions').values():
        if not action.get('next_step') or action.get('completed_at'):
            continue
        person = people.get(relations.get(action.get('relation_id'), {}).get('person_id'), {})
        result.append({**action, 'person_name': person.get('name', '待核实联系人'),
                       'owner_label': crm_member_label(username, action.get('owner')), 'owner_staff': crm_member_profile(username, action.get('owner')),
                       'overdue': bool(action.get('due_date') and action['due_date'] < today)})
    return sorted(result, key=lambda a: (not a['overdue'], a.get('due_date') or '9999'))


def crm_followup_complete(payload, username, completed_by=''):
    with CRM_LOCK:
        actions = crm_load(username, 'actions')
        record = actions.get(crm_text(payload.get('id')))
        if not record or not record.get('next_step'):
            return {'ok': False, 'error': '跟进事项不存在'}
        if record.get('completed_at'):
            return {'ok': True}
        record['completed_at'] = crm_now()
        record['completed_by'] = completed_by or username
        record['updated_by'] = completed_by or username
        record['updated_at'] = record['completed_at']
        crm_store(username, 'actions', actions)
        crm_on_change(username)
        return {'ok': True}


def crm_can_complete_followup(action, relation, user, caps, resolve_member):
    if not caps.get('read') or not caps.get('write'):
        return False
    owner = action.get('_owner', '')
    if owner == user.get('username'):
        return True
    profile, _ = resolve_member(owner, action.get('owner') or relation.get('our_member'))
    return bool(profile and profile.get('username') == user.get('username'))


def crm_followup_complete_authorized(payload, caller):
    with CRM_LOCK:
        caps = crm_capabilities(caller)
        if not caps.get('read') or not caps.get('write'):
            raise PermissionError('没有完成客户跟进事项的权限')
        snapshot = crm_read_snapshot(caller, ('relations', 'actions'))
        matches = [a for a in snapshot['actions'] if a.get('id') == crm_text(payload.get('id'))]
        if len(matches) != 1:
            raise PermissionError('跟进事项不在可操作范围内或标识冲突')
        action = matches[0]
        relation = next((item for item in snapshot['relations']
                         if (item.get('_owner'), item.get('id')) ==
                         (action.get('_owner'), action.get('relation_id'))), {})
        if not action.get('_owner') or not crm_can_complete_followup(action, relation, caller, caps, crm_member_resolver()):
            raise PermissionError('仅跟进负责人可以完成该事项')
        return crm_followup_complete(payload, action['_owner'], completed_by=caller['username'])


def crm_read_playbook(user):
    caps = crm_capabilities(user)
    if not caps.get('read'):
        raise PermissionError('没有客户经营读取权限')
    snapshot = crm_read_snapshot(user, ('people', 'relations', 'actions'))
    people = {(p['_owner'], p['id']): p for p in snapshot['people']}
    relations = {(r['_owner'], r['id']): r for r in snapshot['relations']}
    today = crm_now()[:10]
    followups = []
    resolve_member = crm_member_resolver()
    for action in snapshot['actions']:
        if not action.get('next_step') or action.get('completed_at'):
            continue
        owner = action.get('_owner', user['username'])
        relation = relations.get((owner, action.get('relation_id')), {})
        person = people.get((owner, relation.get('person_id')), {})
        owner_staff, owner_label = resolve_member(owner, action.get('owner'))
        followups.append({**action, 'person_name': person.get('name', '待核实联系人'),
                          'can_complete': crm_can_complete_followup(action, relation, user, caps, resolve_member),
                          'owner_label': owner_label,
                          'owner_staff': owner_staff,
                          'overdue': bool(action.get('due_date') and action['due_date'] < today)})
    return crm_playbook(user['username'], sorted(followups, key=lambda a: (not a['overdue'], a.get('due_date') or '9999')))


def crm_playbook(username, followups=None):
    return {'ok': True, 'organizations': CRM_ORGANIZATIONS, 'stages': CRM_RAIL_STAGES,
            'followups': crm_followups(username) if followups is None else followups,
            'sources': [
                {'title':'国务院：保障城市轨道交通安全运行的意见', 'url':'https://app.www.gov.cn/govdata/gov/201803/23/421876/article.html'},
                {'title':'交通运输部：运营安全评估管理办法', 'url':'https://xxgk.mot.gov.cn/jigou/ysfws/202308/t20230828_3901763.html'},
                {'title':'北京：建设工程验收管理办法（地方参考）', 'url':'https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_60035.html'}]}
