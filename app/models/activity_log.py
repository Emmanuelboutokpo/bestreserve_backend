from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Index, JSON
from sqlmodel import Field, Relationship

from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ActivityLog(UUIDMixin, TimestampMixin, table=True):
    """
    Journal des actions importantes effectuées sur BestRev.

    Exemples :
    - Connexion et déconnexion
    - Création ou modification d'un établissement
    - Validation ou rejet d'un établissement
    - Création d'une réservation
    - Confirmation, refus ou annulation d'une réservation
    - Enregistrement d'un paiement ou d'un remboursement

    Les journaux doivent être conservés pour les besoins d'audit.
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
        nullable=True,
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
        nullable=True,
    )

    # ============================================================
    # ENTITÉ CONCERNÉE
    # ============================================================

    entity_type: Optional[str] = Field(
        default=None,
        max_length=100,
        nullable=True,
    )

    entity_id: Optional[UUID] = Field(
        default=None,
        nullable=True,
    )

    # ============================================================
    # CONTEXTE DE LA REQUÊTE
    # ============================================================

    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        nullable=True,
    )

    user_agent: Optional[str] = Field(
        default=None,
        max_length=1000,
        nullable=True,
    )

    # ============================================================
    # MÉTADONNÉES
    # ============================================================

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