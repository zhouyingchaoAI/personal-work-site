"""Project assistant: project membership, materials and report timeline.

Projects are shared records under ``user_data/projects``.  The project itself
is the authorization boundary; reports and diaries remain owned by the user
that created them and only store a lightweight project id for aggregation.
"""

PROJECT_MEMBER_ROLES = {
    "manager": "项目管理员",
    "echo": "回声",
    "delta": "三角洲",
}

# 兼容首版项目数据：原“项目成员/只读成员”无权限差异，分别迁移到新角色。
PROJECT_MEMBER_ROLE_ALIASES = {"member": "echo", "viewer": "delta"}


def project_root_dir():
    return USER_DATA_DIR / "projects"


def project_index_path():
    return project_root_dir() / "projects.json"


def _project_now():
    return datetime.now().isoformat(timespec="seconds")


def _project_read_all():
    data = office_doc_read("project", project_index_path(), [])
    return data if isinstance(data, list) else []


def _project_write_all(projects):
    office_doc_write("project", project_index_path(), projects)


def _project_id():
    return "project-" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3)


def _project_normalize_member(item):
    if isinstance(item, str):
        item = {"username": item}
    username = safe_username(str((item or {}).get("username", "") or ""))
    if not username:
        return None
    return {
        "username": username,
        "roles": _project_member_roles(item),
        "joined_at": str((item or {}).get("joined_at", "") or _project_now()),
    }


def _project_member_roles(member):
    raw_roles = (member or {}).get("roles")
    if not isinstance(raw_roles, list):
        raw_roles = [(member or {}).get("role", "echo")]
    roles = []
    for raw_role in raw_roles:
        role = PROJECT_MEMBER_ROLE_ALIASES.get(str(raw_role or "").strip().lower(), str(raw_role or "").strip().lower())
        if role in PROJECT_MEMBER_ROLES and role not in roles:
            roles.append(role)
    return roles or ["echo"]


def _project_public(project):
    result = deepcopy(project)
    result["members"] = [
        {
            **member,
            "roles": _project_member_roles(member),
            "role_name": "、".join(PROJECT_MEMBER_ROLES[role] for role in _project_member_roles(member)),
        }
        for member in (project.get("members") or [])
    ]
    return result


def project_is_platform_admin(username):
    user = find_user(username) or {}
    if user.get("role") == "superadmin":
        return True
    configured = {safe_username(item) for item in (read_config().get("project_admins") or [])}
    return safe_username(username) in configured


def project_member(project, username):
    username = safe_username(username)
    return next((item for item in (project.get("members") or []) if item.get("username") == username), None)


def project_can_view(project, username):
    return project_is_platform_admin(username) or bool(project_member(project, username))


def project_can_manage(project, username):
    member = project_member(project, username)
    return project_is_platform_admin(username) or bool(member and "manager" in _project_member_roles(member))


def _project_find(project_id):
    project_id = str(project_id or "").strip()
    projects = _project_read_all()
    for index, project in enumerate(projects):
        if project.get("id") == project_id:
            return projects, index, project
    raise ValueError("项目不存在或已删除")


def _project_users():
    return [{"username": item.get("username", ""), "name": item.get("name") or item.get("username", "")} for item in read_config().get("users", [])]


def project_admins_payload(username):
    # 平台级「项目管理员」名单属于权限配置，查看与修改均仅限超级管理员。
    # 项目内管理员仍可维护自己项目的成员、角色和资料，但不能触及平台授权名单。
    if (find_user(username) or {}).get("role") != "superadmin":
        raise PermissionError("只有超级管理员可以查看和配置项目管理员")
    config = read_config()
    selected = {safe_username(item) for item in (config.get("project_admins") or [])}
    return {
        "ok": True,
        "admins": sorted(selected),
        "users": _project_users(),
        "can_configure": True,
    }


def project_save_admins(payload, username):
    if (find_user(username) or {}).get("role") != "superadmin":
        raise PermissionError("只有超级管理员可以配置项目管理员")
    users = {item["username"] for item in _project_users()}
    admins = []
    for item in (payload.get("admins") or []):
        candidate = safe_username(item)
        if candidate in users and candidate not in admins:
            admins.append(candidate)
    config = read_config()
    config["project_admins"] = admins
    write_config(config)
    return project_admins_payload(username)


def project_list(username):
    projects = [project for project in _project_read_all() if project_can_view(project, username)]
    projects.sort(key=lambda item: (item.get("updated_at", ""), item.get("created_at", "")), reverse=True)
    return {
        "ok": True,
        "projects": [_project_public(item) for item in projects],
        "can_create": project_is_platform_admin(username),
        "can_configure_admins": (find_user(username) or {}).get("role") == "superadmin",
    }


def project_get(project_id, username):
    _, _, project = _project_find(project_id)
    if not project_can_view(project, username):
        raise PermissionError("你不是该项目成员")
    return {"ok": True, "project": _project_public(project), "can_manage": project_can_manage(project, username)}


def project_create(payload, username):
    if not project_is_platform_admin(username):
        raise PermissionError("只有平台项目管理员可以创建项目")
    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise ValueError("请填写项目名称")
    now = _project_now()
    members = []
    for raw in [{"username": username, "role": "manager"}, *(payload.get("members") or [])]:
        member = _project_normalize_member(raw)
        if member and member["username"] not in {item["username"] for item in members}:
            members.append(member)
    project = {
        "id": _project_id(),
        "name": name[:100],
        "description": str(payload.get("description", "") or "").strip()[:4000],
        "status": "active",
        "creator": safe_username(username),
        "members": members,
        "files": [],
        "reports": [],
        "created_at": now,
        "updated_at": now,
    }
    projects = _project_read_all()
    projects.append(project)
    _project_write_all(projects)
    return {"ok": True, "project": _project_public(project)}


def project_update(payload, username):
    projects, index, project = _project_find(payload.get("id", ""))
    if not project_can_manage(project, username):
        raise PermissionError("只有项目管理员可以维护该项目")
    for field, limit in (("name", 100), ("description", 4000), ("status", 20)):
        if field in payload:
            value = str(payload.get(field, "") or "").strip()[:limit]
            if field == "name" and not value:
                raise ValueError("项目名称不能为空")
            if field == "status" and value not in {"active", "archived"}:
                raise ValueError("项目状态无效")
            project[field] = value
    project["updated_at"] = _project_now()
    projects[index] = project
    _project_write_all(projects)
    return {"ok": True, "project": _project_public(project)}


def project_delete(payload, username):
    projects, index, project = _project_find(payload.get("id", ""))
    if not project_can_manage(project, username):
        raise PermissionError("只有项目管理员可以删除该项目")

    # 项目目录只存放项目内上传的资料；日报、周报等个人文件位于各自用户目录，
    # 删除项目时保留它们。先移除索引，再清理该项目的资料。
    root = project_root_dir().resolve()
    target = (project_root_dir() / project["id"]).resolve()
    if target.parent != root:
        raise ValueError("项目目录无效")
    remaining = projects[:index] + projects[index + 1:]
    _project_write_all(remaining)
    office_blob_delete_tree("project", project_root_dir() / project["id"])
    return {"ok": True, "deleted_id": project["id"]}


def project_save_members(payload, username):
    projects, index, project = _project_find(payload.get("id", ""))
    if not project_can_manage(project, username):
        raise PermissionError("只有项目管理员可以维护成员")
    known_users = {item["username"] for item in _project_users()}
    members = []
    for raw in (payload.get("members") or []):
        member = _project_normalize_member(raw)
        if member and member["username"] in known_users and member["username"] not in {item["username"] for item in members}:
            members.append(member)
    if not any("manager" in _project_member_roles(item) for item in members):
        manager = project_member(project, username) or project_member(project, project.get("creator", ""))
        if manager:
            members.insert(0, manager)
    project["members"] = members
    project["updated_at"] = _project_now()
    projects[index] = project
    _project_write_all(projects)
    return {"ok": True, "project": _project_public(project)}


def project_upload_file(payload, username):
    projects, index, project = _project_find(payload.get("id", ""))
    if not project_can_manage(project, username):
        raise PermissionError("只有项目管理员可以上传项目资料")
    name = Path(str(payload.get("name", "") or "")).name
    encoded = str(payload.get("content_base64", "") or "")
    if not name or not encoded:
        raise ValueError("请选择项目资料")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("项目资料编码无效") from exc
    if len(raw) > 30 * 1024 * 1024:
        raise ValueError("项目资料不能超过 30MB")
    file_id = "file-" + secrets.token_hex(6)
    directory = project_root_dir() / project["id"] / "files"
    stored_name = f"{file_id}-{name}"
    office_blob_write("project", directory / stored_name, raw, content_type=mimetypes.guess_type(name)[0])
    item = {"id": file_id, "name": name, "stored_name": stored_name, "size": len(raw), "uploaded_by": safe_username(username), "created_at": _project_now()}
    project.setdefault("files", []).append(item)
    project["updated_at"] = _project_now()
    projects[index] = project
    _project_write_all(projects)
    return {"ok": True, "file": item, "project": _project_public(project)}


def project_file(project_id, file_id, username):
    _, _, project = _project_find(project_id)
    if not project_can_view(project, username):
        raise PermissionError("你不是该项目成员")
    item = next((file for file in (project.get("files") or []) if file.get("id") == file_id), None)
    if not item:
        raise ValueError("项目资料不存在")
    path = project_root_dir() / project["id"] / "files" / item.get("stored_name", "")
    raw = office_blob_read("project", path)
    if raw is None:
        raise ValueError("项目资料已丢失")
    return item["name"], raw


def project_report_file(project_id, report_id, username):
    _, _, project = _project_find(project_id)
    if not project_can_view(project, username):
        raise PermissionError("你不是该项目成员")
    item = next((report for report in (project.get("reports") or []) if report.get("id") == report_id), None)
    if not item:
        raise ValueError("项目报告不存在")
    path = Path(str(item.get("path", "") or ""))
    try:
        path.resolve().relative_to(USER_DATA_DIR.resolve())
    except ValueError as exc:
        raise ValueError("项目报告路径无效") from exc
    # 报告文件属于周报/出差报告助手，按其存储模式读取（键即原路径）。
    raw = office_blob_read("reports", path)
    if raw is None:
        raise ValueError("项目报告文件不存在")
    return item.get("name") or path.name, raw


def project_record_report(project_id, kind, path, username, payload=None):
    if not project_id:
        return None
    projects, index, project = _project_find(project_id)
    if not project_can_view(project, username):
        raise PermissionError("你不是该项目成员，不能关联报告")
    path = Path(path)
    item = {
        "id": "report-" + secrets.token_hex(6),
        "type": "weekly" if kind == "weekly" else "trip",
        "name": path.name,
        "path": str(path),
        "author": safe_username(username),
        "period": str((payload or {}).get("period", "") or ""),
        "created_at": _project_now(),
    }
    project.setdefault("reports", []).append(item)
    project["updated_at"] = item["created_at"]
    projects[index] = project
    _project_write_all(projects)
    return item


def project_timeline(project_id, username):
    _, _, project = _project_find(project_id)
    if not project_can_view(project, username):
        raise PermissionError("你不是该项目成员")
    timeline = []
    for item in (project.get("files") or []):
        timeline.append({"type": "material", "title": item.get("name", ""), "author": item.get("uploaded_by", ""), "created_at": item.get("created_at", ""), "file": item})
    for item in (project.get("reports") or []):
        timeline.append({"type": item.get("type", "weekly"), "title": item.get("name", ""), "author": item.get("author", ""), "created_at": item.get("created_at", ""), "report": item})
    for member in (project.get("members") or []):
        member_name = member.get("username", "")
        for diary in (list_diaries({}, member_name).get("diaries") or []):
            project_ids = diary.get("project_ids") or ([diary.get("project_id")] if diary.get("project_id") else [])
            if project["id"] in project_ids:
                project_notes = diary.get("project_notes") if isinstance(diary.get("project_notes"), dict) else {}
                timeline.append({"type": "daily", "title": project_notes.get(project["id"]) or diary.get("today_work_preview") or "工作日报", "author": member_name, "created_at": diary.get("updated_at") or f"{diary.get('date', '')}T23:59:59", "diary": diary})
    timeline.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    can_manage = project_can_manage(project, username)
    return {
        "ok": True,
        "project": _project_public(project),
        "timeline": timeline,
        "can_manage": can_manage,
        "users": _project_users() if can_manage else [],
    }
