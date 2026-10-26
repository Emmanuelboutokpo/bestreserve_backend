from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import PaymentConditionType

if TYPE_CHECKING:
    from app.models.establishment_payment_condition import (
        EstablishmentPaymentCondition,
    )


class PaymentCondition(UUIDMixin, TimestampMixin, table=True):
    """
    Définit une modalité de paiement proposée par BestRev.

    Exemples :
    - paiement intégral ;
    - paiement avec acompte ;
    - paiement sur place.
    """

    __tablename__ = "payment_conditions"

    __table_args__ = (
        Index(
            "idx_payment_conditions_type",
            "condition_type",
        ),
        CheckConstraint(
            "percentage IS NULL OR "
            "(percentage >= 1 AND percentage <= 100)",
            name="ck_payment_conditions_percentage_range",
        ),
    )

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=150,
        nullable=False,
    )

    condition_type: PaymentConditionType = Field(
        nullable=False,
    )

    percentage: Optional[int] = Field(
        default=None,
        nullable=True,
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