from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class OverlapSignalOut(BaseModel):
    id: str
    student_a_id: str
    student_a_name: str
    student_b_id: str
    student_b_name: str
    evidence_a_id: str
    evidence_a_name: str
    evidence_b_id: str
    evidence_b_name: str
    overlap_type: str
    confidence: float
    snippet: Optional[str] = None
    detected_at: datetime


class OverlapWarningOut(BaseModel):
    has_overlap: bool
    high_risk_count: int
    signal_count: int
    warning: str


class OverlapAnalysisOut(BaseModel):
    module_id: str
    generated_count: int
    warning: OverlapWarningOut
    signals: List[OverlapSignalOut]
