from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.establishment import EstablishmentPublic

class FavoritePublic(BaseModel):
    id: UUID
    establishment_id: UUID
    note: str | None
    created_at: datetime
    establishment: EstablishmentPublic


class FavoritePage(BaseModel):
    items: list[FavoritePublic]
    total: int
    limit: int
    offset: int
