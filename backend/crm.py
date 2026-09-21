CRM_SUPPORT_LABELS = ('反对', '中立', '支持', '积极支持')
CRM_SUPPORT_LEGACY = {'-1':'反对', '0':'中立', '1':'支持', '2':'积极支持'}


def crm_support_label(value):
    text = '' if value is None else str(value).strip()
    return CRM_SUPPORT_LEGACY.get(text, text)

CRM_BUSINESS_REGIONS = ("东区", "西区", "中区", "广东区")

"""客户经营助手：五层关系资产建模、强度评分、衰减预警与作战地图。

沿用平台"每用户 JSON 存储 + path 分发"范式。所有数据落在
``user_data/<username>/crm/<collection>.json``，按登录用户物理隔离；
API 不接受客户端指定归属用户。Neo4j 承载图投影，Redis/Celery 提供缓存与异步同步。
"""

CRM_LOCK = threading.RLock()
import copy as crm_copy
import hashlib as crm_hashlib
from collections import OrderedDict as CrmOrderedDict
CRM_SNAPSHOT_CACHE = CrmOrderedDict()
CRM_SNAPSHOT_CACHE_LOCK = threading.RLock()


def _crm_snapshot_fingerprint(user):
    config = read_config()
    stamps = []
    paths = [Path(USER_DATA_DIR) / '_crm_staff_directory.json']
    for account in config.get('users', []):
        username = account.get('username', '')
        if username and safe_username(username) == username:
            paths.extend(Path(USER_DATA_DIR) / username / 'crm' / (name + '.json') for name in CRM_COLLECTIONS)
    for path in paths:
        try:
            stat = path.stat()
            stamps.append((str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        except FileNotFoundError:
            stamps.append((str(path), None))
    return (crm_hashlib.sha256(json.dumps([user, config, crm_capabilities(user)], sort_keys=True, ensure_ascii=False).encode()).digest(), tuple(stamps))


def crm_read_snapshot(user, collections=None):
    def isolated(value):
        # Copy only what this endpoint consumes; never expose cached objects.
        return crm_copy.deepcopy(value if collections is None else {name: value[name] for name in collections})
    # Check live grants before every hit. No shared result objects escape the cache.
    if not crm_capabilities(user).get('read'):
        return isolated(_crm_build_snapshot(user))
    key = (str(Path(USER_DATA_DIR).resolve()), user.get('username', ''))
    with CRM_SNAPSHOT_CACHE_LOCK:
        signature = _crm_snapshot_fingerprint(user)
        entry = CRM_SNAPSHOT_CACHE.get(key)
        now = time.monotonic()
        if entry and entry[0] == signature and now - entry[1] < 10:
            CRM_SNAPSHOT_CACHE.move_to_end(key)
            return isolated(entry[2])
        result = _crm_build_snapshot(user)
        # External writers (including imports in worker processes) need no
        # invalidation call: inode/mtime/ctime changes invalidate the next read.
        if signature == _crm_snapshot_fingerprint(user):
            CRM_SNAPSHOT_CACHE[key] = (signature, time.monotonic(), result)
            CRM_SNAPSHOT_CACHE.move_to_end(key)
            while len(CRM_SNAPSHOT_CACHE) > 4:
                CRM_SNAPSHOT_CACHE.popitem(last=False)
        return isolated(result)

from backend import crm_amap
from backend import crm_quality


def crm_quality_settings(caller):
    if not crm_capabilities(caller).get('read'):
        raise PermissionError('无客户经营查看权限')
    with CRM_LOCK:
        path = USER_DATA_DIR / '.crm-quality-settings.json'
        value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
            'rules': crm_copy.deepcopy(crm_quality.DEFAULT_RULES), 'version': 0,
            'updated_at': '', 'updated_by': '',
        }
        # Add new personal-model defaults in memory only; preserve existing company rules/version.
        for key in ('personal_weights', 'personal_min_dimensions', 'personal_maintenance_days'):
            value['rules'].setdefault(key, crm_copy.deepcopy(crm_quality.DEFAULT_RULES[key]))
        crm_quality.validate_rules(value['rules'])
        return {'ok': True, **value, 'defaults': crm_copy.deepcopy(crm_quality.DEFAULT_RULES), 'roles': list(crm_quality.ROLES)}


def crm_quality_settings_save(payload, caller):
    caps = crm_capabilities(caller)
    if not (caps.get('manage') or caps.get('appoint')):
        raise PermissionError('只有客户经营管理员或超级管理员可编辑评估规则')
    rules = crm_quality.validate_rules(payload.get('rules'))
    with CRM_LOCK:
        previous = crm_quality_settings(caller)
        if type(payload.get('version')) is not int or payload['version'] != previous['version']:
            raise ValueError('评估规则已被其他人更新，请重新加载后编辑')
        result = {'rules': rules, 'version': previous['version'] + 1,
                  'updated_at': crm_now(), 'updated_by': caller['username']}
        details = {'before': previous['rules'], 'after': rules, 'version': result['version']}
        crm_audit(caller['username'], 'quality_rules_requested', '/api/crm/security/quality-settings', 200, '', details)
        path = USER_DATA_DIR / '.crm-quality-settings.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        crm_audit(caller['username'], 'quality_rules_applied', '/api/crm/security/quality-settings', 200, '', details)
        return crm_quality_settings(caller)

def crm_amap_settings():
    with CRM_LOCK:
        return crm_amap.public_settings(USER_DATA_DIR)

def crm_amap_settings_save(payload, caller):
    caps = crm_capabilities(caller)
    if not (caps.get('manage') or caps.get('appoint')):
        raise PermissionError('只有客户经营管理员或超级管理员可编辑地图配置')
    with CRM_LOCK:
        return crm_amap.save_settings(USER_DATA_DIR, payload)

CRM_STANDARD_REGIONS = {
    '东区': ['浙江', '江苏', '上海'],
    '中区': ['北京', '天津', '河北', '湖北', '河南', '山东', '安徽'],
    '西区': ['湖南', '四川', '重庆', '陕西'],
    '广东区': ['广东', '湖南'],
}
CRM_STANDARD_PROVINCES = '北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏 陕西 甘肃 青海 宁夏 新疆 台湾 香港 澳门'.split()


def crm_region_settings():
    path = USER_DATA_DIR / '.crm-region-settings.json'
    with CRM_LOCK:
        catalog = json.loads((APP_ROOT / 'backend' / 'crm_region_cities.json').read_text(encoding='utf-8'))
        empty_cities = {name: [] for name in CRM_STANDARD_REGIONS}
        if path.exists():
            return {'ok': True, 'cities': empty_cities, **json.loads(path.read_text(encoding='utf-8')), 'city_options': catalog}
        return {'ok': True, 'regions': {k: list(v) for k, v in CRM_STANDARD_REGIONS.items()},
                'cities': empty_cities, 'city_options': catalog,
                'version': 0, 'updated_at': '', 'updated_by': ''}


def crm_region_settings_save(payload, caller):
    caps = crm_capabilities(caller)
    if not (caps.get('manage') or caps.get('appoint')):
        raise PermissionError('只有客户经营管理员或超级管理员可编辑标准区域')
    regions = payload.get('regions')
    if not isinstance(regions, dict) or set(regions) != set(CRM_STANDARD_REGIONS):
        raise ValueError('请完整提交东区、中区、西区和广东区的省份配置')
    cleaned = {}
    for name, provinces in regions.items():
        if not isinstance(provinces, list) or any(not isinstance(p, str) or p not in CRM_STANDARD_PROVINCES for p in provinces):
            raise ValueError('请选择有效的省份')
        cleaned[name] = list(dict.fromkeys(provinces))
    with CRM_LOCK:
        previous = crm_region_settings()
        if type(payload.get('version')) is not int or payload['version'] != previous['version']:
            raise ValueError('区域设置已被其他人更新，请重新加载后编辑')
        cities = payload.get('cities', previous['cities'])
        if not isinstance(cities, dict) or set(cities) != set(CRM_STANDARD_REGIONS):
            raise ValueError('请完整提交四个区域的城市绑定')
        cleaned_cities = {}
        for name, bindings in cities.items():
            if not isinstance(bindings, list) or len(bindings) > 1000:
                raise ValueError('城市绑定格式无效')
            cleaned_cities[name] = []
            for binding in bindings:
                if not isinstance(binding, dict):
                    raise ValueError('城市绑定格式无效')
                province, city = binding.get('province'), binding.get('city')
                if not isinstance(province, str) or not isinstance(city, str) or city not in previous['city_options'].get(province, []):
                    raise ValueError('城市与省份不匹配，请从城市列表选择')
                item = {'province': province, 'city': city}
                if item not in cleaned_cities[name]: cleaned_cities[name].append(item)
        result = {'regions': cleaned, 'cities': cleaned_cities, 'version': previous['version'] + 1,
                  'updated_at': crm_now(), 'updated_by': caller['username']}
        path = USER_DATA_DIR / '.crm-region-settings.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        return {'ok': True, **result, 'city_options': previous['city_options']}

# 单位类型（客户经营五类参与主体）
CRM_UNIT_TYPES = ["主管单位", "业主单位", "总包单位", "设计单位", "厂商"]
# 决策链节点（项目阶段），热力图七列
CRM_DECISION_NODES = ["立项", "设计", "招标", "定标", "履约", "联调试运行", "验收", "初期运营", "付款"]
# 关系强度六级
CRM_STRENGTH_LEVELS = {
    0: "未接触", 1: "认识", 2: "可对话", 3: "可信任", 4: "可协同", 5: "关键盟友",
}
# 决策角色
CRM_DECISION_ROLES = ["定标", "定技术", "签验收", "批付款", "影响者", "需求提出", "采购经办", "运营接管", "安全评估协调"]
# 按层级设定的衰减阈值（天）：预警 / 告警
CRM_DECAY_THRESHOLDS = {"高层": (90, 180), "中层": (45, 90), "基层": (21, 45)}
CRM_COLLECTIONS = ("units", "people", "relations", "actions", "links", "staff", "opportunities")


def crm_unit_regions(unit):
    """Return a unit's normalized multi-region membership, including legacy data."""
    values = unit.get('business_regions', []) if isinstance(unit, dict) else []
    if not isinstance(values, list):
        values = []
    regions = []
    for value in values:
        region = crm_text(value, 40)
        if region in CRM_BUSINESS_REGIONS and region not in regions:
            regions.append(region)
    legacy = crm_text(unit.get('business_region', ''), 40) if isinstance(unit, dict) else ''
    if legacy in CRM_BUSINESS_REGIONS and legacy not in regions:
        regions.insert(0, legacy)
    return regions


def crm_normalize_unit_regions(values):
    if not isinstance(values, list):
        return None
    regions = []
    for value in values:
        region = crm_text(value, 40)
        if region not in CRM_BUSINESS_REGIONS:
            raise ValueError('经营区域请选择东区、西区、中区或广东区')
        if region not in regions:
            regions.append(region)
    return regions


def crm_directory(username):
    if not isinstance(username, str) or not username or safe_username(username) != username:
        raise PermissionError("无效用户身份")
    directory = user_root(username) / "crm"
    if directory.exists() and directory.resolve() != (USER_DATA_DIR / username / "crm").resolve():
        raise PermissionError("用户目录不可用")
    return directory


def crm_collection_path(username, collection):
    if collection not in CRM_COLLECTIONS:
        raise ValueError("未知数据集")
    return crm_directory(username) / f"{collection}.json"


# Collections rewritten row-by-row during a bulk Excel import. Reading and
# rewriting the whole JSON file on every row is O(n^2) and times out large
# imports, so these are held in memory during a batch and flushed once at the end.
CRM_BATCH_COLLECTIONS = {'units', 'people', 'relations', 'actions', 'links'}


def _crm_read_collection(source):
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _crm_import_batch():
    context = globals().get("CRM_IMPORT_CONTEXT")
    return getattr(context, "batch", None) if context is not None else None


def crm_load(username, collection):
    path = crm_collection_path(username, collection)
    batch = _crm_import_batch()
    if batch is not None and collection in CRM_BATCH_COLLECTIONS:
        key = (username, collection)
        if key not in batch['data']:
            # Two independent parses: one live working set, one untouched
            # pre-import snapshot used for change history at flush time.
            batch['data'][key] = _crm_read_collection(path)
            batch['original'][key] = _crm_read_collection(path)
        return batch['data'][key]
    data = _crm_read_collection(path)
    if collection == 'staff':
        directory = _crm_read_collection(Path(USER_DATA_DIR) / '_crm_staff_directory.json')
        # Personal edits take precedence; never replace an existing staff identity.
        existing_keys = {r.get('member_key') for r in data.values()}
        directory = {k:v for k,v in directory.items() if v.get('member_key') not in existing_keys}
        data = {**directory, **data}
        data = internal_organization_staff(data)
    return data


def _crm_store_disk(username, collection, records, previous=None):
    path = crm_collection_path(username, collection)
    path.parent.mkdir(parents=True, exist_ok=True)
    if previous is None:
        previous = _crm_read_collection(path) if path.exists() else {}
    if isinstance(previous, dict):
        changes = [
            {'at': crm_now(), 'collection': collection, 'record_id': record_id, 'record': old}
            for record_id, old in previous.items()
            if records.get(record_id) != old
        ]
        if changes:
            history = crm_directory(username) / 'history'
            history.mkdir(parents=True, exist_ok=True)
            with (history / f'{collection}.jsonl').open('a', encoding='utf-8') as stream:
                for change in changes: stream.write(json.dumps(change, ensure_ascii=False) + '\n')
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def crm_store(username, collection, records):
    batch = _crm_import_batch()
    if batch is not None and collection in CRM_BATCH_COLLECTIONS:
        key = (username, collection)
        if key not in batch['original']:
            batch['original'][key] = _crm_read_collection(crm_collection_path(username, collection))
        batch['data'][key] = records
        batch['dirty'].add(key)
        return
    _crm_store_disk(username, collection, records)


def crm_flush_import_batch():
    """Persist all collections mutated during a bulk import in one write each."""
    batch = _crm_import_batch()
    if not batch:
        return
    for key in list(batch['dirty']):
        username, collection = key
        _crm_store_disk(username, collection, batch['data'][key], batch['original'].get(key, {}))
    batch['dirty'].clear()


def crm_record_versions(username, collection, record_id):
    if collection not in CRM_COLLECTIONS: raise ValueError('未知数据集')
    path = crm_directory(username) / 'history' / f'{collection}.jsonl'
    if not path.exists(): return []
    rows = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            try:
                item = json.loads(line)
                if item.get('record_id') == record_id: rows.append(item)
            except ValueError: continue
    return list(reversed(rows[-50:]))


def crm_bulk_update(payload, username):
    collection = crm_text(payload.get('collection'))
    ids = payload.get('ids', [])
    changes = payload.get('changes', {})
    allowed = {
        'units': {'business_region', 'region', 'type', 'source'},
        'people': {'department', 'title', 'importance', 'support_level', 'maintenance_days'},
        'relations': {'our_member', 'source'},
    }
    if collection not in allowed or not isinstance(ids, list) or not ids or not isinstance(changes, dict):
        raise ValueError('批量修改参数无效')
    if any(not isinstance(item, str) for item in ids) or any(key not in allowed[collection] for key in changes):
        raise ValueError('不支持修改该字段')
    rows = crm_load(username, collection)
    changed = 0
    for record_id in ids:
        record = rows.get(record_id)
        if not record: continue
        for key, value in changes.items():
            if key == 'business_region' and value and value not in CRM_BUSINESS_REGIONS: raise ValueError('经营区域无效')
            if key == 'type' and value and value not in CRM_UNIT_TYPES: raise ValueError('单位类型无效')
            if key == 'importance' and value not in ('', '重要', '一般'): raise ValueError('重要程度无效')
            if key == 'support_level' and crm_support_label(value) not in ('', *CRM_SUPPORT_LABELS): raise ValueError('支持程度无效')
            if key == 'business_region':
                record['business_region'] = value
                record['business_regions'] = [value] if value else []
            else:
                record[key] = crm_support_label(value) if key == 'support_level' else value
        record['updated_at'] = crm_now(); record['version'] = int(record.get('version', 0)) + 1
        changed += 1
    if changed:
        crm_store(username, collection, rows)
        crm_on_change(username)
    return {'ok': True, 'updated': changed}


def _crm_unique_account_identity(value):
    """Resolve a login, employee ID, or display name without guessing duplicates."""
    identity = crm_text(value, 80)
    if not identity:
        return None
    matches = [user for user in read_config().get('users', []) if identity in {
        crm_text(user.get('username'), 80),
        crm_text(user.get('employee_id'), 80),
        crm_text(user.get('name'), 80),
    }]
    return matches[0] if len(matches) == 1 else None


def crm_relation_batch_assign(payload, caller):
    """Region-scoped assignment, including safe handover of unfinished plans."""
    caps = crm_capabilities(caller or {})
    if not caps.get('batch_assign'):
        raise PermissionError('只有客户经营管理员或区域管理员可以批量指派客情关系')
    relation_ids = (payload or {}).get('relation_ids', [])
    if (not isinstance(relation_ids, list) or not relation_ids or len(relation_ids) > 500 or
            any(not isinstance(item, str) or not crm_text(item, 120) for item in relation_ids)):
        raise ValueError('请选择1至500条需要指派的客情关系')
    relation_ids = list(dict.fromkeys(crm_text(item, 120) for item in relation_ids))
    changes_assignment = 'our_member' in (payload or {}) and bool(crm_text((payload or {}).get('our_member'), 80))
    target = _crm_unique_account_identity((payload or {}).get('our_member')) if changes_assignment else None
    if changes_assignment and not target:
        raise ValueError('我方对接人员无法唯一匹配，请使用账号或工号')
    target_key = crm_text((target or {}).get('employee_id') or (target or {}).get('username'), 80)
    transfer = bool((payload or {}).get('transfer'))
    if transfer and not changes_assignment:
        raise ValueError('关系转移必须选择新的客户对接人')
    supervision = (payload or {}).get('supervision') or {}
    if not isinstance(supervision, dict):
        raise ValueError('维系监督配置格式无效')
    next_step = crm_text(supervision.get('next_step'), 1000)
    due_date = crm_text(supervision.get('due_date'), 20)
    if due_date:
        try:
            parsed = datetime.strptime(due_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError('监督截止日期格式应为 YYYY-MM-DD')
        if parsed.strftime('%Y-%m-%d') != due_date:
            raise ValueError('监督截止日期格式应为 YYYY-MM-DD')
    if not changes_assignment and not next_step:
        raise ValueError('请设置我方对接人员或填写维系监督要求')
    supervisor = _crm_unique_account_identity(supervision.get('supervisor')) if supervision.get('supervisor') else (caller or {})
    if next_step and not supervisor:
        raise ValueError('监督人无法唯一匹配，请使用账号或工号')
    supervisor_key = crm_text((supervisor or {}).get('employee_id') or (supervisor or {}).get('username'), 80)

    snapshot = crm_read_snapshot(caller or {})
    by_id = {}
    for relation in snapshot['relations']:
        by_id.setdefault(relation.get('id'), []).append(relation)
    selected = []
    for relation_id in relation_ids:
        matches = by_id.get(relation_id, [])
        if len(matches) != 1:
            raise PermissionError('所选关系不存在、重复或不在当前授权范围，请刷新后重试')
        selected.append(matches[0])
    if next_step and not target_key and any(not crm_text(item.get('our_member'), 80) for item in selected):
        raise ValueError('未指派关系需先选择我方对接人员，才能配置维系监督')
    full_access = bool(caps.get('manage') or caps.get('appoint') or (caller or {}).get('role') == 'superadmin')
    if not full_access:
        allowed_regions = set(caps.get('regions', []))
        units = {(item.get('_owner'), item.get('id')): item for item in snapshot['units']}
        people = {(item.get('_owner'), item.get('id')): item for item in snapshot['people']}
        for relation in selected:
            owner = relation.get('_owner', '')
            person = people.get((owner, relation.get('person_id')), {})
            unit = units.get((owner, person.get('unit_id')), {})
            if not (set(crm_unit_regions(unit)) & allowed_regions):
                raise PermissionError('批量指派包含非授权区域关系，整批操作已取消')

    details = {'relations': relation_ids, 'count': len(selected), 'our_member': target_key, 'transfer': transfer,
               'supervision': {'next_step': next_step, 'due_date': due_date, 'supervisor': supervisor_key} if next_step else {}}
    crm_audit((caller or {}).get('username', ''), 'batch_assign_requested', '/api/crm/relations/batch-assign', 200, target_key, details)
    plans_created = 0
    plans_transferred = 0
    with CRM_LOCK:
        owners = {}
        for relation in selected:
            owner = relation.get('_owner', '')
            owners.setdefault(owner, {'relations': crm_load(owner, 'relations'), 'actions': crm_load(owner, 'actions'), 'ids': []})
            rows = owners[owner]
            stored = rows['relations'].get(relation['id'])
            if not stored:
                raise PermissionError('关系数据已变化，整批操作已取消，请刷新后重试')
            rows['ids'].append(relation['id'])
        for owner, rows in owners.items():
            for relation_id in rows['ids']:
                relation = rows['relations'][relation_id]
                if changes_assignment:
                    previous_member = crm_text(relation.get('our_member'), 80)
                    relation['our_member'] = target_key
                    relation['updated_at'] = crm_now()
                    relation['version'] = int(relation.get('version', 0)) + 1
                    # Handover moves only unfinished future plans.  Historical
                    # interaction ownership is preserved as evidence of who did it.
                    if transfer:
                        for action in rows['actions'].values():
                            if (action.get('relation_id') == relation_id and action.get('record_kind') == 'plan'
                                    and not action.get('completed_at') and crm_text(action.get('owner'), 80) in ('', previous_member)):
                                action['owner'] = target_key
                                action['updated_at'] = crm_now()
                                plans_transferred += 1
                if next_step:
                    action_id = crm_new_id('act')
                    rows['actions'][action_id] = {
                        'id': action_id, 'relation_id': relation_id, 'type': '维系监督',
                        'record_kind': 'plan', 'level': '', 'intel': '', 'cost': '',
                        'effective': False, 'bidirectional': False, 'decision_node': '',
                        'happened_at': '', 'next_step': next_step,
                        'owner': target_key or crm_text(relation.get('our_member'), 80),
                        'supervisor': supervisor_key, 'project_id': '', 'due_date': due_date,
                        'created_by': (caller or {}).get('username', ''), 'created_at': crm_now(),
                    }
                    plans_created += 1
            if changes_assignment:
                crm_store(owner, 'relations', rows['relations'])
            if next_step or transfer:
                crm_store(owner, 'actions', rows['actions'])
            crm_on_change(owner)
    crm_audit((caller or {}).get('username', ''), 'batch_assign_applied', '/api/crm/relations/batch-assign', 200, target_key, details)
    return {'ok': True, 'updated': len(selected) if changes_assignment else 0,
            'plans_created': plans_created, 'plans_transferred': plans_transferred,
            'our_member': target_key, 'supervisor': supervisor_key}


def crm_migrate_account_autofill_our_member(username):
    """Heal relations where the old importer auto-filled 我方对接人 with the account.

    Before blank 我方对接人 was supported, imports stamped every relation with the
    uploader's own account (e.g. 'zhouyingchao'). Re-uploading after the fix then
    created duplicate blank ('待指派') relations. This one-time, idempotent cleanup:
      * only touches relations whose our_member == the owner's own account name AND
        where that name is not a real staff member_key (i.e. genuine auto-fill);
      * if a blank counterpart exists for the same person, merges the auto-filled
        relation's actions/links into it (dropping exact-duplicate actions) and drops
        the auto-filled relation;
      * otherwise just clears our_member to blank (converts to 待指派).
    """
    staff_keys = {s.get('member_key') for s in crm_load(username, 'staff').values()}
    if username in staff_keys:
        return {'ok': True, 'cleared': 0, 'removed': 0}  # account is a real member; leave as-is
    relations = crm_load(username, 'relations')
    if not any(r.get('our_member') == username for r in relations.values()):
        return {'ok': True, 'cleared': 0, 'removed': 0}
    actions = crm_load(username, 'actions')
    links = crm_load(username, 'links')
    by_person = {}
    for rid, record in relations.items():
        by_person.setdefault(record.get('person_id'), []).append(rid)
    def action_signature(action):
        return tuple(action.get(key, '') for key in ('type', 'happened_at', 'next_step', 'record_kind', 'intel', 'due_date'))
    cleared = 0
    removed_relations = set()
    for pid, rids in by_person.items():
        account_rids = [rid for rid in rids if relations[rid].get('our_member') == username]
        blank_rids = [rid for rid in rids if relations[rid].get('our_member') == '']
        if not account_rids:
            continue
        if blank_rids:
            survivor = blank_rids[0]
            survivor_sigs = {action_signature(a) for a in actions.values() if a.get('relation_id') == survivor}
            for rid in account_rids:
                for aid, action in list(actions.items()):
                    if action.get('relation_id') != rid:
                        continue
                    if action_signature(action) in survivor_sigs:
                        actions.pop(aid, None)  # exact duplicate already on the survivor
                    else:
                        action['relation_id'] = survivor  # keep unique history on the survivor
                        survivor_sigs.add(action_signature(action))
                for lid, link in links.items():
                    if link.get('relation_id') == rid:
                        link['relation_id'] = survivor
                removed_relations.add(rid)
        else:
            for rid in account_rids:
                relations[rid]['our_member'] = ''
                relations[rid]['updated_at'] = crm_now()
                relations[rid]['version'] = int(relations[rid].get('version', 0)) + 1
                cleared += 1
    for rid in removed_relations:
        relations.pop(rid, None)
    if cleared or removed_relations:
        if removed_relations:
            crm_store(username, 'actions', actions)
            crm_store(username, 'links', links)
        crm_store(username, 'relations', relations)
        # Recompute survivors so strength/decay reflect the merged action set.
        for rid in list(relations):
            crm_recompute_relation(username, rid)
    return {'ok': True, 'cleared': cleared, 'removed': len(removed_relations)}


def crm_now():
    return datetime.now().isoformat(timespec="seconds")


def crm_new_id(prefix):
    return f"{prefix}-{secrets.token_hex(8)}"


def crm_text(value, limit=500):
    return str(value or "").strip()[:limit]


def crm_id_owned_by_another(username, collection, record_id):
    """Cross-region views are read-only for records owned by another account."""
    if not record_id:
        return False
    for account in read_config().get('users', []):
        owner = account.get('username', '')
        if owner and owner != username and record_id in crm_load(owner, collection):
            return True
    return False


def crm_days_since(iso_date):
    """给定 ISO 日期/时间字符串，返回距今天数；无效返回 None。"""
    raw = str(iso_date or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return max(0, (datetime.now() - parsed).days)


# ---------------------------------------------------------------------------
# 单位层 / 人物层：建档
# ---------------------------------------------------------------------------

def crm_validate_parent(records, record_id, parent_id, field):
    if not parent_id:
        return
    if parent_id not in records:
        raise ValueError("上级不存在或不属于当前账号")
    seen = {record_id}
    cursor = parent_id
    while cursor:
        if cursor in seen:
            raise ValueError("不能把自身或下级设为上级，组织关系不能形成循环")
        seen.add(cursor)
        cursor = records.get(cursor, {}).get(field, "")


def crm_unit_save(payload, username):
    with CRM_LOCK:
        units = crm_load(username, "units")
        unit_id = crm_text(payload.get("id"))
        if crm_id_owned_by_another(username, 'units', unit_id):
            return {"ok": False, "error": "这是其他账号上传的客户资料，仅可查看"}
        now = crm_now()
        if unit_id and unit_id in units:
            record = units[unit_id]
            if int(payload.get("version", record.get("version", 1))) != int(record.get("version", 1)):
                return {"ok": False, "error": "单位已被更新，请刷新后重试"}
        else:
            unit_id = crm_new_id("unit")
            record = {"id": unit_id, "created_at": now, "version": 0}
        business_region = crm_text(payload.get("business_region", record.get("business_region", "")))
        if business_region and business_region not in CRM_BUSINESS_REGIONS:
            return {"ok": False, "error": "经营区域请选择东区、西区、中区或广东区"}
        try:
            business_regions = crm_normalize_unit_regions(payload.get('business_regions'))
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if business_regions is None:
            business_regions = [business_region] if business_region else []
        if business_region and business_region not in business_regions:
            business_regions.insert(0, business_region)
        business_region = business_regions[0] if business_regions else ''
        parent_id = crm_text(payload.get("parent_unit_id", record.get("parent_unit_id", "")))
        try:
            crm_validate_parent(units, unit_id, parent_id, "parent_unit_id")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        organization_level = crm_text(payload.get("organization_level", record.get("organization_level", "")), 24)
        if organization_level and organization_level not in ('company', 'subsidiary', 'unit'):
            return {"ok": False, "error": "组织层级仅可为公司全称、子公司全称或单位"}
        parent = units.get(parent_id, {}) if parent_id else {}
        if organization_level == 'company' and parent_id:
            return {"ok": False, "error": "公司全称为最高级组织，不能设置上级"}
        if organization_level in ('subsidiary', 'unit') and not parent_id:
            return {"ok": False, "error": "请选择已建档的上级组织"}
        record["parent_unit_id"] = parent_id
        unit_type = crm_text(payload.get("type"))
        record.update({
            "name": crm_text(payload.get("name")),
            "type": unit_type if unit_type in CRM_UNIT_TYPES else "",
            "region": crm_text(payload.get("region")),
            "business_region": business_region,
            "business_regions": business_regions,
            "line_scale": crm_text(payload.get("line_scale")),
            "bid_preference": crm_text(payload.get("bid_preference"), 1000),
            "history": crm_text(payload.get("history"), 2000),
            "win_rate": crm_text(payload.get("win_rate")),
            # These are semantic organization categories, not a depth limit.
            # parent_unit_id defines an acyclic tree of arbitrary depth.
            "organization_level": organization_level,
            "company_full_name": crm_text(payload.get("company_full_name", record.get("company_full_name", "")), 200),
            "subsidiary_full_name": crm_text(payload.get("subsidiary_full_name", record.get("subsidiary_full_name", "")), 200),
            "unit_name": crm_text(payload.get("unit_name", record.get("unit_name", "")), 200),
            "source": crm_text(payload.get("source")) or "手工录入",
            "updated_at": now,
            "version": int(record.get("version", 0)) + 1,
        })
        if not record["name"]:
            return {"ok": False, "error": "单位名称必填"}
        if organization_level == 'company':
            record.update({'company_full_name': record['name'], 'subsidiary_full_name': '', 'unit_name': ''})
        elif organization_level == 'subsidiary':
            record.update({'company_full_name': parent.get('company_full_name') or parent.get('name', ''), 'subsidiary_full_name': record['name'], 'unit_name': ''})
        elif organization_level == 'unit':
            record.update({'company_full_name': parent.get('company_full_name') or parent.get('name', ''),
                           'subsidiary_full_name': parent.get('subsidiary_full_name', ''),
                           'unit_name': record['name']})
        units[unit_id] = record
        crm_store(username, "units", units)
        crm_on_change(username)
        return {"ok": True, "unit": record}


def crm_unit_delete(unit_id, username):
    """Delete a customer organization only when no CRM record still depends on it.

    The visual editor may move nodes around freely, but a delete must never
    orphan a subtree or silently detach customer contacts.  The caller can
    re-parent child organizations or move contacts first, then retry.
    """
    with CRM_LOCK:
        unit_id = crm_text(unit_id)
        units = crm_load(username, "units")
        if unit_id not in units:
            return {"ok": False, "error": "组织不存在或不属于当前账号"}
        children = [unit for unit in units.values() if unit.get("parent_unit_id") == unit_id]
        if children:
            return {"ok": False, "error": "该组织仍有下级组织，请先拖动调整下级归属"}
        people = crm_load(username, "people")
        if any(person.get("unit_id") == unit_id for person in people.values()):
            return {"ok": False, "error": "该组织仍有关联联系人，请先调整联系人归属"}
        del units[unit_id]
        crm_store(username, "units", units)
        crm_on_change(username)
        return {"ok": True, "deleted_id": unit_id}


def crm_department_node(payload, username):
    """Edit a department grouping without deleting contacts or their relations."""
    with CRM_LOCK:
        units = crm_load(username, 'units')
        people = crm_load(username, 'people')
        parent_id = crm_text(payload.get('unit_id'))
        department = crm_text(payload.get('department'))
        action = payload.get('action')
        if parent_id not in units:
            return {'ok': False, 'error': '组织不存在或不属于当前账号'}
        members = [p for p in people.values() if p.get('unit_id') == parent_id and (p.get('department') or '') == department]
        if not members:
            return {'ok': False, 'error': '该部门已变化，请刷新画布'}
        if action not in ('add', 'delete'):
            return {'ok': False, 'error': '无效操作'}
        name = crm_text(payload.get('name'))
        if action == 'add' and not name:
            return {'ok': False, 'error': '请填写下级节点名称'}
        if action == 'delete' and not department:
            return {'ok': False, 'error': '未分部门是人员归属提示，请先将这些联系人移入具体组织或部门'}
        now = crm_now()
        target_id = parent_id
        child = None
        if action == 'add':
            parent = units[parent_id]
            title = department or '未分部门'
            target = next((u for u in units.values() if u.get('parent_unit_id') == parent_id and u.get('name') == title), None)
            def new_node(label, ancestor):
                return dict(id=crm_new_id('unit'), name=label, parent_unit_id=ancestor['id'], organization_level='unit',
                            type=ancestor.get('type', ''), region=ancestor.get('region', ''),
                            business_regions=ancestor.get('business_regions', []), business_region=ancestor.get('business_region', ''),
                            company_full_name=ancestor.get('company_full_name') or ancestor.get('name', ''),
                            subsidiary_full_name=ancestor.get('subsidiary_full_name', ''), unit_name=label,
                            source='画布建档', created_at=now, updated_at=now, version=1)
            if target is None:
                target = new_node(title, parent)
                units[target['id']] = target
            target_id = target['id']
            child = new_node(name, target)
            units[child['id']] = child
        for person in members:
            person.update(unit_id=target_id, department='', updated_at=now, version=int(person.get('version', 0)) + 1)
        if action == 'add':
            crm_store(username, 'units', units)
        crm_store(username, 'people', people)
        crm_on_change(username)
        return {'ok': True, 'unit': child, 'moved_people': len(members)}


def crm_person_save(payload, username):
    with CRM_LOCK:
        target_unit = crm_text(payload.get('unit_id'))
        if target_unit and target_unit not in crm_load(username, 'units'):
            return {'ok': False, 'error': '目标组织不存在或不属于当前账号，无法匹配人员'}
        people = crm_load(username, "people")
        person_id = crm_text(payload.get("id"))
        if crm_id_owned_by_another(username, 'people', person_id):
            return {"ok": False, "error": "这是其他账号上传的客户资料，仅可查看"}
        now = crm_now()
        if person_id and person_id in people:
            record = people[person_id]
            if int(payload.get("version", record.get("version", 1))) != int(record.get("version", 1)):
                return {"ok": False, "error": "人物已被更新，请刷新后重试"}
        else:
            person_id = crm_new_id("person")
            record = {"id": person_id, "created_at": now, "version": 0}
        try:
            influence = max(0, min(100, int(payload.get("influence", record.get("influence", 0)) or 0)))
        except (TypeError, ValueError):
            influence = 0
        importance = crm_text(payload.get('importance', record.get('importance', '')))
        support = crm_support_label(payload.get('support_level', record.get('support_level', '')))
        cadence = str(payload.get('maintenance_days', record.get('maintenance_days', '')) or '').strip()
        if importance not in ('', '重要', '一般') or support not in ('', *CRM_SUPPORT_LABELS):
            return {'ok':False, 'error':'重要程度或支持程度无效'}
        if cadence and (not cadence.isdigit() or not 1 <= int(cadence) <= 365):
            return {'ok':False, 'error':'维系周期须为1到365天'}
        record.update(importance=importance, support_level=support, maintenance_days=int(cadence) if cadence else '', imported_history=crm_text(payload.get('imported_history', record.get('imported_history','')), 2000))
        manager_id = crm_text(payload.get("manager_id", record.get("manager_id", "")))
        try:
            crm_validate_parent(people, person_id, manager_id, "manager_id")
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        record["manager_id"] = manager_id
        record["department"] = crm_text(payload.get("department", record.get("department", "")))
        record["responsibilities"] = crm_text(payload.get("responsibilities", record.get("responsibilities", "")), 1000)
        stance = crm_text(payload.get("stance"))
        role = crm_text(payload.get("decision_role"))
        career = payload.get("career_track")
        if isinstance(career, list):
            career = [crm_text(item, 100) for item in career if crm_text(item, 100)]
        else:
            career = [seg.strip() for seg in crm_text(career, 1000).split("→") if seg.strip()]
        record.update({
            "name": crm_text(payload.get("name")),
            "unit_id": crm_text(payload.get("unit_id")),
            "title": crm_text(payload.get("title")),
            # 联系方式为可选业务资料；未传字段时保留既有档案，避免编辑其他资料时丢失。
            "mobile": crm_text(payload.get("mobile", record.get("mobile", "")), 40),
            "office_phone": crm_text(payload.get("office_phone", record.get("office_phone", "")), 60),
            "email": crm_text(payload.get("email", record.get("email", "")), 160),
            "wechat": crm_text(payload.get("wechat", record.get("wechat", "")), 100),
            "decision_role": role if role in CRM_DECISION_ROLES else "",
            "power_radius": crm_text(payload.get("power_radius")),
            "influence": influence,
            "stance": stance if stance in {"支持", "中立", "反对", "未知"} else "未知",
            "career_track": career,
            "rotation_window": crm_text(payload.get("rotation_window")),
            "updated_at": now,
            "version": int(record.get("version", 0)) + 1,
        })
        if not record["name"]:
            return {"ok": False, "error": "人物姓名必填"}
        people[person_id] = record
        crm_store(username, "people", people)
        crm_on_change(username)
        return {"ok": True, "person": record}


# ---------------------------------------------------------------------------
# 关系层 / 动作层：一次触达即一条动作，关系强度由系统计算
# ---------------------------------------------------------------------------

def crm_relation_save(payload, username):
    with CRM_LOCK:
        relations = crm_load(username, "relations")
        relation_id = crm_text(payload.get("id"))
        if crm_id_owned_by_another(username, 'relations', relation_id):
            return {"ok": False, "error": "这是其他账号上传的客户关系，仅可查看"}
        now = crm_now()
        if relation_id and relation_id in relations:
            record = relations[relation_id]
            if int(payload.get("version", record.get("version", 1))) != int(record.get("version", 1)):
                return {"ok": False, "error": "关系已被更新，请刷新后重试"}
        else:
            relation_id = crm_new_id("rel")
            record = {"id": relation_id, "created_at": now, "version": 0}
        person_id = crm_text(payload.get("person_id"))
        if not person_id or person_id not in crm_load(username, "people"):
            return {"ok": False, "error": "关系必须关联一位已建档客户人"}
        record.update({
            "person_id": person_id,
            # When 我方对接人 is explicitly provided (Excel/page import always sends the
            # key), keep it verbatim — blank stays blank and shows as “—”. Only fall
            # back to the account when the field is entirely absent (legacy manual save).
            "our_member": crm_text(payload.get("our_member")) if "our_member" in payload else username,
            "source": crm_text(payload.get("source"), 500),
            "intro_path": crm_text(payload.get("intro_path"), 500),
            "updated_at": now,
            "version": int(record.get("version", 0)) + 1,
        })
        relations[relation_id] = record
        crm_store(username, "relations", relations)
        # 单点风险不是人工勾选项：同一客户联系人只有一位已指派我方
        # 对接人时才成立。新建或改派关系会同步刷新该联系人的所有关系。
        crm_recompute_single_point_risks(username, person_id)
        # 保存后重算强度与衰减
        crm_recompute_relation(username, relation_id)
        crm_on_change(username)
        return {"ok": True, "relation": relations_get(username, relation_id)}


def crm_relation_save_authorized(payload, caller):
    with CRM_LOCK:
        return _crm_relation_save_authorized_locked(payload, caller)


def _crm_relation_save_authorized_locked(payload, caller):
    """Save a relationship in its physical namespace when its liaison edits it.

    Imports are stored under the importing account, while ``our_member`` is the
    business owner.  Requiring these two values to be identical turned every
    imported relationship into a read-only record for its actual customer
    manager.  Keep the physical namespace intact, but let the uniquely matched
    liaison maintain the relationship background they are responsible for.
    Reassignment remains a manager-only batch operation.
    """
    caps = crm_capabilities(caller)
    if not caps.get('write'):
        raise PermissionError('没有编辑客户关系权限，请联系客户经营管理员授权')
    relation_id = crm_text((payload or {}).get('id'))
    if not relation_id:
        # A new relationship still belongs to the creator's own data space.
        return crm_relation_save(payload, caller.get('username', ''))
    matches = [item for item in crm_read_snapshot(caller)['relations'] if item.get('id') == relation_id]
    if len(matches) != 1:
        raise PermissionError('该客户关系不在当前可编辑的数据范围内')
    relation = matches[0]
    owner = crm_text(relation.get('_owner'))
    if not owner:
        raise ValueError('客户关系缺少数据归属，无法保存')
    caller_name = crm_text(caller.get('username'))
    assigned_profile, _ = crm_member_resolver()(owner, relation.get('our_member'))
    is_assignee = bool(assigned_profile and assigned_profile.get('username') == caller_name)
    if owner != caller_name and not is_assignee:
        raise PermissionError('仅该客户关系的我方对接人可以编辑')
    if owner != caller_name and crm_text(payload.get('person_id', relation.get('person_id'))) != relation.get('person_id'):
        raise PermissionError('维护关系不能变更关联联系人')
    if type(payload.get('version')) is not int or payload['version'] != relation.get('version', 1):
        return {'ok': False, 'error': '关系已被更新或缺少版本，请刷新后重试'}
    previous_member = crm_text(relation.get('our_member'))
    requested_member = crm_text(payload.get('our_member', previous_member))
    if requested_member != previous_member and owner != caller_name and not caps.get('batch_assign'):
        raise PermissionError('变更我方对接人请由区域负责人或客户经营管理员统一分配')
    clean_payload = {**relation, **payload}
    # Snapshot metadata must never become a persisted business field.
    clean_payload.pop('_owner', None)
    result = crm_relation_save(clean_payload, owner)
    if result.get('ok'):
        records = crm_load(owner, 'relations')
        records[relation_id]['created_by'] = relation.get('created_by') or owner
        records[relation_id]['updated_by'] = caller_name
        crm_store(owner, 'relations', records)
        result['relation'] = {**records[relation_id], '_owner': owner}
    return result


def relations_get(username, relation_id):
    return crm_load(username, "relations").get(relation_id)


def crm_action_add(payload, username, created_by=''):
    with CRM_LOCK:
        relations = crm_load(username, "relations")
        relation_id = crm_text(payload.get("relation_id"))
        if relation_id not in relations:
            return {"ok": False, "error": "动作必须关联一条已建立的关系"}
        actions = crm_load(username, "actions")
        action_id = crm_new_id("act")
        action_type = crm_text(payload.get("type"))
        record = {
            "id": action_id,
            "relation_id": relation_id,
            "type": action_type,
            "level": crm_text(payload.get("level")),
            "intel": crm_text(payload.get("intel"), 2000),
            "cost": crm_text(payload.get("cost")),
            "effective": bool(payload.get("effective")),
            "bidirectional": bool(payload.get("bidirectional")),
            "decision_node": crm_text(payload.get("decision_node")),
            "happened_at": crm_text(payload.get("happened_at")) or crm_now()[:10],
            "created_at": crm_now(),
            "created_by": crm_text(created_by) or username,
        }
        if payload.get('record_kind') == 'plan':
            if not crm_text(payload.get('next_step')): return {'ok':False, 'error':'计划内容不能为空'}
            record.update(record_kind='plan', happened_at='', effective=False, bidirectional=False)
        for key in ("next_step", "owner", "project_id", "due_date"):
            record[key] = crm_text(payload.get(key))
        if record["due_date"]:
            try:
                datetime.strptime(record["due_date"], "%Y-%m-%d")
            except ValueError:
                return {"ok": False, "error": "跟进日期格式应为 YYYY-MM-DD"}
        actions[action_id] = record
        crm_store(username, "actions", actions)
        crm_recompute_relation(username, relation_id)
        crm_on_change(username)
        return {"ok": True, "action": record, "relation": relations_get(username, relation_id)}


def crm_action_add_authorized(payload, caller):
    """Add an action to a visible relationship while retaining its physical owner."""
    if not crm_capabilities(caller).get('register_action'):
        raise PermissionError('没有登记动作权限，请联系客户经营管理员授权')
    relation_id = crm_text((payload or {}).get('relation_id'))
    matches = [item for item in crm_read_snapshot(caller)['relations'] if item.get('id') == relation_id]
    if not matches:
        raise PermissionError('该关系不在当前可操作的数据范围内')
    if len(matches) != 1:
        raise ValueError('关系标识存在冲突，无法安全登记动作')
    owner = matches[0].get('_owner', '')
    if not owner:
        raise ValueError('关系缺少数据归属，无法登记动作')
    result = crm_action_add(payload, owner, created_by=caller.get('username', ''))
    if result.get('action'):
        result['action']['_owner'] = owner
    return result


# ---------------------------------------------------------------------------
# 关系强度算法（六维加权，双向性权重×3）与衰减预警
# ---------------------------------------------------------------------------

def crm_relation_actions(actions, relation_id):
    items = [a for a in actions.values() if a.get("relation_id") == relation_id]
    items.sort(key=lambda a: a.get("happened_at", ""), reverse=True)
    return items


def crm_person_tier(person):
    """按职务/权力半径粗分层，用于衰减阈值。"""
    text = (str(person.get("title", "")) + str(person.get("power_radius", ""))) if person else ""
    if any(k in text for k in ("总", "长", "主任", "书记", "董事")):
        return "高层"
    if any(k in text for k in ("经理", "部长", "科长", "主管", "工程师")):
        return "中层"
    return "基层"


def crm_score_relation(relation, actions_for_rel, person):
    """返回 (score0-100, level0-5, radar 六维, decay_state, days_since)。"""
    radar = {"触达近因": 0, "动作深度": 0, "双向性": 0, "情报质量": 0, "关键时刻": 0, "多点触达": 0}
    if not actions_for_rel:
        return 0, 0, radar, "normal", None
    days = crm_days_since(actions_for_rel[0].get("happened_at"))
    # 触达近因：30天内满分，线性衰减到180天为0
    if days is not None:
        radar["触达近因"] = round(max(0.0, min(1.0, (180 - days) / 180)) * 100)
    # 动作深度：有效动作数量累计
    effective = [a for a in actions_for_rel if a.get("effective")]
    radar["动作深度"] = min(100, len(effective) * 25)
    # 双向性：客户主动占比（权重最高，在合成时×3）
    bidir = [a for a in actions_for_rel if a.get("bidirectional")]
    radar["双向性"] = round(len(bidir) / len(actions_for_rel) * 100)
    # 情报质量：产出情报的动作占比
    intel = [a for a in actions_for_rel if crm_text(a.get("intel"))]
    radar["情报质量"] = round(len(intel) / len(actions_for_rel) * 100)
    # 关键时刻：是否在定标/验收等关键节点触达
    key_nodes = {"定标", "验收", "招标", "付款"}
    radar["关键时刻"] = 100 if any(a.get("decision_node") in key_nodes for a in actions_for_rel) else 0
    # 多点触达：我方触达该客户的不同成员数
    members = {a_our for a_our in (relation.get("our_member"),) if a_our}
    radar["多点触达"] = min(100, len(members) * 50)
    # 加权合成：双向性权重3，其余权重1
    weights = {"触达近因": 1, "动作深度": 1, "双向性": 3, "情报质量": 1, "关键时刻": 1, "多点触达": 1}
    total_w = sum(weights.values())
    score = round(sum(radar[k] * weights[k] for k in radar) / total_w)
    # 分数→六级
    if score >= 85:
        level = 5
    elif score >= 68:
        level = 4
    elif score >= 50:
        level = 3
    elif score >= 30:
        level = 2
    elif score >= 1:
        level = 1
    else:
        level = 0
    # 衰减状态：按层级阈值
    tier = crm_person_tier(person)
    warn, alarm = CRM_DECAY_THRESHOLDS.get(tier, (45, 90))
    cadence = (person or {}).get('maintenance_days')
    if isinstance(cadence, int) and 1 <= cadence <= 365: warn, alarm = cadence, cadence * 2
    decay = "normal"
    if days is not None:
        if days >= alarm:
            decay = "alarm"
        elif days >= warn:
            decay = "warning"
    return score, level, radar, decay, days


def crm_recompute_relation(username, relation_id):
    relations = crm_load(username, "relations")
    record = relations.get(relation_id)
    if not record:
        return
    actions = crm_load(username, "actions")
    people = crm_load(username, "people")
    person = people.get(record.get("person_id"), {})
    acts = [a for a in crm_relation_actions(actions, relation_id) if a.get("record_kind") != "plan"]
    score, level, radar, decay, days = crm_score_relation(record, acts, person)
    record.update({
        "strength": level,
        "strength_label": CRM_STRENGTH_LEVELS[level],
        "score": score,
        "radar": radar,
        "decay_state": decay,
        "last_touch": acts[0].get("happened_at") if acts else "",
        "days_since_touch": days,
        "action_count": len(acts),
    })
    relations[relation_id] = record
    crm_store(username, "relations", relations)


def crm_apply_single_point_risks(relations):
    """Derive single-point risk from distinct assigned liaisons per contact.

    Unassigned records are a separate assignment gap, not a single point.  This
    accepts either a collection dictionary or a snapshot list and mutates only
    the supplied records, so read paths can also make legacy data consistent.
    """
    records = relations.values() if isinstance(relations, dict) else relations
    records = list(records)
    members_by_person = {}
    for record in records:
        person_id = crm_text(record.get('person_id'))
        member = crm_text(record.get('our_member'))
        if person_id and member:
            members_by_person.setdefault(person_id, set()).add(member)
    for record in records:
        person_id = crm_text(record.get('person_id'))
        record['single_point_risk'] = bool(person_id and len(members_by_person.get(person_id, set())) == 1)
    return relations


def crm_recompute_single_point_risks(username, person_id):
    """Persist the automatic single-point result for every relation of a contact."""
    relations = crm_load(username, 'relations')
    related = {rid: record for rid, record in relations.items() if record.get('person_id') == person_id}
    crm_apply_single_point_risks(related)
    relations.update(related)
    crm_store(username, 'relations', relations)


# ---------------------------------------------------------------------------
# 项目关联层
# ---------------------------------------------------------------------------

def crm_link_save(payload, username):
    with CRM_LOCK:
        links = crm_load(username, "links")
        link_id = crm_text(payload.get("id")) or crm_new_id("link")
        if crm_id_owned_by_another(username, 'links', crm_text(payload.get("id"))):
            return {"ok": False, "error": "这是其他账号上传的项目关联，仅可查看"}
        node = crm_text(payload.get("decision_node"))
        record = {
            "id": link_id,
            "project_id": crm_text(payload.get("project_id")),
            "decision_node": node if node in CRM_DECISION_NODES else "",
            "person_id": crm_text(payload.get("person_id")),
            "our_member": crm_text(payload.get("our_member")) or username,
            "updated_at": crm_now(),
        }
        if not record["project_id"] or not record["decision_node"]:
            return {"ok": False, "error": "项目与决策节点必填"}
        if record["person_id"] not in crm_load(username, "people"):
            return {"ok": False, "error": "请选择当前账号下的客户联系人"}
        links[link_id] = record
        crm_store(username, "links", links)
        crm_on_change(username)
        return {"ok": True, "link": record}


# ---------------------------------------------------------------------------
# 聚合：总览（网络图谱 + 衰减预警）
# ---------------------------------------------------------------------------

def crm_overview(username, use_cache=True):
    if use_cache:
        cached = crm_cache_get(username)
        if cached is not None and cached.get("staff_schema") == 1:
            return cached
    units = crm_load(username, "units")
    people = crm_load(username, "people")
    relations = crm_load(username, "relations")
    crm_apply_single_point_risks(relations)
    # 惰性刷新所有关系的评分/衰减
    for rid in list(relations.keys()):
        crm_recompute_relation(username, rid)
    relations = crm_load(username, "relations")

    # 网络图谱节点/边
    nodes = [{"id": "self", "label": "我方", "kind": "self", "type": "我方"}]
    for u in units.values():
        nodes.append({"id": u["id"], "label": u["name"], "kind": "unit", "type": u.get("type", "")})
    person_index = {}
    for p in people.values():
        person_index[p["id"]] = p
        nodes.append({
            "id": p["id"], "label": p["name"], "kind": "person",
            "unit_id": p.get("unit_id", ""), "influence": p.get("influence", 0),
            "type": (units.get(p.get("unit_id"), {}) or {}).get("type", ""),
        })
    edges = []
    warnings = []
    for r in relations.values():
        p = person_index.get(r.get("person_id"))
        if not p:
            continue
        if r.get("our_member"):
            edges.append({
                "source": "self", "target": r["person_id"], "our_member": r.get("our_member", ""), "our_member_label": crm_member_label(username, r.get("our_member")), "strength": r.get("strength", 0),
                "score": r.get("score", 0), "decay_state": r.get("decay_state", "normal"),
                "days_since_touch": r.get("days_since_touch"),
                "single_point_risk": bool(r.get("single_point_risk")),
            })
        if r.get("decay_state") in {"warning", "alarm"}:
            warnings.append({
                "relation_id": r["id"], "person_id": r["person_id"], "person_name": p.get("name", ""),
                "unit_name": (units.get(p.get("unit_id"), {}) or {}).get("name", ""),
                "tier": crm_person_tier(p), "decay_state": r["decay_state"],
                "days_since_touch": r.get("days_since_touch"), "strength": r.get("strength", 0),
            })
    warnings.sort(key=lambda w: (w["decay_state"] != "alarm", -(w.get("days_since_touch") or 0)))

    operating_units = [unit for unit in units.values() if unit.get('organization_level', '') not in ('company', 'subsidiary')]
    stats = {
        "units": len(operating_units), "people": len(people), "relations": len(relations),
        "trusted": sum(1 for r in relations.values() if r.get("strength", 0) >= 3),
        "warnings": len(warnings),
        "single_point": sum(1 for r in relations.values() if r.get("single_point_risk")),
    }
    result = {
        "ok": True, "staff_schema": 1, "stats": stats, "graph": {"nodes": nodes, "edges": edges},
        "warnings": warnings[:50], "unit_types": CRM_UNIT_TYPES,
        "infra": crm_infra_status(),
    }
    crm_cache_set(username, result)
    return result


def _crm_build_snapshot(user):
    """Read CRM data under the caller's private, regional, or administrator scope.

    Writes always retain the caller's own physical namespace; this function is
    intentionally read-only, so sharing cannot accidentally create cross-user
    edits.
    """
    caps = crm_capabilities(user)
    username = user.get('username', '')
    scope = caps.get('data_scope', 'self')
    users = read_config().get('users', [])
    def in_department_scope(candidate, company, departments):
        if str(candidate.get('company', '') or '').strip() != company:
            return False
        value = str(candidate.get('department', '') or '').strip()
        return not departments or any(value == item or value.startswith(item + ' / ') for item in departments)
    if scope == 'all' or scope == 'regions':
        owners = [item.get('username', '') for item in users]
    elif scope == 'team':
        own_company = str(user.get('company', '') or '').strip()
        own_department = str(user.get('department', '') or '').strip()
        owners = [item.get('username', '') for item in users if in_department_scope(item, own_company, [own_department] if own_department else [])]
    elif scope == 'organization':
        owners = [item.get('username', '') for item in users if in_department_scope(item, caps.get('scope_company', ''), caps.get('scope_departments', []))]
    else:
        owners = [username]
    allowed_regions = set(caps.get('regions', []))
    scoped_owners = set(owners)
    account = next((item for item in users if item.get('username') == username), user)
    my_keys = {username, str(account.get('employee_id') or '').strip()} - {''}
    resolve_member = crm_member_resolver()
    def assigned_to_caller(owner, relation):
        """Match both canonical account keys and uniquely resolved legacy labels."""
        member_key = str(relation.get('our_member') or '').strip()
        if not member_key:
            return False
        if member_key in my_keys:
            return True
        profile, _label = resolve_member(owner, member_key)
        return bool(profile and profile.get('username') == username)
    # An explicit personal assignment grants read access to that relationship,
    # regardless of who originally entered it. It never grants write access.
    owners = list(dict.fromkeys([*owners, *(item.get('username', '') for item in users)]))
    result = {name: [] for name in ('units', 'people', 'relations', 'actions', 'links', 'staff', 'opportunities')}
    # Staff records are keyed by employee ID, while people commonly search by
    # their login account.  Expose that non-sensitive alias to the picker so
    # Element Plus's built-in fuzzy (substring) search can match either form.
    account_by_member_key = {
        str(item.get('employee_id', '') or '').strip(): str(item.get('username', '') or '').strip()
        for item in users if str(item.get('employee_id', '') or '').strip()
    }
    for owner in owners:
        if not owner:
            continue
        all_units = crm_load(owner, 'units')
        all_people = crm_load(owner, 'people')
        all_relations = crm_load(owner, 'relations')
        mine = {key: value for key, value in all_relations.items() if caps.get('read') and assigned_to_caller(owner, value)}
        assigned_people = {item.get('person_id') for item in mine.values()}
        assigned_units = {item.get('unit_id') for key, item in all_people.items() if key in assigned_people}
        ordinary_units = {key: value for key, value in all_units.items() if owner in scoped_owners and (scope != 'regions' or set(crm_unit_regions(value)) & allowed_regions)}
        units = {key: value for key, value in all_units.items() if key in ordinary_units or key in assigned_units}
        unit_ids = set(units)
        people = {key: value for key, value in all_people.items() if value.get('unit_id') in unit_ids and (value.get('unit_id') in ordinary_units or key in assigned_people)}
        person_ids = set(people)
        ordinary_people = {key for key, value in people.items() if value.get('unit_id') in ordinary_units}
        relations = {key: value for key, value in all_relations.items() if value.get('person_id') in person_ids and (value.get('person_id') in ordinary_people or key in mine)}
        relation_ids = set(relations)
        actions = {key: value for key, value in crm_load(owner, 'actions').items() if value.get('relation_id') in relation_ids}
        links = {key: value for key, value in crm_load(owner, 'links').items() if value.get('person_id') in ordinary_people}
        for name, records in (('units', units), ('people', people), ('relations', relations), ('actions', actions), ('links', links)):
            for record in records.values():
                item = dict(record)
                item['_owner'] = owner
                result[name].append(item)
        if owner == username or scope == 'all':
            result['staff'].extend(
                dict(record, _owner=owner, username=account_by_member_key.get(str(record.get('member_key', '') or '').strip(), ''))
                for record in crm_load(owner, 'staff').values()
            )
        if owner in scoped_owners:
            result['opportunities'].extend(
                dict(record, _owner=owner) for record in crm_load(owner, 'opportunities').values()
            )
    # Relationship visibility follows the actual liaison, not the uploader or
    # broad archive/organization visibility. Administrators retain the full view;
    # regional grants add regional relationships to a caller's own assignments.
    admin_view = user.get('role') in ('admin', 'superadmin') or caps.get('manage') or caps.get('appoint')
    if not caps.get('read'):
        result['relations'] = []
    elif not admin_view:
        unit_by_key = {(u['_owner'], u['id']): u for u in result['units']}
        person_by_key = {(p['_owner'], p['id']): p for p in result['people']}
        def visible_relationship(relation):
            if assigned_to_caller(relation.get('_owner', ''), relation):
                return True
            if scope != 'regions':
                return False
            person = person_by_key.get((relation['_owner'], relation.get('person_id')), {})
            unit = unit_by_key.get((relation['_owner'], person.get('unit_id')), {})
            return bool(set(crm_unit_regions(unit)) & allowed_regions)
        result['relations'] = [r for r in result['relations'] if visible_relationship(r)]
    visible_relation_keys = {(r['_owner'], r['id']) for r in result['relations']}
    result['actions'] = [a for a in result['actions'] if (a['_owner'], a.get('relation_id')) in visible_relation_keys]
    return result


def crm_read_units(user):
    return {"ok": True, "units": crm_read_snapshot(user, ('units',))['units'], "types": CRM_UNIT_TYPES}


def crm_read_opportunities(user):
    opportunities = crm_read_snapshot(user, ('opportunities',))['opportunities']
    opportunities.sort(key=lambda item: (bool(item.get('cancelled')), item.get('name', ''), item.get('code', '')))
    return {"ok": True, "opportunities": opportunities}


def crm_opportunity_save(payload, username):
    """Create or update an opportunity without changing its stable project code."""
    with CRM_LOCK:
        records = crm_load(username, 'opportunities')
        record_id = crm_text(payload.get('id'), 80)
        code = crm_text(payload.get('code'), 80)
        if record_id and crm_id_owned_by_another(username, 'opportunities', record_id):
            return {'ok': False, 'error': '这是其他账号导入的机会点，仅可查看'}
        record = records.get(record_id) if record_id else None
        if record:
            if int(payload.get('version', record.get('version', 1))) != int(record.get('version', 1)):
                return {'ok': False, 'error': '机会点已被更新，请刷新后重试'}
            if code != record.get('code'):
                return {'ok': False, 'error': '机会点编码用于关联作战记录，保存后不可修改'}
        else:
            if not code:
                return {'ok': False, 'error': '请填写机会点编码'}
            if code in records:
                return {'ok': False, 'error': '机会点编码已存在'}
            record_id, record = code, {'id': code, 'code': code, 'created_at': crm_now(), 'version': 0}
        name = crm_text(payload.get('name'), 240)
        owner_unit = crm_text(payload.get('owner_unit'), 240)
        if not name or not owner_unit:
            return {'ok': False, 'error': '请填写机会点名称和业主单位'}
        raw_amount = payload.get('amount', 0)
        try:
            amount = float(raw_amount or 0)
        except (TypeError, ValueError):
            return {'ok': False, 'error': '可参与份额请填写数字'}
        if amount < 0:
            return {'ok': False, 'error': '可参与份额不能为负数'}
        cancelled = bool(payload.get('cancelled'))
        record.update({
            'id': record_id, 'code': code, 'name': name, 'owner_unit': owner_unit,
            'stage': crm_text(payload.get('stage'), 80), 'win_rate': crm_text(payload.get('win_rate'), 20),
            'status': crm_text(payload.get('status'), 80), 'region': crm_text(payload.get('region'), 80),
            'manager': crm_text(payload.get('manager'), 80), 'bid_date': crm_text(payload.get('bid_date'), 40),
            'contract_date': crm_text(payload.get('contract_date'), 40), 'amount': amount,
            'cancelled': cancelled, 'cancel_reason': crm_text(payload.get('cancel_reason'), 500) if cancelled else '',
            'updated_at': crm_now(), 'version': int(record.get('version', 0)) + 1,
        })
        records[record_id] = record
        crm_store(username, 'opportunities', records)
        crm_on_change(username)
        return {'ok': True, 'opportunity': record}


def crm_read_overview(user):
    snapshot = crm_read_snapshot(user, ('units', 'people', 'relations'))
    units = snapshot['units']
    people = snapshot['people']
    relations = snapshot['relations']
    crm_apply_single_point_risks(relations)
    unit_by_id = {item['id']: item for item in units}
    person_by_id = {item['id']: item for item in people}
    nodes = [{'id': 'self', 'label': '我方', 'kind': 'self', 'type': '我方'}]
    nodes.extend({'id': item['id'], 'label': item.get('name', ''), 'kind': 'unit', 'type': item.get('type', '')} for item in units)
    nodes.extend({'id': item['id'], 'label': item.get('name', ''), 'kind': 'person', 'unit_id': item.get('unit_id', ''), 'influence': item.get('influence', 0), 'type': unit_by_id.get(item.get('unit_id', ''), {}).get('type', '')} for item in people)
    edges = []
    warnings = []
    for relation in relations:
        person = person_by_id.get(relation.get('person_id'))
        if not person:
            continue
        if relation.get('our_member'):
            edges.append({'source':'self','target':relation.get('person_id'),'our_member':relation.get('our_member',''),'strength':relation.get('strength',0),'score':relation.get('score',0),'decay_state':relation.get('decay_state','normal'),'days_since_touch':relation.get('days_since_touch')})
        if relation.get('decay_state') in {'warning','alarm'}:
            warnings.append({'relation_id':relation.get('id'),'person_id':person.get('id'),'person_name':person.get('name',''),'unit_name':unit_by_id.get(person.get('unit_id',''),{}).get('name',''),'tier':crm_person_tier(person),'decay_state':relation.get('decay_state'),'days_since_touch':relation.get('days_since_touch'),'strength':relation.get('strength',0)})
    warnings.sort(key=lambda item: (item['decay_state'] != 'alarm', -(item.get('days_since_touch') or 0)))
    operating_units = [item for item in units if item.get('organization_level', '') not in ('company', 'subsidiary')]
    return {'ok':True,'staff_schema':1,'stats':{'units':len(operating_units),'people':len(people),'relations':len(relations),'trusted':sum(1 for item in relations if item.get('strength',0) >= 3),'warnings':len(warnings),'single_point':sum(1 for item in relations if item.get('single_point_risk'))},'graph':{'nodes':nodes,'edges':edges},'warnings':warnings[:50],'unit_types':CRM_UNIT_TYPES,'infra':crm_infra_status()}


def crm_read_people(user):
    snapshot = crm_read_snapshot(user, ('units', 'people'))
    people = snapshot['people']
    units = {item['id']: item for item in snapshot['units']}
    for p in people:
        unit = units.get(p.get("unit_id"), {}) or {}
        chain = []
        cursor = unit
        seen = set()
        while cursor and cursor.get('id') not in seen:
            seen.add(cursor.get('id'))
            chain.append(cursor)
            cursor = units.get(cursor.get('parent_unit_id', ''))
        chain.reverse()
        # Older records do not have organization_level metadata. Their unit
        # remains the terminal “单位” level so existing archives stay legible.
        p["unit_name"] = unit.get("name", "")
        p["company_full_name"] = next((item.get('name', '') for item in chain if item.get('organization_level') == 'company'), unit.get('company_full_name', ''))
        p["subsidiary_full_name"] = next((item.get('name', '') for item in chain if item.get('organization_level') == 'subsidiary'), unit.get('subsidiary_full_name', ''))
        p["organization_unit_name"] = next((item.get('name', '') for item in chain if item.get('organization_level') == 'unit'), unit.get('unit_name', '') or unit.get('name', ''))
        p["organization_path"] = ' / '.join(item.get('name', '') for item in chain if item.get('name'))
        p["support_level"] = crm_support_label(p.get("support_level", ""))
    return {"ok": True, "people": people, "roles": CRM_DECISION_ROLES}


def crm_read_relations(user):
    snapshot = crm_read_snapshot(user, ('people', 'relations', 'actions'))
    relations = snapshot['relations']
    crm_apply_single_point_risks(relations)
    people = {item['id']: item for item in snapshot['people']}
    actions = snapshot['actions']
    result = []
    resolve_member = crm_member_resolver()
    for r in relations:
        p = people.get(r.get("person_id"), {})
        item = dict(r)
        item["person_name"] = p.get("name", "")
        item["our_staff"], item["our_member_label"] = resolve_member(r.get('_owner', ''), r.get("our_member"))
        item["actions"] = [a for a in actions if a.get('relation_id') == r["id"]]
        result.append(item)
    return {"ok": True, "relations": result, "levels": CRM_STRENGTH_LEVELS}


# Backward-compatible private-data aliases for internal write workflows.
def crm_units(username):
    return {"ok": True, "units": list(crm_load(username, "units").values()), "types": CRM_UNIT_TYPES}


def crm_people(username):
    people = list(crm_load(username, "people").values())
    units = crm_load(username, "units")
    for p in people:
        p["unit_name"] = (units.get(p.get("unit_id"), {}) or {}).get("name", "")
        p["support_level"] = crm_support_label(p.get("support_level", ""))
    return {"ok": True, "people": people, "roles": CRM_DECISION_ROLES}


def crm_relations(username):
    return crm_read_relations({'username': username, 'role': 'member', 'assistant_permissions': {'crm': True}})


# ---------------------------------------------------------------------------
# 项目作战地图：决策链覆盖度 + 二度路径 + 排人选 + 六步
# ---------------------------------------------------------------------------

def crm_normalize_organization_name(value):
    """Make imported owner names comparable with CRM organization names."""
    text = crm_text(value).lower()
    for mark in '（）()·、，,./\\-':
        text = text.replace(mark, '')
    text = ''.join(text.split())
    for suffix in ('有限责任公司', '股份有限公司', '有限公司', '集团公司', '集团'):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break
    return text


def crm_opportunity_context(username, project_id, people=None, units=None, relations=None):
    """Resolve an opportunity into its owner organization and reusable relationship assets.

    An opportunity is the commercial context, while people and relationships are
    reusable assets.  Matching the owner's organization tree here keeps the
    battle-map recommendation on the same customer scope as the selected
    opportunity rather than treating its code as an opaque string.
    """
    project_id = crm_text(project_id)
    opportunity = next((item for item in crm_load(username, 'opportunities').values()
                        if item.get('code') == project_id or item.get('id') == project_id), None)
    if not opportunity:
        return None
    people = people if people is not None else crm_load(username, 'people')
    units = units if units is not None else crm_load(username, 'units')
    relations = relations if relations is not None else crm_load(username, 'relations')
    owner = crm_normalize_organization_name(opportunity.get('owner_unit'))
    matched_ids = set()
    if owner:
        for unit_id, unit in units.items():
            names = (unit.get('name', ''), unit.get('company_full_name', ''), unit.get('subsidiary_full_name', ''))
            normalized = [crm_normalize_organization_name(name) for name in names]
            if any(name and (name == owner or (len(name) >= 4 and (name in owner or owner in name))) for name in normalized):
                matched_ids.add(unit_id)
    # A hit at a company or a subsidiary covers every child organization where
    # the real contacts normally live.  Do not traverse upward: an opportunity
    # for one branch must not accidentally include the whole parent group.
    changed = True
    while changed:
        changed = False
        for unit_id, unit in units.items():
            if unit.get('parent_unit_id') in matched_ids and unit_id not in matched_ids:
                matched_ids.add(unit_id)
                changed = True
    matched_people = [person for person in people.values() if person.get('unit_id') in matched_ids]
    people_ids = {person.get('id') for person in matched_people}
    scoped_relations = [relation for relation in relations.values() if relation.get('person_id') in people_ids]
    assigned = [relation for relation in scoped_relations if relation.get('our_member')]
    strong = [relation for relation in assigned if relation.get('strength', 0) >= 3]
    return {
        'code': opportunity.get('code', project_id),
        'name': opportunity.get('name', ''),
        'owner_unit': opportunity.get('owner_unit', ''),
        'stage': opportunity.get('stage', ''),
        'cancelled': bool(opportunity.get('cancelled')),
        'matched_units': len(matched_ids),
        'matched_people': len(matched_people),
        'relations': len(scoped_relations),
        'assigned_relations': len(assigned),
        'strong_relations': len(strong),
        'single_point_risks': sum(bool(relation.get('single_point_risk')) for relation in assigned),
        'unit_ids': list(matched_ids),
        'person_ids': list(people_ids),
    }

def crm_decision_coverage(username, project_id):
    """决策链热力图：五类单位 × 决策节点覆盖强度矩阵。"""
    project_id = crm_text(project_id)
    links = [l for l in crm_load(username, "links").values() if l.get("project_id") == project_id]
    people = crm_load(username, "people")
    units = crm_load(username, "units")
    relations = crm_load(username, "relations")
    rel_by_person = {}
    for r in relations.values():
        rel_by_person.setdefault(r.get("person_id"), []).append(r)
    applicable = {o["type"]: set(o["stages"]) for o in CRM_ORGANIZATIONS}
    matrix = {ut: {node: {"covered": False, "strength": 0, "applicable": node in applicable[ut]} for node in CRM_DECISION_NODES} for ut in CRM_UNIT_TYPES}
    covered = 0
    strong = 0
    for l in links:
        p = people.get(l.get("person_id"))
        if not p:
            continue
        ut = (units.get(p.get("unit_id"), {}) or {}).get("type", "")
        node = l.get("decision_node")
        if ut not in matrix or node not in matrix[ut]:
            continue
        best = max((r.get("strength", 0) for r in rel_by_person.get(p["id"], [])), default=0)
        cell = matrix[ut][node]
        if not cell["covered"]:
            covered += 1
        cell["applicable"] = True
        cell["covered"] = True
        cell["strength"] = max(cell["strength"], best)
        if best >= 3:
            strong += 1
    strong = sum(c["covered"] and c["strength"] >= 3 for row in matrix.values() for c in row.values())
    should_cover = sum(c["applicable"] for row in matrix.values() for c in row.values())
    return {
        "matrix": matrix, "nodes": CRM_DECISION_NODES, "unit_types": CRM_UNIT_TYPES,
        "should_cover": should_cover, "covered": covered, "l3_plus": strong,
    }


def crm_battle_map_generate(payload, username):
    """针对目标客户人，输出：打谁 / 谁去 / 走哪条路 / 第一步做什么。"""
    project_id = crm_text(payload.get("project_id"))
    target_person_id = crm_text(payload.get("target_person_id"))
    people = crm_load(username, "people")
    units = crm_load(username, "units")
    relations = crm_load(username, "relations")
    target = people.get(target_person_id)
    if not target:
        return {"ok": False, "error": "请选择一位目标客户人"}

    rel_by_person = {}
    for r in relations.values():
        rel_by_person.setdefault(r.get("person_id"), []).append(r)

    for rid in list(relations):
        crm_recompute_relation(username, rid)
    relations = crm_load(username, "relations")
    rel_by_person = {}
    for r in relations.values():
        rel_by_person.setdefault(r.get("person_id"), []).append(r)
    opportunity_context = crm_opportunity_context(username, project_id, people, units, relations)

    # 排人选：直接关系候选（关系强度 × 是否有效历史）
    candidates = []
    for r in rel_by_person.get(target_person_id, []):
        candidates.append({
            "our_member": r.get("our_member", ""), "strength": r.get("strength", 0),
            "score": r.get("score", 0), "path": "直接触达",
        })
    # 找路径：二度引荐。机会点已匹配业主组织时，优先在同一业主组织树内
    # 检索关系资产；否则维持历史的同单位兜底规则。
    if not any(c["strength"] >= 3 for c in candidates):
        unit_id = target.get("unit_id")
        owner_scope = set(opportunity_context.get('unit_ids', [])) if opportunity_context else set()
        for p in people.values():
            same_owner_organization = bool(owner_scope and p.get('unit_id') in owner_scope)
            same_unit = bool(unit_id and p.get('unit_id') == unit_id)
            if p["id"] == target_person_id or not (same_owner_organization or same_unit):
                continue
            for r in rel_by_person.get(p["id"], []):
                if r.get("strength", 0) >= 3:
                    scope_label = '同一业主组织线索，需确认' if same_owner_organization and not same_unit else '同单位线索，需确认'
                    candidates.append({
                        "our_member": r.get("our_member", ""), "strength": r.get("strength", 0),
                        "score": max(0, r.get("score", 0) - 20),
                        "path": f"经 {p.get('name', '')} 尝试引荐（{scope_label}）",
                    })
    requested_members = payload.get('our_members')
    if requested_members is not None:
        if not isinstance(requested_members, list) or any(not isinstance(k, str) for k in requested_members):
            return {'ok': False, 'error': '我方人员范围无效'}
        candidates = [c for c in candidates if c['our_member'] in requested_members]
    for c in candidates:
        c['our_staff'] = crm_member_profile(username, c['our_member'])
        c['our_member_label'] = crm_member_label(username, c['our_member'])
    candidates.sort(key=lambda c: c["score"], reverse=True)

    unit = units.get(target.get("unit_id"), {})
    best = candidates[0] if candidates else None
    current_level = max((r.get("strength", 0) for r in rel_by_person.get(target_person_id, [])), default=0)
    target_level = min(5, max(3, current_level + 1))
    stage = crm_stage(payload.get("stage"))
    first_step = f"{best['our_member_label'] if best else '待指派负责人'}：{stage['action']}；产出：{stage['deliverable']}。"
    pipeline = [
        {"step": "01 确认阶段", "detail": stage["title"]},
        {"step": "02 核查覆盖", "detail": "按参考职责与已登记节点计算，灰格为模板非必需"},
        {"step": "03 核实路径", "detail": "同单位连线仅为引荐线索，使用前确认"},
        {"step": "04 建议人选", "detail": f"候选 {len(candidates)} 条关系，按已记录关系评分排序"},
        {"step": "05 执行动作", "detail": stage["action"]},
        {"step": "06 留存证据", "detail": stage["gate"]},
    ]
    coverage = crm_decision_coverage(username, project_id) if project_id else None
    # 用最短引荐路径描述"走哪条路"（Neo4j 优先，回退内存 BFS）
    path_info = crm_path_to_person(username, target_person_id)
    graph_path = path_info if path_info.get("ok") and path_info.get("hops", 0) > 0 else None
    route = best["path"] if best else "无现成路径"
    if requested_members is not None: graph_path = None
    if graph_path:
        route = " → ".join(graph_path["names"]) + ("（同单位推测，需核实）" if graph_path["hops"] > 1 else "（已登记直接关系）")
    return {
        "ok": True,
        "battle_map": {
            "target": f"{target.get('name', '')}（{unit.get('name', '')} {target.get('title', '')}）",
            "who_goes": best["our_member_label"] if best else "待指派",
            "route": route,
            "first_step": first_step,
            "current_level": current_level,
            "target_level": target_level,
        },
        "candidates": candidates[:8],
        "pipeline": pipeline,
        "coverage": coverage,
        "opportunity_context": opportunity_context,
        "graph_path": graph_path,
        "graph_source": path_info.get("source", "memory"),
    }


def crm_project_map(username, project_id):
    return {"ok": True, "coverage": crm_decision_coverage(username, project_id)}


def crm_path_to_person(username, target_person_id):
    """引荐路径：我方→目标客户人。优先 Neo4j shortestPath，否则内存 BFS。

    内存图：我方(self)连所有已建关系的客户人（KNOWS）；同单位客户人两两相连
    （COLLEAGUE）。返回 {names, ids, hops, source} 或 ok=False。
    """
    people = crm_load(username, "people")
    if target_person_id not in people:
        return {"ok": False, "error": "目标客户人不存在"}
    graph = crm_graph_shortest_path(username, target_person_id)
    if graph and graph.get("hops", 0) > 0:
        ids = graph.get("ids", [])
        valid = len(ids) >= 2 and ids[-1] == target_person_id
        for left, right in zip(ids[1:], ids[2:]):
            unit = people.get(left, {}).get("unit_id")
            valid = valid and bool(unit) and unit == people.get(right, {}).get("unit_id")
        if valid:
            return {"ok": True, **graph}
    # 内存 BFS 回退
    relations = crm_load(username, "relations")
    adjacency = {"self": set()}
    for r in relations.values():
        pid = r.get("person_id")
        if pid in people and r.get("our_member"):
            adjacency["self"].add(pid)
            adjacency.setdefault(pid, set()).add("self")
    by_unit = {}
    for p in people.values():
        if p.get("unit_id"):
            by_unit.setdefault(p["unit_id"], []).append(p["id"])
    for members in by_unit.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                adjacency.setdefault(members[i], set()).add(members[j])
                adjacency.setdefault(members[j], set()).add(members[i])
    # BFS
    from collections import deque
    queue = deque([["self"]])
    seen = {"self"}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target_person_id:
            names = ["我方" if n == "self" else people.get(n, {}).get("name", "") for n in path]
            return {"ok": True, "ids": path, "names": names, "hops": len(path) - 1, "source": "memory"}
        for nxt in adjacency.get(node, ()):  # noqa: E501
            if nxt not in seen:
                seen.add(nxt)
                queue.append(path + [nxt])
    return {"ok": True, "ids": [], "names": [], "hops": 0, "source": "memory"}


# ---------------------------------------------------------------------------
# 从合同带入：把合同甲方落成客户单位、乙方联系人落成人物
# ---------------------------------------------------------------------------

def crm_import_from_contract(payload, username):
    contract_id = crm_text(payload.get("contract_id"))
    try:
        contract = contract_read(username, contract_id)
    except (ValueError, PermissionError) as exc:
        return {"ok": False, "error": str(exc)}
    customer = crm_text(contract.get("customer")) or crm_text(contract.get("party_a"))
    if not customer:
        return {"ok": False, "error": "该合同未识别出客户单位，请先在合同中补全甲方/客户"}
    result = crm_unit_save({
        "name": customer, "type": "业主单位", "source": f"合同带入 {contract.get('contract_no', '')}",
        "history": f"合同金额 {contract.get('total_amount', '')}；项目 {contract.get('project_code', '')}",
    }, username)
    return {"ok": result.get("ok"), "unit": result.get("unit"), "error": result.get("error"),
            "note": "已从合同建档客户单位，联系人与决策角色仍需人工补录"}


def crm_staff_save(payload, username, dry_run=False):
    """Owner-scoped internal staff; hierarchy never implies access permissions."""
    with CRM_LOCK:
        rows = crm_load(username, 'staff')
        ident = crm_text(payload.get('id'))
        old = rows.get(ident)
        if ident and not old:
            return {'ok': False, 'error': '人员不存在，请刷新'}
        if old and payload.get('version') != old.get('version'):
            return {'ok': False, 'error': '人员已被修改，请刷新'}
        name = crm_text(payload.get('name'), 80)
        key = old['member_key'] if old else crm_text(payload.get('member_key'), 80) or name
        if not name or not key:
            return {'ok': False, 'error': '请填写姓名'}
        if any(r['member_key'] == key and r['id'] != ident for r in rows.values()):
            return {'ok': False, 'error': '对接标识已存在；同名人员请填写不同工号作为标识'}
        parent = crm_text(payload.get('manager_id'))
        if parent and parent not in rows:
            return {'ok': False, 'error': '请先登记直接上级'}
        cursor, seen = parent, {ident}
        while cursor:
            if cursor in seen:
                return {'ok': False, 'error': '汇报关系不能形成循环'}
            seen.add(cursor); cursor = rows[cursor].get('manager_id', '')
        region = crm_text(payload.get('business_region'))
        if region and region not in CRM_BUSINESS_REGIONS:
            return {'ok': False, 'error': '经营区域请选择东区、西区、中区或广东区'}
        record = dict(old or {}, id=ident or crm_new_id('staff'), name=name, member_key=key,
            company=crm_text(payload.get('company'),120), department=crm_text(payload.get('department'),120),
            title=crm_text(payload.get('title'),80), manager_id=parent, business_region=region,
            responsibilities=crm_text(payload.get('responsibilities'),1000), updated_at=crm_now(),
            version=(old or {}).get('version',0)+1)
        if dry_run: return {'ok': True, 'staff': record}
        rows[record['id']] = record
        crm_store(username, 'staff', rows)
        crm_on_change(username)
        return {'ok': True, 'staff': record}


def crm_member_resolver():
    """Request-local staff index: read each owner's directory once, not per row."""
    directories = {}
    accounts, names = {}, {}
    for user in read_config().get('users', []):
        for alias in set(filter(None, [user.get('username'), user.get('employee_id')])):
            accounts.setdefault(alias, []).append(user)
        if crm_text(user.get('name')):
            names.setdefault(crm_text(user.get('name')), []).append(user)
    def resolve(username, key):
        key = crm_text(key)
        if not key:
            return None, '—'
        if username not in directories:
            directories[username] = {p.get('member_key'): p for p in crm_load(username, 'staff').values()}
        profile = directories[username].get(crm_text(key))
        matches = accounts.get(crm_text(key), [])
        if not matches:
            matches = names.get(crm_text(key), [])
        if not matches and profile:
            matches = names.get(crm_text(profile.get('name')), [])
        if len(matches) == 1:
            user = matches[0]
            # Account directory data identifies the login, while the CRM staff
            # profile is the source of truth for the person's organization.
            # Do not erase imported company/department/title merely because the
            # account configuration leaves those optional fields blank.
            profile = dict(profile or {}, member_key=key, username=user['username'],
                           name=(profile or {}).get('name') or user.get('name') or user['username'],
                           company=(profile or {}).get('company') or user.get('company') or '',
                           department=(profile or {}).get('department') or user.get('department') or '',
                           title=(profile or {}).get('title') or user.get('position') or '')
        label = ' · '.join(v for v in [profile.get('name'), profile.get('department'), profile.get('title')] if v) if profile else key or '—'
        return dict(profile) if profile else None, label
    return resolve


def crm_member_profile(username, key):
    key = crm_text(key)
    return next((dict(p) for p in crm_load(username, 'staff').values() if p['member_key'] == key), None)


def crm_member_label(username, key):
    p = crm_member_profile(username, key)
    return ' · '.join(v for v in [p['name'], p.get('department'), p.get('title')] if v) if p else key or '—'
