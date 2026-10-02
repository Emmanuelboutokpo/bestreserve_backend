# app/models/payment_condition.py

from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.establishment_payment_condition import (
        EstablishmentPaymentCondition,
    )


class PaymentCondition(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    table=True,
):


    __tablename__ = "payment_conditions"

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=150,
        nullable=False,
    )

    slug: str = Field(
        max_length=180,
        nullable=False,
        unique=True,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    percentage: Optional[int] = Field(
        default=None,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment_links: list[
        "EstablishmentPaymentCondition"
    ] = Relationship(
        back_populates="payment_condition",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )