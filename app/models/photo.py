# app/models/photo.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.establishment import Establishment


class Photo(UUIDMixin, TimestampMixin, table=True):
    """
    Photo appartenant à un établissement.
    """

    __tablename__ = "photos"

    # ============================================================
    # ETABLISSEMENT
    # ============================================================

    establishment_id: UUID = Field(
        foreign_key="establishments.id",
        nullable=False,
        index=True,
    )

    # ============================================================
    # FICHIER
    # ============================================================

    url: str = Field(
        max_length=1000,
        nullable=False,
    )
 
    # ============================================================
    # AFFICHAGE
    # ============================================================

    is_cover: bool = Field(
        default=False,
        nullable=False,
    )

    # ============================================================
    # RELATION
    # ============================================================

    establishment: "Establishment" = Relationship(
        back_populates="photos",
    )