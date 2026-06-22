"""Shared imports for module route handlers."""
import mimetypes
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.config import settings
from app.models.assessment import Assessment
from app.models.enums import AuditSource, ProjectStatus, StudentStatus
from app.models.evidence import Evidence
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student, student_projects
from app.models.teacher import Teacher
from app.schemas.module import (
    ModuleCreate,
    ModuleGroupCreate,
    ModuleGroupUpdate,
    ModuleOut,
    RubricFileOut,
    StudentGroupUpdate,
)
from app.schemas.overlap import OverlapAnalysisOut, OverlapSignalOut, OverlapWarningOut
from app.schemas.project import (
    ImportRowError,
    ProjectOut,
    StudentCreate,
    StudentImportResult,
    StudentOut,
)
from app.services import audit_service
from app.services.module_group_service import DEFAULT_GROUP_NAME as _DEFAULT_GROUP_NAME
from app.services.module_service import (
    MODULE_BOOK_UPLOAD_DIR,
    RUBRIC_UPLOAD_DIR,
    ModuleService,
    _module_file_path,
)
from app.services.overlap.service import OverlapService
from app.services.student_import import ImportParseError, parse_student_file

from .constants import DUPLICATE_DETAIL as _DUPLICATE_DETAIL
from .deps import (
    _build_student_project_map,
    _get_or_create_default_group,
    _get_visible_module_or_404,
    _module_project_counts,
    _module_project_ids,
    _module_signal_context,
    _resolve_group_for_module,
    _student_duplicate_in_module,
    _students_in_projects,
    _visible_modules_query,
)
from .mappers import (
    _assessment_grade,
    _assessment_status,
    _group_to_out,
    _module_to_out,
    _signal_to_out,
    _student_to_out,
)

# `from .shared import *` skips names starting with `_` unless listed in __all__.
__all__ = [
    "APIRouter",
    "Assessment",
    "AuditSource",
    "Depends",
    "Evidence",
    "File",
    "FileRecord",
    "FileResponse",
    "HTTPException",
    "ImportParseError",
    "ImportRowError",
    "IntegrityError",
    "List",
    "MODULE_BOOK_UPLOAD_DIR",
    "Module",
    "ModuleCreate",
    "ModuleGroupCreate",
    "ModuleGroupUpdate",
    "ModuleOut",
    "ModuleService",
    "Optional",
    "OverlapAnalysisOut",
    "OverlapService",
    "OverlapSignalOut",
    "OverlapWarningOut",
    "Project",
    "ProjectOut",
    "ProjectStatus",
    "Query",
    "RUBRIC_UPLOAD_DIR",
    "Request",
    "Response",
    "Session",
    "StreamingResponse",
    "Student",
    "StudentCreate",
    "StudentGroupUpdate",
    "StudentImportResult",
    "StudentOut",
    "StudentStatus",
    "Teacher",
    "UploadFile",
    "audit_service",
    "func",
    "get_current_teacher",
    "get_db",
    "mimetypes",
    "parse_student_file",
    "settings",
    "status",
    "student_projects",
    "_DEFAULT_GROUP_NAME",
    "_DUPLICATE_DETAIL",
    "_assessment_grade",
    "_assessment_status",
    "_build_student_project_map",
    "_get_or_create_default_group",
    "_get_visible_module_or_404",
    "_group_to_out",
    "_module_file_path",
    "_module_project_counts",
    "_module_project_ids",
    "_module_signal_context",
    "_module_to_out",
    "_resolve_group_for_module",
    "_signal_to_out",
    "_student_duplicate_in_module",
    "_student_to_out",
    "_students_in_projects",
    "_visible_modules_query",
]
