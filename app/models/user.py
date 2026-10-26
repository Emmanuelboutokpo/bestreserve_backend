from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import UserRole, UserStatus, UserProvider

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.establishment import Establishment
    from app.models.favorite import Favorite
    from app.models.notification import Notification
    from app.models.reservation import Reservation
    from app.models.transaction import Transaction
    from app.models.review import Review
    from app.models.activity_log import ActivityLog


class User(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "users"

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
    )

    # ============================================================
    # AUTHENTIFICATION
    # ============================================================

    email: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True,
    )

    password: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
    )

    provider: UserProvider = Field(
        default=UserProvider.LOCAL,
        nullable=False,
    )

    token_version: int = Field(
        default=0,
        nullable=False,
        ge=0,
    )

    two_factor_enabled: bool = Field(
        default=False,
        nullable=False,
    )

    # ============================================================
    # AUTORISATIONS ET STATUT
    # ============================================================

    role: UserRole = Field(
        default=UserRole.CLIENT,
        nullable=False,
    )

    status: UserStatus = Field(
        default=UserStatus.ACTIF,
        nullable=False,
    )

    # ============================================================
    # TRAÇABILITÉ
    # ============================================================

    created_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )

    is_deleted: bool = Field(default=False, index=True)

    # ============================================================
    # PROFIL
    # ============================================================

    profile: Optional["Profile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
        },
    )

    # ============================================================
    # ÉTABLISSEMENTS
    # ============================================================

    establishments_owned: List["Establishment"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={
            "foreign_keys": "Establishment.owner_id",
        },
    )

    # ============================================================
    # FAVORIS
    # ============================================================

    favorites: List["Favorite"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    notifications: List["Notification"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    # ============================================================
    # RÉSERVATIONS
    # ============================================================

    reservations: List["Reservation"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "Reservation.user_id",
        },
    )

    # ============================================================
    # TRANSACTIONS FINANCIÈRES
    # ============================================================

    transactions: List["Transaction"] = Relationship(
        back_populates="user",
    )

    # ============================================================
    # AVIS
    # ============================================================

    reviews: List["Review"] = Relationship(
        back_populates="user",
    )

    # ============================================================
    # JOURNAUX D'ACTIVITÉ
    # ============================================================

    activity_logs: List["ActivityLog"] = Relationship(
        back_populates="user",
    )