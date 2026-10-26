from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.establishment import Establishment
    from app.models.reservation import Reservation


class Review(UUIDMixin, TimestampMixin, table=True):
    """
    Avis laissé par un client après une réservation terminée.

    Règles :
    - Une réservation ne peut avoir qu'un seul avis.
    - La note doit être comprise entre 1 et 5.
    - Un avis n'est publié qu'après validation lorsqu'une
      modération est requise.
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
        Index(
            "idx_reviews_approval",
            "is_approved",
        ),
    )

    # ============================================================
    # CLÉS ÉTRANGÈRES
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
        ge=1,
        le=5,
        nullable=False,
    )

    # ============================================================
    # CONTENU
    # ============================================================

    comment: Optional[str] = Field(
        default=None,
        max_length=3000,
        nullable=True,
    )

    # ============================================================
    # MODÉRATION
    # ============================================================

    is_approved: bool = Field(
        default=False,
        nullable=False,
    )

    approved_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        sa_type=DateTime(timezone=True),
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