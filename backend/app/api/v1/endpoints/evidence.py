from fastapi import APIRouter, Depends, Response, status
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


@router.delete(
    "/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an evidence record and its file on disk",
)
def delete_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    _: Teacher = Depends(get_current_teacher),
):
    """Delete the evidence record from the database and remove the file from disk."""
    EvidenceService.delete(evidence_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
