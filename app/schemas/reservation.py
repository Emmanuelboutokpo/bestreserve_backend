# app/schemas/reservation.py

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import (
    AvailabilityStatus,
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
)


# =========================================================
# CRÉATION D'UNE RÉSERVATION
# =========================================================

class ReservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    establishment_id: UUID

    # Hébergement : date d'arrivée et de départ.
    # Restaurant / loisirs : date de réservation.
    start_date: date
    end_date: date | None = None

    # Créneau horaire éventuel.
    start_time: time | None = None
    end_time: time | None = None

    quantity: int = Field(default=1, ge=1, le=100)
    adults: int = Field(default=1, ge=1, le=1000)
    children: int = Field(default=0, ge=0, le=1000)

    room_or_unit: str | None = Field(
        default=None,
        max_length=100,
    )

    options: dict[str, Any] | None = None

    special_requests: str | None = Field(
        default=None,
        max_length=3000,
    )

    payment_method: PaymentMethod | None = None

    @field_validator("options")
    @classmethod
    def validate_options_size(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and len(
            str(value).encode("utf-8")
        ) > 5000:
            raise ValueError(
                "Les options sont trop volumineuses."
            )

        return value

    @field_validator("special_requests")
    @classmethod
    def normalize_special_requests(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @model_validator(mode="after")
    def validate_dates_and_size(self):
        if self.start_date < date.today():
            raise ValueError(
                "La date de début ne peut pas être passée."
            )

        if self.end_date is not None:
            if self.end_date <= self.start_date:
                raise ValueError(
                    "La date de fin doit être après "
                    "la date de début."
                )

            if (
                self.end_date - self.start_date
            ).days > 730:
                raise ValueError(
                    "La réservation ne peut pas dépasser deux ans."
                )

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError(
                "L'heure de fin doit être après l'heure de début."
            )

        return self

# =========================================================
# MODIFICATION D'UNE RÉSERVATION
# =========================================================

class ReservationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None

    start_time: time | None = None
    end_time: time | None = None

    quantity: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    adults: int | None = Field(
        default=None,
        ge=1,
        le=1000,
    )

    children: int | None = Field(
        default=None,
        ge=0,
        le=1000,
    )

    room_or_unit: str | None = Field(
        default=None,
        max_length=100,
    )

    options: dict[str, Any] | None = None

    special_requests: str | None = Field(
        default=None,
        max_length=3000,
    )

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError(
                "Aucune information à modifier."
            )

        if self.start_date is not None:
            if self.start_date < date.today():
                raise ValueError(
                    "La date de début ne peut pas être passée."
                )

        if (
            self.start_date is not None
            and self.end_date is not None
        ):
            if self.end_date <= self.start_date:
                raise ValueError(
                    "La date de fin doit être après "
                    "la date de début."
                )

            if (
                self.end_date - self.start_date
            ).days > 730:
                raise ValueError(
                    "La réservation ne peut pas dépasser deux ans."
                )

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError(
                "L'heure de fin doit être après l'heure de début."
            )

        if self.options is not None:
            if len(str(self.options).encode("utf-8")) > 5000:
                raise ValueError(
                    "Les options sont trop volumineuses."
                )

        if self.special_requests is not None:
            self.special_requests = (
                self.special_requests.strip() or None
            )

        return self

class ReservationEstablishmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    address: str


# =========================================================
# RÉSERVATION PUBLIQUE
# =========================================================

class ReservationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str

    establishment_id: UUID
    establishment: ReservationEstablishmentPublic | None = None

    category: str | None

    reservation_date: date | None
    start_date: date | None
    end_date: date | None

    start_time: time | None
    end_time: time | None

    quantity: int
    nights: int | None

    adults: int
    children: int

    room_or_unit: str | None
    options: dict[str, Any] | None
    special_requests: str | None

    subtotal: Decimal
    service_fee: Decimal
    total: Decimal
    currency: str

    payment_method: PaymentMethod | None
    payment_status: PaymentStatus
    status: ReservationStatus

    cancelled_at: datetime | None
    cancellation_reason: str | None

    created_at: datetime
    updated_at: datetime

    
# =========================================================
# RÉSERVATION ADMINISTRATEUR
# =========================================================

class AdminReservationPublic(ReservationPublic):
    user_id: UUID

    client_first_name: str
    client_last_name: str
    client_email: EmailStr
    client_phone: str | None

    payment_provider: str | None
    payment_reference: str | None
    paid_at: datetime | None


# =========================================================
# PAGINATION
# =========================================================

class ReservationPage(BaseModel):
    items: list[ReservationPublic]
    total: int
    limit: int
    offset: int


class AdminReservationPage(BaseModel):
    items: list[AdminReservationPublic]
    total: int
    limit: int
    offset: int


# =========================================================
# ANNULATION CLIENT
# =========================================================

class ReservationCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip() or None


# =========================================================
# CHANGEMENT DE STATUT ADMINISTRATEUR
# =========================================================

class AdminReservationStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReservationStatus

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return value.strip() or None


# =========================================================
# REMBOURSEMENT ADMINISTRATEUR
# =========================================================

class AdminRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["REFUNDED"]

    external_reference: str = Field(
        min_length=3,
        max_length=255,
    )

    reason: str = Field(
        min_length=3,
        max_length=1000,
    )

    @field_validator("external_reference", "reason")
    @classmethod
    def normalize_text(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Cette valeur ne peut pas être vide."
            )

        return value


# =========================================================
# DISPONIBILITÉ PUBLIQUE
# =========================================================

class PublicAvailability(BaseModel):
    establishment_id: UUID

    available: bool
    availability_status: AvailabilityStatus

    start_date: date
    end_date: date | None = None

    start_time: time | None = None
    end_time: time | None = None

    remaining_capacity: int | None


# =========================================================
# DEVIS DE RÉSERVATION
# =========================================================


class ReservationQuote(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    establishment_id: UUID
    category_kind: str  # hebergement | restaurant | loisir
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    nights: int | None = None

    quantity: int
    adults: int
    children: int

    price_unit: str
    unit_label: str
    unit_price: Decimal
    price_units: Decimal

    base_subtotal: Decimal
    options_total: Decimal = Decimal("0.00")
    options_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    subtotal: Decimal

    service_fee_percent: Decimal
    service_fee: Decimal
    tax_percent: Decimal = Decimal("0.00")
    tax_amount: Decimal
    discount_amount: Decimal
    total: Decimal

    commission_rate: Decimal
    commission_amount: Decimal
    partner_amount: Decimal
    currency: str

# =========================================================
# STATISTIQUES ADMINISTRATEUR
# =========================================================

class AdminReservationStats(BaseModel):
    total: int

    pending: int
    confirmed: int
    ongoing: int
    completed: int
    cancelled: int

    payment_pending: int
    paid: int
    refunded: int

    gross_paid: Decimal
    gross_refunded: Decimal