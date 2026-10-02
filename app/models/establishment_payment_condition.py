# app/models/establishment_payment_condition.py

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.establishment import Establishment
    from app.models.payment_condition import PaymentCondition


class EstablishmentPaymentCondition(SQLModel, table=True):
    """
    Association entre un établissement
    et une condition de paiement.
    """

    __tablename__ = "establishment_payment_conditions"

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        primary_key=True,
        nullable=False,
    )

    payment_condition_id: UUID = Field(
        foreign_key="payment_conditions.id",
        primary_key=True,
        nullable=False,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment: "Establishment" = Relationship(
        back_populates="payment_condition_links",
    )

    payment_condition: "PaymentCondition" = Relationship(
        back_populates="establishment_links",
    )