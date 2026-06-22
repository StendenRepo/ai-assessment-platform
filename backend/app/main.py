from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models.enums import AuditSource
from app.models.teacher import Teacher
from app.services import audit_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


_AUDIT_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
_AUDIT_SKIP_PATH_PREFIXES = (
    f"{settings.API_V1_PREFIX}/auth",
    f"{settings.API_V1_PREFIX}/notifications",
    f"{settings.API_V1_PREFIX}/admin/audit-events",
)
_AUDIT_SKIP_PATTERNS = (
    "/rubric",
    "/module-book",
)

_METHOD_OPERATION = {
    "POST": "created",
    "PATCH": "updated",
    "PUT": "updated",
    "DELETE": "deleted",
}


def _resolve_actor(request: Request, db):
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None, None, AuditSource.system

    token = auth.split(" ", 1)[1].strip()
    subject = decode_access_token(token)
    if not subject:
        return None, None, AuditSource.system

    teacher = db.query(Teacher).filter(Teacher.id == subject).first()
    if not teacher:
        return None, None, AuditSource.system

    teacher_id = _as_uuid(getattr(teacher, "id", None))
    teacher_name = getattr(teacher, "name", None)
    if teacher_name is not None:
        teacher_name = str(teacher_name)

    return teacher_id, teacher_name, AuditSource.teacher


def _humanize_segment(segment: str) -> str:
    return segment.replace("-", " ").replace("_", " ").strip().title()


def _action_and_where(path: str, route_template: str, method: str) -> tuple[str, str, str]:
    operation = _METHOD_OPERATION.get(method, method.lower())
    relative = route_template
    if relative.startswith(settings.API_V1_PREFIX):
        relative = relative[len(settings.API_V1_PREFIX):]

    parts = [p for p in relative.split("/") if p and not p.startswith("{")]
    if not parts:
        return f"api.{method.lower()}", operation, "API"

    resource = parts[-1]
    # Normalize common plural resource names for cleaner audit action labels.
    if resource.endswith("s") and len(resource) > 1:
        resource = resource[:-1]
    resource = resource.replace("-", "_")

    action = f"{resource}.{operation}"
    where = " > ".join(_humanize_segment(part) for part in parts)
    return action, operation, where


def _as_uuid(value):
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _extract_path_params(route_template: str, path: str) -> dict:
    """Extract path parameters by matching the URL path against the route template."""
    import re

    # Convert route template to regex: /api/v1/modules/{module_id}/rubric -> regex pattern
    pattern = route_template
    param_names = []

    # Find all {param_name} placeholders
    for match in re.finditer(r'\{(\w+)\}', pattern):
        param_names.append(match.group(1))

    # Replace placeholders with regex groups
    pattern = re.sub(r'\{(\w+)\}', r'([^/]+)', pattern)
    pattern = f"^{pattern}$"

    try:
        match = re.match(pattern, path)
        if match:
            return dict(zip(param_names, match.groups()))
    except Exception:
        pass

    return {}


def _build_entity_context(db, path_params: dict) -> dict:
    context = {}

    module_id = _as_uuid(path_params.get("module_id"))
    project_id = _as_uuid(path_params.get("project_id"))
    group_id = _as_uuid(path_params.get("group_id"))
    evidence_id = _as_uuid(path_params.get("evidence_id"))
    student_id = path_params.get("student_id")

    if module_id:
        from app.models.module import Module

        module = db.query(Module).filter(Module.id == module_id).first()
        if module:
            context["module_id"] = str(module.id)
            context["module_name"] = module.name

    if project_id:
        from app.models.module import Module
        from app.models.project import Project

        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            context["project_id"] = str(project.id)
            context["project_name"] = project.name
            context["group_name"] = project.group_name or project.name
            if "module_name" not in context:
                module = db.query(Module).filter(Module.id == project.module_id).first()
                if module:
                    context["module_id"] = str(module.id)
                    context["module_name"] = module.name

    if group_id:
        from app.models.module import Module
        from app.models.project import Project

        group = db.query(Project).filter(Project.id == group_id).first()
        if group:
            context["group_id"] = str(group.id)
            context["group_name"] = group.group_name or group.name
            context["project_name"] = group.name
            if "module_name" not in context:
                module = db.query(Module).filter(Module.id == group.module_id).first()
                if module:
                    context["module_id"] = str(module.id)
                    context["module_name"] = module.name

    if student_id:
        from app.models.student import Student

        student = db.query(Student).filter(Student.student_number == str(student_id)).first()
        if student:
            context["student_id"] = student.student_number
            context["student_name"] = student.name
        else:
            context["student_id"] = str(student_id)

    if evidence_id:
        from app.models.evidence import Evidence

        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if evidence:
            context["evidence_id"] = str(evidence.id)
            context["file_name"] = evidence.file_name
            if evidence.project_id and "project_id" not in context:
                context["project_id"] = str(evidence.project_id)
            if evidence.student_id and "student_id" not in context:
                context["student_id"] = evidence.student_id

    return context


@app.middleware("http")
async def auto_audit_mutations(request: Request, call_next):
    response = await call_next(request)

    method = request.method.upper()
    path = request.url.path
    if method not in _AUDIT_METHODS:
        return response
    if not path.startswith(settings.API_V1_PREFIX):
        return response
    if any(path.startswith(prefix) for prefix in _AUDIT_SKIP_PATH_PREFIXES):
        return response
    if any(pattern in path for pattern in _AUDIT_SKIP_PATTERNS):
        return response
    # Skip module creation, rename, delete (all have explicit audit logging)
    if "/modules" in path and path.count("/") <= 4:
        if method == "POST" and path.count("/") == 3:  # POST /api/v1/modules (create)
            return response
        if method in ("PATCH", "DELETE") and path.count("/") == 4:  # PATCH/DELETE /api/v1/modules/{id}
            return response
    # Skip group and student operations (all have explicit audit logging)
    if "/groups" in path or "/students" in path:
        return response
    if response.status_code >= 400:
        return response

    db = SessionLocal()
    try:
        teacher_id, teacher_name, source = _resolve_actor(request, db)
        route_template = getattr(request.scope.get("route"), "path", path)
        action, operation, where = _action_and_where(path, route_template, method)
        path_params = _extract_path_params(route_template, path)
        entity_context = _build_entity_context(db, path_params)
        audit_service.log_action(
            db,
            action=action,
            source=source,
            teacher_id=teacher_id,
            teacher_name=teacher_name,
            details={
                "operation": operation,
                "where": where,
                "route": route_template,
                "path": path,
                "status_code": response.status_code,
                "query": request.url.query or None,
                "path_params": path_params or None,
                **entity_context,
            },
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        # Audit logging must not break user-facing API behavior.
        pass
    finally:
        db.close()

    return response


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"message": "AI Assessment Service Running"}
