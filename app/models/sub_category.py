# app/models/sub_category.py

from typing import TYPE_CHECKING, Optional
from uuid import UUID
from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.establishment import Establishment


class SubCategory(UUIDMixin, TimestampMixin, table=True):

    __tablename__ = "sub_categories"

    __table_args__ = (
        Index(
            "idx_subcategories_category",
            "category_id",
        ),
    )  

    # ============================================================
    # RELATION CATEGORY
    # ============================================================

    category_id: UUID = Field(
        foreign_key="categories.id",
        nullable=False,
    )

    # ============================================================
    # INFORMATIONS
    # ============================================================

    name: str = Field(
        max_length=100,
        nullable=False,
    )

    icon: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    # ============================================================
    # RELATIONS
    # ============================================================

    category: "Category" = Relationship(
        back_populates="subcategories",
    )

    establishments: list["Establishment"] = Relationship(
        back_populates="subcategory",
    )