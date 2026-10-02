# app/models/profile.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship
from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.user import User


class Profile(UUIDMixin, TimestampMixin, table=True):
   
    __tablename__ = "profiles"

    # ============================================================
    # RELATION USER
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        unique=True,
    )

    # ============================================================
    # IDENTITE
    # ============================================================

    firstName: Optional[str] = Field(
        max_length=100,
        nullable=None,
    )

    lastName: Optional[str] = Field(
        max_length=100,
        nullable=None,
    )

    phone: Optional[str] = Field(default=None)

    img: Optional[str] = Field(
        default=None,
    )

    avatar_public_id: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # ============================================================
    # LOCALISATION
    # ============================================================

    country_code: Optional[str] = Field(
        default=None,
        max_length=2,
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    # ============================================================
    # PREFERENCES
    # ============================================================

    language: Optional[str] = Field(
        default="fr",
        max_length=5,
        nullable=None,
    )

    currency: Optional[str] = Field(
        default="XOF",
        max_length=3,
        nullable=None,
    )

    # ============================================================
    # RELATION
    # ============================================================

    user: Optional["User"] = Relationship(
        back_populates="profile",
    )

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def full_name(self) -> str:

        return f"{self.firstName} {self.lastName}".strip()

    @property
    def initials(self) -> str:

        first_initial = self.firstName[:1].upper()
        last_initial = self.lastName[:1].upper()

        return f"{first_initial}{last_initial}"