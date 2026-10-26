# app/models/establishment_amenity.py

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.establishment import Establishment
    from app.models.amenity import Amenity


class EstablishmentAmenity(SQLModel, table=True):
    
    __tablename__ = "establishment_amenities"

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        primary_key=True,
        nullable=False,
    )

    amenity_id: UUID = Field(
        foreign_key="amenities.id",
        primary_key=True,
        nullable=False,
    )

    establishment: "Establishment" = Relationship(
        back_populates="amenity_links",
    )

    amenity: "Amenity" = Relationship(
        back_populates="establishment_links",
    )