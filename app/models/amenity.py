# app/models/amenity.py

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.establishment_amenity import EstablishmentAmenity


class Amenity(UUIDMixin, TimestampMixin, table=True):
  
    __tablename__ = "amenities"

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=100,
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