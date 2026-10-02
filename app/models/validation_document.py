# app/models/validation_document.py

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)
from app.models.enums import (
    DocumentType,
    ValidationStatus,
)
from app.models.base import utc_now

if TYPE_CHECKING:
    from app.models.establishment import Establishment
    from app.models.user import User


class ValidationDocument(
    UUIDMixin,
    TimestampMixin,
    table=True,
):
    """
    Document utilisé pour valider un établissement.
    """

    __tablename__ = "validation_documents"

    __table_args__ = (
        Index(
            "idx_validation_documents_establishment",
            "establishment_id",
        ),
        Index(
            "idx_validation_documents_owner",
            "owner_id",
        ),
        Index(
            "idx_validation_documents_status",
            "status",
        ),
        Index(
            "idx_validation_documents_type",
            "type",
        ),
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        nullable=False,
    )

    owner_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
    )

    reviewed_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    # ============================================================
    # DOCUMENT
    # ============================================================

    name: str = Field(
        max_length=255,
        nullable=False,
    )

    type: DocumentType = Field(
        nullable=False,
    )

    file_name: str = Field(
        max_length=255,
        nullable=False,
    )

    file_size: Optional[int] = Field(
        default=None,
    )

    file_url: str = Field(
        max_length=1000,
        nullable=False,
    )

    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    # ============================================================
    # VALIDATION
    # ============================================================

    status: ValidationStatus = Field(
        default=ValidationStatus.EN_ATTENTE,
        nullable=False,
    )

    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    submitted_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
    )

    reviewed_at: Optional[datetime] = Field(
        default=None,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    establishment: "Establishment" = Relationship(
        back_populates="validation_documents",
    )

    owner: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "ValidationDocument.owner_id",
        },
    )

    reviewer: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "ValidationDocument.reviewed_by",
        },
    )