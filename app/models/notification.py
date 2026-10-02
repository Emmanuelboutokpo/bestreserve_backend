# app/models/notification.py

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)
from app.models.enums import NotificationType
from app.models.base import utc_now

if TYPE_CHECKING:
    from app.models.user import User


class Notification(UUIDMixin, TimestampMixin, table=True):
   
    __tablename__ = "notifications"

    __table_args__ = (
        Index(
            "idx_notifications_user",
            "user_id",
        ),
        Index(
            "idx_notifications_read",
            "is_read",
        ),
        Index(
            "idx_notifications_type",
            "type",
        ),
        Index(
            "idx_notifications_created",
            "created_at",
        ),
    )

    # ============================================================
    # DESTINATAIRE
    # ============================================================

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    # ============================================================
    # CONTENU
    # ============================================================

    type: NotificationType = Field(
        nullable=False,
    )

    title: str = Field(
        max_length=255,
        nullable=False,
    )

    message: str = Field(
        max_length=2000,
        nullable=False,
    )

    action_url: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    # ============================================================
    # ETAT DE LECTURE
    # ============================================================

    is_read: bool = Field(
        default=False,
        nullable=False,
    )

    read_at: Optional[datetime] = Field(
        default=None,
    )

    # ============================================================
    # RELATION
    # ============================================================

    user: "User" = Relationship(
        back_populates="notifications",
    )

    # ============================================================
    # METHODES
    # ============================================================

    def mark_as_read(self) -> None:
        self.is_read = True

        if self.read_at is None:
            self.read_at = utc_now()

    def mark_as_unread(self) -> None:
        self.is_read = False
        self.read_at = None