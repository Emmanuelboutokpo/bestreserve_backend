# app/models/user.py

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)
from app.models.enums import (
    UserRole,
    UserStatus,
    UserProvider,
)

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.establishment import Establishment
    from app.models.session import Session as UserSession
    from app.models.favorite import Favorite
    from app.models.notification import Notification
    from app.models.reservation import Reservation
    from app.models.transaction import Transaction
    from app.models.review import Review
    from app.models.activity_log import ActivityLog


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):

    __tablename__ = "users"

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
    )

    email: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
    )

    password: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
    )

    role: UserRole = Field(
        default=UserRole.CLIENT,
        nullable=False,
    )

    status: UserStatus = Field(
        default=UserStatus.ACTIF,
        nullable=False,
    )

    refreshToken : Optional[str] = None       

    token_version: int = Field(
        default=0,
        nullable=False,
    )

    provider: UserProvider = Field(
        default=UserProvider.LOCAL,
        nullable=False,
    )

    two_factor_enabled: bool = Field(
        default=False,
        nullable=False,
    )

    created_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    profile: Optional["Profile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
        },
    )

    establishments_owned: List["Establishment"] = Relationship(
        back_populates="owner",
        sa_relationship_kwargs={
            "foreign_keys": "Establishment.owner_id",
        },
    )


    favorites: List["Favorite"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    notifications: List["Notification"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    reservations: List["Reservation"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "Reservation.user_id",
        },
    )

    transactions: List["Transaction"] = Relationship(
        back_populates="user",
    )

    reviews: List["Review"] = Relationship(
        back_populates="user",
    )

    activity_logs: List["ActivityLog"] = Relationship(
        back_populates="user",
    )