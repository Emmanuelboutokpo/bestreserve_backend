from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    """Ajoute les timestamps de création et de modification."""

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": utc_now},
    )


class UUIDMixin(SQLModel):
    """Ajoute un UUID v4 comme clé primaire."""

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        nullable=False,
        index=True,
    )