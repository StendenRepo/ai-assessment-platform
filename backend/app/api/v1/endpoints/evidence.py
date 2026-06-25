from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_teacher, get_db
from app.core import crypto
from app.models.teacher import Teacher
from app.services import audit_service
from app.services.evidence_service import SUPPORTED_EXTENSIONS, EvidenceService

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """
    Return the raw text content of an evidence file.

    Response shape: `{ "id": "...", "file_name": "...", "content": "..." }`
    """
    evidence, content = EvidenceService.read_content(evidence_id, db, current_teacher)
    audit_service.log_action(
        db,
        action="document.viewed",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "kind": "evidence",
            "evidence_id": str(evidence.id),
            "file_name": evidence.file_name,
        },
        ip_address=_client_ip(request),
    )
    return {
        "id": str(evidence.id),
        "file_name": evidence.file_name,
        "content": content,
    }


@router.get(
    "/{evidence_id}/file",
    summary="Download or preview the raw evidence file",
)
def get_evidence_file(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
):
    """Return the stored raw evidence file for authenticated preview/download."""
    evidence, full_path, media_type = EvidenceService.get_raw_file(
        evidence_id, db, current_teacher
    )
    audit_service.log_action(
        db,
        action="document.viewed",
        teacher_id=current_teacher.id,
        teacher_name=current_teacher.name,
        details={
            "kind": "evidence",
            "evidence_id": str(evidence.id),
            "file_name": evidence.file_name,
        },
        ip_address=_client_ip(request),
    )
    # Files are encrypted at rest (G2-162); decrypt in-process and serve the
    # plaintext from memory rather than streaming the ciphertext on disk.
    data = crypto.read_encrypted_file(full_path)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{evidence.file_name}"'
        },
    )
