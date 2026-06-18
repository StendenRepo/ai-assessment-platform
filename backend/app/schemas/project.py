from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator


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


class StudentCreate(BaseModel):
    name: str
    student_number: str
    project_id: Optional[str] = None  # optional group hint used by the modules endpoint
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    @field_validator("name", "student_number")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("student_number")
    @classmethod
    def _digits_only(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("student number must contain digits only")
        return value

    @field_validator("github_repo_url")
    @classmethod
    def _normalize_repo_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_github_repo_url(value)


class StudentOut(BaseModel):
    id: str
    name: str
    student_number: str
    status: str
    consent_given: bool = False
    assessment_status: str = "not-started"
    grade: Optional[str] = None
    project_id: Optional[str] = None  # populated in module context to identify the student's group
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: str
    name: str
    group_name: Optional[str] = None
    module_id: str
    status: str
    created_at: Optional[datetime] = None
    student_count: int = 0
    file_count: int = 0
    github_repo_url: Optional[str] = None
    github_branch: Optional[str] = None

    model_config = {"from_attributes": True}


class ImportRowError(BaseModel):
    row: int
    student_number: Optional[str] = None
    message: str


class StudentImportResult(BaseModel):
    imported_count: int
    error_count: int
    total_rows: int
    errors: List[ImportRowError]
    students: List[StudentOut]
