from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import EmbeddingStatus, FileType, SourceType


class EvidenceOut(BaseModel):
    id: UUID
    student_id: str
    file_name: str
    file_type: FileType | None
    file_path: str
    source_type: SourceType | None
    embedding_status: EmbeddingStatus
    uploaded_at: datetime
    content: str | None = None  # populated when ?include_content=true

    model_config = {"from_attributes": True}
