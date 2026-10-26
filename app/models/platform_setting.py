from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Index, JSON
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class PlatformSetting(UUIDMixin, TimestampMixin, table=True):
    """
    Paramètres de configuration de la plateforme BestRev.

    Exemples :
    - service_fee_percent
    - reservation_expiration_minutes
    - default_currency
    """

    __tablename__ = "platform_settings"

    __table_args__ = (
        Index(
            "idx_settings_section",
            "section",
        ),
    )

    # ============================================================
    # IDENTIFICATION DU PARAMÈTRE
    # ============================================================

    key: str = Field(
        max_length=150,
        nullable=False,
        unique=True,
    )

    # ============================================================
    # VALEURS
    # ============================================================

    value: Optional[str] = Field(
        default=None,
        nullable=True,
    )

    value_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    # ============================================================
    # DOCUMENTATION ET ORGANISATION
    # ============================================================

    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        nullable=True,
    )

    section: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    is_public: bool = Field(
        default=False,
        nullable=False,
    )

    # ============================================================
    # TRAÇABILITÉ
    # ============================================================

    updated_by: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )

    # ============================================================
    # RELATION
    # ============================================================

    updater: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "PlatformSetting.updated_by",
        },
    )