from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RubricScoreOut(BaseModel):
    rubric_id: UUID
    rubric_name: str | None = None
    weight: float | None = None
    score: float | None = None
    grade: str | None = None
    ai_score: float | None = None
    teacher_score: float | None = None
    generated_at: datetime | None = None


class RubricScoreOverride(BaseModel):
    score: float | None = None


class FinalGradeComponent(BaseModel):
    rubric_id: UUID
    rubric_name: str | None = None
    weight: float | None = None
    score: float | None = None
    grade: str | None = None


class FinalGradeOut(BaseModel):
    score: float | None = None
    grade: str | None = None
    total_weight: float | None = None
    components: list[FinalGradeComponent] = []
