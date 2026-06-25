from uuid import UUID

from pydantic import BaseModel


class CriterionQuestions(BaseModel):
    criterion_key: str
    basis: str
    covered: bool
    questions: list[str]


class AssessmentQuestionsReport(BaseModel):
    student_id: str
    module_id: UUID | None = None
    questions: list[CriterionQuestions]


class GenerateQuestionsRequest(BaseModel):
    module_id: UUID | None = None
