from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SubcategoryCreate(BaseModel):
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


class SubcategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
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
        if any(
            key in self.model_fields_set and getattr(self, key) is None
            for key in ("category_id", "name")
        ):
            raise ValueError("Un champ obligatoire ne peut pas être nul.")
        return self


class SubcategoryPublic(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    icon: str | None
    created_at: datetime


class SubcategoryPage(BaseModel):
    items: list[SubcategoryPublic]
    total: int
    limit: int
    offset: int