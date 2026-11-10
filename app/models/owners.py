from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Index
from sqlmodel import Field, Relationship

from app.models.base import TimestampMixin, UUIDMixin, utc_now
from app.models.enums import OwnerApplicationStatus

if TYPE_CHECKING:
    from app.models.user import User


class OwnerApplication(UUIDMixin, TimestampMixin, table=True):
    """A submitted owner dossier; a new row preserves each resubmission."""

    __tablename__ = "owner_applications"
    __table_args__ = (
        Index("idx_owner_applications_owner", "owner_id"),
        Index("idx_owner_applications_status", "status"),
    )

    owner_id: UUID = Field(foreign_key="users.id", nullable=False)
    owner: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "OwnerApplication.owner_id",
        },
    )
    status: OwnerApplicationStatus = Field(
        default=OwnerApplicationStatus.EN_ATTENTE,
        nullable=False,
    )

    registry_file_name: str = Field(max_length=255, nullable=False)
    registry_file_public_id: str = Field(max_length=255, nullable=False)
    registry_mime_type: str = Field(max_length=100, nullable=False)
    registry_file_size: int = Field(ge=1, nullable=False)

    partnership_file_name: str = Field(max_length=255, nullable=False)
    partnership_file_public_id: str = Field(max_length=255, nullable=False)
    partnership_mime_type: str = Field(max_length=100, nullable=False)
    partnership_file_size: int = Field(ge=1, nullable=False)

    submitted_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    reviewed_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    rejection_reason: Optional[str] = Field(default=None, max_length=2000)
