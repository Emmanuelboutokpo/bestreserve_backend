# app/models/category.py

from typing import List, TYPE_CHECKING, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship

from app.models.base import (
    UUIDMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.sub_category import SubCategory
    from app.models.establishment import Establishment


class Category(UUIDMixin, TimestampMixin, table=True):
  
    __tablename__ = "categories"

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

    subcategories: List["SubCategory"] = Relationship(
        back_populates="category",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
        },
    )

    establishments: List["Establishment"] = Relationship(
        back_populates="category",
    )