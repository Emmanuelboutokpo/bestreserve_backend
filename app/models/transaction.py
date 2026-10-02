# app/models/transaction.py

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
    TransactionType,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.reservation import Reservation


class Transaction(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "transactions"

    __table_args__ = (
        UniqueConstraint(
            "transaction_ref",
            name="uq_transactions_reference",
        ),
        Index(
            "idx_transactions_user",
            "user_id",
        ),
        Index(
            "idx_transactions_reservation",
            "reservation_id",
        ),
        Index(
            "idx_transactions_status",
            "status",
        ),
        Index(
            "idx_transactions_provider",
            "provider",
            "provider_transaction_id",
        ),
    )

    # ============================================================
    # REFERENCES
    # ============================================================

    transaction_ref: str = Field(
        default_factory=lambda: f"TX-{uuid4().hex[:12].upper()}",
        max_length=40,
        nullable=False,
    )

    provider_transaction_id: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    reservation_id: UUID = Field(
        foreign_key="reservations.id",
        nullable=False,
    )

    # ============================================================
    # TRANSACTION
    # ============================================================

    type: TransactionType = Field(
        nullable=False,
    )

    amount: Decimal = Field(
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

    payment_method: PaymentMethod = Field(
        nullable=False,
    )

    provider: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    status: PaymentStatus = Field(
        default=PaymentStatus.EN_ATTENTE,
        nullable=False,
    )

    metadata_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    user: "User" = Relationship(
        back_populates="transactions",
    )

    reservation: "Reservation" = Relationship(
        back_populates="transactions",
    )