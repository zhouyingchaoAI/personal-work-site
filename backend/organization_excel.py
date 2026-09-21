"""Admin-only company organization Excel export and additive profile updates."""

ORGANIZATION_EXCEL_HEADERS = ['工号', '姓名', '账号', '公司', '部门', '岗位', '系统角色']


def organization_cell_text(cell):
    value = cell.value
    if value is None:
        return ''
    if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer():
        text = str(int(value))
        if re.fullmatch(r'0+', cell.number_format or ''):
            return text.zfill(len(cell.number_format))
        return text
    return str(value).strip()


def organization_default_username(name, existing):
    from pypinyin import lazy_pinyin
    base = ''.join(lazy_pinyin(name)).lower()
    base = re.sub(r'[^a-z0-9]', '', base)[:32]
    if len(base) < 2:
        raise ValueError('姓名无法生成拼音账号，请人工开户')
    candidate, number = base, 2
    while candidate in existing:
        candidate = f'{base}{number}'
        number += 1
    return candidate


def organization_excel_export():
    book = Workbook()
    sheet = book.active
    sheet.title = '组织架构'
    sheet.append(ORGANIZATION_EXCEL_HEADERS)
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = 'A1:G1'
    for cell in sheet[1]:
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = PatternFill('solid', fgColor='174B91')
        cell.alignment = Alignment(vertical='center')
    sheet.row_dimensions[1].height = 26
    widths = [16, 16, 20, 32, 48, 24, 16]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
    for user in sorted(read_config().get('users', []), key=lambda item: (str(item.get('company') or ''), str(item.get('department') or ''), str(item.get('employee_id') or item.get('username') or ''))):
        sheet.append([
            user.get('employee_id', ''), user.get('name', ''), user.get('username', ''),
            user.get('company', ''), user.get('department', ''), user.get('position', ''), user.get('role', 'member'),
        ])
    guide = book.create_sheet('填写说明')
    roster = read_config().get('organization_roster', [])
    if roster:
        roster_sheet = book.create_sheet('岗位名册')
        roster_headers = list(dict.fromkeys(k for entry in roster for k in entry.get('values', {})))
        roster_sheet.append(roster_headers + ['绑定账号', '绑定状态'])
        for entry in roster:
            roster_sheet.append([entry.get('values', {}).get(k, '') for k in roster_headers] +
                                [entry.get('username', ''), entry.get('status', '')])
    for line in [
        '公司组织架构表：下载后可直接修改“公司、部门、岗位”列并上传。',
        '优先按账号、工号识别；新工号可绑定唯一同名且尚无工号的账号，身份冲突须人工核对。工号按文本保存。',
        '空白组织字段不会清空原资料；系统角色、账号、姓名仅用于识别，不会被本次导入修改。',
        '勾选自动开户时可为未匹配人员创建普通成员；不会重置已有密码、调整角色或助手权限。仅超级管理员可操作。',
        '请保留“组织架构”工作表名称及第一行表头；仅支持 .xlsx，最多 500 行、5MB。',
    ]:
        guide.append([line])
    guide.column_dimensions['A'].width = 105
    for row in guide:
        row[0].alignment = Alignment(wrap_text=True, vertical='center')
        guide.row_dimensions[row[0].row].height = 32
    raw = io.BytesIO()
    book.save(raw)
    book.close()
    return raw.getvalue()


def _organization_directory_update(employee_id, fields):
    if not employee_id:
        return
    path = Path(USER_DATA_DIR) / '_crm_staff_directory.json'
    try:
        directory = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return
    changed = False
    for record in directory.values():
        if str(record.get('member_key', '') or '').strip() != employee_id:
            continue
        if fields['company']:
            record['company'] = fields['company']
        if fields['department']:
            record['department'] = fields['department']
        if fields['position']:
            record['title'] = fields['position']
        changed = True
    if changed:
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(directory, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)


def organization_roster_reconcile(config, identities, source_filename):
    """Mark employee accounts against one complete, successfully parsed roster."""
    checked_at = datetime.now().isoformat(timespec='seconds')
    source_usernames = {str(item.get('username', '') or '').strip() for item in identities}
    source_employees = {str(item.get('employee_id', '') or '').strip() for item in identities}
    source_usernames.discard('')
    source_employees.discard('')
    missing_users = []
    checked = 0
    for user in config.get('users', []):
        employee_id = str(user.get('employee_id', '') or '').strip()
        if user.get('role') == 'superadmin' or not employee_id:
            continue
        checked += 1
        present = user.get('username') in source_usernames or employee_id in source_employees
        user['organization_check'] = {
            'status': 'present' if present else 'missing',
            'checked_at': checked_at,
            'source': source_filename[:240],
        }
        if not present:
            missing_users.append({
                'username': user.get('username', ''), 'name': user.get('name') or user.get('username', ''),
                'employee_id': employee_id, 'company': user.get('company', ''),
                'department': user.get('department', ''), 'position': user.get('position', ''),
            })
    config['organization_roster_check'] = {
        'checked_at': checked_at, 'source': source_filename[:240],
        'checked': checked, 'present': checked - len(missing_users), 'missing': len(missing_users),
    }
    return {**config['organization_roster_check'], 'applied': True, 'missing_users': missing_users}


def organization_excel_import(payload, caller_username):
    if _caller_role(caller_username) != 'superadmin':
        raise PermissionError('只有超级管理员可以导入组织架构表')
    filename = str(payload.get('filename', '') or '')
    encoded = payload.get('data', '')
    if not filename.lower().endswith('.xlsx'):
        raise ValueError('请上传 .xlsx 格式的组织架构表')
    if not isinstance(encoded, str) or len(encoded) > 7 * 1024 * 1024:
        raise ValueError('文件不能超过5MB')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError('文件编码无效') from exc
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('文件不能超过5MB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024 or len(archive.infolist()) > 200:
                raise ValueError('工作簿内容过大')
        book = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('无法读取工作簿，请使用未加密的xlsx文件') from exc
    cached_book = None
    try:
        candidates = []
        required = {'姓名', '在职状态', '一级部门', '二级部门', '岗位', '成本中心'}
        for candidate in book:
            headers = [str(c.value or '').strip() for c in next(candidate.iter_rows(max_row=1), [])]
            if candidate.title == '组织架构' and headers[:7] == ORGANIZATION_EXCEL_HEADERS:
                candidates = [(candidate, headers, False)]
                break
            if required.issubset(headers):
                candidates.append((candidate, headers, True))
        if len(candidates) != 1:
            raise ValueError('请上传一个岗位信息工作表（姓名、在职状态、一级部门、二级部门、岗位、成本中心），或下载的组织架构模板')
        sheet, headers, position_sheet = candidates[0]
        if sheet.max_row > 501 or sheet.max_column > 20:
            raise ValueError('单次最多导入500行，请删除多余行列')
        rows = list(sheet.iter_rows())
        cached_book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        cached_rows = list(cached_book[sheet.title].iter_rows())
        def import_cell(cell, row_index, column_index):
            if cell.data_type == 'f' and headers[column_index] == '工号':
                return organization_cell_text(cached_rows[row_index][column_index])
            return organization_cell_text(cell)
        config = read_config()
        users = config.get('users', [])
        result = {'ok': True, 'updated': 0, 'skipped': 0, 'errors': [], 'imported': 0, 'pending': 0, 'notices': [], 'created': 0, 'created_users': []}
        verification_identities = []
        create_users = payload.get('create_users') is True
        source_names = [str(row[headers.index('姓名')].value or '').strip() for row in rows[1:]]
        roster = {entry['key']: entry for entry in config.get('organization_roster', [])}
        by_employee = {}
        for user in users:
            employee = str(user.get('employee_id', '') or '').strip()
            if employee:
                by_employee.setdefault(employee, []).append(user)
        source_employees = [import_cell(row[headers.index('工号')], i, headers.index('工号')) for i, row in enumerate(rows[1:], 1)] if '工号' in headers else []
        by_username = {str(user.get('username', '') or '').strip(): user for user in users}
        for row_number, row in enumerate(rows[1:], 2):
            values = [import_cell(cell, row_number - 1, i) for i, cell in enumerate(row)]
            if not any(values):
                continue
            if position_sheet:
                record = dict(zip(headers, values))
                name = record.get('姓名', '')
                employee_id, username = record.get('工号', ''), record.get('账号', '')
                company, position = record.get('成本中心', ''), record.get('岗位', '')
                department = ' / '.join(record.get(k, '') for k in ('一级部门', '二级部门') if record.get(k, ''))
            else:
                employee_id, name, username, company, department, position, _role = values[:7]
            try:
                if not name and not username and not employee_id:
                    raise ValueError('缺少姓名、账号或工号，无法识别人员')
                if any(cell.data_type == 'f' and headers[i] == '工号' and (not values[i] or cached_rows[row_number - 1][i].data_type == 'e') for i, cell in enumerate(row)):
                    raise ValueError('工号公式没有有效的已保存结果，请在Excel中重新计算并保存，或粘贴为文本')
                if any(cell.data_type == 'f' and headers[i] != '工号' for i, cell in enumerate(row)):
                    raise ValueError('请将公式转为文本或数值后上传')
                values_record = dict(zip(headers, values))
                if not position_sheet or record.get('在职状态') == '在职':
                    verification_identities.append({'username': username, 'employee_id': employee_id, 'name': name})
                identity = username or employee_id or [name, company, department, position]
                key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
                entry = {'key': key, 'values': values_record, 'company': company, 'department': department,
                         'position': position, 'name': name, 'source_row': row_number, 'username': '', 'status': '待绑定账号'}
                roster[key] = entry
                result['imported'] += 1
                employee_matches = by_employee.get(employee_id, [])
                target = by_username.get(username) if username else (employee_matches[0] if len(employee_matches) == 1 else None)
                reason = ''
                if employee_id and source_employees.count(employee_id) > 1:
                    reason = '原表工号重复，请核对后重新上传'
                elif employee_id and len(employee_matches) > 1:
                    reason = '工号对应多个账号，请核对身份'
                elif username and not target:
                    reason = '填写的账号未匹配，请核对身份'
                elif target and employee_id and (any(u is not target for u in employee_matches) or str(target.get('employee_id') or '').strip() not in ('', employee_id)):
                    reason = '账号与工号不一致，不覆盖已有工号'
                elif target and name and str(target.get('name') or '').strip() not in ('', name):
                    reason = '工号或账号对应姓名不一致，请核对身份'
                if not target and not username and name and not reason:
                    matches = [user for user in users if str(user.get('name', '') or '').strip() == name]
                    if len(matches) == 1:
                        target = matches[0]
                        if employee_id and str(target.get('employee_id') or '').strip() not in ('', employee_id):
                            reason = '同名账号已有其他工号，请核对身份'
                    elif len(matches) > 1:
                        reason = '姓名对应多个账号，请补充工号或账号'
                if position_sheet and record.get('在职状态') != '在职':
                    target = None
                    reason = '已保存岗位资料；非在职或状态未填写，不更新登录账号'
                if reason:
                    target = None
                if not target and create_users and not reason:
                    if not name or not company or not department:
                        reason = '自动开户需要姓名、公司和部门'
                    elif source_names.count(name) > 1:
                        reason = '原表姓名重复，请核对身份后单独开户'
                    elif username:
                        reason = '填写的账号或工号未匹配，请核对后开户'
                    else:
                        new_username = organization_default_username(name, by_username)
                        if new_username in by_username:
                            reason = '生成的账号已存在，请核对身份'
                        else:
                            target = {'username': new_username, 'name': name, 'role': 'member',
                                      'employee_id': employee_id, 'email': '', 'company': company[:200],
                                      'department': department[:500], 'position': position[:200],
                                      'password': hash_password(secrets.token_urlsafe(32))}
                            users.append(target)
                            by_username[new_username] = target
                            if employee_id:
                                by_employee[employee_id] = [target]
                            result['created'] += 1
                            result['created_users'].append({'username': new_username, 'name': name})
                            openclaw_sync_user(target, 'upsert')
                if not target:
                    result['pending'] += 1
                    result['notices'].append({'row': row_number, 'error': f'{name}：{reason or "已保存岗位资料，待绑定账号"}'})
                    continue
                entry['username'], entry['status'] = target['username'], '已绑定'
                # Replace the same previously imported position when its new ID changes the roster key.
                for old_key, old in list(roster.items()):
                    if old_key != entry['key'] and old.get('username') == target['username'] and all(old.get(k) == entry.get(k) for k in ('name', 'company', 'department', 'position')):
                        del roster[old_key]
                fields = {'company': company[:200], 'department': department[:500], 'position': position[:200]}
                if employee_id:
                    fields['employee_id'] = employee_id
                    by_employee[employee_id] = [target]
                changed = any(value and str(target.get(key, '') or '') != value for key, value in fields.items())
                if not changed:
                    if not any(u['username'] == target['username'] for u in result['created_users']):
                        result['skipped'] += 1
                    continue
                for key, value in fields.items():
                    if value:
                        target[key] = value
                _organization_directory_update(str(target.get('employee_id', '') or '').strip(), fields)
                openclaw_sync_user(target, 'upsert')
                result['updated'] += 1
            except (ValueError, TypeError) as exc:
                result['errors'].append({'row': row_number, 'error': f'{name or username or employee_id}：{exc}'})
        if result['imported']:
            config['organization_roster'] = list(roster.values())
            if result['errors']:
                result['roster_check'] = {
                    'applied': False, 'reason': '存在格式错误，本次未更新缺席标记',
                    'missing_users': [],
                }
            else:
                result['roster_check'] = organization_roster_reconcile(config, verification_identities, filename)
            write_config(config)
        return result
    finally:
        if cached_book:
            cached_book.close()
        book.close()
