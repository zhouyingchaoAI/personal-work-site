"""Shared account organization canvas. Account identities and grants are immutable here."""
import hashlib
import threading

INTERNAL_ORG_LOCK = threading.RLock()
INTERNAL_ORG_UNASSIGNED = 'own:unassigned'


def _internal_org_revision(config):
    relevant = {'nodes': config.get('internal_organization', {}), 'users': [
        {key: u.get(key, '') for key in ('username', 'name', 'employee_id', 'company', 'department', 'position')}
        for u in config.get('users', [])]}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _internal_org_paths(nodes):
    by_id = {n['id']: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ValueError('组织节点标识重复')
    paths = {}
    for node in nodes:
        chain, seen, cursor = [], set(), node
        while cursor:
            if cursor['id'] in seen:
                raise ValueError('组织层级不能形成循环')
            seen.add(cursor['id']); chain.append(cursor)
            parent = cursor['parent_id']
            if parent and parent not in by_id:
                raise ValueError('上级组织不存在')
            cursor = by_id.get(parent)
        chain.reverse()
        company = '' if chain[0]['id'] == INTERNAL_ORG_UNASSIGNED else chain[0]['name']
        department = ' / '.join(n['name'] for n in chain[1:])
        if len(company) > 200 or len(department) > 500:
            raise ValueError('公司或完整部门路径过长')
        path = (company, department)
        if path in paths.values():
            raise ValueError('同一上级下不能有同名组织')
        paths[node['id']] = path
    return paths


def _internal_org_snapshot(config):
    nodes = [dict(n) for n in config.get('internal_organization', {}).get('nodes', [])]
    paths = _internal_org_paths(nodes)
    by_path = {path: ident for ident, path in paths.items()}

    def ensure(company, departments):
        parent = ''
        for index in range(len(departments) + 1):
            path = (company, ' / '.join(departments[:index]))
            ident = by_path.get(path)
            if not ident:
                ident = (INTERNAL_ORG_UNASSIGNED if not company and index == 0 else
                         'own:' + hashlib.sha256(json.dumps(path, ensure_ascii=False).encode()).hexdigest()[:24])
                nodes.append({'id': ident, 'name': (company or '未分配公司') if index == 0 else departments[index-1], 'parent_id': parent})
                by_path[path] = ident
            parent = ident
        return parent

    members = []
    for entry in config.get('organization_roster', []):
        ensure(str(entry.get('company') or '').strip(),
               [p.strip() for p in str(entry.get('department') or '').split('/') if p.strip()])
    for user in config.get('users', []):
        company = str(user.get('company') or '').strip()
        departments = [p.strip() for p in str(user.get('department') or '').split('/') if p.strip()]
        members.append({'username': user['username'], 'name': user.get('name') or user['username'],
                        'employee_id': user.get('employee_id') or '', 'position': user.get('position') or '',
                        'node_id': ensure(company, departments),
                        'node_ids': config.get('internal_organization', {}).get('memberships', {}).get(user['username'], [])})
    return {'ok': True, 'revision': _internal_org_revision(config), 'nodes': nodes, 'members': members}


def internal_organization_get(caller_username):
    if _caller_role(caller_username) != 'superadmin':
        raise PermissionError('只有超级管理员可以调整正式账号组织架构')
    return _internal_org_snapshot(read_config())


def internal_organization_save(payload, caller_username):
    if _caller_role(caller_username) != 'superadmin':
        raise PermissionError('只有超级管理员可以调整正式账号组织架构')
    with INTERNAL_ORG_LOCK:
        config = read_config()
        if payload.get('revision') != _internal_org_revision(config):
            raise ValueError('组织或用户资料已更新，请关闭画布后重新打开再调整')
        raw_nodes, assignments = payload.get('nodes'), payload.get('assignments')
        if not isinstance(raw_nodes, list) or len(raw_nodes) > 3000 or not isinstance(assignments, dict):
            raise ValueError('组织结构格式不正确或节点过多')
        nodes = []
        for raw in raw_nodes:
            if not isinstance(raw, dict):
                raise ValueError('组织节点格式不正确')
            ident, name, parent = (raw.get(k) for k in ('id', 'name', 'parent_id'))
            if (not all(isinstance(v, str) for v in (ident, name, parent)) or
                    not ident.startswith('own:') or len(ident) > 100 or not name.strip() or
                    len(name.strip()) > 200 or '/' in name):
                raise ValueError('节点名称不能为空、不能包含 /，且最长 200 字')
            if ident == INTERNAL_ORG_UNASSIGNED and (parent or name != '未分配公司'):
                raise ValueError('未分配公司节点不能改名或移动，请将人员匹配到正式公司')
            nodes.append({'id': ident, 'name': name.strip(), 'parent_id': parent})
        paths = _internal_org_paths(nodes)
        users = config.get('users', [])
        if set(assignments) != {u['username'] for u in users}:
            raise ValueError('必须保留全部账号的人员匹配，不能删除或新增账号')
        if any(not isinstance(target, str) or target not in paths for target in assignments.values()):
            raise ValueError('人员匹配的目标组织不存在')
        memberships = payload.get('memberships', config.get('internal_organization', {}).get('memberships', {}))
        if not isinstance(memberships, dict) or set(memberships) - set(assignments):
            raise ValueError('兼任人员必须为已有账号')
        normalized = {}
        for username, targets in memberships.items():
            if not isinstance(targets, list) or len(targets) > 100 or any(not isinstance(target, str) or target not in paths or target == INTERNAL_ORG_UNASSIGNED for target in targets):
                raise ValueError('兼任组织无效，最多支持100个正式组织')
            normalized[username] = list(dict.fromkeys(target for target in targets if target != assignments[username]))
        affected = set(config.get('internal_organization', {}).get('managed_users', []))
        changed = 0
        for user in users:
            company, department = paths[assignments[user['username']]]
            old_department = ' / '.join(p.strip() for p in str(user.get('department') or '').split('/') if p.strip())
            if company != str(user.get('company') or '').strip() or department != old_department:
                user['company'], user['department'] = company, department
                affected.add(user['username']); changed += 1
        config['internal_organization'] = {'nodes': nodes, 'managed_users': sorted(affected), 'memberships': normalized}
        # All account fields not explicitly assigned above, including permission grants,
        # passwords, roles, employee IDs and positions, remain untouched.
        write_config(config)
        result = _internal_org_snapshot(config)
        result['updated_members'] = changed
        return result


def internal_organization_staff(records):
    """Resolve canvas-managed account fields at read time, without copying identities.

    This covers global directory AND personal CRM overlays, with no partial multi-file
    update. Unlinked/external staff and accounts never moved in the canvas are untouched.
    """
    config = read_config()
    managed = set(config.get('internal_organization', {}).get('managed_users', []))
    memberships = config.get('internal_organization', {}).get('memberships', {})
    paths = _internal_org_paths(config.get('internal_organization', {}).get('nodes', []))
    aliases = {}
    for user in config.get('users', []):
        if user.get('username') in managed or memberships.get(user.get('username')):
            for key in (user.get('username'), user.get('employee_id')):
                if key:
                    aliases[str(key)] = user
    return {ident: dict(record, company=aliases[str(record.get('member_key'))].get('company', ''),
                        department=aliases[str(record.get('member_key'))].get('department', ''),
                        organization_memberships=[{'company': paths[target][0], 'department': paths[target][1]}
                            for target in memberships.get(aliases[str(record.get('member_key'))]['username'], []) if target in paths])
            if str(record.get('member_key')) in aliases else record for ident, record in records.items()}
