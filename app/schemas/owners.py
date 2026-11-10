from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from app.models.enums import EstablishmentStatus, OwnerApplicationStatus
from app.schemas.establishment import EstablishmentListItem


class OwnerApplicationOwner(BaseModel):
    id: UUID
    email: str
    firstName: str | None = None
    lastName: str | None = None
    phone: str | None = None
    img: str | None = None
    city: str | None = None


class OwnerApplicationPublic(BaseModel):
    id: UUID
    owner_id: UUID
    owner: OwnerApplicationOwner
    status: OwnerApplicationStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None
    registry_document_url: str
    partnership_document_url: str


class OwnerApplicationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROUVE", "REJETE"]
    rejection_reason: str | None = None

    @field_validator("rejection_reason")
    @classmethod
    def normalize_rejection_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Le motif de rejet ne peut pas être vide.")
        return value

    @model_validator(mode="after")
    def validate_rejection(self) -> "OwnerApplicationDecision":
        if self.decision == "REJETE" and not self.rejection_reason:
            raise ValueError("Un motif est requis pour rejeter le dossier.")
        return self


class OwnerEstablishmentListItem(EstablishmentListItem):
    status: EstablishmentStatus


class OwnerEstablishmentPage(BaseModel):
    items: list[OwnerEstablishmentListItem]
    total: int
    limit: int
    offset: int
