from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.models.teacher import Teacher
from app.services.evidence_service import SUPPORTED_EXTENSIONS, EvidenceService

router = APIRouter()


@router.get(
    "/supported-types",
    summary="List supported upload file types",
)
def get_supported_types():
    """Return the file extensions that are currently accepted for evidence upload."""
    return {"supported_extensions": list(SUPPORTED_EXTENSIONS.keys())}


@router.get(
    "/{evidence_id}/content",
    summary="Read the text content of an evidence file",
)
def get_evidence_content(
    evidence_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """
    Return the raw text content of an evidence file.

    Response shape: `{ "id": "...", "file_name": "...", "content": "..." }`
    """
    evidence, content = EvidenceService.read_content(evidence_id, db)
    return {
        "id": str(evidence.id),
        "file_name": evidence.file_name,
        "content": content,
    }
