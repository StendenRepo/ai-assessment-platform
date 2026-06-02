from pydantic import BaseModel


class OverlapSummary(BaseModel):
    id: str
    status: str
    scope: str
    student_a_id: str
    student_a_name: str
    student_b_id: str
    student_b_name: str
    file_a: str
    file_b: str
    similarity: float
    similarity_percent: float
    detected_at: str | None = None
    group_id: str | None = None
    group_a_id: str | None = None
    group_b_id: str | None = None
    group_a_name: str | None = None
    group_b_name: str | None = None


class OverlapDetail(OverlapSummary):
    passage_a: str
    passage_b: str
    evidence_a_id: str
    evidence_b_id: str


class OverlapListResponse(BaseModel):
    module_id: str
    group_id: str | None = None
    confirmed_count: int
    possible_count: int
    within_group_count: int = 0
    cross_group_count: int = 0
    items: list[OverlapSummary]


class OverlapDetectResponse(BaseModel):
    module_id: str
    group_id: str | None = None
    scanned_students: int = 0
    confirmed_count: int
    possible_count: int
    within_group_count: int = 0
    cross_group_count: int = 0
    items: list[OverlapSummary]
