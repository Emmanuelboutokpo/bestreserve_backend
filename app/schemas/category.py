from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    icon: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Le nom doit contenir au moins deux caractères.")
        return value


class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    icon: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Le nom doit contenir au moins deux caractères.")
        return value

class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    icon: str | None
    img: str | None
    created_at: datetime


class CategoryPage(BaseModel):
    items: list[CategoryPublic]
    total: int
    limit: int
    offset: int