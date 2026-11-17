from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, Index, Numeric, UniqueConstraint, text
from sqlmodel import Field

from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import PaymentMethod, PaymentStatus


class LocationAccessPayment(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "location_access_payments"

    __table_args__ = (
        UniqueConstraint(
            "transaction_ref",
            name="uq_location_access_payments_reference",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_location_access_payments_idempotency_key",
        ),
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_location_access_payments_provider_reference",
        ),
        Index("idx_location_access_payments_user", "user_id"),
        Index(
            "uq_location_access_payments_user_pending",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'EN_ATTENTE'"),
            sqlite_where=text("status = 'EN_ATTENTE'"),
        ),
        CheckConstraint(
            "amount = 500",
            name="ck_location_access_payments_amount",
        ),
    )

    transaction_ref: str = Field(
        default_factory=lambda: f"TX-{uuid4().hex[:12].upper()}",
        max_length=40,
        nullable=False,
    )
    idempotency_key: str = Field(max_length=255, nullable=False)
    provider_transaction_id: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
    )
    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    amount: Decimal = Field(
        default=Decimal("500.00"),
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    currency: str = Field(default="XOF", max_length=3, nullable=False)
    payment_method: PaymentMethod = Field(nullable=False)
    provider: str = Field(default="KKIAPAY", max_length=100, nullable=False)
    status: PaymentStatus = Field(
        default=PaymentStatus.EN_ATTENTE,
        nullable=False,
    )
