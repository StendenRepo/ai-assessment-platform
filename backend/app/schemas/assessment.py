"""Pydantic models for assessment draft, override, chat, and finalization."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceRefOut(BaseModel):
    evidence_id: Optional[str] = None
    file_name: Optional[str] = None
    quote: Optional[str] = None
    confidence: Optional[float] = None
    missing_note: Optional[str] = None


class CriterionValueOut(BaseModel):
    score: Optional[float] = None
    comment: Optional[str] = None
    generated_at: Optional[datetime] = None
    overridden_at: Optional[datetime] = None
    confidence: Optional[float] = None
    refined_via_chat: Optional[bool] = None
    evidence_refs: list[EvidenceRefOut] = Field(default_factory=list)


class OverlapAlertOut(BaseModel):
    signal_id: str
    status: str
    confidence: float
    other_student_id: str
    overlap_type: str
    snippet: Optional[str] = None


class CriterionDefOut(BaseModel):
    key: str
    name: str
    description: str
    max_score: float = 10
    category: str = "General"


class CriterionDraftOut(BaseModel):
    key: str
    definition: CriterionDefOut
    ai: Optional[CriterionValueOut] = None
    teacher: Optional[CriterionValueOut] = None
    effective: Optional[CriterionValueOut] = None
    is_overridden: bool = False


class TextFieldOut(BaseModel):
    ai: Optional[str] = None
    teacher: Optional[str] = None
    effective: Optional[str] = None


class DraftFormOut(BaseModel):
    assessment_id: str
    status: str
    locked: bool
    version: int = 1
    generated_at: Optional[datetime] = None
    criteria: list[CriterionDraftOut] = Field(default_factory=list)
    summary: TextFieldOut = Field(default_factory=TextFieldOut)
    overall_grade: TextFieldOut = Field(default_factory=TextFieldOut)
    overall_score: Optional[float] = None
    evidence_match_count: int = 0
    overlap_alerts: list[OverlapAlertOut] = Field(default_factory=list)
    finalize_blocked_reason: Optional[str] = None
    can_edit: bool = True
    can_chat: bool = True
    can_finalize: bool = False


class CriterionOverrideIn(BaseModel):
    criterion_key: str
    score: Optional[float] = None
    comment: Optional[str] = None


class OverridesPatchIn(BaseModel):
    overrides: list[CriterionOverrideIn]
    summary: Optional[str] = None
    overall_grade: Optional[str] = None


class RevertCriterionIn(BaseModel):
    criterion_key: str


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[dict[str, Any]] = None


class ChatPostIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    criterion_key: Optional[str] = None


class ChatChangeOut(BaseModel):
    criterion_key: str
    criterion_name: str
    before_score: Optional[float] = None
    after_score: Optional[float] = None
    before_comment: Optional[str] = None
    after_comment: Optional[str] = None


class ChatDiscussOut(BaseModel):
    messages: list[ChatMessageOut]
    assistant_reply: str


class ChatProposalOut(BaseModel):
    proposal_id: str
    message_id: str
    reply: str
    proposed_changes: list[ChatChangeOut] = Field(default_factory=list)
    summary_proposed: Optional[str] = None
    updates_requested: int = 0
    messages: list[ChatMessageOut] = Field(default_factory=list)


class ChatApplyIn(BaseModel):
    proposal_id: str


class ChatApplyOut(BaseModel):
    draft: DraftFormOut
    changes_applied: list[ChatChangeOut] = Field(default_factory=list)
    messages: list[ChatMessageOut] = Field(default_factory=list)


class ChatUndoOut(BaseModel):
    draft: DraftFormOut
    changes_restored: list[ChatChangeOut] = Field(default_factory=list)
    messages: list[ChatMessageOut] = Field(default_factory=list)


class FinalizeIn(BaseModel):
    confirm: bool = True
    teacher_notes: Optional[str] = None


class FinalFormOut(BaseModel):
    assessment_id: str
    status: str
    finalized_at: Optional[datetime] = None
    form: dict[str, Any]
    criteria: list[CriterionDraftOut] = Field(default_factory=list)
    summary: Optional[str] = None
    overall_grade: Optional[str] = None
    overall_score: Optional[float] = None
    audit_summary: list[dict[str, Any]] = Field(default_factory=list)


class GenerateDraftOut(BaseModel):
    draft: DraftFormOut
    message: str


class AiItemOut(BaseModel):
    type: str
    timestamp: Optional[datetime] = None
    source: str = "ai"
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ProgressStageOut(BaseModel):
    key: str
    label: str
    status: str
    timestamp: Optional[datetime] = None
    source: Optional[str] = None
    summary: str = ""
    content: dict[str, Any] = Field(default_factory=dict)


class ProgressTrailOut(BaseModel):
    assessment_id: Optional[str] = None
    student_name: str
    student_number: str
    module_name: str = ""
    exported_at: datetime
    stages: list[ProgressStageOut] = Field(default_factory=list)
