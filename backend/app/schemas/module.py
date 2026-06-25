from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

from app.models.enums import ModuleStatus


def _normalize_github_repo_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(candidate)
    host = (parsed.netloc or "").lower()
    if host not in {"github.com", "www.github.com"}:
        raise ValueError("github_repo_url must point to github.com")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError("github_repo_url must include owner and repository")

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        raise ValueError("github_repo_url must include owner and repository")

    return f"https://github.com/{owner}/{repo}"


class RubricFileOut(BaseModel):
    id: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModuleRubricOut(BaseModel):
    id: str
    name: Optional[str] = None
    weight: Optional[float] = None
    position: int = 0
    file_id: str
    file_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ModuleRubricUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[float] = None


class ModuleCreate(BaseModel):
    name: str
    academic_year: Optional[str] = None
    deadline: Optional[str] = None

    @field_validator("name", "academic_year", "deadline")
    @classmethod
    def _trim(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


class ModuleGroupCreate(BaseModel):
    name: str
    group_name: Optional[str] = None
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    @field_validator("name", "group_name")
    @classmethod
    def _trim(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @field_validator("github_repo_url")
    @classmethod
    def _normalize_repo_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_github_repo_url(value)


class ModuleGroupUpdate(BaseModel):
    name: Optional[str] = None
    group_name: Optional[str] = None
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    @field_validator("name", "group_name")
    @classmethod
    def _trim_non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("github_repo_url")
    @classmethod
    def _normalize_group_repo_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_github_repo_url(value)


class StudentGroupUpdate(BaseModel):
    project_id: Optional[str] = None
    name: Optional[str] = None
    student_number: Optional[str] = None
    status: Optional[str] = None
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    @field_validator("name", "student_number")
    @classmethod
    def _trim_non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"active", "inactive"}:
            raise ValueError("status must be 'active' or 'inactive'")
        return normalized

    @field_validator("github_repo_url")
    @classmethod
    def _normalize_student_repo_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_github_repo_url(value)


class ModuleStatusUpdate(BaseModel):
    status: ModuleStatus

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        # Accept case-insensitive strings ("Active" -> "active") before the
        # enum coercion runs; invalid values still raise a 422.
        if isinstance(value, str):
            return value.strip().lower()
        return value


class CoTeacherOut(BaseModel):
    id: str
    name: str
    email: str

    model_config = {"from_attributes": True}


class AddCoTeacherRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip().lower()


class BulkMoveStudentsRequest(BaseModel):
    student_ids: list[str]
    target_project_id: str

    @field_validator("student_ids")
    @classmethod
    def _non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("student_ids must not be empty")
        if len(value) > 100:
            raise ValueError("Cannot move more than 100 students at once")
        return value


class BulkMoveResult(BaseModel):
    moved_count: int
    skipped_count: int
    skipped_ids: list[str]


class ModuleOut(BaseModel):
    id: str
    teacher_id: str
    name: str
    academic_year: Optional[str] = None
    deadline: Optional[str] = None
    status: str
    created_at: datetime
    project_count: int = 0
    student_count: int = 0
    rubric_file: Optional[RubricFileOut] = None
    module_book_file: Optional[RubricFileOut] = None

    model_config = {"from_attributes": True}
