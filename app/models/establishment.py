# app/models/establishment.py

from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Index, JSON, Numeric
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)
from app.models.enums import (
    AvailabilityStatus,
    EstablishmentStatus,
    PriceUnit,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.category import Category
    from app.models.sub_category import SubCategory
    from app.models.location import Location
    from app.models.photo import Photo
    from app.models.establishment_amenity import EstablishmentAmenity
    from app.models.establishment_payment_condition import (
        EstablishmentPaymentCondition,
    )
    from app.models.validation_document import ValidationDocument
    from app.models.reservation import Reservation
    from app.models.review import Review
    from app.models.favorite import Favorite


class Establishment(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):

    __tablename__ = "establishments"

    __table_args__ = (
        Index(
            "idx_establishments_owner",
            "owner_id",
        ),
        Index(
            "idx_establishments_category",
            "category_id",
        ),
        Index(
            "idx_establishments_subcategory",
            "subcategory_id",
        ),
        Index(
            "idx_establishments_location",
            "location_id",
        ),
        Index(
            "idx_establishments_status",
            "status",
        ),
        Index(
            "idx_establishments_availability",
            "availability_status",
        ),
        Index(
            "idx_establishments_price",
            "price",
        ),
        Index(
            "idx_establishments_rating",
            "rating",
        ),
        Index(
            "idx_establishments_coordinates",
            "latitude",
            "longitude",
        ),
        Index(
            "idx_establishments_slug",
            "slug",
            unique=True,
        ),
    )

    # ============================================================
    # PROPRIETAIRE
    # ============================================================

    owner_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    # ============================================================
    # CATEGORISATION
    # ============================================================

    category_id: UUID = Field(
        foreign_key="categories.id",
        nullable=False,
    )

    subcategory_id: Optional[UUID] = Field(
        default=None,
        foreign_key="sub_categories.id",
    )

    # ============================================================
    # LOCALISATION
    # ============================================================

    location_id: UUID = Field(
        foreign_key="locations.id",
        nullable=False,
    )

    address: str = Field(
        max_length=500,
        nullable=False,
    )

    latitude: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(10, 7),
            nullable=True,
        ),
    )

    longitude: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(10, 7),
            nullable=True,
        ),
    )

    # ============================================================
    # IDENTITE
    # ============================================================

    name: str = Field(
        max_length=200,
        nullable=False,
    )

    slug: str = Field(
        max_length=220,
        nullable=False,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=5000,
    )

    short_description: Optional[str] = Field(
        default=None,
        max_length=500,
    )


    # ============================================================
    # TARIFICATION
    # ============================================================

    price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(12, 2),
            nullable=True,
        ),
    )

    price_per_night: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(12, 2),
            nullable=True,
        ),
    )

    price_per_month: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(12, 2),
            nullable=True,
        ),
    )

    price_unit: Optional[PriceUnit] = Field(
        default=None,
    )

    currency: str = Field(
        default="XOF",
        max_length=3,
        nullable=False,
    )

    # ============================================================
    # CAPACITE
    # ============================================================

    capacity: Optional[int] = Field(
        default=None,
    )

    rooms_count: Optional[int] = Field(
        default=None,
    )

    # ============================================================
    # INFORMATIONS RESTAURANT
    # ============================================================

    cuisine_type: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    opening_hours: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    # ============================================================
    # INFORMATIONS GENERALES
    # ============================================================

    area: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(12, 2),
            nullable=True,
        ),
    )

    availability_status: AvailabilityStatus = Field(
        default=AvailabilityStatus.AVAILABLE,
        nullable=False,
    )

    # ============================================================
    # STATUT DE PUBLICATION
    # ============================================================

    status: EstablishmentStatus = Field(
        default=EstablishmentStatus.BROUILLON,
        nullable=False,
    )

    # ============================================================
    # NOTATION
    # ============================================================

    rating: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(
            Numeric(3, 2),
            nullable=False,
        ),
    )

    reviews_count: int = Field(
        default=0,
        nullable=False,
    )

    # ============================================================
    # MODERATION / AUDIT
    # ============================================================

    created_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    updated_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )


    # ============================================================
    # RELATIONS
    # ============================================================

    owner: "User" = Relationship(
        back_populates="establishments_owned",
        sa_relationship_kwargs={
            "foreign_keys": "Establishment.owner_id",
        },
    )

    category: "Category" = Relationship(
        back_populates="establishments",
    )

    subcategory: Optional["SubCategory"] = Relationship(
        back_populates="establishments",
    )

    location: "Location" = Relationship(
        back_populates="establishments",
    )

    photos: list["Photo"] = Relationship(
        back_populates="establishment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    amenity_links: list["EstablishmentAmenity"] = Relationship(
        back_populates="establishment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    payment_condition_links: list[
        "EstablishmentPaymentCondition"
    ] = Relationship(
        back_populates="establishment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    validation_documents: list["ValidationDocument"] = Relationship(
        back_populates="establishment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    reservations: list["Reservation"] = Relationship(
        back_populates="establishment",
    )

    reviews: list["Review"] = Relationship(
        back_populates="establishment",
    )

    favorites: list["Favorite"] = Relationship(
        back_populates="establishment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )