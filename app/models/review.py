# app/models/review.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.establishment import Establishment
    from app.models.reservation import Reservation


class Review(
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    table=True,
):
    """
    Avis laissé par un client après une réservation.
    """

    __tablename__ = "reviews"

    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            name="uq_reviews_reservation",
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_reviews_rating",
        ),
        CheckConstraint(
            "cleanliness_rating IS NULL OR "
            "(cleanliness_rating >= 1 AND cleanliness_rating <= 5)",
            name="ck_reviews_cleanliness",
        ),
        CheckConstraint(
            "service_rating IS NULL OR "
            "(service_rating >= 1 AND service_rating <= 5)",
            name="ck_reviews_service",
        ),
        CheckConstraint(
            "location_rating IS NULL OR "
            "(location_rating >= 1 AND location_rating <= 5)",
            name="ck_reviews_location",
        ),
        CheckConstraint(
            "value_rating IS NULL OR "
            "(value_rating >= 1 AND value_rating <= 5)",
            name="ck_reviews_value",
        ),
        Index(
            "idx_reviews_establishment",
            "establishment_id",
        ),
        Index(
            "idx_reviews_user",
            "user_id",
        ),
        Index(
            "idx_reviews_rating",
            "rating",
        ),
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        nullable=False,
    )

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    reservation_id: UUID = Field(
        foreign_key="reservations.id",
        nullable=False,
    )

    # ============================================================
    # NOTATION
    # ============================================================

    rating: int = Field(
        nullable=False,
    )

    cleanliness_rating: Optional[int] = Field(
        default=None,
    )

    service_rating: Optional[int] = Field(
        default=None,
    )

    location_rating: Optional[int] = Field(
        default=None,
    )

    value_rating: Optional[int] = Field(
        default=None,
    )

    # ============================================================
    # CONTENU
    # ============================================================

    comment: Optional[str] = Field(
        default=None,
        max_length=3000,
    )

    # ============================================================
    # MODERATION
    # ============================================================

    is_approved: bool = Field(
        default=False,
        nullable=False,
    )

    approved_at: Optional[datetime] = Field(
       default=None,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment: "Establishment" = Relationship(
        back_populates="reviews",
    )

    user: "User" = Relationship(
        back_populates="reviews",
    )

    reservation: "Reservation" = Relationship(
        back_populates="review",
    )