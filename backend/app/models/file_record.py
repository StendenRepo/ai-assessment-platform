import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.database import Base


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=True)
    path = Column(String, nullable=False)
    file_type = Column(String)
    size_bytes = Column(Integer)
    hash = Column(String)  # SHA-256
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    # Retention: recordings are flagged for deletion after delete_after passes (GDPR).
    delete_after = Column(DateTime, nullable=True)
    flagged_for_deletion = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deleted_at = Column(DateTime, nullable=True)
    # Number of times the retention expiry has been extended (GDPR cap: max 2).
    extension_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Plain text extracted from the uploaded document at (re-)upload time.
    # This is what the AI retrieval (TF-IDF) reads — keeping it current on
    # replace is the point of G2-105. Nullable: extraction is best-effort, so
    # an unparseable file leaves this empty rather than blocking the upload.
    extracted_text = Column(Text, nullable=True)
