"""Ground AI suggestions in uploaded student evidence via TF-IDF retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.evidence_match import EvidenceMatch
from app.services.evidence_service import EVIDENCE_UPLOAD_DIR
from app.services.text_extraction import read_stored_evidence_text
from app.services.text_chunker import chunk_text

_MIN_SIMILARITY = 0.12
_TOP_K = 3


@dataclass
class MatchedChunk:
    evidence_id: Optional[UUID]
    file_name: str
    chunk_index: int
    quote: str
    confidence: float
    missing_note: Optional[str] = None


def _read_evidence_text(evidence: Evidence) -> str:
    return read_stored_evidence_text(evidence, EVIDENCE_UPLOAD_DIR)


def match_criterion_to_evidence(
    criterion_key: str,
    criterion_name: str,
    criterion_description: str,
    evidence_rows: list[Evidence],
) -> list[MatchedChunk]:
    """Return top evidence chunks for a rubric criterion."""
    query = f"{criterion_name}. {criterion_description}".strip()
    if not evidence_rows:
        return [
            MatchedChunk(
                evidence_id=None,
                file_name="",
                chunk_index=0,
                quote="",
                confidence=0.0,
                missing_note="No evidence uploaded for this student yet.",
            )
        ]

    corpus_chunks: list[tuple[Evidence, int, str]] = []
    for ev in evidence_rows:
        text = _read_evidence_text(ev)
        for idx, chunk in enumerate(chunk_text(text)):
            corpus_chunks.append((ev, idx, chunk))

    if not corpus_chunks:
        return [
            MatchedChunk(
                evidence_id=evidence_rows[0].id,
                file_name=evidence_rows[0].file_name,
                chunk_index=0,
                quote="",
                confidence=0.0,
                missing_note="Evidence files exist but contain no extractable text.",
            )
        ]

    documents = [query] + [c[2] for c in corpus_chunks]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=8000)
    matrix = vectorizer.fit_transform(documents)
    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True,
    )

    results: list[MatchedChunk] = []
    for idx, score in ranked[:_TOP_K]:
        if score < _MIN_SIMILARITY:
            continue
        ev, chunk_index, chunk_text_value = corpus_chunks[idx]
        results.append(
            MatchedChunk(
                evidence_id=ev.id,
                file_name=ev.file_name,
                chunk_index=chunk_index,
                quote=chunk_text_value[:500],
                confidence=round(float(score), 4),
            )
        )

    if not results:
        best_idx = ranked[0][0]
        ev, chunk_index, chunk_text_value = corpus_chunks[best_idx]
        results.append(
            MatchedChunk(
                evidence_id=ev.id,
                file_name=ev.file_name,
                chunk_index=chunk_index,
                quote=chunk_text_value[:500],
                confidence=round(float(ranked[0][1]), 4),
                missing_note="Weak evidence match — review manually.",
            )
        )
    return results


def persist_matches(
    db: Session,
    *,
    assessment_id: UUID,
    criterion_key: str,
    matches: list[MatchedChunk],
) -> None:
    """Replace stored evidence matches for one criterion."""
    (
        db.query(EvidenceMatch)
        .filter(
            EvidenceMatch.assessment_id == assessment_id,
            EvidenceMatch.criterion_key == criterion_key,
        )
        .delete(synchronize_session=False)
    )
    for m in matches:
        if m.evidence_id is None:
            continue
        db.add(
            EvidenceMatch(
                assessment_id=assessment_id,
                criterion_key=criterion_key,
                evidence_id=m.evidence_id,
                chunk_index=m.chunk_index,
                confidence_score=m.confidence,
                supporting_quote=m.quote,
                missing_note=m.missing_note,
            )
        )
