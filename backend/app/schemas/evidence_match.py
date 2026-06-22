from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MatchedEvidence(BaseModel):
    evidence_id: UUID
    file_name: str | None
    file_type: str | None = None
    chunk_index: int | None
    supporting_quote: str | None
    confidence_score: float | None
    rationale: str | None = None


class CriterionCoverage(BaseModel):
    criterion_key: str
    covered: bool
    missing_note: str | None
    matches: list[MatchedEvidence]


class GenerationRunSummary(BaseModel):
    run_id: UUID
    created_at: datetime
    mode: str
    ai_model: str | None = None
    ai_used: bool
    criteria_total: int
    criteria_covered: int
    expires_at: datetime | None = None
    expired: bool = False


class EvidenceMatchReport(BaseModel):
    assessment_id: UUID | None
    module_id: UUID | None
    run_id: UUID | None = None
    created_at: datetime | None = None
    mode: str | None = None
    expires_at: datetime | None = None
    criteria: list[CriterionCoverage]
    runs: list[GenerationRunSummary] = []


class RunMatchingRequest(BaseModel):
    module_id: UUID | None = None
    mode: Literal["standard", "thorough"] = "standard"
