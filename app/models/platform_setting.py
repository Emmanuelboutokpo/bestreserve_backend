# app/models/platform_setting.py

from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Index, JSON
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.user import User


class PlatformSetting(
    UUIDMixin,
    TimestampMixin,
    table=True,
):
    """
    Paramètre global de la plateforme.

    Exemple :

        site_name
        maintenance_mode
        service_fee
        default_currency
        support_email
    """

    __tablename__ = "platform_settings"

    __table_args__ = (
        Index(
            "idx_settings_section",
            "section",
        ),
    )

    # ============================================================
    # PARAMETRE
    # ============================================================

    key: str = Field(
        max_length=150,
        nullable=False,
        unique=True,
    )

    value: Optional[str] = Field(
        default=None,
    )

    value_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    description: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    section: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    is_public: bool = Field(
        default=False,
        nullable=False,
    )

    updated_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    # ============================================================
    # RELATION
    # ============================================================

    updater: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "PlatformSetting.updated_by",
        },
    )