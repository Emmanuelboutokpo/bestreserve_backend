# app/models/photo.py

from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.establishment import Establishment


class Photo(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):
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

    thumbnail_url: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    public_id: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    # ============================================================
    # INFORMATIONS IMAGE
    # ============================================================

    width: Optional[int] = Field(
        default=None,
    )

    height: Optional[int] = Field(
        default=None,
    )

    alt_text: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    # ============================================================
    # AFFICHAGE
    # ============================================================

    is_cover: bool = Field(
        default=False,
        nullable=False,
    )

    display_order: int = Field(
        default=0,
        nullable=False,
    )

    # ============================================================
    # RELATION
    # ============================================================

    establishment: "Establishment" = Relationship(
        back_populates="photos",
    )