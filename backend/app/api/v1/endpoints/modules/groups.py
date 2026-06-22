"""Module API routes — groups."""
from .router import router
from .shared import *  # noqa: F403

@router.get("/{module_id}/groups", response_model=List[ProjectOut])
def list_module_groups(
    module_id: str,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    projects = (
        db.query(Project)
        .filter(Project.module_id == module.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    student_project_map = _build_student_project_map(db, project_ids)

    # Group student counts by project
    student_count_by_project: dict = {}
    for project_id in student_project_map.values():
        student_count_by_project[project_id] = student_count_by_project.get(project_id, 0) + 1

    # Count evidence files per project via student membership and shared project evidence.
    student_ids_by_project: dict = {}
    for sid, pid in student_project_map.items():
        student_ids_by_project.setdefault(pid, []).append(sid)

    all_student_ids = list(student_project_map.keys())
    file_counts: dict = {}
    if all_student_ids:
        for sid, cnt in db.query(Evidence.student_id, func.count(Evidence.id)).filter(
            Evidence.student_id.in_(all_student_ids)
        ).group_by(Evidence.student_id).all():
            pid = student_project_map.get(sid)
            if pid is not None:
                file_counts[pid] = file_counts.get(pid, 0) + cnt

    for pid, cnt in db.query(Evidence.project_id, func.count(Evidence.id)).filter(
        Evidence.project_id.in_(project_ids)
    ).group_by(Evidence.project_id).all():
        file_counts[pid] = file_counts.get(pid, 0) + cnt

    return [
        _group_to_out(
            project,
            student_count_by_project.get(project.id, 0),
            file_counts.get(project.id, 0),
        )
        for project in projects
    ]


@router.post("/{module_id}/groups", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_module_group(
    module_id: str,
    payload: ModuleGroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    project = Project(
        module_id=module.id,
        name=payload.name,
        group_name=payload.group_name or payload.name,
        github_repo_url=payload.github_repo_url,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    audit_service.log_action(
        db,
        action="group.created",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "group_id": str(project.id),
            "group_name": project.group_name or project.name,
            "project_name": project.name,
            "github_repo_url": project.github_repo_url,
            "github_branch": project.github_branch,
            "operation": "create",
            "where": f"Modules > {module.name} > Groups",
            "route": "/api/v1/modules/{module_id}/groups",
        },
        ip_address=request.client.host if request.client else None,
    )

    return _group_to_out(project, 0)


@router.patch("/{module_id}/groups/{group_id}", response_model=ProjectOut)
def update_module_group(
    module_id: str,
    group_id: str,
    payload: ModuleGroupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    updates = payload.model_fields_set
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No group updates provided")

    old_name = group.name
    old_group_name = group.group_name
    old_github_repo_url = group.github_repo_url
    old_github_branch = group.github_branch

    if payload.name is not None:
        group.name = payload.name
    if payload.group_name is not None:
        group.group_name = payload.group_name
    if "github_repo_url" in updates:
        group.github_repo_url = payload.github_repo_url

        # Keep student-level repo references in sync whenever a group repo changes.
        student_ids = [
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == group.id)
            ).all()
        ]
        if student_ids:
            for student in db.query(Student).filter(Student.student_number.in_(student_ids)).all():
                student.github_repo_url = payload.github_repo_url

    if "github_branch" in updates:
        group.github_branch = payload.github_branch

        # Sync branch to all students in this group.
        student_ids = [
            row.student_id
            for row in db.execute(
                student_projects.select().where(student_projects.c.project_id == group.id)
            ).all()
        ]
        if student_ids:
            for student in db.query(Student).filter(Student.student_number.in_(student_ids)).all():
                student.github_branch = payload.github_branch

    repo_removed = old_github_repo_url is not None and group.github_repo_url is None
    repo_added = old_github_repo_url is None and group.github_repo_url is not None
    audit_service.log_action(
        db,
        action="group.updated",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "group_id": str(group.id),
            "old_name": old_name,
            "new_name": group.name,
            "old_group_name": old_group_name,
            "new_group_name": group.group_name,
            "old_github_repo_url": old_github_repo_url,
            "new_github_repo_url": group.github_repo_url,
            "repo_removed": repo_removed,
            "repo_added": repo_added,
            "old_github_branch": old_github_branch,
            "new_github_branch": group.github_branch,
            "branch_changed": old_github_branch != group.github_branch and not repo_removed and not repo_added,
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )

    db.commit()
    db.refresh(group)

    student_count = db.query(student_projects).filter(
        student_projects.c.project_id == group.id
    ).count()
    student_ids = [
        row.student_id
        for row in db.execute(
            student_projects.select().where(student_projects.c.project_id == group.id)
        ).all()
    ]
    file_count = 0
    if student_ids:
        file_count = (
            db.query(func.count(Evidence.id))
            .filter(Evidence.student_id.in_(student_ids))
            .scalar()
            or 0
        )
    return _group_to_out(group, student_count, file_count)


@router.delete("/{module_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module_group(
    module_id: str,
    group_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    from app.services.module_group_service import ModuleGroupService

    module = _get_visible_module_or_404(db, module_id, current_teacher)
    group = (
        db.query(Project)
        .filter(Project.id == group_id, Project.module_id == module.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    group_name = group.group_name or group.name
    group_id_str = str(group.id)
    github_repo_url = group.github_repo_url
    github_branch = group.github_branch

    ModuleGroupService.delete_group(module, group, db)

    audit_service.log_action(
        db,
        action="group.deleted",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "module_id": str(module.id),
            "module_name": module.name,
            "group_id": group_id_str,
            "group_name": group_name,
            "github_repo_url": github_repo_url,
            "github_branch": github_branch,
            "operation": "delete",
            "where": f"Modules > {module.name} > Groups",
            "route": "/api/v1/modules/{module_id}/groups/{group_id}",
        },
        ip_address=request.client.host if request.client else None,
        commit=False,
    )
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

