from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Le nom ne peut pas être nul.")
        return self


class CategoryPublic(BaseModel):
    id: UUID
    name: str
    icon: str | None
    created_at: datetime


class CategoryPage(BaseModel):
    items: list[CategoryPublic]
    total: int
    limit: int
    offset: int