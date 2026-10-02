# app/models/reservation.py

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, Index, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)
from app.models.enums import (
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
)
from app.models.base import utc_now

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.establishment import Establishment
    from app.models.transaction import Transaction
    from app.models.review import Review


class Reservation(UUIDMixin, TimestampMixin, table=True):
   
    __tablename__ = "reservations"

    __table_args__ = (
        UniqueConstraint(
            "reference",
            name="uq_reservations_reference",
        ),
        Index(
            "idx_reservations_user",
            "user_id",
        ),
        Index(
            "idx_reservations_establishment",
            "establishment_id",
        ),
        Index(
            "idx_reservations_status",
            "status",
        ),
        Index(
            "idx_reservations_payment_status",
            "payment_status",
        ),
        Index(
            "idx_reservations_start_date",
            "start_date",
        ),
        Index(
            "idx_reservations_reference",
            "reference",
        ),
    )

    # ============================================================
    # REFERENCE
    # ============================================================

    reference: str = Field(
        default_factory=lambda: f"BR-{uuid4().hex[:10].upper()}",
        max_length=30,
        nullable=False,
    )

    # ============================================================
    # RELATIONS PRINCIPALES
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        nullable=False,
    )

    # ============================================================
    # TYPE / CONTEXTE
    # ============================================================

    category: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    # ============================================================
    # DATES
    # ============================================================

    reservation_date: Optional[date] = Field(
        default=None,
    )

    start_date: Optional[date] = Field(
        default=None,
    )

    end_date: Optional[date] = Field(
        default=None,
    )

    start_time: Optional[time] = Field(
        default=None,
    )

    end_time: Optional[time] = Field(
        default=None,
    )

    # ============================================================
    # QUANTITES
    # ============================================================

    quantity: int = Field(
        default=1,
        nullable=False,
    )

    nights: Optional[int] = Field(
        default=None,
    )

    adults: int = Field(
        default=1,
        nullable=False,
    )

    children: int = Field(
        default=0,
        nullable=False,
    )

    room_or_unit: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    # ============================================================
    # OPTIONS
    # ============================================================

    options: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    special_requests: Optional[str] = Field(
        default=None,
        max_length=3000,
    )

    # ============================================================
    # SNAPSHOT CLIENT
    # ============================================================

    client_first_name: str = Field(
        max_length=100,
        nullable=False,
    )

    client_last_name: str = Field(
        max_length=100,
        nullable=False,
    )

    client_email: str = Field(
        max_length=255,
        nullable=False,
    )

    client_phone: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    # ============================================================
    # TARIFICATION
    # ============================================================

    subtotal: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    service_fee: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    total: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    currency: str = Field(
        default="XOF",
        max_length=3,
        nullable=False,
    )

    # ============================================================
    # PAIEMENT
    # ============================================================

    payment_method: Optional[PaymentMethod] = Field(
        default=None,
    )

    payment_status: PaymentStatus = Field(
        default=PaymentStatus.EN_ATTENTE,
        nullable=False,
    )

    payment_provider: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    payment_reference: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    paid_at: Optional[datetime] = Field(
        default=None,
    )

    # ============================================================
    # STATUT RESERVATION
    # ============================================================

    status: ReservationStatus = Field(
        default=ReservationStatus.EN_ATTENTE,
        nullable=False,
    )

    # ============================================================
    # ANNULATION
    # ============================================================

    cancelled_at: Optional[datetime] = Field(
        default=None,
    )

    cancellation_reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    user: "User" = Relationship(
        back_populates="reservations",
        sa_relationship_kwargs={
            "foreign_keys": "Reservation.user_id",
        },
    )

    establishment: "Establishment" = Relationship(
        back_populates="reservations",
    )

    transactions: list["Transaction"] = Relationship(
        back_populates="reservation",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    review: Optional["Review"] = Relationship(
        back_populates="reservation"
    )

    # ============================================================
    # METHODES
    # ============================================================

    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Annule la réservation.
        """

        self.status = ReservationStatus.ANNULEE
        self.cancelled_at = utc_now()
        self.cancellation_reason = reason