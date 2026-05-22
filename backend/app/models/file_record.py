import uuid
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.database import Base


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path = Column(String, nullable=False)
    file_type = Column(String)
    size_bytes = Column(Integer)
    hash = Column(String)  # SHA-256
    uploaded_at = Column(DateTime, default=datetime.utcnow)
