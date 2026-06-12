from uuid import UUID

from pydantic import BaseModel


class MatchedEvidence(BaseModel):
    evidence_id: UUID
    file_name: str | None
    chunk_index: int | None
    supporting_quote: str | None
    confidence_score: float | None
    rationale: str | None = None


class CriterionCoverage(BaseModel):
    criterion_key: str
    covered: bool
    missing_note: str | None
    matches: list[MatchedEvidence]


class EvidenceMatchReport(BaseModel):
    assessment_id: UUID | None
    module_id: UUID | None
    criteria: list[CriterionCoverage]


class RunMatchingRequest(BaseModel):
    module_id: UUID | None = None
