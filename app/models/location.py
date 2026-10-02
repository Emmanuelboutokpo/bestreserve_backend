from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, Relationship, Index
from app.models.base import UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import LocationType

if TYPE_CHECKING:
    from app.models.establishment import Establishment


class Location(UUIDMixin, TimestampMixin, SoftDeleteMixin, table=True):
    __tablename__ = "locations"
    __table_args__ = (
        Index("idx_locations_type", "type"),
        Index("idx_locations_parent", "parent_id"),
        Index("idx_locations_country", "country_code"),
        Index("idx_locations_slug", "slug", unique=True),
        Index("idx_locations_active", "is_active"),
    )

    name: str = Field(max_length=150, nullable=False, index=True)
    slug: str = Field(max_length=180, nullable=False)
    type: LocationType = Field(nullable=False)
    parent_id: Optional[UUID] = Field(default=None, foreign_key="locations.id")
    country_code: str = Field(max_length=2, nullable=False)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    timezone: Optional[str] = Field(default=None, max_length=50)
    population: Optional[int] = Field(default=None)
    metadata_json: Optional[str] = Field(default=None, max_length=5000)
    is_active: bool = Field(default=True)

    # Relations
    parent: Optional["Location"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Location.id"},
    )
    children: List["Location"] = Relationship(back_populates="parent")
    establishments: List["Establishment"] = Relationship(back_populates="location")