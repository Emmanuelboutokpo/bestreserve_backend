# app/models/favorite.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.establishment import Establishment


class Favorite(UUIDMixin, TimestampMixin, table=True):
    """
    Établissement enregistré dans les favoris d'un utilisateur.
    """

    __tablename__ = "favorites"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "establishment_id",
            name="uq_favorite_user_establishment",
        ),
        Index(
            "idx_favorites_user",
            "user_id",
        ),
        Index(
            "idx_favorites_establishment",
            "establishment_id",
        ),
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        nullable=False,
    )

    # ============================================================
    # INFORMATIONS
    # ============================================================

    note: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    user: "User" = Relationship(
        back_populates="favorites",
    )

    establishment: "Establishment" = Relationship(
        back_populates="favorites",
    )