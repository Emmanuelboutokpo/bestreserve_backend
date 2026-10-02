# app/models/contact_message.py

from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)
from app.models.enums import (
    ContactStatus,
    ContactSubject,
)


class ContactMessage(
    UUIDMixin,
    TimestampMixin,
    table=True,
):
    """
    Message envoyé depuis le formulaire de contact.
    """

    __tablename__ = "contact_messages"

    __table_args__ = (
        Index(
            "idx_contact_messages_status",
            "status",
        ),
        Index(
            "idx_contact_messages_subject",
            "subject",
        ),
        Index(
            "idx_contact_messages_email",
            "email",
        ),
    )

    # ============================================================
    # EXPEDITEUR
    # ============================================================

    first_name: str = Field(
        max_length=100,
        nullable=False,
    )

    last_name: str = Field(
        max_length=100,
        nullable=False,
    )

    email: str = Field(
        max_length=255,
        nullable=False,
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    # ============================================================
    # MESSAGE
    # ============================================================

    subject: ContactSubject = Field(
        nullable=False,
    )

    message: str = Field(
        max_length=5000,
        nullable=False,
    )

    # ============================================================
    # TRAITEMENT
    # ============================================================

    status: ContactStatus = Field(
        default=ContactStatus.NON_LU,
        nullable=False,
    )

    admin_response: Optional[str] = Field(
        default=None,
        max_length=5000,
    )