import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    AvailabilityStatus,
    EstablishmentStatus,
    PriceUnit,
)
from app.schemas.commons.common import slug as _slug


# ---------------------------------------------------------
# CRÉATION
# ---------------------------------------------------------

class EstablishmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    subcategory_id: UUID | None = None
    location_id: UUID
    address: str = Field(min_length=3, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, ge=0)
    price_per_night: Decimal | None = Field(default=None, ge=0)
    price_per_month: Decimal | None = Field(default=None, ge=0)
    price_unit: PriceUnit | None = None
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    rooms_count: int | None = Field(default=None, ge=0, le=10000)
    cuisine_type: str | None = Field(default=None, max_length=150)
    opening_hours: dict[str, Any] | None = None
    area: Decimal | None = Field(default=None, ge=0)

    @field_validator("name", "address")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cette valeur ne peut pas être vide.")
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        return _slug(value)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError(
                "Le code devise doit contenir trois lettres ASCII."
            )
        return value

    @field_validator("opening_hours")
    @classmethod
    def validate_opening_hours(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and len(
            json.dumps(value, ensure_ascii=False)
        ) > 5000:
            raise ValueError(
                "Les horaires ne peuvent pas dépasser 5000 caractères."
            )
        return value

    @model_validator(mode="after")
    def validate_required_text_lengths(self):
        if len(self.name) < 2 or len(self.address) < 3:
            raise ValueError(
                "Le nom ou l'adresse est trop court après normalisation."
            )
        return self


# ---------------------------------------------------------
# MODIFICATION PARTIELLE
# ---------------------------------------------------------

class EstablishmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    location_id: UUID | None = None
    address: str | None = Field(default=None, min_length=3, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, ge=0)
    price_per_night: Decimal | None = Field(default=None, ge=0)
    price_per_month: Decimal | None = Field(default=None, ge=0)
    price_unit: PriceUnit | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    capacity: int | None = Field(default=None, ge=1, le=10000)
    rooms_count: int | None = Field(default=None, ge=0, le=10000)
    cuisine_type: str | None = Field(default=None, max_length=150)
    opening_hours: dict[str, Any] | None = None
    area: Decimal | None = Field(default=None, ge=0)

    @field_validator("name", "address")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        if not value:
            raise ValueError("Cette valeur ne peut pas être vide.")

        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        return _slug(value)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError(
                "Le code devise doit contenir trois lettres ASCII."
            )

        return value

    @field_validator("opening_hours")
    @classmethod
    def validate_opening_hours(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and len(
            json.dumps(value, ensure_ascii=False)
        ) > 5000:
            raise ValueError(
                "Les horaires ne peuvent pas dépasser 5000 caractères."
            )
        return value

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")

        non_nullable = {
            "category_id",
            "location_id",
            "address",
            "name",
            "slug",
            "currency",
        }

        if any(
            key in self.model_fields_set and getattr(self, key) is None
            for key in non_nullable
        ):
            raise ValueError(
                "Un champ obligatoire ne peut pas être nul."
            )

        if self.name is not None and len(self.name) < 2:
            raise ValueError(
                "Le nom doit contenir au moins deux caractères."
            )

        if self.address is not None and len(self.address) < 3:
            raise ValueError(
                "L'adresse doit contenir au moins trois caractères."
            )

        return self


# ---------------------------------------------------------
# MODIFICATION DU STATUT
# ---------------------------------------------------------

class EstablishmentStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EstablishmentStatus


class EstablishmentAvailabilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    availability_status: AvailabilityStatus


# ---------------------------------------------------------
# SCHÉMAS COMMUNS AUX RÉPONSES GET
# ---------------------------------------------------------

class EstablishmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    subcategory_id: UUID | None
    location_id: UUID
    address: str
    latitude: Decimal | None
    longitude: Decimal | None
    name: str
    slug: str
    description: str | None
    price: Decimal | None
    price_per_night: Decimal | None
    price_per_month: Decimal | None
    price_unit: PriceUnit | None
    currency: str
    capacity: int | None
    rooms_count: int | None
    cuisine_type: str | None
    opening_hours: dict[str, Any] | None
    area: Decimal | None
    availability_status: AvailabilityStatus
    rating: Decimal
    reviews_count: int
    created_at: datetime


# ---------------------------------------------------------
# GET ALL : LISTE DES ÉTABLISSEMENTS
# ---------------------------------------------------------

class EstablishmentListItem(EstablishmentPublic):
    category: dict[str, Any] | None = None
    subcategory: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    amenities: list[dict[str, Any]] = Field(default_factory=list)
    cover_photo: dict[str, Any] | None = None


class EstablishmentPage(BaseModel):
    items: list[EstablishmentListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------
# GET DÉTAIL : ÉTABLISSEMENT COMPLET
# ---------------------------------------------------------

class EstablishmentDetailPublic(EstablishmentPublic):
    category: dict[str, Any] | None = None
    subcategory: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    owner: dict[str, Any] | None = None
    photos: list[dict[str, Any]] | None = None
    amenities: list[dict[str, Any]] = Field(default_factory=list)
    payment_conditions: list[dict[str, Any]] = Field(
        default_factory=list
    )


# ---------------------------------------------------------
# GET ADMINISTRATEUR
# ---------------------------------------------------------

class EstablishmentAdminDetailPublic(EstablishmentDetailPublic):
    status: EstablishmentStatus


class EstablishmentAdminPublic(EstablishmentPublic):
    status: EstablishmentStatus


# ---------------------------------------------------------
# DISPONIBILITÉ
# ---------------------------------------------------------

class EstablishmentAvailabilityPublic(BaseModel):
    establishment_id: UUID
    availability_status: AvailabilityStatus
    opening_hours: dict[str, Any] | None


# ---------------------------------------------------------
# AVIS
# ---------------------------------------------------------

class ReviewPublic(BaseModel):
    id: UUID
    author_name: str
    rating: int
    comment: str | None
    created_at: datetime


class ReviewPage(BaseModel):
    items: list[ReviewPublic]
    total: int
    average_rating: Decimal
    limit: int
    offset: int
