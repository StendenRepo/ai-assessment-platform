import enum


class ModuleStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class ProjectStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    archived = "archived"


class StudentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class FileType(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    pptx = "pptx"
    markdown = "markdown"
    image = "image"
    zip = "zip"
    other = "other"


class SourceType(str, enum.Enum):
    upload = "upload"
    github = "github"
    gitlab = "gitlab"


class EmbeddingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AssessmentStatus(str, enum.Enum):
    draft = "draft"
    reviewed = "reviewed"
    final = "final"


class OverlapType(str, enum.Enum):
    textual = "textual"
    semantic = "semantic"


class AuditSource(str, enum.Enum):
    system = "system"
    teacher = "teacher"
    ai = "ai"
