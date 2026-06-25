import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ModuleRubric(Base):
    __tablename__ = "module_rubrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id = Column(
        UUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id = Column(
        UUID(as_uuid=True), ForeignKey("file_records.id"), nullable=False
    )
    name = Column(String, nullable=True)
    weight = Column(Float, nullable=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    module = relationship("Module", back_populates="rubrics")
    file = relationship("FileRecord")
