# app/models/reservation.py

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    JSON,
    Numeric,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin, utc_now
from app.models.enums import (
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.establishment import Establishment
    from app.models.transaction import Transaction
    from app.models.review import Review


ZERO = Decimal("0.00")


class Reservation(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "reservations"

    __table_args__ = (
        UniqueConstraint(
            "reference",
            name="uq_reservations_reference",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_reservations_user_idempotency",
        ),
        Index("idx_reservations_user", "user_id"),
        Index("idx_reservations_establishment", "establishment_id"),
        Index("idx_reservations_status", "status"),
        Index("idx_reservations_payment_status", "payment_status"),
        Index("idx_reservations_start_date", "start_date"),
        Index("idx_reservations_reference", "reference"),
        Index("idx_reservations_expires_at", "expires_at"),
        CheckConstraint(
            "quantity > 0",
            name="ck_reservations_quantity_positive",
        ),
        CheckConstraint(
            "adults >= 0 AND children >= 0",
            name="ck_reservations_guests_nonnegative",
        ),
        CheckConstraint(
            "subtotal >= 0 AND service_fee >= 0",
            name="ck_reservations_amounts_nonnegative",
        ),
        CheckConstraint(
            "tax_amount >= 0 AND discount_amount >= 0",
            name="ck_reservations_tax_discount_nonnegative",
        ),
        CheckConstraint(
            "total >= 0 AND amount_paid >= 0 AND balance_due >= 0",
            name="ck_reservations_financial_amounts_nonnegative",
        ),
        CheckConstraint(
            "commission_amount >= 0 AND partner_amount >= 0",
            name="ck_reservations_commission_partner_nonnegative",
        ),
    )

    # ============================================================
    # IDENTIFICATION
    # ============================================================

    reference: str = Field(
        default_factory=lambda: f"BR-{uuid4().hex[:10].upper()}",
        max_length=30,
        nullable=False,
    )

    # Clé fournie par le client pour rendre la création idempotente.
    # La contrainte porte sur le couple user_id / idempotency_key.
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=255,
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

    category: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    # ============================================================
    # DATES ET CRÉNEAUX
    # ============================================================

    reservation_date: Optional[date] = Field(default=None)
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)

    start_time: Optional[time] = Field(default=None)
    end_time: Optional[time] = Field(default=None)

    # ============================================================
    # QUANTITÉS ET PARTICIPANTS
    # ============================================================

    quantity: int = Field(
        default=1,
        nullable=False,
    )

    nights: Optional[int] = Field(default=None)

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
    # OPTIONS ET DEMANDES PARTICULIÈRES
    # ============================================================

    options: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
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
    # SNAPSHOT TARIFAIRE
    # ============================================================

    # Copie immuable du détail de calcul appliqué à la réservation :
    # tarifs unitaires, quantités, durée, suppléments et autres détails.
    pricing_snapshot: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    subtotal: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    service_fee: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    tax_amount: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    discount_amount: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    total: Decimal = Field(
        default=ZERO,
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
    # COMMISSION ET PARTENAIRE
    # ============================================================

    # Copie du taux applicable au moment de la réservation.
    commission_rate: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(5, 2),
            nullable=False,
        ),
    )

    commission_amount: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    partner_amount: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    # Ces champs représentent le calcul financier historique.
    # Le règlement effectif des commissions devra être suivi séparément.

    # ============================================================
    # PAIEMENT
    # ============================================================

    payment_method: Optional[PaymentMethod] = Field(default=None)

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

    paid_at: datetime | None = Field(
       default=None,
       sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    amount_paid: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    balance_due: Decimal = Field(
        default=ZERO,
        sa_column=Column(
            Numeric(12, 2),
            nullable=False,
        ),
    )

    # ============================================================
    # CYCLE DE VIE DE LA RÉSERVATION
    # ============================================================

    status: ReservationStatus = Field(
        default=ReservationStatus.EN_ATTENTE,
        nullable=False,
    )

    expires_at: Optional[datetime] = Field(default=None)

    confirmed_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # ============================================================
    # VÉRIFICATION MANUELLE PAR BESTREV
    # ============================================================

    verified_at: Optional[datetime] = Field(default=None)

    verified_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    verification_channel: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    verification_result: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    admin_notes: Optional[str] = Field(
        default=None,
        max_length=3000,
    )

    refusal_reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # ============================================================
    # ANNULATION
    # ============================================================

    cancelled_at: Optional[datetime] = Field(default=None)

    cancellation_reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # ============================================================
    # RELATIONS ORM
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

    # Pas de cascade delete-orphan : l'historique financier
    # ne doit pas être supprimé automatiquement avec la réservation.
    transactions: list["Transaction"] = Relationship(
        back_populates="reservation",
    )

    review: Optional["Review"] = Relationship(
        back_populates="reservation",
    )

    # ============================================================
    # MÉTHODES
    # ============================================================

    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Annule une réservation en attente ou confirmée.

        Les autorisations, les règles contractuelles et les éventuels
        remboursements restent de la responsabilité du service métier.
        """

        cancellable_statuses = {
            ReservationStatus.EN_ATTENTE,
            ReservationStatus.CONFIRMEE,
        }

        if self.status not in cancellable_statuses:
            raise ValueError(
                f"Impossible d'annuler une réservation au statut "
                f"{self.status.value}."
            )

        self.status = ReservationStatus.ANNULEE
        self.cancelled_at = utc_now()
        self.cancellation_reason = reason