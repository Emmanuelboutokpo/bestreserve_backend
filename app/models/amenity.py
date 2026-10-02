# app/models/amenity.py

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.establishment_amenity import EstablishmentAmenity


class Amenity(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):
    """
    Équipement / service disponible dans un établissement.

    Exemples :

        - Wi-Fi
        - Piscine
        - Parking
        - Climatisation
        - Restaurant
        - Salle de sport
    """

    __tablename__ = "amenities"

    __table_args__ = (
        Index(
            "idx_amenities_slug",
            "slug",
            unique=True,
        ),
    )

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=100,
        nullable=False,
    )

    slug: str = Field(
        max_length=120,
        nullable=False,
    )

    icon: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment_links: list["EstablishmentAmenity"] = Relationship(
        back_populates="amenity",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )