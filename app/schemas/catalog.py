from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
)


class AmenityPublic(BaseModel):
    id: UUID
    name: str
    slug: str
    icon: str | None


class ReviewPublic(BaseModel):
    id: UUID
    author_name: str
    rating: int
    cleanliness_rating: int | None
    service_rating: int | None
    location_rating: int | None
    value_rating: int | None
    comment: str | None
    created_at: datetime

