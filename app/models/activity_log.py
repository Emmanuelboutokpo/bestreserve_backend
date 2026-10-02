# app/models/activity_log.py

from datetime import datetime
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


class ActivityLog(
    UUIDMixin,
    TimestampMixin,
    table=True,
):
    """
    Journal des actions importantes effectuées sur la plateforme.

    Exemple :
        - Connexion
        - Création d'établissement
        - Validation
        - Suppression
        - Modification d'une réservation
    """

    __tablename__ = "activity_logs"

    __table_args__ = (
        Index(
            "idx_activity_logs_user",
            "user_id",
        ),
        Index(
            "idx_activity_logs_action",
            "action",
        ),
        Index(
            "idx_activity_logs_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "idx_activity_logs_created",
            "created_at",
        ),
    )

    # ============================================================
    # ACTEUR
    # ============================================================

    user_id: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
    )

    # ============================================================
    # ACTION
    # ============================================================

    action: str = Field(
        max_length=100,
        nullable=False,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    # ============================================================
    # ENTITE CONCERNEE
    # ============================================================

    entity_type: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    entity_id: Optional[UUID] = Field(
        default=None,
    )

    # ============================================================
    # CONTEXTE
    # ============================================================

    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
    )

    user_agent: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    metadata_json: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(
            JSON,
            nullable=True,
        ),
    )

    # ============================================================
    # RELATION
    # ============================================================

    user: Optional["User"] = Relationship(
        back_populates="activity_logs",
    )