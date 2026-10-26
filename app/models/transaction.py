from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    JSON,
    Numeric,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin
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
        # --------------------------------------------------------
        # UNICITÉ
        # --------------------------------------------------------
        UniqueConstraint(
            "transaction_ref",
            name="uq_transactions_reference",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_transactions_idempotency_key",
        ),
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_transactions_provider_reference",
        ),

        # --------------------------------------------------------
        # INDEX
        # --------------------------------------------------------
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
        Index(
            "idx_transactions_refund_origin",
            "refund_of_transaction_id",
        ),

        # --------------------------------------------------------
        # CONTRAINTES FINANCIÈRES
        # --------------------------------------------------------
        CheckConstraint(
            "amount > 0",
            name="ck_transactions_amount_positive",
        ),
    )

    # ============================================================
    # RÉFÉRENCES
    # ============================================================

    transaction_ref: str = Field(
        default_factory=lambda: f"TX-{uuid4().hex[:12].upper()}",
        max_length=40,
        nullable=False,
    )

    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
    )

    provider_transaction_id: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
    )

    # ============================================================
    # RELATIONS MÉTIER
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    reservation_id: UUID = Field(
        foreign_key="reservations.id",
        nullable=False,
    )

    # Pour un remboursement, référence à la transaction d'origine.
    # Ce champ reste nul pour les paiements et les transactions
    # qui ne correspondent pas à un remboursement.
    refund_of_transaction_id: Optional[UUID] = Field(
        default=None,
        foreign_key="transactions.id",
        nullable=True,
    )

    # ============================================================
    # OPÉRATION FINANCIÈRE
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

    # ============================================================
    # MOYEN DE PAIEMENT
    # ============================================================

    payment_method: PaymentMethod = Field(
        nullable=False,
    )

    provider: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    # ============================================================
    # STATUT
    # ============================================================

    status: PaymentStatus = Field(
        default=PaymentStatus.EN_ATTENTE,
        nullable=False,
    )

    # ============================================================
    # MÉTADONNÉES
    # ============================================================

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