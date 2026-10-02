from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampMixin, UUIDMixin


class UserConsent(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "user_consents"

    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_user_consent_purpose"),
        Index("idx_user_consents_user", "user_id"),
    )

    user_id: UUID = Field(foreign_key="users.id", nullable=False)
    purpose: str = Field(max_length=50, nullable=False)
    granted: bool = Field(default=False, nullable=False)
    granted_at: Optional[datetime] = Field(default=None)