from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class AmenityCreate(BaseModel):
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


class AmenityPatch(BaseModel):
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


class AmenityPublic(BaseModel):
    id: UUID
    name: str
    icon: str | None


class AmenityPage(BaseModel):
    items: list[AmenityPublic]
    total: int
    limit: int
    offset: int


class EstablishmentAmenityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amenity_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("amenity_ids")
    @classmethod
    def require_unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("La liste contient des équipements dupliqués.")
        return value
