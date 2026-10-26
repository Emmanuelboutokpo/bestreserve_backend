from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlalchemy import Index, text
from sqlmodel import Field, Relationship
from app.models.base import UUIDMixin, TimestampMixin
from app.models.enums import LocationType

if TYPE_CHECKING:
    from app.models.establishment import Establishment


class Location(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "locations"
    
    __table_args__ = (
        Index("idx_locations_type", "type"),
        Index("idx_locations_parent", "parent_id"),
        Index("idx_locations_country", "country_code"),
        Index("idx_locations_active", "is_active"),
        Index(
            "uq_locations_root_country_code",
            "country_code",
            unique=True,
            postgresql_where=text(
                "type = 'COUNTRY' AND parent_id IS NULL"
            ),  # ✅ retiré "AND deleted_at IS NULL"
            sqlite_where=text(
                "type = 'COUNTRY' AND parent_id IS NULL"
            ),  # ✅ retiré "AND deleted_at IS NULL"
        ),
    )

    name: str = Field(max_length=150, nullable=False, index=True)
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