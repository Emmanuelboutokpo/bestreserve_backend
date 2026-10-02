# app/models/category.py

from typing import List, TYPE_CHECKING, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from app.models.sub_category import SubCategory
    from app.models.establishment import Establishment


class Category(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):
  
    __tablename__ = "categories"

    __table_args__ = (
        Index(
            "idx_categories_slug",
            "slug",
            unique=True,
        ),
    )

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=100,
        nullable=False,
    )

    slug: str = Field(
        max_length=120,
        nullable=False,
    )

    icon: Optional[str] = Field(
        default=None,
        max_length=100,
    )
   
    # ============================================================
    # RELATIONS
    # ============================================================

    subcategories: List["SubCategory"] = Relationship(
        back_populates="category",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    establishments: List["Establishment"] = Relationship(
        back_populates="category",
    )