"""CRM-specific grants and metadata-only audit trail; no cross-owner data access."""
CRM_SECURITY_LOCK = threading.RLock()
CRM_SECURITY_ROLES = {'disabled':'无权限', 'viewer':'只读', 'account_manager':'客户经理', 'editor':'编辑', 'importer':'编辑与导入', 'regional_manager':'区域管理员'}
CRM_DATA_SCOPES = {'self':'仅本人','team':'本人及下属组织','organization':'指定组织','regions':'指定区域','all':'全部客户数据'}
CRM_LIAISON_REGIONS = {'东区', '中区', '西区', '广东区', '非区域人员'}


def crm_security_path(name):
    return USER_DATA_DIR / '.crm-security' / name


def crm_security_policies():
    path = crm_security_path('policies.json')
    if not path.exists():
        return {}
    # Fail closed on corrupted policy data instead of silently restoring access.
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('CRM权限配置异常，请联系超级管理员')
    return data


def crm_liaison_region_overrides():
    path = crm_security_path('liaison-regions.json')
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('我方人员区域配置异常，请联系超级管理员')
    return {str(username): region for username, region in data.items() if region in CRM_LIAISON_REGIONS}


def crm_liaison_region_save(payload, caller):
    """Persist a manual liaison-region override; blank restores organization inference."""
    if not (crm_capabilities(caller)['manage'] or caller.get('role') == 'superadmin'):
        raise PermissionError('只有客户经营管理员或超级管理员可以调整我方人员区域')
    username = str(payload.get('username', '') or '').strip()
    region = str(payload.get('region', '') or '').strip()
    if not find_user(username):
        raise ValueError('账号不存在')
    if region and region not in CRM_LIAISON_REGIONS:
        raise ValueError('请选择有效的人员区域')
    with CRM_SECURITY_LOCK:
        overrides = crm_liaison_region_overrides()
        if region:
            overrides[username] = region
        else:
            overrides.pop(username, None)
        record = {'region': region or '自动归属', 'updated_by': caller['username'], 'updated_at': datetime.now().isoformat(timespec='seconds')}
        crm_audit(caller['username'], 'liaison_region_requested', '/api/crm/security/liaison-region', 200, username, record)
        dest = crm_security_path('liaison-regions.json'); dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix('.tmp'); temp.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding='utf-8'); temp.replace(dest)
        crm_audit(caller['username'], 'liaison_region_applied', '/api/crm/security/liaison-region', 200, username, record)
    return {'ok': True, 'username': username, 'region': region}


def crm_capabilities(user):
    if user.get('role') == 'superadmin':
        return {'role':'superadmin','read':True,'write':True,'register_action':True,'import':True,'complete_import_task':True,'manage':False,'approve_changes':True,'appoint':True,'security_users':True,'batch_assign':True,'supervise':True,'expires_on':'','expired':False,'data_scope':'all','regions':[]}
    try:
        policy = crm_security_policies().get(user.get('username',''))
        old = user.get('assistant_permissions', {})
        system_admin = user.get('role') == 'admin'
        role = policy.get('role','disabled') if policy else ('viewer' if isinstance(old,dict) and old.get('crm') is True else ('admin' if system_admin else 'disabled'))
        expires = policy.get('expires_on','') if policy else ''
        expired = bool(expires and expires < datetime.now().strftime('%Y-%m-%d'))
        if expired: role = 'disabled'
        if policy and policy.get('manager') is True:
            role = 'manager'
            expired = False
            expires = ''
        regions = [item for item in (policy.get('regions', []) if policy else []) if item in CRM_BUSINESS_REGIONS]
        requested_scope = policy.get('data_scope', '') if policy else ''
        scope = 'all' if system_admin or role == 'manager' else ('regions' if role == 'regional_manager' else (requested_scope if requested_scope in CRM_DATA_SCOPES else ('regions' if regions else 'self')))
        if scope == 'regions' and not regions: scope = 'self'
        scope_company = str((policy or {}).get('scope_company', '') or '').strip()
        scope_departments = [str(item).strip() for item in ((policy or {}).get('scope_departments', []) or []) if str(item).strip()]
        default_register_action = role in ('account_manager','editor','importer','regional_manager','manager')
        register_action = True if role == 'manager' else (policy.get('register_action', default_register_action) if policy else default_register_action)
        return {'role':role,'read':role in ('viewer','account_manager','editor','importer','regional_manager','manager','admin'),'write':role in ('account_manager','editor','importer','regional_manager','manager'),'register_action':register_action is True,
                # A recipient may complete only their own routed import task.
                # That constrained action must not require broad write access.
                'complete_import_task':role in ('viewer','account_manager','editor','importer','regional_manager','manager','admin'),
                'import':role in ('account_manager','importer','manager'),'manage':role == 'manager','approve_changes':role == 'manager','appoint':False,'security_users':role == 'manager',
                'batch_assign':role in ('regional_manager','manager'),'supervise':role in ('regional_manager','manager'),'expires_on':expires,'expired':expired,
                'data_scope':scope,'regions':regions,'scope_company':scope_company,'scope_departments':scope_departments}
    except (ValueError, TypeError, AttributeError, OSError):
        return {'role':'disabled','read':False,'write':False,'register_action':False,'import':False,'manage':False,'appoint':False,'batch_assign':False,'supervise':False,'expires_on':'','expired':False,'data_scope':'self','regions':[]}


def crm_security_operation(path, method):
    if path == '/api/crm/action/add': return 'register_action'
    if path == '/api/crm/relations/batch-assign': return 'batch_assign'
    if path == '/api/crm/security/amap-settings': return 'read' if method in ('GET', 'HEAD') else 'manage'
    if path == '/api/crm/security/region-settings': return 'read' if method in ('GET', 'HEAD') else 'manage'
    if path == '/api/crm/security/quality-settings': return 'read' if method in ('GET', 'HEAD') else 'manage'
    if path == '/api/crm/security/appoint': return 'appoint'
    if path == '/api/crm/security/users': return 'security_users'
    # Operation traces are visible to every CRM user under their own data scope,
    # so viewing the audit trail only needs read access, not management rights.
    if path == '/api/crm/security/audit': return 'read'
    if path.startswith('/api/crm/security/') and path != '/api/crm/security/me':
        return 'manage'
    if path in ('/api/crm/excel/import','/api/crm/import-from-contract'):
        return 'import'
    if path in ('/api/crm/import-completion/complete', '/api/crm/import-completion/excel'):
        return 'complete_import_task'
    if method in ('GET','HEAD') or path == '/api/crm/battle-map/generate':
        return 'read'
    return 'write'


def crm_audit(actor, operation, path, status, target='', details=None, outcome=None):
    event = {'at':datetime.now().isoformat(timespec='seconds'),'actor':actor,'operation':operation,
             'path':path,'status':status,'target':target,'outcome':outcome or ('成功' if status < 400 else '拒绝或失败')}
    if details is not None: event['grant'] = details
    with CRM_SECURITY_LOCK:
        dest=crm_security_path('audit.jsonl'); dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(event,ensure_ascii=False)+'\n')


def crm_manager_directory(caller):
    caps = crm_capabilities(caller)
    if not (caps.get('read') and caps.get('data_scope') == 'all' and
            (caps.get('manage') or caps.get('appoint') or caller.get('role') == 'admin')):
        raise PermissionError('只有具备全量数据权限的管理员可以逐位查看客户经理大屏')
    managers = []
    for account in read_config().get('users', []):
        username = account.get('username', '')
        if not username:
            continue
        keys = list(dict.fromkeys(filter(None, [username, str(account.get('employee_id') or '').strip()])))
        managers.append({'username': username, 'name': account.get('name') or username,
                         'department': account.get('department', ''), 'member_keys': keys})
    return {'ok': True, 'managers': sorted(managers, key=lambda m: m['username'])}


def crm_security_users(caller):
    if not (crm_capabilities(caller)['manage'] or caller.get('role') == 'superadmin'): raise PermissionError('只有客户经营管理员或超级管理员可查看授权名单')
    policies=crm_security_policies()
    liaison_regions=crm_liaison_region_overrides()
    return {'ok':True,'roles':CRM_SECURITY_ROLES,'data_scopes':CRM_DATA_SCOPES,'users':[
        {'username':u['username'],'name':u.get('name') or u['username'],'employee_id':u.get('employee_id',''),
         'company':u.get('company',''),'department':u.get('department',''),'position':u.get('position',''),'superadmin':u.get('role')=='superadmin',
         'capabilities':crm_capabilities(u),'grant':policies.get(u['username']),'liaison_region_override':liaison_regions.get(u['username'],'')}
        for u in read_config().get('users',[])]}


def crm_security_grant(payload, caller, mode='grant'):
    if mode in ('appoint','delete'):
        if caller.get('role') != 'superadmin': raise PermissionError('只有超级管理员可指定或撤销客户经营管理员')
    elif not (crm_capabilities(caller)['manage'] or caller.get('role') == 'superadmin'):
        raise PermissionError('只有客户经营管理员或超级管理员可管理客户数据权限')
    username = str(payload.get('username','')).strip()
    role=payload.get('role'); expires=payload.get('expires_on') or ''
    regions = payload.get('regions', [])
    data_scope = payload.get('data_scope', 'regions' if regions else 'self')
    scope_company = str(payload.get('scope_company', '') or '').strip()[:200]
    scope_departments = payload.get('scope_departments', [])
    register_action = payload.get('register_action')
    if role not in CRM_SECURITY_ROLES: raise ValueError('请选择有效的权限角色')
    if register_action is not None and type(register_action) is not bool: raise ValueError('登记动作权限格式错误')
    if not isinstance(expires,str): raise ValueError('到期日格式错误')
    if not isinstance(regions, list) or any(not isinstance(item, str) or item not in CRM_BUSINESS_REGIONS for item in regions):
        raise ValueError('区域权限格式错误')
    if data_scope not in CRM_DATA_SCOPES: raise ValueError('数据范围无效')
    if role == 'regional_manager' and (data_scope != 'regions' or not regions):
        raise ValueError('区域管理员必须选择“指定区域”并至少授权一个区域')
    if data_scope == 'all' and caller.get('role') != 'superadmin': raise PermissionError('全量数据范围只能由超级管理员授权')
    if not isinstance(scope_departments, list) or any(not isinstance(item, str) for item in scope_departments): raise ValueError('组织范围格式错误')
    if data_scope == 'organization' and not scope_company: raise ValueError('请选择组织范围所属公司')
    if expires:
        try: parsed=datetime.strptime(expires,'%Y-%m-%d')
        except ValueError: raise ValueError('到期日须为YYYY-MM-DD')
        if parsed.strftime('%Y-%m-%d') != expires: raise ValueError('到期日须为YYYY-MM-DD')
    target=find_user(username)
    if not target: raise ValueError('账号不存在')
    if target.get('role')=='superadmin': raise ValueError('超级管理员权限由系统角色控制')
    with CRM_SECURITY_LOCK:
        policies=crm_security_policies()
        if mode == 'grant' and not (crm_capabilities(caller)['manage'] or caller.get('role') == 'superadmin'):
            raise PermissionError('客户经营管理员权限已撤销')
        previous = policies.get(username) or {}
        if mode == 'grant' and previous.get('manager') is True:
            raise PermissionError('客户经营管理员只能由超级管理员指定或撤销')
        if mode == 'appoint':
            if type(payload.get('manager')) is not bool: raise ValueError('请指定是否担任客户经营管理员')
            role = previous.get('role', crm_capabilities(target)['role'])
            expires = previous.get('expires_on','')
            data_scope = previous.get('data_scope', data_scope)
            scope_company = previous.get('scope_company', scope_company)
            scope_departments = previous.get('scope_departments', scope_departments)
            regions = previous.get('regions', regions)
            register_action = previous.get('register_action', register_action)
        if register_action is None:
            register_action = role in ('account_manager','editor','importer','regional_manager','manager')
        record={'manager':payload['manager'] if mode == 'appoint' else False,'role':role,'register_action':register_action,'expires_on':expires,'data_scope':data_scope,'scope_company':scope_company,'scope_departments':sorted(set(str(item).strip() for item in scope_departments if str(item).strip())),'regions':sorted(set(regions)),'updated_by':caller['username'],'updated_at':datetime.now().isoformat(timespec='seconds')}
        # Record the intended grant before committing, so audit failure cannot silently grant access.
        crm_audit(caller['username'],mode+'_requested','/api/crm/security/'+mode,200,username,record)
        policies[username]=record
        dest=crm_security_path('policies.json');dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(policies,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(dest)
        crm_audit(caller['username'],mode+'_applied','/api/crm/security/'+mode,200,username,record)
    return {'ok':True}


def crm_security_batch_grant(payload, caller):
    """Grant a CRM role and data scope to ordinary personnel in an organization node."""
    if not (crm_capabilities(caller)['manage'] or caller.get('role') == 'superadmin'):
        raise PermissionError('只有客户经营管理员或超级管理员可以批量管理客户数据权限')
    company = str(payload.get('company', '') or '').strip()
    departments = payload.get('departments', [])
    role = payload.get('role')
    expires = payload.get('expires_on') or ''
    # Batch grants act on a whole organization node, so only per-member data scopes
    # make sense here (each member sees their own or their own sub-tree). Aggregation
    # scopes (organization / regions / all) are configured per-leader in the dialog.
    data_scope = payload.get('data_scope', 'self') or 'self'
    register_action = payload.get('register_action')
    if not company:
        raise ValueError('请选择公司')
    if not isinstance(departments, list) or not all(isinstance(item, str) for item in departments):
        raise ValueError('部门选择格式无效')
    if role not in CRM_SECURITY_ROLES:
        raise ValueError('请选择有效权限等级')
    if register_action is not None and type(register_action) is not bool:
        raise ValueError('登记动作权限格式错误')
    if role == 'regional_manager':
        raise ValueError('区域管理员需逐人设置并明确指定负责区域')
    if data_scope not in ('self', 'team'):
        raise ValueError('批量授权仅支持“仅本人”或“本人及下属组织”数据范围')
    if not isinstance(expires, str):
        raise ValueError('到期日格式无效')
    if expires:
        try: parsed = datetime.strptime(expires, '%Y-%m-%d')
        except ValueError: raise ValueError('到期日须为YYYY-MM-DD')
        if parsed.strftime('%Y-%m-%d') != expires: raise ValueError('到期日须为YYYY-MM-DD')
    selected_departments = {item.strip() for item in departments if item.strip()}
    def in_selected_scope(department):
        """A selected organization node includes all of its descendant paths."""
        value = str(department or '').strip()
        return not selected_departments or any(
            value == scope or value.startswith(scope + ' / ')
            for scope in selected_departments
        )
    with CRM_SECURITY_LOCK:
        policies = crm_security_policies()
        targets = [
            user for user in read_config().get('users', [])
            if user.get('role') != 'superadmin'
            and not (policies.get(user.get('username', '')) or {}).get('manager')
            and str(user.get('company', '') or '').strip() == company
            and in_selected_scope(user.get('department', ''))
        ]
        if not targets:
            raise ValueError('所选组织范围内没有可配置的普通人员')
        if register_action is None:
            register_action = role in ('account_manager','editor','importer')
        record = {'manager': False, 'role': role, 'register_action': register_action, 'data_scope': data_scope, 'expires_on': expires, 'updated_by': caller['username'], 'updated_at': datetime.now().isoformat(timespec='seconds')}
        target_names = [user['username'] for user in targets]
        details = {**record, 'company': company, 'departments': sorted(selected_departments), 'count': len(target_names)}
        crm_audit(caller['username'], 'batch_grant_requested', '/api/crm/security/batch-grant', 200, ','.join(target_names), details)
        for target in targets:
            policies[target['username']] = dict(record)
        dest = crm_security_path('policies.json'); dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix('.tmp'); temp.write_text(json.dumps(policies, ensure_ascii=False, indent=2), encoding='utf-8'); temp.replace(dest)
        crm_audit(caller['username'], 'batch_grant_applied', '/api/crm/security/batch-grant', 200, ','.join(target_names), details)
    return {'ok': True, 'updated': len(target_names), 'role': role, 'data_scope': data_scope, 'expires_on': expires}


def crm_audit_actor_scope(user):
    """Usernames whose CRM operation traces `user` may see; None means全量可见。

    Customer data scope never expands operation-log visibility: ordinary users
    see only their own traces; customer-operation and super administrators see all.
    """
    caps = crm_capabilities(user)
    username = user.get('username', '')
    if not caps.get('read'):
        return set()
    if user.get('role') == 'superadmin' or caps.get('manage') or caps.get('role') == 'admin':
        return None
    return {username} if username else set()


def crm_security_audit(caller):
    caps = crm_capabilities(caller)
    if not caps.get('read'): raise PermissionError('无客户经营访问权限，无法查看操作留痕')
    scope = crm_audit_actor_scope(caller)  # None means全量
    username = caller.get('username', '')
    from collections import deque
    path=crm_security_path('audit.jsonl')
    if not path.exists(): return {'ok':True,'events':[],'scope':'all' if scope is None else 'limited'}
    # Scan a bounded window of recent history, then filter to the caller's scope.
    with CRM_SECURITY_LOCK, path.open(encoding='utf-8') as stream:
        lines=deque(stream,maxlen=5000)
    events=[]
    for line in reversed(lines):
        try: event=json.loads(line)
        except ValueError: continue
        if scope is not None:
            actor = event.get('actor', '')
            if actor not in scope:
                continue
        events.append(event)
        if len(events) >= 200:
            break
    return {'ok':True,'events':events,'scope':'all' if scope is None else 'limited'}
