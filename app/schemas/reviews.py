from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.establishment import ReviewPublic


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=3000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=3000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")
        return self


class ReviewAdminPublic(ReviewPublic):
    user_id: UUID
    reservation_id: UUID
    establishment_id: UUID
    is_approved: bool
    approved_at: datetime | None

class ReviewReportPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_id: UUID
    reason: str
    details: str | None
    status: str
    created_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewAdminPublic]
    total: int
    limit: int
    offset: int