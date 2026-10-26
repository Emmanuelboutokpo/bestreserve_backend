from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import PaymentStatus, ReservationStatus, UserStatus
from app.schemas.auth import UserPublic


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    firstName: str | None = Field(default=None, max_length=100)
    lastName: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if (
            not any(char.isupper() for char in value)
            or not any(char.islower() for char in value)
            or not any(char.isdigit() for char in value)
            or not any(not char.isalnum() for char in value)
        ):
            raise ValueError(
                "Le mot de passe doit contenir une majuscule, "
                "une minuscule, un chiffre et un caractère spécial."
            )
        return value


class AdminUserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    firstName: str | None = Field(default=None, max_length=100)
    lastName: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)

    @field_validator("firstName", "lastName", "city")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("La valeur ne peut pas être vide.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 30:
            raise ValueError("Numéro de téléphone invalide.")
        return value

    @field_validator("email")
    @classmethod
    def reject_null_email(cls, value: EmailStr | None) -> EmailStr | None:
        if value is None:
            raise ValueError("L'email ne peut pas être vide.")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Aucune information à modifier.")
        return self


class AdminUserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["CLIENT", "ADMIN"]


class AdminUserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: UserStatus


class AdminUserPage(BaseModel):
    items: list[UserPublic]
    total: int
    limit: int
    offset: int


class AdminFavoritePublic(BaseModel):
    id: UUID
    establishment_id: UUID
    note: str | None
    created_at: datetime


class AdminReservationPublic(BaseModel):
    id: UUID
    reference: str
    establishment_id: UUID
    reservation_date: date | None
    start_date: date | None
    end_date: date | None
    quantity: int
    adults: int
    children: int
    subtotal: Decimal
    service_fee: Decimal
    total: Decimal
    currency: str
    payment_status: PaymentStatus
    status: ReservationStatus
    created_at: datetime


class AdminActivityPublic(BaseModel):
    id: UUID
    action: str
    description: str | None
    entity_type: str | None
    entity_id: UUID | None
    created_at: datetime


class AdminUserStats(BaseModel):
    total: int
    active: int
    inactive: int
    pending: int
    suspended: int
    clients: int
    admins: int
    created_last_30_days: int