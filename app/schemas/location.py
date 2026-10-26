import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import LocationType


class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    type: LocationType
    parent_id: UUID | None = None
    country_code: str = Field(min_length=2, max_length=2)
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        allow_inf_nan=False,
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        allow_inf_nan=False,
    )
    timezone: str | None = Field(default=None, max_length=50)
    population: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le nom du lieu ne peut pas être vide.")
        return value


    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("Le code pays doit être composé de deux lettres ASCII.")
        return value


class LocationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=150)
    type: LocationType | None = None
    parent_id: UUID | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        allow_inf_nan=False,
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        allow_inf_nan=False,
    )
    timezone: str | None = Field(default=None, max_length=50)
    population: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Le nom du lieu ne peut pas être vide.")
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("Le code pays doit être composé de deux lettres ASCII.")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")
        non_nullable = {"name", "type", "country_code", "is_active"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in non_nullable
        ):
            raise ValueError("Un champ obligatoire ne peut pas être nul.")
        return self


class LocationPublic(BaseModel):
    id: UUID
    name: str
    type: LocationType
    parent_id: UUID | None
    country_code: str
    latitude: float | None
    longitude: float | None
    timezone: str | None
    population: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationAdminPublic(LocationPublic):
    metadata_json: dict[str, Any] | None


class LocationTree(LocationPublic):
    children: list["LocationTree"] = Field(default_factory=list)


class LocationImportItem(LocationCreate):
    id: UUID | None = None


class LocationImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locations: list[LocationImportItem] = Field(min_length=1, max_length=500)


class LocationPage(BaseModel):
    items: list[LocationPublic]
    total: int
    limit: int
    offset: int


class NearbyLocation(LocationPublic):
    distance_km: float


class NearbyLocationPage(BaseModel):
    items: list[NearbyLocation]
    limit: int
    radius_km: float