from typing import Optional, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Profile(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "profiles"

    # ============================================================
    # RELATION UTILISATEUR
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        unique=True,
    )

    # ============================================================
    # IDENTITÉ
    # ============================================================

    firstName: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    lastName: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=30,
        nullable=True,
    )

    img: Optional[str] = Field(
        default=None,
        max_length=2048,
        nullable=True,
    )

    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
        nullable=True,
    )

    # ============================================================
    # LOCALISATION
    # ============================================================

    city: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    # ============================================================
    # PRÉFÉRENCES
    # ============================================================

    language: Optional[str] = Field(
        default="fr",
        max_length=5,
        nullable=True,
    )

    currency: Optional[str] = Field(
        default="XOF",
        max_length=3,
        nullable=True,
    )

    # ============================================================
    # RELATION
    # ============================================================

    user: Optional["User"] = Relationship(
        back_populates="profile",
    )

    # ============================================================
    # PROPRIÉTÉS
    # ============================================================

    @property
    def full_name(self) -> str:
        first_name = (self.firstName or "").strip()
        last_name = (self.lastName or "").strip()

        return f"{first_name} {last_name}".strip()

    @property
    def initials(self) -> str:
        first_name = (self.firstName or "").strip()
        last_name = (self.lastName or "").strip()

        first_initial = first_name[:1].upper()
        last_initial = last_name[:1].upper()

        return f"{first_initial}{last_initial}"