from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Whitelist of allowed category values. Extending this is a one-line change;
# no DB migration is required because the underlying column is a plain String.
ALLOWED_CATEGORIES = {"technical", "communication", "process"}


def _validate_category(v: str) -> str:
    if v not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"category must be one of {sorted(ALLOWED_CATEGORIES)}"
        )
    return v


class RubricCriterionBase(BaseModel):
    category: str
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    points: int = Field(gt=0)
    position: int = 0

    @field_validator("category")
    @classmethod
    def check_category(cls, v: str) -> str:
        return _validate_category(v)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class RubricCriterionCreate(RubricCriterionBase):
    pass


class RubricCriterionUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    points: Optional[int] = Field(default=None, gt=0)
    position: Optional[int] = None

    @field_validator("category")
    @classmethod
    def check_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_category(v)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class RubricCriterionResponse(BaseModel):
    id: UUID
    project_id: UUID
    category: str
    title: str
    description: Optional[str]
    points: int
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RubricBulkSave(BaseModel):
    """Payload for POST /projects/{id}/rubric/save (the "Complete Setup" action).

    Replaces the project's criteria with the provided list AND flips the
    project's status from "draft" to "ready" in a single transaction. The
    "Save Draft" button on the frontend uses the per-row POST/PATCH/DELETE
    endpoints instead and never calls this one.
    """

    criteria: List[RubricCriterionCreate]
